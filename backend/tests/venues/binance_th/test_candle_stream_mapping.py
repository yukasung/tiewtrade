import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tiewtrade.core.candle_preview import Progress, compare
from tiewtrade.core.market_data import CandleFinality, CandleSeries, Timeframe, next_open
from tiewtrade.core.money import Money, Quantity
from tiewtrade.venues.binance_th.candle_stream_mapping import candle_from_stream
from tiewtrade.venues.errors import VenueProtocolError

EVIDENCE = Path(__file__).parents[4] / "specs/features/2026-10-12-candlestick-chart/evidence"
SERIES = tuple(CandleSeries(base, "USDT", tf) for base in ("BTC", "ETH") for tf in Timeframe)


def sample() -> dict[str, object]:
    fixture = json.loads((EVIDENCE / "kline-public.json").read_text(encoding="utf-8"))
    return next(
        json.loads(frame["raw"])
        for frame in fixture["frames"]
        if "data" in json.loads(frame["raw"])
    )


def test_recorded_frames_all_decode_with_exact_ohlcv() -> None:
    fixture = json.loads((EVIDENCE / "kline-public.json").read_text(encoding="utf-8"))
    observed = set()
    for frame in fixture["frames"]:
        payload = json.loads(frame["raw"])
        if "data" not in payload:
            continue
        result = candle_from_stream(
            payload=payload, series=SERIES, received_at=datetime.fromisoformat(frame["received_at"])
        )
        observed.add((result.candle.base, result.candle.timeframe))
        assert result.candle.close == Money.of(payload["data"]["k"]["c"], "USDT")
        assert result.candle.finality is not CandleFinality.CLOSED
    assert len(observed) == 12


@pytest.mark.parametrize(
    "field,value",
    [("n", True), ("x", 1), ("o", 1.2), ("i", "9m"), ("t", True), ("v", "NaN"), ("s", "UNKNOWN")],
)
def test_invalid_fields_fail_closed(field: str, value: object) -> None:
    payload = sample()
    payload["data"]["k"][field] = value  # type: ignore[index]
    with pytest.raises(VenueProtocolError):
        candle_from_stream(payload=payload, series=SERIES, received_at=datetime.now(UTC))


def test_closure_hint_never_becomes_closed_history() -> None:
    payload = sample()
    payload["data"]["k"]["x"] = True  # type: ignore[index]
    result = candle_from_stream(payload=payload, series=SERIES, received_at=datetime.now(UTC))
    assert result.closed_hint and result.candle.finality is CandleFinality.UNCONFIRMED


@pytest.mark.parametrize("timeframe", [Timeframe.W1, Timeframe.MN1])
def test_week_and_month_stream_names_and_calendar_close_are_native(
    timeframe: Timeframe,
) -> None:
    payload = sample()
    opened = datetime(2026, 2, 1 if timeframe is Timeframe.MN1 else 2, tzinfo=UTC)
    ended = next_open(opened, timeframe)
    epoch = datetime(1970, 1, 1, tzinfo=UTC)
    payload["stream"] = f"btcusdt@kline_{timeframe.value}"
    payload["data"]["k"].update(  # type: ignore[index, union-attr]
        {
            "i": timeframe.value,
            "t": (opened - epoch) // timedelta(milliseconds=1),
            "T": (ended - epoch) // timedelta(milliseconds=1) - 1,
        }
    )
    result = candle_from_stream(
        payload=payload,
        series=SERIES,
        received_at=opened + timedelta(seconds=1),
    )
    assert result.candle.timeframe is timeframe
    assert result.candle.open_at == opened
    assert result.candle.end_at == ended


@given(st.integers(min_value=1, max_value=10000), st.integers(min_value=1, max_value=10000))
def test_cumulative_order_ignores_event_time_and_detects_equal_progress_conflict(
    n: int,
    increment: int,
) -> None:
    old = candle_from_stream(payload=sample(), series=SERIES, received_at=datetime.now(UTC))
    old = replace(
        old,
        trade_count=n,
        first_trade_id=1,
        last_trade_id=n,
        candle=replace(
            old.candle,
            open=Money.of(100, "USDT"),
            high=Money.of(101, "USDT"),
            low=Money.of(99, "USDT"),
            close=Money.of(100, "USDT"),
            volume=Quantity.of(n, old.candle.base),
        ),
    )
    new = replace(
        old,
        trade_count=n + increment,
        last_trade_id=n + increment,
        candle=replace(
            old.candle,
            high=Money.of(102, "USDT"),
            volume=Quantity.of(n + increment, old.candle.base),
        ),
    )
    assert compare(old, new) is Progress.NEWER
    assert compare(new, old) is Progress.OLDER
    assert compare(new, new) is Progress.DUPLICATE
    conflict = replace(new, candle=replace(new.candle, close=Money.of(101, "USDT")))
    assert compare(new, conflict) is Progress.CONFLICT
