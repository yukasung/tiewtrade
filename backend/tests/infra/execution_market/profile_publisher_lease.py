"""LEASE-01 fixture-only spans and delays; never renew/reacquire on failure."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections.abc import AsyncIterator, Awaitable, Callable, Coroutine, Iterator
from contextlib import ExitStack, asynccontextmanager, contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from typing import Any
from unittest.mock import patch

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market import profile_internal as internal
from tests.infra.execution_market import profile_workload as workload
from tests.infra.execution_market import remaining_paper_campaign as campaign
from tests.infra.execution_market.profile_publisher_readiness import observe_publisher_readiness
from tiewtrade.core.order_book import BookState
from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.infra.db.session import market_data_session
from tiewtrade.infra.market_data import order_book_storage as books
from tiewtrade.infra.market_data import realtime_storage as prices
from tiewtrade.infra.market_data.realtime_records import WriterLeaseLost

ROOT = Path(__file__).resolve().parents[4]


@dataclass(frozen=True)
class Case:
    name: str
    update_price: bool
    delay_at: str | None = None
    delay_seconds: float = 0

    @property
    def tick(self) -> int:
        return 10 if self.update_price else 2


CASES = (
    Case("L0-H", False),
    Case("L0-P", True),
    Case("L1-H", False, "after_book", 4.5),
    Case("L1-P", True, "after_book", 4.5),
    Case("L2-U", False, "before_renew_update", 5.25),
)
FINANCIAL_TABLES = (
    "paper_wallet_ledger",
    "paper_order_commands",
    "paper_order_events",
    "paper_position_events",
    "paper_reservations",
    "paper_position_projections",
)


@dataclass(frozen=True)
class Publication:
    tick: int
    update_price: bool
    heartbeat_per_book: bool


class LeaseTrace:
    def __init__(
        self,
        case: Case | None,
        path: Path,
        *,
        publication: Publication | None = None,
        sink: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        if case is not None:
            if case not in CASES or publication is not None or sink is not None:
                raise ValueError("approved lease diagnostic case required")
        elif (
            publication is None
            or sink is None
            or type(publication.tick) is not int
            or publication.tick < 1
            or type(publication.update_price) is not bool
            or type(publication.heartbeat_per_book) is not bool
        ):
            raise ValueError("actual workload publication and sink required")
        self.case = case
        self.publication = publication
        self.sink = sink
        self.path = path
        self.actor = asyncio.current_task()
        self.operation: ContextVar[str] = ContextVar("lease_operation", default="publisher_body")
        self.spans: list[dict[str, Any]] = []
        self.statements: list[dict[str, Any]] = []
        self.locked_rows: list[dict[str, Any]] = []
        self.events: list[dict[str, Any]] = []
        self.injections = 0
        self.guard_calls = 0
        self.evidence_ok = True

    def active(self) -> bool:
        return asyncio.current_task() is self.actor

    async def delay(self, point: str) -> None:
        if not self.active() or self.case is None or point != self.case.delay_at or self.injections:
            return
        self.injections += 1
        row: dict[str, Any] = {
            "stage": "controlled_delay",
            "point": point,
            "started": monotonic(),
            "requested_seconds": self.case.delay_seconds,
        }
        self.spans.append(row)
        try:
            await asyncio.sleep(self.case.delay_seconds)
            row["outcome"] = "RETURNED"
        except BaseException as error:
            row["outcome"] = type(error).__name__
            raise
        finally:
            row["finished"] = monotonic()

    def wrap(
        self, stage: str, original: Callable[..., Awaitable[Any]]
    ) -> Callable[..., Coroutine[Any, Any, Any]]:
        async def observed(*args: Any, **kwargs: Any) -> Any:
            if not self.active():
                return await original(*args, **kwargs)
            row: dict[str, Any] = {"stage": stage, "started": monotonic()}
            self.spans.append(row)
            token = self.operation.set(stage)
            try:
                result = await original(*args, **kwargs)
                if stage == "book_publish":
                    await self.delay("after_book")
                row["outcome"] = "RETURNED"
                return result
            except BaseException as error:
                row["outcome"] = type(error).__name__
                raise
            finally:
                row["finished"] = monotonic()
                self.operation.reset(token)

        return observed

    def report(self) -> dict[str, Any]:
        case, publication = self.case, self.publication
        if case is not None:
            publication = Publication(case.tick, case.update_price, True)
        assert publication is not None
        return {
            "case": case.name if case is not None else "WORKLOAD",
            "update_price": publication.update_price,
            "heartbeat_per_book": publication.heartbeat_per_book,
            "tick": publication.tick,
            "injections": self.injections,
            "guard_calls": self.guard_calls,
            "spans": self.spans,
            "statements": self.statements,
            "locked_rows": self.locked_rows,
            "events": self.events,
        }

    def persist(self) -> None:
        if self.sink is not None:
            self.sink(json.loads(json.dumps(self.report())))
            return
        workload.save(self.path, self.report())
        if json.loads(self.path.read_text()) != self.report():
            raise ValueError("lease trace evidence differs")

    @contextmanager
    def observe(self, engine: AsyncEngine) -> Iterator[None]:
        # Preserve any session fault wrapper installed on the harness alias.
        original_session = vars(workload)["market_data_session"]
        original_locked = books._locked
        original_guard = BookState.require_ready
        active_statement: dict[int, dict[str, Any]] = {}
        listeners: list[tuple[str, Any]] = []

        def milestone(name: str) -> Callable[..., None]:
            def record(*args: Any) -> None:
                if self.active():
                    self.events.append({"event": name, "at": monotonic()})

            return record

        def before(
            connection: Any, cursor: Any, statement: str, parameters: Any, context: Any, many: bool
        ) -> None:
            if not self.active():
                return
            operation = self.operation.get()
            stage = operation
            if operation == "book_renew":
                sql = " ".join(statement.upper().split())
                if (
                    sql.startswith("WITH LOCKED AS MATERIALIZED")
                    and "MARKET_EXECUTION_STATE" in sql
                ):
                    stage = "book_locked"
                elif sql.startswith("UPDATE MARKET_EXECUTION_STATE SET LEASE_UNTIL="):
                    stage = "book_renew_update"
                else:
                    raise ValueError("unsupported book renewal observation SQL")
            row = {
                "stage": stage,
                "started": monotonic(),
                "backend_pid": connection.connection.driver_connection.get_server_pid(),
            }
            self.statements.append(row)
            active_statement[id(context)] = row

        def after(
            connection: Any, cursor: Any, statement: str, parameters: Any, context: Any, many: bool
        ) -> None:
            row = active_statement.pop(id(context), None)
            if row is not None:
                row.update(finished=monotonic(), outcome="RETURNED", rowcount=cursor.rowcount)

        def failed(context: Any) -> None:
            row = active_statement.pop(id(context.execution_context), None)
            if row is not None:
                row.update(finished=monotonic(), outcome=type(context.original_exception).__name__)

        def guard(book: BookState, now: Any) -> None:
            if self.active():
                self.guard_calls += 1
            return original_guard(book, now)

        async def locked(*args: Any, **kwargs: Any) -> Any:
            row = await original_locked(*args, **kwargs)
            if self.active():
                self.locked_rows.append(
                    {
                        "stage": self.operation.get(),
                        "at": monotonic(),
                        "owner": str(row["owner"]),
                        "generation": row["generation"],
                        "input_id": row["last_input_id"],
                        "lease_until": row["lease_until"].isoformat(),
                        "db_now": row["db_now"].isoformat(),
                        "remaining_seconds": (row["lease_until"] - row["db_now"]).total_seconds(),
                    }
                )
                if self.operation.get() == "book_renew":
                    await self.delay("before_renew_update")
            return row

        @asynccontextmanager
        async def session(*args: Any, **kwargs: Any) -> AsyncIterator[Any]:
            if not self.active():
                async with original_session(*args, **kwargs) as current:
                    yield current
                return
            self.events.append({"event": "session_requested", "at": monotonic()})
            token = self.operation.set("session_role_setup")
            try:
                async with original_session(*args, **kwargs) as current:
                    self.events.append({"event": "session_ready", "at": monotonic()})
                    self.operation.set("publisher_body")
                    yield current
                    rolled_back = current._connection.get_transaction() is None
                    if not rolled_back:
                        self.operation.set("precommit_clock_probe")
                        probe = (await current.execute("SELECT clock_timestamp()")).scalar_one()
                        self.events.append(
                            {
                                "event": "precommit_db_clock",
                                "at": monotonic(),
                                "db_now": probe.isoformat(),
                            }
                        )
                    self.operation.set("session_exit")
                self.events.append(
                    {
                        "event": "session_exited_rollback_confirmed"
                        if rolled_back
                        else "session_exited_confirmed",
                        "at": monotonic(),
                    }
                )
            except BaseException as error:
                self.events.append(
                    {
                        "event": "session_exit_error",
                        "at": monotonic(),
                        "error_type": type(error).__name__,
                    }
                )
                raise
            finally:
                self.operation.reset(token)

        primary: BaseException | None = None
        try:
            for name, callback in (
                ("checkout", milestone("connection_checkout")),
                ("begin", milestone("transaction_begin")),
                ("commit", milestone("commit_started_not_confirmed")),
                ("before_cursor_execute", before),
                ("after_cursor_execute", after),
                ("handle_error", failed),
            ):
                event.listen(engine.sync_engine, name, callback)
                listeners.append((name, callback))
            with ExitStack() as stack:
                stack.enter_context(patch.object(workload, "market_data_session", session))
                stack.enter_context(patch.object(books, "_locked", locked))
                stack.enter_context(patch.object(BookState, "require_ready", guard))
                for name, stage in (
                    ("renew_book_writer", "book_renew"),
                    ("publish_input", "book_publish"),
                    ("renew_writer", "price_renew"),
                    ("read_snapshot", "price_read"),
                    ("write_price", "price_write"),
                ):
                    stack.enter_context(
                        patch.object(workload, name, self.wrap(stage, getattr(workload, name)))
                    )
                yield
        except BaseException as error:
            primary = error
            raise
        finally:
            for name, callback in reversed(listeners):
                event.remove(engine.sync_engine, name, callback)
            for row in active_statement.values():
                row.update(finished=monotonic(), outcome="UNCONFIRMED")
            try:
                self.persist()
            except (OSError, ValueError) as error:
                self.evidence_ok = False
                if primary is None:
                    raise
                primary.add_note(f"lease evidence failed: {type(error).__name__}")


async def state_snapshot(engine: AsyncEngine) -> dict[str, Any]:
    async with market_data_session(engine) as session:
        row = dict(
            (
                await session.execute("""SELECT owner,generation,last_input_id,lease_until,
            clock_timestamp() AS db_now FROM market_execution_state FOR UPDATE NOWAIT""")
            )
            .mappings()
            .one()
        )
        db_now = row.pop("db_now")
        ids = list(
            (
                await session.execute(
                    "SELECT input_id FROM market_execution_buffer ORDER BY input_id"
                )
            ).scalars()
        )
        snapshot = await prices.read_snapshot(session)
    return {
        "book": row,
        "buffer_ids": ids,
        "feed": snapshot.feed,
        "prices": snapshot.rows,
        "db_now": db_now,
    }


async def financial_counts() -> dict[str, int]:
    observer = internal.readonly_admin()
    try:
        async with observer.connect() as connection:
            return {
                name: int(
                    (await connection.execute(text(f"SELECT count(*) FROM {name}"))).scalar_one()
                )
                for name in FINANCIAL_TABLES
            }
    finally:
        await observer.dispose()


def require_readiness_evidence(
    path: Path,
    case: Case,
    book: books.BookLease,
    *,
    input_id: int,
    rejected: bool,
) -> None:
    """Require the final guard receipt for this isolated publication, including L2's zero checks."""
    readiness = json.loads(path.read_text())
    expected_checks = 0 if case.name == "L2-U" else 1
    expected_guard = {
        "owner": str(book.owner),
        "tick": case.tick,
        "input_id": input_id,
        "generation": book.generation,
        "outcome": "RETURNED",
    }
    checks = readiness["checks"]
    if (
        readiness["flush_reason"] != ("WriterLeaseLost" if rejected else "completed")
        or type(readiness["total_checks"]) is not int
        or readiness["total_checks"] != expected_checks
        or readiness["discarded_earlier_checks"] != 0
        or not isinstance(checks, list)
        or len(checks) != expected_checks
        or any(any(row[key] != value for key, value in expected_guard.items()) for row in checks)
    ):
        raise ValueError("lease readiness evidence differs")


