"""Migrator rollout orchestration with an explicit, verified Compose inventory.

External routing, offline image allowlists and keyring distribution remain operator
responsibilities in the approved runbook. Docker and DB observations supplement
those attestations; they cannot discover unmanaged hosts or cron controllers.
"""

import asyncio
import hashlib
import json
from contextlib import suppress
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4
from xml.etree import ElementTree

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.infra.db import DatabaseRole
from tiewtrade.infra.db.errors import InfraError
from tiewtrade.infra.db.session import _assert_role, _begin, _execute
from tiewtrade.infra.indicators.recovery import OwnerStopUnverifiedError, Runner, docker_command


class RolloutRejectedError(InfraError):
    code = "INDICATOR_ROLLOUT_REJECTED"


class Mode(StrEnum):
    LEGACY = "LEGACY"
    PREPARING = "PREPARING"
    PREPARED = "PREPARED"
    PAUSED = "PAUSED"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class Container(StrictModel):
    container_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    image_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    service: Literal["api", "market-data", "indicator-builder"]


class Inventory(StrictModel):
    version: Literal[1]
    project: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,62}$")
    containers: tuple[Container, ...] = Field(min_length=3, max_length=100)
    # Explicit operator attestations, not values inferred from health endpoints.
    external_paths_drained: Literal[True]
    legacy_restart_disabled: Literal[True]
    verification_keyring_verified: Literal[True]
    keyring_config_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")


GATES = frozenset(
    {
        "R2-L",
        "R2-F",
        "R2-G",
        "R2-C1",
        "R2-C2",
        "R2-C3",
        "R2-C4",
        "R2-C5",
        "R2-C6",
        "R2-D1",
        "R2-D2",
        "R2-D3",
        "R2-D4",
        "R2-D5",
        "R2-D6",
        "R2-D7",
        "REGRESSION",
        "READY-API",
    }
)


class Gate(StrictModel):
    name: str
    artifact: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: Literal["PASSED"]


class Evidence(StrictModel):
    version: Literal[1]
    image_ids: tuple[str, ...]
    keyring_config_id: str
    # The owner certifies that these reports implement the named approved gates.
    approved_gate_mapping: Literal[True]
    gates: tuple[Gate, ...]


def load_inventory(path: Path) -> Inventory:
    if path.stat().st_size > 65_536:
        raise RolloutRejectedError("inventory rejected")
    return Inventory.model_validate_json(path.read_bytes())


def verify_evidence(path: Path, inventory: Inventory) -> None:
    if path.stat().st_size > 65_536:
        raise RolloutRejectedError("evidence rejected")
    evidence = Evidence.model_validate_json(path.read_bytes())
    if (
        set(evidence.image_ids) != {c.image_id for c in inventory.containers}
        or evidence.keyring_config_id != inventory.keyring_config_id
        or len(evidence.gates) != len(GATES)
        or {g.name for g in evidence.gates} != GATES
    ):
        raise RolloutRejectedError("evidence rejected")
    root = path.resolve().parent
    for gate in evidence.gates:
        artifact = (root / gate.artifact).resolve()
        if not artifact.is_relative_to(root) or artifact.stat().st_size > 4_194_304:
            raise RolloutRejectedError("evidence rejected")
        raw = artifact.read_bytes()
        if hashlib.sha256(raw).hexdigest() != gate.sha256:
            raise RolloutRejectedError("evidence rejected")
        report = ElementTree.fromstring(raw)
        suites = [report] if report.tag == "testsuite" else list(report.findall("testsuite"))
        if not suites or any(
            int(s.get("tests", "0")) <= 0
            or any(int(s.get(name, "-1")) != 0 for name in ("failures", "errors", "skipped"))
            or s.find(".//failure") is not None
            or s.find(".//error") is not None
            or s.find(".//skipped") is not None
            for s in suites
        ):
            raise RolloutRejectedError("evidence rejected")


_INSPECT = (
    '{"id":{{json .Id}},"image":{{json .Image}},"state":{{json .State}},'
    '"restart":{{json .HostConfig.RestartPolicy.Name}},'
    '"project":{{json (index .Config.Labels "com.docker.compose.project")}},'
    '"service":{{json (index .Config.Labels "com.docker.compose.service")}}}'
)


