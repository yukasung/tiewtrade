"""Checkpoint replay across warm-up and controls, checked against an exact oracle."""

import json
from dataclasses import replace
from datetime import UTC, datetime
from decimal import ROUND_UP, Inexact, Rounded, localcontext

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tests.infra.indicators.parity_reference import (
    SPAN,
    canonical_digest,
    parity_slots,
    reference_points,
    scan,
)
from tiewtrade.core.indicators import IndicatorStream
from tiewtrade.core.market_data import CandleFinality, CandleWindow, Timeframe
from tiewtrade.infra.indicators.codec import decode_checkpoint, encode_checkpoint

START = datetime(2026, 10, 1, tzinfo=UTC)
IDENTITY = {"generation_id": "warm-parity", "source": "primary_spot"}


@pytest.mark.parametrize("warm_count", [1, 14, 26, 199])
@pytest.mark.parametrize("batch_size", [1, 2, 16])
@settings(max_examples=3, deadline=None)
@given(
    offsets=st.lists(st.integers(-5 * 10**18, 5 * 10**18), min_size=440, max_size=440),
    refresh_index=st.integers(1020, 1030),
    gap_index=st.integers(1040, 1060),
    open_index=st.integers(1003, 1015),
)
def test_randomized_warm_checkpoint_matches_oracle_and_full_scan(
    warm_count: int,
    batch_size: int,
    offsets: list[int],
    refresh_index: int,
    gap_index: int,
    open_index: int,
) -> None:
    slots = parity_slots(
        START,
        warm_count,
        offsets,
        refresh_index=refresh_index,
        gap_index=gap_index,
        open_index=open_index,
    )
    calculation = CandleWindow(START, START + len(slots) * SPAN)
    as_of = calculation.end + SPAN
    oracle = reference_points(slots)
    full = IndicatorStream("BTC", "USDT", Timeframe.M1, as_of)
    expected = scan(full, slots, 16, 1000)
    assert expected == oracle
    builder = IndicatorStream("BTC", "USDT", Timeframe.M1, as_of)
    assert scan(builder, slots[:1000], batch_size, 64) == oracle[:1000]
    assert builder.state.accepted_count == warm_count
    assert any(average.pending for average in builder.state.averages)
    payload = encode_checkpoint(
        builder, **IDENTITY, calculation=calculation, next_open_at=START + 1000 * SPAN
    )
    assert len(json.dumps(payload).encode()) <= 16 * 1024
    for fetch_size in (7, 64, 1000):
        restored = decode_checkpoint(
            json.loads(json.dumps(payload)),
            **IDENTITY,
            base="BTC",
            quote="USDT",
            timeframe=Timeframe.M1,
            as_of=as_of,
            calculation=calculation,
            next_open_at=START + 1000 * SPAN,
        )
        assert restored.export_state() == builder.export_state()
        observed = scan(restored, slots[1000:], batch_size, fetch_size)
        assert observed == oracle[1000:] == expected[1000:]
        assert restored.export_state() == full.export_state()


def test_restored_accept_transition_ignores_hostile_decimal_context() -> None:
    slots = parity_slots(START, 199, [((i % 41) - 20) * 10**17 + i for i in range(440)])
    calculation = CandleWindow(START, START + len(slots) * SPAN)
    as_of = calculation.end + SPAN
    full = IndicatorStream("BTC", "USDT", Timeframe.M1, as_of)
    expected = scan(full, slots, 16, 1000)
    assert expected == reference_points(slots)
    stream = IndicatorStream("BTC", "USDT", Timeframe.M1, as_of)
    scan(stream, slots[:1000], 16, 1000)
    payload = encode_checkpoint(
        stream, **IDENTITY, calculation=calculation, next_open_at=START + 1000 * SPAN
    )
    assert stream.state.averages[2].value is None
    with localcontext() as context:
        context.prec = 2
        context.rounding = ROUND_UP
        context.traps[Inexact] = context.traps[Rounded] = True
        restored = decode_checkpoint(
            payload,
            **IDENTITY,
            base="BTC",
            quote="USDT",
            timeframe=Timeframe.M1,
            as_of=as_of,
            calculation=calculation,
            next_open_at=START + 1000 * SPAN,
        )
        first = restored.feed(*slots[1000])
        assert restored.state.accepted_count == 200
        assert restored.state.averages[2].value is not None
        assert first.finality is CandleFinality.UNCONFIRMED
        assert (first, *scan(restored, slots[1001:], 16, 7)) == expected[1000:]
        assert restored.export_state() == full.export_state()


def test_rebuilt_checkpoint_after_unconfirmed_to_closed_update_matches_reference() -> None:
    original_slots = parity_slots(START, 199, [((i % 41) - 20) * 10**17 + i for i in range(440)])
    updated_slots = tuple(
        (moment, replace(bar, finality=CandleFinality.CLOSED), None)
        if bar is not None and bar.finality is CandleFinality.UNCONFIRMED
        else (moment, bar, fetched)
        for moment, bar, fetched in original_slots
    )
    calculation = CandleWindow(START, START + len(original_slots) * SPAN)
    as_of = calculation.end + SPAN
    assert canonical_digest(updated_slots, calculation) != canonical_digest(
        original_slots, calculation
    )
    old = IndicatorStream("BTC", "USDT", Timeframe.M1, as_of)
    scan(old, original_slots[:1000], 16, 64)
    assert old.export_state().unconfirmed
    updated = IndicatorStream("BTC", "USDT", Timeframe.M1, as_of)
    scan(updated, updated_slots[:1000], 16, 64)
    assert not updated.export_state().unconfirmed
    payload = encode_checkpoint(
        updated, **IDENTITY, calculation=calculation, next_open_at=START + 1000 * SPAN
    )
    restored = decode_checkpoint(
        payload,
        **IDENTITY,
        base="BTC",
        quote="USDT",
        timeframe=Timeframe.M1,
        as_of=as_of,
        calculation=calculation,
        next_open_at=START + 1000 * SPAN,
    )
    full = IndicatorStream("BTC", "USDT", Timeframe.M1, as_of)
    expected = scan(full, updated_slots, 16, 1000)
    assert expected == reference_points(updated_slots)
    assert scan(restored, updated_slots[1000:], 2, 7) == expected[1000:]
    assert restored.export_state() == full.export_state()
