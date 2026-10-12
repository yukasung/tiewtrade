"""D5/D7 isolated Compose rehearsal. No live venue, capacity bundle or long wait."""

import asyncio
import base64
import json
import os
import sys
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.conftest import TEST_SEALING_KEY, TEST_VENUE_KEY
from tests.infra.indicators.test_claims import builder_engine as builder_engine
from tests.infra.indicators.test_claims import prepared as prepared
from tests.infra.indicators.test_rollout import control
from tests.infra.indicators.test_source import active as active
from tests.services.indicator_builder.profile_container_recovery import docker
from tests.services.indicator_builder.profile_mixed_replicas import (
    PATH,
    QUERY,
    Replicas,
    authenticate,
    reset_admission,
)
from tests.services.indicator_builder.profile_mixed_replicas import (
    isolated_services as isolated_services,
)
from tests.services.indicator_builder.profile_mixed_replicas import published as published
from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.infra.indicators.recovery import OwnerStopUnverifiedError
from tiewtrade.infra.indicators.rollout import (
    Inventory,
    Mode,
    RolloutRejectedError,
    inspect_rollout,
    orchestrate,
    retirement_ready,
    verify_capabilities,
    verify_inventory,
)

CLEANUP = """
import asyncio
from tiewtrade.infra.db import DatabaseRole,create_engine_for
from tiewtrade.infra.db.session import market_data_session
from tiewtrade.infra.market_data.claims import cleanup
async def run():
    engine=create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        async with market_data_session(engine) as s:
            await cleanup(s)
    finally:
        await engine.dispose()
asyncio.run(run())
"""


async def command(*args: str) -> str:
    process = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    try:
        output, error = await asyncio.wait_for(process.communicate(), 55)
    except BaseException:
        if process.returncode is None:
            process.kill()
        await process.wait()
        raise
    assert process.returncode == 0, error.decode()
    return output.decode().strip()


async def migrate(target: str, direction: str) -> None:
    # Config API avoids Windows locale decoding of Thai alembic.ini comments.
    await command(
        sys.executable,
        "-c",
        "from alembic import command; from alembic.config import Config; "
        "c=Config(); c.set_main_option('script_location','migrations'); "
        f"command.{direction}(c,'{target}')",
    )


