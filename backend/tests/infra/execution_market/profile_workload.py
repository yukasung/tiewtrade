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
from contextlib import (
    AbstractAsyncContextManager,
    AbstractContextManager,
    AsyncExitStack,
    asynccontextmanager,
    nullcontext,
    suppress,
)
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import monotonic
from typing import TYPE_CHECKING, Any, Protocol, TypedDict
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine
from sqlalchemy.pool import QueuePool

from tests.infra.bots.order_fixture import submit_fixture_bot_order
from tests.infra.execution_market import profile_internal as internal
from tests.infra.execution_market import profile_observer_prefix as prefix
from tests.infra.execution_market import profile_publisher_recovery as clock_recovery
from tests.infra.execution_market.profile_parent_poll import (
    ParentPollGate,
    poll_interval,
    poll_options,
    validate_options,
)

if TYPE_CHECKING:
    from tests.infra.execution_market.profile_runtime_observation import RuntimeObservation

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
    SourceUnavailableError,
    TimeInForce,
    TradingMode,
)
from tiewtrade.core.positions import ExecutionSide, PositionPair
from tiewtrade.core.realtime_prices import ObservationKind, QuoteObservation
from tiewtrade.infra.db import DatabaseRole, create_engine_for, user_session
from tiewtrade.infra.db import session as db_session
from tiewtrade.infra.db.session import market_data_session
from tiewtrade.infra.market_data.catalog import SOURCE
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
MAX_INPUT_LAG = 20
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


class CommandSender(Protocol):
    def order_id(self, owner: OwnerState, key: UUID) -> UUID: ...

    async def submit(self, owner: OwnerState, intent: OrderIntent) -> OrderCommand: ...

    async def cancel(self, owner: OwnerState, order_id: UUID, key: UUID) -> OrderCommand: ...


class CycleOptions(TypedDict, total=False):
    poll_gate: ParentPollGate
    sender: CommandSender


def cycle_options(gate: ParentPollGate | None, sender: CommandSender | None) -> CycleOptions:
    result: CycleOptions = {}
    if gate is not None:
        result["poll_gate"] = gate
    if sender is not None:
        result["sender"] = sender
    return result


class CycleScheduleOptions(TypedDict, total=False):
    cycle_budget_seconds: int
    cycle_report: Path


class CycleBudgetExceededError(TimeoutError):
    """The declared positive-cycle deadline expired, rather than an inner timeout."""


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
        self._holds = 0
        self._paused_at: float | None = None

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
        if self._holds == 0:
            self.open.clear()
            self._paused_at = monotonic()
        self._holds += 1

    def resume(self, elapsed: float) -> None:
        if elapsed < 0 or self._holds <= 0 or self._paused_at is None:
            raise RuntimeError("fault gate resume without a matching pause")
        self._holds -= 1
        if self._holds == 0:
            self.pause_seconds += monotonic() - self._paused_at
            self._paused_at = None
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


def measured_transaction_seconds(
    paths: list[Path],
    *,
    started: float,
    ended: float,
    excluded: list[tuple[float, float]] | None = None,
) -> list[float]:
    """Attribute a transaction by start time; keep its full duration after the cut.

    All workers are local child processes sharing the controller's monotonic clock.
    Setup, final drain and W2 overflow are separate from the declared load window.
    Missing timestamped evidence must fail rather than reuse pooled legacy metrics.
    """
    values = []
    for path in paths:
        if path.name.startswith("risk-"):
            continue  # Separate monitor SLA is measured by committed cursor evidence.
        records = json.loads(path.read_text())["transaction_samples"]
        for row in records:
            if started <= row["started"] < ended and not any(
                a <= row["started"] < b for a, b in excluded or []
            ):
                values.append(float(row["seconds"]))
    return values


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
    values: list[Any],
    operation: Callable[[Any], Awaitable[Any]],
    *,
    limit: int = 20,
    join_on_error: bool = False,
) -> list[Any]:
    semaphore = asyncio.Semaphore(limit)

    async def bounded(value: Any) -> Any:
        async with semaphore:
            return await operation(value)

    if not join_on_error:
        return list(await asyncio.gather(*(bounded(value) for value in values)))
    tasks = [asyncio.create_task(bounded(value)) for value in values]
    try:
        return list(await asyncio.gather(*tasks))
    finally:
        await join_owned_tasks(tasks, sys.exception())


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
    heartbeat_per_book: bool = False,
    price_amount: Money | None = None,
    publication: dict[str, Any] | None = None,
) -> tuple[BookLease, FeedLease]:
    recovery = clock_recovery.current()
    if recovery is not None and recovery.publisher_task is not asyncio.current_task():
        recovery = None

    async def transaction(
        attempt: clock_recovery.Attempt | None = None,
        budget: asyncio.Timeout | None = None,
        *,
        retry: bool = False,
    ) -> tuple[BookLease, FeedLease, datetime]:
        next_book, next_price = book_lease, price_lease
        rejected: SourceUnavailableError | None = None
        async with market_data_session(engine) as session:
            try:
                next_book = await renew_book_writer(session, next_book)
                if recovery is not None and retry:
                    recovery.require_retry_identity(next_book)
                now = (await session.execute("SELECT clock_timestamp()")).scalar_one()
                book = BookState(
                    PAIR,
                    next_book.last_input_id + 1,
                    next_book.generation,
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
                with (
                    clock_recovery.capture(attempt, book, next_book, now)
                    if attempt is not None
                    else nullcontext()
                ):
                    next_book = await publish_input(session, next_book, book, metadata)
                if heartbeat_per_book or update_price:
                    next_price = await renew_writer(session, next_price)
                if update_price:
                    snapshot = await read_snapshot(session)
                    row = next(value for value in snapshot.rows if value.base == "BTC")
                    observation = QuoteObservation(
                        row.source,
                        "BTC",
                        "USDT",
                        Money.of(100, "USDT") if price_amount is None else price_amount,
                        trade_id,
                        now,
                        now,
                        ObservationKind.STREAM,
                    )
                    changed = await write_price(
                        session,
                        next_price,
                        replace(
                            row,
                            observation=observation,
                            reconciled_generation=next_price.generation,
                            effective_readiness="READY",
                            reason=None,
                            unavailable_since=None,
                            order_ambiguous_at=None,
                        ),
                    )
                    if not changed and trade_id == 1:
                        raise RuntimeError("F15_WORKLOAD_PRICE_NOT_PUBLISHED")
            except SourceUnavailableError as error:
                if (
                    recovery is not None
                    and attempt is not None
                    and budget is not None
                    and recovery.claim(attempt, error)
                ):
                    budget.reschedule(recovery.deadline)
                    active = session._connection.get_transaction()
                    if active is None:
                        error.add_note("publisher rollback not confirmed: no active transaction")
                        raise
                    try:
                        await active.rollback()
                    except asyncio.CancelledError:
                        raise
                    except Exception as rollback_error:
                        error.add_note(
                            f"publisher rollback not confirmed: {type(rollback_error).__name__}"
                        )
                        raise error from rollback_error
                    recovery.rolled_back(attempt)
                    rejected = error
                else:
                    raise
        # Normal exit exposes close errors that the error path may suppress.
        if rejected is not None:
            raise rejected
        if attempt is not None:
            attempt.committed_at = monotonic()
        return next_book, next_price, now

    if recovery is None:
        following_book, following_price, now = await transaction()
    else:
        first = recovery.new_attempt(tick=trade_id)
        try:
            async with asyncio.timeout(None) as budget:
                try:
                    following_book, following_price, now = await transaction(first, budget)
                except SourceUnavailableError as error:
                    if not recovery.retry_ready(first, error):
                        raise
                    recovery.retrying()
                    second = recovery.new_attempt(tick=trade_id)
                    following_book, following_price, now = await transaction(
                        second, budget, retry=True
                    )
                    # The recovery bound ends only at a confirmed commit/session exit.
                    if second.committed_at is None or second.committed_at > (
                        recovery.deadline or 0
                    ):
                        raise TimeoutError("publisher clock recovery budget exceeded") from error
                    budget.reschedule(None)
                    recovery.committed(second)
        except BaseException as error:
            recovery.abort(error)
            raise
    if publication is not None:
        publication.setdefault("first_input_ready", now.isoformat())
    return following_book, following_price


class PricePublishOptions(TypedDict, total=False):
    price_amount: Money
    publication: dict[str, Any]


async def market_publisher(
    engine: AsyncEngine,
    stop: asyncio.Event,
    stats: dict[str, Any],
    *,
    heartbeat_per_book: bool = False,
    price_amount: Money | None = None,
) -> None:
    stats["stage"] = "acquire_sources"
    price_options: PricePublishOptions = (
        {} if price_amount is None else {"price_amount": price_amount, "publication": stats}
    )
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
                heartbeat_per_book=heartbeat_per_book,
                **price_options,
            )
            stats["published"] = tick
            stats["last_input_id"] = book.last_input_id
            stats["book_owner"] = str(book.owner)
            stats["book_generation"] = book.generation
            stats["last_progress_at"] = datetime.now(UTC).isoformat()
            stats["max_publish_seconds"] = max(
                stats.get("max_publish_seconds", 0.0), monotonic() - before
            )
            next_due += 1 / float(stats["target_hz"])
    except Exception as error:
        stats["failure_type"] = type(error).__name__
        stats["failed_at"] = datetime.now(UTC).isoformat()
        raise


