import pytest

from tiewtrade.integrations.binance.kline_parser import BinanceMarketDataPayloadError
from tiewtrade.integrations.binance.public_endpoints import BinancePublicEndpoints
from tiewtrade.market_data.config import MarketDataConfig
from tiewtrade.trading.session_config import MarketType


def test_market_type_selects_distinct_public_endpoint_profiles() -> None:
    spot = BinancePublicEndpoints.for_market_type(MarketType.SPOT)
    futures = BinancePublicEndpoints.for_market_type(MarketType.FUTURES)

    assert spot.rest_klines_url == "https://data-api.binance.vision/api/v3/klines"
    assert spot.websocket_base_url == "wss://data-stream.binance.vision/ws"
    assert futures.rest_klines_url == "https://fapi.binance.com/fapi/v1/klines"
    assert futures.websocket_base_url == "wss://fstream.binance.com/ws"


@pytest.mark.parametrize("timeframe", ["3m", "5m", "15m", "30m", "1h", "4h"])
def test_supported_product_intervals_are_accepted(timeframe: str) -> None:
    BinancePublicEndpoints.validate_config(
        MarketDataConfig(symbol="BTCUSDT", timeframe=timeframe)
    )


def test_unsupported_product_interval_is_rejected_before_network_use() -> None:
    with pytest.raises(BinanceMarketDataPayloadError, match="unsupported Binance"):
        BinancePublicEndpoints.validate_config(
            MarketDataConfig(symbol="BTCUSDT", timeframe="7m")
        )
