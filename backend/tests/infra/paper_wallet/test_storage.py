from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.infra.db import DatabaseRole, UserSession, scan_session_bypassing_rls, user_session
from tiewtrade.infra.db.errors import AppendOnlyViolationError, NotPermittedError
from tiewtrade.infra.paper_wallet import (
    PaperCommand,
    PaperCommandState,
    PaperWalletAction,
    PaperWalletIntegrityError,
    admit_command,
    get_command,
    get_wallet,
    inspect_submission,
)
from tiewtrade.services.engine.paper_wallet import run_paper_wallet_round


async def _submit(
    api_engine: AsyncEngine,
    owner: UUID,
    key: UUID,
    capital: str = "1234.567890123456789012",
) -> PaperCommand:
    async with user_session(api_engine, owner) as session:
        previous = await inspect_submission(
            session,
            action=PaperWalletAction.CREATE,
            idempotency_key=key,
            capital_text=capital,
            expected_episode_id=None,
        )
        if previous is not None:
            return previous
        return await admit_command(
            session,
            action=PaperWalletAction.CREATE,
            idempotency_key=key,
            capital_text=capital,
            expected_episode_id=None,
        )


async def test_concurrent_replay_creates_one_command(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
) -> None:
    key = uuid4()
    first, second = await asyncio.gather(
        _submit(api_engine, owner, key),
        _submit(api_engine, owner, key),
    )
    assert first == second
    assert first.state is PaperCommandState.PENDING
    async with user_session(api_engine, owner) as session:
        count = (
            await session.execute(
                "SELECT count(*) FROM paper_wallet_commands WHERE idempotency_key=:key",
                {"key": key},
            )
        ).scalar_one()
    assert count == 1
    await run_paper_wallet_round(
        engine=engine_engine,
        scan_engine=scan_engine,
        worker="test-worker",
    )


async def test_equivalent_money_text_replays_the_same_command(
    api_engine: AsyncEngine,
    owner: UUID,
) -> None:
    key = uuid4()
    first = await _submit(api_engine, owner, key, "1500")
    replay = await _submit(api_engine, owner, key, "1500.00")

    assert replay == first


async def test_worker_creates_exact_wallet_and_reset_fails_closed(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
) -> None:
    created = await _submit(api_engine, owner, uuid4())
    result = await run_paper_wallet_round(
        engine=engine_engine,
        scan_engine=scan_engine,
        worker="test-worker",
    )
    assert result.processed >= 1

    async with user_session(api_engine, owner) as session:
        command = await get_command(session, created.command_id)
        wallet = await get_wallet(session)
        assert command is not None and command.state is PaperCommandState.SUCCEEDED
        assert wallet is not None
        assert wallet.initial_capital.as_parts()["amount"] == "1234.567890123456789012"
        assert wallet.balance == wallet.initial_capital
        episode_id = wallet.episode_id
        reset_key = uuid4()
        reset = await admit_command(
            session,
            action=PaperWalletAction.RESET,
            idempotency_key=reset_key,
            capital_text="2000",
            expected_episode_id=episode_id,
        )

    rejected = await run_paper_wallet_round(
        engine=engine_engine,
        scan_engine=scan_engine,
        worker="test-worker",
    )
    assert rejected.rejected >= 1
    async with user_session(api_engine, owner) as session:
        reset_result = await get_command(session, reset.command_id)
        unchanged = await get_wallet(session)
        assert reset_result == PaperCommand(
            reset.command_id, PaperCommandState.REJECTED, "ACTIVITY_UNKNOWN"
        )
        assert unchanged is not None and unchanged.episode_id == episode_id


async def test_owner_isolation_hides_wallet_and_command(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
) -> None:
    from tiewtrade.infra.users import create_user

    command = await _submit(api_engine, owner, uuid4())
    await run_paper_wallet_round(
        engine=engine_engine,
        scan_engine=scan_engine,
        worker="test-worker",
    )
    stranger = uuid4()
    await create_user(api_engine, stranger)
    async with user_session(api_engine, stranger) as session:
        assert await get_wallet(session) is None
        assert await get_command(session, command.command_id) is None


async def test_invalid_admission_is_a_stable_audited_result(
    api_engine: AsyncEngine, owner: UUID
) -> None:
    key = uuid4()
    async with user_session(api_engine, owner) as session:
        rejected = await admit_command(
            session,
            action=PaperWalletAction.CREATE,
            idempotency_key=key,
            capital_text="1000",
            expected_episode_id=None,
        )
    assert rejected.state is PaperCommandState.REJECTED
    assert rejected.failure_code == "INITIAL_CAPITAL_TOO_SMALL"
    async with user_session(api_engine, owner) as session:
        replay = await inspect_submission(
            session,
            action=PaperWalletAction.CREATE,
            idempotency_key=key,
            capital_text="1000",
            expected_episode_id=None,
        )
        audit_count = (
            await session.execute(
                """SELECT count(*) FROM audit_events
                   WHERE owner_user_id=:owner
                     AND action='PAPER_WALLET_CREATE_REJECTED'
                     AND subject_id=:subject""",
                {"owner": owner, "subject": str(rejected.command_id)},
            )
        ).scalar_one()
    assert replay == rejected
    assert audit_count == 1


async def test_financial_ledger_is_append_only(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
) -> None:
    await _submit(api_engine, owner, uuid4())
    await run_paper_wallet_round(
        engine=engine_engine,
        scan_engine=scan_engine,
        worker="test-worker",
    )
    # Production roles have no UPDATE grant. Keep accepting the trigger's
    # domain error as a second line of defence if privileges are broadened.
    with pytest.raises((NotPermittedError, AppendOnlyViolationError)):
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await session.execute(
                "UPDATE paper_wallet_ledger SET amount=amount+1 WHERE user_id=:owner",
                {"owner": owner},
            )


async def test_scan_role_only_sees_due_identifiers(scan_engine: AsyncEngine) -> None:
    async with scan_session_bypassing_rls(scan_engine) as session:
        columns = (
            (
                await session.execute(
                    """SELECT column_name FROM information_schema.column_privileges
                   WHERE grantee='tiewtrade_engine_scan'
                     AND table_name='paper_wallet_commands'"""
                )
            )
            .scalars()
            .all()
        )
        ledger_foreign_keys = (
            (
                await session.execute(
                    """SELECT pg_get_constraintdef(oid) FROM pg_constraint
                   WHERE conrelid='paper_wallet_ledger'::regclass AND contype='f'"""
                )
            )
            .scalars()
            .all()
        )
    assert set(columns) == {"id", "user_id", "requested_at"}
    assert any(
        "FOREIGN KEY (source_command_id, user_id)" in definition
        and "paper_wallet_commands(id, user_id)" in definition
        for definition in ledger_foreign_keys
    )


async def test_wallet_read_fails_closed_when_active_episode_has_no_ledger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tiewtrade.infra.paper_wallet import storage

    row = SimpleNamespace(
        wallet_id=uuid4(),
        active_episode_id=uuid4(),
        episode_id=uuid4(),
        sequence=1,
        initial_capital="1500",
        currency="USDT",
        started_at=datetime.now(UTC),
        revision=1,
        episode_closed=False,
        snapshot_at=datetime.now(UTC),
    )
    session = SimpleNamespace(
        user_id=uuid4(),
        execute=AsyncMock(
            side_effect=[SimpleNamespace(first=lambda: row), SimpleNamespace(all=lambda: [])]
        ),
    )
    monkeypatch.setattr(storage, "require_user_session", lambda candidate: candidate)

    with pytest.raises(PaperWalletIntegrityError):
        await storage.get_wallet(cast(UserSession, session))
