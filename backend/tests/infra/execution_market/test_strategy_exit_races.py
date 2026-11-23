"""Real F-21 writer ordering, delayed match and post-close correction regressions."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market.test_bot_decisions import (
    bot_bracket_protocol as bot_bracket_protocol,
)
from tests.infra.execution_market.test_dispatch import intent
from tests.infra.execution_market.test_strategy_baskets import (
    accounting_indicator_heads as accounting_indicator_heads,
)
from tests.infra.execution_market.test_strategy_baskets import (
    accounting_signal_proof,
    entry,
    f21_run,
    queue_entry,
    queue_entry_in_session,
)
from tests.infra.protections.test_lifecycle import single_fill, transfer
from tests.infra.risk_limits.test_execution import drive, runtime
from tests.strategies.fixtures import snapshot
from tests.strategies.test_rsi_step_grid import strategy
from tiewtrade.core.market_data import Timeframe, advance, align_floor
from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.orders import BaseSize, OrderConflictError
from tiewtrade.core.positions import ExecutionSide
from tiewtrade.core.strategies import document_from_payload
from tiewtrade.infra.bots.decisions import EvaluatedDecision, record_paper_decision
from tiewtrade.infra.bots.feedback import next_paper_feedback
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.db.session import UserSession
from tiewtrade.infra.paper_orders.corrections import correct_fill
from tiewtrade.infra.paper_orders.dispatch import ClaimedOrder, DueOrder, claim_order
from tiewtrade.infra.paper_orders.worker import process_claimed_order
from tiewtrade.infra.paper_wallet import get_wallet
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot
from tiewtrade.infra.positions import PositionEventKind
from tiewtrade.infra.protections.storage import load
from tiewtrade.infra.protections.worker import process_group
from tiewtrade.infra.risk_limits.policy import TransactionalRiskPolicy
from tiewtrade.services.engine.bot import StrategyRegistry, run_bot_quote
from tiewtrade.strategies.rsi_step_grid.strategy import initial_state

pytestmark = pytest.mark.usefixtures(
    "accounting_indicator_heads", "internal_database", "bot_bracket_protocol"
)


async def claim_match(engine: AsyncEngine, owner: UUID, command: UUID) -> ClaimedOrder:
    async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
        due = (
            await session.execute(
                "UPDATE paper_order_dispatch SET next_attempt_at=clock_timestamp() "
                "WHERE command_id=:id RETURNING next_attempt_at",
                {"id": command},
            )
        ).scalar_one()
        token = await claim_order(session, DueOrder(command, owner, due), worker="race-test")
        assert token is not None
        return token


async def ordered_writers(
    engine: AsyncEngine,
    owner: UUID,
    first: Callable[[UserSession], Awaitable[None]],
    second: Callable[[UserSession], Awaitable[None]],
    *,
    other_engine: AsyncEngine | None = None,
    first_role: DatabaseRole = DatabaseRole.ENGINE,
    second_role: DatabaseRole = DatabaseRole.ENGINE,
) -> None:
    pid = asyncio.get_running_loop().create_future()

    async def competing_writer() -> None:
        async with user_session(
            other_engine if other_engine is not None else engine, owner, role=second_role
        ) as session:
            pid.set_result((await session.execute("SELECT pg_backend_pid()")).scalar_one())
            await second(session)

    # Release the observed blocker before TaskGroup joins the second writer.
    async with (
        asyncio.timeout(8),
        asyncio.TaskGroup() as tasks,
        user_session(engine, owner, role=first_role) as session,
    ):
        await first(session)
        tasks.create_task(competing_writer())
        waiter = await pid
        while not (
            await session.execute(
                "SELECT pg_backend_pid()=ANY(pg_blocking_pids(:pid))", {"pid": waiter}
            )
        ).scalar_one():
            await asyncio.sleep(0.01)


@pytest.mark.parametrize("buy_first", [True, False], ids=["decision-first", "exit-first"])
async def test_buy_decision_and_exit_fill_serialize(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    buy_first: bool,
) -> None:
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000", account_use="BOT"
    ) as source:
        run = await f21_run(engine_engine, owner, wallet, timeframe=Timeframe.MN1)
        _, group = await entry(engine_engine, owner, wallet, run, source)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            protection = await load(session, group)
            assert protection is not None
        sale = replace(
            intent(owner, wallet.episode_id),
            side=ExecutionSide.SELL,
            size=BaseSize(Quantity.of("0.4", "BTC")),
        )
        sold = await transfer(
            api_engine,
            engine_engine,
            scan_engine,
            owner,
            wallet,
            sale,
            selections=(
                {
                    "protection_id": str(group),
                    "expected_revision": protection.value.revision,
                    "quantity": "0.4",
                },
            ),
        )
        await drive(engine_engine, owner, sold)
        await asyncio.sleep(0.12)
        await source.next_book()
        token = await claim_match(engine_engine, owner, sold)

        async def sell(session: UserSession) -> None:
            await process_claimed_order(session, token, policy=TransactionalRiskPolicy())

        opening = None

        async def buy(session: UserSession) -> None:
            nonlocal opening
            if buy_first:
                _, opening = await queue_entry_in_session(session, wallet, run)
            else:
                with pytest.raises(OrderConflictError, match="exit guard changed"):
                    await queue_entry_in_session(session, wallet, run)

        await ordered_writers(engine_engine, owner, *((buy, sell) if buy_first else (sell, buy)))
        if buy_first:
            assert opening is not None
            await drive(engine_engine, owner, opening)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            if buy_first:
                assert (
                    await session.execute(
                        "SELECT state FROM paper_order_command_results WHERE command_id=:id",
                        {"id": opening},
                    )
                ).scalar_one() == "REJECTED"
            assert (
                await session.execute("SELECT count(*) FROM bot_order_links")
            ).scalar_one() == 1 + int(buy_first)
            assert (await session.execute("SELECT count(*) FROM paper_orders")).scalar_one() == 2
            assert (
                await session.execute("SELECT count(*) FROM paper_position_events")
            ).scalar_one() == 2
            assert (
                await session.execute("SELECT guard_revision FROM bot_strategy_progress")
            ).scalar_one() == 1
            balance = await get_wallet(session)
            assert balance is not None and balance.balance == wallet.balance - Money.of(
                "60.4396", "USDT"
            )
            held = (
                await session.execute("SELECT held_quantity FROM paper_position_projections")
            ).scalar_one()
            assert Quantity.of(held, "BTC") == Quantity.of("0.599", "BTC")


@pytest.mark.parametrize("match_first", [True, False], ids=["buy-fill-first", "tp-first"])
async def test_delayed_buy_match_and_tp_share_one_winner(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    match_first: bool,
) -> None:
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000", account_use="BOT"
    ) as source:
        run = await f21_run(engine_engine, owner, wallet)
        _, first = await entry(engine_engine, owner, wallet, run, source)
        order, pending = await queue_entry(engine_engine, owner, wallet, run)
        await drive(engine_engine, owner, pending)
        await asyncio.sleep(0.12)
        await source.next_book()
        token = await claim_match(engine_engine, owner, pending)
        await source.price("107")

        async def match(session: UserSession) -> None:
            await process_claimed_order(session, token, policy=TransactionalRiskPolicy())

        async def trigger(session: UserSession) -> None:
            await process_group(session, first)

        await ordered_writers(
            engine_engine, owner, *((match, trigger) if match_first else (trigger, match))
        )
        await source.price("104")
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await process_group(session, first)
            cancel = (
                await session.execute(
                    "SELECT id FROM paper_order_commands WHERE action='CANCEL' AND order_id=:id",
                    {"id": order},
                )
            ).scalar_one()
        await drive(engine_engine, owner, cancel)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            assert (
                await session.execute(
                    "SELECT status FROM paper_order_projections WHERE order_id=:id", {"id": order}
                )
            ).scalar_one() == ("FILLED" if match_first else "CANCELED")
            n = 2 if match_first else 1
            assert (
                await session.execute("SELECT count(*) FROM bot_basket_triggers")
            ).scalar_one() == 1
            sizes = (
                (await session.execute("SELECT quantity FROM paper_protection_exits"))
                .scalars()
                .all()
            )
            assert len(sizes) == n and all(
                Quantity.of(q, "BTC") == Quantity.of("0.999", "BTC") for q in sizes
            )
            assert (
                await session.execute("SELECT count(*) FROM paper_position_events")
            ).scalar_one() == n
            balance = await get_wallet(session)
            assert balance is not None and balance.balance == wallet.balance - Money.of(
                200 if match_first else 100, "USDT"
            )


async def test_delayed_entry_price_correction_after_tp_close_replays_once(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000", account_use="BOT"
    ) as source:
        run = await f21_run(engine_engine, owner, wallet)
        order, group = await entry(engine_engine, owner, wallet, run, source)
        await source.price("107")
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            original, event, fact = await single_fill(session, order)
            await process_group(session, group)
            sold = (
                await session.execute("SELECT command_id FROM paper_protection_exits")
            ).scalar_one()
        await drive(engine_engine, owner, sold)
        await asyncio.sleep(0.12)
        await source.next_book()
        await drive(engine_engine, owner, sold)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await process_group(session, group)
            assert (
                await session.execute("SELECT status FROM bot_strategy_baskets")
            ).scalar_one() == "CLOSED"
        correction = uuid4()
        for replay in (False, True):
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                result = await correct_fill(
                    session,
                    wallet_id=wallet.wallet_id,
                    episode_id=wallet.episode_id,
                    order_event_id=event,
                    correction_event_id=correction,
                    supersedes_position_event_id=original,
                    kind=PositionEventKind.REPLACE,
                    fact=replace(fact, quote_amount=Money.of(80, "USDT")),
                )
                assert (result is None) == replay
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await process_group(session, group)
            assert (
                await session.execute(
                    "SELECT status,reconciliation_required FROM bot_strategy_baskets"
                )
            ).one() == ("CLOSED", True)
            assert (
                await session.execute("SELECT reconciliation_required FROM bot_strategy_progress")
            ).scalar_one()
            assert (
                await session.execute("SELECT count(*) FROM paper_position_events")
            ).scalar_one() == 3
            assert (
                await session.execute("SELECT count(*) FROM paper_protection_exits")
            ).scalar_one() == 1
            assert (await session.execute("SELECT count(*) FROM paper_orders")).scalar_one() == 2
            pos = (
                await session.execute(
                    "SELECT held_quantity,total_cost,realized_pnl FROM paper_position_projections"
                )
            ).one()
            assert Quantity.of(pos.held_quantity, "BTC") == Quantity.of(0, "BTC")
            assert Money.of(pos.total_cost, "USDT") == Money.of(0, "USDT")
            assert Money.of(pos.realized_pnl, "USDT") == Money.of("18.802099", "USDT")
            balance = await get_wallet(session)
            assert balance is not None and balance.balance == wallet.balance + Money.of(
                "18.802099", "USDT"
            )


async def test_partial_buy_feedback_delivered_after_tp_close_cannot_reopen_basket(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000", account_use="BOT"
    ) as source:
        run = await f21_run(engine_engine, owner, wallet)
        impl = strategy()
        state = initial_state()
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            clock = (await session.execute("SELECT clock_timestamp()")).scalar_one()
        # Typed signal fixtures isolate feedback delivery; the strategy itself
        # creates the pending ID, immutable decision, intent and bracket.
        for offset, rsi in enumerate(("29", "61")):
            sample = snapshot(rsi=rsi, offset=offset)
            cap = sample.candle_input
            assert cap is not None
            opened = advance(align_floor(clock, Timeframe.M5), Timeframe.M5, offset - 2)
            cap = replace(
                cap,
                candle=replace(cap.candle, open_at=opened, end_at=advance(opened, Timeframe.M5, 1)),
            )
            if offset == 0:
                cap = replace(cap, candle=replace(cap.candle, close=cap.candle.open))
            sample = replace(
                sample,
                scope=replace(
                    sample.scope, owner_id=owner, episode_id=UUID(str(wallet.episode_id))
                ),
                run_id=run,
                observed_at=clock,
                candle_input=cap,
            )
            decision = impl.evaluate(sample, impl.config.document(), state)
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                revision = (
                    await session.execute("SELECT revision FROM bot_runs WHERE id=:id", {"id": run})
                ).scalar_one()
                await record_paper_decision(
                    session,
                    EvaluatedDecision(
                        run,
                        uuid4(),
                        sample.input_identity,
                        revision,
                        1,
                        1,
                        state,
                        decision,
                        {
                            "candle_open_at": cap.candle.open_at.isoformat(),
                            **await accounting_signal_proof(session, run, Timeframe.M5),
                            "signal_atr": "2",
                            "guard_revision": 0,
                        },
                    ),
                )
            state = decision.state
        order = decision.intents[0].order_id
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            command = (
                await session.execute(
                    "SELECT command_id FROM bot_order_links WHERE order_id=:id", {"id": order}
                )
            ).scalar_one()
        await drive(engine_engine, owner, command)
        source.metadata = replace(
            source.metadata,
            market=replace(source.metadata.market, quantity_step=Quantity.of("0.0001", "BTC")),
        )
        source.book = replace(
            source.book, asks=(replace(source.book.asks[0], quantity=Quantity.of("0.4", "BTC")),)
        )
        await asyncio.sleep(0.12)
        await source.next_book()
        await drive(engine_engine, owner, command)
        await source.price("107")
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            group = (
                await session.execute(
                    "SELECT id FROM paper_protections WHERE entry_order_id=:id", {"id": order}
                )
            ).scalar_one()
            await process_group(session, group)
            exit_row = (
                (await session.execute("SELECT command_id,quantity FROM paper_protection_exits"))
                .mappings()
                .one()
            )
            sold, qty = exit_row["command_id"], exit_row["quantity"]
            assert Quantity.of(qty, "BTC") == Quantity.of("0.3996", "BTC")
        await drive(engine_engine, owner, sold)
        await asyncio.sleep(0.12)
        await source.next_book()
        await drive(engine_engine, owner, sold)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await process_group(session, group)
            assert (
                await session.execute("SELECT status FROM bot_strategy_baskets")
            ).scalar_one() == "CLOSED"
            stored = (
                await session.execute(
                    "SELECT strategy_state FROM bot_runs WHERE id=:id", {"id": run}
                )
            ).scalar_one()
            pending = dict(document_from_payload(stored, expected_version=1).fields)
            cancel = (
                await session.execute(
                    "SELECT id FROM paper_order_commands WHERE action='CANCEL' AND order_id=:id",
                    {"id": order},
                )
            ).scalar_one()
            assert pending["pending_id"] == str(order) and pending["pending_filled"] is False
        await drive(engine_engine, owner, cancel)
        # Deliver the accumulated real order events via the engine only now.
        worker_id = run
        statuses = []
        for _ in range(3):
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                message = await next_paper_feedback(session, run)
                assert message is not None
                assert message.value.execution is not None or message.value.status is not None
                if message.value.execution is not None:
                    statuses.append("FILL")
                else:
                    assert message.value.status is not None
                    statuses.append(message.value.status.value)
            decided = await run_bot_quote(
                engine=engine_engine,
                owner=owner,
                run_id=run,
                worker_id=worker_id,
                registry=StrategyRegistry(enable_f21=True),
            )
            assert decided is not None
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                row = (
                    await session.execute(
                        "SELECT input_identity,state_after FROM bot_decisions WHERE id=:id",
                        {"id": decided},
                    )
                ).one()
                assert row.input_identity == message.input_identity
                fields = dict(document_from_payload(row.state_after, expected_version=1).fields)
                if message.value.execution is not None:
                    assert fields["pending_filled"] and fields["reset_close"] is None
        assert statuses == ["ACCEPTED", "FILL", "EXPIRED"]
        assert fields["pending_id"] is None and fields["reset_close"] is None
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            assert await next_paper_feedback(session, run) is None
            assert (
                await session.execute("SELECT count(*) FROM bot_strategy_baskets")
            ).scalar_one() == 1
            assert (await session.execute("SELECT count(*) FROM paper_orders")).scalar_one() == 2
            assert (
                await session.execute("SELECT count(*) FROM paper_position_events")
            ).scalar_one() == 2
            held = (
                await session.execute("SELECT held_quantity FROM paper_position_projections")
            ).scalar_one()
            assert Quantity.of(held, "BTC") == Quantity.of(0, "BTC")
            balance = await get_wallet(session)
            assert balance is not None and balance.balance == wallet.balance - Money.of(
                "0.4791604", "USDT"
            )


@pytest.mark.parametrize("change", ["risk", "takeover", "catalog"])
@pytest.mark.parametrize("match_first", [True, False])
async def test_accepted_buy_vs_authority_change(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    change: str,
    match_first: bool,
) -> None:
    from tests.infra.execution_market.test_bot_catalog import enable_catalog
    from tests.infra.risk_limits.test_requests import submission
    from tests.infra.risk_limits.test_worker import claim
    from tiewtrade.infra.bots.evaluation import evaluate_published_quote
    from tiewtrade.infra.platform import CatalogReason, request_remove
    from tiewtrade.infra.risk_limits.records import RiskAction
    from tiewtrade.infra.risk_limits.requests import submit_request
    from tiewtrade.infra.risk_limits.storage import process_request

    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000", account_use="BOT"
    ) as source:
        if change == "catalog":
            await enable_catalog(api_engine, engine_engine, migrator_engine, owner)
        run = await f21_run(engine_engine, owner, wallet)
        await entry(engine_engine, owner, wallet, run, source)
        _, command = await queue_entry(engine_engine, owner, wallet, run)
        await drive(engine_engine, owner, command)
        await asyncio.sleep(0.12)
        await source.next_book()
        token = await claim_match(engine_engine, owner, command)
        risk_claim = None
        if change == "risk":
            async with user_session(api_engine, owner) as session:
                receipt = await submit_request(
                    session,
                    replace(
                        submission(owner, wallet),
                        action=RiskAction.DECREASE,
                        expected_revision=1,
                        amount=Money.of("0.01", "USDT"),
                    ),
                )
            risk_claim = await claim(engine_engine, owner, receipt)
        elif change == "takeover":
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                await session.execute(
                    "UPDATE bot_run_leases SET lease_until=clock_timestamp()-interval '1 second'"
                )

        async def match(session: UserSession) -> None:
            await process_claimed_order(session, token, policy=TransactionalRiskPolicy())

        async def mutate(session: UserSession) -> None:
            if change == "risk":
                assert risk_claim is not None
                await process_request(session, risk_claim)
            elif change == "catalog":
                await request_remove(
                    session,
                    command_id=uuid4(),
                    idempotency_key="race-removal",
                    base="BTC",
                    quote="USDT",
                    expected_revision=2,
                    reason=CatalogReason.RISK_REVIEW,
                )
            else:
                registry = StrategyRegistry(enable_f21=True)
                await evaluate_published_quote(
                    session,
                    run,
                    worker_id=uuid4(),
                    resolve=registry.implementation,
                    resolve_configuration=registry.configured_implementation,
                )

        if change == "catalog":
            await ordered_writers(
                engine_engine if match_first else api_engine,
                owner,
                *((match, mutate) if match_first else (mutate, match)),
                other_engine=api_engine if match_first else engine_engine,
                first_role=DatabaseRole.ENGINE if match_first else DatabaseRole.API,
                second_role=DatabaseRole.API if match_first else DatabaseRole.ENGINE,
            )
        else:
            await ordered_writers(
                engine_engine, owner, *((match, mutate) if match_first else (mutate, match))
            )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            fills = (
                await session.execute("SELECT count(*) FROM paper_position_events")
            ).scalar_one()
            assert fills == 1 + int(match_first)
            assert (await session.execute("SELECT count(*) FROM bot_order_links")).scalar_one() == 2
            wallet_after = await get_wallet(session)
            assert wallet_after is not None
            count = 2 if match_first else 1
            # The fixture charges 0.001 BTC per gross BTC, yielding 0.999
            # net BTC while debiting exactly the 100 USDT quote budget.
            expected_cost = Money.of(100, "USDT").times(count)
            assert wallet_after.balance == wallet.balance - expected_cost
            position = (
                await session.execute(
                    "SELECT held_quantity,total_cost FROM paper_position_projections"
                )
            ).one()
            assert Quantity.of(position.held_quantity, "BTC") == Quantity.of("0.999", "BTC").times(
                count
            )
            assert Money.of(position.total_cost, "USDT") == expected_cost
            if change == "risk":
                assert (
                    await session.execute("SELECT latched FROM risk_limit_settings")
                ).scalar_one()
            elif change == "takeover":
                assert (
                    await session.execute("SELECT generation FROM bot_run_leases")
                ).scalar_one() == 2
