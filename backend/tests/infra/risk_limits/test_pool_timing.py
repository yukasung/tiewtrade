"""NC16 observes cancellation/pool contention without changing transaction behavior."""

import asyncio
import json
from pathlib import Path
from time import monotonic
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.pool import AsyncAdaptedQueuePool

from tests.infra.risk_limits.profile_dispatch_timing import Recorder
from tests.infra.risk_limits.profile_pool_timing import TransactionTrace, operation_scope
from tiewtrade.infra.db import DatabaseRole, create_engine_for, user_session
from tiewtrade.infra.db import session as db


def activate(path: Path) -> None:
    (path / "dispatch-trace-control.json").write_text(
        json.dumps({"started": monotonic(), "seconds": 180, "owners": [], "detail_limit": 0})
    )


@pytest.mark.asyncio
async def test_cancelled_pool_wait_is_distinct_and_trace_restores(tmp_path: Path) -> None:
    activate(tmp_path)
    engine = create_engine_for(DatabaseRole.API, pool_size=1, max_overflow=0)
    original = db._begin
    trace = TransactionTrace(tmp_path / "transactions.jsonl")
    owner = uuid4()
    try:
        async with trace.observe(), user_session(engine, owner):
            with (
                operation_scope(phase="REQUEST_VIEW", owner=str(owner), request=str(uuid4())),
                pytest.raises(TimeoutError),
            ):
                async with asyncio.timeout(0.05):
                    async with user_session(engine, owner):
                        pytest.fail("pool is already occupied")
        assert db._begin is original
        assert not trace.listeners
        assert isinstance(engine.pool, AsyncAdaptedQueuePool)
        assert engine.pool.size() == 1
        assert engine.pool._max_overflow == 0
        rows = [json.loads(line) for line in trace.path.read_text().splitlines()]
        waiting = next(row for row in rows if row.get("phase") == "REQUEST_VIEW")
        assert waiting["pool_wait_seconds"] >= 0.04
        assert waiting["outcome"] == "CancelledError"
        assert "backend_pid" not in waiting
        completed = next(row for row in rows if row.get("outcome") == "COMMIT")
        assert completed["backend_pid"] > 0
        assert completed["checkin_at"] >= completed["checkout_at"]
        assert completed["owner"] == str(owner)
        assert rows[-1]["truncated"] is False
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_trace_redacts_sql_parameters_and_failure_text(tmp_path: Path) -> None:
    activate(tmp_path)
    engine = create_engine_for(DatabaseRole.API)
    secret = "NC16_TEST_ONLY_SECRET_BOUND_VALUE"
    trace = TransactionTrace(tmp_path / "transactions.jsonl")
    original = db._begin
    try:
        with pytest.raises(RuntimeError):
            async with trace.observe(), user_session(engine, uuid4()) as session:
                assert (
                    await session.execute("SELECT CAST(:value AS text)", {"value": secret})
                ).scalar_one() == secret
                raise RuntimeError(secret)
        assert db._begin is original
        assert not trace.listeners
        raw = trace.path.read_text()
        assert secret not in raw
        assert "SELECT" not in raw
        row = json.loads(raw.splitlines()[0])
        assert row["outcome"] == "RuntimeError"
        assert row["queries"]
        # Normal transaction paths still operate after listener/patch cleanup.
        async with engine.connect() as connection:
            assert (await connection.execute(text("SELECT 1"))).scalar_one() == 1
    finally:
        await engine.dispose()


def test_dispatch_observation_extends_only_explicit_diagnostic(tmp_path: Path) -> None:
    recorder = Recorder(tmp_path / "worker.json")
    try:
        assert recorder.seconds == 60
        assert recorder.detail_limit == 100
        activate(tmp_path)
        recorder.record("test", monotonic())
        assert recorder.seconds == 180
        assert recorder.detail_limit == 0
        assert not recorder.truncated
    finally:
        recorder.stream.close()


