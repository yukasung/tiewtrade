"""Kill a real worker at explicit transaction boundaries and recover its command."""

import asyncio
import sys
from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market.test_dispatch import intent
from tests.infra.execution_market.test_worker import AllowPolicy, ready_public_sources
from tiewtrade.core.money import Money, Quantity
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.db.session import market_data_session
from tiewtrade.infra.market_data.order_book_storage import publish_input, renew_book_writer
from tiewtrade.infra.paper_orders.dispatch import (
    ClaimedOrder,
    DueOrder,
    claim_order,
    get_order_command,
    submit_order,
)
from tiewtrade.infra.paper_orders.worker import process_claimed_order
from tiewtrade.infra.paper_wallet import (
    PaperCommandState,
    PaperWalletAction,
    admit_command,
    get_command,
    get_wallet,
    inspect_submission,
)
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot
from tiewtrade.infra.positions import read_position_snapshot
from tiewtrade.services.engine.paper_wallet import run_paper_wallet_round

CHILD = """
import asyncio, sys
from uuid import UUID
from tests.infra.execution_market.test_worker import AllowPolicy
from tiewtrade.infra.db import DatabaseRole, create_engine_for, user_session
from tiewtrade.infra.paper_orders.dispatch import DueOrder, claim_order
from tiewtrade.infra.paper_orders.worker import process_claimed_order
from tiewtrade.infra.paper_wallet import claim_command, process_claimed
from tiewtrade.infra.paper_wallet.records import DuePaperCommand

async def run():
    owner, command = UUID(sys.argv[1]), UUID(sys.argv[2])
    reset = len(sys.argv) > 4 and sys.argv[4] == "reset"
    engine = create_engine_for(DatabaseRole.ENGINE)
    try:
        async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
            if reset:
                claim = await claim_command(
                    session, DuePaperCommand(command, owner), worker="kill-boundary")
            else:
                scheduled = (await session.execute(
                    "SELECT next_attempt_at FROM paper_order_dispatch WHERE command_id=:id",
                    {"id": command})).scalar_one()
                claim = await claim_order(
                    session, DueOrder(command, owner, scheduled), worker="kill-boundary")
            assert claim is not None
        print("CLAIMED", flush=True)
        assert await asyncio.to_thread(sys.stdin.readline) == "go\\n"
        async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
            if reset:
                result = await process_claimed(session, claim)
                assert result.failure_code is None
            else:
                await process_claimed_order(session, claim, policy=AllowPolicy())
                links = (await session.execute(
                    "SELECT count(*) FROM paper_execution_links WHERE user_id=:owner",
                    {"owner": owner})).scalar_one()
                assert links == 1
            if sys.argv[3] == "before_commit":
                print("BEFORE_COMMIT", flush=True)
                await asyncio.Event().wait()
        print("AFTER_COMMIT", flush=True)
        await asyncio.Event().wait()
    finally:
        await engine.dispose()
asyncio.run(run())
"""


async def marker(process: asyncio.subprocess.Process, expected: bytes) -> None:
    assert process.stdout is not None
    line = await asyncio.wait_for(process.stdout.readline(), 10)
    if not line:
        assert process.stderr is not None
        errors = await asyncio.wait_for(process.stderr.read(), 2)
        pytest.fail(errors.decode())
    assert line.strip() == expected


