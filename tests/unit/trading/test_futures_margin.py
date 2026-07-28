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


def test_snapshot_does_not_duplicate_liquidation_verdict() -> None:
    snapshot = model().snapshot(
        **margin_inputs(),  # type: ignore[arg-type]
        current_price=Decimal("90"),
    )

    assert not hasattr(snapshot, "is_liquidated")
    assert not hasattr(snapshot, "maintenance_margin")


@pytest.mark.parametrize(
    ("side", "candle_low", "candle_high"),
    [
        (PositionSide.LONG, Decimal("80"), Decimal("100")),
        (PositionSide.SHORT, Decimal("100"), Decimal("120")),
    ],
)
def test_liquidation_crossing_includes_exact_threshold(
    side: PositionSide,
    candle_low: Decimal,
    candle_high: Decimal,
) -> None:
    assert model().is_liquidation_crossed(
        side=side,
        liquidation_price=Decimal("80")
        if side is PositionSide.LONG
        else Decimal("120"),
        candle_low=candle_low,
        candle_high=candle_high,
    )


@pytest.mark.parametrize(
    ("side", "liquidation_price", "candle_low", "candle_high"),
    [
        (PositionSide.LONG, Decimal("80"), Decimal("80.1"), Decimal("100")),
        (PositionSide.SHORT, Decimal("120"), Decimal("100"), Decimal("119.9")),
    ],
)
def test_liquidation_crossing_rejects_ranges_that_do_not_touch_threshold(
    side: PositionSide,
    liquidation_price: Decimal,
    candle_low: Decimal,
    candle_high: Decimal,
) -> None:
    assert not model().is_liquidation_crossed(
        side=side,
        liquidation_price=liquidation_price,
        candle_low=candle_low,
        candle_high=candle_high,
    )


@pytest.mark.parametrize(
    "liquidation_price",
    [
        Decimal("NaN"),
        Decimal("Infinity"),
        Decimal("0"),
        Decimal("-1"),
    ],
)
def test_liquidation_crossing_rejects_invalid_threshold(
    liquidation_price: Decimal,
) -> None:
    with pytest.raises(ValueError, match="liquidation_price"):
        model().is_liquidation_crossed(
            side=PositionSide.LONG,
            liquidation_price=liquidation_price,
            candle_low=Decimal("80"),
            candle_high=Decimal("100"),
        )


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
    assert isinstance(snapshot.account_equity, Decimal)


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


def test_snapshot_keeps_equity_at_adverse_price() -> None:
    snapshot = model().snapshot(
        side=PositionSide.LONG,
        average_entry_price=Decimal("100"),
        quantity=Decimal("1"),
        available_capital=Decimal("10"),
        accumulated_entry_fees=Decimal("0"),
        current_price=Decimal("90"),
    )

    assert snapshot.account_equity == Decimal("0")


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
