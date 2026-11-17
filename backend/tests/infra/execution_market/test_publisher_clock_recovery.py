"""The future guard must reject; only confirmed rollback permits one fixture retry."""

import argparse
import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import monotonic
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncTransaction

from tests.infra.execution_market import profile_internal as internal
from tests.infra.execution_market import profile_publisher_recovery as recovery
from tests.infra.execution_market import profile_workload as workload
from tests.infra.execution_market import remaining_paper_campaign as campaign
from tests.infra.execution_market.profile_publisher_readiness import observe_publisher_readiness
from tests.infra.risk_limits.test_book_clock import ready_book
from tiewtrade.core.orders import SourceUnavailableError
from tiewtrade.infra.db import DatabaseRole, create_engine_for, user_session
from tiewtrade.infra.db.session import MarketDataSession, market_data_session
from tiewtrade.infra.market_data import order_book_storage as storage
from tiewtrade.infra.market_data.realtime_records import FeedLease
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot

PublishedMarket = tuple[AsyncEngine, storage.BookLease, FeedLease]


async def published_input_ids(session: MarketDataSession) -> list[int]:
    result = await session.execute("SELECT input_id FROM market_execution_buffer ORDER BY input_id")
    return list(result.scalars().all())


def candidate(state: recovery.ClockRecovery) -> tuple[recovery.Attempt, SourceUnavailableError]:
    now = datetime(2026, 11, 15, tzinfo=UTC)
    state.publisher_task = asyncio.current_task()
    book = ready_book(now)
    attempt = state.new_attempt(tick=2)
    attempt.book = book
    attempt.lease = storage.BookLease(
        book.pair, uuid4(), book.generation, now + timedelta(seconds=5), book.input_id - 1
    )
    attempt.observed_at = now
    attempt.guard_now = now - timedelta(microseconds=230)
    attempt.checked_at = monotonic()
    attempt.guard_calls = 1
    attempt.evidence_ok = True
    error = SourceUnavailableError("book readiness cannot be proved")
    attempt.error = error
    return attempt, error


@pytest.mark.parametrize(
    "kind",
    [
        "setup",
        "before_window",
        "after_window",
        "other_error",
        "missing",
        "not_ready",
        "stale",
        "source_future",
        "source_stale",
        "unequal_times",
        "wrong_generation",
        "gap",
        "repeated_guard",
        "unrecorded",
        "other_identity",
    ],
)
async def test_noneligible_rejections_never_consume_recovery(tmp_path: Path, kind: str) -> None:
    state = recovery.ClockRecovery(tmp_path / "recovery.json")
    state.window_start = monotonic() - 1
    attempt, error = candidate(state)
    assert attempt.book is not None and attempt.lease is not None
    if kind == "setup":
        state.window_start = None
    elif kind == "before_window":
        state.window_start = attempt.started + 1
    elif kind == "after_window":
        state.window_end = attempt.started - 1
    elif kind == "other_error":
        error = SourceUnavailableError("different failure")
    elif kind == "missing":
        attempt.guard_now = None
    elif kind == "not_ready":
        attempt.book = replace(attempt.book, ready=False)
    elif kind == "stale":
        attempt.guard_now = attempt.book.verified_at + timedelta(seconds=31)
    elif kind == "source_future":
        attempt.book = replace(attempt.book, source_at=attempt.observed_at)
    elif kind == "source_stale":
        attempt.book = replace(
            attempt.book, source_at=attempt.book.received_at - timedelta(seconds=31)
        )
    elif kind == "unequal_times":
        attempt.book = replace(
            attempt.book, verified_at=attempt.book.verified_at - timedelta(microseconds=1)
        )
    elif kind == "wrong_generation":
        attempt.lease = replace(attempt.lease, generation=attempt.lease.generation + 1)
    elif kind == "gap":
        attempt.lease = replace(attempt.lease, last_input_id=attempt.book.input_id)
    elif kind == "repeated_guard":
        attempt.guard_calls = 2
    elif kind == "unrecorded":
        attempt.evidence_ok = False
    elif kind == "other_identity":
        attempt.error = SourceUnavailableError("same text, wrong identity")
    assert not state.claim(attempt, error)
    assert state.event is None and not state.path.exists()


