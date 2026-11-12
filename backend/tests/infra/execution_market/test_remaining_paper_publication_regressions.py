"""Prepublication malformed-W4 and observer-disposal regression proof."""

import asyncio
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest

from tests.infra.execution_market import profile_internal as internal
from tests.infra.execution_market import remaining_paper_campaign as campaign
from tests.infra.execution_market import remaining_paper_cleanup_diagnostic as diagnostic
from tests.infra.execution_market import remaining_paper_restore as restore
from tests.infra.execution_market.test_remaining_paper_review_regressions import (
    DiagnosticObserver,
)
from tests.infra.execution_market.test_remaining_paper_review_regressions import (
    campaign_output as campaign_output,
)
from tests.infra.execution_market.test_remaining_paper_review_regressions import (
    diagnostic_observer as diagnostic_observer,
)


@pytest.mark.parametrize("code", [0, 1])
@pytest.mark.parametrize(
    "snapshot",
    [
        {},
        None,
        [],
        {"connections": 0},
        {"connections": 0, "advisory_locks": "0"},
        {"connections": False, "advisory_locks": 0},
        {"connections": -1, "advisory_locks": 0},
        {"connections": 0, "advisory_locks": 0, "secret": "PRIVATE"},
    ],
)
async def test_w4_missing_or_malformed_cleanup_never_passes(
    code: int, snapshot: Any, campaign_output: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(internal, "run_preflighted", AsyncMock(return_value=code))
    monkeypatch.setattr(campaign, "capture", lambda *args: json.dumps(snapshot))
    assert await restore.main() == 1
    result = json.loads((campaign_output / "campaign-result.json").read_text())
    assert result["status"] == ("FAILED" if code else "INCOMPLETE")
    cleanup = json.loads((campaign_output / "cleanup.json").read_text())
    assert len(cleanup) == 2
    assert all(row["error_type"] == "ValueError" for row in cleanup.values())
    assert "PRIVATE" not in (campaign_output / "cleanup.json").read_text()


async def test_w4_zero_counts_still_pass_without_an_extra_attempt(
    campaign_output: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    phase = AsyncMock(return_value=0)
    monkeypatch.setattr(internal, "run_preflighted", phase)
    monkeypatch.setattr(campaign, "capture", lambda *args: '{"connections":0,"advisory_locks":0}')
    assert await restore.main() == 0
    assert phase.await_count == 1
    assert json.loads((campaign_output / "campaign-result.json").read_text())["status"] == "PASSED"


@pytest.mark.parametrize("outcome", ["disposal", "primary", "cancel"])
@pytest.mark.parametrize("disposal_kind", ["error", "cancel"])
async def test_observer_disposal_failure_still_saves_evidence_and_preserves_primary(
    outcome: str,
    disposal_kind: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    diagnostic_observer: DiagnosticObserver,
) -> None:
    disposal = (
        asyncio.CancelledError()
        if disposal_kind == "cancel"
        else OSError("PRIVATE_DISPOSAL_DETAIL")
    )
    primary = asyncio.CancelledError() if outcome == "cancel" else RuntimeError("PRIVATE_PRIMARY")

    diagnostic_observer.disposal_error = disposal
    monkeypatch.setattr(
        diagnostic,
        "parent_lifecycle",
        AsyncMock(
            side_effect=None if outcome == "disposal" else primary,
        ),
    )
    output = tmp_path / "diagnostic"
    expected = disposal if outcome == "disposal" else primary
    with pytest.raises(type(expected)) as caught:
        await diagnostic.run(output)
    assert caught.value is expected
    result = json.loads((output / "result.json").read_text())
    assert result["status"] == "INCOMPLETE"
    assert result["error_type"] == type(expected).__name__
    assert result["observer_disposal_error"] == type(disposal).__name__
    assert (output / "pool-events.json").is_file()
    assert "PRIVATE" not in (output / "result.json").read_text()
    if outcome != "disposal":
        assert primary.__notes__ == ["secondary observer disposal: " + type(disposal).__name__]