async def run_case(case: Case, output: Path) -> dict[str, Any]:
    if case not in CASES:
        raise ValueError("approved lease diagnostic case required")
    database = internal.guard_database(dict(os.environ))
    if len(database.encode("ascii")) > 63:
        raise ValueError("fixture database identifier exceeds PostgreSQL limit")
    output.mkdir(parents=True, exist_ok=False)
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    witness = create_engine_for(DatabaseRole.MARKET_DATA)
    report: dict[str, Any] = {"status": "INCOMPLETE", "case": case.name}
    trace: LeaseTrace | None = None
    try:
        await internal.require_empty_database()
        before_money = await financial_counts()
        if any(before_money.values()):
            raise ValueError("lease diagnostic needs empty financial tables")
        book, price = await workload.acquire_sources(engine)
        for tick in range(1, case.tick):
            book, price = await workload.publish_market(
                engine,
                book,
                price,
                rebase=tick == 1,
                trade_id=tick,
                update_price=tick == 1,
                heartbeat_per_book=True,
            )
        before = await state_snapshot(witness)
        report["before"] = before
        report["financial_counts_before"] = before_money
        trace = LeaseTrace(case, output / "trace.json")
        rejection: WriterLeaseLost | None = None
        readiness_status = {"write_failed": False}
        try:
            with (
                trace.observe(engine),
                observe_publisher_readiness(
                    output / "readiness.json", evidence_status=readiness_status
                ),
            ):
                async with asyncio.timeout(15):
                    await workload.publish_market(
                        engine,
                        book,
                        price,
                        rebase=False,
                        trade_id=case.tick,
                        update_price=case.update_price,
                        heartbeat_per_book=True,
                    )
        except WriterLeaseLost as error:
            rejection = error
        after = await state_snapshot(
            witness
        )  # Independent lock-release and committed-state witness.
        report["after"] = after
        report["rejection_type"] = None if rejection is None else type(rejection).__name__
        if not trace.evidence_ok or json.loads(trace.path.read_text()) != trace.report():
            raise ValueError("lease case evidence missing")
        try:
            if readiness_status["write_failed"]:
                raise ValueError("lease readiness evidence write failed")
            require_readiness_evidence(
                output / "readiness.json",
                case,
                book,
                input_id=before["book"]["last_input_id"] + 1,
                rejected=rejection is not None,
            )
        except (OSError, ValueError, KeyError, TypeError) as error:
            report["readiness_evidence_error_type"] = type(error).__name__
            if rejection is not None:
                rejection.add_note(f"lease readiness evidence invalid: {type(error).__name__}")
                raise rejection from error
            raise ValueError("lease readiness evidence missing or invalid") from error
        report["readiness_evidence_valid"] = True
        if trace.injections != int(case.delay_at is not None):
            raise ValueError("lease delay count differs")
        if rejection is not None:
            if case.delay_at is None or {k: v for k, v in before.items() if k != "db_now"} != {
                k: v for k, v in after.items() if k != "db_now"
            }:
                raise RuntimeError("lease rejection did not prove unchanged committed state")
            failures = [
                span["stage"] for span in trace.spans if span.get("outcome") == "WriterLeaseLost"
            ]
            if not any(
                stage in {"book_renew", "book_publish", "price_renew", "price_write"}
                for stage in failures
            ):
                raise RuntimeError("lease rejection stage is not proven")
            if case.name == "L2-U" and (
                "book_renew" not in failures
                or not any(
                    row["stage"] == "book_renew_update"
                    and row.get("outcome") == "RETURNED"
                    and row.get("rowcount") == 0
                    for row in trace.statements
                )
                or after["db_now"] < before["book"]["lease_until"]
            ):
                raise RuntimeError("expiry at renewal UPDATE was not observed")
            outcome = "LEASE_REJECTED_ROLLBACK_CONFIRMED"
        else:
            if (
                case.name == "L2-U"
                or after["book"]["last_input_id"] != before["book"]["last_input_id"] + 1
            ):
                raise RuntimeError("lease case publication identity mismatch")
            if (after["book"]["owner"], after["book"]["generation"]) != (
                before["book"]["owner"],
                before["book"]["generation"],
            ):
                raise RuntimeError("lease case source owner changed")
            if not case.update_price and after["prices"] != before["prices"]:
                raise RuntimeError("heartbeat changed price facts")
            if case.update_price:
                row = next(row for row in after["prices"] if row.base == "BTC")
                if row.observation is None or row.observation.trade_id != case.tick:
                    raise RuntimeError("price observation mismatch")
            outcome = "COMMITTED_ONCE"
        after_money = await financial_counts()
        if before_money != after_money:
            raise RuntimeError("publisher changed financial tables")
        if any(workload.parent_pool_state(owned)["checked_out"] for owned in (engine, witness)):
            raise RuntimeError("lease diagnostic has borrowed connections")
        report.update(
            status="DIAGNOSTIC_COMPLETE",
            outcome=outcome,
            trace=trace.report(),
            before=before,
            after=after,
            financial_counts=after_money,
            independent_lock_witness=True,
        )
        return report
    except BaseException as error:
        report["error_type"] = type(error).__name__
        raise
    finally:
        primary = sys.exception()
        cleanup_error: BaseException | None = None
        for owned in (engine, witness):
            try:
                await owned.dispose()
            except BaseException as error:
                if primary is not None:
                    primary.add_note(f"lease engine cleanup failed: {type(error).__name__}")
                elif cleanup_error is None:
                    cleanup_error = error
        if trace is not None:
            report["trace"] = trace.report()
        if cleanup_error is not None:
            report.update(status="INCOMPLETE", error_type=type(cleanup_error).__name__)
        try:
            workload.save(output / "result.json", report)
        except (OSError, ValueError) as error:
            failure = primary if primary is not None else cleanup_error
            if failure is None:
                raise
            failure.add_note(f"lease result evidence failed: {type(error).__name__}")
        if primary is None and cleanup_error is not None:
            raise cleanup_error


