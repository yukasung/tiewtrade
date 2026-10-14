"""Explicit Docker acceptance: independent compatible API releases, actual PG/Redis.

Run only against disposable F-11 test services. Images must contain the real API;
no source mounts, decoder stubs, or application containers are used. These tests
do not certify R2-D1 (a preserved full-scan release is required) or capacity.
"""

import asyncio
import base64
import json
import os
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from random import Random
from time import monotonic
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.conftest import TEST_SEALING_KEY, TEST_VENUE_KEY
from tests.infra.indicators.test_claims import builder_engine as builder_engine
from tests.infra.indicators.test_claims import prepared as prepared
from tests.infra.indicators.test_rollout import control, transition
from tests.infra.indicators.test_rollout import reset_transition_history as reset_transition_history
from tests.infra.indicators.test_source import active as active
from tests.services.indicator_builder.profile_container_recovery import docker
from tiewtrade.core.indicators import IndicatorPoint
from tiewtrade.core.market_data import CandleWindow, Timeframe, advance
from tiewtrade.core.money import Money, Scalar
from tiewtrade.infra.auth.sessions import hash_token, owner_of_presented
from tiewtrade.infra.crypto.indicator_cursor import (
    CursorClaims,
    PreparedCursorClaims,
    check_expiry,
    issue,
    verify,
)
from tiewtrade.infra.crypto.keys import KeyPurpose, KeySource
from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.infra.db.session import indicator_read_session, presented_session
from tiewtrade.infra.indicators.pinned import pinned_indicator_writer
from tiewtrade.infra.indicators.rollout import (
    Mode,
    RolloutRejectedError,
    orchestrate,
)
from tiewtrade.infra.market_data.indicator_reader import read_indicators
from tiewtrade.services.api.indicator_routes import IndicatorPointView, IndicatorValueView
from tiewtrade.services.api.settings import CSRF_COOKIE, CSRF_HEADER, SESSION_COOKIE
from tiewtrade.services.indicator_builder.attempt import AttemptStatus, run_attempt

PATH = "/market-data/indicators"
QUERY: dict[str, str | int] = {"base": "BTC", "quote": "USDT", "timeframe": "4h", "page_size": 2}

# Only the D3 window enables this clock; image code/decoders/cleanup stay real.
CLOCKED_API = """
import json
from datetime import datetime
from pathlib import Path
import uvicorn
import tiewtrade.infra.db.session as db
import tiewtrade.services.api.authentication as authentication
clock=Path('/tmp/d3-clock')
execute=db._execute
async def clocked(connection, statement, parameters):
    if Path('/tmp/d4-audit-enabled').exists():
        lowered=statement.lower()
        kind=lowered.strip().split()[0]
        event={'kind':kind,
               'unsafe_dml':kind in ('insert','update','delete','merge','truncate')
                    and 'sessions' not in lowered,
               'payload':any(name in lowered for name in
                   ('indicator_generations','indicator_checkpoints','indicator_heads',
                    'indicator_ready_','indicator_numeric_failures','market_candles'))}
        with Path('/tmp/d4-audit.jsonl').open('a') as output:
            output.write(json.dumps(event)+'\\n')
    if clock.exists():
        moment=datetime.fromisoformat(clock.read_text()).isoformat()
        expression="CAST('"+moment+"' AS timestamptz)"
        statement=statement.replace('clock_timestamp()',expression).replace('now()',expression)
    return await execute(connection,statement,parameters)
class Clock(datetime):
    @classmethod
    def now(cls, tz=None):
        if clock.exists():
            return datetime.fromisoformat(clock.read_text()).astimezone(tz)
        return datetime.now(tz)
db._execute=clocked
authentication.datetime=Clock
uvicorn.run('tiewtrade.services.api.app:app',host='0.0.0.0',port=8000,access_log=False)
"""


@pytest.fixture(autouse=True)
def isolated_services() -> None:
    assert "127.0.0.1:55433/" in os.environ["TIEWTRADE_DATABASE_URL_MIGRATOR"]
    assert "127.0.0.1:56379/" in os.environ["TIEWTRADE_TEST_REDIS_URL"]


