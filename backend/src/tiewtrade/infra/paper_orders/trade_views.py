"""Exact owner trade/order snapshots. All arithmetic delegates to shared core types."""

from typing import Any
from uuid import UUID

from tiewtrade.core.manual_trading import available_base, available_quote
from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.order_book import BookState
from tiewtrade.core.orders import OrderConflictError, SourceUnavailableError
from tiewtrade.core.positions import PositionPair
from tiewtrade.core.realtime_prices import Readiness, readiness
from tiewtrade.infra.db.session import UserSession, require_user_session
from tiewtrade.infra.market_data.order_book_storage import read_latest_book
from tiewtrade.infra.market_data.realtime_storage import read_public_snapshot
from tiewtrade.infra.paper_orders.requests import RequestIntegrityError
from tiewtrade.infra.paper_wallet import get_wallet


async def trade_snapshot(
    session: UserSession,
    *,
    risk_policy_available: bool,
    pair: PositionPair | None,
    risk_reason: str | None = None,
) -> dict[str, Any]:
    session = require_user_session(session)
    wallet = await get_wallet(session)
    use = (
        await session.execute(
            "SELECT use FROM user_trading_preferences WHERE user_id=:owner",
            {"owner": session.user_id},
        )
    ).scalar_one_or_none()
    prices = await read_public_snapshot(session)
    observed = next(
        (
            r.observation
            for r in prices.rows
            if pair is not None and (r.base, r.quote) == (pair.base, pair.quote)
        ),
        None,
    )
    reasons: list[str] = []
    if not risk_policy_available:
        reasons.append(risk_reason or "ORDER_SAFETY_UNAVAILABLE")
    if use != "MANUAL":
        reasons.append("MANUAL_USE_REQUIRED")
    if wallet is None:
        reasons.append("PAPER_WALLET_REQUIRED")
    elif wallet.reset_reason == "ACTIVITY_UNKNOWN":
        reasons.append("ORDER_SOURCE_UNAVAILABLE")
    if pair is None:
        reasons.append("ORDER_PAIR_REQUIRED")
    elif prices.catalog_pairs is None or (pair.base, pair.quote) not in prices.catalog_pairs:
        reasons.append("CATALOG_PAIR_REMOVED")
    else:
        row = next((r for r in prices.rows if (r.base, r.quote) == (pair.base, pair.quote)), None)
        feed = prices.feed
        if (
            row is None
            or feed is None
            or row.effective_readiness != Readiness.READY.value
            or readiness(
                quote=row.observation,
                connected=feed.connected,
                reconciled=row.reconciled_generation == feed.generation,
                producer_alive=feed.lease_until > prices.server_time,
                now=prices.server_time,
            )
            is not Readiness.READY
        ):
            reasons.append("ORDER_PRICE_UNAVAILABLE")
        try:
            book = await read_latest_book(session, pair)
            assert isinstance(book.market, BookState)
            book.market.require_ready(prices.server_time)
            if book.metadata.market.unsupported_rules or book.metadata.limit.unsupported_rules:
                reasons.append("ORDER_UNSUPPORTED")
        except SourceUnavailableError:
            reasons.append("ORDER_BOOK_UNAVAILABLE")
    result: dict[str, Any] = {
        "mode": "PAPER",
        "wallet": None,
        "account_use": use,
        "base": None if pair is None else pair.base,
        "quote": "USDT",
        "catalog_revision": prices.catalog_revision,
        "snapshot_at": prices.server_time.isoformat(),
        "market_observed_at": None if observed is None else observed.received_at.isoformat(),
        "admission_ready": not reasons,
        "admission_reasons": reasons,
    }
    if wallet is None:
        return result
    reservations = (
        await session.execute(
            """SELECT base,quote,quote_reserved,base_reserved
        FROM paper_reservations WHERE episode_id=:episode""",
            {"episode": wallet.episode_id},
        )
    ).all()
    positions = (
        await session.execute(
            """SELECT base,quote,held_quantity FROM paper_position_projections
        WHERE episode_id=:episode ORDER BY base,quote""",
            {"episode": wallet.episode_id},
        )
    ).all()
    result["wallet"] = {
        "wallet_id": str(wallet.wallet_id),
        "episode_id": str(wallet.episode_id),
        "balance": wallet.balance.as_parts()["amount"],
        "reserved_quote": None,
        "available_quote": None,
        "base_balances": [],
        "source_availability": "UNKNOWN" if wallet.reset_reason == "ACTIVITY_UNKNOWN" else "READY",
        "revision": wallet.revision,
    }
    if wallet.reset_reason == "ACTIVITY_UNKNOWN":
        return result
    quote_reserved, quote_available = available_quote(
        wallet.balance, tuple(Money.of(r.quote_reserved, r.quote) for r in reservations)
    )
    balances = []
    assets = {r.base for r in positions} | {r.base for r in reservations}
    for asset in sorted(assets):
        held = next(
            (Quantity.of(p.held_quantity, p.base) for p in positions if p.base == asset),
            Quantity.of(0, asset),
        )
        reserved, available = available_base(
            held,
            tuple(Quantity.of(r.base_reserved, asset) for r in reservations if r.base == asset),
        )
        balances.append(
            {
                "asset": asset,
                "held": held.as_parts()["quantity"],
                "reserved": reserved.as_parts()["quantity"],
                "available": available.as_parts()["quantity"],
            }
        )
    result["wallet"].update(
        reserved_quote=quote_reserved.as_parts()["amount"],
        available_quote=quote_available.as_parts()["amount"],
        base_balances=balances,
    )
    return result


