"""F18 integrated release profile. Explicit invocation only; never a pytest test.

Reuses F15's positive five-command cycle, financial oracles and resource thresholds.
CHECK validates the harness only. It can never report release acceptance.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import platform
import subprocess
import sys
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import monotonic
from typing import Any, TypedDict
from urllib.parse import urlparse
from uuid import UUID, uuid4

from sqlalchemy import Engine, RowMapping, event, text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from tests.infra.execution_market import profile_workload as f15
from tests.infra.risk_limits.profile_dispatch_timing import traced_worker
from tests.infra.risk_limits.profile_memory import diagnostic_window, sample_memory
from tests.infra.risk_limits.profile_observations import (
    SOURCE_HZ,
    PhaseJournal,
    busy_intervals,
    cadence_summary,
    live_progress,
    overflow_timings,
)
from tests.infra.risk_limits.profile_publisher import SourcePublisher
from tests.infra.risk_limits.profile_publisher_process import PublisherLink
from tests.infra.risk_limits.profile_resets import (
    ResetProgress,
    reset_schedule,
    run_resets,
    run_scheduled_work,
)
from tests.infra.risk_limits.profile_resources import (
    PoolEvidence,
    cleanup_connections,
    connection_budget,
    returned_pools,
    worker_pool_evidence,
)
from tests.infra.risk_limits.profile_saturation import (
    Progress as SaturationProgress,
)
from tests.infra.risk_limits.profile_saturation import (
    demand_slots,
    run_saturation,
    verify_identities,
)
from tests.infra.risk_limits.profile_source_timing import SourceTimeline
from tests.infra.risk_limits.profile_timing import (
    cycle_scope,
    recovery_scope,
    recovery_stage,
    trading_completed,
)
from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.orders import (
    BaseSize,
    OrderError,
    OrderIntent,
    OrderStatus,
    OrderType,
    TimeInForce,
    TradingMode,
)
from tiewtrade.core.realtime_prices import Readiness, readiness
from tiewtrade.core.risk_limits import RiskScope, RiskUnavailableError
from tiewtrade.core.totp import code_for, step_at
from tiewtrade.infra.auth import totp
from tiewtrade.infra.crypto import KeyPurpose, KeySource
from tiewtrade.infra.db import DatabaseRole, create_engine_for, user_session
from tiewtrade.infra.db import session as db_session
from tiewtrade.infra.db.session import market_data_session
from tiewtrade.infra.market_data.realtime_storage import (
    read_snapshot,
)
from tiewtrade.infra.paper_orders.dispatch import OrderCommand, get_order_command
from tiewtrade.infra.paper_orders.manual_policy import manual_policy_for
from tiewtrade.infra.paper_orders.requests import (
    ManualRequest,
    admit_cancel_request,
    admit_new_request,
    inspect_new_request,
)
from tiewtrade.infra.paper_orders.views import request_view
from tiewtrade.infra.risk_limits.evaluation_requests import request_evaluation
from tiewtrade.infra.risk_limits.policy import TransactionalRiskPolicy
from tiewtrade.infra.risk_limits.prices import decode_frame
from tiewtrade.infra.risk_limits.records import RiskAction, RiskSubmission
from tiewtrade.infra.risk_limits.requests import authorize_increase, submit_request
from tiewtrade.services.engine.paper_order_main import (
    ALTERNATE_ADMISSION_PRIORITY,
    CANDIDATE_LIMIT,
    CLAIM_LIMIT,
    PREFER_SAME_PAIR_ADMISSION,
    SOURCE_RESUMPTION,
)
from tiewtrade.services.engine.risk_limit_main import serve as serve_risk

MODULE = "tests.infra.risk_limits.profile_workload"


class OverflowResult(TypedDict):
    inputs: int
    injection_seconds: float
    recovery_seconds: float
    verification_seconds: float
    total_seconds: float
    live_baseline: dict[str, Any]
    economics_unchanged: bool


PROFILE = "F18_F15_F16_INTEGRATED_V2"
DURATION = {"W1": 600, "W2": 300, "W3": 1800, "CHECK": 10}
RATE = {"W1": 10, "W2": 100, "W3": 10, "CHECK": 5}


@asynccontextmanager
async def telemetry(path: Path) -> AsyncIterator[None]:
    """Observe successful COMMIT, never statement execution time as durable completion."""
    original = db_session._begin
    stream = path.open("w", encoding="utf-8")

    def cursor(
        connection: Any, _cursor: Any, statement: str, _parameters: Any, context: Any, _many: bool
    ) -> None:
        if "INSERT INTO risk_owner_state" not in statement:
            return
        values = context.compiled_parameters[0]
        if not all(key in values for key in ("owner", "cursor", "boundary", "pending")):
            return
        connection.info["f18_cursor"] = {
            key: values[key] for key in ("owner", "cursor", "boundary", "pending")
        }

    event.listen(Engine, "after_cursor_execute", cursor)

    @asynccontextmanager
    async def measured(
        engine: AsyncEngine, *, cleanup_seconds: float | None = None
    ) -> AsyncIterator[AsyncConnection]:
        sample = None
        async with original(engine, cleanup_seconds=cleanup_seconds) as connection:
            yield connection
            sample = connection.info.pop("f18_cursor", None)
            if sample is not None:
                # A risk-only savepoint may have rolled back after its INSERT.
                # Read the final transaction state before acknowledging any cursor.
                actual = (
                    await connection.execute(
                        text("""SELECT cursor,boundary_cursor,replay_pending
                  FROM risk_owner_state WHERE user_id=:owner AND mode='PAPER'"""),
                        {"owner": sample["owner"]},
                    )
                ).one_or_none()
                if actual is None:
                    sample = None
                else:
                    sample.update(
                        cursor=actual.cursor,
                        boundary=actual.boundary_cursor,
                        pending=actual.replay_pending,
                    )
        # Reaching this line proves that the transaction committed successfully.
        if sample is not None:
            stream.write(
                json.dumps(
                    {**sample, "committed_observed_at": datetime.now(UTC).isoformat()}, default=str
                )
                + "\n"
            )
            stream.flush()

    db_session._begin = measured
    try:
        yield
    finally:
        db_session._begin = original
        event.remove(Engine, "after_cursor_execute", cursor)
        stream.close()


async def worker(args: argparse.Namespace) -> int:
    with worker_pool_evidence(args.metrics):
        async with telemetry(args.metrics.with_suffix(".risk.jsonl")):
            if args.worker == "risk":
                f15.publish_runtime_pid(args.metrics)
                task = asyncio.create_task(serve_risk())
                try:
                    while not args.stop.exists():
                        if task.done():
                            await task
                            raise RuntimeError("F18_MONITOR_EXITED")
                        await asyncio.sleep(0.05)
                finally:
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
                    f15.save(args.metrics, {"transaction_seconds": []})
            else:
                operation = f15.run_worker_process(
                    args.worker,
                    args.stop,
                    args.metrics,
                    policy=TransactionalRiskPolicy(),
                    manual_intake=True,
                    round_limit=CANDIDATE_LIMIT,
                    claim_limit=CLAIM_LIMIT,
                    prefer_same_pair=PREFER_SAME_PAIR_ADMISSION,
                    alternate_admission=ALTERNATE_ADMISSION_PRIORITY,
                    source_resumption=SOURCE_RESUMPTION,
                )
                if getattr(args, "dispatch_trace", False):
                    await traced_worker(operation, args.metrics)
                else:
                    await operation
    return 0


class Fixture(SourcePublisher):
    def __init__(self, output: Path) -> None:
        super().__init__(output, self.source_event)
        self.publisher_mode = "inline"
        self.source_diagnostic = False
        self.sampled_processes: list[asyncio.subprocess.Process] = []
        self.publisher_link = PublisherLink(output, self.source_event, self.sampled_processes)
        self.output = output
        self.dispatch_trace = False
        self.bounded_saturation = False
        self.api = create_engine_for(DatabaseRole.API)
        self.engine = create_engine_for(DatabaseRole.ENGINE)
        self.scan = create_engine_for(DatabaseRole.ENGINE_SCAN)
        self.market = create_engine_for(DatabaseRole.MARKET_DATA, pool_size=5, max_overflow=7)
        self.migrator = create_engine_for(DatabaseRole.MIGRATOR)
        self.auth = create_engine_for(DatabaseRole.AUTH, pool_size=1, max_overflow=0)
        self.pools = PoolEvidence(output / "parent.pools.json")
        for engine, role in (
            (self.api, DatabaseRole.API),
            (self.engine, DatabaseRole.ENGINE),
            (self.scan, DatabaseRole.ENGINE_SCAN),
            (self.market, DatabaseRole.MARKET_DATA),
            (self.migrator, DatabaseRole.MIGRATOR),
            (self.auth, DatabaseRole.AUTH),
        ):
            self.pools.add(engine, role)
        self.policy = TransactionalRiskPolicy()
        self.processes: list[asyncio.subprocess.Process] = []
        self.metrics: list[Path] = []
        self.stop = output / "workers.stop"
        self.owners: list[f15.OwnerState] = []
        self.selected: UUID | None = None
        self.baseline_orders = 20
        self.partial_ready = asyncio.Event()
        self.recovery_complete = asyncio.Event()
        self.selected_limit_restore: UUID | None = None
        self.marker_locks: dict[UUID, asyncio.Lock] = defaultdict(asyncio.Lock)
        self.extra_fills = 0
        self.publisher: asyncio.Task[None] | None = None
        self.input_stream = (output / "inputs.jsonl").open("w", encoding="utf-8")
        self.phases = PhaseJournal(output / "phases.jsonl")
        self.source_stream = (output / "source-commits.jsonl").open("w", encoding="utf-8")
        self.price_suspensions: list[tuple[datetime, datetime]] = []
        self.last_live_baseline: dict[str, Any] | None = None
        self.extra_cancels: dict[UUID, int] = {}
        self.last_markers: dict[UUID, int] = {}
        self.scenarios: list[dict[str, object]] = []

    async def spawn(self, name: str, generation: int = 0) -> None:
        metric = self.output / f"{name}-{generation}.json"
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            MODULE,
            "--worker",
            name,
            "--stop",
            str(self.stop),
            "--metrics",
            str(metric),
            *(["--dispatch-trace"] if getattr(self, "dispatch_trace", False) else []),
            env=f15.paper_worker_environment(),
        )
        self.processes.append(process)
        self.sampled_processes.append(process)
        self.metrics.append(metric)
        f15.WORKER_RUNTIME_PIDS[process.pid] = await f15.wait_runtime_pid(
            process, metric, timeout_seconds=20
        )

    async def publish(self) -> None:
        if self.publisher_mode == "child":
            await self.publisher_link.run(self.stop_market)
        else:
            await super().publish()

    async def source_control(self, **values: Any) -> None:
        if self.publisher_mode == "child":
            await self.publisher_link.control(values)
        self.configure(values)

    async def dispose_source_connections(self) -> None:
        if self.publisher_mode == "child":
            await self.publisher_link.request("DISPOSE")
        else:
            await self.source_market.dispose()

    def source_event(self, event: dict[str, Any]) -> None:
        if event["kind"] == "receipt":
            self.record_source_receipt(
                event["source"],
                event["pair"],
                event["identity"],
                datetime.fromisoformat(event["committed_at"]),
            )
        elif event["kind"] == "frame":
            self.input_stream.write(
                json.dumps(
                    {
                        "kind": "PRICE",
                        "cursor": event["cursor"],
                        "ready_at": event["ready_at"],
                        "measured": event["measured"],
                    }
                )
                + "\n"
            )
            self.input_stream.flush()
            self.last_frame = event["cursor"]
        elif event["kind"] == "stats":
            self.publisher_stats.update(event["values"])
        else:
            raise RuntimeError("F18_SOURCE_EVENT_UNKNOWN")

    def record_source_receipt(
        self, kind: str, pair: str, identity: str, committed: datetime | None
    ) -> None:
        if committed is None:
            raise RuntimeError("F18_COMMIT_TIMESTAMPS_REQUIRED")
        self.source_stream.write(
            json.dumps(
                {
                    "kind": kind,
                    "pair": pair,
                    "identity": identity,
                    "committed_at": committed.isoformat(),
                    "phase": self.phases.at(committed),
                    "observed_at": datetime.now(UTC).isoformat(),
                    "monotonic": monotonic(),
                }
            )
            + "\n"
        )
        self.source_stream.flush()

    async def live_baseline(self, captured: int, deadline: float) -> dict[str, Any]:
        expected = {str(owner.user_id) for owner in self.owners}
        captured_price: int | None = None
        dependencies_ready = False
        async with asyncio.timeout_at(deadline):
            while True:
                rows: list[RowMapping] = []
                # Same MVCC snapshot, owner-local RLS for each inventory member.
                # The migrator is intentionally not BYPASSRLS; never grant it access.
                async with db_session._begin(self.engine) as connection:
                    await connection.exec_driver_sql(
                        "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
                    )
                    await db_session._assert_role(connection, DatabaseRole.ENGINE)
                    for owner in self.owners:
                        await connection.execute(
                            text("SELECT set_config(:setting,:value,true)"),
                            {
                                "setting": db_session.CURRENT_USER_SETTING,
                                "value": str(owner.user_id),
                            },
                        )
                        result = await connection.execute(
                            text("""
                        SELECT a.user_id AS owner_id, a.availability,
                          transaction_timestamp() AS observed, f.id, f.payload,
                          f.captured_at, f.proof, ro.cursor AS risk_cursor, ro.replay_pending,
                          f.proof=encode(sha256(convert_to(f.payload::text,'UTF8')),'hex') AS valid,
                          coalesce(k.input_id,0) AS input_id, s.last_input_id AS watermark,
                          (s.ready AND s.lease_until>transaction_timestamp()
                           AND s.verified_at<=transaction_timestamp()
                           AND s.verified_at>=transaction_timestamp()-interval '1 second')
                          AS source_ready
                        FROM paper_order_activity a CROSS JOIN market_execution_state s
                        LEFT JOIN risk_owner_state ro ON ro.user_id=a.user_id AND ro.mode='PAPER'
                        LEFT JOIN risk_price_publication p ON true
                        LEFT JOIN market_risk_price_frames f ON f.id=p.watermark
                        LEFT JOIN LATERAL (SELECT max(input_id) AS input_id
                          FROM paper_execution_input_keys k WHERE k.episode_id=a.episode_id
                          AND k.base=s.base AND k.quote=s.quote) k ON true
                        WHERE a.episode_id=:episode AND s.source='primary_spot'
                          AND s.base='BTC' AND s.quote='USDT'
                    """),
                            {"episode": owner.wallet.episode_id},
                        )
                        rows.extend(result.mappings().all())
                price_ready = False
                if rows and rows[0]["valid"]:
                    frame = decode_frame(rows[0])
                    price_ready = len(frame.prices) == 2 and all(
                        readiness(
                            quote=price.observation,
                            connected=price.connected,
                            reconciled=price.reconciled,
                            producer_alive=price.lease_until > rows[-1]["observed"],
                            now=rows[-1]["observed"],
                        )
                        is Readiness.READY
                        for price in frame.prices
                    )
                if (
                    captured_price is None
                    and price_ready
                    and all(row["source_ready"] for row in rows)
                ):
                    captured_price = int(rows[0]["id"])
                progress_rows = [
                    {
                        key: row[key]
                        for key in (
                            "owner_id",
                            "availability",
                            "input_id",
                            "watermark",
                            "source_ready",
                        )
                    }
                    for row in rows
                ]
                for row in progress_rows:
                    row["owner_id"] = str(row["owner_id"])
                    row["source_ready"] = bool(row["source_ready"] and price_ready)
                observation = live_progress(progress_rows, expected, captured)
                observation["captured_price_watermark"] = captured_price
                observation["risk_progress"] = [
                    {
                        "owner": str(row["owner_id"]),
                        "cursor": row["risk_cursor"],
                        "pending": row["replay_pending"],
                    }
                    for row in rows
                ]
                observation["passed"] = (
                    observation["passed"]
                    and captured_price is not None
                    and all(
                        row["risk_cursor"] is not None
                        and row["risk_cursor"] >= captured_price
                        and row["replay_pending"] is False
                        for row in rows
                    )
                )
                if (
                    not dependencies_ready
                    and progress_rows
                    and all(row["source_ready"] for row in progress_rows)
                ):
                    dependencies_ready = True
                    self.phases.mark(
                        self.phases.phase,
                        dependencies_ready=True,
                        captured_price_watermark=captured_price,
                    )

                self.last_live_baseline = observation
                if observation["passed"]:
                    self.phases.mark(self.phases.phase, live_baseline=observation)
                    if monotonic() > deadline:
                        raise TimeoutError("F18_LIVE_BASELINE_DEADLINE_EXCEEDED")
                    return observation
                await asyncio.sleep(0.05)

    async def final_risk_drain(self) -> None:
        async with asyncio.timeout(60):
            while True:

                async def caught_up(owner: f15.OwnerState) -> bool:
                    async with user_session(self.api, owner.user_id) as session:
                        row = (
                            await session.execute(
                                "SELECT cursor,replay_pending FROM risk_owner_state "
                                "WHERE mode='PAPER'"
                            )
                        ).one()
                        return row.cursor == self.last_frame and not row.replay_pending

                if all(await f15.bounded_map(self.owners, caught_up)):
                    return
                await asyncio.sleep(0.02)

    async def request(
        self,
        owner: f15.OwnerState,
        intent: OrderIntent | None,
        *,
        cancel: UUID | None = None,
        expected_status: OrderStatus | None = None,
        cancel_key: UUID | None = None,
    ) -> OrderCommand:
        key = (cancel_key or uuid4()) if intent is None else intent.idempotency_key
        receipt: ManualRequest | None = None
        async with asyncio.timeout(60):
            while True:
                try:
                    admission_error: OrderError | None = None
                    async with user_session(self.api, owner.user_id) as session:
                        if intent is None:
                            assert cancel is not None
                            receipt = await admit_cancel_request(
                                session,
                                wallet_id=owner.wallet.wallet_id,
                                episode_id=owner.wallet.episode_id,
                                order_id=cancel,
                                idempotency_key=key,
                            )
                        else:
                            receipt = await inspect_new_request(
                                session, wallet_id=owner.wallet.wallet_id, intent=intent
                            )
                            if receipt is None:
                                try:
                                    checked = await manual_policy_for(
                                        session, intent, delegate=self.policy
                                    )
                                    checked.check(intent)
                                except OrderError as error:
                                    # Match the API: commit the non-authoritative
                                    # evaluation hint before returning refusal.
                                    await request_evaluation(
                                        session, intent, owner.wallet.wallet_id
                                    )
                                    admission_error = error
                                if admission_error is None:
                                    receipt = await admit_new_request(
                                        session, wallet_id=owner.wallet.wallet_id, intent=intent
                                    )
                    if admission_error is not None:
                        raise admission_error
                    break
                except RiskUnavailableError:
                    # A refused retry must not repeatedly take the same owner
                    # lock needed by the monitor to make progress. This is only
                    # a scheduling hint: the loop above always checks the full
                    # policy again before any actual intake.
                    while True:
                        await asyncio.sleep(0.02 if self.started else f15.RESULT_POLL_SECONDS)
                        async with user_session(self.api, owner.user_id) as session:
                            ready = (
                                await session.execute(
                                    """SELECT EXISTS(SELECT 1 FROM risk_limit_evaluations e
                                    JOIN risk_owner_state o USING(user_id,mode)
                                    JOIN risk_limit_settings s USING(user_id,mode)
                                    CROSS JOIN (SELECT watermark FROM risk_price_publication
                                      LIMIT 1) p
                                    WHERE e.mode='PAPER' AND e.reason='READY'
                                      AND e.setting_revision=s.revision AND NOT s.latched
                                      AND NOT e.replay_pending AND NOT o.replay_pending
                                      AND e.price_watermark=p.watermark AND o.cursor=p.watermark
                                      AND o.wallet_id=:wallet AND o.episode_id=:episode)""",
                                    {
                                        "wallet": owner.wallet.wallet_id,
                                        "episode": owner.wallet.episode_id,
                                    },
                                )
                            ).scalar_one()
                        if ready:
                            break
            assert receipt is not None
            while True:
                async with user_session(self.api, owner.user_id) as session:
                    view = await request_view(session, receipt.request_id)
                assert view is not None
                if view.intake_state == "REJECTED" or view.command_state == "REJECTED":
                    raise RuntimeError(
                        f"F18_POSITIVE_REQUEST_REJECTED:{view.intake_failure_code}:{view.command_failure_code}"
                    )
                if (
                    view.command_id is not None
                    and view.command_state == "SUCCEEDED"
                    and (expected_status is None or view.order_state == expected_status.value)
                ):
                    async with user_session(
                        self.engine, owner.user_id, role=DatabaseRole.ENGINE
                    ) as session:
                        result = await get_order_command(session, view.command_id)
                    assert result is not None
                    return result
                # Retain the original F15 result-observation cadence. Polling
                # 100 waiting owners at20ms adds unrelated read contention;
                # the authoritative commit timestamps still measure engine SLA.
                await asyncio.sleep(f15.RESULT_POLL_SECONDS)

    async def mutation(
        self,
        owner: f15.OwnerState,
        action: RiskAction,
        amount: str | None = None,
        *,
        idempotency_key: UUID | None = None,
    ) -> UUID:
        async with user_session(self.api, owner.user_id) as session:
            revision = (
                await session.execute("SELECT revision FROM risk_limit_settings WHERE mode='PAPER'")
            ).scalar_one_or_none() or 0
            submission = RiskSubmission(
                RiskScope(
                    owner.user_id,
                    TradingMode.PAPER,
                    UUID(str(owner.wallet.wallet_id)),
                    UUID(str(owner.wallet.episode_id)),
                ),
                action,
                uuid4() if idempotency_key is None else idempotency_key,
                revision,
                None if amount is None else Money.of(amount, "USDT"),
            )
            if action is not RiskAction.INCREASE:
                receipt = await submit_request(session, submission)
        if action is RiskAction.INCREASE:
            # Isolated synthetic owner only, matching W4's real F-06 AUTH path.
            # Enrollment consumes the preceding step; authorization consumes now.
            keys = KeySource(KeyPurpose.TOTP_SECRET, "f18-profile", {"f18-profile": b"F" * 32})
            secret = totp.new_secret()
            async with user_session(self.auth, owner.user_id, role=DatabaseRole.AUTH) as session:
                now = (await session.execute("SELECT clock_timestamp()")).scalar_one()
                await totp.stage_secret(session, keys, secret)
                if not await totp.confirm_secret(
                    session, keys, presented=code_for(secret, step_at(now) - 1), now=now
                ):
                    raise RuntimeError("F18_FIXTURE_TOTP_ENROLLMENT_FAILED")
                if (
                    await totp.verify(
                        session, keys, presented=code_for(secret, step_at(now)), now=now
                    )
                    is not totp.CodeOutcome.ACCEPTED
                ):
                    raise RuntimeError("F18_FIXTURE_TOTP_VERIFICATION_FAILED")
                await authorize_increase(session, submission)
            async with user_session(self.api, owner.user_id) as session:
                receipt = await submit_request(session, submission)
        async with asyncio.timeout(60):
            while True:
                async with user_session(self.api, owner.user_id) as session:
                    result = (
                        await session.execute(
                            "SELECT state,failure_code FROM risk_limit_results "
                            "WHERE request_id=:id",
                            {"id": receipt.receipt_id},
                        )
                    ).one_or_none()
                if result is not None:
                    if result.state != "APPLIED":
                        raise RuntimeError(f"F18_RISK_MUTATION_REJECTED:{result.failure_code}")
                    await self.record_financial(owner)
                    return receipt.receipt_id
                await asyncio.sleep(0.02)

    async def record_financial(self, owner: f15.OwnerState) -> None:
        async with self.marker_locks[owner.user_id]:
            async with user_session(self.api, owner.user_id) as session:
                rows = await session.execute(
                    """SELECT sequence,kind,pg_xact_commit_timestamp(xmin) ready_at
                  FROM risk_financial_boundaries WHERE sequence>:last ORDER BY sequence""",
                    {"last": self.last_markers.get(owner.user_id, 0)},
                )
                for row in rows:
                    if row.ready_at is None:
                        raise RuntimeError("F18_FINANCIAL_COMMIT_TIMESTAMP_MISSING")
                    self.input_stream.write(
                        json.dumps(
                            {
                                "kind": row.kind,
                                "owner": str(owner.user_id),
                                "cursor": row.sequence,
                                "ready_at": row.ready_at.isoformat(),
                                "measured": self.started,
                            }
                        )
                        + "\n"
                    )
                    self.last_markers[owner.user_id] = row.sequence
            self.input_stream.flush()

    async def new(
        self,
        engine: AsyncEngine,
        owner: f15.OwnerState,
        intent: OrderIntent,
        expected: OrderStatus,
        counters: f15.Counters,
        latencies: list[float],
    ) -> OrderCommand:
        start = monotonic()
        counters.offered += 1
        partial = (
            owner.user_id == self.selected
            and expected is OrderStatus.FILLED
            and not self.partial_ready.is_set()
        )
        result = await self.request(
            owner,
            intent,
            expected_status=OrderStatus.PARTIALLY_FILLED if partial else expected,
        )
        counters.admitted += 1
        if partial:
            await f15.wait_status(
                self.engine, owner.user_id, intent.order_id, OrderStatus.PARTIALLY_FILLED
            )
            await self.record_financial(owner)
            async with user_session(self.api, owner.user_id) as session:
                row = (
                    await session.execute(
                        "SELECT loss FROM risk_limit_evaluations WHERE mode='PAPER'"
                    )
                ).one()
                assert row.loss is not None and Money.of(row.loss, "USDT") == Money.of(
                    "0.05", "USDT"
                )
            await self.source_control(ask_quantity="1000000", finish_partial=True)
            self.extra_fills = 1
        # Other NEW states were already proved in the same joined request view
        # as the successful command result. Partial completion still needs a
        # later FILLED observation after enabling the contra-trade fixture.
        if partial:
            await f15.wait_status(self.engine, owner.user_id, intent.order_id, expected)
        if (
            owner.user_id == self.selected
            and expected is OrderStatus.FILLED
            and not self.partial_ready.is_set()
        ):
            await self.source_control(finish_partial=False)
            self.partial_ready.set()
            self.scenarios.append(
                {
                    "owner": str(owner.user_id),
                    "scenario": "PARTIAL_FILL_RISK_ORACLE",
                    "loss": "0.05",
                }
            )
        counters.completed += 1
        latencies.append(monotonic() - start)
        if expected is OrderStatus.FILLED:
            await self.record_financial(owner)
        return result

    @asynccontextmanager
    async def cycle_scope(self, owner: f15.OwnerState, number: int) -> AsyncIterator[None]:
        async with cycle_scope(
            self.output / "cycle-timing.jsonl",
            owner=owner.user_id,
            number=number,
            recovery_allowed=owner.user_id == self.selected and number == 0,
        ):
            yield

    async def cycle(
        self,
        engine: AsyncEngine,
        owner: f15.OwnerState,
        run_id: UUID,
        number: int,
        counters: f15.Counters,
        latencies: list[float],
    ) -> None:
        if owner.user_id != self.selected:
            await self.partial_ready.wait()
        buy = f15.market_buy(owner, run_id, number)
        if owner.user_id == self.selected and number == 0:
            buy = replace(
                buy,
                kind=OrderType.LIMIT,
                size=BaseSize(Quantity.of(1, "BTC")),
                limit_price=Money.of(100, "USDT"),
                time_in_force=TimeInForce.GTC,
            )
        await self.new(self.engine, owner, buy, OrderStatus.FILLED, counters, latencies)
        counters.fills += 1
        if owner.user_id == self.selected and number == 0:
            async with recovery_scope():
                await self.breach_reset(owner, run_id)
        resting = f15.limit_sell(owner, run_id, number)
        await self.new(self.engine, owner, resting, OrderStatus.ACCEPTED, counters, latencies)
        started = monotonic()
        counters.offered += 1
        replay = await self.request(owner, resting)
        assert replay.state == "SUCCEEDED" and replay.failure_code is None
        counters.admitted += 1
        counters.completed += 1
        counters.replays += 1
        latencies.append(monotonic() - started)
        started = monotonic()
        counters.offered += 1
        if getattr(self, "bounded_saturation", False):
            await self.request(
                owner,
                None,
                cancel=resting.order_id,
                cancel_key=f15.identity(run_id, owner.user_id, number, "cancel-key"),
            )
        else:
            await self.request(owner, None, cancel=resting.order_id)
        counters.admitted += 1
        await f15.wait_status(self.engine, owner.user_id, resting.order_id, OrderStatus.CANCELED)
        counters.completed += 1
        counters.cancels += 1
        latencies.append(monotonic() - started)
        await self.new(
            self.engine,
            owner,
            f15.market_sell(owner, run_id, number),
            OrderStatus.FILLED,
            counters,
            latencies,
        )
        counters.fills += 1
        counters.cycles += 1
        trading_completed()
        if owner.user_id == self.selected and number == 0:
            await self.correction(owner, buy.order_id)
            # The temporary breach limit must not require synthetic per-cycle resets.
            self.selected_limit_restore = await self.mutation(owner, RiskAction.INCREASE, "1000")
            self.recovery_complete.set()

    async def correction(self, owner: f15.OwnerState, order_id: UUID) -> None:
        from tiewtrade.infra.paper_orders.codec import execution_from_payload
        from tiewtrade.infra.paper_orders.corrections import correct_fill
        from tiewtrade.infra.positions import PositionEventKind

        async with user_session(self.engine, owner.user_id, role=DatabaseRole.ENGINE) as session:
            linked = (
                (
                    await session.execute(
                        """SELECT l.position_event_id,l.order_event_id,e.payload
              FROM paper_execution_links l JOIN paper_order_events e ON e.id=l.order_event_id
              WHERE l.order_id=:order AND l.position_event_kind='RECORD'
                  ORDER BY e.sequence LIMIT 1""",
                        {"order": order_id},
                    )
                )
                .mappings()
                .one()
            )
            fact = execution_from_payload(linked["payload"]["execution"])
            correction = uuid4()
            for _ in range(2):
                await correct_fill(
                    session,
                    wallet_id=owner.wallet.wallet_id,
                    episode_id=owner.wallet.episode_id,
                    order_event_id=linked["order_event_id"],
                    correction_event_id=correction,
                    supersedes_position_event_id=linked["position_event_id"],
                    kind=PositionEventKind.REPLACE,
                    fact=fact,
                )
        await self.record_financial(owner)
        self.scenarios.append(
            {"owner": str(owner.user_id), "scenario": "EXACT_CORRECTION_AND_REPLAY"}
        )

    async def breach_reset(self, owner: f15.OwnerState, run_id: UUID) -> None:
        await self.source_control(price="80")
        async with recovery_stage("breach_stop"), asyncio.timeout(30):
            while True:
                async with user_session(self.api, owner.user_id) as session:
                    row = (
                        await session.execute("""
                      SELECT s.latched,p.target_set_complete,p.pending_count
                      FROM risk_limit_settings s LEFT JOIN risk_stop_requests r USING(user_id,mode)
                      LEFT JOIN risk_stop_progress p ON p.stop_id=r.id WHERE s.mode='PAPER'""")
                    ).one()
                if row.latched and row.target_set_complete and row.pending_count == 0:
                    break
                await asyncio.sleep(0.02)
        await self.source_control(price="100")
        # Wait for the recorded recovery input, without clearing the durable latch.
        async with recovery_stage("recovery_price"), asyncio.timeout(10):
            while True:
                async with market_data_session(self.market) as session:
                    price_row = next(
                        row for row in (await read_snapshot(session)).rows if row.base == "BTC"
                    )
                if price_row.observation is not None and price_row.observation.amount == Money.of(
                    100, "USDT"
                ):
                    break
                await asyncio.sleep(0.02)
        async with recovery_stage("reset"):
            await self.mutation(owner, RiskAction.RESET)
        ignored = f15.Counters()
        times: list[float] = []
        for index in range(self.baseline_orders):
            intent = f15.baseline(owner, run_id, index + self.baseline_orders)
            async with recovery_stage(f"reseed-{index + 1}", order_id=intent.order_id):
                await self.new(self.engine, owner, intent, OrderStatus.ACCEPTED, ignored, times)
        self.extra_cancels[owner.user_id] = self.baseline_orders
        self.scenarios.append(
            {
                "owner": str(owner.user_id),
                "scenario": "PRICE_BREACH_STOP_RESET_RESEED",
                "targets": self.baseline_orders,
            }
        )

    async def close(self) -> None:
        self.stop_market.set()
        if self.publisher is not None:
            self.publisher.cancel()
            await asyncio.gather(self.publisher, return_exceptions=True)
        self.stop.touch()
        if self.processes:
            await f15.stop_worker_processes(self.processes, self.stop)
        try:
            await self.publisher_link.close()
        finally:
            await self.close_source()
            self.input_stream.close()
            self.source_stream.close()
            for engine in (self.api, self.engine, self.scan, self.market, self.migrator, self.auth):
                await engine.dispose()
            self.pools.finish()


def sla_summary(output: Path, owners: list[UUID], *, phase: str | None = None) -> dict[str, object]:
    """Every measured input must have a successful, authoritative cursor COMMIT."""
    import heapq

    # R34 extends the Paper acceptance per-owner quota; run-wide stays at 99.9%.
    owner_required_per_thousand = 995 if phase in ("W1", "W2", "W3") else 999
    prices: list[tuple[int, datetime]] = []
    facts: dict[str, list[tuple[int, datetime]]] = {str(owner): [] for owner in owners}
    fault_windows = []
    fault_path = output / "fault-windows.jsonl"
    if fault_path.exists():
        for line in fault_path.read_text().splitlines():
            window = json.loads(line)
            fault_windows.append(
                (datetime.fromisoformat(window["start"]), datetime.fromisoformat(window["end"]))
            )
    for line in (output / "inputs.jsonl").read_text().splitlines():
        row = json.loads(line)
        if not row["measured"]:
            continue
        point = (int(row["cursor"]), datetime.fromisoformat(row["ready_at"]))
        if any(start <= point[1] <= end for start, end in fault_windows):
            continue
        if row["kind"] == "PRICE":
            prices.append(point)
        else:
            facts[row["owner"]].append(point)
    for points in facts.values():
        points.sort()
    indexes = {str(owner): [0, 0] for owner in owners}
    busy = busy_intervals(output)
    idle = {str(owner): {"expected": 0, "acknowledged": 0} for owner in owners}
    for owner in idle:
        idle[owner]["expected"] = sum(
            not any(a <= at.timestamp() < b for a, b in busy.get(owner, [])) for _, at in prices
        )
    counts = misses = target_misses = clock_errors = service_misses = 0
    owner_counts = {str(owner): {"samples": 0, "service_misses": 0} for owner in owners}
    maximum = 0.0
    histogram: dict[int, int] = {}
    failures: list[dict[str, object]] = []
    streams = [path.open() for path in output.glob("*.risk.jsonl")]
    late_stream = (output / "risk-late-inputs.jsonl").open("w")
    try:
        merged = heapq.merge(
            *(map(json.loads, stream) for stream in streams),
            key=lambda row: row["committed_observed_at"],
        )
        for ack in merged:
            owner = ack["owner"]
            if owner not in indexes or ack["pending"]:
                continue
            observed = datetime.fromisoformat(ack["committed_observed_at"])
            for kind, points, through in (
                (0, prices, ack["cursor"]),
                (1, facts[owner], ack["boundary"]),
            ):
                index = indexes[owner][kind]
                while index < len(points) and points[index][0] <= through:
                    identity, ready = points[index]
                    # Only acknowledgements after the input's actual commit qualify.
                    if observed < ready:
                        clock_errors += 1
                        break
                    seconds = (observed - ready).total_seconds()
                    maximum = max(maximum, seconds)
                    counts += 1
                    if kind == 0 and not any(
                        a <= ready.timestamp() < b for a, b in busy.get(owner, [])
                    ):
                        idle[owner]["acknowledged"] += 1
                    owner_counts[owner]["samples"] += 1
                    bucket = min(5001, int(seconds * 1000))
                    histogram[bucket] = histogram.get(bucket, 0) + 1
                    if seconds > 1:
                        target_misses += 1
                    if seconds > 3:
                        service_misses += 1
                        owner_counts[owner]["service_misses"] += 1
                        late_stream.write(
                            json.dumps(
                                {
                                    "owner": owner,
                                    "kind": kind,
                                    "input": identity,
                                    "ready_at": ready.isoformat(),
                                    "commit_observed_at": observed.isoformat(),
                                    "seconds": seconds,
                                }
                            )
                            + "\n"
                        )
                    if seconds > 5:
                        misses += 1
                        if len(failures) < 20:
                            failures.append(
                                {
                                    "owner": owner,
                                    "kind": kind,
                                    "input": identity,
                                    "ready_at": ready.isoformat(),
                                    "commit_observed_at": observed.isoformat(),
                                    "seconds": seconds,
                                }
                            )
                    index += 1
                indexes[owner][kind] = index
    finally:
        late_stream.close()
        for stream in streams:
            stream.close()
    expected = len(prices) * len(owners) + sum(len(points) for points in facts.values())
    for owner, values in owner_counts.items():
        total = len(prices) + len(facts[owner])
        values["expected"] = total
        values["passed"] = (
            total > 0
            and values["samples"] == total
            and (total - values["service_misses"]) * 1000 >= total * owner_required_per_thousand
        )
    service_passed = (expected - service_misses) * 1000 >= expected * 999
    return {
        "samples": counts,
        "expected": expected,
        "hard_limit_seconds": 5,
        "service_limit_seconds": 3,
        "idle_owner_coverage": idle,
        "idle_coverage_complete": (output / "cycle-timing.jsonl").exists()
        and (output / "scheduled-resets.jsonl").exists()
        and set(busy) == set(idle)
        and all(
            row["expected"] > 0 and row["acknowledged"] == row["expected"] for row in idle.values()
        ),
        "minimum_service_fraction": "0.999",
        "minimum_owner_service_fraction": f"0.{owner_required_per_thousand}",
        "phase": phase,
        "service_miss_count": service_misses,
        "service_passed": service_passed,
        "owners": owner_counts,
        "late_inputs_path": "risk-late-inputs.jsonl",
        "target_seconds": 1,
        "target_miss_count": target_misses,
        "miss_count": misses,
        "unacknowledged": expected - counts,
        "clock_errors": clock_errors,
        "max_seconds": maximum,
        "histogram_milliseconds": histogram,
        "first_misses": failures,
        "passed": counts == expected
        and counts > 0
        and misses == 0
        and clock_errors == 0
        and service_passed
        and all(value["passed"] for value in owner_counts.values()),
    }


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


def guard_release_database() -> None:
    targets = set()
    for role in ("API", "ENGINE", "ENGINE_SCAN", "MIGRATOR", "MARKET_DATA", "AUTH"):
        url = urlparse(os.environ.get(f"TIEWTRADE_DATABASE_URL_{role}", ""))
        if url.hostname not in {"localhost", "127.0.0.1", "::1"} or not url.path.startswith(
            "/tiewtrade_f18_release"
        ):
            raise RuntimeError("F18_ISOLATED_RELEASE_DATABASE_REQUIRED")
        targets.add((url.hostname, url.port, url.path))
    if len(targets) != 1:
        raise RuntimeError("F18_ISOLATED_RELEASE_DATABASE_REQUIRED")


def source_manifest() -> dict[str, object]:
    root = Path(__file__).resolve().parents[4]
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    digest = hashlib.sha256()
    files = sorted(
        path
        for directory in ("backend/src", "backend/migrations", "backend/tests")
        for path in (root / directory).rglob("*.py")
        if "__pycache__" not in path.parts
    )
    files.extend(
        root / name for name in ("backend/uv.lock", "backend/pyproject.toml", "compose.yaml")
    )
    for path in files:
        digest.update(str(path.relative_to(root)).encode() + b"\0" + path.read_bytes() + b"\0")
    return {
        "source_commit": commit,
        "acceptance_revision": "R25+R26+R27-A+R28+R29+R30+R32+R33+R34",
        "source_target_hz": SOURCE_HZ,
        "source_tree_sha256": digest.hexdigest(),
        "source_files": len(files),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "host_logical_cpus": os.cpu_count(),
        "market_fixture_sha256": f15.CAPABILITY_VERSION,
        "prefer_same_pair_admission": PREFER_SAME_PAIR_ADMISSION,
        "alternate_admission_priority": ALTERNATE_ADMISSION_PRIORITY,
        "source_resumption": SOURCE_RESUMPTION,
        "fixture_publication": "R31 shared native source loops; bounded source pool3/parent12",
        "worker_round_limits": {
            "manual": {"candidates": CANDIDATE_LIMIT, "claims": CLAIM_LIMIT},
            "matching": {"candidates": CANDIDATE_LIMIT, "claims": CLAIM_LIMIT},
        },
        "risk_pools": {"monitor": 4, "request": 1, "stop": 2, "scan": 3, "overflow": 0},
    }


async def run(args: argparse.Namespace) -> int:
    guard_release_database()
    output: Path = args.output
    output.mkdir(parents=True, exist_ok=False)
    fixture = Fixture(output)
    fixture.publisher_mode = getattr(args, "publisher_mode", "inline")
    fixture.source_diagnostic = getattr(args, "source_diagnostic_seconds", None) is not None
    fixture.publisher_link.trace = fixture.source_diagnostic
    if fixture.source_diagnostic and fixture.publisher_mode == "inline":
        fixture.source_timeline = SourceTimeline(
            output, fixture.source_market, observe_backend=True
        )
    fixture.dispatch_trace = getattr(args, "dispatch_diagnostic_seconds", None) is not None
    fixture.bounded_saturation = args.phase == "W2" and not fixture.dispatch_trace
    fixture.baseline_orders = 2 if args.phase == "CHECK" else 20
    owner_count = 2 if args.phase == "CHECK" else 100
    workers = 2 if args.phase == "CHECK" else 10
    duration, rate = DURATION[args.phase], RATE[args.phase]
    cycles = 1 if args.phase == "CHECK" else duration * rate // (owner_count * 5)
    run_id = uuid4()
    counters = f15.Counters()
    latencies: list[float] = []
    resources: list[dict[str, object]] = []
    sampler_stop = asyncio.Event()
    sampler = None
    fault_task = None
    fault_events: list[f15.FaultEvent] = []
    reset_progress = ResetProgress(0)
    saturation: SaturationProgress | None = None
    slots = []
    gate = None
    fault_observations: list[dict[str, object]] = []
    process_lock = asyncio.Lock()
    original_submit, original_cycle = f15.submit_new, f15.cycle
    manifest = {
        **source_manifest(),
        "profile": PROFILE,
        "phase": args.phase,
        "duration_seconds": duration,
        "owners": owner_count,
        "baseline_orders": fixture.baseline_orders,
        "rate": rate,
        "setup_refusal_retry_seconds": f15.RESULT_POLL_SECONDS,
        "measured_refusal_retry_seconds": 0.02,
        "setup_result_poll_seconds": f15.RESULT_POLL_SECONDS,
        "measured_result_poll_seconds": f15.RESULT_POLL_SECONDS,
        "refusal_backpressure": "read-only READY hint; full fresh policy recheck before intake",
        "workers": workers,
        "run_id": str(run_id),
        "started_at": datetime.now(UTC).isoformat(),
        "acceptance_result": False,
        "source_diagnostic_seconds": getattr(args, "source_diagnostic_seconds", None),
        "publisher_mode": fixture.publisher_mode,
        "memory_diagnostic_seconds": getattr(args, "memory_diagnostic_seconds", None),
        "dispatch_diagnostic_seconds": getattr(args, "dispatch_diagnostic_seconds", None),
    }
    try:
        if args.phase == "W3":
            if not args.redis_container or not args.redis_container.startswith(
                "tiewtrade-f18-release"
            ):
                raise RuntimeError("F18_W3_REQUIRES_ISOLATED_REDIS_CONTAINER")
            fault_file = Path(__file__).with_name("w3_fault_schedule.json")
            events, cycles, digest = f15.load_fault_schedule(fault_file)
            fault_events = events
            manifest.update(
                fault_schedule=[asdict(event) for event in events],
                fault_schedule_digest=digest,
                additional_faults=(
                    "monitor restarts with Paper workers; 12s price gap on connection churn"
                ),
            )
        async with fixture.migrator.connect() as connection:
            tracked: str = (
                await connection.execute(text("SHOW track_commit_timestamp"))
            ).scalar_one()
        if tracked != "on":
            raise RuntimeError("F18_COMMIT_TIMESTAMPS_REQUIRED")
        manifest["database"] = await f15.database_manifest(fixture.migrator)
        f15.save(output / "manifest.json", manifest)
        async with fixture.migrator.begin() as connection:
            await connection.execute(
                text("""UPDATE risk_protocol_control SET
              publication_enabled=true,financial_enabled=true,admission_enabled=true""")
            )
        fixture.owners = await f15.seed_owners(
            fixture.api, fixture.engine, fixture.scan, owner_count
        )
        manifest["dataset"] = [
            {
                "owner": str(owner.user_id),
                "wallet": str(owner.wallet.wallet_id),
                "episode": str(owner.wallet.episode_id),
                "initial_capital": owner.wallet.initial_capital.as_parts(),
            }
            for owner in fixture.owners
        ]
        manifest["dataset_sha256"] = hashlib.sha256(
            json.dumps(
                {
                    "dataset": manifest["dataset"],
                    "run_id": str(run_id),
                    "baseline_orders": fixture.baseline_orders,
                    "market_fixture": f15.CAPABILITY_VERSION,
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()
        fixture.selected = fixture.owners[0].user_id
        if fixture.bounded_saturation:
            slots = demand_slots([owner.user_id for owner in fixture.owners], cycles, rate)
            saturation = SaturationProgress([owner.user_id for owner in fixture.owners], len(slots))
            f15.save(output / "w2-demand-plan.json", [asdict(slot) for slot in slots])
            manifest["w2_profile"] = "R28_CLIENT_BOUNDED_SATURATION"
            manifest["w2_planned_slots"] = len(slots)
            manifest["w2_planned_logical_commands"] = len(slots) * 5
            manifest["w2_demand_plan_sha256"] = hashlib.sha256(
                (output / "w2-demand-plan.json").read_bytes()
            ).hexdigest()
            manifest["server_100_requests_per_second_certified"] = False
        reset_plan = (
            []
            if args.phase == "CHECK"
            else reset_schedule(
                [owner.user_id for owner in fixture.owners],
                selected=fixture.selected,
                run_id=run_id,
                faults=fault_events,
            )
        )
        reset_progress = ResetProgress(len(reset_plan))
        manifest["selected_post_scenario_limit"] = "1000"
        manifest["scheduled_resets"] = [asdict(item) for item in reset_plan]
        manifest["scheduled_resets_sha256"] = hashlib.sha256(
            json.dumps(manifest["scheduled_resets"], default=str, sort_keys=True).encode()
        ).hexdigest()
        manifest["scheduled_reset_mode"] = (
            "omitted-nonaccepting-CHECK" if args.phase == "CHECK" else "R27"
        )
        f15.save(output / "manifest.json", manifest)
        for owner in fixture.owners:
            async with user_session(fixture.api, owner.user_id) as session:
                await session.execute(
                    "INSERT INTO user_trading_preferences(user_id,use) VALUES(:owner,'MANUAL')",
                    {"owner": owner.user_id},
                )
        fixture.publisher = asyncio.create_task(fixture.publish())
        await fixture.spawn("risk")
        async with asyncio.timeout(20):
            while (
                fixture.publisher_stats.get("published", 0) < 2
                or fixture.publisher_stats.get("price_published", 0) < 2
            ):
                if fixture.publisher.done():
                    await fixture.publisher
                await asyncio.sleep(0.02)
        for owner in fixture.owners:
            await fixture.mutation(
                owner, RiskAction.SET, "10" if owner.user_id == fixture.selected else "1000"
            )
            await fixture.mutation(owner, RiskAction.RESET)
        await fixture.mutation(fixture.owners[0], RiskAction.DECREASE, "5")
        for number in range(workers):
            await fixture.spawn(f"paper-{number}")
        f15.submit_new, f15.cycle = fixture.new, fixture.cycle
        await f15.with_publisher(
            f15.seed_baseline(fixture.engine, fixture.owners, run_id, fixture.baseline_orders),
            fixture.publisher,
        )
        sampler = asyncio.create_task(
            f15.resource_sampler(
                fixture.migrator,
                fixture.market,
                fixture.sampled_processes,
                process_lock,
                sampler_stop,
                resources,
                evidence_path=output / "resources.json",
            )
        )
        await fixture.source_control(ask_quantity="0.5")
        # Begin measurement only after the required partial-fill liquidity is
        # committed. An in-flight publisher may still hold the prior depth.
        async with asyncio.timeout(10):
            while fixture.publisher_stats.get("last_ask_quantity") != "0.5":
                if fixture.publisher.done():
                    await fixture.publisher
                    raise RuntimeError("F18_PARTIAL_FIXTURE_PUBLICATION_STOPPED")
                await asyncio.sleep(0.01)
        budget = await connection_budget(
            fixture.migrator,
            [
                fixture.pools.path,
                output / "publisher.pools.json",
                *(path.with_suffix(".pools.json") for path in fixture.metrics),
            ],
            expected_counts=[
                6,
                1,
                *(4 if path.name.startswith("risk-") else 2 for path in fixture.metrics),
            ],
        )
        manifest["connection_budget"] = budget
        f15.save(output / "manifest.json", manifest)
        await fixture.source_control(started=True)
        load_anchor = fixture.phases.begin_load(duration)
        started = float(load_anchor["monotonic"])
        await fixture.source_control(trace_start=started)
        if fixture.dispatch_trace:
            f15.save(
                output / "dispatch-trace-control.json",
                {
                    "started": started,
                    "owners": [str(owner.user_id) for owner in fixture.owners[1:6]],
                    "sample_cycles": [0],
                    "detail_scope": "sampled owners; first-cycle subset joined offline",
                },
            )
        if args.phase == "W3":
            gate = f15.FaultGate()
            generation = 0

            async def restart_workers() -> None:
                nonlocal generation
                async with process_lock:
                    await f15.stop_worker_processes(fixture.processes, fixture.stop)
                    if any(process.returncode != 0 for process in fixture.processes):
                        raise RuntimeError("F18_RESTART_WORKER_EXIT_FAILED")
                    fixture.processes.clear()
                    fixture.stop.unlink()
                    generation += 1
                    await fixture.spawn("risk", generation)
                    for number in range(workers):
                        await fixture.spawn(f"paper-{number}", generation)

            async def churn_connections() -> None:
                suspension = datetime.now(UTC)
                fixture.price_suspensions.append((suspension, suspension + timedelta(seconds=12)))
                await fixture.source_control(suspend_prices_until=monotonic() + 12)
                await asyncio.gather(
                    fixture.dispose_source_connections(),
                    *(
                        engine.dispose()
                        for engine in (fixture.engine, fixture.scan, fixture.api, fixture.market)
                    ),
                )

            def fault_transition(observation: dict[str, object]) -> None:
                f15.save(output / "fault-observations.json", fault_observations)
                with (output / "fault-windows.jsonl").open("w") as stream:
                    for row in fault_observations:
                        if "ended_at" in row:
                            stream.write(
                                json.dumps(
                                    {
                                        "start": row["started_at"],
                                        "end": row["ended_at"],
                                        "kind": row["kind"],
                                    }
                                )
                                + "\n"
                            )

            async def fault_recovery(observation: dict[str, object]) -> None:
                assert fixture.publisher is not None
                observation["recovery_baseline"] = await f15.with_publisher(
                    fixture.live_baseline(
                        int(fixture.publisher_stats["last_input_id"]),
                        float(str(observation["restored"])) + 60,
                    ),
                    fixture.publisher,
                )

            async def faults() -> None:
                await f15.run_fault_schedule(
                    events,
                    gate,
                    redis_container=args.redis_container,
                    restart_workers=restart_workers,
                    churn_connections=churn_connections,
                    observations=fault_observations,
                    on_transition=fault_transition,
                    recover=fault_recovery,
                )
                # Persist actual declared fault phases; never reclassify a non-fault miss.
                f15.save(output / "fault-observations.json", fault_observations)
                with (output / "fault-windows.jsonl").open("w") as stream:
                    for observation in fault_observations:
                        stream.write(
                            json.dumps(
                                {
                                    "start": observation["started_at"],
                                    "end": observation["ended_at"],
                                    "kind": observation["kind"],
                                }
                            )
                            + "\n"
                        )

            fault_task = asyncio.create_task(faults())
        owners_by_id = {owner.user_id: owner for owner in fixture.owners}

        async def scheduled_reset(owner_id: UUID, key: UUID) -> UUID:
            return await fixture.mutation(
                owners_by_id[owner_id], RiskAction.RESET, idempotency_key=key
            )

        async def saturated_cycle(owner_id: UUID, number: int) -> None:
            owner = owners_by_id[owner_id]
            async with fixture.cycle_scope(owner, number):
                await fixture.cycle(fixture.engine, owner, run_id, number, counters, latencies)

        cycles_operation = (
            run_saturation(
                slots,
                started=started,
                duration=duration,
                drain=60,
                operation=saturated_cycle,
                progress=saturation,
                path=output / "w2-slots.jsonl",
            )
            if saturation is not None
            else f15.run_scheduled_cycles(
                fixture.engine,
                fixture.owners,
                run_id,
                cycles,
                rate,
                counters,
                latencies,
                gate,
                cycle_scope=fixture.cycle_scope,
            )
        )
        scheduled = run_scheduled_work(
            cycles_operation,
            run_resets(
                reset_plan,
                started=started,
                recovery_complete=fixture.recovery_complete,
                apply=scheduled_reset,
                path=output / "scheduled-resets.jsonl",
                progress=reset_progress,
                gate=gate,
            ),
            fault_task,
        )
        diagnostic_seconds = getattr(args, "memory_diagnostic_seconds", None) or getattr(
            args, "dispatch_diagnostic_seconds", None
        )
        diagnostic_seconds = diagnostic_seconds or getattr(args, "source_diagnostic_seconds", None)
        if diagnostic_seconds is not None:
            await f15.with_publisher(
                diagnostic_window(scheduled, diagnostic_seconds), fixture.publisher
            )
            f15.save(
                output / "diagnostic.json",
                {
                    "status": "WINDOW_COMPLETE",
                    "acceptance_result": False,
                    "elapsed_seconds": monotonic() - started,
                    "counters": asdict(counters),
                    "scheduled_resets_not_exercised": True,
                },
            )
            return 0
        async with asyncio.timeout_at(started + duration + 60):
            await f15.with_publisher(scheduled, fixture.publisher)

        await f15.with_publisher(
            asyncio.sleep(max(0, started + duration - monotonic())), fixture.publisher
        )
        fixture.phases.mark("drain")
        live_baseline = await f15.with_publisher(
            fixture.live_baseline(
                int(fixture.publisher_stats["last_input_id"]), started + duration + 60
            ),
            fixture.publisher,
        )
        elapsed = monotonic() - started
        fixture.stop_market.set()
        await fixture.publisher
        fixture.publisher = None
        await fixture.final_risk_drain()
        overflow: OverflowResult | None = None
        if args.phase == "W2":
            await fixture.source_control(started=False)
            overflow_started = monotonic()
            fixture.phases.mark("verification", operation="before_overflow")
            before_overflow = await f15.economic_snapshot(fixture.engine, fixture.owners)
            injection = fixture.phases.mark("injection")
            recovered_input = await f15.publish_overflow(fixture.market)
            recovery = fixture.phases.mark("recovery", captured_watermark=recovered_input)
            fixture.stop_market.clear()
            fixture.publisher = asyncio.create_task(fixture.publish())
            live_baseline = await f15.with_publisher(
                fixture.live_baseline(recovered_input, float(recovery["monotonic"]) + 60),
                fixture.publisher,
            )
            verification = fixture.phases.mark("verification", operation="after_overflow")
            fixture.stop_market.set()
            await fixture.publisher
            fixture.publisher = None
            await fixture.final_risk_drain()
            after_overflow = await f15.economic_snapshot(fixture.engine, fixture.owners)
            timing = overflow_timings(
                before=overflow_started,
                injection=float(injection["monotonic"]),
                recovery=float(recovery["monotonic"]),
                recovered=float(verification["monotonic"]),
                finished=monotonic(),
            )
            overflow = {
                "inputs": 4097,
                "injection_seconds": timing["injection_seconds"],
                "recovery_seconds": timing["recovery_seconds"],
                "verification_seconds": timing["verification_seconds"],
                "total_seconds": timing["total_seconds"],
                "live_baseline": live_baseline,
                "economics_unchanged": before_overflow == after_overflow,
            }
        fixture.phases.mark("shutdown")
        assert fixture.phases.load_start is not None and fixture.phases.load_end is not None
        cadence = cadence_summary(
            output / "source-commits.jsonl",
            start=fixture.phases.load_start,
            end=fixture.phases.load_end,
            price_suspensions=fixture.price_suspensions,
            missing_commit_allowance=int(args.phase in ("W1", "W2", "W3")),
        )
        measured_book_inputs = cadence["channels"]["BOOK:BTC/USDT"]["count"]
        sampler_stop.set()
        await sampler
        sampler = None
        await f15.stop_worker_processes(fixture.processes, fixture.stop)
        cycle_counts = saturation.counts if saturation is not None else None
        observations = await f15.verify(
            fixture.engine,
            fixture.owners,
            baseline_orders=fixture.baseline_orders,
            cycles_per_owner=cycles,
            extra_cancels=fixture.extra_cancels,
            cycle_counts=cycle_counts,
        )
        invariants = await f15.verify_global_invariants(
            fixture.engine,
            fixture.owners,
            baseline_orders=fixture.baseline_orders,
            cycles_per_owner=cycles,
            extra_cancels=sum(fixture.extra_cancels.values()),
            extra_fills=fixture.extra_fills,
            cycle_counts=cycle_counts,
        )
        identities_passed = (
            (
                await verify_identities(
                    fixture.engine,
                    fixture.owners,
                    run_id,
                    saturation,
                    fixture.baseline_orders,
                    fixture.extra_cancels,
                    output / "w2-identities.json",
                )
            )
            if saturation is not None
            else True
        )
        metric = measured_transaction_seconds(
            fixture.metrics,
            started=started,
            ended=started + elapsed,
            excluded=[
                (float(str(row["started"])), float(str(row["restored"])))
                for row in fault_observations
            ],
        )
        resource_summary = f15.summarize_resources(resources)
        sla = sla_summary(output, [owner.user_id for owner in fixture.owners], phase=args.phase)
        expected_cycles = (
            sum(cycle_counts.values()) if cycle_counts is not None else owner_count * cycles
        )
        expected = expected_cycles * 5
        saturation_summary = saturation.summary() if saturation is not None else None
        saturation_passed = saturation is None or (
            saturation_summary is not None
            and saturation.planned == 6000
            and duration == 300
            and rate == 100
            and owner_count == 100
            and saturation_summary["conserved"]
            and saturation_summary["all_started_complete"]
            and expected_cycles >= 600
            and all(n >= 1 for n in saturation.counts.values())
            and saturation.peak_active <= owner_count
        )
        endurance = (
            f15.endurance_rss(
                resources, duration_seconds=duration, measured_start=fixture.phases.load_start
            )
            if args.phase == "W3"
            else None
        )
        await fixture.close()
        connection_cleanup = await cleanup_connections()
        pools_returned = returned_pools(
            [
                fixture.pools.path,
                output / "publisher.pools.json",
                *(path.with_suffix(".pools.json") for path in fixture.metrics),
            ],
            budget,
        )
        resource_passed = (
            f15.integer(resource_summary["peak_process_rss_bytes"]) <= f15.MAX_WORKER_RSS_BYTES
            and f15.integer(resource_summary["lock_waits_end"]) == 0
            and live_baseline["passed"]
            and all(f15.integer(sample["connections"]) <= budget["limit"] for sample in resources)
            and pools_returned
            and connection_cleanup["passed"]
            and (endurance is None or endurance["passed"])
        )
        passed = (
            fixture.selected_limit_restore is not None
            and saturation_passed
            and identities_passed
            and reset_progress.passed
            and counters.offered == expected
            and counters.admitted == expected
            and counters.completed == expected
            and counters.rejected == 0
            and counters.cycles == expected_cycles
            and counters.fills == expected_cycles * 2
            and counters.cancels == expected_cycles
            and counters.replays == expected_cycles
            and elapsed >= duration
            and elapsed <= duration + 60
            and f15.percentile(metric, 0.95) <= 0.500
            and f15.percentile(metric, 0.99) <= 1
            and all(row["passed"] for row in observations)
            and invariants["passed"]
            and sla["passed"]
            and (
                args.phase != "W3"
                or (
                    sla["idle_coverage_complete"]
                    and len(fault_observations) == len(events)
                    and all(row["status"] == "RECOVERED" for row in fault_observations)
                )
            )
            and resource_passed
            and len(fixture.scenarios) == 3
            and cadence["passed"]
            and all(process.returncode == 0 for process in fixture.processes)
            and (
                overflow is None
                or (
                    overflow["economics_unchanged"] is True
                    and float(overflow["recovery_seconds"]) <= 60
                )
            )
        )
        result = {
            **manifest,
            "status": "PASSED" if passed else "FAILED",
            "smoke_only": args.phase == "CHECK",
            "acceptance_result": passed and args.phase != "CHECK",
            "elapsed_seconds": elapsed,
            "source_cadence": cadence,
            "live_baseline": live_baseline,
            "shutdown_input_lag": invariants["input_lag"],
            "measured_book_inputs": measured_book_inputs,
            "required_book_inputs": duration * SOURCE_HZ,
            "counters": asdict(counters),
            "scheduled_reset_counters": asdict(reset_progress),
            "scheduled_reset_passed": reset_progress.passed,
            "w2_saturation": saturation_summary,
            "w2_actual_logical_rates": (
                {
                    "scope": "logical harness operations including replay; not incoming HTTP",
                    "seconds_including_drain": elapsed,
                    "offered_per_second": counters.offered / elapsed,
                    "admitted_counter_per_second": counters.admitted / elapsed,
                    "completed_per_second": counters.completed / elapsed,
                }
                if saturation is not None
                else None
            ),
            "w2_saturation_passed": bool(saturation_passed) if saturation is not None else None,
            "exact_identities_passed": identities_passed if saturation is not None else None,
            "risk_sla": sla,
            "owners": observations,
            "global_invariants": invariants,
            "overflow": overflow,
            "scenarios": fixture.scenarios,
            "selected_limit_restore_request": fixture.selected_limit_restore,
            "engine_transaction_seconds": {
                "p95": f15.percentile(metric, 0.95),
                "p99": f15.percentile(metric, 0.99),
                "max": max(metric),
            },
            "resources": resource_summary,
            "resource_assertions_passed": resource_passed,
            "connection_cleanup": connection_cleanup,
            "pools_returned": pools_returned,
            "publisher": fixture.publisher_stats,
            "fault_transaction_seconds": [
                seconds
                for row in fault_observations
                for seconds in measured_transaction_seconds(
                    fixture.metrics,
                    started=float(str(row["started"])),
                    ended=float(str(row["restored"])),
                )
            ],
            "all_transaction_seconds": measured_transaction_seconds(
                fixture.metrics, started=started, ended=started + elapsed
            ),
            "fault_observations": fault_observations,
            "endurance_rss": endurance,
        }
        f15.save(output / "resources.json", resources)
        f15.save(output / "result.json", result)
        return 0 if passed else 1
    except BaseException as error:
        f15.save(output / "resources.json", resources)
        f15.save(output / "fault-observations.json", fault_observations)
        fixture.phases.mark("failure", error_type=type(error).__name__)
        f15.save(
            output / "failure.json",
            {
                "status": "FAILED",
                "acceptance_result": False,
                "w2_saturation": saturation.summary() if saturation is not None else None,
                "last_live_baseline": fixture.last_live_baseline,
                "error_type": type(error).__name__,
                "error": str(error),
                "counters": asdict(counters),
                "scheduled_reset_counters": asdict(reset_progress),
                "scenarios": fixture.scenarios,
                "selected_limit_restore_request": fixture.selected_limit_restore,
            },
        )
        raise
    finally:
        f15.submit_new, f15.cycle = original_submit, original_cycle
        sampler_stop.set()
        if fault_task is not None and not fault_task.done():
            fault_task.cancel()
            await asyncio.gather(fault_task, return_exceptions=True)
        if sampler is not None:
            sampler.cancel()
            await asyncio.gather(sampler, return_exceptions=True)
        await fixture.close()


async def run_memory_diagnostic(args: argparse.Namespace) -> int:
    # Evidence is adjacent because run() exclusively creates its output directory.
    stop = asyncio.Event()
    observer = asyncio.create_task(sample_memory(args.output.with_suffix(".memory.jsonl"), stop))
    try:
        return await f15.with_publisher(run(args), observer)
    finally:
        stop.set()
        await observer


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=tuple(DURATION))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--worker")
    parser.add_argument("--stop", type=Path)
    parser.add_argument("--metrics", type=Path)
    parser.add_argument("--redis-container")
    parser.add_argument("--memory-diagnostic-seconds", type=int, choices=(60,))
    parser.add_argument("--dispatch-diagnostic-seconds", type=int, choices=(60,))
    parser.add_argument("--source-diagnostic-seconds", type=int, choices=(60,))
    parser.add_argument("--publisher-mode", choices=("inline", "child"), default="inline")
    parser.add_argument("--dispatch-trace", action="store_true")
    args = parser.parse_args()
    if args.worker:
        if args.stop is None or args.metrics is None:
            parser.error("worker requires stop and metrics")
        return asyncio.run(worker(args))
    if args.phase is None or args.output is None:
        parser.error("phase and output are required")
    if args.dispatch_trace:
        parser.error("dispatch-trace is worker-only")
    if args.source_diagnostic_seconds is not None:
        if args.phase != "W2" or args.memory_diagnostic_seconds or args.dispatch_diagnostic_seconds:
            parser.error("source diagnostic requires W2 alone; never acceptance")
        return asyncio.run(run_memory_diagnostic(args))
    if args.dispatch_diagnostic_seconds is not None:
        if args.phase != "W2" or args.memory_diagnostic_seconds is not None:
            parser.error("dispatch diagnostic requires W2 without memory diagnostic")
        return asyncio.run(run(args))
    if args.memory_diagnostic_seconds is not None:
        if args.phase != "W1":
            parser.error("memory diagnostic uses W1 dataset/rates only; never acceptance")
        return asyncio.run(run_memory_diagnostic(args))
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
