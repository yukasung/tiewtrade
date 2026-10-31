"""Opt-in bounded W2 timing. Observes existing calls/transactions; never adds SQL."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import asdict, is_dataclass
from pathlib import Path
from time import monotonic, time
from typing import Any

from tests.infra.execution_market import profile_workload as f15
from tiewtrade.infra.db import session as db
from tiewtrade.infra.paper_orders import worker as order_worker
from tiewtrade.services.engine import manual_order, paper_order

_CURRENT: ContextVar[dict[str, Any] | None] = ContextVar("dispatch_observation", default=None)


class Recorder:
    def __init__(self, metrics: Path) -> None:
        self.control = metrics.parent / "dispatch-trace-control.json"
        self.start: float | None = None
        self.owners: set[str] = set()
        self.buckets: dict[int, dict[str, Any]] = {}
        self.setup: dict[str, Any] = {}
        self.last_round_end: float | None = None
        self.detail_count = 0
        self.truncated = False
        self.stream = metrics.with_suffix(".dispatch.jsonl").open("x")

    def activate(self) -> None:
        if self.start is None and self.control.exists():
            control = json.loads(self.control.read_text())
            self.start = float(control["started"])
            self.owners = set(control["owners"])
            self.write({"event": "SETUP_SUMMARY", "calls": self.setup, "observed_at": time()})

    def write(self, row: dict[str, Any]) -> None:
        self.stream.write(json.dumps(row) + "\n")
        self.stream.flush()

    def record(self, phase: str, started: float, **fields: Any) -> None:
        self.activate()
        ended = monotonic()
        measured = self.start is not None and 0 <= started - self.start < 60
        if measured:
            assert self.start is not None
            # Late completions have a separate bounded tail bucket.
            bucket = min(60, int(max(0, ended - self.start)))
            target = self.buckets.setdefault(bucket, {})
        else:
            target = self.setup
        group = phase + "/" + fields["work"] if "work" in fields else phase
        values = target.setdefault(group, {"count": 0, "seconds": 0.0, "max_seconds": 0.0})
        values["count"] += 1
        values["seconds"] += ended - started
        values["max_seconds"] = max(values["max_seconds"], ended - started)
        for key in ("hints", "claimed", "skipped", "processed", "deferred"):
            if key in fields:
                values[key] = values.get(key, 0) + fields[key]
        if measured and fields.get("owner") in self.owners:
            if self.detail_count >= 100:  # Ten workers: <=1000 detail records in total.
                self.truncated = True
                return
            self.detail_count += 1
            self.write(
                {
                    "event": "DETAIL",
                    "phase": phase,
                    "started": started,
                    "finished": ended,
                    "observed_at": time(),
                    **fields,
                }
            )

    def flush(self, *, final: bool = False) -> None:
        self.activate()
        if self.start is None:
            return
        current = min(60, int(max(0, monotonic() - self.start)))
        for bucket in sorted(self.buckets):
            if final or bucket < current:
                self.write(
                    {
                        "event": "TAIL" if bucket == 60 else "SECOND",
                        "second": bucket,
                        "phases": self.buckets.pop(bucket),
                    }
                )
        if self.truncated:
            raise RuntimeError("F18_DISPATCH_TRACE_TRUNCATED")

    def wrap(self, phase: str, original: Callable[..., Any]) -> Callable[..., Any]:
        async def observed(*args: Any, **kwargs: Any) -> Any:
            self.activate()
            if phase == "manual_round" and self.last_round_end is not None:
                self.record("loop_gap", self.last_round_end)
            started = monotonic()
            wall = time()
            transaction = _CURRENT.get()
            identity: dict[str, Any] = {}
            if len(args) > 1:
                claim = args[1]
                for source, key in (
                    ("user_id", "owner"),
                    ("command_id", "command"),
                    ("request_id", "request"),
                    ("claim_id", "attempt"),
                ):
                    if hasattr(claim, source):
                        identity[key] = str(getattr(claim, source))
            if transaction is not None:
                transaction.update(phase=phase, **identity)
            fields = {"started_wall": wall, **identity}
            try:
                result = await original(*args, **kwargs)
                if phase.endswith("scan"):
                    fields["hints"] = len(result)
                elif phase.endswith("claim"):
                    fields.update(claimed=int(result is not None), skipped=int(result is None))
                    if result is not None:
                        fields["attempt"] = str(result.claim_id)
                        if transaction is not None:
                            transaction["attempt"] = fields["attempt"]
                elif is_dataclass(result) and not isinstance(result, type):
                    fields.update(
                        {
                            k: v
                            for k, v in asdict(result).items()
                            if k in {"processed", "deferred", "skipped"}
                        }
                    )
                fields["outcome"] = "returned"
                return result
            except BaseException as error:
                fields["outcome"] = type(error).__name__
                raise
            finally:
                if transaction is not None and "work" in transaction:
                    fields["work"] = transaction["work"]
                self.record(phase + ".call", started, **fields)
                if phase == "order_round":
                    self.last_round_end = monotonic()

        return observed


async def traced_worker(operation: Awaitable[None], metrics: Path) -> None:
    recorder = Recorder(metrics)
    original_begin = db._begin
    patches: list[tuple[Any, str, Any]] = []

    @asynccontextmanager
    async def transaction(
        engine: Any, *, cleanup_seconds: float | None = None
    ) -> AsyncIterator[Any]:
        started = monotonic()
        context: dict[str, Any] = {"phase": "other", "started_wall": time()}
        token = _CURRENT.set(context)
        outcome = "COMMIT"
        try:
            async with original_begin(engine, cleanup_seconds=cleanup_seconds) as connection:
                yield connection
        except BaseException as error:
            outcome = "ROLLBACK:" + type(error).__name__
            raise
        finally:
            _CURRENT.reset(token)
            phase = context.pop("phase")
            recorder.record(phase + ".transaction", started, outcome=outcome, **context)

    async def classify_new(*args: Any, **kwargs: Any) -> Any:
        context = _CURRENT.get()
        if context is not None:
            context["work"] = "ACTIVE" if args[2]["result_state"] is not None else "PENDING"
        return await original_new(*args, **kwargs)

    async def classify_cancel(*args: Any, **kwargs: Any) -> Any:
        context = _CURRENT.get()
        if context is not None:
            context["work"] = "CANCEL"
        return await original_cancel(*args, **kwargs)

    def patch(module: Any, name: str, phase: str) -> None:
        original = getattr(module, name)
        patches.append((module, name, original))
        setattr(module, name, recorder.wrap(phase, original))

    original_cancel = order_worker._process_cancel
    original_new = order_worker._process_new
    order_worker._process_new = classify_new
    order_worker._process_cancel = classify_cancel
    db._begin = transaction
    for module, name, phase in (
        (f15, "run_manual_order_round", "manual_round"),
        (f15, "run_paper_order_round", "order_round"),
        (manual_order, "due_requests", "manual_scan"),
        (manual_order, "claim_request", "manual_claim"),
        (manual_order, "process_request", "manual_process"),
        (paper_order, "due_orders", "order_scan"),
        (paper_order, "claim_order", "order_claim"),
        (paper_order, "process_claimed_order", "order_process"),
        (paper_order, "reconcile_removal_effects", "maintenance_removal"),
        (paper_order, "reconcile_maintenance_proofs", "maintenance_proofs"),
    ):
        patch(module, name, phase)

    stop = asyncio.Event()

    async def flush() -> None:
        while not stop.is_set():
            recorder.flush()
            try:
                await asyncio.wait_for(stop.wait(), timeout=1)
            except TimeoutError:
                continue

    observer = asyncio.create_task(flush())
    try:
        await f15.with_publisher(operation, observer)
    finally:
        stop.set()
        try:
            await observer
        finally:
            db._begin = original_begin
            order_worker._process_new = original_new
            order_worker._process_cancel = original_cancel
            for module, name, original in reversed(patches):
                setattr(module, name, original)
            try:
                recorder.flush(final=True)
                recorder.write(
                    {
                        "event": "CLOSED",
                        "detail_records": recorder.detail_count,
                        "truncated": recorder.truncated,
                    }
                )
            finally:
                recorder.stream.close()
