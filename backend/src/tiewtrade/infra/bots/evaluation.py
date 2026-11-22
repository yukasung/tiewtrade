"""Check Paper strategy inputs against current financial and market authority."""

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import cast
from uuid import UUID, uuid5

from tiewtrade.core.bots import BotStatus, BotTransition, transition_bot
from tiewtrade.core.manual_trading import available_quote
from tiewtrade.core.money import Money
from tiewtrade.core.orders import OrderOrigin, OrderScope, SourceUnavailableError, TradingMode
from tiewtrade.core.realtime_prices import MAX_PRICE_AGE
from tiewtrade.core.risk_limits import RiskReason, RiskScope
from tiewtrade.core.strategies import (
    Strategy,
    StrategyDecision,
    StrategyDocument,
    StrategyInput,
    document_from_payload,
)
from tiewtrade.core.strategy_config import (
    CANDLE_STRATEGIES,
    decode_strategy_config,
)
from tiewtrade.infra.bots.candle_sources import (
    candle_source_state,
    ensure_candles,
    price_recovery_at,
)
from tiewtrade.infra.bots.catalog import CatalogStopHint, apply_catalog_stop
from tiewtrade.infra.bots.decisions import EvaluatedDecision, record_paper_decision
from tiewtrade.infra.bots.feedback import (
    next_paper_feedback,
    restore_status_feedback,
    status_feedback_payload,
)
from tiewtrade.infra.bots.inputs import (
    IndicatorInputs,
    require_current_candle,
    require_current_indicators,
    strategy_candle_identity,
)
from tiewtrade.infra.bots.system_stop import request_system_stop
from tiewtrade.infra.db.session import UserSession
from tiewtrade.infra.paper_orders.storage import lock_pair_catalog
from tiewtrade.infra.paper_wallet import get_wallet
from tiewtrade.infra.paper_wallet.records import ACTIVITY_UNKNOWN
from tiewtrade.infra.positions.views import held_and_reserved
from tiewtrade.infra.risk_limits.dispatch import lock_risk_owner
from tiewtrade.infra.risk_limits.monitor import replay_monitor
from tiewtrade.infra.risk_limits.policy import paper_opening_protocol_enabled
from tiewtrade.infra.risk_limits.storage import read_setting
from tiewtrade.infra.risk_limits.views import read_evidence
from tiewtrade.infra.trading_stops.storage import current_opening_blocked, global_shared_lock


@dataclass(frozen=True, slots=True)
class PreparedQuote:
    run_id: UUID
    run_revision: int
    lease_generation: int | None
    input_identity: str
    strategy: Strategy
    scope: OrderScope
    snapshot: StrategyInput
    configuration: StrategyDocument
    state: StrategyDocument
    risk_revision: int | None
    previous_decision: UUID | None = None


@dataclass(frozen=True, slots=True)
class QuoteEvaluation:
    prepared: PreparedQuote
    # None is a pure strategy failure. It is applied only if its snapshot is current.
    decision: StrategyDecision | None


async def _write_status(
    session: UserSession,
    run_id: UUID,
    target: BotStatus,
    revision: int,
    event: str,
    reason: str | None = None,
) -> None:
    await session.execute(
        "UPDATE bot_runs SET status=:status,revision=:revision WHERE id=:id",
        {"id": run_id, "status": target.value, "revision": revision},
    )
    await session.execute(
        """INSERT INTO bot_run_events(id,run_id,user_id,mode,revision,event,details)
           VALUES(:id,:run,:owner,'PAPER',:revision,:event,
                  jsonb_build_object('reason',CAST(:reason AS text)))""",
        {
            "id": uuid5(run_id, f"{event}:{revision}"),
            "run": run_id,
            "owner": session.user_id,
            "revision": revision,
            "event": event,
            "reason": reason,
        },
    )
    if target in (BotStatus.PAUSED, BotStatus.RECOVERING):
        name = (
            await session.execute(
                "SELECT strategy_name FROM bot_runs WHERE id=:run", {"run": run_id}
            )
        ).scalar_one()
        indicator_wait = reason in (
            "INDICATOR_NOT_READY",
            "INDICATOR_SOURCE_CHANGED",
            "BOT_CANDLE_WARM_UP",
            "BOT_CANDLE_NOT_READY",
            "BOT_CANDLE_AUTHORITY_CHANGED",
        )
        if name in CANDLE_STRATEGIES and (target is BotStatus.RECOVERING or not indicator_wait):
            await session.execute(
                "UPDATE bot_strategy_progress SET eligible_after=clock_timestamp(),"
                "recovery_required=true "
                "WHERE run_id=:run",
                {"run": run_id},
            )