@pytest.mark.parametrize("microseconds", [1, 230])
async def test_qualifying_rejection_is_recorded_before_rollback(
    tmp_path: Path, microseconds: int
) -> None:
    state = recovery.ClockRecovery(tmp_path / "recovery.json")
    state.window_start = monotonic() - 1
    attempt, error = candidate(state)
    assert attempt.book is not None
    attempt.guard_now = attempt.book.received_at - timedelta(microseconds=microseconds)
    assert state.claim(attempt, error)
    assert not state.retry_ready(attempt, error)
    record = json.loads(state.path.read_text())
    assert record["event"]["status"] == "REJECTED"
    assert not record["event"]["attempts"][0]["rollback_confirmed"]
    assert not record["clock_recovery_warning"]


async def test_inherited_child_guard_cannot_supply_parent_recovery_evidence(tmp_path: Path) -> None:
    state = recovery.ClockRecovery(tmp_path / "r.json")
    state.window_start = monotonic() - 1
    attempt, error = candidate(state)
    attempt.guard_calls = 0
    attempt.error = None
    assert (
        attempt.book is not None and attempt.lease is not None and attempt.observed_at is not None
    )

    book, guard_now = attempt.book, attempt.guard_now
    assert book is not None and guard_now is not None

    async def child() -> None:
        recovery.observe_guard(book, guard_now, error, checked_at=monotonic(), evidence_ok=True)

    with recovery.capture(attempt, attempt.book, attempt.lease, attempt.observed_at):
        await asyncio.create_task(child())
    assert attempt.guard_calls == 0 and not state.claim(attempt, error)


@pytest.mark.parametrize(
    "phase,profile,extra",
    [
        ("SMOKE", internal.NAME, {}),
        ("W3", internal.NAME_V3, {}),
        ("W3", internal.RELEASE_NAME, {}),
        ("W3", internal.NAME, {"worker_only": True}),
        ("W3", internal.NAME, {"diagnostics": True}),
        ("W3", internal.NAME, {"failure_timeline": True}),
        ("CONTROLLED20", internal.NAME, {}),
    ],
)
async def test_unsupported_options_stop_before_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, phase: str, profile: str, extra: dict[str, Any]
) -> None:
    args = argparse.Namespace(
        phase=phase,
        acceptance_profile=profile,
        publisher_clock_recovery=True,
        output=tmp_path / "out",
        **extra,
    )
    monkeypatch.setattr(argparse.ArgumentParser, "parse_args", lambda _: args)
    preflight = AsyncMock()
    monkeypatch.setattr(internal, "run_preflighted", preflight)
    with pytest.raises(SystemExit) as caught:
        await campaign.main()
    assert caught.value.code == 2 and not args.output.exists()
    preflight.assert_not_awaited()
    with pytest.raises(ValueError, match="parent only"):
        await workload.run(args)


async def financial_state(engine: AsyncEngine, owner: UUID) -> dict[str, Any]:
    tables = (
        "paper_wallet_ledger",
        "paper_order_events",
        "paper_position_events",
        "paper_reservations",
        "paper_position_projections",
        "paper_order_commands",
    )
    async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
        return {
            name: (
                await session.execute(
                    "SELECT coalesce(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text),"
                    f"'[]'::jsonb) FROM {name} t"
                )
            ).scalar_one()
            for name in tables
        }


@pytest.mark.usefixtures("internal_database")
async def test_explicit_root_rollback_survives_authorized_context_exit(
    published_market: PublishedMarket,
) -> None:
    engine, book, price = published_market
    witness = create_engine_for(DatabaseRole.MARKET_DATA)
    primary = SourceUnavailableError("controlled rejection")
    try:
        with pytest.raises(SourceUnavailableError) as caught:
            async with market_data_session(engine) as session:
                await session.execute("UPDATE market_execution_state SET ready=false")
                transaction = session._connection.get_transaction()
                assert transaction is not None
                await transaction.rollback()
                raise primary
        assert caught.value is primary
        async with market_data_session(witness) as session:
            # NOWAIT also proves the aborted transaction no longer holds the source row lock.
            row = (
                await session.execute("SELECT ready FROM market_execution_state FOR UPDATE NOWAIT")
            ).one()
            assert row.ready is True
        following, _ = await workload.publish_market(engine, book, price, rebase=False, trade_id=2)
        assert following.last_input_id == book.last_input_id + 1
    finally:
        await witness.dispose()


