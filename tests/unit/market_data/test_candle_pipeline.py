import asyncio
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from tiewtrade.market_data.candle import Candle
from tiewtrade.market_data.candle_pipeline import (
    CandlePipelineSinkError,
    CompletedCandlePipeline,
)
from tiewtrade.market_data.completed_candle_stream import CandleGapError
from tiewtrade.market_data.config import MarketDataConfig

RECEIVED_AT = datetime(2026, 1, 1, 0, 30, tzinfo=UTC)


def candle_at(minute: int) -> Candle:
    return Candle(
        symbol="BTCUSDT",
        timeframe="5m",
        open_time=datetime(2026, 1, 1, 0, minute, tzinfo=UTC),
        open=Decimal("100"),
        high=Decimal("102"),
        low=Decimal("99"),
        close=Decimal("101"),
        volume=Decimal("10"),
    )


class RecordingSink:
    def __init__(
        self,
        *,
        fail_at: int | None = None,
        fail_warm_up: bool = False,
    ) -> None:
        self._fail_at = fail_at
        self._fail_warm_up = fail_warm_up
        self.live_attempts = 0
        self.events: list[str] = []

    async def warm_up(
        self,
        candles: tuple[Candle, ...],
        *,
        received_at: datetime,
    ) -> None:
        if self._fail_warm_up:
            raise RuntimeError("warm-up failed")
        self.events.append("warm_up")

    async def process_completed(
        self,
        candle: Candle,
        *,
        received_at: datetime,
    ) -> None:
        self.live_attempts += 1
        if self.live_attempts == self._fail_at:
            raise RuntimeError("sink failed")
        self.events.append(f"sink:{candle.open_time.minute}")


def pipeline_for(
    sink: RecordingSink,
    deliveries: list[datetime],
) -> CompletedCandlePipeline:
    return CompletedCandlePipeline(
        config=MarketDataConfig(symbol="BTCUSDT", timeframe="5m"),
        sink=sink,
        on_delivery=deliveries.append,
    )


def test_live_gap_does_not_reach_sink() -> None:
    sink = RecordingSink()
    deliveries: list[datetime] = []
    pipeline = pipeline_for(sink, deliveries)
    asyncio.run(
        pipeline.warm_up(
            (candle_at(0), candle_at(5)),
            expected_count=2,
            received_at=RECEIVED_AT,
        )
    )
    with pytest.raises(CandleGapError):
        asyncio.run(pipeline.process_live(candle_at(15), received_at=RECEIVED_AT))
    assert sink.events == ["warm_up"]
    assert deliveries == [candle_at(5).open_time]


def test_partial_backfill_records_only_successful_deliveries() -> None:
    sink = RecordingSink(fail_at=2)
    deliveries: list[datetime] = []
    pipeline = pipeline_for(sink, deliveries)
    asyncio.run(
        pipeline.warm_up(
            (candle_at(0), candle_at(5), candle_at(10)),
            expected_count=3,
            received_at=RECEIVED_AT,
        )
    )
    with pytest.raises(CandlePipelineSinkError):
        asyncio.run(
            pipeline.process_backfill(
                (candle_at(15), candle_at(20)),
                start=candle_at(15).open_time,
                end=candle_at(25).open_time,
                observed=candle_at(20),
                received_at=RECEIVED_AT,
                on_ready_for_delivery=lambda: sink.events.append("ready"),
            )
        )
    assert sink.events == ["warm_up", "ready", "sink:15"]
    assert deliveries == [
        candle_at(10).open_time,
        candle_at(15).open_time,
    ]


def test_duplicate_live_returns_false_without_sink_delivery() -> None:
    sink = RecordingSink()
    deliveries: list[datetime] = []
    pipeline = pipeline_for(sink, deliveries)
    asyncio.run(
        pipeline.warm_up(
            (candle_at(0), candle_at(5)),
            expected_count=2,
            received_at=RECEIVED_AT,
        )
    )
    accepted = asyncio.run(pipeline.process_live(candle_at(5), received_at=RECEIVED_AT))
    assert accepted is False
    assert sink.events == ["warm_up"]


def test_warm_up_sink_failure_does_not_record_delivery() -> None:
    deliveries: list[datetime] = []
    pipeline = pipeline_for(
        RecordingSink(fail_warm_up=True),
        deliveries,
    )
    with pytest.raises(CandlePipelineSinkError):
        asyncio.run(
            pipeline.warm_up(
                (candle_at(0),),
                expected_count=1,
                received_at=RECEIVED_AT,
            )
        )
    assert deliveries == []
