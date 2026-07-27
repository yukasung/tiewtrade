from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import datetime
from decimal import Decimal
from uuid import UUID

import pytest

from tiewtrade.application.public_market_data_runtime import (
    create_public_market_data_runtime,
)
from tiewtrade.integrations.binance.public_endpoints import BinancePublicEndpoints
from tiewtrade.market_data.candle import Candle
from tiewtrade.market_data.config import MarketDataConfig
from tiewtrade.market_data.runtime import MarketDataRuntime
from tiewtrade.strategies.rsi_step_grid.preset import RsiStepGridPreset
from tiewtrade.trading.entry_policy import EntryPolicy
from tiewtrade.trading.futures_policy import FuturesTradingPolicy
from tiewtrade.trading.session_config import MarketType, SessionConfig, TradeMode
from tiewtrade.trading.spot_policy import SpotTradingPolicy


class FakePublicCandleSource:
    def __init__(self) -> None:
        self.requested_warm_up_counts: list[int] = []

    async def load_recent(
        self,
        config: MarketDataConfig,
        *,
        count: int,
        completed_before: datetime,
    ) -> tuple[Candle, ...]:
        self.requested_warm_up_counts.append(count)
        return ()

    async def load_range(
        self,
        config: MarketDataConfig,
        *,
        start: datetime,
        end: datetime,
    ) -> tuple[Candle, ...]:
        raise AssertionError("unit composition must not backfill market data")

    def stream_completed(self, config: MarketDataConfig) -> AsyncIterator[Candle]:
        return self._stream_completed()

    async def close(self) -> None:
        return None

    async def _stream_completed(self) -> AsyncIterator[Candle]:
        if False:
            yield


class RecordingSink:
    async def warm_up(
        self, candles: tuple[Candle, ...], *, received_at: datetime
    ) -> None:
        return None

    async def process_completed(self, candle: Candle, *, received_at: datetime) -> None:
        return None


@pytest.mark.parametrize(
    ("market_type", "expected_rest_url", "expected_websocket_url"),
    [
        (
            MarketType.SPOT,
            "https://data-api.binance.vision/api/v3/klines",
            "wss://data-stream.binance.vision/ws",
        ),
        (
            MarketType.FUTURES,
            "https://fapi.binance.com/fapi/v1/klines",
            "wss://fstream.binance.com/ws",
        ),
    ],
)
def test_session_market_type_selects_public_endpoint_before_source_creation(
    market_type: MarketType,
    expected_rest_url: str,
    expected_websocket_url: str,
) -> None:
    selected_endpoints: list[BinancePublicEndpoints] = []
    fake_source = FakePublicCandleSource()

    def source_factory(
        endpoints: BinancePublicEndpoints,
    ) -> FakePublicCandleSource:
        selected_endpoints.append(endpoints)
        return fake_source

    runtime = create_public_market_data_runtime(
        session=session_config(market_type),
        market_data=MarketDataConfig(symbol="ETHUSDT", timeframe="15m"),
        preset=RsiStepGridPreset.v1(),
        sink=RecordingSink(),
        source_factory=source_factory,
    )

    assert isinstance(runtime, MarketDataRuntime)
    assert selected_endpoints == [
        BinancePublicEndpoints(
            rest_klines_url=expected_rest_url,
            websocket_base_url=expected_websocket_url,
        )
    ]
    asyncio.run(runtime.run())
    assert fake_source.requested_warm_up_counts == [15]


def session_config(market_type: MarketType) -> SessionConfig:
    return SessionConfig(
        session_id=UUID("00000000-0000-0000-0000-000000000099"),
        preset_version="rsi-step-grid-v1",
        market_type=market_type,
        trade_mode=TradeMode.PAPER,
        available_capital=Decimal("1000"),
        fee_rate=Decimal("0.001"),
        slippage_bps=Decimal("2"),
        entry_policy=EntryPolicy(max_entries=4),
        spot_policy=(
            SpotTradingPolicy(trading_capital_ratio=Decimal("0.6"))
            if market_type is MarketType.SPOT
            else None
        ),
        futures_policy=(
            FuturesTradingPolicy.v1(leverage=3)
            if market_type is MarketType.FUTURES
            else None
        ),
    )
