"""Owner-scoped authoritative kill-switch status views."""

from tiewtrade.core.orders import TradingMode
from tiewtrade.core.trading_stops import StopCause, progress_for
from tiewtrade.infra.db.session import UserSession, require_user_session
from tiewtrade.infra.trading_stops.records import StopStatus


async def read_status(session: UserSession, mode: TradingMode) -> StopStatus:
    checked = require_user_session(session)
    active = (
        await checked.execute(
            """WITH latest AS (
              SELECT * FROM trading_stop_requests s WHERE s.action='STOP'
                AND s.scope_owner_id=:owner AND s.mode=:mode
              ORDER BY revision DESC LIMIT 1)
            SELECT s.*,j.id risk_stop_id,p.target_set_complete,p.effects_revision,p.target_count,
              p.pending_count,p.failed_count,x.state result_state
            FROM latest s LEFT JOIN risk_stop_requests j ON j.authority_request_id=s.id
            LEFT JOIN risk_stop_progress p ON p.stop_id=j.id
            LEFT JOIN trading_stop_results x ON x.request_id=s.id
            WHERE NOT EXISTS(SELECT 1 FROM trading_stop_requests r
              JOIN trading_stop_results resumed ON resumed.request_id=r.id
                AND resumed.state='APPLIED'
              WHERE r.action='RESUME' AND r.expected_stop_id=s.id)""",
            {"owner": checked.user_id, "mode": mode.value},
        )
    ).one_or_none()
    platform = (
        await checked.execute(
            """WITH latest AS (
              SELECT * FROM trading_stop_requests s WHERE s.action='STOP' AND s.cause='PLATFORM'
              ORDER BY revision DESC LIMIT 1)
            SELECT s.id,s.reason_text,s.revision FROM latest s
            WHERE NOT EXISTS(SELECT 1 FROM trading_stop_requests r
              JOIN trading_stop_results x ON x.request_id=r.id AND x.state='APPLIED'
              WHERE r.action='RESUME' AND r.expected_stop_id=s.id)"""
        )
    ).one_or_none()
    account_use = (
        await checked.execute(
            "SELECT use FROM user_trading_preferences WHERE user_id=:owner",
            {"owner": checked.user_id},
        )
    ).scalar_one_or_none()
    reconciliation_revision = 0
    reconciliation_ready = mode is TradingMode.LIVE
    if mode is TradingMode.PAPER:
        reconciliation = (
            await checked.execute(
                """SELECT coalesce(a.revision,0) revision,
                  coalesce(a.availability='READY',false) ready
                FROM paper_wallet_state w LEFT JOIN paper_position_activity a
                  ON a.episode_id=w.active_episode_id WHERE w.user_id=:owner""",
                {"owner": checked.user_id},
            )
        ).one_or_none()
        reconciliation_revision = 0 if reconciliation is None else int(reconciliation.revision)
        reconciliation_ready = reconciliation is None or bool(reconciliation.ready)
    cause_ready = active is not None and active.cause == "USER"
    if active is not None and active.cause == "LOSS_LIMIT":
        cause_ready = bool(
            (
                await checked.execute(
                    """SELECT 1 FROM risk_limit_settings s
                    JOIN risk_limit_baselines b ON b.id=s.baseline_id AND b.user_id=s.user_id
                    WHERE s.user_id=:owner AND s.mode=:mode AND NOT s.latched
                      AND CAST(b.snapshot->>'reset_at' AS timestamptz)>:stopped_at""",
                    {
                        "owner": checked.user_id,
                        "mode": mode.value,
                        "stopped_at": active.recorded_at,
                    },
                )
            ).first()
        )
    complete = bool(
        mode is TradingMode.PAPER
        and active is not None
        and (
            active.target_set_complete
            or (active.result_state == "APPLIED" and active.risk_stop_id is None)
        )
    )
    target_count = 0 if active is None or active.target_count is None else int(active.target_count)
    pending = 0 if active is None or active.pending_count is None else int(active.pending_count)
    failed = 0 if active is None or active.failed_count is None else int(active.failed_count)
    progress = (
        None
        if active is None
        else progress_for(target_set_complete=complete, pending_count=pending, failed_count=failed)
    )
    # A platform banner is an independent cause. Its revision must never replace
    # the owner stop CAS revision used by the resume endpoint.
    revision = 0 if active is None else int(active.revision)
    return StopStatus(
        mode=mode,
        stop_id=None if active is None else active.id,
        cause=None if active is None else StopCause(str(active.cause)),
        generation=None if active is None else int(active.generation),
        revision=revision,
        summary_revision=0
        if active is None or active.effects_revision is None
        else int(active.effects_revision),
        progress=progress,
        target_set_complete=complete,
        target_count=target_count,
        pending_count=pending,
        failed_count=failed,
        platform_stop_id=None if platform is None else platform.id,
        platform_reason=None if platform is None else platform.reason_text,
        resume_ready=bool(
            mode is TradingMode.PAPER
            and active is not None
            and complete
            and pending == 0
            and failed == 0
            and account_use == "BOT"
            and cause_ready
            and reconciliation_ready
        ),
        reconciliation_revision=None if active is None else reconciliation_revision,
    )
