"""Authenticated prepared reads through actual API roles, worker and Redis admission."""

import asyncio
import os
from datetime import datetime, timedelta
from time import monotonic
from typing import Any, cast
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.api.conftest import register
from tests.infra.indicators.test_claims import builder_engine as builder_engine
from tests.infra.indicators.test_claims import prepared as prepared
from tests.infra.indicators.test_source import active as active
from tests.services.indicator_builder.test_attempt import metadata, seed
from tests.services.indicator_builder.test_scheduler import change_source, numeric
from tiewtrade.core.market_data import CandleWindow, Timeframe
from tiewtrade.core.money import Money, Scalar
from tiewtrade.infra.auth.sessions import hash_token, owner_of_presented
from tiewtrade.infra.crypto.indicator_cursor import PreparedCursorClaims, verify
from tiewtrade.infra.db.session import indicator_read_session
from tiewtrade.infra.market_data.indicator_reader import read_indicators
from tiewtrade.services.api.app import app
from tiewtrade.services.api.indicator_routes import IndicatorPointView, IndicatorValueView
from tiewtrade.services.api.settings import SESSION_COOKIE
from tiewtrade.services.indicator_builder.attempt import AttemptStatus, run_attempt


@pytest_asyncio.fixture(autouse=True)
async def admission_state() -> Any:
    redis = Redis.from_url(os.environ["TIEWTRADE_TEST_REDIS_URL"])
    await redis.flushdb()
    try:
        yield
    finally:
        await redis.aclose()


@pytest_asyncio.fixture
async def ready(
    prepared: None, builder_engine: AsyncEngine, migrator_engine: AsyncEngine
) -> dict[str, Any]:
    await seed(builder_engine, migrator_engine)
    async with migrator_engine.begin() as c:
        await c.execute(text("SELECT begin_indicator_source_write()"))
        await c.execute(
            text("""INSERT INTO market_candles
          (source,base,quote,timeframe,open_at,end_at,open,high,low,close,volume,finality,
           observed_at,fetch_started_at,last_checked_at,ingestion_generation)
          SELECT 'primary_spot','BTC','USDT','4h',moment,moment+interval '4 hours',
            100+n%17,103+n%17,98+n%17,101+n%17,1,
            CASE WHEN moment+interval '4 hours'<=clock_timestamp()-interval '24 hours'
              THEN 'CLOSED' ELSE 'UNCONFIRMED' END,
            clock_timestamp(),clock_timestamp(),clock_timestamp(),1
          FROM indicator_build_jobs j CROSS JOIN LATERAL generate_series(
            j.desired_start,j.desired_end-interval '4 hours',interval '4 hours')
              WITH ORDINALITY t(moment,n)
          WHERE j.base='BTC' AND j.timeframe='4h'""")
        )
    assert (await run_attempt(builder_engine, uuid4())).status is AttemptStatus.READY
    async with migrator_engine.begin() as c:
        await c.execute(text("UPDATE indicator_rollout_control SET mode='PREPARED'"))
        generation = (
            (
                await c.execute(
                    text("SELECT * FROM indicator_generations WHERE job_id=:id"),
                    {"id": (await metadata(migrator_engine))["id"]},
                )
            )
            .mappings()
            .one()
        )
    return dict(generation)


def first(client: TestClient, **extra: Any) -> Any:
    return client.get(
        "/market-data/indicators",
        params={"base": "BTC", "quote": "USDT", "timeframe": "4h", "page_size": 2} | extra,
    )


