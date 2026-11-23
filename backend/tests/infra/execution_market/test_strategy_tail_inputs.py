"""Central F-11 suffix state, normal preparation lag and source recovery fences."""

import asyncio
import json
from dataclasses import replace
from datetime import datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market.test_bot_decisions import (
    bot_bracket_protocol as bot_bracket_protocol,
)
from tests.infra.execution_market.test_bot_indicator_inputs import (
    append_recorded_candle,
    fixture_candles,
    seed_prepared,
)
from tests.infra.execution_market.test_strategy_baskets import entry, f21_run
from tests.infra.indicators.test_source import active as active
from tests.infra.risk_limits.test_execution import Runtime, drive, runtime
from tiewtrade.core.market_data import Candle, CandleFinality, Timeframe, advance, align_floor
from tiewtrade.core.money import Money, Scalar
from tiewtrade.core.strategies import StrategyDocument, document_from_payload, document_payload
from tiewtrade.infra.bots.evaluation import PreparedQuote, evaluate_published_quote
from tiewtrade.infra.bots.inputs import (
    BotInputsUnavailableError,
    IndicatorInputs,
    read_bot_indicators,
    require_current_indicators,
)
from tiewtrade.infra.db import DatabaseRole, create_engine_for, user_session
from tiewtrade.infra.db.session import market_data_session
from tiewtrade.infra.indicators.prepared import proof_valid
from tiewtrade.infra.market_data.realtime_storage import read_snapshot, set_connected, write_price
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot
from tiewtrade.infra.protections.worker import process_group
from tiewtrade.services.engine.bot import StrategyRegistry, run_bot_quote
from tiewtrade.strategies.rsi_step_grid.strategy import initial_state

pytestmark = pytest.mark.usefixtures("internal_database")


async def restored_run(
    api: AsyncEngine,
    engine: AsyncEngine,
    migrator: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    source: Runtime,
) -> tuple[UUID, UUID, Candle, tuple[Money, ...]]:
    await source.price("310")
    async with market_data_session(source.market) as session:
        snapshot = await read_snapshot(session)
        quote = next(row.observation for row in snapshot.rows if row.base == "BTC")
        assert quote is not None
    end = align_floor(quote.trade_time, Timeframe.M1)
    history = tuple(Money.of(index + 100, "USDT") for index in range(250))
    await seed_prepared(migrator, 250, advance(end, Timeframe.M1, -1), closes=history)
    run, worker = await f21_run(engine, owner, wallet, timeframe=Timeframe.M1), uuid4()
    async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
        await session.execute(
            "UPDATE bot_strategy_progress SET eligible_after=:old,indicator_source_epoch="
            "(SELECT epoch FROM indicator_source_guard WHERE id=1),price_recovery_at="
            "(SELECT bot_recovery_at FROM market_price_feed WHERE source='primary_spot') "
            "WHERE run_id=:run",
            {"old": advance(end, Timeframe.M1, -2), "run": run},
        )
        await session.execute(
            "INSERT INTO bot_run_leases(run_id,user_id,mode,worker_id,generation,lease_until) "
            "VALUES(:run,:owner,'PAPER',:worker,1,clock_timestamp()+interval '30 seconds')",
            {"run": run, "owner": owner, "worker": worker},
        )
    candle = fixture_candles(
        advance(end, Timeframe.M1, -251),
        (*history, Money.of(310, "USDT")),
        spread=Money.of(10, "USDT"),
    )[-1]
    return run, worker, candle, history


async def indicator_input(
    engine: AsyncEngine, owner: UUID, run: UUID, worker: UUID
) -> tuple[PreparedQuote, IndicatorInputs]:
    registry = StrategyRegistry(enable_f21=True)
    async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
        prepared = await evaluate_published_quote(
            session,
            run,
            worker_id=worker,
            resolve=registry.implementation,
            resolve_configuration=registry.configured_implementation,
        )
    assert isinstance(prepared, PreparedQuote)
    async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
        inputs = await read_bot_indicators(
            session, prepared.strategy.descriptor, prepared.snapshot, prepared.state
        )
    return prepared, inputs


