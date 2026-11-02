"""NC20 child-only observation of the existing book readiness failure arguments."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic_ns, perf_counter_ns, time_ns
from typing import Any
from unittest.mock import patch

from tiewtrade.core.order_book import MAX_BOOK_AGE, BookState
from tiewtrade.core.orders import SourceUnavailableError

FAILURE_LIMIT = 32


@contextmanager
def observe_book_clock(path: Path) -> Iterator[None]:
    """Preserve the original return/exception; fail the diagnostic if evidence is lost."""
    original = BookState.require_ready
    calls = records = record_ns = 0
    complete = True
    stream = path.open("x")

    def observed(book: BookState, now: datetime) -> None:
        nonlocal calls, records, record_ns, complete
        calls += 1
        try:
            original(book, now)
        except SourceUnavailableError:
            started = perf_counter_ns()
            try:
                if records >= FAILURE_LIMIT:
                    complete = False
                    raise RuntimeError("F19_BOOK_CLOCK_TRACE_TRUNCATED") from None
                row: dict[str, Any] = {
                    "event": "BOOK_READINESS_FAILURE",
                    "pid": os.getpid(),
                    "input_id": book.input_id,
                    "generation": book.generation,
                    "ready": book.ready,
                    "received_at": book.received_at.isoformat(),
                    "verified_at": book.verified_at.isoformat(),
                    "source_at": None if book.source_at is None else book.source_at.isoformat(),
                    "caller_db_now": now.isoformat(),
                    "observed_at": datetime.now(UTC).isoformat(),
                    "wall_ns": time_ns(),
                    "monotonic_ns": monotonic_ns(),
                    "conditions": {
                        "not_ready": not book.ready,
                        "received_in_future": now < book.received_at,
                        "verified_in_future": now < book.verified_at,
                        "verified_stale": now - book.verified_at > MAX_BOOK_AGE,
                        "source_in_future": book.source_at is not None and book.source_at > now,
                        "source_stale": book.source_at is not None
                        and now - book.source_at > MAX_BOOK_AGE,
                    },
                }
                stream.write(json.dumps(row) + "\n")
                stream.flush()
                records += 1
            except BaseException:
                complete = False
                raise
            finally:
                record_ns += perf_counter_ns() - started
            raise

    try:
        with patch.object(BookState, "require_ready", observed):
            yield
    finally:
        try:
            stream.close()
        except BaseException:
            complete = False
            raise
        finally:
            path.with_suffix(".summary.json").write_text(
                json.dumps(
                    {
                        "closed": True,
                        "complete": complete,
                        "calls": calls,
                        "failure_records": records,
                        "failure_limit": FAILURE_LIMIT,
                        "failure_record_ns": record_ns,
                        "timing_scope": (
                            "failure recording only; wrapper dispatch/counter overhead unmeasured"
                        ),
                        "acceptance_result": False,
                    },
                    indent=2,
                )
                + "\n"
            )
