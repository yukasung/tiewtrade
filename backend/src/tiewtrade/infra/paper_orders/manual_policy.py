"""Read manual-account evidence inside the existing owner financial transaction."""

from tiewtrade.core.manual_trading import ManualAccountPolicy
from tiewtrade.core.money import Quantity
from tiewtrade.core.orders import AdmissionPolicy, OrderIntent, SourceUnavailableError
from tiewtrade.core.trading_account import AccountUse
from tiewtrade.infra.db.session import UserSession, require_user_session


async def manual_policy_for(
    session: UserSession,
    intent: OrderIntent,
    *,
    delegate: AdmissionPolicy | None,
    held: Quantity | None = None,
    reserved: Quantity | None = None,
) -> ManualAccountPolicy:
    session = require_user_session(session)
    use = (
        await session.execute(
            "SELECT use FROM user_trading_preferences WHERE user_id=:owner",
            {"owner": session.user_id},
        )
    ).scalar_one_or_none()
    if held is None or reserved is None:
        row = (
            await session.execute(
                """SELECT a.availability,p.held_quantity,
            (SELECT coalesce(sum(r.base_reserved),0) FROM paper_reservations r
              WHERE r.episode_id=a.episode_id AND r.base=:base AND r.quote=:quote) AS reserved
            FROM paper_position_activity a LEFT JOIN paper_position_projections p
              ON p.episode_id=a.episode_id AND p.base=:base AND p.quote=:quote
            WHERE a.episode_id=:episode""",
                {
                    "episode": intent.scope.episode_id,
                    "base": intent.pair.base,
                    "quote": intent.pair.quote,
                },
            )
        ).one_or_none()
        if row is None or row.availability != "READY":
            raise SourceUnavailableError("authoritative holdings are unavailable")
        held = Quantity.of(
            row.held_quantity if row.held_quantity is not None else 0, intent.pair.base
        )
        reserved = Quantity.of(row.reserved, intent.pair.base)
    return ManualAccountPolicy(None if use is None else AccountUse(use), held, reserved, delegate)
