"""Kill the bridge at real COMMIT boundaries, then recover the same request identity."""

import asyncio
import sys
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market.test_dispatch import intent
from tests.infra.execution_market.test_process_recovery import marker
from tests.infra.execution_market.test_worker import AllowPolicy
from tests.infra.manual_orders.test_bridge import select_use
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.paper_orders.request_dispatch import DueRequest, claim_request
from tiewtrade.infra.paper_orders.request_worker import process_request
from tiewtrade.infra.paper_orders.requests import admit_new_request
from tiewtrade.infra.paper_orders.views import request_view
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot

_CHILD = """
import asyncio,sys
from uuid import UUID, uuid4
from tests.infra.execution_market.test_worker import AllowPolicy
from tiewtrade.infra.db import DatabaseRole,create_engine_for,user_session
from tiewtrade.infra.paper_orders.request_dispatch import DueRequest,claim_request
from tiewtrade.infra.paper_orders.request_worker import process_request
async def main():
    owner,identity=UUID(sys.argv[1]),UUID(sys.argv[2])
    engine=create_engine_for(DatabaseRole.ENGINE)
    async with user_session(engine,owner,role=DatabaseRole.ENGINE) as session:
        due=(await session.execute(
            'SELECT next_attempt_at FROM paper_order_request_dispatch WHERE request_id=:id',
            {'id':identity})).scalar_one()
        claim=await claim_request(session,DueRequest(identity,owner,due),worker='bridge-kill')
        assert claim is not None
    print('CLAIMED',flush=True)
    assert await asyncio.to_thread(sys.stdin.readline)=='go\\n'
    async with user_session(engine,owner,role=DatabaseRole.ENGINE) as session:
        await process_request(session,claim,policy=AllowPolicy())
        if sys.argv[3]=='before_commit':
            print('BEFORE_COMMIT',flush=True)
            await asyncio.Event().wait()
    print('AFTER_COMMIT',flush=True)
    await asyncio.Event().wait()
asyncio.run(main())
"""


@pytest.mark.parametrize("boundary", ["before_commit", "after_commit"])
async def test_process_kill_does_not_duplicate_transfer(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    boundary: str,
) -> None:
    await select_use(api_engine, owner)
    value = intent(owner, wallet.episode_id)
    async with user_session(api_engine, owner) as session:
        receipt = await admit_new_request(session, wallet_id=wallet.wallet_id, intent=value)
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        _CHILD,
        str(owner),
        str(receipt.request_id),
        boundary,
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
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            count = (
                await session.execute(
                    "SELECT count(*) FROM paper_order_commands WHERE idempotency_key=:key",
                    {"key": value.idempotency_key},
                )
            ).scalar_one()
            assert count == (0 if boundary == "before_commit" else 1)
            if boundary == "before_commit":
                await session.execute(
                    """UPDATE paper_order_request_dispatch
                    SET lease_until=clock_timestamp()-interval '1 second' WHERE request_id=:id""",
                    {"id": receipt.request_id},
                )
                timestamp = (
                    await session.execute(
                        """SELECT next_attempt_at FROM paper_order_request_dispatch
                    WHERE request_id=:id""",
                        {"id": receipt.request_id},
                    )
                ).scalar_one()
                claim = await claim_request(
                    session, DueRequest(receipt.request_id, owner, timestamp), worker="recovery"
                )
                assert claim is not None
        if boundary == "before_commit":
            assert claim is not None
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                await process_request(session, claim, policy=AllowPolicy())
        async with user_session(api_engine, owner) as session:
            view = await request_view(session, receipt.request_id)
            assert (
                view is not None
                and view.intake_state == "TRANSFERRED"
                and view.command_id is not None
            )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            assert (
                await session.execute(
                    "SELECT count(*) FROM paper_order_commands WHERE idempotency_key=:key",
                    {"key": value.idempotency_key},
                )
            ).scalar_one() == 1
            assert (
                await session.execute(
                    "SELECT count(*) FROM paper_reservations WHERE episode_id=:episode",
                    {"episode": wallet.episode_id},
                )
            ).scalar_one() == 0
    finally:
        if process.returncode is None:
            process.kill()
            await asyncio.wait_for(process.wait(), 5)


async def test_real_commit_ack_loss_recovers_same_intake_key(
    api_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    from dataclasses import replace

    from sqlalchemy.ext.asyncio import create_async_engine

    from tests.infra.execution_market.commit_proxy import drop_commit_reply
    from tiewtrade.infra.db import InfraError
    from tiewtrade.infra.paper_orders.requests import get_request_by_key

    value = intent(owner, wallet.episode_id)
    armed, dropped = asyncio.Event(), asyncio.Event()
    async with drop_commit_reply(
        api_engine.url.host or "localhost", api_engine.url.port or 5432, armed, dropped
    ) as port:
        proxy = create_async_engine(
            api_engine.url.set(host="127.0.0.1", port=port),
            connect_args={"ssl": False},
            hide_parameters=True,
        )
        try:
            async with asyncio.timeout(10):
                with pytest.raises(InfraError):
                    async with user_session(proxy, owner) as session:
                        await admit_new_request(session, wallet_id=wallet.wallet_id, intent=value)
                        armed.set()
            assert dropped.is_set()
        finally:
            await proxy.dispose()
    async with user_session(api_engine, owner) as session:
        original = await get_request_by_key(session, action="NEW", key=value.idempotency_key)
        assert original is not None
        replay = await admit_new_request(
            session, wallet_id=wallet.wallet_id, intent=replace(value, order_id=uuid4())
        )
        assert replay.request_id == original.request_id and replay.order_id == original.order_id