async def evaluate_published_quote(
    session: UserSession,
    run_id: UUID,
    *,
    resolve: Callable[[str, int, int, int], Strategy | None],
    worker_id: UUID,
    probe_stop_id: UUID | None = None,
    evaluation: QuoteEvaluation | None = None,
    indicator_inputs: IndicatorInputs | None = None,
    resolve_configuration: Callable[[str, int, int, int, StrategyDocument], Strategy | None]
    | None = None,
) -> UUID | PreparedQuote | None:
    """Prepare or fence a declared quote/feedback input and its dependencies."""
    # asyncpg UUID subclasses must not leak into the strict pure contract.
    run_id = UUID(str(run_id))
    await global_shared_lock(session)
    await lock_risk_owner(session, TradingMode.PAPER)
    if probe_stop_id is None and await current_opening_blocked(
        session, TradingMode.PAPER, OrderOrigin.BOT
    ):
        return None
    run = (
        await session.execute(
            """SELECT r.*,r.configuration::text AS configuration_text,
                   r.strategy_state::text AS state_text,e.details AS entry
               FROM bot_runs r JOIN bot_run_events e ON e.run_id=r.id AND e.user_id=r.user_id
                 AND e.mode=r.mode AND e.event='START_REQUEST_APPLIED' AND e.revision=1
               WHERE r.id=:id AND r.user_id=:owner AND r.mode='PAPER'
                 AND ((CAST(:probe AS uuid) IS NULL
                   AND r.status IN ('STARTING','RUNNING','PAUSED','RECOVERING'))
                   OR (CAST(:probe AS uuid) IS NOT NULL AND r.status='STOPPED')) FOR UPDATE OF r""",
            {"id": run_id, "owner": session.user_id, "probe": probe_stop_id},
        )
    ).one_or_none()
    if run is None:
        return None

    status = BotStatus(run.status)
    run_revision = int(run.revision)
    generation: int | None = None
    failed_input: str | None = None
    failed_feedback_status: object = None
    if probe_stop_id is not None:
        eligible = (
            await session.execute(
                """SELECT e.details->>'input_identity' AS failed_input,
                          e.details->'feedback_status' AS failed_feedback_status,
                          e.event AS failure_event,e.details ? 'input_identity' AS input_known
                   FROM trading_stop_requests r
                   JOIN bot_run_events e ON e.run_id=:run AND e.user_id=r.user_id
                     AND e.event IN ('STRATEGY_VERSION_UNAVAILABLE','STRATEGY_EVALUATION_FAILED')
                     AND e.details->>'stop_id'=CAST(:stop AS uuid)::text
                   WHERE r.id=:stop AND r.user_id=:owner AND r.mode='PAPER'
                     AND r.action='STOP' AND r.cause='SYSTEM'
                     AND r.reason_code IN
                       ('STRATEGY_VERSION_UNAVAILABLE','STRATEGY_EVALUATION_FAILED')
                     AND r.revision=(SELECT max(revision) FROM trading_stop_requests
                       WHERE user_id=:owner AND mode='PAPER' AND action='STOP' AND cause='SYSTEM')
                     AND NOT EXISTS(SELECT 1 FROM trading_stop_requests resumed
                       JOIN trading_stop_results outcome ON outcome.request_id=resumed.id
                       WHERE resumed.expected_stop_id=r.id AND resumed.action='RESUME'
                         AND outcome.state='APPLIED')
                   ORDER BY e.revision DESC LIMIT 1""",
                {
                    "run": run_id,
                    "stop": probe_stop_id,
                    "owner": session.user_id,
                },
            )
        ).one_or_none()
        if eligible is None:
            return None
        failed_input = eligible.failed_input
        failed_feedback_status = eligible.failed_feedback_status
        await session.execute(
            """INSERT INTO bot_recovery_schedule(run_id,user_id,mode,last_attempt_at)
               VALUES(:run,:owner,'PAPER',clock_timestamp())
               ON CONFLICT(run_id) DO UPDATE SET last_attempt_at=EXCLUDED.last_attempt_at""",
            {"run": run_id, "owner": session.user_id},
        )
        if eligible.failure_event == "STRATEGY_EVALUATION_FAILED" and not eligible.input_known:
            # An older writer did not retain whether quote or feedback failed.
            # Rotate the scheduling hint, but never certify a guessed context.
            return None
    else:
        lease = (
            await session.execute(
                """SELECT worker_id,generation,lease_until>clock_timestamp() AS valid
                   FROM bot_run_leases WHERE run_id=:run FOR UPDATE""",
                {"run": run_id},
            )
        ).one_or_none()
        if lease is not None and lease.valid and lease.worker_id != worker_id:
            return None
        takeover = lease is None or not lease.valid
        generation = 1 if lease is None else int(lease.generation) + int(takeover)
        await session.execute(
            """INSERT INTO bot_run_leases(run_id,user_id,mode,worker_id,generation,lease_until)
               VALUES(:run,:owner,'PAPER',:worker,:generation,
                      clock_timestamp()+interval '30 seconds')
               ON CONFLICT(run_id) DO UPDATE SET worker_id=EXCLUDED.worker_id,
                 generation=EXCLUDED.generation,lease_until=EXCLUDED.lease_until""",
            {
                "run": run_id,
                "owner": session.user_id,
                "worker": worker_id,
                "generation": generation,
            },
        )
        if takeover and status in (BotStatus.RUNNING, BotStatus.PAUSED):
            status = transition_bot(status, BotTransition.RECOVER)
            run_revision += 1
            await _write_status(session, run_id, status, run_revision, "WORKER_TAKEOVER")

    async def pause(reason: str) -> None:
        if status in (BotStatus.STARTING, BotStatus.RUNNING, BotStatus.RECOVERING):
            target = transition_bot(status, BotTransition.SOURCE_UNAVAILABLE)
            await _write_status(
                session, run_id, target, run_revision + 1, "SOURCE_NOT_READY", reason
            )

    async def ready() -> int:
        if run.strategy_name in CANDLE_STRATEGIES and indicator_inputs is not None:
            pinned = decode_strategy_config(run.strategy_name, config)
            source = await candle_source_state(session, pinned.pair, pinned.timeframe, lock=True)
            price_recovered = await price_recovery_at(session)
            if source.ready:
                await session.execute(
                    """UPDATE bot_strategy_progress SET eligible_after=clock_timestamp(),
                    recovery_required=false,source_recovery_at=:recovered,
                    price_recovery_at=:price_recovered,indicator_source_epoch=:epoch
                    WHERE run_id=:run AND (recovery_required OR
                      price_recovery_at IS DISTINCT FROM CAST(:price_recovered AS timestamptz) OR
                      indicator_source_epoch IS DISTINCT FROM CAST(:epoch AS uuid) OR
                      (CAST(:recovered AS timestamptz) IS NOT NULL AND
                        (source_recovery_at IS NULL OR source_recovery_at<:recovered)))""",
                    {
                        "run": run_id,
                        "recovered": source.recovery_at,
                        "price_recovered": price_recovered,
                        "epoch": indicator_inputs.generation["source_epoch"],
                    },
                )
        if status is BotStatus.RUNNING:
            return run_revision
        target = transition_bot(
            status, BotTransition.READY, readiness_proven=True, stop_cleared=True
        )
        revision = run_revision + 1
        await _write_status(session, run_id, target, revision, "RUN_READY")
        return revision

    strategy = resolve(
        run.strategy_name, run.strategy_version, run.configuration_version, run.state_version
    )
    if resolve_configuration is not None and run.strategy_name in CANDLE_STRATEGIES:
        try:
            pinned = document_from_payload(
                json.loads(run.configuration_text), expected_version=run.configuration_version
            )
            strategy = resolve_configuration(
                run.strategy_name,
                run.strategy_version,
                run.configuration_version,
                run.state_version,
                pinned,
            )
        except (ValueError, TypeError):
            strategy = None
    if strategy is None:
        if probe_stop_id is not None:
            return None
        await request_system_stop(
            session,
            run_id=run_id,
            stop_id=uuid5(run_id, f"missing-version:{run.revision}"),
            reason="STRATEGY_VERSION_UNAVAILABLE",
        )
        return None
    try:
        config = document_from_payload(
            json.loads(run.configuration_text), expected_version=run.configuration_version
        )
        state = document_from_payload(
            json.loads(run.state_text), expected_version=run.state_version
        )
        if run.strategy_name in CANDLE_STRATEGIES:
            decode_strategy_config(run.strategy_name, config).validate_checkpoint(state)
    except Exception:
        if probe_stop_id is not None:
            return None
        # Only pure decoding/evaluation is inside this boundary. A database
        # failure must roll back instead of being classified as a strategy error.
        await request_system_stop(
            session,
            run_id=run_id,
            stop_id=uuid5(run_id, f"evaluation:{run.revision}"),
            reason="STRATEGY_EVALUATION_FAILED",
        )
        return None
    if not (strategy.descriptor.quote_trigger or strategy.descriptor.execution_feedback_trigger):
        return None
    if strategy.descriptor.name in CANDLE_STRATEGIES:
        from tiewtrade.infra.bots.baskets import finish_empty_baskets

        await finish_empty_baskets(session, run_id)
    pair = next(
        (
            p
            for p in strategy.descriptor.pairs
            if (p.base, p.quote) == (run.entry.get("base"), run.entry.get("quote"))
        ),
        None,
    )
    if pair is None:
        return None
    catalog = await lock_pair_catalog(session, pair)
    if (
        probe_stop_id is None
        and catalog.latest_removed_revision is not None
        and catalog.latest_removed_revision > run.entry["catalog_revision"]
    ):
        await apply_catalog_stop(
            session,
            CatalogStopHint(
                run_id, session.user_id, TradingMode.PAPER, catalog.latest_removed_revision
            ),
        )
        return None
    if (pair.base, pair.quote) not in catalog.snapshot.active_pairs:
        return None

    reconciliation_required = (
        status in (BotStatus.STARTING, BotStatus.PAUSED, BotStatus.RECOVERING)
        or probe_stop_id is not None
    )
    wallet = await get_wallet(session, include_reset_readiness=reconciliation_required)
    if wallet is None or wallet.wallet_id != run.wallet_id or wallet.episode_id != run.episode_id:
        await pause("ACCOUNT_NOT_READY")
        return None
    if reconciliation_required:
        if wallet.reset_reason == ACTIVITY_UNKNOWN:
            await pause("ACCOUNT_NOT_READY")
            return None
        pending = (
            await session.execute(
                """SELECT EXISTS(
                    SELECT 1 FROM paper_order_commands c
                    WHERE c.episode_id=:episode AND NOT EXISTS (
                      SELECT 1 FROM paper_order_command_results r WHERE r.command_id=c.id))""",
                {"episode": wallet.episode_id},
            )
        ).scalar_one()
        if pending:
            await pause("ORDER_RECONCILIATION_PENDING")
            return None
    use = (
        await session.execute(
            "SELECT use FROM user_trading_preferences WHERE user_id=:owner",
            {"owner": session.user_id},
        )
    ).scalar_one_or_none()
    if use != "BOT" or not await paper_opening_protocol_enabled(session):
        await pause("BOT_ACCOUNT_NOT_READY")
        return None
    scope = OrderScope(UUID(str(session.user_id)), UUID(str(wallet.episode_id)), TradingMode.PAPER)
    risk_scope = RiskScope(
        scope.owner_id, scope.mode, UUID(str(wallet.wallet_id)), scope.episode_id
    )
    setting = await read_setting(session, risk_scope)
    if setting.limit is None or setting.latched:
        await pause("RISK_NOT_READY")
        return None
    await replay_monitor(session, setting)
    setting = await read_setting(session, risk_scope)
    evidence = await read_evidence(session, setting)
    quote = next((item for item in evidence.prices if item.pair == pair), None)
    if (
        evidence.evaluation.reason is not RiskReason.READY
        or not evidence.admission_enabled
        or quote is None
        or quote.observation is None
    ):
        await pause("MARKET_OR_RISK_NOT_READY")
        return None
    price = quote.price_at(evidence.evaluation.evaluated_at)
    if price is None:
        await pause("MARKET_NOT_READY")
        return None
    observation = quote.observation
    feedback = (
        await next_paper_feedback(session, run_id)
        if strategy.descriptor.execution_feedback_trigger and probe_stop_id is None
        else None
    )
    if probe_stop_id is not None and failed_input is not None:
        if failed_input.startswith(("order:", "reject:", "state:")):
            # A quote/no-op cannot prove recovery from a feedback failure.
            if not strategy.descriptor.execution_feedback_trigger:
                return None
            if failed_feedback_status is None:
                feedback = await next_paper_feedback(session, run_id, input_identity=failed_input)
            else:
                feedback = await restore_status_feedback(
                    session, run_id, failed_input, failed_feedback_status
                )
            if feedback is None:
                return None
        elif failed_input.startswith("candle:") and strategy.descriptor.name in CANDLE_STRATEGIES:
            # Preparation loads the candle. The final proof must include that dependency.
            if evaluation is not None and (
                indicator_inputs is None or indicator_inputs.candle_input is None
            ):
                return None
        elif not failed_input.startswith("quote:"):
            return None
    if feedback is None and not strategy.descriptor.quote_trigger and probe_stop_id is None:
        return None
    strategy_candle = feedback is None and strategy.descriptor.name in CANDLE_STRATEGIES
    if evaluation is None and strategy_candle:
        pinned_config = decode_strategy_config(run.strategy_name, config)
        await ensure_candles(session, pair, pinned_config.timeframe, observation.trade_time)
    input_identity = (
        f"quote:{observation.source}:{observation.trade_id}"
        if feedback is None
        else feedback.input_identity
    )
    if (
        feedback is None
        and indicator_inputs is not None
        and indicator_inputs.candle_input is not None
    ):
        input_identity = strategy_candle_identity(indicator_inputs.candle_input)
    previous = (
        await session.execute(
            "SELECT id FROM bot_decisions WHERE run_id=:run AND input_identity=:input",
            {"run": run_id, "input": input_identity},
        )
    ).scalar_one_or_none()
    needs_indicators = (
        bool(strategy.descriptor.required_indicators) or strategy.descriptor.timeframe is not None
    ) and not (strategy.descriptor.name in CANDLE_STRATEGIES and feedback is not None)
    if previous is not None and probe_stop_id is None and not needs_indicators:
        await ready()
        return UUID(str(previous))

    try:
        held, _ = await held_and_reserved(session, scope.episode_id, pair)
    except SourceUnavailableError:
        if probe_stop_id is None:
            await pause("ACCOUNT_NOT_READY")
        return None
    rows = (
        await session.execute(
            "SELECT quote_reserved,quote FROM paper_reservations WHERE episode_id=:episode",
            {"episode": scope.episode_id},
        )
    ).all()
    _, cash = available_quote(
        wallet.balance, tuple(Money.of(r.quote_reserved, r.quote) for r in rows)
    )
    snapshot = StrategyInput(
        pair,
        observation.trade_time,
        quote.revision,
        wallet.revision,
        price,
        cash,
        held,
        scope,
        run_id,
        input_identity,
        feedback=None if feedback is None else feedback.value,
        indicators=() if indicator_inputs is None else indicator_inputs.values,
        indicator_revision=None if indicator_inputs is None else indicator_inputs.revision,
        candle_input=None if indicator_inputs is None else indicator_inputs.candle_input,
    )
    if needs_indicators and indicator_inputs is not None:
        await require_current_indicators(session, indicator_inputs)
        await require_current_candle(session, snapshot, indicator_inputs)
    prepared = PreparedQuote(
        run_id,
        run_revision,
        generation,
        input_identity,
        strategy,
        scope,
        snapshot,
        config,
        state,
        setting.revision if strategy_candle else None,
        None if previous is None else UUID(str(previous)),
    )
    if evaluation is None:
        return prepared
    if prepared != evaluation.prepared:
        return None
    if needs_indicators and indicator_inputs is None:
        return None
    if previous is not None and probe_stop_id is None:
        await ready()
        return UUID(str(previous))
    decision = evaluation.decision
    if decision is None:
        if probe_stop_id is None:
            await request_system_stop(
                session,
                run_id=run_id,
                stop_id=uuid5(run_id, f"evaluation:{run.revision}"),
                reason="STRATEGY_EVALUATION_FAILED",
                input_identity=input_identity,
                feedback_status=status_feedback_payload(snapshot.feedback),
            )
        return None
    if probe_stop_id is not None:
        watermark = evidence.price_watermark
        if watermark is None or watermark <= 0:
            return None
        expires = min(quote.lease_until, observation.trade_time + MAX_PRICE_AGE)
        proof_id = uuid5(
            probe_stop_id,
            f"{run_revision}:{wallet.revision}:{catalog.snapshot.revision}:"
            f"{setting.revision}:{watermark}:{expires.isoformat()}",
        )
        await session.execute(
            """INSERT INTO bot_resume_proofs(id,run_id,user_id,mode,stop_id,run_revision,
                   wallet_revision,catalog_revision,risk_revision,watermark,expires_at)
               VALUES(:id,:run,:owner,'PAPER',:stop,:rev,:wallet,:catalog,:risk,:frame,:expires)
               ON CONFLICT(id) DO NOTHING""",
            {
                "id": proof_id,
                "run": run_id,
                "owner": session.user_id,
                "stop": probe_stop_id,
                "rev": run_revision,
                "wallet": wallet.revision,
                "catalog": catalog.snapshot.revision,
                "risk": setting.revision,
                "frame": watermark,
                "expires": expires,
            },
        )
        return proof_id
    revision = await ready()
    return await record_paper_decision(
        session,
        EvaluatedDecision(
            run_id,
            uuid5(run_id, input_identity),
            input_identity,
            revision,
            run.strategy_version,
            run.configuration_version,
            state,
            decision,
            {
                "market_revision": snapshot.market_revision,
                "account_revision": snapshot.account_revision,
                "observed_at": snapshot.observed_at.isoformat(),
                "indicator_revision": snapshot.indicator_revision or "",
                **(
                    {
                        "candle_open_at": snapshot.candle_input.candle.open_at.isoformat(),
                        "guard_revision": snapshot.candle_input.guard_revision,
                        "closure_proof_id": (
                            ""
                            if snapshot.candle_input.closure_proof is None
                            else snapshot.candle_input.closure_proof[0]
                        ),
                        "closure_policy_version": (
                            0
                            if snapshot.candle_input.closure_proof is None
                            else snapshot.candle_input.closure_proof[1]
                        ),
                        "closure_fingerprint": (
                            ""
                            if snapshot.candle_input.closure_proof is None
                            else snapshot.candle_input.closure_proof[2]
                        ),
                        "indicator_generation": str(indicator_inputs.generation["id"]),
                        "rollout_epoch": str(indicator_inputs.rollout_epoch),
                        "source_fence": (
                            indicator_inputs.tail.fence.revision
                            if indicator_inputs.tail
                            else int(indicator_inputs.generation["source_fence"])
                        ),
                        "indicator_prefix_end": (
                            indicator_inputs.tail.prefix_end.isoformat()
                            if indicator_inputs.tail is not None
                            and indicator_inputs.tail.prefix_end is not None
                            else ""
                        ),
                        "risk_revision": setting.revision,
                        "lease_generation": generation,
                        "signal_atr": cast(
                            Money, dict(snapshot.indicators)["atr14"].value
                        ).as_parts()["amount"],
                    }
                    if snapshot.candle_input is not None
                    and indicator_inputs is not None
                    and generation is not None
                    else {}
                ),
            },
        ),
    )


