"""Canonical exact public-input serialization, also used by financial replay evidence."""

import json
from datetime import datetime
from typing import Any

from tiewtrade.core.money import Money, Quantity, Scalar
from tiewtrade.core.order_book import BookLevel, BookState, MarketInput, MarketTrade
from tiewtrade.core.orders import OrderConstraints, OrderType
from tiewtrade.core.positions import ExecutionSide, PositionPair


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def input_payload(value: MarketInput) -> str:
    row: dict[str, object] = {
        "base": value.pair.base,
        "quote": value.pair.quote,
        "input_id": value.input_id,
        "generation": value.generation,
        "received_at": value.received_at.isoformat(),
    }
    if isinstance(value, BookState):
        row.update(
            kind="BOOK",
            verified_at=value.verified_at.isoformat(),
            ready=value.ready,
            rebase=value.rebase,
            bids=[_level(v) for v in value.bids],
            asks=[_level(v) for v in value.asks],
            source_at=None if value.source_at is None else value.source_at.isoformat(),
            source_first_sequence=value.source_first_sequence,
            source_last_sequence=value.source_last_sequence,
            snapshot_sequence=value.snapshot_sequence,
        )
    else:
        row.update(
            kind="TRADE",
            trade_id=value.trade_id,
            side=value.resting_side.value,
            price=value.price.as_parts()["amount"],
            quantity=value.quantity.as_parts()["quantity"],
            ordering_proven=value.ordering_proven,
            source_at=None if value.source_at is None else value.source_at.isoformat(),
            source_event_at=None
            if value.source_event_at is None
            else value.source_event_at.isoformat(),
        )
    return canonical(row)


def _level(value: BookLevel) -> list[str]:
    return [value.price.as_parts()["amount"], value.quantity.as_parts()["quantity"]]


def _object(value: object) -> dict[str, Any]:
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, dict):
        raise ValueError("invalid stored execution document")
    return value


def input_from_payload(payload: object) -> MarketInput:
    row = _object(payload)
    pair = PositionPair(row["base"], row["quote"])
    common = (pair, row["input_id"], row["generation"], datetime.fromisoformat(row["received_at"]))
    if row["kind"] == "BOOK":

        def levels(key: str) -> tuple[BookLevel, ...]:
            return tuple(
                BookLevel(Money.of(v[0], pair.quote), Quantity.of(v[1], pair.base))
                for v in row[key]
            )

        return BookState(
            *common,
            datetime.fromisoformat(row["verified_at"]),
            levels("bids"),
            levels("asks"),
            row["ready"],
            row["rebase"],
            source_at=None
            if row.get("source_at") is None
            else datetime.fromisoformat(row["source_at"]),
            source_first_sequence=row.get("source_first_sequence"),
            source_last_sequence=row.get("source_last_sequence"),
            snapshot_sequence=row.get("snapshot_sequence"),
        )
    if row["kind"] != "TRADE":
        raise ValueError("unknown stored execution input")
    return MarketTrade(
        *common,
        row["trade_id"],
        ExecutionSide(row["side"]),
        Money.of(row["price"], pair.quote),
        Quantity.of(row["quantity"], pair.base),
        row["ordering_proven"],
        source_at=None
        if row.get("source_at") is None
        else datetime.fromisoformat(row["source_at"]),
        source_event_at=None
        if row.get("source_event_at") is None
        else datetime.fromisoformat(row["source_event_at"]),
    )


def constraints_payload(value: OrderConstraints) -> dict[str, object]:
    return {
        "base": value.pair.base,
        "quote": value.pair.quote,
        "version": value.version,
        "minimum_quantity": value.minimum_quantity.as_parts()["quantity"],
        "quantity_step": value.quantity_step.as_parts()["quantity"],
        "minimum_notional": value.minimum_notional.as_parts()["amount"],
        "price_tick": value.price_tick.as_parts()["amount"],
        "maximum_quantity": None
        if value.maximum_quantity is None
        else value.maximum_quantity.as_parts()["quantity"],
        "maximum_notional": None
        if value.maximum_notional is None
        else value.maximum_notional.as_parts()["amount"],
        "minimum_price": None
        if value.minimum_price is None
        else value.minimum_price.as_parts()["amount"],
        "maximum_price": None
        if value.maximum_price is None
        else value.maximum_price.as_parts()["amount"],
        "supported_types": [v.value for v in value.supported_types],
        "unsupported_rules": list(value.unsupported_rules),
        "average_price_minutes": value.average_price_minutes,
        "percent_price_multiplier_down": None
        if value.percent_price_multiplier_down is None
        else value.percent_price_multiplier_down.as_text(),
        "percent_price_multiplier_up": None
        if value.percent_price_multiplier_up is None
        else value.percent_price_multiplier_up.as_text(),
        "maximum_open_orders": value.maximum_open_orders,
    }


def constraints_from_payload(payload: object) -> OrderConstraints:
    row = _object(payload)
    pair = PositionPair(row["base"], row["quote"])

    def money(key: str) -> Money | None:
        return None if row[key] is None else Money.of(row[key], pair.quote)

    maximum = row["maximum_quantity"]
    return OrderConstraints(
        pair,
        row["version"],
        Quantity.of(row["minimum_quantity"], pair.base),
        Quantity.of(row["quantity_step"], pair.base),
        Money.of(row["minimum_notional"], pair.quote),
        Money.of(row["price_tick"], pair.quote),
        maximum_quantity=None if maximum is None else Quantity.of(maximum, pair.base),
        maximum_notional=money("maximum_notional"),
        minimum_price=money("minimum_price"),
        maximum_price=money("maximum_price"),
        supported_types=tuple(OrderType(v) for v in row["supported_types"]),
        unsupported_rules=tuple(row["unsupported_rules"]),
        average_price_minutes=row.get("average_price_minutes", 0),
        percent_price_multiplier_down=None
        if row.get("percent_price_multiplier_down") is None
        else Scalar.of(row["percent_price_multiplier_down"]),
        percent_price_multiplier_up=None
        if row.get("percent_price_multiplier_up") is None
        else Scalar.of(row["percent_price_multiplier_up"]),
        maximum_open_orders=row.get("maximum_open_orders"),
    )
