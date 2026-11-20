"""Transactional Paper decision journal. The caller supplies fenced admission."""

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from uuid import UUID

from tiewtrade.core.bots import BotStatus
from tiewtrade.core.orders import OrderIntent, OrderOrigin, TradingMode
from tiewtrade.core.strategies import StrategyDecision, StrategyDocument, document_payload
from tiewtrade.infra.bots.paper_admission import admit_paper_bot_intent
from tiewtrade.infra.db.session import UserSession, require_user_session
from tiewtrade.infra.risk_limits.dispatch import lock_risk_owner
from tiewtrade.infra.trading_stops.storage import current_opening_blocked, global_shared_lock


class BotDecisionConflictError(ValueError):
    """The decision does not match the current authority or stored input."""


@dataclass(frozen=True, slots=True)
class EvaluatedDecision:
    run_id: UUID
    decision_id: UUID
    input_identity: str
    run_revision: int
    strategy_version: int
    configuration_version: int
    state_before: StrategyDocument
    decision: StrategyDecision
    input_provenance: dict[str, str | int] | None = None


# Admission receives the very same UserSession so command creation and linking
# roll back with the decision. It must enforce the current Paper admission policy.
type AdmitPaperIntent = Callable[[UserSession, UUID, OrderIntent], Awaitable[UUID]]


async def record_paper_decision(
    session: UserSession,
    evaluated: EvaluatedDecision,
    *,
    admit: AdmitPaperIntent = admit_paper_bot_intent,
) -> UUID:
    """Persist the accepted decision and its command IDs in one caller transaction."""
    checked = require_user_session(session)
    await global_shared_lock(checked)
    await lock_risk_owner(checked, TradingMode.PAPER)

    params = {
        "id": evaluated.decision_id,
        "run": evaluated.run_id,
        "owner": checked.user_id,
        "input": evaluated.input_identity,
    }
    previous = (
        await checked.execute(
            """SELECT id FROM bot_decisions WHERE run_id=:run AND user_id=:owner
              AND mode='PAPER' AND input_identity=:input""",
            params,
        )
    ).scalar_one_or_none()
    if previous is not None:
        return UUID(str(previous))
    if await current_opening_blocked(checked, TradingMode.PAPER, OrderOrigin.BOT):
        raise BotDecisionConflictError("trading stop blocks strategy decisions")

    run = (
        await checked.execute(
            """SELECT status,revision,strategy_version,configuration_version,state_version,
                     wallet_id,episode_id,strategy_state::text AS strategy_state
                FROM bot_runs WHERE id=:run AND user_id=:owner AND mode='PAPER' FOR UPDATE""",
            params,
        )
    ).one_or_none()
    before = document_payload(evaluated.state_before)
    after = document_payload(evaluated.decision.state)
    if (
        run is None
        or run.status != BotStatus.RUNNING
        or run.revision != evaluated.run_revision
        or run.strategy_version != evaluated.strategy_version
        or run.configuration_version != evaluated.configuration_version
        or run.state_version != evaluated.decision.state.version
        or before != json.loads(run.strategy_state)
    ):
        raise BotDecisionConflictError("run version or checkpoint changed")

    intents = evaluated.decision.intents
    if any(
        intent.origin is not OrderOrigin.BOT
        or intent.scope.owner_id != checked.user_id
        or intent.scope.mode is not TradingMode.PAPER
        or intent.scope.episode_id != run.episode_id
        for intent in intents
    ):
        raise BotDecisionConflictError("intent scope does not match the run")

    # Roll back all writes even if the caller catches a domain exception.
    await checked.execute("SAVEPOINT bot_decision")
    try:
        await checked.execute(
            """INSERT INTO bot_decisions(id,run_id,user_id,mode,input_identity,run_revision,
                  strategy_version,configuration_version,state_before,state_after,input_provenance)
                VALUES(:id,:run,:owner,'PAPER',:input,:rev,:strategy,:config,
                       CAST(:before AS jsonb),CAST(:after AS jsonb),CAST(:provenance AS jsonb))""",
            {
                **params,
                "rev": evaluated.run_revision,
                "strategy": evaluated.strategy_version,
                "config": evaluated.configuration_version,
                "before": json.dumps(before),
                "after": json.dumps(after),
                "provenance": None
                if evaluated.input_provenance is None
                else json.dumps(evaluated.input_provenance),
            },
        )
        brackets = dict(evaluated.decision.brackets)
        for ordinal, intent in enumerate(intents):
            command_id = await admit(checked, run.wallet_id, intent)
            bracket = brackets.get(intent.order_id)
            levels = (
                None
                if bracket is None
                else json.dumps(
                    {
                        "tp": None
                        if bracket.take_profit is None
                        else bracket.take_profit.as_parts()["amount"],
                        "sl": None
                        if bracket.stop_loss is None
                        else bracket.stop_loss.as_parts()["amount"],
                    }
                )
            )
            await checked.execute(
                """INSERT INTO bot_order_links(decision_id,run_id,user_id,mode,episode_id,
                        ordinal,command_id,order_id,bracket)
                    VALUES(:id,:run,:owner,'PAPER',:episode,:ordinal,:command,:order,
                           CAST(:levels AS jsonb))""",
                {
                    **params,
                    "episode": run.episode_id,
                    "ordinal": ordinal,
                    "command": command_id,
                    "order": intent.order_id,
                    "levels": levels,
                },
            )
        await checked.execute(
            """UPDATE bot_runs SET revision=revision+1,strategy_state=CAST(:after AS jsonb),
                source_progress=jsonb_build_object('input_identity',CAST(:input AS text))
                WHERE id=:run AND user_id=:owner""",
            {**params, "after": json.dumps(after)},
        )
        await checked.execute(
            """INSERT INTO bot_run_events(id,run_id,user_id,mode,revision,event,details)
                VALUES(:id,:run,:owner,'PAPER',:revision,'DECISION_RECORDED',
                jsonb_build_object('decision_id',CAST(:id AS uuid)))""",
            {**params, "revision": evaluated.run_revision + 1},
        )
    except Exception:
        await checked.execute("ROLLBACK TO SAVEPOINT bot_decision")
        raise
    finally:
        await checked.execute("RELEASE SAVEPOINT bot_decision")
    return evaluated.decision_id