@dataclass
class Replicas:
    project: str
    image_ids: tuple[str, str]
    containers: list[str] = field(default_factory=list)
    clients: list[httpx.AsyncClient] = field(default_factory=list)
    controlled_clock: bool = False

    async def start(self, image: str) -> httpx.AsyncClient:
        # Values are public, isolated test credentials. No inherited app env.
        env = {
            "TIEWTRADE_DATABASE_URL_API": "postgresql+asyncpg://tiewtrade_api:dev_api@"
            "tiewtrade-f11-test-postgres:5432/tiewtrade",
            "TIEWTRADE_DATABASE_URL_AUTH": "postgresql+asyncpg://tiewtrade_auth:dev_auth@"
            "tiewtrade-f11-test-postgres:5432/tiewtrade",
            "TIEWTRADE_REDIS_URL_API": "redis://tiewtrade-f11-test-redis:6379/0",
            "TIEWTRADE_SEALING_KEY_TOTP_SECRET": TEST_SEALING_KEY,
            "TIEWTRADE_SEALING_KEY_VENUE_API_SECRET": TEST_VENUE_KEY,
            "TIEWTRADE_SEALING_KEY_INDICATOR_CURSOR": "1:" + base64.b64encode(b"I" * 32).decode(),
            "TIEWTRADE_PRICE_ORIGINS": "http://localhost:5173",
            "TIEWTRADE_SIGNUP_OPEN": "1",
            "TIEWTRADE_COOKIE_SECURE": "0",
        }
        arguments = [
            "run",
            "-d",
            "--pull=never",
            "--network",
            "tiewtrade-f11-test-net",
            "--restart=no",
            "--label",
            f"com.docker.compose.project={self.project}",
            "--label",
            "com.docker.compose.service=api",
            "--memory=512m",
            "--cpus=1",
            "-p",
            "127.0.0.1::8000",
        ]
        for name, value in env.items():
            arguments.extend(("-e", name + "=" + value))
        command = [
            "uvicorn",
            "tiewtrade.services.api.app:app",
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
            "--no-access-log",
        ]
        if self.controlled_clock:
            command = ["python", "-c", CLOCKED_API]
        container = await docker(*arguments, image, *command)
        self.containers.append(container)
        port = (await docker("port", container, "8000/tcp")).rsplit(":", 1)[1]
        client = httpx.AsyncClient(base_url="http://127.0.0.1:" + port, timeout=35)
        self.clients.append(client)
        await self.ready(client)
        return client

    async def ready(self, client: httpx.AsyncClient) -> None:
        async with asyncio.timeout(15):
            while True:
                try:
                    if (await client.get("/auth/csrf")).status_code == 200:
                        return
                except httpx.TransportError:
                    pass  # Docker process has not bound its HTTP socket yet.
                await asyncio.sleep(0.1)

    async def stop_all(self) -> None:
        for container in self.containers:
            await docker("stop", "--time", "2", container)

    async def resume_all(self) -> None:
        for container in self.containers:
            await docker("start", container)
        for index, client in enumerate(self.clients):
            await self.refresh_address(index)
            await self.ready(client)

    async def refresh_address(self, index: int) -> None:
        # Docker can assign a new ephemeral host port after stop/start.
        port = (await docker("port", self.containers[index], "8000/tcp")).rsplit(":", 1)[1]
        self.clients[index].base_url = httpx.URL("http://127.0.0.1:" + port)


@pytest_asyncio.fixture
async def replicas(migrator_engine: AsyncEngine) -> AsyncIterator[Replicas]:
    # Reject accidental use of the developer/application DB before any mutation.
    assert "127.0.0.1:55433/" in os.environ["TIEWTRADE_DATABASE_URL_MIGRATOR"]
    assert "127.0.0.1:56379/" in os.environ["TIEWTRADE_TEST_REDIS_URL"]
    async with migrator_engine.begin() as c:
        await c.execute(text("DELETE FROM auth_throttle"))
    redis = Redis.from_url(os.environ["TIEWTRADE_TEST_REDIS_URL"])
    try:
        await redis.flushdb()
    finally:
        await redis.aclose()
    images = tuple(
        [
            await docker("image", "inspect", "--format", "{{.Id}}", tag)
            for tag in ("tiewtrade-f11-rollout-test:latest", "tiewtrade-f11-mixed-test:latest")
        ]
    )
    assert len(images) == 2 and images[0] != images[1]
    pair = Replicas("f11-mixed-" + uuid4().hex, (images[0], images[1]), controlled_clock=True)
    try:
        await pair.start(images[0])
        await pair.start(images[1])
        yield pair
    finally:
        for client in pair.clients:
            await client.aclose()
        for container in pair.containers:
            await docker("rm", "--force", container)


