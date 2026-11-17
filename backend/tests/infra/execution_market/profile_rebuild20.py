"""Approved offline rebuild fixture; never a workload, strategy or Live entry point."""

from __future__ import annotations

import argparse
import ast
import asyncio
import hashlib
import json
import os
from collections.abc import Iterator
from contextlib import suppress
from dataclasses import asdict, replace
from pathlib import Path
from time import monotonic
from typing import Any
from unittest.mock import patch
from urllib.parse import urlparse
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market import profile_internal as internal
from tests.infra.execution_market import profile_tail_reads as tail
from tests.infra.execution_market import profile_workload as workload
from tests.infra.execution_market.profile_owned_pools import (
    WORKER_CONFIGURATION,
    OwnedPools,
    parent_configuration,
)
from tests.infra.execution_market.profile_parent_poll import ParentPollGate
from tests.infra.execution_market.profile_positions import PositionChecks
from tests.infra.execution_market.profile_replay_reads import save_partial_result
from tests.infra.execution_market.profile_restore import economic_digest
from tiewtrade.core.order_book import BookState
from tiewtrade.core.orders import SimulationProfile
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.db.session import market_data_session
from tiewtrade.infra.market_data.order_book_codec import input_from_payload, input_payload
from tiewtrade.infra.market_data.order_book_storage import (
    BookLease,
    StoredExecutionInput,
    metadata_from_payload,
    metadata_payload,
    publish_input,
    renew_book_writer,
)
from tiewtrade.infra.paper_orders import storage
from tiewtrade.services.engine.paper_order import run_paper_order_round

HEAD = 96000
OWNERS = 20
CYCLES = 282
BASELINE = 20
BATCH = 500
POOL_CONFIGURATION = parent_configuration(rebuild_fixture=True)


def guard_engines(*engines: AsyncEngine) -> None:
    database = internal.guard_database(dict(os.environ))
    if any(
        engine.url.database != database or engine.url.host not in {"localhost", "127.0.0.1", "::1"}
        for engine in engines
    ):
        raise ValueError("rebuild fixture engine differs from guarded database")


async def finish_mutators(
    tasks: tuple[asyncio.Task[None], ...],
    stop: asyncio.Event,
    journal: SourceJournal,
    *,
    primary: BaseException | None = None,
) -> None:
    stop.set()
    joined = asyncio.gather(*tasks, return_exceptions=True)
    while not joined.done():
        try:
            await asyncio.shield(joined)
        except asyncio.CancelledError as error:
            if primary is None:
                primary = error
    failures = [result for result in joined.result() if isinstance(result, BaseException)]
    try:
        journal.flush()
    except BaseException as error:
        failures.append(error)
    for failure in failures:
        if primary is None:
            primary = failure
        elif failure is not primary:
            primary.add_note(f"rebuild mutator cleanup failed: {type(failure).__name__}")
    if primary is not None:
        raise primary


class SourceJournal:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.touch(exist_ok=False)
        self.pending: list[str] = []
        self.count = 0
        self.last: StoredExecutionInput | None = None

    def append(self, record: StoredExecutionInput) -> None:
        if (
            record.market.input_id != self.count + 1
            or storage._source_digest(record) != record.digest
        ):
            raise ValueError("journal source sequence/digest mismatch")
        self.pending.append(
            json.dumps(
                {
                    "market": input_payload(record.market),
                    "metadata": metadata_payload(record.metadata),
                    "digest": record.digest,
                }
            )
        )
        self.count += 1
        self.last = record
        if len(self.pending) == BATCH:
            self.flush()

    def flush(self) -> None:
        if self.pending:
            with self.path.open("a") as stream:
                stream.write("\n".join(self.pending) + "\n")
            self.pending.clear()

    def batches(self, expected: int) -> Iterator[list[StoredExecutionInput]]:
        self.flush()
        count = 0
        batch = []
        with self.path.open() as stream:
            for line in stream:
                row = json.loads(line)
                record = StoredExecutionInput(
                    input_from_payload(row["market"]),
                    metadata_from_payload(row["metadata"]),
                    row["digest"],
                )
                count += 1
                if (
                    record.market.input_id != count
                    or storage._source_digest(record) != record.digest
                ):
                    raise ValueError("journal retained sequence/digest mismatch")
                batch.append(record)
                if len(batch) == BATCH:
                    yield batch
                    batch = []
        if count != expected:
            raise ValueError("journal retained count mismatch")
        if batch:
            yield batch


