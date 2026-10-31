"""Owner-scoped F-19 workload schedule using the real durable inbox and worker."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from pathlib import Path
from time import monotonic
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market.profile_workload import FaultGate, OwnerState
from tests.infra.risk_limits.profile_stop_schedule import StopSchedule
from tiewtrade.core.orders import TradingMode
from tiewtrade.core.trading_stops import StopAction
from tiewtrade.infra.db import user_session
from tiewtrade.infra.paper_orders.views import request_view
from tiewtrade.infra.trading_stops import (
    read_status,
    receipt_by_id,
    receipt_by_key,
    submit_request,
)
from tiewtrade.infra.trading_stops.records import StopReceipt, StopStatus

PostCutoffProbe = Callable[[OwnerState], Awaitable[dict[str, object]]]
PrepareQueued = Callable[[OwnerState], Awaitable[UUID]]
PreparePartial = Callable[[OwnerState], Awaitable[dict[str, object]]]
FinishPartial = Callable[[OwnerState], Awaitable[None]]
PlatformBlockedProbe = Callable[[OwnerState], Awaitable[dict[str, object]]]
BotRearm = Callable[[OwnerState], Awaitable[dict[str, object]]]


class UserStopScheduleRunner:
    def __init__(
        self,
        *,
        api_engine: AsyncEngine,
        schedule: StopSchedule,
        owners: list[OwnerState],
        journal: Path,
        offset_scale: float = 1,
    ) -> None:
        if schedule.phase not in {"W1", "W2"}:
            raise ValueError("user stop runner supports W1 and W2 only")
        if tuple(owner.user_id for owner in owners) != schedule.owners:
            raise ValueError("runtime owners do not match the immutable schedule")
        if not 0 < offset_scale <= 1:
            raise ValueError("stop schedule offset scale must be in (0,1]")
        self.api_engine = api_engine
        self.schedule = schedule
        self.owners = owners
        self.journal = journal
        self.offset_scale = offset_scale
        self.stops: dict[UUID, StopReceipt] = {}

    def _key(self, owner: UUID, label: str) -> UUID:
        return uuid5(
            NAMESPACE_URL,
            f"tiewtrade:f19:set5:{self.schedule.digest()}:{owner}:{label}",
        )

    def _record(self, action: str, owner: UUID, **details: object) -> None:
        with self.journal.open("a", encoding="utf-8") as stream:
            stream.write(
                json.dumps(
                    {"action": action, "owner": str(owner), **details},
                    sort_keys=True,
                    default=str,
                )
                + "\n"
            )

    async def _at(self, started: float, offset: int) -> None:
        await asyncio.sleep(max(0, started + offset * self.offset_scale - monotonic()))

    async def _stop(self, owner: OwnerState, label: str) -> StopReceipt:
        key = self._key(owner.user_id, label)
        async with user_session(self.api_engine, owner.user_id) as session:
            receipt = await submit_request(
                session,
                mode=TradingMode.PAPER,
                action=StopAction.STOP,
                key=key,
                reason_code="SET5_VALIDATION",
            )
        self.stops[owner.user_id] = receipt
        self._record(
            "STOP_SUBMITTED",
            owner.user_id,
            request_id=receipt.request_id,
            stop_id=receipt.stop_id,
            generation=receipt.generation,
            revision=receipt.revision,
            key=key,
        )
        return receipt

    async def _status(self, owner: OwnerState) -> StopStatus:
        async with user_session(self.api_engine, owner.user_id) as session:
            return await read_status(session, TradingMode.PAPER)

    async def _terminal(self, owner: OwnerState, request: UUID) -> StopReceipt:
        async with asyncio.timeout(90):
            while True:
                async with user_session(self.api_engine, owner.user_id) as session:
                    receipt = await receipt_by_id(session, request)
                if receipt is not None and receipt.state != "REQUEST_PENDING":
                    return receipt
                await asyncio.sleep(0.02)

    async def _ready(self, owner: OwnerState) -> StopStatus:
        async with asyncio.timeout(90):
            while True:
                status = await self._status(owner)
                if status.resume_ready:
                    return status
                await asyncio.sleep(0.02)

    async def _resume(
        self,
        owner: OwnerState,
        *,
        effects_complete: FinishPartial | None = None,
    ) -> StopReceipt:
        stop = self.stops[owner.user_id]
        status = await self._ready(owner)
        if effects_complete is not None:
            await effects_complete(owner)
        if status.stop_id != stop.stop_id or status.reconciliation_revision is None:
            raise RuntimeError("F19_SET5_RESUME_SNAPSHOT_CHANGED")
        async with user_session(self.api_engine, owner.user_id) as session:
            receipt = await submit_request(
                session,
                mode=TradingMode.PAPER,
                action=StopAction.RESUME,
                key=self._key(owner.user_id, f"resume-{stop.generation}"),
                expected_stop_id=stop.stop_id,
                expected_revision=stop.revision,
                expected_summary_revision=status.summary_revision,
                expected_reconciliation_revision=status.reconciliation_revision,
                reason_code="SET5_VALIDATION_RESUME",
            )
        terminal = await self._terminal(owner, receipt.request_id)
        if terminal.state != "APPLIED":
            raise RuntimeError(f"F19_SET5_RESUME_REJECTED:{terminal.failure_code}")
        current = await self._status(owner)
        if current.stop_id is not None:
            raise RuntimeError("F19_SET5_RESUME_DID_NOT_CLOSE_EXPECTED_STOP")
        self._record(
            "RESUME_APPLIED",
            owner.user_id,
            request_id=receipt.request_id,
            stop_id=stop.stop_id,
            generation=stop.generation,
        )
        return terminal

    async def _duplicate(self, owner: OwnerState) -> None:
        original = self.stops[owner.user_id]
        async with user_session(self.api_engine, owner.user_id) as session:
            duplicate = await submit_request(
                session,
                mode=TradingMode.PAPER,
                action=StopAction.STOP,
                key=original.idempotency_key,
                reason_code="SET5_VALIDATION",
            )
        if duplicate.request_id != original.request_id:
            raise RuntimeError("F19_SET5_DUPLICATE_CREATED_NEW_STOP")
        self._record("EXACT_DUPLICATE_RECOVERED", owner.user_id, request_id=original.request_id)

    async def _lookup_lost_ack(self, owner: OwnerState) -> None:
        original = self.stops[owner.user_id]
        async with user_session(self.api_engine, owner.user_id) as session:
            recovered = await receipt_by_key(
                session,
                mode=TradingMode.PAPER,
                action=StopAction.STOP,
                key=original.idempotency_key,
            )
        if recovered is None or recovered.request_id != original.request_id:
            raise RuntimeError("F19_SET5_LOST_ACK_LOOKUP_MISMATCH")
        self._record("LOST_ACK_RECOVERED", owner.user_id, request_id=original.request_id)

    async def _stale_resume(self, owner: OwnerState) -> None:
        stop = self.stops[owner.user_id]
        status = await self._ready(owner)
        if status.reconciliation_revision is None:
            raise RuntimeError("F19_SET5_STALE_RESUME_MISSING_RECONCILIATION")
        async with user_session(self.api_engine, owner.user_id) as session:
            stale = await submit_request(
                session,
                mode=TradingMode.PAPER,
                action=StopAction.RESUME,
                key=self._key(owner.user_id, "stale-resume"),
                expected_stop_id=stop.stop_id,
                expected_revision=stop.revision,
                expected_summary_revision=status.summary_revision + 1,
                expected_reconciliation_revision=status.reconciliation_revision,
                reason_code="SET5_VALIDATION_STALE_RESUME",
            )
        terminal = await self._terminal(owner, stale.request_id)
        if terminal.state != "REJECTED":
            raise RuntimeError("F19_SET5_STALE_RESUME_WAS_NOT_REJECTED")
        self._record(
            "STALE_RESUME_REJECTED",
            owner.user_id,
            request_id=stale.request_id,
            failure_code=terminal.failure_code,
        )

    async def _queued_rejected(self, owner: OwnerState, request_id: UUID) -> None:
        async with asyncio.timeout(90):
            while True:
                async with user_session(self.api_engine, owner.user_id) as session:
                    view = await request_view(session, request_id)
                if view is not None and (
                    view.intake_state == "REJECTED" or view.command_state == "REJECTED"
                ):
                    failure = view.intake_failure_code or view.command_failure_code
                    if failure != "ORDER_SAFETY_UNAVAILABLE":
                        raise RuntimeError(f"F19_SET5_QUEUED_REJECTION_MISMATCH:{failure}")
                    self._record(
                        "QUEUED_MANUAL_REJECTED",
                        owner.user_id,
                        request_id=request_id,
                        failure_code=failure,
                    )
                    return
                await asyncio.sleep(0.02)

    async def run(
        self,
        *,
        started: float,
        post_cutoff_probe: PostCutoffProbe,
        prepare_queued: PrepareQueued | None = None,
        prepare_partial: PreparePartial | None = None,
        finish_partial: FinishPartial | None = None,
    ) -> None:
        if self.schedule.phase == "W1":
            if prepare_queued is None or prepare_partial is None or finish_partial is None:
                raise ValueError("W1 stop schedule requires queued and partial preparation/cleanup")
            await self._at(started, 50)
            queued_request = await prepare_queued(self.owners[0])
            self._record(
                "QUEUED_MANUAL_PREPARED",
                self.owners[0].user_id,
                request_id=queued_request,
            )
            await self._at(started, 60)
            await self._stop(self.owners[0], "first-stop")
            await self._queued_rejected(self.owners[0], queued_request)
            await self._at(started, 90)
            probe = await post_cutoff_probe(self.owners[0])
            self._record("POST_CUTOFF_MANUAL", self.owners[0].user_id, **probe)
            await self._at(started, 110)
            partial = await prepare_partial(self.owners[1])
            if partial.get("partially_filled") is not True:
                raise RuntimeError("F19_SET5_PARTIAL_ORDER_WAS_NOT_PREPARED")
            self._record("PARTIAL_BOT_PREPARED", self.owners[1].user_id, **partial)
            await self._at(started, 120)
            first, second = await asyncio.gather(
                self._stop(self.owners[0], "repeated-stop"),
                self._stop(self.owners[1], "partial-stop"),
            )
            if first.generation <= 1 or second.generation != 1:
                raise RuntimeError("F19_SET5_STOP_GENERATION_MISMATCH")
            await self._at(started, 150)
            await self._resume(self.owners[1], effects_complete=finish_partial)
            manual_status = await self._status(self.owners[0])
            if (
                manual_status.stop_id != first.stop_id
                or manual_status.generation != first.generation
            ):
                raise RuntimeError("F19_SET5_MANUAL_STOP_DID_NOT_REMAIN_ACTIVE")
            self._record(
                "MANUAL_STOP_REMAINS_ACTIVE",
                self.owners[0].user_id,
                stop_id=first.stop_id,
                generation=first.generation,
            )
            return

        await self._at(started, 30)
        await asyncio.gather(*(self._stop(owner, "concurrent-stop") for owner in self.owners))
        await asyncio.gather(*(self._duplicate(owner) for owner in self.owners[:3]))
        await asyncio.gather(*(self._lookup_lost_ack(owner) for owner in self.owners[3:6]))
        await self._at(started, 60)
        await asyncio.gather(*(self._stale_resume(owner) for owner in self.owners[6:8]))
        await self._at(started, 90)
        await asyncio.gather(*(self._resume(owner) for owner in self.owners))


class PlatformStopScheduleRunner:
    def __init__(
        self,
        *,
        api_engine: AsyncEngine,
        migrator_engine: AsyncEngine,
        schedule: StopSchedule,
        owners: list[OwnerState],
        journal: Path,
        gate: FaultGate,
        offset_scale: float = 1,
    ) -> None:
        if schedule.phase != "W3":
            raise ValueError("platform stop runner supports W3 only")
        if tuple(owner.user_id for owner in owners) != schedule.owners:
            raise ValueError("runtime owners do not match the immutable schedule")
        if not 0 < offset_scale <= 1:
            raise ValueError("stop schedule offset scale must be in (0,1]")
        self.api_engine = api_engine
        self.migrator_engine = migrator_engine
        self.schedule = schedule
        self.owners = owners
        self.journal = journal
        self.gate = gate
        self.offset_scale = offset_scale
        self.blocked_count = 0

    def _key(self, label: str) -> UUID:
        return uuid5(
            NAMESPACE_URL,
            f"tiewtrade:f19:set5:{self.schedule.digest()}:platform:{label}",
        )

    def _record(self, action: str, **details: object) -> None:
        with self.journal.open("a", encoding="utf-8") as stream:
            stream.write(
                json.dumps({"action": action, **details}, sort_keys=True, default=str) + "\n"
            )

    async def _at(self, started: float, offset: int) -> None:
        await asyncio.sleep(max(0, started + offset * self.offset_scale - monotonic()))

    async def install_operator(self) -> None:
        owner = self.owners[0].user_id
        async with self.migrator_engine.begin() as connection:
            await connection.execute(
                text("ALTER TABLE platform_memberships NO FORCE ROW LEVEL SECURITY")
            )
            try:
                await connection.execute(
                    text(
                        """INSERT INTO platform_memberships(user_id,role)
                        VALUES(:owner,'PLATFORM_OWNER') ON CONFLICT(user_id) DO UPDATE
                        SET role='PLATFORM_OWNER'"""
                    ),
                    {"owner": owner},
                )
            finally:
                await connection.execute(
                    text("ALTER TABLE platform_memberships FORCE ROW LEVEL SECURITY")
                )

    async def _terminal(self, request: UUID) -> StopReceipt:
        operator = self.owners[0]
        async with asyncio.timeout(90):
            while True:
                async with user_session(self.api_engine, operator.user_id) as session:
                    receipt = await receipt_by_id(session, request)
                if receipt is not None and receipt.state != "REQUEST_PENDING":
                    return receipt
                await asyncio.sleep(0.02)

    async def _stop(self, label: str) -> StopReceipt:
        operator = self.owners[0]
        async with user_session(self.api_engine, operator.user_id) as session:
            receipt = await submit_request(
                session,
                mode=None,
                action=StopAction.STOP,
                key=self._key(label),
                reason_code="SET5_PLATFORM_VALIDATION",
                reason_text=f"set-5 {label}",
                platform=True,
            )
        terminal = await self._terminal(receipt.request_id)
        if terminal.state != "APPLIED":
            raise RuntimeError(f"F19_SET5_PLATFORM_STOP_REJECTED:{terminal.failure_code}")
        self._record(
            "PLATFORM_STOP_APPLIED",
            request_id=receipt.request_id,
            stop_id=receipt.stop_id,
            generation=receipt.generation,
        )
        return receipt

    async def _progress(self, stop: StopReceipt) -> Any:
        operator = self.owners[0]
        async with user_session(self.api_engine, operator.user_id) as session:
            return (
                await session.execute(
                    """SELECT p.discovery_complete,p.pending_count,p.failed_count,p.revision,
                      c.revision reconciliation_revision
                    FROM platform_stop_progress p CROSS JOIN trading_reconciliation_clock c
                    WHERE p.stop_id=:stop AND c.singleton""",
                    {"stop": stop.stop_id},
                )
            ).one()

    async def _ready(self, stop: StopReceipt) -> Any:
        async with asyncio.timeout(120):
            while True:
                progress = await self._progress(stop)
                if (
                    progress.discovery_complete
                    and progress.pending_count == 0
                    and progress.failed_count == 0
                ):
                    return progress
                await asyncio.sleep(0.05)

    async def _resume(self, stop: StopReceipt, label: str) -> None:
        progress = await self._ready(stop)
        operator = self.owners[0]
        async with user_session(self.api_engine, operator.user_id) as session:
            receipt = await submit_request(
                session,
                mode=None,
                action=StopAction.RESUME,
                key=self._key(f"resume-{label}"),
                expected_stop_id=stop.stop_id,
                expected_revision=stop.revision,
                expected_summary_revision=int(progress.revision),
                expected_reconciliation_revision=int(progress.reconciliation_revision),
                reason_code="SET5_PLATFORM_RESUME",
                platform=True,
            )
        terminal = await self._terminal(receipt.request_id)
        if terminal.state != "APPLIED":
            raise RuntimeError(f"F19_SET5_PLATFORM_RESUME_REJECTED:{terminal.failure_code}")
        self._record("PLATFORM_RESUME_APPLIED", request_id=receipt.request_id, stop_id=stop.stop_id)

    async def _install_cancel_fault(self) -> None:
        owner = self.owners[1].user_id
        async with self.migrator_engine.begin() as connection:
            await connection.execute(
                text(
                    f"""CREATE FUNCTION f19_set5_cancel_fault() RETURNS trigger
                    LANGUAGE plpgsql AS $$ BEGIN
                      IF NEW.user_id='{owner}'::uuid AND NEW.action='CANCEL' THEN
                        RAISE EXCEPTION 'injected set-5 cancel fault';
                      END IF;
                      RETURN NEW;
                    END $$"""
                )
            )
            await connection.execute(
                text(
                    """CREATE TRIGGER f19_set5_cancel_fault BEFORE INSERT ON paper_order_commands
                    FOR EACH ROW EXECUTE FUNCTION f19_set5_cancel_fault()"""
                )
            )

    async def _remove_cancel_fault(self) -> None:
        async with self.migrator_engine.begin() as connection:
            await connection.execute(
                text("DROP TRIGGER IF EXISTS f19_set5_cancel_fault ON paper_order_commands")
            )
            await connection.execute(text("DROP FUNCTION IF EXISTS f19_set5_cancel_fault()"))

    async def _wait_alert(self, stop: StopReceipt) -> None:
        alert_owner = self.owners[1]
        async with asyncio.timeout(90):
            while True:
                async with user_session(self.api_engine, alert_owner.user_id) as session:
                    row = (
                        await session.execute(
                            """SELECT p.alert_due,p.failed_count FROM platform_stop_targets t
                            JOIN risk_stop_progress p ON p.stop_id=t.risk_stop_id
                            WHERE t.stop_id=:stop AND t.user_id=:owner""",
                            {"stop": stop.stop_id, "owner": alert_owner.user_id},
                        )
                    ).one_or_none()
                if row is not None and row.alert_due and row.failed_count > 0:
                    self._record(
                        "CANCEL_ALERT_DUE",
                        stop_id=stop.stop_id,
                        owner=alert_owner.user_id,
                        failed_count=row.failed_count,
                    )
                    return
                await asyncio.sleep(0.05)

    async def _window(
        self,
        *,
        started: float,
        start_offset: int,
        resume_offset: int,
        label: str,
        blocked_probe: PlatformBlockedProbe,
        inject_cancel_fault: bool,
    ) -> None:
        await self._at(started, start_offset)
        held_at = monotonic()
        await self.gate.pause()
        async with asyncio.timeout(60):
            while self.gate.active:
                await asyncio.sleep(0.01)
        if inject_cancel_fault:
            await self._install_cancel_fault()
        try:
            stop = await self._stop(label)
            probe = await blocked_probe(self.owners[0])
            if probe.get("blocked") is not True:
                raise RuntimeError("F19_SET5_PLATFORM_PROBE_WAS_NOT_BLOCKED")
            self.blocked_count += 1
            self._record("PLATFORM_OPENING_BLOCKED", stop_id=stop.stop_id, **probe)
            if inject_cancel_fault:
                await self._at(started, start_offset + 61)
                await self._wait_alert(stop)
                await self._remove_cancel_fault()
            await self._at(started, resume_offset)
            await self._resume(stop, label)
        finally:
            await self._remove_cancel_fault()
            self.gate.resume(monotonic() - held_at)

    async def run(
        self,
        *,
        started: float,
        blocked_probe: PlatformBlockedProbe,
        bot_rearm: BotRearm,
    ) -> None:
        await self._window(
            started=started,
            start_offset=210,
            resume_offset=285,
            label="worker-restart-window",
            blocked_probe=blocked_probe,
            inject_cancel_fault=False,
        )
        await self._at(started, 600)
        rearmed = await bot_rearm(self.owners[1])
        if rearmed.get("accepted") is not True:
            raise RuntimeError("F19_SET5_BOT_REARM_WAS_NOT_ACCEPTED")
        self._record("BOT_ORDER_REARMED", owner=self.owners[1].user_id, **rearmed)
        await self._window(
            started=started,
            start_offset=660,
            resume_offset=750,
            label="redis-alert-window",
            blocked_probe=blocked_probe,
            inject_cancel_fault=True,
        )
