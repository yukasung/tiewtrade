"""Persist a real decision for synthetic BOT orders in Paper safety tests."""

import json
from uuid import UUID, uuid4

from tiewtrade.core.orders import OrderIntent, OrderOrigin, TradingMode
from tiewtrade.core.strategies import StrategyDecision, StrategyDocument, document_payload
from tiewtrade.infra.bots.decisions import EvaluatedDecision, record_paper_decision
from tiewtrade.infra.db.session import UserSession
from tiewtrade.infra.paper_orders.dispatch import OrderCommand, get_order_command, submit_order
from tiewtrade.infra.risk_limits.dispatch import lock_risk_owner
from tiewtrade.infra.trading_stops.storage import global_shared_lock


async def submit_fixture_bot_order(
    session: UserSession, *, wallet_id: UUID, intent: OrderIntent
) -> OrderCommand:
    if intent.origin is not OrderOrigin.BOT or intent.scope.owner_id != session.user_id:
        raise ValueError("BOT fixture requires an owner-scoped intent")
    state = StrategyDocument(1, ())
    await global_shared_lock(session)
    await lock_risk_owner(session, TradingMode.PAPER)
    await session.execute(
        """INSERT INTO bot_runs(id,user_id,mode,wallet_id,episode_id,strategy_name,
          strategy_version,configuration_version,state_version,configuration,strategy_state,status)
        VALUES(:run,:owner,'PAPER',:wallet,:episode,'stop_fixture',1,1,1,
          CAST(:state AS jsonb),CAST(:state AS jsonb),'RUNNING')
        ON CONFLICT(user_id,mode) WHERE status<>'RETIRED' DO NOTHING""",
        {
            "run": uuid4(),
            "owner": session.user_id,
            "wallet": wallet_id,
            "episode": intent.scope.episode_id,
            "state": json.dumps(document_payload(state)),
        },
    )
    run = (
        await session.execute(
            """SELECT id,revision FROM bot_runs WHERE user_id=:owner AND mode='PAPER'
              AND episode_id=:episode AND strategy_name='stop_fixture' AND status='RUNNING'""",
            {"owner": session.user_id, "episode": intent.scope.episode_id},
        )
    ).one()

    async def admit(checked: UserSession, wallet: UUID, order: OrderIntent) -> UUID:
        command = await submit_order(checked, wallet_id=wallet, intent=order)
        return command.command_id

    decision_id = await record_paper_decision(
        session,
        EvaluatedDecision(
            run.id,
            uuid4(),
            str(intent.idempotency_key),
            run.revision,
            1,
            1,
            state,
            StrategyDecision(state, (intent,)),
        ),
        admit=admit,
    )
    command_id = (
        await session.execute(
            "SELECT command_id FROM bot_order_links WHERE decision_id=:id AND ordinal=0",
            {"id": decision_id},
        )
    ).scalar_one()
    command = await get_order_command(session, command_id)
    assert command is not None
    return command
