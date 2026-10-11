"""Rollout graph, replay, drain, privileges and inventory/evidence fail closed.

Synthetic READY metadata tests the transition predicate only. It is not capacity
evidence and cannot be used as the activation evidence bundle.
"""

import asyncio
import hashlib
import json
from datetime import timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
import pytest_asyncio
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.util import load_python_file
from sqlalchemy import Connection, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.indicators.test_claims import prepared as prepared
from tests.infra.indicators.test_source import active as active
from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.infra.indicators.rollout import (
    GATES,
    Inventory,
    Mode,
    RolloutRejectedError,
    inspect_rollout,
    orchestrate,
    retirement_ready,
    verify_capabilities,
    verify_evidence,
    verify_inventory,
)


@pytest_asyncio.fixture(autouse=True)
async def reset_transition_history(migrator_engine: AsyncEngine) -> Any:
    yield
    async with migrator_engine.begin() as c:
        await c.execute(
            text("""UPDATE indicator_rollout_control SET transition_from_mode=NULL,
          transition_from_epoch=NULL,transition_target=NULL,last_v2_issue_cutoff=NULL,
          active_cursor_format=1 WHERE id=1""")
        )


async def control(engine: AsyncEngine) -> dict[str, Any]:
    async with engine.connect() as c:
        return dict(
            (await c.execute(text("SELECT * FROM indicator_rollout_control"))).mappings().one()
        )


async def transition(engine: AsyncEngine, mode: Mode, epoch: UUID, target: Mode) -> dict[str, Any]:
    async with engine.begin() as c:
        return dict(
            (
                await c.execute(
                    text("""SELECT transition_indicator_rollout(
          CAST(:mode AS indicator_rollout_mode),:epoch,CAST(:target AS indicator_rollout_mode))"""),
                    {"mode": mode.value, "epoch": epoch, "target": target.value},
                )
            ).scalar_one()
        )


async def synthetic_heads(engine: AsyncEngine) -> None:
    async with engine.begin() as c:
        await c.execute(
            text("""INSERT INTO indicator_build_jobs
          (source,base,quote,timeframe,formula_version,desired_start,desired_end,
           first_eligible_at,availability_deadline,generation_sequence)
          SELECT 'primary_spot',b,'USDT',t,'indicators-v1',clock_timestamp()-interval '1 day',
            clock_timestamp()-interval '1 hour',clock_timestamp(),
            clock_timestamp()+interval '600s',1
          FROM unnest(ARRAY['BTC','ETH','DOGE','SOL','XRP']) b
          CROSS JOIN unnest(ARRAY['1m','5m','15m','1h','4h','1d']) t""")
        )
        await c.execute(
            text("""INSERT INTO indicator_generations
          (id,job_id,source,base,quote,timeframe,formula_version,calculation_start,calculation_end,
           as_of,source_epoch,source_fence,dataset_revision,checkpoint_count,codec_version,
           build_rollout_epoch,candidate_sequence,claim_token,status,expires_at,prepared_at)
          SELECT gen_random_uuid(),j.id,j.source,j.base,j.quote,j.timeframe,j.formula_version,
            j.desired_start,j.desired_end,now(),s.epoch,s.revision,repeat('a',64),2,1,
            c.rollout_epoch,1,gen_random_uuid(),'READY',now()+interval '6 hours 10 minutes',now()
          FROM indicator_build_jobs j CROSS JOIN indicator_source_guard s
            CROSS JOIN indicator_rollout_control c""")
        )
        await c.execute(
            text("""INSERT INTO indicator_checkpoints SELECT id,calculation_start,'{}'::jsonb
          FROM indicator_generations UNION ALL SELECT id,calculation_end,'{}'::jsonb
          FROM indicator_generations""")
        )
        await c.execute(
            text("""INSERT INTO indicator_heads SELECT source,base,quote,timeframe,
          formula_version,id FROM indicator_generations""")
        )


