"""Actual persisted F-21 config/registry and central F-11 candle readiness."""

import json
from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market.test_bot_indicator_inputs import seed_prepared
from tests.infra.execution_market.test_strategy_baskets import f21_run
from tests.infra.indicators.test_source import active as active
from tests.infra.positions.conftest import create_production_wallet
from tests.infra.risk_limits.test_execution import runtime
from tests.infra.risk_limits.test_requests import submission
from tests.infra.risk_limits.test_worker import claim
from tiewtrade.core.market_data import Timeframe
from tiewtrade.core.money import Money
from tiewtrade.core.orders import TradingMode
from tiewtrade.core.positions import PositionPair
from tiewtrade.core.strategies import (
    StrategyContractError,
    StrategyDocument,
    document_from_payload,
    document_payload,
)
from tiewtrade.core.strategy_config import RsiStepGridConfig
from tiewtrade.core.trading_stops import StopAction
from tiewtrade.infra.bots.configurations import create_configuration
from tiewtrade.infra.bots.requests import receipt_by_key, submit_start
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.db.session import market_data_session
from tiewtrade.infra.market_data.realtime_storage import read_snapshot
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot
from tiewtrade.infra.risk_limits.requests import submit_request as submit_risk
from tiewtrade.infra.risk_limits.storage import process_request as process_risk
from tiewtrade.infra.trading_stops import read_status, submit_request
from tiewtrade.infra.users import create_user
from tiewtrade.services.engine.bot import (
    StrategyRegistry,
    prove_bot_strategy_recovery,
    run_bot_control_round,
    run_bot_quote,
    run_bot_worker_round,
)
from tiewtrade.services.engine.kill_switch import run_stop_request_round
from tiewtrade.services.engine.risk_limit import run_risk_stop_round
from tiewtrade.strategies.rsi_step_grid.strategy import RsiStepGridStrategy, initial_state

pytestmark = pytest.mark.usefixtures("internal_database")


@pytest.mark.parametrize("bars", [249, 250])
async def test_dynamic_configuration_uses_central_warmup_and_cannot_trade_backfill(
    active: None,
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    bars: int,
) -> None:
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000", account_use="BOT"
    ) as source:
        config = RsiStepGridConfig(
            PositionPair("BTC", "USDT"), Timeframe.M1, Money.of("17.000000000000000001", "USDT"), 3
        )
        key = uuid4()
        async with user_session(api_engine, owner) as session:
            identity = await create_configuration(session, configuration=config, key=uuid4())
            reference = f"f21:{identity}"
            await submit_start(
                session,
                mode=TradingMode.PAPER,
                request_id=uuid4(),
                key=key,
                payload={"strategy_config_ref": reference},
            )
        registry = StrategyRegistry(enable_f21=True)
        result = await run_bot_control_round(
            engine=engine_engine, scan_engine=scan_engine, registry=registry
        )
        assert result.applied == 1 and result.refused == 0
        async with user_session(api_engine, owner) as session:
            receipt = await receipt_by_key(session, TradingMode.PAPER, key)
            assert receipt is not None and receipt.run_id is not None and not receipt.pending
            run = receipt.run_id
        async with market_data_session(source.market) as session:
            snapshot = await read_snapshot(session)
            quote = next(row.observation for row in snapshot.rows if row.base == "BTC")
            assert quote is not None
        await seed_prepared(migrator_engine, bars, quote.trade_time)
        worker = uuid4()
        evaluated = await run_bot_quote(
            engine=engine_engine, owner=owner, run_id=run, registry=registry, worker_id=worker
        )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            row = (
                await session.execute(
                    "SELECT configuration,status FROM bot_runs WHERE id=:id", {"id": run}
                )
            ).one()
            assert (
                RsiStepGridConfig.from_document(
                    document_from_payload(row.configuration, expected_version=1)
                )
                == config
            )
            assert (
                await session.execute("SELECT count(*) FROM paper_order_commands")
            ).scalar_one() == 0
            assert (
                await session.execute("SELECT count(*) FROM bot_decisions")
            ).scalar_one() == int(bars == 250)
            assert row.status == ("RUNNING" if bars == 250 else "PAUSED")
            if bars == 249:
                assert evaluated is None
                reason = (
                    await session.execute(
                        "SELECT details->>'reason' FROM bot_run_events "
                        "ORDER BY revision DESC LIMIT 1"
                    )
                ).scalar_one()
                assert reason == "BOT_CANDLE_WARM_UP"
            else:
                assert evaluated is not None
                state = (
                    await session.execute(
                        "SELECT strategy_state FROM bot_runs WHERE id=:id", {"id": run}
                    )
                ).scalar_one()
                assert (
                    dict(document_from_payload(state, expected_version=1).fields)["last_candle"]
                    is None
                )
        await run_bot_quote(
            engine=engine_engine,
            owner=owner,
            run_id=run,
            registry=StrategyRegistry(enable_f21=True),
            worker_id=worker,
        )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            assert (
                await session.execute("SELECT count(*) FROM bot_decisions")
            ).scalar_one() == int(bars == 250)


