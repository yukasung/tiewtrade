"""F-20 review regressions on isolated PostgreSQL, including real process failures."""

import asyncio
import json
import os
import sys
from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market.test_bot_decisions import seed_run
from tests.infra.execution_market.test_dispatch import intent
from tests.infra.positions.conftest import create_production_wallet
from tests.infra.risk_limits.test_execution import drive, runtime
from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.orders import (
    BaseSize,
    OrderIntent,
    OrderOrigin,
    OrderType,
    TimeInForce,
    TradingMode,
)
from tiewtrade.core.positions import PositionPair
from tiewtrade.core.strategies import (
    StrategyDecision,
    StrategyDescriptor,
    StrategyDocument,
    StrategyInput,
)
from tiewtrade.infra.bots.decisions import EvaluatedDecision, record_paper_decision
from tiewtrade.infra.bots.start import PublishedConfiguration
from tiewtrade.infra.db import DatabaseRole, InfraError, create_engine_for, user_session
from tiewtrade.infra.db.session import UserSession, scan_session_bypassing_rls
from tiewtrade.infra.paper_orders.dispatch import submit_order
from tiewtrade.infra.paper_wallet import get_wallet
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot
from tiewtrade.infra.risk_limits.dispatch import lock_risk_owner
from tiewtrade.infra.users import create_user
from tiewtrade.services.engine.bot import (
    PublishedStrategy,
    StrategyRegistry,
    run_bot_quote,
    run_bot_worker_round,
)
from tiewtrade.services.engine.kill_switch import run_stop_request_round

pytestmark = pytest.mark.usefixtures("internal_database")
DOC = StrategyDocument(1, ())
PAIR = PositionPair("BTC", "USDT")


class NoopStrategy:
    descriptor = StrategyDescriptor(
        "fixture", 1, 1, 1, frozenset({PAIR}), None, frozenset(), False, quote_trigger=True
    )

    def evaluate(
        self, snapshot: StrategyInput, configuration: StrategyDocument, state: StrategyDocument
    ) -> StrategyDecision:
        return StrategyDecision(state)


def registry(strategy: NoopStrategy | None = None) -> StrategyRegistry:
    value = strategy or NoopStrategy()
    definition = PublishedConfiguration("fixture-v1", value.descriptor, PAIR, DOC, DOC)
    return StrategyRegistry((PublishedStrategy(definition, value),))


async def seed_input_run(engine: AsyncEngine, owner: UUID, wallet: PaperWalletSnapshot) -> UUID:
    run = uuid4()
    await seed_run(engine, owner, wallet, run, DOC)
    async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
        await session.execute(
            """INSERT INTO bot_run_events(id,run_id,user_id,mode,revision,event,details)
               VALUES(:id,:run,:owner,'PAPER',1,'START_REQUEST_APPLIED',
                 jsonb_build_object('base','BTC','quote','USDT','catalog_revision',
                   (SELECT current_revision FROM supported_symbol_catalog_control)))""",
            {"id": uuid4(), "run": run, "owner": owner},
        )
    return run


@pytest.mark.parametrize(
    "corrupt", [{"version": 2, "fields": []}, {"version": 1, "fields": [["bad", 1.5]]}]
)
async def test_duplicate_quote_recovery_validates_state_before_reauthorizing_accepted_buy(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    corrupt: dict[str, object],
) -> None:
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000", account_use="BOT"
    ) as sources:
        run = await seed_input_run(engine_engine, owner, wallet)
        value = replace(
            intent(owner, wallet.episode_id),
            origin=OrderOrigin.BOT,
            kind=OrderType.LIMIT,
            size=BaseSize(Quantity.of(1, "BTC")),
            limit_price=Money.of(90, "USDT"),
            time_in_force=TimeInForce.GTC,
        )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await record_paper_decision(
                session,
                EvaluatedDecision(
                    run,
                    uuid4(),
                    "quote:primary_spot:100",
                    1,
                    1,
                    1,
                    DOC,
                    StrategyDecision(DOC, (value,)),
                ),
            )
            command = (await session.execute("SELECT command_id FROM bot_order_links")).scalar_one()
        await drive(engine_engine, owner, command)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await session.execute(
                "UPDATE bot_runs SET strategy_state=CAST(:state AS jsonb)",
                {"state": json.dumps(corrupt)},
            )
        assert (
            await run_bot_quote(
                engine=engine_engine,
                owner=owner,
                run_id=run,
                registry=registry(),
                worker_id=uuid4(),
            )
            is None
        )
        await asyncio.sleep(0.12)
        sources.book = replace(
            sources.book,
            bids=(replace(sources.book.bids[0], price=Money.of(89, "USDT")),),
            asks=(replace(sources.book.asks[0], price=Money.of(90, "USDT")),),
        )
        await sources.next_book()
        await drive(engine_engine, owner, command)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            assert (await session.execute("SELECT status FROM bot_runs")).scalar_one() == "STOPPED"
            assert (
                await session.execute("SELECT reason_code FROM trading_stop_requests")
            ).scalar_one() == "STRATEGY_EVALUATION_FAILED"
            assert (
                await session.execute("SELECT count(*) FROM paper_position_events")
            ).scalar_one() == 0
            assert (await session.execute("SELECT count(*) FROM bot_decisions")).scalar_one() == 1
            after = await get_wallet(session)
            assert after is not None and after.balance == wallet.balance


