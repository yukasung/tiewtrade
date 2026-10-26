"""Optional measurement import in the dedicated supervised worker image.

Mount this directory as PYTHONPATH and /evidence as a test output directory.
It records attempts without replacing claims, scans, publications or retries.
The explicit R2-7 fixture pins calculation bounds while
``/evidence/exact-clock-enabled`` exists, preserving the real snapshot timestamp.
"""

import asyncio
import json
import os
from contextvars import ContextVar
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import monotonic
from typing import Literal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

import tiewtrade.infra.indicators.scan as scan
import tiewtrade.services.indicator_builder.attempt as attempt
from tiewtrade.core.market_data import CandleWindow, align_ceil, align_floor, retention_cutoff
from tiewtrade.infra.indicators.claims import BuildClaim
from tiewtrade.infra.indicators.pinned import PinnedIndicatorWriter
from tiewtrade.infra.indicators.session import IndicatorSourceSession
from tiewtrade.infra.indicators.staging import StagingSnapshot
from tiewtrade.infra.indicators.staging import capture_snapshot as original_capture_snapshot

CLAIM = PinnedIndicatorWriter.claim
ATTEMPT = attempt.run_attempt
CAPTURE_SNAPSHOT = original_capture_snapshot
CURRENT: ContextVar[BuildClaim | None] = ContextVar("measured_claim", default=None)
EXACT_CLOCK_MARKER = Path("/evidence/exact-clock-enabled")


def memory(field: str) -> int:
    total = 0
    for pid in (os.getpid(), os.getppid()):
        total += next(
            int(line.split()[1]) * 1024
            for line in Path(f"/proc/{pid}/status").read_text().splitlines()
            if line.startswith(field + ":")
        )
    return total


async def claim(self: PinnedIndicatorWriter, owner: UUID) -> BuildClaim | None:
    result = await CLAIM(self, owner)
    CURRENT.set(result)
    return result


async def capture_snapshot(session: IndicatorSourceSession, claim: BuildClaim) -> StagingSnapshot:
    snapshot = await CAPTURE_SNAPSHOT(session, claim)
    if not EXACT_CLOCK_MARKER.exists():
        return snapshot
    boundary = datetime.fromisoformat(EXACT_CLOCK_MARKER.read_text(encoding="ascii"))
    return replace(
        snapshot,
        calculation=CandleWindow(
            align_ceil(retention_cutoff(boundary, claim.timeframe), claim.timeframe),
            align_floor(boundary, claim.timeframe),
        ),
    )


async def run_attempt(
    engine: AsyncEngine,
    owner: UUID,
    *,
    connection_mode: Literal["direct", "session", "transaction", "statement"] = "direct",
    scheduled: bool = False,
) -> attempt.AttemptResult:
    token = CURRENT.set(None)
    baseline = memory("VmRSS")
    started = previous = monotonic()
    lag = 0.0

    async def watch() -> None:
        nonlocal previous, lag
        while True:
            await asyncio.sleep(0.01)
            now = monotonic()
            lag = max(lag, now - previous - 0.01)
            previous = now

    watcher = asyncio.create_task(watch())
    result: attempt.AttemptResult | None = None
    try:
        result = await ATTEMPT(engine, owner, connection_mode=connection_mode, scheduled=scheduled)
        return result
    finally:
        elapsed = monotonic() - started
        lag = max(lag, monotonic() - previous - 0.01)
        watcher.cancel()
        await asyncio.gather(watcher, return_exceptions=True)
        current = CURRENT.get()
        if current is not None:
            with Path("/evidence/worker-attempts.jsonl").open("a", encoding="utf-8") as output:
                output.write(
                    json.dumps(
                        {
                            "base": current.base,
                            "job_id": str(current.job_id),
                            "timeframe": current.timeframe.value,
                            "generation_id": str(current.generation_id),
                            "claimed_at": str(current.attempt_deadline - timedelta(seconds=120)),
                            "attempt_deadline": str(current.attempt_deadline),
                            "finished_at": str(datetime.now(UTC)),
                            "dispatch_round": current.dispatch_round,
                            "fence": current.fence,
                            "owner": str(owner),
                            "status": result.status.value
                            if result is not None
                            else "CANCELLED_OR_FAILED",
                            "reason": result.reason.value
                            if result is not None and result.reason
                            else None,
                            "seconds_including_acquire_cleanup": elapsed,
                            "lag_seconds": lag,
                            "rss_delta_upper_bytes": max(0, memory("VmHWM") - baseline),
                        }
                    )
                    + "\n"
                )
        CURRENT.reset(token)


if os.environ.get("TIEWTRADE_INDICATOR_OWNER"):
    PinnedIndicatorWriter.claim = claim  # type: ignore[method-assign]
    # Patch the scan module's imported binding, not the production function.
    scan.capture_snapshot = capture_snapshot  # type: ignore[attr-defined]
    attempt.run_attempt = run_attempt
