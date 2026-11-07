"""NC12 pool ownership evidence; observations are never trading/session state."""

from __future__ import annotations

import asyncio
import json
import os
from collections import Counter
from collections.abc import AsyncIterator
from contextlib import ExitStack, asynccontextmanager, contextmanager, suppress
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic
from typing import Any, cast
from unittest.mock import patch
from weakref import ref

from sqlalchemy import event
from sqlalchemy.engine import make_url
from sqlalchemy.exc import TimeoutError as PoolTimeoutError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine
from sqlalchemy.pool import QueuePool

from tests.infra.risk_limits.profile_resources import PoolEvidence
from tiewtrade.infra.db import DatabaseRole

WORKER_CONFIGURATION = [("ENGINE", 5, 10), ("ENGINE_SCAN", 5, 10)]
PARENT_CONFIGURATION = sorted(
    WORKER_CONFIGURATION
    + [("API", 5, 10)] * 2
    + [("API", 1, 0)] * 3
    + [("API", 3, 0)]
    + [("AUTH", 5, 10)] * 2
    + [("MARKET_DATA", 5, 10), ("MIGRATOR", 5, 10), ("ADMIN_OBSERVER", 5, 10)]
)
CURRENT: ContextVar[OwnedPools | None] = ContextVar("nc12_owned_pools", default=None)


def task_provenance() -> dict[str, Any]:
    """Code locations only: task names, frame locals and exception text are untrusted."""
    try:
        task = asyncio.current_task()
    except RuntimeError:
        task = None
    if task is None:
        return {"task_id": None, "cancellation_requests": None, "await_chain": []}
    backend = Path(__file__).resolve().parents[3]
    locations: list[dict[str, Any]] = []
    current: Any = task.get_coro()
    for _ in range(48):
        code = getattr(current, "cr_code", None) or getattr(current, "gi_code", None)
        if code is not None:
            source = Path(code.co_filename).resolve()
            if source.is_relative_to(backend) and len(locations) < 8:
                locations.append(
                    {
                        "file": str(source.relative_to(backend)),
                        "function": code.co_name,
                        "line": code.co_firstlineno,
                    }
                )
        current = getattr(current, "cr_await", None) or getattr(current, "gi_yieldfrom", None)
        if current is None:
            break
    return {
        "task_id": id(task),
        "cancellation_requests": task.cancelling(),
        "await_chain": locations,
    }


