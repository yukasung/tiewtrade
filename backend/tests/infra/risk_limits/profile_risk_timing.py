"""NC18 scoped test observers; no scheduler, pool or authorization changes."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import asynccontextmanager, contextmanager, suppress
from contextvars import ContextVar
from pathlib import Path
from time import monotonic, time
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.risk_limits.profile_dispatch_timing import _CURRENT
from tests.infra.risk_limits.profile_pool_timing import TransactionTrace
from tiewtrade.infra.risk_limits import monitor
from tiewtrade.services.engine import risk_limit as service
from tiewtrade.services.engine import risk_limit_main as runtime

_ROUND: ContextVar[dict[str, Any] | None] = ContextVar("risk_round_observation", default=None)
_SPAN: ContextVar[dict[str, Any] | None] = ContextVar("risk_span_observation", default=None)


class Journal:
    def __init__(self, path: Path, window: TransactionTrace) -> None:
        self.path, self.window = path, window
        self.pending: list[dict[str, Any]] = []
        self.count = 0
        self.stream: Any = None
        self.truncated = False

    def record(self, row: dict[str, Any]) -> None:
        self.count += 1
        if self.count > 100000:
            self.truncated = True
            raise RuntimeError("F19_RISK_OBSERVER_TRUNCATED")
        self.pending.append(row)

    def flush(self) -> None:
        if self.truncated:
            raise RuntimeError("F19_RISK_OBSERVER_TRUNCATED")
        if self.stream is None:
            self.stream = self.path.open("x")
        self.stream.writelines(json.dumps(r, default=str) + "\n" for r in self.pending)
        self.pending.clear()
        self.stream.flush()

    def close(self, **fields: Any) -> None:
        try:
            self.flush()
            self.stream.write(
                json.dumps(
                    {
                        "event": "CLOSED",
                        "records": self.count,
                        "truncated": self.truncated,
                        "acceptance_result": False,
                        **fields,
                    }
                )
                + "\n"
            )
        finally:
            if self.stream is not None:
                self.stream.close()


@contextmanager
def phase(name: str) -> Iterator[None]:
    span = _SPAN.get()
    if span is None:
        yield
        return
    context = _CURRENT.get()
    parent = context.get("phase") if context is not None else None
    if context is not None:
        context["phase"] = name
    started = monotonic()
    row = {"phase": name, "parent": parent, "started_at": time()}
    try:
        yield
    except BaseException as error:
        row["error_type"] = type(error).__name__
        span.setdefault("failure_phase", name)
        span.setdefault("error_type", type(error).__name__)
        raise
    finally:
        row["seconds"] = monotonic() - started
        span["stages"].append(row)
        if context is not None:
            context["phase"] = parent


class RiskObserver:
    def __init__(self, metrics: Path, *, full: bool) -> None:
        self.window = TransactionTrace(
            metrics.with_suffix(".transactions.jsonl"),
            buffered=True,
            control=metrics.parent / "risk-trace-control.json",
        )
        self.proofs = Journal(metrics.with_suffix(".commit-proofs.jsonl"), self.window)
        self.spans = Journal(metrics.with_suffix(".risk-stages.jsonl"), self.window)
        self.full = full
        self.rounds = self.attempts = self.setup_rounds = 0
        self.selection: dict[str, int] = {}
        self.flush_seconds = self.loop_delay_max = 0.0

    def committed(self, sample: dict[str, Any]) -> None:
        # Only post-commit producers call this method. Pending rows are labelled and
        # never promoted into authoritative acknowledgements by the observer.
        self.proofs.record(
            {
                "event": "COMMIT_PROOF",
                "proof_id": f"{self.proofs.path.name}:{self.proofs.count + 1}",
                "span": (_SPAN.get() or {}).get("attempt"),
                **sample,
            }
        )

    @contextmanager
    def patches(self) -> Iterator[None]:
        if not self.full:
            yield
            return
        patches: list[tuple[dict[str, Any], str, Any]] = []

        def patch(module: Any, name: str, value: Any) -> None:
            namespace = vars(module)
            patches.append((namespace, name, namespace[name]))
            namespace[name] = value

        original_round = service.run_risk_monitor_round
        original_candidates = vars(runtime)["_scan_monitor_candidates"]
        original_evaluate = vars(runtime)["_evaluate_monitor_owner"]
        original_session = vars(service)["user_session"]
        original_scan = vars(service)["scan_session_bypassing_rls"]
        recorder = self

        class Semaphore:
            def __init__(self, value: int) -> None:
                self.actual = asyncio.Semaphore(value)

            async def __aenter__(self) -> Any:
                recorder.attempts += 1
                row: dict[str, Any] = {
                    "event": "OWNER",
                    "attempt": recorder.attempts,
                    "round": (_ROUND.get() or {}).get("round"),
                    "queued_at": time(),
                    "stages": [],
                }
                started = monotonic()
                span_token = _SPAN.set(row)
                context_token = _CURRENT.set(
                    {"phase": "monitor", "attempt": recorder.attempts, "round": row["round"]}
                )
                row["tokens"] = (span_token, context_token)
                try:
                    await self.actual.__aenter__()
                    row["slot_acquired_at"] = time()
                    row["semaphore_wait_seconds"] = monotonic() - started
                    return None
                except BaseException as error:
                    row["error_type"] = type(error).__name__
                    row["semaphore_wait_seconds"] = monotonic() - started
                    finish_span(row)
                    raise

            async def __aexit__(self, *args: Any) -> Any:
                row = _SPAN.get()
                try:
                    await self.actual.__aexit__(*args)
                finally:
                    assert row is not None
                    finish_span(row)

        def finish_span(row: dict[str, Any]) -> None:
            row["finished_at"] = time()
            span_token, context_token = row.pop("tokens")
            _CURRENT.reset(context_token)
            _SPAN.reset(span_token)
            self.spans.record(row)

        class AsyncioProxy:
            def __getattr__(self, name: str) -> Any:
                if name == "Semaphore" and _ROUND.get() is not None:
                    return Semaphore
                return getattr(asyncio, name)

        class ScanProxy:
            def __init__(self, session: Any) -> None:
                self.session = session

            async def execute(self, statement: str, parameters: Any = None) -> Any:
                result = await self.session.execute(statement, parameters)
                current = _ROUND.get()
                if current is not None and "WITH hints AS" in statement:
                    frozen = result.freeze()
                    rows = list(frozen())
                    current["selection_at"] = time()
                    current["selected"] = [
                        {
                            "owner": str(r.user_id),
                            "due_at": str(r.due_at) if r.due_at is not None else None,
                        }
                        for r in rows
                    ]
                    return frozen()
                return result

        @asynccontextmanager
        async def scan(*args: Any, **kwargs: Any) -> AsyncIterator[Any]:
            async with original_scan(*args, **kwargs) as session:
                yield ScanProxy(session) if _ROUND.get() is not None else session

        @asynccontextmanager
        async def session(engine: Any, owner: Any, **kwargs: Any) -> AsyncIterator[Any]:
            row = _SPAN.get()
            if row is not None:
                row["owner"] = str(owner)
                context = _CURRENT.get()
                assert context is not None
                context["owner"] = str(owner)
                row["transaction_requested_at"] = time()
            async with original_session(engine, owner, **kwargs) as value:
                yield value

        async def round_call(*args: Any, **kwargs: Any) -> Any:
            if not self.window.active():
                self.setup_rounds += 1
                return await original_round(*args, **kwargs)
            self.rounds += 1
            row: dict[str, Any] = {
                "event": "ROUND",
                "round": self.rounds,
                "started_at": time(),
                "after_owner": str(kwargs.get("after_owner")),
                "limit": kwargs.get("limit", 20),
                "concurrency": kwargs.get("concurrency", 4),
            }
            token = _ROUND.set(row)
            try:
                result = await original_round(*args, **kwargs)
                row.update(
                    processed=result.processed,
                    deferred=result.deferred,
                    skipped=result.skipped,
                    next_owner=str(result.next_owner),
                )
                return result
            except BaseException as error:
                row["error_type"] = type(error).__name__
                raise
            finally:
                row["finished_at"] = time()
                _ROUND.reset(token)
                self.spans.record(row)

        def observed(original: Callable[..., Any], name: str) -> Callable[..., Any]:
            async def call(*args: Any, **kwargs: Any) -> Any:
                with phase(name):
                    result = await original(*args, **kwargs)
                    span = _SPAN.get()
                    if name == "snapshot" and span is not None and result.state is not None:
                        span["snapshot"] = {
                            key: result.state.get(key)
                            for key in (
                                "cursor",
                                "boundary_cursor",
                                "captured_watermark",
                                "replay_pending",
                                "due_at",
                            )
                        }
                    return result

            return call

        patch(service, "asyncio", AsyncioProxy())
        patch(service, "user_session", session)
        patch(service, "scan_session_bypassing_rls", scan)
        patch(service, "run_risk_monitor_round", round_call)

        async def rolling_scan(*args: Any, **kwargs: Any) -> Any:
            if not self.window.active():
                self.setup_rounds += 1
                return await original_candidates(*args, **kwargs)
            self.rounds += 1
            row: dict[str, Any] = {
                "event": "ROLLING_TURN",
                "round": self.rounds,
                "started_at": time(),
                "after_owner": str(kwargs.get("after_owner")),
                "limit": kwargs["limit"],
                "concurrency": runtime.MONITOR_CONCURRENCY,
                "excluded": [str(owner) for owner in kwargs.get("excluded", ())],
            }
            token = _ROUND.set(row)
            try:
                result = await original_candidates(*args, **kwargs)
                # This is also validated against the real SQL selection by ScanProxy.
                if "selected" not in row:
                    raise RuntimeError("rolling selection trace incomplete")
                self.selection = {str(candidate.user_id): row["round"] for candidate in result}
                return result
            except BaseException as error:
                row["error_type"] = type(error).__name__
                raise
            finally:
                row["finished_at"] = time()
                _ROUND.reset(token)
                self.spans.record(row)

        async def rolling_evaluate(engine: Any, owner: Any) -> Any:
            if not self.window.active() and str(owner) not in self.selection:
                return await original_evaluate(engine, owner)
            turn = self.selection.pop(str(owner), None)
            if turn is None:
                raise RuntimeError("rolling owner trace missing selection")
            token = _ROUND.set({"round": turn})
            # One-slot local observer context only; runtime already admitted this task.
            try:
                async with Semaphore(1):
                    result = await original_evaluate(engine, owner)
                    span = _SPAN.get()
                    assert span is not None
                    span["scheduler"] = "rolling"
                    span["outcome"] = result
                    return result
            finally:
                _ROUND.reset(token)

        patch(runtime, "_scan_monitor_candidates", rolling_scan)
        patch(runtime, "_evaluate_monitor_owner", rolling_evaluate)
        for module, name, label in (
            (service, "lock_risk_owner", "owner_lock"),
            (service, "read_monitor_snapshot", "snapshot"),
            (service, "initialize_monitor", "initialize"),
            (service, "replay_monitor", "replay"),
            (monitor, "lock_risk_owner", "reentrant_owner_lock"),
            (monitor, "persist_evaluation", "persist"),
            (monitor, "_save_cursor", "cursor_persist"),
        ):
            patch(module, name, observed(vars(module)[name], label))
        try:
            yield
        finally:
            for namespace, name, original in reversed(patches):
                namespace[name] = original

    @asynccontextmanager
    async def observe(self) -> AsyncIterator[asyncio.Task[None]]:
        stop = asyncio.Event()

        async def flush() -> None:
            target = monotonic() + 1
            while not stop.is_set():
                with suppress(TimeoutError):
                    await asyncio.wait_for(stop.wait(), timeout=max(0, target - monotonic()))
                self.loop_delay_max = max(self.loop_delay_max, max(0, monotonic() - target))
                before = monotonic()
                self.proofs.flush()
                if self.full:
                    self.spans.flush()
                    self.window.flush()
                self.flush_seconds += monotonic() - before
                target = monotonic() + 1

        @asynccontextmanager
        async def transaction_trace() -> AsyncIterator[None]:
            if self.full:
                async with self.window.observe():
                    yield
            else:
                yield

        observer = asyncio.create_task(flush())
        try:
            async with transaction_trace():
                with self.patches():
                    yield observer
        finally:
            stop.set()
            try:
                await observer
            finally:
                self.proofs.close(
                    flush_seconds=self.flush_seconds, loop_delay_max=self.loop_delay_max
                )
                if self.full:
                    self.spans.record(
                        {
                            "event": "OBSERVER",
                            "setup_rounds": self.setup_rounds,
                            "flush_seconds": self.flush_seconds,
                            "loop_delay_max": self.loop_delay_max,
                        }
                    )
                    self.spans.close()


async def lookup_commits(engine: AsyncEngine, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    verified = set()
    for row in rows:
        if row.get("writer_xmin") is not None and row.get("transaction_xid") is not None:
            xid = int(row["writer_xmin"])
            if xid == int(row["transaction_xid"]) & 0xFFFFFFFF:
                verified.add(str(xid))
    times = {}
    if verified:
        async with engine.connect() as connection:
            result = await connection.execute(
                text("""SELECT x,pg_xact_commit_timestamp(x::xid) AS committed
              FROM unnest(CAST(:xids AS text[])) AS x"""),
                {"xids": sorted(verified)},
            )
            times = {r.x: r.committed for r in result}
    result_rows = []
    for row in rows:
        writer = row.get("writer_xmin")
        same_writer = (
            writer is not None
            and row.get("transaction_xid") is not None
            and int(writer) == int(row["transaction_xid"]) & 0xFFFFFFFF
        )
        committed = times.get(str(writer)) if same_writer else None
        result_rows.append(
            {
                **row,
                "status": "VERIFIED" if committed is not None else "UNKNOWN",
                "server_committed_at": committed.isoformat() if committed else None,
                "lookup_observed_at": time(),
            }
        )
    return result_rows


async def collect_commits(engine: AsyncEngine, output: Path, stop: asyncio.Event) -> None:
    offsets: dict[Path, int] = {}
    with (output / "commit-times.jsonl").open("x") as stream:
        while True:
            batch = []
            for path in sorted(output.glob("*.commit-proofs.jsonl")):
                with path.open() as source:
                    source.seek(offsets.get(path, 0))
                    while True:
                        position = source.tell()
                        line = source.readline()
                        if not line or not line.endswith("\n"):
                            source.seek(position)
                            break
                        row = json.loads(line)
                        if row.get("event") == "COMMIT_PROOF":
                            batch.append(row)
                    offsets[path] = source.tell()
            for index in range(0, len(batch), 500):
                for row in await lookup_commits(engine, batch[index : index + 500]):
                    stream.write(json.dumps(row, default=str) + "\n")
            stream.flush()
            if stop.is_set():
                return
            with suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=1)


@contextmanager
def rolling_inventory(metrics: Path) -> Iterator[None]:
    """Bounded counters for the real scheduler; no per-owner retained history or SQL."""
    original_scan = vars(runtime)["_scan_monitor_candidates"]
    original_evaluate = vars(runtime)["_evaluate_monitor_owner"]
    counts: dict[str, Any] = {
        "scheduler": "NC-F19-19 bounded rolling",
        "scan_calls": 0,
        "selected": 0,
        "max_selected": 0,
        "max_inflight": 0,
        "processed": 0,
        "deferred": 0,
        "skipped": 0,
        "cancelled": 0,
        "failed": 0,
    }
    active: set[Any] = set()

    async def scan(*args: Any, **kwargs: Any) -> Any:
        counts["scan_calls"] += 1
        limit = kwargs["limit"]
        excluded = kwargs.get("excluded", ())
        if limit + len(excluded) != runtime.MONITOR_CONCURRENCY:
            raise RuntimeError("rolling scan slot inventory mismatch")
        rows = await original_scan(*args, **kwargs)
        identities = [r.user_id for r in rows]
        if (
            len(rows) > limit
            or len(set(identities)) != len(rows)
            or set(identities) & set(excluded)
        ):
            raise RuntimeError("rolling selection inventory mismatch")
        counts["selected"] += len(rows)
        counts["max_selected"] = max(counts["max_selected"], len(rows))
        return rows

    async def evaluate(engine: Any, owner: Any) -> Any:
        if owner in active:
            raise RuntimeError("duplicate rolling owner admission")
        active.add(owner)
        counts["max_inflight"] = max(counts["max_inflight"], len(active))
        try:
            if len(active) > runtime.MONITOR_CONCURRENCY:
                raise RuntimeError("rolling slot bound exceeded")
            result = await original_evaluate(engine, owner)
            counts[result] += 1
            return result
        except asyncio.CancelledError:
            counts["cancelled"] += 1
            raise
        except BaseException:
            counts["failed"] += 1
            raise
        finally:
            active.remove(owner)

    vars(runtime)["_scan_monitor_candidates"] = scan
    vars(runtime)["_evaluate_monitor_owner"] = evaluate
    try:
        yield
    finally:
        vars(runtime)["_scan_monitor_candidates"] = original_scan
        vars(runtime)["_evaluate_monitor_owner"] = original_evaluate
        counts["active_at_close"] = len(active)
        counts["closed"] = True
        metrics.with_suffix(".scheduler.json").write_text(json.dumps(counts, indent=2) + "\n")
