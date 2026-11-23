"""Recovery must not reapply a consumed book under a new consumer rebase flag."""

import asyncio
from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market.test_dispatch import intent
from tests.infra.execution_market.test_evidence import source_record
from tests.infra.execution_market.test_worker import AllowPolicy, ready_public_sources
from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.order_book import BookState, MarketTrade
from tiewtrade.core.orders import (
    BaseSize,
    OrderConflictError,
    OrderScope,
    OrderType,
    SimulationProfile,
    TimeInForce,
    TradingMode,
    standard_execution_fee,
)
from tiewtrade.core.paper_matching import MatchingState
from tiewtrade.core.positions import ExecutionSide
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.db.session import market_data_session
from tiewtrade.infra.market_data.order_book_storage import (
    ExecutionInputGapError,
    StoredExecutionInput,
    publish_input,
    renew_book_writer,
)
from tiewtrade.infra.paper_orders import worker
from tiewtrade.infra.paper_orders.codec import state_from_payload, state_payload
from tiewtrade.infra.paper_orders.dispatch import submit_order
from tiewtrade.infra.paper_orders.matching_storage import load_matching_state
from tiewtrade.infra.paper_wallet import get_wallet
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot
from tiewtrade.services.engine.paper_order import run_paper_order_round


def consumed_book_state(record: StoredExecutionInput, book: BookState) -> MatchingState:
    return MatchingState(
        OrderScope(uuid4(), uuid4(), TradingMode.PAPER),
        book.pair,
        SimulationProfile(),
        inputs=(book,),
        input_constraints=(record.metadata.limit,),
        book=book,
        input_market_constraints=(record.metadata.market,),
    )


@pytest.mark.parametrize("rebased", [False, True])
@pytest.mark.parametrize("following", [False, True])
async def test_recovery_skips_identical_consumed_book_after_checkpoint_reload(
    monkeypatch: pytest.MonkeyPatch, rebased: bool, following: bool
) -> None:
    record = source_record()
    assert isinstance(record.market, BookState)
    book = replace(record.market, rebase=False)
    record = replace(record, market=book)
    consumed = replace(book, rebase=rebased)
    state = consumed_book_state(record, consumed)
    state = state_from_payload(state_payload(state))
    next_record = replace(
        record, market=replace(record.market, input_id=record.market.input_id + 1)
    )
    read = AsyncMock(return_value=(next_record,) if following else ())
    monkeypatch.setattr(worker, "read_latest_book", AsyncMock(return_value=record))
    monkeypatch.setattr(worker, "read_inputs", read)
    session: Any = None
    if following:
        result = await worker._recovery_inputs(session, state)
        assert tuple(v.market for v in result) == (next_record.market,)
    else:
        with pytest.raises(worker.NoNewExecutionInputError):
            await worker._recovery_inputs(session, state)
    read.assert_awaited_once_with(session, state.pair, after=consumed.input_id, limit=19)
    assert state.inputs == (consumed,)


