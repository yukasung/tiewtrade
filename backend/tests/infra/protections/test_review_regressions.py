"""Review regressions using actual financial facts, owner locks and PostgreSQL."""

import asyncio
import sys
from dataclasses import replace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market.test_dispatch import intent
from tests.infra.execution_market.test_process_recovery import CHILD, marker
from tests.infra.execution_market.test_worker import AllowPolicy, ready_public_sources
from tests.infra.manual_orders.test_bridge import select_use
from tests.infra.protections.test_lifecycle import buy, execute, single_fill, transfer
from tests.infra.protections.test_lifecycle import protocol as protocol
from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.orders import BaseSize, OrderType, SourceUnavailableError, TimeInForce
from tiewtrade.core.positions import ExecutionSide, PositionPair
from tiewtrade.core.protections import ProtectionState
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.db.session import market_data_session
from tiewtrade.infra.market_data.order_book_storage import publish_input, read_latest_book
from tiewtrade.infra.paper_orders.corrections import correct_fill
from tiewtrade.infra.paper_orders.dispatch import DueOrder, claim_order
from tiewtrade.infra.paper_orders.trade_views import trade_snapshot
from tiewtrade.infra.paper_orders.worker import process_claimed_order
from tiewtrade.infra.paper_wallet import get_wallet
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot
from tiewtrade.infra.positions import PositionEventKind
from tiewtrade.infra.positions.views import held_and_reserved
from tiewtrade.infra.protections import worker
from tiewtrade.infra.protections.storage import admit_request, allocated, load, lock_scope

PAIR = PositionPair("BTC", "USDT")


