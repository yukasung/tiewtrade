"""One bounded processing round for durable Paper-wallet commands."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.infra.db import DatabaseRole, InfraError, scan_session_bypassing_rls, user_session
from tiewtrade.infra.paper_wallet import (
    claim_command,
    due_hints,
    process_claimed,
    schedule_failure,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PaperWalletRound:
    processed: int = 0
    rejected: int = 0
    deferred: int = 0
    skipped: int = 0


async def run_paper_wallet_round(
    *, engine: AsyncEngine, scan_engine: AsyncEngine, worker: str, limit: int = 20
) -> PaperWalletRound:
    async with scan_session_bypassing_rls(scan_engine) as scan:
        candidates = await due_hints(scan, limit=limit)
    totals = PaperWalletRound()
    for due in candidates:
        try:
            async with user_session(engine, due.user_id, role=DatabaseRole.ENGINE) as session:
                await session.execute("SET LOCAL statement_timeout='5s'")
                claimed = await claim_command(session, due, worker=worker)
            if claimed is None:
                totals = _add(totals, skipped=1)
                continue
            try:
                async with user_session(engine, due.user_id, role=DatabaseRole.ENGINE) as session:
                    await session.execute("SET LOCAL statement_timeout='5s'")
                    result = await process_claimed(session, claimed)
            except InfraError as error:
                async with user_session(engine, due.user_id, role=DatabaseRole.ENGINE) as session:
                    await session.execute("SET LOCAL statement_timeout='5s'")
                    await schedule_failure(session, claimed, error.code)
                totals = _add(totals, deferred=1)
                continue
            totals = _add(
                totals,
                rejected=int(result.failure_code is not None),
                processed=int(result.failure_code is None),
            )
        except Exception:
            # A programming error in one immutable command must not starve other owners.
            # Bound context to identifiers; payload and amounts are deliberately absent.
            _LOGGER.exception("paper wallet command failed command_id=%s", due.command_id)
            totals = _add(totals, deferred=1)
    return totals


def _add(
    value: PaperWalletRound,
    *,
    processed: int = 0,
    rejected: int = 0,
    deferred: int = 0,
    skipped: int = 0,
) -> PaperWalletRound:
    return PaperWalletRound(
        value.processed + processed,
        value.rejected + rejected,
        value.deferred + deferred,
        value.skipped + skipped,
    )
