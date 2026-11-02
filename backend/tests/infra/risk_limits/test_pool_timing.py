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
