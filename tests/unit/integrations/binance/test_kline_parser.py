from datetime import UTC, datetime
from decimal import Decimal

import pytest

from tiewtrade.integrations.binance.kline_parser import (
    BinanceMarketDataPayloadError,
    parse_rest_kline,
    parse_websocket_kline,
)
from tiewtrade.market_data.config import MarketDataConfig


def config(*, symbol: str = "BTCUSDT", timeframe: str = "5m") -> MarketDataConfig:
    return MarketDataConfig(symbol=symbol, timeframe=timeframe)


def closed_kline_payload(
    *, symbol: str = "BTCUSDT", timeframe: str = "5m"
) -> dict[str, object]:
    return {
        "s": symbol,
        "k": {
            "t": 1767225600000,
            "s": symbol,
            "i": timeframe,
            "o": "100.10",
            "h": "102.20",
            "l": "99.90",
            "c": "101.30",
            "v": "12.50",
            "x": True,
        },
    }


def open_kline_payload() -> dict[str, object]:
    payload = closed_kline_payload()
    kline = payload["k"]
    assert isinstance(kline, dict)
    kline["x"] = False
    return payload


def test_rest_kline_maps_exact_decimal_and_utc_values() -> None:
    candle = parse_rest_kline(
        [1767225600000, "100.10", "102.20", "99.90", "101.30", "12.50"],
        config(),
    )

    assert candle.symbol == "BTCUSDT"
    assert candle.timeframe == "5m"
    assert candle.open_time == datetime(2026, 1, 1, tzinfo=UTC)
    assert candle.open == Decimal("100.10")
    assert candle.high == Decimal("102.20")
    assert candle.low == Decimal("99.90")
    assert candle.close == Decimal("101.30")
    assert candle.volume == Decimal("12.50")


def test_closed_websocket_kline_maps_to_candle() -> None:
    candle = parse_websocket_kline(closed_kline_payload(), config())

    assert candle is not None
    assert candle.open_time == datetime(2026, 1, 1, tzinfo=UTC)
    assert candle.close == Decimal("101.30")


def test_open_websocket_kline_is_not_emitted() -> None:
    assert parse_websocket_kline(open_kline_payload(), config()) is None


@pytest.mark.parametrize(
    ("payload", "market_data_config"),
    [
        (closed_kline_payload(symbol="ETHUSDT"), config()),
        (closed_kline_payload(timeframe="3m"), config()),
    ],
)
def test_websocket_kline_with_mismatched_identity_is_rejected(
    payload: dict[str, object], market_data_config: MarketDataConfig
) -> None:
    with pytest.raises(BinanceMarketDataPayloadError, match="invalid Binance"):
        parse_websocket_kline(payload, market_data_config)


@pytest.mark.parametrize(
    "payload",
    [
        [],
        [1767225600000, "100.10", "102.20"],
        [1767225600000, "invalid", "102.20", "99.90", "101.30", "12.50"],
    ],
)
def test_malformed_rest_kline_is_rejected(payload: list[object]) -> None:
    with pytest.raises(BinanceMarketDataPayloadError, match="invalid Binance"):
        parse_rest_kline(payload, config())


def test_malformed_websocket_kline_is_rejected() -> None:
    with pytest.raises(BinanceMarketDataPayloadError, match="invalid Binance"):
        parse_websocket_kline({"s": "BTCUSDT", "k": {"x": True}}, config())


def test_unsupported_binance_interval_is_rejected_at_parser_boundary() -> None:
    with pytest.raises(BinanceMarketDataPayloadError, match="unsupported Binance"):
        parse_rest_kline(
            [1767225600000, "100.10", "102.20", "99.90", "101.30", "12.50"],
            config(timeframe="7m"),
        )
