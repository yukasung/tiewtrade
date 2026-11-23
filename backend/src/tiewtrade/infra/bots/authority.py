"""Paper order lineage checks executed under the existing owner lock."""

from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from tiewtrade.core.indicators import FORMULA_VERSION
from tiewtrade.core.market_data import Timeframe, advance
from tiewtrade.core.positions import PositionPair
from tiewtrade.core.strategy_config import CANDLE_STRATEGIES
from tiewtrade.infra.bots.candle_sources import candle_source_state
from tiewtrade.infra.bots.indicator_tail import IndicatorTailProof, require_tail_proof
from tiewtrade.infra.db.session import UserSession, require_user_session
from tiewtrade.infra.indicators.prepared import fresh_proof_valid, read_generation_authority
from tiewtrade.infra.indicators.source import SourceFence
from tiewtrade.infra.market_data.candle_closure import (
    ClosureUnavailableError,
    current_proof,
    proof_reference,
)
from tiewtrade.infra.market_data.storage import _stored, closure_control


class BotOrderAuthority(StrEnum):
    UNLINKED = "UNLINKED"
    BLOCKED = "BLOCKED"
    READY = "READY"


async def blocked_paper_openings(
    session: UserSession, *, episode_id: UUID, order_ids: tuple[UUID, ...]
) -> frozenset[UUID]:
    """Fence all BOT buys in a shared matcher, including another command's orders."""
    checked = require_user_session(session)
    if not order_ids:
        return frozenset()
    rows = await checked.execute(
        """SELECT o.id FROM paper_orders o
           LEFT JOIN bot_order_links b ON b.command_id=o.command_id AND b.order_id=o.id
             AND b.user_id=o.user_id AND b.episode_id=o.episode_id AND b.mode='PAPER'
           LEFT JOIN bot_runs r ON r.id=b.run_id AND r.user_id=b.user_id AND r.mode=b.mode
           LEFT JOIN user_trading_preferences p ON p.user_id=o.user_id
           LEFT JOIN paper_wallet_state w ON w.user_id=o.user_id AND w.wallet_id=r.wallet_id
           WHERE o.user_id=:owner AND o.episode_id=:episode AND o.id=ANY(:orders)
             AND o.origin='BOT'
             AND (r.status='RUNNING' AND p.use='BOT'
                  AND w.active_episode_id=r.episode_id) IS NOT TRUE""",
        {"owner": checked.user_id, "episode": episode_id, "orders": list(order_ids)},
    )
    blocked = {UUID(str(row.id)) for row in rows}
    blocked.update(
        await invalidated_strategy_openings(
            checked,
            episode_id=episode_id,
            order_ids=order_ids,
        )
    )
    if await closure_control(checked) is None:
        # Expand compatibility: pre-closure schemas have no receipt to recheck.
        return frozenset(blocked)
    pending = (
        await checked.execute(
            """SELECT o.id,e.signal_open_at,b.base,b.quote,b.timeframe,d.input_provenance
            FROM paper_orders o JOIN bot_order_links l ON l.order_id=o.id
            JOIN bot_runs r ON r.id=l.run_id
            LEFT JOIN bot_strategy_entries e ON e.order_id=o.id
            LEFT JOIN bot_strategy_baskets b ON b.id=e.basket_id
            LEFT JOIN bot_decisions d ON d.id=l.decision_id
            WHERE o.episode_id=:episode AND o.id=ANY(:orders)
              AND o.origin='BOT' AND r.strategy_name=ANY(:strategies)""",
            {
                "episode": episode_id,
                "orders": list(order_ids),
                "strategies": list(CANDLE_STRATEGIES),
            },
        )
    ).all()
    if pending:
        # Matchers may be driven by another order, including SELL. Hold these
        # fences until fill commit, rather than waiting for the bot to pause.
        await checked.execute("SELECT risk_financial_fence()")
        await checked.execute("SELECT hold_bot_indicator_source()")
    for order in pending:
        if order.id in blocked:
            continue
        if order.signal_open_at is None or not await _closure_signal_current(
            checked,
            base=order.base,
            quote=order.quote,
            timeframe=Timeframe(order.timeframe),
            opened=order.signal_open_at,
            provenance=order.input_provenance or {},
        ):
            blocked.add(UUID(str(order.id)))
    return frozenset(blocked)


