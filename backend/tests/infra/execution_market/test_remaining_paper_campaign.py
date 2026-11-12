"""Current-worktree wiring must refuse reuse before any fixture or worker starts."""

import json
import sys
from pathlib import Path

import pytest

from tests.infra.execution_market import remaining_paper_campaign as campaign
from tests.infra.execution_market import remaining_paper_restore as restore


def test_campaign_root_and_restore_support_resolve_this_candidate() -> None:
    root = Path(__file__).resolve().parents[4]
    assert root == campaign.ROOT
    assert root / "backend" == campaign.BACKEND
    assert restore.common is campaign
    assert (campaign.BACKEND / "src/tiewtrade/core/protections.py").is_file()


@pytest.mark.parametrize("phase", ["CONTROLLED20", "SMOKE", "W4"])
async def test_existing_output_refused_before_environment_or_workload(
    phase: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "retained"
    output.mkdir()
    sentinel = output / "sentinel"
    sentinel.write_text("unchanged")
    args = ["campaign", str(output)] if phase == "W4" else ["campaign", phase, str(output)]
    monkeypatch.setattr(sys, "argv", args)

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("reused output must not inspect services or start workload")

    monkeypatch.setattr(campaign.internal, "guard_database", forbidden)
    monkeypatch.setattr(campaign, "capture", forbidden)
    with pytest.raises(FileExistsError):
        await (restore.main() if phase == "W4" else campaign.main())
    assert sentinel.read_text() == "unchanged"
    assert list(output.iterdir()) == [sentinel]


def test_candidate_binding_records_source_identity_before_timing(tmp_path: Path) -> None:
    candidate = campaign.hashes()
    runner = "backend/tests/infra/execution_market/remaining_paper_campaign.py"
    assert runner in candidate
    campaign.pin_candidate(tmp_path, candidate)
    binding = json.loads((tmp_path / "candidate-binding.json").read_text())
    assert binding["head"] == campaign.capture("git", "-C", str(campaign.ROOT), "rev-parse", "HEAD")
    assert isinstance(binding["source_status"], list)
    assert candidate[runner]
    assert (tmp_path / "candidate-diff.patch").is_file()
    assert "postgresql+asyncpg" not in (tmp_path / "candidate-binding.json").read_text()
