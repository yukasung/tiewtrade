"""Persist owner-scoped F-19 system stops and their failure context."""

import json
from uuid import UUID, uuid5

from tiewtrade.core.orders import OrderConflictError
from tiewtrade.infra.db.session import UserSession


async def stop_for_protection_failure(
    session: UserSession, *, entry_order_id: UUID, protection_id: UUID
) -> None:
    """Run under global shared and Paper owner locks in the protection transaction."""
    run = (
        await session.execute(
            """SELECT b.run_id FROM bot_order_links b
               WHERE b.order_id=:entry AND b.user_id=:owner AND b.mode='PAPER'""",
            {"entry": entry_order_id, "owner": session.user_id},
        )
    ).scalar_one_or_none()
    if run is None:
        raise OrderConflictError("protection failure has no bot run authority")
    await request_system_stop(
        session,
        run_id=UUID(str(run)),
        stop_id=uuid5(protection_id, "setup-failed"),
        reason="PROTECTION_SETUP_FAILED",
    )


async def request_system_stop(
    session: UserSession,
    *,
    run_id: UUID,
    stop_id: UUID,
    reason: str,
    input_identity: str | None = None,
    feedback_status: dict[str, str | int] | None = None,
) -> None:
    """Persist the run transition and F-19 authority in one owner transaction."""
    identity = {"id": stop_id, "owner": session.user_id, "run": run_id, "reason": reason}
    revision = (
        await session.execute(
            """UPDATE bot_runs SET status='STOPPED',revision=revision+1
               WHERE id=:run AND user_id=:owner AND mode='PAPER' AND status<>'RETIRED'
               RETURNING revision""",
            identity,
        )
    ).scalar_one_or_none()
    if revision is None:
        raise OrderConflictError("system stop run unavailable")
    await session.execute(
        """INSERT INTO bot_run_events(id,run_id,user_id,mode,revision,event,details)
           VALUES(:id,:run,:owner,'PAPER',:revision,:reason,
             jsonb_build_object('stop_id',CAST(:id AS uuid),
                               'input_identity',CAST(:input AS text),
                               'feedback_status',CAST(:feedback AS jsonb)))""",
        {
            **identity,
            "revision": revision,
            "input": input_identity,
            "feedback": None if feedback_status is None else json.dumps(feedback_status),
        },
    )
    await session.execute(
        """INSERT INTO trading_stop_requests
            (id,user_id,scope_owner_id,mode,action,cause,actor_role,idempotency_key,
             fingerprint,reason_code,generation,recorded_at)
           SELECT :id,:owner,:owner,'PAPER','STOP','SYSTEM','SYSTEM',:id,
                  repeat('0',64),:reason,coalesce(max(generation),0)+1,clock_timestamp()
           FROM trading_stop_requests
           WHERE scope_owner_id=:owner AND mode='PAPER' AND cause='SYSTEM'""",
        identity,
    )
    await session.execute(
        "INSERT INTO trading_stop_dispatch(request_id,user_id) VALUES(:id,:owner)", identity
    )
