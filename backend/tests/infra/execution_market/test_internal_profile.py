"""NC12 cannot silently shrink capacity, change rates or enter a normal database."""

import argparse
from itertools import pairwise
from pathlib import Path

import pytest

from tests.infra.execution_market import profile_internal as profile
from tests.infra.execution_market.profile_parent_poll import validate_options


def options(phase: str = "SMOKE") -> argparse.Namespace:
    value = profile.PHASES[phase]
    return argparse.Namespace(
        acceptance_profile=profile.NAME,
        phase=phase,
        owners=20,
        baseline_orders=20,
        workers=20,
        rate=value.rate,
        cycles_per_owner=value.cycles_per_owner,
        parent_poll_limit=4,
        r8_claim_budget=True,
        coordinate_claims=True,
        publisher_heartbeat_per_book=True,
        final_tail_drain=True,
        baseline_manifest=None,
    )


@pytest.mark.parametrize(
    "phase,commands,seconds",
    [
        ("SMOKE", 600, 300),
        ("W1", 3600, 1800),
        ("W2", 12000, 600),
        ("W3", 28200, 14400),
        ("W2_OVERFLOW", 0, 0),
    ],
)
def test_pinned_counts_and_distinct_profile(phase: str, commands: int, seconds: int) -> None:
    args = options(phase)
    validate_options(args)
    value = profile.validate(args)
    assert value is not None and value.commands == commands and value.seconds == seconds
    manifest = profile.manifest(args)
    assert manifest is not None and manifest["name"] == "PAPER_INTERNAL20_V1"
    assert manifest["expected_commands"] == commands
    assert profile.validate(argparse.Namespace()) is None
    assert profile.manifest(argparse.Namespace()) is None


@pytest.mark.parametrize(
    "key,value",
    [
        ("owners", 10),
        ("owners", True),
        ("baseline_orders", 1),
        ("workers", 4),
        ("rate", 10),
        ("cycles_per_owner", 1),
        ("parent_poll_limit", None),
        ("r8_claim_budget", False),
        ("coordinate_claims", False),
        ("publisher_heartbeat_per_book", False),
        ("final_tail_drain", False),
        ("baseline_manifest", Path("old.json")),
        ("phase", "BASELINE"),
        ("acceptance_profile", "unknown"),
    ],
)
def test_profile_mismatch_is_rejected(key: str, value: object) -> None:
    args = options()
    setattr(args, key, value)
    with pytest.raises(ValueError):
        validate_options(args)


def test_no_new_profile_does_not_authorize_old_w1_poll_gate() -> None:
    args = options("W1")
    args.acceptance_profile = None
    with pytest.raises(ValueError, match="SMOKE"):
        validate_options(args)


@pytest.mark.parametrize(
    "role", ["API", "AUTH", "ENGINE", "ENGINE_SCAN", "MIGRATOR", "MARKET_DATA"]
)
@pytest.mark.parametrize(
    "target",
    [
        "postgresql://localhost/development",
        "postgresql://remote/tiewtrade_internal20_test",
        "postgresql://localhost/tiewtrade_internal20_other",
    ],
)
def test_guard_rejects_nonisolated_or_mixed_role_targets(role: str, target: str) -> None:
    env = {
        f"TIEWTRADE_DATABASE_URL_{name}": "postgresql://localhost/tiewtrade_internal20_test"
        for name in ("API", "AUTH", "ENGINE", "ENGINE_SCAN", "MIGRATOR", "MARKET_DATA")
    }
    assert profile.guard_database(env) == "tiewtrade_internal20_test"
    env[f"TIEWTRADE_DATABASE_URL_{role}"] = target
    with pytest.raises(ValueError):
        profile.guard_database(env)


def test_fault_schedule_cannot_be_shortened(tmp_path: Path) -> None:
    original = Path(profile.__file__).with_name("w3_fault_schedule.json")
    profile.validate_fault_schedule(original)
    altered = tmp_path / "schedule.json"
    altered.write_text(original.read_text().replace("14400", "1440"))
    with pytest.raises(ValueError, match="unchanged"):
        profile.validate_fault_schedule(altered)


@pytest.mark.parametrize("change", ["source", "admin", "same_target", "unsafe_target", "container"])
def test_restore_guard_rejects_mismatched_or_unsafe_destinations(change: str) -> None:
    from tests.infra.execution_market.profile_internal_restore import guard_restore

    source = "postgresql://localhost/tiewtrade_internal20_source"
    env = {
        f"TIEWTRADE_DATABASE_URL_{role}": source
        for role in ("API", "AUTH", "ENGINE", "ENGINE_SCAN", "MIGRATOR", "MARKET_DATA")
    }
    env.update(SOURCE=source, ADMIN=source)
    args = argparse.Namespace(
        action="verify",
        source_url_env="SOURCE",
        admin_url_env="ADMIN",
        target_database="tiewtrade_internal20_target",
        postgres_container="tiewtrade-postgres-1",
    )
    guard_restore(args, env)
    if change in ("source", "admin"):
        env[change.upper()] = "postgresql://remote/development"
    elif change == "same_target":
        args.target_database = "tiewtrade_internal20_source"
    elif change == "unsafe_target":
        args.target_database = "tiewtrade_internal20_/unsafe"
    else:
        args.postgres_container = "other-postgres"
    with pytest.raises(ValueError):
        guard_restore(args, env)


