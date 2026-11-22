"""Owned F-21 browser fixture: actual API/workers with recorded CLOSED market data.

Never mounted by production. Candle publication waits for real UTC minute closes;
no historical BUY replay, strategy stub or artificial execution facts.
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import datetime
from uuid import uuid4, uuid5

from fastapi import FastAPI, HTTPException
from sqlalchemy import text

from tests import e2e_risk_app as sources
from tests.e2e_bot_app import prepare_owner
from tests.e2e_manual_order_app import Owner, guard
from tests.infra.execution_market.test_bot_indicator_inputs import (
    append_recorded_candle,
    fixture_candles,
    seed_prepared,
)
from tiewtrade.core.market_data import Timeframe, advance, align_floor
from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.order_book import BookLevel
from tiewtrade.infra.db import DatabaseRole, create_engine_for, user_session
from tiewtrade.infra.paper_wallet import get_wallet
from tiewtrade.services.api.app import app as production_app
from tiewtrade.services.engine.bot import StrategyRegistry, run_bot_worker_round

_end: datetime | None = None
_history = tuple(Money.of(index + 100, "USDT") for index in range(250))
_closes: tuple[str, ...] = ("310", "355", "315", "260", "395")
_step = 0


@asynccontextmanager
async def lifespan(instance: FastAPI, *, enable_paper_test: bool = False) -> AsyncIterator[None]:
    guard()
    async with sources.lifespan(instance):
        migrator, engine, scan = (
            create_engine_for(role)
            for role in (DatabaseRole.MIGRATOR, DatabaseRole.ENGINE, DatabaseRole.ENGINE_SCAN)
        )
        previous = getattr(production_app.state, "bot_f21_enabled", False)
        previous_test = getattr(production_app.state, "paper_test_strategy_enabled", False)
        worker = uuid4()

        async def bots() -> None:
            cursor = None
            while True:
                result = await run_bot_worker_round(
                    engine=engine,
                    scan_engine=scan,
                    registry=StrategyRegistry(enable_f21=True, enable_paper_test=enable_paper_test),
                    cursor=cursor,
                    worker_id=worker,
                )
                cursor = result.next_cursor
                await asyncio.sleep(0.2)

        task = None
        try:
            async with migrator.begin() as connection:
                await connection.execute(text("UPDATE paper_protection_protocol SET enabled=true"))
                proof: str = (
                    await connection.execute(
                        text("SELECT source_proof_state FROM indicator_rollout_control WHERE id=1")
                    )
                ).scalar_one()
                if proof != "READY":
                    await connection.execute(text("SELECT activate_indicator_source_proof()"))
            production_app.state.bot_f21_enabled = True
            production_app.state.paper_test_strategy_enabled = enable_paper_test
            task = asyncio.create_task(bots())
            yield
        finally:
            production_app.state.bot_f21_enabled = previous
            production_app.state.paper_test_strategy_enabled = previous_test
            if task is not None:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            async with migrator.begin() as connection:
                await connection.execute(text("UPDATE paper_protection_protocol SET enabled=false"))
            await engine.dispose()
            await scan.dispose()
            await migrator.dispose()


app = FastAPI(lifespan=lifespan)
app.post("/__e2e/strategy/prepare-owner", status_code=204)(prepare_owner)


def public_price(amount: str, *, trigger: bool = False) -> None:
    source = sources._runtime
    assert source is not None
    sources._price = amount
    ask = Money.of(amount, "USDT")
    old_prices = {level.price for level in source.book.asks} | {
        Money.of(355, "USDT"),
        Money.of(395, "USDT"),
    }
    source.book = replace(
        source.book,
        bids=(
            BookLevel(
                Money.of("434.5", "USDT") if trigger else ask - Money.of("0.5", "USDT"),
                Quantity.of(100, "BTC"),
            ),
        ),
        asks=tuple(
            BookLevel(price, Quantity.of(100 if price == ask else 0, "BTC"))
            for price in sorted(old_prices | {ask})
        ),
    )
    source.metadata = replace(
        source.metadata,
        market=replace(source.metadata.market, quantity_step=Quantity.of("0.0001", "BTC")),
        limit=replace(source.metadata.limit, quantity_step=Quantity.of("0.0001", "BTC")),
    )


@app.post("/__e2e/strategy/prepare", status_code=204)
async def prepare(body: Owner) -> None:
    global _end, _step
    await prepare_owner(body)
    migrator = create_engine_for(DatabaseRole.MIGRATOR)
    try:
        async with migrator.connect() as connection:
            now: datetime = (
                await connection.execute(text("SELECT clock_timestamp()"))
            ).scalar_one()
        # Seed just after a real minute boundary, leaving a complete minute for
        # the browser to start and the engine to establish its live cutoff.
        boundary = advance(align_floor(now, Timeframe.M1), Timeframe.M1, 1)
        await asyncio.sleep((boundary - now).total_seconds() + 0.1)
        async with migrator.connect() as connection:
            now = (await connection.execute(text("SELECT clock_timestamp()"))).scalar_one()
        _end, _step = align_floor(now, Timeframe.M1), 0
        await seed_prepared(migrator, 250, _end, closes=_history)
        public_price("349")
    finally:
        await migrator.dispose()


@app.post("/__e2e/strategy/step")
async def step(body: Owner) -> dict[str, int]:
    global _end, _step
    assert _end is not None and _step < len(_closes)
    source = sources._runtime
    assert source is not None
    migrator = create_engine_for(DatabaseRole.MIGRATOR)
    engine = create_engine_for(DatabaseRole.ENGINE)
    try:
        target = advance(_end, Timeframe.M1, 1)
        async with migrator.connect() as connection:
            now: datetime = (
                await connection.execute(text("SELECT clock_timestamp()"))
            ).scalar_one()
        if _step == 0:
            async with user_session(engine, body.user_id, role=DatabaseRole.ENGINE) as session:
                progress = (
                    await session.execute(
                        "SELECT r.status,p.eligible_after,p.recovery_required "
                        "FROM bot_strategy_progress p JOIN bot_runs r ON r.id=p.run_id "
                        "WHERE r.status<>'RETIRED'"
                    )
                ).one_or_none()
            if (
                progress is None
                or progress.status != "RUNNING"
                or progress.recovery_required
                or target <= progress.eligible_after
                or target <= now
            ):
                raise HTTPException(409, "FIXTURE_SIGNAL_IS_NOT_FUTURE_LIVE_INPUT")
        await asyncio.sleep(max(0, (target - now).total_seconds()) + 0.1)
        closes = (*_history, *(Money.of(value, "USDT") for value in _closes[: _step + 1]))
        start = advance(_end, Timeframe.M1, -250 - _step)
        candle = fixture_candles(start, closes, spread=Money.of(10, "USDT"))[-1]
        public_price(_closes[_step])
        await source.next_book()
        await source.price(_closes[_step])
        await append_recorded_candle(source.market, candle)
        _end, _step = target, _step + 1
        return {"step": _step}
    finally:
        await engine.dispose()
        await migrator.dispose()


@app.post("/__e2e/strategy/trigger", status_code=204)
async def trigger() -> None:
    public_price("435", trigger=True)


@app.post("/__e2e/strategy/metrics")
async def metrics(body: Owner) -> dict[str, object]:
    engine = create_engine_for(DatabaseRole.ENGINE)
    try:
        async with user_session(engine, body.user_id, role=DatabaseRole.ENGINE) as session:
            wallet = await get_wallet(session)
            assert wallet is not None
            baskets = (
                (
                    await session.execute(
                        "SELECT status,target::text AS target FROM bot_strategy_baskets "
                        "ORDER BY created_at"
                    )
                )
                .mappings()
                .all()
            )
            state = (await session.execute("SELECT strategy_state FROM bot_runs")).scalar_one()
            commands = (
                await session.execute(
                    "SELECT action,count(*) AS total FROM paper_order_commands GROUP BY action"
                )
            ).all()
            sides = (
                await session.execute(
                    "SELECT side,count(*) AS total FROM paper_orders GROUP BY side"
                )
            ).all()
            cancels = (
                await session.execute(
                    "SELECT c.idempotency_key,p.id AS protection_id FROM paper_order_commands c "
                    "LEFT JOIN paper_protections p ON p.entry_order_id=c.order_id "
                    "WHERE c.action='CANCEL'"
                )
            ).all()
            positions = (
                (
                    await session.execute(
                        "SELECT held_quantity::text AS quantity,total_cost::text AS cost,"
                        "realized_pnl::text AS realized_pnl FROM paper_position_projections "
                        "ORDER BY base,quote"
                    )
                )
                .mappings()
                .all()
            )
            return {
                "balance": wallet.balance.as_parts()["amount"],
                "baskets": [dict(row) for row in baskets],
                "state": state,
                "orders": (await session.execute("SELECT count(*) FROM paper_orders")).scalar_one(),
                "commands": {row.action: row.total for row in commands},
                "order_sides": {row.side: row.total for row in sides},
                "cancel_keys_valid": all(
                    row.protection_id is not None
                    and row.idempotency_key == uuid5(row.protection_id, "cancel-entry")
                    for row in cancels
                ),
                "unfinished_commands": (
                    await session.execute(
                        "SELECT count(*) FROM paper_order_commands c "
                        "LEFT JOIN paper_order_command_results r ON r.command_id=c.id "
                        "WHERE r.state IS DISTINCT FROM 'SUCCEEDED'"
                    )
                ).scalar_one(),
                "position_state": [dict(row) for row in positions],
                "active_reservations": (
                    await session.execute(
                        "SELECT count(*) FROM paper_reservations "
                        "WHERE quote_reserved<>0 OR base_reserved<>0"
                    )
                ).scalar_one(),
                "winning_triggers": (
                    await session.execute("SELECT count(*) FROM bot_basket_triggers")
                ).scalar_one(),
                "executions": (
                    await session.execute("SELECT count(*) FROM paper_position_events")
                ).scalar_one(),
            }
    finally:
        await engine.dispose()


app.mount("/", sources.app)
