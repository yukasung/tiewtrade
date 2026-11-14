"""Opt-in F15 observations using existing test instrumentation; never acceptance."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from contextlib import AsyncExitStack, asynccontextmanager, contextmanager, nullcontext, suppress
from contextvars import ContextVar
from functools import lru_cache, wraps
from pathlib import Path
from time import monotonic, time
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market import profile_workload as f15
from tests.infra.execution_market.profile_runtime_observation import RuntimeObservation
from tests.infra.risk_limits.profile_dispatch_timing import traced_worker
from tests.infra.risk_limits.profile_pool_timing import (
    TransactionTrace,
    operation_scope,
    sample_database,
)
from tests.infra.risk_limits.profile_resources import worker_pool_evidence
from tests.infra.risk_limits.scheduler_diagnostics import read_scheduler_diagnostics
from tiewtrade.core.orders import OrderStatus
from tiewtrade.infra.db import DatabaseRole
from tiewtrade.infra.db import session as db

_CYCLE: ContextVar[dict[str, Any] | None] = ContextVar("f15_diagnostic_cycle", default=None)
_OBSERVATIONS: ContextVar[list[dict[str, Any]] | None] = ContextVar(
    "f15_first_observations", default=None
)


def generator_operation(
    phase: str, original: Callable[..., Awaitable[Any]]
) -> Callable[..., Awaitable[Any]]:
    @wraps(original)
    async def observed(*args: Any, **kwargs: Any) -> Any:
        identity = {"phase": phase}
        if len(args) > 1:
            owner = getattr(args[1], "user_id", args[1])
            if isinstance(owner, UUID):
                identity["owner"] = str(owner)
        if len(args) > 2:
            target = args[2]
            if phase == "wait_status" and isinstance(target, UUID):
                identity["order_id"] = str(target)
            for name in ("command_id", "order_id"):
                value = getattr(target, name, None)
                if isinstance(value, UUID):
                    identity[name] = str(value)
        target = kwargs.get("intent")
        if target is not None and isinstance(getattr(target, "order_id", None), UUID):
            identity["order_id"] = str(target.order_id)
        if isinstance(kwargs.get("order_id"), UUID):
            identity["order_id"] = str(kwargs["order_id"])
        if phase == "publish_market":
            tick = kwargs.get("trade_id")
            if isinstance(tick, int):
                identity["publisher_tick"] = str(tick)
            if len(args) > 1:
                lease = args[1]
                if isinstance(getattr(lease, "owner", None), UUID):
                    identity["book_owner"] = str(lease.owner)
                for name in ("generation", "last_input_id"):
                    value = getattr(lease, name, None)
                    if isinstance(value, int):
                        identity["book_" + name] = str(value)
        if "owner" not in identity and args:
            owner = getattr(args[0], "user_id", None)
            if isinstance(owner, UUID):
                identity["owner"] = str(owner)
        if phase == "wait_status" and len(args) > 3 and isinstance(args[3], OrderStatus):
            identity["expected_status"] = args[3].value

        cycle = _CYCLE.get()
        entry = None
        started = monotonic()
        if cycle is not None:
            if len(cycle["phases"]) < 32:
                entry = {**identity, "started_at": time(), "started_monotonic": started}
                cycle["phases"].append(entry)
            else:
                cycle["truncated"] = True
        outcome = "returned"
        with operation_scope(**identity):
            try:
                return await original(*args, **kwargs)
            except BaseException as error:
                outcome = type(error).__name__
                raise
            finally:
                if entry is not None:
                    entry.update(finished_at=time(), seconds=monotonic() - started, outcome=outcome)
                    observations = _OBSERVATIONS.get()
                    if (
                        observations is not None
                        and phase
                        in {"submit_order", "submit_cancel", "wait_command", "wait_status"}
                        and outcome == "returned"
                    ):
                        if len(observations) >= 10000:
                            raise RuntimeError("first observation bound exceeded")
                        observations.append({**entry, "finished_monotonic": monotonic()})

    return observed


@lru_cache(maxsize=128)
def query_fingerprint(statement: str) -> str:
    return hashlib.sha256(statement.encode()).hexdigest()


@contextmanager
def query_observations() -> Iterator[None]:
    """Only in-flight cycle aggregates; no query text/values or successful-cycle I/O."""
    original = db._execute

    @wraps(original)
    async def observed(connection: Any, statement: str, parameters: Any) -> Any:
        cycle = _CYCLE.get()
        if cycle is None:
            return await original(connection, statement, parameters)
        queries = cycle.setdefault("queries", {})
        fingerprint = query_fingerprint(statement)
        if fingerprint not in queries and len(queries) >= 32:
            cycle["queries_truncated"] = True
            aggregate = None
        else:
            aggregate = queries.setdefault(fingerprint, {"count": 0, "seconds": 0.0, "max": 0.0})
        cycle["query_count"] = cycle.get("query_count", 0) + 1
        started = monotonic()
        outcome = "RETURNED"
        try:
            return await original(connection, statement, parameters)
        except BaseException as error:
            outcome = type(error).__name__
            raise
        finally:
            duration = monotonic() - started
            if aggregate is not None:
                aggregate["count"] += 1
                aggregate["seconds"] += duration
                aggregate["max"] = max(aggregate["max"], duration)
            recent = cycle.setdefault("recent_queries", [])
            if len(recent) == 16:
                recent.pop(0)
            recent.append(
                {
                    "fingerprint": fingerprint,
                    "started": started,
                    "seconds": duration,
                    "outcome": outcome,
                }
            )

    db._execute = observed
    try:
        yield
    finally:
        db._execute = original
        query_fingerprint.cache_clear()


def write_worker_progress(output: Path) -> None:
    """Read existing metric tails only, after worker shutdown; never a live snapshot."""
    workers: list[dict[str, Any]] = []
    for path in sorted(output.glob("worker-*.latencies"))[:20]:
        record: dict[str, Any] = {"worker": path.stem, "tail_limit_bytes": 65536}
        try:
            with path.open("rb") as stream:
                size = path.stat().st_size
                offset = max(0, size - 65536)
                stream.seek(offset)
                lines = stream.read(65536).splitlines()
            if offset:
                lines = lines[1:]
            rows = [json.loads(line) for line in lines]
            record.update(tail_rows=len(rows), truncated=bool(offset))
            if rows:
                last = rows[-1]
                timing = {key: last[key] for key in ("started", "finished", "seconds")}
                if not all(
                    type(value) in (int, float) and math.isfinite(value) and value >= 0
                    for value in timing.values()
                ):
                    raise ValueError("invalid worker timing")
                record["last_transaction"] = timing
        except (OSError, ValueError, KeyError, TypeError) as error:
            record["error_type"] = type(error).__name__
        workers.append(record)
    f15.save(
        output / "timeout-worker-progress.json",
        {"after_workers_stopped": True, "observed_monotonic": monotonic(), "workers": workers},
    )


@contextmanager
def parent_observations(
    output: Path, *, failure_only: bool = False
) -> Iterator[list[dict[str, Any]]]:
    names = (
        "cycle",
        "submit_new",
        "submit_order",
        "submit_cancel",
        "wait_command",
        "wait_status",
        "acquire_sources",
        "publish_market",
    )
    originals = {name: getattr(f15, name) for name in names}
    original_sampler = f15.resource_sampler
    original_cycles = f15.run_scheduled_cycles
    timeouts: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    token = _OBSERVATIONS.set(observations if failure_only else None)
    primary: BaseException | None = None

    async def scheduled(*args: Any, **kwargs: Any) -> float:
        # Existing custom scopes remain untouched; standalone W1 uses the default60s.
        if kwargs.get("cycle_scope") is not None:
            return await original_cycles(*args, **kwargs)
        owners = args[1] if len(args) > 1 else kwargs["owners"]
        run_id = args[2] if len(args) > 2 else kwargs["run_id"]

        @asynccontextmanager
        async def cycle_scope(owner: f15.OwnerState, number: int) -> AsyncIterator[None]:
            started = monotonic()
            record: dict[str, Any] = {
                "owner": str(owner.user_id),
                "run_id": str(run_id),
                "cycle": number,
                "started_at": time(),
                "started_monotonic": started,
                "phases": [],
                "truncated": False,
                "budget_seconds": 60,
            }
            token = _CYCLE.set(record)
            budget = asyncio.timeout(60)
            try:
                async with budget:
                    record["deadline_monotonic"] = budget.when()
                    yield
            except TimeoutError as error:
                # A sibling cancellation or an inner TimeoutError is not cycle expiry.
                if budget.expired() and len(timeouts) < len(owners):
                    record.update(timed_out_at=time(), elapsed_seconds=monotonic() - started)
                    timeouts.append(record)
                    try:
                        f15.save(output / "cycle-timeouts.json", {"cycles": timeouts})
                    except OSError as write_error:
                        record["write_error"] = type(write_error).__name__
                if budget.expired():
                    raise f15.CycleBudgetExceededError(
                        "Paper cycle exceeded its 60-second budget"
                    ) from error
                raise
            finally:
                _CYCLE.reset(token)

        return await original_cycles(*args, **{**kwargs, "cycle_scope": cycle_scope})

    async def sampler(
        migrator: AsyncEngine,
        source: AsyncEngine,
        processes: list[asyncio.subprocess.Process],
        process_lock: asyncio.Lock,
        stop: asyncio.Event,
        samples: list[dict[str, object]],
        evidence_path: Path | None = None,
        *,
        observe_host: bool = False,
    ) -> None:
        async def database() -> None:
            with suppress(TimeoutError):
                async with asyncio.timeout(180):
                    await sample_database(migrator, output / "database.jsonl", stop)

        host_options: f15.ResourceOptions = {"observe_host": True} if observe_host else {}
        async with asyncio.TaskGroup() as tasks:
            tasks.create_task(database())
            tasks.create_task(
                original_sampler(
                    migrator,
                    source,
                    processes,
                    process_lock,
                    stop,
                    samples,
                    evidence_path,
                    **host_options,
                )
            )

    for name, original in originals.items():
        setattr(f15, name, generator_operation(name, original))
    if not failure_only:
        f15.resource_sampler = sampler
    f15.run_scheduled_cycles = scheduled
    try:
        with query_observations() if failure_only else nullcontext():
            yield timeouts
    except BaseException as error:
        primary = error
        raise
    finally:
        _OBSERVATIONS.reset(token)
        f15.run_scheduled_cycles = original_cycles
        f15.resource_sampler = original_sampler
        for name, original in originals.items():
            setattr(f15, name, original)
        if failure_only:
            try:
                f15.save(
                    output / "first-observations.json",
                    {"acceptance_result": False, "row_limit": 10000, "rows": observations},
                )
            except OSError as error:
                if primary is None:
                    raise
                primary.add_note(f"first observation write failed: {type(error).__name__}")


async def write_timeout_queue_snapshot(output: Path, timeouts: list[dict[str, Any]]) -> None:
    snapshots: list[dict[str, object]] = []
    document: dict[str, object] = {"after_workers_stopped": True, "snapshots": snapshots}
    engine = vars(f15)["create_engine_for"](DatabaseRole.ENGINE_SCAN)
    try:
        try:
            async with asyncio.timeout(5):
                for record in timeouts:
                    commands = tuple(
                        sorted(
                            {
                                UUID(entry["command_id"])
                                for entry in record["phases"]
                                if "command_id" in entry
                            }
                        )
                    )
                    snapshots.append(
                        await read_scheduler_diagnostics(
                            engine, UUID(record["owner"]), command_ids=commands
                        )
                    )
        except Exception as error:
            document["error_type"] = type(error).__name__
    finally:
        await engine.dispose()
    f15.save(output / "timeout-queue-snapshot.json", document)


async def observe_workload(args: argparse.Namespace, *, failure_only: bool = False) -> int:
    if args.phase not in {"W1", "SMOKE"}:
        raise ValueError("diagnostics requires W1 or SMOKE")
    output: Path = args.output
    if output.exists():
        raise FileExistsError(output)
    limited = getattr(args, "parent_poll_limit", None) is not None
    publisher_timing = (
        args.phase == "SMOKE" and limited and getattr(args, "coordinate_claims", False)
    )
    outcome: dict[str, object] = {
        "acceptance_result": False,
        "failure_timeline_only": failure_only,
        "trace_seconds": 0 if failure_only else 900 if limited else 180,
        "baseline_publisher_timing": publisher_timing and not failure_only,
    }
    runtime = RuntimeObservation(output / "parent-runtime.json", enabled=limited)
    timeouts: list[dict[str, Any]] = []
    run_error: BaseException | None = None
    try:
        async with AsyncExitStack() as stack:
            if not failure_only:
                await stack.enter_async_context(runtime.observe())
                await stack.enter_async_context(
                    TransactionTrace(
                        output / "parent.transactions.jsonl",
                        monotonic_fields=limited,
                        early_phases=(
                            frozenset({"acquire_sources", "publish_market"})
                            if publisher_timing
                            else frozenset()
                        ),
                    ).observe()
                )
                stack.enter_context(worker_pool_evidence(output / "parent.json"))
            timeouts = stack.enter_context(parent_observations(output, failure_only=failure_only))
            try:
                result = await f15._run(
                    args, **({"parent_runtime": runtime} if limited and not failure_only else {})
                )
            except BaseException as error:
                # Preserve workload failure even if an observer's cleanup also fails.
                run_error = error
        if run_error is not None:
            raise run_error
        outcome["exit_code"] = result
        return result
    except BaseException as error:
        if run_error is not None and error is not run_error:
            run_error.add_note(f"observer cleanup also failed: {type(error).__name__}")
            outcome["error_type"] = type(run_error).__name__
            raise run_error from error
        outcome["error_type"] = type(error).__name__
        raise
    finally:
        if output.is_dir():
            outcome["timeout_cycles"] = len(timeouts)
            if timeouts and isinstance(run_error, TimeoutError):
                try:
                    await write_timeout_queue_snapshot(output, timeouts)
                    if failure_only:
                        write_worker_progress(output)
                except Exception as error:
                    outcome["queue_snapshot_error"] = type(error).__name__
            if failure_only:
                from tests.infra.execution_market.profile_commit_observation import (
                    correlate_observations,
                )

                try:
                    f15.save(output / "completion-correlation.json", correlate_observations(output))
                except (OSError, ValueError, KeyError) as error:
                    outcome["completion_correlation_error"] = type(error).__name__
            try:
                f15.save(output / "diagnostic-only.json", outcome)
            except OSError as error:
                if run_error is None:
                    raise
                run_error.add_note(f"diagnostic receipt write failed: {type(error).__name__}")


async def observe_worker(args: argparse.Namespace) -> int:
    f15.validate_claim_coordination(
        getattr(args, "coordinate_claims", False), r8=getattr(args, "r8_claim_budget", False)
    )
    async with TransactionTrace(args.worker_metrics.with_suffix(".transactions.jsonl")).observe():
        with worker_pool_evidence(args.worker_metrics):
            await traced_worker(
                f15.run_worker_process(
                    args.worker_name,
                    args.worker_stop,
                    args.worker_metrics,
                    claim_limit=1 if getattr(args, "r8_claim_budget", False) else None,
                    **f15.coordination_options(getattr(args, "coordinate_claims", False)),
                    **f15.internal_worker_options(args),
                ),
                args.worker_metrics,
            )
    return 0