async def test_checkpoint_page_matches_full_scan_and_signed_v2(
    ready: dict[str, Any],
    client: TestClient,
    api_engine: AsyncEngine,
) -> None:
    register(client)
    response = first(client)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["generation_id"] == str(ready["id"]) and body["prepared_at"]
    token = body["next_cursor"]
    # Obtain the actual authenticated user via the session-bound verification.
    from tiewtrade.infra.db.session import presented_session

    hashed = hash_token(str(client.cookies.get(SESSION_COOKIE)))
    async with presented_session(api_engine, token_hash=hashed) as s:
        owner = await owner_of_presented(s)
        assert owner is not None
    claims = verify(token, app.state.indicator_keys, owner.user_id, hashed)
    assert isinstance(claims, PreparedCursorClaims)
    async with indicator_read_session(api_engine, owner.user_id) as s:
        reference = await read_indicators(
            s,
            "BTC",
            "USDT",
            Timeframe.H4,
            CandleWindow(ready["calculation_start"], ready["calculation_end"]),
            CandleWindow(datetime.fromisoformat(body["rows"][0]["open_at"]), claims.next_open_at),
            ready["as_of"],
            monotonic() + 30,
        )
    assert reference.revision == body["dataset_revision"]
    expected = [
        IndicatorPointView(
            open_at=p.open_at,
            seed_open_at=p.seed_open_at,
            finality=p.finality.value if p.finality else None,
            values={
                name: IndicatorValueView(
                    value=value.value.as_text()
                    if isinstance(value.value, Scalar)
                    else value.value.as_parts()["amount"]
                    if value.value is not None
                    else None,
                    unit=value.value.currency if isinstance(value.value, Money) else None,
                    status=value.status.value,
                )
                for name, value in p.values.items()
            },
        ).model_dump(mode="json")
        for p in reference.points
    ]
    assert body["rows"] == expected
    following = client.get("/market-data/indicators", params={"cursor": token})
    assert following.status_code == 200, following.text
    assert following.json()["generation_id"] == body["generation_id"]
    assert following.json()["rows"][0]["open_at"] > body["rows"][-1]["open_at"]


@pytest.mark.parametrize(
    "fault", ["age", "expire", "floor", "epoch", "codec", "checkpoint", "payload", "mode"]
)
async def test_first_page_fails_closed(
    ready: dict[str, Any],
    client: TestClient,
    migrator_engine: AsyncEngine,
    fault: str,
) -> None:
    register(client)
    async with migrator_engine.begin() as c:
        statements = {
            "age": """UPDATE indicator_generations SET as_of=as_of-interval '601 seconds',
                expires_at=expires_at-interval '601 seconds',
                calculation_start=calculation_start-interval '601 seconds',
                calculation_end=calculation_end-interval '601 seconds'""",
            "expire": """UPDATE indicator_generations SET as_of=as_of-interval '7 hours',
                expires_at=expires_at-interval '7 hours',
                calculation_end=calculation_end-interval '7 hours',
                calculation_start=calculation_start-interval '7 hours'""",
            "floor": """UPDATE indicator_source_guard SET
                revision=revision+1,journal_floor=revision+1""",
            "epoch": "UPDATE indicator_source_guard SET epoch=gen_random_uuid()",
            "codec": "UPDATE indicator_generations SET codec_version=2",
            "checkpoint": "DELETE FROM indicator_checkpoints",
            "payload": "UPDATE indicator_checkpoints SET payload='{}'",
            "mode": "UPDATE indicator_rollout_control SET mode='PAUSED'",
        }
        await c.execute(text(statements[fault]))
    response = first(client)
    assert response.status_code == 503, response.text
    assert response.headers["retry-after"] == "10"


@pytest.mark.parametrize("fault", ["source", "gc", "floor", "epoch", "mode"])
async def test_continuation_invalidates_without_fallback(
    ready: dict[str, Any],
    client: TestClient,
    migrator_engine: AsyncEngine,
    fault: str,
) -> None:
    register(client)
    response = first(client)
    assert response.status_code == 200, response.text
    token = response.json()["next_cursor"]
    if fault == "source":
        await change_source(migrator_engine)
    else:
        async with migrator_engine.begin() as c:
            await c.execute(
                text(
                    {
                        "gc": "DELETE FROM indicator_checkpoints",
                        "floor": """UPDATE indicator_source_guard SET
                            revision=revision+1,journal_floor=revision+1""",
                        "epoch": """UPDATE indicator_rollout_control SET
                            rollout_epoch=gen_random_uuid()""",
                        "mode": "UPDATE indicator_rollout_control SET mode='PREPARING'",
                    }[fault]
                )
            )
    result = client.get("/market-data/indicators", params={"cursor": token})
    assert result.status_code == 409, result.text


