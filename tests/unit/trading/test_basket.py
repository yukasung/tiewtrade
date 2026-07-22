from datetime import UTC, datetime
from decimal import Decimal

import pytest

from tiewtrade.trading.basket import Basket


def test_basket_reprices_take_profit_after_each_entry() -> None:
    basket = Basket(max_entries=10, take_profit_atr_multiplier=Decimal("3"))
    basket.add_entry(
        price=Decimal("100"),
        quantity=Decimal("1"),
        fee=Decimal("0.1"),
        filled_at=datetime(2026, 1, 1, tzinfo=UTC),
        atr=Decimal("2"),
        tick_size=Decimal("0.1"),
    )
    assert basket.take_profit_price == Decimal("106.0")

    basket.add_entry(
        price=Decimal("90"),
        quantity=Decimal("1"),
        fee=Decimal("0.09"),
        filled_at=datetime(2026, 1, 2, tzinfo=UTC),
        atr=Decimal("3"),
        tick_size=Decimal("0.1"),
    )

    assert basket.average_entry_price == Decimal("95")
    assert basket.take_profit_price == Decimal("104.0")


def test_close_subtracts_entry_and_exit_fees() -> None:
    basket = Basket(max_entries=10, take_profit_atr_multiplier=Decimal("3"))
    basket.add_entry(
        price=Decimal("100"),
        quantity=Decimal("1"),
        fee=Decimal("0.1"),
        filled_at=datetime(2026, 1, 1, tzinfo=UTC),
        atr=Decimal("2"),
        tick_size=Decimal("0.1"),
    )

    closed = basket.close(
        exit_price=Decimal("106"),
        exit_fee=Decimal("0.106"),
        closed_at=datetime(2026, 1, 2, tzinfo=UTC),
    )

    assert closed.realized_pnl == Decimal("5.794")


def test_basket_rejects_more_than_ten_entries() -> None:
    basket = Basket(max_entries=10, take_profit_atr_multiplier=Decimal("3"))
    for day in range(1, 11):
        basket.add_entry(
            price=Decimal("100"),
            quantity=Decimal("1"),
            fee=Decimal("0.1"),
            filled_at=datetime(2026, 1, day, tzinfo=UTC),
            atr=Decimal("2"),
            tick_size=Decimal("0.1"),
        )

    with pytest.raises(ValueError, match="maximum entries"):
        basket.add_entry(
            price=Decimal("100"),
            quantity=Decimal("1"),
            fee=Decimal("0.1"),
            filled_at=datetime(2026, 1, 11, tzinfo=UTC),
            atr=Decimal("2"),
            tick_size=Decimal("0.1"),
        )


def test_basket_configuration_cannot_exceed_ten_entries() -> None:
    with pytest.raises(ValueError, match="maximum entries"):
        Basket(max_entries=11, take_profit_atr_multiplier=Decimal("3"))


def test_basket_requires_utc_fill_timestamp() -> None:
    basket = Basket(max_entries=10, take_profit_atr_multiplier=Decimal("3"))

    with pytest.raises(ValueError, match="UTC"):
        basket.add_entry(
            price=Decimal("100"),
            quantity=Decimal("1"),
            fee=Decimal("0.1"),
            filled_at=datetime(2026, 1, 1),
            atr=Decimal("2"),
            tick_size=Decimal("0.1"),
        )


def test_basket_requires_utc_close_timestamp() -> None:
    basket = Basket(max_entries=10, take_profit_atr_multiplier=Decimal("3"))
    basket.add_entry(
        price=Decimal("100"),
        quantity=Decimal("1"),
        fee=Decimal("0.1"),
        filled_at=datetime(2026, 1, 1, tzinfo=UTC),
        atr=Decimal("2"),
        tick_size=Decimal("0.1"),
    )

    with pytest.raises(ValueError, match="UTC"):
        basket.close(
            exit_price=Decimal("106"),
            exit_fee=Decimal("0.106"),
            closed_at=datetime(2026, 1, 2),
        )
