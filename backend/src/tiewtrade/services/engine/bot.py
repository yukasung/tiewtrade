"""Explicit F-20 worker composition for deployment-owned strategies."""

import logging
from collections.abc import Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.core.orders import OrderError, TradingMode
from tiewtrade.core.strategies import Strategy, StrategyDecision, evaluate_strategy
from tiewtrade.infra.bots.catalog import apply_catalog_stop, due_catalog_stops
from tiewtrade.infra.bots.claims import (
    BotClaimLostError,
    claim_control,
    due_controls,
    finish_control,
    require_control_claim,
)
from tiewtrade.infra.bots.decisions import BotDecisionConflictError
from tiewtrade.infra.bots.evaluation import (
    PreparedQuote,
    QuoteEvaluation,
    evaluate_published_quote,
    pause_missing_inputs,
)
from tiewtrade.infra.bots.inputs import BotInputsUnavailableError, read_bot_indicators
from tiewtrade.infra.bots.start import PublishedConfiguration, apply_paper_start
from tiewtrade.infra.db import DatabaseRole, InfraError, scan_session_bypassing_rls, user_session
from tiewtrade.services.engine.bot_replacement import clear_replacement_stop

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PublishedStrategy:
    definition: PublishedConfiguration
    strategy: Strategy

    def __post_init__(self) -> None:
        if self.strategy.descriptor != self.definition.descriptor:
            raise ValueError("strategy implementation does not match its published definition")


class StrategyRegistry:
    """Immutable executable definitions. Runtime state always lives in PostgreSQL."""

    def __init__(self, entries: tuple[PublishedStrategy, ...] = ()) -> None:
        by_ref: dict[str, PublishedStrategy] = {}
        implementations: dict[tuple[str, int], Strategy] = {}
        for entry in entries:
            descriptor = entry.definition.descriptor
            identity = (descriptor.name, descriptor.version)
            if entry.definition.reference in by_ref:
                raise ValueError("duplicate published configuration reference")
            existing = implementations.get(identity)
            if existing is not None and existing is not entry.strategy:
                raise ValueError("strategy version identifies more than one implementation")
            implementations[identity] = entry.strategy
            by_ref[entry.definition.reference] = entry
        self._by_ref: Mapping[str, PublishedStrategy] = MappingProxyType(by_ref)
        self._implementations: Mapping[tuple[str, int], Strategy] = MappingProxyType(
            implementations
        )

    def configuration(self, reference: str) -> PublishedStrategy | None:
        return self._by_ref.get(reference)

    def implementation(
        self, name: str, version: int, configuration_version: int, state_version: int
    ) -> Strategy | None:
        strategy = self._implementations.get((name, version))
        if strategy is None:
            return None
        descriptor = strategy.descriptor
        if (
            descriptor.name != name
            or descriptor.version != version
            or descriptor.configuration_version != configuration_version
            or descriptor.state_version != state_version
        ):
            return None
        return strategy


@dataclass(frozen=True, slots=True)
class BotControlRound:
    applied: int = 0
    refused: int = 0
    deferred: int = 0


async def run_bot_control_round(
    *, engine: AsyncEngine, scan_engine: AsyncEngine, registry: StrategyRegistry, limit: int = 20
) -> BotControlRound:
    """Process bounded due hints with a separately committed owner lease."""
    async with scan_session_bypassing_rls(scan_engine) as scan:
        hints = await due_controls(scan, limit=limit)
    applied = refused = deferred = 0
    for hint in hints:
        try:
            async with user_session(engine, hint.user_id, role=DatabaseRole.ENGINE) as session:
                await session.execute("SET LOCAL lock_timeout='500ms'")
                claim = await claim_control(session, hint)
            if claim is None:
                continue
            async with user_session(engine, hint.user_id, role=DatabaseRole.ENGINE) as session:
                await session.execute("SET LOCAL lock_timeout='500ms'")
                await require_control_claim(session, claim)
                started = False
                if hint.mode is not TradingMode.PAPER:
                    await finish_control(session, claim, failure_code="LIVE_EXECUTION_UNAVAILABLE")
                else:
                    reference = (
                        await session.execute(
                            """SELECT payload->>'strategy_config_ref' FROM bot_control_requests
                               WHERE id=:id AND user_id=:owner AND mode='PAPER'""",
                            {"id": hint.request_id, "owner": hint.user_id},
                        )
                    ).scalar_one_or_none()
                    entry = (
                        registry.configuration(reference) if isinstance(reference, str) else None
                    )
                    if entry is None:
                        await finish_control(
                            session, claim, failure_code="BOT_STRATEGY_UNAVAILABLE"
                        )
                    else:
                        started = (
                            await apply_paper_start(
                                session,
                                claim,
                                entry.definition,
                                clear_replacement_stop=clear_replacement_stop,
                            )
                            is not None
                        )
            if started:
                applied += 1
            else:
                refused += 1
        except (BotClaimLostError, InfraError):
            deferred += 1
            _LOGGER.warning("bot control deferred request_id=%s", hint.request_id)
    return BotControlRound(applied, refused, deferred)


async def run_bot_quote(
    *, engine: AsyncEngine, owner: UUID, run_id: UUID, registry: StrategyRegistry, worker_id: UUID
) -> UUID | None:
    """Evaluate without financial locks, then discard any stale snapshot or result."""
    return await _evaluate_bot_input(
        engine=engine, owner=owner, run_id=run_id, registry=registry, worker_id=worker_id
    )


