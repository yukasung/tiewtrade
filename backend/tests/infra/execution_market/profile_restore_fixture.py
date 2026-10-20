"""Build the real financial/history fixture required by the F-15 W4 restore profile."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from tests.infra.execution_market.profile_workload import (
    Counters,
    OwnerState,
    baseline,
    cycle,
    identity,
    market_buy,
    market_publisher,
    seed_owners,
    start_worker_processes,
    stop_worker_processes,
    submit_new,
)
from tiewtrade.core.orders import OrderStatus, standard_execution_fee
from tiewtrade.core.positions import ExecutionFact
from tiewtrade.infra.db import DatabaseRole, create_engine_for, user_session
from tiewtrade.infra.db.session import scan_session_bypassing_rls
from tiewtrade.infra.paper_orders.codec import execution_from_payload
from tiewtrade.infra.paper_orders.corrections import correct_fill
from tiewtrade.infra.paper_orders.dispatch import claim_order, due_orders
from tiewtrade.infra.paper_wallet import PaperWalletAction, admit_command, get_wallet
from tiewtrade.infra.positions import PositionEventKind
from tiewtrade.services.engine.paper_wallet import run_paper_wallet_round


def save(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, default=str, indent=2) + "\n", encoding="utf-8")


async def apply_partial_correction(engine: AsyncEngine, owner: OwnerState, run_id: UUID) -> None:
    user_id = owner.user_id
    wallet = owner.wallet
    order_id = identity(run_id, user_id, 0, "buy-order")
    async with user_session(engine, user_id, role=DatabaseRole.ENGINE) as session:
        linked = (
            (
                await session.execute(
                    """SELECT l.position_event_id,l.order_event_id,e.payload
                    FROM paper_execution_links l JOIN paper_order_events e
                      ON e.id=l.order_event_id
                    WHERE l.order_id=:order AND l.position_event_kind='RECORD'""",
                    {"order": order_id},
                )
            )
            .mappings()
            .one()
        )
        original = execution_from_payload(linked["payload"]["execution"])
        quantity = original.gross_quantity.__class__.of("0.5", "BTC")
        quote = original.quote_amount.__class__.of("50", "USDT")
        replacement = ExecutionFact(
            original.execution_id,
            original.pair,
            original.side,
            quantity,
            quote,
            standard_execution_fee(original.side, quantity, quote),
            original.source_sequence,
            original.occurred_at,
        )
        await correct_fill(
            session,
            wallet_id=wallet.wallet_id,
            episode_id=wallet.episode_id,
            order_event_id=linked["order_event_id"],
            correction_event_id=uuid4(),
            supersedes_position_event_id=linked["position_event_id"],
            kind=PositionEventKind.REPLACE,
            fact=replacement,
        )


async def reset_owner(
    api: AsyncEngine, engine: AsyncEngine, scan: AsyncEngine, owner: OwnerState
) -> None:
    async with user_session(api, owner.user_id) as session:
        wallet = await get_wallet(session)
        if wallet is None or not wallet.reset_available:
            raise RuntimeError("F15_W4_RESET_FIXTURE_NOT_READY")
        command = await admit_command(
            session,
            action=PaperWalletAction.RESET,
            idempotency_key=uuid4(),
            capital_text="10000",
            expected_episode_id=wallet.episode_id,
        )
    result = await run_paper_wallet_round(engine=engine, scan_engine=scan, worker="f15-w4-reset")
    if result.processed != 1:
        raise RuntimeError(f"F15_W4_RESET_FIXTURE_FAILED:{command.command_id}")


async def stage_expired_claim(
    engine: AsyncEngine, scan: AsyncEngine, owner: OwnerState, admin_url: str
) -> None:
    async with scan_session_bypassing_rls(scan) as session:
        due = next(value for value in await due_orders(session) if value.user_id == owner.user_id)
    async with user_session(engine, owner.user_id, role=DatabaseRole.ENGINE) as session:
        claim = await claim_order(session, due, worker="f15-w4-crashed-worker")
    if claim is None:
        raise RuntimeError("F15_W4_CLAIM_FIXTURE_FAILED")
    admin = create_async_engine(admin_url, hide_parameters=True)
    try:
        async with admin.begin() as connection:
            await connection.exec_driver_sql(
                """UPDATE paper_order_dispatch
                SET lease_until=clock_timestamp()-interval '1 second'
                WHERE command_id=$1""",
                (claim.command_id,),
            )
    finally:
        await admin.dispose()


async def run(args: argparse.Namespace) -> None:
    output: Path = args.output
    output.mkdir(parents=True, exist_ok=False)
    api = create_engine_for(DatabaseRole.API)
    engine = create_engine_for(DatabaseRole.ENGINE)
    scan = create_engine_for(DatabaseRole.ENGINE_SCAN)
    market = create_engine_for(DatabaseRole.MARKET_DATA)
    stop = asyncio.Event()
    publisher_stats: dict[str, Any] = {"target_hz": 10}
    publisher = asyncio.create_task(market_publisher(market, stop, publisher_stats))
    workers: list[asyncio.subprocess.Process] = []
    worker_stop: Path | None = None
    run_id = uuid4()
    counters = Counters()
    latencies: list[float] = []
    try:
        async with asyncio.timeout(5):
            while int(publisher_stats.get("published", 0)) < 2:
                await asyncio.sleep(0.01)
        owners = await seed_owners(api, engine, scan, 3)
        workers, worker_stop, _ = await start_worker_processes(1, output)
        buy = market_buy(owners[0], run_id, 0)
        await submit_new(engine, owners[0], buy, OrderStatus.FILLED, counters, latencies)
        counters.fills += 1
        await apply_partial_correction(engine, owners[0], run_id)
        await cycle(engine, owners[1], run_id, 0, counters, latencies)
        await reset_owner(api, engine, scan, owners[1])
        resting = baseline(owners[2], run_id, 0)
        await submit_new(engine, owners[2], resting, OrderStatus.ACCEPTED, counters, latencies)
        await stop_worker_processes(workers, worker_stop)
        workers = []
        await asyncio.sleep(0.25)
        await stage_expired_claim(engine, scan, owners[2], os.environ[args.admin_url_env])
        stop.set()
        await publisher
        save(
            output / "fixture.json",
            {
                "profile": "F15_W4_FIXTURE_V1",
                "run_id": run_id,
                "owners": [asdict(owner) for owner in owners],
                "counters": asdict(counters),
                "publisher": publisher_stats,
            },
        )
    finally:
        stop.set()
        if not publisher.done():
            publisher.cancel()
        await asyncio.gather(publisher, return_exceptions=True)
        if workers and worker_stop is not None:
            await stop_worker_processes(workers, worker_stop)
        for connection in (api, engine, scan, market):
            await connection.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--admin-url-env", default="TIEWTRADE_TEST_ADMIN_URL")
    asyncio.run(run(parser.parse_args()))
