from datetime import UTC, datetime
from decimal import Decimal

import pytest

from tiewtrade.trading.basket import Basket
from tiewtrade.trading.entry_policy import EntryPolicy


def policy(max_entries: int = 10) -> EntryPolicy:
    return EntryPolicy(max_entries=max_entries)


def test_basket_reprices_take_profit_after_each_entry() -> None:
    basket = Basket(policy=policy(), take_profit_atr_multiplier=Decimal("3"))
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


def test_basket_requires_positive_take_profit_multiplier() -> None:
    with pytest.raises(ValueError, match="take_profit_atr_multiplier"):
        Basket(
            policy=policy(),
            take_profit_atr_multiplier=Decimal("0"),
        )


def test_close_subtracts_entry_and_exit_fees() -> None:
    basket = Basket(policy=policy(), take_profit_atr_multiplier=Decimal("3"))
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


def test_basket_rejects_entries_beyond_configured_maximum() -> None:
    basket = Basket(policy=policy(4), take_profit_atr_multiplier=Decimal("3"))
    for day in range(1, 5):
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
            filled_at=datetime(2026, 1, 5, tzinfo=UTC),
            atr=Decimal("2"),
            tick_size=Decimal("0.1"),
        )


def test_basket_requires_utc_fill_timestamp() -> None:
    basket = Basket(policy=policy(), take_profit_atr_multiplier=Decimal("3"))

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
    basket = Basket(policy=policy(), take_profit_atr_multiplier=Decimal("3"))
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


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("price", Decimal("0")),
        ("quantity", Decimal("0")),
        ("fee", Decimal("-0.1")),
        ("atr", Decimal("-1")),
        ("tick_size", Decimal("0")),
    ],
)
def test_invalid_entry_does_not_mutate_basket(field: str, value: Decimal) -> None:
    basket = Basket(policy=policy(), take_profit_atr_multiplier=Decimal("3"))
    values = {
        "price": Decimal("100"),
        "quantity": Decimal("1"),
        "fee": Decimal("0.1"),
        "atr": Decimal("2"),
        "tick_size": Decimal("0.1"),
    }
    values[field] = value

    with pytest.raises(ValueError, match=field):
        basket.add_entry(
            **values,
            filled_at=datetime(2026, 1, 1, tzinfo=UTC),
        )

    assert basket.entry_count == 0


def test_closed_basket_cannot_close_or_accept_entries_twice() -> None:
    basket = Basket(policy=policy(), take_profit_atr_multiplier=Decimal("3"))
    basket.add_entry(
        price=Decimal("100"),
        quantity=Decimal("1"),
        fee=Decimal("0.1"),
        filled_at=datetime(2026, 1, 1, tzinfo=UTC),
        atr=Decimal("2"),
        tick_size=Decimal("0.1"),
    )
    basket.close(
        exit_price=Decimal("106"),
        exit_fee=Decimal("0.106"),
        closed_at=datetime(2026, 1, 2, tzinfo=UTC),
    )

    assert basket.is_closed
    with pytest.raises(ValueError, match="closed"):
        basket.close(
            exit_price=Decimal("106"),
            exit_fee=Decimal("0.106"),
            closed_at=datetime(2026, 1, 2, tzinfo=UTC),
        )
    with pytest.raises(ValueError, match="closed"):
        basket.add_entry(
            price=Decimal("100"),
            quantity=Decimal("1"),
            fee=Decimal("0.1"),
            filled_at=datetime(2026, 1, 3, tzinfo=UTC),
            atr=Decimal("2"),
            tick_size=Decimal("0.1"),
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [("exit_price", Decimal("0")), ("exit_fee", Decimal("-0.1"))],
)
def test_invalid_close_does_not_close_basket(field: str, value: Decimal) -> None:
    basket = Basket(policy=policy(), take_profit_atr_multiplier=Decimal("3"))
    basket.add_entry(
        price=Decimal("100"),
        quantity=Decimal("1"),
        fee=Decimal("0.1"),
        filled_at=datetime(2026, 1, 1, tzinfo=UTC),
        atr=Decimal("2"),
        tick_size=Decimal("0.1"),
    )
    values = {"exit_price": Decimal("106"), "exit_fee": Decimal("0.106")}
    values[field] = value

    with pytest.raises(ValueError, match=field):
        basket.close(
            **values,
            closed_at=datetime(2026, 1, 2, tzinfo=UTC),
        )

    assert not basket.is_closed