@pytest.mark.parametrize("phase", list(profile.PHASES))
def test_v2_changes_only_burst_rate_and_duration(phase: str) -> None:
    args = options(phase)
    args.acceptance_profile = profile.NAME_V2
    args.rate = profile.PROFILES[profile.NAME_V2][phase].rate
    validate_options(args)
    value = profile.validate(args)
    assert value is not None
    original = profile.PHASES[phase]
    assert value.cycles_per_owner == original.cycles_per_owner
    assert value.commands == original.commands
    if phase == "W2":
        assert value.rate == 10 and value.seconds == 1200
        assert value.commands / value.rate == value.seconds
        assert value.seconds + 60 == 1260
        assert value.seconds * 10 == 12000
    else:
        assert value == original
    manifest = profile.manifest(args)
    assert manifest is not None
    assert manifest["name"] == profile.NAME_V2
    assert manifest["rate"] == value.rate and manifest["seconds"] == value.seconds
    original_manifest = profile.manifest(options(phase))
    assert original_manifest is not None and original_manifest["name"] == profile.NAME


@pytest.mark.parametrize(
    "key,value",
    [
        ("rate", 20),
        ("rate", True),
        ("cycles_per_owner", 60),
        ("owners", 10),
        ("workers", 10),
        ("baseline_orders", 10),
        ("parent_poll_limit", 8),
        ("coordinate_claims", False),
        ("r8_claim_budget", False),
    ],
)
def test_v2_cannot_silently_change_pinned_safety_or_load(key: str, value: object) -> None:
    args = options("W2")
    args.acceptance_profile = profile.NAME_V2
    args.rate = 10
    setattr(args, key, value)
    with pytest.raises(ValueError):
        validate_options(args)


@pytest.mark.parametrize("profile_name", [profile.NAME_V2, profile.NAME_V3])
async def test_internal_worker_subprocess_receives_explicit_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, profile_name: str
) -> None:
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from tests.infra.execution_market import profile_workload as workload

    process = SimpleNamespace(pid=77777)
    spawned = AsyncMock(return_value=process)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawned)
    monkeypatch.setattr(workload, "wait_runtime_pid", AsyncMock(return_value=77778))
    try:
        processes, _, _ = await workload.start_worker_processes(
            1,
            tmp_path,
            r8_claim_budget=True,
            coordinate_claims=True,
            acceptance_profile=profile_name,
        )
        assert processes == [process]
        command = spawned.call_args.args
        assert command[command.index("--acceptance-profile") + 1] == profile_name
        assert "--r8-claim-budget" in command and "--coordinate-claims" in command
    finally:
        workload.WORKER_RUNTIME_PIDS.pop(process.pid, None)


@pytest.mark.parametrize("phase", list(profile.PHASES))
def test_v3_changes_only_short_stability_phase(phase: str) -> None:
    import json

    from tests.infra.execution_market import profile_workload as workload

    args = options(phase)
    args.acceptance_profile = profile.NAME_V3
    value = profile.PROFILES[profile.NAME_V3][phase]
    args.rate, args.cycles_per_owner = value.rate, value.cycles_per_owner
    assert profile.validate(args) == value
    manifest = profile.manifest(args)
    assert manifest is not None and manifest["name"] == profile.NAME_V3
    if phase != "W3":
        assert value == profile.PROFILES[profile.NAME_V2][phase]
        return
    assert value.commands == 3000 and value.cycles_per_owner == 30 and value.seconds == 1800
    schedule = profile.fault_schedule_for(profile.NAME_V3)
    profile.validate_fault_schedule(schedule, profile_name=profile.NAME_V3)
    events, cycles, _ = workload.load_fault_schedule(schedule)
    original, _, _ = workload.load_fault_schedule(profile.fault_schedule_for(profile.NAME))
    assert cycles == 30 and len(events) == 7
    assert [(e.kind, e.duration_seconds) for e in events] == [
        (e.kind, e.duration_seconds) for e in original
    ]
    assert [e.offset_seconds for e in events] == [180, 360, 540, 720, 900, 1080, 1260]
    assert all(
        a.offset_seconds + a.duration_seconds < b.offset_seconds for a, b in pairwise(events)
    )
    assert events[-1].offset_seconds + events[-1].duration_seconds < value.seconds
    assert value.commands / value.rate + sum(e.duration_seconds for e in events) + 60 == 1830
    assert int(value.commands / value.rate * 10) == 15000
    assert value.seconds // 60 == 30 and 20 * (value.seconds // 60 + 1) == 620
    assert json.loads(schedule.read_text())["duration_seconds"] == 1800
    assert "four-hour Release validation pending" in str(manifest["scope"])
    assert profile.PROFILES[profile.NAME]["W3"].seconds == 14400
    assert profile.PROFILES[profile.NAME_V2]["W3"].cycles_per_owner == 282


@pytest.mark.parametrize("change", ["offset", "duration", "kind", "count", "window", "cycles"])
def test_v3_rejects_modified_fault_fixture(tmp_path: Path, change: str) -> None:
    import json

    data = json.loads(profile.fault_schedule_for(profile.NAME_V3).read_text())
    if change == "offset":
        data["events"][0]["offset_seconds"] = 1
    elif change == "duration":
        data["events"][0]["duration_seconds"] = 1
    elif change == "kind":
        data["events"][0]["kind"] = "REDIS_OUTAGE"
    elif change == "count":
        data["events"].pop()
    elif change == "window":
        data["duration_seconds"] = 14400
    else:
        data["cycles_per_owner"] = 282
    altered = tmp_path / "altered.json"
    altered.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="unchanged"):
        profile.validate_fault_schedule(altered, profile_name=profile.NAME_V3)
    with pytest.raises(ValueError, match="unchanged"):
        profile.validate_fault_schedule(
            profile.fault_schedule_for(profile.NAME_V3), profile_name=profile.NAME_V2
        )
