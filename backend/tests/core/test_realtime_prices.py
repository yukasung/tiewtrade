from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tiewtrade.core.money import Money
from tiewtrade.core.realtime_prices import (
    ObservationKind,
    QuoteObservation,
    QuoteState,
    Readiness,
    observe,
    readiness,
    reconcile,
)

NOW = datetime(2026, 10, 7, tzinfo=UTC)


def quote(seconds: int = 0, price: str = "1", trade_id: int = 1) -> QuoteObservation:
    return QuoteObservation(
        "primary_spot",
        "BTC",
        "USDT",
        Money.of(price, "USDT"),
        trade_id,
        NOW + timedelta(seconds=seconds),
        NOW,
        ObservationKind.STREAM,
    )


def test_readiness_age_boundaries_and_connection_fencing() -> None:
    def status(now: datetime, *, connected: bool = True, producer_alive: bool = True) -> Readiness:
        return readiness(
            quote=quote(),
            connected=connected,
            reconciled=True,
            producer_alive=producer_alive,
            now=now,
        )

    assert status(NOW + timedelta(seconds=10)) is Readiness.READY
    assert status(NOW + timedelta(seconds=10, microseconds=1)) is Readiness.STALE
    assert status(NOW, connected=False) is Readiness.RECOVERING
    assert status(NOW, producer_alive=False) is Readiness.RECOVERING
    assert status(NOW - timedelta(seconds=1)) is Readiness.RECOVERING


def test_same_time_conflict_is_durable_until_post_latch_recovery() -> None:
    first = observe(QuoteState(), quote(price="1", trade_id=3))
    conflict = observe(first, quote(price="2", trade_id=4))
    assert conflict.confirmed == first.confirmed
    assert conflict.order_ambiguous_at == NOW
    newer = observe(conflict, quote(1, "3", 2))
    assert newer.order_ambiguous_at == NOW
    assert newer.confirmed == first.confirmed
    assert (
        reconcile(
            newer, quote(1, "3", 99), started_at=NOW, now=NOW + timedelta(seconds=1)
        ).state.order_ambiguous_at
        == NOW
    )
    recovered = reconcile(
        newer,
        quote(1, "3", 99),
        started_at=NOW + timedelta(microseconds=1),
        now=NOW + timedelta(seconds=1),
    )
    assert recovered.succeeded
    assert recovered.state.order_ambiguous_at is None
    assert recovered.state.confirmed is not None and recovered.state.confirmed.amount == Money.of(
        "3", "USDT"
    )


def test_recovery_equal_time_conflict_expands_latch() -> None:
    state = observe(observe(QuoteState(), quote()), quote(price="2", trade_id=2))
    state = observe(state, quote(1, "3", 3))
    result = reconcile(
        state,
        quote(1, "4", 4),
        started_at=NOW + timedelta(microseconds=1),
        now=NOW + timedelta(seconds=1),
    )
    assert not result.succeeded
    assert result.state.order_ambiguous_at == NOW + timedelta(seconds=1)


def test_repeated_stream_id_content_conflict_is_protocol_failure() -> None:
    state = observe(QuoteState(), quote())
    result = observe(state, quote(1, "2"))
    assert result.protocol_error
    assert result.confirmed == state.confirmed


@given(st.permutations([1, 2, 3]))
def test_distinct_timestamp_order_ignores_numeric_ids(order: list[int]) -> None:
    state = QuoteState()
    for t in order:
        state = observe(state, quote(t, str(t), 4 - t))
    assert state.confirmed is not None
    assert state.confirmed.trade_time == NOW + timedelta(seconds=3)


@pytest.mark.parametrize("trade_id", [-1, True, 2**63, 10**100])
def test_observation_rejects_invalid_ids(trade_id: int) -> None:
    with pytest.raises(ValueError):
        quote(trade_id=trade_id)


@pytest.mark.parametrize("trade_id", [0, 2**63 - 1])
def test_observation_accepts_persistable_id_boundaries(trade_id: int) -> None:
    assert quote(trade_id=trade_id).trade_id == trade_id


@pytest.mark.parametrize("ids", [(1, 2), (2, 1)])
def test_equal_time_price_conflict_is_ambiguous_in_both_arrival_orders(
    ids: tuple[int, int],
) -> None:
    state = observe(
        observe(QuoteState(), quote(price="1", trade_id=ids[0])), quote(price="2", trade_id=ids[1])
    )
    assert state.order_ambiguous_at == NOW
    assert state.confirmed is not None and state.confirmed.amount == Money.of("1", "USDT")


def test_same_price_equal_time_different_id_does_not_refresh_observation() -> None:
    first = quote(trade_id=1)
    newer_receipt = QuoteObservation(
        first.source,
        first.base,
        first.quote,
        first.amount,
        9,
        first.trade_time,
        NOW + timedelta(seconds=100),
        ObservationKind.STREAM,
    )
    state = observe(observe(QuoteState(), first), newer_receipt)
    assert state.confirmed == first
    assert state.candidate == first
    assert state.order_ambiguous_at is None


def test_snapshot_id_is_not_compared_as_stream_duplicate_identity() -> None:
    first = quote()
    snapshot = QuoteObservation(
        first.source,
        first.base,
        first.quote,
        first.amount,
        first.trade_id,
        first.trade_time,
        first.received_at,
        ObservationKind.SNAPSHOT,
    )
    state = observe(observe(QuoteState(), snapshot), quote(1, "2"))
    assert not state.protocol_error
    assert state.confirmed == quote(1, "2")


@pytest.mark.parametrize("offset", [-11, 60])
def test_rejected_recovery_explicitly_reports_failure(offset: int) -> None:
    state = QuoteState() if offset < 0 else observe(QuoteState(), quote())
    result = reconcile(state, quote(offset), started_at=NOW, now=NOW)
    assert not result.succeeded
    assert result.state == state


def test_recovery_can_succeed_without_changing_quote_values() -> None:
    state = observe(QuoteState(), quote())
    result = reconcile(state, quote(), started_at=NOW, now=NOW)
    assert result.succeeded
    assert result.state == state
