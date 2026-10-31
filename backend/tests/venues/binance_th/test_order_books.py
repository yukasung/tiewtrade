"""Strict public execution shapes and capability fail-closed behavior."""

from copy import deepcopy
from datetime import timedelta
from typing import cast

import pytest

from tests.order_book_fixtures import (
    NOW,
    SYMBOL,
    capability,
    depth_payload,
    pair_payload,
    snapshot,
    trade_payload,
)
from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.positions import ExecutionSide
from tiewtrade.venues.binance_th.order_book_mapping import (
    capability_from_pair,
    observation_from_stream,
    snapshot_from_payload,
    trade_samples_from_payload,
)
from tiewtrade.venues.errors import VenueProtocolError
from tiewtrade.venues.order_books import DepthUpdate, TradeObservation


def test_bounded_snapshot_is_exact_and_validated() -> None:
    result = snapshot()
    assert result.last_update_id == 10
    assert result.asks[0].quantity == Quantity.of(10, "BTC")
    assert result.bids[0].price == Money.of(99, "USDT")
    for row in (
        {"lastUpdateId": True, "bids": [], "asks": []},
        {"lastUpdateId": 1, "bids": [["100", "1"]], "asks": [["99", "1"]]},
        {"lastUpdateId": 1, "bids": [["99", "0"]], "asks": [["100", "1"]]},
        {"lastUpdateId": 1, "bids": [["99", "1"], ["99", "2"]], "asks": [["100", "1"]]},
    ):
        with pytest.raises(VenueProtocolError):
            snapshot_from_payload(SYMBOL, row, NOW)


def test_depth_and_trade_parser_preserves_ids_sides_and_source_time() -> None:
    depth = observation_from_stream(depth_payload(9, 12), (SYMBOL,), NOW)
    assert isinstance(depth, DepthUpdate) and (depth.first_update_id, depth.last_update_id) == (
        9,
        12,
    )
    trade = observation_from_stream(trade_payload(), (SYMBOL,), NOW)
    assert isinstance(trade, TradeObservation)
    assert trade.resting_side is ExecutionSide.BUY and trade.quantity == Quantity.of("2.5", "BTC")
    row = trade_payload()
    cast(dict[str, object], row["data"])["m"] = False
    trade = observation_from_stream(row, (SYMBOL,), NOW + timedelta(milliseconds=1))
    assert isinstance(trade, TradeObservation) and trade.resting_side is ExecutionSide.SELL


def test_aggregate_trade_history_is_contiguous_and_exact() -> None:
    result = trade_samples_from_payload(
        SYMBOL,
        [
            {"a": 7, "p": "100", "q": "1.5", "f": 10, "l": 11, "T": 1792291200000, "m": True},
            {"a": 8, "p": "101", "q": "2", "f": 12, "l": 12, "T": 1792291200001, "m": False},
        ],
    )
    assert result[0].price == Money.of(100, "USDT")
    assert result[0].quantity == Quantity.of("1.5", "BTC")
    assert (result[-1].aggregate_id, result[-1].last_trade_id) == (8, 12)
    broken = [
        {"a": 7, "p": "100", "q": "1", "f": 10, "l": 10, "T": 1792291200000, "m": True},
        {"a": 9, "p": "100", "q": "1", "f": 12, "l": 12, "T": 1792291200001, "m": True},
    ]
    with pytest.raises(VenueProtocolError):
        trade_samples_from_payload(SYMBOL, broken)


@pytest.mark.parametrize(
    "field,value", [("m", 1), ("t", True), ("p", "0"), ("q", "-1"), ("s", "ETHUSDT"), ("new", 1)]
)
def test_unknown_or_malformed_trade_is_not_a_fill(field: str, value: object) -> None:
    row = trade_payload()
    cast(dict[str, object], row["data"])[field] = value
    with pytest.raises(VenueProtocolError):
        observation_from_stream(row, (SYMBOL,), NOW)


def test_real_execution_filters_are_strictly_mapped_for_each_order_type() -> None:
    result = capability(venue_rules=True)
    assert result.limit.unsupported_rules == ()
    assert result.market.unsupported_rules == ()
    assert result.limit.average_price_minutes == 5
    assert result.market.average_price_minutes == 5
    assert result.limit.percent_price_multiplier_down is not None
    assert result.limit.percent_price_multiplier_down.as_text() == "0.2"
    assert result.limit.percent_price_multiplier_up is not None
    assert result.limit.percent_price_multiplier_up.as_text() == "5"
    assert result.market.percent_price_multiplier_down is None
    assert result.limit.maximum_open_orders == 201
    assert result.market.maximum_open_orders == 201
    assert '"PERCENT_PRICE"' in result.source_document
    assert result.limit.maximum_quantity == Quantity.of(9000, "BTC")
    assert result.version == capability(venue_rules=True).version
    assert result.version != capability().version


def test_duplicate_filters_unknown_fields_and_disabled_filters_fail_closed() -> None:
    original = pair_payload()
    for mutate in ("duplicate", "required_field", "disabled"):
        row = deepcopy(original)
        filters = cast(list[dict[str, object]], row["filters"])
        if mutate == "duplicate":
            filters.append(filters[0].copy())
        elif mutate == "required_field":
            filters[0]["newRequiredRule"] = "x"
        else:
            filters[0]["tickSize"] = "0"
        with pytest.raises(VenueProtocolError):
            capability_from_pair(SYMBOL, row, NOW)
