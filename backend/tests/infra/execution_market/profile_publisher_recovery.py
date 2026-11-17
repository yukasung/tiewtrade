"""Opt-in fixture control, never trading state, clock repair or order retry."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from time import monotonic
from typing import Any

from tiewtrade.core.order_book import BookState
from tiewtrade.core.orders import SourceUnavailableError
from tiewtrade.infra.market_data.order_book_storage import BookLease

REVISION = "NC_F17_CLOCK_01"
MAX_EVENTS = 1
BUDGET_SECONDS = 1.0


def validate_options(args: argparse.Namespace) -> None:
    enabled = getattr(args, "publisher_clock_recovery", False)
    if enabled is False:
        return
    from tests.infra.execution_market import profile_internal as internal

    if (
        enabled is not True
        or getattr(args, "acceptance_profile", None) != internal.NAME
        or getattr(args, "phase", None) != "W3"
        or any(
            getattr(args, name, False)
            for name in ("worker_only", "diagnostics", "failure_timeline")
        )
    ):
        raise ValueError("publisher clock recovery requires internal20 V1 W3 parent only")


def configuration(args: argparse.Namespace) -> dict[str, Any]:
    validate_options(args)
    if not getattr(args, "publisher_clock_recovery", False):
        return {}
    return {
        "publisher_clock_recovery": {
            "revision": REVISION,
            "max_events": MAX_EVENTS,
            "max_retries": 1,
            "budget_seconds": BUDGET_SECONDS,
            "scope": "measured fixture publication only; original no-retry results unchanged",
            "authorization": "specs/features/2026-11-02-tp-sl/publisher-clock-recovery-plan.md",
        }
    }


@dataclass
class Attempt:
    tick: int | None = None
    started: float = field(default_factory=monotonic)
    task: asyncio.Task[Any] | None = field(default_factory=asyncio.current_task)
    book: BookState | None = None
    lease: BookLease | None = None
    observed_at: datetime | None = None
    guard_now: datetime | None = None
    checked_at: float | None = None
    error: BaseException | None = None
    guard_calls: int = 0
    evidence_ok: bool = False
    rollback_confirmed: bool = False
    committed_at: float | None = None

    def row(self) -> dict[str, Any]:
        book = self.book
        return {
            "tick": self.tick,
            "started": self.started,
            "observed_at": None if self.observed_at is None else self.observed_at.isoformat(),
            "guard_age_microseconds": None
            if book is None or self.guard_now is None
            else (self.guard_now - book.received_at) // timedelta(microseconds=1),
            "guard_checked_at": self.checked_at,
            "pair": None if book is None else [book.pair.base, book.pair.quote],
            "input_id": None if book is None else book.input_id,
            "generation": None if book is None else book.generation,
            "owner": None if self.lease is None else str(self.lease.owner),
            "received_at": None if book is None else book.received_at.isoformat(),
            "verified_at": None if book is None else book.verified_at.isoformat(),
            "guard_now": None if self.guard_now is None else self.guard_now.isoformat(),
            "error_type": None if self.error is None else type(self.error).__name__,
            "rollback_confirmed": self.rollback_confirmed,
            "committed_at": self.committed_at,
        }


_ATTEMPT: ContextVar[Attempt | None] = ContextVar("fixture_publication_attempt", default=None)
_CURRENT: ContextVar[ClockRecovery | None] = ContextVar("fixture_clock_recovery", default=None)


@contextmanager
def capture(
    attempt: Attempt, book: BookState, lease: BookLease, observed_at: datetime
) -> Iterator[None]:
    attempt.book, attempt.lease, attempt.observed_at = book, lease, observed_at
    token = _ATTEMPT.set(attempt)
    try:
        yield
    finally:
        _ATTEMPT.reset(token)


def observe_guard(
    book: BookState,
    now: datetime,
    error: BaseException | None,
    *,
    checked_at: float,
    evidence_ok: bool,
) -> None:
    attempt = _ATTEMPT.get()
    if attempt is None or attempt.task is not asyncio.current_task() or attempt.book is not book:
        return
    attempt.guard_calls += 1
    attempt.guard_now = now if isinstance(now, datetime) else None
    attempt.checked_at = checked_at
    attempt.error = error
    attempt.evidence_ok = evidence_ok


def current() -> ClockRecovery | None:
    return _CURRENT.get()


class ClockRecovery:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.publisher_task: asyncio.Task[Any] | None = None
        self.window_start: float | None = None
        self.window_end: float | None = None
        self.event: dict[str, Any] | None = None
        self.terminal_rejection: dict[str, Any] | None = None
        self.deadline: float | None = None
        self.first: Attempt | None = None
        self.latest: Attempt | None = None

    def new_attempt(self, *, tick: int | None = None) -> Attempt:
        self.latest = Attempt(tick=tick)
        return self.latest

    def eligible(self, attempt: Attempt, error: BaseException) -> bool:
        book, lease, now = attempt.book, attempt.lease, attempt.guard_now
        return (
            self.window_start is not None
            and attempt.started >= self.window_start
            and (self.window_end is None or attempt.started <= self.window_end)
            and attempt.task is asyncio.current_task()
            and self.publisher_task is asyncio.current_task()
            and type(error) is SourceUnavailableError
            and error is attempt.error
            and attempt.guard_calls == 1
            and attempt.checked_at is not None
            and math.isfinite(attempt.checked_at)
            and type(attempt.tick) is int
            and attempt.tick > 0
            and attempt.evidence_ok
            and book is not None
            and lease is not None
            and isinstance(now, datetime)
            and now.tzinfo is not None
            and book.ready
            and not book.rebase
            and book.source_at is None
            and book.received_at == book.verified_at == attempt.observed_at
            and now < book.received_at
            and book.pair == lease.pair
            and book.generation == lease.generation
            and book.input_id == lease.last_input_id + 1
        )

    def claim(self, attempt: Attempt, error: BaseException) -> bool:
        if not self.eligible(attempt, error):
            return False
        if self.event is not None:
            self.terminal_rejection = attempt.row()
            self.persist()
            return False
        assert attempt.checked_at is not None
        self.first = attempt
        self.deadline = attempt.checked_at + BUDGET_SECONDS
        self.event = {"status": "REJECTED", "attempts": [attempt.row()], "retry_count": 0}
        self.persist()
        return True

    def rolled_back(self, attempt: Attempt) -> None:
        assert self.event is not None and attempt is self.first
        attempt.rollback_confirmed = True
        self.event["rollback_confirmed_at"] = monotonic()
        self.event["attempts"][0] = attempt.row()
        self.persist()

    def retry_ready(self, attempt: Attempt, error: BaseException) -> bool:
        return (
            self.event is not None
            and attempt is self.first
            and attempt.rollback_confirmed
            and error is attempt.error
        )

    def retrying(self) -> None:
        assert self.event is not None
        self.event.update(status="RETRYING", retry_count=1, prior_session_exited_at=monotonic())
        self.persist()

    def require_retry_identity(self, lease: BookLease) -> None:
        if self.first is None:
            return
        book, original = self.first.book, self.first.lease
        if (
            book is None
            or original is None
            or lease.pair != book.pair
            or lease.generation != book.generation
            or lease.owner != original.owner
            or lease.last_input_id + 1 != book.input_id
        ):
            raise RuntimeError("clock recovery source identity changed before publication")

    def committed(self, attempt: Attempt) -> None:
        assert self.event is not None and self.deadline is not None
        if attempt.committed_at is None or attempt.committed_at > self.deadline:
            raise TimeoutError("publisher clock recovery budget exceeded")
        first = self.first
        if (
            attempt.guard_calls != 1
            or attempt.error is not None
            or not attempt.evidence_ok
            or attempt.book is None
            or first is None
            or first.book is None
            or attempt.tick != first.tick
            or attempt.book.pair != first.book.pair
            or attempt.book.input_id != first.book.input_id
            or attempt.book.generation != first.book.generation
            or attempt.lease is None
            or first.lease is None
            or attempt.lease.owner != first.lease.owner
        ):
            raise RuntimeError("clock recovery commit evidence is incomplete")
        self.event.update(status="COMMITTED", committed_at=attempt.committed_at)
        self.event["attempts"] = [first.row(), attempt.row()]
        self.persist()

    def abort(self, error: BaseException) -> None:
        if self.event is None or self.event["status"] == "COMMITTED":
            return
        self.event.update(
            status="ABORTED",
            error_type=type(error).__name__,
            cause_type=None if error.__cause__ is None else type(error.__cause__).__name__,
        )
        attempts = [] if self.first is None else [self.first.row()]
        if self.latest is not None and self.latest is not self.first:
            attempts.append(self.latest.row())
        self.event["attempts"] = attempts
        try:
            self.persist()
        except (OSError, ValueError) as evidence_error:
            error.add_note(f"clock recovery evidence failed: {type(evidence_error).__name__}")

    def report(self) -> dict[str, Any]:
        recovered = self.event is not None and self.event["status"] == "COMMITTED"
        return {
            "revision": REVISION,
            "max_events": MAX_EVENTS,
            "max_retries": 1,
            "budget_seconds": BUDGET_SECONDS,
            "window_start": self.window_start,
            "window_end": self.window_end,
            "event": self.event,
            "terminal_rejection": self.terminal_rejection,
            "recovered_count": int(recovered),
            "clock_recovery_warning": recovered,
        }

    def validate_success(self) -> None:
        if (
            self.window_start is None
            or self.window_end is None
            or self.window_end < self.window_start
            or self.terminal_rejection is not None
            or (self.event is not None and self.event["status"] != "COMMITTED")
        ):
            raise RuntimeError("clock recovery evidence is incomplete")
        self.persist()

    def persist(self) -> None:
        from tests.infra.execution_market.profile_workload import save

        report = self.report()
        save(self.path, report)
        if json.loads(self.path.read_text()) != report:
            raise ValueError("clock recovery evidence differs")

    @contextmanager
    def observe(self) -> Iterator[None]:
        if self.publisher_task is None:
            self.publisher_task = asyncio.current_task()
        token = _CURRENT.set(self)
        primary: BaseException | None = None
        try:
            yield
            if self.event is not None and (
                self.event["status"] != "COMMITTED" or self.terminal_rejection is not None
            ):
                raise RuntimeError("clock recovery evidence is incomplete")
        except BaseException as error:
            primary = error
            raise
        finally:
            _CURRENT.reset(token)
            if self.path.parent.is_dir():
                try:
                    self.persist()
                except (OSError, ValueError) as error:
                    if primary is None:
                        raise
                    primary.add_note(
                        f"clock recovery final evidence failed: {type(error).__name__}"
                    )
