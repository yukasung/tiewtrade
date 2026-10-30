"""Durable non-authoritative hints from refused API opening attempts."""

from uuid import UUID, uuid4

from tiewtrade.core.orders import OrderIntent, TradingMode
from tiewtrade.core.risk_limits import RiskReason
from tiewtrade.infra.db.session import UserSession, require_user_session
from tiewtrade.infra.risk_limits.prices import price_watermark


async def request_evaluation(session: UserSession, intent: OrderIntent, wallet_id: UUID) -> None:
    checked = require_user_session(session)
    if intent.scope.owner_id != checked.user_id or intent.scope.mode is not TradingMode.PAPER:
        raise ValueError("evaluation request owner mismatch")
    await checked.execute(
        """INSERT INTO risk_evaluation_requests
        (id,user_id,mode,wallet_id,episode_id,setting_revision,source_revision,price_watermark)
        SELECT :id,s.user_id,s.mode,:wallet,:episode,s.revision,
          coalesce(o.source_revision,0),:watermark
        FROM risk_limit_settings s LEFT JOIN risk_owner_state o USING(user_id,mode)
        WHERE s.mode='PAPER' ON CONFLICT DO NOTHING""",
        {
            "id": uuid4(),
            "wallet": wallet_id,
            "episode": intent.scope.episode_id,
            "watermark": await price_watermark(checked),
        },
    )


async def acknowledge_evaluations(session: UserSession, reason: RiskReason) -> None:
    state = (
        "BREACHED"
        if reason is RiskReason.BREACHED
        else "READY"
        if reason is RiskReason.READY
        else "UNAVAILABLE"
    )
    await session.execute(
        """INSERT INTO risk_evaluation_results(request_id,user_id,mode,state)
        SELECT id,user_id,mode,:state FROM risk_evaluation_requests r
        WHERE r.mode='PAPER' AND NOT EXISTS(SELECT 1 FROM risk_evaluation_results x
          WHERE x.request_id=r.id) ORDER BY recorded_at,id LIMIT 100 ON CONFLICT DO NOTHING""",
        {"state": state},
    )
