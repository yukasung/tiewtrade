"""Missing Feature scenarios: proof binding, flat replacement and exposure recovery."""

import asyncio
from collections.abc import AsyncIterator
from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market.test_bot_readiness_recovery import OpeningProbe
from tests.infra.execution_market.test_bot_review_safety import DOC, registry, seed_input_run
from tests.infra.execution_market.test_dispatch import intent
from tests.infra.risk_limits.test_execution import Runtime, drive, runtime
from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.orders import OrderOrigin, QuoteBudget, TradingMode
from tiewtrade.core.realtime_prices import MAX_PRICE_AGE
from tiewtrade.core.strategies import StrategyDecision
from tiewtrade.core.trading_stops import StopAction
from tiewtrade.infra.bots.decisions import EvaluatedDecision, record_paper_decision
from tiewtrade.infra.bots.evaluation import PreparedQuote, QuoteEvaluation, evaluate_published_quote
from tiewtrade.infra.bots.feedback import next_paper_feedback
from tiewtrade.infra.bots.requests import receipt_by_key, submit_start
from tiewtrade.infra.bots.resume_proofs import has_fresh_strategy_proof
from tiewtrade.infra.bots.system_stop import request_system_stop
from tiewtrade.infra.db import DatabaseRole, create_engine_for, user_session
from tiewtrade.infra.paper_orders.initialization import enable_financial_writer
from tiewtrade.infra.paper_orders.storage import increment_wallet_revision
from tiewtrade.infra.paper_wallet import get_wallet
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot
from tiewtrade.infra.risk_limits.dispatch import lock_risk_owner
from tiewtrade.infra.trading_stops import read_status, submit_request
from tiewtrade.infra.users import create_user
from tiewtrade.services.engine.bot import (
    StrategyRegistry,
    prove_bot_strategy_recovery,
    run_bot_control_round,
    run_bot_quote,
)
from tiewtrade.services.engine.kill_switch import run_stop_request_round
from tiewtrade.services.engine.risk_limit import run_risk_stop_round

pytestmark = pytest.mark.usefixtures("internal_database")


@pytest.fixture
async def proven_stop(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> AsyncIterator[tuple[UUID, UUID, Runtime]]:
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000", account_use="BOT"
    ) as sources:
        run, worker = await seed_input_run(engine_engine, owner, wallet), uuid4()
        assert (
            await run_bot_quote(
                engine=engine_engine, owner=owner, run_id=run, registry=registry(), worker_id=worker
            )
            is not None
        )
        assert (
            await run_bot_quote(
                engine=engine_engine,
                owner=owner,
                run_id=run,
                registry=StrategyRegistry(),
                worker_id=worker,
            )
            is None
        )
        await run_stop_request_round(engine=engine_engine, scan_engine=scan_engine)
        await run_risk_stop_round(engine=engine_engine, scan_engine=scan_engine)
        async with user_session(api_engine, owner) as session:
            stopped = await read_status(session, TradingMode.PAPER)
            assert stopped.stop_id is not None and not stopped.resume_ready
        assert (
            await prove_bot_strategy_recovery(
                engine=engine_engine,
                owner=owner,
                run_id=run,
                stop_id=stopped.stop_id,
                registry=registry(),
                worker_id=worker,
            )
            is not None
        )
        async with user_session(api_engine, owner) as session:
            assert (await read_status(session, TradingMode.PAPER)).resume_ready
        yield run, UUID(str(stopped.stop_id)), sources


@pytest.mark.parametrize(
    "changed",
    [
        "stop-id",
        "owner",
        "run-revision",
        "state",
        "wallet",
        "risk",
        "generation",
        "watermark",
        "expiry",
    ],
)
async def test_strategy_proof_is_bound_to_current_owner_stop_and_source_revisions(
    proven_stop: tuple[UUID, UUID, Runtime],
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    changed: str,
) -> None:
    run, stop, sources = proven_stop
    checked_owner = owner
    if changed == "stop-id":
        stop = uuid4()
    elif changed == "owner":
        checked_owner = uuid4()
        await create_user(api_engine, checked_owner)
    elif changed == "watermark":
        await sources.price("101")
    elif changed == "expiry":
        await asyncio.sleep(MAX_PRICE_AGE.total_seconds() + 0.05)
    else:
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await lock_risk_owner(session, TradingMode.PAPER)
            if changed == "run-revision":
                await session.execute("UPDATE bot_runs SET revision=revision+1")
            elif changed == "state":
                await session.execute(
                    """UPDATE bot_runs SET revision=revision+1,
                  strategy_state=CAST(:state AS jsonb)""",
                    {"state": '{"version":1,"fields":[["repaired",true]]}'},
                )
            elif changed == "wallet":
                await enable_financial_writer(session)
                await increment_wallet_revision(session, wallet.wallet_id)
            elif changed == "risk":
                await session.execute("UPDATE risk_limit_settings SET revision=revision+1")
            else:
                await request_system_stop(
                    session, run_id=run, stop_id=uuid4(), reason="STRATEGY_VERSION_UNAVAILABLE"
                )
        if changed == "generation":
            await run_stop_request_round(engine=engine_engine, scan_engine=scan_engine)
    async with user_session(api_engine, checked_owner) as session:
        assert not await has_fresh_strategy_proof(session, stop)
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        assert (await session.execute("SELECT status FROM bot_runs")).scalar_one() == "STOPPED"
        for table in (
            "paper_order_commands",
            "paper_orders",
            "paper_reservations",
            "paper_position_events",
        ):
            assert (await session.execute(f"SELECT count(*) FROM {table}")).scalar_one() == 0
        current = await get_wallet(session)
        assert current is not None and current.balance == wallet.balance


