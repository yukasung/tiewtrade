"""F-21 authority changes between a valid BUY, decision commit and Paper admission."""

import asyncio
from contextlib import AbstractAsyncContextManager
from dataclasses import replace
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market.test_bot_catalog import enable_catalog
from tests.infra.execution_market.test_bot_decisions import (
    bot_bracket_protocol as bot_bracket_protocol,
)
from tests.infra.execution_market.test_bot_indicator_inputs import seed_prepared
from tests.infra.execution_market.test_strategy_tail_inputs import restored_run, seed_armed_buy
from tests.infra.indicators.test_source import active as active
from tests.infra.risk_limits.test_execution import Runtime, drive, runtime
from tests.infra.risk_limits.test_requests import submission
from tests.infra.risk_limits.test_worker import claim
from tiewtrade.core.market_data import Timeframe, advance
from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.orders import TradingMode
from tiewtrade.core.trading_stops import StopAction
from tiewtrade.infra.bots.candle_sources import CandleSourceState, candle_source_state
from tiewtrade.infra.bots.decisions import EvaluatedDecision
from tiewtrade.infra.bots.evaluation import (
    PreparedQuote,
    QuoteEvaluation,
    evaluate_published_quote,
    pause_missing_inputs,
)
from tiewtrade.infra.bots.inputs import IndicatorInputs
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.db.session import UserSession, market_data_session
from tiewtrade.infra.indicators.prepared import proof_valid
from tiewtrade.infra.indicators.source import begin_source_write
from tiewtrade.infra.market_data.realtime_storage import read_snapshot, set_connected
from tiewtrade.infra.paper_orders.dispatch import DueOrder, claim_order
from tiewtrade.infra.paper_wallet import get_wallet
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot
from tiewtrade.infra.platform import CatalogReason, request_remove
from tiewtrade.infra.risk_limits.records import RiskAction
from tiewtrade.infra.risk_limits.requests import submit_request
from tiewtrade.infra.risk_limits.storage import process_request
from tiewtrade.infra.trading_stops import submit_request as submit_stop
from tiewtrade.services.engine import bot

pytestmark = pytest.mark.usefixtures("internal_database", "active", "bot_bracket_protocol")


async def verify_queued_result(
    engine: AsyncEngine,
    owner: UUID,
    command: UUID,
    wallet: PaperWalletSnapshot,
    source: Runtime,
    *,
    should_fill: bool,
) -> None:
    await drive(engine, owner, command)
    if should_fill:
        await asyncio.sleep(0.12)
        await source.next_book()
        await drive(engine, owner, command)
    async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
        outcome = (
            await session.execute(
                """SELECT r.state, d.state AS dispatch,d.next_attempt_at
               FROM paper_order_command_results r JOIN paper_order_dispatch d USING(command_id)"""
            )
        ).one()
        assert outcome.dispatch == "TERMINAL"
        assert (
            await claim_order(
                session, DueOrder(command, owner, outcome.next_attempt_at), worker="replay"
            )
            is None
        )
        after = await get_wallet(session, include_reset_readiness=False)
        assert after is not None
        if should_fill:
            assert outcome.state == "SUCCEEDED"
            assert (
                await session.execute("SELECT status FROM paper_order_projections")
            ).scalar_one() == "FILLED"
            position = (
                await session.execute(
                    "SELECT held_quantity,total_cost FROM paper_position_projections"
                )
            ).one()
            assert Quantity.of(position.held_quantity, "BTC") > Quantity.of(0, "BTC")
            assert after.balance == wallet.balance - Money.of(position.total_cost, "USDT")
            assert (
                await session.execute("SELECT count(*) FROM paper_position_events")
            ).scalar_one() == 1
        else:
            assert outcome.state == "REJECTED"
            assert after.balance == wallet.balance and after.revision == wallet.revision
            counts = (
                await session.execute("""SELECT (SELECT count(*) FROM paper_orders),
                (SELECT count(*) FROM paper_reservations),
                (SELECT count(*) FROM paper_position_events)""")
            ).one()
            assert tuple(counts) == (0, 0, 0)


AUTHORITY_CHANGES = (
    "unchanged",
    "quote",
    "candle",
    "catalog",
    "risk",
    "worker",
    "generation",
    "numeric_failure",
    "rollout",
    "run",
    "stop",
)