@pytest.mark.parametrize("boundary", ["before_commit", "after_commit"])
async def test_worker_kill_recovers_without_duplicate_economic_effects(
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    boundary: str,
) -> None:
    market, lease, book, metadata = await ready_public_sources()
    value = intent(owner, wallet.episode_id)
    process: asyncio.subprocess.Process | None = None

    async def publish_fresh() -> None:
        nonlocal lease, book
        async with market_data_session(market) as session:
            lease = await renew_book_writer(session, lease)
            now = (await session.execute("SELECT clock_timestamp()")).scalar_one()
            book = replace(
                book, input_id=book.input_id + 1, received_at=now, verified_at=now, rebase=False
            )
            lease = await publish_input(session, lease, book, metadata)

    async def claim_target(command_id: UUID) -> ClaimedOrder:
        # The recovery boundary is owner-scoped; scanner fairness has separate tests.
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            scheduled = (
                await session.execute(
                    "SELECT next_attempt_at FROM paper_order_dispatch WHERE command_id=:id",
                    {"id": command_id},
                )
            ).scalar_one()
            claimed = await claim_order(
                session, DueOrder(command_id, owner, scheduled), worker="kill-recovery"
            )
        assert claimed is not None
        return claimed

    try:
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            command = await submit_order(session, wallet_id=wallet.wallet_id, intent=value)
        accepted = await claim_target(command.command_id)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await process_claimed_order(session, accepted, policy=AllowPolicy())
        # Eligibility delay only; the kill interleaving uses child stdout/stdin barriers.
        await asyncio.sleep(0.12)
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            CHILD,
            str(owner),
            str(command.command_id),
            boundary,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await marker(process, b"CLAIMED")
        await publish_fresh()
        assert process.stdin is not None
        process.stdin.write(b"go\n")
        await process.stdin.drain()
        await marker(process, boundary.upper().encode())
        process.kill()
        await asyncio.wait_for(process.wait(), 5)
        assert process.returncode != 0

        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            current = await get_wallet(session)
            assert current is not None
            assert current.balance.amount == (10000 if boundary == "before_commit" else 9900)
            # Simulate lease expiry rather than waiting 30s; no financial rows are edited.
            await session.execute(
                """UPDATE paper_order_dispatch
                SET lease_until=clock_timestamp()-interval '1 second',
                    next_attempt_at=clock_timestamp()
                WHERE command_id=:command AND state<>'TERMINAL'""",
                {"command": command.command_id},
            )
        if boundary == "before_commit":
            recovered = await claim_target(command.command_id)
            # Publish after the claim barrier. A global scan can legitimately process
            # unrelated owners long enough to expire a one-shot 1s book, then back off.
            await publish_fresh()
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                await process_claimed_order(session, recovered, policy=AllowPolicy())

        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            replay = await submit_order(session, wallet_id=wallet.wallet_id, intent=value)
            result = await get_order_command(session, command.command_id)
            current = await get_wallet(session)
            position = await read_position_snapshot(session, wallet.episode_id)
            projection = (
                await session.execute(
                    """SELECT p.status,r.quote_reserved FROM paper_order_projections p
                    JOIN paper_reservations r USING(order_id) WHERE p.order_id=:order""",
                    {"order": value.order_id},
                )
            ).one()
            links = (
                await session.execute(
                    "SELECT count(*) FROM paper_execution_links WHERE order_id=:order",
                    {"order": value.order_id},
                )
            ).scalar_one()
            cash_entries = (
                await session.execute(
                    """SELECT count(*) FROM paper_wallet_ledger
                    WHERE episode_id=:episode AND kind='TRADE_CASH'""",
                    {"episode": wallet.episode_id},
                )
            ).scalar_one()
        assert replay == result and result is not None and result.state == "SUCCEEDED"
        assert current is not None and current.balance.amount == 9900
        assert projection.status == "FILLED" and projection.quote_reserved == 0
        assert links == cash_entries == 1
        assert position is not None and len(position.positions) == 1
        assert position.positions[0].held_quantity == Quantity.of("0.999", "BTC")
        assert position.positions[0].total_cost == Money.of(100, "USDT")
    finally:
        if process is not None and process.returncode is None:
            process.kill()
            await process.wait()
        await market.dispose()


@pytest.mark.parametrize("boundary", ["before_commit", "after_commit"])
async def test_reset_worker_kill_preserves_single_new_episode(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    boundary: str,
) -> None:
    key = uuid4()
    async with user_session(api_engine, owner) as session:
        command = await admit_command(
            session,
            action=PaperWalletAction.RESET,
            idempotency_key=key,
            capital_text="2000",
            expected_episode_id=wallet.episode_id,
        )
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        CHILD,
        str(owner),
        str(command.command_id),
        boundary,
        "reset",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        await marker(process, b"CLAIMED")
        assert process.stdin is not None
        process.stdin.write(b"go\n")
        await process.stdin.drain()
        await marker(process, boundary.upper().encode())
        process.kill()
        await asyncio.wait_for(process.wait(), 5)
        assert process.returncode != 0
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            current = await get_wallet(session)
            assert current is not None
            if boundary == "before_commit":
                assert current.episode_id == wallet.episode_id
                assert current.balance == Money.of(10000, "USDT")
                count = (
                    await session.execute(
                        "SELECT count(*) FROM paper_wallet_episodes WHERE wallet_id=:wallet",
                        {"wallet": wallet.wallet_id},
                    )
                ).scalar_one()
                assert count == 1
            else:
                assert current.episode_id != wallet.episode_id
                assert current.balance == Money.of(2000, "USDT")
            await session.execute(
                """UPDATE paper_wallet_command_dispatch
                SET claim_expires_at=clock_timestamp()-interval '1 second',
                    next_attempt_at=clock_timestamp() WHERE command_id=:command""",
                {"command": command.command_id},
            )
        await run_paper_wallet_round(
            engine=engine_engine, scan_engine=scan_engine, worker="recover-reset"
        )
        async with user_session(api_engine, owner) as session:
            result = await get_command(session, command.command_id)
            replay = await inspect_submission(
                session,
                action=PaperWalletAction.RESET,
                idempotency_key=key,
                capital_text="2000",
                expected_episode_id=wallet.episode_id,
            )
            final = await get_wallet(session)
        assert result is not None and result.state is PaperCommandState.SUCCEEDED
        assert replay == result
        assert final is not None and final.episode_id != wallet.episode_id
        assert final.balance == Money.of(2000, "USDT") and final.reset_available
        if boundary == "after_commit":
            assert final.episode_id == current.episode_id
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            for table, count in (
                ("paper_wallet_episodes", 2),
                ("paper_wallet_episode_closures", 1),
                ("paper_wallet_ledger", 2),
            ):
                actual = (
                    await session.execute(
                        f"SELECT count(*) FROM {table} WHERE wallet_id=:wallet",
                        {"wallet": wallet.wallet_id},
                    )
                ).scalar_one()
                assert actual == count, table
            audits = (
                await session.execute(
                    """SELECT count(*) FROM audit_events WHERE owner_user_id=:owner
                    AND action='PAPER_WALLET_RESET' AND outcome='SUCCEEDED'""",
                    {"owner": owner},
                )
            ).scalar_one()
            assert audits == 1
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()
