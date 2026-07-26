from tiewtrade.integrations.binance.public_endpoints import BinancePublicEndpoints
from tiewtrade.trading.session_config import MarketType


def test_market_type_selects_distinct_public_endpoint_profiles() -> None:
    spot = BinancePublicEndpoints.for_market_type(MarketType.SPOT)
    futures = BinancePublicEndpoints.for_market_type(MarketType.FUTURES)

    assert spot.rest_klines_url == "https://data-api.binance.vision/api/v3/klines"
    assert spot.websocket_base_url == "wss://data-stream.binance.vision/ws"
    assert futures.rest_klines_url == "https://fapi.binance.com/fapi/v1/klines"
    assert futures.websocket_base_url == "wss://fstream.binance.com/ws"