@pytest_asyncio.fixture
async def published(
    prepared: None, builder_engine: AsyncEngine, migrator_engine: AsyncEngine
) -> dict[str, Any]:
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
        assert writer is not None
        await writer.seed()
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
    # Actual sealed manifests/checkpoints for every series; sparse source is a
    # lifecycle fixture, never a substitute for the C1..C6 full capacity workload.
    for _ in range(30):
        assert (await run_attempt(builder_engine, uuid4())).status is AttemptStatus.READY
    state = await control(migrator_engine)
    assert (
        await transition(migrator_engine, Mode.PREPARING, state["rollout_epoch"], Mode.PREPARED)
    )["result"] == "APPLIED"
    async with migrator_engine.connect() as c:
        generation = dict(
            (
                await c.execute(
                    text(
                        "SELECT * FROM indicator_generations "
                        "WHERE base='BTC' AND timeframe='4h' AND status='READY'"
                    )
                )
            )
            .mappings()
            .one()
        )
    await builder_engine.dispose()
    return generation


async def authenticate(pair: Replicas) -> None:
    a, b = pair.clients[:2]
    response = await a.post(
        "/auth/register",
        json={
            "email": "mixed-" + uuid4().hex + "@example.com",
            "password": "รหัสผ่านที่ยาวพอใช้งานจริง",
        },
        headers={CSRF_HEADER: str(a.cookies.get(CSRF_COOKIE))},
    )
    assert response.status_code == 201
    b.cookies.update(dict(a.cookies))


async def claims_for(
    client: httpx.AsyncClient, token: str
) -> tuple[PreparedCursorClaims, UUID, str]:
    engine = create_engine_for(DatabaseRole.API)
    hashed = hash_token(str(client.cookies.get(SESSION_COOKIE)))
    try:
        async with presented_session(engine, token_hash=hashed) as s:
            owner = await owner_of_presented(s)
            assert owner is not None
        result = verify(
            token, KeySource.from_environment(KeyPurpose.INDICATOR_CURSOR), owner.user_id, hashed
        )
        assert isinstance(result, PreparedCursorClaims)
        return result, owner.user_id, hashed
    finally:
        await engine.dispose()


async def token_status(pair: Replicas, token: str, expected: int) -> None:
    # Independent cursor rejection cases need a fresh rate bucket, like the
    # existing API tests. The actual 6/min shared limit is tested below.
    await reset_admission()
    for client in pair.clients[:2]:
        response = await client.get(PATH, params={"cursor": token})
        # Do not print response/cursor in assertion diagnostics or JUnit.
        assert response.status_code == expected


async def reset_admission() -> None:
    redis = Redis.from_url(os.environ["TIEWTRADE_TEST_REDIS_URL"])
    try:
        await redis.flushdb()
    finally:
        await redis.aclose()


def point_views(points: Sequence[IndicatorPoint]) -> list[dict[str, Any]]:
    return [
        IndicatorPointView(
            open_at=p.open_at,
            seed_open_at=p.seed_open_at,
            finality=p.finality.value if p.finality else None,
            values={
                name: IndicatorValueView(
                    value=v.value.as_text()
                    if isinstance(v.value, Scalar)
                    else v.value.as_parts()["amount"]
                    if v.value is not None
                    else None,
                    unit=v.value.currency if isinstance(v.value, Money) else None,
                    status=v.status.value,
                )
                for name, v in p.values.items()
            },
        ).model_dump(mode="json")
        for p in points
    ]


