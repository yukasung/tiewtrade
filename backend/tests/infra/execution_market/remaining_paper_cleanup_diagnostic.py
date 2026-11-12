"""One no-order lifecycle observation; never a replacement workload acceptance."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections.abc import Iterator
from contextlib import AsyncExitStack, contextmanager
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from time import monotonic
from typing import Any

from sqlalchemy import event, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import Pool

from tests.infra.execution_market import profile_internal as internal
from tests.infra.execution_market import profile_workload as workload
from tests.infra.execution_market import remaining_paper_campaign as campaign
from tests.infra.execution_market.profile_http import internal_intake
from tests.infra.execution_market.profile_owned_pools import PARENT_CONFIGURATION, observe_owned
from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.services.api.app import app

SNAPSHOT_SQL = text("""SELECT pid,usename AS role,state,backend_type,
    application_name,wait_event_type,wait_event,xact_start IS NOT NULL AS transaction_open
    FROM pg_stat_activity WHERE datname=:target ORDER BY pid""")


def observer_url(environment: dict[str, str]) -> str:
    internal.guard_database(environment)
    supplied = make_url(environment["TIEWTRADE_TEST_ADMIN_URL"])
    target = make_url(environment[DatabaseRole.MIGRATOR.url_variable])
    if (supplied.host, supplied.port, supplied.database) != (
        target.host,
        target.port,
        target.database,
    ):
        raise ValueError("observer must share the guarded isolated source")
    return supplied.set(database="postgres").render_as_string(hide_password=False)


@contextmanager
def pool_events(rows: list[dict[str, Any]]) -> Iterator[None]:
    def observed(kind: str, connection: Any, record: Any, *extra: Any) -> None:
        if kind == "connect":
            record.info["diagnostic_backend_pid"] = connection.driver_connection.get_server_pid()
        rows.append(
            {
                "event": kind,
                "backend_pid": record.info.get("diagnostic_backend_pid"),
                "at": datetime.now(UTC).isoformat(),
                "monotonic": monotonic(),
            }
        )

    listeners = [
        (kind, partial(observed, kind)) for kind in ("connect", "checkout", "checkin", "close")
    ]
    try:
        for kind, callback in listeners:
            event.listen(Pool, kind, callback)
        yield
    finally:
        for kind, callback in listeners:
            if event.contains(Pool, kind, callback):
                event.remove(Pool, kind, callback)


async def parent_lifecycle(output: Path, snapshot: Any) -> None:
    # Same five parent engines, empty guard, ASGI/intake and sampler teardown paths;
    # empty owners means no user/session/order requests are created.
    async with observe_owned(output / "parent.owned-pools.json", PARENT_CONFIGURATION) as tracker:
        engines = {
            role: create_engine_for(role)
            for role in (
                DatabaseRole.MARKET_DATA,
                DatabaseRole.MIGRATOR,
                DatabaseRole.API,
                DatabaseRole.ENGINE,
                DatabaseRole.ENGINE_SCAN,
            )
        }
        intake_stack = AsyncExitStack()
        try:
            await internal.require_empty_database()
            await intake_stack.enter_async_context(
                internal_intake(
                    [],
                    engine=engines[DatabaseRole.ENGINE],
                    api=engines[DatabaseRole.API],
                    migrator=engines[DatabaseRole.MIGRATOR],
                    gate=None,
                    output=output,
                )
            )
            for engine in engines.values():
                async with engine.connect() as connection:
                    await connection.execute(text("SELECT 1"))
            for engine in app.state._state.values():
                if isinstance(engine, AsyncEngine):
                    async with engine.connect() as connection:
                        await connection.execute(text("SELECT 1"))
            stop = asyncio.Event()

            async def stop_sample() -> None:
                await asyncio.sleep(0.1)
                stop.set()

            stopper = asyncio.create_task(stop_sample())
            try:
                await workload.resource_sampler(
                    engines[DatabaseRole.MIGRATOR],
                    engines[DatabaseRole.MARKET_DATA],
                    [],
                    asyncio.Lock(),
                    stop,
                    [],
                    observe_host=False,
                )
            finally:
                stopper.cancel()
                await asyncio.gather(stopper, return_exceptions=True)
            await snapshot("parent_before_shutdown")
        finally:
            primary = sys.exception()
            cleanup_errors: list[BaseException] = []
            try:
                tracker.begin_quiescence()
            except BaseException as failure:
                cleanup_errors.append(failure)
            try:
                await intake_stack.aclose()
                await snapshot("intake_closed")
            except BaseException as failure:
                cleanup_errors.append(failure)
            for role, engine in engines.items():
                try:
                    await engine.dispose()
                except BaseException as failure:
                    cleanup_errors.append(failure)
                try:
                    await snapshot("disposed_" + role.name)
                except BaseException as failure:
                    cleanup_errors.append(failure)
            if cleanup_errors:
                reported = primary if primary is not None else cleanup_errors[0]
                for cleanup_error in cleanup_errors:
                    if cleanup_error is not reported:
                        reported.add_note(
                            "secondary lifecycle cleanup: " + type(cleanup_error).__name__
                        )
                if primary is None:
                    raise reported
    await snapshot("pool_observer_closed")


async def run(output: Path) -> int:
    target = internal.guard_database(dict(os.environ))
    url = observer_url(dict(os.environ))
    output.mkdir(parents=True, exist_ok=False)
    source = campaign.hashes()
    campaign.pin_candidate(output, source)
    workload.save(output / "candidate-sha256.json", source)
    (output / "diagnostic-runner.py").write_bytes(Path(__file__).read_bytes())
    events: list[dict[str, Any]] = []
    snapshots: list[dict[str, Any]] = []
    observer = create_async_engine(
        url,
        hide_parameters=True,
        isolation_level="AUTOCOMMIT",
        connect_args={
            "server_settings": {
                "default_transaction_read_only": "on",
                "application_name": "f17_cleanup_diag_observer",
            }
        },
    )
    started = monotonic()
    status, error = "INCOMPLETE", None
    try:
        async with asyncio.timeout(300), observer.connect() as connection:
            identity = (
                await connection.execute(
                    text(
                        "SELECT current_database(),pg_backend_pid(),"
                        "current_setting('transaction_read_only')"
                    )
                )
            ).one()
            if identity[0] != "postgres" or identity[2] != "on":
                raise ValueError("separate read-only observer required")

            async def snapshot(stage: str) -> None:
                rows = (await connection.execute(SNAPSHOT_SQL, {"target": target})).mappings().all()
                snapshots.append(
                    {
                        "stage": stage,
                        "at": datetime.now(UTC).isoformat(),
                        "monotonic": monotonic(),
                        "backends": [dict(row) for row in rows],
                    }
                )
                workload.save(output / "timeline.json", snapshots)

            await snapshot("before_target_connections")
            with pool_events(events):
                await internal.require_empty_database()
                await snapshot("initial_empty_guard_closed")
                for role in (
                    DatabaseRole.API,
                    DatabaseRole.AUTH,
                    DatabaseRole.ENGINE,
                    DatabaseRole.ENGINE_SCAN,
                    DatabaseRole.MIGRATOR,
                    DatabaseRole.MARKET_DATA,
                ):
                    engine = create_engine_for(role)
                    await engine.dispose()
                await snapshot("manifest_defaults_closed")
                await parent_lifecycle(output, snapshot)
                await snapshot("one_shot_cleanup")
                checkpoint = monotonic()
                for offset in (0.05, 0.25, 1.0, 5.0, 15.0):
                    await asyncio.sleep(max(0, checkpoint + offset - monotonic()))
                    await snapshot("post_cleanup_" + str(offset))
            status = "OBSERVATION_COMPLETE"
    except BaseException as failure:
        error = type(failure).__name__
        raise
    finally:
        primary = sys.exception()
        disposal_error: BaseException | None = None
        try:
            await observer.dispose()
        except BaseException as failure:
            disposal_error = failure
            error = error or type(failure).__name__
            status = "INCOMPLETE"
            if primary is not None:
                primary.add_note("secondary observer disposal: " + type(failure).__name__)
        workload.save(output / "pool-events.json", events)
        unchanged = source == campaign.hashes()
        if not unchanged:
            status = "INCOMPLETE"
            error = error or "CandidateChanged"
        disposal_error_type = None if disposal_error is None else type(disposal_error).__name__
        workload.save(
            output / "result.json",
            {
                "status": status,
                "error_type": error,
                "seconds": monotonic() - started,
                "source_unchanged": unchanged,
                "observer_disposal_error": disposal_error_type,
                "one_shot_connections": next(
                    (
                        len(row["backends"])
                        for row in snapshots
                        if row["stage"] == "one_shot_cleanup"
                    ),
                    None,
                ),
                "scope": "no-order lifecycle diagnostic; original D20 stays Incomplete",
            },
        )
        if disposal_error is not None and primary is None:
            raise disposal_error
    return 0 if status == "OBSERVATION_COMPLETE" else 1


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    return await run(parser.parse_args().output)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
