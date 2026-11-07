"""NC12 controlled protection case, sharing F17 fixtures and the real worker runtime."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from collections.abc import Iterator
from contextlib import AsyncExitStack, contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from tests.infra.execution_market import profile_internal as internal
from tests.infra.execution_market import profile_workload as f15
from tests.infra.execution_market.profile_parent_poll import ParentPollGate
from tests.infra.execution_market.profile_restore import replay_owner_domain
from tests.infra.protections.test_lifecycle import buy
from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.positions import PositionPair
from tiewtrade.core.protections import ProtectionState, TriggerEvidence
from tiewtrade.infra.db import DatabaseRole, create_engine_for, user_session
from tiewtrade.infra.db.session import UserSession
from tiewtrade.infra.paper_wallet import get_wallet
from tiewtrade.infra.positions.views import held_and_reserved
from tiewtrade.infra.protections import worker
from tiewtrade.infra.protections.storage import load


@contextmanager
def observe_processing(path: Path) -> Iterator[None]:
    """Same post-lock upper-bound observation as F17 test_validation, per process."""
    original = worker.market_evidence
    seen: set[UUID] = set()

    async def observed(session: UserSession, pair: PositionPair) -> TriggerEvidence:
        evidence = await original(session, pair)
        if evidence.price == Money.of(111, "USDT") and session.user_id not in seen:
            started = (await session.execute("SELECT clock_timestamp()")).scalar_one()
            with path.open("a", encoding="utf-8") as stream:
                stream.write(
                    json.dumps(
                        {
                            "owner": str(session.user_id),
                            "started": started.isoformat(),
                            "ready": evidence.received_at.isoformat(),
                            "sequence": evidence.sequence,
                            "generation": evidence.generation,
                            "source": str(evidence.source_id),
                        }
                    )
                    + "\n"
                )
            seen.add(session.user_id)
        return evidence

    worker.market_evidence = observed
    try:
        yield
    finally:
        worker.market_evidence = original


def processing_verdict(
    paths: list[Path], owners: list[f15.OwnerState], ready: datetime
) -> dict[str, Any]:
    first: dict[str, datetime] = {}
    for path in paths:
        if path.exists():
            for line in path.read_text().splitlines():
                row = json.loads(line)
                started = datetime.fromisoformat(row["started"])
                if datetime.fromisoformat(row["ready"]) >= ready:
                    owner = row["owner"]
                    first[owner] = min(first.get(owner, started), started)
    delays = {
        str(owner.user_id): (first[str(owner.user_id)] - ready).total_seconds()
        if str(owner.user_id) in first
        else None
        for owner in owners
    }
    return {
        "owners": delays,
        "expected": len(owners),
        "observed": sum(v is not None for v in delays.values()),
        "passed": all(v is not None and 0 <= v <= 1 for v in delays.values()),
    }


async def verify_exit(
    engine: Any, owner: f15.OwnerState, group_id: UUID, *, baseline_orders: int = 0
) -> None:
    # Exact values and immutable-event checks from the existing F17 crash/retry fixture.
    async with user_session(engine, owner.user_id, role=DatabaseRole.ENGINE) as session:
        current = await load(session, group_id)
        cash = await get_wallet(session)
        assert current is not None and current.value.state is ProtectionState.CLOSED
        assert current.value.quantity == Quantity.of(0, "BTC")
        assert current.disposed == Quantity.of("0.999", "BTC")
        assert cash is not None and cash.balance == Money.of("9998.802099", "USDT")
        held, reserved = await held_and_reserved(session, owner.wallet.episode_id, f15.PAIR)
        assert held == reserved == Quantity.of(0, "BTC")
        resting = (
            await session.execute(
                """SELECT count(*) orders,coalesce(sum(r.quote_reserved),0) reserved
                FROM paper_order_projections p JOIN paper_reservations r USING(order_id)
                WHERE p.episode_id=:episode AND p.status='ACCEPTED'""",
                {"episode": owner.wallet.episode_id},
            )
        ).one()
        assert resting.orders == baseline_orders
        assert Money.of(resting.reserved, "USDT") == Money.of(baseline_orders, "USDT")
        assert (
            await session.execute(
                "SELECT count(*) FROM paper_execution_links WHERE episode_id=:id",
                {"id": owner.wallet.episode_id},
            )
        ).scalar_one() == 2
        assert (
            await session.execute(
                "SELECT count(*) FROM paper_protection_exits WHERE protection_id=:id",
                {"id": group_id},
            )
        ).scalar_one() == 1
        assert (
            await session.execute(
                """SELECT count(*) FROM audit_events WHERE owner_user_id=:owner
          AND action='PROTECTION_EVENT' AND details->>'kind'='FILL'
          AND details->>'protection_id'=:id""",
                {"owner": owner.user_id, "id": str(group_id)},
            )
        ).scalar_one() == 2
        revision = current.value.revision
        await worker.process_group(session, group_id)
        replayed = await load(session, group_id)
        assert replayed is not None and replayed.value.revision == revision
    await replay_owner_domain(
        engine,
        user_id=owner.user_id,
        wallet_id=owner.wallet.wallet_id,
        episode_id=owner.wallet.episode_id,
        active=True,
    )


async def run(output: Path) -> int:
    internal.guard_database(dict(os.environ))
    await internal.require_empty_database()
    output.mkdir(parents=True, exist_ok=False)
    engines = {
        role: create_engine_for(role)
        for role in (
            DatabaseRole.API,
            DatabaseRole.ENGINE,
            DatabaseRole.ENGINE_SCAN,
            DatabaseRole.MIGRATOR,
            DatabaseRole.MARKET_DATA,
        )
    }
    api, engine, scan, admin, market = engines.values()
    poll_gate = ParentPollGate(stream_path=output / "parent-poll-attempts.jsonl")
    stop = asyncio.Event()
    publisher = None
    processes: list[asyncio.subprocess.Process] = []
    worker_stop = None
    stack = AsyncExitStack()
    started = datetime.now(UTC)
    try:
        poll_gate.verify_pool(engine)
        await stack.enter_async_context(internal.activated_protocols(admin, protections=True))
        owners = await f15.seed_owners(api, engine, scan, 20)
        f15.save(
            output / "owners.json",
            [
                {
                    "owner": str(owner.user_id),
                    "wallet": str(owner.wallet.wallet_id),
                    "episode": str(owner.wallet.episode_id),
                }
                for owner in owners
            ],
        )
        groups = []
        for owner in owners:
            source, _, _, _, group = await buy(api, engine, scan, owner.user_id, owner.wallet)
            groups.append(group)
            await source.dispose()
        stats: dict[str, Any] = {"target_hz": 10}
        publisher = asyncio.create_task(
            f15.market_publisher(market, stop, stats, heartbeat_per_book=True)
        )
        await f15.wait_publisher_ready(publisher, stats)
        processes, worker_stop, metrics = await f15.start_worker_processes(
            20,
            output,
            r8_claim_budget=True,
            coordinate_claims=True,
            acceptance_profile=internal.NAME,
        )
        await f15.with_publisher(
            f15.seed_baseline(engine, owners, uuid4(), 20, poll_gate=poll_gate), publisher
        )
        # Pause only the fixture publisher. Workers and the 400 baseline orders stay active.
        stop.set()
        await publisher
        stop = asyncio.Event()
        poll_gate.phase = "trigger"
        trigger_stats: dict[str, Any] = {"target_hz": 10}
        publisher = asyncio.create_task(
            f15.market_publisher(
                market,
                stop,
                trigger_stats,
                heartbeat_per_book=True,
                price_amount=Money.of(111, "USDT"),
            )
        )

        async def completed() -> None:
            async with asyncio.timeout(60):
                for owner, group in zip(owners, groups, strict=True):
                    while True:
                        async with f15.poll_session(
                            engine, owner.user_id, "protection_closed", poll_gate
                        ) as session:
                            current = await load(session, group)
                        if current is not None and current.value.state is ProtectionState.CLOSED:
                            break
                        await asyncio.sleep(0.05)

        await f15.with_publisher(completed(), publisher)
        await f15.stop_worker_processes(processes, worker_stop)
        for owner, group in zip(owners, groups, strict=True):
            await verify_exit(engine, owner, group, baseline_orders=20)
        timing = processing_verdict(
            [path.with_suffix(".protection.jsonl") for path in metrics],
            owners,
            datetime.fromisoformat(trigger_stats["first_input_ready"]),
        )
        failures = f15.worker_process_failures(processes)
        f15.save(
            output / "result.json",
            {
                "status": "PASSED" if timing["passed"] and not failures else "FAILED",
                "profile": internal.NAME,
                "timing": timing,
                "financial": "PASSED",
                "worker_failures": failures,
                "baseline_orders": 400,
                "groups": [str(value) for value in groups],
                "started": started,
            },
        )
        return 0 if timing["passed"] and not failures else 1
    except BaseException as error:
        f15.save(output / "failure.json", {"error_type": type(error).__name__, "started": started})
        raise
    finally:
        stop.set()
        if publisher is not None:
            if not publisher.done():
                publisher.cancel()
            await asyncio.gather(publisher, return_exceptions=True)
        if processes and worker_stop is not None:
            await f15.stop_worker_processes(processes, worker_stop)
        await stack.aclose()
        for resource in engines.values():
            await resource.dispose()
        poll_gate.save(output / "parent-poll-gate.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args.output)))
