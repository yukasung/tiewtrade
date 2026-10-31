"""Read manual-account evidence inside the existing owner financial transaction."""

from tiewtrade.core.manual_trading import ManualAccountPolicy
from tiewtrade.core.money import Quantity
from tiewtrade.core.orders import AdmissionPolicy, OrderIntent, SourceUnavailableError
from tiewtrade.core.trading_account import AccountUse
from tiewtrade.infra.db.session import UserSession, require_user_session
from tiewtrade.infra.positions.views import held_and_reserved
from tiewtrade.infra.risk_limits.policy import TransactionalRiskPolicy


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
        if intent.scope.episode_id is None:
            raise SourceUnavailableError("Paper episode is required")
        held, reserved = await held_and_reserved(session, intent.scope.episode_id, intent.pair)
    if isinstance(delegate, TransactionalRiskPolicy):
        delegate = await delegate.resolve(session, intent, held=held, reserved=reserved)
    return ManualAccountPolicy(None if use is None else AccountUse(use), held, reserved, delegate)
