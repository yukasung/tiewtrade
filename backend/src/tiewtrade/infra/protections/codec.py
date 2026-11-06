"""Canonical, validated protection documents used by immutable history and projections."""

from datetime import datetime
from typing import Any
from uuid import UUID

from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.orders import OrderConflictError, OrderOrigin, OrderScope, TradingMode
from tiewtrade.core.positions import PositionPair
from tiewtrade.core.protections import (
    Protection,
    ProtectionLeg,
    ProtectionPrices,
    ProtectionState,
    TriggerEvidence,
)
from tiewtrade.infra.paper_orders.codec import object_payload


def encode(value: Protection) -> dict[str, object]:
    trigger = value.trigger
    return {
        "id": str(value.protection_id),
        "owner": str(value.scope.owner_id),
        "episode": str(value.scope.episode_id),
        "mode": value.scope.mode.value,
        "origin": value.origin.value,
        "base": value.prices.pair.base,
        "quote": value.prices.pair.quote,
        "tp": None
        if value.prices.take_profit is None
        else value.prices.take_profit.as_parts()["amount"],
        "sl": None
        if value.prices.stop_loss is None
        else value.prices.stop_loss.as_parts()["amount"],
        "quantity": value.quantity.as_parts()["quantity"],
        "state": value.state.value,
        "revision": value.revision,
        "entry": None if value.entry_order_id is None else str(value.entry_order_id),
        "leg": None if value.winning_leg is None else value.winning_leg.value,
        "conflicted": value.conflicted,
        "setup_attempt": value.setup_attempt,
        "setup_due_at": None if value.setup_due_at is None else value.setup_due_at.isoformat(),
        "trigger": None
        if trigger is None
        else {
            "source": str(trigger.source_id),
            "generation": trigger.generation,
            "sequence": trigger.sequence,
            "price": trigger.price.as_parts()["amount"],
            "occurred_at": trigger.occurred_at.isoformat(),
            "received_at": trigger.received_at.isoformat(),
            "base": trigger.pair.base,
            "quote": trigger.pair.quote,
        },
    }


def decode(raw: Any) -> Protection:
    row = object_payload(raw)
    pair = PositionPair(row["base"], row["quote"])
    t = row["trigger"]
    value = Protection(
        UUID(row["id"]),
        OrderScope(UUID(row["owner"]), UUID(row["episode"]), TradingMode(row["mode"])),
        OrderOrigin(row["origin"]),
        ProtectionPrices(
            pair,
            None if row["tp"] is None else Money.of(row["tp"], pair.quote),
            None if row["sl"] is None else Money.of(row["sl"], pair.quote),
        ),
        Quantity.of(row["quantity"], pair.base),
        ProtectionState(row["state"]),
        row["revision"],
        None if row["entry"] is None else UUID(row["entry"]),
        None if row["leg"] is None else ProtectionLeg(row["leg"]),
        None
        if t is None
        else TriggerEvidence(
            UUID(t["source"]),
            t["generation"],
            t["sequence"],
            Money.of(t["price"], t["quote"]),
            datetime.fromisoformat(t["occurred_at"]),
            datetime.fromisoformat(t["received_at"]),
            PositionPair(t["base"], t["quote"]),
        ),
        row["conflicted"],
        row["setup_attempt"],
        None if row["setup_due_at"] is None else datetime.fromisoformat(row["setup_due_at"]),
    )
    if row != encode(value):
        raise OrderConflictError("noncanonical protection document")
    return value