@pytest.mark.parametrize("enabled", [False, True])
async def test_early_trace_captures_only_selected_phase_without_control(
    tmp_path: Path, enabled: bool
) -> None:
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    trace = TransactionTrace(
        tmp_path / "early.jsonl",
        early_phases=frozenset({"publisher"}) if enabled else frozenset(),
    )
    private = "EARLY_QUERY_PRIVATE_BIND_VALUE"
    try:
        async with trace.observe():
            for phase in ("unrelated", "publisher"):
                with operation_scope(phase=phase):
                    async with db.market_data_session(engine) as session:
                        await session.execute("SELECT CAST(:value AS text)", {"value": private})
        raw = trace.path.read_text()
        rows = [json.loads(line) for line in raw.splitlines()]
        assert len(rows) == (2 if enabled else 1)
        assert rows[-1]["setup"] == (1 if enabled else 2)
        assert private not in raw and "SELECT" not in raw
        if enabled:
            row = rows[0]
            assert row["phase"] == "publisher" and row["measurement_active_at_start"] is False
            assert row["outcome"] == "COMMIT"
            assert len(row["query_details"]) == 2
            assert all(len(query["hash"]) == 64 for query in row["query_details"])
            assert row["started_monotonic"] <= row["checkout_monotonic"]
            assert row["checkout_monotonic"] <= row["transaction_acquired_monotonic"]
            assert row["transaction_acquired_monotonic"] <= row["body_finished_monotonic"]
            assert row["body_finished_monotonic"] <= row["checkin_monotonic"]
            assert row["checkin_monotonic"] <= row["finished_monotonic"]
    finally:
        await engine.dispose()


@pytest.mark.parametrize("failure", [False, True])
async def test_early_trace_separates_query_and_finalization_and_retains_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: bool
) -> None:
    from collections.abc import AsyncIterator
    from contextlib import asynccontextmanager
    from typing import Any

    original = db._begin
    private = RuntimeError("PRIVATE_FINALIZATION_ERROR")

    @asynccontextmanager
    async def delayed(engine: Any, *, cleanup_seconds: float | None = None) -> AsyncIterator[Any]:
        async with original(engine, cleanup_seconds=cleanup_seconds) as connection:
            yield connection
            await asyncio.sleep(0.04)
            if failure:
                raise private

    monkeypatch.setattr(db, "_begin", delayed)
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    trace = TransactionTrace(tmp_path / "stages.jsonl", early_phases=frozenset({"publisher"}))
    try:

        async def operation() -> None:
            async with trace.observe():
                with operation_scope(phase="publisher"):
                    async with db.market_data_session(engine) as session:
                        await session.execute("SELECT pg_sleep(0.02)")

        if failure:
            with pytest.raises(RuntimeError) as error:
                await operation()
            assert error.value is private
        else:
            await operation()
        assert db._begin is delayed and not trace.listeners
        raw = trace.path.read_text()
        row = json.loads(raw.splitlines()[0])
        assert "PRIVATE_FINALIZATION_ERROR" not in raw
        assert row["outcome"] == ("RuntimeError" if failure else "COMMIT")
        assert row["finalization_seconds"] >= 0.04
        assert max(query["seconds"] for query in row["query_details"]) >= 0.02
        assert row["body_seconds"] >= 0.02
        assert row["seconds"] >= row["body_seconds"] + row["finalization_seconds"]
    finally:
        await engine.dispose()


async def test_early_trace_cancelled_pool_wait_remains_visible(tmp_path: Path) -> None:
    engine = create_engine_for(DatabaseRole.MARKET_DATA, pool_size=1, max_overflow=0)
    trace = TransactionTrace(tmp_path / "wait.jsonl", early_phases=frozenset({"publisher"}))
    try:
        async with engine.connect(), trace.observe():
            with operation_scope(phase="publisher"), pytest.raises(TimeoutError):
                async with asyncio.timeout(0.05), db.market_data_session(engine):
                    pytest.fail("occupied pool must not grant a connection")
        row = json.loads(trace.path.read_text().splitlines()[0])
        assert row["outcome"] == "CancelledError"
        assert row["pool_wait_seconds"] >= 0.04
        assert "body_seconds" not in row and "finalization_seconds" not in row
        assert row["query_details"] == []
    finally:
        await engine.dispose()


async def test_early_query_detail_cap_fails_closed(tmp_path: Path) -> None:
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    trace = TransactionTrace(tmp_path / "bounded.jsonl", early_phases=frozenset({"publisher"}))
    try:
        with pytest.raises(RuntimeError, match="PUBLISHER_QUERY_TRACE_TRUNCATED"):
            async with trace.observe():
                with operation_scope(phase="publisher"):
                    async with db.market_data_session(engine) as session:
                        for _ in range(65):
                            await session.execute("SELECT 1")
        row = json.loads(trace.path.read_text().splitlines()[0])
        assert len(row["query_details"]) == 64 and row["query_detail_truncated"]
        assert not trace.listeners
    finally:
        await engine.dispose()
