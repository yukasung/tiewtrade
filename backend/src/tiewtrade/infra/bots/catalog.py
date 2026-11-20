"""Apply F-37 catalog withdrawals to scoped bot runs and retain the acknowledgement."""

from dataclasses import dataclass
from uuid import UUID, uuid5

from tiewtrade.core.orders import TradingMode
from tiewtrade.infra.db.session import ScanSession, UserSession, require_user_session
from tiewtrade.infra.risk_limits.dispatch import lock_risk_owner
from tiewtrade.infra.trading_stops.storage import global_shared_lock


@dataclass(frozen=True, slots=True)
class CatalogStopHint:
    run_id: UUID
    user_id: UUID
    mode: TradingMode
    withdrawal_revision: int


async def due_catalog_stops(
    session: ScanSession, *, limit: int = 20
) -> tuple[CatalogStopHint, ...]:
    if not isinstance(session, ScanSession) or type(limit) is not int or not 1 <= limit <= 20:
        raise ValueError("bounded scan session required")
    rows = (
        await session.execute("SELECT * FROM due_bot_catalog_stops(:limit)", {"limit": limit})
    ).all()
    return tuple(
        CatalogStopHint(row.run_id, row.user_id, TradingMode(row.mode), row.withdrawal_revision)
        for row in rows
    )


async def apply_catalog_stop(session: UserSession, hint: CatalogStopHint) -> bool:
    checked = require_user_session(session)
    if checked.user_id != hint.user_id:
        raise ValueError("catalog stop owner mismatch")
    await global_shared_lock(checked)
    await lock_risk_owner(checked, hint.mode)
    params = {
        "run": hint.run_id,
        "owner": hint.user_id,
        "mode": hint.mode.value,
        "withdrawn": hint.withdrawal_revision,
    }
    receipt = (
        await checked.execute(
            """INSERT INTO bot_catalog_stops(run_id,user_id,mode,withdrawal_revision)
              SELECT r.id,r.user_id,r.mode,c.revision
              FROM bot_runs r
              JOIN bot_run_events e ON e.run_id=r.id AND e.user_id=r.user_id AND e.mode=r.mode
                AND e.event='START_REQUEST_APPLIED' AND e.revision=1
              JOIN supported_symbol_events c ON c.revision=:withdrawn AND c.status='REMOVED'
                AND c.base=e.details->>'base' AND c.quote=e.details->>'quote'
                AND c.revision>(e.details->>'catalog_revision')::bigint
              WHERE r.id=:run AND r.user_id=:owner AND r.mode=:mode AND r.status<>'RETIRED'
              ON CONFLICT(run_id,withdrawal_revision) DO NOTHING RETURNING run_id""",
            params,
        )
    ).scalar_one_or_none()
    if receipt is None:
        return False
    revision = (
        await checked.execute(
            """UPDATE bot_runs SET status='STOPPED',revision=revision+1
               WHERE id=:run AND user_id=:owner AND mode=:mode RETURNING revision""",
            params,
        )
    ).scalar_one()
    await checked.execute(
        """INSERT INTO bot_run_events(id,run_id,user_id,mode,revision,event,details)
           VALUES(:id,:run,:owner,:mode,:revision,'CATALOG_REMOVED',
             jsonb_build_object('withdrawal_revision',CAST(:withdrawn AS bigint)))""",
        {
            **params,
            "id": uuid5(hint.run_id, f"catalog:{hint.withdrawal_revision}"),
            "revision": revision,
        },
    )
    return True