async def check_d2_cross_replica_parity_restart_and_cursor_lifecycle(
    published: dict[str, Any], replicas: Replicas, api_engine: AsyncEngine
) -> None:
    await authenticate(replicas)
    a, b = replicas.clients[:2]
    first = await a.get(PATH, params=QUERY)
    assert first.status_code == 200
    page = first.json()
    token = page["next_cursor"]
    claims, user, hashed = await claims_for(a, token)
    async with indicator_read_session(api_engine, user) as s:
        reference = await read_indicators(
            s,
            "BTC",
            "USDT",
            Timeframe.H4,
            CandleWindow(published["calculation_start"], published["calculation_end"]),
            CandleWindow(claims.result_start, claims.result_end),
            published["as_of"],
            monotonic() + 30,
        )
    expected = point_views(reference.points)
    # This dense fixture has a known page size; an empty/short prefix is invalid.
    assert len(expected) >= 14
    keys = KeySource.from_environment(KeyPurpose.INDICATOR_CURSOR)

    def check_page(body: dict[str, Any], offset: int) -> str:
        assert len(body["rows"]) == claims.page_size
        assert body["rows"] == expected[offset : offset + claims.page_size]
        next_token = body["next_cursor"]
        assert isinstance(next_token, str)
        next_claims = verify(next_token, keys, user, hashed)
        assert isinstance(next_claims, PreparedCursorClaims)
        assert next_claims == claims.model_copy(
            update={
                "next_open_at": advance(
                    claims.result_start, claims.timeframe, offset + claims.page_size
                )
            }
        )
        return next_token

    token = check_page(page, 0)
    offset = claims.page_size
    # Five requests total in one window, with both cross-replica directions.
    routing = [1, 0, *Random(11).sample([0, 1], 2)]
    for index in routing:
        response = await replicas.clients[index].get(PATH, params={"cursor": token})
        assert response.status_code == 200
        body = response.json()
        token = check_page(body, offset)
        offset += claims.page_size
    await docker("restart", "--time", "2", replicas.containers[1])
    await replicas.refresh_address(1)
    await replicas.ready(b)
    await reset_admission()
    # Replay the same input on both releases after restart, then advance across
    # replicas. Every returned page and signed cursor must match the reference.
    after_restart = []
    for client in (a, b):
        response = await client.get(PATH, params={"cursor": token})
        assert response.status_code == 200
        after_restart.append(check_page(response.json(), offset))
    same_cursor = after_restart[0] == after_restart[1]
    assert same_cursor
    token = after_restart[1]
    offset += claims.page_size
    response = await a.get(PATH, params={"cursor": token})
    assert response.status_code == 200
    token = check_page(response.json(), offset)
    v1 = CursorClaims.model_validate(
        {
            k: v
            for k, v in claims.model_dump().items()
            if k not in {"generation_id", "codec_version", "rollout_epoch"}
        }
        | {"format_version": 1}
    )
    await token_status(replicas, issue(v1, keys, user, hashed), 409)
    expired = claims.model_copy(
        update={
            "issued_at": claims.issued_at - timedelta(hours=6),
            "expires_at": claims.issued_at - timedelta(seconds=1),
        }
    )
    await token_status(replicas, issue(expired, keys, user, hashed), 409)
    retired = KeySource(KeyPurpose.INDICATOR_CURSOR, "retired", {"retired": b"R" * 32})
    await token_status(replicas, issue(claims, retired, user, hashed), 409)
    await token_status(replicas, token[:-1] + ("A" if token[-1] != "A" else "B"), 422)
    version, payload, mac = token.split(".")
    data = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    data["format_version"] = 1
    spoof = base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")
    await token_status(replicas, version + "." + spoof + "." + mac, 422)
    other = await replicas.start(replicas.image_ids[1])
    response = await other.post(
        "/auth/register",
        json={
            "email": "other-" + uuid4().hex + "@example.com",
            "password": "รหัสผ่านที่ยาวพอใช้งานจริง",
        },
        headers={CSRF_HEADER: str(other.cookies.get(CSRF_COOKIE))},
    )
    assert response.status_code == 201
    assert (await other.get(PATH, params={"cursor": token})).status_code == 422
    await reset_admission()
    redis = Redis.from_url(os.environ["TIEWTRADE_TEST_REDIS_URL"])
    try:
        seconds, _ = await redis.time()
        if seconds % 60 > 50:
            await asyncio.sleep(60 - seconds % 60)
    finally:
        await redis.aclose()
    for index in range(6):
        assert (await replicas.clients[index % 2].get(PATH, params=QUERY)).status_code == 200
    assert (await b.get(PATH, params=QUERY)).status_code == 429
    await reset_admission()


