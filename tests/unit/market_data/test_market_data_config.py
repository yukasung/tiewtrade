from datetime import timedelta

import pytest

from tiewtrade.market_data.config import MarketDataConfig


def test_market_data_config_exposes_symbol_and_timeframe() -> None:
    config = MarketDataConfig(symbol="ETHUSDT", timeframe="15m")

    assert config.symbol == "ETHUSDT"
    assert config.timeframe == "15m"
    assert config.interval == timedelta(minutes=15)


@pytest.mark.parametrize("timeframe", ["3m", "5m", "15m", "30m", "1h", "4h"])
def test_market_data_config_accepts_supported_v1_timeframes(timeframe: str) -> None:
    config = MarketDataConfig(symbol="BTCUSDT", timeframe=timeframe)

    assert config.timeframe == timeframe


@pytest.mark.parametrize("timeframe", ["", "5", "0m", "-5m", "five minutes"])
def test_market_data_config_rejects_invalid_timeframe(timeframe: str) -> None:
    with pytest.raises(ValueError, match="timeframe"):
        MarketDataConfig(symbol="BTCUSDT", timeframe=timeframe)


def test_market_data_config_rejects_blank_symbol() -> None:
    with pytest.raises(ValueError, match="symbol"):
        MarketDataConfig(symbol="", timeframe="5m")


@pytest.mark.parametrize("timeframe", ["1m", "7m", "1d"])
def test_market_data_config_rejects_timeframe_outside_v1_session_options(
    timeframe: str,
) -> None:
    with pytest.raises(ValueError, match="supported V1 timeframe"):
        MarketDataConfig(symbol="BTCUSDT", timeframe=timeframe)
