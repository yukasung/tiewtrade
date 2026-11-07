"""Bounded fair rounds for the isolated Paper matching worker."""

import asyncio
import logging
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from itertools import cycle, repeat

from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.core.orders import AdmissionPolicy, SourceUnavailableError
from tiewtrade.infra.db import DatabaseRole, scan_session_bypassing_rls, user_session
from tiewtrade.infra.db.session import presented_session
from tiewtrade.infra.paper_orders.dispatch import (
    ClaimedOrder,
    DueOrder,
    OrderClaimLostError,
    claim_order,
    defer_claim,
    due_orders,
    try_lock_order_selection,
)
from tiewtrade.infra.paper_orders.worker import (
    OrderFinancialConflictError,
    persist_financial_conflict,
    process_claimed_order,
)
from tiewtrade.infra.platform.effects import (
    reconcile_maintenance_proofs,
    reconcile_removal_effects,
)

_LOGGER = logging.getLogger(__name__)


@asynccontextmanager
async def _claim_candidate(
    engine: AsyncEngine, due: DueOrder, worker: str, *, cleanup_seconds: float | None = None
) -> AsyncIterator[ClaimedOrder | None]:
    transaction = (
        user_session(engine, due.user_id, role=DatabaseRole.ENGINE)
        if cleanup_seconds is None
        else user_session(
            engine, due.user_id, role=DatabaseRole.ENGINE, cleanup_seconds=cleanup_seconds
        )
    )
    async with transaction as session:
        await session.execute("SET LOCAL statement_timeout='5s'")
        await session.execute("SET LOCAL lock_timeout='5s'")
        # Yield before commit so callers consume the budget even if its reply is lost.
        yield await claim_order(session, due, worker=worker)


async def _select_coordinated_claim(
    engine: AsyncEngine, scan_engine: AsyncEngine, worker: str
) -> tuple[tuple[DueOrder, ClaimedOrder] | None, int]:
    skipped = 0
    async with asyncio.timeout(5):
        async with scan_session_bypassing_rls(scan_engine, cleanup_seconds=2) as scan:
            acquired = await try_lock_order_selection(scan)
            if acquired:
                for due in await due_orders(scan, limit=20):
                    async with _claim_candidate(engine, due, worker, cleanup_seconds=2) as claim:
                        if claim is not None:
                            # Return only after both contexts close. Any ambiguous commit
                            # propagates; it must never trigger another candidate attempt.
                            return (due, claim), skipped
                    skipped += 1
    if not acquired:
        # Only an explicit busy result permits backoff, after both DB contexts
        # close successfully. Cancellation, timeout and uncertain commits propagate.
        await asyncio.sleep(0.250)
    return None, skipped


@dataclass(frozen=True, slots=True)
class PaperOrderRound:
    processed: int = 0
    deferred: int = 0
    skipped: int = 0


def matching_round_modes(
    *, prefer_same_pair: bool = False, alternate_admission: bool = False
) -> Iterator[tuple[bool, bool]]:
    """Yield (same-pair, admission-first), starting R8 when alternation is enabled."""
    if type(prefer_same_pair) is not bool:
        raise ValueError("explicit same-pair selector option required")
    if type(alternate_admission) is not bool or (alternate_admission and prefer_same_pair):
        raise ValueError("alternating admission requires a legacy base selection")
    return (
        cycle(((False, False), (True, True)))
        if alternate_admission
        else repeat((prefer_same_pair, False))
    )


