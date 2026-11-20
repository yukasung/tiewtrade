"""Barrier-controlled F-19/replacement/stale-decision races on real owner locks."""

import asyncio
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market.test_bot_review_safety import DOC, registry, seed_input_run
from tests.infra.execution_market.test_dispatch import intent
from tests.infra.risk_limits.test_execution import drive, runtime
from tests.infra.risk_limits.test_requests import submission
from tests.infra.risk_limits.test_worker import claim as claim_risk
from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.orders import BaseSize, OrderOrigin, TradingMode
from tiewtrade.core.positions import ExecutionSide
from tiewtrade.core.risk_limits import RiskEvaluation, RiskReason
from tiewtrade.core.strategies import StrategyDecision
from tiewtrade.core.trading_stops import StopAction
from tiewtrade.infra.bots.claims import BotRequestClaim, BotRequestHint
from tiewtrade.infra.bots.claims import claim_control as original_claim
from tiewtrade.infra.bots.decisions import (
    BotDecisionConflictError,
    EvaluatedDecision,
    record_paper_decision,
)
from tiewtrade.infra.bots.evaluation import PreparedQuote, QuoteEvaluation, evaluate_published_quote
from tiewtrade.infra.bots.requests import receipt_by_key, submit_start
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.db.session import UserSession
from tiewtrade.infra.paper_orders.dispatch import DueOrder, claim_order, submit_order
from tiewtrade.infra.paper_orders.worker import process_claimed_order
from tiewtrade.infra.paper_wallet import get_wallet
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot
from tiewtrade.infra.risk_limits.monitor import persist_evaluation
from tiewtrade.infra.risk_limits.policy import TransactionalRiskPolicy
from tiewtrade.infra.risk_limits.records import RiskAction
from tiewtrade.infra.risk_limits.requests import submit_request as submit_risk
from tiewtrade.infra.risk_limits.storage import process_request, read_setting
from tiewtrade.infra.trading_stops import read_status, submit_request
from tiewtrade.services.engine import bot as worker
from tiewtrade.services.engine.bot_replacement import clear_replacement_stop as original_clear
from tiewtrade.services.engine.kill_switch import run_stop_request_round
from tiewtrade.services.engine.risk_limit import run_risk_stop_round

pytestmark = pytest.mark.usefixtures("internal_database")


@pytest.mark.parametrize(
    "replacement_first", [False, True], ids=["stop-first", "replacement-first"]
)
async def test_replacement_stop_race_and_old_decision_cannot_create_orders(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    replacement_first: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable = registry()
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000", account_use="BOT"
    ):
        old = await seed_input_run(engine_engine, owner, wallet)
        stale = EvaluatedDecision(
            old,
            uuid4(),
            "stale-before-stop",
            1,
            1,
            1,
            DOC,
            StrategyDecision(
                DOC, (replace(intent(owner, wallet.episode_id), origin=OrderOrigin.BOT),)
            ),
        )
        async with user_session(api_engine, owner) as session:
            await submit_request(
                session,
                mode=TradingMode.PAPER,
                action=StopAction.STOP,
                key=uuid4(),
                reason_code="USER_STOP",
            )
        await run_stop_request_round(engine=engine_engine, scan_engine=scan_engine)
        await run_risk_stop_round(engine=engine_engine, scan_engine=scan_engine)
        async with user_session(api_engine, owner) as session:
            status = await read_status(session, TradingMode.PAPER)
            assert status.resume_ready
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
                        "run_revision": 2,
                        "stop_id": str(status.stop_id),
                        "stop_revision": status.revision,
                        "summary_revision": status.summary_revision,
                        "reconciliation_revision": status.reconciliation_revision,
                    },
                },
            )
        held, entered, release = asyncio.Event(), asyncio.Event(), asyncio.Event()

        async def new_stop() -> None:
            async with user_session(api_engine, owner) as session:
                entered.set()
                await submit_request(
                    session,
                    mode=TradingMode.PAPER,
                    action=StopAction.STOP,
                    key=uuid4(),
                    reason_code="USER_STOP",
                )
                if not replacement_first:
                    held.set()
                    await release.wait()

        async def control() -> None:
            await worker.run_bot_control_round(
                engine=engine_engine, scan_engine=scan_engine, registry=executable
            )

        async def clear(
            session: UserSession, claim: BotRequestClaim, proof: dict[str, object]
        ) -> None:
            held.set()
            await release.wait()
            await original_clear(session, claim, proof)

        async def claim(session: UserSession, hint: BotRequestHint) -> BotRequestClaim | None:
            entered.set()
            return await original_claim(session, hint)

        if replacement_first:
            monkeypatch.setattr(worker, "clear_replacement_stop", clear)
            first = asyncio.create_task(control())
            await asyncio.wait_for(held.wait(), 3)
            second = asyncio.create_task(new_stop())
        else:
            monkeypatch.setattr(worker, "claim_control", claim)
            first = asyncio.create_task(new_stop())
            await asyncio.wait_for(held.wait(), 3)
            entered.clear()
            second = asyncio.create_task(control())
        try:
            await asyncio.wait_for(entered.wait(), 3)
            assert not second.done()
            release.set()
            await asyncio.wait_for(asyncio.gather(first, second), 5)
        finally:
            release.set()
            for task in (first, second):
                if not task.done():
                    task.cancel()
            await asyncio.gather(first, second, return_exceptions=True)
        await run_stop_request_round(engine=engine_engine, scan_engine=scan_engine)
        await run_risk_stop_round(engine=engine_engine, scan_engine=scan_engine)
        async with user_session(api_engine, owner) as session:
            receipt = await receipt_by_key(session, TradingMode.PAPER, key)
            assert receipt is not None and not receipt.pending
            if replacement_first:
                assert receipt.run_id is not None and receipt.run_id != old
            else:
                assert receipt.failure_code == "BOT_REPLACEMENT_NOT_READY"
            stopped = await read_status(session, TradingMode.PAPER)
            assert stopped.resume_ready and stopped.stop_id is not None
            await submit_request(
                session,
                mode=TradingMode.PAPER,
                action=StopAction.RESUME,
                key=uuid4(),
                reason_code="USER_RESUME",
                expected_stop_id=stopped.stop_id,
                expected_revision=stopped.revision,
                expected_summary_revision=stopped.summary_revision,
                expected_reconciliation_revision=stopped.reconciliation_revision,
            )
        await run_stop_request_round(engine=engine_engine, scan_engine=scan_engine)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            # The latest stop was acknowledged. Rejection now proves the old run
            # revision/identity fence rather than merely an active stop check.
            with pytest.raises(BotDecisionConflictError):
                await record_paper_decision(session, stale)
            states = {
                row.id: row.status
                for row in (await session.execute("SELECT id,status FROM bot_runs")).all()
            }
            if replacement_first:
                assert states[old] == "RETIRED"
                assert receipt.run_id is not None and states[receipt.run_id] == "RECOVERING"
            else:
                assert states == {old: "RECOVERING"}
            for table in (
                "bot_decisions",
                "paper_order_commands",
                "paper_orders",
                "paper_reservations",
                "paper_position_events",
            ):
                assert (await session.execute(f"SELECT count(*) FROM {table}")).scalar_one() == 0
            after = await get_wallet(session)
            assert after is not None and after.balance == wallet.balance


