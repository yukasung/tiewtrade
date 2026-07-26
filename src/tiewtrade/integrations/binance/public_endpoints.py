from __future__ import annotations

from dataclasses import dataclass

from tiewtrade.trading.session_config import MarketType


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
