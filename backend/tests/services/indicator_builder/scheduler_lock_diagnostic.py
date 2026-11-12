"""Bounded opt-in evidence for PR66; never changes scheduler test outcomes."""

from __future__ import annotations

import asyncio
import json
import os
import warnings
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from pathlib import Path
from time import monotonic
from typing import Any

import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine
from sqlalchemy.pool import NullPool

REPORT_VARIABLE = "TIEWTRADE_TEST_SCHEDULER_LOCK_REPORT"
MAX_SAMPLES = 200
MAX_ROWS = 64
SECONDS = 2.0
INTERVAL = 0.01
ACTIVITY = text("""SELECT pid,usename AS role,state,wait_event_type,wait_event,
    pg_blocking_pids(pid) AS blockers,
    extract(epoch FROM clock_timestamp()-xact_start)::double precision AS transaction_age_seconds,
    extract(epoch FROM clock_timestamp()-query_start)::double precision AS query_age_seconds,
    query='SELECT public.coalesce_indicator_build_jobs()' AS coalescing,
    count(*) OVER() AS total_rows
    FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid()
    ORDER BY pid LIMIT 64""")
LOCKS = text("""SELECT pid,locktype,mode,granted,relation::regclass::text AS relation,
    transactionid::text AS transaction_id,virtualxid,classid,objid,objsubid,
    count(*) OVER() AS total_rows FROM pg_locks
    WHERE pid=ANY(CAST(:pids AS integer[]))
      AND (NOT granted OR locktype IN ('transactionid','tuple','advisory'))
    ORDER BY pid,locktype,mode LIMIT 64""")
ACTIVITY_FIELDS = (
    "pid",
    "role",
    "state",
    "wait_event_type",
    "wait_event",
    "blockers",
    "transaction_age_seconds",
    "query_age_seconds",
    "coalescing",
)
LOCK_FIELDS = (
    "pid",
    "locktype",
    "mode",
    "granted",
    "relation",
    "transaction_id",
    "virtualxid",
    "classid",
    "objid",
    "objsubid",
)


def observer_url(environment: Mapping[str, str]) -> str:
    supplied = make_url(environment["TIEWTRADE_TEST_ADMIN_URL"])
    target = make_url(environment["TIEWTRADE_DATABASE_URL_MIGRATOR"])
    if supplied.drivername != "postgresql+asyncpg" or (
        supplied.host,
        supplied.port,
        supplied.database,
    ) != (target.host, target.port, target.database):
        raise ValueError("observer must match the test database")
    return supplied.render_as_string(hide_password=False)


def allowlisted_rows(rows: Sequence[Mapping[Any, Any]], fields: tuple[str, ...]) -> dict[str, Any]:
    return {
        "rows": [{key: row[key] for key in fields} for row in rows[:MAX_ROWS]],
        "truncated": bool(rows and rows[0]["total_rows"] > MAX_ROWS),
    }


async def snapshot(connection: AsyncConnection) -> dict[str, Any]:
    # READ COMMITTED per statement; do not reuse a transaction-cached activity view.
    async with connection.begin():
        await connection.execute(text("SET TRANSACTION READ ONLY"))
        await connection.execute(text("SET LOCAL statement_timeout='100ms'"))
        activity = list((await connection.execute(ACTIVITY)).mappings())
        pids = [row["pid"] for row in activity]
        locks = list((await connection.execute(LOCKS, {"pids": pids})).mappings())
        return {
            "activity": allowlisted_rows(activity, ACTIVITY_FIELDS),
            "locks": allowlisted_rows(locks, LOCK_FIELDS),
            "views_sampled_separately": True,
        }


async def collect(
    connection: AsyncConnection, report: dict[str, Any], ready: asyncio.Event
) -> None:
    started = previous = monotonic()
    budget = asyncio.timeout(SECONDS)
    try:
        async with budget:
            while len(report["samples"]) < MAX_SAMPLES and monotonic() - started < SECONDS:
                async with asyncio.timeout(0.5):
                    sample = await snapshot(connection)
                now = monotonic()
                report["samples"].append(
                    {"elapsed_seconds": now - started, "interval_seconds": now - previous, **sample}
                )
                previous = now
                ready.set()
                await asyncio.sleep(INTERVAL)
        report["observation_limit_reached"] = True
    except TimeoutError:
        if budget.expired():
            report["observation_limit_reached"] = True
        else:
            report["errors"].append("TimeoutError")
    except Exception as error:
        report["errors"].append(type(error).__name__)
    finally:
        ready.set()


@asynccontextmanager
async def observe(report_path: Path, environment: Mapping[str, str]) -> AsyncIterator[None]:
    report: dict[str, Any] = {
        "samples": [],
        "errors": [],
        "observation_limit_reached": False,
        "test_error": None,
        "status": "Incomplete",
    }
    engine = None
    connection = None
    task = None
    cleanup_cancellation = None
    try:
        try:
            engine = create_async_engine(
                observer_url(environment),
                poolclass=NullPool,
                hide_parameters=True,
                connect_args={
                    "server_settings": {
                        "application_name": "scheduler_lock_observer",
                        "default_transaction_read_only": "on",
                    }
                },
            )
            async with asyncio.timeout(1):
                connection = await engine.connect()
                ready = asyncio.Event()
                task = asyncio.create_task(collect(connection, report, ready))
                await ready.wait()
        except asyncio.CancelledError:
            report["test_error"] = "CancelledError"
            raise
        except Exception as error:
            report["errors"].append(type(error).__name__)
        try:
            yield
        except BaseException as error:
            report["test_error"] = type(error).__name__
            raise
    finally:
        try:
            async with asyncio.timeout(1):
                try:
                    if task is not None:
                        task.cancel()
                        await asyncio.gather(task, return_exceptions=True)
                    if connection is not None:
                        await connection.close()
                finally:
                    if engine is not None:
                        await engine.dispose()
        except BaseException as error:
            report["errors"].append(type(error).__name__)
            if isinstance(error, asyncio.CancelledError):
                cleanup_cancellation = error
        if report["samples"] and not report["errors"]:
            report["status"] = "Captured"
        # No concurrent reader: CI uploads only after pytest exits.
        try:
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps(report, indent=2) + "\n")
        except OSError:
            # A secondary evidence write cannot replace the original test outcome.
            # A missing artifact is explicitly incomplete evidence, never no-contention proof.
            warnings.warn("scheduler diagnostic report unavailable", RuntimeWarning, stacklevel=2)
        if cleanup_cancellation is not None and report["test_error"] is None:
            raise cleanup_cancellation


@pytest_asyncio.fixture
async def scheduler_lock_observer(mode: str) -> AsyncIterator[None]:
    supplied = os.environ.get(REPORT_VARIABLE)
    if mode != "PREPARING" or not supplied:
        yield
        return
    async with observe(Path(supplied), os.environ):
        yield
