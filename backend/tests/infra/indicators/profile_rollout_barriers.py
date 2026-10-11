"""Explicit isolated-Docker gate: reader barriers and a lost committed CLI response."""

import asyncio
import json
import os
from contextlib import suppress
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.util import load_python_file
from sqlalchemy import Connection, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.indicators.test_claims import prepared as prepared
from tests.infra.indicators.test_rollout import Docker, control, inventory, transition
from tests.infra.indicators.test_rollout import reset_transition_history as reset_transition_history
from tests.infra.indicators.test_source import active as active
from tests.services.indicator_builder.profile_container_recovery import docker
from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.infra.db.session import market_data_session
from tiewtrade.infra.indicators.recovery import OwnerStopUnverifiedError
from tiewtrade.infra.indicators.rollout import Inventory, Mode, RolloutRejectedError, orchestrate
from tiewtrade.infra.indicators.session import indicator_source_session
from tiewtrade.infra.market_data.claims import cleanup


@pytest.fixture(autouse=True)
def isolated_database() -> None:
    assert "127.0.0.1:55433/" in os.environ["TIEWTRADE_DATABASE_URL_MIGRATOR"]


async def test_d3_offline_legacy_f09_inventory_cannot_install_proof(
    prepared: None, migrator_engine: AsyncEngine
) -> None:
    project = "f11-source-inventory-" + uuid4().hex
    containers: list[dict[str, str]] = []
    try:
        for service in ("api", "market-data", "indicator-builder"):
            tag = (
                "tiewtrade-api:latest"
                if service == "market-data"
                else ("tiewtrade-f11-mixed-test:latest")
            )
            image = await docker("image", "inspect", "--format", "{{.Id}}", tag)
            ident = await docker(
                "create",
                "--network=none",
                "--restart=no",
                "--label",
                f"com.docker.compose.project={project}",
                "--label",
                f"com.docker.compose.service={service}",
                image,
                "python",
                "-c",
                "pass",
            )
            containers.append({"container_id": ident, "image_id": image, "service": service})
        data = Inventory.model_validate_json(
            json.dumps(
                {
                    "version": 1,
                    "project": project,
                    "containers": containers,
                    "external_paths_drained": True,
                    "legacy_restart_disabled": True,
                    "verification_keyring_verified": True,
                    "keyring_config_id": "isolated-test",
                }
            )
        )
        async with migrator_engine.begin() as c:
            await c.execute(
                text(
                    "UPDATE indicator_rollout_control SET mode='LEGACY',"
                    "source_proof_state='PENDING'"
                )
            )
        before = await control(migrator_engine)
        with pytest.raises(OwnerStopUnverifiedError):
            await orchestrate(
                migrator_engine, data, Mode.LEGACY, before["rollout_epoch"], Mode.PREPARING
            )
        after = await control(migrator_engine)
        assert after["mode"] == "LEGACY" and after["source_proof_state"] == "PENDING"
        assert after["rollout_epoch"] == before["rollout_epoch"]
    finally:
        for item in containers:
            await docker("rm", "--force", item["container_id"])


@pytest.mark.parametrize("offset", [1, 0, -1])
async def test_d5_actual_downgrade_db_clock_support_boundary(
    prepared: None, migrator_engine: AsyncEngine, offset: int
) -> None:
    migration = load_python_file(
        Path(__file__).resolve().parents[3] / "migrations/versions", "0023_indicator_rollout.py"
    )

    def downgrade(connection: Connection) -> None:
        with Operations.context(MigrationContext.configure(connection)):
            migration.downgrade()

    async with migrator_engine.connect() as c:
        transaction = await c.begin()
        try:
            await c.execute(
                text(
                    "UPDATE indicator_rollout_control SET mode='PAUSED',"
                    "last_v2_issue_cutoff=clock_timestamp()-interval '6 hours'+:delta"
                ),
                {"delta": timedelta(seconds=offset)},
            )
            if offset > 0:
                with pytest.raises(DBAPIError, match="INDICATOR_DOWNGRADE_NOT_DRAINED"):
                    await c.run_sync(downgrade)
            else:
                # At the boundary the DB clock continues forward; there is no
                # mocked clock or claim of freezing PostgreSQL at one microsecond.
                await c.run_sync(downgrade)
                assert (
                    await c.execute(
                        text(
                            "SELECT NOT EXISTS(SELECT 1 FROM pg_proc "
                            "WHERE proname='transition_indicator_rollout')"
                        )
                    )
                ).scalar_one()
        finally:
            await transaction.rollback()  # Restore real schema after either outcome.