@pytest.mark.parametrize("failure", ["malformed_checkpoint", "candle_evaluation"])
async def test_strategy_failure_is_scoped_and_recovery_requires_healthy_inputs(
    active: None,
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000", account_use="BOT"
    ) as source:
        run = await f21_run(engine_engine, owner, wallet, timeframe=Timeframe.M1)
        registry = StrategyRegistry(enable_f21=True)
        worker = uuid4()
        async with market_data_session(source.market) as market_session:
            now = (await market_session.execute("SELECT clock_timestamp()")).scalar_one()
        await seed_prepared(migrator_engine, 250, now)

        def broken_evaluation(*args: object) -> None:
            raise StrategyContractError("test strategy failure")

        if failure == "candle_evaluation":
            with monkeypatch.context() as patch:
                patch.setattr(RsiStepGridStrategy, "evaluate", broken_evaluation)
                assert (
                    await run_bot_quote(
                        engine=engine_engine,
                        owner=owner,
                        run_id=run,
                        registry=registry,
                        worker_id=worker,
                    )
                    is None
                )
        else:
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                fields = dict(initial_state().fields)
                fields.update(
                    reset_close=Money.of(100, "USDT"), reset_open_at="2026-01-01T00:00:00"
                )
                await session.execute(
                    "UPDATE bot_runs SET strategy_state=CAST(:state AS jsonb) WHERE id=:run",
                    {
                        "state": json.dumps(
                            document_payload(StrategyDocument(1, tuple(fields.items())))
                        ),
                        "run": run,
                    },
                )

            # Both runs share the same worker scan. The malformed owner's
            # SYSTEM stop must not prevent the healthy owner's evaluation.
            healthy_owner = uuid4()
            await create_user(api_engine, healthy_owner)
            healthy_wallet = await create_production_wallet(
                api_engine, engine_engine, scan_engine, healthy_owner
            )
            # runtime() already prepared the public feed; configure only this owner's risk.
            async with user_session(api_engine, healthy_owner) as session:
                await session.execute(
                    "INSERT INTO user_trading_preferences(user_id,use) VALUES(:id,'BOT')",
                    {"id": healthy_owner},
                )
                receipt = await submit_risk(
                    session,
                    replace(
                        submission(healthy_owner, healthy_wallet), amount=Money.of(1000, "USDT")
                    ),
                )
            token = await claim(engine_engine, healthy_owner, receipt)
            async with user_session(
                engine_engine, healthy_owner, role=DatabaseRole.ENGINE
            ) as session:
                await process_risk(session, token)
            healthy_run = await f21_run(
                engine_engine, healthy_owner, healthy_wallet, timeframe=Timeframe.M1
            )
            result = await run_bot_worker_round(
                engine=engine_engine,
                scan_engine=scan_engine,
                registry=registry,
                worker_id=worker,
                cursor=None,
            )
            assert result.evaluated == 1
            async with user_session(
                engine_engine, healthy_owner, role=DatabaseRole.ENGINE
            ) as session:
                assert (
                    await session.execute("SELECT run_id FROM bot_decisions")
                ).scalar_one() == healthy_run
        await run_stop_request_round(engine=engine_engine, scan_engine=scan_engine)
        await run_risk_stop_round(engine=engine_engine, scan_engine=scan_engine)
        async with user_session(api_engine, owner) as session:
            status = await read_status(session, TradingMode.PAPER)
            assert status.stop_id is not None and not status.resume_ready
            stop = status.stop_id
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            failed = (
                await session.execute(
                    "SELECT details->>'input_identity' FROM bot_run_events "
                    "WHERE event='STRATEGY_EVALUATION_FAILED'"
                )
            ).scalar_one()
            if failure == "candle_evaluation":
                assert failed.startswith("candle:BTC:USDT:1m:")
            else:
                assert failed is None

        async def recovery_proof() -> UUID | None:
            return await prove_bot_strategy_recovery(
                engine=engine_engine,
                owner=owner,
                run_id=run,
                stop_id=stop,
                registry=registry,
                worker_id=worker,
            )

        if failure == "malformed_checkpoint":
            assert await recovery_proof() is None
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                await session.execute(
                    "UPDATE bot_runs SET revision=revision+1, "
                    "strategy_state=CAST(:state AS jsonb) WHERE id=:run",
                    {"state": json.dumps(document_payload(initial_state())), "run": run},
                )
        assert await recovery_proof() is not None
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            assert (
                await session.execute("SELECT count(*) FROM paper_order_commands")
            ).scalar_one() == 0
            assert (await session.execute("SELECT status FROM bot_runs")).scalar_one() == "STOPPED"
        async with user_session(api_engine, owner) as session:
            status = await read_status(session, TradingMode.PAPER)
            assert status.resume_ready
            await submit_request(
                session,
                mode=TradingMode.PAPER,
                action=StopAction.RESUME,
                key=uuid4(),
                expected_stop_id=stop,
                expected_revision=status.revision,
                expected_summary_revision=status.summary_revision,
                expected_reconciliation_revision=status.reconciliation_revision,
                reason_code="USER_RESUME",
            )
        await run_stop_request_round(engine=engine_engine, scan_engine=scan_engine)
        async with user_session(api_engine, owner) as session:
            assert (await read_status(session, TradingMode.PAPER)).stop_id is None
