"""Real process composition requires the same disposable E2E guard as its worker."""

import asyncio
import os
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text

from tests.e2e_candle_runner import run
from tiewtrade.core.market_data import CandleSeries, Timeframe, previous_open
from tiewtrade.core.money import Money
from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.infra.db.session import indicator_read_session
from tiewtrade.infra.market_data.candle_preview import read_live

pytestmark = pytest.mark.skipif(
    not os.environ.get("TIEWTRADE_E2E_DATABASE_NAME"),
    reason="Process composition deliberately requires an owned disposable E2E database",
)


@pytest.mark.parametrize("repair", [False, True])
async def test_native_3m_process_recovery_is_opt_in_and_stop_joins_workers(
    tmp_path: Path, repair: bool
) -> None:
    # Let the actual worker validate its role URL/database guard before any mutation.
    control = tmp_path / "control"
    control.write_text("stop")
    await run(control)
    migrator = create_engine_for(DatabaseRole.MIGRATOR)
    api = create_engine_for(DatabaseRole.API)
    worker: asyncio.Task[None] | None = None
    try:
        async with migrator.begin() as connection:
            result = await connection.execute(text("SELECT current_database()"))
            database_name: str = result.scalar_one()
            assert database_name == os.environ["TIEWTRADE_E2E_DATABASE_NAME"]
            await connection.execute(text("SELECT begin_indicator_source_write()"))
            await connection.execute(text("DELETE FROM market_candles"))
            await connection.execute(text("DELETE FROM market_candle_demand"))
            await connection.execute(text("DELETE FROM market_candle_preview"))
            await connection.execute(
                text(
                    """UPDATE market_candle_feed_state
                    SET lease_until=clock_timestamp(),metadata='{}'"""
                )
            )
        control.write_text("healthy")
        worker = asyncio.create_task(run(control, repair_three_minute=repair))
        previous_slots: dict[str, datetime] = {}
        async with asyncio.timeout(8):
            while True:
                if worker.done():
                    await worker
                    pytest.fail("producer ended before readiness assertion")
                seen = []
                for base, price in [
                    ("BTC", "200.000000000000000001"),
                    ("ETH", "300.000000000000000001"),
                ]:
                    async with indicator_read_session(api, uuid4()) as session:
                        feed, rows, now, recovered = await read_live(
                            session, CandleSeries(base, "USDT", Timeframe.M3)
                        )
                    if feed["connected"] and feed["lease_until"] > now and rows:
                        assert rows[-1]["open"] == Money.of(price, "USDT").amount
                        previous_slots[base] = previous_open(rows[-1]["open_at"], Timeframe.M3)
                        seen.append(recovered)
                if len(seen) == 2 and all(value is repair for value in seen):
                    break
                await asyncio.sleep(0.05)
        async with migrator.connect() as connection:
            stored_rows = (
                await connection.execute(
                    text(
                        """SELECT base,timeframe,count(*),count(DISTINCT open_at),
                        bool_and(end_at-open_at=:span)
                        FROM market_candles GROUP BY base,timeframe"""
                    ),
                    {"span": Timeframe.M3.span},
                )
            ).all()
        if repair:
            assert {tuple(row[:2]) for row in stored_rows} == {("BTC", "3m"), ("ETH", "3m")}
            assert all(row[2] == row[3] and row[2] > 0 and row[4] for row in stored_rows)
            async with migrator.connect() as connection:
                for base, previous in previous_slots.items():
                    finality, end_qualified = (
                        await connection.execute(
                            text(
                                """SELECT finality,fetch_started_at>=end_at
                                FROM market_candles WHERE source='primary_spot'
                                AND base=:base AND quote='USDT' AND timeframe='3m'
                                AND open_at=:previous"""
                            ),
                            {"base": base, "previous": previous},
                        )
                    ).one()
                    assert finality != "OPEN" and end_qualified
        else:
            assert not stored_rows  # Stream-only cannot manufacture committed REST predecessors.
        control.write_text("stop")
        await asyncio.wait_for(worker, timeout=3)
        assert worker.done()
        async with migrator.connect() as connection:
            connected, released = (
                await connection.execute(
                    text(
                        "SELECT connected,lease_until<=clock_timestamp() "
                        "FROM market_candle_feed_state"
                    )
                )
            ).one()
            assert not connected and released
    finally:
        if worker is not None and not worker.done():
            control.write_text("stop")
            worker.cancel()
            await asyncio.gather(worker, return_exceptions=True)
        await migrator.dispose()
        await api.dispose()
