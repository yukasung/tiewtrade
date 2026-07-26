from collections.abc import Callable

from tiewtrade.integrations.binance.public_endpoints import BinancePublicEndpoints
from tiewtrade.integrations.binance.public_market_data import BinancePublicMarketData
from tiewtrade.market_data.candle_source import MarketDataCandleSource
from tiewtrade.market_data.config import MarketDataConfig
from tiewtrade.market_data.runtime import (
    AsyncioRuntimeScheduler,
    MarketDataCandleSink,
    MarketDataRuntime,
    RuntimeScheduler,
)
from tiewtrade.trading.session_config import SessionConfig


def create_public_market_data_runtime(
    *,
    session: SessionConfig,
    market_data: MarketDataConfig,
    warm_up_count: int,
    sink: MarketDataCandleSink,
    scheduler: RuntimeScheduler | None = None,
    source_factory: Callable[
        [BinancePublicEndpoints], MarketDataCandleSource
    ] = BinancePublicMarketData,
) -> MarketDataRuntime:
    endpoints = BinancePublicEndpoints.for_market_type(session.market_type)
    source = source_factory(endpoints)
    return MarketDataRuntime(
        config=market_data,
        warm_up_count=warm_up_count,
        source=source,
        sink=sink,
        scheduler=scheduler or AsyncioRuntimeScheduler(),
    )
