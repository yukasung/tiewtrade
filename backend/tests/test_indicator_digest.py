from datetime import UTC, datetime, timedelta, timezone

import pytest

from tiewtrade.core.market_data import CandleWindow, Timeframe
from tiewtrade.infra.market_data.indicator_reader import IndicatorDigest

SPAN = timedelta(minutes=1)


@pytest.mark.parametrize("size", [1, 2, 16, 1000])
@pytest.mark.parametrize("zone", [UTC, timezone(timedelta(hours=7))])
def test_missing_digest_batch_is_byte_exact(size: int, zone: timezone) -> None:
    start = datetime(2026, 10, 13, tzinfo=zone)
    window = CandleWindow(start, start + size * SPAN)
    scalar = IndicatorDigest("BTC", "USDT", Timeframe.M1, window)
    batched = IndicatorDigest("BTC", "USDT", Timeframe.M1, window)
    slots = tuple((start + index * SPAN, None) for index in range(size))
    for moment, row in slots:
        scalar.feed(moment, row)
    batched.feed_batch(slots)
    assert batched.hexdigest() == scalar.hexdigest()
