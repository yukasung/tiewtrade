"""D4 actual CPU build/transition barriers and post-cutoff HTTP observations."""

import json
import os
from pathlib import Path
from time import monotonic_ns
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.indicators.test_claims import builder_engine as builder_engine
from tests.infra.indicators.test_claims import prepared as prepared
from tests.infra.indicators.test_claims import slot
from tests.infra.indicators.test_rollout import control, transition
from tests.infra.indicators.test_rollout import reset_transition_history as reset_transition_history
from tests.infra.indicators.test_source import active as active
from tests.services.indicator_builder.profile_container_recovery import docker
from tests.services.indicator_builder.profile_global_handoff import (
    Probes,
    derived_state,
    ordered_shutdown,
    outcome,
)
from tests.services.indicator_builder.profile_global_handoff import probes as probes
from tests.services.indicator_builder.profile_mixed_replicas import (
    PATH,
    QUERY,
    Replicas,
    authenticate,
    claims_for,
    reset_admission,
)
from tests.services.indicator_builder.profile_mixed_replicas import published as published
from tests.services.indicator_builder.profile_mixed_replicas import replicas as replicas
from tiewtrade.infra.indicators.rollout import Mode


async def drained(admin: AsyncEngine) -> None:
    async with admin.connect() as c:
        assert (
            await c.execute(
                text("""SELECT count(*) FROM pg_stat_activity
          WHERE datname=current_database() AND usename IN
            ('tiewtrade_api','tiewtrade_market_data','tiewtrade_indicator_builder')""")
            )
        ).scalar_one() == 0
    assert (await slot(admin))["state"] == "IDLE"


async def test_cpu_build_blocks_activate_and_pause_then_http_obeys_cutoff(
    published: dict[str, Any],
    replicas: Replicas,
    probes: Probes,
    api_engine: AsyncEngine,
    builder_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
) -> None:
    await authenticate(replicas)
    await replicas.stop_all()
    await api_engine.dispose()
    await builder_engine.dispose()
    await drained(migrator_engine)
    initial = await control(migrator_engine)
    assert (
        await transition(migrator_engine, Mode.PREPARED, initial["rollout_epoch"], Mode.PAUSED)
    )["result"] == "APPLIED"
    paused = await control(migrator_engine)
    assert (
        await transition(migrator_engine, Mode.PAUSED, paused["rollout_epoch"], Mode.PREPARING)
    )["result"] == "APPLIED"
    trace: list[dict[str, Any]] = []
    token = ""
    for expected, target in ((Mode.PREPARING, Mode.PREPARED), (Mode.PREPARED, Mode.PAUSED)):
        before = await control(migrator_engine)
        async with migrator_engine.begin() as c:
            await c.execute(
                text("""UPDATE indicator_build_jobs SET status='QUEUED',
              retry_not_before=clock_timestamp() WHERE base='BTC' AND timeframe='4h'""")
            )
        worker = await probes.start("cpu")
        running = await probes.wait(worker, "barrier")
        assert any(row.get("step") == "cpu_start" for row in running)
        held = await slot(migrator_engine)
        assert held["state"] == "RUNNING"
        result = await transition(migrator_engine, expected, before["rollout_epoch"], target)
        assert result["result"] == "NOT_DRAINED"
        assert await control(migrator_engine) == before
        assert await slot(migrator_engine) == held
        if expected is Mode.PREPARED:
            await reset_admission()
            await docker(
                "exec",
                replicas.containers[0],
                "python",
                "-c",
                "from pathlib import Path; Path('/tmp/d4-audit.jsonl').write_text(''); "
                "Path('/tmp/d4-audit-enabled').touch()",
            )
            response = await replicas.clients[0].get(PATH, params=QUERY)
            assert response.status_code == 200
            positive = [
                json.loads(line)
                for line in (
                    await docker("exec", replicas.containers[0], "cat", "/tmp/d4-audit.jsonl")
                ).splitlines()
            ]
            assert any(row["payload"] for row in positive)
            assert not any(row["unsafe_dml"] for row in positive)
            await docker(
                "exec",
                replicas.containers[0],
                "python",
                "-c",
                "from pathlib import Path; Path('/tmp/d4-audit-enabled').unlink()",
            )
            token = response.json()["next_cursor"]
            claims, _, _ = await claims_for(replicas.clients[0], token)
            assert claims.rollout_epoch == before["rollout_epoch"]
            trace.append(
                {
                    "step": "v2_before_pause",
                    "epoch": claims.rollout_epoch,
                    "issued_at": claims.issued_at,
                    "sql_positive_control": positive,
                }
            )
        await probes.release(worker)
        finished = await probes.finish(worker)
        assert outcome(finished) == "READY"
        ordered_shutdown(finished)
        joined = monotonic_ns()
        await replicas.stop_all()
        await api_engine.dispose()
        await builder_engine.dispose()
        await drained(migrator_engine)
        drained_at = monotonic_ns()
        result = await transition(migrator_engine, expected, before["rollout_epoch"], target)
        assert result["result"] == "APPLIED"
        after = await control(migrator_engine)
        assert after["mode"] == target.value and after["rollout_epoch"] != before["rollout_epoch"]
        assert joined <= drained_at <= monotonic_ns()
        trace.append(
            {
                "step": "drained_transition",
                "from": expected.value,
                "to": target.value,
                "worker": finished,
                "joined_ns": joined,
                "drained_ns": drained_at,
                "transition_observed_ns": monotonic_ns(),
                "epoch": after["rollout_epoch"],
                "cutoff": after["last_v2_issue_cutoff"],
            }
        )
        await replicas.resume_all()
    assert token
    assert claims.issued_at <= after["last_v2_issue_cutoff"]
    before_http = await derived_state(migrator_engine)
    await reset_admission()
    for index, client in enumerate(replicas.clients[:2]):
        ident = replicas.containers[index]
        await docker(
            "exec",
            ident,
            "python",
            "-c",
            "from pathlib import Path; Path('/tmp/d4-audit.jsonl').write_text(''); "
            "Path('/tmp/d4-audit-enabled').touch()",
        )
        try:
            first = await client.get(PATH, params=QUERY)
            continuation = await client.get(PATH, params={"cursor": token})
            assert first.status_code == 503 and continuation.status_code == 409
            rows = [
                json.loads(line)
                for line in (await docker("exec", ident, "cat", "/tmp/d4-audit.jsonl")).splitlines()
            ]
            assert rows and not any(row["payload"] or row["unsafe_dml"] for row in rows)
            # Authentication can renew sessions; indicator GET must not write payloads.
            assert await derived_state(migrator_engine) == before_http
            trace.append(
                {
                    "step": "paused_http",
                    "replica": index,
                    "first": 503,
                    "continuation": 409,
                    "sql": rows,
                }
            )
        finally:
            await docker(
                "exec",
                ident,
                "python",
                "-c",
                "from pathlib import Path; Path('/tmp/d4-audit-enabled').unlink()",
            )
    destination = os.environ.get("TIEWTRADE_D4_EVIDENCE_PATH")
    if destination:
        Path(destination).write_text(json.dumps(trace, default=str, indent=2), encoding="utf-8")