async def test_numeric_manifest_masks_old_head_and_new_bounds_give_503(
    ready: dict[str, Any],
    client: TestClient,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
) -> None:
    register(client)
    async with migrator_engine.begin() as c:
        await c.execute(
            text(
                """UPDATE indicator_build_jobs SET status='QUEUED'
                WHERE base='BTC' AND timeframe='4h'"""
            )
        )
    await numeric(builder_engine)
    response = first(client)
    assert response.status_code == 422 and response.json()["detail"] == "INDICATOR_NUMERIC_ERROR"
    assert "retry-after" not in response.headers
    async with migrator_engine.begin() as c:
        await c.execute(
            text(
                """UPDATE indicator_build_jobs SET desired_end=desired_end+interval '4 hours',
                desired_start=desired_start+interval '4 hours'"""
            )
        )
    assert first(client).status_code == 503


async def test_numeric_manifest_gc_does_not_restore_old_head(
    ready: dict[str, Any],
    client: TestClient,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
) -> None:
    register(client)
    response = first(client)
    assert response.status_code == 200, response.text
    token = response.json()["next_cursor"]
    async with migrator_engine.begin() as c:
        await c.execute(
            text("""UPDATE indicator_build_jobs SET status='QUEUED'
            WHERE base='BTC' AND timeframe='4h'""")
        )
    await numeric(builder_engine)
    # A different failed candidate never changes a valid READY continuation.
    assert client.get("/market-data/indicators", params={"cursor": token}).status_code == 200
    async with migrator_engine.begin() as c:
        await c.execute(
            text("UPDATE indicator_generations SET status='EXPIRED' WHERE status='FAILED_NUMERIC'")
        )
    result = first(client)
    assert result.status_code == 503, result.text


