"""Observer failures and private fields cannot change scheduler assertions."""

import asyncio
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from tests.services.indicator_builder import scheduler_lock_diagnostic as diagnostic

ENV = {
    "TIEWTRADE_TEST_ADMIN_URL": "postgresql+asyncpg://admin:private@localhost:5432/test",
    "TIEWTRADE_DATABASE_URL_MIGRATOR": "postgresql+asyncpg://migrator@localhost:5432/test",
}


@pytest.fixture
def observer(monkeypatch: pytest.MonkeyPatch) -> tuple[Any, Any, Any]:
    connection = AsyncMock()
    engine = Mock(connect=AsyncMock(return_value=connection), dispose=AsyncMock())
    factory = Mock(return_value=engine)
    monkeypatch.setattr(diagnostic, "create_async_engine", factory)
    monkeypatch.setattr(diagnostic, "snapshot", AsyncMock(return_value={"activity": {"rows": []}}))
    return factory, engine, connection


@pytest.mark.parametrize("target", ["elsewhere", "5433", "another_database"])
def test_rejects_mismatched_admin_target(target: str) -> None:
    host, port, database = "localhost", "5432", "test"
    if target == "elsewhere":
        host = target
    elif target == "5433":
        port = target
    else:
        database = target
    with pytest.raises(ValueError, match="observer must match"):
        diagnostic.observer_url(
            {
                **ENV,
                "TIEWTRADE_TEST_ADMIN_URL": f"postgresql+asyncpg://admin:private@{host}:{port}/{database}",
            }
        )


def test_allowlist_excludes_private_fields_and_caps_rows() -> None:
    rows = [
        {"pid": i, "query": "private", "secret": "private", "total_rows": 100} for i in range(100)
    ]
    result = diagnostic.allowlisted_rows(rows, ("pid",))
    assert result["truncated"] is True
    assert len(result["rows"]) == diagnostic.MAX_ROWS
    assert "private" not in json.dumps(result)


async def test_read_only_setup_and_disposal(observer: Any, tmp_path: Path) -> None:
    factory, engine, connection = observer
    path = tmp_path / "report.json"
    async with diagnostic.observe(path, ENV):
        pass
    options = factory.call_args.kwargs
    assert options["connect_args"]["server_settings"]["default_transaction_read_only"] == "on"
    assert options["hide_parameters"] is True
    connection.close.assert_awaited_once()
    engine.dispose.assert_awaited_once()
    report = json.loads(path.read_text())
    assert report["status"] == "Captured" and report["samples"]
    assert "private" not in path.read_text()


@pytest.mark.parametrize("failure", ["connect", "snapshot", "close", "dispose"])
async def test_observer_error_preserves_original_failure(
    observer: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, failure: str
) -> None:
    _, engine, connection = observer
    if failure == "snapshot":
        monkeypatch.setattr(diagnostic, "snapshot", AsyncMock(side_effect=ValueError("private")))
    else:
        owner = connection if failure == "close" else engine
        getattr(owner, failure).side_effect = ValueError("private")
    path = tmp_path / "report.json"
    primary = AssertionError("original assertion")
    with pytest.raises(AssertionError) as caught:
        async with diagnostic.observe(path, ENV):
            raise primary
    assert caught.value is primary
    report = json.loads(path.read_text())
    assert report["status"] == "Incomplete" and report["errors"] == ["ValueError"]
    assert report["test_error"] == "AssertionError"
    assert "private" not in path.read_text() and "original assertion" not in path.read_text()
    engine.dispose.assert_awaited_once()


async def test_cancellation_preserved_and_resources_closed(observer: Any, tmp_path: Path) -> None:
    _, engine, connection = observer
    path = tmp_path / "report.json"
    primary = asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError) as caught:
        async with diagnostic.observe(path, ENV):
            raise primary
    assert caught.value is primary
    assert json.loads(path.read_text())["test_error"] == "CancelledError"
    connection.close.assert_awaited_once()
    engine.dispose.assert_awaited_once()


async def test_report_write_error_does_not_mask_failure(observer: Any, tmp_path: Path) -> None:
    primary = AssertionError("original")
    with (
        pytest.warns(RuntimeWarning, match="report unavailable"),
        pytest.raises(AssertionError) as caught,
    ):
        async with diagnostic.observe(tmp_path, ENV):
            raise primary
    assert caught.value is primary


async def test_collection_sample_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(diagnostic, "INTERVAL", 0)
    monkeypatch.setattr(diagnostic, "snapshot", AsyncMock(return_value={}))
    report: dict[str, Any] = {"samples": [], "errors": []}
    ready = asyncio.Event()
    await diagnostic.collect(AsyncMock(), report, ready)
    assert ready.is_set() and len(report["samples"]) == diagnostic.MAX_SAMPLES
    assert report["observation_limit_reached"] is True


async def test_snapshot_uses_only_read_only_bounded_views() -> None:
    connection = AsyncMock()
    connection.begin = MagicMock()
    connection.execute.return_value = Mock(mappings=Mock(return_value=[]))
    result = await diagnostic.snapshot(connection)
    queries = [str(call.args[0]) for call in connection.execute.call_args_list]
    assert queries[:2] == ["SET TRANSACTION READ ONLY", "SET LOCAL statement_timeout='100ms'"]
    assert "LIMIT 64" in queries[2] and "LIMIT 64" in queries[3]
    assert "pg_blocking_pids" in queries[2]
    assert result["views_sampled_separately"] is True
    assert result["activity"]["rows"] == result["locks"]["rows"] == []


async def test_collection_time_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(diagnostic, "monotonic", Mock(side_effect=[0, diagnostic.SECONDS + 1]))
    report: dict[str, Any] = {"samples": [], "errors": []}
    ready = asyncio.Event()
    await diagnostic.collect(AsyncMock(), report, ready)
    assert ready.is_set() and report["samples"] == []
    assert report["observation_limit_reached"] is True


async def test_cleanup_cancellation_cannot_mask_primary(observer: Any, tmp_path: Path) -> None:
    _, engine, connection = observer
    connection.close.side_effect = asyncio.CancelledError()
    primary = AssertionError("original")
    path = tmp_path / "report.json"
    with pytest.raises(AssertionError) as caught:
        async with diagnostic.observe(path, ENV):
            raise primary
    assert caught.value is primary
    assert json.loads(path.read_text())["errors"] == ["CancelledError"]
    engine.dispose.assert_awaited_once()
