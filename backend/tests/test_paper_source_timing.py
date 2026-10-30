"""Bounded source diagnostics retain outcomes and leave the runtime unpatched."""

import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path
from time import monotonic

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.conftest import _engine
from tests.infra.risk_limits.profile_source_timing import (
    SourceTimeline,
    source_cycle,
    statement_label,
)
from tiewtrade.infra.db import DatabaseRole
from tiewtrade.infra.db import session as db
from tiewtrade.infra.db.session import market_data_session


@pytest.fixture
async def market_engine() -> AsyncIterator[AsyncEngine]:
    async for engine in _engine(DatabaseRole.MARKET_DATA):
        yield engine


async def test_source_timeline_real_commit_and_receipt(
    tmp_path: Path,
    market_engine: AsyncEngine,
) -> None:
    original = db._begin
    trace = SourceTimeline(tmp_path, market_engine)
    trace.activate(monotonic())
    try:
        async with source_cycle(trace, "BOOK", monotonic()):
            async with market_data_session(market_engine) as session:
                await session.execute("SELECT 1")
            trace.receipt("BOOK", "BTC/USDT", "42", "2026-10-29T00:00:00+00:00")
    finally:
        trace.close()
    assert db._begin is original
    row = next(
        json.loads(line)
        for line in (tmp_path / "source-timeline.jsonl").read_text().splitlines()
        if json.loads(line)["event"] == "CYCLE"
    )
    tx = row["transactions"][0]
    assert (
        tx["requested"]
        <= tx["checkout"]
        <= tx["entered"]
        <= tx["body_finished"]
        <= tx["commit_sent"]
        <= tx["committed_ack"]
    )
    assert isinstance(tx["backend_pid"], int) and tx["backend_pid"] > 0
    assert tx["sql_count"] == 2  # existing role check + SELECT; instrumentation adds no SQL
    assert [query["label"] for query in tx["queries"]] == ["ROLE_CHECK", "OTHER"]
    assert sum(query["finished"] - query["started"] for query in tx["queries"]) == pytest.approx(
        tx["sql_seconds"]
    )
    assert row["receipts"][0]["identity"] == "42"
    assert "parameters" not in json.dumps(row)


async def test_source_timeline_limit_fails_loudly(
    tmp_path: Path, market_engine: AsyncEngine
) -> None:
    trace = SourceTimeline(tmp_path, market_engine)
    trace.activate(monotonic())
    trace.limit = 1
    try:
        async with source_cycle(trace, "BOOK", monotonic()):
            pass
        with pytest.raises(RuntimeError, match="TIMELINE_LIMIT"):
            async with source_cycle(trace, "PRICE", monotonic()):
                pass
    finally:
        trace.close()
    assert '"reason": "DETAIL_LIMIT"' in (tmp_path / "source-timeline.jsonl").read_text()


async def test_source_error_and_cancellation_are_preserved(
    tmp_path: Path, market_engine: AsyncEngine
) -> None:
    trace = SourceTimeline(tmp_path, market_engine)
    trace.activate(monotonic())
    try:
        for error in (RuntimeError("safe"), asyncio.CancelledError()):
            with pytest.raises(type(error)):
                async with source_cycle(trace, "PRICE", monotonic()):
                    raise error
    finally:
        trace.close()
    rows = [
        json.loads(line) for line in (tmp_path / "source-timeline.jsonl").read_text().splitlines()
    ]
    assert [row["outcome"] for row in rows if row["event"] == "CYCLE"] == [
        "RuntimeError",
        "CancelledError",
    ]


async def test_setup_baseline_has_aggregates_without_detail_budget(
    tmp_path: Path, market_engine: AsyncEngine
) -> None:
    trace = SourceTimeline(tmp_path, market_engine)
    try:
        async with (
            source_cycle(trace, "PRICE", monotonic()),
            market_data_session(market_engine) as session,
        ):
            await session.execute("SELECT 1")
    finally:
        trace.close()
    rows = [
        json.loads(line) for line in (tmp_path / "source-timeline.jsonl").read_text().splitlines()
    ]
    assert not any(row["event"] == "CYCLE" for row in rows)
    assert any(row["event"] == "SECOND" and row["phase"] == "setup" for row in rows)


@pytest.mark.parametrize(
    "statement,label",
    [
        ("SELECT risk_publication_fence()", "PUBLICATION_FENCE"),
        (
            "WITH locked AS (SELECT * FROM market_price_feed FOR UPDATE) SELECT * FROM locked",
            "FEED_LOCK_AND_CLOCK",
        ),
        ("UPDATE market_latest_prices SET amount=$1", "PRICE_WRITE"),
        ("SELECT * FROM active_supported_symbols", "CATALOG_READ"),
        ("SELECT clock_timestamp()", "DB_CLOCK"),
        ("SELECT id,payload FROM market_risk_price_frames", "PRICE_RECEIPTS"),
        ("SELECT 'private-secret-do-not-record'", "OTHER"),
    ],
)
def test_query_labels_are_fixed_and_never_echo_sql(statement: str, label: str) -> None:
    assert statement_label(statement) == label


