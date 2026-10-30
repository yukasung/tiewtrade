"""Strict public depth/trade/capability mapping for Binance TH (F-15)."""

import json
from datetime import datetime
from hashlib import sha256
from itertools import pairwise

from tiewtrade.core.money import Money, Quantity, Scalar
from tiewtrade.core.order_book import BookLevel, BookState
from tiewtrade.core.orders import OrderConstraints, OrderType
from tiewtrade.core.positions import ExecutionSide, PositionPair
from tiewtrade.venues.binance_th.mapping import (
    _integer,
    _mapping,
    _readable,
    _sequence,
    _text,
    market_symbol,
    moment_from_millis,
)
from tiewtrade.venues.errors import VenueProtocolError
from tiewtrade.venues.order_books import (
    DepthSnapshot,
    DepthUpdate,
    ExecutionCapability,
    TradeObservation,
    TradeSample,
)
from tiewtrade.venues.symbols import Symbol


def _levels(value: object, symbol: Symbol, *, snapshot: bool) -> tuple[BookLevel, ...]:
    result: list[BookLevel] = []
    for entry in _sequence(value):
        row = _sequence(entry)
        if len(row) != 2:
            raise VenueProtocolError()
        with _readable():
            level = BookLevel(
                Money.of(_text(row[0]), symbol.quote), Quantity.of(_text(row[1]), symbol.base)
            )
        if snapshot and level.quantity.amount <= 0:
            raise VenueProtocolError()
        result.append(level)
    if len({level.price for level in result}) != len(result):
        raise VenueProtocolError()
    return tuple(result)


def snapshot_from_payload(symbol: Symbol, payload: object, received_at: datetime) -> DepthSnapshot:
    row = _mapping(payload)
    if set(row) != {"lastUpdateId", "bids", "asks"}:
        raise VenueProtocolError()
    identity = _integer(row["lastUpdateId"])
    if identity < 0:
        raise VenueProtocolError()
    bids = _levels(row["bids"], symbol, snapshot=True)
    asks = _levels(row["asks"], symbol, snapshot=True)
    if len(bids) > 1000 or len(asks) > 1000 or not bids or not asks:
        raise VenueProtocolError()
    with _readable():
        BookState(
            PositionPair(symbol.base, symbol.quote),
            1,
            1,
            received_at,
            received_at,
            bids,
            asks,
            False,
        )
    return DepthSnapshot(symbol, identity, bids, asks, received_at)


def observation_from_stream(
    payload: object,
    symbols: tuple[Symbol, ...],
    received_at: datetime,
) -> DepthUpdate | TradeObservation:
    envelope = _mapping(payload)
    if set(envelope) != {"stream", "data"}:
        raise VenueProtocolError()
    row = _mapping(envelope["data"])
    symbol = next((s for s in symbols if market_symbol(s) == row.get("s")), None)
    if symbol is None:
        raise VenueProtocolError()
    name = market_symbol(symbol).lower()
    if row.get("e") == "depthUpdate":
        if (
            set(row) != {"e", "E", "s", "U", "u", "b", "a"}
            or envelope["stream"] != f"{name}@depth@100ms"
        ):
            raise VenueProtocolError()
        first, last = _integer(row["U"]), _integer(row["u"])
        if first <= 0 or last < first:
            raise VenueProtocolError()
        return DepthUpdate(
            symbol,
            first,
            last,
            _levels(row["b"], symbol, snapshot=False),
            _levels(row["a"], symbol, snapshot=False),
            moment_from_millis(row["E"]),
            received_at,
        )
    if row.get("e") != "trade" or envelope["stream"] != f"{name}@trade":
        raise VenueProtocolError()
    if (
        set(row) != {"e", "E", "s", "t", "p", "q", "T", "m", "M"}
        or type(row["m"]) is not bool
        or type(row["M"]) is not bool
    ):
        raise VenueProtocolError()
    identity = _integer(row["t"])
    with _readable():
        price = Money.of(_text(row["p"]), symbol.quote)
        quantity = Quantity.of(_text(row["q"]), symbol.base)
    if identity <= 0 or price.amount <= 0 or quantity.amount <= 0:
        raise VenueProtocolError()
    return TradeObservation(
        symbol,
        identity,
        ExecutionSide.BUY if row["m"] else ExecutionSide.SELL,
        price,
        quantity,
        moment_from_millis(row["T"]),
        moment_from_millis(row["E"]),
        received_at,
    )


def trade_samples_from_payload(symbol: Symbol, payload: object) -> tuple[TradeSample, ...]:
    samples: list[TradeSample] = []
    for value in _sequence(payload):
        row = _mapping(value)
        if set(row) != {"a", "p", "q", "f", "l", "T", "m"} or type(row["m"]) is not bool:
            raise VenueProtocolError()
        aggregate = _integer(row["a"])
        first, last = _integer(row["f"]), _integer(row["l"])
        with _readable():
            price = Money.of(_text(row["p"]), symbol.quote)
            quantity = Quantity.of(_text(row["q"]), symbol.base)
        if aggregate < 0 or first < 0 or last < first or price.amount <= 0 or quantity.amount <= 0:
            raise VenueProtocolError()
        samples.append(
            TradeSample(
                symbol,
                aggregate,
                first,
                last,
                price,
                quantity,
                moment_from_millis(row["T"]),
            )
        )
    if any(
        current.aggregate_id != previous.aggregate_id + 1
        or current.first_trade_id != previous.last_trade_id + 1
        or current.occurred_at < previous.occurred_at
        for previous, current in pairwise(samples)
    ):
        raise VenueProtocolError()
    return tuple(samples)