def inject_clock(monkeypatch: pytest.MonkeyPatch, *, repeat: bool = False) -> list[dict[str, Any]]:
    original_publish = storage.publish_input
    original_locked = storage._locked
    state: dict[str, Any] = {"now": None}
    calls: list[dict[str, Any]] = []

    async def locked(*args: Any, **kwargs: Any) -> Any:
        row = await original_locked(*args, **kwargs)
        return {**row, "db_now": state["now"]} if state["now"] is not None else row

    async def publish(session: Any, lease: Any, book: Any, metadata: Any) -> Any:
        calls.append(
            {
                "input_id": book.input_id,
                "owner": lease.owner,
                "generation": lease.generation,
                "received_at": book.received_at,
            }
        )
        if len(calls) == 1 or repeat:
            state["now"] = book.received_at - timedelta(microseconds=230)
        try:
            return await original_publish(session, lease, book, metadata)
        finally:
            state["now"] = None

    monkeypatch.setattr(storage, "_locked", locked)
    monkeypatch.setattr(workload, "publish_input", publish)
    return calls


@pytest.mark.usefixtures("internal_database")
async def test_real_publication_recovers_once_after_confirmed_rollback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    engine_engine: AsyncEngine,
    owner: UUID,
    production_wallet: PaperWalletSnapshot,
    published_market: PublishedMarket,
) -> None:
    engine, book, price = published_market
    state = recovery.ClockRecovery(tmp_path / "recovery.json")
    state.window_start = monotonic() - 1
    try:
        before = await financial_state(engine_engine, owner)
        calls = inject_clock(monkeypatch)
        with state.observe(), observe_publisher_readiness(tmp_path / "readiness.json"):
            following, following_price = await workload.publish_market(
                engine, book, price, rebase=False, trade_id=2, heartbeat_per_book=True
            )
            assert following.last_input_id == book.last_input_id + 1
            assert (
                following_price.owner == price.owner
                and following_price.generation == price.generation
            )
        assert len(calls) == 2 and calls[0]["input_id"] == calls[1]["input_id"]
        assert (
            calls[0]["owner"] == calls[1]["owner"]
            and calls[0]["generation"] == calls[1]["generation"]
        )
        async with market_data_session(engine) as session:
            ids = await published_input_ids(session)
            assert ids == [book.last_input_id, following.last_input_id]
        assert await financial_state(engine_engine, owner) == before
        record = json.loads(state.path.read_text())
        event = record["event"]
        assert event["status"] == "COMMITTED" and event["retry_count"] == 1
        assert event["attempts"][0]["rollback_confirmed"]
        assert event["prior_session_exited_at"] >= event["rollback_confirmed_at"]
        assert (
            len(event["attempts"]) == 2
            and event["committed_at"] - event["attempts"][0]["guard_checked_at"] <= 1
        )
        assert record["clock_recovery_warning"] and record["recovered_count"] == 1
    finally:
        assert recovery.current() is None


@pytest_asyncio.fixture
async def published_market(internal_database: None) -> AsyncIterator[PublishedMarket]:
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        book, price = await workload.acquire_sources(engine)
        book, price = await workload.publish_market(engine, book, price, rebase=True, trade_id=1)
        yield engine, book, price
    finally:
        await engine.dispose()


