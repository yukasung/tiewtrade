"""Explicit host Docker/isolated PG gate for the real rollout CLI.

Build tiewtrade-f11-rollout-test:latest first. Created test containers only;
application containers, routing and the application database are never changed.
"""

import asyncio
import json
import sys
from pathlib import Path
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.indicators.test_claims import prepared as prepared
from tests.infra.indicators.test_rollout import control
from tests.infra.indicators.test_source import active as active
from tests.services.indicator_builder.profile_container_recovery import docker


async def cli(*args: str) -> tuple[int, str]:
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "tiewtrade.services.indicator_builder.main",
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        output, error = await asyncio.wait_for(process.communicate(), 30)
        assert not error
        assert process.returncode is not None
        return process.returncode, output.decode()
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()


async def test_real_inventory_image_probe_cli_pause_and_replay(
    prepared: None, migrator_engine: AsyncEngine, tmp_path: Path
) -> None:
    project = "f11-rollout-" + uuid4().hex
    image = await docker(
        "image", "inspect", "--format", "{{.Id}}", "tiewtrade-f11-rollout-test:latest"
    )
    containers = []
    try:
        for service in ("api", "market-data", "indicator-builder"):
            ident = await docker(
                "create",
                "--restart=no",
                "--network=none",
                "--label",
                f"com.docker.compose.project={project}",
                "--label",
                f"com.docker.compose.service={service}",
                image,
                "python",
                "-m",
                "tiewtrade.infra.indicators.capabilities",
            )
            containers.append({"container_id": ident, "image_id": image, "service": service})
        data = {
            "version": 1,
            "project": project,
            "containers": containers,
            "external_paths_drained": True,
            "legacy_restart_disabled": True,
            "verification_keyring_verified": True,
            "keyring_config_id": "isolated-test",
        }
        path = tmp_path / "inventory.json"
        path.write_text(json.dumps(data))
        state = await control(migrator_engine)
        args = (
            "rollout",
            "--inventory",
            str(path),
            "--expected-mode",
            "PREPARING",
            "--expected-epoch",
            str(state["rollout_epoch"]),
            "--target",
            "PAUSED",
        )
        code, output = await cli(*args)
        assert code == 0, output
        first = json.loads(output)
        assert first["result"] == "APPLIED"
        code, output = await cli(*args)
        assert code == 0 and json.loads(output)["result"] == "ALREADY_APPLIED"
        assert json.loads(output)["epoch"] == first["epoch"]
        # Offline legacy replicas omitted from inventory still block transitions.
        old = await docker(
            "create",
            "--restart=no",
            "--network=none",
            "--label",
            f"com.docker.compose.project={project}",
            "--label",
            "com.docker.compose.service=api",
            "tiewtrade-api:latest",
            "python",
            "-c",
            "pass",
        )
        containers.append({"container_id": old, "image_id": "unused", "service": "api"})
        code, output = await cli(*args)
        assert code == 13 and "OPERATIONAL_FAILURE" in output
    finally:
        for item in containers:
            await docker("rm", item["container_id"])
