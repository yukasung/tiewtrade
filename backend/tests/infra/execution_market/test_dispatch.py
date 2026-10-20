"""Durable Paper command admission, ownership, fairness and lease fencing."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.core.money import Money
from tiewtrade.core.orders import (
    OrderConflictError,
    OrderIntent,
    OrderOrigin,
    OrderScope,
    OrderType,
    QuoteBudget,
    TradingMode,
)
from tiewtrade.core.positions import ExecutionSide, PositionPair
from tiewtrade.infra.db import DatabaseRole, scan_session_bypassing_rls, user_session
from tiewtrade.infra.paper_orders.dispatch import (
    OrderClaimLostError,
    claim_order,
    due_orders,
    require_claim,
    submit_order,
)
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot


def intent(owner: UUID, episode: UUID, *, key: UUID | None = None) -> OrderIntent:
    episode = UUID(str(episode))
    return OrderIntent(
        uuid4(),
        key or uuid4(),
        OrderScope(owner, episode, TradingMode.PAPER),
        PositionPair("BTC", "USDT"),
        OrderOrigin.MANUAL,
        ExecutionSide.BUY,
        OrderType.MARKET,
        QuoteBudget(Money.of(100, "USDT")),
    )


async def test_submit_initializes_replays_and_rejects_payload_conflict(
    engine_engine: AsyncEngine, owner: UUID, wallet: PaperWalletSnapshot
) -> None:
    value = intent(owner, wallet.episode_id)
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        first = await submit_order(session, wallet_id=wallet.wallet_id, intent=value)
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        replay = await submit_order(session, wallet_id=wallet.wallet_id, intent=value)
        initialized = (
            await session.execute(
                "SELECT count(*) FROM paper_order_initializations WHERE episode_id=:episode",
                {"episode": wallet.episode_id},
            )
        ).scalar_one()
    assert replay == first
    assert initialized == 1
    changed = intent(owner, wallet.episode_id, key=value.idempotency_key)
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        with pytest.raises(OrderConflictError):
            await submit_order(session, wallet_id=wallet.wallet_id, intent=changed)


async def test_scanner_is_fair_and_expired_claim_is_fenced(
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await submit_order(
            session, wallet_id=wallet.wallet_id, intent=intent(owner, wallet.episode_id)
        )
        await submit_order(
            session, wallet_id=wallet.wallet_id, intent=intent(owner, wallet.episode_id)
        )
    async with scan_session_bypassing_rls(scan_engine) as scan:
        due = await due_orders(scan)
    owned = [value for value in due if value.user_id == owner]
    assert len(owned) == 1
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        first = await claim_order(session, owned[0], worker="one")
    assert first is not None
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await session.execute(
            """UPDATE paper_order_dispatch SET lease_until=clock_timestamp()-interval '1 second'
            WHERE command_id=:id""",
            {"id": first.command_id},
        )
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        second = await claim_order(session, owned[0], worker="two")
    assert second is not None and second.claim_id != first.claim_id
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        with pytest.raises(OrderClaimLostError):
            await require_claim(session, first)
        await require_claim(session, second)