async def test_replacement_waits_for_real_reducing_fill_and_rejects_stale_acknowledgement(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000", account_use="BOT"
    ) as sources:
        run = await seed_input_run(engine_engine, owner, wallet)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await record_paper_decision(
                session,
                EvaluatedDecision(
                    run,
                    uuid4(),
                    "entry",
                    1,
                    1,
                    1,
                    DOC,
                    StrategyDecision(
                        DOC, (replace(intent(owner, wallet.episode_id), origin=OrderOrigin.BOT),)
                    ),
                ),
            )
            entry = (await session.execute("SELECT command_id FROM bot_order_links")).scalar_one()
        await drive(engine_engine, owner, entry)
        await asyncio.sleep(0.12)
        await sources.next_book()
        await drive(engine_engine, owner, entry)
        async with user_session(api_engine, owner) as session:
            await submit_request(
                session,
                mode=TradingMode.PAPER,
                action=StopAction.STOP,
                key=uuid4(),
                reason_code="USER_STOP",
            )
        await run_stop_request_round(engine=engine_engine, scan_engine=scan_engine)
        await run_risk_stop_round(engine=engine_engine, scan_engine=scan_engine)
        async with user_session(api_engine, owner) as session:
            stopped = await read_status(session, TradingMode.PAPER)
            assert stopped.resume_ready
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            revision = (await session.execute("SELECT revision FROM bot_runs")).scalar_one()
            assert Quantity.of(
                (
                    await session.execute("SELECT held_quantity FROM paper_position_projections")
                ).scalar_one(),
                "BTC",
            ) == Quantity.of("0.999", "BTC")
            reduction_intent = replace(
                intent(owner, wallet.episode_id),
                side=ExecutionSide.SELL,
                size=BaseSize(Quantity.of("0.999", "BTC")),
            )
            reduction = await submit_order(
                session,
                wallet_id=wallet.wallet_id,
                intent=reduction_intent,
            )
        await drive(engine_engine, owner, reduction.command_id)
        await asyncio.sleep(0.12)
        await sources.next_book()
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            due = (
                await session.execute(
                    "UPDATE paper_order_dispatch SET next_attempt_at=clock_timestamp() "
                    "WHERE command_id=:id RETURNING next_attempt_at",
                    {"id": reduction.command_id},
                )
            ).scalar_one()
            token = await claim_order(
                session, DueOrder(reduction.command_id, owner, due), worker="fill-barrier"
            )
        assert token is not None
        held, entered, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
        key = uuid4()

        async def fill() -> None:
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                await process_claimed_order(session, token, policy=TransactionalRiskPolicy())
                assert (
                    await session.execute(
                        "SELECT status FROM paper_order_projections WHERE order_id=:id",
                        {"id": reduction_intent.order_id},
                    )
                ).scalar_one() == "FILLED"
                held.set()
                await release.wait()

        async def replacement() -> None:
            async with user_session(api_engine, owner) as session:
                entered.set()
                await submit_start(
                    session,
                    mode=TradingMode.PAPER,
                    request_id=uuid4(),
                    key=key,
                    payload={
                        "strategy_config_ref": "fixture-v1",
                        "replacement": {
                            "run_id": str(run),
                            "run_revision": revision,
                            "stop_id": str(stopped.stop_id),
                            "stop_revision": stopped.revision,
                            "summary_revision": stopped.summary_revision,
                            "reconciliation_revision": stopped.reconciliation_revision,
                        },
                    },
                )

        first = asyncio.create_task(fill())
        second = None
        try:
            await asyncio.wait_for(held.wait(), 5)
            second = asyncio.create_task(replacement())
            await asyncio.wait_for(entered.wait(), 3)
            assert not second.done()
            release.set()
            await asyncio.wait_for(asyncio.gather(first, second), 5)
        finally:
            release.set()
            tasks = [first] if second is None else [first, second]
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        await worker.run_bot_control_round(
            engine=engine_engine, scan_engine=scan_engine, registry=registry()
        )
        async with user_session(api_engine, owner) as session:
            result = await receipt_by_key(session, TradingMode.PAPER, key)
            assert result is not None and result.failure_code == "BOT_REPLACEMENT_NOT_READY"
            assert (await read_status(session, TradingMode.PAPER)).stop_id == stopped.stop_id
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            assert (await session.execute("SELECT status FROM bot_runs")).scalar_one() == "STOPPED"
            assert (
                await session.execute("SELECT count(*) FROM paper_position_events")
            ).scalar_one() == 2
            assert (
                await session.execute("SELECT held_quantity FROM paper_position_projections")
            ).scalar_one() == 0
            assert (
                await session.execute("SELECT count(*) FROM paper_order_commands")
            ).scalar_one() == 2
            assert (
                await session.execute(
                    "SELECT count(*) FROM paper_reservations "
                    "WHERE quote_reserved<>0 OR base_reserved<>0"
                )
            ).scalar_one() == 0
            # Buy 100 USDT -> 0.999 BTC after base fee. Sell at 99:
            # 98.901 gross - 0.098901 quote fee = 98.802099 USDT.
            after = await get_wallet(session)
            assert after is not None and after.balance == wallet.balance - Money.of(
                "1.197901", "USDT"
            )


