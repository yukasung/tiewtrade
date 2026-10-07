from datetime import UTC, datetime, timedelta

from tiewtrade.core.market_data import CandleWindow, Timeframe
from tiewtrade.venues import FakeVenue, Symbol
from tiewtrade.venues.candles import CandlePage, CandleSource


async def test_fake_records_explicit_requests_and_queued_partial_pages() -> None:
    now = datetime(2026, 10, 7, tzinfo=UTC)
    symbol = Symbol("BTC", "USDT")
    window = CandleWindow(now, now + timedelta(minutes=1))
    page = CandlePage(symbol, Timeframe.M1, window, (), now)
    fake = FakeVenue()
    fake.queue_candle_pages([page])
    assert isinstance(fake, CandleSource)
    assert await fake.fetch_candles(symbol, Timeframe.M1, window.start, window.end, 1000) == page
    assert fake.candle_calls[0].limit == 1000
