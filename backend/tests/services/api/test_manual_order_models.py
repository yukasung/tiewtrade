"""Untrusted order shape and exact domain-boundary validation."""

from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from tiewtrade.core.money import MoneyError
from tiewtrade.core.orders import BaseSize, OrderError, OrderType, QuoteBudget, TradingMode
from tiewtrade.services.api.manual_order_models import NewOrderInput, manual_intent

_ADAPTER: TypeAdapter[NewOrderInput] = TypeAdapter(NewOrderInput)
_BASE: dict[str, object] = {
    "expected_wallet_id": str(uuid4()),
    "expected_episode_id": str(uuid4()),
    "base": "BTC",
    "quote": "USDT",
}


@pytest.mark.parametrize(
    "fields",
    [
        {"kind": "MARKET", "side": "BUY", "quote_budget": "100.000000000000000001"},
        {"kind": "MARKET", "side": "SELL", "base_quantity": "0.000000000000000001"},
        {
            "kind": "LIMIT",
            "side": "BUY",
            "base_quantity": "1",
            "limit_price": "100",
            "time_in_force": "GTC",
        },
        {
            "kind": "LIMIT",
            "side": "SELL",
            "base_quantity": "1",
            "limit_price": "100",
            "time_in_force": "GTC",
        },
    ],
)
def test_supported_variants_keep_exact_money_and_server_scope(fields: dict[str, object]) -> None:
    body = _ADAPTER.validate_python({**_BASE, **fields})
    owner, identity, key = uuid4(), uuid4(), uuid4()
    intent = manual_intent(body, owner_id=owner, order_id=identity, idempotency_key=key)
    assert intent.scope.owner_id == owner and intent.scope.mode is TradingMode.PAPER
    assert intent.order_id == identity and intent.idempotency_key == key
    assert intent.kind.value == fields["kind"]
    if intent.kind is OrderType.MARKET and intent.side.value == "BUY":
        assert isinstance(intent.size, QuoteBudget)
        assert intent.size.amount.as_parts()["amount"] == fields["quote_budget"]
    else:
        assert isinstance(intent.size, BaseSize)
        assert intent.size.quantity.as_parts()["quantity"] == fields["base_quantity"]


@pytest.mark.parametrize(
    "changes",
    [
        {"quote_budget": 100},
        {"quote_budget": True},
        {"quote_budget": None},
        {"quote_budget": ""},
        {"mode": "LIVE"},
        {"origin": "BOT"},
        {"owner_id": str(uuid4())},
        {"order_id": str(uuid4())},
        {"reduce_only": True},
        {"base_quantity": "1"},
        {"limit_price": "10"},
        {"time_in_force": "GTC"},
        {"kind": "STOP_LOSS"},
        {"side": "SELL"},
        {"base": "btc"},
        {"base": "USDT"},
        {"quote": "THB"},
    ],
)
def test_shape_rejects_coercion_and_client_controlled_fields(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        _ADAPTER.validate_python(
            {**_BASE, "kind": "MARKET", "side": "BUY", "quote_budget": "100", **changes}
        )


@pytest.mark.parametrize(
    "amount",
    [
        "0",
        "-1",
        "NaN",
        "Infinity",
        "100000000000000000000",
        "0.0000000000000000001",
    ],
)
def test_financial_bounds_are_enforced_by_domain(amount: str) -> None:
    body = _ADAPTER.validate_python(
        {**_BASE, "kind": "MARKET", "side": "BUY", "quote_budget": amount}
    )
    with pytest.raises((MoneyError, OrderError)):
        manual_intent(body, owner_id=uuid4(), order_id=uuid4(), idempotency_key=uuid4())


def test_limit_requires_gtc_and_never_accepts_market_units() -> None:
    valid = {
        **_BASE,
        "kind": "LIMIT",
        "side": "SELL",
        "base_quantity": "1",
        "limit_price": "100",
        "time_in_force": "GTC",
    }
    invalid: list[dict[str, object]] = [
        {"time_in_force": "IOC"},
        {"quote_budget": "100"},
        {"limit_price": 100},
    ]
    for changes in invalid:
        with pytest.raises(ValidationError):
            _ADAPTER.validate_python({**valid, **changes})
