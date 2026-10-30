"""Public sequence bootstrap, bounded coverage and ambiguity tests."""

import asyncio
from dataclasses import replace
from datetime import timedelta
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.order_book_fixtures import NOW, SYMBOL, depth_payload, snapshot, trade_payload
from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.order_book import BookLevel, BookState, MarketTrade
from tiewtrade.core.orders import SourceUnavailableError
from tiewtrade.core.positions import ExecutionSide, PositionPair
from tiewtrade.infra.market_data.order_book_storage import BUFFER_SIZE
from tiewtrade.services.market_data import order_book
from tiewtrade.services.market_data.order_book import (
    ExecutionBookAssembler,
    ExecutionBookSupervisor,
    TradeWindow,
)
from tiewtrade.venues.binance_th.order_book_mapping import observation_from_stream
from tiewtrade.venues.order_books import (
    DepthUpdate,
    ExecutionFeed,
    TradeObservation,
    TradeSample,
)


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
    stale_duplicate = replace(
        depth(13, 13, 3), bids=(BookLevel(Money.of(1, "USDT"), Quantity.of(1, "BTC")),)
    )
    assert assembler.observe(stale_duplicate, 3) is None
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


def test_trade_receive_order_dedupe_and_freshness() -> None:
    assembler = ExecutionBookAssembler(snapshot(), 1)
    assembler.observe(depth(), 1)
    result = assembler.observe(trade(), 2)
    assert isinstance(result, MarketTrade) and result.ordering_proven
    assert assembler.observe(trade(), 3) is None
    assert isinstance(assembler.observe(trade(101, 3), 3), MarketTrade)
    skipped = trade(103, 4)
    assert isinstance(assembler.observe(skipped, 4), MarketTrade)
    replay = replace(
        skipped,
        event_at=skipped.event_at + timedelta(milliseconds=1),
        received_at=skipped.received_at + timedelta(milliseconds=1),
    )
    assert assembler.observe(replay, 5) is None
    with pytest.raises(SourceUnavailableError):
        assembler.observe(replace(replay, price=Money.of(101, "USDT")), 5)
    reversed_ids = ExecutionBookAssembler(snapshot(), 1)
    reversed_ids.observe(depth(), 1)
    reversed_ids.observe(trade(103, 3), 2)
    assert isinstance(reversed_ids.observe(trade(102, 4), 3), MarketTrade)
    fresh = ExecutionBookAssembler(snapshot(), 1)
    fresh.observe(depth(), 1)
    assert isinstance(fresh.observe(trade(milliseconds=1), 2), MarketTrade)
    stale = ExecutionBookAssembler(snapshot(), 1)
    stale.observe(depth(), 1)
    with pytest.raises(SourceUnavailableError):
        stale.observe(trade(milliseconds=30002), 2)


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
    assert result.source_at is not None
    result.require_ready(result.source_at + timedelta(seconds=30))
    with pytest.raises(SourceUnavailableError):
        result.require_ready(result.source_at + timedelta(seconds=30, microseconds=1))


def test_depth_source_freshness_uses_the_approved_thirty_second_boundary() -> None:
    boundary = depth()
    boundary = replace(boundary, received_at=boundary.event_at + timedelta(seconds=30))
    assert isinstance(ExecutionBookAssembler(snapshot(), 1).observe(boundary, 1), BookState)

    expired = depth()
    expired = replace(
        expired,
        received_at=expired.event_at + timedelta(seconds=30, microseconds=1),
    )
    with pytest.raises(SourceUnavailableError, match="depth source freshness unproven"):
        ExecutionBookAssembler(snapshot(), 1).observe(expired, 1)


def test_public_source_clock_skew_uses_the_approved_hundred_millisecond_boundary() -> None:
    boundary_depth = depth(milliseconds=1000)
    boundary_depth = replace(
        boundary_depth,
        received_at=boundary_depth.event_at - timedelta(milliseconds=100),
    )
    depth_assembler = ExecutionBookAssembler(snapshot(), 1)
    assert isinstance(depth_assembler.observe(boundary_depth, 1), BookState)

    future_depth = depth(milliseconds=1000)
    future_depth = replace(
        future_depth,
        received_at=future_depth.event_at - timedelta(milliseconds=100, microseconds=1),
    )
    with pytest.raises(SourceUnavailableError, match="depth source freshness unproven"):
        ExecutionBookAssembler(snapshot(), 1).observe(future_depth, 1)

    trade_assembler = ExecutionBookAssembler(snapshot(), 1)
    trade_assembler.observe(depth(), 1)
    boundary_trade = trade(milliseconds=1000)
    boundary_trade = replace(
        boundary_trade,
        received_at=boundary_trade.event_at - timedelta(milliseconds=100),
    )
    assert isinstance(trade_assembler.observe(boundary_trade, 2), MarketTrade)

    future_trade_assembler = ExecutionBookAssembler(snapshot(), 1)
    future_trade_assembler.observe(depth(), 1)
    future_trade = trade(milliseconds=1000)
    future_trade = replace(
        future_trade,
        received_at=future_trade.event_at - timedelta(milliseconds=100, microseconds=1),
    )
    with pytest.raises(SourceUnavailableError, match="trade ordering unproven"):
        future_trade_assembler.observe(future_trade, 2)


def test_trade_dedupe_window_is_bounded() -> None:
    assembler = ExecutionBookAssembler(snapshot(), 1)
    assembler.observe(depth(), 1)
    for offset in range(BUFFER_SIZE + 1):
        assert isinstance(assembler.observe(trade(100 + offset), 2 + offset), MarketTrade)
    assert len(assembler._trades) == BUFFER_SIZE
    assert 100 not in assembler._trades


def test_trade_window_uses_quantity_weight_and_excludes_seed_overlap() -> None:
    started = NOW - timedelta(minutes=5)
    history = (
        TradeSample(SYMBOL, 1, 10, 10, Money.of(100, "USDT"), Quantity.of(1, "BTC"), started),
        TradeSample(SYMBOL, 2, 11, 11, Money.of(200, "USDT"), Quantity.of(3, "BTC"), NOW),
    )
    window = TradeWindow(SYMBOL, 5, started, NOW, history)
    price, window_start, observed = window.evidence(NOW)
    assert price == Money.of(175, "USDT")
    assert (window_start, observed) == (started, NOW)
    window.observe(replace(trade(11), occurred_at=NOW, received_at=NOW))
    assert window.evidence(NOW)[0] == Money.of(175, "USDT")


async def test_supervisor_starts_and_stops_managed_pair(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    desired = {PositionPair(SYMBOL.base, SYMBOL.quote)}
    started = asyncio.Event()
    stopped = asyncio.Event()

    async def pairs(self: ExecutionBookSupervisor) -> frozenset[PositionPair]:
        del self
        return frozenset(desired)

    async def ingest(**kwargs: object) -> None:
        assert kwargs["symbol"] == SYMBOL
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    monkeypatch.setattr(ExecutionBookSupervisor, "_desired_pairs", pairs)
    monkeypatch.setattr(order_book, "ingest_execution_pair", ingest)
    supervisor = ExecutionBookSupervisor(
        cast(AsyncEngine, object()), cast(ExecutionFeed, object()), refresh_interval=0.001
    )
    task = asyncio.create_task(supervisor.run())
    try:
        await asyncio.wait_for(started.wait(), timeout=1)
        desired.clear()
        await asyncio.wait_for(stopped.wait(), timeout=1)
        assert not supervisor.tasks
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
