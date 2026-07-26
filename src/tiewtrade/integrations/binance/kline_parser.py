from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

from tiewtrade.integrations.binance.public_endpoints import (
    BinanceMarketDataPayloadError,
)
from tiewtrade.market_data.candle import Candle
from tiewtrade.market_data.config import MarketDataConfig

_INVALID_PAYLOAD_MESSAGE = "invalid Binance market-data payload"


def parse_rest_kline(payload: object, config: MarketDataConfig) -> Candle:
    """Normalize one Binance REST kline array into a validated Candle."""
    try:
        if not isinstance(payload, list) or len(payload) < 6:
            raise ValueError
        return _candle_from_values(payload[:6], config)
    except BinanceMarketDataPayloadError:
        raise
    except (InvalidOperation, OverflowError, TypeError, ValueError) as error:
        raise BinanceMarketDataPayloadError(_INVALID_PAYLOAD_MESSAGE) from error


def parse_websocket_kline(payload: object, config: MarketDataConfig) -> Candle | None:
    """Normalize a valid closed WebSocket kline; ignore valid open updates."""
    try:
        if not isinstance(payload, Mapping):
            raise ValueError

        symbol = _required_string(payload, "s")
        kline = _required_mapping(payload, "k")
        if symbol != config.symbol or _required_string(kline, "s") != config.symbol:
            raise ValueError
        if _required_string(kline, "i") != config.timeframe:
            raise ValueError

        is_closed = kline.get("x")
        if not isinstance(is_closed, bool):
            raise ValueError
        candle = _candle_from_values(
            [
                kline.get("t"),
                kline.get("o"),
                kline.get("h"),
                kline.get("l"),
                kline.get("c"),
                kline.get("v"),
            ],
            config,
        )
        if not is_closed:
            return None
        return candle
    except BinanceMarketDataPayloadError:
        raise
    except (InvalidOperation, OverflowError, TypeError, ValueError) as error:
        raise BinanceMarketDataPayloadError(_INVALID_PAYLOAD_MESSAGE) from error


def _candle_from_values(values: Sequence[object], config: MarketDataConfig) -> Candle:
    open_time = _utc_datetime(_required_milliseconds(values[0]))
    return Candle(
        symbol=config.symbol,
        timeframe=config.timeframe,
        open_time=open_time,
        open=_decimal_from_string(values[1]),
        high=_decimal_from_string(values[2]),
        low=_decimal_from_string(values[3]),
        close=_decimal_from_string(values[4]),
        volume=_decimal_from_string(values[5]),
    )


def _required_milliseconds(value: object) -> int:
    if type(value) is not int:
        raise ValueError
    return value


def _utc_datetime(milliseconds: int) -> datetime:
    return datetime.fromtimestamp(milliseconds / 1000, tz=UTC)


def _decimal_from_string(value: object) -> Decimal:
    if not isinstance(value, str):
        raise ValueError
    decimal = Decimal(value)
    if not decimal.is_finite():
        raise ValueError
    return decimal


def _required_string(payload: Mapping[object, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise ValueError
    return value


def _required_mapping(
    payload: Mapping[object, object], key: str
) -> Mapping[object, object]:
    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise ValueError
    return value
