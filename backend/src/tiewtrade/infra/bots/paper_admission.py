"""Resolve the same authoritative risk policy as the Paper financial worker."""

from uuid import UUID

from tiewtrade.core.orders import OrderIntent, OrderOrigin, SafetyUnavailableError, TradingMode
from tiewtrade.infra.db.session import UserSession, require_user_session
from tiewtrade.infra.paper_orders.dispatch import submit_order
from tiewtrade.infra.positions.views import held_and_reserved
from tiewtrade.infra.risk_limits.dispatch import lock_risk_owner
from tiewtrade.infra.risk_limits.policy import TransactionalRiskPolicy
from tiewtrade.infra.trading_stops.storage import global_shared_lock


async def admit_paper_bot_intent(
    session: UserSession, wallet_id: UUID, intent: OrderIntent
) -> UUID:
    """Resolve risk before queueing, in the decision journal's owner transaction."""
    checked = require_user_session(session)
    if (
        intent.origin is not OrderOrigin.BOT
        or intent.scope.owner_id != checked.user_id
        or intent.scope.mode is not TradingMode.PAPER
    ):
        raise SafetyUnavailableError("owner-scoped Paper BOT intent required")
    await global_shared_lock(checked)
    await lock_risk_owner(checked, TradingMode.PAPER)
    held, reserved = await held_and_reserved(checked, intent.scope.episode_id, intent.pair)
    resolved = await TransactionalRiskPolicy().resolve(
        checked, intent, held=held, reserved=reserved
    )
    resolved.check(intent)
    command = await submit_order(checked, wallet_id=wallet_id, intent=intent)
    return command.command_id
