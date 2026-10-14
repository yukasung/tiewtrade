from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any
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
from tests.infra.market_data.test_chart_preview import observation
from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.infra.db.session import market_data_session
from tiewtrade.infra.market_data.candle_preview import acquire, connection, flush
from tiewtrade.infra.realtime.admission import AdmissionOutcome


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
    "fault,expected",
    [
        ("gap", "CHANGED"),
        ("finality", "CHANGED"),
        ("fetch_start", "CHANGED"),
        ("floor", "UNVERIFIABLE"),
        ("rollout_epoch", "CHANGED"),
        ("maintenance", "UNVERIFIABLE"),
        ("expiry", "UNVERIFIABLE"),
    ],
)
async def test_display_proof_rejects_source_and_generation_faults(
    fault: str,
    expected: str,
    ready: dict[str, Any],
    client: TestClient,
    migrator_engine: AsyncEngine,
) -> None:
    register(client)
    response = client.get(
        "/market-data/chart/history", params={"base": "BTC", "quote": "USDT", "timeframe": "4h"}
    )
    assert response.status_code == 200, response.text
    async with migrator_engine.begin() as c:
        if fault in ("gap", "finality", "fetch_start"):
            await c.execute(text("SELECT begin_indicator_source_write()"))
            statement = {
                "gap": """DELETE FROM market_candles
                    WHERE base='BTC' AND timeframe='4h' AND open_at=:seed""",
                "finality": """UPDATE market_candles SET finality='UNCONFIRMED'
                    WHERE base='BTC' AND timeframe='4h' AND open_at=:seed""",
                "fetch_start": """UPDATE market_candles
                    SET fetch_started_at=end_at-interval '1 second'
                    WHERE base='BTC' AND timeframe='4h' AND open_at=:seed""",
            }[fault]
            await c.execute(text(statement), {"seed": ready["calculation_start"]})
        else:
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
    checked = client.post(
        "/market-data/chart/verify",
        json={"display_proof": response.json()["display_proof"]},
        headers=csrf_headers(client),
    )
    assert checked.status_code == 200, checked.text
    assert checked.json()["status"] == expected
