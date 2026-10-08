"""Nonwaiting reservations; accepted sockets still consume physical capacity."""

from __future__ import annotations

from dataclasses import dataclass

from tiewtrade.services.api.settings import PRICE_SETTINGS


@dataclass(slots=True)
class ProcessBudget:
    physical_limit: int = PRICE_SETTINGS.physical_limit
    pending_limit: int = PRICE_SETTINGS.pending_limit
    physical: int = 0
    pending: int = 0

    def reserve(self) -> Reservation | None:
        if self.physical >= self.physical_limit or self.pending >= self.pending_limit:
            return None
        self.physical += 1
        self.pending += 1
        return Reservation(self)


@dataclass(slots=True)
class Reservation:
    budget: ProcessBudget
    is_pending: bool = True
    closed: bool = False

    def accepted(self) -> None:
        if self.is_pending and not self.closed:
            self.budget.pending -= 1
            self.is_pending = False

    def close(self) -> None:
        if self.closed:
            return
        self.accepted()
        self.budget.physical -= 1
        self.closed = True
