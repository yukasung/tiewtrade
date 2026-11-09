"""Observer isolation and cancellation must hold before the single diagnostic."""

import asyncio
import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest
from sqlalchemy import event
from sqlalchemy.engine import make_url

from tests.infra.execution_market import remaining_paper_cleanup_diagnostic as diagnostic
from tiewtrade.infra.db import DatabaseRole


def test_observer_uses_postgres_without_retargeting_source() -> None:
    environment = {
        role.url_variable: "postgresql+asyncpg://fixture:private@localhost:55432/"
        "tiewtrade_internal20_test_fixture"
        for role in DatabaseRole
    }
    environment["TIEWTRADE_TEST_ADMIN_URL"] = environment[DatabaseRole.MIGRATOR.url_variable]
    before = dict(environment)
    assert make_url(diagnostic.observer_url(environment)).database == "postgres"
    assert environment == before
    environment["TIEWTRADE_TEST_ADMIN_URL"] = "postgresql+asyncpg://fixture@other/db"
    with pytest.raises(ValueError):
        diagnostic.observer_url(environment)


@pytest.mark.parametrize("error", [RuntimeError("private"), asyncio.CancelledError()])
def test_pool_listener_cleanup_and_allowlisted_output(
    monkeypatch: pytest.MonkeyPatch, error: BaseException
) -> None:
    listen, remove = Mock(), Mock()
    monkeypatch.setattr(event, "listen", listen)
    monkeypatch.setattr(event, "remove", remove)
    monkeypatch.setattr(event, "contains", Mock(return_value=True))
    rows: list[dict[str, Any]] = []
    with pytest.raises(type(error)), diagnostic.pool_events(rows):
        callback = listen.call_args_list[0].args[2]
        callback(
            SimpleNamespace(driver_connection=SimpleNamespace(get_server_pid=lambda: 123)),
            SimpleNamespace(info={"private": "must not be copied"}),
        )
        raise error
    assert remove.call_count == 4
    assert rows[0]["backend_pid"] == 123
    assert "private" not in json.dumps(rows)


@pytest.mark.usefixtures("internal_database")
@pytest.mark.parametrize("outcome", ["error", "cancel"])
async def test_actual_parent_lifecycle_disposes_every_engine_on_interruption(
    tmp_path: Path, outcome: str
) -> None:
    before = dict(os.environ)
    stages: list[str] = []
    failure = RuntimeError("controlled") if outcome == "error" else asyncio.CancelledError()

    async def snapshot(stage: str) -> None:
        stages.append(stage)
        if stage == "parent_before_shutdown":
            raise failure

    with pytest.raises(type(failure)):
        await diagnostic.parent_lifecycle(tmp_path, snapshot)
    assert stages[-1] == "disposed_ENGINE_SCAN"
    report = json.loads((tmp_path / "parent.owned-pools.json").read_text())
    assert all(row["checked_out"] == 0 for row in report["pools"])
    assert dict(os.environ) == before
