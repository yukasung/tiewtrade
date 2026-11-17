"""Regression proof for the four reviewed harness failure paths, without workloads."""

import argparse
import asyncio
import json
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest
from starlette.datastructures import State

from tests.infra.execution_market import profile_internal as internal
from tests.infra.execution_market import profile_workload as workload
from tests.infra.execution_market import remaining_paper_campaign as campaign
from tests.infra.execution_market import remaining_paper_cleanup_diagnostic as diagnostic
from tests.infra.execution_market import remaining_paper_restore as restore
from tiewtrade.services.api.app import app


def nonempty() -> dict[str, Any]:
    return {
        "observed_at": "2026-11-09T00:00:00+00:00",
        "connections": 1,
        "advisory_locks": 0,
        "backends": [
            {
                "pid": 123,
                "role": "tiewtrade_engine",
                "state": "idle",
                "backend_type": "client backend",
                "transaction_open": False,
            }
        ],
    }


@pytest.fixture
def campaign_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Share only CLI/isolation setup; each case controls its own outcome and snapshot."""
    output = tmp_path / "result"
    monkeypatch.setattr(
        argparse.ArgumentParser,
        "parse_args",
        lambda _: SimpleNamespace(
            phase="SMOKE",
            output=output,
            acceptance_profile=campaign.internal.NAME,
            observer_w3_prefix=False,
        ),
    )
    monkeypatch.setattr(internal, "guard_database", lambda _: "tiewtrade_internal20_test")
    monkeypatch.setattr(campaign, "hashes", lambda: {})
    monkeypatch.setattr(campaign, "pin_candidate", lambda *args: None)
    return output


@pytest.mark.parametrize("kind", ["D20", "W4"])
@pytest.mark.parametrize("code", [0, 1])
async def test_cleanup_never_downgrades_a_known_failed_workload(
    kind: str, code: int, campaign_output: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(internal, "run_preflighted", AsyncMock(return_value=code))
    snapshot = nonempty() if kind == "D20" else {"connections": 1, "advisory_locks": 0}
    monkeypatch.setattr(campaign, "capture", lambda *args: json.dumps(snapshot))
    assert await (campaign.main() if kind == "D20" else restore.main()) == 1
    result = json.loads((campaign_output / "campaign-result.json").read_text())
    assert result["workload_status"] == ("FAILED" if code else "PASSED")
    assert result["status"] == ("FAILED" if code else "INCOMPLETE")


async def test_rejected_snapshot_keeps_identity_but_drops_unapproved_fields(
    campaign_output: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(internal, "run_preflighted", AsyncMock(return_value=0))
    snapshot = nonempty()
    snapshot["backends"][0].update(role=None, query="PRIVATE_NOT_ALLOWED")
    snapshot["secret"] = "PRIVATE_NOT_ALLOWED"
    monkeypatch.setattr(campaign, "capture", lambda *args: json.dumps(snapshot))
    assert await campaign.main() == 1
    cleanup = json.loads((campaign_output / "cleanup.json").read_text())
    assert cleanup["backends"][0]["pid"] == 123
    assert cleanup["backends"][0]["role"] is None
    assert cleanup["connections"] == 1 and cleanup["error_type"] == "ValueError"
    assert "PRIVATE_NOT_ALLOWED" not in (campaign_output / "cleanup.json").read_text()
    assert (
        json.loads((campaign_output / "campaign-result.json").read_text())["status"] == "INCOMPLETE"
    )


@pytest.mark.parametrize("kind", ["D20", "W4"])
async def test_assertion_failure_remains_failed_and_preserves_primary_exception(
    kind: str, campaign_output: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    failure = AssertionError("controlled workload assertion")
    monkeypatch.setattr(internal, "run_preflighted", AsyncMock(side_effect=failure))
    monkeypatch.setattr(campaign, "capture", lambda *args: json.dumps(nonempty()))
    with pytest.raises(AssertionError) as caught:
        await (campaign.main() if kind == "D20" else restore.main())
    assert caught.value is failure
    assert json.loads((campaign_output / "campaign-result.json").read_text())["status"] == "FAILED"


@pytest.mark.parametrize(
    "outcome", ["snapshot", "dispose", "primary", "cancel", "quiescence", "intake"]
)
async def test_observer_or_disposal_failure_cannot_skip_remaining_engines(
    outcome: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engines: dict[str, Any] = {}
    primary = asyncio.CancelledError() if outcome == "cancel" else RuntimeError("primary")
    secondary = OSError("secondary")

    class Engine:
        attempted = False

        def __init__(self, role: Any) -> None:
            self.role = role

        @asynccontextmanager
        async def connect(self) -> Any:
            yield SimpleNamespace(execute=AsyncMock())

        async def dispose(self) -> None:
            self.attempted = True
            if outcome == "dispose" and self.role.name == "MARKET_DATA":
                raise secondary

    @asynccontextmanager
    async def observe(*args: Any) -> Any:
        def quiesce() -> None:
            if outcome == "quiescence":
                raise secondary

        yield SimpleNamespace(begin_quiescence=quiesce)

    @asynccontextmanager
    async def intake(*args: Any, **kwargs: Any) -> Any:
        try:
            yield None
        finally:
            if outcome == "intake":
                raise secondary

    def create(role: Any) -> Engine:
        value = Engine(role)
        engines[role.name] = value
        return value

    async def snapshot(stage: str) -> None:
        if stage == "parent_before_shutdown" and outcome in ("primary", "cancel"):
            raise primary
        if stage == "disposed_MARKET_DATA" and outcome in ("snapshot", "primary", "cancel"):
            raise secondary

    monkeypatch.setattr(diagnostic, "observe_owned", observe)
    monkeypatch.setattr(diagnostic, "internal_intake", intake)
    monkeypatch.setattr(diagnostic, "create_engine_for", create)
    monkeypatch.setattr(internal, "require_empty_database", AsyncMock())
    monkeypatch.setattr(workload, "resource_sampler", AsyncMock())
    previous_state = app.state
    previous_entries = dict(previous_state._state)
    monkeypatch.setattr(app, "state", State())
    assert app.state is not previous_state
    expected = primary if outcome in ("primary", "cancel") else secondary
    with pytest.raises(type(expected)) as caught:
        await diagnostic.parent_lifecycle(tmp_path, snapshot)
    assert caught.value is expected
    assert len(engines) == 5 and all(engine.attempted for engine in engines.values())
    assert previous_state._state == previous_entries
    if outcome in ("primary", "cancel"):
        assert primary.__notes__ == ["secondary lifecycle cleanup: OSError"]


class DiagnosticObserver:
    """Read-only observer double shared by source-binding and disposal error cases."""

    def __init__(self) -> None:
        self.disposal_error: BaseException | None = None

    @asynccontextmanager
    async def connect(self) -> Any:
        yield self

    async def execute(self, *args: Any, **kwargs: Any) -> Any:
        return SimpleNamespace(
            one=lambda: ("postgres", 42, "on"),
            mappings=lambda: SimpleNamespace(all=lambda: []),
        )

    async def dispose(self) -> None:
        if self.disposal_error is not None:
            raise self.disposal_error


@pytest.fixture
def diagnostic_observer(monkeypatch: pytest.MonkeyPatch) -> DiagnosticObserver:
    observer = DiagnosticObserver()

    @contextmanager
    def events(*args: Any) -> Any:
        yield

    monkeypatch.setattr(internal, "guard_database", lambda _: "tiewtrade_internal20_test")
    monkeypatch.setattr(diagnostic, "observer_url", lambda _: "unused")
    monkeypatch.setattr(campaign, "hashes", lambda: {})
    monkeypatch.setattr(campaign, "pin_candidate", lambda *args: None)
    monkeypatch.setattr(diagnostic, "create_async_engine", lambda *args, **kwargs: observer)
    monkeypatch.setattr(diagnostic, "pool_events", events)
    monkeypatch.setattr(internal, "require_empty_database", AsyncMock())
    monkeypatch.setattr(diagnostic, "create_engine_for", lambda _: DiagnosticObserver())
    monkeypatch.setattr(diagnostic, "parent_lifecycle", AsyncMock())
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    return observer


@pytest.mark.parametrize("changed", [False, True])
async def test_diagnostic_source_change_is_incomplete_with_nonzero_exit(
    changed: bool,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    diagnostic_observer: DiagnosticObserver,
) -> None:
    monkeypatch.setattr(
        campaign,
        "hashes",
        Mock(
            side_effect=[{"file": "before"}, {"file": "after" if changed else "before"}],
        ),
    )
    output = tmp_path / "diagnostic"
    assert await diagnostic.run(output) == int(changed)
    result = json.loads((output / "result.json").read_text())
    assert result["status"] == ("INCOMPLETE" if changed else "OBSERVATION_COMPLETE")
    assert result["source_unchanged"] is not changed
    assert result["error_type"] == ("CandidateChanged" if changed else None)


@pytest.mark.parametrize("cycle_expired", [False, True])
async def test_positive_cycle_failure_survives_cleanup_error(
    campaign_output: Path, monkeypatch: pytest.MonkeyPatch, cycle_expired: bool
) -> None:
    failure = (
        campaign.workload.CycleBudgetExceededError("cycle budget")
        if cycle_expired
        else TimeoutError("unknown transport")
    )
    monkeypatch.setattr(internal, "run_preflighted", AsyncMock(side_effect=failure))
    monkeypatch.setattr(campaign, "capture", lambda *args: json.dumps(nonempty()))
    with pytest.raises(TimeoutError):
        await campaign.main()
    result = json.loads((campaign_output / "campaign-result.json").read_text())
    assert result["status"] == ("FAILED" if cycle_expired else "INCOMPLETE")
    assert result["workload_status"] == result["status"]


@pytest.mark.parametrize("phase", ["CONTROLLED20", "SMOKE", "W1", "W3", "W2_OVERFLOW"])
async def test_burst5_unsupported_phase_stops_before_preflight_or_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, phase: str
) -> None:
    output = tmp_path / "result"
    monkeypatch.setattr(
        argparse.ArgumentParser,
        "parse_args",
        lambda _: SimpleNamespace(
            phase=phase, output=output, acceptance_profile=internal.NAME_BURST5
        ),
    )
    preflight = AsyncMock()
    monkeypatch.setattr(internal, "run_preflighted", preflight)
    with pytest.raises(SystemExit) as caught:
        await campaign.main()
    assert caught.value.code == 2
    assert not output.exists()
    preflight.assert_not_awaited()


@pytest.mark.parametrize("profile", tuple(internal.PROFILES))
def test_manifest_authorization_matches_selected_profile(profile: str) -> None:
    value = campaign.profile_authorization(profile)
    assert profile in value
    if profile in {internal.RELEASE_TIMING_NAME, internal.NAME_BURST5}:
        assert "paper-timing-acceptance-amendment-20261114.md" in value
    elif profile == internal.RELEASE_NAME:
        assert "integrated-paper-acceptance-plan.md" in value
    else:
        assert "internal-paper-acceptance-amendment.md" in value
    assert "250ms" not in value and "burst10" not in value


def test_manifest_authorization_rejects_unknown_profile() -> None:
    with pytest.raises(ValueError, match="unknown acceptance profile"):
        campaign.profile_authorization("UNKNOWN")
