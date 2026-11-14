"""Accounting reads preserve financial evidence while leaving reset fail-closed."""

from collections.abc import Mapping
from dataclasses import replace
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.db.session import UserSession
from tiewtrade.infra.paper_wallet import get_wallet
from tiewtrade.infra.paper_wallet.records import ACTIVITY_UNKNOWN, PaperWalletSnapshot
from tiewtrade.infra.users import create_user


@pytest.mark.usefixtures("internal_database")
@pytest.mark.parametrize("role", [DatabaseRole.API, DatabaseRole.ENGINE])
async def test_current_accounting_matches_default_without_reset_function(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    owner: UUID,
    production_wallet: PaperWalletSnapshot,
    monkeypatch: pytest.MonkeyPatch,
    role: DatabaseRole,
) -> None:
    statements: list[str] = []
    original = UserSession.execute

    async def observed(
        session: UserSession, statement: str, parameters: Mapping[str, object] | None = None
    ) -> Any:
        statements.append(statement)
        return await original(session, statement, parameters)

    monkeypatch.setattr(UserSession, "execute", observed)
    engine = api_engine if role is DatabaseRole.API else engine_engine
    async with user_session(engine, owner, role=role) as session:
        complete = await get_wallet(session)
        assert complete is not None and complete.reset_available
        assert any("paper_wallet_reset_readiness" in sql for sql in statements)
        statements.clear()
        accounting = await get_wallet(session, include_reset_readiness=False)
        assert accounting is not None
        assert not any("paper_wallet_reset_readiness" in sql for sql in statements)
        assert any("FROM paper_wallet_ledger" in sql for sql in statements)
        assert accounting.reset_available is False
        assert accounting.reset_reason == ACTIVITY_UNKNOWN
        assert (
            replace(
                accounting,
                snapshot_at=complete.snapshot_at,
                reset_available=complete.reset_available,
                reset_reason=complete.reset_reason,
            )
            == complete
        )
        # The lightweight choice cannot leak into later default API/reset reads.
        statements.clear()
        again = await get_wallet(session)
        assert again is not None and again.reset_available
        assert any("paper_wallet_reset_readiness" in sql for sql in statements)


@pytest.mark.usefixtures("internal_database")
async def test_accounting_remains_owner_scoped(
    api_engine: AsyncEngine,
    production_wallet: PaperWalletSnapshot,
) -> None:
    other = uuid4()
    await create_user(api_engine, other)
    async with user_session(api_engine, other) as session:
        assert await get_wallet(session, include_reset_readiness=False) is None
        assert await get_wallet(session) is None
