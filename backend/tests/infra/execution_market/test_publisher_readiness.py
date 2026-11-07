"""A parent diagnostic must observe the exact guard without repairing its inputs."""

import asyncio
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest

from tests.infra.execution_market import profile_workload as f15
from tests.infra.execution_market.profile_publisher_readiness import (
    WINDOW,
    observe_publisher_readiness,
)
from tests.infra.execution_market.test_internal_profile import options
from tests.infra.risk_limits.test_book_clock import ready_book
from tiewtrade.core.order_book import BookState
from tiewtrade.core.orders import SourceUnavailableError


@pytest.mark.parametrize(
    "case",
    [
        "ready",
        "received_future",
        "verified_future",
        "stale",
        "not_ready",
        "source_future",
        "source_stale",
    ],
)
async def test_guard_receives_exact_values_once_and_preserves_result_or_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    now = datetime(2026, 11, 7, tzinfo=UTC)
    changes: dict[str, dict[str, Any]] = {
        "received_future": {"received_at": now + timedelta(microseconds=1)},
        "verified_future": {"verified_at": now + timedelta(microseconds=1)},
        "stale": {"verified_at": now - timedelta(seconds=31)},
        "not_ready": {"ready": False},
        "source_future": {"source_at": now + timedelta(microseconds=1)},
        "source_stale": {"source_at": now - timedelta(seconds=31)},
    }
    book = replace(ready_book(now), **changes.get(case, {}))
    unchanged = book
    original = BookState.require_ready
    calls, errors = [], []
    result = object()
    owner = uuid4()

    def counted(value: BookState, at: datetime) -> None:
        calls.append((value, at))
        try:
            return original(value, at)
        except SourceUnavailableError as error:
            errors.append(error)
            raise

    async def publish(*args: Any, **kwargs: Any) -> Any:
        book.require_ready(now)
        return result

    monkeypatch.setattr(BookState, "require_ready", counted)
    monkeypatch.setattr(f15, "publish_market", publish)
    path = tmp_path / "readiness.json"
    with observe_publisher_readiness(path):
        if case == "ready":
            assert (
                await cast(Any, f15.publish_market)(
                    None, SimpleNamespace(owner=owner), None, trade_id=2119
                )
                is result
            )
        else:
            with pytest.raises(SourceUnavailableError) as caught:
                await cast(Any, f15.publish_market)(
                    None, SimpleNamespace(owner=owner), None, trade_id=2119
                )
            assert caught.value is errors[0]
            assert json.loads(path.read_text())["flush_reason"] == "guard_failure"
    assert calls == [(unchanged, now)] and book is unchanged
    assert f15.publish_market is publish and BookState.require_ready is counted
    document = json.loads(path.read_text())
    assert document["total_checks"] == 1 and document["discarded_earlier_checks"] == 0
    row = document["checks"][0]
    assert row["owner"] == str(owner) and row["tick"] == 2119
    assert row["guard_now"] == now.isoformat()
    assert row["received_at"] == book.received_at.isoformat()
    assert row["verified_at"] == book.verified_at.isoformat()
    assert row["source_at"] == (None if book.source_at is None else book.source_at.isoformat())
    assert row["outcome"] == ("RETURNED" if case == "ready" else "SourceUnavailableError")
    assert row["monotonic"] > 0


