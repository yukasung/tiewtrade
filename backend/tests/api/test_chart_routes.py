from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any, cast
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.api.conftest import csrf_headers, register
from tests.api.test_prepared_indicators import admission_state as admission_state
from tests.api.test_prepared_indicators import ready as ready
from tests.infra.indicators.test_claims import builder_engine as builder_engine
from tests.infra.indicators.test_claims import prepared as prepared
from tests.infra.indicators.test_source import active as active
from tests.infra.indicators.test_source import md as md
from tests.infra.market_data.test_chart_preview import observation
from tiewtrade.core.market_data import Timeframe, align_floor, next_open
from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.infra.db.errors import DatabaseTimeoutError
from tiewtrade.infra.db.session import market_data_session
from tiewtrade.infra.indicators.maintenance import collect
from tiewtrade.infra.market_data import claims as candle_claims
from tiewtrade.infra.market_data.candle_preview import acquire, connection, flush
from tiewtrade.infra.realtime.admission import AdmissionOutcome
from tiewtrade.services.api.indicator_read_controller import IndicatorHistoryView


@pytest.fixture(autouse=True)
def chart_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TIEWTRADE_CHART_ENABLED", "1")


async def test_bundle_matches_indicator_page_and_proof_invalidates_seed(
    ready: dict[str, Any],
    client: TestClient,
    migrator_engine: AsyncEngine,
) -> None:
    register(client)
    args = {"base": "BTC", "quote": "USDT", "timeframe": "4h", "page_size": 2}
    response = client.get("/market-data/chart/history", params=args)
    assert response.status_code == 200, response.text
    bundle = response.json()
    reference = client.get("/market-data/indicators", params={"cursor": bundle["next_cursor"]})
    assert reference.status_code == 200, reference.text
    assert reference.json()["dataset_revision"] == bundle["dataset_revision"]
    assert len(bundle["candles"]) == 2
    assert [row["open_at"] for row in bundle["candles"]] == [
        row["open_at"] for row in bundle["rows"]
    ]
    proof = {"display_proof": bundle["display_proof"]}
    checked = client.post("/market-data/chart/verify", json=proof, headers=csrf_headers(client))
    assert checked.status_code == 200, checked.text
    assert checked.json()["status"] == "MATCHED"
    # Dependency before the output viewport must invalidate the same display proof.
    async with migrator_engine.begin() as c:
        await c.execute(text("SELECT begin_indicator_source_write()"))
        await c.execute(
            text("""UPDATE market_candles SET close=open
            WHERE base='BTC' AND timeframe='4h' AND open_at=:seed"""),
            {"seed": ready["calculation_start"]},
        )
    changed = client.post("/market-data/chart/verify", json=proof, headers=csrf_headers(client))
    assert changed.status_code == 200, changed.text
    assert changed.json()["status"] == "CHANGED"


def test_chart_auth_csrf_and_sanitized_input(client: TestClient) -> None:
    assert client.get("/market-data/chart/history").status_code == 401
    register(client)
    assert (
        client.post("/market-data/chart/verify", json={"display_proof": "bad"}).status_code == 403
    )
    response = client.post(
        "/market-data/chart/verify",
        json={"display_proof": "sentinel-secret"},
        headers=csrf_headers(client),
    )
    assert response.status_code == 422
    assert response.json() == {"detail": "INPUT_REJECTED"}
    rejected_origin = client.post(
        "/market-data/chart/verify",
        json={"display_proof": "sentinel-secret"},
        headers=csrf_headers(client) | {"Origin": "https://untrusted.invalid"},
    )
    assert rejected_origin.status_code == 403
    assert rejected_origin.json() == {"detail": "CSRF_ORIGIN_REJECTED"}