async def check_d4_live_api_pool_blocks_pause_then_db_epoch_invalidates_every_replica(
    published: dict[str, Any], replicas: Replicas, migrator_engine: AsyncEngine
) -> None:
    from tests.infra.indicators.test_rollout import Docker, inventory

    await reset_admission()
    response = await replicas.clients[0].get(PATH, params=QUERY)
    assert response.status_code == 200
    token = response.json()["next_cursor"]
    before = await control(migrator_engine)
    # A real HTTP continuation is held at its source relation read. Observe the
    # backend barrier instead of pausing a mocked request handler.
    async with migrator_engine.begin() as blocker:
        await blocker.execute(text("LOCK TABLE market_candles IN ACCESS EXCLUSIVE MODE"))
        pending = asyncio.create_task(replicas.clients[0].get(PATH, params={"cursor": token}))
        try:
            async with asyncio.timeout(2):
                while True:
                    async with migrator_engine.connect() as c:
                        waiting: bool = (
                            await c.execute(
                                text(
                                    "SELECT EXISTS(SELECT 1 "
                                    "FROM pg_locks l JOIN pg_stat_activity a ON a.pid=l.pid "
                                    "WHERE a.datname=current_database() "
                                    "AND a.usename='tiewtrade_api' "
                                    "AND l.locktype='relation' AND NOT l.granted "
                                    "AND l.relation='market_candles'::regclass)"
                                )
                            )
                        ).scalar_one()
                    if waiting:
                        break
                    assert not pending.done()
                    await asyncio.sleep(0.01)
            with pytest.raises(RolloutRejectedError):
                await orchestrate(
                    migrator_engine,
                    inventory(),
                    Mode.PREPARED,
                    before["rollout_epoch"],
                    Mode.PAUSED,
                    runner=Docker(),
                )
            assert (await control(migrator_engine))["rollout_epoch"] == before["rollout_epoch"]
        finally:
            # API lock/query budgets bound the response; join it before flipping.
            response = await asyncio.wait_for(pending, 2)
            assert response.status_code == 503
    # Even a supplied inventory cannot hide active or idle DB pools of live APIs.
    try:
        await orchestrate(
            migrator_engine,
            inventory(),
            Mode.PREPARED,
            before["rollout_epoch"],
            Mode.PAUSED,
            runner=Docker(),
        )
    except RolloutRejectedError:
        pass
    else:
        raise AssertionError("live replica accepted")
    assert (await control(migrator_engine))["rollout_epoch"] == before["rollout_epoch"]
    await replicas.stop_all()
    result = await transition(migrator_engine, Mode.PREPARED, before["rollout_epoch"], Mode.PAUSED)
    assert result["result"] == "APPLIED"
    await replicas.resume_all()
    # Remove derived payloads: PAUSED must decide lifecycle before accessing them.
    async with migrator_engine.begin() as c:
        await c.execute(text("DELETE FROM indicator_checkpoints"))
    await reset_admission()
    for client in replicas.clients[:2]:
        assert (await client.get(PATH, params=QUERY)).status_code == 503
    await token_status(replicas, token, 409)


