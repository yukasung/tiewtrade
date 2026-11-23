from uuid import UUID

import pytest

from tiewtrade.core.basket_disposals import SelectedEntry, fifo_disposals
from tiewtrade.core.money import Quantity


def q(value: str) -> Quantity:
    return Quantity.of(value, "BTC")


def test_fifo_selected_caps_across_partial_fills_and_unselected_inventory() -> None:
    old, new = UUID(int=1), UUID(int=2)
    selected = (SelectedEntry(new, 2, q("2"), q("1.5")), SelectedEntry(old, 1, q("3"), q("0.5")))
    assert fifo_disposals(selected, q("0.25")) == ((old, q("0.25")),)
    assert fifo_disposals(
        (SelectedEntry(new, 2, q("2"), q("1.5")), SelectedEntry(old, 1, q("2.75"), q("0.25"))),
        q("1"),
    ) == ((old, q("0.25")), (new, q("0.75")))
    assert fifo_disposals(selected, q("9")) == ((old, q("0.5")), (new, q("1.5")))


@pytest.mark.parametrize(
    "selected",
    [
        (SelectedEntry(UUID(int=1), 1, q("1"), q("1")),) * 2,
        (SelectedEntry(UUID(int=1), 0, q("1"), q("1")),),
        (SelectedEntry(UUID(int=1), 1, q("1"), Quantity.of("1", "ETH")),),
    ],
)
def test_invalid_fifo_selection_fails_closed(selected: tuple[SelectedEntry, ...]) -> None:
    with pytest.raises(ValueError):
        fifo_disposals(selected, q("1"))
