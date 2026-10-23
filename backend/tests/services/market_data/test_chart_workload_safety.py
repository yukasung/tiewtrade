import json
from pathlib import Path

import pytest

from tests.services.market_data.profile_chart_workload import evaluate, require_isolated_database
from tiewtrade.infra.db import DatabaseRole

ROLES = (DatabaseRole.MIGRATOR, DatabaseRole.API, DatabaseRole.AUTH, DatabaseRole.MARKET_DATA)


@pytest.mark.parametrize("wrong_role", ROLES)
@pytest.mark.parametrize(
    "target", ["127.0.0.1:55432/tiewtrade", "db:55434/tiewtrade", "127.0.0.1:55434/other"]
)
def test_fixture_rejects_non_capacity_database(
    monkeypatch: pytest.MonkeyPatch, wrong_role: DatabaseRole, target: str
) -> None:
    for role in ROLES:
        monkeypatch.setenv(
            role.url_variable, "postgresql+asyncpg://user:password@127.0.0.1:55434/tiewtrade"
        )
    monkeypatch.setenv(wrong_role.url_variable, f"postgresql+asyncpg://user:password@{target}")
    with pytest.raises(RuntimeError, match="F12_VALIDATION_REQUIRES_ISOLATED_DATABASE"):
        require_isolated_database()


def test_fixture_accepts_capacity_database(monkeypatch: pytest.MonkeyPatch) -> None:
    for role in ROLES:
        monkeypatch.setenv(
            role.url_variable, "postgresql+asyncpg://user:password@127.0.0.1:55434/tiewtrade"
        )
    require_isolated_database()


@pytest.mark.parametrize("before,after,progress", [("99", "100", True), ("100", "99", False)])
def test_generation_progress_compares_numeric_sequences(
    tmp_path: Path, before: str, after: str, progress: bool
) -> None:
    browser = {
        "measurement_started_at": "2026-10-23T00:00:00+00:00",
        "measurement_ended_at": "2026-10-23T00:10:00+00:00",
        "browser_text_seconds": [],
        "live": [],
        "clients": 20,
        "mount_unmount_cycles": 100,
        "maximum_retained_slots": 0,
        "forbidden_requests": [],
    }
    counts = {"preview_rows": 0, "api_connections": 0, "market_connections": 0}
    for name, value in (
        ("browser.json", browser),
        ("database-before.json", counts | {"generation_sequence": before}),
        ("database-counts.json", counts | {"generation_sequence": after}),
    ):
        (tmp_path / name).write_text(json.dumps(value), encoding="utf-8")
    result = evaluate("PREPARED", tmp_path, 100)
    assert result["checks"]["prepared_jobs_progress"] is progress
