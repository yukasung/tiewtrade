"""OBS-02 isolated fixture collector; no workload or publisher replacement."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from time import monotonic
from typing import Any, cast
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market import profile_internal as internal
from tests.infra.execution_market.profile_observer_timing import (
    PHASES as PHASES,
)
from tests.infra.execution_market.profile_observer_timing import (
    CaptureTiming as CaptureTiming,
)
from tests.infra.execution_market.profile_observer_timing import (
    LoopLag as LoopLag,
)
from tests.infra.execution_market.profile_observer_timing import (
    TimedEngine as TimedEngine,
)
from tests.infra.execution_market.profile_publisher_fence import FenceObservation
from tests.infra.execution_market.profile_replay_reads import save_partial_result
from tests.infra.execution_market.profile_workload import finish_observed_cleanup
from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.infra.db.session import market_data_session, user_session

GROUPS = ("cold", "reused", "known_blocker")


async def capture(
    observer: FenceObservation, statement: dict[str, Any], record: dict[str, Any]
) -> dict[str, Any]:
    if observer.task is not None or isinstance(cast(Any, observer.engine), TimedEngine):
        raise ValueError("observer must be idle and exclusively owned")
    timing = CaptureTiming()
    record.update(spans=timing.spans, outcome="INCOMPLETE", fixture_only=True)
    engine = observer.engine
    observer.engine = cast(AsyncEngine, TimedEngine(engine, timing))
    try:
        result = await observer.sample(statement)  # Original, once, in this same task.
        timing.validate()
        if result.get("activity_row_count") is None or result.get("locks_row_count") is None:
            raise ValueError("observer rows incomplete")
        record.update(outcome="RETURNED", observation=result)
        return result
    except BaseException as error:
        record.update(outcome=type(error).__name__, observation=observer.failed_observation)
        raise
    finally:
        observer.engine = engine


@asynccontextmanager
async def fixture_statement(blocked: bool) -> AsyncIterator[tuple[dict[str, Any], int | None]]:
    """Reuse the real shared-holder/exclusive-waiter fence test; never place orders."""
    internal.guard_database(dict(os.environ))
    financial = create_engine_for(DatabaseRole.ENGINE)
    publisher = create_engine_for(DatabaseRole.MARKET_DATA)
    task: asyncio.Task[None] | None = None
    primary: BaseException | None = None
    try:
        if not blocked:
            async with market_data_session(publisher) as session:
                pid = (await session.execute("SELECT pg_backend_pid()")).scalar_one()
                yield {"backend_pid": pid, "stage": "fixture_idle", "started": monotonic()}, None
        else:
            entered = asyncio.Event()
            statement: dict[str, Any] = {"stage": "fixture_waiter", "started": monotonic()}
            async with user_session(financial, uuid4(), role=DatabaseRole.ENGINE) as holder_session:
                holder = (await holder_session.execute("SELECT pg_backend_pid()")).scalar_one()
                await holder_session.execute("SELECT risk_financial_fence()")

                async def wait() -> None:
                    async with market_data_session(publisher) as current:
                        statement["backend_pid"] = (
                            await current.execute("SELECT pg_backend_pid()")
                        ).scalar_one()
                        entered.set()
                        await current.execute("SELECT risk_publication_fence()")

                task = asyncio.create_task(wait())
                await asyncio.wait_for(entered.wait(), 2)
                # Establish the fixture once, independently of measured captures.
                async with publisher.connect() as probe:
                    async with asyncio.timeout(2):
                        while True:
                            blockers: list[int] = (
                                await probe.execute(
                                    text("SELECT pg_blocking_pids(:pid)"),
                                    {"pid": statement["backend_pid"]},
                                )
                            ).scalar_one()
                            if holder in blockers:
                                break
                            if task.done():
                                task.result()
                                raise ValueError("fixture waiter finished before observation")
                            await asyncio.sleep(0.02)
                yield statement, holder
            await asyncio.wait_for(task, 2)
    except BaseException as error:
        primary = error
        raise
    finally:

        async def cleanup() -> None:
            try:
                if task is not None:
                    if not task.done():
                        task.cancel()
                    results = await asyncio.gather(task, return_exceptions=True)
                    error = results[0]
                    if isinstance(error, BaseException) and not isinstance(
                        error, asyncio.CancelledError
                    ):
                        raise error
            finally:
                try:
                    await financial.dispose()
                finally:
                    await publisher.dispose()

        await finish_observed_cleanup(cleanup(), primary)


async def run_captures(output: Path) -> dict[str, Any]:
    """Coordinator owns preflight, empty DB creation, total budget and independent cleanup."""
    output.mkdir(exist_ok=False)
    report: dict[str, Any] = {"status": "INCOMPLETE", "fixture_only": True, "captures": []}
    lag = LoopLag()
    task = asyncio.create_task(lag.run())
    primary: BaseException | None = None
    try:
        for group in GROUPS:
            observer: FenceObservation | None = None
            group_error: BaseException | None = None
            try:
                async with fixture_statement(group == "known_blocker") as (statement, holder):
                    for index in range(10):
                        if observer is None:
                            observer = FenceObservation(lambda: None)
                        record: dict[str, Any] = {"group": group, "index": index}
                        report["captures"].append(record)
                        row = await capture(observer, statement, record)
                        if holder is not None:
                            if not any(
                                value["pid"] == statement["backend_pid"]
                                and holder in value["blocking_pids"]
                                for value in row["activity"]
                            ):
                                raise ValueError("fixture blocker missing")
                            if not any(
                                value["pid"] == statement["backend_pid"] and not value["granted"]
                                for value in row["locks"]
                            ):
                                raise ValueError("fixture waiting lock missing")
                        if group == "cold":
                            await observer.close()
                            observer = None
                        await asyncio.sleep(0.25)
            except BaseException as error:
                group_error = error
                raise
            finally:
                if observer is not None:
                    await finish_observed_cleanup(observer.close(), group_error)
        report["status"] = "CAPTURES_COMPLETE"
    except BaseException as error:
        primary = error
        report["error_type"] = type(error).__name__
        raise
    finally:

        async def finish() -> None:
            lag.stop.set()
            await task

        try:
            await finish_observed_cleanup(finish(), primary)
        except BaseException as error:
            report.update(status="INCOMPLETE", error_type=type(error).__name__)
            primary = error
            raise
        finally:
            report["loop_lag"] = lag.report()
            save_partial_result(output / "observer-captures.json", report, primary=primary)
    return report
