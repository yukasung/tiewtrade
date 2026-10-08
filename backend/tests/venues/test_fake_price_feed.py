from datetime import UTC, datetime

import pytest

from tiewtrade.core.money import Money
from tiewtrade.core.realtime_prices import ObservationKind, QuoteObservation
from tiewtrade.venues.fake import FakePriceFeed
from tiewtrade.venues.price_streams import FeedConnected, FeedQuote
from tiewtrade.venues.symbols import Symbol


@pytest.mark.asyncio
async def test_fake_feed_replays_events_and_returns_configured_snapshot() -> None:
    now = datetime(2026, 10, 7, tzinfo=UTC)
    quote = QuoteObservation(
        source="primary_spot",
        base="BTC",
        quote="USDT",
        amount=Money.of("1", "USDT"),
        trade_id=1,
        trade_time=now,
        received_at=now,
        observation_kind=ObservationKind.SNAPSHOT,
    )
    pair = Symbol("BTC", "USDT")
    feed = FakePriceFeed(snapshots={pair: quote}, events=(FeedConnected(2), FeedQuote(2, quote)))
    assert await feed.snapshot(pair) == quote
    assert [event async for event in feed.events((pair,))] == [
        FeedConnected(2),
        FeedQuote(2, quote),
    ]
