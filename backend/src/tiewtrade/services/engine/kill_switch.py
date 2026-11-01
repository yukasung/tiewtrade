"""Bounded single-writer processing for durable F-19 stop requests."""

import logging
from dataclasses import dataclass
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.core.orders import TradingMode
from tiewtrade.infra.audit import (
    ActorKind,
    AuditAction,
    AuditEvent,
    AuditMode,
    AuditOutcome,
    SubjectKind,
    TradingStopDetails,
    record_event,
)
from tiewtrade.infra.db import DatabaseRole, scan_session_bypassing_rls, user_session
from tiewtrade.infra.db.errors import DatabaseTimeoutError
from tiewtrade.infra.db.session import UserSession
from tiewtrade.infra.risk_limits.dispatch import lock_risk_owner
from tiewtrade.infra.trading_stops.storage import global_exclusive_lock, global_shared_lock

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class StopRound:
    processed: int = 0
    deferred: int = 0
    discovered: int = 0
    active: bool = False


async def _audit(
    session: UserSession, request: Any, action: AuditAction, *, rejected: bool = False
) -> None:
    platform = request["cause"] == "PLATFORM"
    await record_event(
        session,
        AuditEvent(
            owner_user_id=session.user_id,
            actor_kind=ActorKind.SYSTEM,
            actor_id=None,
            action=action,
            subject_kind=SubjectKind.TRADING_STOP,
            subject_id=str(request["expected_stop_id"] or request["id"]),
            mode=AuditMode.NOT_APPLICABLE if platform else AuditMode(str(request["mode"])),
            outcome=AuditOutcome.REJECTED if rejected else AuditOutcome.SUCCEEDED,
            details=TradingStopDetails(
                UUID(str(request["id"])),
                UUID(str(request["expected_stop_id"] or request["id"])),
                str(request["cause"]),
                "PLATFORM" if platform else str(request["mode"]),
                int(request["revision"]),
                str(request["reason_code"]),
            ),
        ),
    )


async def _request(session: UserSession, request_id: UUID) -> Any | None:
    # The inbox is append-only, so the engine deliberately has no UPDATE grant.
    # Serialize duplicate workers with a transaction advisory lock instead of a
    # row lock (PostgreSQL requires UPDATE privilege for SELECT ... FOR UPDATE).
    await session.execute("SET LOCAL lock_timeout='500ms'")
    await session.execute("SET LOCAL statement_timeout='2s'")
    await session.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(:key,0))",
        {"key": f"trading-stop-request:{request_id}"},
    )
    return (
        (
            await session.execute(
                """SELECT r.* FROM trading_stop_requests r
          WHERE r.id=:id AND r.user_id=:owner""",
                {"id": request_id, "owner": session.user_id},
            )
        )
        .mappings()
        .one_or_none()
    )


async def _paper_job(
    session: UserSession,
    request: Any,
    *,
    stop_id: UUID,
    cause: str,
    target_policy: str,
) -> UUID | None:
    wallet = (
        await session.execute(
            """SELECT wallet_id,active_episode_id FROM paper_wallet_state
        WHERE user_id=:owner""",
            {"owner": session.user_id},
        )
    ).one_or_none()
    if wallet is None:
        return None
    job_id = UUID(str(stop_id))
    existing = (
        await session.execute(
            """SELECT id FROM risk_stop_requests
        WHERE authority_request_id=:authority AND user_id=:owner""",
            {"authority": request["id"], "owner": session.user_id},
        )
    ).scalar_one_or_none()
    if existing is not None:
        return UUID(str(existing))
    await session.execute(
        """INSERT INTO risk_stop_requests
      (id,user_id,mode,event_id,wallet_id,episode_id,risk_revision,recorded_at,
       authority_request_id,cause,target_policy)
      VALUES(:id,:owner,'PAPER',NULL,:wallet,:episode,NULL,:cut,:authority,:cause,:policy)""",
        {
            "id": job_id,
            "owner": session.user_id,
            "wallet": wallet.wallet_id,
            "episode": wallet.active_episode_id,
            "cut": request["recorded_at"],
            "authority": request["id"],
            "cause": cause,
            "policy": target_policy,
        },
    )
    await session.execute(
        """INSERT INTO risk_stop_progress(stop_id,user_id,mode)
      VALUES(:id,:owner,'PAPER')""",
        {"id": job_id, "owner": session.user_id},
    )
    return job_id


