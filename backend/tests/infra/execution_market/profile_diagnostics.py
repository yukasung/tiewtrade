"""Opt-in F15 observations using existing test instrumentation; never acceptance."""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from contextlib import asynccontextmanager, contextmanager, suppress
from contextvars import ContextVar
from functools import wraps
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

_CYCLE: ContextVar[dict[str, Any] | None] = ContextVar("f15_diagnostic_cycle", default=None)


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

    return observed


@contextmanager
def parent_observations(output: Path) -> Iterator[list[dict[str, Any]]]:
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
            except TimeoutError:
                # A sibling cancellation or an inner TimeoutError is not cycle expiry.
                if budget.expired() and len(timeouts) < len(owners):
                    record.update(timed_out_at=time(), elapsed_seconds=monotonic() - started)
                    timeouts.append(record)
                    try:
                        f15.save(output / "cycle-timeouts.json", {"cycles": timeouts})
                    except OSError as error:
                        record["write_error"] = type(error).__name__
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
    f15.resource_sampler = sampler
    f15.run_scheduled_cycles = scheduled
    try:
        yield timeouts
    finally:
        f15.run_scheduled_cycles = original_cycles
        f15.resource_sampler = original_sampler
        for name, original in originals.items():
            setattr(f15, name, original)


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


async def observe_workload(args: argparse.Namespace) -> int:
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
        "trace_seconds": 900 if limited else 180,
        "baseline_publisher_timing": publisher_timing,
    }
    runtime = RuntimeObservation(output / "parent-runtime.json", enabled=limited)
    timeouts: list[dict[str, Any]] = []
    run_error: BaseException | None = None
    try:
        async with (
            runtime.observe(),
            TransactionTrace(
                output / "parent.transactions.jsonl",
                monotonic_fields=limited,
                early_phases=(
                    frozenset({"acquire_sources", "publish_market"})
                    if publisher_timing
                    else frozenset()
                ),
            ).observe(),
        ):
            with (
                worker_pool_evidence(output / "parent.json"),
                parent_observations(output) as timeouts,
            ):
                try:
                    result = await f15._run(
                        args, **({"parent_runtime": runtime} if limited else {})
                    )
                except BaseException as error:
                    # Defer rethrow until the observation TaskGroup closes; preserve original type.
                    run_error = error
        if run_error is not None:
            raise run_error
        outcome["exit_code"] = result
        return result
    except BaseException as error:
        if (
            run_error is not None
            and not isinstance(run_error, asyncio.CancelledError)
            and error is not run_error
        ):
            run_error.add_note(f"observer cleanup also failed: {type(error).__name__}")
            outcome["error_type"] = type(run_error).__name__
            raise run_error from error
        outcome["error_type"] = type(error).__name__
        raise
    finally:
        if output.is_dir():
            outcome["timeout_cycles"] = len(timeouts)
            if timeouts and outcome.get("error_type") == "TimeoutError":
                try:
                    await write_timeout_queue_snapshot(output, timeouts)
                except Exception as error:
                    outcome["queue_snapshot_error"] = type(error).__name__
            f15.save(output / "diagnostic-only.json", outcome)


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