@pytest.mark.parametrize("mode", ["repeat_during_retry", "second_incident", "setup", "disabled"])
async def test_real_rejection_never_exceeds_one_campaign_recovery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    published_market: PublishedMarket,
    mode: str,
) -> None:
    engine, book, price = published_market
    state = recovery.ClockRecovery(tmp_path / "recovery.json")
    if mode != "setup":
        state.window_start = monotonic() - 1
    calls = inject_clock(monkeypatch, repeat=mode == "repeat_during_retry")
    if mode == "disabled":
        with (
            pytest.raises(SourceUnavailableError),
            observe_publisher_readiness(tmp_path / "readiness.json"),
        ):
            await workload.publish_market(engine, book, price, rebase=False, trade_id=2)
        assert len(calls) == 1 and state.event is None
    else:
        with (
            pytest.raises(SourceUnavailableError),
            state.observe(),
            observe_publisher_readiness(tmp_path / "readiness.json"),
        ):
            next_book, next_price = await workload.publish_market(
                engine, book, price, rebase=False, trade_id=2
            )
            assert mode == "second_incident"
            # Reset injection for a later logical publication; the global slot is already spent.
            calls = inject_clock(monkeypatch, repeat=True)
            await workload.publish_market(engine, next_book, next_price, rebase=False, trade_id=3)
        assert len(calls) == (2 if mode == "repeat_during_retry" else 1)
        if mode == "setup":
            assert state.event is None
        else:
            assert state.event is not None
            assert state.event["retry_count"] == 1 and state.terminal_rejection is not None
            assert state.event["status"] == (
                "COMMITTED" if mode == "second_incident" else "ABORTED"
            )
    async with market_data_session(engine) as session:
        ids = await published_input_ids(session)
    assert ids == ([1, 2] if mode == "second_incident" else [1])


@pytest.mark.parametrize(
    "kind", ["rollback_error", "rollback_timeout", "cancel", "missing_transaction", "evidence"]
)
async def test_rollback_or_evidence_failure_never_permits_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    published_market: PublishedMarket,
    kind: str,
) -> None:
    engine, book, price = published_market
    state = recovery.ClockRecovery(tmp_path / "recovery.json")
    state.window_start = monotonic() - 1
    calls = inject_clock(monkeypatch)
    original_rollback = AsyncTransaction.rollback

    async def rollback(transaction: AsyncTransaction) -> None:
        if kind == "rollback_error":
            raise OSError("PRIVATE_ROLLBACK_DETAIL")
        if kind == "cancel":
            raise asyncio.CancelledError("PRIVATE_CANCEL_DETAIL")
        await original_rollback(transaction)
        if kind == "rollback_timeout":
            await asyncio.sleep(2)

    if kind in {"rollback_error", "rollback_timeout", "cancel"}:
        monkeypatch.setattr(AsyncTransaction, "rollback", rollback)
    if kind == "missing_transaction":
        from sqlalchemy.ext.asyncio import AsyncConnection

        monkeypatch.setattr(AsyncConnection, "get_transaction", lambda _: None)
    if kind == "evidence":
        original_save = workload.save

        def save(path: Path, value: object) -> None:
            if path == state.path:
                raise OSError("PRIVATE_FILE_DETAIL")
            original_save(path, value)

        monkeypatch.setattr(workload, "save", save)
    expected = (
        asyncio.CancelledError
        if kind == "cancel"
        else TimeoutError
        if kind == "rollback_timeout"
        else OSError
        if kind == "evidence"
        else SourceUnavailableError
    )
    with (
        pytest.raises(expected),
        state.observe(),
        observe_publisher_readiness(tmp_path / "readiness.json"),
    ):
        await workload.publish_market(engine, book, price, rebase=False, trade_id=2)
    assert len(calls) == 1 and state.event is not None
    assert state.event["status"] == "ABORTED" and state.event["retry_count"] == 0
    assert not state.event["attempts"][0]["rollback_confirmed"]
    if state.path.exists():
        assert "PRIVATE" not in state.path.read_text()
    async with market_data_session(engine) as session:
        assert (
            await session.execute("SELECT count(*) FROM market_execution_buffer")
        ).scalar_one() == 1