async def verify_inventory(
    inventory: Inventory, runner: Runner = docker_command
) -> tuple[str, ...]:
    ids = {c.container_id for c in inventory.containers}
    if len(ids) != len(inventory.containers) or {c.service for c in inventory.containers} != {
        "api",
        "market-data",
        "indicator-builder",
    }:
        raise RolloutRejectedError("inventory rejected")
    discovered = await runner(
        (
            "ps",
            "--all",
            "--no-trunc",
            "--filter",
            f"label=com.docker.compose.project={inventory.project}",
            "--format",
            '{{.ID}} {{.Label "com.docker.compose.service"}}',
        )
    )
    relevant: set[str] = set()
    for line in discovered.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1] in {"api", "market-data", "indicator-builder"}:
            relevant.add(parts[0])
    if relevant != ids:
        raise RolloutRejectedError("inventory incomplete")
    observed: list[str] = []
    for item in inventory.containers:
        raw = await runner(("inspect", "--format", _INSPECT, item.container_id))
        record = json.loads(raw)
        state = record["state"]
        if (
            record["id"] != item.container_id
            or record["image"] != item.image_id
            or record["project"] != inventory.project
            or record["service"] != item.service
            or record["restart"] != "no"
            or state["Running"] is not False
            or state["Restarting"] is not False
            or state["Dead"] is not False
            or type(state["Pid"]) is not int
            or state["Pid"] != 0
            or state["Status"] not in ("created", "exited")
        ):
            raise RolloutRejectedError("container not drained")
        if state["Status"] == "exited":
            start, end = (
                datetime.fromisoformat(state["StartedAt"]),
                datetime.fromisoformat(state["FinishedAt"]),
            )
            if start.tzinfo is None or end.tzinfo is None or start.year <= 1970 or end < start:
                raise RolloutRejectedError("container stop unverified")
        observed.append(raw)
    return tuple(observed)


async def verify_capabilities(inventory: Inventory, runner: Runner = docker_command) -> None:
    for image in sorted({c.image_id for c in inventory.containers}):
        # Immutable local image; no shell, credentials, network or application startup.
        probe = "f11-capability-" + uuid4().hex
        try:
            raw = await runner(
                (
                    "run",
                    "--rm",
                    "--name",
                    probe,
                    "--pull=never",
                    "--network=none",
                    "--memory=128m",
                    "--cpus=1",
                    "--pids-limit=32",
                    "--read-only",
                    "--cap-drop=ALL",
                    "--security-opt=no-new-privileges",
                    "--entrypoint=python",
                    image,
                    "-m",
                    "tiewtrade.infra.indicators.capabilities",
                )
            )
        finally:
            # The probe never has a DB credential. On timeout/cancel, kill only
            # this invocation's auxiliary container, not an inventory process.
            # A successful --rm probe is already absent (Docker returns nonzero).
            with suppress(OwnerStopUnverifiedError):
                await asyncio.shield(runner(("rm", "--force", probe)))
        if json.loads(raw) != {
            "cursor_formats": [1, 2],
            "codec_version": 1,
            "protocol_version": 1,
            "source_scope": 1,
            "physical_grace_seconds": 22500,
        }:
            raise RolloutRejectedError("image incompatible")


