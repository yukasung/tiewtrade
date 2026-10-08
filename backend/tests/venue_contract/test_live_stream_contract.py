"""Bounded, credential-free TH stream contract; excluded from merge gates."""

import asyncio
from datetime import UTC, datetime

import pytest

from tiewtrade.venues.binance_th.stream_transport import BinanceThStreamTransport
from tiewtrade.venues.price_streams import FeedConnected, FeedDisconnected, FeedQuote
from tiewtrade.venues.symbols import Symbol

pytestmark = pytest.mark.venue_contract


async def test_public_trade_stream_has_ack_and_all_five_pairs_within_capture() -> None:
    pairs = tuple(Symbol(base, "USDT") for base in ("BTC", "ETH", "SOL", "XRP", "DOGE"))
    events = BinanceThStreamTransport(clock=lambda: datetime.now(UTC)).connection(
        pairs, generation=1
    )
    seen: set[str] = set()
    acknowledged = False
    try:
        async with asyncio.timeout(30):
            async for event in events:
                if isinstance(event, FeedConnected):
                    acknowledged = True
                elif isinstance(event, FeedQuote):
                    assert acknowledged, "trade appeared before the subscription gate"
                    assert event.quote.quote == "USDT"
                    seen.add(event.quote.base)
                    if seen == {pair.base for pair in pairs}:
                        return
                elif isinstance(event, FeedDisconnected):
                    if event.failure_code == "VENUE_PROTOCOL":
                        pytest.fail("public TH stream contract rejected by parser")
                    pytest.skip(f"inconclusive public capture: {event.failure_code}")
    except TimeoutError:
        pytest.skip(
            f"inconclusive public capture: missing pairs {sorted({p.base for p in pairs} - seen)}"
        )
    finally:
        await events.aclose()
    pytest.fail("public TH stream ended without a disconnect event")