async def _apply_stop(session: UserSession, request: Any) -> None:
    platform = request["cause"] == "PLATFORM"
    if not platform:
        await global_shared_lock(session)
        await lock_risk_owner(session, TradingMode(str(request["mode"])))
    prior = (
        await session.execute(
            "SELECT 1 FROM trading_stop_results WHERE request_id=:id",
            {"id": request["id"]},
        )
    ).first()
    if prior is not None:
        return
    if platform:
        await session.execute(
            """INSERT INTO platform_stop_progress(stop_id,user_id,request_id)
          VALUES(:stop,:owner,:request) ON CONFLICT(stop_id) DO NOTHING""",
            {"stop": request["id"], "owner": session.user_id, "request": request["id"]},
        )
    elif request["mode"] == "PAPER":
        await _paper_job(
            session,
            request,
            stop_id=UUID(str(request["id"])),
            cause=str(request["cause"]),
            target_policy="ALL",
        )
    scope_key = "PLATFORM" if platform else f"{request['mode']}:{request['scope_owner_id']}"
    await session.execute(
        """INSERT INTO trading_stop_events
      (request_id,user_id,stop_id,scope_owner_id,mode,cause,active,revision)
      VALUES(:request,:owner,:stop,:scope_owner,:mode,:cause,true,:revision)""",
        {
            "request": request["id"],
            "owner": session.user_id,
            "stop": request["id"],
            "scope_owner": request["scope_owner_id"],
            "mode": request["mode"],
            "cause": request["cause"],
            "revision": request["revision"],
        },
    )
    await session.execute(
        """INSERT INTO trading_stop_causes
      (scope_key,cause,scope_owner_id,mode,stop_id,request_id,user_id,generation,revision,active)
      VALUES(:scope_key,:cause,:scope_owner,:mode,:stop,:request,:owner,:generation,:revision,true)
      ON CONFLICT(scope_key,cause) DO UPDATE SET stop_id=excluded.stop_id,
        request_id=excluded.request_id,user_id=excluded.user_id,generation=excluded.generation,
        revision=excluded.revision,active=true,updated_at=clock_timestamp()
      WHERE excluded.revision>trading_stop_causes.revision""",
        {
            "scope_key": scope_key,
            "cause": request["cause"],
            "scope_owner": request["scope_owner_id"],
            "mode": request["mode"],
            "stop": request["id"],
            "request": request["id"],
            "owner": session.user_id,
            "generation": request["generation"],
            "revision": request["revision"],
        },
    )
    await session.execute(
        """INSERT INTO trading_stop_results(request_id,user_id,state,stop_id,revision)
      VALUES(:request,:owner,'APPLIED',:stop,:revision)""",
        {
            "request": request["id"],
            "owner": session.user_id,
            "stop": request["id"],
            "revision": request["revision"],
        },
    )
    await _audit(
        session,
        request,
        AuditAction.PLATFORM_STOPPED if platform else AuditAction.STOP_UPDATED,
    )


async def _resume_failure(session: UserSession, request: Any, code: str) -> None:
    await session.execute(
        """INSERT INTO trading_stop_results
      (request_id,user_id,state,stop_id,revision,failure_code)
      VALUES(:request,:owner,'REJECTED',:stop,:revision,:failure)""",
        {
            "request": request["id"],
            "owner": session.user_id,
            "stop": request["expected_stop_id"],
            "revision": request["revision"],
            "failure": code,
        },
    )
    await _audit(session, request, AuditAction.RESUME_REJECTED, rejected=True)