class FixturePublisher:
    def __init__(self, engine: AsyncEngine, journal: SourceJournal) -> None:
        self.engine, self.journal = engine, journal
        self.book: BookLease | None = None
        self.price: Any = None

    async def tick(self) -> None:
        guard_engines(self.engine)
        if self.book is None:
            self.book, self.price = await workload.acquire_sources(self.engine)
        original = publish_input
        task = asyncio.current_task()
        captured = []

        async def capture(session: Any, lease: Any, market: Any, metadata: Any) -> Any:
            result = await original(session, lease, market, metadata)
            if asyncio.current_task() is task:
                record = StoredExecutionInput(market, metadata, "")
                captured.append(replace(record, digest=storage._source_digest(record)))
            return result

        with patch.object(workload, "publish_input", capture):
            book, price = await workload.publish_market(
                self.engine,
                self.book,
                self.price,
                rebase=self.journal.count == 0,
                trade_id=self.journal.count + 1,
            )
        if len(captured) != 1:
            raise ValueError("fixture publication capture missing")
        # publish_market's normal session exit confirms commit before journal insertion.
        self.book, self.price = book, price
        self.journal.append(captured[0])

    async def paced(self, stop: asyncio.Event, *, hz: int = 1) -> None:
        if type(hz) is not int or hz not in (1, 10):
            raise ValueError("fixture publisher requires1Hz or10Hz")
        next_due = monotonic()
        while not stop.is_set():
            await self.tick()
            next_due += 1 / hz
            delay = 1 if hz == 1 else max(0, next_due - monotonic())
            with suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), delay)

    async def extend(self, head: int) -> None:
        guard_engines(self.engine)
        if self.book is None or self.journal.last is None or head < self.journal.count:
            raise ValueError("invalid public history extension")
        while self.journal.count < head:
            tail.require_space(self.journal.path.parent)
            pending = []
            book = self.book
            template = self.journal.last
            if not isinstance(template.market, BookState):
                raise ValueError("rebuild fixture requires book source")
            async with market_data_session(self.engine) as session:
                await session.execute("SELECT risk_publication_fence()")
                book = await renew_book_writer(session, book)
                now = (await session.execute("SELECT clock_timestamp()")).scalar_one()
                for number in range(book.last_input_id + 1, min(head, book.last_input_id + 20) + 1):
                    market = replace(
                        template.market,
                        input_id=number,
                        received_at=now,
                        verified_at=now,
                        rebase=False,
                    )
                    metadata = replace(template.metadata, observed_at=now)
                    book = await publish_input(session, book, market, metadata)
                    record = StoredExecutionInput(market, metadata, "")
                    pending.append(replace(record, digest=storage._source_digest(record)))
            self.book = book
            for record in pending:
                self.journal.append(record)
        self.journal.flush()


async def stop_fixture_workers(
    processes: list[asyncio.subprocess.Process],
    stop_path: Path,
    *,
    graceful_seconds: float = 12,
    termination_seconds: float = 2,
) -> None:
    """Bound the reused shutdown helper and retain evidence of unjoined owned children."""
    primary: BaseException | None = None
    try:
        async with asyncio.timeout(graceful_seconds):
            await workload.stop_worker_processes(processes, stop_path)
        return
    except BaseException as error:
        primary = error
    for process in processes:
        if process.returncode is not None:
            continue
        try:
            process.terminate()
        except ProcessLookupError:
            pass  # The owned child exited between inspection and signaling.
        except BaseException as error:
            primary.add_note(
                f"fixture terminate failed for PID {process.pid}: {type(error).__name__}"
            )
    try:
        async with asyncio.timeout(termination_seconds):
            await asyncio.gather(*(process.wait() for process in processes))
    except BaseException as error:
        primary.add_note(f"fixture join failed: {type(error).__name__}")
    remaining = [process.pid for process in processes if process.returncode is None]
    if remaining:
        primary.add_note(f"fixture workers remain: {remaining}")
    raise primary


