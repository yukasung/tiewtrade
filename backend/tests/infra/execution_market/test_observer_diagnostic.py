"""OBS-02 timing transparency, isolation, bounds and real PostgreSQL ownership."""

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from time import monotonic
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy import text

from tests.infra.execution_market import profile_internal as internal
from tests.infra.execution_market import profile_observer_diagnostic as diagnostic
from tests.infra.execution_market.profile_publisher_fence import FenceObservation
from tests.infra.execution_market.test_publisher_fence import QueryResult


def statement() -> dict[str, Any]:
    return {"backend_pid": 7, "stage": "fixture", "started": monotonic()}


@pytest.fixture
def observer(monkeypatch: pytest.MonkeyPatch) -> FenceObservation:
    class Connection:
        async def exec_driver_sql(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def execute(self, sql: Any, *args: Any, **kwargs: Any) -> QueryResult:
            if "pg_stat_activity" in str(sql):
                return QueryResult([{"pid": 7, "blocking_pids": [8]}])
            if "pg_locks" in str(sql):
                return QueryResult([{"pid": 7, "granted": False}])
            return QueryResult()

    @asynccontextmanager
    async def connect() -> Any:
        yield Connection()

    monkeypatch.setattr(
        internal, "readonly_admin", lambda: SimpleNamespace(connect=connect, dispose=AsyncMock())
    )
    return FenceObservation(lambda: None)


async def test_original_once_and_result_unchanged(
    observer: FenceObservation, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = observer.sample
    calls = 0
    result = None

    async def sample(value: dict[str, Any]) -> dict[str, Any]:
        nonlocal calls, result
        calls += 1
        result = await original(value)
        return result

    monkeypatch.setattr(observer, "sample", sample)
    engine = observer.engine
    record: dict[str, Any] = {}
    actual = await diagnostic.capture(observer, statement(), record)
    assert actual is result and calls == 1 and observer.engine is engine
    assert record["outcome"] == "RETURNED" and record["observation"] is actual
    assert [span["phase"] for span in record["spans"]] == list(diagnostic.PHASES)
    assert all(span["finished"] >= span["started"] for span in record["spans"])
    assert "SELECT" not in json.dumps(record, default=str)


@pytest.mark.parametrize("error_type", [RuntimeError, TimeoutError, asyncio.CancelledError])
async def test_error_identity_and_restore(
    observer: FenceObservation, monkeypatch: pytest.MonkeyPatch, error_type: type[BaseException]
) -> None:
    primary = error_type("SECRET SQL TOKEN")
    sample = AsyncMock(side_effect=primary)
    monkeypatch.setattr(observer, "sample", sample)
    engine = observer.engine
    record: dict[str, Any] = {}
    with pytest.raises(error_type) as caught:
        await diagnostic.capture(observer, {}, record)
    assert caught.value is primary and sample.await_count == 1 and observer.engine is engine
    assert record["outcome"] == error_type.__name__
    assert "SECRET" not in json.dumps(record)


async def test_task_isolation_and_bound() -> None:
    timing = diagnostic.CaptureTiming()
    operation = AsyncMock()
    with pytest.raises(ValueError, match="task mismatch"):
        await asyncio.create_task(timing.measure("checkout_and_setup", operation))
    operation.assert_not_awaited()
    for phase in diagnostic.PHASES:
        await timing.measure(phase, operation)
    timing.validate()
    with pytest.raises(ValueError, match="bound"):
        await timing.measure("extra", operation)
    assert len(timing.spans) == 7 and operation.await_count == 7


@pytest.mark.parametrize("bad", [None, float("nan"), float("inf"), -1, True, "123"])
async def test_invalid_timing(bad: Any) -> None:
    timing = diagnostic.CaptureTiming()
    for phase in diagnostic.PHASES:
        await timing.measure(phase, AsyncMock())
    timing.spans[2]["finished"] = bad
    with pytest.raises(ValueError, match="invalid"):
        timing.validate()


async def test_missing_timing() -> None:
    with pytest.raises(ValueError, match="incomplete"):
        diagnostic.CaptureTiming().validate()


async def test_concurrent_capture_rejected(
    observer: FenceObservation, monkeypatch: pytest.MonkeyPatch
) -> None:
    entered, release = asyncio.Event(), asyncio.Event()
    original = observer.sample

    async def sample(value: dict[str, Any]) -> dict[str, Any]:
        entered.set()
        await release.wait()
        return await original(value)

    monkeypatch.setattr(observer, "sample", sample)
    task = asyncio.create_task(diagnostic.capture(observer, statement(), {}))
    await entered.wait()
    try:
        with pytest.raises(ValueError, match="exclusively owned"):
            await diagnostic.capture(observer, {}, {})
    finally:
        release.set()
        await task


@pytest.mark.parametrize("failed", [False, True])
async def test_campaign_stop_and_io_primary(
    tmp_path: Path, observer: FenceObservation, monkeypatch: pytest.MonkeyPatch, failed: bool
) -> None:
    primary = RuntimeError("PRIVATE")
    groups: list[bool] = []

    @asynccontextmanager
    async def fixture(blocked: bool) -> Any:
        groups.append(blocked)
        yield statement(), 8 if blocked else None

    monkeypatch.setattr(diagnostic, "fixture_statement", fixture)
    monkeypatch.setattr(diagnostic, "FenceObservation", lambda current: observer)
    if failed:
        monkeypatch.setattr(observer, "sample", AsyncMock(side_effect=primary))
    original_write = Path.write_text

    def fail_write(path: Path, *args: Any, **kwargs: Any) -> Any:
        if path.name == "observer-captures.json":
            raise OSError("SECRET")
        return original_write(path, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", fail_write)
    with pytest.raises(RuntimeError if failed else OSError) as caught:
        await diagnostic.run_captures(tmp_path / "run")
    if failed:
        assert caught.value is primary and groups == [False]
        assert any("OSError" in note for note in primary.__notes__)
    else:
        assert groups == [False, False, True]


@pytest.mark.usefixtures("internal_database")
@pytest.mark.parametrize("blocked", [False, True])
async def test_real_capture_readonly_and_lock_release(blocked: bool) -> None:
    observer = FenceObservation(lambda: None)
    waiter = None
    try:
        async with diagnostic.fixture_statement(blocked) as (value, holder):
            waiter = value["backend_pid"]
            row = await diagnostic.capture(observer, value, {})
            if blocked:
                assert any(
                    item["pid"] == waiter and holder in item["blocking_pids"]
                    for item in row["activity"]
                )
                assert any(item["pid"] == waiter and not item["granted"] for item in row["locks"])
            async with observer.engine.connect() as connection:
                assert (
                    await connection.execute(text("SHOW transaction_read_only"))
                ).scalar_one() == "on"
        async with observer.engine.connect() as connection:
            assert (
                await connection.execute(
                    text("SELECT count(*) FROM pg_locks WHERE pid=:pid AND locktype='advisory'"),
                    {"pid": waiter},
                )
            ).scalar_one() == 0
        assert observer.engine.pool.checkedout() == 0  # type: ignore[attr-defined]
    finally:
        await observer.close()


@pytest.mark.parametrize("phase", diagnostic.PHASES)
@pytest.mark.parametrize("error_type", [RuntimeError, asyncio.CancelledError])
async def test_phase_failure_keeps_identity_and_partial_spans(
    observer: FenceObservation,
    monkeypatch: pytest.MonkeyPatch,
    phase: str,
    error_type: type[BaseException],
) -> None:
    primary = error_type("SECRET")
    original = diagnostic.CaptureTiming.measure

    async def measure(self: diagnostic.CaptureTiming, name: str, operation: Any) -> Any:
        async def fail() -> Any:
            # Session exit still owns a real context and must close it first.
            if name == "session_exit":
                await operation()
            raise primary

        return await original(self, name, fail if name == phase else operation)

    monkeypatch.setattr(diagnostic.CaptureTiming, "measure", measure)
    record: dict[str, Any] = {}
    engine = observer.engine
    with pytest.raises(error_type) as caught:
        await diagnostic.capture(observer, statement(), record)
    assert caught.value is primary and observer.engine is engine
    assert (
        next(span for span in record["spans"] if span["phase"] == phase)["outcome"]
        == error_type.__name__
    )
    assert len(record["spans"]) <= 7 and "SECRET" not in json.dumps(record, default=str)


async def test_existing_one_second_timeout_is_not_extended(
    observer: FenceObservation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = diagnostic.CaptureTiming.measure

    async def measure(self: diagnostic.CaptureTiming, phase: str, operation: Any) -> Any:
        async def delayed() -> Any:
            await asyncio.sleep(2)
            return await operation()

        return await original(self, phase, delayed if phase == "activity" else operation)

    monkeypatch.setattr(diagnostic.CaptureTiming, "measure", measure)
    record: dict[str, Any] = {}
    with pytest.raises(TimeoutError):
        await asyncio.wait_for(diagnostic.capture(observer, statement(), record), 1.8)
    assert record["outcome"] == "TimeoutError"
    assert observer.failed_observation is not None
    assert observer.failed_observation["capture_phase"] == "activity"


async def test_lag_uses_bounded_aggregate_and_stops() -> None:
    lag = diagnostic.LoopLag()
    task = asyncio.create_task(lag.run())
    await asyncio.sleep(0.12)
    lag.stop.set()
    await task
    result = lag.report()
    assert result["count"] >= 1 and result["total_seconds"] >= result["maximum_seconds"] >= 0
    assert len(result) == 3


@pytest.mark.usefixtures("internal_database")
@pytest.mark.parametrize("error_type", [RuntimeError, asyncio.CancelledError])
async def test_real_fixture_failure_releases_lock_and_rolls_back(
    error_type: type[BaseException],
) -> None:
    observer = FenceObservation(lambda: None)
    primary = error_type("fixture stop")
    try:
        with pytest.raises(error_type) as caught:
            async with diagnostic.fixture_statement(True) as (value, holder):
                row = await diagnostic.capture(observer, value, {})
                assert any(holder in item["blocking_pids"] for item in row["activity"])
                raise primary
        assert caught.value is primary
        async with observer.engine.connect() as connection:
            assert (
                await connection.execute(
                    text(
                        "SELECT count(*) FROM pg_locks WHERE pid=ANY(CAST(:pids AS int[])) "
                        "AND locktype='advisory'"
                    ),
                    {"pids": [holder, value["backend_pid"]]},
                )
            ).scalar_one() == 0
            assert (
                await connection.execute(
                    text(
                        "SELECT count(*) FROM pg_stat_activity "
                        "WHERE pid=ANY(CAST(:pids AS int[])) AND xact_start IS NOT NULL"
                    ),
                    {"pids": [holder, value["backend_pid"]]},
                )
            ).scalar_one() == 0
    finally:
        await observer.close()


@pytest.mark.parametrize("blocked", [False, True])
@pytest.mark.parametrize(
    "invalid_url",
    [
        pytest.param(None, id="missing"),
        pytest.param(
            "postgresql+asyncpg://example.invalid:5432/tiewtrade_internal20_guard_test", id="remote"
        ),
        pytest.param("postgresql+asyncpg://127.0.0.1:5432/tiewtrade", id="normal-database"),
        pytest.param(
            "postgresql+asyncpg://127.0.0.1:5432/tiewtrade_internal20_other", id="other-database"
        ),
        pytest.param(
            "postgresql+asyncpg://127.0.0.1:5433/tiewtrade_internal20_guard_test", id="other-port"
        ),
        pytest.param(
            "postgresql+asyncpg://localhost:5432/tiewtrade_internal20_guard_test", id="other-host"
        ),
    ],
)
async def test_fixture_rejects_invalid_database_before_any_engine_or_session(
    monkeypatch: pytest.MonkeyPatch,
    blocked: bool,
    invalid_url: str | None,
) -> None:
    roles = ("API", "AUTH", "ENGINE", "ENGINE_SCAN", "MIGRATOR", "MARKET_DATA")
    for role in roles:
        monkeypatch.setenv(
            f"TIEWTRADE_DATABASE_URL_{role}",
            "postgresql+asyncpg://127.0.0.1:5432/tiewtrade_internal20_guard_test",
        )
    key = "TIEWTRADE_DATABASE_URL_MARKET_DATA"
    if invalid_url is None:
        monkeypatch.delenv(key)
    else:
        monkeypatch.setenv(key, invalid_url)
    engine = Mock(side_effect=AssertionError("engine must not be created"))
    market_session = Mock(side_effect=AssertionError("session must not open"))
    financial_session = Mock(side_effect=AssertionError("session must not open"))
    monkeypatch.setattr(diagnostic, "create_engine_for", engine)
    monkeypatch.setattr(diagnostic, "market_data_session", market_session)
    monkeypatch.setattr(diagnostic, "user_session", financial_session)
    with pytest.raises(ValueError, match="internal Paper profile"):
        async with diagnostic.fixture_statement(blocked):
            pytest.fail("invalid fixture must not yield")
    engine.assert_not_called()
    market_session.assert_not_called()
    financial_session.assert_not_called()
