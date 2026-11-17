"""Before LEASE-01: preserve original fencing, errors, tasks and committed state."""

import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market import profile_publisher_lease as lease
from tests.infra.execution_market import profile_workload as workload
from tests.infra.execution_market.test_publisher_clock_recovery import (
    published_market as published_market,
)
from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.infra.db.session import market_data_session
from tiewtrade.infra.market_data import order_book_storage as books
from tiewtrade.infra.market_data.realtime_records import FeedLease


@pytest.mark.parametrize("name", ["L0-H", "L0-P", "L2-U"])
async def test_original_publication_and_expired_update_state_proof(
    internal_database: None,
    tmp_path: Path,
    name: str,
) -> None:
    case = next(case for case in lease.CASES if case.name == name)
    result = await lease.run_case(case, tmp_path / name)
    assert result["status"] == "DIAGNOSTIC_COMPLETE"
    assert result["independent_lock_witness"]
    assert not any(result["financial_counts"].values())
    assert result["trace"]["injections"] == int(case.delay_at is not None)
    if name == "L2-U":
        assert result["outcome"] == "LEASE_REJECTED_ROLLBACK_CONFIRMED"
        assert result["after"]["book"] == result["before"]["book"]
        assert any(row["stage"] == "book_renew_update" for row in result["trace"]["statements"])
    else:
        assert result["outcome"] == "COMMITTED_ONCE"
        assert result["after"]["buffer_ids"] == list(range(1, case.tick + 1))
    raw = json.loads((tmp_path / name / "trace.json").read_text())
    assert raw["case"] == name


async def test_foreign_child_cannot_consume_delay_or_mutate_trace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trace = lease.LeaseTrace(lease.CASES[2], tmp_path / "trace.json")
    sleep = AsyncMock()
    monkeypatch.setattr(asyncio, "sleep", sleep)
    original = AsyncMock(return_value=object())
    observed = trace.wrap("book_publish", original)
    result = await asyncio.create_task(observed())
    assert result is original.return_value
    assert trace.injections == 0 and not trace.spans
    await trace.delay("after_book")
    await trace.delay("after_book")
    sleep.assert_awaited_once_with(4.5)
    assert trace.injections == 1 and original.await_count == 1


@pytest.mark.parametrize(
    "case", [lease.Case("unknown", False), lease.Case("L1-H", False, "after_book", 9)]
)
async def test_unapproved_case_rejected(tmp_path: Path, case: lease.Case) -> None:
    with pytest.raises(ValueError, match="approved"):
        lease.LeaseTrace(case, tmp_path / "trace.json")


async def test_wrapper_calls_original_once_preserves_exact_error(tmp_path: Path) -> None:
    trace = lease.LeaseTrace(lease.CASES[0], tmp_path / "trace.json")
    error = RuntimeError("PRIVATE")
    original = AsyncMock(side_effect=error)
    with pytest.raises(RuntimeError) as caught:
        await trace.wrap("book_renew", original)()
    assert caught.value is error and original.await_count == 1
    assert trace.operation.get() == "publisher_body"
    assert trace.spans[0]["outcome"] == "RuntimeError"


async def test_trace_io_failure_preserves_primary_and_restores_hooks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    published_market: tuple[AsyncEngine, books.BookLease, FeedLease],
) -> None:
    engine, _book, _price = published_market
    trace = lease.LeaseTrace(lease.CASES[0], tmp_path / "trace.json")
    original = books._locked
    parent = RuntimeError("PRIVATE")
    monkeypatch.setattr(trace, "persist", lambda: (_ for _ in ()).throw(OSError("PRIVATE_IO")))
    with pytest.raises(RuntimeError) as caught, trace.observe(engine):
        raise parent
    assert caught.value is parent and not trace.evidence_ok
    assert books._locked is original
    assert any("OSError" in note for note in parent.__notes__)


