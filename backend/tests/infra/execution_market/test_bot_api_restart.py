"""V-06: real API process loss after commit, key-only recovery and stable outcomes."""

import asyncio
import os
import socket
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

import httpx
import pytest
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market.test_bot_review_safety import registry
from tests.infra.positions.conftest import create_production_wallet
from tests.infra.risk_limits.test_execution import runtime
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.paper_wallet import get_wallet
from tiewtrade.services.engine.bot import StrategyRegistry, run_bot_control_round

pytestmark = pytest.mark.usefixtures("internal_database")

CHILD = """
import asyncio, sys
import uvicorn
from tiewtrade.services.api.app import app
app.state.bot_f21_enabled = sys.argv[2] == 'f21'
app.state.bot_paper_configurations = frozenset({'fixture-v1','unavailable-v1'})
@app.middleware('http')
async def hold_committed_ack(request, call_next):
    start = request.url.path == '/paper/bots/requests'
    if start and request.headers.get('X-Test-Hold-Before') == '1':
        await asyncio.sleep(60)
    response = await call_next(request)
    if start and request.headers.get('X-Test-Hold-Ack') == '1':
        await asyncio.sleep(60)
    return response
uvicorn.run(app, host='127.0.0.1', port=int(sys.argv[1]), log_level='error')
"""


@asynccontextmanager
async def api_process(port: int, *, enable_f21: bool = False) -> AsyncIterator[None]:
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        CHILD,
        str(port),
        "f21" if enable_f21 else "f20",
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}", timeout=0.2) as probe:
            for _ in range(100):
                if process.returncode is not None:
                    raise RuntimeError("isolated API exited before readiness")
                try:
                    if (await probe.get("/health")).status_code == 200:
                        break
                except httpx.TransportError:
                    pass
                await asyncio.sleep(0.05)
            else:
                raise RuntimeError("isolated API did not become ready")
        yield
    finally:
        if process.returncode is None:
            process.kill()
        await process.wait()


async def test_api_restart_recovers_committed_start_by_key_without_duplicate_run_or_audit(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    redis_url = os.environ.get("TIEWTRADE_TEST_REDIS_URL")
    if not redis_url:
        pytest.skip("isolated Redis test URL required")
    monkeypatch.setenv("TIEWTRADE_SIGNUP_OPEN", "1")
    monkeypatch.setenv("TIEWTRADE_COOKIE_SECURE", "0")
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    address = f"http://127.0.0.1:{port}"
    async with api_process(port), httpx.AsyncClient(base_url=address) as client:
        await client.get("/auth/csrf")
        registered = await client.post(
            "/auth/register",
            json={
                "email": f"f20-restart-{uuid4().hex}@example.com",
                "password": "isolated-process-fixture-password",
            },
            headers={"X-CSRF-Token": client.cookies["tiewtrade_csrf"]},
        )
        assert registered.status_code == 201
        owner = UUID((await client.get("/auth/me")).json()["user_id"])
        cookies = dict(client.cookies)
    wallet = await create_production_wallet(api_engine, engine_engine, scan_engine, owner)
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000", account_use="BOT"
    ) as sources:
        key, rejected_key = uuid4(), uuid4()
        payload = {"strategy_config_ref": "fixture-v1"}
        async with (
            api_process(port),
            httpx.AsyncClient(base_url=address, cookies=cookies) as client,
        ):
            headers = {
                "X-CSRF-Token": client.cookies["tiewtrade_csrf"],
                "Idempotency-Key": str(key),
            }
            with pytest.raises(httpx.ReadTimeout):
                await client.post(
                    "/paper/bots/requests",
                    json=payload,
                    headers={**headers, "X-Test-Hold-Ack": "1"},
                    timeout=0.3,
                )
            for _ in range(50):
                recovered = await client.get(f"/paper/bots/requests/by-key/{key}")
                if recovered.status_code == 200:
                    break
                await asyncio.sleep(0.05)
            assert recovered.status_code == 200 and recovered.json()["pending"]
            await sources.price("100")
            await run_bot_control_round(
                engine=engine_engine, scan_engine=scan_engine, registry=registry()
            )
            applied = (await client.get(f"/paper/bots/requests/by-key/{key}")).json()
            assert applied["run_id"] is not None and not applied["pending"]
            rejected_payload = {"strategy_config_ref": "unavailable-v1"}
            assert (
                await client.post(
                    "/paper/bots/requests",
                    json=rejected_payload,
                    headers={**headers, "Idempotency-Key": str(rejected_key)},
                )
            ).status_code == 202
            await run_bot_control_round(
                engine=engine_engine, scan_engine=scan_engine, registry=registry()
            )
            rejected = (await client.get(f"/paper/bots/requests/by-key/{rejected_key}")).json()
            assert rejected["failure_code"] == "BOT_STRATEGY_UNAVAILABLE"
            cookies = dict(client.cookies)
        # Lose the disposable notification/cache store after both durable outcomes.
        # Sessions, request identities and business facts must remain in PostgreSQL.
        redis = Redis.from_url(redis_url)
        try:
            await redis.flushdb()
            assert await redis.dbsize() == 0
        finally:
            await redis.aclose()
        # New process and HTTP client know cookies and original keys, not an
        # in-memory receipt or generated request ID. The previous server was killed.
        async with (
            api_process(port),
            httpx.AsyncClient(base_url=address, cookies=cookies) as restarted,
        ):
            assert (await restarted.get(f"/paper/bots/requests/by-key/{key}")).json() == applied
            assert (
                await restarted.get(f"/paper/bots/requests/by-key/{rejected_key}")
            ).json() == rejected
            for identity, body, expected in (
                (key, payload, applied),
                (rejected_key, rejected_payload, rejected),
            ):
                replay = await restarted.post(
                    "/paper/bots/requests",
                    json=body,
                    headers={
                        "X-CSRF-Token": restarted.cookies["tiewtrade_csrf"],
                        "Idempotency-Key": str(identity),
                    },
                )
                assert replay.status_code == 200 and replay.json() == expected
            conflict = await restarted.post(
                "/paper/bots/requests",
                json=rejected_payload,
                headers={
                    "X-CSRF-Token": restarted.cookies["tiewtrade_csrf"],
                    "Idempotency-Key": str(key),
                },
            )
            assert conflict.status_code == 409
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            for table, count in (
                ("bot_control_requests", 2),
                ("bot_control_results", 2),
                ("bot_runs", 1),
                ("bot_run_events", 1),
                ("paper_order_commands", 0),
                ("paper_orders", 0),
                ("paper_reservations", 0),
                ("paper_position_events", 0),
            ):
                assert (
                    await session.execute(f"SELECT count(*) FROM {table}")
                ).scalar_one() == count
            current = await get_wallet(session)
            assert current is not None and current.balance == wallet.balance


