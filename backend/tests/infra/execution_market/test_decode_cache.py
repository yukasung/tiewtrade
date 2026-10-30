"""Cached public values never bypass fresh execution-source proof checks."""

from dataclasses import fields, is_dataclass, replace
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market.test_storage import PAIR, prepared
from tiewtrade.core.orders import SourceUnavailableError
from tiewtrade.infra.db import DatabaseRole, create_engine_for, user_session
from tiewtrade.infra.db.session import market_data_session
from tiewtrade.infra.market_data.order_book_codec import input_payload
from tiewtrade.infra.market_data.order_book_storage import (
    _decode_execution_input,
    metadata_payload,
    publish_input,
    read_inputs,
)


@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "payload",
        "capability",
        "digest",
        "identity",
        "generation",
        "lease",
        "ready",
        "verified",
    ],
)
async def test_warm_cache_still_rejects_changed_source(
    engine_engine: AsyncEngine, migrator_engine: AsyncEngine, fault: str
) -> None:
    market = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        lease, book, metadata = await prepared(market)
        async with market_data_session(market) as session:
            await publish_input(session, lease, book, metadata)
        _decode_execution_input.cache_clear()
        async with user_session(engine_engine, uuid4(), role=DatabaseRole.ENGINE) as session:
            cold = await read_inputs(session, PAIR, after=book.input_id - 1)
            warm = await read_inputs(session, PAIR, after=book.input_id - 1)
            assert cold == warm and warm[0].market == book and warm[0].metadata == metadata
        assert _decode_execution_input.cache_info().hits == 1
        changes = {
            "payload": "payload=jsonb_set(payload,'{rebase}','false'::jsonb)",
            "capability": (
                "capability=jsonb_set(capability,'{source_document}','\"tampered\"'::jsonb)"
            ),
            "digest": "digest=repeat('0',64)",
            "identity": "received_at=received_at+interval '1 millisecond'",
            "generation": "generation=generation+1",
            "lease": "lease_until=clock_timestamp()-interval '1 second'",
            "ready": "ready=false",
            "verified": "verified_at=clock_timestamp()-interval '2 seconds'",
        }
        async with market_data_session(market) as session:
            if fault == "missing":
                async with migrator_engine.begin() as admin:
                    await admin.execute(
                        text(
                            "DELETE FROM market_execution_buffer WHERE base='BTC' AND input_id=:id"
                        ),
                        {"id": book.input_id},
                    )
            elif fault in {"generation", "lease", "ready", "verified"}:
                await session.execute(
                    f"UPDATE market_execution_state SET {changes[fault]} WHERE base='BTC'"
                )
            else:
                await session.execute(
                    f"UPDATE market_execution_buffer SET {changes[fault]} "
                    "WHERE base='BTC' AND input_id=:id",
                    {"id": book.input_id},
                )
        async with user_session(engine_engine, uuid4(), role=DatabaseRole.ENGINE) as session:
            with pytest.raises(SourceUnavailableError):
                await read_inputs(session, PAIR, after=book.input_id - 1)
    finally:
        await market.dispose()


def assert_immutable(value: object) -> None:
    assert not isinstance(value, (list, dict, set))
    if is_dataclass(value) and not isinstance(value, type):
        assert type(value).__dict__["__dataclass_params__"].frozen
        for field in fields(value):
            assert_immutable(getattr(value, field.name))
    elif isinstance(value, (tuple, frozenset)):
        for item in value:
            assert_immutable(item)


async def test_eviction_preserves_exact_values_and_cached_graph_is_immutable() -> None:
    market = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        _, book, metadata = await prepared(market)
        payload, capability = input_payload(book), metadata_payload(metadata)
        _decode_execution_input.cache_clear()
        original = _decode_execution_input(payload, capability)
        assert_immutable(original)
        for index in range(1, 257):
            _decode_execution_input(
                input_payload(replace(book, input_id=book.input_id + index)), capability
            )
        assert _decode_execution_input.cache_info().currsize == 256
        restored = _decode_execution_input(payload, capability)
        assert restored == original
        assert restored is not original
        assert_immutable(restored)
    finally:
        await market.dispose()
