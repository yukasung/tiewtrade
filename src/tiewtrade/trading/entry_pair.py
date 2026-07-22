from datetime import datetime, timedelta

from tiewtrade.trading.spot_policy import SpotTradingPolicy


def month_index(at: datetime) -> int:
    if at.tzinfo is None or at.utcoffset() != timedelta(0):
        raise ValueError("timestamp must use UTC")
    return (at.year * 12) + at.month


class EntryPairLifecycle:
    def __init__(self, policy: SpotTradingPolicy) -> None:
        self._policy = policy
        self._entry_count = 0
        self._completed_pair_month: int | None = None

    @property
    def entry_count(self) -> int:
        return self._entry_count

    def can_enter(self, at: datetime) -> bool:
        current_month = month_index(at)
        if self._entry_count >= self._policy.max_entries:
            return False
        if self._entry_count == 0 or self._entry_count % 2 == 1:
            return True

        assert self._completed_pair_month is not None
        return current_month >= self._completed_pair_month + 2

    def record_fill(self, at: datetime) -> None:
        if not self.can_enter(at):
            raise ValueError("entry is blocked by pair lifecycle")

        self._entry_count += 1
        if self._entry_count % 2 == 0:
            self._completed_pair_month = month_index(at)

    def reset(self) -> None:
        self._entry_count = 0
        self._completed_pair_month = None