async def _apply_resume(session: UserSession, request: Any) -> None:
    platform = request["cause"] == "PLATFORM"
    if platform:
        # Admission uses the shared form. Keep the exclusive form until the
        # platform cause and its durable resume result commit together.
        await global_exclusive_lock(session)
    else:
        await global_shared_lock(session)
        await lock_risk_owner(session, TradingMode(str(request["mode"])))
    if (
        await session.execute(
            "SELECT 1 FROM trading_stop_results WHERE request_id=:id", {"id": request["id"]}
        )
    ).first() is not None:
        return
    scope_key = "PLATFORM" if platform else f"{request['mode']}:{request['scope_owner_id']}"
    cause = (
        await session.execute(
            """SELECT * FROM trading_stop_causes WHERE scope_key=:scope AND cause=:cause
          FOR UPDATE""",
            {"scope": scope_key, "cause": request["cause"]},
        )
    ).one_or_none()
    latest = (
        await session.execute(
            """SELECT id,revision FROM trading_stop_requests WHERE action='STOP'
          AND cause=:cause AND scope_owner_id IS NOT DISTINCT FROM :scope_owner
          AND mode IS NOT DISTINCT FROM :mode ORDER BY revision DESC LIMIT 1""",
            {
                "cause": request["cause"],
                "scope_owner": request["scope_owner_id"],
                "mode": request["mode"],
            },
        )
    ).one_or_none()
    if (
        cause is None
        or latest is None
        or not cause.active
        or cause.stop_id != request["expected_stop_id"]
        or int(cause.revision) != int(request["expected_stop_revision"])
        or latest.id != request["expected_stop_id"]
        or int(latest.revision) != int(request["expected_stop_revision"])
    ):
        await _resume_failure(session, request, "TRADING_STOP_REVISION_CONFLICT")
        return
    if platform:
        await session.execute("SELECT lock_trading_reconciliation_clock()")
        ready = (
            await session.execute(
                """SELECT 1 FROM platform_stop_progress g WHERE stop_id=:stop
              AND discovery_complete AND pending_count=0 AND failed_count=0
              AND revision=:summary
              AND g.reconciliation_revision=CAST(:reconciliation AS bigint)
              AND (SELECT revision FROM trading_reconciliation_clock WHERE singleton)
                    =CAST(:reconciliation AS bigint)""",
                {
                    "stop": cause.stop_id,
                    "summary": request["expected_summary_revision"],
                    "reconciliation": request["expected_reconciliation_revision"],
                },
            )
        ).first()
    elif request["mode"] == "PAPER":
        ready = (
            await session.execute(
                """SELECT 1 FROM user_trading_preferences u WHERE u.user_id=:owner
              AND u.use='BOT'
              AND (NOT EXISTS(SELECT 1 FROM paper_wallet_state w WHERE w.user_id=:owner)
                OR EXISTS(SELECT 1 FROM paper_wallet_state w JOIN paper_position_activity a
                  ON a.episode_id=w.active_episode_id WHERE w.user_id=:owner
                    AND a.availability='READY'))
              AND CAST(:reconciliation AS bigint)=coalesce((SELECT a.revision
                FROM paper_wallet_state w LEFT JOIN paper_position_activity a
                  ON a.episode_id=w.active_episode_id WHERE w.user_id=:owner),0)
              AND (:cause='USER' OR (:cause='LOSS_LIMIT' AND EXISTS(
                SELECT 1 FROM risk_limit_settings s JOIN risk_limit_baselines b
                  ON b.id=s.baseline_id AND b.user_id=s.user_id
                JOIN trading_stop_requests stopped ON stopped.id=:stop
                WHERE s.user_id=:owner AND s.mode='PAPER' AND NOT s.latched
                  AND CAST(b.snapshot->>'reset_at' AS timestamptz)>stopped.recorded_at))) AND (
                EXISTS(SELECT 1 FROM risk_stop_requests j JOIN risk_stop_progress p
                  ON p.stop_id=j.id WHERE j.authority_request_id=:stop
                    AND p.target_set_complete AND p.pending_count=0 AND p.failed_count=0
                    AND p.effects_revision=CAST(:summary AS bigint))
                OR (CAST(:summary AS bigint)=0 AND NOT EXISTS(SELECT 1 FROM paper_wallet_state w
                  WHERE w.user_id=:owner)))""",
                {
                    "stop": cause.stop_id,
                    "owner": session.user_id,
                    "summary": request["expected_summary_revision"],
                    "reconciliation": request["expected_reconciliation_revision"],
                    "cause": request["cause"],
                },
            )
        ).first()
    else:
        ready = None
    if ready is None:
        await _resume_failure(session, request, "TRADING_STOP_NOT_READY")
        return
    await session.execute(
        """UPDATE trading_stop_causes SET active=false,request_id=:request,user_id=:owner,
      revision=:revision,updated_at=clock_timestamp() WHERE scope_key=:scope AND cause=:cause""",
        {
            "request": request["id"],
            "owner": session.user_id,
            "revision": request["revision"],
            "scope": scope_key,
            "cause": request["cause"],
        },
    )
    await session.execute(
        """INSERT INTO trading_stop_events
      (request_id,user_id,stop_id,scope_owner_id,mode,cause,active,revision)
      VALUES(:request,:owner,:stop,:scope_owner,:mode,:cause,false,:revision)""",
        {
            "request": request["id"],
            "owner": session.user_id,
            "stop": request["expected_stop_id"],
            "scope_owner": request["scope_owner_id"],
            "mode": request["mode"],
            "cause": request["cause"],
            "revision": request["revision"],
        },
    )
    await session.execute(
        """INSERT INTO trading_stop_results(request_id,user_id,state,stop_id,revision)
      VALUES(:request,:owner,'APPLIED',:stop,:revision)""",
        {
            "request": request["id"],
            "owner": session.user_id,
            "stop": request["expected_stop_id"],
            "revision": request["revision"],
        },
    )
    await _audit(session, request, AuditAction.RESUMED)


