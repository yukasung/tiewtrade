"""Public sequence bootstrap, bounded coverage and ambiguity tests."""

from dataclasses import replace
from datetime import timedelta

import pytest

from tests.order_book_fixtures import NOW, SYMBOL, depth_payload, snapshot, trade_payload
from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.order_book import BookLevel, BookState, MarketTrade
from tiewtrade.core.orders import SourceUnavailableError
from tiewtrade.core.positions import ExecutionSide
from tiewtrade.services.market_data.order_book import ExecutionBookAssembler
from tiewtrade.venues.binance_th.order_book_mapping import observation_from_stream
from tiewtrade.venues.order_books import DepthUpdate, TradeObservation


def depth(first: int = 11, last: int = 11, milliseconds: int = 1) -> DepthUpdate:
    at = NOW + timedelta(milliseconds=milliseconds)
    value = observation_from_stream(depth_payload(first, last, at), (SYMBOL,), at)
    assert isinstance(value, DepthUpdate)
    return value


def trade(identity: int = 100, milliseconds: int = 2) -> TradeObservation:
    at = NOW + timedelta(milliseconds=milliseconds)
    value = observation_from_stream(trade_payload(identity, at), (SYMBOL,), at)
    assert isinstance(value, TradeObservation)
    return value


def test_snapshot_needs_a_proven_bridge_and_contiguous_updates() -> None:
    assembler = ExecutionBookAssembler(snapshot(), 1)
    assert assembler.observe(trade(), 1) is None
    assert assembler.observe(depth(1, 10), 1) is None
    first = assembler.observe(depth(9, 12), 1)
    assert isinstance(first, BookState) and first.ready and first.rebase
    assert assembler.observe(depth(9, 12), 2) is None
    second = assembler.observe(depth(13, 13, 2), 2)
    assert isinstance(second, BookState) and not second.rebase
    with pytest.raises(SourceUnavailableError):
        assembler.observe(depth(15, 16, 3), 3)
    assert not assembler.ready
    with pytest.raises(SourceUnavailableError):
        assembler.observe(depth(14, 14, 4), 3)


def test_bootstrap_does_not_publish_an_unbridged_snapshot() -> None:
    assembler = ExecutionBookAssembler(snapshot(), 1)
    assert not assembler.ready and assembler.book is None
    with pytest.raises(SourceUnavailableError):
        assembler.observe(depth(12, 13), 1)


def test_absolute_zero_removal_preserves_proven_boundary_not_outside_depth() -> None:
    assembler = ExecutionBookAssembler(snapshot(), 1)
    update = replace(
        depth(),
        asks=(
            BookLevel(Money.of(100, "USDT"), Quantity.of(0, "BTC")),
            BookLevel(Money.of(1000, "USDT"), Quantity.of(1000, "BTC")),
        ),
        bids=(BookLevel(Money.of(1, "USDT"), Quantity.of(0, "BTC")),),
    )
    result = assembler.observe(update, 1)
    assert isinstance(result, BookState)
    assert result.reported(ExecutionSide.BUY, Money.of(1, "USDT")) == Quantity.of(0, "BTC")
    assert [v.price for v in result.asks] == [Money.of(200, "USDT")]


def test_trade_sequence_freshness_and_ambiguous_ordering_fail_closed() -> None:
    assembler = ExecutionBookAssembler(snapshot(), 1)
    assembler.observe(depth(), 1)
    result = assembler.observe(trade(), 2)
    assert isinstance(result, MarketTrade) and result.ordering_proven
    assert assembler.observe(trade(), 3) is None
    assert isinstance(assembler.observe(trade(101, 3), 3), MarketTrade)
    with pytest.raises(SourceUnavailableError):
        assembler.observe(trade(103, 4), 4)
    fresh = ExecutionBookAssembler(snapshot(), 1)
    fresh.observe(depth(), 1)
    with pytest.raises(SourceUnavailableError):
        fresh.observe(trade(milliseconds=1), 2)
    stale = ExecutionBookAssembler(snapshot(), 1)
    stale.observe(depth(), 1)
    with pytest.raises(SourceUnavailableError):
        stale.observe(trade(milliseconds=1002), 2)


def test_source_receipt_and_verification_clocks_and_sequence_provenance() -> None:
    assembler = ExecutionBookAssembler(snapshot(), 1)
    update = replace(depth(), received_at=NOW + timedelta(milliseconds=5))
    result = assembler.observe(update, 1)
    assert isinstance(result, BookState)
    assert result.source_at == NOW + timedelta(milliseconds=1)
    assert result.received_at == result.verified_at == NOW + timedelta(milliseconds=5)
    assert (
        result.snapshot_sequence,
        result.source_first_sequence,
        result.source_last_sequence,
    ) == (10, 11, 11)
    with pytest.raises(SourceUnavailableError):
        result.require_ready(NOW + timedelta(milliseconds=1002))
