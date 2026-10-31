"""Opt-in bounded source-cycle timeline. No SQL or financial instrumentation."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from contextvars import ContextVar
from pathlib import Path
from time import monotonic, time
from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from tiewtrade.infra.db import session as db

_CYCLE: ContextVar[dict[str, Any] | None] = ContextVar("source_cycle", default=None)
_TX: ContextVar[dict[str, Any] | None] = ContextVar("source_transaction", default=None)


def statement_label(statement: str) -> str:
    """Return only fixed labels; never persist SQL text, literals or parameters."""
    sql = " ".join(statement.casefold().split())
    if "pg_roles" in sql:
        return "ROLE_CHECK"
    if "risk_publication_fence()" in sql:
        return "PUBLICATION_FENCE"
    if sql == "select clock_timestamp()":
        return "DB_CLOCK"
    if "market_risk_price_frames" in sql:
        return "PRICE_RECEIPTS"
    if "active_supported_symbols" in sql or "supported_symbol" in sql:
        return "CATALOG_READ"
    if "market_latest_prices" in sql:
        return "PRICE_WRITE" if sql.startswith("update") else "PRICE_SNAPSHOT"
    if "market_price_feed" in sql:
        if "for update" in sql:
            return "FEED_LOCK_AND_CLOCK"
        return "FEED_RENEW" if sql.startswith("update") else "FEED_ACQUIRE"
    if "market_execution_buffer" in sql:
        return "BOOK_BUFFER_WRITE" if sql.startswith("insert") else "BOOK_RECEIPT"
    if "market_execution_state" in sql:
        if "for update" in sql:
            return "BOOK_LOCK_AND_CLOCK"
        return "BOOK_LEASE_RENEW" if "set lease_until" in sql else "BOOK_STATE_WRITE"
    return "OTHER"


class SourceTimeline:
    def __init__(self, output: Path, engine: AsyncEngine, *, observe_backend: bool = False) -> None:
        self.output = output
        self.observe_backend = observe_backend
        self.observer: subprocess.Popen[bytes] | None = None
        self.heartbeat: asyncio.TimerHandle | None = None
        self.heartbeats: list[dict[str, float]] = []
        self.stream = (output / "source-timeline.jsonl").open("x")
        self.engine = engine
        self.started: float | None = None
        self.duration = 60
        self.details = 0
        self.sequence = 0
        self.last_finished: dict[str, float] = {}
        self.recording_seconds = 0.0
        self.limit = 2400
        self.buckets: dict[tuple[str, int, str], dict[str, Any]] = {}
        self.original_begin = db._begin
        self.listeners: list[tuple[Any, str, Any]] = []
        self.closed = False
        self.setup_start = monotonic()
        self.write({"event": "CLOCK", "monotonic": self.setup_start, "wall": time()})

        @asynccontextmanager
        async def observed_begin(
            engine: AsyncEngine,
            *,
            cleanup_seconds: float | None = None,
        ) -> AsyncIterator[AsyncConnection]:
            cycle = _CYCLE.get()
            if cycle is None or engine is not self.engine:
                async with self.original_begin(
                    engine, cleanup_seconds=cleanup_seconds
                ) as connection:
                    yield connection
                return
            if len(cycle["transactions"]) >= 8:
                self.write({"event": "INCOMPLETE", "reason": "TRANSACTION_LIMIT"})
                raise RuntimeError("F18_SOURCE_TRANSACTION_LIMIT")
            tx: dict[str, Any] = {
                "requested": monotonic(),
                "sql_seconds": 0.0,
                "sql_count": 0,
                "queries": [],
            }
            cycle["transactions"].append(tx)
            token = _TX.set(tx)
            try:
                async with self.original_begin(
                    engine, cleanup_seconds=cleanup_seconds
                ) as connection:
                    tx["entered"] = monotonic()
                    yield connection
                    tx["body_finished"] = monotonic()
                tx["committed_ack"] = monotonic()
                tx["outcome"] = "COMMIT"
            except BaseException as error:
                tx["outcome"] = type(error).__name__
                raise
            finally:
                tx["finished"] = monotonic()
                if tx["queries"] and tx["queries"][-1]["outcome"] == "STARTED":
                    tx["queries"][-1].update(abort_observed=monotonic(), outcome=tx["outcome"])
                _TX.reset(token)

        def checkout(connection: Any, *_: Any) -> None:
            if (tx := _TX.get()) is not None:
                tx["checkout"] = monotonic()
                tx["backend_pid"] = connection.driver_connection.get_server_pid()

        def before_cursor(
            _connection: Any,
            _cursor: Any,
            statement: str,
            _parameters: Any,
            _context: Any,
            _many: bool,
        ) -> None:
            if (tx := _TX.get()) is not None:
                if len(tx["queries"]) >= 64:
                    self.write({"event": "INCOMPLETE", "reason": "SQL_LIMIT"})
                    raise RuntimeError("F18_SOURCE_SQL_LIMIT")
                started = monotonic()
                tx["sql_started"] = started
                tx["queries"].append(
                    {
                        "index": len(tx["queries"]),
                        "label": statement_label(statement),
                        "started": started,
                        "outcome": "STARTED",
                    }
                )

        def after_cursor(*_: Any) -> None:
            if (tx := _TX.get()) is not None:
                finished = monotonic()
                tx["sql_seconds"] += finished - tx.pop("sql_started")
                tx["sql_count"] += 1
                tx["queries"][-1].update(finished=finished, outcome="RETURNED")

        def commit(*_: Any) -> None:
            if (tx := _TX.get()) is not None:
                tx["commit_sent"] = monotonic()

        for target, name, callback in (
            (engine.sync_engine.pool, "checkout", checkout),
            (engine.sync_engine, "before_cursor_execute", before_cursor),
            (engine.sync_engine, "after_cursor_execute", after_cursor),
            (engine.sync_engine, "commit", commit),
        ):
            event.listen(target, name, callback)
            self.listeners.append((target, name, callback))
        self.observed_begin = observed_begin
        db._begin = observed_begin

    def write(self, row: dict[str, Any]) -> None:
        self.stream.write(json.dumps(row) + "\n")
        self.stream.flush()

    def activate(self, started: float) -> None:
        self.started = started
        loop = asyncio.get_running_loop()

        def beat(due: float) -> None:
            now = monotonic()
            self.heartbeats.append({"due": due, "resumed": now})
            if not self.closed and now < started + self.duration and len(self.heartbeats) < 6000:
                self.heartbeat = loop.call_later(0.01, beat, now + 0.01)

        self.heartbeat = loop.call_later(0.01, beat, monotonic() + 0.01)
        if self.observe_backend:
            environment = os.environ.copy()
            environment["F18_SOURCE_OBSERVER_DSN"] = self.engine.url.set(
                drivername="postgresql"
            ).render_as_string(hide_password=False)
            self.observer = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "tests.infra.risk_limits.profile_source_waits",
                    str(self.output / "source-waits.json"),
                    str(started + self.duration),
                ],
                env=environment,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        self.write(
            {
                "event": "MEASURED_WINDOW",
                "started": started,
                "seconds": self.duration,
                "wall": time(),
                "monotonic": monotonic(),
                "detail_limit": self.limit,
            }
        )

    def record(self, row: dict[str, Any]) -> None:
        ended = monotonic()
        row["finished"] = ended
        row["previous_finished"] = self.last_finished.get(row["source"])
        measured = (
            self.started is not None
            and self.started <= row["resumed"] < self.started + self.duration
        )
        phase = (
            "load"
            if measured
            else "setup"
            if self.started is None or row["resumed"] < self.started
            else "tail"
        )
        anchor = self.setup_start if phase == "setup" else self.started
        assert anchor is not None
        key = (phase, int(max(0, row["resumed"] - anchor)), row["source"])
        bucket = self.buckets.setdefault(
            key,
            {
                "event": "SECOND",
                "phase": phase,
                "second": key[1],
                "source": row["source"],
                "count": 0,
                "stages": {},
            },
        )
        stages = {
            "due_lag": row["resumed"] - row["due"],
            "scheduler_delay": max(
                0.0, row["resumed"] - max(row["due"], row["previous_finished"] or row["due"])
            ),
            "cycle": ended - row["resumed"],
            "acquire": 0.0,
            "sql_round_trip": 0.0,
            "body": 0.0,
            "commit_ack": 0.0,
        }
        for tx in row["transactions"]:
            if tx.get("outcome") == "COMMIT":
                if not all(
                    name in tx
                    for name in (
                        "checkout",
                        "entered",
                        "body_finished",
                        "commit_sent",
                        "committed_ack",
                    )
                ):
                    raise RuntimeError("F18_SOURCE_TIMELINE_INCOMPLETE")
                if len(tx["queries"]) != tx["sql_count"] or any(
                    "finished" not in query for query in tx["queries"]
                ):
                    raise RuntimeError("F18_SOURCE_SQL_TIMESTAMPS_INCOMPLETE")
                stages["acquire"] += tx["entered"] - tx["requested"]
                stages["sql_round_trip"] += tx["sql_seconds"]
                stages["body"] += tx["body_finished"] - tx["entered"]
                stages["commit_ack"] += tx["committed_ack"] - tx["body_finished"]
        for tx in row["transactions"]:
            for query in tx["queries"]:
                if query["outcome"] == "RETURNED":
                    group = bucket.setdefault("queries", {}).setdefault(
                        query["label"], {"count": 0, "seconds": 0.0, "max_seconds": 0.0}
                    )
                    seconds = query["finished"] - query["started"]
                    group["count"] += 1
                    group["seconds"] += seconds
                    group["max_seconds"] = max(group["max_seconds"], seconds)
        bucket["count"] += 1
        for name, value in stages.items():
            item = bucket["stages"].setdefault(name, {"sum": 0.0, "max": 0.0})
            item["sum"] += value
            item["max"] = max(item["max"], value)
        if measured:
            if self.details >= self.limit:
                self.write({"event": "INCOMPLETE", "reason": "DETAIL_LIMIT", "limit": self.limit})
                raise RuntimeError("F18_SOURCE_TIMELINE_LIMIT")
            self.details += 1
            self.write({"event": "CYCLE", "phase": phase, **row, "stages": stages})
        for previous in list(self.buckets):
            if previous[:2] != key[:2]:
                self.write(self.buckets.pop(previous))
        self.last_finished[row["source"]] = monotonic()
        self.recording_seconds += self.last_finished[row["source"]] - ended

    def receipt(self, kind: str, pair: str, identity: str, committed_at: str) -> None:
        if (row := _CYCLE.get()) is not None:
            row["receipts"].append(
                {
                    "kind": kind,
                    "pair": pair,
                    "identity": identity,
                    "committed_at": committed_at,
                    "recorded": monotonic(),
                }
            )

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        if self.heartbeat is not None:
            self.heartbeat.cancel()
        self.write({"event": "HEARTBEATS", "samples": self.heartbeats})
        if self.observer is not None:
            try:
                self.observer.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.observer.terminate()
                self.observer.wait(timeout=2)
                self.write({"event": "INCOMPLETE", "reason": "OBSERVER_TIMEOUT"})
            if self.observer.returncode != 0:
                self.write({"event": "INCOMPLETE", "reason": "OBSERVER_EXIT"})
        db._begin = self.original_begin
        for target, name, callback in self.listeners:
            event.remove(target, name, callback)
        for row in self.buckets.values():
            self.write(row)
        self.buckets.clear()
        self.write(
            {
                "event": "CLOSED",
                "details": self.details,
                "recording_seconds": self.recording_seconds,
                "monotonic": monotonic(),
                "wall": time(),
            }
        )
        self.stream.close()


@asynccontextmanager
async def source_cycle(
    trace: SourceTimeline | None, source: str, due: float
) -> AsyncIterator[None]:
    if trace is None:
        yield
        return
    trace.sequence += 1
    row: dict[str, Any] = {
        "source": source,
        "sequence": trace.sequence,
        "due": due,
        "resumed": monotonic(),
        "wall": time(),
        "transactions": [],
        "receipts": [],
    }
    token = _CYCLE.set(row)
    try:
        yield
        row["outcome"] = "RETURNED"
    except BaseException as error:
        row["outcome"] = type(error).__name__
        raise
    finally:
        _CYCLE.reset(token)
        trace.record(row)
