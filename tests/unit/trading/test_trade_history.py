from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from tests.support.trade_history_records import basket_result, trade_fill
from tiewtrade.trading.trade_history import BasketStatus


def test_trade_fill_is_immutable_and_preserves_exact_notional() -> None:
    fill = trade_fill()

    assert fill.notional == fill.price * fill.quantity
    with pytest.raises(FrozenInstanceError):
        fill.fill_id = "another-fill"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("filled_at_utc", datetime(2026, 1, 1), "filled_at_utc must use UTC"),
        (
            "filled_at_utc",
            datetime(2026, 1, 1, tzinfo=timezone(timedelta(hours=7))),
            "filled_at_utc must use UTC",
        ),
        ("price", Decimal("0"), "price must be a finite positive decimal"),
        ("price", Decimal("NaN"), "price must be a finite positive decimal"),
        ("quantity", Decimal("-1"), "quantity must be a finite positive decimal"),
        ("quantity", Decimal("Infinity"), "quantity must be a finite positive decimal"),
        ("notional", Decimal("201"), r"notional must equal price \* quantity"),
        (
            "commission",
            Decimal("-0.01"),
            "commission must be a finite non-negative decimal",
        ),
        ("entry_number", 0, "entry_number must be positive when present"),
        ("fill_id", "", "fill_id must not be empty"),
        ("commission_asset", "", "commission_asset must not be empty"),
    ],
)
def test_trade_fill_rejects_invalid_values(
    field: str, value: object, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        replace(trade_fill(), **{field: value})


def test_closed_basket_requires_close_time_and_balanced_net_pnl() -> None:
    basket = basket_result()

    assert basket.status is BasketStatus.CLOSED
    assert basket.net_realized_pnl == (
        basket.gross_realized_pnl - basket.trading_fees - basket.funding_fee
    )
    with pytest.raises(ValueError, match="net_realized_pnl"):
        replace(basket, net_realized_pnl=Decimal("99"))
    with pytest.raises(ValueError, match="closed Basket requires closed_at_utc"):
        replace(basket, closed_at_utc=None)


def test_open_basket_requires_no_close_time() -> None:
    with pytest.raises(ValueError, match="open Basket must not have closed_at_utc"):
        replace(basket_result(), status=BasketStatus.OPEN)

    open_basket = replace(basket_result(), status=BasketStatus.OPEN, closed_at_utc=None)

    assert open_basket.closed_at_utc is None


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("symbol", "", "symbol must not be empty"),
        ("timeframe", "", "timeframe must not be empty"),
        (
            "strategy_preset_version",
            "",
            "strategy_preset_version must not be empty",
        ),
        ("opened_at_utc", datetime(2026, 1, 1), "opened_at_utc must use UTC"),
        ("entry_count", 0, "entry_count must be at least 1"),
        (
            "invested_notional",
            Decimal("-1"),
            "invested_notional must be a finite non-negative decimal",
        ),
        (
            "trading_fees",
            Decimal("NaN"),
            "trading_fees must be a finite non-negative decimal",
        ),
        (
            "gross_realized_pnl",
            Decimal("Infinity"),
            "gross_realized_pnl must be finite",
        ),
        ("funding_fee", Decimal("NaN"), "funding_fee must be finite"),
        ("net_realized_pnl", Decimal("NaN"), "net_realized_pnl must be finite"),
    ],
)
def test_basket_result_rejects_invalid_values(
    field: str, value: object, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        replace(basket_result(), **{field: value})