async def test_graph_replay_pause_cutoff_and_reenable(
    prepared: None, migrator_engine: AsyncEngine
) -> None:
    await synthetic_heads(migrator_engine)
    initial = await control(migrator_engine)
    args = (migrator_engine, Mode.PREPARING, initial["rollout_epoch"], Mode.PREPARED)
    first = await transition(*args)
    assert first["result"] == "APPLIED" and first["epoch"] != str(initial["rollout_epoch"])
    assert (await transition(*args))["result"] == "ALREADY_APPLIED"
    activated = await control(migrator_engine)
    assert activated["active_cursor_format"] == 2
    paused = await transition(
        migrator_engine, Mode.PREPARED, activated["rollout_epoch"], Mode.PAUSED
    )
    assert paused["result"] == "APPLIED" and paused["cutoff"] is not None
    pause_state = await control(migrator_engine)
    replay = await transition(
        migrator_engine, Mode.PREPARED, activated["rollout_epoch"], Mode.PAUSED
    )
    assert replay["result"] == "ALREADY_APPLIED" and replay["cutoff"] == paused["cutoff"]
    assert (
        await transition(migrator_engine, Mode.PAUSED, pause_state["rollout_epoch"], Mode.PREPARED)
    )["result"] == "REJECTED"
    assert (
        await transition(migrator_engine, Mode.PAUSED, pause_state["rollout_epoch"], Mode.LEGACY)
    )["result"] == "REJECTED"
    assert (await transition(*args))["result"] == "STALE"
    assert (
        await transition(migrator_engine, Mode.PAUSED, pause_state["rollout_epoch"], Mode.PREPARING)
    )["result"] == "APPLIED"
    prepared_again = await control(migrator_engine)
    assert prepared_again["rollout_epoch"] != pause_state["rollout_epoch"]
    assert prepared_again["last_v2_issue_cutoff"] == pause_state["last_v2_issue_cutoff"]
    paused_again = await transition(
        migrator_engine, Mode.PREPARING, prepared_again["rollout_epoch"], Mode.PAUSED
    )
    assert paused_again["cutoff"] == paused["cutoff"]
    async with migrator_engine.connect() as c:
        assert (
            await c.execute(text("SELECT count(*) FROM indicator_generations WHERE status='READY'"))
        ).scalar_one() == 30


@pytest.mark.parametrize(
    "fault", ["missing", "age", "floor", "epoch", "checkpoint", "numeric", "codec", "policy"]
)
async def test_activation_requires_all_fresh_valid_heads(
    prepared: None, migrator_engine: AsyncEngine, fault: str
) -> None:
    await synthetic_heads(migrator_engine)
    async with migrator_engine.begin() as c:
        await c.execute(
            text(
                {
                    "missing": "DELETE FROM indicator_heads WHERE base='BTC'",
                    "age": "UPDATE indicator_generations SET as_of=as_of-interval '601s',"
                    "expires_at=expires_at-interval '601s'",
                    "floor": "UPDATE indicator_source_guard SET revision=revision+1,"
                    "journal_floor=revision+1",
                    "epoch": "UPDATE indicator_source_guard SET epoch=gen_random_uuid()",
                    "checkpoint": "DELETE FROM indicator_checkpoints WHERE generation_id="
                    "(SELECT id FROM indicator_generations LIMIT 1)",
                    "numeric": "UPDATE indicator_build_jobs SET failed_calculation_key='{}',"
                    "generation_sequence=2",
                    "codec": "UPDATE indicator_generations SET codec_version=2",
                    "policy": "UPDATE indicator_rollout_control SET protocol_version=2",
                }[fault]
            )
        )
    before = await control(migrator_engine)
    result = await transition(
        migrator_engine, Mode.PREPARING, before["rollout_epoch"], Mode.PREPARED
    )
    assert result["result"] == ("POLICY_UNSUPPORTED" if fault == "policy" else "HEADS_NOT_READY")
    assert (await control(migrator_engine))["rollout_epoch"] == before["rollout_epoch"]
    # Even unsupported policy must not prevent the safe PAUSED transition.
    assert (
        await transition(migrator_engine, Mode.PREPARING, before["rollout_epoch"], Mode.PAUSED)
    )["result"] == "APPLIED"


async def test_concurrent_pause_exactly_one_epoch(
    prepared: None, migrator_engine: AsyncEngine
) -> None:
    state = await control(migrator_engine)
    results = await asyncio.gather(
        *(
            transition(migrator_engine, Mode.PREPARING, state["rollout_epoch"], Mode.PAUSED)
            for _ in range(2)
        )
    )
    assert sorted(r["result"] for r in results) == ["ALREADY_APPLIED", "APPLIED"]
    assert results[0]["epoch"] == results[1]["epoch"]


