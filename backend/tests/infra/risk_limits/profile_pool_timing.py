"""NC-F19-16 opt-in observations. Never changes pools, SQL or authorization."""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager, suppress
from contextvars import ContextVar
from pathlib import Path
from time import monotonic, time
from typing import Any
from uuid import UUID

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.risk_limits.profile_dispatch_timing import _CURRENT
from tiewtrade.infra.db import session as db

_TRANSACTION: ContextVar[dict[str, Any] | None] = ContextVar("pool_transaction", default=None)


@contextmanager
def operation_scope(**identity: str) -> Iterator[None]:
    token = _CURRENT.set(dict(identity))
    try:
        yield
    finally:
        _CURRENT.reset(token)


class TransactionTrace:
    def __init__(
        self,
        path: Path,
        *,
        buffered: bool = False,
        control: Path | None = None,
        monotonic_fields: bool = False,
        early_phases: frozenset[str] = frozenset(),
    ) -> None:
        self.early_phases = early_phases
        self.monotonic_fields = monotonic_fields or bool(early_phases)
        self.path = path
        self.control = control or path.parent / "dispatch-trace-control.json"
        self.buffered = buffered
        self.pending: list[dict[str, Any]] = []
        self.listeners: list[tuple[Any, str, Any]] = []
        self.engines: set[AsyncEngine] = set()
        self.next_control_check = 0.0
        self.start: float | None = None
        self.seconds = 180
        self.rows = 0
        self.setup = 0
        self.stream: Any = None

    def active(self) -> bool:
        now = monotonic()
        if self.start is None and now >= self.next_control_check:
            self.next_control_check = now + 0.1
            if self.control.exists():
                control = json.loads(self.control.read_text())
                self.start = float(control["started"])
                self.seconds = int(control["seconds"])
        return self.start is not None and 0 <= now - self.start < self.seconds

    def write(self, row: dict[str, Any]) -> None:
        self.pending.append(row)
        if not self.buffered:
            self.flush()

    def flush(self) -> None:
        if not self.pending:
            return
        if self.stream is None:
            self.stream = self.path.open("x")
        self.stream.writelines(json.dumps(row) + "\n" for row in self.pending)
        self.stream.flush()
        self.pending.clear()

    def attach(self, engine: AsyncEngine) -> None:
        if engine in self.engines:
            return
        self.engines.add(engine)

        def checkout(connection: Any, record: Any, proxy: Any) -> None:
            row = _TRANSACTION.get()
            if row is not None:
                row["checkout_at"] = time()
                if self.monotonic_fields:
                    row["checkout_monotonic"] = monotonic()
                row["pool_wait_seconds"] = monotonic() - row.pop("waiting_since")
                row["backend_pid"] = connection.driver_connection.get_server_pid()

        def checkin(connection: Any, record: Any) -> None:
            row = _TRANSACTION.get()
            if row is not None:
                row["checkin_at"] = time()
                if self.monotonic_fields:
                    row["checkin_monotonic"] = monotonic()

        def before(
            connection: Any,
            cursor: Any,
            statement: str,
            parameters: Any,
            context: Any,
            executemany: bool,
        ) -> None:
            row = _TRANSACTION.get()
            if row is None:
                return
            row["query_started"] = monotonic()
            row["query_hash"] = hashlib.sha256(statement.encode()).hexdigest()
            # Read only the UUID owner setting. Never serialize SQL parameters.
            for values in context.compiled_parameters or ():
                if values.get("setting") == db.CURRENT_USER_SETTING:
                    with suppress(ValueError, TypeError, AttributeError):
                        row["owner"] = str(UUID(values["value"]))

        def after(*args: Any) -> None:
            row = _TRANSACTION.get()
            if row is None or "query_started" not in row:
                return
            started = row.pop("query_started")
            duration = monotonic() - started
            fingerprint = row.pop("query_hash")
            if "query_details" in row:
                if len(row["query_details"]) < 64:
                    row["query_details"].append(
                        {"hash": fingerprint, "started_monotonic": started, "seconds": duration}
                    )
                else:
                    row["query_detail_truncated"] = True
            queries = row["queries"]
            if fingerprint not in queries and len(queries) >= 63:
                fingerprint = "OTHER"
            summary = queries.setdefault(fingerprint, {"count": 0, "seconds": 0.0, "max": 0.0})
            summary["count"] += 1
            summary["seconds"] += duration
            summary["max"] = max(summary["max"], duration)

        def failed(context: Any) -> None:
            row = _TRANSACTION.get()
            if row is not None:
                error = context.original_exception
                code = getattr(error, "sqlstate", None) or getattr(
                    getattr(error, "orig", None), "sqlstate", None
                )
                if isinstance(code, str) and len(code) == 5 and code.isalnum():
                    row["sqlstate"] = code
            after()

        for target, name, callback in (
            (engine.pool, "checkout", checkout),
            (engine.pool, "checkin", checkin),
            (engine.sync_engine, "before_cursor_execute", before),
            (engine.sync_engine, "after_cursor_execute", after),
            (engine.sync_engine, "handle_error", failed),
        ):
            event.listen(target, name, callback)
            self.listeners.append((target, name, callback))

    @asynccontextmanager
    async def observe(self) -> AsyncIterator[None]:
        original = db._begin

        @asynccontextmanager
        async def transaction(
            engine: Any,
            *,
            cleanup_seconds: float | None = None,
        ) -> AsyncIterator[Any]:
            self.attach(engine)
            active = self.active()
            detailed = (_CURRENT.get() or {}).get("phase") in self.early_phases
            if not active and not detailed:
                self.setup += 1
                async with original(engine, cleanup_seconds=cleanup_seconds) as connection:
                    yield connection
                return
            started = monotonic()
            row: dict[str, Any] = {
                "started_at": time(),
                "waiting_since": started,
                "queries": {},
                "pool": str(engine.url.username),
                "checked_out": engine.pool.checkedout(),
                "pool_size": engine.pool.size(),
                "max_overflow": engine.pool._max_overflow,
            }
            if detailed:
                row.update(
                    query_details=[],
                    query_detail_truncated=False,
                    measurement_active_at_start=active,
                )
            if self.monotonic_fields or detailed:
                row["started_monotonic"] = started
            token = _TRANSACTION.set(row)
            outcome = "COMMIT"
            failure: BaseException | None = None
            try:
                async with original(engine, cleanup_seconds=cleanup_seconds) as connection:
                    row["transaction_acquired_at"] = time()
                    if detailed:
                        row["transaction_acquired_monotonic"] = monotonic()
                    try:
                        yield connection
                    finally:
                        if detailed:
                            row["body_finished_monotonic"] = monotonic()
            except BaseException as error:
                failure = error
                outcome = type(error).__name__
                raise
            finally:
                row.update(_CURRENT.get() or {})
                row["finished_at"] = time()
                ended = monotonic()
                row["seconds"] = ended - started
                if self.monotonic_fields or detailed:
                    row["finished_monotonic"] = ended
                if detailed and "body_finished_monotonic" in row:
                    row["body_seconds"] = (
                        row["body_finished_monotonic"] - row["transaction_acquired_monotonic"]
                    )
                    # Includes commit/rollback and connection cleanup, not server commit alone.
                    row["finalization_seconds"] = ended - row["body_finished_monotonic"]
                if "checkout_at" in row:
                    row["held_seconds"] = (
                        row.get("checkin_at", row["finished_at"]) - row["checkout_at"]
                    )
                if self.monotonic_fields and "checkout_monotonic" in row:
                    row["held_seconds"] = (
                        row.get("checkin_monotonic", ended) - row["checkout_monotonic"]
                    )
                row["outcome"] = outcome
                if "waiting_since" in row:
                    row["pool_wait_seconds"] = monotonic() - row.pop("waiting_since")
                if "query_started" in row:
                    query_started = row.pop("query_started")
                    row["interrupted_query_seconds"] = monotonic() - query_started
                    if detailed:
                        row["interrupted_query_started_monotonic"] = query_started
                _TRANSACTION.reset(token)
                self.rows += 1
                if self.rows <= 100000:
                    self.write(row)
                else:
                    raise RuntimeError("F19_POOL_TRACE_TRUNCATED")
                if row.get("query_detail_truncated"):
                    if failure is None:
                        raise RuntimeError("PUBLISHER_QUERY_TRACE_TRUNCATED")
                    failure.add_note("publisher query trace truncated")

        db._begin = transaction
        try:
            yield
        finally:
            db._begin = original
            for target, name, callback in reversed(self.listeners):
                event.remove(target, name, callback)
            self.listeners.clear()
            self.write(
                {
                    "event": "CLOSED",
                    "transactions": self.rows,
                    "setup": self.setup,
                    "acceptance_result": False,
                    "truncated": self.rows > 100000,
                }
            )
            self.flush()
            self.stream.close()


async def sample_database(engine: AsyncEngine, path: Path, stop: asyncio.Event) -> None:
    """Reuse migrator pool; absent cross-role metadata explicitly remains unknown."""
    query = text("""SELECT pid,usename,state,xact_start,wait_event_type,wait_event,
      pg_blocking_pids(pid) AS blockers FROM pg_stat_activity
      WHERE datname=current_database() AND pid<>pg_backend_pid() ORDER BY pid""")
    with path.open("x") as stream:
        while not stop.is_set():
            async with engine.connect() as connection:
                rows = (await connection.execute(query)).mappings().all()
            stream.write(
                json.dumps(
                    {
                        "observed_at": time(),
                        "unknown_nulls": True,
                        "connections": [dict(row) for row in rows],
                    },
                    default=str,
                )
                + "\n"
            )
            stream.flush()
            with suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=2)