async def check_d5_pause_cutoff_retirement_reader_drain_and_reenable_old_token(
    published: dict[str, Any], replicas: Replicas, migrator_engine: AsyncEngine
) -> None:
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from alembic.util import load_python_file
    from sqlalchemy import Connection
    from sqlalchemy.exc import DBAPIError

    response = await replicas.clients[0].get(PATH, params=QUERY)
    assert response.status_code == 200
    token = response.json()["next_cursor"]
    claims, user, hashed = await claims_for(replicas.clients[0], token)
    other = replicas.clients[2]
    other_response = await other.get(PATH, params=QUERY)
    assert other_response.status_code == 200
    other_token = other_response.json()["next_cursor"]
    _, _, other_hash = await claims_for(other, other_token)
    older = claims.model_copy(
        update={
            "issued_at": claims.issued_at - timedelta(hours=1),
            "expires_at": claims.expires_at - timedelta(hours=1),
        }
    )
    older_token = issue(
        older, KeySource.from_environment(KeyPurpose.INDICATOR_CURSOR), user, hashed
    )
    await replicas.stop_all()
    before = await control(migrator_engine)
    pause = await transition(migrator_engine, Mode.PREPARED, before["rollout_epoch"], Mode.PAUSED)
    assert pause["result"] == "APPLIED" and pause["cutoff"] is not None
    assert (await transition(migrator_engine, Mode.PREPARED, before["rollout_epoch"], Mode.PAUSED))[
        "cutoff"
    ] == pause["cutoff"]
    migration = load_python_file(
        Path(__file__).resolve().parents[3] / "migrations/versions", "0023_indicator_rollout.py"
    )

    def downgrade(connection: Connection) -> None:
        with Operations.context(MigrationContext.configure(connection)):
            migration.downgrade()

    try:
        async with migrator_engine.begin() as c:
            await c.run_sync(downgrade)
    except DBAPIError:
        pass
    else:
        raise AssertionError("premature schema removal accepted")
    await replicas.resume_all()
    await token_status(replicas, token, 409)
    await token_status(replicas, older_token, 409)
    expiry_engine = create_engine_for(DatabaseRole.API)
    try:
        async with presented_session(expiry_engine, token_hash=other_hash) as s:
            assert (
                await s.execute(
                    "UPDATE sessions SET idle_expires_at="
                    "clock_timestamp()+interval '200 milliseconds' "
                    "WHERE token_hash=:hash RETURNING 1",
                    {"hash": other_hash},
                )
            ).scalar_one() == 1
    finally:
        await expiry_engine.dispose()
    await asyncio.sleep(0.35)
    assert (await other.get(PATH, params={"cursor": other_token})).status_code == 401
    await replicas.stop_all()
    paused = await control(migrator_engine)
    assert (
        await transition(migrator_engine, Mode.PAUSED, paused["rollout_epoch"], Mode.PREPARING)
    )["result"] == "APPLIED"
    preparing = await control(migrator_engine)
    assert (
        await transition(migrator_engine, Mode.PREPARING, preparing["rollout_epoch"], Mode.PREPARED)
    )["result"] == "APPLIED"
    await replicas.resume_all()
    await token_status(replicas, token, 409)
    for client in replicas.clients[:2]:
        assert (await client.get(PATH, params=QUERY)).status_code == 200