async def test_bounded_source_prefix_and_snapshot_consistency(
    ready: dict[str, Any],
    client: TestClient,
    api_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tiewtrade.infra.market_data import indicator_reader

    original = indicator_reader.fetch_rows
    lengths: list[int] = []
    committed = False

    register(client)
    # Reentrant event-loop barrier: API reads run on TestClient's thread, so
    # use a role-identical engine in that loop for the concurrent writer.
    # Avoid sharing the admin pool across threads.
    from tiewtrade.infra.db import DatabaseRole, create_engine_for

    async def thread_change(*args: Any, **kwargs: Any) -> Any:
        nonlocal committed
        window = args[4]
        lengths.append(int((window.end - window.start) / Timeframe.H4.span))
        if not committed:
            committed = True
            admin = create_engine_for(DatabaseRole.MIGRATOR)
            try:
                await change_source(admin)
            finally:
                await admin.dispose()
        return await original(*args, **kwargs)

    monkeypatch.setattr(indicator_reader, "fetch_rows", thread_change)
    response = first(client, page_size=1000)
    assert response.status_code == 200, response.text
    assert sum(lengths) <= 1999 and max(lengths) <= 1000
    # Writer committed after API snapshot: this response is internally coherent;
    # the next snapshot rejects the same head.
    assert first(client).status_code == 503


@pytest.mark.parametrize("mode", ["LEGACY", "PREPARING", "PAUSED", "PREPARED"])
async def test_verified_v1_is_409_outside_legacy(
    ready: dict[str, Any],
    client: TestClient,
    api_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    mode: str,
) -> None:
    from tiewtrade.infra.crypto.indicator_cursor import CursorClaims, issue

    register(client)
    hashed = hash_token(str(client.cookies.get(SESSION_COOKIE)))
    from tiewtrade.infra.db.session import presented_session

    async with presented_session(api_engine, token_hash=hashed) as s:
        owner = await owner_of_presented(s)
        assert owner is not None
    now = ready["as_of"]
    claims = CursorClaims(
        source="primary_spot",
        base="BTC",
        quote="USDT",
        timeframe=Timeframe.H4,
        dataset_revision=ready["dataset_revision"],
        calculation_start=ready["calculation_start"],
        calculation_end=ready["calculation_end"],
        as_of=now,
        result_start=ready["calculation_end"] - timedelta(hours=8),
        result_end=ready["calculation_end"],
        next_open_at=ready["calculation_end"] - timedelta(hours=8),
        page_size=1,
        issued_at=now,
        expires_at=now + timedelta(hours=6),
    )
    token = issue(claims, app.state.indicator_keys, owner.user_id, hashed)
    async with migrator_engine.begin() as c:
        await c.execute(text("UPDATE indicator_rollout_control SET mode=:mode"), {"mode": mode})
    response = client.get("/market-data/indicators", params={"cursor": token})
    assert response.status_code == (200 if mode == "LEGACY" else 409), response.text


async def test_continuation_ignores_freshness_but_first_page_does_not(
    ready: dict[str, Any],
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tiewtrade.services.api import indicator_routes

    register(client)
    response = first(client)
    assert response.status_code == 200, response.text

    async def later(*args: Any) -> datetime:
        return cast(datetime, ready["as_of"]) + timedelta(seconds=601)

    monkeypatch.setattr(indicator_routes, "database_now", later)
    assert first(client).status_code == 503
    assert (
        client.get(
            "/market-data/indicators", params={"cursor": response.json()["next_cursor"]}
        ).status_code
        == 200
    )


@pytest.mark.parametrize("microseconds,status", [(-1, 200), (0, 200), (1, 503)])
async def test_exact_head_freshness_boundary(
    ready: dict[str, Any],
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    microseconds: int,
    status: int,
) -> None:
    from tiewtrade.services.api import indicator_routes

    register(client)

    async def clock(*args: Any) -> datetime:
        return cast(datetime, ready["as_of"]) + timedelta(seconds=600, microseconds=microseconds)

    monkeypatch.setattr(indicator_routes, "database_now", clock)
    response = first(client)
    assert response.status_code == status, response.text
    if status == 200:
        assert response.headers["cache-control"] == "private, no-store"


@pytest.mark.parametrize("fault", ["database", "redis"])
async def test_indicator_outage_recovers_without_session_renewal(
    ready: dict[str, Any],
    client: TestClient,
    api_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
    fault: str,
) -> None:
    from sqlalchemy.ext.asyncio import create_async_engine

    from tiewtrade.infra.realtime.admission import AdmissionRedis, RedisAdmission

    register(client)
    hashed = hash_token(str(client.cookies.get(SESSION_COOKIE)))

    async def idle_expiry() -> Any:
        from tiewtrade.infra.db.session import presented_session

        async with presented_session(api_engine, token_hash=hashed) as session:
            return (
                await session.execute(
                    "SELECT idle_expires_at FROM sessions WHERE token_hash=:hash",
                    {"hash": hashed},
                )
            ).scalar_one()

    before = await idle_expiry()
    with monkeypatch.context() as patch:
        if fault == "database":
            unavailable = create_async_engine(
                "postgresql+asyncpg://invalid@127.0.0.1:1/unavailable"
            )
            patch.setattr(app.state, "indicator_engine", unavailable)
            try:
                response = first(client)
            finally:
                await unavailable.dispose()
            expected = "INDICATOR_DATA_UNAVAILABLE"
        else:
            redis = Redis.from_url("redis://127.0.0.1:1/0", socket_connect_timeout=0.1)
            patch.setattr(
                app.state, "indicator_admission", RedisAdmission(cast(AdmissionRedis, redis))
            )
            try:
                response = first(client)
            finally:
                assert client.portal is not None
                client.portal.call(redis.aclose)
            expected = "INDICATOR_ADMISSION_UNAVAILABLE"
        assert response.status_code == 503, response.text
        assert response.json() == {"detail": expected}
        assert not app.state.indicator_budget.busy
    recovered = first(client)
    assert recovered.status_code == 200, recovered.text
    assert recovered.headers["cache-control"] == "private, no-store"
    assert await idle_expiry() == before


@pytest.mark.parametrize("expiry", ["token", "generation"])
@pytest.mark.parametrize("stage", ["entry", "response"])
async def test_expiry_is_independent_of_authentication(
    ready: dict[str, Any],
    client: TestClient,
    api_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
    expiry: str,
    stage: str,
) -> None:
    from tiewtrade.infra.crypto.indicator_cursor import issue
    from tiewtrade.infra.db.session import presented_session
    from tiewtrade.services.api import indicator_routes

    register(client)
    response = first(client)
    assert response.status_code == 200, response.text
    hashed = hash_token(str(client.cookies.get(SESSION_COOKIE)))
    async with presented_session(api_engine, token_hash=hashed) as session:
        owner = await owner_of_presented(session)
        assert owner is not None
    claims = verify(response.json()["next_cursor"], app.state.indicator_keys, owner.user_id, hashed)
    assert isinstance(claims, PreparedCursorClaims)
    boundary = ready["as_of"] + timedelta(seconds=60)
    if expiry == "token":
        claims = claims.model_copy(update={"expires_at": boundary})
    else:
        boundary = ready["expires_at"]
        claims = claims.model_copy(
            update={
                "issued_at": ready["as_of"] + timedelta(minutes=20),
                "expires_at": boundary + timedelta(minutes=1),
            }
        )
    async with presented_session(api_engine, token_hash=hashed) as session:
        updated = await session.execute(
            "UPDATE sessions SET idle_expires_at=:expiry "
            "WHERE token_hash=:hash RETURNING token_hash",
            {"expiry": boundary + timedelta(minutes=2), "hash": hashed},
        )
        assert updated.scalar_one() == hashed
    token = issue(claims, app.state.indicator_keys, owner.user_id, hashed)

    calls = 0

    async def clock(*args: Any) -> datetime:
        nonlocal calls
        calls += 1
        return cast(datetime, boundary) - (
            timedelta(microseconds=1) if stage == "response" and calls == 1 else timedelta()
        )

    monkeypatch.setattr(indicator_routes, "database_now", clock)
    result = client.get("/market-data/indicators", params={"cursor": token})
    assert result.status_code == 409, result.text
    assert result.json() == {"detail": "INDICATOR_DATASET_CHANGED"}
    assert not app.state.indicator_budget.busy


async def test_missing_ready_never_builds_or_writes_demand(
    prepared: None,
    client: TestClient,
    migrator_engine: AsyncEngine,
) -> None:
    register(client)
    async with migrator_engine.begin() as c:
        await c.execute(text("UPDATE indicator_rollout_control SET mode='PREPARED'"))
    response = first(client)
    assert response.status_code == 503, response.text
    assert response.headers["retry-after"] == "10"
    async with migrator_engine.connect() as c:
        assert (
            await c.execute(text("SELECT count(*) FROM indicator_generations"))
        ).scalar_one() == 0
        assert (
            await c.execute(text("SELECT count(*) FROM market_candle_demand"))
        ).scalar_one() == 0


async def test_empty_derived_scheduler_refresh_and_rebuild(
    prepared: None,
    client: TestClient,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import UTC

    from tests.api.conftest import csrf_headers
    from tests.services.market_data.test_ingestion import FullSource
    from tiewtrade.infra.db import DatabaseRole, create_engine_for
    from tiewtrade.services.indicator_builder import scheduler
    from tiewtrade.services.market_data.ingestion import run_round

    register(client)
    async with migrator_engine.begin() as c:
        await c.execute(text("UPDATE indicator_rollout_control SET mode='PREPARED'"))
        for table in ("indicator_generations", "indicator_checkpoints", "indicator_heads"):
            assert (await c.execute(text(f"SELECT count(*) FROM {table}"))).scalar_one() == 0
    assert first(client).status_code == 503
    await seed(builder_engine, migrator_engine)
    async with migrator_engine.begin() as c:
        await c.execute(text("SELECT begin_indicator_source_write()"))
        await c.execute(
            text("""INSERT INTO market_candles
          (source,base,quote,timeframe,open_at,end_at,open,high,low,close,volume,finality,
           observed_at,fetch_started_at,last_checked_at,ingestion_generation)
          SELECT 'primary_spot','BTC','USDT','4h',moment,moment+interval '4 hours',
            2,2,2,2,1,'UNCONFIRMED',clock_timestamp(),moment,clock_timestamp(),1
          FROM indicator_build_jobs j CROSS JOIN LATERAL generate_series(
            j.desired_start,j.desired_start+interval '116 hours',interval '4 hours') t(moment)
          WHERE j.base='BTC' AND j.timeframe='4h'""")
        )
    stop = asyncio.Event()
    original = run_attempt
    published = []

    async def observed_attempt(*args: Any, **kwargs: Any) -> Any:
        result = await original(*args, **kwargs)
        assert result.status is AttemptStatus.READY
        published.append(result)
        stop.set()
        return result

    monkeypatch.setattr(scheduler, "run_attempt", observed_attempt)
    await asyncio.wait_for(scheduler.run_scheduler(builder_engine, uuid4(), stop), 30)
    window = await metadata(migrator_engine)
    bounds = {
        "start": window["desired_start"].isoformat(),
        "end": (window["desired_start"] + timedelta(hours=120)).isoformat(),
    }
    before = first(client, page_size=25, **bounds)
    assert before.status_code == 200, before.text
    assert before.json()["refresh"]["required"]
    assert before.json()["refresh"]["queue_status"] is None
    target = before.json()["refresh"]["target"]
    async with migrator_engine.connect() as connection:
        assert (
            await connection.execute(text("SELECT count(*) FROM market_candle_demand"))
        ).scalar_one() == 0
    assert client.post("/market-data/candles/requests", json=target).status_code == 403
    # Two real HTTP requests, separate request transactions, one shared demand.
    refreshed = await asyncio.gather(
        *(
            asyncio.to_thread(
                client.post,
                "/market-data/candles/requests",
                json=target,
                headers=csrf_headers(client),
            )
            for _ in range(2)
        )
    )
    assert all(response.status_code == 202 for response in refreshed)
    async with migrator_engine.connect() as connection:
        assert (
            await connection.execute(text("SELECT count(*) FROM market_candle_demand"))
        ).scalar_one() == 1
    pending = first(client, page_size=25, **bounds)
    assert pending.status_code == 200 and pending.json()["refresh"]["required"]
    md = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        from tiewtrade.infra.db.session import market_data_session
        from tiewtrade.infra.indicators.source import begin_source_write
        from tiewtrade.services.market_data.ingestion import _seed_initial_demand

        class RollbackError(Exception):
            pass

        with pytest.raises(RollbackError):
            async with market_data_session(md) as session:
                await begin_source_write(session)
                await session.execute("UPDATE market_candles SET fetch_started_at=end_at")
                uncommitted = first(client, page_size=25, **bounds)
                assert uncommitted.status_code == 200
                assert uncommitted.json()["refresh"]["required"]
                assert uncommitted.json()["dataset_revision"] == before.json()["dataset_revision"]
                raise RollbackError()
        async with market_data_session(md) as session:
            assert (
                await session.execute(
                    "SELECT bool_and(fetch_started_at<end_at) FROM market_candles"
                )
            ).scalar_one()
        async with market_data_session(md) as session:
            await _seed_initial_demand(session)
            await session.execute("""UPDATE market_candle_demand SET
                next_attempt_at=clock_timestamp()+interval '1 hour'
                WHERE NOT(base='BTC' AND timeframe='4h')""")
        from tests.api.indicator_refresh_consumer import refresh_once

        advanced = False
        consumer_time = 0.0

        async def advance(seconds: float) -> None:
            nonlocal advanced, consumer_time
            assert seconds == 10
            consumer_time += seconds
            if not advanced:
                advanced = True
                summary = await run_round(md, FullSource(), "ad-refresh", datetime.now(UTC))
                assert summary.stored >= 30
                stop.clear()
                await asyncio.wait_for(scheduler.run_scheduler(builder_engine, uuid4(), stop), 30)

        consumed = await refresh_once(
            client,
            before.json(),
            {"base": "BTC", "quote": "USDT", "timeframe": "4h", "page_size": 25} | bounds,
            csrf_headers(client),
            advance,
            requested=True,
            clock=lambda: consumer_time,
        )
        assert consumed.status == "READY", consumed
        after_body = consumed.pages[0]
    finally:
        await md.dispose()
    # The original cursor cannot silently switch to newly ingested source.
    stale = client.get("/market-data/indicators", params={"cursor": before.json()["next_cursor"]})
    assert stale.status_code == 409, stale.text
    assert len(published) == 2
    assert before.json()["generation_id"] != after_body["generation_id"]
    assert before.json()["dataset_revision"] != after_body["dataset_revision"]
    assert after_body["rows"][20]["values"]["ema20"]["status"] == "READY"
    assert after_body["rows"][20]["finality"] == "UNCONFIRMED"


async def test_duplicate_refresh_preserves_active_fetch_and_backoff(
    prepared: None,
    client: TestClient,
    migrator_engine: AsyncEngine,
) -> None:
    from datetime import UTC

    from tests.api.conftest import csrf_headers
    from tiewtrade.core.market_data import align_floor
    from tiewtrade.infra.db import DatabaseRole, create_engine_for
    from tiewtrade.infra.db.session import market_data_session
    from tiewtrade.infra.market_data.claims import claim_next, update_claim

    register(client)
    end = align_floor(datetime.now(UTC), Timeframe.H4)
    start = end - timedelta(hours=8)
    target = {
        "base": "BTC",
        "quote": "USDT",
        "timeframe": "4h",
        "start": start.isoformat(),
        "end": end.isoformat(),
    }
    assert (
        client.post(
            "/market-data/candles/requests", json=target, headers=csrf_headers(client)
        ).status_code
        == 202
    )
    md = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        async with market_data_session(md) as session:
            claim = await claim_next(session, "ad-active-fetch")
            assert claim is not None
            await update_claim(
                session,
                claim,
                attemptcount=2,
                fetch_unit_id=uuid4(),
                fetch_start=start,
                fetch_end=end,
                next_attempt_at=datetime.now(UTC) + timedelta(minutes=1),
            )
        async with migrator_engine.connect() as connection:
            before = dict(
                (await connection.execute(text("SELECT * FROM market_candle_demand")))
                .mappings()
                .one()
            )
        responses = await asyncio.gather(
            *(
                asyncio.to_thread(
                    client.post,
                    "/market-data/candles/requests",
                    json=target,
                    headers=csrf_headers(client),
                )
                for _ in range(2)
            )
        )
        assert all(response.status_code == 202 for response in responses)
        async with migrator_engine.connect() as connection:
            after = dict(
                (await connection.execute(text("SELECT * FROM market_candle_demand")))
                .mappings()
                .one()
            )
        for key in (
            "token",
            "worker",
            "generation",
            "lease_until",
            "cursor",
            "attemptcount",
            "fetch_unit_id",
            "fetch_start",
            "fetch_end",
            "next_attempt_at",
            "status",
        ):
            assert before[key] == after[key], key
    finally:
        await md.dispose()


async def test_satisfied_refresh_returns_200_and_expired_target_is_not_clamped(
    ready: dict[str, Any],
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.api.conftest import csrf_headers
    from tiewtrade.infra.market_data import storage

    register(client)
    target = {
        "base": "BTC",
        "quote": "USDT",
        "timeframe": "4h",
        "start": (ready["calculation_end"] - timedelta(hours=8)).isoformat(),
        "end": ready["calculation_end"].isoformat(),
    }
    response = client.post(
        "/market-data/candles/requests", json=target, headers=csrf_headers(client)
    )
    assert response.status_code == 200 and response.json() == {"accepted": False}

    async def expired(*args: Any) -> datetime:
        return cast(datetime, ready["as_of"]) + timedelta(days=366)

    monkeypatch.setattr(storage, "database_now", expired)
    result = client.post("/market-data/candles/requests", json=target, headers=csrf_headers(client))
    assert result.status_code == 422, result.text
    assert result.json() == {"detail": "RANGE_OUTSIDE_RETENTION"}


async def test_expiry_at_response_boundary_fails_without_partial_rows(
    ready: dict[str, Any],
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tiewtrade.services.api import indicator_routes

    register(client)
    response = first(client)
    assert response.status_code == 200, response.text
    from tiewtrade.infra.market_data.storage import database_now

    original = database_now
    calls = 0

    async def boundary(*args: Any) -> datetime:
        nonlocal calls
        calls += 1
        return await original(*args) if calls == 1 else cast(datetime, ready["expires_at"])

    monkeypatch.setattr(indicator_routes, "database_now", boundary)
    result = client.get(
        "/market-data/indicators", params={"cursor": response.json()["next_cursor"]}
    )
    # Session may expire before generation; either failure must return no rows.
    assert result.status_code in (401, 409), result.text
    assert "rows" not in result.json()


async def test_append_outside_upper_does_not_invalidate(
    ready: dict[str, Any],
    client: TestClient,
    migrator_engine: AsyncEngine,
) -> None:
    register(client)
    response = first(client)
    assert response.status_code == 200, response.text
    await change_source(migrator_engine, outside=True)
    assert (
        client.get(
            "/market-data/indicators", params={"cursor": response.json()["next_cursor"]}
        ).status_code
        == 200
    )
    # Default prepared result ends at U, independently of a newly aligned DB window.
    assert response.json()["result_end"] == ready["calculation_end"].isoformat().replace(
        "+00:00", "Z"
    )


async def test_fresh_head_at_next_window_does_not_clamp_explicit_end(
    ready: dict[str, Any],
    client: TestClient,
    migrator_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tiewtrade.services.api import indicator_routes

    register(client)
    next_upper = cast(datetime, ready["calculation_end"]) + Timeframe.H4.span
    as_of = next_upper - timedelta(microseconds=1)
    async with migrator_engine.begin() as c:
        # Controlled boundary fixture: preserve aligned L/U and controller state,
        # adjust only identity time and session lifetime for the clock probe.
        await c.execute(
            text("""UPDATE indicator_generations SET as_of=:asof,
            expires_at=CAST(:asof AS timestamptz)+interval '6 hours 10 minutes'"""),
            {"asof": as_of},
        )
        await c.execute(
            text("""UPDATE indicator_checkpoints SET payload=
            jsonb_set(payload,'{as_of}',to_jsonb(CAST(:moment AS text)))"""),
            {"moment": as_of.isoformat(timespec="microseconds")},
        )
        await c.execute(
            text("""UPDATE sessions SET idle_expires_at=
            least(absolute_expires_at,CAST(:now AS timestamptz)+interval '1 minute')
            WHERE token_hash=:hash"""),
            {"now": next_upper, "hash": hash_token(str(client.cookies.get(SESSION_COOKIE)))},
        )

    async def boundary(*args: Any) -> datetime:
        return next_upper

    monkeypatch.setattr(indicator_routes, "database_now", boundary)
    default = first(client)
    assert default.status_code == 200, default.text
    explicit = first(
        client, start=(next_upper - timedelta(hours=8)).isoformat(), end=next_upper.isoformat()
    )
    assert explicit.status_code == 503, explicit.text
    assert explicit.json()["detail"] == "INDICATOR_DATA_NOT_READY"
