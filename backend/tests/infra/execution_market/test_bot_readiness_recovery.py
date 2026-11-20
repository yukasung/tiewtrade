"""Real-DB regressions for dry recovery proofs and same-lease readiness."""

import asyncio
from dataclasses import replace
from uuid import UUID, uuid4, uuid5

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market.test_bot_review_safety import (
    DOC,
    NoopStrategy,
    registry,
    seed_input_run,
)
from tests.infra.execution_market.test_dispatch import intent
from tests.infra.risk_limits.test_execution import drive, runtime
from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.orders import (
    BaseSize,
    OrderIntent,
    OrderOrigin,
    OrderType,
    QuoteBudget,
    TimeInForce,
    TradingMode,
)
from tiewtrade.core.positions import ExecutionSide
from tiewtrade.core.strategies import StrategyDecision, StrategyDocument, StrategyInput
from tiewtrade.infra.bots.decisions import EvaluatedDecision, record_paper_decision
from tiewtrade.infra.bots.feedback import next_paper_feedback, restore_status_feedback
from tiewtrade.infra.bots.requests import receipt_by_key, submit_start
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.db.session import UserSession, market_data_session
from tiewtrade.infra.market_data.realtime_storage import read_snapshot, renew_writer, set_connected
from tiewtrade.infra.paper_orders.dispatch import submit_order
from tiewtrade.infra.paper_wallet import get_wallet
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot
from tiewtrade.infra.risk_limits.dispatch import lock_risk_owner
from tiewtrade.infra.risk_limits.stops import consume_stop
from tiewtrade.infra.trading_stops import read_status
from tiewtrade.infra.trading_stops.storage import global_shared_lock
from tiewtrade.services.engine.bot import (
    prove_bot_strategy_recovery,
    run_bot_control_round,
    run_bot_quote,
)
from tiewtrade.services.engine.kill_switch import run_stop_request_round
from tiewtrade.services.engine.risk_limit import run_risk_stop_round

pytestmark = pytest.mark.usefixtures("internal_database")


async def _set_admission_enabled(engine: AsyncEngine, *, enabled: bool) -> None:
    async with engine.begin() as connection:
        await connection.execute(
            text("UPDATE risk_protocol_control SET admission_enabled=:enabled"),
            {"enabled": enabled},
        )


async def _set_order_source_ready(session: UserSession, *, ready: bool) -> None:
    await session.execute(
        "UPDATE paper_order_activity SET availability=:availability,failure_code=:failure",
        {
            "availability": "READY" if ready else "CONFLICTED",
            "failure": None if ready else "TEST_ORDER_SOURCE_UNAVAILABLE",
        },
    )


async def test_legacy_failure_without_input_context_cannot_get_a_guessed_recovery_proof(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    worker = uuid4()
    executable = registry()
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000", account_use="BOT"
    ):
        run = await seed_input_run(engine_engine, owner, wallet)
        assert (
            await run_bot_quote(
                engine=engine_engine,
                owner=owner,
                run_id=run,
                registry=executable,
                worker_id=worker,
            )
            is not None
        )
        stop = uuid4()
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await global_shared_lock(session)
            await lock_risk_owner(session, TradingMode.PAPER)
            revision = (
                await session.execute(
                    "UPDATE bot_runs SET status='STOPPED',revision=revision+1 RETURNING revision"
                )
            ).scalar_one()
            # The exact older writer shape: immutable cause, but no retained
            # quote/feedback context. Do not edit an existing append-only event.
            params = {"id": stop, "run": run, "owner": owner, "revision": revision}
            await session.execute(
                """INSERT INTO bot_run_events(id,run_id,user_id,mode,revision,event,details)
                VALUES(:id,:run,:owner,'PAPER',:revision,'STRATEGY_EVALUATION_FAILED',
                  jsonb_build_object('stop_id',CAST(:id AS uuid)))""",
                params,
            )
            await session.execute(
                """INSERT INTO trading_stop_requests
                (id,user_id,scope_owner_id,mode,action,cause,actor_role,idempotency_key,
                 fingerprint,reason_code,generation,recorded_at)
                VALUES(:id,:owner,:owner,'PAPER','STOP','SYSTEM','SYSTEM',:id,
                  repeat('0',64),'STRATEGY_EVALUATION_FAILED',1,clock_timestamp())""",
                params,
            )
            await session.execute(
                "INSERT INTO trading_stop_dispatch(request_id,user_id) VALUES(:id,:owner)",
                params,
            )
        await run_stop_request_round(engine=engine_engine, scan_engine=scan_engine)
        await run_risk_stop_round(engine=engine_engine, scan_engine=scan_engine)
        assert (
            await prove_bot_strategy_recovery(
                engine=engine_engine,
                owner=owner,
                run_id=run,
                stop_id=stop,
                registry=executable,
                worker_id=worker,
            )
            is None
        )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            assert (await session.execute("SELECT status FROM bot_runs")).scalar_one() == "STOPPED"
            assert (
                await session.execute("SELECT count(*) FROM bot_resume_proofs")
            ).scalar_one() == 0
            assert (
                await session.execute("SELECT count(*) FROM bot_recovery_schedule")
            ).scalar_one() == 1
            assert (await session.execute("SELECT count(*) FROM bot_decisions")).scalar_one() == 1
            assert (
                await session.execute("SELECT count(*) FROM paper_order_commands")
            ).scalar_one() == 0
            assert (
                await session.execute("SELECT count(*) FROM paper_position_events")
            ).scalar_one() == 0
            current = await get_wallet(session)
            assert current is not None and current.balance == wallet.balance