async def wait_publisher_ready(publisher: asyncio.Task[None], stats: dict[str, Any]) -> None:
    async with asyncio.timeout(5):
        while stats.get("published", 0) < 2:
            if publisher.done():
                await publisher
                raise RuntimeError("F15_WORKLOAD_PUBLISHER_STOPPED_UNEXPECTEDLY")
            await asyncio.sleep(0.01)


def check_observer(failure: asyncio.Future[None] | None) -> None:
    if failure is not None and failure.done():
        raise RuntimeError("F17_FENCE_OBSERVER_EVIDENCE_INCOMPLETE")


async def with_publisher[T](
    operation: Awaitable[T],
    publisher: asyncio.Task[None] | None,
    *,
    failure: asyncio.Future[None] | None = None,
    checks: tuple[asyncio.Task[None], ...] = (),
    cutoff: asyncio.Task[None] | None = None,
) -> T:
    """Fail on source/check errors immediately and join abandoned workload tasks."""
    if publisher is None and failure is None and cutoff is None:
        return await operation
    task = asyncio.ensure_future(operation)
    stopped_before_start = (
        failure is not None and failure.done() and not isinstance(operation, asyncio.Future)
    )
    if stopped_before_start:
        task.cancel()
    pending_checks = set(checks)
    try:
        while True:
            done, _ = await asyncio.wait(
                (
                    task,
                    *(() if publisher is None else (publisher,)),
                    *pending_checks,
                    *(() if cutoff is None else (cutoff,)),
                    *(() if failure is None else (failure,)),
                ),
                return_when=asyncio.FIRST_COMPLETED,
            )
            if failure is not None or cutoff is not None:
                # Preserve already available real failures before the diagnostic stop signal.
                for completed in (task, publisher):
                    if (
                        not (completed is task and stopped_before_start)
                        and completed is not None
                        and completed.done()
                        and (completed.cancelled() or completed.exception() is not None)
                    ):
                        await completed
            for check in pending_checks.intersection(done):
                await check
                pending_checks.remove(check)
            if publisher is not None and publisher in done:
                await publisher
                raise RuntimeError("F15_WORKLOAD_PUBLISHER_STOPPED_UNEXPECTEDLY")
            check_observer(failure)
            if cutoff is not None and cutoff in done:
                await cutoff  # Timer failure/cancellation is never a planned cutoff.
                if not task.done():
                    task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                if not task.cancelled() and task.exception() is not None:
                    await task  # Preserve errors raised while cancelling in-flight work.
                check_observer(failure)
                for checked in (publisher, *pending_checks):
                    if checked is not None and checked.done():
                        await checked
                        if checked is publisher:
                            raise RuntimeError("F15_WORKLOAD_PUBLISHER_STOPPED_UNEXPECTEDLY")
                raise prefix.PrefixCutoffError("F17_PLANNED_PREFIX_CUTOFF")
            if task in done:
                return await task
    finally:
        if not task.done():
            task.cancel()
        joined = asyncio.gather(task, return_exceptions=True)
        if failure is None:
            await joined
        else:
            cancellation: asyncio.CancelledError | None = None
            while not joined.done():
                try:
                    await asyncio.shield(joined)
                except asyncio.CancelledError as error:
                    cancellation = cancellation or error
            if cancellation is not None and sys.exception() is None:
                raise cancellation


async def finish_observed_cleanup(
    operation: Awaitable[None], primary: BaseException | None
) -> None:
    """Join owned finalizers through repeated caller cancellation; retain the original failure."""
    task = asyncio.ensure_future(operation)
    cancelled: asyncio.CancelledError | None = None
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError as error:
            cancelled = cancelled or error
        except BaseException:
            break  # Retrieve the exact exception below, after task ownership ends.
    try:
        task.result()
    except BaseException as error:
        if primary is None:
            raise
        primary.add_note(f"owned cleanup failed: {type(error).__name__}")
    if cancelled is not None:
        if primary is None:
            raise cancelled
        primary.add_note("caller cancelled during owned cleanup")


async def join_owned_tasks(tasks: list[asyncio.Task[Any]], primary: BaseException | None) -> None:
    """Cancel once, then join through repeated parent cancellation before disposing pools."""
    for task in tasks:
        if not task.done() and not task.cancelling():
            task.cancel()

    async def join() -> None:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        original = primary
        for result in results:
            if not isinstance(result, BaseException) or isinstance(result, asyncio.CancelledError):
                continue
            if original is None:
                original = result
            elif result is not original:
                original.add_note(f"owned child cleanup failed: {type(result).__name__}")
        if primary is None and original is not None:
            raise original

    await finish_observed_cleanup(join(), primary)


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


def publish_trace_control(output: Path, started: float, *, seconds: int = 180) -> None:
    """Publish complete observer metadata using the existing atomic PID pattern."""
    control = output / "dispatch-trace-control.json"
    pending = control.with_suffix(".json.tmp")
    save(pending, {"started": started, "seconds": seconds, "owners": [], "detail_limit": 0})
    pending.replace(control)


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


class CoordinationOptions(TypedDict, total=False):
    coordinate_claims: bool


def coordination_options(enabled: bool) -> CoordinationOptions:
    return {"coordinate_claims": True} if enabled else {}


def validate_claim_coordination(enabled: bool, *, r8: bool) -> None:
    if type(enabled) is not bool or (enabled and r8 is not True):
        raise ValueError("claim coordination requires explicit legacy R8 limit20/claim_limit1")


class WorkerOptions(TypedDict, total=False):
    policy: AdmissionPolicy
    manual_intake: bool
    protection_rounds: bool