@pytest.mark.parametrize("after_recovery", [False, True])
async def test_unknown_commit_after_real_commit_is_not_retried(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    published_market: PublishedMarket,
    after_recovery: bool,
) -> None:
    engine, book, price = published_market
    state = recovery.ClockRecovery(tmp_path / "recovery.json")
    state.window_start = monotonic() - 1
    original = market_data_session
    sessions: list[int] = []

    @asynccontextmanager
    async def ambiguous(*args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        sessions.append(len(sessions) + 1)
        async with original(*args, **kwargs) as session:
            yield session
        # A rolled-back session exits normally now; it is not a commit reply.
        if not after_recovery or len(sessions) == 2:
            raise TimeoutError("PRIVATE_COMMIT_REPLY")

    monkeypatch.setattr(workload, "market_data_session", ambiguous)
    if after_recovery:
        inject_clock(monkeypatch)
    with (
        pytest.raises(TimeoutError),
        state.observe(),
        observe_publisher_readiness(tmp_path / "readiness.json"),
    ):
        await workload.publish_market(engine, book, price, rebase=False, trade_id=2)
    assert len(sessions) == (2 if after_recovery else 1)
    async with original(engine) as session:
        ids = await published_input_ids(session)
    assert ids == [1, 2]
    if after_recovery:
        assert state.event is not None and state.event["status"] == "ABORTED"
        assert (
            state.event["retry_count"] == 1 and state.event["attempts"][1]["committed_at"] is None
        )
    else:
        assert state.event is None
    assert "PRIVATE" not in state.path.read_text()


async def test_session_exit_error_after_rollback_is_not_retried(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, published_market: PublishedMarket
) -> None:
    engine, book, price = published_market
    state = recovery.ClockRecovery(tmp_path / "recovery.json")
    state.window_start = monotonic() - 1
    calls = inject_clock(monkeypatch)
    original = market_data_session

    @asynccontextmanager
    async def broken_exit(*args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        try:
            async with original(*args, **kwargs) as session:
                yield session
        finally:
            raise OSError("PRIVATE_EXIT_DETAIL")

    monkeypatch.setattr(workload, "market_data_session", broken_exit)
    with (
        pytest.raises(OSError),
        state.observe(),
        observe_publisher_readiness(tmp_path / "readiness.json"),
    ):
        await workload.publish_market(engine, book, price, rebase=False, trade_id=2)
    assert len(calls) == 1 and state.event is not None
    assert state.event["attempts"][0]["rollback_confirmed"] and state.event["retry_count"] == 0
    assert state.event["status"] == "ABORTED"


async def test_external_cancellation_while_rolling_back_preserves_cancellation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, published_market: PublishedMarket
) -> None:
    engine, book, price = published_market
    state = recovery.ClockRecovery(tmp_path / "recovery.json")
    state.window_start = monotonic() - 1
    calls = inject_clock(monkeypatch)
    entered = asyncio.Event()

    async def held_rollback(transaction: AsyncTransaction) -> None:
        entered.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(AsyncTransaction, "rollback", held_rollback)
    with (
        pytest.raises(asyncio.CancelledError),
        state.observe(),
        observe_publisher_readiness(tmp_path / "readiness.json"),
    ):
        task = asyncio.create_task(
            workload.publish_market(engine, book, price, rebase=False, trade_id=2)
        )
        state.publisher_task = task  # Same explicit binding as the campaign runner.
        try:
            await asyncio.wait_for(entered.wait(), 2)
            task.cancel()
            await task
        finally:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)
    assert task.cancelled() and len(calls) == 1 and state.event is not None
    assert state.event["status"] == "ABORTED" and state.event["retry_count"] == 0
    assert recovery.current() is None


async def test_rejected_attempt_survives_readiness_window_eviction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, published_market: PublishedMarket
) -> None:
    engine, book, price = published_market
    state = recovery.ClockRecovery(tmp_path / "recovery.json")
    state.window_start = monotonic() - 1
    inject_clock(monkeypatch)
    with state.observe(), observe_publisher_readiness(tmp_path / "readiness.json"):
        for tick in range(2, 72):
            book, price = await workload.publish_market(
                engine, book, price, rebase=False, trade_id=tick
            )
    window = json.loads((tmp_path / "readiness.json").read_text())
    assert len(window["checks"]) == 64 and window["discarded_earlier_checks"] > 0
    assert all(row["outcome"] == "RETURNED" for row in window["checks"])
    event = json.loads(state.path.read_text())["event"]
    assert (
        len(event["attempts"]) == 2
        and event["attempts"][0]["error_type"] == "SourceUnavailableError"
    )
    assert event["attempts"][0]["input_id"] == 2 and event["status"] == "COMMITTED"