@pytest.mark.parametrize("after_commit", [False, True], ids=["before-commit", "after-commit"])
async def test_f21_recovers_start_after_http_timeout(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    after_commit: bool,
) -> None:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    address = f"http://127.0.0.1:{port}"
    config_key, start_key = uuid4(), uuid4()
    config = {"base": "BTC", "capital_per_entry": "100", "max_entries": 3}
    async with api_process(port, enable_f21=True), httpx.AsyncClient(base_url=address) as client:
        await client.get("/auth/csrf")
        auth = await client.post(
            "/auth/register",
            json={
                "email": f"f21-{uuid4().hex}@example.com",
                "password": "isolated-process-fixture-password",
            },
            headers={"X-CSRF-Token": client.cookies["tiewtrade_csrf"]},
        )
        assert auth.status_code == 201
        owner = UUID((await client.get("/auth/me")).json()["user_id"])
        cookies = dict(client.cookies)
        headers = {"X-CSRF-Token": cookies["tiewtrade_csrf"]}
        config_headers = {**headers, "Idempotency-Key": str(config_key)}
        start_headers = {**headers, "Idempotency-Key": str(start_key)}
        created = await client.post(
            "/paper/bots/configurations", json=config, headers=config_headers
        )
        assert created.status_code == 200
        ref = created.json()["reference"]
    wallet = await create_production_wallet(api_engine, engine_engine, scan_engine, owner)
    payload = {"strategy_config_ref": ref}
    path = "/paper/bots/requests"
    lookup = f"{path}/by-key/{start_key}"
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000", account_use="BOT"
    ) as source:
        async with (
            api_process(port, enable_f21=True),
            httpx.AsyncClient(base_url=address, cookies=cookies) as client,
        ):
            hold = "X-Test-Hold-Ack" if after_commit else "X-Test-Hold-Before"
            with pytest.raises(httpx.ReadTimeout):
                await client.post(
                    path, json=payload, headers={**start_headers, hold: "1"}, timeout=0.3
                )
            if after_commit:
                # Verify commit before killing the API; an arbitrary slow request is insufficient.
                for _ in range(50):
                    recovered = await client.get(lookup)
                    if recovered.status_code == 200:
                        break
                    await asyncio.sleep(0.05)
                assert recovered.status_code == 200 and recovered.json()["pending"]
        async with (
            api_process(port, enable_f21=True),
            httpx.AsyncClient(base_url=address, cookies=cookies) as client,
        ):
            stored = await client.get("/paper/bots/configurations/" + ref[4:])
            assert stored.status_code == 200 and stored.json() == created.json()
            replay = await client.post(
                "/paper/bots/configurations", json=config, headers=config_headers
            )
            assert replay.status_code == 200 and replay.json() == created.json()
            before = await client.get(lookup)
            assert before.status_code == (200 if after_commit else 404)
            retry = await client.post(path, json=payload, headers=start_headers)
            assert retry.status_code in (200, 202) and retry.json()["pending"]
            if after_commit:
                assert retry.json() == recovered.json()
            await source.price("100")
            controls = await run_bot_control_round(
                engine=engine_engine,
                scan_engine=scan_engine,
                registry=StrategyRegistry(enable_f21=True),
            )
            assert controls.applied == 1 and controls.refused == 0
            receipt = await client.get(lookup)
            assert (
                receipt.status_code == 200
                and receipt.json()["run_id"]
                and not receipt.json()["pending"]
            )
            replay = await client.post(path, json=payload, headers=start_headers)
            assert replay.status_code == 200 and replay.json() == receipt.json()
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            for table, count in (
                ("bot_strategy_configurations", 1),
                ("bot_control_requests", 1),
                ("bot_control_results", 1),
                ("bot_runs", 1),
                ("paper_order_commands", 0),
                ("paper_position_events", 0),
            ):
                assert (
                    await session.execute(f"SELECT count(*) FROM {table}")
                ).scalar_one() == count