def load_fixture_helpers(
    source: Path, output: Path, expected_sha256: str, namespace: dict[str, Any]
) -> None:
    """Pin external launcher dependencies before executing their selected functions."""
    content = source.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    if digest != expected_sha256:
        raise ValueError("fixture helper digest differs from reviewed source")
    pinned = output / "fixture-helpers.py"
    with pinned.open("xb") as stream:
        stream.write(content)
    with (output / "fixture-helpers.sha256").open("x") as stream:
        stream.write(digest + "\n")
    retained = pinned.read_bytes()
    if hashlib.sha256(retained).hexdigest() != expected_sha256:
        raise ValueError("pinned fixture helper digest mismatch")
    names = {"run", "sql", "environment", "create", "cleanup"}
    tree = ast.parse(retained)
    functions = [
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    if {node.name for node in functions} != names or len(functions) != len(names):
        raise ValueError("fixture helper inventory mismatch")
    body: list[ast.stmt] = list(functions)
    exec(compile(ast.Module(body=body, type_ignores=[]), str(pinned), "exec"), namespace)


async def parallel_workers(
    output: Path,
    stop: asyncio.Event,
    processes: list[asyncio.subprocess.Process],
    metrics: list[Path],
    *,
    ready: asyncio.Event | None = None,
) -> None:
    stop_paths: list[Path] = []
    primary: BaseException | None = None
    try:
        for number in range(20):
            if stop.is_set():
                return
            started, stop_path, paths = await workload.start_worker_processes(
                1,
                output,
                group=f"prep-{number}",
                r8_claim_budget=True,
                coordinate_claims=True,
                rebuild_fixture=True,
            )
            processes.extend(started)
            metrics.extend(paths)
            stop_paths.append(stop_path)
            if workload.worker_process_failures(processes):
                raise RuntimeError("fixture worker exited during startup")
        if ready is not None:
            ready.set()
        while not stop.is_set():
            if any(process.returncode is not None for process in processes):
                raise RuntimeError("fixture worker exited before stop")
            await asyncio.sleep(0.02)
    except BaseException as error:
        primary = error
        raise
    finally:
        cleanup_error: BaseException | None = None
        for stop_path in stop_paths:
            try:
                stop_path.touch()
            except BaseException as error:
                cleanup_error = cleanup_error or error
        if processes:
            try:
                await stop_fixture_workers(processes, output / "prep-all.stop")
            except BaseException as error:
                cleanup_error = cleanup_error or error
        if cleanup_error is not None:
            if primary is None:
                raise cleanup_error
            primary.add_note(f"fixture worker shutdown failed: {type(cleanup_error).__name__}")
            for note in getattr(cleanup_error, "__notes__", []):
                primary.add_note(note)


async def prepare_economics(
    api: AsyncEngine,
    engine: AsyncEngine,
    scan: AsyncEngine,
    source: AsyncEngine,
    output: Path,
    *,
    owners: int = OWNERS,
    cycles: int = CYCLES,
    baseline: int = BASELINE,
    parallel_runtime: bool = False,
    owned_processes: list[asyncio.subprocess.Process] | None = None,
) -> tuple[list[workload.OwnerState], FixturePublisher, workload.Counters]:
    if type(parallel_runtime) is not bool or owned_processes:
        raise ValueError("explicit fixture runtime and empty owned-process list required")
    guard_engines(api, engine, scan, source)
    processes = [] if owned_processes is None else owned_processes
    metrics: list[Path] = []
    people = await workload.seed_owners(api, engine, scan, owners)
    publisher = FixturePublisher(source, SourceJournal(output / "source-journal.jsonl"))
    stop = asyncio.Event()
    worker_ready = asyncio.Event()

    async def worker() -> None:
        if parallel_runtime:
            await parallel_workers(output, stop, processes, metrics, ready=worker_ready)
            return
        worker_ready.set()
        while not stop.is_set():
            await run_paper_order_round(
                engine=engine,
                scan_engine=scan,
                worker="rebuild-fixture",
                policy=workload.AllowPaperPolicy(),
                limit=20,
                claim_limit=1,
            )
            await asyncio.sleep(0.01)

    trace_path = output / "parent-poll-attempts.jsonl" if parallel_runtime else None
    if trace_path is not None:
        trace_path.touch(exist_ok=False)
    gate = ParentPollGate(stream_path=trace_path)
    publishing = asyncio.create_task(publisher.paced(stop, hz=10 if parallel_runtime else 1))
    working = asyncio.create_task(worker())
    counters = workload.Counters()
    run_id = uuid4()

    async def seed() -> None:
        while publisher.journal.count == 0 or not worker_ready.is_set():
            await asyncio.sleep(0.01)
        await workload.seed_baseline(engine, people, run_id, baseline, poll_gate=gate)

        async def owner_flow(owner: workload.OwnerState) -> None:
            for number in range(cycles):
                async with asyncio.timeout(60):
                    await workload.cycle(
                        engine, owner, run_id, number, counters, [], poll_gate=gate
                    )
            workload.progress("economic fixture owner complete", str(owner.user_id))

        await workload.bounded_map(
            people, owner_flow, limit=20 if parallel_runtime else 4, join_on_error=True
        )

    primary: BaseException | None = None
    try:
        await workload.with_publisher(seed(), publishing, checks=(working,))
    except BaseException as error:
        primary = error
        raise
    finally:
        try:
            await finish_mutators((publishing, working), stop, publisher.journal, primary=primary)
        except BaseException as error:
            primary = error
            raise
        finally:
            try:
                gate.save(output / "parent-poll-gate.json")
            except BaseException as error:
                if primary is None:
                    primary = error
                    raise
                primary.add_note(f"fixture poll evidence failed: {type(error).__name__}")
            finally:
                save_partial_result(
                    output / "fixture-progress.json",
                    {
                        "counters": asdict(counters),
                        "journal_records": publisher.journal.count,
                        "parallel_runtime": parallel_runtime,
                        "workers": [
                            {
                                "pid": process.pid,
                                "runtime_pid": workload.WORKER_RUNTIME_PIDS.get(process.pid),
                                "returncode": process.returncode,
                            }
                            for process in processes
                        ],
                        "worker_metrics": [str(path) for path in metrics],
                    },
                    primary=primary,
                )
    return people, publisher, counters


async def pad_history(
    engine: AsyncEngine, owners: list[workload.OwnerState], journal: SourceJournal, head: int
) -> None:
    guard_engines(engine)
    existing = {}
    for owner in owners:
        async with user_session(engine, owner.user_id, role=DatabaseRole.ENGINE) as session:
            rows = (
                await session.execute(
                    """SELECT input_id,source_digest FROM paper_execution_inputs
                WHERE episode_id=:episode ORDER BY input_id""",
                    {"episode": owner.wallet.episode_id},
                )
            ).all()
        known = {row.input_id: row.source_digest for row in rows}
        if len(known) != len(rows) or any(number <= 0 or number > head for number in known):
            raise ValueError("fixture has duplicate/out-of-range private inputs")
        existing[owner.user_id] = known
    seen = set()
    for batch in journal.batches(head):
        tail.require_space(journal.path.parent)
        for record in batch:
            seen.add(record.market.input_id)
        for owner in owners:
            async with user_session(engine, owner.user_id, role=DatabaseRole.ENGINE) as session:
                await storage.pin_execution_profile(
                    session,
                    wallet_id=owner.wallet.wallet_id,
                    episode_id=owner.wallet.episode_id,
                    profile=SimulationProfile(),
                )
                prepared = []
                for record in batch:
                    old = existing[owner.user_id].get(record.market.input_id)
                    if old is not None:
                        if old != record.digest:
                            raise ValueError("existing economic source differs from journal")
                        continue
                    prepared.append(
                        storage._prepare_execution_input(
                            session,
                            wallet_id=owner.wallet.wallet_id,
                            episode_id=owner.wallet.episode_id,
                            evidence_id=uuid4(),
                            record=record,
                            decision_market=None,
                            fee_version=SimulationProfile().fee_version,
                            model_version=SimulationProfile().liquidity_version,
                        )
                    )
                if prepared:
                    await session.execute(
                        tail.SEED_SQL, {"rows": json.dumps(prepared, default=str)}
                    )
    if any(not set(known) <= seen for known in existing.values()):
        raise ValueError("existing private source not represented in journal")
    for owner in owners:
        await tail.verify_owner(engine, owner, head)


async def verify_rebuild(
    engine: AsyncEngine,
    admin: AsyncEngine,
    owners: list[workload.OwnerState],
    output: Path,
    *,
    cycles: int,
    baseline: int,
    report: dict[str, Any],
) -> None:
    guard_engines(engine, admin)
    report["financial"] = await workload.verify(
        engine, owners, baseline_orders=baseline, cycles_per_owner=cycles
    )
    report["global"] = await workload.verify_global_invariants(
        engine, owners, baseline_orders=baseline, cycles_per_owner=cycles
    )
    if not all(row["passed"] for row in report["financial"]) or not report["global"]["passed"]:
        raise ValueError("rebuild fixture financial/global oracle failed")
    if report["global"]["input_lag"] != 0:
        raise ValueError("rebuild fixture source head differs")
    before = await economic_digest(admin)
    try:
        report["positions"] = await PositionChecks(engine, owners, output).final(
            expected_periodic=0
        )
        if not report["positions"]["passed"]:
            raise ValueError("original snapshot/rebuild/resource criteria failed")
        if await economic_digest(admin) != before:
            raise ValueError("rebuild changed economic facts")
    finally:
        save_partial_result(output / "verification.json", report)


def guard_fixture_worker(environment: dict[str, str]) -> None:
    targets = set()
    for role in ("ENGINE", "ENGINE_SCAN"):
        parsed = urlparse(environment.get(f"TIEWTRADE_DATABASE_URL_{role}", ""))
        if parsed.hostname not in {"localhost", "127.0.0.1", "::1"} or not parsed.path.startswith(
            "/tiewtrade_internal20_"
        ):
            raise ValueError("fixture worker requires local internal20 role databases")
        targets.add((parsed.hostname, parsed.port, parsed.path))
    if len(targets) != 1:
        raise ValueError("fixture worker role databases differ")


async def fixture_worker_entry(name: str, stop: Path, metrics: Path) -> None:
    guard_fixture_worker(dict(os.environ))
    with OwnedPools(metrics.with_suffix(".owned-pools.json"), WORKER_CONFIGURATION):
        await workload.run_worker_process(
            name,
            stop,
            metrics,
            policy=workload.AllowPaperPolicy(),
            claim_limit=1,
            coordinate_claims=True,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker-only", action="store_true")
    parser.add_argument("--r8-claim-budget", action="store_true")
    parser.add_argument("--coordinate-claims", action="store_true")
    parser.add_argument("--worker-name", required=True)
    parser.add_argument("--worker-stop", type=Path, required=True)
    parser.add_argument("--worker-metrics", type=Path, required=True)
    arguments = parser.parse_args()
    if not (arguments.worker_only and arguments.r8_claim_budget and arguments.coordinate_claims):
        raise ValueError("fixture entry requires explicit worker/R8/coordination flags")
    asyncio.run(
        fixture_worker_entry(
            arguments.worker_name,
            arguments.worker_stop,
            arguments.worker_metrics,
        )
    )
