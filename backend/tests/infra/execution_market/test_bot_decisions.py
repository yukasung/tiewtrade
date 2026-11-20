"""Bot decision and Paper command rollback on the real shared database."""

import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market.test_dispatch import intent
from tests.infra.execution_market.test_worker import AllowPolicy
from tests.infra.manual_orders.test_bridge import select_use
from tests.infra.risk_limits.test_execution import drive, runtime
from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.orders import (
    BaseSize,
    OrderConflictError,
    OrderIntent,
    OrderOrigin,
    OrderType,
    SafetyUnavailableError,
    TimeInForce,
)
from tiewtrade.core.protections import ProtectionPrices
from tiewtrade.core.strategies import StrategyDecision, StrategyDocument, document_payload
from tiewtrade.infra.bots.decisions import (
    BotDecisionConflictError,
    EvaluatedDecision,
    record_paper_decision,
)
from tiewtrade.infra.bots.feedback import next_paper_feedback
from tiewtrade.infra.bots.paper_admission import admit_paper_bot_intent
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.db.session import UserSession
from tiewtrade.infra.paper_orders.dispatch import (
    DueOrder,
    claim_order,
    get_order_command,
    submit_order,
)
from tiewtrade.infra.paper_orders.worker import process_claimed_order
from tiewtrade.infra.paper_wallet import get_wallet
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot
from tiewtrade.infra.protections import worker as protection_worker
from tiewtrade.infra.protections.storage import load, save


async def seed_run(
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    run_id: UUID,
    initial: StrategyDocument,
) -> None:
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await session.execute(
            """INSERT INTO bot_runs(id,user_id,mode,wallet_id,episode_id,strategy_name,
                strategy_version,configuration_version,state_version,configuration,strategy_state,status)
            VALUES(:id,:owner,'PAPER',:wallet,:episode,'fixture',
                1,1,1,CAST(:state AS jsonb),CAST(:state AS jsonb),'RUNNING')""",
            {
                "id": run_id,
                "owner": owner,
                "wallet": UUID(str(wallet.wallet_id)),
                "episode": UUID(str(wallet.episode_id)),
                "state": json.dumps(document_payload(initial)),
            },
        )


async def test_bot_decision_and_command_are_atomic_and_replay_once(
    engine_engine: AsyncEngine, api_engine: AsyncEngine, owner: UUID, wallet: PaperWalletSnapshot
) -> None:
    await select_use(api_engine, owner, "BOT")
    run_id = uuid4()
    initial = StrategyDocument(1, ())
    checkpoint = StrategyDocument(1, (("evaluated", True),))
    first = replace(intent(owner, wallet.episode_id), origin=OrderOrigin.BOT)
    second = replace(intent(owner, wallet.episode_id), origin=OrderOrigin.BOT)
    evaluated = EvaluatedDecision(
        run_id,
        uuid4(),
        "fixture-input",
        1,
        1,
        1,
        initial,
        StrategyDecision(checkpoint, (first, second)),
    )

    async def admit(session: UserSession, wallet_id: UUID, value: OrderIntent) -> UUID:
        command = await submit_order(session, wallet_id=wallet_id, intent=value)
        return command.command_id

    async def fail_second(session: UserSession, wallet_id: UUID, value: OrderIntent) -> UUID:
        if value == second:
            raise BotDecisionConflictError("simulated failure after first command")
        return await admit(session, wallet_id, value)

    await seed_run(engine_engine, owner, wallet, run_id, initial)
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        with pytest.raises(BotDecisionConflictError, match="simulated failure"):
            await record_paper_decision(session, evaluated, admit=fail_second)
        assert (
            await session.execute("SELECT count(*) FROM paper_order_commands")
        ).scalar_one() == 0
        assert (await session.execute("SELECT count(*) FROM bot_decisions")).scalar_one() == 0
        assert (await session.execute("SELECT revision FROM bot_runs")).scalar_one() == 1
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        assert await record_paper_decision(session, evaluated, admit=admit) == evaluated.decision_id
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        replay = replace(evaluated, decision_id=uuid4())
        assert (
            await record_paper_decision(session, replay, admit=fail_second) == evaluated.decision_id
        )
        assert (
            await session.execute("SELECT count(*) FROM paper_order_commands")
        ).scalar_one() == 2
        assert (await session.execute("SELECT count(*) FROM bot_order_links")).scalar_one() == 2
        assert (await session.execute("SELECT count(*) FROM bot_run_events")).scalar_one() == 1
        assert (await session.execute("SELECT revision FROM bot_runs")).scalar_one() == 2

    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await session.execute("UPDATE bot_runs SET status='STOPPED' WHERE id=:id", {"id": run_id})
        link = (
            await session.execute(
                "SELECT command_id FROM bot_order_links WHERE decision_id=:id AND ordinal=0",
                {"id": evaluated.decision_id},
            )
        ).scalar_one()
        due = (
            await session.execute(
                """UPDATE paper_order_dispatch SET next_attempt_at=clock_timestamp()
            WHERE command_id=:id RETURNING next_attempt_at""",
                {"id": link},
            )
        ).scalar_one()
        claimed = await claim_order(session, DueOrder(link, owner, due), worker="bot-stop-race")
        assert claimed is not None
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await process_claimed_order(session, claimed, policy=AllowPolicy())
        result = await get_order_command(session, link)
        assert result is not None and result.failure_code == "ORDER_SAFETY_UNAVAILABLE"
        assert (await session.execute("SELECT count(*) FROM paper_orders")).scalar_one() == 0
        assert (await session.execute("SELECT count(*) FROM paper_reservations")).scalar_one() == 0


