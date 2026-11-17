"""Real-PG fixture/role/timing proof before the one diagnostic campaign."""

import ast
import asyncio
import json
import shutil
from collections.abc import AsyncIterator
from dataclasses import replace
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market import profile_internal as internal
from tests.infra.execution_market import profile_tail_reads as tail
from tests.infra.execution_market import profile_workload as workload
from tests.infra.execution_market.profile_parent_poll import ParentPollGate
from tests.infra.execution_market.test_evidence import source_record
from tests.infra.execution_market.test_publisher_clock_recovery import financial_state
from tests.order_book_fixtures import capability, snapshot
from tiewtrade.core.order_book import BookState
from tiewtrade.core.positions import PositionPair
from tiewtrade.infra.db import DatabaseRole, create_engine_for, user_session
from tiewtrade.infra.db.errors import InfraError
from tiewtrade.infra.market_data.order_book_storage import ExecutionMetadata, StoredExecutionInput
from tiewtrade.infra.paper_orders import storage
from tiewtrade.venues.symbols import Symbol


@pytest.fixture
def exact_sql() -> str:
    return tail.diagnostic_sql()


@pytest.mark.parametrize("failure", ["missing", "different", "duplicate"])
def test_source_drift_is_rejected(failure: str) -> None:
    source = Path(workload.__file__).read_text()
    if failure == "missing":
        source = source.replace("async def wait_for_input_recovery(", "async def missing(")
    elif failure == "different":
        source = source.replace(
            "coalesce((SELECT max(k.input_id)",
            "coalesce((SELECT min(k.input_id)",
            1,
        )
    else:
        source = source.replace(
            "    async def recovered(owner:",
            "    unused = read_input_cursor\n    async def recovered(owner:",
            1,
        )
    with pytest.raises(ValueError):
        tail.diagnostic_sql(source)


@pytest.mark.parametrize("free", [2 * 1024**3 - 1, 2 * 1024**3])
def test_disk_boundary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, free: int) -> None:
    monkeypatch.setattr(shutil, "disk_usage", lambda root: type("Disk", (), {"free": free})())
    if free < 2 * 1024**3:
        with pytest.raises(RuntimeError, match="headroom"):
            tail.require_space(tmp_path)
    else:
        tail.require_space(tmp_path)


@pytest_asyncio.fixture
async def market(
    internal_database: None,
) -> AsyncIterator[tuple[AsyncEngine, list[workload.OwnerState]]]:
    engines = [
        create_engine_for(role)
        for role in (DatabaseRole.API, DatabaseRole.ENGINE, DatabaseRole.ENGINE_SCAN)
    ]
    try:
        yield engines[1], await workload.seed_owners(engines[0], engines[1], engines[2], 2)
    finally:
        for engine in engines:
            await engine.dispose()


async def test_valid_seed_read_only_explain_and_rls(
    market: tuple[AsyncEngine, list[workload.OwnerState]],
    tmp_path: Path,
    exact_sql: str,
) -> None:
    engine, owners = market
    await tail.seed_history(engine, owners[0], 3, tmp_path)
    await tail.seed_history(engine, owners[1], 4, tmp_path)
    assert (await tail.verify_owner(engine, owners[0], 3))["decoded_samples"] == 2
    before = [await financial_state(engine, owner.user_id) for owner in owners]
    rows: list[dict[str, Any]] = []
    gate = ParentPollGate()
    listeners = len(engine.sync_engine.pool.dispatch.checkout)
    with tail.observe_connection(engine):
        value = await tail.observe_read(
            engine, owners[0], owners[0].wallet.episode_id, exact_sql, gate, rows
        )
        assert value == {"availability": "READY", "input_id": 3}
        await tail.observe_read(
            engine, owners[0], owners[0].wallet.episode_id, exact_sql, gate, rows, explain=True
        )
        with pytest.raises(Exception, match="No row"):
            await tail.observe_read(
                engine, owners[0], owners[1].wallet.episode_id, exact_sql, gate, rows
            )
    assert len(engine.sync_engine.pool.dispatch.checkout) == listeners
    assert gate.active == 0 and gate.finished == gate.attempts == 3
    row = rows[0]
    times = [
        row[key]
        for key in (
            "started",
            "session_enter_at",
            "checkout_at",
            "begin_at",
            "role_ready_at",
            "query_started_at",
            "query_returned_at",
            "session_exited_at",
            "finished",
        )
    ]
    assert times == sorted(times) and rows[-1]["outcome"] != "RETURNED"
    assert [await financial_state(engine, owner.user_id) for owner in owners] == before


