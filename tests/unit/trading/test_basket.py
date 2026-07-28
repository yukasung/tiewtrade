from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from tiewtrade.trading.basket import Basket, BasketCloseReason
from tiewtrade.trading.entry_policy import EntryPolicy
from tiewtrade.trading.position import PositionSide


def policy(max_entries: int = 10) -> EntryPolicy:
    return EntryPolicy(max_entries=max_entries)


def basket_id() -> UUID:
    return UUID("00000000-0000-0000-0000-000000000092")


def test_take_profit_price_is_read_only() -> None:
    basket = Basket(
        basket_id=basket_id(),
        policy=policy(),
        take_profit_atr_multiplier=Decimal("3"),
    )

    with pytest.raises(AttributeError):
        setattr(basket, "take_profit_price", Decimal("999"))  # noqa: B010

    assert basket.take_profit_price is None


def test_basket_reprices_take_profit_after_each_entry() -> None:
    basket = Basket(
        basket_id=basket_id(), policy=policy(), take_profit_atr_multiplier=Decimal("3")
    )
    basket.add_entry(
        price=Decimal("100"),
        quantity=Decimal("3"),
        fee=Decimal("0.1"),
        filled_at=datetime(2026, 1, 1, tzinfo=UTC),
        atr=Decimal("2.03"),
        tick_size=Decimal("0.1"),
    )
    assert basket.take_profit_price == Decimal("106.0")

    basket.add_entry(
        price=Decimal("90"),
        quantity=Decimal("1"),
        fee=Decimal("0.09"),
        filled_at=datetime(2026, 1, 2, tzinfo=UTC),
        atr=Decimal("3.03"),
        tick_size=Decimal("0.1"),
    )

    assert basket.average_entry_price == Decimal("97.5")
    assert basket.take_profit_price == Decimal("106.5")


def test_short_basket_reprices_take_profit_below_average_and_rounds_up() -> None:
    basket = Basket(
        basket_id=basket_id(),
        policy=policy(),
        take_profit_atr_multiplier=Decimal("3"),
        position_side=PositionSide.SHORT,
    )

    basket.add_entry(
        position_side=PositionSide.SHORT,
        price=Decimal("100"),
        quantity=Decimal("1"),
        fee=Decimal("0.1"),
        filled_at=datetime(2026, 1, 1, tzinfo=UTC),
        atr=Decimal("1.03"),
        tick_size=Decimal("0.1"),
    )

    assert basket.position_side is PositionSide.SHORT
    assert basket.take_profit_price == Decimal("97.0")

    basket.add_entry(
        position_side=PositionSide.SHORT,
        price=Decimal("90"),
        quantity=Decimal("3"),
        fee=Decimal("0.09"),
        filled_at=datetime(2026, 1, 2, tzinfo=UTC),
        atr=Decimal("1.03"),
        tick_size=Decimal("0.1"),
    )

    assert basket.average_entry_price == Decimal("92.5")
    assert basket.take_profit_price == Decimal("89.5")


def test_one_way_basket_rejects_opposite_side_without_mutation() -> None:
    basket = Basket(
        basket_id=basket_id(),
        policy=policy(),
        take_profit_atr_multiplier=Decimal("3"),
        position_side=PositionSide.LONG,
    )

    with pytest.raises(ValueError, match="opposite"):
        basket.add_entry(
            position_side=PositionSide.SHORT,
            price=Decimal("100"),
            quantity=Decimal("1"),
            fee=Decimal("0.1"),
            filled_at=datetime(2026, 1, 1, tzinfo=UTC),
            atr=Decimal("2"),
            tick_size=Decimal("0.1"),
        )

    assert basket.entry_count == 0
    assert basket.entry_fees == Decimal("0")
    assert basket.take_profit_price is None


def test_invalid_short_take_profit_does_not_mutate_basket() -> None:
    basket = Basket(
        basket_id=basket_id(),
        policy=policy(),
        take_profit_atr_multiplier=Decimal("3"),
        position_side=PositionSide.SHORT,
    )

    with pytest.raises(ValueError, match="take profit price"):
        basket.add_entry(
            position_side=PositionSide.SHORT,
            price=Decimal("2"),
            quantity=Decimal("1"),
            fee=Decimal("0.01"),
            filled_at=datetime(2026, 1, 1, tzinfo=UTC),
            atr=Decimal("1"),
            tick_size=Decimal("0.1"),
        )

    assert basket.entry_count == 0
    assert basket.entry_fees == Decimal("0")
    assert basket.take_profit_price is None


def test_basket_requires_positive_take_profit_multiplier() -> None:
    with pytest.raises(ValueError, match="take_profit_atr_multiplier"):
        Basket(
            basket_id=basket_id(),
            policy=policy(),
            take_profit_atr_multiplier=Decimal("0"),
        )


def test_close_exposes_identity_and_pnl_accounting_components() -> None:
    expected_basket_id = basket_id()
    basket = Basket(
        basket_id=expected_basket_id,
        policy=policy(),
        take_profit_atr_multiplier=Decimal("3"),
    )
    basket.add_entry(
        price=Decimal("100"),
        quantity=Decimal("1"),
        fee=Decimal("0.2"),
        filled_at=datetime(2026, 1, 1, tzinfo=UTC),
        atr=Decimal("2"),
        tick_size=Decimal("0.1"),
    )

    closed = basket.close(
        exit_price=Decimal("120"),
        exit_fee=Decimal("0.22"),
        closed_at=datetime(2026, 1, 2, tzinfo=UTC),
    )

    assert closed.basket_id == expected_basket_id
    assert closed.gross_realized_pnl == Decimal("20")
    assert closed.trading_fees == Decimal("0.42")
    assert closed.funding_fee == Decimal("0")
    assert closed.net_realized_pnl == Decimal("19.58")
    assert closed.realized_pnl == closed.net_realized_pnl
    assert closed.position_side is PositionSide.LONG
    assert closed.close_reason is BasketCloseReason.TAKE_PROFIT


