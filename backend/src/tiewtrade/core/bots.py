"""Pure lifecycle rules for a single bot run (F-20)."""

from enum import StrEnum


class BotLifecycleError(ValueError):
    """The requested lifecycle edge is unavailable."""


class BotStatus(StrEnum):
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    RECOVERING = "RECOVERING"
    STOPPED = "STOPPED"
    RETIRED = "RETIRED"


class BotTransition(StrEnum):
    READY = "READY"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    RECOVER = "RECOVER"
    STOP = "STOP"
    RESUME = "RESUME"
    REPLACE = "REPLACE"


def transition_bot(
    status: BotStatus,
    event: BotTransition,
    *,
    readiness_proven: bool = False,
    stop_cleared: bool = False,
    flatness_proven: bool = False,
) -> BotStatus:
    """Apply a transition using evidence validated by the financial writer."""
    if not isinstance(status, BotStatus) or not isinstance(event, BotTransition):
        raise BotLifecycleError("typed lifecycle status and event required")
    if status is not BotStatus.RETIRED and event is BotTransition.STOP:
        return BotStatus.STOPPED
    if status is BotStatus.STOPPED:
        if event is BotTransition.RESUME and stop_cleared:
            return BotStatus.RECOVERING
        if event is BotTransition.REPLACE and stop_cleared and flatness_proven:
            return BotStatus.RETIRED
    if status is BotStatus.STARTING and event is BotTransition.SOURCE_UNAVAILABLE:
        return BotStatus.PAUSED
    if status in (BotStatus.RUNNING, BotStatus.PAUSED, BotStatus.RECOVERING):
        if event is BotTransition.RECOVER:
            return BotStatus.RECOVERING
        if event is BotTransition.SOURCE_UNAVAILABLE:
            return BotStatus.PAUSED
    if (
        status in (BotStatus.STARTING, BotStatus.PAUSED, BotStatus.RECOVERING)
        and event is BotTransition.READY
        and readiness_proven
        and stop_cleared
    ):
        return BotStatus.RUNNING
    raise BotLifecycleError("unsupported transition or missing evidence")
