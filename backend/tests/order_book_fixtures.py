"""Synthetic public prices; shapes checked against read-only TH endpoints 2026-10-18."""

from datetime import UTC, datetime, timedelta

from tiewtrade.venues.binance_th.order_book_mapping import (
    capability_from_pair,
    snapshot_from_payload,
)
from tiewtrade.venues.order_books import DepthSnapshot, ExecutionCapability
from tiewtrade.venues.symbols import Symbol

SYMBOL = Symbol("BTC", "USDT")
NOW = datetime(2026, 10, 18, tzinfo=UTC)


def snapshot(at: datetime = NOW, identity: int = 10, *, symbol: Symbol = SYMBOL) -> DepthSnapshot:
    return snapshot_from_payload(
        symbol,
        {
            "lastUpdateId": identity,
            "bids": [["99", "2"], ["1", "10"]],
            "asks": [["100", "10"], ["200", "10"]],
        },
        at,
    )


def pair_payload(*, venue_rules: bool = False, symbol: Symbol = SYMBOL) -> dict[str, object]:
    filters: list[dict[str, object]] = [
        {
            "filterType": "PRICE_FILTER",
            "minPrice": "0.01",
            "maxPrice": "1000000.0",
            "tickSize": "0.01",
        },
        {"filterType": "LOT_SIZE", "minQty": "0.001", "maxQty": "9000.0", "stepSize": "0.001"},
        {
            "filterType": "MIN_NOTIONAL",
            "minNotional": "5.0",
            "applyToMarket": True,
            "avgPriceMins": 5 if venue_rules else 0,
        },
    ]
    if venue_rules:
        filters.extend(
            [
                {
                    "filterType": "PERCENT_PRICE",
                    "avgPriceMins": 5,
                    "multiplierDown": "0.2",
                    "multiplierUp": "5.0",
                },
                {"filterType": "MAX_NUM_ORDERS", "maxNumOrders": 201},
            ]
        )
    return {
        "symbol": f"{symbol.base}{symbol.quote}",
        "baseAsset": symbol.base,
        "quoteAsset": symbol.quote,
        "status": "TRADING",
        "orderTypes": ["LIMIT", "MARKET"],
        "filters": filters,
    }


def capability(
    at: datetime = NOW, *, venue_rules: bool = False, symbol: Symbol = SYMBOL
) -> ExecutionCapability:
    return capability_from_pair(symbol, pair_payload(venue_rules=venue_rules, symbol=symbol), at)


def millis(at: datetime) -> int:
    return (at - datetime(1970, 1, 1, tzinfo=UTC)) // timedelta(milliseconds=1)


def depth_payload(
    first: int = 11, last: int = 11, at: datetime = NOW, *, symbol: Symbol = SYMBOL
) -> dict[str, object]:
    return {
        "stream": f"{symbol.base.lower()}{symbol.quote.lower()}@depth@100ms",
        "data": {
            "e": "depthUpdate",
            "E": millis(at),
            "s": f"{symbol.base}{symbol.quote}",
            "U": first,
            "u": last,
            "b": [],
            "a": [["100", "10"]],
        },
    }


def trade_payload(identity: int = 100, at: datetime = NOW) -> dict[str, object]:
    return {
        "stream": "btcusdt@trade",
        "data": {
            "e": "trade",
            "E": millis(at),
            "T": millis(at),
            "s": "BTCUSDT",
            "t": identity,
            "p": "99",
            "q": "2.5",
            "m": True,
            "M": True,
        },
    }
