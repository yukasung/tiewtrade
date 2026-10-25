"""F-15 review regressions through actual fenced workers and financial writers."""

import asyncio
from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market.test_dispatch import intent
from tests.infra.execution_market.test_worker import AllowPolicy, ready_public_sources
from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.order_book import BookLevel, MarketTrade
from tiewtrade.core.orders import (
    BaseSize,
    OrderConstraintError,
    OrderStatus,
    OrderType,
    QuoteBudget,
    TimeInForce,
    UnsupportedOrderError,
)
from tiewtrade.core.positions import ExecutionSide
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.db.session import market_data_session
from tiewtrade.infra.market_data.order_book_storage import publish_input
from tiewtrade.infra.paper_orders.codec import execution_from_payload
from tiewtrade.infra.paper_orders.corrections import correct_fill
from tiewtrade.infra.paper_orders.dispatch import (
    DueOrder,
    claim_order,
    defer_claim,
    submit_cancel,
    submit_order,
)
from tiewtrade.infra.paper_orders.matching_storage import load_matching_state, load_order_state
from tiewtrade.infra.paper_orders.worker import process_claimed_order
from tiewtrade.infra.paper_wallet import get_wallet
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot
from tiewtrade.infra.positions import PositionEventKind


async def process(engine: AsyncEngine, owner: UUID, command: UUID) -> None:
    async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
        due = (
            await session.execute(
                """UPDATE paper_order_dispatch SET next_attempt_at=clock_timestamp()
            WHERE command_id=:id RETURNING next_attempt_at""",
                {"id": command},
            )
        ).scalar_one()
        claim = await claim_order(
            session, DueOrder(command, owner, due), worker="review-regression"
        )
    assert claim is not None
    try:
        async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
            await process_claimed_order(session, claim, policy=AllowPolicy())
    except (OrderConstraintError, UnsupportedOrderError):
        async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
            await defer_claim(session, claim)
        raise


async def cancel(
    engine: AsyncEngine, owner: UUID, wallet: PaperWalletSnapshot, order: UUID
) -> None:
    async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
        command = await submit_cancel(
            session,
            wallet_id=wallet.wallet_id,
            episode_id=wallet.episode_id,
            order_id=order,
            idempotency_key=uuid4(),
        )
    await process(engine, owner, command.command_id)