@pytest.mark.parametrize("reader", ["source", "cleanup"])
async def test_d4_actual_source_snapshot_or_cleanup_transaction_blocks_flip(
    prepared: None, migrator_engine: AsyncEngine, reader: str
) -> None:
    role = DatabaseRole.INDICATOR_BUILDER if reader == "source" else DatabaseRole.MARKET_DATA
    runtime = create_engine_for(role)
    state = await control(migrator_engine)

    async def reject() -> None:
        with pytest.raises(RolloutRejectedError):
            await orchestrate(
                migrator_engine,
                inventory(),
                Mode.PREPARING,
                state["rollout_epoch"],
                Mode.PAUSED,
                runner=Docker(),
            )
        assert (await control(migrator_engine))["rollout_epoch"] == state["rollout_epoch"]

    try:
        if reader == "source":
            async with indicator_source_session(runtime) as snapshot:
                await snapshot.execute("SELECT count(*) FROM market_candles")
                await reject()
        else:
            async with market_data_session(runtime) as session:
                assert await cleanup(session) == 0
                await reject()
    finally:
        await runtime.dispose()
    assert (
        await orchestrate(
            migrator_engine,
            inventory(),
            Mode.PREPARING,
            state["rollout_epoch"],
            Mode.PAUSED,
            runner=Docker(),
        )
    )["result"] == "APPLIED"


async def test_d6_committed_transition_lost_response_then_verified_exact_replay(
    prepared: None, migrator_engine: AsyncEngine
) -> None:
    assert "127.0.0.1:55433/" in os.environ["TIEWTRADE_DATABASE_URL_MIGRATOR"]
    state = await control(migrator_engine)
    marker = "f11-ambiguous-" + uuid4().hex
    # The real DB commits before the client is killed. Its response is discarded,
    # so the operator's only evidence of success is a fresh DB status observation.
    sql = f"""SET application_name='{marker}'; BEGIN;
      SELECT public.transition_indicator_rollout('PREPARING','{state["rollout_epoch"]}','PAUSED');
      COMMIT; SELECT pg_sleep(10);"""
    process = await asyncio.create_subprocess_exec(
        "docker",
        "exec",
        "tiewtrade-f11-test-postgres",
        "psql",
        "-U",
        "tiewtrade_migrator",
        "-d",
        "tiewtrade",
        "-v",
        "ON_ERROR_STOP=1",
        "-c",
        sql,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        async with asyncio.timeout(5):
            while True:
                observed = await control(migrator_engine)
                if observed["mode"] == "PAUSED":
                    break
                assert process.returncode is None
                await asyncio.sleep(0.02)
        process.kill()
        await asyncio.wait_for(process.wait(), 2)
        result = await transition(
            migrator_engine, Mode.PREPARING, state["rollout_epoch"], Mode.PAUSED
        )
        assert result["result"] == "ALREADY_APPLIED"
        assert result["epoch"] == str(observed["rollout_epoch"])
        assert (await control(migrator_engine))["rollout_epoch"] == observed["rollout_epoch"]
    finally:
        if process.returncode is None:
            with suppress(ProcessLookupError):
                process.kill()
            await asyncio.wait_for(process.wait(), 2)
        # Kill only this test's tagged backend if Docker exec outlived its client.
        async with migrator_engine.begin() as c:
            await c.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname=current_database() AND application_name=:marker "
                    "AND usename='tiewtrade_migrator' AND pid<>pg_backend_pid()"
                ),
                {"marker": marker},
            )