async def test_fresh_session_sees_rolled_back_source_and_released_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, published_market: PublishedMarket
) -> None:
    engine, book, price = published_market
    state = recovery.ClockRecovery(tmp_path / "recovery.json")
    state.window_start = monotonic() - 1
    original = market_data_session
    async with original(engine) as session:
        before = (
            await session.execute("SELECT to_jsonb(t) FROM market_execution_state t")
        ).scalar_one()
        price_before = (
            await session.execute("SELECT to_jsonb(t) FROM market_price_feed t")
        ).scalar_one()
    sessions = 0

    @asynccontextmanager
    async def observed(*args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        nonlocal sessions
        sessions += 1
        async with original(*args, **kwargs) as session:
            if sessions == 2:
                row = (
                    await session.execute("SELECT * FROM market_execution_state FOR UPDATE NOWAIT")
                ).one()
                assert row.last_input_id == book.last_input_id
                assert (
                    await session.execute("SELECT to_jsonb(t) FROM market_execution_state t")
                ).scalar_one() == before
                assert (
                    await session.execute("SELECT to_jsonb(t) FROM market_price_feed t")
                ).scalar_one() == price_before
                assert state.event is not None and state.event["attempts"][0]["rollback_confirmed"]
            yield session

    monkeypatch.setattr(workload, "market_data_session", observed)
    inject_clock(monkeypatch)
    with state.observe(), observe_publisher_readiness(tmp_path / "readiness.json"):
        following, _ = await workload.publish_market(engine, book, price, rebase=False, trade_id=2)
    assert sessions == 2 and following.last_input_id == book.last_input_id + 1


@pytest.mark.parametrize("failure", ["missing", "malformed", "different"])
async def test_required_recovery_artifact_roundtrip_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    state = recovery.ClockRecovery(tmp_path / "recovery.json")
    state.window_start = monotonic() - 1
    state.window_end = monotonic()

    def save(path: Path, value: object) -> None:
        if failure == "missing":
            return
        path.write_text("INVALID" if failure == "malformed" else "{}")

    monkeypatch.setattr(workload, "save", save)
    with pytest.raises((OSError, ValueError)):
        state.validate_success()


@pytest.mark.parametrize("field", ["window_start", "window_end"])
def test_success_requires_the_measured_window(tmp_path: Path, field: str) -> None:
    state = recovery.ClockRecovery(tmp_path / "r.json")
    state.window_start = 1
    state.window_end = 2
    setattr(state, field, None)
    with pytest.raises(RuntimeError, match="incomplete"):
        state.validate_success()


async def test_approved_configuration_preserves_legacy_defaults() -> None:
    default = argparse.Namespace(phase="W3", acceptance_profile=internal.NAME)
    assert recovery.configuration(default) == {}
    default.publisher_clock_recovery = True
    config = recovery.configuration(default)["publisher_clock_recovery"]
    assert config["max_events"] == config["max_retries"] == 1 and config["budget_seconds"] == 1
    assert config["revision"] == "NC_F17_CLOCK_01"


@pytest.mark.parametrize("fault", ["missing_clock", "nan_clock", "rebase", "missing_tick"])
async def test_incomplete_clock_or_rebase_evidence_cannot_recover(
    tmp_path: Path, fault: str
) -> None:
    state = recovery.ClockRecovery(tmp_path / "r.json")
    state.window_start = monotonic() - 1
    attempt, error = candidate(state)
    assert attempt.book is not None
    if fault == "missing_clock":
        attempt.checked_at = None
    elif fault == "nan_clock":
        attempt.checked_at = float("nan")
    elif fault == "rebase":
        attempt.book = replace(attempt.book, rebase=True)
    elif fault == "missing_tick":
        attempt.tick = None
    assert not state.claim(attempt, error) and state.event is None


@pytest.mark.parametrize("offset", [-0.000001, 0, 0.000001])
async def test_confirmed_commit_budget_boundary_is_not_extended(
    tmp_path: Path, offset: float
) -> None:
    state = recovery.ClockRecovery(tmp_path / "r.json")
    state.window_start = monotonic() - 1
    first, error = candidate(state)
    assert state.claim(first, error) and state.deadline is not None
    state.rolled_back(first)
    state.retrying()
    second, _ = candidate(state)
    second.lease = first.lease
    second.error = None
    assert second.book is not None
    second.guard_now = second.book.received_at
    second.book.require_ready(second.guard_now)
    second.committed_at = state.deadline + offset
    if offset > 0:
        with pytest.raises(TimeoutError):
            state.committed(second)
        assert not state.report()["clock_recovery_warning"]
    else:
        state.committed(second)
        assert state.report()["clock_recovery_warning"]
    assert state.event is not None and state.event["retry_count"] == 1


async def test_absent_guard_observer_never_infers_readiness_from_later_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, published_market: PublishedMarket
) -> None:
    engine, book, price = published_market
    state = recovery.ClockRecovery(tmp_path / "r.json")
    state.window_start = monotonic() - 1
    calls = inject_clock(monkeypatch)
    with pytest.raises(SourceUnavailableError), state.observe():
        await workload.publish_market(engine, book, price, rebase=False, trade_id=2)
    assert len(calls) == 1 and state.event is None


