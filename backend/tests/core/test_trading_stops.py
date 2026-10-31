from uuid import uuid4

import pytest

from tiewtrade.core.orders import OrderOrigin, TradingMode
from tiewtrade.core.trading_stops import (
    StopCause,
    StopInputError,
    StopProgress,
    StopScope,
    StopSnapshot,
    active_remainder_cancelable,
    opening_blocked,
    progress_for,
)


@pytest.mark.parametrize(
    ("cause", "origin", "blocked", "cancelable"),
    [
        (StopCause.USER, OrderOrigin.MANUAL, False, True),
        (StopCause.USER, OrderOrigin.BOT, True, True),
        (StopCause.SYSTEM, OrderOrigin.MANUAL, True, True),
        (StopCause.LOSS_LIMIT, OrderOrigin.BOT, True, True),
        (StopCause.PLATFORM, OrderOrigin.MANUAL, True, False),
        (StopCause.PLATFORM, OrderOrigin.BOT, True, True),
    ],
)
def test_stop_policy_separates_admission_from_active_remainder_cancellation(
    cause: StopCause, origin: OrderOrigin, blocked: bool, cancelable: bool
) -> None:
    assert opening_blocked(cause=cause, origin=origin) is blocked
    assert active_remainder_cancelable(cause=cause, origin=origin) is cancelable


def test_scope_requires_platform_and_owner_causes_to_match() -> None:
    owner = uuid4()
    StopSnapshot(uuid4(), StopCause.USER, StopScope(TradingMode.PAPER, owner), 1, 1)
    StopSnapshot(uuid4(), StopCause.PLATFORM, StopScope(None, None), 1, 1)
    with pytest.raises(StopInputError):
        StopSnapshot(uuid4(), StopCause.PLATFORM, StopScope(TradingMode.PAPER, owner), 1, 1)


@pytest.mark.parametrize(
    ("complete", "pending", "failed", "expected"),
    [
        (False, 0, 0, StopProgress.STOPPING),
        (True, 1, 0, StopProgress.STOPPING),
        (True, 0, 0, StopProgress.STOPPED),
        (True, 1, 1, StopProgress.PROBLEMS),
    ],
)
def test_progress_never_reports_success_before_complete(
    complete: bool, pending: int, failed: int, expected: StopProgress
) -> None:
    assert (
        progress_for(target_set_complete=complete, pending_count=pending, failed_count=failed)
        is expected
    )