def internal_worker_options(args: argparse.Namespace) -> WorkerOptions:
    internal.validate(args)
    if not internal.selected(args):
        return {}
    from tiewtrade.infra.risk_limits.policy import TransactionalRiskPolicy

    return {"policy": TransactionalRiskPolicy(), "manual_intake": True, "protection_rounds": True}


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
    coordinate_claims: bool = False,
    protection_rounds: bool = False,
    engine_factory: Callable[[DatabaseRole], AsyncEngine] | None = None,
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
    validate_claim_coordination(
        coordinate_claims,
        r8=(
            round_limit == 20
            and claim_limit == 1
            and not prefer_same_pair
            and not alternate_admission
            and not source_resumption
        ),
    )
    publish_runtime_pid(metrics_path)
    factory = create_engine_for if engine_factory is None else engine_factory
    engine = factory(DatabaseRole.ENGINE)
    scan = factory(DatabaseRole.ENGINE_SCAN)
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
        engine: AsyncEngine, *, cleanup_seconds: float | None = None, strict_rollback: bool = False
    ) -> AsyncIterator[AsyncConnection]:
        started = monotonic()
        processing = False
        try:
            async with original_begin(
                engine, cleanup_seconds=cleanup_seconds, strict_rollback=strict_rollback
            ) as connection:
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
    protection_observer: AbstractContextManager[None] = nullcontext()
    if protection_rounds:
        from tests.infra.execution_market.profile_protections import observe_processing

        protection_observer = observe_processing(metrics_path.with_suffix(".protection.jsonl"))
    try:
        protection_observer.__enter__()
        policy = AllowPaperPolicy() if policy is None else policy
        while not stop_path.exists():
            if protection_rounds:
                from tiewtrade.services.engine.paper_order import run_protection_round

                await run_protection_round(engine=engine, scan_engine=scan, limit=round_limit)
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
                **coordination_options(coordinate_claims),
            )
            if manual_intake and protection_rounds:
                from tests.infra.execution_market.profile_owned_pools import sample_current

                sample_current()
            # Match services/engine/paper_order_main.py, including rounds with stale candidates.
            await asyncio.sleep(0.02)
    finally:
        protection_observer.__exit__(None, None, None)
        db_session._begin = original_begin
        samples.close()
        # Materialize only after measurement stops; sample storage stays bounded during W3.
        records = [json.loads(value) for value in samples_path.read_text().splitlines()]
        save(
            metrics_path,
            {
                "claim_coordination": "SERIALIZED_CLAIM_V2" if coordinate_claims else None,
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


class WorkerObservationOptions(TypedDict, total=False):
    failure_timeline: bool
    observed_startup: bool


async def start_worker_processes(
    count: int,
    output: Path,
    *,
    group: str = "worker",
    diagnostics: bool = False,
    failure_timeline: bool = False,
    r8_claim_budget: bool = False,
    coordinate_claims: bool = False,
    acceptance_profile: str | None = None,
    rebuild_fixture: bool = False,
    observed_startup: bool = False,
) -> tuple[list[asyncio.subprocess.Process], Path, list[Path]]:
    if type(rebuild_fixture) is not bool or (
        rebuild_fixture
        and (
            acceptance_profile is not None
            or diagnostics
            or failure_timeline
            or not r8_claim_budget
            or not coordinate_claims
        )
    ):
        raise ValueError("fixture worker requires isolated standalone R8 coordination")
    internal.validate(
        argparse.Namespace(
            acceptance_profile=acceptance_profile,
            worker_only=True,
            r8_claim_budget=r8_claim_budget,
            coordinate_claims=coordinate_claims,
        )
    )
    validate_claim_coordination(coordinate_claims, r8=r8_claim_budget)
    stop_path = output / f"{group}.stop"
    metrics_paths = [output / f"{group}-{number}.json" for number in range(count)]
    processes: list[asyncio.subprocess.Process] = []
    try:
        for number in range(count):
            spawn_operation = asyncio.create_subprocess_exec(
                sys.executable,
                "-m",
                (
                    "tests.infra.execution_market.profile_rebuild20"
                    if rebuild_fixture
                    else "tests.infra.execution_market.profile_workload"
                ),
                "--worker-only",
                "--worker-name",
                f"f15-workload-{group}-{number}",
                "--worker-stop",
                str(stop_path),
                "--worker-metrics",
                str(metrics_paths[number]),
                *(["--diagnostics"] if diagnostics else []),
                *(["--failure-timeline"] if failure_timeline else []),
                *(["--r8-claim-budget"] if r8_claim_budget else []),
                *(["--coordinate-claims"] if coordinate_claims else []),
                *(["--acceptance-profile", acceptance_profile] if acceptance_profile else []),
                env=paper_worker_environment(),
            )
            if not observed_startup:
                processes.append(await spawn_operation)
                continue
            spawn = asyncio.create_task(spawn_operation)
            cancelled: asyncio.CancelledError | None = None
            while not spawn.done():
                try:
                    await asyncio.shield(spawn)
                except asyncio.CancelledError as error:
                    cancelled = cancelled or error
            processes.append(spawn.result())
            if cancelled is not None:
                raise cancelled
        for process, metrics in zip(processes, metrics_paths, strict=True):
            WORKER_RUNTIME_PIDS[process.pid] = await wait_runtime_pid(process, metrics)
    except BaseException as primary:
        if rebuild_fixture:
            from tests.infra.execution_market.profile_rebuild20 import stop_fixture_workers

            try:
                await stop_fixture_workers(processes, stop_path)
            except BaseException as error:
                primary.add_note(f"worker startup cleanup failed: {type(error).__name__}")
                for note in getattr(error, "__notes__", []):
                    primary.add_note(note)
        else:
            try:
                cleanup = stop_worker_processes(processes, stop_path)
                if observed_startup:
                    await finish_observed_cleanup(cleanup, primary)
                else:
                    await cleanup
            except BaseException as error:
                if not observed_startup:
                    raise
                primary.add_note(f"worker startup cleanup failed: {type(error).__name__}")
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


TAIL_CURSOR_SQL = """SELECT a.availability,
    coalesce((SELECT max(k.input_id) FROM paper_execution_input_keys k
              WHERE k.episode_id=a.episode_id),0) AS input_id
    FROM paper_order_activity a WHERE a.episode_id=:episode"""


async def read_input_cursor(session: db_session.UserSession, episode: UUID) -> Any:
    return (await session.execute(TAIL_CURSOR_SQL, {"episode": episode})).one()


async def wait_for_input_recovery(
    engine: AsyncEngine,
    owners: list[OwnerState],
    expected_input_id: int,
    *,
    poll_gate: ParentPollGate | None = None,
) -> None:
    async def recovered(owner: OwnerState) -> bool:
        async with poll_session(engine, owner.user_id, "input_recovery", poll_gate) as session:
            row = await read_input_cursor(session, owner.wallet.episode_id)
        return bool(row.availability == "READY" and row.input_id >= expected_input_id)

    async with asyncio.timeout(60):
        while True:
            if all(await bounded_map(owners, recovered, join_on_error=poll_gate is not None)):
                return
            await asyncio.sleep(0.05)


def parent_pool_state(engine: AsyncEngine) -> dict[str, int]:
    # Same actual QueuePool properties as the existing PoolEvidence inventory.
    pool = engine.pool
    if not isinstance(pool, QueuePool):
        raise ValueError("bounded parent queue pool required")
    return {
        "pool_size": pool.size(),
        "max_overflow": pool._max_overflow,
        "checked_out": pool.checkedout(),
        "checked_in": pool.checkedin(),
        "overflow": pool.overflow(),
    }


async def tail_resource_observation(engine: AsyncEngine, observer: AsyncEngine) -> dict[str, Any]:
    # Existing migrator pool only. Cross-role activity state may be unavailable.
    async with observer.connect() as connection:
        rows = (
            (
                await connection.exec_driver_sql("""SELECT usename AS role,state,
            count(*) AS connections FROM pg_stat_activity
            WHERE datname=current_database() GROUP BY usename,state ORDER BY usename,state""")
            )
            .mappings()
            .all()
        )
    return {
        "parent_pool": parent_pool_state(engine),
        "unknown_nulls": True,
        "connections": sum(int(row["connections"]) for row in rows),
        "by_role_and_state": [dict(row) for row in rows],
    }


async def drain_final_tail(
    engine: AsyncEngine,
    source: AsyncEngine,
    owners: list[OwnerState],
    publisher: asyncio.Task[None],
    stop: asyncio.Event,
    stats: dict[str, Any],
    evidence: Path,
    *,
    poll_gate: ParentPollGate | None = None,
    observation_engine: AsyncEngine | None = None,
) -> float:
    """Drain both watermarks within one budget, without fabricating fresh source data."""
    started = monotonic()
    watermark = int(stats["last_input_id"])
    record: dict[str, Any] = {"budget_seconds": 60, "initial_watermark": watermark, "stages": []}

    async def stage(name: str) -> None:
        row: dict[str, Any] = {"stage": name, "elapsed_seconds": monotonic() - started}
        if observation_engine is not None:
            row["resources"] = await tail_resource_observation(engine, observation_engine)
        record["stages"].append(row)

    try:
        async with asyncio.timeout_at(started + 60):
            await stage("live_recovery")
            await with_publisher(
                wait_for_input_recovery(engine, owners, watermark, **poll_options(poll_gate)),
                publisher,
            )
            await stage("stop_publisher")
            stop.set()
            await publisher
            head = int(stats["last_input_id"])
            async with market_data_session(source) as session:
                row = (
                    await session.execute(
                        """SELECT owner,generation,last_input_id FROM market_execution_state
                    WHERE source=:source AND base=:base AND quote=:quote""",
                        {"source": SOURCE, "base": PAIR.base, "quote": PAIR.quote},
                    )
                ).one_or_none()
            if (
                row is None
                or row.last_input_id != head
                or head < watermark
                or str(row.owner) != stats["book_owner"]
                or row.generation != stats["book_generation"]
            ):
                raise RuntimeError("F15_FINAL_TAIL_SOURCE_MISMATCH")
            target = max(watermark, head - MAX_INPUT_LAG)
            record.update(
                final_head=head,
                minimum_cursor=target,
                book_owner=stats["book_owner"],
                book_generation=stats["book_generation"],
            )
            await stage("final_tail")
            await wait_for_input_recovery(engine, owners, target, **poll_options(poll_gate))

            async def cursor(owner: OwnerState) -> dict[str, Any]:
                async with poll_session(
                    engine, owner.user_id, "final_cursor", poll_gate
                ) as session:
                    row = await read_input_cursor(session, owner.wallet.episode_id)
                return {
                    "owner": str(owner.user_id),
                    "cursor": int(row.input_id),
                    "availability": row.availability,
                    "lag": head - int(row.input_id),
                }

            semaphore = asyncio.Semaphore(20)

            async def bounded_cursor(owner: OwnerState) -> dict[str, Any]:
                async with semaphore:
                    return await cursor(owner)

            # Own and join every reader before disposing engines, including on
            # a sibling read failure or the single outer drain deadline.
            tasks: list[asyncio.Task[dict[str, Any]]] = []
            try:
                async with asyncio.TaskGroup() as group:
                    tasks = [group.create_task(bounded_cursor(owner)) for owner in owners]
            except ExceptionGroup as errors:
                record["snapshot_error_types"] = [
                    type(error).__name__ for error in errors.exceptions
                ]
                raise errors.exceptions[0] from None
            record["owners"] = [task.result() for task in tasks]
            if len({row["owner"] for row in record["owners"]}) != len(owners) or any(
                row["availability"] != "READY"
                or row["cursor"] < target
                or not 0 <= row["lag"] <= MAX_INPUT_LAG
                for row in record["owners"]
            ):
                raise RuntimeError("F15_FINAL_TAIL_NOT_RECOVERED")
            await stage("complete")
        elapsed = monotonic() - started
    except BaseException as error:
        record.update(error_type=type(error).__name__, elapsed_seconds=monotonic() - started)
        if observation_engine is not None:
            # No new DB work/grace period after the deadline; readers are already joined.
            with suppress(Exception):
                record["cleanup_parent_pool"] = parent_pool_state(engine)
        # Evidence must not replace the original publisher/worker/deadline failure.
        with suppress(OSError):
            save(evidence, record)
        raise
    record.update(elapsed_seconds=elapsed, recovered=True)
    if observation_engine is not None:
        record["cleanup_parent_pool"] = parent_pool_state(engine)
    save(evidence, record)
    return elapsed


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
    prefix_started: float | None = None,
) -> None:
    started = monotonic() if prefix_started is None else prefix_started
    for fault in events:
        await asyncio.sleep(max(0, started + fault.offset_seconds - monotonic()))
        if prefix_started is not None and monotonic() >= prefix_started + prefix.SECONDS:
            return
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


def worker_process_failures(processes: list[asyncio.subprocess.Process]) -> list[str]:
    return [
        f"worker-{number}-exited:{process.returncode}"
        for number, process in enumerate(processes)
        if process.returncode not in (None, 0)
    ]


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


class ResourceOptions(TypedDict, total=False):
    observe_host: bool


async def resource_sampler(
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
                **({"host_load": internal.host_load()} if observe_host else {}),
            }
        )
        if observe_host:
            from tests.infra.execution_market.profile_owned_pools import sample_current

            sample_current()
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


