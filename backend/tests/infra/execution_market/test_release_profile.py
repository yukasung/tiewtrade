"""Original100 release counts and safety remain distinct from internal20 pilot."""

import argparse
from contextlib import AsyncExitStack
from pathlib import Path

import pytest

from tests.infra.execution_market import profile_internal as profile
from tests.infra.execution_market import profile_workload as workload
from tests.infra.execution_market.profile_http import internal_intake
from tests.infra.execution_market.profile_parent_poll import ParentPollGate, validate_options
from tests.infra.execution_market.profile_positions import PositionChecks
from tiewtrade.infra.db import DatabaseRole, create_engine_for


def options(phase: str = "W1") -> argparse.Namespace:
    value = profile.PROFILES[profile.RELEASE_NAME][phase]
    return argparse.Namespace(
        acceptance_profile=profile.RELEASE_NAME,
        phase=phase,
        owners=100,
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
    "phase,commands,seconds,rate",
    [
        ("SMOKE", 3000, 300, 10),
        ("W1", 18000, 1800, 10),
        ("W2", 60000, 600, 100),
        ("W3", 141000, 14400, 10),
        ("W2_OVERFLOW", 0, 0, 100),
    ],
)
def test_release_counts_and_http_manifest(
    phase: str, commands: int, seconds: int, rate: int
) -> None:
    args = options(phase)
    validate_options(args)
    value = profile.validate(args)
    assert value is not None
    assert (value.commands, value.seconds, value.rate, value.owners) == (
        commands,
        seconds,
        rate,
        100,
    )
    manifest = profile.manifest(args)
    assert manifest is not None
    assert manifest["owners"] == 100 and manifest["expected_commands"] == commands
    assert manifest["intake"] == (
        "diagnostic internal commands" if phase == "SMOKE" else "authenticated HTTP"
    )
    assert profile.selected(args) and not profile.pilot_selected(args)
    worker = argparse.Namespace(
        acceptance_profile=profile.RELEASE_NAME,
        worker_only=True,
        r8_claim_budget=True,
        coordinate_claims=True,
    )
    assert profile.validate(worker) is None
    worker_options = workload.internal_worker_options(worker)
    from tiewtrade.infra.risk_limits.policy import TransactionalRiskPolicy

    assert isinstance(worker_options["policy"], TransactionalRiskPolicy)
    assert worker_options["manual_intake"] is True
    assert worker_options["protection_rounds"] is True


@pytest.mark.parametrize(
    "key,value",
    [
        ("owners", 20),
        ("owners", True),
        ("workers", 10),
        ("rate", 2),
        ("cycles_per_owner", 6),
        ("parent_poll_limit", None),
        ("baseline_orders", 1),
        ("coordinate_claims", False),
        ("final_tail_drain", False),
    ],
)
def test_release_rejects_smaller_or_changed_workload(key: str, value: object) -> None:
    args = options()
    setattr(args, key, value)
    with pytest.raises(ValueError):
        validate_options(args)


def test_release_never_inherits_pilot_latency_or_resource_exception() -> None:
    args = options()
    assert profile.processing_acceptance(args, 0.250, 1.0)["passed"] is True
    for p95, p99 in [(0.251, 1.0), (0.250, 1.001), (0.4, 1.5)]:
        result = profile.processing_acceptance(args, p95, p99)
        assert result["passed"] is False
        assert result["performance_warning"] is False
    args.acceptance_profile = profile.NAME
    assert profile.pilot_selected(args)
    assert profile.processing_acceptance(args, 0.4, 1.5)["passed"] is True
    assert (
        profile.processing_acceptance(argparse.Namespace(phase="W1"), 0.251, 1)["passed"] is False
    )


def test_release_uses_original_four_hour_faults() -> None:
    original = profile.fault_schedule_for(profile.NAME)
    release = profile.fault_schedule_for(profile.RELEASE_NAME)
    assert release.read_bytes() == original.read_bytes()
    profile.validate_fault_schedule(release, profile_name=profile.RELEASE_NAME)
    events, cycles, _ = workload.load_fault_schedule(release)
    assert cycles == 282 and len(events) == 7
    assert [e.offset_seconds for e in events] == list(range(1800, 12601, 1800))
    assert sum(e.duration_seconds for e in events) == 270


@pytest.mark.usefixtures("internal_database")
async def test_actual_http_identity_and_snapshot_replay_for_all_100(tmp_path: Path) -> None:
    engines = {
        role: create_engine_for(role)
        for role in [
            DatabaseRole.API,
            DatabaseRole.ENGINE,
            DatabaseRole.ENGINE_SCAN,
            DatabaseRole.MIGRATOR,
        ]
    }
    try:
        owners = await workload.seed_owners(
            engines[DatabaseRole.API],
            engines[DatabaseRole.ENGINE],
            engines[DatabaseRole.ENGINE_SCAN],
            100,
        )
        gate = ParentPollGate()
        async with AsyncExitStack() as stack:
            intake = await stack.enter_async_context(
                internal_intake(
                    owners,
                    engine=engines[DatabaseRole.ENGINE],
                    api=engines[DatabaseRole.API],
                    migrator=engines[DatabaseRole.MIGRATOR],
                    gate=gate,
                    output=tmp_path,
                )
            )
            assert set(intake.clients) == {owner.user_id for owner in owners}
            positions = PositionChecks(engines[DatabaseRole.ENGINE], owners, tmp_path)
            result = await positions.final(expected_periodic=0)
            assert result["passed"] is True
            assert result["snapshot_samples"] == result["expected_samples"] == 100
            assert len(result["replays"]) == 100
    finally:
        for engine in engines.values():
            await engine.dispose()