async def test_replacement_progress_uses_owner_rls_and_narrow_runtime_grants(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    from tiewtrade.infra.db import InfraError
    from tiewtrade.infra.db.session import scan_session_bypassing_rls

    async with user_session(api_engine, owner) as session:
        request = await admit_request(
            session,
            wallet_id=wallet.wallet_id,
            episode_id=wallet.episode_id,
            action="CREATE",
            key=uuid4(),
            protection_id=None,
            payload={"base": "BTC", "quantity": "0.1", "tp": "110", "sl": "90"},
        )
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await worker.process_request(session, request)
        assert (
            await session.execute(
                "SELECT attempt FROM paper_protection_request_progress WHERE request_id=:id",
                {"id": request},
            )
        ).scalar_one() == 1
    async with user_session(engine_engine, uuid4(), role=DatabaseRole.ENGINE) as session:
        assert (
            await session.execute(
                "SELECT attempt FROM paper_protection_request_progress WHERE request_id=:id",
                {"id": request},
            )
        ).first() is None
    with pytest.raises(InfraError):
        async with user_session(api_engine, owner) as session:
            await session.execute(
                "UPDATE paper_protection_request_progress SET attempt=4 WHERE request_id=:id",
                {"id": request},
            )
    async with scan_session_bypassing_rls(scan_engine) as session:
        assert (
            await session.execute(
                "SELECT request_id,next_attempt_at FROM paper_protection_request_progress "
                "WHERE request_id=:id",
                {"id": request},
            )
        ).first() is not None
    with pytest.raises(InfraError):
        async with scan_session_bypassing_rls(scan_engine) as session:
            await session.execute("SELECT attempt FROM paper_protection_request_progress")


@pytest.mark.parametrize("action", ["CANCEL", "REPLACE", "SELL"])
@pytest.mark.parametrize("first", ["mutation", "trigger"])
async def test_trigger_and_mutation_serialize_in_both_commit_orders(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    monkeypatch: pytest.MonkeyPatch,
    action: str,
    first: str,
) -> None:
    market, _, _, _, group_id = await buy(api_engine, engine_engine, scan_engine, owner, wallet)
    try:
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            before = await load(session, group_id)
            assert before is not None
            evidence = await worker.market_evidence(session, PAIR)
            source = await read_latest_book(session, PAIR)
        evidence = replace(evidence, source_id=uuid4(), price=Money.of("110", "USDT"))
        monkeypatch.setattr(worker, "market_evidence", AsyncMock(return_value=evidence))
        monkeypatch.setattr(worker, "read_latest_book", AsyncMock(return_value=source))
        claim = None
        if action == "SELL":
            sale = replace(
                intent(owner, wallet.episode_id),
                side=ExecutionSide.SELL,
                kind=OrderType.LIMIT,
                size=BaseSize(Quantity.of("0.4", "BTC")),
                limit_price=Money.of("120", "USDT"),
                time_in_force=TimeInForce.GTC,
            )
            command = await transfer(
                api_engine,
                engine_engine,
                scan_engine,
                owner,
                wallet,
                sale,
                selections=(
                    {
                        "protection_id": str(group_id),
                        "quantity": "0.4",
                        "expected_revision": before.value.revision,
                    },
                ),
            )
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                due = (
                    await session.execute(
                        "SELECT next_attempt_at FROM paper_order_dispatch WHERE command_id=:id",
                        {"id": command},
                    )
                ).scalar_one()
                claim = await claim_order(
                    session, DueOrder(command, owner, due), worker="mutation-race"
                )
                assert claim is not None
        else:
            payload: dict[str, object] = {"expected_revision": before.value.revision}
            if action == "REPLACE":
                payload.update(quantity="0.5", tp="120", sl="80")
            async with user_session(api_engine, owner) as session:
                request = await admit_request(
                    session,
                    wallet_id=wallet.wallet_id,
                    episode_id=wallet.episode_id,
                    action=action,
                    key=uuid4(),
                    protection_id=group_id,
                    payload=payload,
                )

        entered, release, waiting = asyncio.Event(), asyncio.Event(), asyncio.Event()

        async def operation(name: str) -> None:
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                if name == first:
                    await lock_scope(session, wallet.wallet_id, wallet.episode_id)
                else:
                    waiting.set()
                if name == "trigger":
                    await worker.process_group(session, group_id)
                elif action == "SELL":
                    assert claim is not None
                    await process_claimed_order(session, claim, policy=AllowPolicy())
                else:
                    await worker.process_request(session, request)
                if name == first:
                    entered.set()
                    await release.wait()

        winner = asyncio.create_task(operation(first))
        await asyncio.wait_for(entered.wait(), 5)
        loser = asyncio.create_task(operation("trigger" if first == "mutation" else "mutation"))
        try:
            await asyncio.wait_for(waiting.wait(), 5)
            await asyncio.sleep(0.03)
            assert not loser.done()
        finally:
            release.set()
        await asyncio.wait_for(asyncio.gather(winner, loser), 10)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            current = await load(session, group_id)
            assert current is not None
            count = (
                await session.execute(
                    "SELECT count(*) FROM paper_protection_exits WHERE protection_id=:id",
                    {"id": group_id},
                )
            ).scalar_one()
            assert count == (0 if first == "mutation" and action in ("CANCEL", "REPLACE") else 1)
            held, reserved = await held_and_reserved(session, wallet.episode_id, PAIR)
            assert not held < reserved + await allocated(session, wallet.episode_id, PAIR)
            if first == "trigger":
                assert current.value.quantity == Quantity.of("0.999", "BTC")
                assert current.value.state is ProtectionState.EXITING
            elif action == "SELL":
                assert current.value.quantity == Quantity.of("0.599", "BTC")
            elif action == "CANCEL":
                assert current.value.state is ProtectionState.CANCELED
            else:
                assert current.value.state is ProtectionState.ARMED
                assert current.value.quantity == Quantity.of("0.5", "BTC")
    finally:
        await market.dispose()


@pytest.mark.parametrize("boundary", ["before_commit", "after_commit"])
async def test_bracket_fill_process_kill_preserves_one_financial_effect(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    boundary: str,
) -> None:
    await select_use(api_engine, owner)
    market, lease, book, metadata = await ready_public_sources()
    process = None
    try:
        value = intent(owner, wallet.episode_id)
        command = await transfer(
            api_engine,
            engine_engine,
            scan_engine,
            owner,
            wallet,
            value,
            bracket={"tp": "110", "sl": "90"},
        )
        await execute(engine_engine, owner, command)
        await asyncio.sleep(0.23)
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            CHILD,
            str(owner),
            str(command),
            boundary,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await marker(process, b"CLAIMED")
        async with market_data_session(market) as session:
            now = (await session.execute("SELECT clock_timestamp()")).scalar_one()
            book = replace(
                book, input_id=book.input_id + 1, received_at=now, verified_at=now, rebase=False
            )
            lease = await publish_input(session, lease, book, metadata)
        assert process.stdin is not None
        process.stdin.write(b"go\n")
        await process.stdin.drain()
        await marker(process, boundary.upper().encode())
        process.kill()
        await asyncio.wait_for(process.wait(), 5)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            group_id = (
                await session.execute(
                    "SELECT id FROM paper_protections WHERE entry_order_id=:id",
                    {"id": value.order_id},
                )
            ).scalar_one()
            current = await load(session, group_id)
            cash = await get_wallet(session)
            assert current is not None and cash is not None
            assert current.value.quantity == Quantity.of(
                "0" if boundary == "before_commit" else "0.999", "BTC"
            )
            assert cash.balance == Money.of(
                "10000" if boundary == "before_commit" else "9900", "USDT"
            )
            await session.execute(
                """UPDATE paper_order_dispatch
                SET lease_until=clock_timestamp()-interval '1 second',
                next_attempt_at=clock_timestamp() WHERE command_id=:id AND state<>'TERMINAL'""",
                {"id": command},
            )
        if boundary == "before_commit":
            async with market_data_session(market) as session:
                now = (await session.execute("SELECT clock_timestamp()")).scalar_one()
                book = replace(book, input_id=book.input_id + 1, received_at=now, verified_at=now)
                lease = await publish_input(session, lease, book, metadata)
            await execute(engine_engine, owner, command)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            current = await load(session, group_id)
            cash = await get_wallet(session)
            assert current is not None and current.value.quantity == Quantity.of("0.999", "BTC")
            assert current.acquired == Quantity.of("0.999", "BTC")
            assert cash is not None and cash.balance == Money.of("9900", "USDT")
            assert (
                await session.execute(
                    "SELECT count(*) FROM paper_execution_links WHERE episode_id=:episode",
                    {"episode": wallet.episode_id},
                )
            ).scalar_one() == 1
    finally:
        if process is not None and process.returncode is None:
            process.kill()
            await process.wait()
        await market.dispose()


@pytest.mark.parametrize("failure", ["minimum", "source"])
async def test_replace_failure_preserves_working_revision(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    market, _, _, _, group_id = await buy(api_engine, engine_engine, scan_engine, owner, wallet)
    try:
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            before = await load(session, group_id)
            assert before is not None and before.value.state is ProtectionState.ARMED
            evidence = await worker.market_evidence(session, PAIR)
            source = await read_latest_book(session, PAIR)
        monkeypatch.setattr(worker, "market_evidence", AsyncMock(return_value=evidence))
        monkeypatch.setattr(
            worker,
            "read_latest_book",
            AsyncMock(side_effect=SourceUnavailableError("test unavailable"))
            if failure == "source"
            else AsyncMock(return_value=source),
        )
        async with user_session(api_engine, owner) as session:
            request = await admit_request(
                session,
                wallet_id=wallet.wallet_id,
                episode_id=wallet.episode_id,
                action="REPLACE",
                key=uuid4(),
                protection_id=group_id,
                payload={
                    "quantity": "0.00000001" if failure == "minimum" else "0.5",
                    "tp": "120",
                    "sl": "80",
                    "expected_revision": before.value.revision,
                },
            )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await worker.process_request(session, request)
        if failure == "source":
            from datetime import timedelta

            for attempt, delay in ((2, 1), (3, 2), (4, 4)):
                async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                    current = await load(session, group_id)
                    assert current is not None and current.value == before.value
                    progress = (
                        await session.execute(
                            """SELECT attempt,next_attempt_at,clock_timestamp() AS now
                        FROM paper_protection_request_progress WHERE request_id=:id""",
                            {"id": request},
                        )
                    ).one()
                    assert progress.attempt == attempt
                    assert (
                        timedelta(0)
                        < progress.next_attempt_at - progress.now
                        <= timedelta(seconds=delay)
                    )
                    await worker.process_request(session, request)
                    assert (
                        await session.execute(
                            "SELECT count(*) FROM paper_protection_results WHERE request_id=:id",
                            {"id": request},
                        )
                    ).scalar_one() == 0
                    await session.execute(
                        """UPDATE paper_protection_request_progress
                        SET next_attempt_at=clock_timestamp()-interval '1 second'
                        WHERE request_id=:id""",
                        {"id": request},
                    )
                async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                    await worker.process_request(session, request)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await worker.process_request(session, request)
            after = await load(session, group_id)
            assert after is not None and after.value == before.value
            assert (
                await session.execute(
                    "SELECT state FROM paper_protection_results WHERE request_id=:id",
                    {"id": request},
                )
            ).scalar_one() == "REJECTED"
    finally:
        await market.dispose()


async def test_entry_correction_snapshot_remains_repairable_after_reload(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    market, _, _, _, group_id = await buy(api_engine, engine_engine, scan_engine, owner, wallet)
    try:
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            before = await load(session, group_id)
            assert before is not None
            evidence = await worker.market_evidence(session, PAIR)
            source = await read_latest_book(session, PAIR)
            assert before.value.entry_order_id is not None
            position_event_id, order_event_id, fact = await single_fill(
                session, before.value.entry_order_id
            )
            await correct_fill(
                session,
                wallet_id=wallet.wallet_id,
                episode_id=wallet.episode_id,
                order_event_id=order_event_id,
                correction_event_id=uuid4(),
                supersedes_position_event_id=position_event_id,
                kind=PositionEventKind.REPLACE,
                fact=replace(
                    fact,
                    gross_quantity=Quantity.of("0.5", "BTC"),
                    quote_amount=Money.of("50", "USDT"),
                    fee=None,
                ),
            )
        async with user_session(api_engine, owner) as session:
            snapshot = await trade_snapshot(session, risk_policy_available=True, pair=PAIR)
            assert snapshot["wallet"]["episode_id"] == str(wallet.episode_id)
            assert snapshot["wallet"]["base_balances"][0]["held"] == "0.5"
            assert snapshot["wallet"]["base_balances"][0]["available"] is None
            assert snapshot["wallet"]["source_availability"] == "UNKNOWN"
            assert (
                not snapshot["admission_ready"]
                and "ORDER_CONFLICT" in snapshot["admission_reasons"]
            )
            conflicted = await load(session, group_id)
            assert conflicted is not None and conflicted.value.conflicted
            request = await admit_request(
                session,
                wallet_id=wallet.wallet_id,
                episode_id=wallet.episode_id,
                action="REPLACE",
                key=uuid4(),
                protection_id=group_id,
                payload={
                    "quantity": "0.5",
                    "tp": "110",
                    "sl": "90",
                    "expected_revision": conflicted.value.revision,
                },
            )
        monkeypatch.setattr(worker, "market_evidence", AsyncMock(return_value=evidence))
        monkeypatch.setattr(worker, "read_latest_book", AsyncMock(return_value=source))
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await worker.process_request(session, request)
        async with user_session(api_engine, owner) as session:
            repaired = await load(session, group_id)
            assert repaired is not None and not repaired.value.conflicted
            assert repaired.value.quantity == Quantity.of("0.5", "BTC")
            assert repaired.value.state is ProtectionState.ARMED
            snapshot = await trade_snapshot(session, risk_policy_available=True, pair=PAIR)
            assert snapshot["wallet"]["source_availability"] == "READY"
            assert snapshot["wallet"]["base_balances"][0]["available"] == "0"
    finally:
        await market.dispose()