def test_short_basket_close_calculates_directional_pnl() -> None:
    basket = Basket(
        basket_id=basket_id(),
        policy=policy(),
        take_profit_atr_multiplier=Decimal("3"),
        position_side=PositionSide.SHORT,
    )
    basket.add_entry(
        position_side=PositionSide.SHORT,
        price=Decimal("100"),
        quantity=Decimal("2"),
        fee=Decimal("0.2"),
        filled_at=datetime(2026, 1, 1, tzinfo=UTC),
        atr=Decimal("2"),
        tick_size=Decimal("0.1"),
    )

    closed = basket.close(
        exit_price=Decimal("90"),
        exit_fee=Decimal("0.18"),
        closed_at=datetime(2026, 1, 2, tzinfo=UTC),
        close_reason=BasketCloseReason.TAKE_PROFIT,
    )

    assert closed.position_side is PositionSide.SHORT
    assert closed.close_reason is BasketCloseReason.TAKE_PROFIT
    assert closed.gross_realized_pnl == Decimal("20")
    assert closed.trading_fees == Decimal("0.38")
    assert closed.net_realized_pnl == Decimal("19.62")


def test_close_records_explicit_liquidation_reason() -> None:
    basket = Basket(
        basket_id=basket_id(), policy=policy(), take_profit_atr_multiplier=Decimal("3")
    )
    basket.add_entry(
        price=Decimal("100"),
        quantity=Decimal("1"),
        fee=Decimal("0.1"),
        filled_at=datetime(2026, 1, 1, tzinfo=UTC),
        atr=Decimal("2"),
        tick_size=Decimal("0.1"),
    )

    closed = basket.close(
        exit_price=Decimal("80"),
        exit_fee=Decimal("0.08"),
        closed_at=datetime(2026, 1, 2, tzinfo=UTC),
        close_reason=BasketCloseReason.LIQUIDATION,
    )

    assert closed.close_reason is BasketCloseReason.LIQUIDATION


def test_basket_exposes_accumulated_entry_fees() -> None:
    basket = Basket(
        basket_id=basket_id(), policy=policy(), take_profit_atr_multiplier=Decimal("3")
    )
    basket.add_entry(
        price=Decimal("100"),
        quantity=Decimal("1"),
        fee=Decimal("0.1"),
        filled_at=datetime(2026, 1, 1, tzinfo=UTC),
        atr=Decimal("2"),
        tick_size=Decimal("0.1"),
    )
    basket.add_entry(
        price=Decimal("90"),
        quantity=Decimal("1"),
        fee=Decimal("0.09"),
        filled_at=datetime(2026, 1, 2, tzinfo=UTC),
        atr=Decimal("3"),
        tick_size=Decimal("0.1"),
    )

    assert basket.entry_fees == Decimal("0.19")


def test_basket_rejects_entries_beyond_configured_maximum() -> None:
    basket = Basket(
        basket_id=basket_id(), policy=policy(4), take_profit_atr_multiplier=Decimal("3")
    )
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
    basket = Basket(
        basket_id=basket_id(), policy=policy(), take_profit_atr_multiplier=Decimal("3")
    )

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
    basket = Basket(
        basket_id=basket_id(), policy=policy(), take_profit_atr_multiplier=Decimal("3")
    )
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
    basket = Basket(
        basket_id=basket_id(), policy=policy(), take_profit_atr_multiplier=Decimal("3")
    )
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


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("price", Decimal("NaN")),
        ("price", Decimal("Infinity")),
        ("quantity", Decimal("NaN")),
        ("quantity", Decimal("Infinity")),
        ("fee", Decimal("NaN")),
        ("fee", Decimal("Infinity")),
        ("atr", Decimal("NaN")),
        ("atr", Decimal("Infinity")),
        ("tick_size", Decimal("NaN")),
        ("tick_size", Decimal("Infinity")),
    ],
)
def test_non_finite_entry_does_not_mutate_basket(field: str, value: Decimal) -> None:
    basket = Basket(
        basket_id=basket_id(), policy=policy(), take_profit_atr_multiplier=Decimal("3")
    )
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
    assert basket.entry_fees == Decimal("0")
    assert basket.take_profit_price is None


def test_closed_basket_cannot_close_or_accept_entries_twice() -> None:
    basket = Basket(
        basket_id=basket_id(), policy=policy(), take_profit_atr_multiplier=Decimal("3")
    )
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
    basket = Basket(
        basket_id=basket_id(), policy=policy(), take_profit_atr_multiplier=Decimal("3")
    )
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


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("exit_price", Decimal("NaN")),
        ("exit_price", Decimal("Infinity")),
        ("exit_fee", Decimal("NaN")),
        ("exit_fee", Decimal("Infinity")),
    ],
)
def test_non_finite_close_does_not_close_basket(field: str, value: Decimal) -> None:
    basket = Basket(
        basket_id=basket_id(), policy=policy(), take_profit_atr_multiplier=Decimal("3")
    )
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