async def _child_decision(arguments: list[str]) -> None:
    owner, episode, _wallet, run, decision, order, key = (UUID(value) for value in arguments[:7])
    phase = arguments[7]
    engine = create_engine_for(DatabaseRole.ENGINE)

    async def admit(session: UserSession, wallet_id: UUID, value: OrderIntent) -> UUID:
        return (await submit_order(session, wallet_id=wallet_id, intent=value)).command_id

    value = replace(
        intent(owner, episode), origin=OrderOrigin.BOT, order_id=order, idempotency_key=key
    )
    try:
        try:
            async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
                await record_paper_decision(
                    session,
                    EvaluatedDecision(
                        run,
                        decision,
                        "process-window",
                        1,
                        1,
                        1,
                        DOC,
                        StrategyDecision(StrategyDocument(1, (("processed", True),)), (value,)),
                    ),
                    admit=admit,
                )
                if phase == "disconnect":
                    await session.execute("SELECT pg_terminate_backend(pg_backend_pid())")
                if phase == "before-commit":
                    sys.stdout.write("STAGED\n")
                    sys.stdout.flush()
                    await asyncio.to_thread(sys.stdin.readline)
            sys.stdout.write("COMMITTED\n")
            sys.stdout.flush()
            await asyncio.to_thread(sys.stdin.readline)
        except InfraError:
            if phase != "disconnect":
                raise
            sys.stdout.write("DISCONNECTED\n")
            sys.stdout.flush()
    finally:
        await engine.dispose()


@pytest.mark.parametrize("phase", ["before-commit", "after-commit", "disconnect"])
async def test_real_process_and_connection_failure_preserve_atomic_journal_and_financial_sources(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    phase: str,
) -> None:
    from tests.infra.manual_orders.test_bridge import select_use

    await select_use(api_engine, owner, "BOT")
    run = await seed_input_run(engine_engine, owner, wallet)
    decision, order, key = uuid4(), uuid4(), uuid4()
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        "import asyncio,sys; "
        "from tests.infra.execution_market.test_bot_review_safety import _child_decision; "
        "asyncio.run(_child_decision(sys.argv[1:]))",
        *(
            str(value)
            for value in (owner, wallet.episode_id, wallet.wallet_id, run, decision, order, key)
        ),
        phase,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=os.environ.copy(),
    )
    try:
        assert process.stdout is not None
        marker = (await asyncio.wait_for(process.stdout.readline(), 8)).decode().strip()
        assert (
            marker
            == {
                "before-commit": "STAGED",
                "after-commit": "COMMITTED",
                "disconnect": "DISCONNECTED",
            }[phase]
        )
        if phase != "disconnect":
            process.kill()
        await asyncio.wait_for(process.wait(), 4)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await lock_risk_owner(session, TradingMode.PAPER)
            committed = phase == "after-commit"
            for table in ("bot_decisions", "bot_order_links", "paper_order_commands"):
                assert (await session.execute(f"SELECT count(*) FROM {table}")).scalar_one() == int(
                    committed
                )
            assert (
                await session.execute(
                    "SELECT count(*) FROM bot_run_events WHERE event='DECISION_RECORDED'"
                )
            ).scalar_one() == int(committed)
            assert (await session.execute("SELECT revision FROM bot_runs")).scalar_one() == (
                2 if committed else 1
            )
            for table in (
                "paper_orders",
                "paper_reservations",
                "paper_position_events",
                "paper_position_projections",
            ):
                assert (await session.execute(f"SELECT count(*) FROM {table}")).scalar_one() == 0
            assert (
                await session.execute("SELECT count(*) FROM paper_wallet_ledger")
            ).scalar_one() == 1
            after = await get_wallet(session)
            assert after is not None and after.balance == wallet.balance
        # A fresh process/session replays the original identity, never a replacement command.
        value = replace(
            intent(owner, UUID(str(wallet.episode_id))),
            origin=OrderOrigin.BOT,
            order_id=order,
            idempotency_key=key,
        )

        async def admit(session: UserSession, wallet_id: UUID, value: OrderIntent) -> UUID:
            return (await submit_order(session, wallet_id=wallet_id, intent=value)).command_id

        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            assert (
                await record_paper_decision(
                    session,
                    EvaluatedDecision(
                        run,
                        decision,
                        "process-window",
                        1,
                        1,
                        1,
                        DOC,
                        StrategyDecision(StrategyDocument(1, (("processed", True),)), (value,)),
                    ),
                    admit=admit,
                )
                == decision
            )
            assert (
                await session.execute("SELECT count(*) FROM paper_order_commands")
            ).scalar_one() == 1
            assert (await session.execute("SELECT count(*) FROM bot_decisions")).scalar_one() == 1
    finally:
        if process.returncode is None:
            process.kill()
        await process.wait()