async def test_unknown_commit_never_becomes_confirmed_or_retried(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    published_market: tuple[AsyncEngine, books.BookLease, FeedLease],
) -> None:
    from contextlib import asynccontextmanager

    engine, book, price = published_market
    original = market_data_session

    @asynccontextmanager
    async def ambiguous(*args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        async with original(*args, **kwargs) as session:
            yield session
        raise TimeoutError("PRIVATE_COMMIT_REPLY")

    monkeypatch.setattr(workload, "market_data_session", ambiguous)
    trace = lease.LeaseTrace(lease.CASES[0], tmp_path / "trace.json")
    with pytest.raises(TimeoutError), trace.observe(engine):
        await workload.publish_market(
            engine,
            book,
            price,
            rebase=False,
            trade_id=2,
            update_price=False,
            heartbeat_per_book=True,
        )
    assert not any(row["event"] == "session_exited_confirmed" for row in trace.events)
    assert sum(row["stage"] == "book_renew" for row in trace.spans) == 1
    async with market_data_session(engine) as session:
        assert (
            await session.execute("SELECT input_id FROM market_execution_buffer ORDER BY input_id")
        ).scalars().all() == [1, 2]
    assert "PRIVATE" not in trace.path.read_text()


async def test_cancelled_delay_has_no_retry_and_restores_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trace = lease.LeaseTrace(lease.CASES[2], tmp_path / "trace.json")

    async def cancelled(seconds: float) -> None:
        raise asyncio.CancelledError()

    monkeypatch.setattr(asyncio, "sleep", cancelled)
    original = AsyncMock(return_value=object())
    with pytest.raises(asyncio.CancelledError):
        await trace.wrap("book_publish", original)()
    assert trace.injections == 1 and original.await_count == 1
    assert trace.operation.get() == "publisher_body"
    assert trace.spans[-1]["outcome"] == "CancelledError"


@pytest.mark.parametrize("name", ["L1-H", "L1-P"])
async def test_slow_after_book_is_classified_without_retry(
    internal_database: None,
    tmp_path: Path,
    name: str,
) -> None:
    case = next(case for case in lease.CASES if case.name == name)
    result = await lease.run_case(case, tmp_path / name)
    assert result["status"] == "DIAGNOSTIC_COMPLETE" and result["trace"]["injections"] == 1
    assert result["outcome"] in {"COMMITTED_ONCE", "LEASE_REJECTED_ROLLBACK_CONFIRMED"}
    assert sum(span["stage"] == "book_publish" for span in result["trace"]["spans"]) == 1


async def test_unknown_renewal_sql_fails_observation(
    tmp_path: Path,
    published_market: tuple[AsyncEngine, books.BookLease, FeedLease],
) -> None:
    engine, _book, _price = published_market
    trace = lease.LeaseTrace(lease.CASES[0], tmp_path / "trace.json")
    with trace.observe(engine):
        async with market_data_session(engine) as session:
            token = trace.operation.set("book_renew")
            try:
                with pytest.raises(ValueError, match="unsupported"):
                    await session.execute("SELECT 1")
            finally:
                trace.operation.reset(token)
    assert not any(row["stage"] == "book_renew_update" for row in trace.statements)


async def test_real_cancelled_publication_rolls_back_and_joins(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    published_market: tuple[AsyncEngine, books.BookLease, FeedLease],
) -> None:
    engine, book, price = published_market
    witness = create_engine_for(DatabaseRole.MARKET_DATA)
    trace = lease.LeaseTrace(lease.CASES[2], tmp_path / "trace.json")
    entered = asyncio.Event()
    original_delay = trace.delay

    async def held(point: str) -> None:
        if point == "after_book" and trace.active():
            trace.injections += 1
            entered.set()
            await asyncio.Event().wait()
        else:
            await original_delay(point)

    monkeypatch.setattr(trace, "delay", held)
    try:
        before = await lease.state_snapshot(witness)
        with trace.observe(engine):
            task = asyncio.create_task(
                workload.publish_market(
                    engine,
                    book,
                    price,
                    rebase=False,
                    trade_id=2,
                    update_price=False,
                    heartbeat_per_book=True,
                )
            )
            trace.actor = task
            try:
                await asyncio.wait_for(entered.wait(), 2)
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
            finally:
                if not task.done():
                    task.cancel()
                await asyncio.gather(task, return_exceptions=True)
        after = await lease.state_snapshot(witness)
        assert after["book"] == before["book"] and after["buffer_ids"] == before["buffer_ids"]
        assert after["prices"] == before["prices"] and task.cancelled()
        assert not any(row["event"] == "session_exited_confirmed" for row in trace.events)
    finally:
        await witness.dispose()


async def test_invalid_case_never_starts_fixture(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="approved"):
        await lease.run_case(lease.Case("unknown", False), tmp_path / "case")
    assert not (tmp_path / "case").exists()


async def test_case_evidence_io_preserves_original_failure(
    internal_database: None,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.infra.execution_market import profile_internal as internal

    error = RuntimeError("PRIVATE_PRIMARY")
    monkeypatch.setattr(internal, "require_empty_database", AsyncMock())
    monkeypatch.setattr(lease, "financial_counts", AsyncMock(side_effect=error))
    original = workload.save

    def broken(path: Path, value: Any) -> None:
        if path.name == "result.json":
            raise OSError("PRIVATE_IO")
        original(path, value)

    monkeypatch.setattr(workload, "save", broken)
    with pytest.raises(RuntimeError) as caught:
        await lease.run_case(lease.CASES[0], tmp_path / "case")
    assert caught.value is error
    assert any("OSError" in note for note in error.__notes__)


async def test_preflight_prepares_evidence_without_publishing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.infra.execution_market import profile_internal as internal

    preflight = AsyncMock()
    publish = AsyncMock()
    monkeypatch.setattr(internal, "environment_preflight", preflight)
    monkeypatch.setattr(workload, "acquire_sources", publish)
    await lease.prepare(tmp_path / "run")
    publish.assert_not_awaited()
    preflight.assert_awaited_once()
    cases = json.loads((tmp_path / "run/cases.json").read_text())
    assert [row["name"] for row in cases] == [case.name for case in lease.CASES]
    assert [row["tick"] for row in cases] == [2, 10, 2, 10, 2]
    with pytest.raises(FileExistsError):
        await lease.prepare(tmp_path / "run")


@pytest.mark.parametrize("rejected", [False, True], ids=["committed", "lease-rejected"])
@pytest.mark.parametrize(
    "fault", ["io", "io-after-write", "missing", "malformed", "wrong-identity"]
)
async def test_case_readiness_failure_never_reports_complete(
    internal_database: None,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    rejected: bool,
    fault: str,
) -> None:
    from unittest.mock import patch

    from tiewtrade.infra.market_data.realtime_records import WriterLeaseLost

    original_write = Path.write_text
    original_delay = lease.LeaseTrace.delay
    rejection = WriterLeaseLost()
    original_renew = vars(workload)["renew_writer"]
    renewals = 0

    async def reject_observed(*args: Any, **kwargs: Any) -> Any:
        nonlocal renewals
        renewals += 1
        if renewals == 1:
            return await original_renew(*args, **kwargs)
        raise rejection

    renew = AsyncMock(side_effect=reject_observed)
    if rejected:
        # Fail after the actual book/guard work; the unchanged transaction rolls back.
        monkeypatch.setattr(workload, "renew_writer", renew)

    async def immediate_delay(trace: lease.LeaseTrace, point: str) -> None:
        with patch.object(asyncio, "sleep", AsyncMock()):
            await original_delay(trace, point)

    monkeypatch.setattr(lease.LeaseTrace, "delay", immediate_delay)

    def broken_readiness(path: Path, data: str, *args: Any, **kwargs: Any) -> int:
        if path.name != "readiness.json":
            return original_write(path, data, *args, **kwargs)
        if fault == "io":
            raise OSError("PRIVATE_READINESS_IO")
        if fault == "io-after-write":
            original_write(path, data, *args, **kwargs)
            raise OSError("PRIVATE_READINESS_IO_AFTER_WRITE")
        if fault == "missing":
            return len(data)
        if fault == "malformed":
            data = "{"
        else:
            document = json.loads(data)
            document["checks"][0]["tick"] = 999
            data = json.dumps(document)
        return original_write(path, data, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", broken_readiness)
    output = tmp_path / "case"
    with pytest.raises((WriterLeaseLost, ValueError, OSError)) as caught:
        await lease.run_case(lease.CASES[2] if rejected else lease.CASES[0], output)
    if rejected:
        assert caught.value is rejection
        assert renew.await_count == 2  # One setup, one rejected observed attempt; no retry.
        assert any("readiness" in note for note in rejection.__notes__)
    report = json.loads((output / "result.json").read_text())
    assert report["status"] == "INCOMPLETE"
    assert "outcome" not in report and not report.get("readiness_evidence_valid")
    assert "PRIVATE" not in (output / "result.json").read_text()
    witness = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        snapshot = await lease.state_snapshot(witness)
        assert snapshot["buffer_ids"] == ([1] if rejected else [1, 2])
        assert snapshot["book"]["last_input_id"] == (1 if rejected else 2)
    finally:
        await witness.dispose()