@asynccontextmanager
async def poll_session(
    engine: AsyncEngine,
    owner: UUID,
    kind: str,
    poll_gate: ParentPollGate | None,
) -> AsyncIterator[db_session.UserSession]:
    async with (
        poll_gate.permit(owner, kind) if poll_gate is not None else nullcontext(),
        user_session(engine, owner, role=DatabaseRole.ENGINE) as session,
    ):
        yield session


async def wait_command(
    engine: AsyncEngine,
    owner: UUID,
    command: OrderCommand,
    *,
    timeout: float = 60,
    poll_gate: ParentPollGate | None = None,
) -> OrderCommand:
    async with asyncio.timeout(timeout):
        while True:
            async with poll_session(engine, owner, "wait_command", poll_gate) as session:
                current = await get_order_command(session, command.command_id)
            if current is not None and current.state != "PENDING":
                return current
            await asyncio.sleep(poll_interval(poll_gate, RESULT_POLL_SECONDS))


async def wait_status(
    engine: AsyncEngine,
    owner: UUID,
    order_id: UUID,
    expected: OrderStatus,
    *,
    timeout: float = 60,
    poll_gate: ParentPollGate | None = None,
) -> None:
    async with asyncio.timeout(timeout):
        while True:
            async with poll_session(engine, owner, "wait_status", poll_gate) as session:
                status = (
                    await session.execute(
                        "SELECT status FROM paper_order_projections WHERE order_id=:order",
                        {"order": order_id},
                    )
                ).scalar_one_or_none()
            if status == expected.value:
                return
            await asyncio.sleep(poll_interval(poll_gate, RESULT_POLL_SECONDS))


async def submit_new(
    engine: AsyncEngine,
    owner: OwnerState,
    intent: OrderIntent,
    expected: OrderStatus,
    counters: Counters,
    latencies: list[float],
    *,
    poll_gate: ParentPollGate | None = None,
    sender: CommandSender | None = None,
) -> OrderCommand:
    started = monotonic()
    counters.offered += 1
    with poll_gate.scope("submit_new", owner.user_id) if poll_gate else nullcontext():
        if sender is None:
            async with user_session(engine, owner.user_id, role=DatabaseRole.ENGINE) as session:
                submit = (
                    submit_fixture_bot_order if intent.origin is OrderOrigin.BOT else submit_order
                )
                command = await submit(session, wallet_id=owner.wallet.wallet_id, intent=intent)
        else:
            command = await sender.submit(owner, intent)
    counters.admitted += 1
    result = await wait_command(engine, owner.user_id, command, **poll_options(poll_gate))
    if result.failure_code is not None:
        counters.rejected += 1
        raise RuntimeError(f"F15_WORKLOAD_ORDER_REJECTED:{result.failure_code}")
    order_id = intent.order_id if sender is None else sender.order_id(owner, intent.idempotency_key)
    await wait_status(engine, owner.user_id, order_id, expected, **poll_options(poll_gate))
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
    *,
    poll_gate: ParentPollGate | None = None,
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
                **poll_options(poll_gate),
            )

        await bounded_map(
            owners,
            submit_baseline,
            **({"join_on_error": True} if poll_gate is not None else {}),
        )
        progress("baseline", index + 1, "/", count)