class BrokenQuote(NoopStrategy):
    def __init__(self, invalid_output: bool) -> None:
        self.invalid_output = invalid_output
        self.calls = 0

    def evaluate(
        self, snapshot: StrategyInput, configuration: StrategyDocument, state: StrategyDocument
    ) -> StrategyDecision:
        self.calls += 1
        if self.invalid_output:
            return StrategyDecision(StrategyDocument(2, ()))
        raise ValueError("fixture strategy still broken")


class OpeningProbe(NoopStrategy):
    def evaluate(
        self, snapshot: StrategyInput, configuration: StrategyDocument, state: StrategyDocument
    ) -> StrategyDecision:
        identity = uuid5(snapshot.run_id, snapshot.input_identity)
        return StrategyDecision(
            state,
            (
                OrderIntent(
                    identity,
                    identity,
                    snapshot.scope,
                    snapshot.pair,
                    OrderOrigin.BOT,
                    ExecutionSide.BUY,
                    OrderType.MARKET,
                    QuoteBudget(Money.of(25, "USDT")),
                ),
            ),
        )


@pytest.mark.parametrize("invalid_output", [False, True], ids=["exception", "invalid-output"])
async def test_duplicate_quote_never_substitutes_for_a_real_recovery_probe(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    invalid_output: bool,
) -> None:
    worker = uuid4()
    healthy = registry()
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000", account_use="BOT"
    ):
        run = await seed_input_run(engine_engine, owner, wallet)
        previous = await run_bot_quote(
            engine=engine_engine, owner=owner, run_id=run, registry=healthy, worker_id=worker
        )
        assert previous is not None
        # Deploy without the pinned implementation, before the quote changes.
        assert (
            await run_bot_quote(
                engine=engine_engine,
                owner=owner,
                run_id=run,
                registry=type(healthy)(),
                worker_id=worker,
            )
            is None
        )
        await run_stop_request_round(engine=engine_engine, scan_engine=scan_engine)
        await run_risk_stop_round(engine=engine_engine, scan_engine=scan_engine)
        async with user_session(api_engine, owner) as session:
            stopped = await read_status(session, TradingMode.PAPER)
            assert stopped.stop_id is not None and not stopped.resume_ready
        broken = BrokenQuote(invalid_output)
        assert (
            await prove_bot_strategy_recovery(
                engine=engine_engine,
                owner=owner,
                run_id=run,
                stop_id=stopped.stop_id,
                registry=registry(broken),
                worker_id=worker,
            )
            is None
        )
        assert broken.calls == 1
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            assert (
                await session.execute("SELECT count(*) FROM bot_resume_proofs")
            ).scalar_one() == 0
            assert (await session.execute("SELECT status FROM bot_runs")).scalar_one() == "STOPPED"
        assert (
            await prove_bot_strategy_recovery(
                engine=engine_engine,
                owner=owner,
                run_id=run,
                stop_id=stopped.stop_id,
                registry=registry(OpeningProbe()),
                worker_id=worker,
            )
            is not None
        )
        async with user_session(api_engine, owner) as session:
            assert (await read_status(session, TradingMode.PAPER)).resume_ready
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            assert (await session.execute("SELECT count(*) FROM bot_decisions")).scalar_one() == 1
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