@pytest.mark.parametrize("activity", ["position", "pending-command", "unknown-orders"])
async def test_replacement_refuses_existing_or_unproven_activity_and_preserves_original_run(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    activity: str,
) -> None:
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000", account_use="BOT"
    ) as sources:
        old = await seed_input_run(engine_engine, owner, wallet)
        if activity in ("position", "pending-command"):
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                await record_paper_decision(
                    session,
                    EvaluatedDecision(
                        old,
                        uuid4(),
                        "fixture-entry",
                        1,
                        1,
                        1,
                        DOC,
                        StrategyDecision(
                            DOC,
                            (replace(intent(owner, wallet.episode_id), origin=OrderOrigin.BOT),),
                        ),
                    ),
                )
                command = (
                    await session.execute("SELECT command_id FROM bot_order_links")
                ).scalar_one()
            if activity == "position":
                await drive(engine_engine, owner, command)
                await asyncio.sleep(0.12)
                await sources.next_book()
                await drive(engine_engine, owner, command)
        async with user_session(api_engine, owner) as session:
            await submit_request(
                session,
                mode=TradingMode.PAPER,
                action=StopAction.STOP,
                key=uuid4(),
                reason_code="USER_STOP",
            )
        await run_stop_request_round(engine=engine_engine, scan_engine=scan_engine)
        if activity != "pending-command":
            await run_risk_stop_round(engine=engine_engine, scan_engine=scan_engine)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            revision = (await session.execute("SELECT revision FROM bot_runs")).scalar_one()
            if activity == "unknown-orders":
                await session.execute(
                    "UPDATE paper_order_activity SET availability='CONFLICTED',"
                    "failure_code='TEST_SOURCE_UNKNOWN'"
                )
        async with user_session(api_engine, owner) as session:
            stopped = await read_status(session, TradingMode.PAPER)
            key = uuid4()
            await submit_start(
                session,
                mode=TradingMode.PAPER,
                request_id=uuid4(),
                key=key,
                payload={
                    "strategy_config_ref": "fixture-v1",
                    "replacement": {
                        "run_id": str(old),
                        "run_revision": revision,
                        "stop_id": str(stopped.stop_id),
                        "stop_revision": stopped.revision,
                        "summary_revision": stopped.summary_revision,
                        "reconciliation_revision": stopped.reconciliation_revision,
                    },
                },
            )
        await run_bot_control_round(
            engine=engine_engine, scan_engine=scan_engine, registry=registry()
        )
        async with user_session(api_engine, owner) as session:
            result = await receipt_by_key(session, TradingMode.PAPER, key)
            assert result is not None and result.failure_code == "BOT_NOT_READY"
            assert (await read_status(session, TradingMode.PAPER)).stop_id == stopped.stop_id
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            assert (await session.execute("SELECT id,status FROM bot_runs")).one() == (
                old,
                "STOPPED",
            )
            assert (
                await session.execute(
                    "SELECT count(*) FROM bot_run_events WHERE event='RETIRED_FOR_REPLACEMENT'"
                )
            ).scalar_one() == 0
            current = await get_wallet(session)
            assert current is not None and current.balance == (
                wallet.balance - Money.of(100, "USDT") if activity == "position" else wallet.balance
            )
            if activity == "position":
                assert Quantity.of(
                    (
                        await session.execute(
                            "SELECT held_quantity FROM paper_position_projections"
                        )
                    ).scalar_one(),
                    "BTC",
                ) == Quantity.of("0.999", "BTC")


