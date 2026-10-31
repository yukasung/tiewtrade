"""Bounded risk inbox rounds. Monitor integration is added at the M3 checkpoint."""

import asyncio
import logging
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.core.orders import TradingMode
from tiewtrade.core.risk_limits import RiskUnavailableError
from tiewtrade.infra.db import DatabaseRole, scan_session_bypassing_rls, user_session
from tiewtrade.infra.db.errors import DatabaseTimeoutError
from tiewtrade.infra.positions import PositionIntegrityError
from tiewtrade.infra.risk_limits.dispatch import (
    RiskClaimLostError,
    claim_request,
    due_requests,
    finish_claim,
    lock_risk_owner,
)
from tiewtrade.infra.risk_limits.evaluation_requests import acknowledge_evaluations
from tiewtrade.infra.risk_limits.monitor import (
    initialize_monitor,
    mark_unavailable_owner,
    replay_monitor,
)
from tiewtrade.infra.risk_limits.monitor_snapshot import read_monitor_snapshot
from tiewtrade.infra.risk_limits.storage import decode_monitor_owner, process_request

_LOGGER = logging.getLogger(__name__)
MAX_MONITOR_CONCURRENCY = 8


@dataclass(frozen=True, slots=True)
class RiskRequestRound:
    processed: int = 0
    deferred: int = 0
    skipped: int = 0
    next_owner: UUID | None = None


async def run_risk_request_round(
    *,
    engine: AsyncEngine,
    scan_engine: AsyncEngine,
    worker: str,
    limit: int = 20,
) -> RiskRequestRound:
    async with scan_session_bypassing_rls(scan_engine) as scan:
        due = await due_requests(scan, limit=limit)
    processed = deferred = skipped = 0
    for candidate in due:
        claim = None
        try:
            async with user_session(engine, candidate.user_id, role=DatabaseRole.ENGINE) as session:
                await session.execute("SET LOCAL lock_timeout='500ms'")
                await session.execute("SET LOCAL statement_timeout='1s'")
                claim = await claim_request(session, candidate, worker=worker)
            if claim is None:
                skipped += 1
                continue
            async with user_session(engine, candidate.user_id, role=DatabaseRole.ENGINE) as session:
                await session.execute("SET LOCAL lock_timeout='500ms'")
                await session.execute("SET LOCAL statement_timeout='1s'")
                await process_request(session, claim)
            processed += 1
        except RiskClaimLostError:
            skipped += 1
        except Exception:
            _LOGGER.exception("risk inbox request failed id=%s", candidate.request_id)
            deferred += 1
            if claim is not None:
                try:
                    async with user_session(
                        engine, candidate.user_id, role=DatabaseRole.ENGINE
                    ) as session:
                        await session.execute("SET LOCAL lock_timeout='500ms'")
                        await finish_claim(session, claim, deferred=True)
                except Exception:
                    _LOGGER.warning("risk inbox defer failed id=%s", candidate.request_id)
    return RiskRequestRound(processed, deferred, skipped)