async def _evaluate_bot_input(
    *,
    engine: AsyncEngine,
    owner: UUID,
    run_id: UUID,
    registry: StrategyRegistry,
    worker_id: UUID,
    probe_stop_id: UUID | None = None,
) -> UUID | None:
    async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
        await session.execute("SET LOCAL lock_timeout='500ms'")
        await session.execute("SET LOCAL statement_timeout='2s'")
        prepared = await evaluate_published_quote(
            session,
            run_id,
            resolve=registry.implementation,
            worker_id=worker_id,
            probe_stop_id=probe_stop_id,
        )
    if not isinstance(prepared, PreparedQuote):
        return prepared
    dependencies = None
    descriptor = prepared.strategy.descriptor
    if descriptor.required_indicators or descriptor.timeframe is not None:
        try:
            async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
                dependencies = await read_bot_indicators(session, descriptor, prepared.snapshot)
            prepared = replace(
                prepared,
                snapshot=replace(
                    prepared.snapshot,
                    indicators=dependencies.values,
                    indicator_revision=dependencies.revision,
                ),
            )
        except BotInputsUnavailableError as error:
            if probe_stop_id is None:
                async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
                    await pause_missing_inputs(session, prepared, str(error))
            return None
    try:
        if prepared.previous_decision is not None and probe_stop_id is None:
            decision = StrategyDecision(prepared.state)
        else:
            decision = evaluate_strategy(
                prepared.strategy,
                prepared.snapshot,
                prepared.configuration,
                prepared.state,
                scope=prepared.scope,
            )
    except Exception:
        # Only the pure boundary is classified here. The final transaction
        # fences a failure exactly as it fences a successful decision.
        decision = None
    async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
        await session.execute("SET LOCAL lock_timeout='500ms'")
        await session.execute("SET LOCAL statement_timeout='2s'")
        try:
            result = await evaluate_published_quote(
                session,
                run_id,
                resolve=registry.implementation,
                worker_id=worker_id,
                probe_stop_id=probe_stop_id,
                evaluation=QuoteEvaluation(prepared, decision),
                indicator_inputs=dependencies,
            )
        except BotInputsUnavailableError as error:
            if probe_stop_id is None:
                await pause_missing_inputs(session, prepared, str(error))
            return None
        assert not isinstance(result, PreparedQuote)
        return result


async def run_bot_catalog_round(
    *, engine: AsyncEngine, scan_engine: AsyncEngine, limit: int = 20
) -> int:
    """Consume withdrawal hints in owner transactions, even with an empty strategy registry."""
    async with scan_session_bypassing_rls(scan_engine) as scan:
        hints = await due_catalog_stops(scan, limit=limit)
    applied = 0
    for hint in hints:
        try:
            async with user_session(engine, hint.user_id, role=DatabaseRole.ENGINE) as session:
                await session.execute("SET LOCAL lock_timeout='500ms'")
                await session.execute("SET LOCAL statement_timeout='2s'")
                changed = await apply_catalog_stop(session, hint)
            applied += int(changed)
        except InfraError:
            _LOGGER.warning("bot catalog stop deferred run_id=%s", hint.run_id)
    return applied


@dataclass(frozen=True, slots=True)
class BotWorkerRound:
    catalog_stops: int
    controls: BotControlRound
    next_cursor: UUID | None
    evaluated: int
    recovery_proofs: int


async def run_bot_worker_round(
    *,
    engine: AsyncEngine,
    scan_engine: AsyncEngine,
    registry: StrategyRegistry,
    cursor: UUID | None,
    worker_id: UUID,
    limit: int = 20,
) -> BotWorkerRound:
    """Bound each phase. The cursor only decides scan order; DB records deduplicate work."""
    catalog = await run_bot_catalog_round(engine=engine, scan_engine=scan_engine, limit=limit)
    controls = await run_bot_control_round(
        engine=engine, scan_engine=scan_engine, registry=registry, limit=limit
    )
    async with scan_session_bypassing_rls(scan_engine) as scan:
        rows = (
            await scan.execute(
                "SELECT * FROM due_paper_bot_runs(:cursor,:limit)",
                {"cursor": cursor, "limit": limit},
            )
        ).all()
    evaluated = 0
    for hint in rows:
        try:
            decision = await run_bot_quote(
                engine=engine,
                owner=hint.user_id,
                run_id=hint.run_id,
                registry=registry,
                worker_id=worker_id,
            )
            evaluated += int(decision is not None)
        except (InfraError, OrderError, BotDecisionConflictError):
            _LOGGER.warning("bot quote deferred run_id=%s", hint.run_id)
    async with scan_session_bypassing_rls(scan_engine) as scan:
        recovery = (
            await scan.execute("SELECT * FROM due_bot_recovery_probes(:limit)", {"limit": limit})
        ).all()
    proofs = 0
    for hint in recovery:
        try:
            proof = await prove_bot_strategy_recovery(
                engine=engine,
                owner=hint.user_id,
                run_id=hint.run_id,
                stop_id=hint.stop_id,
                registry=registry,
                worker_id=worker_id,
            )
            proofs += int(proof is not None)
        except InfraError:
            _LOGGER.warning("bot recovery probe deferred run_id=%s", hint.run_id)
    return BotWorkerRound(
        catalog, controls, rows[-1].run_id if len(rows) == limit else None, evaluated, proofs
    )


async def prove_bot_strategy_recovery(
    *,
    engine: AsyncEngine,
    owner: UUID,
    run_id: UUID,
    stop_id: UUID,
    registry: StrategyRegistry,
    worker_id: UUID,
) -> UUID | None:
    """Evaluate the pinned strategy only as proof. This does not enqueue an order."""
    return await _evaluate_bot_input(
        engine=engine,
        owner=owner,
        run_id=run_id,
        registry=registry,
        worker_id=worker_id,
        probe_stop_id=stop_id,
    )