async def run_stop_request_round(
    *, engine: AsyncEngine, scan_engine: AsyncEngine, limit: int = 20
) -> StopRound:
    if type(limit) is not int or not 1 <= limit <= 20:
        raise ValueError("bounded stop request round required")
    async with scan_session_bypassing_rls(scan_engine) as scan:
        rows = list(
            await scan.execute(
                """WITH due AS (SELECT r.id,r.user_id,d.next_attempt_at,r.revision,
                  row_number() OVER(PARTITION BY r.user_id ORDER BY r.revision) owner_rank
                FROM trading_stop_requests r JOIN trading_stop_dispatch d ON d.request_id=r.id
                WHERE d.next_attempt_at<=clock_timestamp()
                  AND NOT EXISTS(SELECT 1 FROM trading_stop_results x WHERE x.request_id=r.id))
                SELECT id,user_id FROM due WHERE owner_rank=1
                ORDER BY next_attempt_at,revision LIMIT :limit""",
                {"limit": limit},
            )
        )
    processed = deferred = 0
    for row in rows:
        try:
            async with user_session(
                engine, UUID(str(row.user_id)), role=DatabaseRole.ENGINE
            ) as session:
                request = await _request(session, UUID(str(row.id)))
                if request is None:
                    raise RuntimeError("stop request unavailable under actor scope")
                if request["action"] == "STOP":
                    await _apply_stop(session, request)
                else:
                    await _apply_resume(session, request)
            processed += 1
        except Exception:
            deferred += 1
            _LOGGER.exception("trading stop request failed id=%s", row.id)
            try:
                async with user_session(
                    engine, UUID(str(row.user_id)), role=DatabaseRole.ENGINE
                ) as retry:
                    await retry.execute(
                        """UPDATE trading_stop_dispatch SET attempt=attempt+1,
                        next_attempt_at=clock_timestamp()+make_interval(
                          secs=>least(30,power(2,least(attempt+1,5))::integer))
                        WHERE request_id=:id""",
                        {"id": row.id},
                    )
            except Exception:
                _LOGGER.warning("trading stop retry defer failed id=%s", row.id)
    return StopRound(processed=processed, deferred=deferred)


