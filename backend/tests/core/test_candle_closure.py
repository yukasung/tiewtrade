"""Real native observations and independent temporal/equality oracles."""

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tiewtrade.core.candle_closure import ClosureCandidate, ClosureResult, verify_closure
from tiewtrade.core.candle_preview import CandleObservation
from tiewtrade.core.market_data import (
    Candle,
    CandleFinality,
    CandleSeries,
    Timeframe,
    advance,
    align_floor,
)
from tiewtrade.core.money import Money, Quantity
from tiewtrade.venues.binance_th.candle_stream_mapping import candle_from_stream

RECORDING = (
    Path(__file__).parents[3]
    / "specs/features/2026-11-21-candle-closure-proof/evidence/public-closure-probe.json"
)


def recorded(symbol: str) -> tuple[ClosureCandidate, Candle, datetime]:
    value = json.loads(RECORDING.read_text())["closed"][symbol]
    series = CandleSeries(symbol[:-4], "USDT", Timeframe.M1)
    native = candle_from_stream(
        payload=value["payload"],
        series=(series,),
        received_at=datetime.fromisoformat(value["received_at"]),
    )
    r = value["rest_payload"][0]
    epoch = datetime(1970, 1, 1, tzinfo=UTC)
    canonical = Candle(
        series.base,
        series.quote,
        series.timeframe,
        epoch + timedelta(milliseconds=r[0]),
        epoch + timedelta(milliseconds=r[6] + 1),
        Money.of(r[1], "USDT"),
        Money.of(r[2], "USDT"),
        Money.of(r[3], "USDT"),
        Money.of(r[4], "USDT"),
        Quantity.of(r[5], series.base),
        CandleFinality.UNCONFIRMED,
        datetime.fromisoformat(value["rest_received_at"]),
    )
    return (
        ClosureCandidate(native),
        canonical,
        datetime.fromisoformat(value["rest_fetch_started_at"]),
    )


@pytest.mark.parametrize(
    "symbol,result", [("BTCUSDT", ClosureResult.MATCHED), ("ETHUSDT", ClosureResult.CONFLICT)]
)
def test_actual_recorded_close_vs_rest(symbol: str, result: ClosureResult) -> None:
    candidate, canonical, started = recorded(symbol)
    assert (
        verify_closure(candidate, canonical, fetch_started_at=started, as_of=canonical.observed_at)
        is result
    )
    assert canonical.finality is CandleFinality.UNCONFIRMED  # Verification does not mutate input.


def test_closed_hint_required_and_cannot_be_inferred_from_clock() -> None:
    candidate, _, _ = recorded("BTCUSDT")
    with pytest.raises(ValueError, match="native closure"):
        ClosureCandidate(replace(candidate.observation, closed_hint=False))
    with pytest.raises(ValueError, match="interval"):
        ClosureCandidate(
            replace(candidate.observation, received_at=candidate.observation.candle.open_at)
        )


@pytest.mark.parametrize(
    "case", ["pre_end", "future", "response_before_request", "future_response", "open"]
)
def test_temporal_and_open_guards(case: str) -> None:
    candidate, c, started = recorded("BTCUSDT")
    as_of = c.observed_at
    if case == "pre_end":
        started = c.end_at - timedelta(microseconds=1)
    elif case == "future":
        as_of = c.end_at - timedelta(microseconds=1)
    elif case == "response_before_request":
        started = c.observed_at + timedelta(microseconds=1)
    elif case == "future_response":
        as_of = c.observed_at - timedelta(microseconds=1)
    else:
        c = replace(c, finality=CandleFinality.OPEN)
    assert (
        verify_closure(candidate, c, fetch_started_at=started, as_of=as_of)
        is ClosureResult.NOT_SETTLED
    )


def test_exact_end_request_and_asof_boundaries() -> None:
    candidate, c, _ = recorded("BTCUSDT")
    c = replace(c, observed_at=c.end_at)
    assert (
        verify_closure(candidate, c, fetch_started_at=c.end_at, as_of=c.end_at)
        is ClosureResult.MATCHED
    )


@pytest.mark.parametrize("field", ["open", "high", "low", "close", "volume", "time", "base"])
def test_every_changed_value_or_identity_cannot_match(field: str) -> None:
    candidate, c, started = recorded("BTCUSDT")
    expected = ClosureResult.CONFLICT
    if field == "open":
        c = replace(c, open=c.high if c.open != c.high else c.low)
    elif field == "high":
        c = replace(c, high=c.high + Money.of(1, "USDT"))
    elif field == "low":
        c = replace(c, low=c.low - Money.of(1, "USDT"))
    elif field == "close":
        c = replace(c, close=c.close + Money.of(1, "USDT"))
    elif field == "volume":
        c = replace(c, volume=c.volume + Quantity.of("0.00000001", "BTC"))
    elif field == "time":
        c = replace(
            c, open_at=advance(c.open_at, c.timeframe, 1), end_at=advance(c.end_at, c.timeframe, 1)
        )
        expected = ClosureResult.WRONG_SERIES
    else:
        c = replace(c, base="ETH", volume=Quantity.of(c.volume.as_parts()["quantity"], "ETH"))
        expected = ClosureResult.WRONG_SERIES
    assert verify_closure(candidate, c, fetch_started_at=started, as_of=c.observed_at) is expected


@pytest.mark.parametrize("timeframe", list(Timeframe))
def test_native_calendar_and_same_ohlcv_closure_metadata(timeframe: Timeframe) -> None:
    _, c, _ = recorded("BTCUSDT")
    opened = align_floor(datetime(2026, 11, 21, tzinfo=UTC), timeframe)
    ended = advance(opened, timeframe, 1)
    c = replace(c, timeframe=timeframe, open_at=opened, end_at=ended, observed_at=ended)
    native = CandleObservation(c, ended, ended, 1, 1, 1, True)
    candidate = ClosureCandidate(native)
    repeated = ClosureCandidate(
        replace(
            native, event_at=ended + timedelta(seconds=1), received_at=ended + timedelta(seconds=1)
        )
    )
    assert candidate.fingerprint == repeated.fingerprint
    assert (
        verify_closure(candidate, c, fetch_started_at=ended, as_of=ended) is ClosureResult.MATCHED
    )


@given(zeros=st.integers(min_value=0, max_value=16))
def test_decimal_representation_does_not_change_match(zeros: int) -> None:
    candidate, c, started = recorded("BTCUSDT")
    text = c.close.as_parts()["amount"]
    c = replace(c, close=Money.of(text + "0" * zeros, "USDT"))
    assert (
        verify_closure(candidate, c, fetch_started_at=started, as_of=c.observed_at)
        is ClosureResult.MATCHED
    )
