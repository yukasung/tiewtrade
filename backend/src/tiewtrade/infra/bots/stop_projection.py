"""Project an F-19 stop into the durable bot run within the owner transaction."""

from datetime import datetime
from uuid import UUID, uuid5

from tiewtrade.core.orders import OrderOrigin, TradingMode
from tiewtrade.infra.db.session import UserSession, require_user_session
from tiewtrade.infra.trading_stops.storage import current_opening_blocked


async def stop_current_run(
    session: UserSession,
    *,
    mode: TradingMode,
    stop_id: UUID,
    stop_cause: str,
    cutoff: datetime,
) -> None:
    """Called once the stop writer holds the global/owner admission locks."""
    checked = require_user_session(session)
    changed = (
        await checked.execute(
            """UPDATE bot_runs SET status='STOPPED',revision=revision+1
                WHERE user_id=:owner AND mode=:mode AND created_at<=:cutoff
                  AND status NOT IN ('STOPPED','RETIRED')
                RETURNING id,revision""",
            {"owner": checked.user_id, "mode": mode.value, "cutoff": cutoff},
        )
    ).one_or_none()
    if changed is None:
        return
    await checked.execute(
        """INSERT INTO bot_run_events(id,run_id,user_id,mode,revision,event,details)
           VALUES(:id,:run,:owner,:mode,:revision,'TRADING_STOP',
             jsonb_build_object('stop_id',CAST(:stop AS uuid),'cause',CAST(:cause AS text)))""",
        {
            "id": uuid5(stop_id, str(changed.id)),
            "run": changed.id,
            "owner": checked.user_id,
            "mode": mode.value,
            "revision": changed.revision,
            "stop": stop_id,
            "cause": stop_cause,
        },
    )


async def recover_after_owner_resume(
    session: UserSession, *, stop_id: UUID, resume_id: UUID
) -> bool:
    """Move only the existing Paper run into recovery after F-19 accepts a resume."""
    checked = require_user_session(session)
    if await current_opening_blocked(checked, TradingMode.PAPER, OrderOrigin.BOT):
        return False
    row = (
        await checked.execute(
            """UPDATE bot_runs r SET status='RECOVERING',revision=revision+1
               WHERE r.user_id=:owner AND r.mode='PAPER' AND r.status='STOPPED'
                 AND EXISTS(
                   SELECT 1 FROM bot_run_events e WHERE e.run_id=r.id AND e.user_id=r.user_id
                     AND e.mode=r.mode AND e.event IN ('TRADING_STOP',
                       'STRATEGY_VERSION_UNAVAILABLE','STRATEGY_EVALUATION_FAILED'))
                 AND NOT EXISTS(SELECT 1 FROM bot_catalog_stops c WHERE c.run_id=r.id)
               RETURNING r.id,r.revision""",
            {"owner": checked.user_id},
        )
    ).one_or_none()
    if row is None:
        return False
    await checked.execute(
        """INSERT INTO bot_run_events(id,run_id,user_id,mode,revision,event,details)
           VALUES(:id,:run,:owner,'PAPER',:revision,'RESUME_RECONCILING',
             jsonb_build_object('stop_id',CAST(:stop AS uuid),
                                'resume_id',CAST(:resume AS uuid)))""",
        {
            "id": uuid5(resume_id, str(row.id)),
            "run": row.id,
            "owner": checked.user_id,
            "revision": row.revision,
            "stop": stop_id,
            "resume": resume_id,
        },
    )
    return True