async def test_unowned_advisory_lock_blocks_transition_and_preserves_state(
    prepared: None, migrator_engine: AsyncEngine
) -> None:
    state = await control(migrator_engine)
    async with migrator_engine.connect() as holder:
        await holder.execute(text("SELECT pg_advisory_lock(711,1)"))
        try:
            result = await transition(
                migrator_engine, Mode.PREPARING, state["rollout_epoch"], Mode.PAUSED
            )
            assert result["result"] == "NOT_DRAINED"
            assert (await control(migrator_engine))["rollout_epoch"] == state["rollout_epoch"]
        finally:
            await holder.execute(text("SELECT pg_advisory_unlock(711,1)"))


@pytest.mark.parametrize("busy", [False, True])
async def test_initial_prepare_installs_proof_atomically(
    prepared: None, migrator_engine: AsyncEngine, busy: bool
) -> None:
    async with migrator_engine.begin() as c:
        await c.execute(
            text(
                "UPDATE indicator_rollout_control SET mode='LEGACY',"
                "source_proof_state='PENDING' WHERE id=1"
            )
        )
    state = await control(migrator_engine)
    async with migrator_engine.connect() as holder:
        if busy:
            await holder.execute(text("SELECT pg_advisory_lock(711,1)"))
        try:
            if busy:
                with pytest.raises(RolloutRejectedError):
                    await orchestrate(
                        migrator_engine,
                        inventory(),
                        Mode.LEGACY,
                        state["rollout_epoch"],
                        Mode.PREPARING,
                        runner=Docker(),
                    )
                result = await control(migrator_engine)
                assert result["mode"] == "LEGACY" and result["source_proof_state"] == "PENDING"
            else:
                result = await orchestrate(
                    migrator_engine,
                    inventory(),
                    Mode.LEGACY,
                    state["rollout_epoch"],
                    Mode.PREPARING,
                    runner=Docker(),
                )
                assert result["result"] == "APPLIED"
                assert (await control(migrator_engine))["source_proof_state"] == "READY"
        finally:
            if busy:
                await holder.execute(text("SELECT pg_advisory_unlock(711,1)"))


@pytest.mark.parametrize("cancel", [False, True])
async def test_wait_cancel_timeout_releases_transaction(
    prepared: None, migrator_engine: AsyncEngine, cancel: bool
) -> None:
    state = await control(migrator_engine)
    async with migrator_engine.begin() as holder:
        await holder.execute(text("SELECT 1 FROM indicator_source_guard FOR UPDATE"))
        task = asyncio.create_task(
            orchestrate(
                migrator_engine,
                inventory(),
                Mode.PREPARING,
                state["rollout_epoch"],
                Mode.PAUSED,
                runner=Docker(),
            )
        )
        if cancel:
            await asyncio.sleep(0.05)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            from tiewtrade.infra.db.errors import DatabaseTimeoutError

            with pytest.raises(DatabaseTimeoutError):
                await task
    result = await orchestrate(
        migrator_engine,
        inventory(),
        Mode.PREPARING,
        state["rollout_epoch"],
        Mode.PAUSED,
        runner=Docker(),
    )
    assert result["result"] == "APPLIED"


@pytest.mark.parametrize(
    "role",
    [
        DatabaseRole.API,
        DatabaseRole.AUTH,
        DatabaseRole.MARKET_DATA,
        DatabaseRole.INDICATOR_BUILDER,
        DatabaseRole.ENGINE,
        DatabaseRole.ENGINE_SCAN,
    ],
)
async def test_runtime_cannot_transition(
    prepared: None, migrator_engine: AsyncEngine, role: DatabaseRole
) -> None:
    engine = create_engine_for(role)
    try:
        state = await control(migrator_engine)
        with pytest.raises(DBAPIError):
            await transition(engine, Mode.PREPARING, state["rollout_epoch"], Mode.PAUSED)
    finally:
        await engine.dispose()


