from decimal import Decimal

import pytest

from tiewtrade.trading.futures_margin import FuturesMarginModel
from tiewtrade.trading.futures_policy import FuturesTradingPolicy
from tiewtrade.trading.position import PositionSide


def model() -> FuturesMarginModel:
    return FuturesMarginModel(FuturesTradingPolicy.v1(leverage=3))


def margin_inputs() -> dict[str, Decimal | PositionSide]:
    return {
        "side": PositionSide.LONG,
        "average_entry_price": Decimal("100"),
        "quantity": Decimal("3000"),
        "available_capital": Decimal("200000"),
        "accumulated_entry_fees": Decimal("30"),
    }


def test_long_liquidation_threshold_uses_cross_account_equity() -> None:
    price = model().liquidation_price(**margin_inputs())  # type: ignore[arg-type]
    expected = (Decimal("100") * Decimal("3000") - Decimal("199970")) / (
        Decimal("3000") * Decimal("0.995")
    )

    assert price == expected


def test_short_liquidation_threshold_is_above_entry() -> None:
    inputs = margin_inputs()
    inputs["side"] = PositionSide.SHORT

    price = model().liquidation_price(**inputs)  # type: ignore[arg-type]
    expected = (Decimal("199970") + Decimal("100") * Decimal("3000")) / (
        Decimal("3000") * Decimal("1.005")
    )

    assert price == expected
    assert price is not None
    assert price > Decimal("100")


def test_long_threshold_returns_none_when_equity_covers_all_positive_prices() -> None:
    assert (
        model().liquidation_price(
            side=PositionSide.LONG,
            average_entry_price=Decimal("100"),
            quantity=Decimal("1"),
            available_capital=Decimal("200000"),
            accumulated_entry_fees=Decimal("0"),
        )
        is None
    )


def test_entry_fees_reduce_account_equity() -> None:
    snapshot = model().snapshot(
        side=PositionSide.LONG,
        average_entry_price=Decimal("100"),
        quantity=Decimal("3000"),
        available_capital=Decimal("200000"),
        accumulated_entry_fees=Decimal("30"),
        current_price=Decimal("90"),
    )

    assert snapshot.account_equity == Decimal("169970")
    assert snapshot.maintenance_margin == Decimal("1350.000")
    assert isinstance(snapshot.account_equity, Decimal)
    assert isinstance(snapshot.maintenance_margin, Decimal)
    assert not snapshot.is_liquidated


def test_short_snapshot_uses_directional_unrealized_pnl() -> None:
    snapshot = model().snapshot(
        side=PositionSide.SHORT,
        average_entry_price=Decimal("100"),
        quantity=Decimal("2"),
        available_capital=Decimal("1000"),
        accumulated_entry_fees=Decimal("1"),
        current_price=Decimal("110"),
    )

    assert snapshot.account_equity == Decimal("979")
    assert snapshot.maintenance_margin == Decimal("1.100")
    assert not snapshot.is_liquidated


def test_snapshot_marks_position_liquidated_when_equity_reaches_maintenance() -> None:
    snapshot = model().snapshot(
        side=PositionSide.LONG,
        average_entry_price=Decimal("100"),
        quantity=Decimal("1"),
        available_capital=Decimal("10"),
        accumulated_entry_fees=Decimal("0"),
        current_price=Decimal("90"),
    )

    assert snapshot.account_equity == Decimal("0")
    assert snapshot.maintenance_margin == Decimal("0.450")
    assert snapshot.is_liquidated


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("average_entry_price", Decimal("0")),
        ("average_entry_price", Decimal("NaN")),
        ("average_entry_price", Decimal("Infinity")),
        ("quantity", Decimal("0")),
        ("quantity", Decimal("NaN")),
        ("quantity", Decimal("Infinity")),
        ("available_capital", Decimal("0")),
        ("available_capital", Decimal("NaN")),
        ("available_capital", Decimal("Infinity")),
        ("accumulated_entry_fees", Decimal("-1")),
        ("accumulated_entry_fees", Decimal("NaN")),
        ("accumulated_entry_fees", Decimal("Infinity")),
        ("accumulated_entry_fees", Decimal("200000")),
    ],
)
def test_liquidation_price_rejects_invalid_inputs(field: str, value: Decimal) -> None:
    inputs = margin_inputs()
    inputs[field] = value

    with pytest.raises(ValueError, match=field):
        model().liquidation_price(**inputs)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "current_price",
    [
        Decimal("0"),
        Decimal("-1"),
        Decimal("NaN"),
        Decimal("Infinity"),
        Decimal("-Infinity"),
    ],
)
def test_snapshot_rejects_invalid_current_price(current_price: Decimal) -> None:
    with pytest.raises(ValueError, match="current_price"):
        model().snapshot(
            side=PositionSide.LONG,
            average_entry_price=Decimal("100"),
            quantity=Decimal("1"),
            available_capital=Decimal("1000"),
            accumulated_entry_fees=Decimal("0"),
            current_price=current_price,
        )


def test_margin_model_rejects_unknown_position_side() -> None:
    inputs = margin_inputs()
    inputs["side"] = "hedge"  # type: ignore[assignment]

    with pytest.raises(ValueError, match="side"):
        model().liquidation_price(**inputs)  # type: ignore[arg-type]