async def test_active_slot_serializes_concurrent_starts_and_is_scoped_by_mode(
    engine_engine: AsyncEngine, owner: UUID, wallet: PaperWalletSnapshot
) -> None:
    async def insert(*, live: bool = False, base: str = "BTC") -> UUID | None:
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            value = await session.execute(
                """INSERT INTO bot_runs(id,user_id,mode,wallet_id,episode_id,strategy_name,
                    strategy_version,configuration_version,state_version,configuration,
                    strategy_state,status)
                VALUES(:id,:owner,:mode,:wallet,:episode,'fixture',1,1,1,
                       jsonb_build_object('base',CAST(:base AS text)),'{}','STARTING')
                ON CONFLICT (user_id,mode) WHERE status <> 'RETIRED'
                DO NOTHING RETURNING id""",
                {
                    "id": uuid4(),
                    "owner": owner,
                    "mode": "LIVE" if live else "PAPER",
                    "base": base,
                    "wallet": None if live else wallet.wallet_id,
                    "episode": None if live else wallet.episode_id,
                },
            )
            row = value.one_or_none()
            return None if row is None else UUID(str(row.id))

    async with asyncio.timeout(10):
        outcomes = await asyncio.gather(insert(base="BTC"), insert(base="ETH"))
    assert sum(run is not None for run in outcomes) == 1
    assert await insert(live=True) is not None
    assert await insert(live=True) is None
    # All three statuses keep the slot until the replacement transaction retires it.
    for state in ("PAUSED", "RECOVERING", "STOPPED"):
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await session.execute(
                "UPDATE bot_runs SET status=:state WHERE mode='PAPER'", {"state": state}
            )
        assert await insert() is None