class FeedbackStrategy(NoopStrategy):
    descriptor = replace(NoopStrategy.descriptor, execution_feedback_trigger=True)

    def __init__(self, broken: bool) -> None:
        self.broken = broken
        self.observed: list[tuple[str, str | None]] = []

    def evaluate(
        self, snapshot: StrategyInput, configuration: StrategyDocument, state: StrategyDocument
    ) -> StrategyDecision:
        feedback = snapshot.feedback
        self.observed.append(
            (
                snapshot.input_identity,
                None if feedback is None or feedback.status is None else feedback.status.value,
            )
        )
        if self.broken and feedback is not None:
            raise ValueError("fixture feedback path is still broken")
        return StrategyDecision(state)


@pytest.mark.parametrize("partial", [False, True], ids=["accepted", "partial-then-canceled"])
async def test_recovery_probes_the_actual_failed_feedback_instead_of_a_healthy_quote(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    partial: bool,
) -> None:
    worker = uuid4()
    healthy = FeedbackStrategy(False)
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000", account_use="BOT"
    ) as sources:
        run = await seed_input_run(engine_engine, owner, wallet)
        assert (
            await run_bot_quote(
                engine=engine_engine,
                owner=owner,
                run_id=run,
                registry=registry(healthy),
                worker_id=worker,
            )
            is not None
        )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            revision = (await session.execute("SELECT revision FROM bot_runs")).scalar_one()
            entry = replace(intent(owner, wallet.episode_id), origin=OrderOrigin.BOT)
            if partial:
                entry = replace(
                    entry,
                    kind=OrderType.LIMIT,
                    size=BaseSize(Quantity.of(1, "BTC")),
                    limit_price=Money.of(100, "USDT"),
                    time_in_force=TimeInForce.GTC,
                )
            await record_paper_decision(
                session,
                EvaluatedDecision(
                    run,
                    uuid4(),
                    "fixture-entry",
                    revision,
                    1,
                    1,
                    DOC,
                    StrategyDecision(DOC, (entry,)),
                ),
            )
            command = (await session.execute("SELECT command_id FROM bot_order_links")).scalar_one()
        await drive(engine_engine, owner, command)
        if partial:
            await asyncio.sleep(0.12)
            sources.book = replace(
                sources.book,
                asks=(replace(sources.book.asks[0], quantity=Quantity.of("0.4", "BTC")),),
            )
            await sources.next_book()
            await drive(engine_engine, owner, command)
            for _ in range(2):
                assert (
                    await run_bot_quote(
                        engine=engine_engine,
                        owner=owner,
                        run_id=run,
                        registry=registry(healthy),
                        worker_id=worker,
                    )
                    is not None
                )
        broken = FeedbackStrategy(True)
        assert (
            await run_bot_quote(
                engine=engine_engine,
                owner=owner,
                run_id=run,
                registry=registry(broken),
                worker_id=worker,
            )
            is None
        )
        failed_input, status = broken.observed[-1]
        assert status == ("PARTIALLY_FILLED" if partial else "ACCEPTED")
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            recorded = (
                await session.execute(
                    "SELECT details FROM bot_run_events WHERE event='STRATEGY_EVALUATION_FAILED'"
                )
            ).scalar_one()
            assert recorded["input_identity"] == failed_input
            saved_status = recorded["feedback_status"]
            for invalid in (
                {**saved_status, "order_id": str(uuid4())},
                {**saved_status, "revision": 0},
                {**saved_status, "extra": "unrecognized"},
            ):
                assert await restore_status_feedback(session, run, failed_input, invalid) is None
        await run_stop_request_round(engine=engine_engine, scan_engine=scan_engine)
        await run_risk_stop_round(engine=engine_engine, scan_engine=scan_engine)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            cancellation = (
                await session.execute("SELECT id FROM paper_order_commands WHERE action='CANCEL'")
            ).scalar_one()
        await drive(engine_engine, owner, cancellation)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            cleanup = (await session.execute("SELECT id FROM risk_stop_requests")).scalar_one()
            await consume_stop(session, cleanup)
            canceled_id = (
                await session.execute(
                    "SELECT id FROM paper_order_events WHERE event_kind='CANCELED'"
                )
            ).scalar_one()
            canceled = await next_paper_feedback(
                session, run, input_identity=f"order:{canceled_id}"
            )
            assert canceled is not None and canceled.value.status is not None
            assert canceled.value.status.value == "CANCELED"
            assert canceled.value.execution is None
        async with user_session(api_engine, owner) as session:
            stopped = await read_status(session, TradingMode.PAPER)
            assert stopped.stop_id is not None
        assert (
            await prove_bot_strategy_recovery(
                engine=engine_engine,
                owner=owner,
                run_id=run,
                stop_id=stopped.stop_id,
                registry=registry(broken),
                worker_id=worker,
            )
            is None
        )
        assert broken.observed[-1] == (failed_input, status)
        assert len(broken.observed) == 2
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            assert (
                await session.execute("SELECT count(*) FROM bot_resume_proofs")
            ).scalar_one() == 0
        assert (
            await prove_bot_strategy_recovery(
                engine=engine_engine,
                owner=owner,
                run_id=run,
                stop_id=stopped.stop_id,
                registry=registry(healthy),
                worker_id=worker,
            )
            is not None
        )
        assert healthy.observed[-1] == (failed_input, status)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            assert (await session.execute("SELECT status FROM bot_runs")).scalar_one() == "STOPPED"
            assert (await session.execute("SELECT count(*) FROM bot_decisions")).scalar_one() == (
                4 if partial else 2
            )
            assert (
                await session.execute("SELECT count(*) FROM paper_order_commands")
            ).scalar_one() == 2
            assert (
                await session.execute("SELECT count(*) FROM paper_position_events")
            ).scalar_one() == int(partial)
            assert (
                await session.execute(
                    "SELECT count(*) FROM paper_reservations "
                    "WHERE quote_reserved<>0 OR base_reserved<>0"
                )
            ).scalar_one() == 0
            current = await get_wallet(session)
            assert current is not None and current.balance == (
                wallet.balance - Money.of(40, "USDT") if partial else wallet.balance
            )
            if partial:
                assert Quantity.of(
                    (
                        await session.execute(
                            "SELECT held_quantity FROM paper_position_projections"
                        )
                    ).scalar_one(),
                    "BTC",
                ) == Quantity.of("0.3996", "BTC")
            assert (
                await session.execute("SELECT status FROM paper_order_projections")
            ).scalar_one() == "CANCELED"