async def run_risk_monitor_round(
    *,
    engine: AsyncEngine,
    scan_engine: AsyncEngine,
    limit: int = 20,
    after_owner: UUID | None = None,
    concurrency: int = 4,
) -> RiskRequestRound:
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("bounded owner monitor round required")
    if type(concurrency) is not int or not 1 <= concurrency <= MAX_MONITOR_CONCURRENCY:
        raise ValueError("bounded monitor concurrency required")
    async with scan_session_bypassing_rls(scan_engine) as scan:
        candidates = list(
            await scan.execute(
                """WITH hints AS (SELECT r.user_id,r.mode FROM risk_evaluation_requests r
                  WHERE NOT EXISTS(SELECT 1 FROM risk_evaluation_results x WHERE x.request_id=r.id)
                  GROUP BY r.user_id,r.mode)
                SELECT s.user_id,s.mode,o.due_at FROM risk_limit_settings s
            LEFT JOIN risk_owner_state o USING(user_id,mode)
            LEFT JOIN hints h USING(user_id,mode)
            WHERE s.mode='PAPER' AND (o.due_at IS NULL OR o.due_at<=clock_timestamp()
              OR h.user_id IS NOT NULL
              OR o.cursor<(SELECT watermark FROM risk_price_publication))
            ORDER BY CASE WHEN CAST(:after AS uuid) IS NULL OR s.user_id>CAST(:after AS uuid)
              THEN 0 ELSE 1 END,s.user_id LIMIT :limit""",
                {"limit": limit, "after": after_owner},
            )
        )
    semaphore = asyncio.Semaphore(concurrency)

    async def evaluate(owner_id: UUID) -> str:
        async with semaphore:
            try:
                async with user_session(engine, owner_id, role=DatabaseRole.ENGINE) as session:
                    await lock_risk_owner(
                        session, TradingMode.PAPER, lock_timeout_ms=100, statement_timeout_ms=700
                    )
                    snapshot = await read_monitor_snapshot(session)
                    owner_state = decode_monitor_owner(session.user_id, snapshot.owner)
                    if owner_state is None:
                        return "skipped"
                    setting, initialized = owner_state
                    if not initialized:
                        try:
                            evaluation = await initialize_monitor(session, setting)
                        except (RiskUnavailableError, PositionIntegrityError):
                            evaluation = await mark_unavailable_owner(session, setting)
                    else:
                        # R14: later immutable frames are consumed next round;
                        # financial writers retain their full publication fence.
                        evaluation = await replay_monitor(
                            session, setting, publication_fence=False, snapshot=snapshot
                        )
                    await acknowledge_evaluations(session, evaluation.reason)
                return "processed"
            except RiskUnavailableError:
                return "deferred"
            except DatabaseTimeoutError:
                _LOGGER.warning(
                    "risk monitor deferred owner=%s code=%s", owner_id, DatabaseTimeoutError.code
                )
                return "deferred"
            except Exception:
                _LOGGER.exception("risk monitor failed owner=%s", owner_id)
                return "deferred"

    # R19 changes execution priority within the selected page, not its fairness cursor.
    execution = sorted(candidates, key=lambda row: (row.due_at is not None, row.due_at))
    results = await asyncio.gather(*(evaluate(UUID(str(row.user_id))) for row in execution))
    return RiskRequestRound(
        results.count("processed"),
        results.count("deferred"),
        results.count("skipped"),
        None if not candidates else UUID(str(candidates[-1].user_id)),
    )


async def run_risk_stop_round(
    *,
    engine: AsyncEngine,
    scan_engine: AsyncEngine,
    limit: int = 20,
    after_owner: UUID | None = None,
) -> RiskRequestRound:
    from tiewtrade.infra.risk_limits.stops import consume_stop

    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("bounded risk stop scan required")
    async with scan_session_bypassing_rls(scan_engine) as scan:
        candidates = list(
            await scan.execute(
                """WITH due AS (SELECT user_id,stop_id,due_at,
              row_number() OVER(PARTITION BY user_id ORDER BY due_at,stop_id) rank
              FROM risk_stop_progress WHERE mode='PAPER' AND due_at<=clock_timestamp()
                AND (NOT target_set_complete OR pending_count>0))
            SELECT user_id,stop_id FROM due WHERE rank=1
            ORDER BY CASE WHEN CAST(:after AS uuid) IS NULL OR user_id>CAST(:after AS uuid)
              THEN 0 ELSE 1 END,user_id LIMIT :limit""",
                {"limit": limit, "after": after_owner},
            )
        )
    semaphore = asyncio.Semaphore(4)

    async def consume(owner: UUID, stop_id: UUID) -> bool:
        async with semaphore:
            try:
                async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
                    await session.execute("SET LOCAL lock_timeout='100ms'")
                    await session.execute("SET LOCAL statement_timeout='700ms'")
                    await consume_stop(session, stop_id)
                return True
            except Exception:
                _LOGGER.exception("risk stop round failed id=%s", stop_id)
                return False

    results = await asyncio.gather(
        *(consume(UUID(str(row.user_id)), UUID(str(row.stop_id))) for row in candidates)
    )
    return RiskRequestRound(
        results.count(True),
        results.count(False),
        0,
        None if not candidates else UUID(str(candidates[-1].user_id)),
    )
