from __future__ import annotations

from dataclasses import dataclass

from tiewtrade.market_data.config import MarketDataConfig
from tiewtrade.trading.session_config import MarketType

_SUPPORTED_BINANCE_INTERVALS = frozenset({"3m", "5m", "15m", "30m", "1h", "4h"})


class BinanceMarketDataPayloadError(ValueError):
    """Raised when Binance public market data cannot be safely normalized."""


@dataclass(frozen=True, slots=True)
class BinancePublicEndpoints:
    rest_klines_url: str
    websocket_base_url: str

    @classmethod
    def for_market_type(cls, market_type: MarketType) -> BinancePublicEndpoints:
        if market_type is MarketType.SPOT:
            return cls(
                "https://data-api.binance.vision/api/v3/klines",
                "wss://data-stream.binance.vision/ws",
            )
        if market_type is MarketType.FUTURES:
            return cls(
                "https://fapi.binance.com/fapi/v1/klines",
                "wss://fstream.binance.com/ws",
            )
        raise BinanceMarketDataPayloadError("unsupported Binance market type")

    @classmethod
    def validate_config(cls, config: MarketDataConfig) -> None:
        if config.timeframe not in _SUPPORTED_BINANCE_INTERVALS:
            raise BinanceMarketDataPayloadError("unsupported Binance kline interval")