async def test_concurrent_sources_keep_query_identity_separate(
    tmp_path: Path, market_engine: AsyncEngine
) -> None:
    trace = SourceTimeline(tmp_path, market_engine)
    trace.activate(monotonic())

    async def call(source: str, sql: str) -> None:
        async with (
            source_cycle(trace, source, monotonic()),
            market_data_session(market_engine) as session,
        ):
            await session.execute(sql)

    try:
        await asyncio.gather(call("BOOK", "SELECT clock_timestamp()"), call("PRICE", "SELECT 1"))
    finally:
        trace.close()
    rows = [
        json.loads(line) for line in (tmp_path / "source-timeline.jsonl").read_text().splitlines()
    ]
    queries = {
        row["source"]: [q["label"] for q in row["transactions"][0]["queries"]]
        for row in rows
        if row["event"] == "CYCLE"
    }
    assert queries == {"BOOK": ["ROLE_CHECK", "DB_CLOCK"], "PRICE": ["ROLE_CHECK", "OTHER"]}


async def test_failed_sql_is_retained_without_being_reported_committed(
    tmp_path: Path, market_engine: AsyncEngine
) -> None:
    from tiewtrade.infra.db.errors import InfraError

    trace = SourceTimeline(tmp_path, market_engine)
    trace.activate(monotonic())
    try:
        with pytest.raises(InfraError):
            async with (
                source_cycle(trace, "PRICE", monotonic()),
                market_data_session(market_engine) as session,
            ):
                await session.execute("SELECT 1/0")
    finally:
        trace.close()
    rows = [
        json.loads(line) for line in (tmp_path / "source-timeline.jsonl").read_text().splitlines()
    ]
    tx = next(row for row in rows if row["event"] == "CYCLE")["transactions"][0]
    assert tx["outcome"] != "COMMIT" and "committed_ack" not in tx
    assert "abort_observed" in tx["queries"][-1]


async def test_sql_detail_bound_stops_without_silent_truncation(
    tmp_path: Path,
    market_engine: AsyncEngine,
) -> None:
    trace = SourceTimeline(tmp_path, market_engine)
    trace.activate(monotonic())
    try:
        with pytest.raises(RuntimeError, match="SOURCE_SQL_LIMIT"):
            async with (
                source_cycle(trace, "PRICE", monotonic()),
                market_data_session(market_engine) as session,
            ):
                for _ in range(64):
                    await session.execute("SELECT 1")
    finally:
        trace.close()
    rows = [
        json.loads(line) for line in (tmp_path / "source-timeline.jsonl").read_text().splitlines()
    ]
    assert any(row.get("reason") == "SQL_LIMIT" for row in rows)
    tx = next(row for row in rows if row["event"] == "CYCLE")["transactions"][0]
    assert len(tx["queries"]) == 64 and tx["outcome"] != "COMMIT"


async def test_backend_observer_correlates_pid_and_stops(
    tmp_path: Path, market_engine: AsyncEngine
) -> None:
    trace = SourceTimeline(tmp_path, market_engine, observe_backend=True)
    trace.duration = 1
    trace.activate(monotonic())
    try:
        async with (
            source_cycle(trace, "PRICE", monotonic()),
            market_data_session(market_engine) as session,
        ):
            await session.execute("SELECT pg_sleep(0.6)")
        await asyncio.sleep(0.5)
    finally:
        trace.close()
    records = [
        json.loads(line) for line in (tmp_path / "source-timeline.jsonl").read_text().splitlines()
    ]
    tx = next(row for row in records if row["event"] == "CYCLE")["transactions"][0]
    observed = json.loads((tmp_path / "source-waits.json").read_text())
    assert observed["outcome"] == "COMPLETE"
    assert 0 < len(observed["samples"]) <= 3000
    assert any(
        backend["pid"] == tx["backend_pid"] and backend["wait_event"] == "PgSleep"
        for sample in observed["samples"]
        for backend in sample["backends"]
    )
    beats = next(row for row in records if row["event"] == "HEARTBEATS")["samples"]
    assert 0 < len(beats) <= 6000
    assert all(beat["resumed"] >= beat["due"] for beat in beats)
    assert trace.observer is not None and trace.observer.poll() == 0
    assert trace.heartbeat is not None and trace.heartbeat.cancelled()
    assert all(
        "query" not in backend and "parameters" not in backend
        for sample in observed["samples"]
        for backend in sample["backends"]
    )
