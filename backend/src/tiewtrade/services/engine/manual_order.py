"""Bounded owner-fair manual inbox bridge; no network or credential dependency."""

import logging
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.core.orders import AdmissionPolicy
from tiewtrade.infra.db import DatabaseRole, scan_session_bypassing_rls, user_session
from tiewtrade.infra.paper_orders.request_dispatch import (
    RequestClaimLostError,
    claim_request,
    defer_request_claim,
    due_requests,
)
from tiewtrade.infra.paper_orders.request_worker import process_request

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ManualOrderRound:
    processed: int = 0
    deferred: int = 0
    skipped: int = 0


async def run_manual_order_round(
    *,
    engine: AsyncEngine,
    scan_engine: AsyncEngine,
    worker: str,
    policy: AdmissionPolicy | None,
    limit: int = 20,
) -> ManualOrderRound:
    try:
        async with scan_session_bypassing_rls(scan_engine) as scan:
            await scan.execute("SET LOCAL statement_timeout='5s'")
            await scan.execute("SET LOCAL lock_timeout='5s'")
            hints = await due_requests(scan, limit=limit)
    except Exception:
        # This pre-financial queue must not prevent F-15 from servicing existing orders/cancels.
        _LOGGER.warning("manual request scan unavailable")
        return ManualOrderRound()
    processed = deferred = skipped = 0
    for hint in hints:
        claim = None
        try:
            async with user_session(engine, hint.user_id, role=DatabaseRole.ENGINE) as session:
                await session.execute("SET LOCAL statement_timeout='5s'")
                await session.execute("SET LOCAL lock_timeout='5s'")
                claim = await claim_request(session, hint, worker=worker)
            if claim is None:
                skipped += 1
                continue
            async with user_session(engine, hint.user_id, role=DatabaseRole.ENGINE) as session:
                await session.execute("SET LOCAL statement_timeout='5s'")
                await session.execute("SET LOCAL lock_timeout='5s'")
                await process_request(session, claim, policy=policy)
            processed += 1
        except RequestClaimLostError:
            skipped += 1
        except Exception:
            # Do not include payload/exception text in worker logs.
            _LOGGER.warning("manual request deferred request_id=%s", hint.request_id)
            if claim is not None:
                try:
                    async with user_session(
                        engine, hint.user_id, role=DatabaseRole.ENGINE
                    ) as session:
                        await session.execute("SET LOCAL statement_timeout='5s'")
                        await session.execute("SET LOCAL lock_timeout='5s'")
                        await defer_request_claim(session, claim)
                except Exception:
                    _LOGGER.warning(
                        "manual request defer unavailable request_id=%s", hint.request_id
                    )
            deferred += 1
    return ManualOrderRound(processed, deferred, skipped)
