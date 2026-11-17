"""LEASE-02 bounded observer of the actual publisher; never delay or recover it."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter, deque
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from time import monotonic
from typing import Any
from unittest.mock import patch

from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market import profile_internal as internal
from tests.infra.execution_market import profile_workload as workload
from tests.infra.execution_market.profile_publisher_lease import (
    LeaseTrace,
    Publication,
    state_snapshot,
)
from tiewtrade.infra.db import DatabaseRole, create_engine_for


def validate_options(args: argparse.Namespace) -> None:
    timing = getattr(args, "publisher_fence_timing", False)
    short_timing = (
        timing is True
        and getattr(args, "phase", None) == "SMOKE"
        and getattr(args, "acceptance_profile", None) == internal.NAME
        and getattr(args, "publisher_lease_observer", False) is True
        and getattr(args, "publisher_fence_observer", False) is True
        and getattr(args, "publisher_fence_fail_fast", False) is True
        and getattr(args, "publisher_clock_recovery", False) is False
    )
    prefix = getattr(args, "observer_w3_prefix", False)
    prefix_timing = (
        prefix is True
        and timing is True
        and getattr(args, "phase", None) == "W3"
        and getattr(args, "acceptance_profile", None) == internal.NAME
        and all(
            getattr(args, name, False) is True
            for name in (
                "publisher_lease_observer",
                "publisher_fence_observer",
                "publisher_fence_fail_fast",
                "publisher_clock_recovery",
                "observer_scheduled_samples",
            )
        )
    )
    if prefix and not prefix_timing:
        raise ValueError("prefix requires explicit observed internal20 W3 timing")
    if getattr(args, "observer_scheduled_samples", False) and not (short_timing or prefix_timing):
        raise ValueError("scheduled samples require approved timing profile")
    if timing and not (short_timing or prefix_timing):
        raise ValueError("fence timing requires approved fail-fast profile")
    if (
        getattr(args, "publisher_fence_fail_fast", False)
        and not short_timing
        and not (
            getattr(args, "phase", None) == "W3"
            and getattr(args, "acceptance_profile", None) == internal.NAME
            and getattr(args, "publisher_lease_observer", False) is True
            and getattr(args, "publisher_fence_observer", False) is True
            and getattr(args, "publisher_clock_recovery", False) is True
        )
    ):
        raise ValueError("fence fail-fast requires explicit observed internal20 W3")
    if getattr(args, "publisher_fence_observer", False) and not getattr(
        args, "publisher_lease_observer", False
    ):
        raise ValueError("fence observer requires lease observer")
    if not getattr(args, "publisher_lease_observer", False):
        return
    phase = getattr(args, "phase", None)
    recovery = getattr(args, "publisher_clock_recovery", False)
    long_run = (
        phase == "W3"
        and recovery is True
        and getattr(args, "publisher_fence_observer", False) is True
    )
    if (
        getattr(args, "acceptance_profile", None) != internal.NAME
        or not ((phase == "SMOKE" and not recovery) or long_run)
        or any(
            getattr(args, name, False)
            for name in (
                "worker_only",
                "diagnostics",
                "failure_timeline",
                "controlled_delay",
            )
        )
    ):
        raise ValueError(
            "publisher lease observer requires internal20 SMOKE or explicit observed W3"
        )


class LoadLeaseObserver:
    def __init__(
        self,
        output: Path,
        readiness_status: dict[str, bool],
        *,
        fence_observer: bool = False,
        fence_fail_fast: bool = False,
        fence_timing: bool = False,
        scheduled_samples: bool = False,
        w3_prefix: bool = False,
    ) -> None:
        self.output = output
        self.readiness_status = readiness_status
        self.actor: asyncio.Task[Any] | None = None
        self.recent: deque[dict[str, Any]] = deque(maxlen=64)
        self.slowest: list[dict[str, Any]] = []
        self.failed: dict[str, Any] | None = None
        self.outcomes: Counter[str] = Counter()
        self.guard_calls = 0
        self.evidence_failed = False
        self.witness: dict[str, Any] | None = None
        self.publisher_error_type: str | None = None
        self.witness_engine: AsyncEngine | None = None
        if w3_prefix and not scheduled_samples:
            raise ValueError("prefix requires scheduled samples")
        self.w3_prefix = w3_prefix
        self.scheduled_enabled = scheduled_samples
        self.scheduled: Any = None
        if scheduled_samples and not fence_timing:
            raise ValueError("scheduled samples require fence timing")
        self.fence_timing = fence_timing
        if fence_timing and not (fence_observer and fence_fail_fast):
            raise ValueError("fence timing requires observer and fail-fast")
        self.fence_enabled = fence_observer
        self.fence: Any = None
        self.active_trace: LeaseTrace | None = None
        if fence_fail_fast and not fence_observer:
            raise ValueError("fence fail-fast requires fence observer")
        self.failure: asyncio.Future[None] | None = (
            asyncio.get_running_loop().create_future() if fence_fail_fast else None
        )
        self.failure_reason: str | None = None

    def measurement_started(self, started: float) -> None:
        if self.scheduled_enabled:
            if self.scheduled is None:
                raise ValueError("scheduled observer missing at measurement start")
            self.scheduled.start(started)
            self.scheduled.task.add_done_callback(self.scheduled_finished)

    def scheduled_finished(self, task: asyncio.Task[None]) -> None:
        if task.cancelled() or task.exception() is not None:
            self.signal_failure("SCHEDULED_SAMPLER_EVIDENCE_LOST")

    def signal_failure(self, reason: str) -> None:
        if self.failure is not None and not self.failure.done():
            self.failure_reason = reason
            self.failure.set_result(None)

    def sampler_finished(self, task: asyncio.Task[None]) -> None:
        if task.cancelled():
            unexpected = self.fence is not None and not self.fence.stop.is_set()
        else:
            unexpected = task.exception() is not None
        if self.fence is not None and (
            unexpected or self.fence.errors or not self.fence.stop.is_set()
        ):
            self.signal_failure("SAMPLER_EVIDENCE_LOST")

    def flush_failure(self) -> None:
        if self.failure is None or self.failure_reason is None:
            return
        workload.save(
            self.output / "publisher-fence-failure.json",
            {
                "revision": "NC_F17_OBS_03" if self.fence_timing else "NC_F17_W3_OBS_01",
                "status": "INCOMPLETE",
                "reason": self.failure_reason,
                "fence_observation": self.fence.report() if self.fence is not None else None,
                "scheduled_observation": self.scheduled.report()
                if self.scheduled is not None
                else None,
                "publication_counts": dict(self.outcomes),
                "publisher_error_type": self.publisher_error_type,
            },
        )

    def record(self, row: dict[str, Any]) -> None:
        if asyncio.current_task() is not self.actor:
            raise ValueError("foreign lease observation")
        self.outcomes[row["outcome"]] += 1
        self.guard_calls += row.get("guard_calls", 0)
        self.recent.append(row)
        self.slowest.append(row)
        self.slowest.sort(key=lambda value: value["elapsed_seconds"], reverse=True)
        del self.slowest[16:]
        if row["outcome"] != "RETURNED":
            if self.failed is not None:
                raise ValueError("publisher continued after a failed publication")
            self.failed = row

    async def failure_witness(self) -> None:
        if self.witness_engine is None:
            raise ValueError("lease witness engine missing")
        async with asyncio.timeout(5):
            self.witness = await state_snapshot(self.witness_engine)

    @contextmanager
    def observe(self) -> Iterator[None]:
        original_publisher = workload.market_publisher
        original_publish = workload.publish_market

        async def publisher(*args: Any, **kwargs: Any) -> Any:
            if self.actor is not None:
                raise ValueError("lease observer permits one publisher task")
            self.actor = asyncio.current_task()
            try:
                self.witness_engine = create_engine_for(
                    DatabaseRole.MARKET_DATA, pool_size=1, max_overflow=0, pool_timeout=0.5
                )
                if self.fence_enabled:
                    from tests.infra.execution_market.profile_publisher_fence import (
                        FenceObservation,
                    )

                    self.fence = FenceObservation(
                        lambda: self.active_trace, timing=self.fence_timing
                    )
                    self.fence.start()
                    if self.failure is not None:
                        self.fence.task.add_done_callback(self.sampler_finished)
                if self.scheduled_enabled:
                    from tests.infra.execution_market.profile_observer_scheduled import (
                        ScheduledObservation,
                    )

                    self.scheduled = ScheduledObservation(w3_prefix=self.w3_prefix)
                return await original_publisher(*args, **kwargs)
            except BaseException as error:
                self.publisher_error_type = type(error).__name__
                try:
                    await self.failure_witness()
                except BaseException as witness_error:
                    self.evidence_failed = True
                    error.add_note(f"lease witness failed: {type(witness_error).__name__}")
                raise
            finally:
                primary = sys.exception()
                cleanup_error: BaseException | None = None
                if self.scheduled is not None:
                    try:
                        await workload.finish_observed_cleanup(self.scheduled.close(), None)
                    except BaseException as scheduled_error:
                        self.evidence_failed = True
                        if primary is None:
                            cleanup_error = scheduled_error
                        else:
                            primary.add_note(
                                f"scheduled cleanup failed: {type(scheduled_error).__name__}"
                            )
                if self.fence is not None:
                    try:
                        await self.fence.close()
                    except BaseException as fence_error:
                        self.evidence_failed = True
                        if primary is None:
                            cleanup_error = fence_error
                        else:
                            primary.add_note(
                                f"fence observer cleanup failed: {type(fence_error).__name__}"
                            )
                if self.witness_engine is not None:
                    try:
                        await self.witness_engine.dispose()
                    except BaseException as dispose_error:
                        self.evidence_failed = True
                        if primary is None:
                            cleanup_error = cleanup_error or dispose_error
                        else:
                            primary.add_note(
                                f"lease witness dispose failed: {type(dispose_error).__name__}"
                            )
                if primary is None and cleanup_error is not None:
                    raise cleanup_error

        async def publish(*args: Any, **kwargs: Any) -> Any:
            if asyncio.current_task() is not self.actor:
                return await original_publish(*args, **kwargs)
            publication = Publication(
                kwargs["trade_id"],
                kwargs.get("update_price", True),
                kwargs.get("heartbeat_per_book", False),
            )
            started = monotonic()
            outcome = "UNCONFIRMED"

            def retain(value: dict[str, Any]) -> None:
                self.record({**value, "outcome": outcome, "elapsed_seconds": monotonic() - started})

            trace = LeaseTrace(
                None, self.output / "unused.json", publication=publication, sink=retain
            )
            self.active_trace = trace
            try:
                with trace.observe(args[0]):
                    try:
                        result = await original_publish(*args, **kwargs)
                    except BaseException as error:
                        outcome = type(error).__name__
                        raise
                    outcome = "RETURNED"
                    return result
            finally:
                self.active_trace = None
                if not trace.evidence_ok:
                    self.evidence_failed = True
                    self.signal_failure("PUBLICATION_EVIDENCE_LOST")

        primary: BaseException | None = None
        try:
            with (
                patch.object(workload, "market_publisher", publisher),
                patch.object(workload, "publish_market", publish),
            ):
                yield
        except BaseException as error:
            primary = error
            raise
        finally:
            try:
                self.finalize_evidence()
            except (OSError, ValueError, KeyError, TypeError) as error:
                # Finalization failure must not leave an apparently accepted workload result.
                result_path = self.output / "result.json"
                try:
                    if result_path.exists():
                        result = json.loads(result_path.read_text())
                        result.update(
                            status=(
                                "FAILED"
                                if self.failure is not None and result.get("status") == "FAILED"
                                else "INCOMPLETE"
                            ),
                            diagnostic_only=True,
                            lease_evidence_error_type=type(error).__name__,
                        )
                        workload.save(result_path, result)
                except (OSError, ValueError, TypeError) as save_error:
                    error.add_note(f"lease result update failed: {type(save_error).__name__}")
                if primary is None:
                    raise
                primary.add_note(f"lease observer evidence failed: {type(error).__name__}")
            finally:
                if self.failure is not None and not self.failure.done():
                    self.failure.cancel()

    def finalize_evidence(self) -> None:
        """Attempt both opt-in receipts while retaining the first finalization failure."""
        # Each opt-in receipt gets an independent attempt, including on first publication.
        evidence_error: Exception | None = None
        for finalize in (self.flush_failure, self.flush):
            try:
                finalize()
            except (OSError, ValueError, KeyError, TypeError) as error:
                if self.failure is None:
                    raise
                if evidence_error is None:
                    evidence_error = error
                else:
                    evidence_error.add_note(
                        f"lease summary evidence failed: {type(error).__name__}"
                    )
        if evidence_error is not None:
            raise evidence_error
        if self.failure_reason is not None:
            raise ValueError("fence fail-fast evidence incomplete")

    def flush(self) -> None:
        scheduled_incomplete = self.scheduled_enabled and (
            self.scheduled is None or self.scheduled.report()["status"] != "RECORDED"
        )
        fence_incomplete = self.fence_enabled and (
            self.fence is None or bool(self.fence.errors) or not self.fence.report()["task_joined"]
        )
        if self.fence_timing and self.fence is not None:
            timing = self.fence.report().get("timing", {})
            fence_incomplete = fence_incomplete or (
                timing.get("status") not in {"RECORDED", "NO_TRIGGER"}
                or timing.get("lag_task_joined") is not True
                or timing.get("lag_task_completed") is not True
                or timing.get("counts", {}).get("RETURNED", 0) != self.fence.total
            )
        if self.evidence_failed or self.readiness_status["write_failed"] or not self.outcomes:
            raise ValueError("publisher lease evidence incomplete")
        readiness = json.loads((self.output / "publisher-readiness.json").read_text())
        checks = readiness["checks"]
        total_checks = readiness["total_checks"]
        if (
            readiness["scope"] != "parent publish_market readiness guards only"
            or not isinstance(checks, list)
            or type(total_checks) is not int
            or total_checks < 0
            or len(checks) != min(total_checks, 64)
            or readiness["discarded_earlier_checks"] != max(0, total_checks - 64)
            or not isinstance(readiness["flush_reason"], str)
        ):
            raise ValueError("publisher readiness evidence incomplete")
        count = sum(self.outcomes.values())
        if total_checks != self.guard_calls:
            raise ValueError("publisher lease/readiness counts differ")
        report = {
            "revision": "NC_F17_LEASE_02",
            "fence_observation": self.fence.report() if self.fence is not None else None,
            "scheduled_observation": self.scheduled.report()
            if self.scheduled is not None
            else None,
            "diagnostic_only": True,
            "status": "RECORDED_FAILURE" if self.failed is not None else "RECORDED",
            "counts": dict(self.outcomes),
            "total": count,
            "guard_calls": self.guard_calls,
            "recent_limit": 64,
            "slowest_limit": 16,
            "recent": list(self.recent),
            "slowest": self.slowest,
            "failed": self.failed,
            "publisher_error_type": self.publisher_error_type,
            "independent_failure_witness": self.witness,
            "extra_precommit_probes_per_publication_maximum": 1,
        }
        path = self.output / "publisher-lease.json"
        workload.save(path, report)
        if json.loads(path.read_text()) != json.loads(json.dumps(report, default=str)):
            raise ValueError("publisher lease evidence differs")
        if fence_incomplete or scheduled_incomplete:
            raise ValueError("fence observer evidence incomplete")