def capability_from_pair(
    symbol: Symbol, payload: object, received_at: datetime
) -> ExecutionCapability:
    row = _mapping(payload)
    if (row.get("symbol"), row.get("baseAsset"), row.get("quoteAsset")) != (
        market_symbol(symbol),
        symbol.base,
        symbol.quote,
    ):
        raise VenueProtocolError()
    # The canonical public document preserves every rule, including unsupported ones.
    document = json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=False)
    version = sha256(document.encode()).hexdigest()
    filters: dict[str, dict[str, object]] = {}
    for entry in _sequence(row.get("filters")):
        rule = _mapping(entry)
        name = _text(rule.get("filterType"))
        if name in filters:
            raise VenueProtocolError()
        filters[name] = rule
    offered = tuple(_text(v) for v in _sequence(row.get("orderTypes")))
    required = {"PRICE_FILTER", "LOT_SIZE", "MIN_NOTIONAL"}
    if not required.issubset(filters):
        raise VenueProtocolError()
    price, lot, notional = (filters[name] for name in ("PRICE_FILTER", "LOT_SIZE", "MIN_NOTIONAL"))
    if (
        set(price) != {"filterType", "minPrice", "maxPrice", "tickSize"}
        or set(lot) != {"filterType", "minQty", "maxQty", "stepSize"}
        or set(notional) != {"filterType", "minNotional", "applyToMarket", "avgPriceMins"}
    ):
        raise VenueProtocolError()
    if type(notional["applyToMarket"]) is not bool or _integer(notional["avgPriceMins"]) < 0:
        raise VenueProtocolError()
    supported = required | {"PERCENT_PRICE", "MAX_NUM_ORDERS"}
    unsupported = set(filters) - supported
    if row.get("status") != "TRADING":
        unsupported.add("SYMBOL_NOT_TRADING")
    average_minutes = _integer(notional["avgPriceMins"])
    percent = filters.get("PERCENT_PRICE")
    percent_down = percent_up = None
    percent_minutes = 0
    if percent is not None:
        if set(percent) != {
            "filterType",
            "avgPriceMins",
            "multiplierDown",
            "multiplierUp",
        }:
            raise VenueProtocolError()
        percent_minutes = _integer(percent["avgPriceMins"])
        with _readable():
            percent_down = Scalar.of(_text(percent["multiplierDown"]))
            percent_up = Scalar.of(_text(percent["multiplierUp"]))
        if percent_minutes <= 0:
            raise VenueProtocolError()
    maximum_orders = None
    order_limit = filters.get("MAX_NUM_ORDERS")
    if order_limit is not None:
        if set(order_limit) != {"filterType", "maxNumOrders"}:
            raise VenueProtocolError()
        maximum_orders = _integer(order_limit["maxNumOrders"])
        if maximum_orders <= 0:
            raise VenueProtocolError()
    rules: list[OrderConstraints] = []
    for kind in (OrderType.MARKET, OrderType.LIMIT):
        failures = set(unsupported)
        if kind.value not in offered:
            failures.add("ORDER_TYPE_UNAVAILABLE")
        # No invented average-price input or fallback to the latest quote.
        if kind is OrderType.MARKET and notional["applyToMarket"] is not True:
            failures.add("MARKET_NOTIONAL_NOT_APPLIED")
        with _readable():
            rules.append(
                OrderConstraints(
                    PositionPair(symbol.base, symbol.quote),
                    version,
                    Quantity.of(_text(lot["minQty"]), symbol.base),
                    Quantity.of(_text(lot["stepSize"]), symbol.base),
                    Money.of(_text(notional["minNotional"]), symbol.quote),
                    Money.of(_text(price["tickSize"]), symbol.quote),
                    maximum_quantity=Quantity.of(_text(lot["maxQty"]), symbol.base),
                    minimum_price=Money.of(_text(price["minPrice"]), symbol.quote),
                    maximum_price=Money.of(_text(price["maxPrice"]), symbol.quote),
                    supported_types=(kind,),
                    unsupported_rules=tuple(sorted(failures)),
                    average_price_minutes=(
                        average_minutes if kind is OrderType.MARKET else percent_minutes
                    ),
                    percent_price_multiplier_down=(
                        percent_down if kind is OrderType.LIMIT else None
                    ),
                    percent_price_multiplier_up=(percent_up if kind is OrderType.LIMIT else None),
                    maximum_open_orders=maximum_orders,
                )
            )
    return ExecutionCapability(symbol, version, received_at, rules[0], rules[1], document)
