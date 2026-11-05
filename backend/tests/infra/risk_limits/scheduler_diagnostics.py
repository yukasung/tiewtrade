"""Failure-only scheduling diagnostics using the existing read-only scanner role."""

import json
import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.infra.db import scan_session_bypassing_rls
from tiewtrade.infra.paper_orders.dispatch import due_orders

_LOGGER = logging.getLogger(__name__)

_QUEUE_COLUMNS = """d.command_id,d.user_id,d.episode_id,d.state,d.next_attempt_at,
    d.lease_until,d.attempts,d.claim_revision,d.routing_action,d.routing_stage,
    d.routing_base,d.routing_quote,d.preferred_for_due,d.source_wait_since,
    d.source_wait_revision,d.source_resume_used,d.source_resume_claim,
    d.next_attempt_at<=clock_timestamp() AS due_now,
    d.state='CLAIMED' AND d.lease_until>clock_timestamp() AS live_claim,
    EXISTS(SELECT 1 FROM paper_protections p WHERE p.user_id=d.user_id) AS has_protection"""


async def read_scheduler_diagnostics(
    engine: AsyncEngine,
    owner: UUID,
    *,
    prefer_same_pair: bool = False,
    admission_first: bool = False,
    source_resumption: bool = False,
) -> dict[str, object]:
    # ENGINE_SCAN cannot write or read credentials, order payloads or balances.
    # Keep diagnostics bounded; no protocol, queue or due timestamp is changed.
    async with scan_session_bypassing_rls(engine) as session:
        now = (await session.execute("SELECT clock_timestamp()")).scalar_one()
        actual = await due_orders(
            session,
            prefer_same_pair=prefer_same_pair,
            admission_first=admission_first,
            source_resumption=source_resumption,
        )
        owner_rows = (
            (
                await session.execute(
                    f"SELECT {_QUEUE_COLUMNS} FROM paper_order_dispatch d "
                    "WHERE d.user_id=:owner ORDER BY d.next_attempt_at,d.command_id LIMIT 10",
                    {"owner": owner},
                )
            )
            .mappings()
            .all()
        )
        queue = (
            (
                await session.execute(
                    f"SELECT {_QUEUE_COLUMNS} FROM paper_order_dispatch d "
                    "WHERE d.state<>'TERMINAL' ORDER BY d.next_attempt_at,d.command_id LIMIT 25"
                )
            )
            .mappings()
            .all()
        )
        counts = (
            (
                await session.execute(
                    "SELECT state,count(*) AS commands,count(distinct user_id) AS owners "
                    "FROM paper_order_dispatch GROUP BY state ORDER BY state"
                )
            )
            .mappings()
            .all()
        )
        sources = (
            (
                await session.execute("""SELECT b.source,b.base,b.quote,
            b.ready AS book_ready,b.generation AS book_generation,
            b.lease_until AS book_lease_until,b.verified_at AS book_verified_at,
            p.received_at AS price_received_at,p.trade_at AS price_trade_at,
            p.effective_readiness,p.reconciled_generation,
            f.connected,f.generation AS feed_generation,f.lease_until AS feed_lease_until
            FROM market_execution_state b
            LEFT JOIN market_latest_prices p USING(source,base,quote)
            LEFT JOIN market_price_feed f USING(source)
            WHERE b.base='BTC' AND b.quote='USDT' ORDER BY b.source""")
            )
            .mappings()
            .all()
        )
    return {
        "owner": owner,
        "observed_at_after_missing_hint": now,
        "options": {
            "prefer_same_pair": prefer_same_pair,
            "admission_first": admission_first,
            "source_resumption": source_resumption,
        },
        "actual_candidates": [
            {
                "command_id": item.command_id,
                "user_id": item.user_id,
                "next_attempt_at": item.next_attempt_at,
                "anchor_command_id": item.anchor_command_id,
                "source_wait_revision": item.source_wait_revision,
            }
            for item in actual
        ],
        "owner_rows": [dict(row) for row in owner_rows],
        "first_25_queue_rows": [dict(row) for row in queue],
        "queue_counts": [dict(row) for row in counts],
        "public_sources": [dict(row) for row in sources],
    }


async def emit_scheduler_diagnostics(engine: AsyncEngine, owner: UUID, **options: bool) -> None:
    try:
        snapshot = await read_scheduler_diagnostics(engine, owner, **options)
        _LOGGER.warning(
            "F17_SCHEDULER_DIAGNOSTIC %s", json.dumps(snapshot, default=str, sort_keys=True)
        )
    except Exception as error:
        # Never replace the original failed assertion or print connection details.
        _LOGGER.warning("F17_SCHEDULER_DIAGNOSTIC_ERROR %s", type(error).__name__)
