"""Bounded fair rounds for the isolated Paper matching worker."""

import logging
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.core.orders import AdmissionPolicy, SourceUnavailableError
from tiewtrade.infra.db import DatabaseRole, scan_session_bypassing_rls, user_session
from tiewtrade.infra.db.session import presented_session
from tiewtrade.infra.paper_orders.dispatch import (
    OrderClaimLostError,
    claim_order,
    defer_claim,
    due_orders,
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


@dataclass(frozen=True, slots=True)
class PaperOrderRound:
    processed: int = 0
    deferred: int = 0
    skipped: int = 0


async def run_paper_order_round(
    *,
    engine: AsyncEngine,
    scan_engine: AsyncEngine,
    worker: str,
    policy: AdmissionPolicy | None,
    limit: int = 20,
) -> PaperOrderRound:
    """Claim at most one command per owner and process each in its own transaction."""
    async with scan_session_bypassing_rls(scan_engine) as scan:
        candidates = await due_orders(scan, limit=limit)
    processed = deferred = skipped = 0
    for due in candidates:
        claim = None
        try:
            async with user_session(engine, due.user_id, role=DatabaseRole.ENGINE) as session:
                await session.execute("SET LOCAL statement_timeout='5s'")
                await session.execute("SET LOCAL lock_timeout='5s'")
                claim = await claim_order(session, due, worker=worker)
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
