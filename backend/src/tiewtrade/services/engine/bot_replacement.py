"""Apply replacement from the immutable owner request using F-19 authorization."""

from uuid import UUID, uuid5

from tiewtrade.core.orders import OrderOrigin, TradingMode
from tiewtrade.infra.bots.claims import BotRequestClaim
from tiewtrade.infra.bots.start import BotReplacementRefusedError
from tiewtrade.infra.db.session import UserSession
from tiewtrade.infra.trading_stops import read_status
from tiewtrade.infra.trading_stops.storage import current_opening_blocked
from tiewtrade.services.engine.kill_switch import apply_resume


async def clear_replacement_stop(
    session: UserSession, claim: BotRequestClaim, proof: dict[str, object]
) -> None:
    if any(
        type(proof.get(key)) is not int
        for key in ("run_revision", "summary_revision", "reconciliation_revision")
    ) or (proof.get("stop_revision") is not None and type(proof.get("stop_revision")) is not int):
        raise BotReplacementRefusedError("valid acknowledgement revisions required")
    try:
        run_id = UUID(str(proof["run_id"]))
    except (ValueError, KeyError):
        raise BotReplacementRefusedError("valid run identity required") from None
    existing = (
        await session.execute(
            """SELECT id FROM bot_runs
               WHERE id=:run AND user_id=:owner AND mode='PAPER' AND status='STOPPED'
               AND revision=:revision FOR UPDATE""",
            {"run": run_id, "owner": session.user_id, "revision": proof["run_revision"]},
        )
    ).first()
    if existing is None:
        raise BotReplacementRefusedError("stopped run changed")
    status = await read_status(session, TradingMode.PAPER)
    if status.platform_stop_id is not None:
        raise BotReplacementRefusedError("platform stop remains active")
    if status.stop_id is not None:
        if (
            len(status.active_causes) != 1
            or not status.resume_ready
            or str(status.stop_id) != proof.get("stop_id")
            or status.revision != proof.get("stop_revision")
            or status.summary_revision != proof.get("summary_revision")
            or status.reconciliation_revision != proof.get("reconciliation_revision")
        ):
            raise BotReplacementRefusedError("stop acknowledgement no longer matches")
        resume_id = uuid5(claim.hint.request_id, "f19-resume")
        await session.execute(
            "SELECT submit_bot_replacement_resume(:request,:resume)",
            {"request": claim.hint.request_id, "resume": resume_id},
        )
        resume = (
            (
                await session.execute(
                    "SELECT * FROM trading_stop_requests WHERE id=:id", {"id": resume_id}
                )
            )
            .mappings()
            .one()
        )
        await apply_resume(session, resume, project_bot_recovery=False)
        result = (
            await session.execute(
                "SELECT state FROM trading_stop_results WHERE request_id=:id", {"id": resume_id}
            )
        ).scalar_one_or_none()
        if result != "APPLIED":
            raise BotReplacementRefusedError("F-19 refused the acknowledgement")
    else:
        reconciliation = (
            await session.execute(
                """SELECT a.revision FROM paper_wallet_state w JOIN paper_position_activity a
                     ON a.episode_id=w.active_episode_id AND a.user_id=w.user_id
                   WHERE w.user_id=:owner AND a.availability='READY'""",
                {"owner": session.user_id},
            )
        ).scalar_one_or_none()
        if (
            proof.get("stop_id") is not None
            or proof.get("stop_revision") is not None
            or proof.get("summary_revision") != 0
            or reconciliation is None
            or reconciliation != proof.get("reconciliation_revision")
        ):
            raise BotReplacementRefusedError("reconciliation acknowledgement no longer matches")
    if await current_opening_blocked(session, TradingMode.PAPER, OrderOrigin.BOT):
        raise BotReplacementRefusedError("another stop remains active")
    revision = (
        await session.execute(
            """UPDATE bot_runs SET status='RETIRED',revision=revision+1
               WHERE id=:run AND user_id=:owner AND mode='PAPER' AND status='STOPPED'
               RETURNING revision""",
            {"run": run_id, "owner": session.user_id},
        )
    ).scalar_one()
    await session.execute(
        """INSERT INTO bot_run_events(id,run_id,user_id,mode,revision,event,details)
           VALUES(:id,:run,:owner,'PAPER',:revision,'RETIRED_FOR_REPLACEMENT',
                  jsonb_build_object('request_id',CAST(:request AS uuid)))""",
        {
            "id": uuid5(claim.hint.request_id, "retire"),
            "run": run_id,
            "owner": session.user_id,
            "revision": revision,
            "request": claim.hint.request_id,
        },
    )