async def test_compose_stop_drain_upgrade_pause_and_full_retirement(
    published: dict[str, Any],
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    tmp_path: Path,
) -> None:
    assert published["status"] == "READY"
    project = "f11-compose-" + uuid4().hex
    manifest = tmp_path / "compose.json"
    compatibility, current, legacy = [
        await docker("image", "inspect", "--format", "{{.Id}}", tag)
        for tag in (
            "tiewtrade-f11-rollout-test:latest",
            "tiewtrade-f11-mixed-test:latest",
            "tiewtrade-api:latest",
        )
    ]
    pair = Replicas(project, (compatibility, current))
    trace: list[dict[str, Any]] = []

    def write(image: str, *, retired: bool = False) -> None:
        env = {
            "TIEWTRADE_DATABASE_URL_API": "postgresql+asyncpg://tiewtrade_api:dev_api@tiewtrade-f11-test-postgres:5432/tiewtrade",
            "TIEWTRADE_DATABASE_URL_AUTH": "postgresql+asyncpg://tiewtrade_auth:dev_auth@tiewtrade-f11-test-postgres:5432/tiewtrade",
            "TIEWTRADE_REDIS_URL_API": "redis://tiewtrade-f11-test-redis:6379/0",
            "TIEWTRADE_SEALING_KEY_TOTP_SECRET": TEST_SEALING_KEY,
            "TIEWTRADE_SEALING_KEY_VENUE_API_SECRET": TEST_VENUE_KEY,
            "TIEWTRADE_PRICE_ORIGINS": "http://localhost:5173",
            "TIEWTRADE_SIGNUP_OPEN": "1",
            "TIEWTRADE_COOKIE_SECURE": "0",
        }
        if not retired:
            env["TIEWTRADE_SEALING_KEY_INDICATOR_CURSOR"] = (
                "1:" + base64.b64encode(b"I" * 32).decode()
            )
        common = {
            "image": image,
            "pull_policy": "never",
            "restart": "no",
            "networks": ["test"],
            "mem_limit": "512m",
            "cpus": 1,
            "stop_grace_period": "5s",
        }
        services = {
            "api": common
            | {
                "environment": env,
                "ports": ["127.0.0.1::8000"],
                "command": [
                    "uvicorn",
                    "tiewtrade.services.api.app:app",
                    "--host",
                    "0.0.0.0",
                    "--port",
                    "8000",
                    "--no-access-log",
                ],
                "labels": {
                    "f11.keyring_config_id": "retired" if retired else "isolated-keyring-v1"
                },
            },
            "market-data": common
            | {
                "environment": {
                    "TIEWTRADE_DATABASE_URL_MARKET_DATA": "postgresql+asyncpg://tiewtrade_market_data:dev_market_data@tiewtrade-f11-test-postgres:5432/tiewtrade"
                },
                "command": ["python", "-c", CLEANUP],
            },
            "indicator-builder": common
            | {
                "environment": {
                    "TIEWTRADE_DATABASE_URL_INDICATOR_BUILDER": "postgresql+asyncpg://tiewtrade_indicator_builder:dev_indicator_builder@tiewtrade-f11-test-postgres:5432/tiewtrade"
                },
                "command": ["python", "-m", "tiewtrade.services.indicator_builder.main", "gc"],
            },
        }
        manifest.write_text(
            json.dumps(
                {
                    "services": services,
                    "networks": {"test": {"external": True, "name": "tiewtrade-f11-test-net"}},
                }
            ),
            encoding="utf-8",
        )

    async def compose(*args: str) -> str:
        return await command("docker", "compose", "-p", project, "-f", str(manifest), *args)

    async def connect() -> None:
        ids = (await compose("ps", "-q", "api")).splitlines()
        assert len(ids) == 2
        for index, ident in enumerate(ids):
            port = (await docker("port", ident, "8000/tcp")).rsplit(":", 1)[1]
            if len(pair.clients) <= index:
                pair.clients.append(httpx.AsyncClient(timeout=35))
            pair.clients[index].base_url = httpx.URL("http://127.0.0.1:" + port)
            await pair.ready(pair.clients[index])
        pair.containers = ids

    async def sidecars(*services: str) -> None:
        for service in services:
            ident = await compose("ps", "--all", "-q", service)
            assert ident
            assert await docker("wait", ident) == "0"
            trace.append({"step": "sidecar_completed", "service": service})

    async def inventory() -> Inventory:
        records = []
        for service in ("api", "market-data", "indicator-builder"):
            for ident in (await compose("ps", "--all", "-q", service)).splitlines():
                image = await docker("inspect", "--format", "{{.Image}}", ident)
                records.append({"container_id": ident, "image_id": image, "service": service})
        return Inventory.model_validate_json(
            json.dumps(
                {
                    "version": 1,
                    "project": project,
                    "containers": records,
                    "external_paths_drained": True,
                    "legacy_restart_disabled": True,
                    "verification_keyring_verified": True,
                    "keyring_config_id": "isolated-keyring-v1",
                }
            )
        )

    async def drained() -> Inventory:
        await compose("stop", "--timeout", "5")
        await builder_engine.dispose()
        data = await inventory()
        await verify_inventory(data)
        async with migrator_engine.connect() as c:
            assert (
                await c.execute(
                    text(
                        "SELECT count(*) FROM pg_stat_activity WHERE "
                        "datname=current_database() AND usename IN "
                        "('tiewtrade_api','tiewtrade_market_data','tiewtrade_indicator_builder')"
                    )
                )
            ).scalar_one() == 0
            assert (
                await c.execute(text("SELECT state FROM indicator_build_slot"))
            ).scalar_one() == "IDLE"
        trace.append({"step": "drained", "inventory": data.model_dump(mode="json")})
        return data

    write(compatibility)
    try:
        await reset_admission()
        async with migrator_engine.begin() as c:
            await c.execute(text("DELETE FROM auth_throttle"))
            await c.execute(text("SELECT begin_indicator_source_write()"))
            await c.execute(
                text("""INSERT INTO market_candles
              (source,base,quote,timeframe,open_at,end_at,open,high,low,close,volume,
               finality,observed_at,fetch_started_at,last_checked_at,ingestion_generation)
              SELECT 'primary_spot','DOGE','USDT','1m',moment,moment+interval '1 minute',
                100,102,99,101,1,'CLOSED',clock_timestamp(),clock_timestamp(),clock_timestamp(),1
              FROM (SELECT date_trunc('minute',clock_timestamp())-
                interval '365 days 3 hours' AS moment) fixture""")
            )
        await compose("up", "-d", "--scale", "api=2")
        await connect()
        await sidecars("market-data", "indicator-builder")
        async with migrator_engine.connect() as c:
            assert (
                await c.execute(
                    text("SELECT count(*) FROM market_candles WHERE base='DOGE' AND timeframe='1m'")
                )
            ).scalar_one() == 1
        await authenticate(pair)
        response = await pair.clients[0].get(PATH, params=QUERY)
        assert response.status_code == 200
        token = response.json()["next_cursor"]
        expected = await pair.clients[1].get(PATH, params={"cursor": token})
        assert expected.status_code == 200
        await drained()
        await compose("start", "api")
        await connect()
        old_apis = tuple(pair.containers)
        # S5 compatible rolling update: create a replacement before stopping each old API.
        # Earlier/later drain windows still have downtime; no availability claim is made.
        write(current)
        for old_api in old_apis:
            await compose("up", "-d", "--no-recreate", "--scale", "api=3", "api")
            ids = (await compose("ps", "-q", "api")).splitlines()
            images = {
                ident: await docker("inspect", "--format", "{{.Image}}", ident) for ident in ids
            }
            assert compatibility in images.values() and current in images.values()
            replacement = next(ident for ident in ids if images[ident] == current)
            port = (await docker("port", replacement, "8000/tcp")).rsplit(":", 1)[1]
            async with httpx.AsyncClient(base_url="http://127.0.0.1:" + port, timeout=35) as client:
                await pair.ready(client)
                client.cookies.update(dict(pair.clients[0].cookies))
                await reset_admission()
                page = await client.get(PATH, params={"cursor": token})
                assert page.status_code == 200
                assert page.json()["rows"] == expected.json()["rows"]
                assert page.json()["next_cursor"] == expected.json()["next_cursor"]
            trace.append(
                {
                    "step": "mixed_rolling",
                    "images": images,
                    "cursor_key_configuration": "isolated-keyring-v1",
                }
            )
            await docker("stop", "--time", "5", old_api)
            assert await docker("inspect", "--format", "{{.State.Pid}}", old_api) == "0"
            await docker("rm", old_api)
        await compose("up", "-d", "--scale", "api=2")
        await connect()
        await sidecars("market-data", "indicator-builder")
        await reset_admission()
        for client in pair.clients:
            response = await client.get(PATH, params={"cursor": token})
            assert response.status_code == 200
            for key in ("rows", "next_cursor", "as_of", "dataset_revision"):
                assert response.json()[key] == expected.json()[key]
        data = await drained()
        await verify_capabilities(data)
        omitted = data.model_copy(update={"containers": data.containers[1:]})
        with pytest.raises(RolloutRejectedError):
            await verify_inventory(omitted)
        # Created/offline legacy paths must not be silently left out of inventory.
        old = await docker(
            "create",
            "--label",
            f"com.docker.compose.project={project}",
            "--label",
            "com.docker.compose.service=market-data",
            "--restart=no",
            legacy,
            "python",
            "-c",
            "pass",
        )
        try:
            with pytest.raises(RolloutRejectedError):
                await verify_inventory(data)
            extra = json.loads(data.model_dump_json())
            extra["containers"].append(
                {"container_id": old, "image_id": legacy, "service": "market-data"}
            )
            full = Inventory.model_validate_json(json.dumps(extra))
            await verify_inventory(full)
            with pytest.raises((RolloutRejectedError, OwnerStopUnverifiedError)):
                await verify_capabilities(full)
        finally:
            await docker("rm", old)
        before = await inspect_rollout(migrator_engine)
        paused = await orchestrate(
            migrator_engine, data, Mode.PREPARED, cast(UUID, before["rollout_epoch"]), Mode.PAUSED
        )
        assert paused["result"] == "APPLIED"
        trace.append({"step": "paused", "state": paused})
        # Actual inventory + operator inspection on a committed partial-grant fault.
        inspected = await inspect_rollout(migrator_engine)
        async with migrator_engine.begin() as c:
            await c.execute(text("REVOKE SELECT ON indicator_ready_generations FROM tiewtrade_api"))
        try:
            rejected = await orchestrate(
                migrator_engine,
                data,
                Mode.PAUSED,
                cast(UUID, inspected["rollout_epoch"]),
                Mode.PREPARING,
            )
            assert rejected["result"] == "POLICY_UNSUPPORTED"
            assert await inspect_rollout(migrator_engine) == inspected
        finally:
            async with migrator_engine.begin() as c:
                await c.execute(
                    text("GRANT SELECT ON indicator_ready_generations TO tiewtrade_api")
                )
        replay = await orchestrate(
            migrator_engine, data, Mode.PREPARED, cast(UUID, before["rollout_epoch"]), Mode.PAUSED
        )
        assert replay["result"] == "ALREADY_APPLIED" and replay["epoch"] == paused["epoch"]
        trace.append(
            {
                "step": "partial_grant_inspected",
                "result": rejected["result"],
                "replay": replay["result"],
            }
        )
        with pytest.raises(RolloutRejectedError):
            await retirement_ready(migrator_engine, data)
        with pytest.raises(AssertionError, match="INDICATOR_DOWNGRADE_NOT_DRAINED"):
            await migrate("0014", "downgrade")
        assert (await control(migrator_engine))["last_v2_issue_cutoff"] is not None
        await compose("start", "api")
        await connect()
        await reset_admission()
        for client in pair.clients:
            assert (await client.get(PATH, params=QUERY)).status_code == 503
            assert (await client.get(PATH, params={"cursor": token})).status_code == 409
        data = await drained()
        # DB-clock support-window fixture; no real six-hour sleep or production mutation.
        async with migrator_engine.begin() as c:
            await c.execute(
                text(
                    "UPDATE indicator_rollout_control SET "
                    "last_v2_issue_cutoff=clock_timestamp()-interval '6 hours 1 second'"
                )
            )
        reader = create_engine_for(DatabaseRole.API)
        try:
            async with reader.connect() as c:
                await c.execute(text("SELECT mode FROM indicator_rollout_control"))
                with pytest.raises(RolloutRejectedError):
                    await retirement_ready(migrator_engine, data)
                with pytest.raises(AssertionError, match="INDICATOR_DOWNGRADE_NOT_DRAINED"):
                    await migrate("0014", "downgrade")
        finally:
            await reader.dispose()
        assert (await retirement_ready(migrator_engine, data))["result"] == "RETIREMENT_READY"
        async with migrator_engine.connect() as c:
            candles: int = (
                await c.execute(text("SELECT count(*) FROM market_candles"))
            ).scalar_one()
        await migrate("0014", "downgrade")
        async with migrator_engine.connect() as c:
            remaining: str | None = (
                await c.execute(text("SELECT to_regclass('indicator_rollout_control')"))
            ).scalar_one()
            assert remaining is None
            retained: int = (
                await c.execute(text("SELECT count(*) FROM market_candles"))
            ).scalar_one()
            assert retained == candles
        # Only after support/drain/schema retirement replace API and cleanup with legacy.
        write(legacy, retired=True)
        await compose("up", "-d", "--scale", "api=2", "api", "market-data")
        await connect()
        await sidecars("market-data")
        async with migrator_engine.connect() as c:
            assert (
                await c.execute(
                    text("SELECT count(*) FROM market_candles WHERE base='DOGE' AND timeframe='1m'")
                )
            ).scalar_one() == 0
        for client in pair.clients:
            # Approved D1 pre-F11 binary rejects unclassified routes at middleware.
            assert (await client.get(PATH, params=QUERY)).status_code == 403
        for ident in pair.containers:
            assert (
                await docker(
                    "inspect", "--format", '{{index .Config.Labels "f11.keyring_config_id"}}', ident
                )
                == "retired"
            )
        trace.append(
            {
                "step": "retired",
                "schema": "0014",
                "legacy_api": 403,
                "cursor_key_configuration": "retired",
                "support_clock": "DB cutoff aged by fixture",
            }
        )
        output = os.environ.get("TIEWTRADE_D57_EVIDENCE_PATH")
        if output:
            Path(output).write_text(json.dumps(trace, default=str, indent=2), encoding="utf-8")
    finally:
        for client in pair.clients:
            await client.aclose()
        await compose("down", "--remove-orphans", "--timeout", "5")
        await builder_engine.dispose()
        await migrate("head", "upgrade")
        # Restore the source fixture's active-proof contract before its teardown.
        await migrator_engine.dispose()
        async with migrator_engine.begin() as c:
            await c.execute(text("SELECT activate_indicator_source_proof()"))
