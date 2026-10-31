"""Paper service quotas must not conceal a slow owner or missing acknowledgement."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast
from uuid import UUID

import pytest

from tests.infra.risk_limits.profile_workload import sla_summary


def evidence(path: Path, *, total: int, owners: int, late: int, seconds: float) -> list[UUID]:
    start = datetime(2026, 10, 29, tzinfo=UTC)
    identities = [UUID(int=i + 1) for i in range(owners)]
    (path / "inputs.jsonl").write_text(
        "".join(
            json.dumps(
                {"kind": "PRICE", "cursor": i + 1, "ready_at": start.isoformat(), "measured": True}
            )
            + "\n"
            for i in range(total)
        )
    )
    acks: list[dict[str, Any]] = []
    for index, owner in enumerate(identities):
        if index == 0 and late:
            acks.append(
                {
                    "owner": str(owner),
                    "cursor": total - late,
                    "boundary": 0,
                    "pending": False,
                    "committed_observed_at": (start + timedelta(seconds=1)).isoformat(),
                }
            )
        acks.append(
            {
                "owner": str(owner),
                "cursor": total,
                "boundary": 0,
                "pending": False,
                "committed_observed_at": (
                    start + timedelta(seconds=seconds if index == 0 else 1)
                ).isoformat(),
            }
        )
    (path / "worker.risk.jsonl").write_text(
        "".join(
            json.dumps(a) + "\n" for a in sorted(acks, key=lambda a: a["committed_observed_at"])
        )
    )
    return identities


@pytest.mark.parametrize(
    "seconds,hard,passed", [(3, 0, True), (3.000001, 0, True), (5, 0, True), (5.000001, 1, False)]
)
def test_exact_service_and_hard_boundaries(
    tmp_path: Path, seconds: float, hard: int, passed: bool
) -> None:
    owners = evidence(tmp_path, total=1000, owners=1, late=1, seconds=seconds)
    result = sla_summary(tmp_path, owners)
    assert result["passed"] is passed and result["miss_count"] == hard
    late = (tmp_path / "risk-late-inputs.jsonl").read_text().splitlines()
    assert len(late) == (1 if seconds > 3 else 0)


def test_global_success_cannot_hide_owner_quota_failure(tmp_path: Path) -> None:
    owners = evidence(tmp_path, total=1000, owners=20, late=2, seconds=4)
    result = sla_summary(tmp_path, owners)
    assert result["service_passed"] is True and result["passed"] is False
    assert cast(dict[str, Any], result["owners"])[str(owners[0])]["passed"] is False
    assert result["samples"] == result["expected"] == 20000


def test_small_sample_has_no_rounding_allowance(tmp_path: Path) -> None:
    owners = evidence(tmp_path, total=1, owners=1, late=1, seconds=4)
    assert sla_summary(tmp_path, owners)["passed"] is False


@pytest.mark.parametrize("phase", [None, "W2"])
@pytest.mark.parametrize("case", ["missing", "pending", "clock"])
def test_missing_pending_and_invalid_clock_cannot_pass(
    tmp_path: Path, case: str, phase: str | None
) -> None:
    owners = evidence(tmp_path, total=1000, owners=1, late=1, seconds=4)
    path = tmp_path / "worker.risk.jsonl"
    rows: list[dict[str, Any]] = [json.loads(x) for x in path.read_text().splitlines()]
    if case == "missing":
        rows.pop()
    elif case == "pending":
        rows[-1]["pending"] = True
    else:
        rows[0]["committed_observed_at"] = "2026-10-28T23:59:59+00:00"
    path.write_text("".join(json.dumps(x) + "\n" for x in rows))
    result = sla_summary(tmp_path, owners, phase=phase)
    assert result["passed"] is False
    assert (
        cast(int, result["clock_errors"]) > 0 if case == "clock" else result["unacknowledged"] == 1
    )


def test_original_fault_window_exclusion_is_preserved(tmp_path: Path) -> None:
    owners = evidence(tmp_path, total=1000, owners=1, late=1, seconds=4)
    # Fault boundaries are inclusive, as in the approved prior oracle.
    (tmp_path / "fault-windows.jsonl").write_text(
        json.dumps({"start": "2026-10-29T00:00:00+00:00", "end": "2026-10-29T00:00:00+00:00"})
        + "\n"
    )
    result = sla_summary(tmp_path, owners)
    assert result["expected"] == 0 and result["passed"] is False


@pytest.mark.parametrize("phase", [None, "W1", "W3", "CHECK", "W2"])
def test_saturation_owner_quota_applies_only_to_w2(tmp_path: Path, phase: str | None) -> None:
    owners = evidence(tmp_path, total=1000, owners=20, late=5, seconds=4)
    result = sla_summary(tmp_path, owners, phase=phase)
    assert result["passed"] is (phase in ("W1", "W2", "W3"))
    assert result["minimum_service_fraction"] == "0.999"
    assert result["minimum_owner_service_fraction"] == (
        "0.995" if phase in ("W1", "W2", "W3") else "0.999"
    )
    assert result["service_miss_count"] == 5
    assert len((tmp_path / "risk-late-inputs.jsonl").read_text().splitlines()) == 5


@pytest.mark.parametrize("total,late,passed", [(1000, 5, True), (1000, 6, False), (999, 5, False)])
def test_w2_owner_quota_uses_exact_counts(
    tmp_path: Path, total: int, late: int, passed: bool
) -> None:
    owners = evidence(tmp_path, total=total, owners=20, late=late, seconds=4)
    result = sla_summary(tmp_path, owners, phase="W2")
    assert result["service_passed"] is True
    assert result["passed"] is passed


def test_w2_owner_allowance_cannot_weaken_global_quota(tmp_path: Path) -> None:
    owners = evidence(tmp_path, total=1000, owners=1, late=5, seconds=4)
    result = sla_summary(tmp_path, owners, phase="W2")
    assert cast(dict[str, Any], result["owners"])[str(owners[0])]["passed"] is True
    assert result["service_passed"] is False and result["passed"] is False


@pytest.mark.parametrize("seconds,passed", [(5, True), (5.000001, False)])
def test_w2_owner_allowance_keeps_hard_limit(tmp_path: Path, seconds: float, passed: bool) -> None:
    owners = evidence(tmp_path, total=1000, owners=20, late=5, seconds=seconds)
    result = sla_summary(tmp_path, owners, phase="W2")
    assert result["passed"] is passed
