"""Reuse worker snapshot proof while rereading current owner financial quantities."""

from collections.abc import Mapping
from dataclasses import replace
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market.test_executions import prepare_fill, write_fill
from tiewtrade.core.money import Quantity
from tiewtrade.core.orders import SourceUnavailableError
from tiewtrade.core.positions import PositionAvailability, PositionPair
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.db.session import UserSession
from tiewtrade.infra.paper_orders.initialization import enable_financial_writer
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot
from tiewtrade.infra.positions import read_position_snapshot
from tiewtrade.infra.positions.views import held_and_reserved


@pytest.mark.usefixtures("internal_database")
async def test_worker_holdings_match_default_with_actual_fill_and_current_sql(
    engine_engine: AsyncEngine,
    api_engine: AsyncEngine,
    owner: UUID,
    production_wallet: PaperWalletSnapshot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wallet = production_wallet
    event, position, fact = await prepare_fill(engine_engine, owner, wallet)
    await write_fill(engine_engine, owner, wallet, event, position, fact)
    pair = PositionPair("BTC", "USDT")
    statements: list[str] = []
    original = UserSession.execute

    async def observed(
        session: UserSession, statement: str, parameters: Mapping[str, object] | None = None
    ) -> Any:
        statements.append(statement)
        return await original(session, statement, parameters)

    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        snapshot = await read_position_snapshot(session, wallet.episode_id)
        assert snapshot is not None
        expected = await held_and_reserved(session, wallet.episode_id, pair)
        monkeypatch.setattr(UserSession, "execute", observed)
        actual = await held_and_reserved(
            session, wallet.episode_id, pair, validated_snapshot=snapshot
        )
        assert actual == expected == (Quantity.of("0.999", "BTC"), Quantity.of(0, "BTC"))
        assert len(statements) == 1
        assert "paper_wallet_reset_readiness" not in statements[0]
        assert all(
            table in statements[0]
            for table in (
                "paper_position_activity",
                "paper_position_projections",
                "paper_reservations",
            )
        )
        # Even a supplied snapshot with different numeric values is never the quantity source.
        altered = replace(snapshot, positions=())
        assert (
            await held_and_reserved(session, wallet.episode_id, pair, validated_snapshot=altered)
            == actual
        )
    statements.clear()
    async with user_session(api_engine, owner) as session:
        assert await held_and_reserved(session, wallet.episode_id, pair) == expected
    assert any("paper_wallet_reset_readiness" in sql for sql in statements)


@pytest.mark.usefixtures("internal_database")
@pytest.mark.parametrize(
    "field",
    [
        "user_id",
        "episode_id",
        "mode",
        "availability",
        "source_proof",
        "revision",
        "source_sequence",
    ],
)
async def test_worker_rejects_wrong_scope_unready_or_stale_snapshot(
    engine_engine: AsyncEngine,
    owner: UUID,
    production_wallet: PaperWalletSnapshot,
    field: str,
) -> None:
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        snapshot = await read_position_snapshot(session, production_wallet.episode_id)
        assert snapshot is not None
        invalid: dict[str, Any] = {
            "user_id": uuid4(),
            "episode_id": uuid4(),
            "mode": "LIVE",
            "availability": PositionAvailability.UNKNOWN,
            "source_proof": None,
            "revision": snapshot.activity.revision + 1,
            "source_sequence": snapshot.activity.source_sequence + 1,
        }
        changed = replace(snapshot, activity=replace(snapshot.activity, **{field: invalid[field]}))
        with pytest.raises(SourceUnavailableError):
            await held_and_reserved(
                session,
                production_wallet.episode_id,
                PositionPair("BTC", "USDT"),
                validated_snapshot=changed,
            )


@pytest.mark.usefixtures("internal_database")
async def test_worker_rechecks_source_after_snapshot(
    engine_engine: AsyncEngine,
    owner: UUID,
    production_wallet: PaperWalletSnapshot,
) -> None:
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        snapshot = await read_position_snapshot(session, production_wallet.episode_id)
        assert snapshot is not None
        await enable_financial_writer(session)
        await session.execute(
            "UPDATE paper_position_activity SET revision=revision+1 WHERE episode_id=:episode",
            {"episode": production_wallet.episode_id},
        )
        with pytest.raises(SourceUnavailableError):
            await held_and_reserved(
                session,
                production_wallet.episode_id,
                PositionPair("BTC", "USDT"),
                validated_snapshot=snapshot,
            )
