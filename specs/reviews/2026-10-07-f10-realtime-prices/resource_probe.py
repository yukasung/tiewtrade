"""Disposable F10 actual-network resource validation (no market connections).

Run from backend with isolated DB URLs sourced and --driver. The driver creates
its own DB, runs migrations, uses Redis database 7, and stops both API processes.
Only generated user/session records and this database are changed.
"""

import asyncio
import base64
import json
import os
import subprocess
import sys
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import asyncpg
import httpx
import uvicorn
from redis.asyncio import Redis
from sqlalchemy import event
from websockets.asyncio.client import connect

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "backend"
DB = "tiewtrade_f10_resource_probe_" + str(int(time.time()))
RESULT = Path("/private/tmp/f10-resource-result.json")


async def server(port):
    from tiewtrade.services.api.app import app, lifespan

    metrics = dict(
        transactions=0,
        queries=0,
        max_checked_out=0,
        max_tasks=0,
        max_physical=0,
        max_pending=0,
        samples=[],
        public_reads=[],
    )

    @asynccontextmanager
    async def instrumented(app):
        async with lifespan(app):
            engine = app.state.price_engine
            event.listen(
                engine.sync_engine,
                "begin",
                lambda c: metrics.__setitem__(
                    "transactions", metrics["transactions"] + 1
                ),
            )

            def query_observed(
                conn, cursor, statement, parameters, context, executemany
            ):
                metrics["queries"] += 1
                if "SELECT p.*,f.generation" in statement:
                    metrics["public_reads"].append(time.monotonic())

            event.listen(engine.sync_engine, "before_cursor_execute", query_observed)

            async def monitor():
                while True:
                    metrics["max_checked_out"] = max(
                        metrics["max_checked_out"], engine.pool.checkedout()
                    )
                    metrics["max_tasks"] = max(
                        metrics["max_tasks"], len(asyncio.all_tasks())
                    )
                    metrics["max_physical"] = max(
                        metrics["max_physical"], app.state.price_budget.physical
                    )
                    metrics["max_pending"] = max(
                        metrics["max_pending"], app.state.price_budget.pending
                    )
                    metrics["physical"] = app.state.price_budget.physical
                    metrics["pending"] = app.state.price_budget.pending
                    metrics["pool_size"] = engine.pool.size()
                    metrics["overflow"] = engine.pool.overflow()
                    metrics["samples"].append(
                        [
                            time.monotonic(),
                            metrics["transactions"],
                            metrics["queries"],
                            metrics["physical"],
                            len(asyncio.all_tasks()),
                        ]
                    )
                    Path(f"/private/tmp/f10-resource-{port}.json").write_text(
                        json.dumps(metrics)
                    )
                    await asyncio.sleep(0.1)

            task = asyncio.create_task(monitor())
            try:
                yield
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    app.router.lifespan_context = instrumented
    await uvicorn.Server(
        uvicorn.Config(
            app, host="127.0.0.1", port=port, log_level="critical", access_log=False
        )
    ).serve()


