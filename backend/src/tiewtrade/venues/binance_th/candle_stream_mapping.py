"""Kline field names remain inside the venue adapter; all amounts stay exact."""

from datetime import datetime, timedelta

from tiewtrade.core.candle_preview import CandleObservation
from tiewtrade.core.market_data import Candle, CandleFinality, CandleSeries
from tiewtrade.core.money import Money, Quantity
from tiewtrade.venues.binance_th.mapping import (
    _integer,
    _mapping,
    _readable,
    _text,
    moment_from_millis,
)
from tiewtrade.venues.errors import VenueProtocolError


def candle_from_stream(
    *, payload: object, series: tuple[CandleSeries, ...], received_at: datetime
) -> CandleObservation:
    envelope = _mapping(payload)
    row = _mapping(envelope.get("data"))
    kline = _mapping(row.get("k"))
    selected = next(
        (
            item
            for item in series
            if item.base + item.quote == row.get("s") and item.timeframe.value == kline.get("i")
        ),
        None,
    )
    if (
        selected is None
        or row.get("e") != "kline"
        or kline.get("s") != row.get("s")
        or envelope.get("stream")
        != (f"{selected.base.lower()}{selected.quote.lower()}@kline_{selected.timeframe.value}")
        or type(kline.get("x")) is not bool
        or any(not isinstance(kline.get(field), str) for field in ("o", "h", "l", "c", "v"))
    ):
        raise VenueProtocolError()
    with _readable():
        opened = moment_from_millis(kline.get("t"))
        ended = moment_from_millis(kline.get("T")) + timedelta(milliseconds=1)
        hint = kline["x"] is True
        candle = Candle(
            base=selected.base,
            quote=selected.quote,
            timeframe=selected.timeframe,
            open_at=opened,
            end_at=ended,
            open=Money.of(_text(kline["o"]), selected.quote),
            high=Money.of(_text(kline["h"]), selected.quote),
            low=Money.of(_text(kline["l"]), selected.quote),
            close=Money.of(_text(kline["c"]), selected.quote),
            volume=Quantity.of(_text(kline["v"]), selected.base),
            finality=CandleFinality.UNCONFIRMED
            if hint or received_at >= ended
            else CandleFinality.OPEN,
            observed_at=received_at,
            series=selected,
        )
        return CandleObservation(
            candle,
            moment_from_millis(row.get("E")),
            received_at,
            _integer(kline.get("n")),
            _integer(kline.get("f")),
            _integer(kline.get("L")),
            hint,
        )