async def orchestrate(
    engine: AsyncEngine,
    inventory: Inventory,
    expected: Mode,
    epoch: UUID,
    target: Mode,
    *,
    evidence: Path | None = None,
    runner: Runner = docker_command,
) -> dict[str, object]:
    before = await verify_inventory(inventory, runner)
    await verify_capabilities(inventory, runner)
    if target is Mode.PREPARED:
        if evidence is None:
            raise RolloutRejectedError("activation evidence required")
        verify_evidence(evidence, inventory)
    if await verify_inventory(inventory, runner) != before:
        raise RolloutRejectedError("inventory changed")
    async with asyncio.timeout(2):
        async with _begin(engine, cleanup_seconds=2) as connection:
            await _assert_role(connection, DatabaseRole.MIGRATOR)
            await _execute(
                connection,
                """SELECT set_config('lock_timeout','200ms',true),
                set_config('statement_timeout','500ms',true)""",
                None,
            )
            readers: bool = (
                await _execute(
                    connection,
                    """SELECT EXISTS(
                SELECT 1 FROM pg_catalog.pg_stat_activity WHERE datname=current_database()
                  AND pid<>pg_backend_pid() AND usename IN
                    ('tiewtrade_api','tiewtrade_market_data','tiewtrade_indicator_builder'))""",
                    None,
                )
            ).scalar_one()
            if readers:
                raise RolloutRejectedError("database processes not drained")
            current = (
                (
                    await _execute(
                        connection,
                        "SELECT mode,rollout_epoch,source_proof_state "
                        "FROM indicator_rollout_control WHERE id=1",
                        None,
                    )
                )
                .mappings()
                .one()
            )
            # Proof install is the existing relation->guard maintenance protocol.
            # Never reset proof on a stale or replayed command.
            installed = False
            if (
                expected is Mode.LEGACY
                and target is Mode.PREPARING
                and (
                    current["mode"] == expected.value
                    and current["rollout_epoch"] == epoch
                    and current["source_proof_state"] != "READY"
                )
            ):
                await _execute(connection, "SELECT public.activate_indicator_source_proof()", None)
                installed = True
            result: dict[str, object] = (
                await _execute(
                    connection,
                    """SELECT public.transition_indicator_rollout(
                  CAST(:mode AS public.indicator_rollout_mode),:epoch,
                  CAST(:target AS public.indicator_rollout_mode))""",
                    {"mode": expected.value, "epoch": epoch, "target": target.value},
                )
            ).scalar_one()
            if installed and result.get("result") not in ("APPLIED", "ALREADY_APPLIED"):
                raise RolloutRejectedError("proof activation rolled back")
        return result


async def inspect_rollout(engine: AsyncEngine) -> dict[str, object]:
    async with asyncio.timeout(2):
        async with _begin(engine, cleanup_seconds=2) as connection:
            await _assert_role(connection, DatabaseRole.MIGRATOR)
            await _execute(connection, "SET TRANSACTION READ ONLY", None)
            await _execute(connection, "SET LOCAL statement_timeout='500ms'", None)
            row = (
                (
                    await _execute(
                        connection,
                        """SELECT mode,rollout_epoch,active_cursor_format,
                codec_version,protocol_version,source_proof_state,retention_policy,
                last_v2_issue_cutoff,
                last_v2_issue_cutoff IS NULL OR clock_timestamp()>=
                  last_v2_issue_cutoff+interval '6 hours' AS support_window_elapsed
                FROM public.indicator_rollout_control WHERE id=1""",
                        None,
                    )
                )
                .mappings()
                .one()
            )
            return dict(row)


async def retirement_ready(
    engine: AsyncEngine, inventory: Inventory, *, runner: Runner = docker_command
) -> dict[str, object]:
    """Verify final rollback prerequisites; schema removal stays in Alembic."""
    before = await verify_inventory(inventory, runner)
    await verify_capabilities(inventory, runner)
    if await verify_inventory(inventory, runner) != before:
        raise RolloutRejectedError("inventory changed")
    async with asyncio.timeout(2):
        async with _begin(engine, cleanup_seconds=2) as connection:
            await _execute(connection, "SET TRANSACTION READ ONLY", None)
            await _assert_role(connection, DatabaseRole.MIGRATOR)
            await _execute(connection, "SET LOCAL statement_timeout='500ms'", None)
            allowed: bool = (
                await _execute(
                    connection,
                    """SELECT
                c.mode IN ('LEGACY','PAUSED') AND s.state='IDLE'
                AND (c.last_v2_issue_cutoff IS NULL OR clock_timestamp()>=
                  c.last_v2_issue_cutoff+interval '6 hours')
                AND NOT EXISTS(SELECT 1 FROM public.indicator_build_jobs WHERE status='RUNNING')
                AND NOT EXISTS(SELECT 1 FROM pg_catalog.pg_stat_activity
                  WHERE datname=current_database() AND pid<>pg_backend_pid()
                  AND usename IN
                    ('tiewtrade_api','tiewtrade_market_data','tiewtrade_indicator_builder'))
                AND NOT EXISTS(SELECT 1 FROM pg_catalog.pg_locks WHERE locktype='advisory'
                  AND classid=711 AND objid=1 AND objsubid=2 AND granted
                  AND database=(SELECT oid FROM pg_catalog.pg_database
                    WHERE datname=current_database()))
                FROM public.indicator_rollout_control c CROSS JOIN public.indicator_build_slot s
                WHERE c.id=1 AND s.id=1""",
                    None,
                )
            ).scalar_one()
            if not allowed:
                raise RolloutRejectedError("retirement not ready")
            return {"result": "RETIREMENT_READY"}
