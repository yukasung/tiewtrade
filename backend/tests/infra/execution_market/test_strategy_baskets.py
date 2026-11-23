"""F-21 projections through real Paper matching; no fabricated ledger fills.

Signal/provenance fixtures isolate basket accounting here. Indicator and candle
source admission are separate criteria, not proved by these tests.
"""

import asyncio
import json
from dataclasses import replace
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market.test_bot_decisions import (
    bot_bracket_protocol as bot_bracket_protocol,
)
from tests.infra.execution_market.test_bot_indicator_inputs import seed_prepared
from tests.infra.execution_market.test_dispatch import intent
from tests.infra.protections.test_lifecycle import single_fill, transfer
from tests.infra.risk_limits.test_execution import Runtime, drive, runtime
from tiewtrade.core.market_data import Timeframe, advance, align_floor
from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.orders import BaseSize, OrderConflictError, OrderOrigin, QuoteBudget
from tiewtrade.core.positions import ExecutionSide, PositionPair
from tiewtrade.core.protections import EntryAtrProtection, ProtectionPrices
from tiewtrade.core.strategies import StrategyDecision, document_from_payload, document_payload
from tiewtrade.core.strategy_config import (
    PAPER_TEST_STRATEGY,
    STRATEGY_NAME,
    PaperTestConfig,
    RsiStepGridConfig,
    decode_strategy_config,
    strategy_initial_state,
)
from tiewtrade.infra.bots.authority import blocked_paper_openings
from tiewtrade.infra.bots.baskets import record_execution
from tiewtrade.infra.bots.decisions import EvaluatedDecision, record_paper_decision
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.db.session import UserSession
from tiewtrade.infra.paper_orders.corrections import correct_fill
from tiewtrade.infra.paper_wallet import get_wallet
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot
from tiewtrade.infra.positions import PositionEventKind
from tiewtrade.infra.protections.storage import (
    StoredProtection,
    admit_request,
    load,
    lock_scope,
    save,
)
from tiewtrade.infra.protections.worker import process_group, process_request

pytestmark = pytest.mark.usefixtures(
    "internal_database", "bot_bracket_protocol", "accounting_indicator_heads"
)