@pytest.mark.parametrize("unavailable", ["pending-command", "order-source"])
@pytest.mark.parametrize("new_quote", [False, True], ids=["duplicate-quote", "new-quote"])
async def test_same_lease_paused_run_reconciles_before_readiness_or_new_decision(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    unavailable: str,
    new_quote: bool,
) -> None:
    worker = uuid4()
    executable = registry()
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000", account_use="BOT"
    ) as sources:
        run = await seed_input_run(engine_engine, owner, wallet)
        first = await run_bot_quote(
            engine=engine_engine, owner=owner, run_id=run, registry=executable, worker_id=worker
        )
        assert first is not None
        await _set_admission_enabled(migrator_engine, enabled=False)
        assert (
            await run_bot_quote(
                engine=engine_engine, owner=owner, run_id=run, registry=executable, worker_id=worker
            )
            is None
        )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            assert (await session.execute("SELECT status FROM bot_runs")).scalar_one() == "PAUSED"
            before = (await session.execute("SELECT revision FROM bot_runs")).scalar_one()
            if unavailable == "pending-command":
                pending = await submit_order(
                    session,
                    wallet_id=wallet.wallet_id,
                    intent=replace(intent(owner, wallet.episode_id), origin=OrderOrigin.BOT),
                )
            else:
                await _set_order_source_ready(session, ready=False)
        await _set_admission_enabled(migrator_engine, enabled=True)
        if new_quote:
            await sources.price("101")
        assert (
            await run_bot_quote(
                engine=engine_engine, owner=owner, run_id=run, registry=executable, worker_id=worker
            )
            is None
        )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            row = (await session.execute("SELECT status,revision FROM bot_runs")).one()
            assert tuple(row) == ("PAUSED", before)
            lease = (await session.execute("SELECT worker_id,generation FROM bot_run_leases")).one()
            assert lease.worker_id == worker and lease.generation == 1
            assert (await session.execute("SELECT count(*) FROM bot_decisions")).scalar_one() == 1
            assert (
                await session.execute("SELECT count(*) FROM paper_order_commands")
            ).scalar_one() == int(unavailable == "pending-command")
            assert (await session.execute("SELECT count(*) FROM paper_orders")).scalar_one() == 0
            assert (
                await session.execute("SELECT count(*) FROM paper_reservations")
            ).scalar_one() == 0
            assert (
                await session.execute("SELECT count(*) FROM paper_position_events")
            ).scalar_one() == 0
            current = await get_wallet(session)
            assert current is not None and current.balance == wallet.balance
        if unavailable == "pending-command":
            # The real worker rejects this unlinked fixture BOT command. Only
            # after its durable outcome exists may the paused run become ready.
            await drive(engine_engine, owner, pending.command_id)
        else:
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                await _set_order_source_ready(session, ready=True)
        result = await run_bot_quote(
            engine=engine_engine, owner=owner, run_id=run, registry=executable, worker_id=worker
        )
        assert result is not None and (result != first) is new_quote
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            assert (await session.execute("SELECT status FROM bot_runs")).scalar_one() == "RUNNING"
            assert (
                await session.execute("SELECT count(*) FROM bot_decisions")
            ).scalar_one() == 1 + int(new_quote)