@pytest.mark.parametrize(
    ("stage", "change"),
    [(stage, change) for stage in ("commit", "queued") for change in AUTHORITY_CHANGES]
    + [
        ("queued", change)
        for change in (
            "expired_lease",
            "lease_expires_during_read",
            "tail",
            "corrected_tail",
            "source_recovery",
            "feed_recovery",
            "legacy",
        )
    ],
)
async def test_buy_rechecks_current_authority(
    stage: str,
    change: str,
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000", account_use="BOT"
    ) as source:
        if change == "catalog":
            await enable_catalog(api_engine, engine_engine, migrator_engine, owner)
        run, worker, candle, history = await restored_run(
            api_engine, engine_engine, migrator_engine, owner, wallet, source
        )
        await seed_armed_buy(engine_engine, migrator_engine, owner, candle.end_at, history)
        if change in {"tail", "corrected_tail"}:
            await seed_prepared(
                migrator_engine,
                251,
                advance(candle.end_at, Timeframe.M1, -1),
                closes=(*history, Money.of(310, "USDT")),
            )
        registry = bot.StrategyRegistry(enable_f21=True)

        def engine_session() -> AbstractAsyncContextManager[UserSession]:
            return user_session(engine_engine, owner, role=DatabaseRole.ENGINE)

        async def evaluate() -> UUID | None:
            return await bot.run_bot_quote(
                engine=engine_engine, owner=owner, run_id=run, registry=registry, worker_id=worker
            )

        async with engine_session() as session:
            original = (await session.execute("SELECT strategy_state FROM bot_runs")).scalar_one()
        buy_ids = []

        async def change_authority(evaluation: QuoteEvaluation, inputs: IndicatorInputs) -> None:
            if change == "quote":
                # Two trades may share exchange time. Keep the same closed candle
                # even if the database clock crosses a minute during evaluation.
                await source.price("311", trade_time=evaluation.prepared.snapshot.observed_at)
            elif change == "source_recovery":
                async with market_data_session(source.market) as market:
                    await market.execute(
                        "UPDATE market_candle_demand SET status='FAILED',"
                        "failure_code='SOURCE_FAILURE'"
                    )
                async with market_data_session(source.market) as market:
                    await market.execute(
                        "UPDATE market_candle_demand SET status='COMPLETE',failure_code=NULL"
                    )
            elif change == "feed_recovery":
                async with market_data_session(source.market) as market:
                    feed = (await read_snapshot(market)).feed
                    assert feed is not None
                    disconnected = await set_connected(market, feed, False)
                    await set_connected(market, disconnected, True)
                await source.price("310", trade_time=evaluation.prepared.snapshot.observed_at)
            elif change in {"candle", "corrected_tail"}:
                async with market_data_session(source.market) as market:
                    await begin_source_write(market)
                    changed = await market.execute(
                        """UPDATE market_candles SET high=400
                           WHERE base='BTC' AND quote='USDT' AND timeframe='1m'
                             AND open_at=:at RETURNING open_at""",
                        {"at": inputs.open_at},
                    )
                    assert changed.scalar_one() == inputs.open_at
            elif change == "generation":
                await seed_prepared(
                    migrator_engine,
                    252,
                    candle.end_at,
                    closes=(*history, Money.of(310, "USDT"), Money.of(355, "USDT")),
                )
                old = inputs.generation
                async with engine_session() as other:
                    head = (
                        await other.execute("SELECT generation_id FROM indicator_ready_heads")
                    ).scalar_one()
                    assert head != old["id"]
                    now = (await other.execute("SELECT clock_timestamp()")).scalar_one()
                    assert await proof_valid(other, old, now)
            elif change == "numeric_failure":
                # F-11 retains failure metadata even after the failed manifest is gone.
                async with migrator_engine.begin() as connection:
                    await connection.execute(
                        text("""UPDATE indicator_build_jobs SET
                        generation_sequence=generation_sequence+1,failed_calculation_key='{}',
                        status='FAILED_NUMERIC' WHERE base='BTC' AND timeframe='1m'""")
                    )
                async with engine_session() as other:
                    failed = (
                        await other.execute(
                            "SELECT candidate_sequence FROM indicator_numeric_failures"
                        )
                    ).scalar_one()
                    assert failed > inputs.generation["candidate_sequence"]
            elif change == "rollout":
                async with migrator_engine.begin() as connection:
                    epoch: UUID = (
                        await connection.execute(
                            text(
                                "UPDATE indicator_rollout_control "
                                "SET rollout_epoch=gen_random_uuid() "
                                "WHERE id=1 AND mode='PREPARED' RETURNING rollout_epoch"
                            )
                        )
                    ).scalar_one()
                    assert epoch != inputs.rollout_epoch
            elif change == "run":
                async with engine_session() as other:
                    current_revision = (
                        await other.execute("SELECT revision FROM bot_runs")
                    ).scalar_one()
                    await pause_missing_inputs(
                        other,
                        replace(evaluation.prepared, run_revision=current_revision),
                        "INDICATOR_NOT_READY",
                    )
                    row = (await other.execute("SELECT status,revision FROM bot_runs")).one()
                    assert row.status == "PAUSED" and row.revision == current_revision + 1
            elif change == "stop":
                async with user_session(api_engine, owner) as api:
                    await submit_stop(
                        api,
                        mode=TradingMode.PAPER,
                        action=StopAction.STOP,
                        key=uuid4(),
                        reason_code="USER_STOP",
                    )
            elif change == "catalog":
                async with user_session(api_engine, owner) as admin:
                    removed = await request_remove(
                        admin,
                        command_id=uuid4(),
                        idempotency_key="remove-before-f21-commit",
                        base="BTC",
                        quote="USDT",
                        expected_revision=2,
                        reason=CatalogReason.RISK_REVIEW,
                    )
                    assert removed.revision == 3
            elif change == "risk":
                decrease = replace(
                    submission(owner, wallet),
                    action=RiskAction.DECREASE,
                    expected_revision=1,
                    amount=Money.of(500, "USDT"),
                )
                async with user_session(api_engine, owner) as api:
                    receipt = await submit_request(api, decrease)
                pending = await claim(engine_engine, owner, receipt)
                async with engine_session() as other:
                    await process_request(other, pending)
                    assert (
                        await other.execute("SELECT revision FROM risk_limit_settings")
                    ).scalar_one() == 2
            elif change in {"worker", "expired_lease"}:
                async with engine_session() as other:
                    await other.execute(
                        "UPDATE bot_run_leases SET lease_until=clock_timestamp()-interval "
                        "'1 second' WHERE run_id=:run",
                        {"run": run},
                    )
                if change == "expired_lease":
                    return
                async with engine_session() as other:
                    replacement = await evaluate_published_quote(
                        other,
                        run,
                        worker_id=uuid4(),
                        resolve=registry.implementation,
                        resolve_configuration=registry.configured_implementation,
                    )
                    if stage == "queued":
                        assert replacement is None
                        assert evaluation.prepared.lease_generation is not None
                        assert (
                            await other.execute("SELECT generation FROM bot_run_leases")
                        ).scalar_one() == evaluation.prepared.lease_generation + 1
                        return
                    assert isinstance(replacement, PreparedQuote)
                    assert evaluation.prepared.lease_generation is not None
                    assert replacement.lease_generation == evaluation.prepared.lease_generation + 1

        captured: list[tuple[QuoteEvaluation, IndicatorInputs]] = []

        async def commit_after_change(
            session: UserSession, run_id: UUID, **kwargs: Any
        ) -> UUID | PreparedQuote | None:
            evaluation = kwargs.get("evaluation")
            if evaluation is not None:
                assert evaluation.decision is not None
                (intent,) = evaluation.decision.intents
                assert intent.side.value == "BUY"
                if change in {"tail", "corrected_tail"}:
                    assert kwargs["indicator_inputs"].tail is not None
                buy_ids.append(intent.order_id)
                captured.append((evaluation, kwargs["indicator_inputs"]))
                if stage == "commit":
                    await change_authority(*captured[0])
            return await evaluate_published_quote(session, run_id, **kwargs)

        with monkeypatch.context() as patch:
            if change == "legacy":
                # Write the previous production provenance format through the real decision writer.
                from tiewtrade.infra.bots import evaluation as evaluation_module
                from tiewtrade.infra.bots.decisions import record_paper_decision

                async def legacy_record(session: UserSession, decision: EvaluatedDecision) -> UUID:
                    assert decision.input_provenance is not None
                    old = dict(decision.input_provenance)
                    for key in (
                        "indicator_generation",
                        "rollout_epoch",
                        "source_fence",
                        "risk_revision",
                        "lease_generation",
                    ):
                        del old[key]
                    return await record_paper_decision(
                        session, replace(decision, input_provenance=old)
                    )

                patch.setattr(evaluation_module, "record_paper_decision", legacy_record)
            patch.setattr(bot, "evaluate_published_quote", commit_after_change)
            result = await evaluate()
        assert len(buy_ids) == 1
        if stage == "queued":
            assert result is not None
            async with engine_session() as session:
                command = (
                    await session.execute("SELECT command_id FROM bot_order_links")
                ).scalar_one()
                assert (
                    await session.execute("SELECT count(*) FROM paper_order_command_results")
                ).scalar_one() == 0
                queued_wallet = await get_wallet(session, include_reset_readiness=False)
                assert queued_wallet is not None and queued_wallet.balance == wallet.balance
            await change_authority(*captured[0])
            delayed_read = False
            if change == "lease_expires_during_read":
                from tiewtrade.infra.bots import authority

                read_source = candle_source_state

                async def delayed_source(
                    session: UserSession, *args: Any, **kwargs: Any
                ) -> CandleSourceState:
                    nonlocal delayed_read
                    assert (
                        await session.execute(
                            "SELECT lease_until>clock_timestamp() FROM bot_run_leases "
                            "WHERE run_id=:run",
                            {"run": run},
                        )
                    ).scalar_one()
                    state = await read_source(session, *args, **kwargs)
                    await session.execute(
                        "SELECT pg_sleep(greatest(0,extract(epoch FROM "
                        "lease_until-clock_timestamp()))+0.01) "
                        "FROM bot_run_leases WHERE run_id=:run",
                        {"run": run},
                    )
                    delayed_read = True
                    return state

                async with engine_session() as session:
                    await session.execute(
                        "UPDATE bot_run_leases SET "
                        "lease_until=clock_timestamp()+interval '1 second' "
                        "WHERE run_id=:run",
                        {"run": run},
                    )
                monkeypatch.setattr(authority, "candle_source_state", delayed_source)
            await verify_queued_result(
                engine_engine,
                owner,
                command,
                queued_wallet,
                source,
                should_fill=change in {"unchanged", "quote", "tail"},
            )
            if change == "lease_expires_during_read":
                assert delayed_read
            if change == "risk":
                # Consume the rejection, then deliver the old evaluated BUY after
                # this newer decision and replay the same signal candle.
                feedback_id = await evaluate()
                assert feedback_id is not None and feedback_id != result
                old, inputs = captured[0]
                async with engine_session() as session:
                    stale = await evaluate_published_quote(
                        session,
                        run,
                        worker_id=worker,
                        resolve=registry.implementation,
                        resolve_configuration=registry.configured_implementation,
                        evaluation=old,
                        indicator_inputs=inputs,
                    )
                    assert stale is None
                await evaluate()
                async with engine_session() as session:
                    assert (
                        await session.execute("SELECT id FROM paper_order_commands")
                    ).scalar_one() == command
            return
        if change != "unchanged":
            assert result is None
            async with engine_session() as session:
                assert (
                    await session.execute("SELECT strategy_state FROM bot_runs")
                ).scalar_one() == original
                after = await get_wallet(session, include_reset_readiness=False)
                assert after is not None and (after.balance, after.revision) == (
                    wallet.balance,
                    wallet.revision,
                )
                counts = (
                    await session.execute(
                        """SELECT (SELECT count(*) FROM bot_decisions),
                    (SELECT count(*) FROM bot_order_links),
                    (SELECT count(*) FROM paper_order_commands),
                    (SELECT count(*) FROM paper_orders),
                    (SELECT count(*) FROM paper_reservations),
                    (SELECT count(*) FROM paper_position_events),
                    (SELECT count(*) FROM bot_strategy_baskets)"""
                    )
                ).one()
                assert tuple(counts) == (0,) * len(counts)
            if change in {"candle", "rollout", "numeric_failure", "run"}:
                async with engine_session() as session:
                    assert (
                        await session.execute("SELECT status FROM bot_runs")
                    ).scalar_one() == "PAUSED"
                return
            if change in {"catalog", "worker", "stop"}:
                assert await evaluate() is None
                return
            result = await evaluate()
        assert result is not None
        await evaluate()
        async with engine_session() as session:
            assert (
                await session.execute("SELECT order_id FROM bot_order_links")
            ).scalar_one() == buy_ids[0]
            assert (await session.execute("SELECT id FROM bot_decisions")).scalar_one() == result
            assert (
                await session.execute("SELECT count(*) FROM paper_order_commands")
            ).scalar_one() == 1