def inventory() -> Inventory:
    return Inventory.model_validate_json(
        json.dumps(
            {
                "version": 1,
                "project": "rollout-test",
                "containers": [
                    {
                        "container_id": str(n) * 64,
                        "image_id": "sha256:" + "a" * 64,
                        "service": service,
                    }
                    for n, service in enumerate(("api", "market-data", "indicator-builder"), 1)
                ],
                "external_paths_drained": True,
                "legacy_restart_disabled": True,
                "verification_keyring_verified": True,
                "keyring_config_id": "test-keyring",
            }
        )
    )


class Docker:
    def __init__(self, fault: str = "") -> None:
        self.fault = fault
        self.calls = 0

    async def __call__(self, args: tuple[str, ...]) -> str:
        if args[0] == "rm":
            assert args[-1].startswith("f11-capability-")
            return ""
        if args[0] == "ps":
            self.calls += 1
            items = inventory().containers
            return "\n".join(f"{c.container_id} {c.service}" for c in items) + (
                "\n" + "f" * 64 + " api" if self.fault == "omitted" else ""
            )
        if args[0] == "run":
            assert "--network=none" in args and args[-2:] == (
                "-m",
                "tiewtrade.infra.indicators.capabilities",
            )
            return json.dumps(
                {
                    "cursor_formats": [1, 2] if self.fault != "legacy" else [1],
                    "codec_version": 1,
                    "protocol_version": 1,
                    "source_scope": 1,
                    "physical_grace_seconds": 22500,
                }
            )
        item = next(c for c in inventory().containers if c.container_id == args[-1])
        data: dict[str, Any] = {
            "id": item.container_id,
            "image": item.image_id,
            "restart": "no",
            "project": "rollout-test",
            "service": item.service,
            "state": {
                "Status": "exited",
                "Running": False,
                "Restarting": False,
                "Dead": False,
                "Pid": 0,
                "StartedAt": "2026-10-10T00:00:00Z",
                "FinishedAt": "2026-10-10T00:01:00Z",
            },
        }
        if self.fault == "image":
            data["image"] = "sha256:" + "b" * 64
        if self.fault == "restart":
            data["restart"] = "unless-stopped"
        if self.fault == "running":
            data["state"]["Running"] = True
        if self.fault == "pid":
            data["state"]["Pid"] = 1
        if self.fault == "timestamps":
            data["state"]["FinishedAt"] = "2026-10-09T00:01:00Z"
        if self.fault == "race" and self.calls == 2:
            data["state"]["StartedAt"] = "2026-10-10T00:00:01Z"
        return json.dumps(data)


@pytest.mark.parametrize("fault", ["omitted", "image", "restart", "running", "pid", "timestamps"])
async def test_inventory_rejects_unsafe_stop(fault: str) -> None:
    with pytest.raises(RolloutRejectedError):
        await verify_inventory(inventory(), Docker(fault))


async def test_old_image_cannot_pass_capability_gate() -> None:
    with pytest.raises(RolloutRejectedError):
        await verify_capabilities(inventory(), Docker("legacy"))


@pytest.mark.parametrize("fault", ["race", "reader", "evidence"])
async def test_orchestration_does_not_flip_on_incomplete_gate(
    prepared: None, migrator_engine: AsyncEngine, fault: str
) -> None:
    state = await control(migrator_engine)
    runtime = create_engine_for(DatabaseRole.API)
    try:
        if fault == "reader":
            async with runtime.connect() as c:
                await c.execute(text("SELECT 1"))
        with pytest.raises(RolloutRejectedError):
            await orchestrate(
                migrator_engine,
                inventory(),
                Mode.PREPARING,
                state["rollout_epoch"],
                Mode.PREPARED if fault == "evidence" else Mode.PAUSED,
                runner=Docker(fault),
            )
        assert (await control(migrator_engine))["rollout_epoch"] == state["rollout_epoch"]
    finally:
        await runtime.dispose()


async def test_verified_orchestration_pause_and_support_window(
    prepared: None, migrator_engine: AsyncEngine
) -> None:
    state = await control(migrator_engine)
    result = await orchestrate(
        migrator_engine,
        inventory(),
        Mode.PREPARING,
        state["rollout_epoch"],
        Mode.PAUSED,
        runner=Docker(),
    )
    assert result["result"] == "APPLIED"
    for offset, expected in ((timedelta(seconds=1), False), (-timedelta(seconds=1), True)):
        async with migrator_engine.begin() as c:
            await c.execute(
                text(
                    "UPDATE indicator_rollout_control SET last_v2_issue_cutoff="
                    "clock_timestamp()-interval '6 hours'+:delta"
                ),
                {"delta": offset},
            )
        assert (await inspect_rollout(migrator_engine))["support_window_elapsed"] is expected
    assert (await inspect_rollout(migrator_engine))["mode"] == "PAUSED"


