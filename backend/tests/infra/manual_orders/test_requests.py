"""Real-role inbox transactions, replay, reset exclusion and outcome discovery."""

import asyncio
from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market.test_dispatch import intent
from tiewtrade.core.money import Money
from tiewtrade.core.orders import OrderConflictError, QuoteBudget
from tiewtrade.infra.audit import AuditAction
from tiewtrade.infra.db import DatabaseRole, InfraError, user_session
from tiewtrade.infra.db.session import presented_session, scan_session_bypassing_rls
from tiewtrade.infra.paper_orders import requests
from tiewtrade.infra.paper_orders.codec import intent_payload
from tiewtrade.infra.paper_orders.dispatch import complete_command, submit_order
from tiewtrade.infra.paper_orders.requests import admit_new_request, get_request, get_request_by_key
from tiewtrade.infra.paper_orders.views import request_view, unresolved_requests
from tiewtrade.infra.paper_wallet import (
    PaperWalletAction,
    admit_command,
    get_command,
    get_wallet,
)
from tiewtrade.infra.paper_wallet.records import PaperCommandState, PaperWalletSnapshot
from tiewtrade.infra.users import create_user
from tiewtrade.services.engine.paper_wallet import run_paper_wallet_round


async def test_api_inbox_replays_server_identity_and_does_not_write_money(
    api_engine: AsyncEngine, owner: UUID, wallet: PaperWalletSnapshot
) -> None:
    value = intent(owner, wallet.episode_id)
    async with user_session(api_engine, owner) as session:
        before = await get_wallet(session)
        first = await admit_new_request(session, wallet_id=wallet.wallet_id, intent=value)
    async with user_session(api_engine, owner) as session:
        replay = await admit_new_request(
            session, wallet_id=wallet.wallet_id, intent=replace(value, order_id=uuid4())
        )
        view = await request_view(session, first.request_id)
        after = await get_wallet(session)
        assert before is not None and after is not None
        assert before.balance == after.balance
        assert before.reset_available and not after.reset_available
        assert after.reset_reason == "RESET_UNSAFE"
        assert replay == first
        assert first.admitted_catalog_revision == 2
        assert view is not None and view.intake_state == "PENDING"
        assert view.command_state is None and view.order_state is None
        event = (
            await session.execute(
                """SELECT actor_kind,actor_id,mode,details FROM audit_events
                WHERE action=:action AND details->>'request_id'=:id""",
                {"action": AuditAction.PAPER_ORDER_REQUESTED.value, "id": str(first.request_id)},
            )
        ).one()
        assert event.actor_kind == "USER" and event.actor_id == owner and event.mode == "PAPER"
    with pytest.raises(OrderConflictError):
        async with user_session(api_engine, owner) as session:
            await admit_new_request(
                session,
                wallet_id=wallet.wallet_id,
                intent=replace(value, size=QuoteBudget(Money.of(101, "USDT"))),
            )


async def test_concurrent_same_key_creates_one_request_and_one_audit(
    api_engine: AsyncEngine, owner: UUID, wallet: PaperWalletSnapshot
) -> None:
    value = intent(owner, wallet.episode_id)

    async def submit() -> UUID:
        async with user_session(api_engine, owner) as session:
            return (
                await admit_new_request(
                    session, wallet_id=wallet.wallet_id, intent=replace(value, order_id=uuid4())
                )
            ).request_id

    identities = await asyncio.gather(submit(), submit(), submit())
    assert len(set(identities)) == 1
    async with user_session(api_engine, owner) as session:
        count = (
            await session.execute(
                """SELECT count(*) FROM audit_events WHERE action='PAPER_ORDER_REQUESTED'
                AND details->>'request_id'=:id""",
                {"id": str(identities[0])},
            )
        ).scalar_one()
        assert count == 1