async def _set_discovery_timeouts(session: UserSession) -> None:
    await session.execute("SET LOCAL lock_timeout='100ms'")
    await session.execute("SET LOCAL statement_timeout='700ms'")


async def _create_platform_target(
    engine: AsyncEngine, request: Any, owner_id: UUID, wallet_id: UUID, episode_id: UUID
) -> bool:
    async with user_session(engine, owner_id, role=DatabaseRole.ENGINE) as session:
        await _set_discovery_timeouts(session)
        await global_shared_lock(session)
        await lock_risk_owner(session, TradingMode.PAPER)
        exists = (
            await session.execute(
                """SELECT 1 FROM platform_stop_targets WHERE stop_id=:stop AND user_id=:owner""",
                {"stop": request["id"], "owner": owner_id},
            )
        ).first()
        if exists is not None:
            return False
        job_id = uuid5(NAMESPACE_URL, f"tiewtrade:platform-stop:{request['id']}:{owner_id}")
        await session.execute(
            """INSERT INTO risk_stop_requests
          (id,user_id,mode,event_id,wallet_id,episode_id,risk_revision,recorded_at,
           authority_request_id,cause,target_policy)
          VALUES(:id,:owner,'PAPER',NULL,:wallet,:episode,NULL,:cut,:authority,'PLATFORM','BOT_ONLY')""",
            {
                "id": job_id,
                "owner": owner_id,
                "wallet": wallet_id,
                "episode": episode_id,
                "cut": request["recorded_at"],
                "authority": request["id"],
            },
        )
        await session.execute(
            "INSERT INTO risk_stop_progress(stop_id,user_id,mode) VALUES(:id,:owner,'PAPER')",
            {"id": job_id, "owner": owner_id},
        )
        await session.execute(
            """INSERT INTO platform_stop_targets
          (stop_id,user_id,wallet_id,episode_id,risk_stop_id)
          VALUES(:stop,:owner,:wallet,:episode,:job)""",
            {
                "stop": request["id"],
                "owner": owner_id,
                "wallet": wallet_id,
                "episode": episode_id,
                "job": job_id,
            },
        )
    return True


