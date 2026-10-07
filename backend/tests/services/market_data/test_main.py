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