@pytest.mark.parametrize("awaiting_closure", [False, True])
async def test_normal_preparation_wait_keeps_live_boundary_and_tail_matches_full_generation(
    awaiting_closure: bool,
    active: None,
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000", account_use="BOT"
    ) as source:
        run, worker, candle, history = await restored_run(
            api_engine, engine_engine, migrator_engine, owner, wallet, source
        )
        registry = StrategyRegistry(enable_f21=True)
        if awaiting_closure:
            await append_recorded_candle(
                source.market, replace(candle, finality=CandleFinality.UNCONFIRMED)
            )
        assert (
            await run_bot_quote(
                engine=engine_engine, owner=owner, run_id=run, worker_id=worker, registry=registry
            )
            is None
        )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            progress = (
                await session.execute(
                    "SELECT recovery_required,eligible_after FROM bot_strategy_progress"
                )
            ).one()
            assert not progress.recovery_required and progress.eligible_after < candle.open_at
        await append_recorded_candle(source.market, candle)
        assert (
            await run_bot_quote(
                engine=engine_engine, owner=owner, run_id=run, worker_id=worker, registry=registry
            )
            is not None
        )
        _, tail = await indicator_input(engine_engine, owner, run, worker)
        assert tail.tail is not None and tail.candle_input is not None
        assert not tail.candle_input.backfilled and tail.candle_input.contiguous_count == 251
        assert dict(tail.values)["rsi14"].value == Scalar.of("24.999999999999999993")
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            state = (await session.execute("SELECT strategy_state FROM bot_runs")).scalar_one()
            assert dict(document_from_payload(state, expected_version=1).fields)[
                "reset_close"
            ] == Money.of(310, "USDT")
            assert (
                await session.execute("SELECT count(*) FROM paper_order_commands")
            ).scalar_one() == 0
        await seed_prepared(
            migrator_engine, 251, candle.end_at, closes=(*history, Money.of(310, "USDT"))
        )
        _, full = await indicator_input(engine_engine, owner, run, worker)
        assert full.tail is None and full.values == tail.values


async def test_tail_mutation_is_fenced_even_when_original_generation_prefix_is_valid(
    active: None,
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000", account_use="BOT"
    ) as source:
        run, worker, candle, _ = await restored_run(
            api_engine, engine_engine, migrator_engine, owner, wallet, source
        )
        await append_recorded_candle(source.market, candle)
        _, inputs = await indicator_input(engine_engine, owner, run, worker)
        await append_recorded_candle(source.market, replace(candle, close=Money.of(311, "USDT")))
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            now: datetime = (await session.execute("SELECT clock_timestamp()")).scalar_one()
            assert await proof_valid(session, inputs.generation, now)
            with pytest.raises(BotInputsUnavailableError, match="INDICATOR_SOURCE_CHANGED"):
                await require_current_indicators(session, inputs)


async def test_source_failure_and_recovery_between_polls_cannot_arm_from_backfill(
    active: None,
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000", account_use="BOT"
    ) as source:
        run, worker, candle, _ = await restored_run(
            api_engine, engine_engine, migrator_engine, owner, wallet, source
        )
        await append_recorded_candle(source.market, candle)
        async with market_data_session(source.market) as session:
            await session.execute(
                "UPDATE market_candle_demand SET status='FAILED',failure_code='SOURCE_FAILURE'"
            )
        async with market_data_session(source.market) as session:
            await session.execute(
                "UPDATE market_candle_demand SET status='COMPLETE',failure_code=NULL"
            )
        await run_bot_quote(
            engine=engine_engine,
            owner=owner,
            run_id=run,
            worker_id=worker,
            registry=StrategyRegistry(enable_f21=True),
        )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            row = (await session.execute("SELECT strategy_state,status FROM bot_runs")).one()
            assert row.status == "RUNNING"
            assert (
                dict(document_from_payload(row.strategy_state, expected_version=1).fields)[
                    "reset_close"
                ]
                is None
            )
            progress = (
                await session.execute(
                    "SELECT recovery_required,eligible_after,source_recovery_at "
                    "FROM bot_strategy_progress"
                )
            ).one()
            assert not progress.recovery_required and progress.source_recovery_at is not None
            assert progress.eligible_after >= progress.source_recovery_at > candle.end_at
            assert (
                await session.execute("SELECT count(*) FROM paper_order_commands")
            ).scalar_one() == 0