async def test_two_engine_takeover_discards_a_waiting_old_output_and_fills_only_once(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    executable = registry(OpeningProbe())
    prepared_event, release = asyncio.Event(), asyncio.Event()
    second_engine = create_engine_for(DatabaseRole.ENGINE)
    old_worker, new_worker = uuid4(), uuid4()
    try:
        async with runtime(
            api_engine,
            engine_engine,
            migrator_engine,
            owner,
            wallet,
            limit="1000",
            account_use="BOT",
        ) as sources:
            run = await seed_input_run(engine_engine, owner, wallet)

            async def old_writer() -> UUID | PreparedQuote | None:
                async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                    prepared = await evaluate_published_quote(
                        session, run, resolve=executable.implementation, worker_id=old_worker
                    )
                assert isinstance(prepared, PreparedQuote)
                from tiewtrade.core.strategies import evaluate_strategy

                output = evaluate_strategy(
                    prepared.strategy,
                    prepared.snapshot,
                    prepared.configuration,
                    prepared.state,
                    scope=prepared.scope,
                )
                prepared_event.set()
                await release.wait()
                async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                    return await evaluate_published_quote(
                        session,
                        run,
                        resolve=executable.implementation,
                        worker_id=old_worker,
                        evaluation=QuoteEvaluation(prepared, output),
                    )

            old_task = asyncio.create_task(old_writer())
            try:
                await asyncio.wait_for(prepared_event.wait(), 3)
                async with user_session(second_engine, owner, role=DatabaseRole.ENGINE) as session:
                    await session.execute(
                        "UPDATE bot_run_leases "
                        "SET lease_until=clock_timestamp()-interval '1 second'"
                    )
                applied = await run_bot_quote(
                    engine=second_engine,
                    owner=owner,
                    run_id=run,
                    registry=executable,
                    worker_id=new_worker,
                )
                assert applied is not None
                release.set()
                assert await asyncio.wait_for(old_task, 3) is None
            finally:
                release.set()
                if not old_task.done():
                    old_task.cancel()
                await asyncio.gather(old_task, return_exceptions=True)
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                assert (
                    await session.execute("SELECT count(*) FROM bot_decisions")
                ).scalar_one() == 1
                assert (
                    await session.execute("SELECT count(*) FROM paper_order_commands")
                ).scalar_one() == 1
                assert (
                    await session.execute("SELECT generation FROM bot_run_leases")
                ).scalar_one() == 2
                command = (
                    await session.execute("SELECT command_id FROM bot_order_links")
                ).scalar_one()
            await drive(engine_engine, owner, command)
            await asyncio.sleep(0.12)
            await sources.next_book()
            await drive(engine_engine, owner, command)
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                assert (
                    await session.execute("SELECT status FROM paper_order_projections")
                ).scalar_one() == "FILLED"
                assert (
                    await session.execute("SELECT count(*) FROM paper_position_events")
                ).scalar_one() == 1
                assert Quantity.of(
                    (
                        await session.execute(
                            "SELECT held_quantity FROM paper_position_projections"
                        )
                    ).scalar_one(),
                    "BTC",
                ) == Quantity.of("0.24975", "BTC")
                current = await get_wallet(session)
                assert current is not None and current.balance == wallet.balance - Money.of(
                    25, "USDT"
                )
    finally:
        await second_engine.dispose()


async def test_unknown_then_rejected_linked_command_has_one_feedback_and_no_position(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000", account_use="BOT"
    ):
        run = await seed_input_run(engine_engine, owner, wallet)
        entry = replace(
            intent(owner, wallet.episode_id),
            origin=OrderOrigin.BOT,
            size=QuoteBudget(Money.of("0.01", "USDT")),
        )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await record_paper_decision(
                session,
                EvaluatedDecision(
                    run,
                    uuid4(),
                    "rejected-entry",
                    1,
                    1,
                    1,
                    DOC,
                    StrategyDecision(DOC, (entry,)),
                ),
            )
            command = (await session.execute("SELECT command_id FROM bot_order_links")).scalar_one()
            assert await next_paper_feedback(session, run) is None
            assert (
                await session.execute("SELECT count(*) FROM paper_position_events")
            ).scalar_one() == 0
        await drive(engine_engine, owner, command)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            feedback = await next_paper_feedback(session, run)
            assert feedback is not None and feedback.value.status is not None
            assert feedback.value.status.value == "REJECTED"
            assert feedback.value.order_id == entry.order_id and feedback.value.execution is None
            decision = EvaluatedDecision(
                run,
                uuid4(),
                feedback.input_identity,
                2,
                1,
                1,
                DOC,
                StrategyDecision(DOC),
            )
            assert await record_paper_decision(session, decision) == decision.decision_id
            assert await record_paper_decision(session, decision) == decision.decision_id
            assert await next_paper_feedback(session, run) is None
            assert (await session.execute("SELECT count(*) FROM bot_decisions")).scalar_one() == 2
            for table in ("paper_position_events", "paper_reservations"):
                assert (await session.execute(f"SELECT count(*) FROM {table}")).scalar_one() == 0
            current = await get_wallet(session)
            assert current is not None and current.balance == wallet.balance
