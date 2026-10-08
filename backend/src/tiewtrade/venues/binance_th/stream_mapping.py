"""Exact decoding of public trade stream and recovery responses."""

from datetime import datetime

from tiewtrade.core.realtime_prices import ObservationKind, QuoteObservation
from tiewtrade.venues.binance_th.mapping import (
    _integer,
    _mapping,
    _readable,
    _sequence,
    market_symbol,
    price_from_trade,
)
from tiewtrade.venues.errors import VenueProtocolError, VenueUnavailableError
from tiewtrade.venues.symbols import Symbol


def _observation(
    *, symbol: Symbol, trade: object, received_at: datetime, kind: ObservationKind
) -> QuoteObservation:
    row = _mapping(trade)
    price = price_from_trade(symbol=symbol, trade=row, received_at=received_at)
    with _readable():
        return QuoteObservation(
            source="primary_spot",
            base=symbol.base,
            quote=symbol.quote,
            amount=price.amount,
            trade_id=_integer(row.get("id")),
            trade_time=price.venue_time,
            received_at=received_at,
            observation_kind=kind,
        )


def quote_from_trades(
    *, symbol: Symbol, payload: object, received_at: datetime
) -> QuoteObservation:
    rows = _sequence(payload)
    if not rows:
        raise VenueUnavailableError()
    return _observation(
        symbol=symbol, trade=rows[-1], received_at=received_at, kind=ObservationKind.SNAPSHOT
    )


def quote_from_stream(
    *, payload: object, symbols: tuple[Symbol, ...], received_at: datetime
) -> QuoteObservation:
    envelope = _mapping(payload)
    row = _mapping(envelope.get("data"))
    symbol = next((pair for pair in symbols if market_symbol(pair) == row.get("s")), None)
    if (
        symbol is None
        or row.get("e") != "trade"
        or envelope.get("stream") != f"{market_symbol(symbol).lower()}@trade"
    ):
        raise VenueProtocolError()
    return _observation(
        symbol=symbol,
        trade={"price": row.get("p"), "time": row.get("T"), "id": row.get("t")},
        received_at=received_at,
        kind=ObservationKind.STREAM,
    )


def subscription_ack(payload: object, request_id: int) -> bool:
    row = _mapping(payload)
    if isinstance(row.get("id"), bool) or not isinstance(row.get("id"), int):
        raise VenueProtocolError()
    if "error" in row or "code" in row or row.get("result", "missing") is not None:
        raise VenueProtocolError()
    return row["id"] == request_id