async def test_recent_window_excludes_unrelated_and_inherited_child_guards(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = datetime(2026, 11, 7, tzinfo=UTC)
    book = ready_book(now)
    owner = uuid4()
    calls = 0
    original = BookState.require_ready

    def counted(value: BookState, at: datetime) -> None:
        nonlocal calls
        calls += 1
        return original(value, at)

    async def publish(*args: Any, **kwargs: Any) -> Any:
        current = replace(book, input_id=kwargs["trade_id"])

        async def child() -> None:
            current.require_ready(now)

        await asyncio.create_task(child())
        current.require_ready(now)
        return current

    monkeypatch.setattr(BookState, "require_ready", counted)
    monkeypatch.setattr(f15, "publish_market", publish)
    path = tmp_path / "recent.json"
    with observe_publisher_readiness(path):
        book.require_ready(now)  # Outside a publisher operation: delegated, not recorded.
        for tick in range(1, WINDOW + 6):
            await cast(Any, f15.publish_market)(
                None,
                SimpleNamespace(owner=owner),
                None,
                trade_id=tick,
                secret="PRIVATE_NOT_RECORDED",
            )
    document = json.loads(path.read_text())
    assert calls == 1 + 2 * (WINDOW + 5)
    assert document["total_checks"] == WINDOW + 5 and document["discarded_earlier_checks"] == 5
    assert len(document["checks"]) == WINDOW
    assert [r["input_id"] for r in document["checks"]] == list(range(6, WINDOW + 6))
    assert "not complete publication history" in document["window_policy"]
    assert "PRIVATE" not in path.read_text()
    assert all(
        set(row)
        == {
            "owner",
            "tick",
            "input_id",
            "generation",
            "ready",
            "rebase",
            "received_at",
            "verified_at",
            "source_at",
            "guard_now",
            "monotonic",
            "outcome",
        }
        for row in document["checks"]
    )


async def test_cancellation_restores_publisher_guard_and_flushes_recent_checks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    started = asyncio.Event()
    now = datetime(2026, 11, 7, tzinfo=UTC)
    original = BookState.require_ready

    async def publish(*args: Any, **kwargs: Any) -> Any:
        ready_book(now).require_ready(now)
        started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(f15, "publish_market", publish)
    path = tmp_path / "cancel.json"

    async def parent() -> None:
        with observe_publisher_readiness(path):
            await cast(Any, f15.publish_market)(
                None, SimpleNamespace(owner=uuid4()), None, trade_id=1
            )

    task = asyncio.create_task(parent())
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert BookState.require_ready is original and f15.publish_market is publish
    document = json.loads(path.read_text())
    assert document["flush_reason"] == "CancelledError" and document["total_checks"] == 1


async def test_evidence_io_failure_cannot_replace_original_guard_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    failure = SourceUnavailableError("PRIVATE_FAILURE")
    calls = 0
    now = datetime(2026, 11, 7, tzinfo=UTC)

    def guard(book: BookState, at: datetime) -> None:
        nonlocal calls
        calls += 1
        raise failure

    async def publish(*args: Any, **kwargs: Any) -> Any:
        ready_book(now).require_ready(now)

    def no_write(*args: Any, **kwargs: Any) -> int:
        raise OSError("PRIVATE_IO")

    monkeypatch.setattr(BookState, "require_ready", guard)
    monkeypatch.setattr(f15, "publish_market", publish)
    monkeypatch.setattr(Path, "write_text", no_write)
    with (
        pytest.raises(SourceUnavailableError) as caught,
        observe_publisher_readiness(tmp_path / "fail.json"),
    ):
        await cast(Any, f15.publish_market)(None, SimpleNamespace(owner=uuid4()), None, trade_id=1)
    assert caught.value is failure and calls == 1
    assert BookState.require_ready is guard and f15.publish_market is publish
    assert all("PRIVATE" not in note for note in failure.__notes__)


@pytest.mark.parametrize("internal", [True, False])
async def test_workload_activation_is_only_for_explicit_internal_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, internal: bool
) -> None:
    args = options()
    args.output = tmp_path
    if not internal:
        args.acceptance_profile, args.parent_poll_limit = None, None
    original = BookState.require_ready

    async def run(unused: object) -> int:
        assert (BookState.require_ready is not original) == internal
        return 7

    monkeypatch.setattr(f15, "_run", run)
    assert await f15.run(args) == 7
    assert BookState.require_ready is original
    assert (tmp_path / "publisher-readiness.json").exists() == internal