async def prepare(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=False)
    candidate = campaign.hashes()
    campaign.pin_candidate(output, candidate)
    workload.save(output / "source-inventory.json", candidate)
    (output / "runner.py").write_bytes(Path(__file__).read_bytes())
    workload.save(
        output / "cases.json",
        [{**case.__dict__, "tick": case.tick, "heartbeat_per_book": True} for case in CASES],
    )
    workload.save(
        output / "configuration.json",
        {
            "revision": "NC_F17_LEASE_01",
            "campaign_budget_seconds": 600,
            "case_budget_seconds": 15,
            "clock_recovery": False,
            "lease_policy": "original5s/fail-stop/no reacquisition",
            "extra_precommit_probes": 1,
            "postcommit_probe": "independent state/lock witness",
            "financial_commands": False,
        },
    )
    async with asyncio.timeout(600):
        await internal.environment_preflight(
            output / "preflight.json", ROOT, campaign.check_services
        )


async def execute(mode: str, output: Path) -> None:
    if mode == "preflight":
        await prepare(output)
        return
    case = next(case for case in CASES if case.name == mode)
    candidate = json.loads((output / "source-inventory.json").read_text())
    if (
        campaign.hashes() != candidate
        or json.loads((output / "preflight.json").read_text())["status"] != "PASSED"
    ):
        raise ValueError("lease diagnostic provenance/preflight mismatch")
    async with asyncio.timeout(15):
        await run_case(case, output / case.name)
    if campaign.hashes() != candidate:
        raise ValueError("lease diagnostic candidate changed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["preflight", *(case.name for case in CASES)])
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    asyncio.run(execute(args.mode, args.output))