async def test_loss_hit_then_real_reset_cannot_commit_pre_breach_bot_output(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    executable = registry()
    worker_id = uuid4()
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000", account_use="BOT"
    ):
        run = await seed_input_run(engine_engine, owner, wallet)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            prepared = await evaluate_published_quote(
                session, run, resolve=executable.implementation, worker_id=worker_id
            )
            assert isinstance(prepared, PreparedQuote)
        output = StrategyDecision(
            DOC, (replace(intent(owner, wallet.episode_id), origin=OrderOrigin.BOT),)
        )
        # The financial evaluation commits between preparation and the final
        # decision transaction, as in a monitor on another engine instance.
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            setting = await read_setting(session, submission(owner, wallet).scope)
            await persist_evaluation(
                session,
                setting,
                RiskEvaluation(
                    setting.scope,
                    setting.revision,
                    2,
                    datetime.now(UTC),
                    RiskReason.BREACHED,
                    Money.of(1000, "USDT"),
                    True,
                    True,
                ),
                watermark=0,
                replay_pending=False,
            )
        await run_risk_stop_round(engine=engine_engine, scan_engine=scan_engine)
        await run_stop_request_round(engine=engine_engine, scan_engine=scan_engine)
        async with user_session(api_engine, owner) as session:
            stopped = await read_status(session, TradingMode.PAPER)
            assert stopped.stop_id is not None
            breached = await read_setting(session, submission(owner, wallet).scope)
            assert breached.latched
            reset = await submit_risk(
                session,
                replace(
                    submission(owner, wallet),
                    action=RiskAction.RESET,
                    expected_revision=breached.revision,
                    amount=None,
                ),
            )
        token = await claim_risk(engine_engine, owner, reset)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await process_request(session, token)
            setting = await read_setting(session, reset.submission.scope)
            assert setting.revision == breached.revision + 1 and not setting.latched
            result = await evaluate_published_quote(
                session,
                run,
                resolve=executable.implementation,
                worker_id=worker_id,
                evaluation=QuoteEvaluation(prepared, output),
            )
            assert result is None
            assert (await read_status(session, TradingMode.PAPER)).stop_id == stopped.stop_id
            assert (await session.execute("SELECT status FROM bot_runs")).scalar_one() == "STOPPED"
            for table in (
                "bot_decisions",
                "paper_order_commands",
                "paper_orders",
                "paper_reservations",
                "paper_position_events",
            ):
                assert (await session.execute(f"SELECT count(*) FROM {table}")).scalar_one() == 0
            after = await get_wallet(session)
            assert after is not None and after.balance == wallet.balance