async def test_recovery_scan_rotates_past_twenty_permanently_missing_strategies(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
) -> None:
    runs: list[UUID] = []
    for _ in range(21):
        owner = uuid4()
        await create_user(api_engine, owner)
        wallet = await create_production_wallet(api_engine, engine_engine, scan_engine, owner)
        run = await seed_input_run(engine_engine, owner, wallet)
        runs.append(run)
        assert (
            await run_bot_quote(
                engine=engine_engine,
                owner=owner,
                run_id=run,
                registry=StrategyRegistry(),
                worker_id=uuid4(),
            )
            is None
        )
    await run_stop_request_round(engine=engine_engine, scan_engine=scan_engine)
    await run_stop_request_round(engine=engine_engine, scan_engine=scan_engine)
    async with scan_session_bypassing_rls(scan_engine) as session:
        first = (await session.execute("SELECT * FROM due_bot_recovery_probes(20)")).all()
    assert len(first) == 20 and runs[-1] not in {row.run_id for row in first}
    round_result = await run_bot_worker_round(
        engine=engine_engine,
        scan_engine=scan_engine,
        registry=StrategyRegistry(),
        cursor=None,
        worker_id=uuid4(),
    )
    assert round_result.recovery_proofs == 0
    async with scan_session_bypassing_rls(scan_engine) as session:
        second = (await session.execute("SELECT * FROM due_bot_recovery_probes(20)")).all()
    assert second[0].run_id == runs[-1]