async def check_d3_actual_cleanup_images_preserve_grace_seed(
    replicas: Replicas,
    migrator_engine: AsyncEngine,
    api_engine: AsyncEngine,
    published: dict[str, Any],
) -> None:
    await reset_admission()
    first = await replicas.clients[0].get(PATH, params=QUERY)
    assert first.status_code == 200
    token = first.json()["next_cursor"]
    claims, user, hashed = await claims_for(replicas.clients[0], token)
    keys = KeySource.from_environment(KeyPurpose.INDICATOR_CURSOR)
    async with indicator_read_session(api_engine, user) as session:
        reference = await read_indicators(
            session,
            "BTC",
            "USDT",
            Timeframe.H4,
            CandleWindow(published["calculation_start"], published["calculation_end"]),
            CandleWindow(claims.result_start, claims.result_end),
            published["as_of"],
            monotonic() + 30,
        )
    expected = point_views(reference.points)
    assert len(expected) >= 6
    assert first.json()["rows"] == expected[:2]
    seed = reference.points[0].seed_open_at
    assert seed == published["calculation_start"]
    async with migrator_engine.connect() as c:
        seed_before: dict[str, Any] = (
            await c.execute(
                text(
                    "SELECT to_jsonb(c) FROM market_candles c WHERE base='BTC' "
                    "AND timeframe='4h' AND open_at=:seed"
                ),
                {"seed": seed},
            )
        ).scalar_one()
    async with migrator_engine.begin() as c:
        await c.execute(text("SELECT begin_indicator_source_write()"))
        await c.execute(
            text("""INSERT INTO market_candles
          (source,base,quote,timeframe,open_at,end_at,open,high,low,close,volume,finality,
           observed_at,fetch_started_at,last_checked_at,ingestion_generation)
          SELECT 'primary_spot','BTC','USDT','4h',moment,moment+interval '4 hours',
            1,2,1,1,0,'CLOSED',clock_timestamp(),clock_timestamp(),clock_timestamp(),1
          FROM unnest(ARRAY[
            (SELECT calculation_start-interval '12 hours' FROM indicator_generations
               WHERE base='BTC' AND timeframe='4h' AND status='READY'),
            (SELECT calculation_start-interval '4 hours' FROM indicator_generations
               WHERE base='BTC' AND timeframe='4h' AND status='READY')]) moment""")
        )
    program = """
import asyncio,json,sys
from datetime import datetime
from tiewtrade.infra.db import DatabaseRole,create_engine_for
from tiewtrade.infra.db.session import market_data_session,MarketDataSession
from tiewtrade.infra.market_data.claims import cleanup
execute=MarketDataSession.execute
async def clocked(self,statement,parameters=None):
    if len(sys.argv)>1 and statement=="SELECT clock_timestamp()":
        return await execute(self,"SELECT CAST(:moment AS timestamptz)",
                             {"moment":datetime.fromisoformat(sys.argv[1])})
    return await execute(self,statement,parameters)
MarketDataSession.execute=clocked
async def run():
    engine=create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        async with market_data_session(engine) as session:
            count=await cleanup(session)
        print(json.dumps({'result':'CLEANED','count':count}))
    except Exception as error:
        # Old releases translate driver errors with "raise ... from None".
        # The implicit context still carries SQLSTATE; inspect it without ever
        # serializing exception messages, connection URLs, or driver parameters.
        pending=[error]
        seen=set()
        rejected=False
        while pending:
            current=pending.pop()
            if id(current) in seen:
                continue
            seen.add(id(current))
            if (getattr(current,'sqlstate',None)=='TT011'
                    or getattr(current,'pgcode',None)=='TT011'):
                rejected=True
            for name in ('orig','__cause__','__context__'):
                nested=getattr(current,name,None)
                if isinstance(nested,BaseException):
                    pending.append(nested)
        print(json.dumps({'result':'REJECTED','sqlstate':'TT011'}
                         if rejected else {'result':'FAILED'}))
    finally:
        await engine.dispose()
asyncio.run(run())
"""

    async def cleanup_image(image: str, moment: datetime | None = None) -> dict[str, Any]:
        result = await docker(
            "run",
            "--rm",
            "--network",
            "tiewtrade-f11-test-net",
            "-e",
            "TIEWTRADE_DATABASE_URL_MARKET_DATA="
            "postgresql+asyncpg://tiewtrade_market_data:dev_market_data@"
            "tiewtrade-f11-test-postgres:5432/tiewtrade",
            image,
            "python",
            "-c",
            program,
            *([moment.isoformat()] if moment else []),
        )
        value: dict[str, Any] = json.loads(result)
        return value

    legacy = await docker("image", "inspect", "--format", "{{.Id}}", "tiewtrade-api:latest")
    assert await cleanup_image(legacy) == {"result": "REJECTED", "sqlstate": "TT011"}
    trace: list[dict[str, Any]] = [
        {
            "step": "cursor_before_cleanup",
            "series": "BTC/USDT/4h",
            "seed": seed,
            "generation": claims.generation_id,
            "parity": True,
        },
        {"step": "legacy_cleanup", "image": legacy, "sqlstate": "TT011"},
    ]
    assert seed is not None
    cleanup_now = seed + timedelta(days=365, microseconds=1)
    ordinary_cutoff = cleanup_now - timedelta(days=365)
    grace_cutoff = ordinary_cutoff - timedelta(hours=6, minutes=15)
    assert grace_cutoff < seed < ordinary_cutoff
    assert claims.issued_at < cleanup_now < claims.expires_at
    assert cleanup_now < published["expires_at"]
    check_expiry(claims, cleanup_now)
    # Keep the existing presented session alive across the simulated active-user interval.
    async with presented_session(api_engine, token_hash=hashed) as presented:
        assert (
            await presented.execute(
                "UPDATE sessions SET idle_expires_at=:until WHERE token_hash=:hash RETURNING 1",
                {"until": cleanup_now + timedelta(minutes=30), "hash": hashed},
            )
        ).scalar_one() == 1
    try:
        for container in replicas.containers[:2]:
            await docker(
                "exec",
                container,
                "python",
                "-c",
                "from pathlib import Path; import sys; "
                "Path('/tmp/d3-clock').write_text(sys.argv[1])",
                cleanup_now.isoformat(),
            )
        for index, image in enumerate(replicas.image_ids):
            outcome = await cleanup_image(image, cleanup_now)
            assert outcome == {"result": "CLEANED", "count": 1 if index == 0 else 0}
            async with migrator_engine.connect() as c:
                seed_after: dict[str, Any] = (
                    await c.execute(
                        text(
                            "SELECT to_jsonb(c) FROM market_candles c WHERE base='BTC' "
                            "AND timeframe='4h' AND open_at=:seed"
                        ),
                        {"seed": seed},
                    )
                ).scalar_one()
                assert seed_after == seed_before
                retained: Sequence[datetime] = (
                    (
                        await c.execute(
                            text(
                                "SELECT open_at FROM market_candles "
                                "WHERE base='BTC' AND timeframe='4h' "
                                "AND open_at<:start ORDER BY open_at"
                            ),
                            {"start": published["calculation_start"]},
                        )
                    )
                    .scalars()
                    .all()
                )
                assert retained == [published["calculation_start"] - timedelta(hours=4)]
            await reset_admission()
            offset = 2 + index * 2
            returned = []
            for client in replicas.clients[:2]:
                response = await client.get(PATH, params={"cursor": token})
                assert response.status_code == 200
                body = response.json()
                assert body["generation_age_seconds"] == int(
                    (cleanup_now - claims.as_of).total_seconds()
                )
                assert body["rows"] == expected[offset : offset + 2]
                next_claims = verify(body["next_cursor"], keys, user, hashed)
                assert next_claims == claims.model_copy(
                    update={
                        "next_open_at": claims.result_start + (offset + 2) * Timeframe.H4.span,
                    }
                )
                returned.append(body["next_cursor"])
            assert returned[0] == returned[1]
            token = returned[1]
            trace.append(
                {
                    "step": "cleanup_then_continuation",
                    "image": image,
                    "deleted": outcome["count"],
                    "cleanup_now": cleanup_now,
                    "ordinary_cutoff": ordinary_cutoff,
                    "grace_cutoff": grace_cutoff,
                    "seed_requires_grace": True,
                    "seed_unchanged": True,
                    "grace_probe": retained[0],
                    "offset": offset,
                    "both_replicas_parity": True,
                }
            )
    finally:
        for container in replicas.containers[:2]:
            await docker(
                "exec",
                container,
                "python",
                "-c",
                "from pathlib import Path; Path('/tmp/d3-clock').unlink(missing_ok=True)",
            )
    target = os.environ.get("TIEWTRADE_D3_EVIDENCE_PATH")
    if target:
        Path(target).write_text(json.dumps(trace, default=str, indent=2), encoding="utf-8")
    await api_engine.dispose()


async def test_real_replica_lifecycle_d2_d4_d5(
    published: dict[str, Any],
    replicas: Replicas,
    api_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
) -> None:
    # One continuous deployment rehearsal; build the same immutable source once.
    await check_d2_cross_replica_parity_restart_and_cursor_lifecycle(
        published, replicas, api_engine
    )
    await api_engine.dispose()
    await check_d3_actual_cleanup_images_preserve_grace_seed(
        replicas, migrator_engine, api_engine, published
    )
    await check_d5_pause_cutoff_retirement_reader_drain_and_reenable_old_token(
        published, replicas, migrator_engine
    )
    await check_d4_live_api_pool_blocks_pause_then_db_epoch_invalidates_every_replica(
        published, replicas, migrator_engine
    )
