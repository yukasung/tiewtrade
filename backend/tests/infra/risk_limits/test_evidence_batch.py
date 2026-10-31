"""Batch evidence preserves all immutable inputs and transaction rollback."""

import asyncio
import hashlib
from collections.abc import Mapping
from dataclasses import replace
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market.test_evidence import source_record
from tiewtrade.core.order_book import BookState
from tiewtrade.core.orders import OrderConflictError, SimulationProfile
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.db.session import UserSession
from tiewtrade.infra.market_data.order_book_codec import input_payload
from tiewtrade.infra.market_data.order_book_storage import StoredExecutionInput, metadata_payload
from tiewtrade.infra.paper_orders.records import SavedExecutionInput
from tiewtrade.infra.paper_orders.storage import (
    append_execution_inputs,
    pin_execution_profile,
    read_execution_inputs,
)
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot


async def test_concurrent_batch_replay_keeps_every_input_and_conflict_rolls_back(
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = source_record()
    assert isinstance(original.market, BookState)
    records = []
    for number in range(1, 22):
        market = replace(original.market, input_id=number)
        digest = hashlib.sha256(
            (input_payload(market) + "\n" + metadata_payload(original.metadata)).encode()
        ).hexdigest()
        records.append(StoredExecutionInput(market, original.metadata, digest))
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await pin_execution_profile(
            session,
            wallet_id=wallet.wallet_id,
            episode_id=wallet.episode_id,
            profile=SimulationProfile(),
        )

    async def append(values: list[StoredExecutionInput]) -> tuple[SavedExecutionInput, ...]:
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            return await append_execution_inputs(
                session,
                wallet_id=wallet.wallet_id,
                episode_id=wallet.episode_id,
                inputs=tuple((uuid4(), value, None) for value in values),
            )

    first, second = await asyncio.gather(append(records[:20]), append(records[:20]))
    assert first == second and tuple(value.record for value in first) == tuple(records[:20])
    with pytest.raises(OrderConflictError, match="digest mismatch"):
        await append([records[20], replace(records[0], digest="0" * 64)])
    original_execute = UserSession.execute

    async def fail_registry(
        session: UserSession, statement: str, parameters: Mapping[str, object] | None = None
    ) -> Any:
        if "INSERT INTO paper_execution_input_keys" in statement:
            raise RuntimeError("registry write interrupted after evidence insert")
        return await original_execute(session, statement, parameters)

    with monkeypatch.context() as patch:
        patch.setattr(UserSession, "execute", fail_registry)
        with pytest.raises(RuntimeError, match="registry write interrupted"):
            await append(records[20:])
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        saved = await read_execution_inputs(
            session, episode_id=wallet.episode_id, pair=original.market.pair
        )
        assert saved == first
        assert (
            await session.execute("SELECT count(*) FROM paper_execution_inputs")
        ).scalar_one() == 20
        assert (await session.execute("SELECT count(*) FROM paper_orders")).scalar_one() == 0
