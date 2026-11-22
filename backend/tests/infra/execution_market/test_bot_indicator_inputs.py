"""Real prepared F-11 data, warm-up and source invalidation through the bot boundary."""

import json
from dataclasses import replace
from datetime import datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market.test_bot_review_safety import (
    DOC,
    NoopStrategy,
    registry,
    seed_input_run,
)
from tests.infra.indicators.test_source import active as active
from tests.infra.risk_limits.test_execution import runtime
from tiewtrade.core.indicators import FORMULA_VERSION, IndicatorStream
from tiewtrade.core.market_data import (
    Candle,
    CandleFinality,
    CandleWindow,
    Timeframe,
    advance,
    align_floor,
)
from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.strategies import evaluate_strategy
from tiewtrade.infra.bots.evaluation import (
    PreparedQuote,
    QuoteEvaluation,
    evaluate_published_quote,
    pause_missing_inputs,
)
from tiewtrade.infra.bots.inputs import BotInputsUnavailableError, read_bot_indicators
from tiewtrade.infra.db import DatabaseRole, create_engine_for, user_session
from tiewtrade.infra.db.session import market_data_session
from tiewtrade.infra.indicators.codec import encode_checkpoint
from tiewtrade.infra.indicators.source import begin_source_write
from tiewtrade.infra.market_data.realtime_storage import read_snapshot
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot
from tiewtrade.services.engine.bot import run_bot_quote

pytestmark = pytest.mark.usefixtures("internal_database")


def fixture_candles(
    start: datetime,
    closes: tuple[Money, ...],
    *,
    spread: Money,
    timeframe: Timeframe = Timeframe.M1,
) -> tuple[Candle, ...]:
    candles = []
    previous = closes[0]
    for index, close in enumerate(closes):
        opened = advance(start, timeframe, index)
        closed = advance(opened, timeframe, 1)
        candles.append(
            Candle(
                "BTC",
                "USDT",
                timeframe,
                opened,
                closed,
                previous,
                max(previous, close) + spread,
                min(previous, close) - spread,
                close,
                Quantity.of(10, "BTC"),
                CandleFinality.CLOSED,
                closed,
            )
        )
        previous = close
    return tuple(candles)


async def append_recorded_candle(market: AsyncEngine, candle: Candle) -> None:
    async with market_data_session(market) as session:
        await begin_source_write(session)
        await session.execute(
            """INSERT INTO market_candles(source,base,quote,timeframe,open_at,end_at,
            open,high,low,close,volume,finality,observed_at,fetch_started_at,
            last_checked_at,ingestion_generation)
            VALUES('primary_spot','BTC','USDT','1m',:start,:end,:open,:high,:low,:close,
              10,:finality,:observed,:observed,clock_timestamp(),1)
            ON CONFLICT(source,base,quote,timeframe,open_at) DO UPDATE SET
              open=excluded.open,high=excluded.high,low=excluded.low,close=excluded.close,
              finality=excluded.finality,observed_at=excluded.observed_at,
              last_checked_at=excluded.last_checked_at""",
            {
                "start": candle.open_at,
                "end": candle.end_at,
                "observed": candle.observed_at,
                "finality": candle.finality.value,
                **{
                    name: getattr(candle, name).as_parts()["amount"]
                    for name in ("open", "high", "low", "close")
                },
            },
        )


