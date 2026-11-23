"""Resolve a Paper test ATR instruction once, inside the fill transaction."""

from dataclasses import replace
from uuid import UUID

from tiewtrade.core.money import Money, MoneyError, RoundingDirection, price_for_notional
from tiewtrade.core.orders import OrderConflictError, OrderError
from tiewtrade.core.positions import ExecutionFact, ExecutionSide
from tiewtrade.core.protections import EntryAtrProtection, ProtectionState
from tiewtrade.infra.db.session import UserSession
from tiewtrade.infra.market_data.order_book_storage import read_latest_book
from tiewtrade.infra.protections.storage import load, save


async def resolve_first_fill(
    session: UserSession, order_id: UUID, fact: ExecutionFact, tick: Money | None
) -> bool:
    if fact.side is not ExecutionSide.BUY:
        return False
    if (
        await session.execute("SELECT to_regclass('public.bot_test_entry_anchors')")
    ).scalar_one_or_none() is None:
        return False
    row = (
        await session.execute(
            "SELECT a.*,p.id AS protection_id FROM bot_test_entry_anchors a "
            "LEFT JOIN paper_protections p ON p.entry_order_id=a.order_id "
            "WHERE a.order_id=:order FOR UPDATE OF a",
            {"order": order_id},
        )
    ).one_or_none()
    if row is None or row.execution_id is not None:
        return False
    if row.protection_id is None:
        raise OrderConflictError("first-fill protection allocation missing")
    group = await load(session, row.protection_id)
    if group is None:
        raise OrderConflictError("first-fill protection allocation missing")
    price = price_for_notional(
        fact.quote_amount,
        fact.gross_quantity,
        asset=fact.pair.base,
        rounding=RoundingDirection.TOWARD_NEGATIVE,
    )
    if tick is None:
        tick = (await read_latest_book(session, fact.pair)).metadata.market.price_tick
    levels = None
    failed = False
    try:
        levels = EntryAtrProtection(fact.pair, Money.of(row.atr, fact.pair.quote)).resolve(
            price, tick
        )
    except (OrderError, MoneyError):
        failed = True
    if levels is not None:
        assert levels.take_profit is not None and levels.stop_loss is not None
    await session.execute(
        """UPDATE bot_test_entry_anchors SET execution_id=:execution,anchor_price=:price,
        take_profit=:tp,stop_loss=:sl,failure_code=:failure WHERE order_id=:order""",
        {
            "order": order_id,
            "execution": fact.execution_id,
            "price": price.as_parts()["amount"],
            "tp": None
            if levels is None or levels.take_profit is None
            else levels.take_profit.as_parts()["amount"],
            "sl": None
            if levels is None or levels.stop_loss is None
            else levels.stop_loss.as_parts()["amount"],
            "failure": "PROTECTION_SETUP_REJECTED" if failed else None,
        },
    )
    if levels is not None and group.value.state is not ProtectionState.CANCELED:
        await save(
            session,
            group,
            replace(group.value, prices=levels, revision=group.value.revision + 1),
            kind="REPLACE",
        )
    return failed and group.value.state is not ProtectionState.CANCELED
