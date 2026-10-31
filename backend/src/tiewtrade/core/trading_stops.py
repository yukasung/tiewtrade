"""Pure kill-switch authority and target policy for F-19."""

from dataclasses import dataclass
from enum import Enum
from uuid import UUID

from tiewtrade.core.orders import OrderOrigin, TradingMode


class StopInputError(ValueError):
    code = "TRADING_STOP_INPUT_INVALID"


class StopCause(Enum):
    USER = "USER"
    SYSTEM = "SYSTEM"
    LOSS_LIMIT = "LOSS_LIMIT"
    PLATFORM = "PLATFORM"


class StopActor(Enum):
    USER = "USER"
    SYSTEM = "SYSTEM"
    PLATFORM_ADMIN = "PLATFORM_ADMIN"
    PLATFORM_OWNER = "PLATFORM_OWNER"


class StopAction(Enum):
    STOP = "STOP"
    RESUME = "RESUME"


class StopProgress(Enum):
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    PROBLEMS = "PROBLEMS"


@dataclass(frozen=True, slots=True)
class StopScope:
    mode: TradingMode | None
    owner_id: UUID | None

    def __post_init__(self) -> None:
        if self.mode is None:
            if self.owner_id is not None:
                raise StopInputError("platform scope cannot identify one owner")
        elif type(self.owner_id) is not UUID:
            raise StopInputError("mode stop requires an owner")

    @property
    def platform(self) -> bool:
        return self.mode is None


@dataclass(frozen=True, slots=True)
class StopSnapshot:
    stop_id: UUID
    cause: StopCause
    scope: StopScope
    generation: int
    revision: int

    def __post_init__(self) -> None:
        if type(self.stop_id) is not UUID or not isinstance(self.cause, StopCause):
            raise StopInputError("stop identity and cause required")
        if not isinstance(self.scope, StopScope):
            raise StopInputError("stop scope required")
        if type(self.generation) is not int or self.generation < 1:
            raise StopInputError("positive stop generation required")
        if type(self.revision) is not int or self.revision < 1:
            raise StopInputError("positive stop revision required")
        if self.cause is StopCause.PLATFORM and not self.scope.platform:
            raise StopInputError("platform cause requires platform scope")
        if self.cause is not StopCause.PLATFORM and self.scope.platform:
            raise StopInputError("owner cause requires owner scope")


def opening_blocked(*, cause: StopCause, origin: OrderOrigin) -> bool:
    """Whether an active cause blocks a newly admitted opening intent."""
    if not isinstance(cause, StopCause) or not isinstance(origin, OrderOrigin):
        raise StopInputError("explicit stop cause and order origin required")
    if cause is StopCause.USER:
        return origin is OrderOrigin.BOT
    return True


def active_remainder_cancelable(*, cause: StopCause, origin: OrderOrigin) -> bool:
    """Whether a sent order remainder is a cancellation target for this cause."""
    if not isinstance(cause, StopCause) or not isinstance(origin, OrderOrigin):
        raise StopInputError("explicit stop cause and order origin required")
    if cause is StopCause.PLATFORM:
        return origin is OrderOrigin.BOT
    return True


def progress_for(
    *, target_set_complete: bool, pending_count: int, failed_count: int
) -> StopProgress:
    if type(target_set_complete) is not bool:
        raise StopInputError("explicit target completeness required")
    if any(type(value) is not int or value < 0 for value in (pending_count, failed_count)):
        raise StopInputError("nonnegative stop counts required")
    if failed_count > pending_count:
        raise StopInputError("failed targets cannot exceed pending targets")
    if failed_count:
        return StopProgress.PROBLEMS
    if target_set_complete and pending_count == 0:
        return StopProgress.STOPPED
    return StopProgress.STOPPING
