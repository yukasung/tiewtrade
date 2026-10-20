"""Exact bounded matching checkpoints; immutable events retain the complete decision history."""

import json
from dataclasses import replace
from datetime import datetime
from typing import Any
from uuid import UUID

from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.order_book import BookState, MarketTrade, ShadowLevel
from tiewtrade.core.orders import (
    BaseSize,
    OrderConflictError,
    OrderIntent,
    OrderOrigin,
    OrderScope,
    OrderState,
    OrderStatus,
    OrderType,
    QuoteBudget,
    SimulationProfile,
    TimeInForce,
    TradingMode,
)
from tiewtrade.core.paper_matching import MatchingState
from tiewtrade.core.positions import ExecutionFact, ExecutionSide, FeeEffect, PositionPair
from tiewtrade.infra.market_data.order_book_codec import (
    constraints_from_payload,
    constraints_payload,
    input_from_payload,
    input_payload,
)


def object_payload(value: Any) -> dict[str, Any]:
    result = json.loads(value) if isinstance(value, str) else value
    if not isinstance(result, dict):
        raise OrderConflictError("stored order document is invalid")
    return result


def intent_payload(value: OrderIntent) -> dict[str, object]:
    return {
        "order_id": str(value.order_id),
        "key": str(value.idempotency_key),
        "owner": str(value.scope.owner_id),
        "episode": str(value.scope.episode_id),
        "mode": value.scope.mode.value,
        "base": value.pair.base,
        "quote": value.pair.quote,
        "origin": value.origin.value,
        "side": value.side.value,
        "kind": value.kind.value,
        "budget": value.size.amount.as_parts()["amount"]
        if isinstance(value.size, QuoteBudget)
        else None,
        "quantity": value.size.quantity.as_parts()["quantity"]
        if isinstance(value.size, BaseSize)
        else None,
        "limit": None if value.limit_price is None else value.limit_price.as_parts()["amount"],
        "tif": None if value.time_in_force is None else value.time_in_force.value,
    }


def intent_from_payload(payload: Any) -> OrderIntent:
    row = object_payload(payload)
    scope = OrderScope(UUID(row["owner"]), UUID(row["episode"]), TradingMode(row["mode"]))
    pair = PositionPair(row["base"], row["quote"])
    if (row["budget"] is None) == (row["quantity"] is None):
        raise OrderConflictError("ambiguous durable order size")
    size = (
        QuoteBudget(Money.of(row["budget"], pair.quote))
        if row["budget"] is not None
        else (BaseSize(Quantity.of(row["quantity"], pair.base)))
    )
    value = OrderIntent(
        UUID(row["order_id"]),
        UUID(row["key"]),
        scope,
        pair,
        OrderOrigin(row["origin"]),
        ExecutionSide(row["side"]),
        OrderType(row["kind"]),
        size,
        None if row["limit"] is None else Money.of(row["limit"], pair.quote),
        None if row["tif"] is None else TimeInForce(row["tif"]),
    )
    if row != intent_payload(value):
        raise OrderConflictError("noncanonical durable order intent")
    return value


def compact_state(state: MatchingState) -> MatchingState:
    # Retain the last trade across intervening books, so a source trade cannot fill twice.
    keep = {state.inputs[-1].input_id} if state.inputs else set()
    trade = next((v for v in reversed(state.inputs) if isinstance(v, MarketTrade)), None)
    if trade is not None:
        keep.add(trade.input_id)
    retained = [
        (v, c)
        for v, c in zip(state.inputs, state.input_constraints, strict=True)
        if v.input_id in keep
    ]
    return replace(
        state,
        orders=tuple(order for order in state.orders if not order.status.terminal),
        inputs=tuple(v for v, _ in retained),
        input_constraints=tuple(c for _, c in retained),
        executions=(),
    )


def state_payload(value: MatchingState) -> dict[str, object]:
    value = compact_state(value)
    return {
        "owner": str(value.scope.owner_id),
        "episode": str(value.scope.episode_id),
        "base": value.pair.base,
        "quote": value.pair.quote,
        "fee": value.profile.fee_version,
        "model": value.profile.liquidity_version,
        "sequence": value.execution_sequence,
        "orders": [
            {
                "intent": intent_payload(o.intent),
                "sequence": o.sequence,
                "accepted_at": o.accepted_at.isoformat(),
                "status": o.status.value,
                "filled": o.filled.as_parts()["quantity"],
                "spent": o.spent.as_parts()["amount"],
                "constraints": constraints_payload(o.admission_constraints),
                "resting": o.resting,
                "ahead": None if o.queue_ahead is None else o.queue_ahead.as_parts()["quantity"],
            }
            for o in value.orders
        ],
        "liquidity": [
            {
                "side": v.side.value,
                "price": v.price.as_parts()["amount"],
                "reported": v.reported.as_parts()["quantity"],
                "consumed": v.consumed.as_parts()["quantity"],
            }
            for v in value.liquidity
        ],
        "inputs": [json.loads(input_payload(v)) for v in value.inputs],
        "constraints": [constraints_payload(c) for c in value.input_constraints],
        "book": None if value.book is None else json.loads(input_payload(value.book)),
    }


def state_from_payload(payload: Any) -> MatchingState:
    row = object_payload(payload)
    scope = OrderScope(UUID(row["owner"]), UUID(row["episode"]), TradingMode.PAPER)
    pair = PositionPair(row["base"], row["quote"])
    orders = tuple(
        OrderState(
            intent_from_payload(o["intent"]),
            o["sequence"],
            datetime.fromisoformat(o["accepted_at"]),
            OrderStatus(o["status"]),
            Quantity.of(o["filled"], pair.base),
            Money.of(o["spent"], pair.quote),
            constraints_from_payload(o["constraints"]),
            o["resting"],
            None if o["ahead"] is None else Quantity.of(o["ahead"], pair.base),
        )
        for o in row["orders"]
    )
    liquidity = tuple(
        ShadowLevel(
            ExecutionSide(v["side"]),
            Money.of(v["price"], pair.quote),
            Quantity.of(v["reported"], pair.base),
            Quantity.of(v["consumed"], pair.base),
        )
        for v in row["liquidity"]
    )
    book = None if row["book"] is None else input_from_payload(row["book"])
    if book is not None and not isinstance(book, BookState):
        raise OrderConflictError("checkpoint book is invalid")
    return MatchingState(
        scope,
        pair,
        SimulationProfile(row["fee"], row["model"]),
        orders,
        liquidity,
        tuple(input_from_payload(v) for v in row["inputs"]),
        tuple(constraints_from_payload(v) for v in row["constraints"]),
        (),
        book,
        row["sequence"],
    )


def execution_from_payload(payload: Any) -> ExecutionFact:
    row = object_payload(payload)
    pair = PositionPair(row["base"], row["quote"])
    fee = row["fee"]
    fee_effect = (
        None
        if fee is None
        else FeeEffect(
            Money.of(fee["amount"], fee["currency"])
            if "currency" in fee
            else Quantity.of(fee["quantity"], fee["asset"])
        )
    )
    return ExecutionFact(
        UUID(row["execution_id"]),
        pair,
        ExecutionSide(row["side"]),
        Quantity.of(row["quantity"]["quantity"], row["quantity"]["asset"]),
        Money.of(row["quote_amount"]["amount"], row["quote_amount"]["currency"]),
        fee_effect,
        row["source_sequence"],
        datetime.fromisoformat(row["occurred_at"]),
    )