async def invalidated_strategy_openings(
    session: UserSession, *, episode_id: UUID, order_ids: tuple[UUID, ...]
) -> frozenset[UUID]:
    """Permanent F-21 signal invalidations, distinct from a temporary F-20 pause."""
    checked = require_user_session(session)
    if not order_ids:
        return frozenset()
    if (
        await checked.execute("SELECT to_regclass('public.bot_strategy_entries')")
    ).scalar_one_or_none() is None:
        return frozenset()
    f21 = await checked.execute(
        """SELECT e.order_id FROM bot_strategy_entries e
        JOIN bot_strategy_baskets b ON b.id=e.basket_id
        JOIN bot_strategy_progress p ON p.run_id=e.run_id
        JOIN bot_order_links l ON l.command_id=e.command_id AND l.order_id=e.order_id
        JOIN bot_decisions d ON d.id=l.decision_id
        WHERE e.user_id=:owner AND e.episode_id=:episode AND e.order_id=ANY(:orders)
        AND (b.status<>'OPEN' OR b.reconciliation_required OR p.reconciliation_required
          OR d.input_provenance->'guard_revision' IS DISTINCT FROM to_jsonb(p.guard_revision)
          OR EXISTS(
          SELECT 1 FROM bot_strategy_exit_guards g
          WHERE g.run_id=e.run_id AND g.candle_open_at=e.signal_open_at))""",
        {"owner": checked.user_id, "episode": episode_id, "orders": list(order_ids)},
    )
    return frozenset(UUID(str(row.order_id)) for row in f21)


async def _closure_signal_current(
    session: UserSession,
    *,
    base: str,
    quote: str,
    timeframe: Timeframe,
    opened: datetime,
    provenance: Mapping[str, object],
) -> bool:
    """Caller holds the source fence through admission/fill commit."""
    closure = await closure_control(session)
    if not ((closure is not None and closure["enabled"]) or provenance.get("closure_proof_id")):
        return True
    source = await candle_source_state(session, PositionPair(base, quote), timeframe, lock=True)
    if not source.ready:
        return False
    candle = (
        (
            await session.execute(
                "SELECT * FROM market_candles WHERE source='primary_spot' AND base=:base "
                "AND quote=:quote AND timeframe=:timeframe AND open_at=:opened",
                {"base": base, "quote": quote, "timeframe": timeframe.value, "opened": opened},
            )
        )
        .mappings()
        .one_or_none()
    )
    if candle is None or candle["finality"] != "CLOSED":
        return False
    try:
        reference = proof_reference(await current_proof(session, _stored(candle).candle))
    except ClosureUnavailableError:
        return False
    expected = (
        provenance.get("closure_proof_id"),
        provenance.get("closure_policy_version"),
        provenance.get("closure_fingerprint"),
    )
    return reference is not None and reference == expected