async def test_multi_price_entry_costs_round_only_after_basket_weighting(
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
        level = source.book.asks[0]
        source.book = replace(
            source.book,
            bids=(replace(level, price=Money.of("33.32", "USDT")),),
            asks=(
                replace(level, price=Money.of("33.33", "USDT"), quantity=Quantity.of("2", "BTC")),
                replace(level, price=Money.of("33.34", "USDT"), quantity=Quantity.of("1", "BTC")),
            ),
        )
        await source.price("33.33")
        _, first = await entry(engine_engine, owner, wallet, run, source, atr="1")
        source.book = replace(
            source.book,
            bids=(replace(level, price=Money.of("16.65", "USDT")),),
            asks=(
                replace(level, price=Money.of("16.66", "USDT"), quantity=Quantity.of("1", "BTC")),
                replace(level, price=Money.of("16.67", "USDT"), quantity=Quantity.of("2", "BTC")),
                # Preserve proof that the previously consumed levels are now empty.
                replace(level, price=Money.of("33.33", "USDT"), quantity=Quantity.of("0", "BTC")),
                replace(level, price=Money.of("33.34", "USDT"), quantity=Quantity.of("0", "BTC")),
            ),
        )
        await source.price("16.66")
        second_order, second = await entry(engine_engine, owner, wallet, run, source, atr="1")
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            rows = (
                await session.execute(
                    "SELECT gross_notional,gross_quantity,quantity FROM bot_strategy_entries "
                    "ORDER BY entry_sequence"
                )
            ).all()
            assert [Money.of(row.gross_notional, "USDT") for row in rows] == [
                Money.of("100", "USDT"),
                Money.of("50", "USDT"),
            ]
            assert all(
                Quantity.of(row.gross_quantity, "BTC") == Quantity.of("3", "BTC") for row in rows
            )
            assert all(
                Quantity.of(row.quantity, "BTC") == Quantity.of("2.997", "BTC") for row in rows
            )
            for identity in (first, second):
                group = await load(session, identity)
                assert group is not None and group.value.prices.take_profit == Money.of(
                    "28", "USDT"
                )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            assert (
                await session.execute(
                    "SELECT status FROM paper_order_projections WHERE order_id=:id",
                    {"id": second_order},
                )
            ).scalar_one() == "EXPIRED"
            assert Money.of(
                (await session.execute("SELECT target FROM bot_strategy_baskets")).scalar_one(),
                "USDT",
            ) == Money.of("28", "USDT")


@pytest_asyncio.fixture
async def accounting_indicator_heads(internal_database: None, migrator_engine: AsyncEngine) -> None:
    """Supply published authority for tests that inject the signal at decision commit."""
    async with migrator_engine.begin() as connection:
        await connection.execute(text("SELECT activate_indicator_source_proof()"))
        now: datetime = (await connection.execute(text("SELECT clock_timestamp()"))).scalar_one()
    for timeframe in (Timeframe.M5, Timeframe.MN1):
        await seed_prepared(migrator_engine, 2, now, timeframe=timeframe)


async def accounting_signal_proof(
    session: UserSession, run: UUID, timeframe: Timeframe
) -> dict[str, str | int]:
    await session.execute(
        """INSERT INTO bot_run_leases(run_id,user_id,mode,worker_id,generation,lease_until)
           VALUES(:run,:owner,'PAPER',:run,1,clock_timestamp()+interval '1 minute')
           ON CONFLICT(run_id) DO NOTHING""",
        {"owner": session.user_id, "run": run},
    )
    row = (
        await session.execute(
            """SELECT h.generation_id,c.rollout_epoch,s.revision AS fence,l.generation,
                  (SELECT revision FROM risk_limit_settings WHERE mode='PAPER') AS risk
           FROM indicator_ready_heads h CROSS JOIN indicator_rollout_control c
           CROSS JOIN indicator_source_guard s CROSS JOIN bot_run_leases l
           WHERE h.timeframe=:tf AND l.run_id=:run""",
            {"run": run, "tf": timeframe.value},
        )
    ).one()
    return {
        "indicator_generation": str(row.generation_id),
        "rollout_epoch": str(row.rollout_epoch),
        "source_fence": row.fence,
        "lease_generation": row.generation,
        "risk_revision": row.risk,
    }


async def f21_run(
    engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    *,
    max_entries: int = 10,
    timeframe: Timeframe = Timeframe.M5,
    configuration: PaperTestConfig | None = None,
) -> UUID:
    run = uuid4()
    config = configuration or RsiStepGridConfig(
        PositionPair("BTC", "USDT"), timeframe, Money.of(100, "USDT"), max_entries
    )
    name = PAPER_TEST_STRATEGY if isinstance(config, PaperTestConfig) else STRATEGY_NAME
    async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
        await session.execute(
            """INSERT INTO bot_runs(id,user_id,mode,wallet_id,episode_id,strategy_name,
                strategy_version,configuration_version,state_version,configuration,strategy_state,status)
              VALUES(:id,:owner,'PAPER',:wallet,:episode,:name,1,1,1,
                CAST(:config AS jsonb),CAST(:state AS jsonb),'RUNNING')""",
            {
                "id": run,
                "owner": owner,
                "wallet": wallet.wallet_id,
                "episode": wallet.episode_id,
                "name": name,
                "config": json.dumps(document_payload(config.document())),
                "state": json.dumps(document_payload(strategy_initial_state(name))),
            },
        )
        await session.execute(
            "INSERT INTO bot_strategy_progress(run_id,user_id,mode,episode_id,recovery_required,"
            "price_recovery_at) VALUES(:run,:owner,'PAPER',:episode,false,"
            "(SELECT bot_recovery_at FROM market_price_feed WHERE source='primary_spot'))",
            {"run": run, "owner": owner, "episode": wallet.episode_id},
        )
        await session.execute(
            """INSERT INTO bot_run_events(id,run_id,user_id,mode,revision,event,details)
            VALUES(:id,:run,:owner,'PAPER',1,'START_REQUEST_APPLIED',
              jsonb_build_object('base','BTC','quote','USDT','catalog_revision',
                (SELECT current_revision FROM supported_symbol_catalog_control)))""",
            {"id": uuid4(), "run": run, "owner": owner},
        )
    return run


async def queue_entry(
    engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    run: UUID,
    *,
    budget: str = "100",
    atr: str = "2",
    guard_revision: int = 0,
) -> tuple[UUID, UUID]:
    async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
        return await queue_entry_in_session(
            session, wallet, run, budget=budget, atr=atr, guard_revision=guard_revision
        )


async def queue_entry_in_session(
    session: UserSession,
    wallet: PaperWalletSnapshot,
    run: UUID,
    *,
    budget: str = "100",
    atr: str = "2",
    guard_revision: int = 0,
) -> tuple[UUID, UUID]:
    value = replace(
        intent(session.user_id, wallet.episode_id),
        origin=OrderOrigin.BOT,
        size=QuoteBudget(Money.of(budget, "USDT")),
    )
    row = (
        await session.execute(
            "SELECT revision,configuration,strategy_name FROM bot_runs WHERE id=:id", {"id": run}
        )
    ).one()
    timeframe = decode_strategy_config(
        row.strategy_name, document_from_payload(row.configuration, expected_version=1)
    ).timeframe
    entry_state = strategy_initial_state(row.strategy_name)
    now = (await session.execute("SELECT clock_timestamp()")).scalar_one()
    await record_paper_decision(
        session,
        EvaluatedDecision(
            run,
            uuid4(),
            str(uuid4()),
            row.revision,
            1,
            1,
            entry_state,
            StrategyDecision(
                entry_state,
                (value,),
                (
                    (
                        value.order_id,
                        EntryAtrProtection(value.pair, Money.of(atr, "USDT"))
                        if row.strategy_name == PAPER_TEST_STRATEGY
                        else ProtectionPrices(value.pair, take_profit=Money.of(120, "USDT")),
                    ),
                ),
            ),
            {
                **await accounting_signal_proof(session, run, timeframe),
                "candle_open_at": advance(align_floor(now, timeframe), timeframe, -1).isoformat(),
                "signal_atr": atr,
                "guard_revision": guard_revision,
            },
        ),
    )
    command = (
        await session.execute(
            "SELECT command_id FROM bot_order_links WHERE order_id=:id", {"id": value.order_id}
        )
    ).scalar_one()
    return value.order_id, command


async def entry(
    engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    run: UUID,
    source: Runtime,
    *,
    budget: str = "100",
    atr: str = "2",
) -> tuple[UUID, UUID]:
    order_id, command = await queue_entry(engine, owner, wallet, run, budget=budget, atr=atr)
    await drive(engine, owner, command)
    await asyncio.sleep(0.12)
    await source.next_book()
    await drive(engine, owner, command)
    async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
        group = (
            await session.execute(
                "SELECT id FROM paper_protections WHERE entry_order_id=:id", {"id": order_id}
            )
        ).scalar_one()
    return order_id, group


async def test_basket_trigger_fans_out_once_and_survives_price_drop(
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
        first, a = await entry(engine_engine, owner, wallet, run, source)
        second, b = await entry(engine_engine, owner, wallet, run, source)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            targets = (
                (await session.execute("SELECT document->>'tp' FROM paper_protections ORDER BY id"))
                .scalars()
                .all()
            )
            assert len(targets) == 2 and all(
                Money.of(t, "USDT") == Money.of(106, "USDT") for t in targets
            )
            balance = await get_wallet(session)
            assert balance is not None and balance.balance == wallet.balance - Money.of(200, "USDT")
        await source.price("107")
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await process_group(session, a)
            assert (
                await session.execute("SELECT count(*) FROM paper_protection_exits")
            ).scalar_one() == 2
        await source.price("104")
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await process_group(session, b)
            await process_group(session, a)
            assert (
                await session.execute("SELECT count(*) FROM bot_basket_triggers")
            ).scalar_one() == 1
            assert (
                await session.execute("SELECT count(*) FROM paper_protection_exits")
            ).scalar_one() == 2
            groups = [await load(session, identity) for identity in (a, b)]
            assert all(g is not None and g.value.state.value == "EXITING" for g in groups)
            assert groups[0] is not None and groups[1] is not None
            assert groups[0].value.trigger == groups[1].value.trigger
            assert (
                await session.execute("SELECT count(*) FROM paper_position_events")
            ).scalar_one() == 2
            assert len({first, second}) == 2
            commands = (
                (
                    await session.execute(
                        "SELECT command_id FROM paper_protection_exits ORDER BY protection_id"
                    )
                )
                .scalars()
                .all()
            )
        for command in commands:
            await drive(engine_engine, owner, command)
        await asyncio.sleep(0.12)
        await source.next_book()
        for command in commands:
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                terminal = (
                    await session.execute(
                        "SELECT state='TERMINAL' FROM paper_order_dispatch WHERE command_id=:id",
                        {"id": command},
                    )
                ).scalar_one()
            # Advancing either command matches the shared pair checkpoint;
            # its sibling can already have completed in that transaction.
            if not terminal:
                await drive(engine_engine, owner, command)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            # Actual MARKET sales use the proven bid99 and F-15 fees, not the
            # earlier TP106 or winning last trade107 as guaranteed fill prices.
            balance = await get_wallet(session)
            assert balance is not None and balance.balance == wallet.balance - Money.of(
                "2.395802", "USDT"
            )
            position = (
                await session.execute(
                    "SELECT held_quantity,total_cost,realized_pnl FROM paper_position_projections"
                )
            ).one()
            assert Quantity.of(position.held_quantity, "BTC") == Quantity.of(0, "BTC")
            assert Money.of(position.total_cost, "USDT") == Money.of(0, "USDT")
            assert Money.of(position.realized_pnl, "USDT") == Money.of("-2.395802", "USDT")
            assert (
                await session.execute("SELECT count(*) FROM paper_position_events")
            ).scalar_one() == 4
            await process_group(session, a)
            await process_group(session, b)
            assert (
                await session.execute("SELECT status FROM bot_strategy_baskets")
            ).scalar_one() == "CLOSED"
            assert (
                await session.execute("SELECT count(*) FROM paper_protection_exits")
            ).scalar_one() == 2


async def test_manual_partial_sell_consumes_only_selected_fifo_and_deduplicates(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000", account_use="BOT"
    ) as source:
        run = await f21_run(engine_engine, owner, wallet)
        first, a = await entry(engine_engine, owner, wallet, run, source)
        second, b = await entry(engine_engine, owner, wallet, run, source)
        third, _c = await entry(engine_engine, owner, wallet, run, source)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            selections = []
            # Reverse request order deliberately; FIFO is entry_sequence order.
            for identity in (b, a):
                group = await load(session, identity)
                assert group is not None
                selections.append(
                    {
                        "protection_id": str(identity),
                        "expected_revision": group.value.revision,
                        "quantity": "0.6",
                    }
                )
        sale = replace(
            intent(owner, wallet.episode_id),
            side=ExecutionSide.SELL,
            size=BaseSize(Quantity.of("1.2", "BTC")),
        )
        command = await transfer(
            api_engine,
            engine_engine,
            scan_engine,
            owner,
            wallet,
            sale,
            selections=tuple(selections),
        )
        await drive(engine_engine, owner, command)
        await asyncio.sleep(0.12)
        source.book = replace(
            source.book, bids=(replace(source.book.bids[0], quantity=Quantity.of("0.8", "BTC")),)
        )
        await source.next_book()
        await drive(engine_engine, owner, command)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            quantities: dict[UUID, str] = {
                UUID(str(row.order_id)): str(row.quantity)
                for row in (
                    await session.execute("SELECT order_id,quantity FROM bot_strategy_entries")
                ).all()
            }
            assert Quantity.of(quantities[first], "BTC") == Quantity.of("0.399", "BTC")
            assert Quantity.of(quantities[second], "BTC") == Quantity.of("0.799", "BTC")
            assert Quantity.of(quantities[third], "BTC") == Quantity.of("0.999", "BTC")
            _, _, fact = await single_fill(session, sale.order_id)
            await lock_scope(session, wallet.wallet_id, wallet.episode_id)
            assert await record_execution(session, sale.order_id, fact) == ()
            assert (
                await session.execute(
                    "SELECT guard_revision FROM bot_strategy_progress WHERE run_id=:run",
                    {"run": run},
                )
            ).scalar_one() == 1
            assert (
                await session.execute("SELECT count(*) FROM bot_strategy_exit_guards")
            ).scalar_one() == 1
            assert await blocked_paper_openings(
                session, episode_id=wallet.episode_id, order_ids=(first, second, third)
            ) == frozenset((first, second, third))
            assert (
                await session.execute("SELECT count(*) FROM paper_position_events")
            ).scalar_one() == 4
            assert (
                await session.execute(
                    "SELECT count(*) FROM paper_reservations "
                    "WHERE quote_reserved<>0 OR base_reserved<>0"
                )
            ).scalar_one() == 0
            basket = (
                await session.execute(
                    "SELECT target,reconciliation_required FROM bot_strategy_baskets"
                )
            ).one()
            assert Money.of(basket.target, "USDT") == Money.of(106, "USDT")
            assert not basket.reconciliation_required


async def test_confirmed_fill_retargets_every_entry_and_rechecks_same_quote(
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
        _, a = await entry(engine_engine, owner, wallet, run, source)
        await source.price("102")
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await process_group(session, a)
            group = await load(session, a)
            assert group is not None and group.value.state.value == "ARMED"
            assert (
                await session.execute("SELECT count(*) FROM paper_protection_exits")
            ).scalar_one() == 0
        source.book = replace(
            source.book,
            bids=(replace(source.book.bids[0], price=Money.of(89, "USDT")),),
            asks=(
                replace(source.book.asks[0], price=Money.of(90, "USDT")),
                replace(source.book.asks[0], quantity=Quantity.of(0, "BTC")),
            ),
        )
        _, b = await entry(engine_engine, owner, wallet, run, source, budget="100")
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            groups = [await load(session, identity) for identity in (a, b)]
            assert all(
                g is not None and g.value.prices.take_profit == Money.of("100.73", "USDT")
                for g in groups
            )
            assert all(g is not None and g.observation is None for g in groups)
            basket = (
                await session.execute("SELECT target,target_revision FROM bot_strategy_baskets")
            ).one()
            assert Money.of(basket.target, "USDT") == Money.of("100.73", "USDT")
            assert basket.target_revision == 2
            assert (
                await session.execute("SELECT count(*) FROM bot_strategy_entries WHERE quantity>0")
            ).scalar_one() == 2
            assert (
                await session.execute("SELECT count(*) FROM paper_position_events")
            ).scalar_one() == 2
        # No new last-trade observation: 102 was below old106, above new100.73.
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await process_group(session, a)
            assert (
                await session.execute("SELECT count(*) FROM paper_protection_exits")
            ).scalar_one() == 2


async def test_price_only_correction_fences_original_basket_cost_and_queued_openings(
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
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            position_event, order_event, fact = await single_fill(session, order)
            await correct_fill(
                session,
                wallet_id=wallet.wallet_id,
                episode_id=wallet.episode_id,
                order_event_id=order_event,
                correction_event_id=uuid4(),
                supersedes_position_event_id=position_event,
                kind=PositionEventKind.REPLACE,
                fact=replace(fact, quote_amount=Money.of(80, "USDT")),
            )
        await source.price("107")
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            assert (
                await session.execute(
                    "SELECT reconciliation_required FROM bot_strategy_progress WHERE run_id=:id",
                    {"id": run},
                )
            ).scalar_one()
            assert await blocked_paper_openings(
                session, episode_id=wallet.episode_id, order_ids=(order,)
            ) == frozenset((order,))
            await process_group(session, group)
            assert (
                await session.execute("SELECT count(*) FROM paper_protection_exits")
            ).scalar_one() == 0
            balance = await get_wallet(session)
            assert balance is not None and balance.balance == wallet.balance - Money.of(80, "USDT")
            assert (
                await session.execute("SELECT count(*) FROM paper_position_events")
            ).scalar_one() == 2


async def test_managed_tp_rejects_manual_replace_at_admission_and_queued_execution(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tiewtrade.infra.protections import storage

    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000", account_use="BOT"
    ) as source:
        run = await f21_run(engine_engine, owner, wallet)
        _, group_id = await entry(engine_engine, owner, wallet, run, source)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            group = await load(session, group_id)
            assert group is not None
        payload: dict[str, object] = {
            "quantity": "0.999",
            "tp": "120",
            "sl": None,
            "expected_revision": group.value.revision,
        }
        async with user_session(api_engine, owner) as session:
            with pytest.raises(OrderConflictError, match="strategy-managed"):
                await admit_request(
                    session,
                    wallet_id=wallet.wallet_id,
                    episode_id=wallet.episode_id,
                    action="REPLACE",
                    key=uuid4(),
                    protection_id=group_id,
                    payload=payload,
                )

        # Simulate a request accepted by the prior deployment. Only the intake
        # feature gate is bypassed, while DB roles, facts and engine stay real.
        async def legacy_policy(*args: object) -> bool:
            return False

        with monkeypatch.context() as patch:
            patch.setattr(storage, "strategy_managed_protection", legacy_policy)
            async with user_session(api_engine, owner) as session:
                request = await admit_request(
                    session,
                    wallet_id=wallet.wallet_id,
                    episode_id=wallet.episode_id,
                    action="REPLACE",
                    key=uuid4(),
                    protection_id=group_id,
                    payload=payload,
                )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await process_request(session, request)
            result = (
                await session.execute(
                    "SELECT state,failure_code FROM paper_protection_results WHERE request_id=:id",
                    {"id": request},
                )
            ).one()
            assert (result.state, result.failure_code) == ("REJECTED", "ORDER_CONFLICT")
            current = await load(session, group_id)
            assert current is not None and current.value == group.value
        # Explicit cancellation remains available and is never restored by a poll.
        async with user_session(api_engine, owner) as session:
            request = await admit_request(
                session,
                wallet_id=wallet.wallet_id,
                episode_id=wallet.episode_id,
                action="CANCEL",
                key=uuid4(),
                protection_id=group_id,
                payload={"expected_revision": group.value.revision},
            )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await process_request(session, request)
            await process_group(session, group_id)
            current = await load(session, group_id)
            assert current is not None and current.value.state.value == "CANCELED"


@pytest.mark.parametrize("rollback", [False, True], ids=["concurrent-trigger", "rollback-retry"])
async def test_retarget_transaction_is_atomic_against_other_workers_and_faults(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    monkeypatch: pytest.MonkeyPatch,
    rollback: bool,
) -> None:
    from tiewtrade.infra.protections import worker

    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000", account_use="BOT"
    ) as source:
        run = await f21_run(engine_engine, owner, wallet)
        _, a = await entry(engine_engine, owner, wallet, run, source)
        _, b = await entry(engine_engine, owner, wallet, run, source)
        await source.price("102")
        source.book = replace(
            source.book,
            bids=(replace(source.book.bids[0], price=Money.of(84, "USDT")),),
            asks=(
                replace(source.book.asks[0], price=Money.of("86.37", "USDT")),
                replace(source.book.asks[0], quantity=Quantity.of(0, "BTC")),
            ),
        )
        staged, release = asyncio.Event(), asyncio.Event()
        original = save
        intercepted = False

        async def after_first_target(*args: Any, **kwargs: Any) -> StoredProtection:
            nonlocal intercepted
            result = await original(*args, **kwargs)
            if kwargs.get("kind") == "REPLACE" and not intercepted:
                intercepted = True
                staged.set()
                await release.wait()
                if rollback:
                    raise RuntimeError("injected retarget transaction failure")
            return result

        monkeypatch.setattr(worker, "save", after_first_target)
        filling = asyncio.create_task(
            entry(engine_engine, owner, wallet, run, source, budget="100")
        )
        waiting: list[asyncio.Task[None]] = []

        async def trigger(identity: UUID) -> None:
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                await process_group(session, identity)

        try:
            await asyncio.wait_for(staged.wait(), 5)
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                prices = (
                    (
                        await session.execute(
                            "SELECT document->>'tp' FROM paper_protections WHERE quantity>0"
                        )
                    )
                    .scalars()
                    .all()
                )
                assert len(prices) == 2 and all(
                    Money.of(p, "USDT") == Money.of(106, "USDT") for p in prices
                )
                assert (
                    await session.execute("SELECT count(*) FROM paper_position_events")
                ).scalar_one() == 2
            if not rollback:
                waiting = [asyncio.create_task(trigger(identity)) for identity in (a, b)]
                await asyncio.sleep(0.05)
                assert all(not task.done() for task in waiting)
        finally:
            release.set()
            if rollback:
                with pytest.raises(RuntimeError, match="injected retarget"):
                    await asyncio.wait_for(filling, 5)
            else:
                await asyncio.wait_for(filling, 5)
            if waiting:
                await asyncio.wait_for(asyncio.gather(*waiting), 5)
        monkeypatch.setattr(worker, "save", original)
        if rollback:
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                assert (
                    await session.execute("SELECT count(*) FROM paper_position_events")
                ).scalar_one() == 2
                assert (
                    await session.execute("SELECT count(*) FROM paper_protection_exits")
                ).scalar_one() == 0
                prices = (
                    (
                        await session.execute(
                            "SELECT document->>'tp' FROM paper_protections WHERE quantity>0"
                        )
                    )
                    .scalars()
                    .all()
                )
                assert all(Money.of(p, "USDT") == Money.of(106, "USDT") for p in prices)
                command = (
                    await session.execute(
                        "SELECT command_id FROM bot_strategy_entries WHERE entry_sequence=3"
                    )
                ).scalar_one()
                await session.execute(
                    "UPDATE paper_order_dispatch SET "
                    "lease_until=clock_timestamp()-interval '1 second' "
                    "WHERE command_id=:id",
                    {"id": command},
                )
            await drive(engine_engine, owner, command)
            await trigger(a)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            prices = (
                (
                    await session.execute(
                        "SELECT document->>'tp' FROM paper_protections WHERE quantity>0"
                    )
                )
                .scalars()
                .all()
            )
            assert len(prices) == 3 and all(
                Money.of(p, "USDT") == Money.of(101, "USDT") for p in prices
            )
            assert (
                await session.execute("SELECT count(*) FROM bot_basket_triggers")
            ).scalar_one() == 1
            assert (
                await session.execute("SELECT count(*) FROM paper_protection_exits")
            ).scalar_one() == 3
            assert (
                await session.execute("SELECT count(*) FROM paper_position_events")
            ).scalar_one() == 3
            balance = await get_wallet(session)
            assert balance is not None and balance.balance == wallet.balance - Money.of(
                "299.93009", "USDT"
            )


@pytest.mark.parametrize("capacity", [1, 10])
async def test_filled_entry_limit_rolls_back_excess_commands_including_partial_entry(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    capacity: int,
) -> None:
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000", account_use="BOT"
    ) as source:
        run = await f21_run(engine_engine, owner, wallet, max_entries=capacity)
        if capacity == 1:
            source.book = replace(
                source.book,
                asks=(replace(source.book.asks[0], quantity=Quantity.of("0.4", "BTC")),),
            )
        for _ in range(capacity):
            await source.price("100")
            await entry(engine_engine, owner, wallet, run, source)
        with pytest.raises(OrderConflictError, match="entry count is full"):
            await entry(engine_engine, owner, wallet, run, source)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            assert (
                await session.execute("SELECT count(*) FROM bot_strategy_entries")
            ).scalar_one() == capacity
            assert (
                await session.execute("SELECT count(*) FROM bot_order_links")
            ).scalar_one() == capacity
            assert (
                await session.execute(
                    "SELECT count(*) FROM paper_order_commands WHERE action='NEW'"
                )
            ).scalar_one() == capacity
            assert (
                await session.execute("SELECT count(*) FROM paper_position_events")
            ).scalar_one() == capacity
            balance = await get_wallet(session)
            assert balance is not None and balance.balance == wallet.balance - Money.of(
                "40" if capacity == 1 else "1000", "USDT"
            )
            assert (
                await session.execute(
                    "SELECT count(*) FROM paper_reservations "
                    "WHERE quote_reserved<>0 OR base_reserved<>0"
                )
            ).scalar_one() == 0
            if capacity == 1:
                assert (
                    await session.execute("SELECT status FROM paper_order_projections")
                ).scalar_one() == "EXPIRED"
                quantity = (
                    await session.execute("SELECT quantity FROM bot_strategy_entries")
                ).scalar_one()
                assert Quantity.of(quantity, "BTC") == Quantity.of("0.3996", "BTC")


@pytest.mark.parametrize("admitted", [False, True])
async def test_exit_guard_rejects_stale_and_current_same_candle_intents_and_queued_buy(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    admitted: bool,
) -> None:
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000", account_use="BOT"
    ) as source:
        run = await f21_run(engine_engine, owner, wallet, timeframe=Timeframe.MN1)
        _, a = await entry(engine_engine, owner, wallet, run, source)
        queued, pending = await queue_entry(engine_engine, owner, wallet, run)
        if admitted:
            await drive(engine_engine, owner, pending)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            if admitted:
                # Model the existing F-20 pause fence while a reducing order
                # fills; the old BUY must not revive after readiness returns.
                await session.execute(
                    "UPDATE bot_runs SET status='PAUSED',revision=revision+1 WHERE id=:id",
                    {"id": run},
                )
            protection = await load(session, a)
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
                    "protection_id": str(a),
                    "expected_revision": protection.value.revision,
                    "quantity": "0.4",
                },
            ),
        )
        await drive(engine_engine, owner, sold)
        await asyncio.sleep(0.12)
        await source.next_book()
        await drive(engine_engine, owner, sold)
        if admitted:
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                await session.execute(
                    "UPDATE bot_runs SET status='RUNNING',revision=revision+1 WHERE id=:id",
                    {"id": run},
                )
        for revision in (0, 1):
            with pytest.raises(OrderConflictError, match="exit guard changed"):
                await queue_entry(engine_engine, owner, wallet, run, guard_revision=revision)
        await drive(engine_engine, owner, pending)
        if admitted:
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                cancel = (
                    await session.execute(
                        "SELECT id FROM paper_order_commands "
                        "WHERE order_id=:id AND action='CANCEL'",
                        {"id": queued},
                    )
                ).scalar_one()
            await drive(engine_engine, owner, cancel)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            if admitted:
                assert (
                    await session.execute(
                        "SELECT status FROM paper_order_projections WHERE order_id=:id",
                        {"id": queued},
                    )
                ).scalar_one() == "CANCELED"
            else:
                assert (
                    await session.execute(
                        "SELECT state FROM paper_order_command_results WHERE command_id=:id",
                        {"id": pending},
                    )
                ).scalar_one() == "REJECTED"
                assert (
                    await session.execute(
                        "SELECT count(*) FROM paper_orders WHERE id=:id", {"id": queued}
                    )
                ).scalar_one() == 0
            assert (await session.execute("SELECT count(*) FROM bot_order_links")).scalar_one() == 2
            assert (
                await session.execute("SELECT count(*) FROM paper_position_events")
            ).scalar_one() == 2
            assert (
                await session.execute("SELECT count(*) FROM bot_strategy_exit_guards")
            ).scalar_one() == 1
            balance = await get_wallet(session)
            assert balance is not None and balance.balance == wallet.balance - Money.of(
                "60.4396", "USDT"
            )
            assert (
                await session.execute(
                    "SELECT count(*) FROM paper_reservations "
                    "WHERE quote_reserved<>0 OR base_reserved<>0"
                )
            ).scalar_one() == 0