async def cycle(
    engine: AsyncEngine,
    owner: OwnerState,
    run_id: UUID,
    number: int,
    counters: Counters,
    latencies: list[float],
    *,
    poll_gate: ParentPollGate | None = None,
    sender: CommandSender | None = None,
) -> None:
    buy = market_buy(owner, run_id, number)
    await submit_new(
        engine,
        owner,
        buy,
        OrderStatus.FILLED,
        counters,
        latencies,
        **cycle_options(poll_gate, sender),
    )
    counters.fills += 1

    resting = limit_sell(owner, run_id, number)
    await submit_new(
        engine,
        owner,
        resting,
        OrderStatus.ACCEPTED,
        counters,
        latencies,
        **cycle_options(poll_gate, sender),
    )
    if sender is not None:
        resting = replace(resting, order_id=sender.order_id(owner, resting.idempotency_key))

    started = monotonic()
    counters.offered += 1
    with poll_gate.scope("submit_replay", owner.user_id) if poll_gate else nullcontext():
        if sender is None:
            async with user_session(engine, owner.user_id, role=DatabaseRole.ENGINE) as session:
                replay = await submit_order(
                    session, wallet_id=owner.wallet.wallet_id, intent=resting
                )
        else:
            replay = await sender.submit(owner, resting)
    if replay.failure_code is not None or replay.state != "SUCCEEDED":
        counters.rejected += 1
        raise RuntimeError("F15_WORKLOAD_REPLAY_FAILED")
    counters.admitted += 1
    counters.completed += 1
    counters.replays += 1
    latencies.append(monotonic() - started)

    started = monotonic()
    counters.offered += 1
    with poll_gate.scope("submit_cancel", owner.user_id) if poll_gate else nullcontext():
        cancel_key = identity(run_id, owner.user_id, number, "cancel-key")
        if sender is None:
            async with user_session(engine, owner.user_id, role=DatabaseRole.ENGINE) as session:
                cancel = await submit_cancel(
                    session,
                    wallet_id=owner.wallet.wallet_id,
                    episode_id=owner.wallet.episode_id,
                    order_id=resting.order_id,
                    idempotency_key=cancel_key,
                )
        else:
            cancel = await sender.cancel(owner, resting.order_id, cancel_key)
    counters.admitted += 1
    result = await wait_command(engine, owner.user_id, cancel, **poll_options(poll_gate))
    if result.failure_code is not None:
        counters.rejected += 1
        raise RuntimeError(f"F15_WORKLOAD_CANCEL_REJECTED:{result.failure_code}")
    await wait_status(
        engine, owner.user_id, resting.order_id, OrderStatus.CANCELED, **poll_options(poll_gate)
    )
    counters.completed += 1
    counters.cancels += 1
    latencies.append(monotonic() - started)

    sell = market_sell(owner, run_id, number)
    await submit_new(
        engine,
        owner,
        sell,
        OrderStatus.FILLED,
        counters,
        latencies,
        **cycle_options(poll_gate, sender),
    )
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
    poll_gate: ParentPollGate | None = None,
    cycle_scope: Callable[[OwnerState, int], AbstractAsyncContextManager[None]] | None = None,
    sender: CommandSender | None = None,
    cycle_budget_seconds: int = 60,
    cycle_report: Path | None = None,
) -> float:
    if type(cycle_budget_seconds) is not int or cycle_budget_seconds not in (60, 90):
        raise ValueError("unsupported positive cycle budget")
    summary: dict[str, Any] = {
        "budget_seconds": cycle_budget_seconds,
        "original_budget_seconds": 60,
        "completed": 0,
        "interrupted": 0,
        "max_seconds": 0.0,
        "over_original": 0,
    }
    started = monotonic()
    command_interval = 1 / rate
    owner_interval = len(owners) * 5 * command_interval

    @asynccontextmanager
    async def bounded_scope(owner: OwnerState, number: int) -> AsyncIterator[None]:
        if cycle_scope is not None:
            async with cycle_scope(owner, number):
                yield
            return
        budget = asyncio.timeout(cycle_budget_seconds)
        cycle_started = monotonic()
        completed = False
        try:
            async with budget:
                yield
            completed = True
        except TimeoutError as error:
            if budget.expired():
                raise CycleBudgetExceededError(
                    f"Paper cycle exceeded its {cycle_budget_seconds}-second budget"
                ) from error
            raise
        finally:
            if cycle_report is not None:
                duration = monotonic() - cycle_started
                summary["completed" if completed else "interrupted"] += 1
                summary["max_seconds"] = max(summary["max_seconds"], duration)
                summary["over_original"] += int(duration > 60)

    async def owner_cycles(index: int, owner: OwnerState) -> None:
        first_due = started + index * 5 * command_interval
        for number in range(cycles_per_owner):
            due = first_due + number * owner_interval + (0 if gate is None else gate.pause_seconds)
            await asyncio.sleep(max(0, due - monotonic()))
            if gate is None:
                async with bounded_scope(owner, number):
                    await cycle(
                        engine,
                        owner,
                        run_id,
                        number,
                        counters,
                        latencies,
                        **cycle_options(poll_gate, sender),
                    )
            else:
                while True:
                    await gate.enter()
                    due = first_due + number * owner_interval + gate.pause_seconds
                    await asyncio.sleep(max(0, due - monotonic()))
                    if gate.open.is_set():
                        break
                    await gate.leave()
                try:
                    async with bounded_scope(owner, number):
                        await cycle(
                            engine,
                            owner,
                            run_id,
                            number,
                            counters,
                            latencies,
                            **cycle_options(poll_gate, sender),
                        )
                finally:
                    await gate.leave()

    tasks = [asyncio.create_task(owner_cycles(index, owner)) for index, owner in enumerate(owners)]
    primary: BaseException | None = None
    try:
        await asyncio.gather(*tasks)
    except BaseException as error:
        primary = error
        raise
    finally:
        await join_owned_tasks(tasks, sys.exception())
        if cycle_report is not None:
            summary["original_passed"] = (
                summary["interrupted"] == summary["over_original"] == 0
                and summary["completed"] == len(owners) * cycles_per_owner
            )
            summary["accepted_passed"] = (
                summary["interrupted"] == 0
                and summary["completed"] == len(owners) * cycles_per_owner
                and summary["max_seconds"] <= cycle_budget_seconds
            )
            try:
                save(cycle_report, summary)
            except OSError as error:
                if primary is None:
                    raise
                primary.add_note(f"cycle summary write failed: {type(error).__name__}")
            if primary is None and not summary["accepted_passed"]:
                raise CycleBudgetExceededError("positive cycle timing evidence failed")
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
    from tests.infra.execution_market.profile_publisher_lease_load import (
        LoadLeaseObserver,
    )
    from tests.infra.execution_market.profile_publisher_lease_load import (
        validate_options as validate_lease_options,
    )

    validate_lease_options(args)
    clock_recovery.validate_options(args)
    if getattr(args, "acceptance_profile", None) == internal.RELEASE_TIMING_NAME and getattr(
        args, "diagnostics", False
    ):
        raise ValueError("the revised timing profile does not support full diagnostics")
    if getattr(args, "failure_timeline", False) and (
        getattr(args, "diagnostics", False)
        or getattr(args, "worker_only", False)
        or args.phase != "SMOKE"
        or getattr(args, "acceptance_profile", None) != internal.RELEASE_NAME
    ):
        raise ValueError("failure timeline requires original100 SMOKE without full diagnostics")
    validate_options(args)
    validate_claim_coordination(
        getattr(args, "coordinate_claims", False), r8=getattr(args, "r8_claim_budget", False)
    )
    cap = (
        prefix.BUDGET_SECONDS
        if getattr(args, "observer_w3_prefix", False)
        else 1200
        if internal.selected(args) and args.phase == "SMOKE"
        else None
    )
    readiness_status = {"write_failed": False}
    observation: AbstractContextManager[None] = nullcontext()
    if internal.selected(args):
        from tests.infra.execution_market.profile_publisher_readiness import (
            observe_publisher_readiness,
        )

        observation = observe_publisher_readiness(
            args.output / "publisher-readiness.json", evidence_status=readiness_status
        )
    pools = None
    lease_observer = None
    async with AsyncExitStack() as stack:
        if getattr(args, "publisher_clock_recovery", False):
            stack.enter_context(
                clock_recovery.ClockRecovery(
                    args.output / "publisher-clock-recovery.json"
                ).observe()
            )
        if getattr(args, "publisher_lease_observer", False):
            lease_observer = LoadLeaseObserver(
                args.output,
                readiness_status,
                fence_observer=getattr(args, "publisher_fence_observer", False),
                fence_fail_fast=getattr(args, "publisher_fence_fail_fast", False),
                fence_timing=getattr(args, "publisher_fence_timing", False),
                scheduled_samples=getattr(args, "observer_scheduled_samples", False),
                w3_prefix=getattr(args, "observer_w3_prefix", False),
            )
            stack.enter_context(lease_observer.observe())
        stack.enter_context(observation)
        if internal.selected(args):
            from tests.infra.execution_market.profile_owned_pools import (
                observe_owned,
                parent_configuration,
                validate_reports,
            )

            pools = await stack.enter_async_context(
                observe_owned(
                    args.output / "parent.owned-pools.json",
                    parent_configuration(
                        publisher_lease_observer=getattr(args, "publisher_lease_observer", False),
                        publisher_fence_observer=getattr(args, "publisher_fence_observer", False),
                        observer_scheduled_samples=getattr(
                            args, "observer_scheduled_samples", False
                        ),
                    ),
                )
            )
        async with asyncio.timeout(cap):
            failure_only = getattr(args, "failure_timeline", False)
            if getattr(args, "diagnostics", False) or failure_only:
                from tests.infra.execution_market.profile_diagnostics import observe_workload

                code = await observe_workload(
                    args, **({"failure_only": True} if failure_only else {})
                )
            else:
                if lease_observer is not None and lease_observer.failure is not None:
                    if lease_observer.scheduled_enabled:
                        code = await _run(
                            args,
                            observer_failure=lease_observer.failure,
                            measurement_started=lease_observer.measurement_started,
                        )
                    else:
                        code = await _run(args, observer_failure=lease_observer.failure)
                else:
                    code = await _run(args)
    if pools is not None and (args.output / "result.json").exists():
        result = json.loads((args.output / "result.json").read_text())
        report = validate_reports(
            pools.path,
            [Path(p) for p in result.get("owned_worker_pool_paths", [])],
            args.workers,
            publisher_lease_observer=getattr(args, "publisher_lease_observer", False),
            publisher_fence_observer=getattr(args, "publisher_fence_observer", False),
            observer_scheduled_samples=getattr(args, "observer_scheduled_samples", False),
        )
        save(args.output / "pool-contract.json", report)
        if getattr(args, "observer_w3_prefix", False):
            result["pool_contract"] = report
            lease = json.loads((args.output / "publisher-lease.json").read_text())
            errors = prefix.completion_errors(result, lease)
            result["diagnostic_errors"] = errors
            result["diagnostic_status"] = "INCOMPLETE" if errors else "COMPLETE"
            result["status"] = "INCOMPLETE"
            save(args.output / "result.json", result)
            return 2
        base_passed = result["base_assertions_passed"]
        result["pool_contract"] = report
        result["resource_assertions_passed"] = bool(
            result["resource_base_assertions_passed"] and report["passed"]
        )
        result["status"] = (
            "FAILED"
            if not base_passed or report["violations"]
            else "INCOMPLETE"
            if report["incomplete"]
            else "PASSED"
        )
        save(args.output / "result.json", result)
        progress("owned pool contract", result["status"], json.dumps(report))
        return 0 if result["status"] == "PASSED" else 1
    return code