async def test_active_correction_rebase_skips_pre_rebase_trade_after_reload(
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    market, lease, book, metadata = await ready_public_sources()
    value = replace(
        intent(owner, wallet.episode_id),
        kind=OrderType.LIMIT,
        size=BaseSize(Quantity.of(2, "BTC")),
        limit_price=Money.of(99, "USDT"),
        time_in_force=TimeInForce.GTC,
    )
    try:
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            command = await submit_order(session, wallet_id=wallet.wallet_id, intent=value)
        await process(engine_engine, owner, command.command_id)
        await asyncio.sleep(0.12)
        async with market_data_session(market) as public_session:
            now = (await public_session.execute("SELECT clock_timestamp()")).scalar_one()
            placed = replace(
                book,
                bids=(
                    BookLevel(Money.of(99, "USDT"), Quantity.of(10, "BTC")),
                    BookLevel(Money.of(1, "USDT"), Quantity.of(10, "BTC")),
                ),
                input_id=book.input_id + 1,
                received_at=now,
                verified_at=now,
                rebase=False,
            )
            lease = await publish_input(public_session, lease, placed, metadata)
        await process(engine_engine, owner, command.command_id)
        async with market_data_session(market) as public_session:
            now = (await public_session.execute("SELECT clock_timestamp()")).scalar_one()
            initial = MarketTrade(
                book.pair,
                placed.input_id + 1,
                book.generation,
                now,
                1,
                ExecutionSide.BUY,
                Money.of(99, "USDT"),
                Quantity.of("10.5", "BTC"),
                True,
            )
            lease = await publish_input(public_session, lease, initial, metadata)
        await process(engine_engine, owner, command.command_id)
        async with market_data_session(market) as public_session:
            now = (await public_session.execute("SELECT clock_timestamp()")).scalar_one()
            old = replace(
                initial,
                input_id=initial.input_id + 1,
                received_at=now,
                trade_id=2,
                quantity=Quantity.of(1, "BTC"),
            )
            lease = await publish_input(public_session, lease, old, metadata)
            now = (await public_session.execute("SELECT clock_timestamp()")).scalar_one()
            rebased = replace(
                placed,
                input_id=old.input_id + 1,
                received_at=now,
                verified_at=now,
                bids=(
                    BookLevel(Money.of(99, "USDT"), Quantity.of(0, "BTC")),
                    BookLevel(Money.of(1, "USDT"), Quantity.of(10, "BTC")),
                ),
            )
            lease = await publish_input(public_session, lease, rebased, metadata)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            source = (
                await session.execute(
                    """SELECT l.position_event_id,l.order_event_id,e.payload
                FROM paper_execution_links l
                JOIN paper_order_events e ON e.id=l.order_event_id WHERE l.order_id=:order""",
                    {"order": value.order_id},
                )
            ).one()
            original = execution_from_payload(source.payload["execution"])
            corrected = replace(
                original,
                gross_quantity=Quantity.of("0.25", "BTC"),
                quote_amount=Money.of("24.75", "USDT"),
                fee=None,
            )
            await correct_fill(
                session,
                wallet_id=wallet.wallet_id,
                episode_id=wallet.episode_id,
                order_event_id=source.order_event_id,
                correction_event_id=uuid4(),
                supersedes_position_event_id=source.position_event_id,
                kind=PositionEventKind.REPLACE,
                fact=corrected,
            )
        # A new transaction reloads the durable checkpoint, just as after worker restart.
        await process(engine_engine, owner, command.command_id)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            saved = await load_matching_state(
                session, wallet_id=wallet.wallet_id, scope=value.scope, pair=value.pair
            )
            cash = await get_wallet(session)
            count = (
                await session.execute(
                    """SELECT count(*) FROM paper_execution_links WHERE order_id=:order
                    AND position_event_kind='RECORD'""",
                    {"order": value.order_id},
                )
            ).scalar_one()
        assert saved.state.inputs[-1].input_id == rebased.input_id
        assert saved.state.orders[0].filled == Quantity.of("0.25", "BTC")
        assert cash is not None and cash.balance == Money.of("9975.25", "USDT")
        assert count == 1
        await cancel(engine_engine, owner, wallet, value.order_id)
    finally:
        await market.dispose()


async def test_market_expiry_has_immutable_reason_and_terminal_state(
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    market, lease, book, metadata = await ready_public_sources()
    value = replace(intent(owner, wallet.episode_id), size=QuoteBudget(Money.of(150, "USDT")))
    try:
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            command = await submit_order(session, wallet_id=wallet.wallet_id, intent=value)
        await process(engine_engine, owner, command.command_id)
        await asyncio.sleep(0.12)
        async with market_data_session(market) as public_session:
            now = (await public_session.execute("SELECT clock_timestamp()")).scalar_one()
            await publish_input(
                public_session,
                lease,
                replace(
                    book,
                    input_id=book.input_id + 1,
                    received_at=now,
                    verified_at=now,
                    rebase=False,
                    asks=(BookLevel(Money.of(100, "USDT"), Quantity.of(1, "BTC")),),
                ),
                metadata,
            )
        await process(engine_engine, owner, command.command_id)

        class ProjectionProbeError(Exception):
            pass

        with pytest.raises(ProjectionProbeError):
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                events = (
                    (
                        await session.execute(
                            """SELECT payload FROM paper_order_events
                            WHERE order_id=:order AND event_kind='EXPIRED'""",
                            {"order": value.order_id},
                        )
                    )
                    .scalars()
                    .all()
                )
                assert len(events) == 1
                assert events[0]["reason"] == "MARKET_REMAINDER_UNMATCHED"
                assert events[0]["order"]["filled"] == "1"
                # Corrupt only the rebuildable projection; history must remain authoritative.
                await session.execute(
                    """UPDATE paper_order_projections SET filled_quantity=0,spent=0
                    WHERE order_id=:order""",
                    {"order": value.order_id},
                )
                recovered = await load_order_state(session, value.order_id)
                assert recovered.status is OrderStatus.EXPIRED
                assert recovered.filled == Quantity.of(1, "BTC")
                assert recovered.spent == Money.of(100, "USDT")
                assert recovered.reservation.quote == Money.of(0, "USDT")
                raise ProjectionProbeError
    finally:
        await market.dispose()


@pytest.mark.parametrize("unsupported", [False, True])
async def test_execution_market_rules_fail_before_any_financial_effect(
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    unsupported: bool,
) -> None:
    market, lease, book, metadata = await ready_public_sources()
    value = replace(intent(owner, wallet.episode_id), size=QuoteBudget(Money.of(100, "USDT")))
    try:
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            command = await submit_order(session, wallet_id=wallet.wallet_id, intent=value)
        await process(engine_engine, owner, command.command_id)
        await asyncio.sleep(0.12)
        rules = replace(
            metadata.market,
            maximum_quantity=Quantity.of(1, "BTC"),
            unsupported_rules=("NEW_MARKET_RULE",) if unsupported else (),
        )
        async with market_data_session(market) as public_session:
            now = (await public_session.execute("SELECT clock_timestamp()")).scalar_one()
            await publish_input(
                public_session,
                lease,
                replace(
                    book,
                    input_id=book.input_id + 1,
                    received_at=now,
                    verified_at=now,
                    rebase=False,
                    bids=(BookLevel(Money.of(49, "USDT"), Quantity.of(10, "BTC")),),
                    asks=(BookLevel(Money.of(50, "USDT"), Quantity.of(10, "BTC")),),
                ),
                replace(metadata, market=rules),
            )
        with pytest.raises(UnsupportedOrderError if unsupported else OrderConstraintError):
            await process(engine_engine, owner, command.command_id)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            current = await get_wallet(session)
            count = (
                await session.execute(
                    "SELECT count(*) FROM paper_execution_links WHERE order_id=:order",
                    {"order": value.order_id},
                )
            ).scalar_one()
            reservation = (
                await session.execute(
                    "SELECT quote_reserved FROM paper_reservations WHERE order_id=:order",
                    {"order": value.order_id},
                )
            ).scalar_one()
        assert current is not None and current.balance == wallet.balance
        assert count == 0 and Money.of(reservation, "USDT") == Money.of(100, "USDT")
        await cancel(engine_engine, owner, wallet, value.order_id)
    finally:
        await market.dispose()
