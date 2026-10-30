from dataclasses import replace
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.db.test_migrations import _alembic
from tiewtrade.core.money import Money
from tiewtrade.core.realtime_prices import ObservationKind, QuoteObservation
from tiewtrade.infra.db import DatabaseRole, create_engine_for, user_session
from tiewtrade.infra.db.session import market_data_session
from tiewtrade.infra.market_data import realtime_storage
from tiewtrade.infra.market_data.catalog import runtime_pairs
from tiewtrade.infra.market_data.realtime_storage import (
    acquire_writer,
    database_now,
    read_snapshot,
    set_connected,
    write_price,
)
from tiewtrade.services.api.price_routes import snapshot_view


async def test_upgrade_starts_durable_outage_before_first_producer(
    api_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def legacy_pairs(_session: object) -> tuple[tuple[str, str], ...]:
        return tuple((base, "USDT") for base in ("BTC", "ETH", "SOL", "XRP", "DOGE"))

    current_pairs = runtime_pairs
    monkeypatch.setattr(realtime_storage, "runtime_pairs", legacy_pairs)
    _alembic("downgrade", "0013")
    _alembic("upgrade", "0014")
    market_engine = create_engine_for(DatabaseRole.MARKET_DATA)
    restarted_api_engine = create_engine_for(DatabaseRole.API)
    try:
        async with user_session(api_engine, uuid4()) as session:
            initial = await read_snapshot(session)
        assert initial.feed is not None
        assert initial.feed.owner == UUID(int=0)
        assert initial.feed.generation == 1
        assert not initial.feed.connected
        assert initial.feed.last_failure_code == "MISSING"
        assert initial.feed.lease_until <= initial.server_time
        assert len(initial.rows) == 5
        since = initial.feed.lease_until
        assert all(row.unavailable_since == since for row in initial.rows)
        assert all(row.observation is None for row in initial.rows)
        assert all(row.effective_readiness == "MISSING" for row in initial.rows)
        before = snapshot_view(
            replace(initial, server_time=since + timedelta(seconds=59, milliseconds=999)),
            delivery_connected=True,
        )
        due = snapshot_view(
            replace(initial, server_time=since + timedelta(seconds=60)),
            delivery_connected=True,
        )
        assert all(row.readiness == "MISSING" and not row.alert_due for row in before.rows)
        assert all(row.readiness == "MISSING" and row.alert_due for row in due.rows)

        async with user_session(restarted_api_engine, uuid4()) as session:
            restarted = await read_snapshot(session)
        assert restarted.rows == initial.rows

        # Historical 0014 outage facts are checked above. The current producer
        # requires the current schema, including the F18 publication protocol.
        _alembic("upgrade", "head")
        monkeypatch.setattr(realtime_storage, "runtime_pairs", current_pairs)
        async with market_data_session(market_engine) as market_session:
            lease = await acquire_writer(market_session, uuid4())
            assert lease is not None
            assert lease.generation == 2
            assert await acquire_writer(market_session, uuid4()) is None
            acquired = await read_snapshot(market_session)
            assert all(row.unavailable_since == since for row in acquired.rows)
            assert all(row.observation is None for row in acquired.rows)
            lease = await set_connected(market_session, lease, True)
            now = await database_now(market_session)
            btc = next(row for row in acquired.rows if row.base == "BTC")
            healthy = replace(
                btc,
                observation=QuoteObservation(
                    "primary_spot",
                    "BTC",
                    "USDT",
                    Money.of("100", "USDT"),
                    1,
                    now,
                    now,
                    ObservationKind.STREAM,
                ),
                reconciled_generation=lease.generation,
                effective_readiness="READY",
                reason=None,
                unavailable_since=None,
            )
            assert await write_price(market_session, lease, healthy)
        async with user_session(restarted_api_engine, uuid4()) as session:
            recovered = snapshot_view(await read_snapshot(session), delivery_connected=True)
        btc_view = next(row for row in recovered.rows if row.base == "BTC")
        assert btc_view.readiness == "READY"
        assert btc_view.unavailable_since is None
        assert not btc_view.alert_due
    finally:
        await restarted_api_engine.dispose()
        await market_engine.dispose()
        _alembic("upgrade", "head")