_ORDER = """SELECT o.id,o.wallet_id,o.episode_id,o.sequence,o.base,o.quote,o.side,o.kind,
    o.quantity,o.budget,o.limit_price,o.time_in_force,o.accepted_at,
    p.status,p.filled_quantity,p.spent,r.quote_reserved,r.base_reserved,cr.failure_code,
    clock_timestamp() snapshot_at FROM paper_orders o
    LEFT JOIN paper_order_projections p ON p.order_id=o.id
    LEFT JOIN paper_reservations r ON r.order_id=o.id
    LEFT JOIN paper_order_command_results cr ON cr.command_id=o.command_id """


def _order_view(row: Any) -> dict[str, Any]:
    if row.status is None or row.quote_reserved is None or row.base_reserved is None:
        raise RequestIntegrityError("incomplete order projection")
    remaining_quantity = None
    remaining_budget = None
    if row.quantity is not None:
        original = Quantity.of(row.quantity, row.base)
        _, available = available_base(original, (Quantity.of(row.filled_quantity, row.base),))
        remaining_quantity = available.as_parts()["quantity"]
    if row.budget is not None:
        original_quote = Money.of(row.budget, row.quote)
        _, available_quote_value = available_quote(
            original_quote, (Money.of(row.spent, row.quote),)
        )
        remaining_budget = available_quote_value.as_parts()["amount"]
    return {
        "order_id": str(row.id),
        "wallet_id": str(row.wallet_id),
        "episode_id": str(row.episode_id),
        "sequence": row.sequence,
        "mode": "PAPER",
        "base": row.base,
        "quote": row.quote,
        "side": row.side,
        "kind": row.kind,
        "status": row.status,
        "failure_code": row.failure_code,
        "quantity": None
        if row.quantity is None
        else Quantity.of(row.quantity, row.base).as_parts()["quantity"],
        "quote_budget": None
        if row.budget is None
        else Money.of(row.budget, row.quote).as_parts()["amount"],
        "limit_price": None
        if row.limit_price is None
        else Money.of(row.limit_price, row.quote).as_parts()["amount"],
        "time_in_force": row.time_in_force,
        "filled_quantity": Quantity.of(row.filled_quantity, row.base).as_parts()["quantity"],
        "spent": Money.of(row.spent, row.quote).as_parts()["amount"],
        "remaining_quantity": remaining_quantity,
        "remaining_budget": remaining_budget,
        "reserved_quote": Money.of(row.quote_reserved, row.quote).as_parts()["amount"],
        "reserved_base": Quantity.of(row.base_reserved, row.base).as_parts()["quantity"],
        "accepted_at": row.accepted_at.isoformat(),
        "snapshot_at": row.snapshot_at.isoformat(),
    }


async def order_view(session: UserSession, order_id: UUID) -> dict[str, Any] | None:
    session = require_user_session(session)
    row = (await session.execute(_ORDER + "WHERE o.id=:id", {"id": order_id})).one_or_none()
    return None if row is None else _order_view(row)


async def order_page(
    session: UserSession, *, episode_id: UUID, cursor: str | None = None, limit: int = 20
) -> dict[str, Any]:
    session = require_user_session(session)
    if type(limit) is not int or not 1 <= limit <= 100:
        raise OrderConflictError("invalid order page size")
    last_sequence = 0
    if cursor is not None:
        try:
            if len(cursor) > 128:
                raise ValueError
            owner, episode, sequence = cursor.split(":")
            if UUID(owner) != session.user_id or UUID(episode) != episode_id:
                raise ValueError
            last_sequence = int(sequence)
            if last_sequence <= 0:
                raise ValueError
        except ValueError:
            raise OrderConflictError("invalid order cursor") from None
    rows = (
        await session.execute(
            _ORDER
            + """WHERE o.episode_id=:episode AND o.sequence>:after
        ORDER BY o.sequence LIMIT :limit""",
            {"episode": episode_id, "after": last_sequence, "limit": limit + 1},
        )
    ).all()
    visible = rows[:limit]
    now = (await session.execute("SELECT clock_timestamp()")).scalar_one()
    return {
        "orders": [_order_view(row) for row in visible],
        "snapshot_at": now.isoformat(),
        "next_cursor": f"{session.user_id}:{episode_id}:{visible[-1].sequence}"
        if len(rows) > limit
        else None,
    }