@pytest.mark.parametrize("unavailable", ["protocol", "market", "order-source"])
async def test_control_created_starting_run_pauses_with_a_reason_when_readiness_disappears(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    unavailable: str,
) -> None:
    executable = registry()
    worker = uuid4()
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000", account_use="BOT"
    ) as sources:
        key = uuid4()
        async with user_session(api_engine, owner) as session:
            await submit_start(
                session,
                mode=TradingMode.PAPER,
                request_id=uuid4(),
                key=key,
                payload={"strategy_config_ref": "fixture-v1"},
            )
        await run_bot_control_round(
            engine=engine_engine, scan_engine=scan_engine, registry=executable
        )
        async with user_session(api_engine, owner) as session:
            result = await receipt_by_key(session, TradingMode.PAPER, key)
            assert result is not None and result.run_id is not None
            run = result.run_id
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            assert (await session.execute("SELECT status FROM bot_runs")).scalar_one() == "STARTING"
        if unavailable == "protocol":
            await _set_admission_enabled(migrator_engine, enabled=False)
        elif unavailable == "order-source":
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                await _set_order_source_ready(session, ready=False)
        else:
            async with market_data_session(sources.market) as session:
                market = await read_snapshot(session)
                assert market.feed is not None
                lease = await renew_writer(session, market.feed)
                await set_connected(session, lease, False)
        assert (
            await run_bot_quote(
                engine=engine_engine, owner=owner, run_id=run, registry=executable, worker_id=worker
            )
            is None
        )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            assert (await session.execute("SELECT status FROM bot_runs")).scalar_one() == "PAUSED"
            assert (
                await session.execute(
                    "SELECT details->>'reason' FROM bot_run_events WHERE event='SOURCE_NOT_READY'"
                )
            ).scalar_one() == {
                "protocol": "BOT_ACCOUNT_NOT_READY",
                "market": "MARKET_NOT_READY",
                "order-source": "ACCOUNT_NOT_READY",
            }[unavailable]
            for table in (
                "bot_decisions",
                "paper_order_commands",
                "paper_orders",
                "paper_reservations",
                "paper_position_events",
            ):
                assert (await session.execute(f"SELECT count(*) FROM {table}")).scalar_one() == 0
        if unavailable == "protocol":
            await _set_admission_enabled(migrator_engine, enabled=True)
        elif unavailable == "order-source":
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                await _set_order_source_ready(session, ready=True)
        else:
            async with market_data_session(sources.market) as session:
                market = await read_snapshot(session)
                assert market.feed is not None
                lease = await renew_writer(session, market.feed)
                await set_connected(session, lease, True)
            await sources.price("101")
        assert (
            await run_bot_quote(
                engine=engine_engine, owner=owner, run_id=run, registry=executable, worker_id=worker
            )
            is not None
        )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            assert (await session.execute("SELECT status FROM bot_runs")).scalar_one() == "RUNNING"
            assert (await session.execute("SELECT count(*) FROM bot_decisions")).scalar_one() == 1
            current = await get_wallet(session)
            assert current is not None and current.balance == wallet.balance
