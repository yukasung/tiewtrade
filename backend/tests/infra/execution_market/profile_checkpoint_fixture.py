"""Untimed, pinned checkpoint equivalence fixture; never a workload acceptance run."""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import event

from tests.infra.execution_market.profile_workload import AllowPaperPolicy, save, seed_owners
from tests.infra.execution_market.test_dispatch import intent
from tiewtrade.core.market_catalog import CatalogSnapshot
from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.orders import BaseSize, OrderConstraints, OrderType, TimeInForce
from tiewtrade.core.paper_matching import admit_order, cancel_order
from tiewtrade.core.positions import PositionPair
from tiewtrade.infra.db import DatabaseRole, create_engine_for, user_session
from tiewtrade.infra.paper_orders.codec import order_payload, state_from_payload, state_payload
from tiewtrade.infra.paper_orders.dispatch import submit_order
from tiewtrade.infra.paper_orders.matching_storage import (
    insert_order_header,
    load_matching_state,
    persist_checkpoint,
)


async def prepare(path: Path, *, btc_orders: int = 2) -> None:
    if btc_orders not in (2, 20):
        raise ValueError("checkpoint fixture supports only 2 or 20 BTC orders")
    api, engine, scan = [
        create_engine_for(role)
        for role in (DatabaseRole.API, DatabaseRole.ENGINE, DatabaseRole.ENGINE_SCAN)
    ]
    try:
        owner = (await seed_owners(api, engine, scan, 1))[0]
        operations = []
        states = {}
        values = []
        now = datetime(2026, 11, 6, 0, 0, tzinfo=UTC)

        def operation(state: Any, order: UUID, kind: str, decision: str, number: int) -> None:
            payload = state_payload(state)
            # Preserve terminal input states too; production serialization compacts them.
            payload["orders"] = [order_payload(value) for value in state.orders]
            operations.append(
                {
                    "state": payload,
                    "order": order,
                    "kind": kind,
                    "decision": decision,
                    "at": now + timedelta(seconds=number),
                    "id": uuid5(NAMESPACE_URL, f"checkpoint-fixture:{owner.user_id}:{number}"),
                }
            )

        for number, base in enumerate(("BTC",) * btc_orders + ("ETH", "ETH"), start=1):
            pair = PositionPair(base, "USDT")
            value = replace(
                intent(owner.user_id, owner.wallet.episode_id),
                pair=pair,
                kind=OrderType.LIMIT,
                size=BaseSize(Quantity.of(1, base)),
                limit_price=Money.of(100, "USDT"),
                time_in_force=TimeInForce.GTC,
            )
            async with user_session(engine, owner.user_id, role=DatabaseRole.ENGINE) as session:
                command = await submit_order(
                    session, wallet_id=owner.wallet.wallet_id, intent=value
                )
                if base not in states:
                    states[base] = (
                        await load_matching_state(
                            session, wallet_id=owner.wallet.wallet_id, scope=value.scope, pair=pair
                        )
                    ).state
                state = admit_order(
                    states[base],
                    value,
                    now=now + timedelta(seconds=number),
                    sequence=number,
                    cash=Money.of(10000, "USDT"),
                    held=Quantity.of(0, base),
                    constraints=OrderConstraints(
                        pair,
                        "checkpoint-fixture-v1",
                        Quantity.of("0.01", base),
                        Quantity.of("0.01", base),
                        Money.of("0.01", "USDT"),
                        Money.of("0.01", "USDT"),
                    ),
                    reference_price=Money.of(100, "USDT"),
                    policy=AllowPaperPolicy(),
                    catalog=CatalogSnapshot(1, frozenset({(base, "USDT")})),
                )
                await insert_order_header(
                    session,
                    wallet_id=owner.wallet.wallet_id,
                    command_id=command.command_id,
                    order=state.orders[-1],
                )
            states[base] = state
            values.append(value)
            operation(state, value.order_id, "ACCEPTED", "ACCEPT", number)
        canceled = cancel_order(states["BTC"], values[0].order_id, scope=values[0].scope)
        operation(canceled, values[0].order_id, "CANCELED", "CANCEL", btc_orders + 3)
        operation(
            states["ETH"], values[btc_orders].order_id, "INPUT_APPLIED", "INPUT", btc_orders + 4
        )
        save(
            path,
            {"owner": owner.user_id, "wallet": owner.wallet.wallet_id, "operations": operations},
        )
    finally:
        for connection in (api, engine, scan):
            await connection.dispose()


async def checkpoint_snapshot(session: Any, *, raw: bool = False) -> dict[str, Any]:
    tables = {
        "paper_order_events": ["recorded_at"],
        "paper_order_projections": [],
        "paper_reservations": [],
        "paper_order_activity": ["observed_at"],
        "paper_wallet_state": [],
        "paper_wallet_ledger": [],
        "paper_position_activity": [],
        "paper_position_projections": [],
        "paper_order_dispatch": [],
        "audit_events": ["id", "recorded_at"],
    }
    snapshot = {}
    for table, omitted in tables.items():
        rows = (
            (
                await session.execute(
                    "SELECT (to_jsonb(t)-CAST(:omitted AS text[]))::text " + f"FROM {table} t",
                    {"omitted": [] if raw else omitted},
                )
            )
            .scalars()
            .all()
        )
        values = [json.loads(row, parse_float=str) for row in rows]
        snapshot[table] = sorted(values, key=lambda value: json.dumps(value, sort_keys=True))
    return snapshot


async def replay(fixture: Path, output: Path) -> None:
    document = json.loads(fixture.read_text())
    engine = create_engine_for(DatabaseRole.ENGINE)
    counts = []
    snapshots = []
    counting = False
    count = 0

    @event.listens_for(engine.sync_engine, "before_cursor_execute")
    def statement(*args: Any) -> None:
        nonlocal count
        if counting:
            count += 1

    try:
        for item in document["operations"]:
            state = state_from_payload(item["state"])
            async with user_session(
                engine, UUID(document["owner"]), role=DatabaseRole.ENGINE
            ) as session:
                counting, count = True, 0
                try:
                    await persist_checkpoint(
                        session,
                        wallet_id=UUID(document["wallet"]),
                        state=state,
                        anchor_order_id=UUID(item["order"]),
                        event_kind=item["kind"],
                        decision_kind=item["decision"],
                        occurred_at=datetime.fromisoformat(item["at"]),
                        decision_id=UUID(item["id"]),
                    )
                finally:
                    counting = False
                counts.append(count)
                snapshots.append(await checkpoint_snapshot(session))
        save(output, {"statement_counts": counts, "snapshots": snapshots})
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "replay"))
    parser.add_argument("--fixture", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--btc-orders", type=int, choices=(2, 20), default=2)
    args = parser.parse_args()
    if args.action == "prepare":
        asyncio.run(prepare(args.fixture, btc_orders=args.btc_orders))
    else:
        if args.output is None:
            parser.error("replay requires output")
        asyncio.run(replay(args.fixture, args.output))
