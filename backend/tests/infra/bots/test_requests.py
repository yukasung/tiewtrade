import asyncio
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.core.orders import TradingMode
from tiewtrade.infra.bots.claims import (
    BotClaimLostError,
    claim_control,
    due_controls,
    finish_control,
)
from tiewtrade.infra.bots.requests import (
    BotReceipt,
    BotRequestConflictError,
    receipt_by_id,
    receipt_by_key,
    submit_start,
)
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.db.session import scan_session_bypassing_rls
from tiewtrade.infra.users import create_user


@pytest.mark.asyncio
async def test_concurrent_start_and_recovery_by_original_key(api_engine: AsyncEngine) -> None:
    owner, other, key = uuid4(), uuid4(), uuid4()
    await create_user(api_engine, owner)
    await create_user(api_engine, other)
    payload: dict[str, object] = {"strategy_config_ref": "fixture"}
    first_inserted = asyncio.Event()
    second_started = asyncio.Event()

    async def submit(*, first: bool) -> BotReceipt:
        if not first:
            await first_inserted.wait()
        async with user_session(api_engine, owner, role=DatabaseRole.API) as session:
            if not first:
                second_started.set()
            result = await submit_start(
                session, mode=TradingMode.PAPER, request_id=uuid4(), key=key, payload=payload
            )
            if first:
                first_inserted.set()
                await second_started.wait()
            return result

    async with asyncio.timeout(10):
        first, second = await asyncio.gather(submit(first=True), submit(first=False))
    assert first == second
    assert first.pending

    # A fresh transaction recovers the receipt without the POST response or server ID.
    async with user_session(api_engine, owner, role=DatabaseRole.API) as session:
        assert await receipt_by_key(session, TradingMode.PAPER, key) == first
        assert await receipt_by_key(session, TradingMode.LIVE, key) is None
        assert await receipt_by_id(session, TradingMode.PAPER, first.request_id) == first
        count = await session.execute(
            "SELECT count(*) FROM bot_control_requests WHERE idempotency_key=:key", {"key": key}
        )
        assert count.scalar_one() == 1
        with pytest.raises(BotRequestConflictError):
            await submit_start(
                session,
                mode=TradingMode.PAPER,
                request_id=uuid4(),
                key=key,
                payload={"strategy_config_ref": "different"},
            )
    async with user_session(api_engine, other, role=DatabaseRole.API) as session:
        assert await receipt_by_key(session, TradingMode.PAPER, key) is None
        assert await receipt_by_id(session, TradingMode.PAPER, first.request_id) is None
        visible = await session.execute("SELECT count(*) FROM bot_control_requests")
        assert visible.scalar_one() == 0


@pytest.mark.asyncio
async def test_bot_storage_does_not_grant_writes_outside_role(api_engine: AsyncEngine) -> None:
    async with user_session(api_engine, uuid4(), role=DatabaseRole.API) as session:
        grants = await session.execute("""SELECT
          has_table_privilege('tiewtrade_api','bot_runs','UPDATE'),
          has_column_privilege('tiewtrade_engine','bot_runs','strategy_version','UPDATE'),
          has_column_privilege('tiewtrade_engine','bot_runs','revision','UPDATE'),
          has_column_privilege('tiewtrade_engine_scan','bot_control_requests','payload','SELECT'),
          has_table_privilege('tiewtrade_engine','bot_decisions','UPDATE')""")
        assert tuple(grants.one()) == (False, False, True, False, False)


@pytest.mark.asyncio
async def test_expired_claim_cannot_complete_after_takeover(
    api_engine: AsyncEngine, engine_engine: AsyncEngine, scan_engine: AsyncEngine
) -> None:
    owner = uuid4()
    await create_user(api_engine, owner)
    async with user_session(api_engine, owner, role=DatabaseRole.API) as session:
        receipt = await submit_start(
            session,
            mode=TradingMode.PAPER,
            request_id=uuid4(),
            key=uuid4(),
            payload={"strategy_config_ref": "fixture"},
        )
    async with scan_session_bypassing_rls(scan_engine) as scan:
        hint = next(
            item for item in await due_controls(scan) if item.request_id == receipt.request_id
        )
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        old = await claim_control(session, hint)
        assert old is not None
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        assert await claim_control(session, hint) is None
        await session.execute(
            """UPDATE bot_control_dispatch SET lease_until=clock_timestamp()-interval '1 second'
            WHERE request_id=:id""",
            {"id": receipt.request_id},
        )
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        current = await claim_control(session, hint)
        assert current is not None and current.revision == old.revision + 1
        with pytest.raises(BotClaimLostError):
            await finish_control(session, old, failure_code="STALE")
        await finish_control(session, current, failure_code="NOT_READY")
    async with user_session(api_engine, owner, role=DatabaseRole.API) as session:
        result = await receipt_by_key(session, TradingMode.PAPER, receipt.key)
        assert result is not None and result.failure_code == "NOT_READY"
    async with scan_session_bypassing_rls(scan_engine) as scan:
        assert hint not in await due_controls(scan)