async def seed_prepared(
    migrator: AsyncEngine,
    bars: int,
    reference: datetime,
    *,
    timeframe: Timeframe = Timeframe.M1,
    closes: tuple[Money, ...] | None = None,
) -> None:
    """Reader fixture: real source journal and exact F-11 codec, no production activation."""
    market = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        async with market_data_session(market) as session:
            await begin_source_write(session)
            now: datetime = (await session.execute("SELECT clock_timestamp()")).scalar_one()
            end = align_floor(reference, timeframe)
            start = advance(end, timeframe, -bars)
            if closes is not None and len(closes) != bars:
                raise ValueError("one close per completed candle required")
            candles = fixture_candles(
                start,
                closes or (Money.of(100, "USDT"),) * bars,
                timeframe=timeframe,
                spread=Money.of(0 if closes is None else 10, "USDT"),
            )
            await session.execute(
                """INSERT INTO market_candles(source,base,quote,timeframe,open_at,end_at,
                   open,high,low,close,volume,finality,observed_at,fetch_started_at,
                   last_checked_at,ingestion_generation)
                   SELECT 'primary_spot','BTC','USDT',:tf,c.open_at,c.end_at,
                     c.open,c.high,c.low,c.close,10,'CLOSED',c.end_at,c.end_at,:now,1
                   FROM jsonb_to_recordset(CAST(:candles AS jsonb)) AS c(
                     open_at timestamptz,end_at timestamptz,open numeric,high numeric,
                     low numeric,close numeric)
                   ON CONFLICT(source,base,quote,timeframe,open_at) DO UPDATE SET
                     open=excluded.open,high=excluded.high,low=excluded.low,close=excluded.close,
                     last_checked_at=excluded.last_checked_at""",
                {
                    "tf": timeframe.value,
                    "candles": json.dumps(
                        [
                            {
                                "open_at": c.open_at.isoformat(),
                                "end_at": c.end_at.isoformat(),
                                **{
                                    name: getattr(c, name).as_parts()["amount"]
                                    for name in ("open", "high", "low", "close")
                                },
                            }
                            for c in candles
                        ]
                    ),
                    "now": now,
                },
            )
            await session.execute(
                """INSERT INTO market_candle_demand(source,base,quote,timeframe,
                desired_start,desired_end,leased_start,leased_end,cursor,status,checked_at)
                VALUES('primary_spot','BTC','USDT',:tf,:lo,:hi,:lo,:hi,:hi,'COMPLETE',:now)
                ON CONFLICT(source,base,quote,timeframe) DO NOTHING""",
                {"tf": timeframe.value, "lo": start, "hi": end, "now": now},
            )
        identity = uuid4()
        calculation = CandleWindow(start, end)
        stream = IndicatorStream("BTC", "USDT", timeframe, now)
        checkpoints = [
            (
                start,
                encode_checkpoint(
                    stream,
                    generation_id=str(identity),
                    source="primary_spot",
                    calculation=calculation,
                    next_open_at=start,
                ),
            )
        ]
        for candle in candles:
            stream.feed(candle.open_at, candle, candle.end_at)
        checkpoints.append(
            (
                end,
                encode_checkpoint(
                    stream,
                    generation_id=str(identity),
                    source="primary_spot",
                    calculation=calculation,
                    next_open_at=end,
                ),
            )
        )
        async with migrator.begin() as connection:
            job = (
                await connection.execute(
                    text(
                        """INSERT INTO indicator_build_jobs(
                   source,base,quote,timeframe,formula_version,
                   desired_start,desired_end,first_eligible_at,availability_deadline,generation_sequence)
                   VALUES('primary_spot','BTC','USDT',:tf,:formula,:lo,:hi,
                     :now,CAST(:now AS timestamptz)+interval '600s',1)
                   ON CONFLICT(source,base,quote,timeframe,formula_version) DO UPDATE SET
                     desired_start=excluded.desired_start,desired_end=excluded.desired_end,
                     generation_sequence=indicator_build_jobs.generation_sequence+1
                   RETURNING id,generation_sequence"""
                    ),
                    {
                        "tf": timeframe.value,
                        "formula": FORMULA_VERSION,
                        "lo": start,
                        "hi": end,
                        "now": now,
                    },
                )
            ).one()
            await connection.execute(
                text(
                    """INSERT INTO indicator_generations(id,job_id,source,base,quote,timeframe,
                   formula_version,calculation_start,calculation_end,as_of,source_epoch,source_fence,
                   dataset_revision,checkpoint_count,codec_version,build_rollout_epoch,
                   candidate_sequence,claim_token,status,expires_at,prepared_at)
                   SELECT :id,:job,'primary_spot','BTC','USDT',:tf,:formula,:lo,:hi,:now,s.epoch,
                     s.revision,repeat('a',64),2,2,c.rollout_epoch,:sequence,:token,'READY',
                     CAST(:now AS timestamptz)+interval '6 hours 10 minutes',:now
                   FROM indicator_source_guard s CROSS JOIN indicator_rollout_control c"""
                ),
                {
                    "id": identity,
                    "job": job.id,
                    "sequence": job.generation_sequence,
                    "formula": FORMULA_VERSION,
                    "lo": start,
                    "hi": end,
                    "now": now,
                    "token": uuid4(),
                    "tf": timeframe.value,
                },
            )
            for moment, payload in checkpoints:
                await connection.execute(
                    text(
                        """INSERT INTO indicator_checkpoints
                           VALUES(:id,:moment,CAST(:payload AS jsonb))"""
                    ),
                    {"id": identity, "moment": moment, "payload": json.dumps(payload)},
                )
            await connection.execute(
                text(
                    """INSERT INTO indicator_heads
                       VALUES('primary_spot','BTC','USDT',:tf,:formula,:id)
                       ON CONFLICT(source,base,quote,timeframe,formula_version)
                       DO UPDATE SET generation_id=excluded.generation_id"""
                ),
                {"tf": timeframe.value, "formula": FORMULA_VERSION, "id": identity},
            )
            await connection.execute(
                text(
                    """UPDATE indicator_rollout_control SET mode='PREPARED',codec_version=2,
                       protocol_version=1,retention_policy='GRACE'"""
                )
            )
    finally:
        await market.dispose()