async def pause_missing_inputs(session: UserSession, prepared: PreparedQuote, reason: str) -> None:
    """Pause only the still-current leased run; never overwrite a concurrent stop/decision."""
    await global_shared_lock(session)
    await lock_risk_owner(session, TradingMode.PAPER)
    row = (
        await session.execute(
            """SELECT r.status FROM bot_runs r JOIN bot_run_leases l ON l.run_id=r.id
           WHERE r.id=:run AND r.user_id=:owner AND r.mode='PAPER' AND r.revision=:rev
             AND r.status IN ('STARTING','RUNNING','RECOVERING','PAUSED')
             AND l.generation=:generation AND l.lease_until>clock_timestamp() FOR UPDATE OF r""",
            {
                "run": prepared.run_id,
                "owner": session.user_id,
                "rev": prepared.run_revision,
                "generation": prepared.lease_generation,
            },
        )
    ).one_or_none()
    if row is None:
        return
    if row.status == "PAUSED":
        last = (
            await session.execute(
                """SELECT details->>'reason' FROM bot_run_events WHERE run_id=:run
                   ORDER BY revision DESC LIMIT 1""",
                {"run": prepared.run_id},
            )
        ).scalar_one_or_none()
        if last == reason:
            return
    await _write_status(
        session,
        prepared.run_id,
        BotStatus.PAUSED,
        prepared.run_revision + 1,
        "SOURCE_NOT_READY",
        reason,
    )