async def test_empty_mixed_generation_pair_and_rebase_keep_aggregate_semantics(
    market: tuple[AsyncEngine, list[workload.OwnerState]],
    tmp_path: Path,
    exact_sql: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine, owners = market
    owner = owners[0]
    gate = ParentPollGate()
    rows: list[dict[str, Any]] = []
    with tail.observe_connection(engine):
        assert (
            await tail.observe_read(engine, owner, owner.wallet.episode_id, exact_sql, gate, rows)
        )["input_id"] == 0
        await tail.seed_history(engine, owner, 2, tmp_path)
        await tail.seed_history(engine, owner, 3, tmp_path, generation=2)
        await tail.seed_history(engine, owner, 2, tmp_path, generation=2, rebase=True)
        original = source_record()
        at = original.market.received_at
        symbol = Symbol("ETH", "USDT")
        book = snapshot(at, symbol=symbol)
        cap = capability(at, symbol=symbol)
        record = StoredExecutionInput(
            BookState(PositionPair("ETH", "USDT"), 1, 1, at, at, book.bids, book.asks, True, True),
            ExecutionMetadata(cap.market, cap.limit, at, cap.source_document),
            "",
        )
        record = replace(record, digest=storage._source_digest(record))
        monkeypatch.setattr(tail, "source_record", lambda: record)
        await tail.seed_history(engine, owner, 9, tmp_path)
        # Exact existing SQL aggregates across pair/generation; do not silently narrow it.
        assert (
            await tail.observe_read(engine, owner, owner.wallet.episode_id, exact_sql, gate, rows)
        )["input_id"] == 9
        async with user_session(engine, owner.user_id, role=DatabaseRole.ENGINE) as session:
            old = (
                await session.execute(tail.baseline_sql(), {"episode": owner.wallet.episode_id})
            ).one()
            assert (
                tuple(old)
                == tuple(await workload.read_input_cursor(session, owner.wallet.episode_id))
                == ("READY", 9)
            )


async def test_reader_rejects_mutation_and_preserves_exception(
    market: tuple[AsyncEngine, list[workload.OwnerState]],
) -> None:
    engine, owners = market
    rows: list[dict[str, Any]] = []
    with tail.observe_connection(engine), pytest.raises(InfraError, match="25006"):
        await tail.observe_read(
            engine,
            owners[0],
            owners[0].wallet.episode_id,
            "UPDATE paper_order_activity SET revision=revision "
            "WHERE episode_id=:episode RETURNING revision",
            ParentPollGate(),
            rows,
        )
    assert rows[0]["outcome"] != "RETURNED"
    assert tail.READ_SCOPE.get() is None


async def test_cancelled_queued_reader_never_borrows_connection(
    market: tuple[AsyncEngine, list[workload.OwnerState]],
    exact_sql: str,
) -> None:
    engine, owners = market
    gate = ParentPollGate()
    for _ in range(4):
        await gate.semaphore.acquire()
    rows: list[dict[str, Any]] = []
    with tail.observe_connection(engine):
        task = asyncio.create_task(
            tail.observe_read(engine, owners[0], owners[0].wallet.episode_id, exact_sql, gate, rows)
        )
        try:
            while not rows:
                await asyncio.sleep(0)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            for _ in range(4):
                gate.semaphore.release()
    assert "checkout_at" not in rows[0] and gate.active == 0
    assert rows[0]["outcome"] == "CancelledError"


async def test_concurrent_read_failure_joins_siblings(
    market: tuple[AsyncEngine, list[workload.OwnerState]],
    exact_sql: str,
) -> None:
    engine, owners = market
    gate = ParentPollGate()
    rows: list[dict[str, Any]] = []
    with tail.observe_connection(engine), pytest.raises(ExceptionGroup):
        # Empty fixture deliberately fails the expected head check; no automatic retry.
        await tail.run_pass(engine, owners, exact_sql, gate, rows, concurrent=True)
    assert gate.active == 0 and gate.finished == gate.attempts == 2
    assert workload.parent_pool_state(engine)["checked_out"] == 0


async def test_preflight_failure_never_seeds_and_reused_output_is_rejected(
    internal_database: None,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed = AsyncMock()
    monkeypatch.setattr(workload, "seed_owners", seed)
    monkeypatch.setattr(
        internal, "environment_preflight", AsyncMock(side_effect=RuntimeError("preflight"))
    )
    root = tmp_path / "run"
    with pytest.raises(RuntimeError, match="preflight"):
        await tail.execute(root)
    seed.assert_not_awaited()
    assert json.loads((root / "result.json").read_text())["status"] == "INCOMPLETE"
    with pytest.raises(FileExistsError):
        await tail.execute(root)


@pytest.mark.parametrize("head", [-1, True, 144514, 1.5])
async def test_invalid_seed_head_is_rejected_before_access(tmp_path: Path, head: Any) -> None:
    with pytest.raises(ValueError, match="unsupported"):
        await tail.seed_history(None, None, head, tmp_path)  # type: ignore[arg-type]


async def test_oversized_database_name_fails_before_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(internal, "guard_database", lambda env: "tiewtrade_internal20_" + "a" * 50)
    with pytest.raises(ValueError, match="identifier"):
        await tail.execute(tmp_path / "output")
    assert not (tmp_path / "output").exists()


async def test_statement_timeout_cancels_query_without_retry(
    market: tuple[AsyncEngine, list[workload.OwnerState]],
) -> None:
    engine, owners = market
    rows: list[dict[str, Any]] = []
    gate = ParentPollGate()
    with tail.observe_connection(engine), pytest.raises(InfraError):
        await tail.observe_read(
            engine,
            owners[0],
            owners[0].wallet.episode_id,
            "SELECT pg_sleep(11),0 AS input_id",
            gate,
            rows,
        )
    assert len(rows) == 1 and gate.attempts == gate.finished == 1 and gate.active == 0
    assert "query_returned_at" not in rows[0]
    assert workload.parent_pool_state(engine)["checked_out"] == 0


@pytest.mark.parametrize(
    "fault",
    [
        "query_suffix",
        "unused_reference",
        "wrong_episode",
        "not_awaited",
        "discarded_result",
        "helper_extra_statement",
        "wrong_binding",
        "empty_source",
    ],
)
def test_query_call_drift_is_rejected(fault: str) -> None:
    source = Path(workload.__file__).read_text()
    reader_call = "row = await read_input_cursor(session, owner.wallet.episode_id)"
    if fault == "query_suffix":
        changed = source.replace(
            "session.execute(TAIL_CURSOR_SQL,",
            "session.execute(TAIL_CURSOR_SQL + \" AND a.availability='READY'\",",
            1,
        )
    elif fault == "unused_reference":
        changed = source.replace(reader_call, "row = None; unused = read_input_cursor", 1)
    elif fault == "wrong_episode":
        changed = source.replace(
            reader_call, "row = await read_input_cursor(session, owner.user_id)", 1
        )
    elif fault == "not_awaited":
        changed = source.replace(reader_call, reader_call.replace("await ", ""), 1)
    elif fault == "discarded_result":
        changed = source.replace(reader_call, reader_call.removeprefix("row = "), 1)
    elif fault == "helper_extra_statement":
        changed = source.replace(
            "    return (await session.execute(TAIL_CURSOR_SQL,",
            "    session = None\n    return (await session.execute(TAIL_CURSOR_SQL,",
            1,
        )
    elif fault == "wrong_binding":
        changed = source.replace(
            'session.execute(TAIL_CURSOR_SQL, {"episode": episode})',
            'session.execute(TAIL_CURSOR_SQL, {"episode": None})',
            1,
        )
    else:
        changed = ""
    assert changed != source
    with pytest.raises(ValueError):
        tail.diagnostic_sql(changed)


def test_query_binding_accepts_formatting_only_changes() -> None:
    source = Path(workload.__file__).read_text()
    assert tail.diagnostic_sql(ast.unparse(ast.parse(source))) == tail.diagnostic_sql()