def test_live_database_timeout_is_typed(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tiewtrade.services.api import chart_routes

    async def timed_out(*args: object) -> None:
        raise DatabaseTimeoutError("controlled timeout")

    monkeypatch.setattr(chart_routes, "_live", timed_out)
    register(client)
    response = client.get(
        "/market-data/chart/live", params={"base": "BTC", "quote": "USDT", "timeframe": "1h"}
    )
    assert response.status_code == 504
    assert response.json() == {"detail": "CHART_DEADLINE_EXCEEDED"}


@pytest.mark.parametrize("timeframe", ["1w", "1M"])
def test_calendar_timeframes_are_accepted_by_authenticated_chart_and_indicator_routes(
    timeframe: str,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tiewtrade.services.api import chart_routes, indicator_routes

    observed: list[tuple[str, Timeframe | None]] = []

    class Serialized:
        def model_dump_json(self) -> str:
            return "{}"

    async def chart_read(
        query: object, _request: object, _who: object, _deadline: float
    ) -> chart_routes.ChartHistoryView:
        observed.append(("chart", cast(Any, query).timeframe))
        return cast(chart_routes.ChartHistoryView, Serialized())

    async def indicator_read(
        query: object, _request: object, _who: object, _deadline: float
    ) -> IndicatorHistoryView:
        observed.append(("indicator", cast(Any, query).timeframe))
        return cast(IndicatorHistoryView, Serialized())

    monkeypatch.setattr(chart_routes, "_history", chart_read)
    monkeypatch.setattr(indicator_routes, "_read", indicator_read)
    register(client)
    params = {"base": "BTC", "quote": "USDT", "timeframe": timeframe}
    chart = client.get("/market-data/chart/history", params=params)
    indicator = client.get("/market-data/indicators", params=params)
    assert chart.status_code == indicator.status_code == 200
    expected = Timeframe(timeframe)
    assert observed == [("chart", expected), ("indicator", expected)]


@pytest.mark.parametrize("timeframe", ["1W", "1mo", "1m "])
@pytest.mark.parametrize("path", ["/market-data/chart/history", "/market-data/indicators"])
def test_chart_and_indicator_routes_reject_noncanonical_calendar_timeframes(
    path: str, timeframe: str, client: TestClient
) -> None:
    register(client)
    response = client.get(path, params={"base": "BTC", "quote": "USDT", "timeframe": timeframe})
    assert response.status_code == 422
    assert response.json() == {"detail": "INPUT_REJECTED"}


async def test_live_snapshot_is_role_read_only_and_admission_fails_closed(
    client: TestClient,
    migrator_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tiewtrade.services.api import chart_routes
    from tiewtrade.services.api.app import app

    register(client)
    async with migrator_engine.begin() as c:
        await c.execute(text("DELETE FROM market_candle_preview"))
        await c.execute(text("UPDATE market_candle_feed_state SET lease_until=clock_timestamp()"))
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    row = observation()
    try:
        async with market_data_session(engine) as s:
            lease = await acquire(s, uuid4())
            assert lease is not None
            lease = await connection(s, lease, True)
            await flush(s, lease, ((row, 1),))
        response = client.get(
            "/market-data/chart/live", params={"base": "BTC", "quote": "USDT", "timeframe": "1h"}
        )
        assert response.status_code == 200, response.text
        assert len(response.json()["rows"]) == 1
        assert response.json()["rows"][0]["open"] == "100.000000000000000001"
        assert response.headers["cache-control"] == "private, no-store"

        class Unavailable:
            async def outcome(self, subject: str) -> AdmissionOutcome:
                return AdmissionOutcome.UNAVAILABLE

        async def forbidden(*args: object) -> None:
            raise AssertionError("admission outage must never invoke the preview reader")

        monkeypatch.setattr(app.state, "chart_admission", Unavailable())
        monkeypatch.setattr(chart_routes, "_live", forbidden)
        unavailable = client.get(
            "/market-data/chart/live", params={"base": "BTC", "quote": "USDT", "timeframe": "1h"}
        )
        assert unavailable.status_code == 503
        assert unavailable.json() == {"detail": "CHART_ADMISSION_UNAVAILABLE"}
    finally:
        await engine.dispose()


@pytest.mark.parametrize(
    "age,expected",
    [
        (timedelta(seconds=6), "RECOVERING"),
        (timedelta(seconds=6, microseconds=1), "STALE"),
        (-timedelta(seconds=2), "RECOVERING"),
        (-timedelta(seconds=2, microseconds=1), "UNAVAILABLE"),
    ],
)
async def test_live_age_is_decided_by_server_snapshot_at_exact_boundaries(
    age: timedelta,
    expected: str,
    client: TestClient,
    migrator_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tiewtrade.infra.market_data import candle_preview

    register(client)
    row = observation()
    snapshot = row.received_at
    row = replace(row, event_at=snapshot - age, received_at=snapshot - age)

    async def frozen(session: object) -> object:
        return snapshot

    monkeypatch.setattr(candle_preview, "database_now", frozen)
    async with migrator_engine.begin() as c:
        await c.execute(text("DELETE FROM market_candle_preview"))
        await c.execute(text("UPDATE market_candle_feed_state SET lease_until=clock_timestamp()"))
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        async with market_data_session(engine) as s:
            lease = await acquire(s, uuid4())
            assert lease is not None
            lease = await connection(s, lease, True)
            await flush(s, lease, ((row, 1),))
        response = client.get(
            "/market-data/chart/live", params={"base": "BTC", "quote": "USDT", "timeframe": "1h"}
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == expected
        assert response.json()["server_time"] == snapshot.isoformat().replace("+00:00", "Z")
    finally:
        await engine.dispose()


@pytest.mark.parametrize("mode", ["LEGACY", "PREPARED"])
async def test_bundle_ohlc_and_indicators_use_one_snapshot_during_writer_commit(
    mode: str,
    ready: dict[str, Any],
    client: TestClient,
    migrator_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tiewtrade.infra.market_data.storage import stored_rows
    from tiewtrade.services.api import indicator_read_controller

    if mode == "LEGACY":
        async with migrator_engine.begin() as c:
            await c.execute(text("UPDATE indicator_rollout_control SET mode='LEGACY'"))
    register(client)
    args = {"base": "BTC", "quote": "USDT", "timeframe": "4h", "page_size": 2}
    baseline = client.get("/market-data/chart/history", params=args)
    reference = client.get("/market-data/indicators", params=args)
    assert baseline.status_code == reference.status_code == 200
    assert baseline.json()["rows"] == reference.json()["rows"]
    original = stored_rows
    committed = False

    async def writer_barrier(*arguments: Any, **keywords: Any) -> Any:
        nonlocal committed
        assert not committed
        committed = True
        writer = create_engine_for(DatabaseRole.MIGRATOR)
        try:
            async with writer.begin() as c:
                await c.execute(text("SELECT begin_indicator_source_write()"))
                await c.execute(
                    text("""UPDATE market_candles SET close=open
                    WHERE base='BTC' AND timeframe='4h' AND open_at=:output"""),
                    {"output": datetime.fromisoformat(baseline.json()["candles"][0]["open_at"])},
                )
        finally:
            await writer.dispose()
        return await original(*arguments, **keywords)

    monkeypatch.setattr(indicator_read_controller, "stored_rows", writer_barrier)
    response = client.get("/market-data/chart/history", params=args)
    assert response.status_code == 200, response.text
    assert committed
    assert response.json()["candles"] == baseline.json()["candles"]
    assert response.json()["rows"] == reference.json()["rows"]
    checked = client.post(
        "/market-data/chart/verify",
        json={"display_proof": response.json()["display_proof"]},
        headers=csrf_headers(client),
    )
    assert checked.status_code == 200 and checked.json()["status"] == "CHANGED"


@pytest.mark.parametrize(
    "mode,fault,expected",
    [
        (mode, fault, "CHANGED")
        for mode in ("LEGACY", "PREPARED")
        for fault in ("gap", "finality", "fetch_start", "ohlc", "volume", "retention")
    ]
    + [
        ("PREPARED", "floor", "UNVERIFIABLE"),
        ("PREPARED", "rollout_epoch", "CHANGED"),
        ("PREPARED", "maintenance", "UNVERIFIABLE"),
        ("PREPARED", "expiry", "UNVERIFIABLE"),
        ("PREPARED", "generation_cleanup", "UNVERIFIABLE"),
        ("PREPARED", "ddl", "UNVERIFIABLE"),
        # An unrelated future partition leaves the LEGACY content hash unchanged.
        ("LEGACY", "ddl", "MATCHED"),
        ("LEGACY", "detach_seed_partition", "CHANGED"),
        ("PREPARED", "detach_seed_partition", "UNVERIFIABLE"),
    ],
)
async def test_display_proof_tracks_source_and_generation_faults(
    mode: str,
    fault: str,
    expected: str,
    ready: dict[str, Any],
    client: TestClient,
    migrator_engine: AsyncEngine,
    md: AsyncEngine,
    builder_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with migrator_engine.begin() as c:
        await c.execute(text("UPDATE indicator_rollout_control SET mode=:mode"), {"mode": mode})
    register(client)
    response = client.get(
        "/market-data/chart/history", params={"base": "BTC", "quote": "USDT", "timeframe": "4h"}
    )
    assert response.status_code == 200, response.text
    partition_start = align_floor(ready["calculation_start"], Timeframe.MN1)
    partition_end = next_open(partition_start, Timeframe.MN1)
    partition_name = f"market_candles_{partition_start:%Y%m}"
    async with migrator_engine.begin() as c:
        if fault in ("gap", "finality", "fetch_start", "ohlc", "volume"):
            await c.execute(text("SELECT begin_indicator_source_write()"))
            statement = {
                "gap": """DELETE FROM market_candles
                    WHERE base='BTC' AND timeframe='4h' AND open_at=:seed""",
                "finality": """UPDATE market_candles SET finality='UNCONFIRMED'
                    WHERE base='BTC' AND timeframe='4h' AND open_at=:seed""",
                "fetch_start": """UPDATE market_candles
                    SET fetch_started_at=end_at-interval '1 second'
                    WHERE base='BTC' AND timeframe='4h' AND open_at=:seed""",
                "ohlc": """UPDATE market_candles SET close=open
                    WHERE base='BTC' AND timeframe='4h' AND open_at=:seed""",
                "volume": """UPDATE market_candles SET volume=volume+1
                    WHERE base='BTC' AND timeframe='4h' AND open_at=:seed""",
            }[fault]
            await c.execute(text(statement), {"seed": ready["calculation_start"]})
        elif fault == "generation_cleanup":
            # Preserve expiry/window constraints while aging the collected generation.
            await c.execute(
                text("""UPDATE indicator_generations
                SET as_of=as_of-interval '7 hours', expires_at=expires_at-interval '7 hours',
                calculation_end=calculation_end-interval '7 hours',
                calculation_start=calculation_start-interval '7 hours'""")
            )
        elif fault == "ddl":
            await c.execute(text("SELECT begin_indicator_source_maintenance()"))
            await c.execute(
                text("""CREATE TABLE test_chart_proof_2035
                PARTITION OF market_candles
                FOR VALUES FROM ('2035-01-01') TO ('2035-02-01')""")
            )
        elif fault == "detach_seed_partition":
            await c.execute(text("SELECT begin_indicator_source_maintenance()"))
            await c.execute(text(f"ALTER TABLE market_candles DETACH PARTITION {partition_name}"))
        elif fault != "retention":
            await c.execute(
                text(
                    {
                        "floor": """UPDATE indicator_source_guard
                            SET revision=revision+1,journal_floor=revision+1""",
                        "rollout_epoch": """UPDATE indicator_rollout_control
                            SET rollout_epoch=gen_random_uuid()""",
                        "maintenance": "SELECT begin_indicator_source_maintenance()",
                        "expiry": "UPDATE indicator_generations SET status='EXPIRED'",
                    }[fault]
                )
            )
    try:
        if fault == "retention":

            async def cleanup_clock(session: object) -> datetime:
                return cast(datetime, ready["calculation_start"]) + timedelta(
                    days=365, hours=6, minutes=15, seconds=1
                )

            # Advance only the retention worker clock, not display-proof expiry.
            monkeypatch.setattr(candle_claims, "database_now", cleanup_clock)
            async with market_data_session(md) as session:
                assert await candle_claims.cleanup(session) > 0
            async with migrator_engine.connect() as c:
                assert (
                    await c.execute(
                        text("""SELECT count(*) FROM market_candles
                    WHERE base='BTC' AND timeframe='4h' AND open_at=:seed"""),
                        {"seed": ready["calculation_start"]},
                    )
                ).scalar_one() == 0
        elif fault == "generation_cleanup":
            assert (await collect(builder_engine))["generations"] == 1
            async with migrator_engine.connect() as c:
                assert (
                    await c.execute(text("SELECT count(*) FROM indicator_generations"))
                ).scalar_one() == 0
        checked = client.post(
            "/market-data/chart/verify",
            json={"display_proof": response.json()["display_proof"]},
            headers=csrf_headers(client),
        )
        assert checked.status_code == 200, checked.text
        assert checked.json()["status"] == expected
    finally:
        if fault == "ddl":
            async with migrator_engine.begin() as c:
                await c.execute(text("SELECT begin_indicator_source_maintenance()"))
                await c.execute(text("DROP TABLE test_chart_proof_2035"))
        elif fault == "detach_seed_partition":
            async with migrator_engine.begin() as c:
                await c.execute(text("SELECT begin_indicator_source_maintenance()"))
                await c.execute(
                    text(f"""ALTER TABLE market_candles
                    ATTACH PARTITION {partition_name}
                    FOR VALUES FROM ('{partition_start:%Y-%m-%d}')
                    TO ('{partition_end:%Y-%m-%d}')""")
                )
