"""Explicit F-15 W1/W2/W3 workload harness; never collected as a normal test.

The harness uses real PostgreSQL roles and the production Paper workers.  It
publishes a deterministic BTCUSDT book, creates isolated owners/wallets, seeds
the approved baseline orders, and executes the five-command positive cycle from
validation section 6.  Short runs are smoke only and cannot close V-19.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import platform
import sys
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from contextlib import AbstractAsyncContextManager, asynccontextmanager, suppress
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import monotonic
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.order_book import BookLevel, BookState
from tiewtrade.core.orders import (
    AdmissionPolicy,
    BaseSize,
    OrderConstraints,
    OrderIntent,
    OrderOrigin,
    OrderScope,
    OrderStatus,
    OrderType,
    QuoteBudget,
    TimeInForce,
    TradingMode,
)
from tiewtrade.core.positions import ExecutionSide, PositionPair
from tiewtrade.core.realtime_prices import ObservationKind, QuoteObservation
from tiewtrade.infra.db import DatabaseRole, create_engine_for, user_session
from tiewtrade.infra.db import session as db_session
from tiewtrade.infra.db.session import market_data_session
from tiewtrade.infra.market_data.order_book_storage import (
    BookLease,
    ExecutionMetadata,
    acquire_book_writer,
    publish_input,
    renew_book_writer,
)
from tiewtrade.infra.market_data.realtime_records import FeedLease
from tiewtrade.infra.market_data.realtime_storage import (
    acquire_writer,
    read_snapshot,
    renew_writer,
    set_connected,
    write_price,
)
from tiewtrade.infra.paper_orders.dispatch import (
    OrderCommand,
    get_order_command,
    submit_cancel,
    submit_order,
)
from tiewtrade.infra.paper_orders.requests import wallet_lock
from tiewtrade.infra.paper_wallet import PaperWalletAction, admit_command, get_wallet
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot
from tiewtrade.infra.users import create_user
from tiewtrade.services.engine.manual_order import run_manual_order_round
from tiewtrade.services.engine.paper_order import matching_round_modes, run_paper_order_round
from tiewtrade.services.engine.paper_wallet import run_paper_wallet_round

PAIR = PositionPair("BTC", "USDT")
PROFILE_VERSION = "F15_W1_W2_W3_V2"
MAX_WORKER_RSS_BYTES = 1024**3
W3_DURATION_SECONDS = 4 * 60 * 60
# Observation only: do not saturate the load-generator loop with owner-scoped reads.
RESULT_POLL_SECONDS = 0.25
WORKER_RUNTIME_PIDS: dict[int, int] = {}
EXPECTED_CYCLE_LOSS = Money.of("1.197901", "USDT")
SOURCE_DOCUMENT = json.dumps(
    {
        "profile": PROFILE_VERSION,
        "pair": "BTCUSDT",
        "minimum_quantity": "0.001",
        "quantity_step": "0.001",
        "minimum_notional": "1",
        "price_tick": "0.01",
        "maximum_quantity": "1000000",
        "minimum_price": "0.01",
        "maximum_price": "1000000",
    },
    sort_keys=True,
    separators=(",", ":"),
)
CAPABILITY_VERSION = hashlib.sha256(SOURCE_DOCUMENT.encode()).hexdigest()


class AllowPaperPolicy:
    def check(self, intent: OrderIntent) -> None:
        if intent.scope.mode is not TradingMode.PAPER:
            raise AssertionError("workload attempted a non-Paper order")


@dataclass(frozen=True, slots=True)
class OwnerState:
    user_id: UUID
    wallet: PaperWalletSnapshot


@dataclass(slots=True)
class Counters:
    offered: int = 0
    admitted: int = 0
    completed: int = 0
    rejected: int = 0
    fills: int = 0
    cancels: int = 0
    replays: int = 0
    cycles: int = 0


@dataclass(frozen=True, slots=True)
class FaultEvent:
    offset_seconds: float
    duration_seconds: float
    kind: str


class FaultGate:
    def __init__(self) -> None:
        self.open = asyncio.Event()
        self.open.set()
        self.active = 0
        self.pause_seconds = 0.0

    async def enter(self) -> None:
        while True:
            await self.open.wait()
            if self.open.is_set():
                self.active += 1
                return

    async def leave(self) -> None:
        self.active -= 1

    async def pause(self) -> None:
        # Stop new cycles without draining those already exercising the recovery path.
        self.open.clear()

    def resume(self, elapsed: float) -> None:
        self.pause_seconds += elapsed
        self.open.set()


def save(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, default=str, indent=2) + "\n", encoding="utf-8")


def progress(*values: object) -> None:
    sys.stdout.write(" ".join(map(str, values)) + "\n")
    sys.stdout.flush()


def identity(run_id: UUID, owner: UUID, cycle: int, label: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"tiewtrade:f15-workload:{run_id}:{owner}:{cycle}:{label}")


def scope(owner: OwnerState) -> OrderScope:
    return OrderScope(
        UUID(str(owner.user_id)), UUID(str(owner.wallet.episode_id)), TradingMode.PAPER
    )


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        raise AssertionError("latency sample is empty")
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, int(len(ordered) * fraction + 0.999999) - 1))]


def constraints(kind: OrderType) -> OrderConstraints:
    return OrderConstraints(
        PAIR,
        CAPABILITY_VERSION,
        Quantity.of("0.001", "BTC"),
        Quantity.of("0.001", "BTC"),
        Money.of(1, "USDT"),
        Money.of("0.01", "USDT"),
        maximum_quantity=Quantity.of(1_000_000, "BTC"),
        minimum_price=Money.of("0.01", "USDT"),
        maximum_price=Money.of(1_000_000, "USDT"),
        supported_types=(kind,),
    )


async def bounded_map(
    values: list[Any], operation: Callable[[Any], Awaitable[Any]], *, limit: int = 20
) -> list[Any]:
    semaphore = asyncio.Semaphore(limit)

    async def bounded(value: Any) -> Any:
        async with semaphore:
            return await operation(value)

    return list(await asyncio.gather(*(bounded(value) for value in values)))


async def acquire_sources(engine: AsyncEngine) -> tuple[BookLease, FeedLease]:
    async with market_data_session(engine) as session:
        await session.execute("SELECT risk_publication_fence()")
        await session.execute(
            """UPDATE market_execution_state
            SET lease_until=clock_timestamp()-interval '1 second'
            WHERE base='BTC' AND quote='USDT'"""
        )
        await session.execute(
            "UPDATE market_price_feed SET lease_until=clock_timestamp()-interval '1 second'"
        )
        book = await acquire_book_writer(session, PAIR, uuid4())
        price = await acquire_writer(session, uuid4())
        if book is None or price is None:
            raise RuntimeError("F15_WORKLOAD_SOURCE_LEASE_UNAVAILABLE")
        price = await set_connected(session, price, True)
    return book, price


async def publish_market(
    engine: AsyncEngine,
    book_lease: BookLease,
    price_lease: FeedLease,
    *,
    rebase: bool,
    trade_id: int,
    update_price: bool = True,
    ask_quantity: Quantity | None = None,
) -> tuple[BookLease, FeedLease]:
    async with market_data_session(engine) as session:
        book_lease = await renew_book_writer(session, book_lease)
        now = (await session.execute("SELECT clock_timestamp()")).scalar_one()
        book = BookState(
            PAIR,
            book_lease.last_input_id + 1,
            book_lease.generation,
            now,
            now,
            (
                BookLevel(Money.of(99, "USDT"), Quantity.of(1_000_000, "BTC")),
                BookLevel(Money.of(1, "USDT"), Quantity.of(1_000_000, "BTC")),
            ),
            (
                BookLevel(
                    Money.of(100, "USDT"),
                    Quantity.of(1_000_000, "BTC") if ask_quantity is None else ask_quantity,
                ),
                BookLevel(Money.of(120, "USDT"), Quantity.of(1_000_000, "BTC")),
            ),
            True,
            rebase,
        )
        metadata = ExecutionMetadata(
            constraints(OrderType.MARKET),
            constraints(OrderType.LIMIT),
            now,
            SOURCE_DOCUMENT,
        )
        book_lease = await publish_input(session, book_lease, book, metadata)
        if update_price:
            price_lease = await renew_writer(session, price_lease)
            snapshot = await read_snapshot(session)
            row = next(value for value in snapshot.rows if value.base == "BTC")
            observation = QuoteObservation(
                row.source,
                "BTC",
                "USDT",
                Money.of(100, "USDT"),
                trade_id,
                now,
                now,
                ObservationKind.STREAM,
            )
            changed = await write_price(
                session,
                price_lease,
                replace(
                    row,
                    observation=observation,
                    reconciled_generation=price_lease.generation,
                    effective_readiness="READY",
                    reason=None,
                    unavailable_since=None,
                    order_ambiguous_at=None,
                ),
            )
            if not changed and trade_id == 1:
                raise RuntimeError("F15_WORKLOAD_PRICE_NOT_PUBLISHED")
    return book_lease, price_lease


async def market_publisher(
    engine: AsyncEngine,
    stop: asyncio.Event,
    stats: dict[str, Any],
) -> None:
    stats["stage"] = "acquire_sources"
    try:
        book, price = await acquire_sources(engine)
        next_due = monotonic()
        tick = 0
        while not stop.is_set():
            stats["stage"] = "waiting_for_tick"
            await asyncio.sleep(max(0, next_due - monotonic()))
            tick += 1
            before = monotonic()
            stats["stage"] = "publish_market"
            book, price = await publish_market(
                engine,
                book,
                price,
                rebase=tick == 1,
                trade_id=tick,
                update_price=tick == 1 or tick % max(1, int(stats["target_hz"])) == 0,
            )
            stats["published"] = tick
            stats["last_input_id"] = book.last_input_id
            stats["last_progress_at"] = datetime.now(UTC).isoformat()
            stats["max_publish_seconds"] = max(
                stats.get("max_publish_seconds", 0.0), monotonic() - before
            )
            next_due += 1 / float(stats["target_hz"])
    except Exception as error:
        stats["failure_type"] = type(error).__name__
        stats["failed_at"] = datetime.now(UTC).isoformat()
        raise


async def with_publisher[T](operation: Awaitable[T], publisher: asyncio.Task[None]) -> T:
    """Fail on the source error immediately and join abandoned workload tasks."""
    task = asyncio.ensure_future(operation)
    try:
        done, _ = await asyncio.wait((task, publisher), return_when=asyncio.FIRST_COMPLETED)
        if publisher in done:
            await publisher
            raise RuntimeError("F15_WORKLOAD_PUBLISHER_STOPPED_UNEXPECTEDLY")
        return await task
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def seed_owners(
    api: AsyncEngine,
    engine: AsyncEngine,
    scan: AsyncEngine,
    count: int,
) -> list[OwnerState]:
    users = [uuid4() for _ in range(count)]
    await bounded_map(users, lambda user: create_user(api, user))

    async def admit(user: UUID) -> None:
        async with user_session(api, user) as session:
            await admit_command(
                session,
                action=PaperWalletAction.CREATE,
                idempotency_key=uuid4(),
                capital_text="10000",
                expected_episode_id=None,
            )

    await bounded_map(users, admit)
    processed = 0
    while processed < count:
        result = await run_paper_wallet_round(
            engine=engine,
            scan_engine=scan,
            worker=f"f15-workload-wallet-{processed}",
        )
        processed += result.processed
        if result.processed == 0:
            raise RuntimeError("F15_WORKLOAD_WALLET_PROGRESS_STOPPED")

    async def snapshot(user: UUID) -> OwnerState:
        async with user_session(api, user) as session:
            wallet = await get_wallet(session)
        if wallet is None or wallet.balance != Money.of(10_000, "USDT"):
            raise RuntimeError("F15_WORKLOAD_WALLET_INVALID")
        return OwnerState(user, wallet)

    return list(await bounded_map(users, snapshot))


def publish_runtime_pid(metrics_path: Path) -> None:
    """Expose a complete PID atomically, including when a producer write fails."""
    pid_file = metrics_path.with_suffix(".pid")
    pending_pid = pid_file.with_suffix(".pid.tmp")
    pending_pid.write_text(str(os.getpid()), encoding="ascii")
    pending_pid.replace(pid_file)


async def wait_runtime_pid(
    process: asyncio.subprocess.Process, metrics_path: Path, *, timeout_seconds: float = 10
) -> int:
    """Read readiness atomically; bind-mount metadata may precede file visibility."""
    async with asyncio.timeout(timeout_seconds):
        while True:
            if process.returncode is not None:
                raise RuntimeError("F15_WORKLOAD_WORKER_EXITED_BEFORE_READY")
            try:
                pid = int(metrics_path.with_suffix(".pid").read_text())
            except (FileNotFoundError, ValueError):
                await asyncio.sleep(0.01)
                continue
            if pid <= 0:
                raise RuntimeError("F15_WORKLOAD_WORKER_PID_INVALID")
            return pid


async def run_worker_process(
    name: str,
    stop_path: Path,
    metrics_path: Path,
    *,
    policy: AdmissionPolicy | None = None,
    manual_intake: bool = False,
    round_limit: int = 20,
    claim_limit: int | None = None,
    prefer_same_pair: bool = False,
    alternate_admission: bool = False,
    source_resumption: bool = False,
) -> None:
    modes = matching_round_modes(
        prefer_same_pair=prefer_same_pair, alternate_admission=alternate_admission
    )
    if type(round_limit) is not int or not 1 <= round_limit <= 20:
        raise ValueError("bounded worker round required")
    if claim_limit is not None and (
        type(claim_limit) is not int or not 1 <= claim_limit <= round_limit
    ):
        raise ValueError("bounded worker claim budget required")
    publish_runtime_pid(metrics_path)
    engine = create_engine_for(DatabaseRole.ENGINE)
    scan = create_engine_for(DatabaseRole.ENGINE_SCAN)
    original_begin = db_session._begin
    samples_path = metrics_path.with_suffix(".latencies")
    samples = samples_path.open("w", encoding="utf-8")

    @event.listens_for(engine.sync_engine, "before_cursor_execute")
    def mark_processing(
        connection: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        if "SELECT c.*,r.state AS result_state FROM paper_order_commands c" in statement:
            connection.info["f15_processing"] = True

    @asynccontextmanager
    async def measured_begin(
        engine: AsyncEngine, *, cleanup_seconds: float | None = None
    ) -> AsyncIterator[AsyncConnection]:
        started = monotonic()
        processing = False
        try:
            async with original_begin(engine, cleanup_seconds=cleanup_seconds) as connection:
                info = connection.info
                try:
                    yield connection
                finally:
                    processing = bool(info.pop("f15_processing", False))
        finally:
            if processing:
                finished = monotonic()
                samples.write(
                    json.dumps(
                        {"started": started, "finished": finished, "seconds": finished - started}
                    )
                    + "\n"
                )

    db_session._begin = measured_begin
    try:
        policy = AllowPaperPolicy() if policy is None else policy
        while not stop_path.exists():
            if manual_intake:
                await run_manual_order_round(
                    engine=engine,
                    scan_engine=scan,
                    worker=name,
                    policy=policy,
                    limit=round_limit,
                    claim_limit=claim_limit,
                )
            prefer, admission_first = next(modes)
            await run_paper_order_round(
                engine=engine,
                scan_engine=scan,
                worker=name,
                policy=policy,
                limit=round_limit,
                claim_limit=claim_limit,
                prefer_same_pair=prefer,
                admission_first=admission_first,
                source_resumption=source_resumption,
            )
            # Match services/engine/paper_order_main.py, including rounds with stale candidates.
            await asyncio.sleep(0.02)
    finally:
        db_session._begin = original_begin
        samples.close()
        # Materialize only after measurement stops; sample storage stays bounded during W3.
        records = [json.loads(value) for value in samples_path.read_text().splitlines()]
        save(
            metrics_path,
            {
                "transaction_seconds": [value["seconds"] for value in records],
                "transaction_samples": records,
            },
        )
        await engine.dispose()
        await scan.dispose()


def paper_worker_environment() -> dict[str, str]:
    allowed = {"TIEWTRADE_DATABASE_URL_ENGINE", "TIEWTRADE_DATABASE_URL_ENGINE_SCAN"}
    return {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("TIEWTRADE_") or key in allowed
    }


async def start_worker_processes(
    count: int, output: Path, *, group: str = "worker"
) -> tuple[list[asyncio.subprocess.Process], Path, list[Path]]:
    stop_path = output / f"{group}.stop"
    metrics_paths = [output / f"{group}-{number}.json" for number in range(count)]
    processes = [
        await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "tests.infra.execution_market.profile_workload",
            "--worker-only",
            "--worker-name",
            f"f15-workload-{group}-{number}",
            "--worker-stop",
            str(stop_path),
            "--worker-metrics",
            str(metrics_paths[number]),
            env=paper_worker_environment(),
        )
        for number in range(count)
    ]
    try:
        for process, metrics in zip(processes, metrics_paths, strict=True):
            WORKER_RUNTIME_PIDS[process.pid] = await wait_runtime_pid(process, metrics)
    except BaseException:
        await stop_worker_processes(processes, stop_path)
        raise
    return processes, stop_path, metrics_paths


async def economic_snapshot(
    engine: AsyncEngine, owners: list[OwnerState]
) -> list[dict[str, int | str]]:
    async def one(owner: OwnerState) -> dict[str, int | str]:
        async with user_session(engine, owner.user_id, role=DatabaseRole.ENGINE) as session:
            # Use the same owner lock as financial writers so the reader's ledger
            # balance and the event counts describe one economic state.
            await wallet_lock(session)
            wallet = await get_wallet(session)
            if wallet is None or wallet.episode_id != owner.wallet.episode_id:
                raise RuntimeError("F15_ECONOMIC_SNAPSHOT_EPISODE_CHANGED")
            row = (
                (
                    await session.execute(
                        """SELECT
                    (SELECT count(*) FROM paper_order_events
                      WHERE episode_id=:episode AND event_kind='FILL') AS fills,
                    (SELECT count(*) FROM paper_wallet_ledger
                      WHERE episode_id=:episode) AS ledger_rows,
                    (SELECT count(*) FROM paper_position_events
                      WHERE episode_id=:episode) AS position_events""",
                        {"episode": owner.wallet.episode_id},
                    )
                )
                .mappings()
                .one()
            )
        return {
            "fills": integer(row["fills"]),
            "ledger_rows": integer(row["ledger_rows"]),
            "position_events": integer(row["position_events"]),
            "balance": wallet.balance.as_parts()["amount"],
        }

    return list(await bounded_map(owners, one))


async def publish_overflow(engine: AsyncEngine, *, inputs: int = 4097) -> int:
    book, price = await acquire_sources(engine)
    for number in range(1, inputs + 1):
        book, price = await publish_market(
            engine,
            book,
            price,
            rebase=number == 1,
            trade_id=number,
            update_price=number == 1,
        )
        if number % 256 == 0:
            progress("overflow-inputs", number, "/", inputs)
    return int(book.last_input_id)


async def wait_for_input_recovery(
    engine: AsyncEngine, owners: list[OwnerState], expected_input_id: int
) -> None:
    async def recovered(owner: OwnerState) -> bool:
        async with user_session(engine, owner.user_id, role=DatabaseRole.ENGINE) as session:
            row = (
                await session.execute(
                    """SELECT a.availability,coalesce(max(k.input_id),0) AS input_id
                    FROM paper_order_activity a
                    LEFT JOIN paper_execution_input_keys k ON k.episode_id=a.episode_id
                    WHERE a.episode_id=:episode GROUP BY a.availability""",
                    {"episode": owner.wallet.episode_id},
                )
            ).one()
        return bool(row.availability == "READY" and row.input_id >= expected_input_id)

    async with asyncio.timeout(60):
        while True:
            if all(await bounded_map(owners, recovered)):
                return
            await asyncio.sleep(0.05)


def load_fault_schedule(path: Path) -> tuple[list[FaultEvent], int, str]:
    raw = path.read_bytes()
    document = json.loads(raw)
    events = [
        FaultEvent(
            float(item["offset_seconds"]),
            float(item["duration_seconds"]),
            str(item["kind"]),
        )
        for item in document["events"]
    ]
    if any(
        event.offset_seconds <= 0
        or event.duration_seconds < 0
        or event.kind not in {"WORKER_RESTART", "CONNECTION_CHURN", "REDIS_OUTAGE"}
        for event in events
    ):
        raise ValueError("invalid W3 fault schedule")
    if events != sorted(events, key=lambda event: event.offset_seconds):
        raise ValueError("W3 fault schedule must be ordered")
    cycles_per_owner = int(document["cycles_per_owner"])
    if cycles_per_owner <= 0:
        raise ValueError("invalid W3 cycle count")
    return events, cycles_per_owner, hashlib.sha256(raw).hexdigest()


async def docker_container(action: str, container: str) -> None:
    process = await asyncio.create_subprocess_exec(
        "docker",
        action,
        container,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()
    if process.returncode != 0:
        raise RuntimeError(f"F15_W3_REDIS_{action.upper()}_FAILED:{stderr.decode().strip()}")


async def run_fault_schedule(
    events: list[FaultEvent],
    gate: FaultGate,
    *,
    redis_container: str,
    restart_workers: Callable[[], Awaitable[None]],
    churn_connections: Callable[[], Awaitable[None]],
    observations: list[dict[str, object]],
    on_transition: Callable[[dict[str, object]], None] | None = None,
    recover: Callable[[dict[str, object]], Awaitable[None]] | None = None,
) -> None:
    started = monotonic()
    for fault in events:
        await asyncio.sleep(max(0, started + fault.offset_seconds - monotonic()))
        await gate.pause()
        active_at_fault = gate.active
        fault_started = monotonic()
        fault_started_at = datetime.now(UTC)
        observation: dict[str, object] = {
            "kind": fault.kind,
            "started_at": fault_started_at.isoformat(),
            "started": fault_started,
            "status": "STARTED",
            "scheduled_offset_seconds": fault.offset_seconds,
            "scheduled_duration_seconds": fault.duration_seconds,
            "active_cycles_at_fault": active_at_fault,
        }
        if on_transition is not None:
            observations.append(observation)
            on_transition(observation)
        progress("fault", fault.kind, "started")
        try:
            if fault.kind == "WORKER_RESTART":
                await restart_workers()
            elif fault.kind == "CONNECTION_CHURN":
                await churn_connections()
            else:
                await docker_container("pause", redis_container)
            await asyncio.sleep(fault.duration_seconds)
            if fault.kind == "REDIS_OUTAGE":
                await docker_container("unpause", redis_container)
            observation.update(
                ended_at=datetime.now(UTC).isoformat(),
                restored=monotonic(),
                actual_duration_seconds=monotonic() - fault_started,
                status="RESTORED" if recover is not None else "RECOVERED",
            )
            if on_transition is None:
                observations.append(observation)
            else:
                on_transition(observation)
        except BaseException as error:
            if on_transition is not None:
                observation.update(status="FAILED", error_type=type(error).__name__)
                on_transition(observation)
            if fault.kind == "REDIS_OUTAGE":
                with suppress(Exception):
                    await docker_container("unpause", redis_container)
            raise
        finally:
            gate.resume(monotonic() - fault_started)
        # Restoration ends the fault window; recovery must not hold the gate closed.
        if recover is not None:
            await recover(observation)
            observation.update(
                recovered_at=datetime.now(UTC).isoformat(),
                recovered=monotonic(),
                status="RECOVERED",
            )
            if on_transition is not None:
                on_transition(observation)


async def stop_worker_processes(
    processes: list[asyncio.subprocess.Process], stop_path: Path
) -> None:
    stop_path.touch()
    try:
        async with asyncio.timeout(10):
            await asyncio.gather(*(process.wait() for process in processes))
    except TimeoutError:
        for process in processes:
            if process.returncode is None:
                process.terminate()
        await asyncio.gather(*(process.wait() for process in processes))


def mac_process_sample(output: str, pids: list[int]) -> list[dict[str, int | float]]:
    rows: list[dict[str, int | float]] = []
    for line in output.splitlines():
        pid, cpu, rss = line.split()
        days, separator, clock = cpu.rpartition("-")
        parts = list(map(float, (clock if separator else cpu).split(":")))
        seconds = 0.0
        for part in parts:
            seconds = seconds * 60 + part
        if separator:
            seconds += int(days) * 86400
        rows.append({"Id": int(pid), "CPU": seconds, "WorkingSet64": int(rss) * 1024})
    if {int(row["Id"]) for row in rows} != set(pids):
        raise RuntimeError("F15_RESOURCE_PROCESS_SAMPLE_INCOMPLETE")
    return rows


async def resource_sampler(
    migrator: AsyncEngine,
    source: AsyncEngine,
    processes: list[asyncio.subprocess.Process],
    process_lock: asyncio.Lock,
    stop: asyncio.Event,
    samples: list[dict[str, object]],
    evidence_path: Path | None = None,
) -> None:
    while not stop.is_set():
        async with process_lock:
            # Windows venv launchers have a different PID from the Python runtime doing the work.
            pids = [
                os.getpid(),
                *(
                    WORKER_RUNTIME_PIDS[process.pid]
                    for process in processes
                    if process.returncode is None
                ),
            ]
            if sys.platform == "win32":
                command = (
                    f"Get-Process -Id {','.join(map(str, pids))} | "
                    "Select-Object Id,CPU,WorkingSet64 | ConvertTo-Json -Compress"
                )
                shell = await asyncio.create_subprocess_exec(
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await shell.communicate()
                if shell.returncode != 0:
                    raise RuntimeError(
                        f"F15_RESOURCE_PROCESS_SAMPLE_FAILED:{stderr.decode().strip()}"
                    )
                process_rows = json.loads(stdout.decode())
                if isinstance(process_rows, dict):
                    process_rows = [process_rows]
            elif sys.platform == "darwin":
                shell = await asyncio.create_subprocess_exec(
                    "ps",
                    "-p",
                    ",".join(map(str, pids)),
                    "-o",
                    "pid=,time=,rss=",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await shell.communicate()
                if shell.returncode != 0:
                    raise RuntimeError("F15_RESOURCE_PROCESS_SAMPLE_FAILED")
                process_rows = mac_process_sample(stdout.decode(), pids)
            else:
                process_rows = []
                for pid in pids:
                    fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
                    process_rows.append(
                        {
                            "Id": pid,
                            "CPU": (int(fields[11]) + int(fields[12])) / os.sysconf("SC_CLK_TCK"),
                            "WorkingSet64": int(fields[21]) * os.sysconf("SC_PAGE_SIZE"),
                        }
                    )
        async with migrator.connect() as connection:
            database = (
                (
                    await connection.exec_driver_sql(
                        """SELECT pg_database_size(current_database()) AS bytes,
                    count(*) FILTER(WHERE datname=current_database()) AS connections,
                    count(*) FILTER(WHERE datname=current_database()
                      AND wait_event_type='Lock') AS lock_waits
                    FROM pg_stat_activity"""
                    )
                )
                .mappings()
                .one()
            )
        async with market_data_session(source) as session:
            buffer_rows = (
                await session.execute("SELECT count(*) FROM market_execution_buffer")
            ).scalar_one()
        samples.append(
            {
                "at": datetime.now(UTC),
                "processes": process_rows,
                "total_rss_bytes": sum(integer(row["WorkingSet64"]) for row in process_rows),
                "database_bytes": database["bytes"],
                "connections": database["connections"],
                "lock_waits": database["lock_waits"],
                "buffer_rows": buffer_rows,
            }
        )
        with suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=5)
        if evidence_path is not None:
            save(evidence_path, samples)


def integer(value: object) -> int:
    if not isinstance(value, (int, float, str)):
        raise AssertionError("resource metric is not numeric")
    return int(value)


def summarize_resources(samples: list[dict[str, object]]) -> dict[str, object]:
    if not samples:
        raise AssertionError("resource sample is empty")
    process_rows: list[dict[str, object]] = []
    for sample in samples:
        rows = sample["processes"]
        if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
            raise AssertionError("invalid process resource sample")
        process_rows.extend(rows)
    database_sizes = [integer(sample["database_bytes"]) for sample in samples]
    per_process_peak: dict[str, int] = {}
    for row in process_rows:
        pid = str(integer(row["Id"]))
        per_process_peak[pid] = max(per_process_peak.get(pid, 0), integer(row["WorkingSet64"]))
    return {
        "samples": len(samples),
        "peak_process_rss_bytes": max(integer(row["WorkingSet64"]) for row in process_rows),
        "peak_rss_by_pid": per_process_peak,
        "peak_connections": max(integer(sample["connections"]) for sample in samples),
        "connections_start": integer(samples[0]["connections"]),
        "connections_end": integer(samples[-1]["connections"]),
        "peak_lock_waits": max(integer(sample["lock_waits"]) for sample in samples),
        "lock_waits_end": integer(samples[-1]["lock_waits"]),
        "peak_buffer_rows": max(integer(sample["buffer_rows"]) for sample in samples),
        "buffer_rows_start": integer(samples[0]["buffer_rows"]),
        "buffer_rows_end": integer(samples[-1]["buffer_rows"]),
        "database_bytes_start": database_sizes[0],
        "database_bytes_end": database_sizes[-1],
        "database_growth_bytes": database_sizes[-1] - database_sizes[0],
    }


def endurance_rss(
    samples: list[dict[str, object]],
    *,
    duration_seconds: int = W3_DURATION_SECONDS,
    measured_start: datetime | None = None,
) -> dict[str, object]:
    if duration_seconds <= 0:
        raise ValueError("positive endurance duration required")
    if len(samples) < 2:
        return {"passed": False, "reason": "insufficient samples"}
    first_at = samples[0]["at"]
    last_at = samples[-1]["at"]
    if not isinstance(first_at, datetime) or not isinstance(last_at, datetime):
        raise AssertionError("resource timestamps are invalid")
    if measured_start is not None:
        first_at = measured_start
        last_at = measured_start + timedelta(seconds=duration_seconds)
        samples = [
            sample
            for sample in samples
            if isinstance(sample["at"], datetime) and first_at <= sample["at"] <= last_at
        ]
        if len(samples) < 2:
            return {"passed": False, "reason": "insufficient measured samples"}
    observed_end = samples[-1]["at"]
    assert isinstance(observed_end, datetime)
    elapsed = (observed_end - first_at).total_seconds()
    warmup = duration_seconds / 16
    window = duration_seconds / 4
    first_window = [
        integer(sample["total_rss_bytes"])
        for sample in samples
        if isinstance(sample["at"], datetime)
        and warmup <= (sample["at"] - first_at).total_seconds() <= warmup + window
    ]
    last_window = [
        integer(sample["total_rss_bytes"])
        for sample in samples
        if isinstance(sample["at"], datetime) and (last_at - sample["at"]).total_seconds() <= window
    ]
    if elapsed < duration_seconds - warmup or not first_window or not last_window:
        return {"passed": False, "reason": "endurance windows not available"}
    first_average = sum(first_window) / len(first_window)
    last_average = sum(last_window) / len(last_window)
    growth = (last_average - first_average) / first_average
    result: dict[str, object] = {
        "duration_seconds": duration_seconds,
        "warmup_seconds": warmup,
        "window_seconds": window,
        "observed_seconds": elapsed,
        "first_stable_window_average_bytes": first_average,
        "last_window_average_bytes": last_average,
        "growth_fraction": growth,
        "passed": growth <= 0.20,
    }
    if measured_start is not None:
        result.update(
            measured_start=first_at.isoformat(),
            measured_end=last_at.isoformat(),
            first_window_samples=len(first_window),
            last_window_samples=len(last_window),
        )
    if duration_seconds == W3_DURATION_SECONDS:
        # Retain the existing F15 result contract and four-hour defaults.
        result.update(
            first_stable_hour_average_bytes=first_average,
            last_hour_average_bytes=last_average,
        )
    return result


def cycle_counts_for(
    owners: list[OwnerState],
    cycles: int,
    counts: Mapping[UUID, int] | None,
) -> dict[UUID, int]:
    expected = {owner.user_id for owner in owners}
    result = dict.fromkeys(expected, cycles) if counts is None else dict(counts)
    if set(result) != expected or any(type(n) is not int or n < 0 for n in result.values()):
        raise ValueError("complete nonnegative per-owner cycle counts required")
    return result


async def verify_global_invariants(
    engine: AsyncEngine,
    owners: list[OwnerState],
    *,
    baseline_orders: int,
    cycles_per_owner: int,
    extra_cancels: int = 0,
    extra_fills: int = 0,
    cycle_counts: Mapping[UUID, int] | None = None,
) -> dict[str, object]:
    """Check workload-wide safety facts outside owner RLS."""
    total_cycles = sum(cycle_counts_for(owners, cycles_per_owner, cycle_counts).values())
    expected_orders = len(owners) * baseline_orders + total_cycles * 3 + extra_cancels
    expected_fills = total_cycles * 2 + extra_fills
    expected_cancels = total_cycles + extra_cancels
    expected_pending_dispatch = len(owners) * baseline_orders

    async def inspect(owner: OwnerState) -> dict[str, int]:
        async with user_session(engine, owner.user_id, role=DatabaseRole.ENGINE) as session:
            row = (
                (
                    await session.execute(
                        """SELECT
                    (SELECT count(*) FROM paper_orders WHERE episode_id=:episode) AS orders,
                    (SELECT count(*) FROM paper_order_events
                      WHERE episode_id=:episode AND event_kind='FILL') AS fills,
                    (SELECT count(DISTINCT terminal->'intent'->>'order_id')
                      FROM paper_order_events e CROSS JOIN LATERAL
                        jsonb_array_elements(e.payload->'terminal_orders') terminal
                      WHERE e.episode_id=:episode AND terminal->>'status'='CANCELED') AS cancels,
                    (SELECT count(*) FROM paper_order_dispatch
                      WHERE episode_id=:episode AND state<>'TERMINAL') AS pending_dispatch,
                    (SELECT count(*) FROM paper_order_events e
                      WHERE e.episode_id=:episode AND e.event_kind='FILL'
                      AND NOT EXISTS(SELECT 1 FROM paper_execution_links l
                        WHERE l.order_event_id=e.id AND l.execution_id=e.execution_id))
                      AS unlinked_fills,
                    (SELECT count(*) FROM paper_reservations
                      WHERE episode_id=:episode
                      AND (quote_reserved<0 OR base_reserved<0)) AS invalid_reservations,
                    (SELECT count(*) FROM paper_position_projections
                      WHERE episode_id=:episode
                      AND (held_quantity<0 OR total_cost<0)) AS invalid_positions,
                    (SELECT count(*) FROM paper_order_activity
                      WHERE episode_id=:episode AND mode<>'PAPER') AS wrong_mode,
                    (SELECT s.last_input_id-coalesce(max(k.input_id),0)
                      FROM paper_order_activity a
                      JOIN market_execution_state s ON s.base='BTC' AND s.quote='USDT'
                      LEFT JOIN paper_execution_input_keys k ON k.episode_id=a.episode_id
                      WHERE a.episode_id=:episode GROUP BY s.last_input_id) AS input_lag,
                    (SELECT count(*) FROM (
                      SELECT execution_id,count(*) FROM paper_order_events
                      WHERE episode_id=:episode AND event_kind='FILL'
                      GROUP BY execution_id HAVING count(*)<>1
                    ) duplicates) AS duplicate_fill_effects""",
                        {"episode": owner.wallet.episode_id},
                    )
                )
                .mappings()
                .one()
            )
        return {key: integer(value) for key, value in row.items()}

    owner_values = await bounded_map(owners, inspect)
    values = {
        key: (
            max(value[key] for value in owner_values)
            if key == "input_lag"
            else sum(value[key] for value in owner_values)
        )
        for key in owner_values[0]
    }
    values["expected_orders"] = expected_orders
    values["expected_fills"] = expected_fills
    values["expected_cancels"] = expected_cancels
    values["expected_pending_dispatch"] = expected_pending_dispatch
    values["passed"] = (
        values["orders"] == expected_orders
        and values["fills"] == expected_fills
        and values["cancels"] == expected_cancels
        and values["pending_dispatch"] == expected_pending_dispatch
        and all(
            values[key] == 0
            for key in (
                "unlinked_fills",
                "invalid_reservations",
                "invalid_positions",
                "wrong_mode",
                "duplicate_fill_effects",
            )
        )
    )
    return values


async def wait_command(
    engine: AsyncEngine,
    owner: UUID,
    command: OrderCommand,
    *,
    timeout: float = 60,
) -> OrderCommand:
    async with asyncio.timeout(timeout):
        while True:
            async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
                current = await get_order_command(session, command.command_id)
            if current is not None and current.state != "PENDING":
                return current
            await asyncio.sleep(RESULT_POLL_SECONDS)


async def wait_status(
    engine: AsyncEngine,
    owner: UUID,
    order_id: UUID,
    expected: OrderStatus,
    *,
    timeout: float = 60,
) -> None:
    async with asyncio.timeout(timeout):
        while True:
            async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
                status = (
                    await session.execute(
                        "SELECT status FROM paper_order_projections WHERE order_id=:order",
                        {"order": order_id},
                    )
                ).scalar_one_or_none()
            if status == expected.value:
                return
            await asyncio.sleep(RESULT_POLL_SECONDS)


async def submit_new(
    engine: AsyncEngine,
    owner: OwnerState,
    intent: OrderIntent,
    expected: OrderStatus,
    counters: Counters,
    latencies: list[float],
) -> OrderCommand:
    started = monotonic()
    counters.offered += 1
    async with user_session(engine, owner.user_id, role=DatabaseRole.ENGINE) as session:
        command = await submit_order(session, wallet_id=owner.wallet.wallet_id, intent=intent)
    counters.admitted += 1
    result = await wait_command(engine, owner.user_id, command)
    if result.failure_code is not None:
        counters.rejected += 1
        raise RuntimeError(f"F15_WORKLOAD_ORDER_REJECTED:{result.failure_code}")
    await wait_status(engine, owner.user_id, intent.order_id, expected)
    counters.completed += 1
    latencies.append(monotonic() - started)
    return result


def market_buy(owner: OwnerState, run_id: UUID, cycle: int) -> OrderIntent:
    return OrderIntent(
        identity(run_id, owner.user_id, cycle, "buy-order"),
        identity(run_id, owner.user_id, cycle, "buy-key"),
        scope(owner),
        PAIR,
        OrderOrigin.MANUAL,
        ExecutionSide.BUY,
        OrderType.MARKET,
        QuoteBudget(Money.of(100, "USDT")),
    )


def limit_sell(owner: OwnerState, run_id: UUID, cycle: int) -> OrderIntent:
    return OrderIntent(
        identity(run_id, owner.user_id, cycle, "limit-order"),
        identity(run_id, owner.user_id, cycle, "limit-key"),
        scope(owner),
        PAIR,
        OrderOrigin.MANUAL,
        ExecutionSide.SELL,
        OrderType.LIMIT,
        BaseSize(Quantity.of("0.999", "BTC")),
        Money.of(110, "USDT"),
        TimeInForce.GTC,
    )


def market_sell(owner: OwnerState, run_id: UUID, cycle: int) -> OrderIntent:
    return OrderIntent(
        identity(run_id, owner.user_id, cycle, "sell-order"),
        identity(run_id, owner.user_id, cycle, "sell-key"),
        scope(owner),
        PAIR,
        OrderOrigin.MANUAL,
        ExecutionSide.SELL,
        OrderType.MARKET,
        BaseSize(Quantity.of("0.999", "BTC")),
    )


def baseline(owner: OwnerState, run_id: UUID, index: int) -> OrderIntent:
    return OrderIntent(
        identity(run_id, owner.user_id, -1, f"baseline-order-{index}"),
        identity(run_id, owner.user_id, -1, f"baseline-key-{index}"),
        scope(owner),
        PAIR,
        OrderOrigin.MANUAL,
        ExecutionSide.BUY,
        OrderType.LIMIT,
        BaseSize(Quantity.of(1, "BTC")),
        Money.of(1, "USDT"),
        TimeInForce.GTC,
    )


async def seed_baseline(
    engine: AsyncEngine,
    owners: list[OwnerState],
    run_id: UUID,
    count: int,
) -> None:
    ignored = Counters()
    latencies: list[float] = []
    for index in range(count):

        async def submit_baseline(owner: OwnerState, current: int = index) -> OrderCommand:
            return await submit_new(
                engine,
                owner,
                baseline(owner, run_id, current),
                OrderStatus.ACCEPTED,
                ignored,
                latencies,
            )

        await bounded_map(
            owners,
            submit_baseline,
        )
        progress("baseline", index + 1, "/", count)


async def cycle(
    engine: AsyncEngine,
    owner: OwnerState,
    run_id: UUID,
    number: int,
    counters: Counters,
    latencies: list[float],
) -> None:
    buy = market_buy(owner, run_id, number)
    await submit_new(engine, owner, buy, OrderStatus.FILLED, counters, latencies)
    counters.fills += 1

    resting = limit_sell(owner, run_id, number)
    await submit_new(engine, owner, resting, OrderStatus.ACCEPTED, counters, latencies)

    started = monotonic()
    counters.offered += 1
    async with user_session(engine, owner.user_id, role=DatabaseRole.ENGINE) as session:
        replay = await submit_order(session, wallet_id=owner.wallet.wallet_id, intent=resting)
    if replay.failure_code is not None or replay.state != "SUCCEEDED":
        counters.rejected += 1
        raise RuntimeError("F15_WORKLOAD_REPLAY_FAILED")
    counters.admitted += 1
    counters.completed += 1
    counters.replays += 1
    latencies.append(monotonic() - started)

    started = monotonic()
    counters.offered += 1
    async with user_session(engine, owner.user_id, role=DatabaseRole.ENGINE) as session:
        cancel = await submit_cancel(
            session,
            wallet_id=owner.wallet.wallet_id,
            episode_id=owner.wallet.episode_id,
            order_id=resting.order_id,
            idempotency_key=identity(run_id, owner.user_id, number, "cancel-key"),
        )
    counters.admitted += 1
    result = await wait_command(engine, owner.user_id, cancel)
    if result.failure_code is not None:
        counters.rejected += 1
        raise RuntimeError(f"F15_WORKLOAD_CANCEL_REJECTED:{result.failure_code}")
    await wait_status(engine, owner.user_id, resting.order_id, OrderStatus.CANCELED)
    counters.completed += 1
    counters.cancels += 1
    latencies.append(monotonic() - started)

    sell = market_sell(owner, run_id, number)
    await submit_new(engine, owner, sell, OrderStatus.FILLED, counters, latencies)
    counters.fills += 1
    counters.cycles += 1


async def run_scheduled_cycles(
    engine: AsyncEngine,
    owners: list[OwnerState],
    run_id: UUID,
    cycles_per_owner: int,
    rate: int,
    counters: Counters,
    latencies: list[float],
    gate: FaultGate | None = None,
    *,
    cycle_scope: Callable[[OwnerState, int], AbstractAsyncContextManager[None]] | None = None,
) -> float:
    started = monotonic()
    command_interval = 1 / rate
    owner_interval = len(owners) * 5 * command_interval

    async def owner_cycles(index: int, owner: OwnerState) -> None:
        first_due = started + index * 5 * command_interval
        for number in range(cycles_per_owner):
            due = first_due + number * owner_interval + (0 if gate is None else gate.pause_seconds)
            await asyncio.sleep(max(0, due - monotonic()))
            if gate is None:
                async with (
                    asyncio.timeout(60) if cycle_scope is None else cycle_scope(owner, number)
                ):
                    await cycle(engine, owner, run_id, number, counters, latencies)
            else:
                while True:
                    await gate.enter()
                    due = first_due + number * owner_interval + gate.pause_seconds
                    await asyncio.sleep(max(0, due - monotonic()))
                    if gate.open.is_set():
                        break
                    await gate.leave()
                try:
                    async with (
                        asyncio.timeout(60) if cycle_scope is None else cycle_scope(owner, number)
                    ):
                        await cycle(engine, owner, run_id, number, counters, latencies)
                finally:
                    await gate.leave()

    tasks = [asyncio.create_task(owner_cycles(index, owner)) for index, owner in enumerate(owners)]
    try:
        await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    return monotonic() - started


async def verify(
    engine: AsyncEngine,
    owners: list[OwnerState],
    *,
    baseline_orders: int,
    cycles_per_owner: int,
    extra_cancels: dict[UUID, int] | None = None,
    cycle_counts: Mapping[UUID, int] | None = None,
) -> list[dict[str, object]]:
    counts = cycle_counts_for(owners, cycles_per_owner, cycle_counts)

    async def one(owner: OwnerState) -> dict[str, object]:
        count = counts[owner.user_id]
        expected = Money.of(10_000, "USDT") - EXPECTED_CYCLE_LOSS.times(count)
        async with user_session(engine, owner.user_id, role=DatabaseRole.ENGINE) as session:
            wallet = await get_wallet(session)
            row = (
                (
                    await session.execute(
                        """SELECT
                    count(*) FILTER(WHERE status='ACCEPTED') AS accepted,
                    count(*) FILTER(WHERE status='FILLED') AS filled,
                    count(*) FILTER(WHERE status='CANCELED') AS canceled,
                    coalesce(sum(r.quote_reserved),0) AS quote_reserved,
                    coalesce(sum(r.base_reserved),0) AS base_reserved
                    FROM paper_order_projections p
                    JOIN paper_reservations r USING(order_id)
                    WHERE p.episode_id=:episode""",
                        {"episode": owner.wallet.episode_id},
                    )
                )
                .mappings()
                .one()
            )
            position = (
                (
                    await session.execute(
                        """SELECT coalesce(sum(held_quantity),0) AS held,
                    coalesce(sum(total_cost),0) AS cost
                    FROM paper_position_projections WHERE episode_id=:episode""",
                        {"episode": owner.wallet.episode_id},
                    )
                )
                .mappings()
                .one()
            )
        passed = (
            wallet is not None
            and wallet.balance == expected
            and row["accepted"] == baseline_orders
            and row["filled"] == count * 2
            and row["canceled"] == count + (extra_cancels or {}).get(owner.user_id, 0)
            and Money.of(row["quote_reserved"], "USDT") == Money.of(baseline_orders, "USDT")
            and Quantity.of(row["base_reserved"], "BTC") == Quantity.of(0, "BTC")
            and Quantity.of(position["held"], "BTC") == Quantity.of(0, "BTC")
            and Money.of(position["cost"], "USDT") == Money.of(0, "USDT")
        )
        return {
            "user_id": owner.user_id,
            "episode_id": owner.wallet.episode_id,
            "balance": None if wallet is None else wallet.balance.amount,
            "expected_balance": expected.amount,
            "accepted": row["accepted"],
            "filled": row["filled"],
            "canceled": row["canceled"],
            "quote_reserved": row["quote_reserved"],
            "base_reserved": row["base_reserved"],
            "held": position["held"],
            "cost": position["cost"],
            "passed": passed,
        }

    return list(await bounded_map(owners, one))


async def database_manifest(engine: AsyncEngine) -> dict[str, object]:
    async with engine.connect() as connection:
        settings = {}
        for key in ("server_version", "max_connections", "shared_buffers", "work_mem"):
            settings[key] = (await connection.exec_driver_sql(f"SHOW {key}")).scalar_one()
        revision = (
            await connection.exec_driver_sql("SELECT version_num FROM alembic_version")
        ).scalar_one()
    return {"alembic_revision": revision, "postgresql": settings}


async def read_baseline(
    path: Path, api: AsyncEngine, *, owners: int, baseline_orders: int
) -> list[OwnerState]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if (
        document["profile"] != PROFILE_VERSION
        or document["baseline_orders_per_owner"] != baseline_orders
        or len(document["owners"]) != owners
        or len({item["user_id"] for item in document["owners"]}) != owners
    ):
        raise ValueError("prepared baseline does not match the requested fixture")

    async def one(item: dict[str, str]) -> OwnerState:
        owner = UUID(item["user_id"])
        async with user_session(api, owner) as session:
            wallet = await get_wallet(session)
        if wallet is None or str(wallet.episode_id) != item["episode_id"]:
            raise ValueError("prepared baseline owner/episode does not match this database")
        return OwnerState(owner, wallet)

    return list(await bounded_map(document["owners"], one))


async def run(args: argparse.Namespace) -> int:
    output: Path = args.output
    output.mkdir(parents=True, exist_ok=False)
    run_id = uuid4()
    source = create_engine_for(DatabaseRole.MARKET_DATA)
    migrator = create_engine_for(DatabaseRole.MIGRATOR)
    api = create_engine_for(DatabaseRole.API)
    engine = create_engine_for(DatabaseRole.ENGINE)
    scan = create_engine_for(DatabaseRole.ENGINE_SCAN)
    stop = asyncio.Event()
    publisher_stats: dict[str, Any] = {"target_hz": 2}
    worker_failures: list[str] = []
    worker_processes: list[asyncio.subprocess.Process] = []
    worker_stop: Path | None = None
    worker_metrics: list[Path] = []
    resource_stop = asyncio.Event()
    process_lock = asyncio.Lock()
    resource_task: asyncio.Task[None] | None = None
    resource_samples: list[dict[str, object]] = []
    publisher: asyncio.Task[None] | None = None
    counters = Counters()
    latencies: list[float] = []
    fault_result: dict[str, object] | None = None
    fault_task: asyncio.Task[None] | None = None
    fault_observations: list[dict[str, object]] = []
    fault_events: list[FaultEvent] = []
    fault_schedule_digest: str | None = None
    drain_seconds = 0.0
    started_at = datetime.now(UTC)
    try:
        if args.phase in {"W3", "W3_SMOKE"}:
            if args.fault_schedule is None or not args.redis_container:
                raise ValueError("W3 requires --fault-schedule and --redis-container")
            fault_events, fixture_cycles, fault_schedule_digest = load_fault_schedule(
                args.fault_schedule
            )
            if args.cycles_per_owner != fixture_cycles:
                raise ValueError("W3 cycles-per-owner must equal the predeclared fault fixture")
        manifest = {
            "profile": PROFILE_VERSION,
            "phase": args.phase,
            "run_id": run_id,
            "started_at": started_at,
            "platform": platform.platform(),
            "python": platform.python_version(),
            "owners": args.owners,
            "baseline_orders_per_owner": args.baseline_orders,
            "cycles_per_owner": args.cycles_per_owner,
            "command_rate": args.rate,
            "workers": args.workers,
            "baseline_manifest": (
                None if args.baseline_manifest is None else str(args.baseline_manifest)
            ),
            "expected_commands": args.owners * args.cycles_per_owner * 5,
            "expected_cycles": args.owners * args.cycles_per_owner,
            "fault_schedule_digest": fault_schedule_digest,
            "fault_schedule": [asdict(event) for event in fault_events],
            "expected_fixture_digest": hashlib.sha256(
                f"{PROFILE_VERSION}:{args.owners}:{args.baseline_orders}:"
                f"{args.cycles_per_owner}:{args.rate}".encode()
            ).hexdigest(),
            "database": await database_manifest(migrator),
        }
        save(output / "manifest.json", manifest)
        if args.baseline_manifest is None:
            owners = await seed_owners(api, engine, scan, args.owners)
        else:
            owners = await read_baseline(
                args.baseline_manifest,
                api,
                owners=args.owners,
                baseline_orders=args.baseline_orders,
            )
            initial = await verify(
                engine, owners, baseline_orders=args.baseline_orders, cycles_per_owner=0
            )
            if not all(row["passed"] for row in initial):
                raise AssertionError("prepared baseline economics are not pristine")
        publisher = asyncio.create_task(market_publisher(source, stop, publisher_stats))
        async with asyncio.timeout(5):
            while publisher_stats.get("published", 0) < 2:
                if publisher.done():
                    await publisher
                    raise RuntimeError("F15_WORKLOAD_PUBLISHER_STOPPED_UNEXPECTEDLY")
                await asyncio.sleep(0.01)
        worker_processes, worker_stop, worker_metrics = await start_worker_processes(
            args.workers, output
        )
        if args.baseline_manifest is None:
            await with_publisher(
                seed_baseline(engine, owners, run_id, args.baseline_orders), publisher
            )
        if args.phase == "BASELINE":
            stop.set()
            await publisher
            publisher = None
            await stop_worker_processes(worker_processes, worker_stop)
            observations = await verify(
                engine, owners, baseline_orders=args.baseline_orders, cycles_per_owner=0
            )
            invariants = await verify_global_invariants(
                engine, owners, baseline_orders=args.baseline_orders, cycles_per_owner=0
            )
            if not all(row["passed"] for row in observations) or not invariants["passed"]:
                raise AssertionError("baseline fixture verification failed")
            save(
                output / "baseline.json",
                {
                    "profile": PROFILE_VERSION,
                    "baseline_orders_per_owner": args.baseline_orders,
                    "owners": [
                        {"user_id": str(owner.user_id), "episode_id": str(owner.wallet.episode_id)}
                        for owner in owners
                    ],
                },
            )
            save(output / "result.json", {"status": "PREPARED", "acceptance_result": False})
            progress("baseline verified; no measured workload was run")
            return 0
        if args.phase == "W2_OVERFLOW":
            stop.set()
            await publisher
            publisher = None
            await stop_worker_processes(worker_processes, worker_stop)
            before_fault = await economic_snapshot(engine, owners)
            fault_started = monotonic()
            recovered_input_id = await publish_overflow(source)
            worker_processes, worker_stop, recovery_metrics = await start_worker_processes(
                args.workers, output, group="recovery-worker"
            )
            worker_metrics.extend(recovery_metrics)
            resource_task = asyncio.create_task(
                resource_sampler(
                    migrator,
                    source,
                    worker_processes,
                    process_lock,
                    resource_stop,
                    resource_samples,
                )
            )
            await wait_for_input_recovery(engine, owners, recovered_input_id)
            elapsed = monotonic() - fault_started
            after_fault = await economic_snapshot(engine, owners)
            fault_result = {
                "kind": "BOOK_BUFFER_OVERFLOW",
                "published_inputs": 4097,
                "recovered_input_id": recovered_input_id,
                "drain_seconds": elapsed,
                "before": before_fault,
                "after": after_fault,
                "no_economic_change": before_fault == after_fault,
            }
            measured_inputs = 4097
        else:
            publisher_stats["target_hz"] = 10
            await asyncio.sleep(0.5)
            measured_input_start = int(publisher_stats.get("published", 0))
            progress("workload", args.phase, "started")
            resource_task = asyncio.create_task(
                resource_sampler(
                    migrator,
                    source,
                    worker_processes,
                    process_lock,
                    resource_stop,
                    resource_samples,
                )
            )
            gate = FaultGate() if args.phase in {"W3", "W3_SMOKE"} else None

            async def restart_workers() -> None:
                nonlocal worker_stop
                if worker_stop is None:
                    raise AssertionError("worker stop path is absent")
                async with process_lock:
                    await stop_worker_processes(worker_processes, worker_stop)
                    processes, worker_stop, metrics = await start_worker_processes(
                        args.workers,
                        output,
                        group=f"restart-{len(fault_observations)}",
                    )
                    worker_processes[:] = processes
                    worker_metrics.extend(metrics)

            async def churn_connections() -> None:
                await asyncio.gather(
                    engine.dispose(), scan.dispose(), api.dispose(), source.dispose()
                )

            if gate is not None:
                fault_task = asyncio.create_task(
                    run_fault_schedule(
                        fault_events,
                        gate,
                        redis_container=args.redis_container,
                        restart_workers=restart_workers,
                        churn_connections=churn_connections,
                        observations=fault_observations,
                    )
                )
            measured_started = monotonic()
            elapsed = await with_publisher(
                run_scheduled_cycles(
                    engine,
                    owners,
                    run_id,
                    args.cycles_per_owner,
                    args.rate,
                    counters,
                    latencies,
                    gate,
                ),
                publisher,
            )
            if fault_task is not None:
                await with_publisher(fault_task, publisher)
            if args.phase == "W3":
                # Keep feed, workers and resource sampling alive for the full acceptance window.
                await with_publisher(
                    asyncio.sleep(max(0, measured_started + W3_DURATION_SECONDS - monotonic())),
                    publisher,
                )
                elapsed = monotonic() - measured_started
            # Drain the measured watermark with dependencies still available. Stopping
            # the feed first makes its final book stale before all owners can recover.
            recovery_input_id = int(publisher_stats.get("last_input_id", 0))
            measured_inputs = int(publisher_stats.get("published", 0)) - measured_input_start
            drain_started = monotonic()
            await with_publisher(
                wait_for_input_recovery(engine, owners, recovery_input_id), publisher
            )
            drain_seconds = monotonic() - drain_started
            stop.set()
            await publisher
            publisher = None
        resource_stop.set()
        await resource_task
        await stop_worker_processes(worker_processes, worker_stop)
        observations = await verify(
            engine,
            owners,
            baseline_orders=args.baseline_orders,
            cycles_per_owner=args.cycles_per_owner,
        )
        invariants = await verify_global_invariants(
            engine,
            owners,
            baseline_orders=args.baseline_orders,
            cycles_per_owner=args.cycles_per_owner,
        )
        expected_commands = args.owners * args.cycles_per_owner * 5
        expected_cycles = args.owners * args.cycles_per_owner
        target_seconds = expected_commands / args.rate
        required_book_inputs = int((elapsed if args.phase == "W3_SMOKE" else target_seconds) * 10)
        engine_latencies = [
            float(value)
            for path in worker_metrics
            for value in json.loads(path.read_text(encoding="utf-8"))["transaction_seconds"]
        ]
        p95 = percentile(engine_latencies, 0.95)
        p99 = percentile(engine_latencies, 0.99)
        resources = summarize_resources(resource_samples)
        rss_endurance = endurance_rss(resource_samples) if args.phase == "W3" else None
        resource_passed = (
            integer(resources["peak_process_rss_bytes"]) <= MAX_WORKER_RSS_BYTES
            and integer(resources["lock_waits_end"]) == 0
            and integer(invariants["input_lag"]) <= 20
            and integer(resources["connections_end"]) <= integer(resources["connections_start"]) + 2
            and (rss_endurance is None or rss_endurance["passed"] is True)
        )
        worker_failures.extend(
            f"worker-{number}-exited:{process.returncode}"
            for number, process in enumerate(worker_processes)
            if process.returncode not in (None, 0)
        )
        passed = (
            counters.offered == expected_commands
            and counters.admitted == expected_commands
            and counters.completed == expected_commands
            and counters.rejected == 0
            and counters.cycles == expected_cycles
            and counters.fills == expected_cycles * 2
            and counters.cancels == expected_cycles
            and counters.replays == expected_cycles
            and (args.phase != "W3" or elapsed >= W3_DURATION_SECONDS)
            and elapsed
            <= target_seconds + sum(event.duration_seconds for event in fault_events) + 60
            and (args.phase == "W2_OVERFLOW" or measured_inputs >= required_book_inputs)
            and p95 <= 0.250
            and p99 <= 1.0
            and not worker_failures
            and all(value["passed"] for value in observations)
            and invariants["passed"]
            and resource_passed
            and drain_seconds <= 60
            and (
                fault_result is None
                or (fault_result["no_economic_change"] is True and elapsed <= 60)
            )
        )
        result = {
            "phase": args.phase,
            "status": "PASSED" if passed else "FAILED",
            "smoke_only": args.phase in {"SMOKE", "W3_SMOKE"},
            "elapsed_seconds": elapsed,
            "target_seconds": target_seconds,
            "drain_seconds": drain_seconds,
            "counters": asdict(counters),
            "engine_transaction_seconds": {
                "p95": p95,
                "p99": p99,
                "max": max(engine_latencies),
                "samples": len(engine_latencies),
            },
            "end_to_end_command_seconds": {
                "p95": None if not latencies else percentile(latencies, 0.95),
                "p99": None if not latencies else percentile(latencies, 0.99),
                "max": None if not latencies else max(latencies),
            },
            "publisher": publisher_stats,
            "measured_book_inputs": measured_inputs,
            "required_book_inputs": required_book_inputs,
            "resources": resources,
            "resource_assertions_passed": resource_passed,
            "global_invariants": invariants,
            "fault": fault_result,
            "fault_observations": fault_observations,
            "endurance_rss": rss_endurance,
            "worker_failures": worker_failures,
            "owners": observations,
        }
        save(output / "resources.json", resource_samples)
        save(output / "result.json", result)
        progress(json.dumps({key: value for key, value in result.items() if key != "owners"}))
        return 0 if passed else 1
    except Exception as error:
        save(output / "resources.json", resource_samples)
        save(
            output / "failure.json",
            {
                "failed_at": datetime.now(UTC),
                "error_type": type(error).__name__,
                "error": str(error),
                "publisher": publisher_stats,
                "worker_failures": worker_failures,
                "counters": asdict(counters),
            },
        )
        raise
    finally:
        stop.set()
        resource_stop.set()
        if resource_task is not None and not resource_task.done():
            resource_task.cancel()
            await asyncio.gather(resource_task, return_exceptions=True)
        if fault_task is not None and not fault_task.done():
            fault_task.cancel()
            await asyncio.gather(fault_task, return_exceptions=True)
        if publisher is not None:
            publisher.cancel()
        if publisher is not None:
            await asyncio.gather(publisher, return_exceptions=True)
        if (
            worker_processes
            and worker_stop is not None
            and any(process.returncode is None for process in worker_processes)
        ):
            await stop_worker_processes(worker_processes, worker_stop)
        for connection in (source, migrator, api, engine, scan):
            await connection.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker-only", action="store_true")
    parser.add_argument("--worker-name")
    parser.add_argument("--worker-stop", type=Path)
    parser.add_argument("--worker-metrics", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--phase", choices=("BASELINE", "SMOKE", "W1", "W2", "W2_OVERFLOW", "W3", "W3_SMOKE")
    )
    parser.add_argument("--baseline-manifest", type=Path)
    parser.add_argument("--owners", type=int)
    parser.add_argument("--baseline-orders", type=int, default=20)
    parser.add_argument("--cycles-per-owner", type=int)
    parser.add_argument("--rate", type=int)
    parser.add_argument("--workers", type=int, default=10)
    parser.add_argument("--fault-schedule", type=Path)
    parser.add_argument("--redis-container")
    parsed = parser.parse_args()
    if parsed.worker_only:
        if not parsed.worker_name or parsed.worker_stop is None or parsed.worker_metrics is None:
            parser.error("worker-only mode requires name, stop and metrics paths")
        raise SystemExit(
            asyncio.run(
                run_worker_process(parsed.worker_name, parsed.worker_stop, parsed.worker_metrics)
            )
        )
    if (
        parsed.output is None
        or parsed.phase is None
        or parsed.owners is None
        or parsed.cycles_per_owner is None
        or parsed.rate is None
    ):
        parser.error("output, phase, owners, cycles-per-owner and rate are required")
    if min(parsed.owners, parsed.baseline_orders, parsed.rate, parsed.workers) <= 0:
        parser.error("owners, baseline-orders, rate and workers must be positive")
    if parsed.cycles_per_owner < 0 or (
        parsed.phase not in {"BASELINE", "W2_OVERFLOW"} and parsed.cycles_per_owner == 0
    ):
        parser.error("cycles-per-owner must be positive outside W2_OVERFLOW")
    if parsed.phase == "BASELINE" and parsed.cycles_per_owner != 0:
        parser.error("BASELINE prepares orders only and requires zero measured cycles")
    raise SystemExit(asyncio.run(run(parsed)))