async def seed_armed_buy(
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    end: datetime,
    history: tuple[Money, ...],
) -> None:
    reset_at = advance(end, Timeframe.M1, -2)
    state = dict(initial_state().fields) | {
        "reset_close": Money.of(310, "USDT"),
        "reset_open_at": reset_at.isoformat(),
        "last_candle": reset_at.isoformat(),
    }
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await session.execute(
            "UPDATE bot_runs SET strategy_state=CAST(:state AS jsonb)",
            {"state": json.dumps(document_payload(StrategyDocument(1, tuple(state.items()))))},
        )
    await seed_prepared(
        migrator_engine,
        252,
        end,
        closes=(*history, Money.of(310, "USDT"), Money.of(355, "USDT")),
    )


async def test_corrected_historical_arm_cannot_authorize_buy(
    active: None,
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000", account_use="BOT"
    ) as source:
        run, worker, candle, history = await restored_run(
            api_engine, engine_engine, migrator_engine, owner, wallet, source
        )
        end = candle.end_at
        await seed_armed_buy(engine_engine, migrator_engine, owner, end, history)
        _, before = await indicator_input(engine_engine, owner, run, worker)
        assert before.candle_input is not None and before.candle_input.arm_validated
        # Rebuild from the corrected authoritative candle; a valid new source
        # generation must not silently certify the old reset price.
        await seed_prepared(
            migrator_engine,
            252,
            end,
            closes=(*history, Money.of(311, "USDT"), Money.of(355, "USDT")),
        )
        _, after = await indicator_input(engine_engine, owner, run, worker)
        assert after.candle_input is not None and not after.candle_input.arm_validated
        await run_bot_quote(
            engine=engine_engine,
            owner=owner,
            run_id=run,
            worker_id=worker,
            registry=StrategyRegistry(enable_f21=True),
        )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            assert (
                await session.execute("SELECT count(*) FROM paper_order_commands")
            ).scalar_one() == 0


async def test_realtime_disconnect_and_reconcile_between_polls_cannot_replay_arm(
    active: None,
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000", account_use="BOT"
    ) as source:
        run, worker, candle, _ = await restored_run(
            api_engine, engine_engine, migrator_engine, owner, wallet, source
        )
        await append_recorded_candle(source.market, candle)
        _, before = await indicator_input(engine_engine, owner, run, worker)
        assert before.candle_input is not None and not before.candle_input.backfilled
        async with market_data_session(source.market) as session:
            snapshot = await read_snapshot(session)
            assert snapshot.feed is not None
            lease = await set_connected(session, snapshot.feed, False)
            await set_connected(session, lease, True)
        await source.price("310")
        async with market_data_session(source.market) as session:
            snapshot = await read_snapshot(session)
            row = next(row for row in snapshot.rows if row.base == "BTC")
            assert snapshot.feed is not None
            await write_price(
                session,
                snapshot.feed,
                replace(row, unavailable_since=None, order_ambiguous_at=None),
            )
        _, after = await indicator_input(engine_engine, owner, run, worker)
        assert after.candle_input is not None and after.candle_input.backfilled
        await run_bot_quote(
            engine=engine_engine,
            owner=owner,
            run_id=run,
            worker_id=worker,
            registry=StrategyRegistry(enable_f21=True),
        )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            state = (await session.execute("SELECT strategy_state FROM bot_runs")).scalar_one()
            assert (
                dict(document_from_payload(state, expected_version=1).fields)["reset_close"] is None
            )
            progress = (
                await session.execute(
                    "SELECT eligible_after,price_recovery_at FROM bot_strategy_progress"
                )
            ).one()
            assert progress.eligible_after >= progress.price_recovery_at > candle.end_at
            assert (
                await session.execute("SELECT count(*) FROM paper_order_commands")
            ).scalar_one() == 0


