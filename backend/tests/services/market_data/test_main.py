from datetime import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.services.market_data import main
from tiewtrade.services.market_data.ingestion import RoundSummary
from tiewtrade.venues import FakeVenue
from tiewtrade.venues.candles import CandleSource


async def test_once_uses_injected_source_and_one_round(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    source = FakeVenue()
    calls = 0

    async def one_round(
        engine: AsyncEngine, source: CandleSource, worker: str, as_of: datetime
    ) -> RoundSummary:
        nonlocal calls
        calls += 1
        assert isinstance(source, FakeVenue)
        assert worker
        assert as_of.tzinfo is not None
        return RoundSummary()

    monkeypatch.setattr(main, "run_round", one_round)
    try:
        await main.serve(once=True, source=source, engine=engine)
        assert calls == 1
    finally:
        await engine.dispose()


async def test_continuous_runner_composes_prices_and_candles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio

    from tiewtrade.venues.fake import FakePriceFeed

    monkeypatch.setenv("TIEWTRADE_REDIS_URL_MARKET_DATA", "redis://127.0.0.1:56379/0")
    started = asyncio.Event()
    canceled = asyncio.Event()
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    feed = FakePriceFeed(snapshots={})

    class Supervisor:
        def __init__(self, *args: object) -> None:
            assert args[1] is feed

        async def run(self) -> None:
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                canceled.set()

    async def one_round(*args: object) -> RoundSummary:
        await started.wait()
        raise asyncio.CancelledError()

    monkeypatch.setattr(main, "QuoteSupervisor", Supervisor, raising=False)
    monkeypatch.setattr(main, "run_round", one_round)
    try:
        with pytest.raises(asyncio.CancelledError):
            await main.serve(source=FakeVenue(), engine=engine, price_feed=feed)
        assert canceled.is_set()
    finally:
        await engine.dispose()