async def driver():
    assert os.environ["TIEWTRADE_DATABASE_URL_API"].endswith("/tiewtrade_f10_test")
    admin = await asyncpg.connect(
        host="127.0.0.1",
        port=55432,
        user="postgres",
        password="postgres",
        database="postgres",
    )
    exists = await admin.fetchval("SELECT 1 FROM pg_database WHERE datname=$1", DB)
    if exists:
        raise RuntimeError("Probe DB already exists; choose a new probe name")
    await admin.execute(f"CREATE DATABASE {DB} OWNER tiewtrade_migrator")
    await admin.close()
    for key, value in list(os.environ.items()):
        if key.startswith("TIEWTRADE_DATABASE_URL_"):
            os.environ[key] = value.rsplit("/", 1)[0] + "/" + DB
    os.environ.update(
        TIEWTRADE_REDIS_URL_API="redis://127.0.0.1:56380/7",
        TIEWTRADE_PRICE_ORIGINS="http://localhost:5173",
        TIEWTRADE_COOKIE_SECURE="0",
    )
    os.environ["TIEWTRADE_SEALING_KEY_TOTP_SECRET"] = (
        "1:" + base64.b64encode(b"T" * 32).decode()
    )
    os.environ["TIEWTRADE_SEALING_KEY_VENUE_API_SECRET"] = (
        "1:" + base64.b64encode(b"V" * 32).decode()
    )
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr.decode()
    from tiewtrade.infra.auth import issue, new_token
    from tiewtrade.infra.db import DatabaseRole, create_engine_for, user_session
    from tiewtrade.infra.users import create_user_in

    engine = create_engine_for(DatabaseRole.AUTH)
    users = []
    tokens = []
    for _ in range(35):
        owner = uuid4()
        user_tokens = []
        async with user_session(engine, owner, role=DatabaseRole.AUTH) as session:
            await create_user_in(session, owner)
            for _ in range(3):
                token, hashed = new_token()
                await issue(
                    session,
                    token_hash=hashed,
                    idle_expires_at=datetime.now(UTC) + timedelta(minutes=15),
                    absolute_expires_at=datetime.now(UTC) + timedelta(hours=1),
                )
                user_tokens.append(token)
        users.append(owner)
        tokens.append(user_tokens)
    await engine.dispose()
    redis_delayed = False

    async def proxy(reader, writer):
        upstream_reader, upstream_writer = await asyncio.open_connection(
            "127.0.0.1", 56379
        )

        async def relay(source, target, delayed=False):
            try:
                while data := await source.read(65536):
                    if delayed and redis_delayed:
                        await asyncio.sleep(1)
                    target.write(data)
                    await target.drain()
            finally:
                target.close()

        await asyncio.gather(
            relay(reader, upstream_writer),
            relay(upstream_reader, writer, True),
            return_exceptions=True,
        )

    redis_proxy = await asyncio.start_server(proxy, "127.0.0.1", 56380)
    ports = [58511, 58512]
    procs = [
        subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "--server", str(p)],
            cwd=BACKEND,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for p in ports
    ]
    sockets = []
    drain_tasks = []

    async def drain(ws):
        try:
            async for _ in ws:
                pass
        except Exception:
            pass

    report = {
        "database": DB,
        "transport": "real TCP; three already assigned source addresses",
        "phases": [],
    }

    async def open_ws(port, token, peer="127.0.0.1"):
        return await connect(
            f"ws://127.0.0.1:{port}/market-data/prices/stream",
            origin="http://localhost:5173",
            additional_headers={"Cookie": "tiewtrade_session=" + token},
            local_addr=(peer, 0),
            open_timeout=3,
        )

    async def http_phase(name, n=20):
        measurements = {"name": name, "health_ms": [], "me_ms": []}
        async with httpx.AsyncClient(
            base_url=f"http://127.0.0.1:{ports[0]}",
            cookies={"tiewtrade_session": tokens[0][0]},
            timeout=3,
        ) as client:
            for _ in range(n):
                for path, key in [("/health", "health_ms"), ("/auth/me", "me_ms")]:
                    start = time.monotonic()
                    response = await client.get(path)
                    assert response.status_code == 200, (path, response.status_code)
                    measurements[key].append(
                        round((time.monotonic() - start) * 1000, 3)
                    )
                await asyncio.sleep(0.05)
        report["phases"].append(measurements)

    try:
        async with httpx.AsyncClient() as client:
            for _ in range(100):
                try:
                    if all(
                        [
                            (
                                await client.get(f"http://127.0.0.1:{p}/health")
                            ).status_code
                            == 200
                            for p in ports
                        ]
                    ):
                        break
                except httpx.TransportError:
                    pass
                await asyncio.sleep(0.05)
            else:
                raise RuntimeError("API startup failed")
        # One user, three distinct sessions on two physically separate API processes.
        for p, t in [
            (ports[0], tokens[0][0]),
            (ports[1], tokens[0][1]),
            (ports[0], tokens[0][2]),
        ]:
            ws = await open_ws(p, t)
            await asyncio.wait_for(ws.recv(), 2)
            sockets.append(ws)
            drain_tasks.append(asyncio.create_task(drain(ws)))
        rejected = False
        try:
            fourth = await open_ws(ports[1], tokens[0][0])
            await fourth.close()
        except Exception as exc:
            rejected = type(exc).__name__ == "InvalidStatus"
        assert rejected
        report["cross_process"] = {
            "pids": [p.pid for p in procs],
            "sessions": 3,
            "accepted": 3,
            "fourth_rejected": True,
        }
        await sockets.pop().close()
        await asyncio.sleep(0.2)
        replacement = await open_ws(ports[1], tokens[0][2])
        await asyncio.wait_for(replacement.recv(), 2)
        sockets.append(replacement)
        drain_tasks.append(asyncio.create_task(drain(replacement)))
        report["cross_process"]["cleanup_replacement_accepted"] = True
        # Spread source addresses across three observed TCP peers; no spoofed headers.
        # User 0 holds one socket on process A and two on process B.
        assigned = subprocess.check_output(["ifconfig"], text=True)
        import re

        peers = re.findall(r"\binet ([0-9.]+)", assigned)
        peers = [p for p in peers if p != "127.0.0.1"] + ["127.0.0.1"]
        assert len(peers) >= 3
        accepted = 1
        for idx in range(1, 35):
            for session_token in tokens[idx]:
                if accepted >= 100:
                    break
                if accepted == 80:
                    # Cross the real Redis fixed window; do not reset admission.
                    await asyncio.sleep(61 - (time.time() % 60))
                ws = await open_ws(
                    ports[0],
                    session_token,
                    peer=peers[((accepted - 1) // 27) % len(peers)],
                )
                await asyncio.wait_for(ws.recv(), 2)
                sockets.append(ws)
                drain_tasks.append(asyncio.create_task(drain(ws)))
                accepted += 1
            if accepted >= 100:
                break
        assert accepted == 100
        report["physical_accepted"] = accepted
        publisher = Redis.from_url("redis://127.0.0.1:56379/7")
        published = 0

        async def burst():
            nonlocal published
            while True:
                async with publisher.pipeline(transaction=False) as pipe:
                    for _ in range(100):
                        pipe.publish(
                            "market.prices.changed", "public-test-notification"
                        )
                    await pipe.execute()
                published += 100
                await asyncio.sleep(0.05)

        publisher_task = asyncio.create_task(burst())
        await http_phase("100 sockets + actual Redis invalidation burst", 60)
        publisher_task.cancel()
        await asyncio.gather(publisher_task, return_exceptions=True)
        await publisher.aclose()
        report["published_invalidations"] = published
        metrics = json.loads(
            Path(f"/private/tmp/f10-resource-{ports[0]}.json").read_text()
        )
        assert metrics["max_physical"] == 100 and metrics["max_checked_out"] <= 3
        # Overflow identity has unused user slots; physical guard must reject first.
        rejected = False
        try:
            overflow = await open_ws(ports[0], tokens[34][0], peer=peers[0])
            await overflow.close()
        except Exception as exc:
            rejected = type(exc).__name__ == "InvalidStatus"
        assert rejected
        report["physical_101_rejected"] = True
        # Hold actual PG locks used by lease coordinator. Dedicated realtime pool
        # fills and sockets fail closed, while interactive HTTP uses its own pool.
        lock = await asyncpg.connect(
            host="127.0.0.1",
            port=55432,
            user="postgres",
            password="postgres",
            database=DB,
        )
        tx = lock.transaction()
        await tx.start()
        await lock.execute(
            "LOCK TABLE market_price_connections IN ACCESS EXCLUSIVE MODE"
        )
        await http_phase("PG lease table exclusive lock", 20)
        await tx.rollback()
        await lock.close()
        await asyncio.sleep(1)
        closed = sum(ws.state.name == "CLOSED" for ws in sockets)
        report["closed_after_lock"] = closed
        assert closed > 0
        await http_phase("after fail-closed cleanup", 10)
        # TCP response delay against actual Redis, on an isolated proxy only.
        redis_delayed = True
        await http_phase("actual Redis response delay 1s", 10)
        start = time.monotonic()
        rejected = False
        try:
            blocked = await open_ws(ports[0], tokens[34][0], peer=peers[0])
            await blocked.close()
        except Exception as exc:
            rejected = type(exc).__name__ == "InvalidStatus"
        report["redis_delay_new_ws_rejected"] = rejected
        report["redis_delay_reject_ms"] = round((time.monotonic() - start) * 1000, 3)
        assert rejected and time.monotonic() - start < 1
        redis_delayed = False
        await asyncio.sleep(1.1)
        report["metrics"] = {
            str(p): json.loads(Path(f"/private/tmp/f10-resource-{p}.json").read_text())
            for p in ports
        }
        for data in report["metrics"].values():
            assert data["pool_size"] == 3 and data["max_checked_out"] <= 3
            assert data["max_pending"] <= 16
            reads = data["public_reads"]
            maximum = max(
                (sum(0 <= r - start < 1 for r in reads) for start in reads), default=0
            )
            data["max_public_reads_per_rolling_second"] = maximum
            assert maximum <= 10
        RESULT.write_text(json.dumps(report, indent=2))
        print(
            json.dumps(
                {k: v for k, v in report.items() if k not in ("metrics", "phases")}
            )
        )
    finally:
        await asyncio.gather(*(ws.close() for ws in sockets), return_exceptions=True)
        await asyncio.gather(*drain_tasks, return_exceptions=True)
        redis_proxy.close()
        for proc in procs:
            proc.terminate()
        for proc in procs:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        await redis_proxy.wait_closed()


if __name__ == "__main__":
    asyncio.run(server(int(sys.argv[2])) if sys.argv[1] == "--server" else driver())