async def test_unlinked_bot_command_cannot_create_order_or_reservation(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    await select_use(api_engine, owner, "BOT")
    value = replace(intent(owner, wallet.episode_id), origin=OrderOrigin.BOT)
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        command = await submit_order(session, wallet_id=wallet.wallet_id, intent=value)
        due = (
            await session.execute(
                """UPDATE paper_order_dispatch SET next_attempt_at=clock_timestamp()
                WHERE command_id=:id RETURNING next_attempt_at""",
                {"id": command.command_id},
            )
        ).scalar_one()
        claimed = await claim_order(
            session, DueOrder(command.command_id, owner, due), worker="unlinked-bot"
        )
        assert claimed is not None
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await process_claimed_order(session, claimed, policy=AllowPolicy())
        result = await get_order_command(session, command.command_id)
        assert result is not None and result.failure_code == "ORDER_SAFETY_UNAVAILABLE"
        assert (await session.execute("SELECT count(*) FROM paper_orders")).scalar_one() == 0
        assert (await session.execute("SELECT count(*) FROM paper_reservations")).scalar_one() == 0


async def test_bot_intake_requires_a_configured_loss_limit_before_queueing(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    value = replace(intent(owner, wallet.episode_id), origin=OrderOrigin.BOT)
    async with (
        runtime(
            api_engine, engine_engine, migrator_engine, owner, wallet, limit=None, account_use="BOT"
        ),
        user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session,
    ):
        with pytest.raises(OrderConflictError, match="optional loss limit applies only"):
            await admit_paper_bot_intent(session, wallet.wallet_id, value)
        assert (
            await session.execute("SELECT count(*) FROM paper_order_commands")
        ).scalar_one() == 0


@pytest.fixture
async def bot_bracket_protocol(migrator_engine: AsyncEngine) -> AsyncIterator[None]:
    async with migrator_engine.begin() as connection:
        await connection.execute(text("UPDATE paper_protection_protocol SET enabled=true"))
    try:
        yield
    finally:
        async with migrator_engine.begin() as connection:
            await connection.execute(text("UPDATE paper_protection_protocol SET enabled=false"))


@pytest.mark.parametrize(
    "partial,setup_failure",
    [(False, False), (True, False), (False, True)],
    ids=["full", "partial", "setup-failure"],
)
async def test_authorized_bot_decision_reaches_real_paper_financial_writer(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    bot_bracket_protocol: None,
    scan_engine: AsyncEngine,
    partial: bool,
    setup_failure: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_id = uuid4()
    initial = StrategyDocument(1, ())
    value = replace(intent(owner, wallet.episode_id), origin=OrderOrigin.BOT)
    evaluated = EvaluatedDecision(
        run_id,
        uuid4(),
        "risk-ready",
        1,
        1,
        1,
        initial,
        StrategyDecision(
            initial,
            (value,),
            ((value.order_id, ProtectionPrices(value.pair, stop_loss=Money.of("90", "USDT"))),),
        ),
    )
    async with runtime(
        api_engine,
        engine_engine,
        migrator_engine,
        owner,
        wallet,
        limit="1000",
        account_use="BOT",
    ) as sources:
        await seed_run(engine_engine, owner, wallet, run_id, initial)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await record_paper_decision(session, evaluated)
            command_id = (
                await session.execute(
                    "SELECT command_id FROM bot_order_links WHERE decision_id=:id",
                    {"id": evaluated.decision_id},
                )
            ).scalar_one()
        await drive(engine_engine, owner, command_id)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            group = (
                await session.execute(
                    """SELECT state,quantity,entry_request_id FROM paper_protections
                       WHERE entry_bot_command_id=:id""",
                    {"id": command_id},
                )
            ).one()
            assert group.state == "WAITING_ENTRY" and group.entry_request_id is None
            assert Quantity.of(group.quantity, "BTC") == Quantity.of(0, "BTC")
        # Existing F-15 eligibility boundary. Receipt records admission while
        # the next market input drives the matching projection and ledger.
        await asyncio.sleep(0.12)
        if partial:
            first_ask = replace(sources.book.asks[0], quantity=Quantity.of("0.4", "BTC"))
            sources.book = replace(sources.book, asks=(first_ask,))
        await sources.next_book()
        await drive(engine_engine, owner, command_id)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            command = await get_order_command(session, command_id)
            assert command is not None and command.failure_code is None
            assert (
                await session.execute(
                    "SELECT status FROM paper_order_projections WHERE order_id=:id",
                    {"id": value.order_id},
                )
            ).scalar_one() == ("EXPIRED" if partial else "FILLED")
            assert (
                await session.execute("SELECT count(*) FROM paper_position_events")
            ).scalar_one() == 1
            after = await get_wallet(session)
            assert after is not None and after.balance == wallet.balance - Money.of(
                "40" if partial else "100", "USDT"
            )
            assert (
                await session.execute(
                    "SELECT count(*) FROM paper_reservations "
                    "WHERE quote_reserved<>0 OR base_reserved<>0"
                )
            ).scalar_one() == 0
            protected = (
                await session.execute(
                    "SELECT quantity FROM paper_protections WHERE entry_bot_command_id=:id",
                    {"id": command_id},
                )
            ).scalar_one()
            assert Quantity.of(protected, "BTC") == Quantity.of(
                "0.3996" if partial else "0.999", "BTC"
            )
            accepted_feedback = await next_paper_feedback(session, run_id)
            assert accepted_feedback is not None
            assert accepted_feedback.value.status is not None
            assert accepted_feedback.value.status.value == "ACCEPTED"
            await record_paper_decision(
                session,
                EvaluatedDecision(
                    run_id,
                    uuid4(),
                    accepted_feedback.input_identity,
                    2,
                    1,
                    1,
                    initial,
                    StrategyDecision(initial),
                ),
            )
            fill_feedback = await next_paper_feedback(session, run_id)
            assert fill_feedback is not None and fill_feedback.value.execution is not None
            assert fill_feedback.value.execution.gross_quantity == Quantity.of(
                "0.4" if partial else "1", "BTC"
            )
            filled_state = StrategyDocument(1, (("fill_seen", True),))
            fill_decision = uuid4()
            await record_paper_decision(
                session,
                EvaluatedDecision(
                    run_id,
                    fill_decision,
                    fill_feedback.input_identity,
                    3,
                    1,
                    1,
                    initial,
                    StrategyDecision(filled_state),
                ),
            )
            # A lost acknowledgement and an older event must resolve the same
            # receipt without restoring the pre-fill strategy checkpoint.
            assert (
                await record_paper_decision(
                    session,
                    EvaluatedDecision(
                        run_id,
                        uuid4(),
                        accepted_feedback.input_identity,
                        2,
                        1,
                        1,
                        initial,
                        StrategyDecision(initial),
                    ),
                )
                is not None
            )
            assert (
                await session.execute("SELECT strategy_state FROM bot_runs")
            ).scalar_one() == document_payload(filled_state)
            terminal = await next_paper_feedback(session, run_id)
            assert terminal is not None and terminal.value.status is not None
            assert terminal.value.status.value == ("EXPIRED" if partial else "FILLED")
            assert terminal.value.revision > fill_feedback.value.revision
            terminal_state = StrategyDocument(1, (("terminal", terminal.value.status.value),))
            await record_paper_decision(
                session,
                EvaluatedDecision(
                    run_id,
                    uuid4(),
                    terminal.input_identity,
                    4,
                    1,
                    1,
                    filled_state,
                    StrategyDecision(terminal_state),
                ),
            )
            assert (
                await record_paper_decision(
                    session,
                    EvaluatedDecision(
                        run_id,
                        uuid4(),
                        fill_feedback.input_identity,
                        3,
                        1,
                        1,
                        initial,
                        StrategyDecision(initial),
                    ),
                )
                == fill_decision
            )
            assert (
                await session.execute("SELECT strategy_state FROM bot_runs")
            ).scalar_one() == document_payload(terminal_state)
            assert await next_paper_feedback(session, run_id) is None
            assert (
                await session.execute("SELECT count(*) FROM paper_position_events")
            ).scalar_one() == 1
        if not partial and not setup_failure:
            from tiewtrade.services.engine.bot import StrategyRegistry, run_bot_quote
            from tiewtrade.services.engine.kill_switch import run_stop_request_round
            from tiewtrade.services.engine.risk_limit import run_risk_stop_round

            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                # This older financial-writer fixture bypasses start intake. Supply
                # its pinned entry fact before exercising the lifecycle evaluator.
                await session.execute(
                    """INSERT INTO bot_run_events(id,run_id,user_id,mode,revision,event,details)
                    VALUES(:id,:run,:owner,'PAPER',1,'START_REQUEST_APPLIED',
                      jsonb_build_object('base','BTC','quote','USDT','catalog_revision',
                        (SELECT current_revision FROM supported_symbol_catalog_control)))""",
                    {"id": uuid4(), "run": run_id, "owner": owner},
                )
                protected_before = (
                    await session.execute("SELECT document FROM paper_protections")
                ).scalar_one()
                held_before = (
                    await session.execute("SELECT held_quantity FROM paper_position_projections")
                ).scalar_one()
            assert (
                await run_bot_quote(
                    engine=engine_engine,
                    owner=owner,
                    run_id=run_id,
                    registry=StrategyRegistry(),
                    worker_id=uuid4(),
                )
                is None
            )
            await run_stop_request_round(engine=engine_engine, scan_engine=scan_engine)
            await run_risk_stop_round(engine=engine_engine, scan_engine=scan_engine)
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                assert (
                    await session.execute("SELECT status FROM bot_runs")
                ).scalar_one() == "STOPPED"
                assert (
                    await session.execute("SELECT document FROM paper_protections")
                ).scalar_one() == protected_before
                assert (
                    await session.execute("SELECT held_quantity FROM paper_position_projections")
                ).scalar_one() == held_before
                unchanged = await get_wallet(session)
                assert unchanged is not None and after is not None
                assert unchanged.balance == after.balance
                assert (
                    await session.execute("SELECT count(*) FROM paper_order_commands")
                ).scalar_one() == 1
        if setup_failure:
            exit_id = await exhaust_bot_protection_setup(
                engine_engine, owner, command_id, monkeypatch
            )
            await drive(engine_engine, owner, exit_id)
            await asyncio.sleep(0.12)
            await sources.next_book()
            await drive(engine_engine, owner, exit_id)
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                group_id = (
                    await session.execute(
                        "SELECT id FROM paper_protections WHERE entry_bot_command_id=:id",
                        {"id": command_id},
                    )
                ).scalar_one()
                await protection_worker.process_group(session, group_id)
                group_after = await load(session, group_id)
                assert group_after is not None
                assert group_after.value.state.value == "CLOSED"
                assert group_after.value.quantity == Quantity.of(0, "BTC")
                assert (
                    await session.execute("SELECT count(*) FROM paper_protection_exits")
                ).scalar_one() == 1


async def exhaust_bot_protection_setup(
    engine: AsyncEngine, owner: UUID, command_id: UUID, monkeypatch: pytest.MonkeyPatch
) -> UUID:
    async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
        group_id = (
            await session.execute(
                "SELECT id FROM paper_protections WHERE entry_bot_command_id=:id",
                {"id": command_id},
            )
        ).scalar_one()
        group = await load(session, group_id)
        assert group is not None and group.value.state.value == "ARMING"
        # Enter the final approved attempt directly. Existing F-17 tests cover 1/2/4s delays.
        await save(
            session,
            group,
            replace(group.value, revision=group.value.revision + 1, setup_attempt=4),
            kind="RETRY",
        )

    async def fail_setup(*args: object, **kwargs: object) -> Quantity:
        raise SafetyUnavailableError("test setup failure")

    with monkeypatch.context() as patch:
        patch.setattr(protection_worker, "_validate_market_setup", fail_setup)
        async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
            await protection_worker.process_group(session, group_id)
            assert (await session.execute("SELECT status FROM bot_runs")).scalar_one() == "STOPPED"
            stop = (
                await session.execute("SELECT cause,reason_code FROM trading_stop_requests")
            ).one()
            assert tuple(stop) == ("SYSTEM", "PROTECTION_SETUP_FAILED")
            pending = await load(session, group_id)
            assert pending is not None and pending.value.setup_failed_exit
            assert pending.extra_exit == Quantity.of("0.999", "BTC")
            assert (
                await session.execute("SELECT count(*) FROM paper_protection_exits")
            ).scalar_one() == 0
    async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
        await protection_worker.process_group(session, group_id)
        await protection_worker.process_group(session, group_id)
        row = (
            await session.execute("SELECT command_id,quantity FROM paper_protection_exits")
        ).one()
        assert Quantity.of(row.quantity, "BTC") == Quantity.of("0.999", "BTC")
        return UUID(str(row.command_id))


async def test_f19_user_stop_persists_the_bot_run_transition(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    from tiewtrade.core.orders import TradingMode
    from tiewtrade.core.trading_stops import StopAction
    from tiewtrade.infra.trading_stops import read_status, submit_request
    from tiewtrade.services.engine.kill_switch import run_stop_request_round
    from tiewtrade.services.engine.risk_limit import run_risk_stop_round

    await select_use(api_engine, owner, "BOT")
    await seed_run(engine_engine, owner, wallet, uuid4(), StrategyDocument(1, ()))
    async with user_session(api_engine, owner) as session:
        receipt = await submit_request(
            session,
            mode=TradingMode.PAPER,
            action=StopAction.STOP,
            key=uuid4(),
            reason_code="USER_STOP",
        )
    await run_stop_request_round(engine=engine_engine, scan_engine=scan_engine)
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        status = (await session.execute("SELECT status FROM bot_runs")).scalar_one()
        assert status == "STOPPED"
        event = (
            await session.execute(
                "SELECT details->>'stop_id',details->>'cause' FROM bot_run_events"
            )
        ).one()
        assert tuple(event) == (str(receipt.stop_id), "USER")
    await run_risk_stop_round(engine=engine_engine, scan_engine=scan_engine, limit=20)
    async with user_session(api_engine, owner) as session:
        summary = await read_status(session, TradingMode.PAPER)
        assert summary.resume_ready and summary.reconciliation_revision is not None
        await submit_request(
            session,
            mode=TradingMode.PAPER,
            action=StopAction.RESUME,
            key=uuid4(),
            expected_stop_id=receipt.stop_id,
            expected_revision=receipt.revision,
            expected_summary_revision=summary.summary_revision,
            expected_reconciliation_revision=summary.reconciliation_revision,
            reason_code="USER_RESUME",
        )
    await run_stop_request_round(engine=engine_engine, scan_engine=scan_engine)
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        assert (await session.execute("SELECT status FROM bot_runs")).scalar_one() == "RECOVERING"


async def test_claimed_start_pins_configuration_before_evaluation(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    from tiewtrade.core.orders import TradingMode
    from tiewtrade.core.positions import PositionPair
    from tiewtrade.core.strategies import StrategyDescriptor, StrategyInput
    from tiewtrade.core.trading_stops import StopAction
    from tiewtrade.infra.bots.requests import receipt_by_key, submit_start
    from tiewtrade.infra.bots.start import PublishedConfiguration
    from tiewtrade.infra.trading_stops import read_status
    from tiewtrade.infra.trading_stops import submit_request as submit_stop
    from tiewtrade.services.engine.bot import (
        PublishedStrategy,
        StrategyRegistry,
        run_bot_control_round,
        run_bot_quote,
        run_bot_worker_round,
    )
    from tiewtrade.services.engine.kill_switch import run_stop_request_round
    from tiewtrade.services.engine.risk_limit import run_risk_stop_round

    pair = PositionPair("BTC", "USDT")
    definition = PublishedConfiguration(
        "test-v1",
        StrategyDescriptor(
            "test", 1, 2, 1, frozenset({pair}), None, frozenset(), False, quote_trigger=True
        ),
        pair,
        StrategyDocument(2, (("size", Money.of("25.00000001", "USDT")),)),
        StrategyDocument(1, ()),
    )

    class FixtureStrategy:
        descriptor = definition.descriptor

        def evaluate(
            self, snapshot: StrategyInput, configuration: StrategyDocument, state: StrategyDocument
        ) -> StrategyDecision:
            return StrategyDecision(StrategyDocument(1, (("evaluated", True),)))

    registered = FixtureStrategy()
    registry = StrategyRegistry((PublishedStrategy(definition, registered),))
    assert (
        registry.implementation("test", 1, configuration_version=2, state_version=1) is registered
    )
    assert registry.implementation("test", 2, configuration_version=2, state_version=1) is None
    assert registry.implementation("test", 1, configuration_version=1, state_version=1) is None
    async with runtime(
        api_engine,
        engine_engine,
        migrator_engine,
        owner,
        wallet,
        limit="1000",
        account_use="BOT",
    ) as sources:
        async with user_session(api_engine, owner) as session:
            receipt = await submit_start(
                session,
                mode=TradingMode.PAPER,
                request_id=uuid4(),
                key=uuid4(),
                payload={"strategy_config_ref": definition.reference},
            )
            unknown = await submit_start(
                session,
                mode=TradingMode.PAPER,
                request_id=uuid4(),
                key=uuid4(),
                payload={"strategy_config_ref": "removed-version"},
            )
        await run_bot_control_round(
            engine=engine_engine, scan_engine=scan_engine, registry=registry
        )
        await run_bot_control_round(
            engine=engine_engine, scan_engine=scan_engine, registry=registry
        )
        async with user_session(api_engine, owner) as session:
            applied = await receipt_by_key(session, TradingMode.PAPER, receipt.key)
            refused = await receipt_by_key(session, TradingMode.PAPER, unknown.key)
            assert applied is not None and applied.run_id is not None
            assert refused is not None and refused.failure_code == "BOT_STRATEGY_UNAVAILABLE"
            run_id = applied.run_id
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            row = (
                await session.execute(
                    "SELECT status,configuration,episode_id FROM bot_runs WHERE id=:id",
                    {"id": run_id},
                )
            ).one()
            assert row.status == "STARTING"
            assert row.configuration == document_payload(definition.configuration)
            assert row.episode_id == wallet.episode_id
        async with user_session(api_engine, owner) as session:
            result = await receipt_by_key(session, TradingMode.PAPER, receipt.key)
            assert result is not None and result.run_id == run_id
        worker = uuid4()
        cursor = None
        evaluated = 0
        while True:
            round_result = await run_bot_worker_round(
                engine=engine_engine,
                scan_engine=scan_engine,
                registry=registry,
                cursor=cursor,
                worker_id=worker,
            )
            evaluated += round_result.evaluated
            cursor = round_result.next_cursor
            if cursor is None:
                break
        # Sweep bounded pages, including retained fixtures of other owners.
        # Exact financial/decision assertions below stay under owner RLS.
        assert evaluated >= 1
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            decision = (await session.execute("SELECT id FROM bot_decisions")).scalar_one()
        assert decision is not None
        assert (
            await run_bot_quote(
                engine=engine_engine,
                owner=owner,
                run_id=run_id,
                registry=registry,
                worker_id=worker,
            )
            == decision
        )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            assert (await session.execute("SELECT status FROM bot_runs")).scalar_one() == "RUNNING"
            assert (await session.execute("SELECT count(*) FROM bot_decisions")).scalar_one() == 1
        async with migrator_engine.begin() as connection:
            await connection.execute(
                text("UPDATE risk_protocol_control SET admission_enabled=false")
            )
        assert (
            await run_bot_quote(
                engine=engine_engine,
                owner=owner,
                run_id=run_id,
                registry=registry,
                worker_id=worker,
            )
            is None
        )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            assert (await session.execute("SELECT status FROM bot_runs")).scalar_one() == "PAUSED"
        async with migrator_engine.begin() as connection:
            await connection.execute(
                text("UPDATE risk_protocol_control SET admission_enabled=true")
            )
        assert (
            await run_bot_quote(
                engine=engine_engine,
                owner=owner,
                run_id=run_id,
                registry=registry,
                worker_id=worker,
            )
            == decision
        )
        replacement_worker = uuid4()
        assert (
            await run_bot_quote(
                engine=engine_engine,
                owner=owner,
                run_id=run_id,
                registry=registry,
                worker_id=replacement_worker,
            )
            is None
        )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await session.execute(
                """UPDATE bot_run_leases SET lease_until=clock_timestamp()-interval '1 second'
                WHERE run_id=:run""",
                {"run": run_id},
            )
        assert (
            await run_bot_quote(
                engine=engine_engine,
                owner=owner,
                run_id=run_id,
                registry=registry,
                worker_id=replacement_worker,
            )
            == decision
        )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            assert (
                await session.execute("SELECT generation FROM bot_run_leases")
            ).scalar_one() == 2
            assert (
                await session.execute(
                    "SELECT count(*) FROM bot_run_events WHERE event='WORKER_TAKEOVER'"
                )
            ).scalar_one() == 1
        assert (
            await run_bot_quote(
                engine=engine_engine,
                owner=owner,
                run_id=run_id,
                registry=registry,
                worker_id=worker,
            )
            is None
        )
        worker = replacement_worker
        # Simulate a replacement process deployed without the pinned implementation.
        assert (
            await run_bot_quote(
                engine=engine_engine,
                owner=owner,
                run_id=run_id,
                registry=StrategyRegistry(),
                worker_id=worker,
            )
            is None
        )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            assert (await session.execute("SELECT status FROM bot_runs")).scalar_one() == "STOPPED"
            assert (await session.execute("SELECT count(*) FROM bot_decisions")).scalar_one() == 1
            reason = (
                await session.execute("SELECT reason_code FROM trading_stop_requests")
            ).scalar_one()
            assert reason == "STRATEGY_VERSION_UNAVAILABLE"
        await run_stop_request_round(engine=engine_engine, scan_engine=scan_engine)
        await run_risk_stop_round(engine=engine_engine, scan_engine=scan_engine, limit=20)
        async with user_session(api_engine, owner) as session:
            stopped = await read_status(session, TradingMode.PAPER)
            assert stopped.stop_id is not None and not stopped.resume_ready
        proof_round = await run_bot_worker_round(
            engine=engine_engine,
            scan_engine=scan_engine,
            registry=registry,
            cursor=None,
            worker_id=worker,
        )
        assert proof_round.recovery_proofs >= 1
        async with user_session(api_engine, owner) as session:
            ready = await read_status(session, TradingMode.PAPER)
            assert ready.resume_ready and ready.reconciliation_revision is not None
            await submit_stop(
                session,
                mode=TradingMode.PAPER,
                action=StopAction.RESUME,
                key=uuid4(),
                expected_stop_id=stopped.stop_id,
                expected_revision=ready.revision,
                expected_summary_revision=ready.summary_revision,
                expected_reconciliation_revision=ready.reconciliation_revision,
                reason_code="USER_RESUME",
            )
        await run_stop_request_round(engine=engine_engine, scan_engine=scan_engine)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            assert (
                await session.execute("SELECT status FROM bot_runs")
            ).scalar_one() == "RECOVERING"
            assert (await session.execute("SELECT count(*) FROM bot_decisions")).scalar_one() == 1
            assert (
                await session.execute("SELECT count(*) FROM paper_order_commands")
            ).scalar_one() == 0
        from tiewtrade.core.strategies import evaluate_strategy
        from tiewtrade.infra.bots.evaluation import (
            PreparedQuote,
            QuoteEvaluation,
            evaluate_published_quote,
        )

        await sources.price("101")
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            prepared = await evaluate_published_quote(
                session,
                run_id,
                resolve=registry.implementation,
                worker_id=worker,
            )
        assert isinstance(prepared, PreparedQuote)
        output = evaluate_strategy(
            prepared.strategy,
            prepared.snapshot,
            prepared.configuration,
            prepared.state,
            scope=prepared.scope,
        )
        # This independent transaction would block if preparation retained the
        # financial lock. The accepted cutoff invalidates the prepared decision.
        async with user_session(api_engine, owner) as session:
            await submit_stop(
                session,
                mode=TradingMode.PAPER,
                action=StopAction.STOP,
                key=uuid4(),
                reason_code="USER_STOP",
            )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            assert (
                await evaluate_published_quote(
                    session,
                    run_id,
                    resolve=registry.implementation,
                    worker_id=worker,
                    evaluation=QuoteEvaluation(prepared, output),
                )
                is None
            )
            assert (await session.execute("SELECT count(*) FROM bot_decisions")).scalar_one() == 1
            assert (
                await session.execute("SELECT count(*) FROM paper_order_commands")
            ).scalar_one() == 0


@pytest.mark.parametrize(
    "stale_summary,commit_fault",
    [(False, False), (True, False), (False, True)],
    ids=["atomic", "stale", "rollback-before-commit"],
)
async def test_replacement_consumes_f19_ack_without_restarting_the_old_run(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    stale_summary: bool,
    commit_fault: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tiewtrade.core.orders import TradingMode
    from tiewtrade.core.positions import PositionPair
    from tiewtrade.core.strategies import StrategyDescriptor, StrategyInput
    from tiewtrade.core.trading_stops import StopAction
    from tiewtrade.infra.bots.requests import receipt_by_key, submit_start
    from tiewtrade.infra.bots.start import PublishedConfiguration
    from tiewtrade.infra.trading_stops import read_status
    from tiewtrade.infra.trading_stops import submit_request as submit_stop
    from tiewtrade.services.engine.bot import (
        PublishedStrategy,
        StrategyRegistry,
        run_bot_control_round,
    )
    from tiewtrade.services.engine.kill_switch import run_stop_request_round
    from tiewtrade.services.engine.risk_limit import run_risk_stop_round

    pair = PositionPair("BTC", "USDT")
    initial = StrategyDocument(1, ())
    definition = PublishedConfiguration(
        "replacement",
        StrategyDescriptor("replacement", 1, 1, 1, frozenset({pair}), None, frozenset(), False),
        pair,
        initial,
        initial,
    )

    class StrategyFixture:
        descriptor = definition.descriptor

        def evaluate(
            self, snapshot: StrategyInput, configuration: StrategyDocument, state: StrategyDocument
        ) -> StrategyDecision:
            return StrategyDecision(state)

    registry = StrategyRegistry((PublishedStrategy(definition, StrategyFixture()),))
    old_run = uuid4()
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000", account_use="BOT"
    ):
        await seed_run(engine_engine, owner, wallet, old_run, initial)
        async with user_session(api_engine, owner) as session:
            stop = await submit_stop(
                session,
                mode=TradingMode.PAPER,
                action=StopAction.STOP,
                key=uuid4(),
                reason_code="USER_STOP",
            )
        await run_stop_request_round(engine=engine_engine, scan_engine=scan_engine)
        await run_risk_stop_round(engine=engine_engine, scan_engine=scan_engine, limit=20)
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
                    "strategy_config_ref": definition.reference,
                    "replacement": {
                        "run_id": str(old_run),
                        "run_revision": 2,
                        "stop_id": str(stop.stop_id),
                        "stop_revision": stop.revision,
                        "summary_revision": status.summary_revision + int(stale_summary),
                        "reconciliation_revision": status.reconciliation_revision,
                    },
                },
            )
        if commit_fault:
            from tiewtrade.infra.bots import start as start_storage
            from tiewtrade.infra.bots.claims import BotRequestClaim, finish_control

            finish = finish_control

            # Inject after the real result/audit write, within the same transaction.
            async def finishing(
                session: UserSession,
                claim: BotRequestClaim,
                *,
                run_id: UUID | None = None,
                failure_code: str | None = None,
            ) -> None:
                await finish(session, claim, run_id=run_id, failure_code=failure_code)
                raise RuntimeError("fixture rollback after replacement outcome")

            with monkeypatch.context() as patch:
                patch.setattr(start_storage, "finish_control", finishing)
                with pytest.raises(RuntimeError, match="rollback after replacement"):
                    await run_bot_control_round(
                        engine=engine_engine, scan_engine=scan_engine, registry=registry
                    )
            async with user_session(api_engine, owner) as session:
                pending = await receipt_by_key(session, TradingMode.PAPER, key)
                assert pending is not None and pending.pending
                assert (await read_status(session, TradingMode.PAPER)).stop_id == stop.stop_id
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                assert (
                    await session.execute("SELECT status FROM bot_runs")
                ).scalar_one() == "STOPPED"
                assert (
                    await session.execute(
                        "SELECT count(*) FROM trading_stop_requests WHERE action='RESUME'"
                    )
                ).scalar_one() == 0
                assert (
                    await session.execute(
                        "SELECT count(*) FROM bot_run_events WHERE event='RETIRED_FOR_REPLACEMENT'"
                    )
                ).scalar_one() == 0
                assert (
                    await session.execute("SELECT count(*) FROM paper_orders")
                ).scalar_one() == 0
                current = await get_wallet(session)
                assert current is not None and current.balance == wallet.balance
                await session.execute(
                    "UPDATE bot_control_dispatch "
                    "SET lease_until=clock_timestamp()-interval '1 second'"
                )
        await run_bot_control_round(
            engine=engine_engine, scan_engine=scan_engine, registry=registry
        )
        async with user_session(api_engine, owner) as session:
            finished = await receipt_by_key(session, TradingMode.PAPER, key)
            if stale_summary:
                assert finished is not None and finished.failure_code == "BOT_REPLACEMENT_NOT_READY"
                assert (await read_status(session, TradingMode.PAPER)).stop_id == stop.stop_id
            else:
                assert finished is not None and finished.run_id is not None
                assert (await read_status(session, TradingMode.PAPER)).stop_id is None
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            rows = (await session.execute("SELECT id,status FROM bot_runs")).all()
            expected = {old_run: "STOPPED" if stale_summary else "RETIRED"}
            if not stale_summary:
                assert finished.run_id is not None
                expected[finished.run_id] = "STARTING"
            assert {row.id: row.status for row in rows} == expected
            assert (
                await session.execute(
                    "SELECT count(*) FROM bot_run_events WHERE event='RESUME_RECONCILING'"
                )
            ).scalar_one() == 0
            assert (
                await session.execute(
                    """SELECT count(*) FROM trading_stop_dispatch d
                    JOIN trading_stop_requests r ON r.id=d.request_id WHERE r.action='RESUME'"""
                )
            ).scalar_one() == 0


async def test_paused_run_fences_accepted_buys_in_another_commands_pair_checkpoint(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    run_id = uuid4()
    initial = StrategyDocument(1, ())
    orders = tuple(
        replace(
            intent(owner, wallet.episode_id),
            origin=OrderOrigin.BOT,
            kind=OrderType.LIMIT,
            size=BaseSize(Quantity.of(1, "BTC")),
            limit_price=Money.of(90, "USDT"),
            time_in_force=TimeInForce.GTC,
        )
        for _ in range(2)
    )
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000", account_use="BOT"
    ) as sources:
        await seed_run(engine_engine, owner, wallet, run_id, initial)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await record_paper_decision(
                session,
                EvaluatedDecision(
                    run_id,
                    uuid4(),
                    "before-pause",
                    1,
                    1,
                    1,
                    initial,
                    StrategyDecision(initial, orders),
                ),
            )
            commands = tuple(
                (
                    await session.execute("SELECT command_id FROM bot_order_links ORDER BY ordinal")
                ).scalars()
            )
        for command in commands:
            await drive(engine_engine, owner, command)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await session.execute("UPDATE bot_runs SET status='PAUSED',revision=revision+1")
        await asyncio.sleep(0.12)
        sources.book = replace(
            sources.book,
            bids=(replace(sources.book.bids[0], price=Money.of(89, "USDT")),),
            asks=(
                replace(
                    sources.book.asks[0],
                    price=Money.of(90, "USDT"),
                    quantity=Quantity.of(10, "BTC"),
                ),
            ),
        )
        await sources.next_book()
        await drive(engine_engine, owner, commands[1])
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            assert (
                await session.execute("SELECT count(*) FROM paper_position_events")
            ).scalar_one() == 0
            assert (
                await session.execute(
                    "SELECT count(*) FROM paper_order_projections WHERE status='ACCEPTED'"
                )
            ).scalar_one() == 2
            balance = await get_wallet(session)
            assert balance is not None and balance.balance == wallet.balance
            assert (
                await session.execute(
                    "SELECT count(*) FROM paper_reservations WHERE quote_reserved>0"
                )
            ).scalar_one() == 2
            await session.execute("UPDATE bot_runs SET status='RUNNING',revision=revision+1")
        await sources.next_book()
        await drive(engine_engine, owner, commands[1])
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            assert (
                await session.execute("SELECT count(*) FROM paper_position_events")
            ).scalar_one() == 2
            balance = await get_wallet(session)
            assert balance is not None and balance.balance == wallet.balance - Money.of(180, "USDT")
