"""Browser-independent durable loss-limit monitor; never owns venue credentials."""

import argparse
import asyncio
import logging
import os
from contextlib import AsyncExitStack
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.infra.db.session import (
    PresentedSession,
    ScanSession,
    presented_session,
    scan_session_bypassing_rls,
)
from tiewtrade.services.engine.kill_switch import (
    run_platform_discovery_round,
    run_stop_request_round,
)
from tiewtrade.services.engine.risk_limit import (
    _evaluate_monitor_owner,
    _scan_monitor_candidates,
    run_risk_request_round,
    run_risk_stop_round,
)

# R21 did not meet the SLA; retain the four-slot runtime.
MONITOR_CONCURRENCY = 4
STOP_ACTIVE_POLL_SECONDS = 0.02
STOP_IDLE_MAX_SECONDS = 0.25
STOP_IDLE_MAX_ROUNDS = 5


def stop_poll_delay(idle_rounds: int) -> float:
    """Return the approved bounded idle cadence; active rounds pass zero."""
    if type(idle_rounds) is not int or idle_rounds < 0:
        raise ValueError("idle stop rounds must be a nonnegative integer")
    if idle_rounds == 0:
        return STOP_ACTIVE_POLL_SECONDS
    if idle_rounds >= STOP_IDLE_MAX_ROUNDS:
        return STOP_IDLE_MAX_SECONDS
    return STOP_ACTIVE_POLL_SECONDS * (1 << (idle_rounds - 1))


async def _serve_stop_rounds(engine: AsyncEngine, scan: AsyncEngine) -> None:
    cursor = None
    idle_rounds = 0
    while True:
        requests = await run_stop_request_round(engine=engine, scan_engine=scan)
        platform = await run_platform_discovery_round(engine=engine, scan_engine=scan)
        stops = await run_risk_stop_round(engine=engine, scan_engine=scan, after_owner=cursor)
        cursor = stops.next_owner or cursor
        active = any(
            (
                requests.processed,
                requests.deferred,
                platform.discovered,
                platform.deferred,
                platform.active,
                stops.processed,
                stops.deferred,
                stops.skipped,
            )
        )
        idle_rounds = 0 if active else min(idle_rounds + 1, STOP_IDLE_MAX_ROUNDS)
        await asyncio.sleep(stop_poll_delay(idle_rounds))


async def _warm_pool(engine: AsyncEngine, role: DatabaseRole, slots: int) -> None:
    """Establish the declared bounded capacity before monitor latency is measured.

    Hold each connection until all slots are ready. These role-checked reads do
    not assume an owner or change financial, risk or protocol state.
    """
    async with AsyncExitStack() as stack:
        for _ in range(slots):
            session: ScanSession | PresentedSession
            if role is DatabaseRole.ENGINE_SCAN:
                session = await stack.enter_async_context(scan_session_bypassing_rls(engine))
            else:
                session = await stack.enter_async_context(presented_session(engine, role=role))
            await session.execute("SELECT 1")


async def _serve_monitor(engine: AsyncEngine, scan: AsyncEngine) -> None:
    """Refill four evaluation slots without queuing an entire owner page.

    The cursor and active map are disposable scheduling hints. PostgreSQL owner
    locks and transactions remain authoritative across processes and restarts.
    """
    cursor: UUID | None = None
    active: dict[UUID, asyncio.Task[str]] = {}
    try:
        while True:
            for owner, task in list(active.items()):
                if task.done():
                    task.result()  # Propagate unexpected failures to serve's TaskGroup.
                    del active[owner]
            free = MONITOR_CONCURRENCY - len(active)
            if not free:
                await asyncio.wait(active.values(), return_when=asyncio.FIRST_COMPLETED)
                continue
            candidates = await _scan_monitor_candidates(
                scan, limit=free, after_owner=cursor, excluded=tuple(active)
            )
            if not candidates:
                await asyncio.sleep(0.02)
                continue
            cursor = UUID(str(candidates[-1].user_id))
            for row in sorted(candidates, key=lambda row: (row.due_at is not None, row.due_at)):
                owner = UUID(str(row.user_id))
                active[owner] = asyncio.create_task(_evaluate_monitor_owner(engine, owner))
    finally:
        for task in active.values():
            task.cancel()
        await asyncio.gather(*active.values(), return_exceptions=True)


async def serve() -> None:
    monitor_engine = create_engine_for(
        DatabaseRole.ENGINE, pool_size=MONITOR_CONCURRENCY, max_overflow=0, pool_timeout=0.1
    )
    request_engine = create_engine_for(
        DatabaseRole.ENGINE, pool_size=1, max_overflow=0, pool_timeout=0.1
    )
    stop_engine = create_engine_for(
        DatabaseRole.ENGINE, pool_size=2, max_overflow=0, pool_timeout=0.1
    )
    scan = create_engine_for(
        DatabaseRole.ENGINE_SCAN, pool_size=3, max_overflow=0, pool_timeout=0.1
    )
    worker = f"risk-limit:{os.getpid()}"

    async def requests() -> None:
        while True:
            await run_risk_request_round(engine=request_engine, scan_engine=scan, worker=worker)
            await asyncio.sleep(0.02)

    try:
        await _warm_pool(monitor_engine, DatabaseRole.ENGINE, MONITOR_CONCURRENCY)
        await _warm_pool(request_engine, DatabaseRole.ENGINE, 1)
        await _warm_pool(stop_engine, DatabaseRole.ENGINE, 2)
        await _warm_pool(scan, DatabaseRole.ENGINE_SCAN, 3)
        async with asyncio.TaskGroup() as group:
            group.create_task(_serve_monitor(monitor_engine, scan))
            group.create_task(requests())
            group.create_task(_serve_stop_rounds(stop_engine, scan))
    finally:
        await monitor_engine.dispose()
        await request_engine.dispose()
        await stop_engine.dispose()
        await scan.dispose()


async def health() -> int:
    """Read-only DB/schema probe; admission readiness is the owner's evidence, not this probe."""
    engine = create_engine_for(DatabaseRole.ENGINE, pool_size=1, max_overflow=0, pool_timeout=0.1)
    scan = create_engine_for(
        DatabaseRole.ENGINE_SCAN, pool_size=1, max_overflow=0, pool_timeout=0.1
    )
    try:
        async with presented_session(engine, role=DatabaseRole.ENGINE) as session:
            await session.execute("SET LOCAL statement_timeout='500ms'")
            await session.execute(
                "SELECT publication_enabled,financial_enabled,admission_enabled "
                "FROM risk_protocol_control"
            )
        async with scan_session_bypassing_rls(scan) as session:
            await session.execute("SET LOCAL statement_timeout='500ms'")
            await session.execute("SELECT user_id,mode,due_at FROM risk_owner_state LIMIT 1")
        return 0
    except Exception:
        logging.getLogger(__name__).warning("risk worker database/schema probe unavailable")
        return 1
    finally:
        await engine.dispose()
        await scan.dispose()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("run", "health"), default="run", nargs="?")
    options = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    if options.action == "health":
        return asyncio.run(health())
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