@pytest.mark.parametrize("future", [True, False])
async def test_retirement_waits_for_support_window(
    prepared: None, migrator_engine: AsyncEngine, future: bool
) -> None:
    state = await control(migrator_engine)
    await transition(migrator_engine, Mode.PREPARING, state["rollout_epoch"], Mode.PAUSED)
    async with migrator_engine.begin() as c:
        await c.execute(
            text("""UPDATE indicator_rollout_control SET last_v2_issue_cutoff=
          clock_timestamp()-interval '6 hours'+:delta"""),
            {"delta": timedelta(seconds=1 if future else -1)},
        )
    if future:
        with pytest.raises(RolloutRejectedError):
            await retirement_ready(migrator_engine, inventory(), runner=Docker())
    else:
        assert (await retirement_ready(migrator_engine, inventory(), runner=Docker()))[
            "result"
        ] == "RETIREMENT_READY"


@pytest.mark.parametrize("fault", ["mode", "cutoff", "reader"])
async def test_schema_downgrade_cannot_bypass_retirement_gate(
    prepared: None, migrator_engine: AsyncEngine, fault: str
) -> None:
    migration = load_python_file(
        Path(__file__).resolve().parents[3] / "migrations/versions", "0023_indicator_rollout.py"
    )
    runtime = create_engine_for(DatabaseRole.API)
    try:
        async with migrator_engine.begin() as c:
            if fault != "mode":
                await c.execute(text("UPDATE indicator_rollout_control SET mode='PAUSED'"))
            if fault == "cutoff":
                await c.execute(
                    text("UPDATE indicator_rollout_control SET last_v2_issue_cutoff=now()")
                )
        if fault == "reader":
            async with runtime.connect() as c:
                await c.execute(text("SELECT 1"))

        def downgrade(connection: Connection) -> None:
            with Operations.context(MigrationContext.configure(connection)):
                migration.downgrade()

        with pytest.raises(DBAPIError, match="INDICATOR_DOWNGRADE_NOT_DRAINED"):
            async with migrator_engine.begin() as c:
                await c.run_sync(downgrade)
        async with migrator_engine.connect() as c:
            assert (
                await c.execute(
                    text(
                        "SELECT to_regprocedure("
                        "'transition_indicator_rollout(indicator_rollout_mode,uuid,indicator_rollout_mode)')"
                        " IS NOT NULL"
                    )
                )
            ).scalar_one()
    finally:
        await runtime.dispose()


@pytest.mark.parametrize("fault", ["none", "missing", "hash", "red", "skip", "path", "image"])
def test_activation_evidence_bound_to_images_and_actual_reports(tmp_path: Path, fault: str) -> None:
    report = (
        b'<testsuite tests="1" failures="0" errors="0" skipped="0">'
        b'<testcase name="gate"/></testsuite>'
    )
    if fault == "red":
        report = report.replace(b'failures="0"', b'failures="1"')
    if fault == "skip":
        report = report.replace(b'skipped="0"', b'skipped="1"')
    (tmp_path / "gate.xml").write_bytes(report)
    gates = [
        {
            "name": name,
            "artifact": "gate.xml",
            "sha256": hashlib.sha256(report).hexdigest(),
            "status": "PASSED",
        }
        for name in sorted(GATES)
    ]
    if fault == "missing":
        gates.pop()
    if fault == "hash":
        gates[0]["sha256"] = "f" * 64
    if fault == "path":
        gates[0]["artifact"] = "../gate.xml"
    data = {
        "version": 1,
        "image_ids": ["sha256:" + ("b" if fault == "image" else "a") * 64],
        "keyring_config_id": "test-keyring",
        "approved_gate_mapping": True,
        "gates": gates,
    }
    path = tmp_path / "evidence.json"
    path.write_text(json.dumps(data))
    if fault == "none":
        verify_evidence(path, inventory())
    else:
        with pytest.raises(RolloutRejectedError):
            verify_evidence(path, inventory())