async def test_audit_failure_rolls_back_inbox_and_reset_blocker(
    api_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def unavailable(*args: object, **kwargs: object) -> None:
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(requests, "record_event", unavailable)
    value = intent(owner, wallet.episode_id)
    with pytest.raises(RuntimeError, match="audit unavailable"):
        async with user_session(api_engine, owner) as session:
            await admit_new_request(session, wallet_id=wallet.wallet_id, intent=value)
    async with user_session(api_engine, owner) as session:
        assert await get_request_by_key(session, action="NEW", key=value.idempotency_key) is None
        snapshot = await get_wallet(session)
        assert snapshot is not None and snapshot.reset_available


async def test_pending_intake_blocks_real_reset_worker(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    async with user_session(api_engine, owner) as session:
        await admit_new_request(
            session, wallet_id=wallet.wallet_id, intent=intent(owner, wallet.episode_id)
        )
        reset = await admit_command(
            session,
            action=PaperWalletAction.RESET,
            idempotency_key=uuid4(),
            capital_text="5000",
            expected_episode_id=wallet.episode_id,
        )
    await run_paper_wallet_round(
        engine=engine_engine, scan_engine=scan_engine, worker="inbox-reset"
    )
    async with user_session(api_engine, owner) as session:
        result = await get_command(session, reset.command_id)
        snapshot = await get_wallet(session)
        assert result is not None and result.state is PaperCommandState.REJECTED
        assert result.failure_code == "RESET_UNSAFE"
        assert snapshot is not None and snapshot.episode_id == wallet.episode_id


async def test_roles_and_owner_isolation(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    other = uuid4()
    await create_user(api_engine, other)
    async with user_session(api_engine, owner) as session:
        receipt = await admit_new_request(
            session, wallet_id=wallet.wallet_id, intent=intent(owner, wallet.episode_id)
        )
    async with user_session(api_engine, other) as session:
        assert await get_request(session, receipt.request_id) is None
        assert await request_view(session, receipt.request_id) is None
        assert (await unresolved_requests(session)).requests == ()
    async with presented_session(api_engine) as session:
        assert (
            await session.execute("SELECT count(*) FROM paper_order_requests")
        ).scalar_one() == 0
    for sql in [
        "UPDATE paper_wallet_state SET revision=revision WHERE false",
        """INSERT INTO paper_order_command_results(command_id,user_id,episode_id,state,snapshot)
        VALUES(:id,:user,:episode,'SUCCEEDED','{}')""",
        "UPDATE paper_order_requests SET payload=payload WHERE false",
        "DELETE FROM paper_order_requests WHERE false",
    ]:
        with pytest.raises(InfraError):
            async with user_session(api_engine, owner) as session:
                await session.execute(
                    sql, {"id": uuid4(), "user": owner, "episode": wallet.episode_id}
                )
    with pytest.raises(InfraError):
        async with scan_session_bypassing_rls(scan_engine) as session:
            await session.execute("SELECT payload FROM paper_order_requests")
    with pytest.raises(InfraError):
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await session.execute("TRUNCATE paper_order_requests CASCADE")


async def test_joined_command_rejection_is_visible_without_order_row(
    api_engine: AsyncEngine, engine_engine: AsyncEngine, owner: UUID, wallet: PaperWalletSnapshot
) -> None:
    value = intent(owner, wallet.episode_id)
    async with user_session(api_engine, owner) as session:
        receipt = await admit_new_request(session, wallet_id=wallet.wallet_id, intent=value)
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        command = await submit_order(session, wallet_id=wallet.wallet_id, intent=value)
        await session.execute(
            """INSERT INTO paper_order_request_results
            (request_id,user_id,episode_id,order_id,action,state,command_id)
            VALUES(:id,:owner,:episode,:order,'NEW','TRANSFERRED',:command)""",
            {
                "id": receipt.request_id,
                "owner": owner,
                "episode": wallet.episode_id,
                "order": value.order_id,
                "command": command.command_id,
            },
        )
        await requests.request_audit(
            session,
            receipt,
            action=AuditAction.PAPER_ORDER_REQUEST_TRANSFERRED,
            command_id=command.command_id,
        )
    async with user_session(api_engine, owner) as session:
        view = await request_view(session, receipt.request_id)
        assert view is not None and view.command_state == "PENDING"
        assert len((await unresolved_requests(session)).requests) == 1
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await complete_command(
            session,
            command_id=command.command_id,
            episode_id=wallet.episode_id,
            succeeded=False,
            failure_code="ORDER_INSUFFICIENT_FUNDS",
            snapshot={"order_id": str(value.order_id), "status": "REJECTED"},
        )
    async with user_session(api_engine, owner) as session:
        view = await request_view(session, receipt.request_id)
        assert view is not None and view.intake_state == "TRANSFERRED"
        assert view.command_state == "REJECTED" and view.order_state is None
        assert view.command_failure_code == "ORDER_INSUFFICIENT_FUNDS"
        assert (await unresolved_requests(session)).requests == ()


async def test_discovery_pagination_binds_owner_and_rejects_bad_cursors(
    api_engine: AsyncEngine, owner: UUID, wallet: PaperWalletSnapshot
) -> None:
    async with user_session(api_engine, owner) as session:
        expected = [
            await admit_new_request(
                session, wallet_id=wallet.wallet_id, intent=intent(owner, wallet.episode_id)
            )
            for _ in range(3)
        ]
        first = await unresolved_requests(session, limit=2)
        assert first.next_cursor is not None
        second = await unresolved_requests(session, limit=2, cursor=first.next_cursor)
        assert [x.request.request_id for x in (*first.requests, *second.requests)] == [
            x.request_id for x in expected
        ]
        assert second.next_cursor is None
        for bad in ["!", "[]", "a" * 513]:
            with pytest.raises(OrderConflictError):
                await unresolved_requests(session, cursor=bad)
    async with user_session(api_engine, uuid4()) as session:
        with pytest.raises(OrderConflictError):
            await unresolved_requests(session, cursor=first.next_cursor)


@pytest.mark.parametrize(
    "change",
    [
        {"mode": "LIVE"},
        {"quantity": "1", "budget": "100"},
        {"budget": 100},
        {"budget": "0.0000000000000000001"},
        {"budget": "NaN"},
        {"budget": "-1"},
        {"kind": "LIMIT", "tif": "IOC"},
        {"secret": "forbidden"},
    ],
)
async def test_database_rejects_invalid_intents(
    api_engine: AsyncEngine, owner: UUID, wallet: PaperWalletSnapshot, change: dict[str, object]
) -> None:
    from tiewtrade.infra.market_data.order_book_codec import canonical

    value = intent(owner, wallet.episode_id)
    payload = {**intent_payload(value), **change}
    with pytest.raises(InfraError):
        async with user_session(api_engine, owner) as session:
            await session.execute(
                """INSERT INTO paper_order_requests
                (id,user_id,wallet_id,episode_id,order_id,action,idempotency_key,
                 request_fingerprint,admitted_catalog_revision,payload)
                VALUES(:id,:user,:wallet,:episode,:order,'NEW',:key,:fp,2,
                       CAST(:payload AS jsonb))""",
                {
                    "id": uuid4(),
                    "user": owner,
                    "wallet": wallet.wallet_id,
                    "episode": wallet.episode_id,
                    "order": value.order_id,
                    "key": value.idempotency_key,
                    "fp": "a" * 64,
                    "payload": canonical(payload),
                },
            )


async def test_terminal_intake_rejection_audits_and_releases_reset_blocker(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    value = intent(owner, wallet.episode_id)
    async with user_session(api_engine, owner) as session:
        receipt = await admit_new_request(session, wallet_id=wallet.wallet_id, intent=value)
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await requests.wallet_lock(session)
        await session.execute(
            """INSERT INTO paper_order_request_results
            (request_id,user_id,episode_id,order_id,action,state,failure_code)
            VALUES(:id,:owner,:episode,:order,'NEW','REJECTED','CATALOG_PAIR_REMOVED')""",
            {
                "id": receipt.request_id,
                "owner": owner,
                "episode": wallet.episode_id,
                "order": receipt.order_id,
            },
        )
        await requests.request_audit(
            session,
            receipt,
            action=AuditAction.PAPER_ORDER_REQUEST_REJECTED,
            failure_code="CATALOG_PAIR_REMOVED",
        )
    async with user_session(api_engine, owner) as session:
        view = await request_view(session, receipt.request_id)
        snapshot = await get_wallet(session)
        assert view is not None and view.intake_state == "REJECTED"
        assert view.intake_failure_code == "CATALOG_PAIR_REMOVED" and view.command_id is None
        assert snapshot is not None and snapshot.reset_available

        reset = await admit_command(
            session,
            action=PaperWalletAction.RESET,
            idempotency_key=uuid4(),
            capital_text="5000",
            expected_episode_id=wallet.episode_id,
        )
    await run_paper_wallet_round(
        engine=engine_engine, scan_engine=scan_engine, worker="terminal-reset"
    )
    async with user_session(api_engine, owner) as session:
        outcome = await get_command(session, reset.command_id)
        assert outcome is not None and outcome.state is PaperCommandState.SUCCEEDED
        replay = await admit_new_request(
            session, wallet_id=wallet.wallet_id, intent=replace(value, order_id=uuid4())
        )
        assert replay == receipt
        # Existing outcomes must win over the permanent closed-episode refusal.
        assert (
            await requests.inspect_new_request(
                session, wallet_id=wallet.wallet_id, intent=replace(value, order_id=uuid4())
            )
            == receipt
        )


@pytest.mark.parametrize("failure", [None, "ARBITRARY_REASON"])
async def test_database_rejection_result_requires_declared_failure(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    failure: str | None,
) -> None:
    async with user_session(api_engine, owner) as session:
        receipt = await admit_new_request(
            session, wallet_id=wallet.wallet_id, intent=intent(owner, wallet.episode_id)
        )
    with pytest.raises(InfraError):
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await session.execute(
                """INSERT INTO paper_order_request_results
                (request_id,user_id,episode_id,order_id,action,state,failure_code)
                VALUES(:id,:owner,:episode,:order,'NEW','REJECTED',:failure)""",
                {
                    "id": receipt.request_id,
                    "owner": owner,
                    "episode": wallet.episode_id,
                    "order": receipt.order_id,
                    "failure": failure,
                },
            )
