"""Per-row immutable reuse must preserve every evidence integrity check."""

import hashlib
import json
from copy import deepcopy
from dataclasses import replace
from typing import Any
from unittest.mock import patch
from uuid import uuid4

import pytest

from tests.infra.execution_market.test_evidence import source_record
from tiewtrade.core.order_book import BookState, MarketTrade
from tiewtrade.core.orders import OrderConflictError, SimulationProfile
from tiewtrade.core.positions import ExecutionSide
from tiewtrade.infra.market_data.order_book_codec import (
    canonical,
    input_from_payload,
    input_payload,
)
from tiewtrade.infra.market_data.order_book_storage import StoredExecutionInput, metadata_payload
from tiewtrade.infra.paper_orders import storage
from tiewtrade.infra.paper_orders.records import SavedExecutionInput


def record_for(kind: str) -> StoredExecutionInput:
    record = source_record()
    if kind == "BOOK":
        return record
    book = record.market
    assert isinstance(book, BookState)
    trade = MarketTrade(
        book.pair,
        1,
        1,
        book.received_at,
        1,
        ExecutionSide.BUY,
        book.bids[0].price,
        book.bids[0].quantity,
        True,
    )
    trade_record = replace(record, market=trade)
    return replace(trade_record, digest=storage._source_digest(trade_record))


def evidence_row(
    record: StoredExecutionInput,
    *,
    decision: BookState | None = None,
    explicit_source: bool = False,
) -> dict[str, Any]:
    market = record.market if decision is None else decision
    profile = SimulationProfile()
    payload = {
        "market": json.loads(input_payload(market)),
        "metadata": json.loads(metadata_payload(record.metadata)),
        "fee_version": profile.fee_version,
        "model_version": profile.liquidity_version,
    }
    if explicit_source or decision is not None:
        payload["source_market"] = json.loads(input_payload(record.market))
    return {
        "id": uuid4(),
        "recorded_at": market.received_at,
        "episode_id": uuid4(),
        "payload": payload,
        "digest": hashlib.sha256(canonical(payload).encode()).hexdigest(),
        "source_digest": record.digest,
        "input_id": market.input_id,
        "generation": market.generation,
        "base": market.pair.base,
        "quote": market.pair.quote,
    }


@pytest.mark.parametrize("kind", ["BOOK", "TRADE"])
@pytest.mark.parametrize("explicit_source", [False, True])
@pytest.mark.parametrize("string_payload", [False, True])
def test_exact_record_and_decode_count(
    kind: str, explicit_source: bool, string_payload: bool
) -> None:
    record = record_for(kind)
    row = evidence_row(record, explicit_source=explicit_source)
    if string_payload:
        row["payload"] = canonical(row["payload"])
    with patch.object(storage, "input_from_payload", wraps=input_from_payload) as decode:
        saved = storage._decode(row)
    assert saved == SavedExecutionInput(
        row["id"], row["recorded_at"], row["episode_id"], record, row["digest"]
    )
    assert decode.call_count == (2 if explicit_source else 1)


@pytest.mark.parametrize("string_payload", [False, True])
def test_actual_consumer_rebase_still_decodes_and_checks_source(string_payload: bool) -> None:
    original = record_for("BOOK")
    assert isinstance(original.market, BookState)
    source = replace(original.market, rebase=False)
    record = replace(original, market=source)
    record = replace(record, digest=storage._source_digest(record))
    decision = replace(source, rebase=True)
    row = evidence_row(record, decision=decision)
    if string_payload:
        row["payload"] = canonical(row["payload"])
    with patch.object(storage, "input_from_payload", wraps=input_from_payload) as decode:
        saved = storage._decode(row)
    assert saved.record == replace(record, market=decision)
    assert decode.call_count == 2


@pytest.mark.parametrize("string_payload", [False, True])
@pytest.mark.parametrize(
    "fault",
    [
        "outer_digest",
        "source_digest",
        "row_input",
        "row_pair",
        "profile",
        "metadata",
        "source_null",
        "source_bool",
        "market_bool",
        "changed_decision",
    ],
)
def test_integrity_checks_still_reject_redigested_invalid_payload(
    fault: str, string_payload: bool
) -> None:
    row = evidence_row(record_for("BOOK"))
    payload = row["payload"]
    if fault == "source_digest":
        row["source_digest"] = "0" * 64
    elif fault == "row_input":
        row["input_id"] += 1
    elif fault == "row_pair":
        row["base"] = "ETH"
    elif fault == "profile":
        payload["fee_version"] = "unsupported"
    elif fault == "metadata":
        payload["metadata"] = None
    elif fault == "source_null":
        payload["source_market"] = None
    elif fault == "source_bool":
        payload["source_market"] = deepcopy(payload["market"])
        payload["source_market"]["ready"] = 1  # Equal to True in Python, invalid in the domain.
    elif fault == "market_bool":
        payload["market"]["ready"] = 1
    elif fault == "changed_decision":
        payload["source_market"] = deepcopy(payload["market"])
        payload["market"]["ready"] = False
    row["digest"] = (
        "0" * 64
        if fault == "outer_digest"
        else hashlib.sha256(canonical(payload).encode()).hexdigest()
    )
    if string_payload:
        row["payload"] = canonical(payload)
    with pytest.raises(OrderConflictError):
        storage._decode(row)
