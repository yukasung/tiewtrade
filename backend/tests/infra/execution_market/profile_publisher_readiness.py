"""NC12 bounded parent-publisher observations; no altered guard or clock."""

from __future__ import annotations

import asyncio
import json
from collections import deque
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
from functools import wraps
from pathlib import Path
from time import monotonic
from typing import Any
from unittest.mock import patch
from uuid import UUID

from tiewtrade.core.order_book import BookState

WINDOW = 64


@contextmanager
def observe_publisher_readiness(path: Path) -> Iterator[None]:
    # Lazy import avoids the workload/observer import cycle.
    from tests.infra.execution_market import profile_workload as workload

    original_publish, original_guard = workload.publish_market, BookState.require_ready
    publication: ContextVar[tuple[asyncio.Task[Any] | None, dict[str, Any]] | None] = ContextVar(
        "parent_publication", default=None
    )
    recent: deque[dict[str, Any]] = deque(maxlen=WINDOW)
    total = 0
    primary: BaseException | None = None

    def flush(reason: str) -> None:
        path.write_text(
            json.dumps(
                {
                    "scope": "parent publish_market readiness guards only",
                    "window_policy": (
                        "most recent 64 guard checks; not complete publication history"
                    ),
                    "window_limit": WINDOW,
                    "total_checks": total,
                    "discarded_earlier_checks": total - len(recent),
                    "flush_reason": reason,
                    "checks": list(recent),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    @wraps(original_publish)
    async def publish(*args: Any, **kwargs: Any) -> Any:
        lease = args[1] if len(args) > 1 else kwargs.get("book_lease")
        owner = getattr(lease, "owner", None)
        tick = kwargs.get("trade_id")
        identity = {
            "owner": str(owner) if isinstance(owner, UUID) else None,
            "tick": tick if type(tick) is int else None,
        }
        token = publication.set((asyncio.current_task(), identity))
        try:
            return await original_publish(*args, **kwargs)
        finally:
            publication.reset(token)

    @wraps(original_guard)
    def guard(book: BookState, now: datetime) -> None:
        nonlocal total
        scope = publication.get()
        if scope is None or scope[0] is not asyncio.current_task():
            return original_guard(book, now)
        checked_at = monotonic()
        failure: BaseException | None = None
        try:
            return original_guard(book, now)
        except BaseException as error:
            failure = error
            raise
        finally:
            # These immutable arguments are the actual inputs to the unchanged guard.
            row = {
                **scope[1],
                "input_id": book.input_id,
                "generation": book.generation,
                "ready": book.ready,
                "rebase": book.rebase,
                "received_at": book.received_at.isoformat(),
                "verified_at": book.verified_at.isoformat(),
                "source_at": None if book.source_at is None else book.source_at.isoformat(),
                "guard_now": now.isoformat() if isinstance(now, datetime) else None,
                "monotonic": checked_at,
                "outcome": "RETURNED" if failure is None else type(failure).__name__,
            }
            recent.append(row)
            total += 1
            if failure is not None:
                try:
                    flush("guard_failure")
                except OSError as observation_error:
                    failure.add_note(
                        f"readiness evidence write failed: {type(observation_error).__name__}"
                    )

    try:
        with (
            patch.object(workload, "publish_market", publish),
            patch.object(BookState, "require_ready", guard),
        ):
            yield
    except BaseException as error:
        primary = error
        raise
    finally:
        try:
            flush("completed" if primary is None else type(primary).__name__)
        except OSError as observation_error:
            if primary is None:
                raise
            primary.add_note(
                f"readiness evidence finalization failed: {type(observation_error).__name__}"
            )