@pytest.mark.parametrize(
    "fault", ["generation", "received_at", "price", "quantity", "source_rebase", "limit", "market"]
)
async def test_same_book_recovery_keeps_real_conflicts_closed(
    monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:

    record = source_record()
    assert isinstance(record.market, BookState)
    book = replace(record.market, rebase=False)
    record = replace(record, market=book)
    state = consumed_book_state(record, book)
    if fault == "source_rebase":
        record = replace(record, market=replace(book, rebase=True))
    elif fault == "generation":
        record = replace(record, market=replace(book, generation=book.generation + 1))
    elif fault == "received_at":
        record = replace(
            record, market=replace(book, received_at=book.received_at + timedelta(microseconds=1))
        )
    elif fault in {"price", "quantity"}:
        level = (
            replace(book.asks[0], price=book.asks[0].price + Money.of(1, book.pair.quote))
            if fault == "price"
            else replace(
                book.asks[0], quantity=book.asks[0].quantity + Quantity.of(1, book.pair.base)
            )
        )
        record = replace(record, market=replace(book, asks=(level, *book.asks[1:])))
    else:
        constraints = getattr(record.metadata, fault)
        record = replace(
            record,
            metadata=replace(
                record.metadata,
                **{fault: replace(constraints, minimum_notional=Money.of(6, book.pair.quote))},
            ),
        )
    monkeypatch.setattr(worker, "read_latest_book", AsyncMock(return_value=record))
    read = AsyncMock(return_value=())
    monkeypatch.setattr(worker, "read_inputs", read)
    session: Any = None
    with pytest.raises(OrderConflictError):
        await worker._recovery_inputs(session, state)
    read.assert_not_awaited()


async def test_real_checkpoint_recovery_preserves_queue_then_fills_once(
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:

    market, lease, book, metadata = await ready_public_sources()
    value = replace(
        intent(owner, wallet.episode_id),
        kind=OrderType.LIMIT,
        size=BaseSize(Quantity.of(1, "BTC")),
        limit_price=Money.of(90, "USDT"),
        time_in_force=TimeInForce.GTC,
    )

    async def run(name: str) -> None:
        await run_paper_order_round(
            engine=engine_engine, scan_engine=scan_engine, worker=name, policy=AllowPolicy()
        )

    try:
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            command = await submit_order(session, wallet_id=wallet.wallet_id, intent=value)
        await run("admit")
        await asyncio.sleep(0.22)
        async with market_data_session(market) as market_session:
            lease = await renew_book_writer(market_session, lease)
            now = (await market_session.execute("SELECT clock_timestamp()")).scalar_one()
            book = replace(
                book, input_id=book.input_id + 1, received_at=now, verified_at=now, rebase=False
            )
            lease = await publish_input(market_session, lease, book, metadata)
        await run("consume-normal-book")
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            checkpoint = await load_matching_state(
                session, wallet_id=wallet.wallet_id, scope=value.scope, pair=value.pair
            )
            assert checkpoint.state.inputs[-1] == book
            before = state_payload(checkpoint.state)
            with pytest.raises(worker.NoNewExecutionInputError):
                await worker._recovery_inputs(session, checkpoint.state)
            after = await load_matching_state(
                session, wallet_id=wallet.wallet_id, scope=value.scope, pair=value.pair
            )
            assert state_payload(after.state) == before
        # New connection after pool disposal must recover the persisted cursor.
        await engine_engine.dispose()
        await asyncio.sleep(0.22)
        async with market_data_session(market) as market_session:
            lease = await renew_book_writer(market_session, lease)
            now = (await market_session.execute("SELECT clock_timestamp()")).scalar_one()
            trade = MarketTrade(
                book.pair,
                book.input_id + 1,
                book.generation,
                now,
                77,
                ExecutionSide.BUY,
                Money.of(90, "USDT"),
                Quantity.of(1, "BTC"),
                True,
            )
            await publish_input(market_session, lease, trade, metadata)
        # Exercise the recovery selector with real stored source/evidence and the
        # complete worker transaction; only routing into recovery is selected here.
        monkeypatch.setattr(worker, "_next_or_recovery_inputs", worker._recovery_inputs)
        await asyncio.gather(run("recovery-a"), run("recovery-b"))
        await run("replay")
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            row = (
                await session.execute(
                    "SELECT status,spent,filled_quantity FROM paper_order_projections"
                )
            ).one()
            assert row.status == "FILLED" and Quantity.of(
                row.filled_quantity, "BTC"
            ) == Quantity.of(1, "BTC")
            assert (
                await session.execute("SELECT count(*) FROM paper_execution_links")
            ).scalar_one() == 1
            assert (
                await session.execute("SELECT count(*) FROM paper_position_events")
            ).scalar_one() == 1
            assert (await session.execute("SELECT count(*) FROM paper_orders")).scalar_one() == 1
            assert (
                await session.execute(
                    "SELECT count(*) FROM paper_reservations "
                    "WHERE quote_reserved<>0 OR base_reserved<>0"
                )
            ).scalar_one() == 0
            current = await get_wallet(session)
            assert current is not None and current.balance == wallet.balance - Money.of(
                row.spent, "USDT"
            )
            projection = (
                await session.execute(
                    "SELECT total_cost,held_quantity FROM paper_position_projections"
                )
            ).one()
            assert Money.of(projection.total_cost, "USDT") == Money.of(row.spent, "USDT")
            gross = Quantity.of(row.filled_quantity, "BTC")
            fee = standard_execution_fee(ExecutionSide.BUY, gross, Money.of(row.spent, "USDT"))
            assert isinstance(fee.amount, Quantity)
            assert Quantity.of(projection.held_quantity, "BTC") == gross - fee.amount
            assert (
                await session.execute(
                    "SELECT state FROM paper_order_dispatch WHERE command_id=:id",
                    {"id": command.command_id},
                )
            ).scalar_one() == "TERMINAL"
    finally:
        await market.dispose()


@pytest.mark.parametrize("cause", ["stale", "gap"])
async def test_normal_selector_recovers_without_replaying_consumed_book(
    monkeypatch: pytest.MonkeyPatch, cause: str
) -> None:

    record = source_record()
    assert isinstance(record.market, BookState)
    book = replace(record.market, rebase=False)
    record = replace(record, market=book)
    state = consumed_book_state(record, book)
    stale = replace(record, market=replace(book, input_id=book.input_id + 1))
    now = book.received_at + timedelta(seconds=2)
    fresh = replace(
        stale, market=replace(book, input_id=book.input_id + 1, received_at=now, verified_at=now)
    )
    first: Any = ExecutionInputGapError("controlled gap") if cause == "gap" else (stale,)
    monkeypatch.setattr(worker, "read_inputs", AsyncMock(side_effect=[first, (fresh,)]))
    monkeypatch.setattr(worker, "read_latest_book", AsyncMock(return_value=record))
    session: Any = SimpleNamespace(
        execute=AsyncMock(return_value=SimpleNamespace(scalar_one=lambda: now))
    )
    result = await worker._next_or_recovery_inputs(session, state)
    assert tuple(v.market for v in result) == (fresh.market,)