async def test_closed_basket_allows_only_next_eligible_real_candle_after_pool_restart(
    active: None,
    bot_bracket_protocol: None,
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    # Leave room to complete the setup and the exit in one real candle.
    async with migrator_engine.connect() as connection:
        now: datetime = (await connection.execute(text("SELECT clock_timestamp()"))).scalar_one()
    boundary = advance(align_floor(now, Timeframe.M1), Timeframe.M1, 1)
    if (boundary - now).total_seconds() < 10:
        await asyncio.sleep((boundary - now).total_seconds() + 0.1)
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000", account_use="BOT"
    ) as source:
        run, worker_id, reset_candle, history = await restored_run(
            api_engine, engine_engine, migrator_engine, owner, wallet, source
        )
        # Seed just the original order using the basket accounting fixture. All
        # post-exit ARM/FIRE decisions read persisted F-11 candles and indicators.
        await source.price("100")
        _, group = await entry(engine_engine, owner, wallet, run, source)
        await source.price("107")
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await process_group(session, group)
            sell = (
                await session.execute("SELECT command_id FROM paper_protection_exits")
            ).scalar_one()
        await drive(engine_engine, owner, sell)
        await asyncio.sleep(0.12)
        await source.next_book()
        await drive(engine_engine, owner, sell)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await process_group(session, group)
            closed = (
                await session.execute("SELECT id FROM bot_strategy_baskets WHERE status='CLOSED'")
            ).scalar_one()
            assert (
                await session.execute("SELECT candle_open_at FROM bot_strategy_exit_guards")
            ).scalar_one() == reset_candle.end_at
        restarted = create_engine_for(DatabaseRole.ENGINE)
        try:
            await append_recorded_candle(source.market, reset_candle)
            registry = StrategyRegistry(enable_f21=True)

            async def evaluate() -> UUID | None:
                return await run_bot_quote(
                    engine=restarted,
                    owner=owner,
                    run_id=run,
                    worker_id=worker_id,
                    registry=registry,
                )

            # Drain the initial order's execution feedback before evaluating the reset.
            for _ in range(6):
                await evaluate()
                async with user_session(restarted, owner, role=DatabaseRole.ENGINE) as session:
                    state = (
                        await session.execute("SELECT strategy_state FROM bot_runs")
                    ).scalar_one()
                    reset = dict(document_from_payload(state, expected_version=1).fields)[
                        "reset_close"
                    ]
                    if isinstance(reset, Money) and reset == reset_candle.close:
                        break
            else:
                pytest.fail("restored run did not arm on the verified RSI reset")
            start = advance(reset_candle.open_at, Timeframe.M1, -250)
            candles = fixture_candles(
                start,
                (*history, reset_candle.close, Money.of(355, "USDT"), Money.of(395, "USDT")),
                spread=Money.of(10, "USDT"),
            )
            for guarded, candle in zip((True, False), candles[-2:], strict=True):
                while True:
                    async with market_data_session(source.market) as market_session:
                        now = (
                            await market_session.execute("SELECT clock_timestamp()")
                        ).scalar_one()
                    remaining = (candle.end_at - now).total_seconds()
                    if remaining <= 0:
                        break
                    await asyncio.sleep(min(remaining, 2))
                    await source.next_book()
                    await source.price("104")
                    if remaining > 4:
                        await evaluate()
                await append_recorded_candle(source.market, candle)
                await source.price(candle.close.as_parts()["amount"])
                prepared, inputs = await indicator_input(restarted, owner, run, worker_id)
                cap = inputs.candle_input
                assert cap is not None and cap.candle == candle and cap.arm_validated
                assert not cap.backfilled and not cap.basket_triggered and cap.open_entries == 0
                assert cap.exit_on_candle == guarded
                # With the guard removed this identical input would really buy.
                snapshot = replace(
                    prepared.snapshot,
                    indicators=inputs.values,
                    candle_input=replace(cap, exit_on_candle=False),
                )
                assert (
                    len(
                        prepared.strategy.evaluate(
                            snapshot, prepared.configuration, prepared.state
                        ).intents
                    )
                    == 1
                )
                assert await evaluate() is not None
                async with user_session(restarted, owner, role=DatabaseRole.ENGINE) as session:
                    count = (
                        await session.execute("SELECT count(*) FROM bot_order_links")
                    ).scalar_one()
                    assert count == (1 if guarded else 2)
            async with user_session(restarted, owner, role=DatabaseRole.ENGINE) as session:
                new = (
                    await session.execute("SELECT id FROM bot_strategy_baskets WHERE status='OPEN'")
                ).scalar_one()
                assert new != closed
                pending = (
                    await session.execute(
                        "SELECT command_id FROM bot_strategy_entries WHERE basket_id=:id",
                        {"id": new},
                    )
                ).scalar_one()
            await drive(restarted, owner, pending)
            await asyncio.sleep(0.12)
            await source.next_book()
            await drive(restarted, owner, pending)
            async with user_session(restarted, owner, role=DatabaseRole.ENGINE) as session:
                target = (
                    await session.execute(
                        "SELECT target FROM bot_strategy_baskets WHERE id=:id", {"id": new}
                    )
                ).scalar_one()
                assert Money.of(target, "USDT") > Money.of(106, "USDT")
                assert (
                    await session.execute("SELECT count(*) FROM paper_position_events")
                ).scalar_one() == 3
        finally:
            await restarted.dispose()
