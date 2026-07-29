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
        if not isinstance(payload, list):
            raise ValueError("REST kline payload must be a list")
        if len(payload) < 6:
            raise ValueError("REST kline payload must contain at least 6 fields")
        return _candle_from_values(
            payload[:6],
            config,
            field_names=("open_time", "open", "high", "low", "close", "volume"),
        )
    except BinanceMarketDataPayloadError:
        raise
    except (InvalidOperation, OverflowError, TypeError, ValueError) as error:
        raise BinanceMarketDataPayloadError(_INVALID_PAYLOAD_MESSAGE) from error


def parse_websocket_kline(payload: object, config: MarketDataConfig) -> Candle | None:
    """Normalize a valid closed WebSocket kline; ignore valid open updates."""
    try:
        if not isinstance(payload, Mapping):
            raise ValueError("WebSocket kline payload must be an object")

        symbol = _required_string(payload, "s")
        kline = _required_mapping(payload, "k")
        if symbol != config.symbol:
            raise ValueError("s must match configured symbol")
        if _required_string(kline, "s", field_name="k.s") != config.symbol:
            raise ValueError("k.s must match configured symbol")
        if _required_string(kline, "i", field_name="k.i") != config.timeframe:
            raise ValueError("k.i must match configured timeframe")

        is_closed = kline.get("x")
        if not isinstance(is_closed, bool):
            raise ValueError("k.x must be a boolean")
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
            field_names=("k.t", "k.o", "k.h", "k.l", "k.c", "k.v"),
        )
        if not is_closed:
            return None
        return candle
    except BinanceMarketDataPayloadError:
        raise
    except (InvalidOperation, OverflowError, TypeError, ValueError) as error:
        raise BinanceMarketDataPayloadError(_INVALID_PAYLOAD_MESSAGE) from error


def _candle_from_values(
    values: Sequence[object],
    config: MarketDataConfig,
    *,
    field_names: tuple[str, str, str, str, str, str],
) -> Candle:
    open_time = _utc_datetime(_required_milliseconds(values[0], name=field_names[0]))
    return Candle(
        symbol=config.symbol,
        timeframe=config.timeframe,
        open_time=open_time,
        open=_decimal_from_string(values[1], name=field_names[1]),
        high=_decimal_from_string(values[2], name=field_names[2]),
        low=_decimal_from_string(values[3], name=field_names[3]),
        close=_decimal_from_string(values[4], name=field_names[4]),
        volume=_decimal_from_string(values[5], name=field_names[5]),
    )


def _required_milliseconds(value: object, *, name: str) -> int:
    if type(value) is not int:
        raise ValueError(f"{name} must be an integer timestamp in milliseconds")
    return value


def _utc_datetime(milliseconds: int) -> datetime:
    seconds, remainder = divmod(milliseconds, 1000)
    if remainder:
        raise ValueError("timestamp milliseconds must align to a whole second")
    return datetime.fromtimestamp(seconds, tz=UTC)


def _decimal_from_string(value: object, *, name: str) -> Decimal:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a finite decimal string")
    try:
        decimal = Decimal(value)
    except InvalidOperation as error:
        raise ValueError(f"{name} must be a finite decimal string") from error
    if not decimal.is_finite():
        raise ValueError(f"{name} must be a finite decimal string")
    return decimal


def _required_string(
    payload: Mapping[object, object], key: str, *, field_name: str | None = None
) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise ValueError(f"{field_name or key} must be a string")
    return value


def _required_mapping(
    payload: Mapping[object, object], key: str
) -> Mapping[object, object]:
    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise ValueError(f"{key} must be an object")
    return value
