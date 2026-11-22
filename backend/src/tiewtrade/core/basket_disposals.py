"""Confirmed manual disposal attribution; F-21 NC-F21-08 (FIFO)."""

from dataclasses import dataclass
from uuid import UUID

from tiewtrade.core.money import Quantity


@dataclass(frozen=True, slots=True)
class SelectedEntry:
    order_id: UUID
    entry_number: int
    remaining: Quantity
    selected_remaining: Quantity


def fifo_disposals(
    entries: tuple[SelectedEntry, ...], filled: Quantity
) -> tuple[tuple[UUID, Quantity], ...]:
    """Attribute only confirmed fills, capped by the user's selected quantities."""
    if type(filled) is not Quantity or filled.amount <= 0:
        raise ValueError("positive filled quantity required")
    remaining = filled
    result: list[tuple[UUID, Quantity]] = []
    seen: set[UUID] = set()

    def entry_number(value: SelectedEntry) -> int:
        return value.entry_number

    for entry in sorted(entries, key=entry_number):
        if entry.order_id in seen or type(entry.entry_number) is not int or entry.entry_number < 1:
            raise ValueError("unique positive entry identities required")
        seen.add(entry.order_id)
        if (
            entry.remaining.asset != filled.asset
            or entry.selected_remaining.asset != filled.asset
            or entry.remaining.amount < 0
            or entry.selected_remaining.amount < 0
        ):
            raise ValueError("invalid selected entry quantities")
        quantity = min(remaining, entry.remaining, entry.selected_remaining)
        if quantity.amount > 0:
            result.append((entry.order_id, quantity))
            remaining -= quantity
    return tuple(result)
