"""Deterministic F-19 schedule and immutable workload conservation oracles."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class StopScheduleEvent:
    offset_seconds: int
    action: str
    owner_slots: tuple[int, ...]
    expected: str
    overlap: str | None = None


@dataclass(frozen=True, slots=True)
class StopSchedule:
    phase: str
    owners: tuple[UUID, ...]
    events: tuple[StopScheduleEvent, ...]

    def document(self) -> dict[str, object]:
        return {
            "profile": "F19_SET5_STOP_SCHEDULE_V1",
            "phase": self.phase,
            "owners": [str(owner) for owner in self.owners],
            "events": [asdict(event) for event in self.events],
        }

    def digest(self) -> str:
        encoded = json.dumps(self.document(), sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()


_EVENTS = {
    "W1": (
        StopScheduleEvent(50, "PREPARE_QUEUED_MANUAL", (0,), "PENDING"),
        StopScheduleEvent(60, "USER_STOP", (0,), "APPLIED"),
        StopScheduleEvent(90, "POST_CUTOFF_MANUAL", (0,), "SUCCEEDED"),
        StopScheduleEvent(110, "PREPARE_PARTIAL_BOT", (1,), "PARTIALLY_FILLED"),
        StopScheduleEvent(120, "REPEATED_USER_STOP", (0,), "NEW_GENERATION"),
        StopScheduleEvent(120, "USER_STOP_DURING_PARTIAL", (1,), "APPLIED"),
        StopScheduleEvent(150, "USER_RESUME_WHEN_READY", (1,), "APPLIED_OR_DEFERRED"),
    ),
    "W2": (
        StopScheduleEvent(30, "CONCURRENT_USER_STOP", tuple(range(10)), "APPLIED"),
        StopScheduleEvent(30, "EXACT_DUPLICATE", (0, 1, 2), "SAME_REQUEST"),
        StopScheduleEvent(30, "LOST_ACK_LOOKUP", (3, 4, 5), "SAME_REQUEST"),
        StopScheduleEvent(60, "STALE_RESUME", (6, 7), "REJECTED_STALE"),
        StopScheduleEvent(90, "USER_RESUME_WHEN_READY", tuple(range(10)), "APPLIED_OR_DEFERRED"),
    ),
    "W3": (
        StopScheduleEvent(
            210,
            "PLATFORM_STOP",
            (0,),
            "APPLIED",
            overlap="WORKER_RESTART@225",
        ),
        StopScheduleEvent(285, "PLATFORM_RESUME_WHEN_READY", (0,), "APPLIED_OR_DEFERRED"),
        StopScheduleEvent(600, "REARM_BOT_ORDER", (1,), "ACCEPTED"),
        StopScheduleEvent(
            660,
            "PLATFORM_STOP",
            (0,),
            "APPLIED",
            overlap="REDIS_OUTAGE@675",
        ),
        StopScheduleEvent(660, "HOLD_ONE_TARGET_FAILED", (1,), "ALERT_AFTER_60_SECONDS"),
        StopScheduleEvent(750, "PLATFORM_RESUME_WHEN_READY", (0,), "APPLIED_OR_DEFERRED"),
    ),
}


def build_stop_schedule(phase: str, owners: list[UUID]) -> StopSchedule:
    if phase not in _EVENTS:
        raise ValueError("stop schedule is required only for W1-W3")
    required = max(slot for event in _EVENTS[phase] for slot in event.owner_slots) + 1
    if len(owners) < required:
        raise ValueError(f"{phase} stop schedule requires {required} dedicated owners")
    return StopSchedule(phase, tuple(owners), _EVENTS[phase])


def conservation_summary(
    *,
    expected: int,
    offered: int,
    admitted: int,
    completed: int,
    blocked_by_scheduled_platform_stop: int,
    other_rejected: int,
    blocked_outside_schedule: int,
) -> dict[str, int | bool]:
    passed = (
        expected >= 0
        and offered == expected
        and completed + blocked_by_scheduled_platform_stop == offered
        and admitted == completed
        and other_rejected == 0
        and blocked_outside_schedule == 0
    )
    return {
        "expected": expected,
        "offered": offered,
        "admitted": admitted,
        "completed": completed,
        "blocked_by_scheduled_platform_stop": blocked_by_scheduled_platform_stop,
        "other_rejected": other_rejected,
        "blocked_outside_schedule": blocked_outside_schedule,
        "passed": passed,
    }