async def _queued_signal_current(session: UserSession, command_id: UUID) -> bool:
    # The Paper wallet lock already fences risk, run and lease writers. The F-11
    # guard serializes publication and source corrections with this admission.
    await session.execute("SELECT risk_financial_fence()")
    await session.execute("SELECT hold_bot_indicator_source()")
    row = (
        await session.execute(
            """SELECT b.base,b.quote,b.timeframe,e.signal_open_at,d.input_provenance,
                  p.source_recovery_at,w.lease_until
           FROM bot_strategy_entries e JOIN bot_strategy_baskets b ON b.id=e.basket_id
           JOIN bot_order_links l ON l.command_id=e.command_id AND l.order_id=e.order_id
           JOIN bot_decisions d ON d.id=l.decision_id
           JOIN bot_runs r ON r.id=e.run_id AND r.revision=d.run_revision+1
           JOIN bot_strategy_progress p ON p.run_id=r.id AND NOT p.recovery_required
           JOIN market_price_feed f ON f.source='primary_spot' AND
             p.price_recovery_at IS NOT DISTINCT FROM f.bot_recovery_at
           JOIN bot_run_leases w ON w.run_id=r.id AND w.lease_until>clock_timestamp()
           JOIN risk_limit_settings k ON k.user_id=e.user_id AND k.mode=e.mode
             AND k.amount IS NOT NULL AND NOT k.latched
           JOIN indicator_rollout_control c ON c.id=1 AND c.mode='PREPARED'
             AND c.source_proof_state='READY'
           WHERE e.command_id=:command AND e.user_id=:owner
             AND d.input_provenance->'risk_revision'=to_jsonb(k.revision)
             AND d.input_provenance->'guard_revision'=to_jsonb(p.guard_revision)
             AND d.input_provenance->'lease_generation'=to_jsonb(w.generation)
             AND d.input_provenance->>'rollout_epoch'=c.rollout_epoch::text""",
            {"command": command_id, "owner": session.user_id},
        )
    ).one_or_none()
    if row is None:
        return False
    timeframe = Timeframe(row.timeframe)
    source = await candle_source_state(
        session, PositionPair(row.base, row.quote), timeframe, lock=True
    )
    if not source.ready or source.recovery_at != row.source_recovery_at:
        return False
    head, failure = await read_generation_authority(
        session, row.base, row.quote, timeframe, FORMULA_VERSION
    )
    now: datetime = (await session.execute("SELECT clock_timestamp()")).scalar_one()
    signal_end = advance(row.signal_open_at, timeframe, 1)
    entry_end = advance(signal_end, timeframe, 1)
    if not signal_end <= now < entry_end:
        return False
    fence = row.input_provenance.get("source_fence")
    prefix = row.input_provenance.get("indicator_prefix_end")
    try:
        prefix_end = None if not prefix else datetime.fromisoformat(prefix)
    except (TypeError, ValueError):
        return False
    if prefix_end is not None and prefix_end.tzinfo is None:
        return False
    if (
        now >= row.lease_until
        or head is None
        or failure is not None
        or str(head["id"]) != row.input_provenance.get("indicator_generation")
        or type(fence) is not int
        or not 0 <= fence <= 2**63 - 1
        or not await fresh_proof_valid(session, head, now, through=prefix_end)
    ):
        return False
    if not await _closure_signal_current(
        session,
        base=row.base,
        quote=row.quote,
        timeframe=timeframe,
        opened=row.signal_open_at,
        provenance=row.input_provenance,
    ):
        return False
    if not (
        prefix_end is None and signal_end <= head["calculation_end"]
    ) and not await require_tail_proof(
        session,
        head,
        IndicatorTailProof(
            SourceFence(head["source_epoch"], fence),
            head["calculation_start"],
            signal_end,
            prefix_end,
        ),
    ):
        return False
    # Proof reads themselves may cross the boundary or exhaust the lease.
    now = (await session.execute("SELECT clock_timestamp()")).scalar_one()
    return bool(now < row.lease_until and signal_end <= now < entry_end)


async def paper_bot_authority(
    session: UserSession, *, command_id: UUID, episode_id: UUID
) -> BotOrderAuthority:
    """Check linked authority while the parent worker holds the owner lock."""
    checked = require_user_session(session)
    row = (
        await checked.execute(
            """SELECT b.order_id,r.strategy_name,(r.status='RUNNING' AND u.use='BOT'
                        AND s.active_episode_id=r.episode_id) IS TRUE AS ready
              FROM bot_order_links b
              JOIN bot_runs r ON (r.id,r.user_id,r.mode,r.episode_id)=
                                  (b.run_id,b.user_id,b.mode,b.episode_id)
              LEFT JOIN user_trading_preferences u ON u.user_id=b.user_id
              LEFT JOIN paper_wallet_state s ON s.user_id=b.user_id AND s.wallet_id=r.wallet_id
              WHERE b.command_id=:command AND b.user_id=:owner
                AND b.episode_id=:episode AND b.mode='PAPER'""",
            {"command": command_id, "owner": checked.user_id, "episode": episode_id},
        )
    ).one_or_none()
    if row is None:
        return BotOrderAuthority.UNLINKED
    if (
        row.ready
        and row.strategy_name in CANDLE_STRATEGIES
        and not await _queued_signal_current(checked, command_id)
    ):
        return BotOrderAuthority.BLOCKED
    if row.ready and await invalidated_strategy_openings(
        checked, episode_id=episode_id, order_ids=(UUID(str(row.order_id)),)
    ):
        return BotOrderAuthority.BLOCKED
    return BotOrderAuthority.READY if row.ready else BotOrderAuthority.BLOCKED
