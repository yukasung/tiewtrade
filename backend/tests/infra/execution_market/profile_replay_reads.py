"""Task-scoped production evidence-reader timing; no query or financial changes."""

from __future__ import annotations

import asyncio
import json
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from time import monotonic
from types import EllipsisType
from typing import Any
from unittest.mock import patch

from tiewtrade.infra.db.session import UserSession
from tiewtrade.infra.paper_orders import storage

_PAGE: ContextVar[dict[str, Any] | None] = ContextVar("replay_read_page", default=None)


class ReplayReadObserver:
    def __init__(self) -> None:
        self.pages: list[dict[str, Any]] = []

    @contextmanager
    def observe(self) -> Iterator[None]:
        task = asyncio.current_task()
        execute = UserSession.execute
        decode = storage._decode

        def current() -> dict[str, Any] | None:
            return _PAGE.get() if asyncio.current_task() is task else None

        async def traced_execute(session: UserSession, *args: Any, **kwargs: Any) -> Any:
            row = current()
            started = monotonic()
            try:
                return await execute(session, *args, **kwargs)
            finally:
                if row is not None:
                    row["sql_calls"] += 1
                    row["sql_driver_seconds"] += monotonic() - started

        def traced_decode(*args: Any, **kwargs: Any) -> Any:
            row = current()
            started = monotonic()
            try:
                return decode(*args, **kwargs)
            finally:
                if row is not None:
                    row["decode_calls"] += 1
                    row["decode_seconds"] += monotonic() - started

        with (
            patch.object(UserSession, "execute", traced_execute),
            patch.object(storage, "_decode", traced_decode),
        ):
            yield

    async def read_page(self, session: UserSession, **kwargs: Any) -> Any:
        cursor = kwargs.get("after")
        row: dict[str, Any] = {
            "after_input_id": (
                cursor.record.market.input_id
                if cursor is not None
                else kwargs.get("after_input_id", 0)
            ),
            "after_generation": cursor.record.market.generation if cursor is not None else None,
            "after_rebase": (
                getattr(cursor.record.market, "rebase", False) if cursor is not None else None
            ),
            "limit": kwargs["limit"],
            "sql_calls": 0,
            "sql_driver_seconds": 0.0,
            "decode_calls": 0,
            "decode_seconds": 0.0,
        }
        self.pages.append(row)
        token = _PAGE.set(row)
        started = monotonic()
        try:
            batch = await storage.read_execution_inputs(session, **kwargs)
            row.update(outcome="RETURNED", rows=len(batch))
            return batch
        except BaseException as error:
            row["outcome"] = type(error).__name__
            raise
        finally:
            row["seconds"] = monotonic() - started
            _PAGE.reset(token)


def _retain_failure(
    report: dict[str, Any], stage: str, error: BaseException, primary: BaseException | None
) -> BaseException:
    error_type = type(error).__name__
    report["status"] = "INCOMPLETE"
    report.setdefault("evidence_errors", []).append({"stage": stage, "error_type": error_type})
    if primary is None:
        primary = error
    elif error is not primary:
        primary.add_note(f"replay {stage} failed: {error_type}")
    report["error_type"] = type(primary).__name__
    return primary


def save_partial_result(
    path: Path,
    report: dict[str, Any],
    *,
    primary: BaseException | EllipsisType | None = ...,
) -> None:
    """Explicit None means no primary error; omission uses the legacy active-error lookup."""
    if isinstance(primary, EllipsisType):
        primary = sys.exception()
    try:
        path.write_text(json.dumps(report, indent=2, default=str))
    except BaseException as error:
        _retain_failure(report, "partial_result", error, primary)
        if primary is None:
            raise


def finalize_replay_run(
    report: dict[str, Any],
    *,
    source_check: Callable[[], bool],
    cleanup_owned: Callable[[], dict[str, Any] | None],
    save_result: Callable[[], None],
    database: str,
    primary: BaseException | None = None,
) -> None:
    """Attempt every lifecycle stage; never let evidence errors skip owned cleanup."""
    if primary is not None:
        report.update(status="INCOMPLETE", error_type=type(primary).__name__)
    try:
        unchanged = source_check() is True
        report["source_unchanged"] = unchanged
        if not unchanged:
            raise ValueError("replay diagnostic source changed")
    except BaseException as error:
        report["source_unchanged"] = False
        primary = _retain_failure(report, "source_check", error, primary)
    try:
        cleanup_result = cleanup_owned()
        if cleanup_result is not None:
            report["cleanup"] = cleanup_result
    except BaseException as error:
        report["retained_database"] = database
        primary = _retain_failure(report, "cleanup", error, primary)
    try:
        save_result()
    except BaseException as error:
        primary = _retain_failure(report, "final_result", error, primary)
    if primary is not None:
        raise primary
