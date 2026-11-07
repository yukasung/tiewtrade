"""Terminal-history optimization retains fallback behavior and owner RLS."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market.order_history_assertions import assert_terminal_history
from tests.infra.execution_market.test_dispatch import intent
from tests.infra.execution_market.test_review_regressions import cancel, process
from tests.infra.execution_market.test_worker import ready_public_sources
from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.orders import OrderConflictError, OrderStatus
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.paper_orders.dispatch import submit_order
from tiewtrade.infra.paper_orders.matching_storage import load_matching_state, load_order_state
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot
from tiewtrade.infra.users import create_user


@pytest.mark.parametrize("terminal", [False, True])
async def test_order_history_fallback_missing_and_wrong_owner_are_unchanged(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    terminal: bool,
) -> None:
    market, _, _, _ = await ready_public_sources()
    other = uuid4()
    await create_user(api_engine, other)
    value = intent(owner, wallet.episode_id)
    try:
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            command = await submit_order(session, wallet_id=wallet.wallet_id, intent=value)
        await process(engine_engine, owner, command.command_id)
        if terminal:
            await cancel(engine_engine, owner, wallet, value.order_id)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            if terminal:
                current = await assert_terminal_history(session, value.order_id)
                assert current.status is OrderStatus.CANCELED
                assert current.filled == Quantity.of(0, "BTC")
                assert current.spent == Money.of(0, "USDT")
            else:
                # No terminal snapshot exists; retain the pre-terminal/legacy projection path.
                current = await load_order_state(session, value.order_id)
                checkpoint = await load_matching_state(
                    session, wallet_id=wallet.wallet_id, scope=value.scope, pair=value.pair
                )
                assert current == checkpoint.state.orders[0]
                assert current.status is OrderStatus.ACCEPTED
                assert current.reservation.quote == Money.of(100, "USDT")
            with pytest.raises(OrderConflictError, match="order projection is unavailable"):
                await load_order_state(session, uuid4())
        async with user_session(engine_engine, other, role=DatabaseRole.ENGINE) as session:
            with pytest.raises(OrderConflictError, match="order projection is unavailable"):
                await load_order_state(session, value.order_id)
    finally:
        await market.dispose()