async def test_deadline_after_retry_commit_does_not_submit_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, published_market: PublishedMarket
) -> None:
    engine, book, price = published_market
    state = recovery.ClockRecovery(tmp_path / "r.json")
    state.window_start = monotonic() - 1
    original = market_data_session
    sessions = 0

    @asynccontextmanager
    async def delayed_reply(*args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        nonlocal sessions
        sessions += 1
        async with original(*args, **kwargs) as session:
            yield session
        if sessions == 2:
            await asyncio.sleep(2)

    monkeypatch.setattr(workload, "market_data_session", delayed_reply)
    calls = inject_clock(monkeypatch)
    with (
        pytest.raises(TimeoutError),
        state.observe(),
        observe_publisher_readiness(tmp_path / "readiness.json"),
    ):
        await workload.publish_market(engine, book, price, rebase=False, trade_id=2)
    assert sessions == len(calls) == 2 and state.event is not None
    assert state.event["status"] == "ABORTED" and state.event["retry_count"] == 1
    async with original(engine) as session:
        assert await published_input_ids(session) == [1, 2]


async def test_direct_run_refuses_enabled_option_without_its_campaign_context(
    tmp_path: Path,
) -> None:
    args = argparse.Namespace(
        acceptance_profile=internal.NAME,
        phase="W3",
        publisher_clock_recovery=True,
        output=tmp_path / "out",
    )
    with pytest.raises(ValueError, match="context missing"):
        await workload._run(args)
    assert not args.output.exists()


async def test_inherited_child_publication_cannot_claim_parent_recovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, published_market: PublishedMarket
) -> None:
    engine, book, price = published_market
    state = recovery.ClockRecovery(tmp_path / "r.json")
    state.window_start = monotonic() - 1
    calls = inject_clock(monkeypatch)
    with (
        pytest.raises(SourceUnavailableError),
        state.observe(),
        observe_publisher_readiness(tmp_path / "readiness.json"),
    ):
        await asyncio.create_task(
            workload.publish_market(engine, book, price, rebase=False, trade_id=2)
        )
    assert len(calls) == 1 and state.event is None
    assert recovery.current() is None
    async with market_data_session(engine) as session:
        assert (
            await session.execute("SELECT count(*) FROM market_execution_buffer")
        ).scalar_one() == 1