async def test_financial_registration_rejects_budget_different_from_run_pin_atomically(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000", account_use="BOT"
    ):
        run = await f21_run(engine_engine, owner, wallet)
        with pytest.raises(OrderConflictError, match="pinned strategy"):
            await queue_entry(engine_engine, owner, wallet, run, budget="99")
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            assert (await session.execute("SELECT count(*) FROM bot_decisions")).scalar_one() == 0
            assert (
                await session.execute("SELECT count(*) FROM paper_order_commands")
            ).scalar_one() == 0
            assert (
                await session.execute("SELECT count(*) FROM bot_strategy_baskets")
            ).scalar_one() == 0


async def test_retarget_uses_the_confirmed_execution_tick_after_metadata_changes(
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
        await entry(engine_engine, owner, wallet, run, source)
        source.metadata = replace(
            source.metadata,
            market=replace(source.metadata.market, price_tick=Money.of(1, "USDT")),
            limit=replace(source.metadata.limit, price_tick=Money.of(1, "USDT")),
        )
        source.book = replace(
            source.book,
            bids=(replace(source.book.bids[0], price=Money.of(89, "USDT")),),
            asks=(
                replace(source.book.asks[0], price=Money.of(90, "USDT")),
                replace(source.book.asks[0], quantity=Quantity.of(0, "BTC")),
            ),
        )
        await source.price("90")
        await entry(engine_engine, owner, wallet, run, source)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            row = (
                await session.execute("SELECT target,price_tick FROM bot_strategy_baskets")
            ).one()
            assert Money.of(row.price_tick, "USDT") == Money.of(1, "USDT")
            assert Money.of(row.target, "USDT") == Money.of(100, "USDT")
            prices = tuple(
                (await session.execute("SELECT document->>'tp' FROM paper_protections")).scalars()
            )
            assert len(prices) == 2 and all(
                Money.of(p, "USDT") == Money.of(100, "USDT") for p in prices
            )


@pytest.mark.parametrize("dust_first", [True, False])
async def test_small_armed_residual_cannot_suppress_shared_exit_or_stop_bot(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    dust_first: bool,
) -> None:
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000", account_use="BOT"
    ) as source:
        run = await f21_run(engine_engine, owner, wallet)
        _, dust = await entry(engine_engine, owner, wallet, run, source)
        _, other = await entry(engine_engine, owner, wallet, run, source)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await process_group(session, dust)
            group = await load(session, dust)
            assert group is not None and group.value.state.value == "ARMED"
            revision = group.value.revision
        sale = replace(
            intent(owner, wallet.episode_id),
            side=ExecutionSide.SELL,
            size=BaseSize(Quantity.of("0.994", "BTC")),
        )
        command = await transfer(
            api_engine,
            engine_engine,
            scan_engine,
            owner,
            wallet,
            sale,
            selections=(
                {"protection_id": str(dust), "expected_revision": revision, "quantity": "0.994"},
            ),
        )
        await drive(engine_engine, owner, command)
        await asyncio.sleep(0.12)
        source.metadata = replace(
            source.metadata,
            market=replace(source.metadata.market, minimum_notional=Money.of(5, "USDT")),
        )
        await source.next_book()
        await drive(engine_engine, owner, command)
        await source.price("107")
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            group = await load(session, dust)
            assert group is not None and group.value.quantity == Quantity.of("0.005", "BTC")
            await process_group(session, dust if dust_first else other)
        await source.price("104")
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await process_group(session, other)
            await process_group(session, dust)
            assert (
                await session.execute("SELECT count(*) FROM bot_basket_triggers")
            ).scalar_one() == 1
            assert (
                await session.execute("SELECT protection_id FROM paper_protection_exits")
            ).scalar_one() == other
            assert (
                await session.execute("SELECT count(*) FROM trading_stop_requests")
            ).scalar_one() == 0
            group = await load(session, dust)
            assert group is not None and group.value.state.value == "FAILED"
            assert group.value.quantity == Quantity.of("0.005", "BTC")


async def test_initial_setup_filter_failure_preserves_bot_stop_after_basket_wins(
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
        _, group_id = await entry(engine_engine, owner, wallet, run, source)
        source.metadata = replace(
            source.metadata,
            market=replace(source.metadata.market, minimum_notional=Money.of(200, "USDT")),
        )
        await source.next_book()
        await source.price("107")
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await process_group(session, group_id)
            await process_group(session, group_id)
            assert (
                await session.execute("SELECT count(*) FROM bot_basket_triggers")
            ).scalar_one() == 1
            assert (
                await session.execute("SELECT reason_code FROM trading_stop_requests")
            ).scalar_one() == "PROTECTION_SETUP_FAILED"
            assert (
                await session.execute("SELECT count(*) FROM paper_protection_exits")
            ).scalar_one() == 0
            group = await load(session, group_id)
            assert group is not None and group.value.setup_failed_exit
