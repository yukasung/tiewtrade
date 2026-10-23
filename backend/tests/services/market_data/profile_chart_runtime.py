"""Controlled public-candle workload for F-12 V-17; no exchange I/O."""

import argparse
import asyncio
import json
import os
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic

from redis.asyncio import Redis

from tiewtrade.core.candle_preview import CandleObservation
from tiewtrade.core.market_data import (
    Candle,
    CandleFinality,
    CandleSeries,
    CandleWindow,
    Timeframe,
    advance,
    align_floor,
    expected_opens,
)
from tiewtrade.core.money import Money, Quantity
from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.infra.realtime.notifications import RedisNotifications
from tiewtrade.services.market_data.candle_realtime import CandleSupervisor
from tiewtrade.services.market_data.ingestion import run_round
from tiewtrade.services.market_data.main import ROUND_INTERVAL
from tiewtrade.venues.candle_streams import CandleFeedEvent, FeedCandle
from tiewtrade.venues.candles import CandlePage
from tiewtrade.venues.errors import VenueUnavailableError
from tiewtrade.venues.price_streams import FeedConnected
from tiewtrade.venues.symbols import Symbol

SERIES = tuple(CandleSeries("BTC", "USDT", timeframe) for timeframe in Timeframe)
FAULT_TIMEFRAMES = frozenset(tuple(Timeframe)[:5])


def memory_bytes(field: str) -> int:
    return next(
        int(line.split()[1]) * 1024
        for line in Path("/proc/self/status").read_text().splitlines()
        if line.startswith(field + ":")
    )


class WorkloadFeed:
    def __init__(self, seconds: int) -> None:
        self.seconds = seconds
        self.sequence = {series.timeframe: 0 for series in SERIES}

    async def events(
        self, requested: tuple[CandleSeries, ...]
    ) -> AsyncGenerator[CandleFeedEvent, None]:
        assert set(SERIES).issubset(requested)
        yield FeedConnected(1)
        started = monotonic()
        cursor = 0
        while monotonic() - started < self.seconds:
            elapsed = monotonic() - started
            rate = 150 if elapsed % 60 < 10 else 15
            series = SERIES[cursor % len(SERIES)]
            cursor += 1
            sequence = self.sequence[series.timeframe] + 1
            self.sequence[series.timeframe] = sequence
            now = datetime.now(UTC)
            opened = align_floor(now, series.timeframe)
            closed = advance(opened, series.timeframe, 1)
            close = Money.of(f"100.{sequence % 1_000_000_000:09d}", "USDT")
            candle = Candle(
                series.base,
                series.quote,
                series.timeframe,
                opened,
                closed,
                Money.of(100, "USDT"),
                Money.of(101, "USDT"),
                Money.of(99, "USDT"),
                close,
                Quantity.of("1.125", "BTC"),
                CandleFinality.OPEN,
                now,
            )
            yield FeedCandle(
                1,
                CandleObservation(candle, now, now, sequence, 1, sequence, False),
            )
            await asyncio.sleep(1 / rate)