async def test_internal_session_close_failure_after_rollback_stops_recovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, published_market: PublishedMarket
) -> None:
    from tiewtrade.infra.db.errors import InfraError

    engine, book, price = published_market
    state = recovery.ClockRecovery(tmp_path / "r.json")
    state.window_start = monotonic() - 1
    calls = inject_clock(monkeypatch)
    original_begin = AsyncEngine.begin
    exit_errors: list[BaseException | None] = []

    @asynccontextmanager
    async def broken_begin(current: AsyncEngine) -> AsyncIterator[Any]:
        error: BaseException | None = None
        try:
            async with original_begin(current) as connection:
                try:
                    yield connection
                except BaseException as caught:
                    error = caught
                    raise
        finally:
            exit_errors.append(error)
            raise OSError("PRIVATE_INTERNAL_EXIT")

    with monkeypatch.context() as patch:
        patch.setattr(AsyncEngine, "begin", broken_begin)
        with (
            pytest.raises(InfraError),
            state.observe(),
            observe_publisher_readiness(tmp_path / "readiness.json"),
        ):
            await workload.publish_market(engine, book, price, rebase=False, trade_id=2)
    assert exit_errors == [None]  # The shared _begin normal-exit path must see the close error.
    assert len(calls) == 1 and state.event is not None
    assert state.event["status"] == "ABORTED" and state.event["retry_count"] == 0
    assert state.event["attempts"][0]["rollback_confirmed"]
    async with market_data_session(engine) as session:
        assert await published_input_ids(session) == [1]


async def test_concurrent_input_before_retry_is_not_followed_by_an_extra_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, published_market: PublishedMarket
) -> None:
    engine, book, price = published_market
    state = recovery.ClockRecovery(tmp_path / "r.json")
    state.window_start = monotonic() - 1
    calls = inject_clock(monkeypatch)
    original_session = market_data_session
    sessions = 0

    @asynccontextmanager
    async def interleaved(*args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        nonlocal sessions
        sessions += 1
        if sessions == 2:
            # A separate publisher commits the expected ID after the first rollback.
            await asyncio.create_task(
                workload.publish_market(engine, book, price, rebase=False, trade_id=99)
            )
        async with original_session(*args, **kwargs) as session:
            yield session

    monkeypatch.setattr(workload, "market_data_session", interleaved)
    with (
        pytest.raises(RuntimeError, match="source identity changed before publication"),
        state.observe(),
        observe_publisher_readiness(tmp_path / "readiness.json"),
    ):
        await workload.publish_market(engine, book, price, rebase=False, trade_id=2)
    assert [call["input_id"] for call in calls] == [2, 2]
    assert state.event is not None and state.event["status"] == "ABORTED"
    async with original_session(engine) as session:
        assert await published_input_ids(session) == [1, 2]


async def test_child_failure_during_parent_recovery_does_not_mutate_parent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, published_market: PublishedMarket
) -> None:
    engine, book, price = published_market
    state = recovery.ClockRecovery(tmp_path / "r.json")
    state.window_start = monotonic() - 1
    calls = inject_clock(monkeypatch)
    original_session = market_data_session
    sessions = 0

    @asynccontextmanager
    async def interrupted(*args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        nonlocal sessions
        sessions += 1
        if sessions == 2:
            assert state.event is not None and state.event["status"] == "RETRYING"
            before = json.dumps(state.report(), sort_keys=True)
            latest = state.latest
            with monkeypatch.context() as patch:
                patch.setattr(
                    workload, "renew_book_writer", AsyncMock(side_effect=RuntimeError("child"))
                )
                with pytest.raises(RuntimeError, match="child"):
                    await asyncio.create_task(
                        workload.publish_market(engine, book, price, rebase=False, trade_id=999)
                    )
            assert state.latest is latest
            assert json.dumps(state.report(), sort_keys=True) == before
        async with original_session(*args, **kwargs) as session:
            yield session

    monkeypatch.setattr(workload, "market_data_session", interrupted)
    with state.observe(), observe_publisher_readiness(tmp_path / "readiness.json"):
        await workload.publish_market(engine, book, price, rebase=False, trade_id=2)
    assert len(calls) == 2 and state.event is not None
    assert state.event["status"] == "COMMITTED"
    assert [attempt["tick"] for attempt in state.event["attempts"]] == [2, 2]