async def run_paper_order_round(
    *,
    engine: AsyncEngine,
    scan_engine: AsyncEngine,
    worker: str,
    policy: AdmissionPolicy | None,
    limit: int = 20,
    claim_limit: int | None = None,
    prefer_same_pair: bool = False,
    admission_first: bool = False,
    source_resumption: bool = False,
    coordinate_claims: bool = False,
) -> PaperOrderRound:
    """Claim at most one command per owner and process each in its own transaction."""
    if type(prefer_same_pair) is not bool:
        raise ValueError("explicit same-pair selector option required")
    if type(admission_first) is not bool or (admission_first and not prefer_same_pair):
        raise ValueError("admission priority requires explicit same-pair preference")
    if type(source_resumption) is not bool:
        raise ValueError("explicit source-resumption option required")
    if claim_limit is not None and (type(claim_limit) is not int or not 1 <= claim_limit <= limit):
        raise ValueError("bounded successful claim budget required")
    if type(coordinate_claims) is not bool or (
        coordinate_claims
        and (
            type(limit) is not int
            or limit != 20
            or claim_limit != 1
            or prefer_same_pair
            or admission_first
            or source_resumption
        )
    ):
        raise ValueError("coordinated selection requires legacy limit20/claim_limit1")
    processed = deferred = skipped = claimed = 0
    candidates: tuple[DueOrder, ...]
    selected_claim = None
    if coordinate_claims:
        selected, skipped = await _select_coordinated_claim(engine, scan_engine, worker)
        candidates = () if selected is None else (selected[0],)
        selected_claim = None if selected is None else selected[1]
    else:
        async with scan_session_bypassing_rls(scan_engine) as scan:
            if source_resumption:
                candidates = await due_orders(
                    scan,
                    limit=limit,
                    prefer_same_pair=prefer_same_pair,
                    admission_first=admission_first,
                    source_resumption=True,
                )
            elif admission_first:
                candidates = await due_orders(
                    scan, limit=limit, prefer_same_pair=True, admission_first=True
                )
            elif prefer_same_pair:
                candidates = await due_orders(scan, limit=limit, prefer_same_pair=True)
            else:
                candidates = await due_orders(scan, limit=limit)
    for due in candidates:
        if claim_limit is not None and claimed >= claim_limit:
            break
        claim = selected_claim
        try:
            if not coordinate_claims:
                async with _claim_candidate(engine, due, worker) as claim:
                    if claim is not None:
                        # Count before commit: a lost commit reply must not permit
                        # a second claimed item in the same phase.
                        claimed += 1
            if claim is None:
                skipped += 1
                continue
            try:
                async with user_session(engine, due.user_id, role=DatabaseRole.ENGINE) as session:
                    await session.execute("SET LOCAL statement_timeout='5s'")
                    await session.execute("SET LOCAL lock_timeout='5s'")
                    await process_claimed_order(session, claim, policy=policy)
                processed += 1
            except SourceUnavailableError:
                async with user_session(engine, due.user_id, role=DatabaseRole.ENGINE) as session:
                    if source_resumption:
                        await defer_claim(session, claim, source_unavailable=True)
                    else:
                        await defer_claim(session, claim)
                deferred += 1
            except OrderFinancialConflictError as conflict:
                async with user_session(engine, due.user_id, role=DatabaseRole.ENGINE) as session:
                    await session.execute("SET LOCAL statement_timeout='5s'")
                    await session.execute("SET LOCAL lock_timeout='5s'")
                    await persist_financial_conflict(session, conflict)
                processed += 1
            except OrderClaimLostError:
                skipped += 1
        except Exception:
            _LOGGER.exception("paper order command failed command_id=%s", due.command_id)
            if claim is not None:
                try:
                    async with user_session(
                        engine, due.user_id, role=DatabaseRole.ENGINE
                    ) as session:
                        await defer_claim(session, claim)
                except Exception:
                    _LOGGER.exception("paper order defer failed command_id=%s", due.command_id)
            deferred += 1
    async with presented_session(engine, role=DatabaseRole.ENGINE) as session:
        await reconcile_removal_effects(session)
        await reconcile_maintenance_proofs(session)
    return PaperOrderRound(processed, deferred, skipped)


async def run_protection_round(
    *, engine: AsyncEngine, scan_engine: AsyncEngine, limit: int = 20
) -> PaperOrderRound:
    """DB hints only; every decision reacquires the existing owner/episode lock."""
    from tiewtrade.infra.protections.worker import process_group, process_request

    async with scan_session_bypassing_rls(scan_engine) as scan:
        hints = (
            await scan.execute(
                """SELECT id,user_id,kind,due FROM (
            SELECT DISTINCT ON (user_id) id,user_id,kind,due FROM (
            SELECT q.id,q.user_id,'REQUEST' AS kind,
              coalesce(p.next_attempt_at,q.recorded_at) AS due
              FROM paper_protection_requests q
              LEFT JOIN paper_protection_request_progress p ON p.request_id=q.id
              WHERE coalesce(p.next_attempt_at,q.recorded_at)<=clock_timestamp() AND NOT EXISTS(
                SELECT 1 FROM paper_protection_results r WHERE r.request_id=q.id)
            UNION ALL SELECT id,user_id,'GROUP',next_attempt_at FROM paper_protections
              WHERE state NOT IN ('CLOSED','CANCELED') AND next_attempt_at<=clock_timestamp()
           ) candidates ORDER BY user_id,due,id
          ) owners ORDER BY due,id LIMIT :limit""",
                {"limit": limit},
            )
        ).all()
    processed = deferred = 0
    for hint in sorted(hints, key=lambda v: (v.due, str(v.id))):
        try:
            async with user_session(engine, hint.user_id, role=DatabaseRole.ENGINE) as session:
                await session.execute("SET LOCAL statement_timeout='500ms'")
                await session.execute("SET LOCAL lock_timeout='100ms'")
                if hint.kind == "REQUEST":
                    await process_request(session, hint.id)
                else:
                    await process_group(session, hint.id)
                    await session.execute(
                        """UPDATE paper_protections
                        SET next_attempt_at=greatest(clock_timestamp()+interval '20 milliseconds',
                            CAST(document->>'setup_due_at' AS timestamptz))
                       WHERE id=:id""",
                        {"id": hint.id},
                    )
            processed += 1
        except Exception:
            _LOGGER.warning("protection work deferred id=%s", hint.id)
            deferred += 1
    return PaperOrderRound(processed, deferred)
