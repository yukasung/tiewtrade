"""F-19 W4 fixtures and recovery oracles using the existing durable stop workers."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market import profile_restore as restore
from tests.infra.execution_market import profile_workload as f15
from tests.infra.risk_limits.profile_stop_runtime import PlatformStopScheduleRunner
from tests.infra.risk_limits.profile_stop_schedule import build_stop_schedule
from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.orders import TradingMode
from tiewtrade.core.trading_stops import StopAction
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.paper_wallet import get_wallet
from tiewtrade.infra.trading_stops import receipt_by_id, submit_request
from tiewtrade.services.engine.kill_switch import (
    run_platform_discovery_round,
    run_stop_request_round,
)
from tiewtrade.services.engine.risk_limit import run_risk_stop_round

if TYPE_CHECKING:
    from tests.infra.risk_limits.profile_workload import Fixture

STOP_TABLES = (
    "trading_stop_requests",
    "trading_stop_results",
    "trading_stop_events",
    "trading_stop_causes",
    "trading_stop_dispatch",
    "platform_stop_progress",
    "platform_stop_targets",
    "trading_reconciliation_clock",
    "platform_memberships",
)


async def financial_snapshot(
    api: AsyncEngine,
    admin: AsyncEngine,
) -> tuple[dict[str, Money], dict[str, tuple[Money, Quantity, str]]]:
    async with admin.connect() as connection:
        owners: list[UUID] = list(
            (
                await connection.execute(
                    text("SELECT user_id FROM paper_wallet_state ORDER BY user_id")
                )
            ).scalars()
        )
        rows = (
            await connection.execute(
                text(
                    "SELECT r.order_id,r.quote_reserved,r.base_reserved,o.base,p.status "
                    "FROM paper_reservations r JOIN paper_orders o ON o.id=r.order_id "
                    "JOIN paper_order_projections p ON p.order_id=r.order_id"
                )
            )
        ).all()
    balances = {}
    for owner in owners:
        async with user_session(api, owner) as session:
            wallet = await get_wallet(session)
            if wallet is None:
                raise RuntimeError("F19_W4_WALLET_MISSING")
            balances[str(owner)] = wallet.balance
    reservations = {
        str(row.order_id): (
            Money.of(row.quote_reserved, "USDT"),
            Quantity.of(row.base_reserved, row.base),
            row.status,
        )
        for row in rows
    }
    return balances, reservations


async def stage(fixture: Fixture, output: Path) -> dict[str, Any]:
    owners = fixture.owners[:2]
    if len(owners) != 2 or any(p.returncode is None for p in fixture.processes):
        raise RuntimeError("F19_W4_REQUIRES_TWO_OWNERS_AND_STOPPED_WORKERS")
    runner = PlatformStopScheduleRunner(
        api_engine=fixture.api,
        migrator_engine=fixture.migrator,
        schedule=build_stop_schedule("W3", [o.user_id for o in owners]),
        owners=owners,
        journal=output / "operator-setup.jsonl",
        gate=f15.FaultGate(),
    )
    await runner.install_operator()
    receipts: list[dict[str, Any]] = []
    for platform in (False, True):
        key = uuid4()
        async with user_session(fixture.api, owners[0].user_id) as session:
            receipt = await submit_request(
                session,
                mode=None if platform else TradingMode.PAPER,
                action=StopAction.STOP,
                key=key,
                reason_code="W4_STOP_RECOVERY",
                reason_text="W4 platform recovery" if platform else None,
                platform=platform,
            )
        receipts.append(
            {
                "owner": str(owners[0].user_id),
                "key": str(key),
                "platform": platform,
                "request_id": str(receipt.request_id),
                "stop_id": str(receipt.stop_id),
                "revision": receipt.revision,
            }
        )
    identity = uuid4()
    async with user_session(fixture.engine, owners[1].user_id, role=DatabaseRole.ENGINE) as session:
        # Same engine-owned SYSTEM ingress fixture as trading_stops/test_storage.py.
        await session.execute(
            """INSERT INTO trading_stop_requests
            (id,user_id,scope_owner_id,mode,action,cause,actor_role,idempotency_key,
             fingerprint,reason_code,generation)
            VALUES(:id,:owner,:owner,'PAPER','STOP','SYSTEM','SYSTEM',:id,
              repeat('0',64),'SOURCE_STOP',1)""",
            {"id": identity, "owner": owners[1].user_id},
        )
        await session.execute(
            "INSERT INTO trading_stop_dispatch(request_id,user_id) VALUES(:id,:owner)",
            {"id": identity, "owner": owners[1].user_id},
        )
    for _ in range(3):
        await run_stop_request_round(engine=fixture.engine, scan_engine=fixture.scan)
    await run_platform_discovery_round(engine=fixture.engine, scan_engine=fixture.scan, limit=1)
    async with user_session(fixture.api, owners[0].user_id) as session:
        progress = (
            await session.execute(
                "SELECT cursor,owner_count,discovery_complete FROM platform_stop_progress "
                "WHERE stop_id=:id",
                {"id": UUID(receipts[1]["stop_id"])},
            )
        ).one()
        if progress.cursor is None or progress.owner_count != 1 or progress.discovery_complete:
            raise RuntimeError("F19_W4_REQUIRES_PARTIAL_DISCOVERY")
    return {"requests": receipts, "system_request": str(identity), "cursor": str(progress.cursor)}


async def verify(
    fixture: dict[str, Any],
    engines: dict[DatabaseRole, AsyncEngine],
    admin: AsyncEngine,
    output: Path,
) -> None:
    api, engine, scan = (
        engines[r] for r in (DatabaseRole.API, DatabaseRole.ENGINE, DatabaseRole.ENGINE_SCAN)
    )
    before = await restore.economic_digest(admin)
    balances_before, reservations_before = await financial_snapshot(api, admin)
    requests = fixture["requests"]
    operator = UUID(requests[1]["owner"])
    platform_id = UUID(requests[1]["stop_id"])
    authorities = [UUID(item["request_id"]) for item in requests] + [
        UUID(fixture["system_request"])
    ]
    for item in requests:
        async with user_session(api, UUID(item["owner"])) as session:
            replay = await submit_request(
                session,
                mode=None if item["platform"] else TradingMode.PAPER,
                action=StopAction.STOP,
                key=UUID(item["key"]),
                reason_code="W4_STOP_RECOVERY",
                reason_text="W4 platform recovery" if item["platform"] else None,
                platform=item["platform"],
            )
            if str(replay.request_id) != item["request_id"]:
                raise RuntimeError("F19_W4_REPLAY_CREATED_NEW_REQUEST")
    async with asyncio.timeout(30):
        while True:
            await run_stop_request_round(engine=engine, scan_engine=scan)
            await run_platform_discovery_round(engine=engine, scan_engine=scan)
            await run_risk_stop_round(engine=engine, scan_engine=scan, limit=100)
            await run_platform_discovery_round(engine=engine, scan_engine=scan)
            async with user_session(api, operator) as session:
                progress = (
                    await session.execute(
                        """SELECT p.*,c.revision AS clock_revision FROM platform_stop_progress p
                    CROSS JOIN trading_reconciliation_clock c
                    WHERE p.stop_id=:id AND c.singleton""",
                        {"id": platform_id},
                    )
                ).one()
            if progress.discovery_complete and progress.pending_count == progress.failed_count == 0:
                async with admin.connect() as connection:
                    unfinished: int = (
                        await connection.execute(
                            text(
                                "SELECT count(*) FROM risk_stop_requests j "
                                "JOIN risk_stop_progress p ON p.stop_id=j.id "
                                "WHERE j.authority_request_id=ANY(:ids) "
                                "AND (NOT p.target_set_complete "
                                "OR p.pending_count<>0 OR p.failed_count<>0)"
                            ),
                            {"ids": authorities},
                        )
                    ).scalar_one()
                if unfinished:
                    await asyncio.sleep(0.02)
                    continue
                if progress.reconciliation_revision != progress.clock_revision:
                    raise RuntimeError("F19_W4_RECONCILIATION_CLOCK_MISMATCH")
                break
            await asyncio.sleep(0.02)
    async with user_session(api, operator) as session:
        stale = await submit_request(
            session,
            mode=None,
            action=StopAction.RESUME,
            key=uuid4(),
            expected_stop_id=platform_id,
            expected_revision=requests[1]["revision"],
            expected_summary_revision=progress.revision,
            expected_reconciliation_revision=progress.reconciliation_revision - 1,
            reason_code="W4_STALE_SNAPSHOT",
            platform=True,
        )
    await run_stop_request_round(engine=engine, scan_engine=scan)
    async with user_session(api, operator) as session:
        rejected = await receipt_by_id(session, stale.request_id)
        if (
            rejected is None
            or rejected.state != "REJECTED"
            or rejected.failure_code != "TRADING_STOP_NOT_READY"
        ):
            raise RuntimeError("F19_W4_STALE_RESUME_NOT_REJECTED")
    async with admin.connect() as connection:
        causes: set[str] = set(
            (
                await connection.execute(text("SELECT cause FROM trading_stop_causes WHERE active"))
            ).scalars()
        )
        if not {"USER", "SYSTEM", "PLATFORM"} <= causes:
            raise RuntimeError("F19_W4_ACTIVE_CAUSE_LOST")
        duplicates: int = (
            await connection.execute(
                text(
                    "SELECT count(*) FROM (SELECT request_id FROM trading_stop_events "
                    "GROUP BY request_id HAVING count(*)>1) d"
                )
            )
        ).scalar_one()
        if duplicates:
            raise RuntimeError("F19_W4_DUPLICATE_EFFECT")
        for authority_id in authorities:
            events: int = (
                await connection.execute(
                    text("SELECT count(*) FROM trading_stop_events WHERE request_id=:id"),
                    {"id": authority_id},
                )
            ).scalar_one()
            if events != 1:
                raise RuntimeError("F19_W4_AUTHORITY_EVENT_MISSING_OR_DUPLICATED")
    if await restore.economic_digest(admin) != before:
        raise RuntimeError("F19_W4_RECOVERY_CHANGED_ECONOMICS")
    balances_after, reservations_after = await financial_snapshot(api, admin)
    if balances_before != balances_after or reservations_before.keys() != reservations_after.keys():
        raise RuntimeError("F19_W4_RECOVERY_CHANGED_BALANCE_OR_RESERVATION_INVENTORY")
    for identity, (quote, base, status) in reservations_after.items():
        if status == "CANCELED":
            if quote != Money.of(0, "USDT") or base != Quantity.of(0, base.asset):
                raise RuntimeError("F19_W4_CANCELED_RESERVATION_NOT_RELEASED")
        elif (quote, base) != reservations_before[identity][:2]:
            raise RuntimeError("F19_W4_UNSELECTED_RESERVATION_CHANGED")
    f15.save(
        output / "stop-recovery.json",
        {
            "status": "PASSED",
            "active_causes": sorted(causes),
            "exact_key_recovery": True,
            "pending_discovery_completed": True,
            "stale_resume_rejected": True,
            "economic_digest_unchanged": True,
            "balances_unchanged": True,
            "only_canceled_reservations_released": True,
        },
    )