async def run_platform_discovery_round(
    *, engine: AsyncEngine, scan_engine: AsyncEngine, limit: int = 20
) -> StopRound:
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("bounded platform stop discovery required")
    async with scan_session_bypassing_rls(scan_engine) as scan:
        current = (
            (
                await scan.execute(
                    """SELECT r.id,r.user_id,r.recorded_at,p.cursor,p.revision
            FROM trading_stop_requests r
            JOIN platform_stop_progress p ON p.stop_id=r.id
            WHERE r.cause='PLATFORM' AND r.action='STOP'
              AND NOT EXISTS(SELECT 1 FROM trading_stop_requests rr
                JOIN trading_stop_results x ON x.request_id=rr.id AND x.state='APPLIED'
                WHERE rr.action='RESUME' AND rr.expected_stop_id=r.id)
            ORDER BY r.revision DESC LIMIT 1"""
                )
            )
            .mappings()
            .one_or_none()
        )
        if current is None:
            return StopRound()
        # Enrolled owners are durable progress. Rotate over missing owners so a
        # locked one cannot hold the cursor back or disappear behind it.
        wallets = list(
            await scan.execute(
                """SELECT * FROM (
                  (SELECT 0 AS phase,user_id,wallet_id,active_episode_id
                   FROM paper_wallet_state w
                   WHERE (CAST(:cursor AS uuid) IS NULL OR user_id>CAST(:cursor AS uuid))
                     AND NOT EXISTS(SELECT 1 FROM platform_stop_targets t
                       WHERE t.stop_id=:stop AND t.user_id=w.user_id)
                   ORDER BY user_id LIMIT :limit)
                  UNION ALL
                  (SELECT 1 AS phase,user_id,wallet_id,active_episode_id
                   FROM paper_wallet_state w
                   WHERE CAST(:cursor AS uuid) IS NOT NULL AND user_id<=CAST(:cursor AS uuid)
                     AND NOT EXISTS(SELECT 1 FROM platform_stop_targets t
                       WHERE t.stop_id=:stop AND t.user_id=w.user_id)
                   ORDER BY user_id LIMIT :limit)
                ) candidates ORDER BY phase,user_id LIMIT :limit""",
                {"stop": current["id"], "cursor": current["cursor"], "limit": limit},
            )
        )
    discovered = deferred = 0
    cursor = current["cursor"]
    for wallet in wallets:
        cursor = wallet.user_id
        try:
            if await _create_platform_target(
                engine,
                current,
                UUID(str(wallet.user_id)),
                UUID(str(wallet.wallet_id)),
                UUID(str(wallet.active_episode_id)),
            ):
                discovered += 1
        except Exception:
            deferred += 1
            _LOGGER.exception("platform stop target failed owner=%s", wallet.user_id)
    async with scan_session_bypassing_rls(scan_engine) as scan:
        counts = (
            await scan.execute(
                """SELECT count(*) owner_count,coalesce(sum(p.pending_count),0) pending_count,
              coalesce(sum(p.failed_count),0) failed_count,
              coalesce(bool_and(p.target_set_complete
                AND coalesce(a.availability='READY',false)),true) children_complete,
              (SELECT revision FROM trading_reconciliation_clock WHERE singleton)
                reconciliation_revision,
              NOT EXISTS(SELECT 1 FROM paper_wallet_state w
                WHERE NOT EXISTS(SELECT 1 FROM platform_stop_targets enrolled
                  WHERE enrolled.stop_id=:stop AND enrolled.user_id=w.user_id)) inventory_complete
            FROM platform_stop_targets t JOIN risk_stop_progress p ON p.stop_id=t.risk_stop_id
            LEFT JOIN paper_position_activity a ON a.episode_id=t.episode_id
            WHERE t.stop_id=:stop""",
                {"stop": current["id"]},
            )
        ).one()
    try:
        async with user_session(
            engine, UUID(str(current["user_id"])), role=DatabaseRole.ENGINE
        ) as actor:
            await _set_discovery_timeouts(actor)
            await actor.execute(
                """UPDATE platform_stop_progress SET cursor=:cursor,
              discovery_complete=:complete,owner_count=:owners,pending_count=:pending,
              failed_count=:failed,reconciliation_revision=:reconciliation,
              revision=revision+1,updated_at=clock_timestamp()
              WHERE stop_id=:stop AND revision=:expected_revision
                AND (SELECT revision FROM trading_reconciliation_clock WHERE singleton)
                  =:reconciliation
                AND (cursor IS DISTINCT FROM CAST(:cursor AS uuid)
                OR discovery_complete IS DISTINCT FROM :complete
                OR owner_count IS DISTINCT FROM :owners
                OR pending_count IS DISTINCT FROM :pending
                OR failed_count IS DISTINCT FROM :failed
                OR reconciliation_revision IS DISTINCT FROM CAST(:reconciliation AS bigint))""",
                {
                    "cursor": cursor,
                    "complete": bool(counts.inventory_complete and counts.children_complete),
                    "owners": counts.owner_count,
                    "pending": counts.pending_count,
                    "failed": counts.failed_count,
                    "stop": current["id"],
                    "reconciliation": counts.reconciliation_revision,
                    "expected_revision": current["revision"],
                },
            )
    except DatabaseTimeoutError:
        deferred += 1
        _LOGGER.warning("platform stop progress deferred stop=%s", current["id"])
    return StopRound(discovered=discovered, deferred=deferred, active=True)
