"""NC20 observes failure arguments without weakening the original readiness guard."""

import asyncio
import io
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from tests.infra.execution_market import profile_workload as f15
from tests.infra.risk_limits import profile_book_clock as observer
from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.order_book import BookLevel, BookState
from tiewtrade.core.orders import SourceUnavailableError


def ready_book(now: datetime) -> BookState:
    return BookState(
        f15.PAIR,
        1,
        1,
        now,
        now,
        (BookLevel(Money.of(99, "USDT"), Quantity.of(1, "BTC")),),
        (BookLevel(Money.of(100, "USDT"), Quantity.of(1, "BTC")),),
        True,
    )


@pytest.mark.parametrize(
    "case,expected",
    [
        ("ready", set()),
        ("received", {"received_in_future"}),
        ("verified", {"verified_in_future"}),
        ("stale", {"verified_stale"}),
        ("not_ready", {"not_ready"}),
        ("source_future", {"source_in_future"}),
        ("source_stale", {"source_stale"}),
    ],
)
def test_original_guard_outcome_and_exact_flags(
    tmp_path: Path,
    case: str,
    expected: set[str],
) -> None:
    now = datetime(2026, 11, 2, tzinfo=UTC)
    book = ready_book(now)
    changes: dict[str, Any] = {
        "received": {"received_at": now + timedelta(microseconds=1)},
        "verified": {"verified_at": now + timedelta(microseconds=1)},
        "stale": {"verified_at": now - timedelta(seconds=31)},
        "not_ready": {"ready": False},
        "source_future": {"source_at": now + timedelta(microseconds=1)},
        "source_stale": {"source_at": now - timedelta(seconds=31)},
    }
    book = replace(book, **changes.get(case, {}))
    path = tmp_path / "clock.jsonl"
    original = BookState.require_ready
    if expected:
        with pytest.raises(SourceUnavailableError):
            original(book, now)
    else:
        original(book, now)
    with observer.observe_book_clock(path):
        if expected:
            with pytest.raises(SourceUnavailableError):
                book.require_ready(now)
        else:
            book.require_ready(now)
    assert BookState.require_ready is original
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert len(rows) == bool(expected)
    if expected:
        row = rows[0]
        assert {key for key, value in row["conditions"].items() if value} == expected
        assert row["caller_db_now"] == now.isoformat()
        assert row["input_id"] == 1 and row["generation"] == 1 and row["pid"] > 0
        assert row["wall_ns"] > 0 and row["monotonic_ns"] > 0
        assert set(row) == {
            "event",
            "pid",
            "input_id",
            "generation",
            "ready",
            "received_at",
            "verified_at",
            "source_at",
            "caller_db_now",
            "observed_at",
            "wall_ns",
            "monotonic_ns",
            "conditions",
        }
    summary = json.loads(path.with_suffix(".summary.json").read_text())
    assert summary["closed"] and summary["complete"] and summary["calls"] == 1
    assert summary["failure_records"] == len(rows) and not summary["acceptance_result"]


def test_original_exception_identity_and_secret_redaction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime(2026, 11, 2, tzinfo=UTC)
    failure = SourceUnavailableError("TEST_ONLY_SECRET")

    def fail(book: BookState, at: datetime) -> None:
        raise failure

    monkeypatch.setattr(BookState, "require_ready", fail)
    path = tmp_path / "clock.jsonl"
    with observer.observe_book_clock(path), pytest.raises(SourceUnavailableError) as caught:
        ready_book(now).require_ready(now)
    assert caught.value is failure and BookState.require_ready is fail
    assert "TEST_ONLY_SECRET" not in path.read_text()


@pytest.mark.parametrize("exit_kind", ["cancel", "cap", "write"])
def test_failure_capture_incomplete_and_patch_restoration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    exit_kind: str,
) -> None:
    now = datetime(2026, 11, 2, tzinfo=UTC)
    book = replace(ready_book(now), ready=False)
    path = tmp_path / "clock.jsonl"
    original = BookState.require_ready
    monkeypatch.setattr(observer, "FAILURE_LIMIT", 1)
    if exit_kind == "write":
        original_open = Path.open

        class FailingStream(io.StringIO):
            def write(self, value: str) -> int:
                raise OSError("TEST_ONLY_SECRET")

        def open_path(self: Path, *args: Any, **kwargs: Any) -> Any:
            return FailingStream() if self == path else original_open(self, *args, **kwargs)

        monkeypatch.setattr(Path, "open", open_path)
    if exit_kind == "cancel":
        with pytest.raises(asyncio.CancelledError), observer.observe_book_clock(path):
            raise asyncio.CancelledError
    elif exit_kind == "cap":
        with pytest.raises(RuntimeError, match="TRUNCATED"), observer.observe_book_clock(path):
            with pytest.raises(SourceUnavailableError):
                book.require_ready(now)
            book.require_ready(now)
    else:
        with pytest.raises(OSError), observer.observe_book_clock(path):
            book.require_ready(now)
    assert BookState.require_ready is original
    summary = json.loads(path.with_suffix(".summary.json").read_text())
    assert summary["closed"] and summary["complete"] == (exit_kind == "cancel")
    assert not summary["acceptance_result"] and "TEST_ONLY_SECRET" not in json.dumps(summary)


@pytest.mark.parametrize("case", ["missing", "incomplete", "unused", "process_error", "complete"])
async def test_child_close_rejects_missing_or_incomplete_observation(
    tmp_path: Path,
    case: str,
) -> None:
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from tests.infra.risk_limits.profile_publisher_process import PublisherLink

    link = PublisherLink(tmp_path, lambda event: None, [])
    link.book_clock = True
    process: Any = SimpleNamespace(
        returncode=1 if case == "process_error" else 0, wait=AsyncMock(return_value=0)
    )
    link.process = process
    if case != "missing":
        (tmp_path / "publisher.book-clock.summary.json").write_text(
            json.dumps(
                {
                    "closed": True,
                    "complete": case != "incomplete",
                    "calls": 0 if case == "unused" else 1,
                }
            )
        )
    if case == "complete":
        await link.close()
    else:
        with pytest.raises(RuntimeError, match="TRACE_INCOMPLETE"):
            await link.close()