class OwnedPools(PoolEvidence):
    def __init__(self, path: Path, expected: list[tuple[str, int, int]]) -> None:
        super().__init__(path)
        self.expected = sorted(expected)
        self.engines: dict[int, AsyncEngine] = {}
        self.bindings: list[tuple[AsyncEngine, Any, dict[str, Any]]] = []
        self.errors: Counter[str] = Counter()
        self.disposal_kind = "final"
        self.next_sample = 0.0
        self.outcome = "RUNNING"
        self.quiescing = False
        self.shutdown_cancellations = 0
        self.resource_errors: list[dict[str, Any]] = []
        self.stream: Any = None
        self.sample_count = 0
        self.stack = ExitStack()

    def save(self, *, finalized: bool) -> None:
        configuration = sorted(
            (row["role"], row["pool_size"], row["max_overflow"])
            for _, _, row in self.bindings
            if row["generation"] == 0
        )
        passed = (
            finalized
            and self.outcome == "RETURNED"
            and configuration == self.expected
            and not self.errors
            and all(
                row["checked_out"] == 0
                and row.get("final_disposed", False)
                and row.get("final_disposal_checked_out") == 0
                and row["peak_checked_out"] <= row["pool_size"] + row["max_overflow"]
                for _, _, row in self.bindings
            )
        )
        try:
            self.path.write_text(
                json.dumps(
                    {
                        "pid": os.getpid(),
                        "pools": self.entries,
                        "configuration": configuration,
                        "expected_configuration": self.expected,
                        "errors": dict(self.errors),
                        "outcome": self.outcome,
                        "sample_count": self.sample_count,
                        "expected_shutdown_cancellations": self.shutdown_cancellations,
                        "resource_errors": self.resource_errors,
                        "resource_errors_omitted": max(
                            0, self.errors["ConnectionResourceError"] - len(self.resource_errors)
                        ),
                        "finalized": finalized,
                        "passed": passed,
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        except OSError as error:
            self.errors[type(error).__name__] += 1

    def register(self, engine: AsyncEngine) -> None:
        pool = engine.pool
        if any(known() is pool for _, known, _ in self.bindings):
            return
        try:
            admin = os.environ.get("TIEWTRADE_TEST_ADMIN_URL")
            is_admin = admin is not None and engine.url == make_url(admin)
            if is_admin:
                options = engine.get_execution_options()
                if (
                    options.get("postgresql_readonly") is not True
                    or options.get("isolation_level") != "REPEATABLE READ"
                ):
                    raise ValueError("read-only admin observer options required")
                # Reuse event accounting only; this never changes the database role.
                role = DatabaseRole.MIGRATOR
            else:
                role = DatabaseRole(engine.url.username)
            engine_id = id(engine)
            generation = sum(known is engine for known, _, _ in self.bindings)
            self.engines[engine_id] = engine
            listener_start = len(self.listeners)
            super().add(engine, role)
            # Retired pools must remain collectible after a deliberate dispose.
            # Strong observer references would otherwise retain late-returned connections.
            for index in range(listener_start, len(self.listeners)):
                target, name, callback = self.listeners[index]
                self.listeners[index] = (ref(target), name, callback)
            row = self.entries[-1]
            if is_admin:
                row["role"] = "ADMIN_OBSERVER"
            row.update(
                pool_id=f"{os.getpid()}:{list(self.engines).index(engine_id)}:{generation}",
                generation=generation,
                pid=os.getpid(),
            )
            self.bindings.append((engine, ref(pool), row))
            if generation == 0:

                def failed(context: Any) -> None:
                    state = getattr(context.original_exception, "sqlstate", "") or ""
                    if context.is_disconnect or state.startswith("08"):
                        if (
                            isinstance(context.original_exception, asyncio.CancelledError)
                            and self.quiescing
                        ):
                            self.shutdown_cancellations += 1
                        else:
                            self.errors["ConnectionResourceError"] += 1
                            if len(self.resource_errors) < 16:
                                current_row = next(
                                    (
                                        r
                                        for e, pool_ref, r in self.bindings
                                        if e is engine and pool_ref() is engine.pool
                                    ),
                                    None,
                                )
                                identity_basis = (
                                    "engine_current_pool"
                                    if current_row is not None
                                    else "original_registration_fallback"
                                )
                                current_row = current_row or row
                                detail = {
                                    "at": datetime.now(UTC).isoformat(),
                                    "monotonic": monotonic(),
                                    "pid": os.getpid(),
                                    "engine_id": id(engine),
                                    "pool_id": current_row["pool_id"],
                                    "pool_identity_basis": identity_basis,
                                    "generation": current_row["generation"],
                                    "role": current_row["role"],
                                    "pool_size": current_row["pool_size"],
                                    "max_overflow": current_row["max_overflow"],
                                    "configured_readonly": engine.get_execution_options().get(
                                        "postgresql_readonly", False
                                    )
                                    is True,
                                    "deadline_context": "not_observed",
                                    "error_type": type(context.original_exception).__name__,
                                    "sqlstate": state,
                                    "quiescing": self.quiescing,
                                }
                                try:
                                    detail.update(task_provenance())
                                except Exception as provenance_error:
                                    self.errors[
                                        "Provenance:" + type(provenance_error).__name__
                                    ] += 1
                                    detail["provenance_error_type"] = type(
                                        provenance_error
                                    ).__name__
                                self.resource_errors.append(detail)
                            self.save(finalized=False)

                event.listen(engine.sync_engine, "handle_error", failed)
                self.listeners.append((ref(engine.sync_engine), "handle_error", failed))
            if generation:
                original = next(r for e, _, r in self.bindings if e is engine)
                if (row["pool_size"], row["max_overflow"]) != (
                    original["pool_size"],
                    original["max_overflow"],
                ):
                    self.errors["PoolConfigurationChanged"] += 1
            self.sample("registered")
        except Exception as error:
            self.errors[type(error).__name__] += 1

    def sample(self, reason: str = "periodic", *, force: bool = True) -> None:
        now = monotonic()
        if not force and now < self.next_sample:
            return
        self.next_sample = now + 5
        rows = []
        for _, pool_ref, entry in self.bindings:
            try:
                retired = entry.get("intermediate_disposed", False)
                if not 0 <= entry["checked_out"] <= entry["pool_size"] + entry["max_overflow"] or (
                    entry["peak_checked_out"] > entry["pool_size"] + entry["max_overflow"]
                ):
                    self.errors["PoolCapacityViolation"] += 1
                pool = pool_ref()
                if pool is None:
                    if not retired and (entry["checked_out"] or not entry.get("final_disposed")):
                        self.errors["PoolDisappearedBeforeReturn"] += 1
                    rows.append(
                        {
                            "pool_id": entry["pool_id"],
                            "collected": True,
                            "lifecycle": "retired" if retired else "live_or_final_disposed",
                            "retired_returns_pending": retired and entry["checked_out"] > 0,
                            "active_borrows": entry["checked_out"],
                        }
                    )
                    continue
                size, maximum = pool.size(), pool._max_overflow
                checked_in, checked_out = pool.checkedin(), pool.checkedout()
                if (
                    type(size) is not int
                    or type(maximum) is not int
                    or size != entry["pool_size"]
                    or maximum != entry["max_overflow"]
                    or size <= 0
                    or maximum < 0
                    or (
                        not retired
                        and (
                            checked_in < 0
                            or checked_out < 0
                            or checked_in + checked_out > size + maximum
                        )
                    )
                ):
                    self.errors["PoolCapacityViolation"] += 1
                rows.append(
                    {
                        "pool_id": entry["pool_id"],
                        "role": entry["role"],
                        "pool_size": size,
                        "max_overflow": maximum,
                        "checked_in": checked_in,
                        "checked_out": checked_out,
                        "overflow": pool.overflow(),
                        "lifecycle": "retired" if retired else "live_or_final_disposed",
                        "native_counts_binding": not retired,
                        "retired_returns_pending": retired and entry["checked_out"] > 0,
                        "active_borrows": entry["checked_out"],
                    }
                )
            except Exception as error:
                self.errors[type(error).__name__] += 1
        try:
            if self.stream is None:
                self.stream = self.path.with_suffix(".jsonl").open("x", encoding="utf-8")
            self.stream.write(
                json.dumps({"pid": os.getpid(), "monotonic": now, "reason": reason, "pools": rows})
                + "\n"
            )
            self.stream.flush()
            self.sample_count += 1
        except OSError as error:
            self.errors[type(error).__name__] += 1
        self.save(finalized=False)

    def begin_quiescence(self) -> None:
        self.quiescing = True
        self.sample("owned_work_stopping")

    @contextmanager
    def intermediate_disposal(self) -> Any:
        previous = self.disposal_kind
        self.disposal_kind = "fault_churn"
        try:
            yield
        finally:
            self.disposal_kind = previous

    def __enter__(self) -> OwnedPools:
        original_init, original_dispose = AsyncEngine.__init__, AsyncEngine.dispose
        original_start = AsyncConnection.start

        def created(engine: AsyncEngine, sync_engine: Any) -> None:
            original_init(engine, sync_engine)
            if CURRENT.get() is self:
                self.register(engine)

        async def disposed(engine: AsyncEngine, close: bool = True) -> None:
            owned = id(engine) in self.engines
            if owned:
                self.sample("before_" + self.disposal_kind + "_disposal")
                for candidate, pool_ref, row in self.bindings:
                    if candidate is engine and pool_ref() is engine.pool:
                        if self.disposal_kind == "final":
                            row["final_disposal_checked_out"] = max(
                                cast(QueuePool, engine.pool).checkedout(), row["checked_out"]
                            )
                            row["final_disposed"] = True
                        else:
                            row["intermediate_disposed"] = True
            await original_dispose(engine, close=close)
            if owned and self.disposal_kind != "final":
                self.register(engine)

        async def started(
            connection: AsyncConnection, is_ctxmanager: bool = False
        ) -> AsyncConnection:
            try:
                return await original_start(connection, is_ctxmanager=is_ctxmanager)
            except PoolTimeoutError:
                if id(connection.engine) in self.engines:
                    self.errors["PoolTimeoutError"] += 1
                raise

        self.token = CURRENT.set(self)
        self.stack.enter_context(patch.object(AsyncEngine, "__init__", created))
        self.stack.enter_context(patch.object(AsyncEngine, "dispose", disposed))
        self.stack.enter_context(patch.object(AsyncConnection, "start", started))
        return self

    def __exit__(self, kind: Any, error: Any, traceback: Any) -> None:
        self.outcome = "RETURNED" if error is None else type(error).__name__
        try:
            self.sample("quiescent")
            # Intermediate generations also must return every borrow before shutdown.
            for _, _, row in self.bindings:
                if row.get("intermediate_disposed"):
                    row["final_disposed"] = True
                    row["final_disposal_checked_out"] = row["checked_out"]
            self.save(finalized=True)
        finally:
            cleanup_errors: list[BaseException] = []
            for target_ref, name, callback in self.listeners:
                try:
                    target = target_ref()
                    if target is not None:
                        event.remove(target, name, callback)
                except Exception as cleanup_error:
                    cleanup_errors.append(cleanup_error)
            self.listeners.clear()
            try:
                self.stack.close()
            finally:
                CURRENT.reset(self.token)
                if self.stream is not None:
                    try:
                        self.stream.close()
                    except OSError as cleanup_error:
                        cleanup_errors.append(cleanup_error)
            for observed_error in cleanup_errors:
                self.errors[type(observed_error).__name__] += 1
                if error is not None:
                    error.add_note(f"pool observer cleanup failed: {type(observed_error).__name__}")
            self.save(finalized=True)


@asynccontextmanager
async def observe_owned(
    path: Path, expected: list[tuple[str, int, int]]
) -> AsyncIterator[OwnedPools]:
    with OwnedPools(path, expected) as tracker:
        stop = asyncio.Event()

        async def samples() -> None:
            while not stop.is_set():
                tracker.sample(force=False)
                with suppress(TimeoutError):
                    await asyncio.wait_for(stop.wait(), timeout=5)

        task = asyncio.create_task(samples())
        try:
            yield tracker
        finally:
            stop.set()
            try:
                outcomes = await asyncio.gather(task, return_exceptions=True)
            except asyncio.CancelledError:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                raise
            for outcome in outcomes:
                if isinstance(outcome, BaseException):
                    tracker.errors["ObserverTask:" + type(outcome).__name__] += 1


def sample_current() -> None:
    tracker = CURRENT.get()
    if tracker is not None:
        tracker.sample(force=False)


def validate_reports(parent: Path, workers: list[Path], expected_workers: int) -> dict[str, Any]:
    incomplete: list[str] = []
    violations: list[str] = []
    reports = []
    if (
        expected_workers <= 0
        or len(workers) < expected_workers
        or len(workers) % expected_workers
        or len(set(workers)) != len(workers)
    ):
        incomplete.append("WorkerInventoryIncomplete")
    proven_errors = {
        "PoolTimeoutError",
        "ConnectionResourceError",
        "PoolCapacityViolation",
        "PoolConfigurationChanged",
        "PoolDisappearedBeforeReturn",
    }
    for path, expected in [
        (parent, PARENT_CONFIGURATION),
        *[(p, WORKER_CONFIGURATION) for p in workers],
    ]:
        try:
            document = json.loads(path.read_text())
            entries = document["pools"]
            configuration = sorted(
                (p["role"], p["pool_size"], p["max_overflow"])
                for p in entries
                if p["generation"] == 0
            )
            if configuration != sorted(expected) or configuration != sorted(
                tuple(c) for c in document["configuration"]
            ):
                incomplete.append("PoolInventoryMismatch:" + path.name)
            if (
                document["finalized"] is not True
                or document["outcome"] != "RETURNED"
                or len({p["pool_id"] for p in entries}) != len(entries)
                or any(p.get("final_disposed") is not True for p in entries)
            ):
                incomplete.append("PoolFinalEvidenceIncomplete:" + path.name)
            for error in document["errors"]:
                target = violations if error in proven_errors else incomplete
                target.append(error + ":" + path.name)
            if any(
                p["checked_out"] != 0
                or p["final_disposal_checked_out"] != 0
                or p["pool_size"] <= 0
                or p["max_overflow"] < 0
                or p["peak_checked_out"] > p["pool_size"] + p["max_overflow"]
                for p in entries
            ):
                violations.append("PoolReturnEvidenceFailed:" + path.name)
            if document["passed"] is not True and not document["errors"]:
                incomplete.append("PoolEvidenceNotAccepted:" + path.name)
            samples = path.with_suffix(".jsonl").read_text().splitlines()
            if (
                not samples
                or len(samples) != document["sample_count"]
                or json.loads(samples[-1])["reason"] != "quiescent"
            ):
                incomplete.append("PoolSamplesIncomplete:" + path.name)
            reports.append(
                {"file": path.name, "pid": document["pid"], "passed": document.get("passed", False)}
            )
        except (OSError, ValueError, KeyError, TypeError):
            incomplete.append("PoolEvidenceUnavailable:" + path.name)
    return {
        "passed": not incomplete and not violations,
        "errors": violations + incomplete,
        "violations": violations,
        "incomplete": incomplete,
        "processes": reports,
        "worker_process_count": len(workers),
    }