def indicator_strategy() -> NoopStrategy:
    value = NoopStrategy()
    value.descriptor = replace(
        value.descriptor, timeframe="1m", required_indicators=frozenset({"ema20", "ema200"})
    )
    return value


@pytest.mark.parametrize("bars", [10, 201])
async def test_prepared_indicator_readiness_controls_decisions_without_zero_fallback(
    active: None,
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    bars: int,
) -> None:
    value = indicator_strategy()
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000", account_use="BOT"
    ) as sources:
        async with market_data_session(sources.market) as session:
            current = await read_snapshot(session)
            quote = next(row.observation for row in current.rows if row.base == "BTC")
            assert quote is not None
        await seed_prepared(migrator_engine, bars, quote.trade_time)
        run = await seed_input_run(engine_engine, owner, wallet)
        result = await run_bot_quote(
            engine=engine_engine,
            owner=owner,
            run_id=run,
            registry=registry(value),
            worker_id=uuid4(),
        )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            assert (
                await session.execute("SELECT count(*) FROM paper_order_commands")
            ).scalar_one() == 0
            assert (
                await session.execute("SELECT count(*) FROM bot_decisions")
            ).scalar_one() == int(bars == 201)
            assert (await session.execute("SELECT status FROM bot_runs")).scalar_one() == (
                "RUNNING" if bars == 201 else "PAUSED"
            )
            if bars == 201:
                assert result is not None
                provenance = (
                    await session.execute("SELECT input_provenance FROM bot_decisions")
                ).scalar_one()
                assert FORMULA_VERSION in provenance["indicator_revision"]
            else:
                assert result is None
                assert (
                    await session.execute(
                        """SELECT details->>'reason' FROM bot_run_events
                           ORDER BY revision DESC LIMIT 1"""
                    )
                ).scalar_one() == "INDICATOR_NOT_READY"


async def test_source_correction_between_preparation_and_commit_cannot_advance_state(
    active: None,
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    value = indicator_strategy()
    executable = registry(value)
    worker = uuid4()
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000", account_use="BOT"
    ) as sources:
        async with market_data_session(sources.market) as session:
            current = await read_snapshot(session)
            quote = next(row.observation for row in current.rows if row.base == "BTC")
            assert quote is not None
        await seed_prepared(migrator_engine, 201, quote.trade_time)
        run = await seed_input_run(engine_engine, owner, wallet)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            prepared = await evaluate_published_quote(
                session, run, resolve=executable.implementation, worker_id=worker
            )
        assert isinstance(prepared, PreparedQuote)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            inputs = await read_bot_indicators(session, value.descriptor, prepared.snapshot)
        assert dict(inputs.values)["ema20"].value == Money.of(100, "USDT")
        assert dict(inputs.values)["ema200"].value == Money.of(100, "USDT")
        prepared = replace(
            prepared,
            snapshot=replace(
                prepared.snapshot, indicators=inputs.values, indicator_revision=inputs.revision
            ),
        )
        decision = evaluate_strategy(value, prepared.snapshot, DOC, DOC, scope=prepared.scope)
        async with market_data_session(sources.market) as session:
            await begin_source_write(session)
            await session.execute(
                """UPDATE market_candles SET high=101,close=101
                   WHERE base='BTC' AND timeframe='1m' AND open_at=:at""",
                {"at": inputs.open_at},
            )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            with pytest.raises(BotInputsUnavailableError, match="SOURCE_CHANGED"):
                await evaluate_published_quote(
                    session,
                    run,
                    resolve=executable.implementation,
                    worker_id=worker,
                    evaluation=QuoteEvaluation(prepared, decision),
                    indicator_inputs=inputs,
                )
            await pause_missing_inputs(session, prepared, "INDICATOR_SOURCE_CHANGED")
            assert (await session.execute("SELECT count(*) FROM bot_decisions")).scalar_one() == 0
            assert (
                await session.execute("SELECT count(*) FROM paper_order_commands")
            ).scalar_one() == 0
            assert (await session.execute("SELECT status FROM bot_runs")).scalar_one() == "PAUSED"
