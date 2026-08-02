from decimal import Decimal

import pytest

from tiewtrade.trading.position import PositionSide, unrealized_pnl


@pytest.mark.parametrize(
    ("side", "expected"),
    [
        (PositionSide.LONG, Decimal("6")),
        (PositionSide.SHORT, Decimal("-6")),
    ],
)
def test_unrealized_pnl_is_side_aware(
    side: PositionSide,
    expected: Decimal,
) -> None:
    assert (
        unrealized_pnl(
            side=side,
            average_entry_price=Decimal("100"),
            quantity=Decimal("2"),
            current_price=Decimal("103"),
        )
        == expected
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("average_entry_price", Decimal("0")),
        ("quantity", Decimal("0")),
        ("current_price", Decimal("NaN")),
    ],
)
def test_unrealized_pnl_rejects_invalid_position_facts(
    field: str,
    value: Decimal,
) -> None:
    values = {
        "average_entry_price": Decimal("100"),
        "quantity": Decimal("2"),
        "current_price": Decimal("103"),
    }
    values[field] = value

    with pytest.raises(ValueError, match=field):
        unrealized_pnl(side=PositionSide.LONG, **values)