async def test_catalog_withdrawal_does_not_destroy_system_proof_for_flat_replacement(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    from datetime import timedelta

    from tests.infra.execution_market.test_bot_catalog import enable_catalog
    from tiewtrade.core.timeframes import Timeframe
    from tiewtrade.infra.bots.catalog import CatalogStopHint, apply_catalog_stop
    from tiewtrade.infra.bots.requests import receipt_by_key, submit_start
    from tiewtrade.infra.db.session import market_data_session
    from tiewtrade.infra.indicators.session import indicator_writer_session
    from tiewtrade.infra.platform import (
        CatalogReason,
        ConstraintEvidence,
        activate,
        prepare,
        record_price_readiness,
        record_timeframe_readiness,
        request_add,
        request_remove,
    )
    from tiewtrade.infra.trading_stops import read_status
    from tiewtrade.services.engine.bot import run_bot_catalog_round, run_bot_control_round
    from tiewtrade.services.engine.risk_limit import run_risk_stop_round

    executable = registry()
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000", account_use="BOT"
    ) as sources:
        run = await seed_input_run(engine_engine, owner, wallet)
        assert (
            await run_bot_quote(
                engine=engine_engine,
                owner=owner,
                run_id=run,
                registry=StrategyRegistry(),
                worker_id=uuid4(),
            )
            is None
        )
        await run_stop_request_round(engine=engine_engine, scan_engine=scan_engine)
        await run_risk_stop_round(engine=engine_engine, scan_engine=scan_engine)
        await enable_catalog(api_engine, engine_engine, migrator_engine, owner)
        async with user_session(api_engine, owner) as session:
            removed = await request_remove(
                session,
                command_id=uuid4(),
                idempotency_key="remove-during-system-stop",
                base="BTC",
                quote="USDT",
                expected_revision=2,
                reason=CatalogReason.RISK_REVIEW,
            )
        assert removed.revision == 3
        assert await run_bot_catalog_round(engine=engine_engine, scan_engine=scan_engine) == 1
        async with user_session(api_engine, owner) as session:
            now = (await session.execute("SELECT clock_timestamp()")).scalar_one()
            evidence = ConstraintEvidence(
                "BTCUSDT", now, '{"symbol":"BTCUSDT","status":"TRADING"}', "a" * 64
            )
            added = await request_add(
                session,
                command_id=uuid4(),
                idempotency_key="readd-after-system-stop",
                base="BTC",
                quote="USDT",
                expected_revision=3,
                reason=CatalogReason.LIQUIDITY_REVIEWED,
                evidence=evidence,
            )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            assert added.revision is not None
            revision = await prepare(
                session, base="BTC", quote="USDT", expected_revision=added.revision
            )
        async with market_data_session(sources.market) as session:
            ready_at = (await session.execute("SELECT clock_timestamp()")).scalar_one()
            await record_price_readiness(
                session, base="BTC", quote="USDT", catalog_revision=revision, price_at=ready_at
            )
            await session.execute("DELETE FROM market_candle_demand WHERE base='BTC'")
            for timeframe in Timeframe:
                await record_timeframe_readiness(
                    session,
                    base="BTC",
                    quote="USDT",
                    catalog_revision=revision,
                    timeframe=timeframe,
                    ready_at=ready_at,
                )
        builder = create_engine_for(DatabaseRole.INDICATOR_BUILDER)
        try:
            async with indicator_writer_session(builder) as session:
                for timeframe in Timeframe:
                    await record_timeframe_readiness(
                        session,
                        base="BTC",
                        quote="USDT",
                        catalog_revision=revision,
                        timeframe=timeframe,
                        ready_at=ready_at,
                    )
        finally:
            await builder.dispose()
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await activate(
                session,
                base="BTC",
                quote="USDT",
                expected_revision=revision,
                validation_started_at=ready_at - timedelta(seconds=1),
                evidence=ConstraintEvidence(
                    "BTCUSDT", ready_at, '{"symbol":"BTCUSDT","status":"TRADING"}', "a" * 64
                ),
            )
        await sources.price("100")
        recovered = await run_bot_worker_round(
            engine=engine_engine,
            scan_engine=scan_engine,
            registry=executable,
            cursor=None,
            worker_id=uuid4(),
        )
        assert recovered.recovery_proofs == 1
        async with user_session(api_engine, owner) as session:
            status = await read_status(session, TradingMode.PAPER)
            assert status.resume_ready and status.stop_id is not None
            run_revision = (await session.execute("SELECT revision FROM bot_runs")).scalar_one()
            key = uuid4()
            await submit_start(
                session,
                mode=TradingMode.PAPER,
                request_id=uuid4(),
                key=key,
                payload={
                    "strategy_config_ref": "fixture-v1",
                    "replacement": {
                        "run_id": str(run),
                        "run_revision": run_revision,
                        "stop_id": str(status.stop_id),
                        "stop_revision": status.revision,
                        "summary_revision": status.summary_revision,
                        "reconciliation_revision": status.reconciliation_revision,
                    },
                },
            )
        assert (
            await run_bot_control_round(
                engine=engine_engine, scan_engine=scan_engine, registry=executable
            )
        ).applied == 1
        async with user_session(api_engine, owner) as session:
            result = await receipt_by_key(session, TradingMode.PAPER, key)
            assert result is not None and result.run_id is not None and result.run_id != run
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            assert not await apply_catalog_stop(
                session, CatalogStopHint(result.run_id, owner, TradingMode.PAPER, 3)
            )
            assert (
                await session.execute(
                    "SELECT status FROM bot_runs WHERE id=:run", {"run": result.run_id}
                )
            ).scalar_one() == "STARTING"
            assert (
                await session.execute("SELECT status FROM bot_runs WHERE id=:run", {"run": run})
            ).scalar_one() == "RETIRED"
            assert (
                await session.execute("SELECT count(*) FROM bot_catalog_stops")
            ).scalar_one() == 1
            assert (
                await session.execute(
                    """SELECT count(*) FROM bot_run_events WHERE run_id=:run
                       AND event IN ('RUN_READY','RESUME_RECONCILING')""",
                    {"run": run},
                )
            ).scalar_one() == 0
            assert (
                await session.execute("SELECT count(*) FROM paper_order_commands")
            ).scalar_one() == 0
            assert (
                await session.execute("SELECT count(*) FROM paper_position_events")
            ).scalar_one() == 0
            after = await get_wallet(session)
            assert after is not None and after.balance == wallet.balance