async def _run(
    args: argparse.Namespace,
    *,
    measurement_started: Callable[[float], None] | None = None,
    parent_runtime: RuntimeObservation | None = None,
    observer_failure: asyncio.Future[None] | None = None,
) -> int:
    clock_recovery.validate_options(args)
    if getattr(args, "publisher_clock_recovery", False) and clock_recovery.current() is None:
        raise ValueError("publisher clock recovery context missing")
    validate_options(args)
    internal_phase = internal.validate(args)
    if internal_phase is not None:
        internal.guard_database(dict(os.environ))
    prefix_enabled = getattr(args, "observer_w3_prefix", False)
    if prefix_enabled:
        from tests.infra.execution_market.profile_publisher_lease_load import (
            validate_options as validate_prefix_options,
        )

        validate_prefix_options(args)
    w3_duration = W3_DURATION_SECONDS if internal_phase is None else internal_phase.seconds
    internal_options = (
        {"acceptance_profile": args.acceptance_profile} if internal_phase is not None else {}
    )
    host_options: ResourceOptions = {"observe_host": True} if internal_phase is not None else {}
    schedule_options: CycleScheduleOptions = (
        {
            "cycle_budget_seconds": internal.positive_cycle_budget(args),
            "cycle_report": args.output / "cycle-budgets.json",
        }
        if getattr(args, "acceptance_profile", None) == internal.RELEASE_TIMING_NAME
        else {}
    )
    observation_options: WorkerObservationOptions = (
        {"failure_timeline": True} if getattr(args, "failure_timeline", False) else {}
    )
    if observer_failure is not None:
        observation_options["observed_startup"] = True
    coordinate_claims = getattr(args, "coordinate_claims", False)
    validate_claim_coordination(coordinate_claims, r8=getattr(args, "r8_claim_budget", False))
    poll_gate = (
        ParentPollGate(
            stream_path=args.output / "parent-poll-attempts.jsonl" if internal_phase else None,
            poll_seconds=getattr(args, "observation_poll_seconds", RESULT_POLL_SECONDS),
        )
        if getattr(args, "parent_poll_limit", None) is not None
        else None
    )
    heartbeat_per_book = getattr(args, "publisher_heartbeat_per_book", False)
    final_tail = getattr(args, "final_tail_drain", False)
    if heartbeat_per_book and not getattr(args, "r8_claim_budget", False):
        raise ValueError("publisher heartbeat requires the explicit R8 runtime")
    if final_tail and (
        not heartbeat_per_book or (args.phase != "SMOKE" and internal_phase is None)
    ):
        raise ValueError("final tail drain requires the explicit heartbeat SMOKE parent")
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
    failure: dict[str, object] | None = None
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
    processing_window: dict[str, object] | None = None
    prefix_timer: asyncio.Task[None] | None = None
    intake_stack = AsyncExitStack()
    position_checks = None
    position_task: asyncio.Task[None] | None = None
    position_result = None
    sender: CommandSender | None = None
    drain_seconds = 0.0
    started_at = datetime.now(UTC)
    try:
        if internal_phase is not None:
            await internal.require_empty_database()
        if poll_gate is not None:
            poll_gate.verify_pool(engine)
        if parent_runtime is not None:
            parent_runtime.mark("baseline_start")
        if args.phase in {"W3", "W3_SMOKE"}:
            if args.fault_schedule is None or not args.redis_container:
                raise ValueError("W3 requires --fault-schedule and --redis-container")
            fault_events, fixture_cycles, fault_schedule_digest = load_fault_schedule(
                args.fault_schedule
            )
            if args.cycles_per_owner != fixture_cycles:
                raise ValueError("W3 cycles-per-owner must equal the predeclared fault fixture")
            if internal_phase is not None:
                internal.validate_fault_schedule(
                    args.fault_schedule, profile_name=args.acceptance_profile
                )
        manifest = {
            **clock_recovery.configuration(args),
            "acceptance_profile": internal.manifest(args),
            "profile": PROFILE_VERSION,
            "worker_runtime": (
                "F15_STANDALONE_R8_HEARTBEAT_TAIL_V1"
                if final_tail
                else "F15_STANDALONE_R8_HEARTBEAT_V1"
                if heartbeat_per_book
                else "F15_STANDALONE_R8_OPTIN_V1"
                if getattr(args, "r8_claim_budget", False)
                else "F15_STANDALONE_DEFAULT_V1"
            ),
            "worker_round_limit": 20,
            "claim_coordination": "SERIALIZED_CLAIM_V2" if coordinate_claims else None,
            "worker_claim_limit": 1 if getattr(args, "r8_claim_budget", False) else None,
            "worker_tick_seconds": 0.02,
            "publisher_heartbeat_per_book": heartbeat_per_book,
            "publisher_readiness_observer": "recent64" if internal_phase is not None else None,
            "final_tail_drain": final_tail,
            "checkpoint_storage": "PG_BATCH_V1",
            "parent_poll_limit": None if poll_gate is None else 4,
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
        if internal_phase is not None:
            from tests.infra.execution_market.profile_http import internal_intake

            intake = await intake_stack.enter_async_context(
                internal_intake(
                    owners, engine=engine, api=api, migrator=migrator, gate=poll_gate, output=output
                )
            )
            if args.phase != "SMOKE":
                sender = intake
        publisher = asyncio.create_task(
            market_publisher(source, stop, publisher_stats, heartbeat_per_book=heartbeat_per_book)
        )
        if (recovery := clock_recovery.current()) is not None:
            recovery.publisher_task = publisher
        if observer_failure is None:
            await wait_publisher_ready(publisher, publisher_stats)
        else:
            await with_publisher(
                wait_publisher_ready(publisher, publisher_stats),
                publisher,
                failure=observer_failure,
            )
        async with asyncio.timeout(60 if observer_failure is not None else None):
            worker_processes, worker_stop, worker_metrics = await start_worker_processes(
                args.workers,
                output,
                diagnostics=getattr(args, "diagnostics", False),
                **observation_options,
                r8_claim_budget=getattr(args, "r8_claim_budget", False),
                coordinate_claims=coordinate_claims,
                **internal_options,
            )
        if observer_failure is not None:
            # Startup has returned ownership; reuse real-error priority before the next phase.
            await with_publisher(asyncio.sleep(0), publisher, failure=observer_failure)
        if args.baseline_manifest is None:
            await with_publisher(
                seed_baseline(
                    engine,
                    owners,
                    run_id,
                    args.baseline_orders,
                    **poll_options(poll_gate),
                ),
                publisher,
                failure=observer_failure,
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
                args.workers,
                output,
                group="recovery-worker",
                diagnostics=getattr(args, "diagnostics", False),
                **observation_options,
                r8_claim_budget=getattr(args, "r8_claim_budget", False),
                coordinate_claims=coordinate_claims,
                **internal_options,
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
                    **host_options,
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
                    **host_options,
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
                        diagnostics=getattr(args, "diagnostics", False),
                        **observation_options,
                        r8_claim_budget=getattr(args, "r8_claim_budget", False),
                        coordinate_claims=coordinate_claims,
                        **internal_options,
                    )
                    worker_processes[:] = processes
                    worker_metrics.extend(metrics)

            async def churn_connections() -> None:
                from tests.infra.execution_market.profile_owned_pools import CURRENT

                tracker = CURRENT.get()
                with tracker.intermediate_disposal() if tracker is not None else nullcontext():
                    await asyncio.gather(
                        engine.dispose(), scan.dispose(), api.dispose(), source.dispose()
                    )

            prefix_started = monotonic() if prefix_enabled else None
            if gate is not None:
                fault_task = asyncio.create_task(
                    run_fault_schedule(
                        fault_events,
                        gate,
                        redis_container=args.redis_container,
                        restart_workers=restart_workers,
                        churn_connections=churn_connections,
                        observations=fault_observations,
                        prefix_started=prefix_started,
                    )
                )
            measured_started = monotonic() if prefix_started is None else prefix_started
            if prefix_enabled:
                prefix_timer = asyncio.create_task(prefix.cutoff(measured_started))
            if measurement_started is not None:
                measurement_started(measured_started)
            if internal_phase is not None and args.phase in {"W1", "W2", "W3"}:
                from tests.infra.execution_market.profile_positions import PositionChecks

                position_checks = PositionChecks(engine, owners, output)
                if args.phase == "W3":
                    position_task = asyncio.create_task(
                        position_checks.observe_endurance(measured_started, internal_phase.seconds)
                    )
            processing_window = {
                "attribution": "transaction_start",
                "started": measured_started,
                "ended": None,
                "status": "RUNNING",
            }
            save(output / "processing-window.json", processing_window)
            if (recovery := clock_recovery.current()) is not None:
                recovery.window_start = measured_started
            if poll_gate is not None:
                poll_gate.phase = "measurement"
            if parent_runtime is not None:
                parent_runtime.mark("measurement_start")
            failure_only = getattr(args, "failure_timeline", False)
            if getattr(args, "diagnostics", False) or failure_only:
                publish_trace_control(
                    output, measured_started, **({} if poll_gate is None else {"seconds": 900})
                )
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
                    **cycle_options(poll_gate, sender),
                    **schedule_options,
                ),
                publisher,
                failure=observer_failure,
                cutoff=prefix_timer,
                checks=(
                    tuple(
                        task
                        for task in (
                            (position_task, fault_task, resource_task)
                            if prefix_enabled
                            else (position_task, fault_task)
                        )
                        if task is not None
                    )
                    if observer_failure is not None
                    else (() if position_task is None else (position_task,))
                ),
            )
            if poll_gate is not None:
                poll_gate.phase = "drain"
            if parent_runtime is not None:
                parent_runtime.mark("cycles_complete")
            if fault_task is not None:
                await with_publisher(
                    fault_task,
                    publisher,
                    failure=observer_failure,
                    cutoff=prefix_timer,
                    checks=(
                        tuple(
                            task
                            for task in (
                                (position_task, fault_task, resource_task)
                                if prefix_enabled
                                else (position_task, fault_task)
                            )
                            if task is not None
                        )
                        if observer_failure is not None
                        else (() if position_task is None else (position_task,))
                    ),
                )
            if args.phase == "W3" or internal_phase is not None:
                # Keep feed, workers and resource sampling alive for the full acceptance window.
                duration = w3_duration
                await with_publisher(
                    asyncio.sleep(max(0, measured_started + duration - monotonic())),
                    publisher,
                    failure=observer_failure,
                    cutoff=prefix_timer,
                    checks=(
                        tuple(
                            task
                            for task in (
                                (position_task, fault_task, resource_task)
                                if prefix_enabled
                                else (position_task, fault_task)
                            )
                            if task is not None
                        )
                        if observer_failure is not None
                        else (() if position_task is None else (position_task,))
                    ),
                )
                elapsed = monotonic() - measured_started
            if position_task is not None:
                await position_task
            measured_ended = monotonic()
            if (recovery := clock_recovery.current()) is not None:
                recovery.window_end = measured_ended
            processing_window.update(
                ended=measured_ended,
                status="MEASURED",
                excluded_fault_intervals=[
                    [row["started"], row["restored"]] for row in fault_observations
                ],
            )
            save(output / "processing-window.json", processing_window)
            # Drain the measured watermark with dependencies still available. Stopping
            # the feed first makes its final book stale before all owners can recover.
            recovery_input_id = int(publisher_stats.get("last_input_id", 0))
            measured_inputs = int(publisher_stats.get("published", 0)) - measured_input_start
            if final_tail:
                drain_seconds = await with_publisher(
                    drain_final_tail(
                        engine,
                        source,
                        owners,
                        publisher,
                        stop,
                        publisher_stats,
                        output / "final-tail-drain.json",
                        poll_gate=poll_gate if internal_phase is not None else None,
                        observation_engine=migrator if internal_phase is not None else None,
                    ),
                    None,
                    failure=observer_failure,
                )
            else:
                drain_started = monotonic()
                await with_publisher(
                    wait_for_input_recovery(engine, owners, recovery_input_id),
                    publisher,
                    failure=observer_failure,
                )
                drain_seconds = monotonic() - drain_started
                stop.set()
                await publisher
            publisher = None
        resource_stop.set()
        await resource_task
        await stop_worker_processes(worker_processes, worker_stop)
        check_observer(observer_failure)
        if position_checks is not None:
            position_result = await position_checks.final(
                expected_periodic=w3_duration // 60 if args.phase == "W3" else 0
            )
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
        # Overflow is a separate negative fault case, not a non-fault latency window.
        engine_latencies = (
            []
            if args.phase == "W2_OVERFLOW"
            else measured_transaction_seconds(
                worker_metrics,
                started=measured_started,
                ended=measured_ended,
                excluded=[
                    (float(str(row["started"])), float(str(row["restored"])))
                    for row in fault_observations
                ],
            )
        )
        p95 = None if args.phase == "W2_OVERFLOW" else percentile(engine_latencies, 0.95)
        p99 = None if args.phase == "W2_OVERFLOW" else percentile(engine_latencies, 0.99)
        processing = internal.processing_acceptance(args, p95, p99)
        resources = summarize_resources(resource_samples)
        rss_endurance = (
            endurance_rss(resource_samples, duration_seconds=w3_duration)
            if args.phase == "W3"
            else None
        )
        resource_passed = (
            integer(resources["peak_process_rss_bytes"]) <= MAX_WORKER_RSS_BYTES
            and integer(resources["lock_waits_end"]) == 0
            and integer(invariants["input_lag"]) <= MAX_INPUT_LAG
            and (
                internal.pilot_selected(args)
                or integer(resources["connections_end"])
                <= integer(resources["connections_start"]) + 2
            )
            and (rss_endurance is None or rss_endurance["passed"] is True)
        )
        worker_failures = worker_process_failures(worker_processes)
        passed = (
            counters.offered == expected_commands
            and counters.admitted == expected_commands
            and counters.completed == expected_commands
            and counters.rejected == 0
            and counters.cycles == expected_cycles
            and counters.fills == expected_cycles * 2
            and counters.cancels == expected_cycles
            and counters.replays == expected_cycles
            and (args.phase != "W3" or elapsed >= w3_duration)
            and elapsed
            <= target_seconds
            + sum(event.duration_seconds for event in fault_events)
            + internal.completion_allowance(args)
            and (args.phase == "W2_OVERFLOW" or measured_inputs >= required_book_inputs)
            and processing["passed"]
            and not worker_failures
            and all(value["passed"] for value in observations)
            and invariants["passed"]
            and resource_passed
            and drain_seconds <= 60
            and (position_result is None or position_result["passed"])
            and (internal_phase is None or elapsed >= internal_phase.seconds)
            and (
                fault_result is None
                or (fault_result["no_economic_change"] is True and elapsed <= 60)
            )
        )
        result = {
            "acceptance_profile": internal.manifest(args),
            "phase": args.phase,
            "status": "PENDING_POOL_VALIDATION"
            if internal_phase is not None and passed
            else "PASSED"
            if passed
            else "FAILED",
            **(
                {
                    "processing_acceptance": processing,
                    "performance_warning": processing["performance_warning"],
                    "base_assertions_passed": passed,
                    "resource_base_assertions_passed": resource_passed,
                    "owned_worker_pool_paths": [
                        str(p.with_suffix(".owned-pools.json")) for p in worker_metrics
                    ],
                }
                if internal_phase is not None
                else {}
            ),
            "smoke_only": args.phase in {"SMOKE", "W3_SMOKE"},
            "elapsed_seconds": elapsed,
            "target_seconds": target_seconds,
            "elapsed_limit_seconds": target_seconds
            + sum(event.duration_seconds for event in fault_events)
            + internal.completion_allowance(args),
            "original_elapsed_limit_seconds": target_seconds
            + sum(event.duration_seconds for event in fault_events)
            + 60,
            "drain_seconds": drain_seconds,
            "counters": asdict(counters),
            "engine_transaction_seconds": {
                "applicable": args.phase != "W2_OVERFLOW",
                "p95": p95,
                "p99": p99,
                "max": max(engine_latencies) if engine_latencies else None,
                "samples": len(engine_latencies),
                "window": processing_window,
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
            "resource_assertions_passed": None if internal_phase is not None else resource_passed,
            "global_invariants": invariants,
            "fault": fault_result,
            "fault_observations": fault_observations,
            "endurance_rss": rss_endurance,
            "worker_failures": worker_failures,
            "owners": observations,
            "positions": position_result,
        }
        if (recovery := clock_recovery.current()) is not None:
            if passed:
                recovery.validate_success()
            result["publisher_clock_recovery"] = recovery.report()
        save(output / "resources.json", resource_samples)
        save(output / "result.json", result)
        progress(json.dumps({key: value for key, value in result.items() if key != "owners"}))
        return 0 if passed else 1
    except prefix.PrefixCutoffError:
        if not prefix_enabled or prefix_timer is None or not prefix_timer.done():
            raise
        ended = monotonic()
        if processing_window is None:
            raise ValueError("prefix window missing") from None
        processing_window.update(
            ended=ended, status="INCOMPLETE", stop_reason="PLANNED_PREFIX_CUTOFF"
        )
        if (recovery := clock_recovery.current()) is not None:
            recovery.window_end = ended
        save(output / "processing-window.json", processing_window)
        save(output / "resources.json", resource_samples)
        save(
            output / "result.json",
            {
                "status": "INCOMPLETE",
                "diagnostic_only": True,
                "diagnostic_status": "INCOMPLETE",
                "stop_reason": "PLANNED_PREFIX_CUTOFF",
                "acceptance_profile": args.acceptance_profile,
                "phase": args.phase,
                "elapsed_seconds": ended - measured_started,
                "target_seconds": w3_duration,
                "diagnostic_target_seconds": prefix.SECONDS,
                "planned_commands": 28200,
                "counters": asdict(counters),
                "inflight_interpretation": "partial; cancellation does not prove rollback",
                "publisher": publisher_stats,
                "fault_observations": fault_observations,
                "worker_failures": worker_process_failures(worker_processes),
                "owned_worker_pool_paths": [
                    str(path.with_suffix(".owned-pools.json")) for path in worker_metrics
                ],
                "final_tail": "NOT_RUN",
                "global_invariants": None,
                "positions": None,
                "full_replay": "NOT_RUN",
                "resource_assertions_passed": None,
            },
        )
        return 2  # This result can never be four-hour workload acceptance.
    except BaseException as error:
        primary_failure = error

        def failure_save(path: Path, value: Any) -> None:
            try:
                save(path, value)
            except BaseException as evidence_error:
                if observer_failure is None:
                    raise
                primary_failure.add_note(
                    f"failure evidence write failed: {type(evidence_error).__name__}"
                )

        if (recovery := clock_recovery.current()) is not None:
            recovery.window_end = monotonic()
        if processing_window is not None:
            processing_window.update(
                status="FAILED" if isinstance(error, CycleBudgetExceededError) else "INCOMPLETE",
                failure_observed=monotonic(),
                fault_observations=fault_observations,
            )
            failure_save(output / "processing-window.json", processing_window)
        failure_save(output / "resources.json", resource_samples)
        failure = {
            "failed_at": datetime.now(UTC),
            "error_type": type(error).__name__,
            "error": str(error),
            "publisher": publisher_stats,
            "worker_failures": worker_process_failures(worker_processes),
            "counters": asdict(counters),
        }
        failure_save(output / "failure.json", failure)
        raise
    finally:
        primary_error = sys.exception()
        if isinstance(primary_error, prefix.PrefixCutoffError):
            primary_error = None  # A real cleanup failure must supersede planned stop.
        if internal_phase is not None:
            from tests.infra.execution_market.profile_owned_pools import CURRENT

            if (tracker := CURRENT.get()) is not None:
                tracker.begin_quiescence()

        async def close_owned_resources() -> None:
            if prefix_enabled:
                stop.set()
                resource_stop.set()
                resources: list[tuple[str, Callable[[], Awaitable[None]]]] = []
                if (
                    worker_processes
                    and worker_stop is not None
                    and any(process.returncode is None for process in worker_processes)
                ):
                    stop_path = worker_stop
                    resources.append(
                        ("workers", lambda: stop_worker_processes(worker_processes, stop_path))
                    )
                resources.extend(
                    [
                        ("intake", intake_stack.aclose),
                        ("source_pool", source.dispose),
                        ("migrator_pool", migrator.dispose),
                        ("api_pool", api.dispose),
                        ("engine_pool", engine.dispose),
                        ("scan_pool", scan.dispose),
                    ]
                )
                await prefix.close_owned(
                    [
                        ("cutoff", prefix_timer),
                        ("positions", position_task),
                        ("resources", resource_task),
                        ("faults", fault_task),
                        ("publisher", publisher),
                    ],
                    resources,
                    output=output,
                    save=save,
                    primary=primary_error,
                )
                return
            if prefix_timer is not None:
                if not prefix_timer.done():
                    prefix_timer.cancel()
                await asyncio.gather(prefix_timer, return_exceptions=True)
            stop.set()
            resource_stop.set()
            if position_task is not None and (
                observer_failure is not None or not position_task.done()
            ):
                position_task.cancel()
                await asyncio.gather(position_task, return_exceptions=True)
            if resource_task is not None and (
                observer_failure is not None or not resource_task.done()
            ):
                resource_task.cancel()
                await asyncio.gather(resource_task, return_exceptions=True)
            if fault_task is not None and (observer_failure is not None or not fault_task.done()):
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
                cleanup = stop_worker_processes(worker_processes, worker_stop)
                if observer_failure is None:
                    await cleanup
                else:
                    await finish_observed_cleanup(cleanup, primary_error)
            try:
                if observer_failure is None:
                    await intake_stack.aclose()
                else:
                    await finish_observed_cleanup(intake_stack.aclose(), primary_error)
            finally:
                for connection in (source, migrator, api, engine, scan):
                    if observer_failure is None:
                        await connection.dispose()
                    else:
                        await finish_observed_cleanup(connection.dispose(), primary_error)

        if observer_failure is None:
            await close_owned_resources()
        else:
            await finish_observed_cleanup(close_owned_resources(), primary_error)
        if failure is not None:
            try:
                failure["worker_failures"] = worker_process_failures(worker_processes)
                save(output / "failure.json", failure)
            except BaseException as cleanup_error:
                if primary_error is None:
                    raise
                primary_error.add_note(
                    f"worker failure evidence cleanup failed: {type(cleanup_error).__name__}"
                )
        if poll_gate is not None:
            try:
                poll_gate.save(output / "parent-poll-gate.json")
            except BaseException as cleanup_error:
                if primary_error is None:
                    raise
                primary_error.add_note(
                    f"poll gate evidence cleanup failed: {type(cleanup_error).__name__}"
                )
        if prefix_enabled and (output / "result.json").exists():
            partial = json.loads((output / "result.json").read_text())
            partial["worker_failures"] = worker_process_failures(worker_processes)
            save(output / "result.json", partial)
        if parent_runtime is not None:
            parent_runtime.mark("resources_closed")


async def worker_entry(args: argparse.Namespace) -> None:
    async with AsyncExitStack() as stack:
        if internal.selected(args):
            from tests.infra.execution_market.profile_owned_pools import (
                WORKER_CONFIGURATION,
                observe_owned,
            )

            await stack.enter_async_context(
                observe_owned(
                    args.worker_metrics.with_suffix(".owned-pools.json"), WORKER_CONFIGURATION
                )
            )
        if getattr(args, "failure_timeline", False):
            from tests.infra.execution_market.profile_commit_observation import observe_commits

            stack.enter_context(observe_commits(args.worker_metrics.with_suffix(".commits.json")))
        if args.diagnostics:
            from tests.infra.execution_market.profile_diagnostics import observe_worker

            await observe_worker(args)
        else:
            await run_worker_process(
                args.worker_name,
                args.worker_stop,
                args.worker_metrics,
                claim_limit=1 if args.r8_claim_budget else None,
                **coordination_options(args.coordinate_claims),
                **internal_worker_options(args),
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--acceptance-profile", choices=tuple(internal.PROFILES))
    parser.add_argument("--parent-poll-limit", type=int)
    parser.add_argument("--diagnostics", action="store_true")
    parser.add_argument("--failure-timeline", action="store_true")
    parser.add_argument("--publisher-clock-recovery", action="store_true")
    parser.add_argument("--publisher-lease-observer", action="store_true")
    parser.add_argument("--publisher-fence-observer", action="store_true")
    parser.add_argument("--publisher-fence-fail-fast", action="store_true")
    parser.add_argument("--publisher-fence-timing", action="store_true")
    parser.add_argument("--observer-scheduled-samples", action="store_true")
    parser.add_argument("--observer-w3-prefix", action="store_true")
    parser.add_argument("--observation-poll-seconds", type=float, choices=(0.25, 1.0), default=0.25)
    parser.add_argument("--r8-claim-budget", action="store_true")
    parser.add_argument("--coordinate-claims", action="store_true")
    parser.add_argument("--publisher-heartbeat-per-book", action="store_true")
    parser.add_argument("--final-tail-drain", action="store_true")
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
    if parsed.publisher_lease_observer:
        # Observer hooks must address this module's actual CLI globals, not a second import.
        sys.modules["tests.infra.execution_market.profile_workload"] = sys.modules[__name__]
    from tests.infra.execution_market.profile_publisher_lease_load import (
        validate_options as validate_lease_options,
    )

    try:
        validate_lease_options(parsed)
    except ValueError as error:
        parser.error(str(error))
    try:
        clock_recovery.validate_options(parsed)
    except ValueError as error:
        parser.error(str(error))
    try:
        validate_options(parsed)
        validate_claim_coordination(parsed.coordinate_claims, r8=parsed.r8_claim_budget)
    except ValueError as error:
        parser.error(str(error))
    if parsed.final_tail_drain and (
        parsed.worker_only
        or not parsed.publisher_heartbeat_per_book
        or (parsed.phase != "SMOKE" and not internal.selected(parsed))
    ):
        parser.error("final tail drain requires the explicit heartbeat SMOKE parent")
    if parsed.publisher_heartbeat_per_book and (parsed.worker_only or not parsed.r8_claim_budget):
        parser.error("publisher heartbeat requires the explicit standalone R8 parent")
    if parsed.worker_only:
        if not parsed.worker_name or parsed.worker_stop is None or parsed.worker_metrics is None:
            parser.error("worker-only mode requires name, stop and metrics paths")
        if internal.selected(parsed):
            asyncio.run(worker_entry(parsed))
            raise SystemExit(0)
        if parsed.diagnostics:
            from tests.infra.execution_market.profile_diagnostics import observe_worker

            raise SystemExit(asyncio.run(observe_worker(parsed)))
        raise SystemExit(
            asyncio.run(
                run_worker_process(
                    parsed.worker_name,
                    parsed.worker_stop,
                    parsed.worker_metrics,
                    claim_limit=1 if parsed.r8_claim_budget else None,
                    **coordination_options(parsed.coordinate_claims),
                    **internal_worker_options(parsed),
                )
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
    if parsed.diagnostics and parsed.phase not in {"W1", "SMOKE"}:
        parser.error("diagnostics requires W1 or SMOKE; the run is not acceptance evidence")
    if parsed.cycles_per_owner < 0 or (
        parsed.phase not in {"BASELINE", "W2_OVERFLOW"} and parsed.cycles_per_owner == 0
    ):
        parser.error("cycles-per-owner must be positive outside W2_OVERFLOW")
    if parsed.phase == "BASELINE" and parsed.cycles_per_owner != 0:
        parser.error("BASELINE prepares orders only and requires zero measured cycles")
    raise SystemExit(asyncio.run(run(parsed)))