class ControlledCandleSource:
    """Exercise real ingestion retries, partial gaps and source commits without network I/O."""

    max_request_span = None

    def __init__(self, evidence: Path) -> None:
        self.evidence = evidence
        self.attempts: dict[tuple[str, Timeframe], int] = {}

    def max_request_slots(self, timeframe: Timeframe) -> int:
        return 1000

    async def fetch_candles(
        self,
        symbol: Symbol,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
        limit: int,
    ) -> CandlePage:
        key = (symbol.base, timeframe)
        attempt = self.attempts.get(key, 0) + 1
        self.attempts[key] = attempt
        controlled_fault = symbol.base == "BTC" and timeframe in FAULT_TIMEFRAMES
        outcome = "COMPLETE"
        if controlled_fault and attempt == 1:
            outcome = "SOURCE_UNAVAILABLE"
            self._record(symbol, timeframe, attempt, outcome, 0)
            raise VenueUnavailableError()
        opens = list(expected_opens(CandleWindow(start, end), timeframe))[:limit]
        if controlled_fault and attempt == 2 and opens:
            opens.pop()
            outcome = "PARTIAL_GAP"
        observed = datetime.now(UTC)
        amount = f"100.{attempt:09d}"
        candles = tuple(
            Candle(
                symbol.base,
                symbol.quote,
                timeframe,
                opened,
                advance(opened, timeframe, 1),
                Money.of(100, symbol.quote),
                Money.of(101, symbol.quote),
                Money.of(99, symbol.quote),
                Money.of(amount, symbol.quote),
                Quantity.of("1.125", symbol.base),
                CandleFinality.CLOSED
                if advance(opened, timeframe, 1) <= observed
                else CandleFinality.UNCONFIRMED,
                observed,
            )
            for opened in opens
        )
        self._record(symbol, timeframe, attempt, outcome, len(candles))
        return CandlePage(symbol, timeframe, CandleWindow(start, end), candles, observed)

    def _record(
        self,
        symbol: Symbol,
        timeframe: Timeframe,
        attempt: int,
        outcome: str,
        rows: int,
    ) -> None:
        with self.evidence.open("a", encoding="utf-8") as output:
            output.write(
                json.dumps(
                    {
                        "recorded_at": str(datetime.now(UTC)),
                        "base": symbol.base,
                        "timeframe": timeframe.value,
                        "attempt": attempt,
                        "outcome": outcome,
                        "rows": rows,
                    }
                )
                + "\n"
            )


class MeasuredSupervisor(CandleSupervisor):
    def __init__(self, *args: object, evidence: Path, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self.evidence = evidence
        self.baseline = memory_bytes("VmRSS")

    async def _flush(self) -> None:
        pending = tuple(self.rows[key][0] for key in self.dirty)
        started = monotonic()
        await super()._flush()
        committed = datetime.now(UTC)
        with self.evidence.open("a", encoding="utf-8") as output:
            for observation in pending:
                output.write(
                    json.dumps(
                        {
                            "recorded_at": str(committed),
                            "base": observation.candle.base,
                            "timeframe": observation.candle.timeframe.value,
                            "event_at": str(observation.event_at),
                            "commit_seconds": max(
                                0.0, (committed - observation.received_at).total_seconds()
                            ),
                            "flush_seconds": monotonic() - started,
                            "rows_in_memory": len(self.rows),
                            "dirty_after": len(self.dirty),
                            "rss_delta_upper_bytes": max(0, memory_bytes("VmHWM") - self.baseline),
                        }
                    )
                    + "\n"
                )


async def run(seconds: int) -> None:
    evidence = Path("/evidence")
    evidence.mkdir(parents=True, exist_ok=True)
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    redis_url = os.environ["TIEWTRADE_REDIS_URL_MARKET_DATA"]
    redis = Redis.from_url(redis_url)
    notifications = RedisNotifications(redis, channel="market.candles.changed")
    supervisor = MeasuredSupervisor(
        engine,
        WorkloadFeed(seconds),
        notifications,
        evidence=evidence / "market-metrics.jsonl",
    )

    async def ingest() -> None:
        source = ControlledCandleSource(evidence / "source-metrics.jsonl")
        started = monotonic()
        while monotonic() - started < seconds:
            summary = await run_round(engine, source, "f12-v17-controlled", datetime.now(UTC))
            with (evidence / "ingestion-metrics.jsonl").open("a", encoding="utf-8") as output:
                output.write(
                    json.dumps(
                        {
                            "recorded_at": str(datetime.now(UTC)),
                            "attempts": summary.attempts,
                            "stored": summary.stored,
                            "stale": summary.stale,
                        }
                    )
                    + "\n"
                )
            await asyncio.sleep(ROUND_INTERVAL.total_seconds())

    try:
        async with asyncio.timeout(seconds + 30):
            await asyncio.gather(supervisor.run(), ingest())
    except TimeoutError:
        pass
    finally:
        await notifications.close()
        await redis.aclose()
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=int, required=True)
    arguments = parser.parse_args()
    asyncio.run(run(arguments.seconds))
