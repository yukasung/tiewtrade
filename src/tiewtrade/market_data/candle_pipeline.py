from collections.abc import Callable
from copy import deepcopy
from datetime import datetime
from typing import Protocol

from tiewtrade.market_data.candle import Candle
from tiewtrade.market_data.completed_candle_stream import (
    CandleGapError,
    CompletedCandleStream,
)
from tiewtrade.market_data.config import MarketDataConfig


class CandlePipelineInputError(ValueError):
    pass


class CandlePipelineSinkError(RuntimeError):
    pass


class MarketDataCandleSink(Protocol):
    async def warm_up(
        self,
        candles: tuple[Candle, ...],
        *,
        received_at: datetime,
    ) -> None: ...

    async def process_completed(
        self,
        candle: Candle,
        *,
        received_at: datetime,
    ) -> None: ...


class CompletedCandlePipeline:
    def __init__(
        self,
        *,
        config: MarketDataConfig,
        sink: MarketDataCandleSink,
        on_delivery: Callable[[datetime], None],
    ) -> None:
        self._config = config
        self._sink = sink
        self._on_delivery = on_delivery
        self._candles = CompletedCandleStream(config)

    async def warm_up(
        self,
        candles: tuple[Candle, ...],
        *,
        expected_count: int,
        received_at: datetime,
    ) -> None:
        try:
            if expected_count <= 0:
                raise ValueError("expected_count must be positive")
            if len(candles) < expected_count:
                raise ValueError("insufficient warm-up candles")
            for candle in candles:
                if not self._candles.accept(candle, received_at):
                    raise ValueError("warm-up requires new completed candles")
        except ValueError as error:
            raise CandlePipelineInputError from error
        try:
            await self._sink.warm_up(candles, received_at=received_at)
        except Exception as error:
            raise CandlePipelineSinkError from error
        self._on_delivery(candles[-1].open_time)

    async def process_live(
        self,
        candle: Candle,
        *,
        received_at: datetime,
    ) -> bool:
        try:
            accepted = self._candles.accept(candle, received_at)
        except CandleGapError:
            raise
        except ValueError as error:
            raise CandlePipelineInputError from error
        if not accepted:
            return False
        await self._deliver(candle, received_at=received_at)
        return True

    async def process_backfill(
        self,
        candles: tuple[Candle, ...],
        *,
        start: datetime,
        end: datetime,
        observed: Candle | None,
        received_at: datetime,
        on_ready_for_delivery: Callable[[], None],
    ) -> None:
        try:
            if start < end and not candles:
                raise ValueError("backfill must not be empty")
            if start >= end and candles:
                raise ValueError("backfill must be empty when no range is missing")
            validation_candles = deepcopy(self._candles)
            accepted: list[Candle] = []
            for candle in candles:
                if not validation_candles.accept(candle, received_at):
                    raise ValueError("backfill requires new completed candles")
                accepted.append(candle)
            if accepted:
                reached = accepted[-1].open_time + self._config.interval
                if reached != end:
                    raise ValueError("backfill did not reach requested boundary")
            if observed is not None and validation_candles.accept(
                observed, received_at
            ):
                raise ValueError("buffered observation was not covered by backfill")
        except ValueError as error:
            raise CandlePipelineInputError from error

        for candle in accepted:
            self._candles.accept(candle, received_at)
        on_ready_for_delivery()
        for candle in accepted:
            await self._deliver(candle, received_at=received_at)

    async def _deliver(
        self,
        candle: Candle,
        *,
        received_at: datetime,
    ) -> None:
        try:
            await self._sink.process_completed(candle, received_at=received_at)
        except Exception as error:
            raise CandlePipelineSinkError from error
        self._on_delivery(candle.open_time)
