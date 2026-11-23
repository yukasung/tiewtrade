"""Campaign scheduling only: real venue/PG acceptance is never mocked by these checks."""

import asyncio
import json
import os
from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market import profile_candle_closure as profile
from tiewtrade.infra.db.errors import DatabaseLockTimeoutError, DatabaseTimeoutError
from tiewtrade.infra.indicators.scheduling import POLL_SECONDS, CoalescingBusyError
from tiewtrade.services.indicator_builder.attempt import AttemptResult, AttemptStatus


@pytest.mark.parametrize(
    "audit_url",
    [
        "postgresql+asyncpg://postgres@127.0.0.1/tiewtrade_e2e_owner",
        "postgresql+asyncpg://postgres@remote.example/tiewtrade_e2e_closure_campaign_test",
        "postgresql+asyncpg://postgres@127.0.0.1/tiewtrade_e2e_closure_campaign_other",
    ],
)
def test_campaign_guard_rejects_owner_remote_or_different_audit_database(
    monkeypatch: pytest.MonkeyPatch, audit_url: str
) -> None:
    for key in tuple(os.environ):
        if key.startswith("TIEWTRADE_DATABASE_URL_"):
            monkeypatch.delenv(key)
    monkeypatch.setenv(
        "TIEWTRADE_DATABASE_URL_MIGRATOR",
        "postgresql+asyncpg://migrator@127.0.0.1/tiewtrade_e2e_closure_campaign_test",
    )
    monkeypatch.setenv("TIEWTRADE_TEST_ADMIN_URL", audit_url)
    monkeypatch.setenv("TIEWTRADE_CANDLE_CLOSURE_ENABLED", "1")
    with pytest.raises(RuntimeError):
        profile.guard()


@pytest.mark.parametrize("outcome", [AttemptStatus.SUPERSEDED, AttemptStatus.NO_JOB])
async def test_preparation_rechecks_real_authority_after_safe_outcomes(
    monkeypatch: pytest.MonkeyPatch,
    outcome: AttemptStatus,
) -> None:
    heads = AsyncMock(side_effect=[False, True])
    coalesce = AsyncMock()
    attempt = AsyncMock(return_value=AttemptResult(outcome))
    sleep = AsyncMock()
    monkeypatch.setattr(profile, "fresh_heads", heads)
    monkeypatch.setattr(profile, "coalesce_jobs", coalesce)
    monkeypatch.setattr(profile, "run_attempt", attempt)
    monkeypatch.setattr(asyncio, "sleep", sleep)
    report: dict[str, Any] = {}
    builder, api = cast(AsyncEngine, None), cast(AsyncEngine, None)
    await profile.prepare_heads(builder, api, report)
    assert report["builds"] == [outcome.value]
    assert heads.await_count == 2 and coalesce.await_count == attempt.await_count == 1
    if outcome is AttemptStatus.NO_JOB:
        sleep.assert_awaited_once_with(POLL_SECONDS)
    else:
        sleep.assert_not_awaited()


@pytest.mark.parametrize("outcome", [AttemptStatus.ORPHANED, AttemptStatus.FAILED_NUMERIC])
async def test_preparation_stops_on_ownership_or_numeric_failure(
    monkeypatch: pytest.MonkeyPatch,
    outcome: AttemptStatus,
) -> None:
    monkeypatch.setattr(profile, "fresh_heads", AsyncMock(return_value=False))
    monkeypatch.setattr(profile, "coalesce_jobs", AsyncMock())
    attempt = AsyncMock(return_value=AttemptResult(outcome))
    monkeypatch.setattr(profile, "run_attempt", attempt)
    with pytest.raises(RuntimeError, match="requires recovery"):
        await profile.prepare_heads(cast(AsyncEngine, None), cast(AsyncEngine, None), {})
    attempt.assert_awaited_once()


async def test_api_rejection_keeps_status_without_response_secrets() -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(503, text="response-secret")),
        base_url="http://localhost:5173",
    ) as client:
        with pytest.raises(profile.ApiRejectedError) as caught:
            await profile.request(client, "/auth/register", {"password": "request-secret"})
    assert caught.value.path == "/auth/register" and caught.value.status == 503
    assert "secret" not in str(caught.value)


async def test_failure_report_is_safe_and_cannot_restart_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def failed_campaign(report: dict[str, Any]) -> None:
        report["phase"] = "OWNED_API_SETUP"
        raise profile.ApiRejectedError("/auth/register", 503) from RuntimeError("private-secret")

    monkeypatch.setattr(profile, "guard", lambda: None)
    monkeypatch.setattr(profile, "campaign", failed_campaign)
    output = tmp_path / "campaign.json"
    await profile.main(output, "a" * 64)
    encoded = output.read_text()
    report = json.loads(encoded)
    assert report["result"] == "PARTIAL"
    assert report["api_rejection"] == {"path": "/auth/register", "status": 503}
    assert report["failure_frames"][-1]["function"] == "failed_campaign"
    assert "private-secret" not in encoded
    with pytest.raises(FileExistsError):
        await profile.main(output, "a" * 64)
    assert output.read_text() == encoded


async def test_nested_failure_report_keeps_child_locations_without_private_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def failed_source() -> Exception:
        try:
            raise TimeoutError("private-message") from RuntimeError("private-cause")
        except TimeoutError as error:
            error.add_note("private-note")
            return error

    async def failed_campaign(report: dict[str, Any]) -> None:
        del report
        raise ExceptionGroup(
            "private-outer", [failed_source(), ExceptionGroup("private-inner", [failed_source()])]
        )

    monkeypatch.setattr(profile, "guard", lambda: None)
    monkeypatch.setattr(profile, "campaign", failed_campaign)
    output = tmp_path / "campaign.json"
    await profile.main(output, "a" * 64)
    encoded = output.read_text()
    report = json.loads(encoded)
    tree = report["failure_tree"]
    assert report["failure_type"] == "ExceptionGroup"
    assert tree["truncated"] is False
    assert [(node["path"], node["type"]) for node in tree["nodes"]] == [
        ([], "ExceptionGroup"),
        ([0], "TimeoutError"),
        ([1], "ExceptionGroup"),
        ([1, 0], "TimeoutError"),
    ]
    for node in (tree["nodes"][1], tree["nodes"][3]):
        assert node["frames"] == [
            {
                "file": "test_closure_campaign.py",
                "function": "failed_source",
                "line": failed_source.__code__.co_firstlineno + 2,
            }
        ]
    assert "private-" not in encoded
    assert str(Path(__file__).parent) not in encoded


@pytest.mark.parametrize(
    "shape,size,truncated",
    [("wide", 31, False), ("wide", 40, True), ("deep", 8, False), ("deep", 12, True)],
)
def test_failure_tree_bounds_group_size_and_depth(shape: str, size: int, truncated: bool) -> None:
    error: Exception = RuntimeError("private-leaf")
    expected_paths: list[tuple[int, ...]]
    if shape == "wide":
        error = ExceptionGroup("private-group", [error] * size)
        expected_paths = [()] + [(index,) for index in range(min(size, 31))]
    else:
        for _ in range(size):
            error = ExceptionGroup("private-group", [error])
        expected_paths = [(0,) * depth for depth in range(min(size, 8) + 1)]
    tree = profile._failure_tree(error)
    assert tree["truncated"] is truncated
    assert [node["path"] for node in tree["nodes"]] == expected_paths
    assert "private-" not in json.dumps(tree)


def test_failure_frames_keep_only_the_last_sixteen_locations() -> None:
    def recurse(depth: int) -> None:
        if depth:
            recurse(depth - 1)
        else:
            raise RuntimeError("private-message")

    with pytest.raises(RuntimeError) as caught:
        recurse(30)
    tree = profile._failure_tree(caught.value)
    assert tree["truncated"] is True
    assert tree["nodes"][0]["frames_truncated"] is True
    frames = tree["nodes"][0]["frames"]
    assert len(frames) == 16
    assert all(frame["function"] == "recurse" for frame in frames)


async def test_cancellation_propagates_and_keeps_exclusive_incomplete_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def cancelled_campaign(report: dict[str, Any]) -> None:
        del report
        raise asyncio.CancelledError("private-cancellation")

    monkeypatch.setattr(profile, "guard", lambda: None)
    monkeypatch.setattr(profile, "campaign", cancelled_campaign)
    output = tmp_path / "campaign.json"
    with pytest.raises(asyncio.CancelledError):
        await profile.main(output, "a" * 64)
    assert json.loads(output.read_text()) == {
        "candidate_fingerprint": "a" * 64,
        "result": "INCOMPLETE",
    }
    with pytest.raises(FileExistsError):
        await profile.main(output, "a" * 64)


async def test_preparation_waits_after_lock_contention_without_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(profile, "fresh_heads", AsyncMock(side_effect=[False, True]))
    coalesce = AsyncMock(side_effect=CoalescingBusyError())
    attempt = AsyncMock()
    sleep = AsyncMock()
    monkeypatch.setattr(profile, "coalesce_jobs", coalesce)
    monkeypatch.setattr(profile, "run_attempt", attempt)
    monkeypatch.setattr(asyncio, "sleep", sleep)
    await profile.prepare_heads(cast(AsyncEngine, None), cast(AsyncEngine, None), {})
    sleep.assert_awaited_once_with(POLL_SECONDS)
    attempt.assert_not_awaited()


@pytest.mark.parametrize("failure", [DatabaseTimeoutError, DatabaseLockTimeoutError])
async def test_preparation_does_not_retry_statement_or_pool_timeout(
    monkeypatch: pytest.MonkeyPatch,
    failure: type[DatabaseTimeoutError],
) -> None:
    monkeypatch.setattr(profile, "fresh_heads", AsyncMock(return_value=False))
    coalesce = AsyncMock(side_effect=failure())
    monkeypatch.setattr(profile, "coalesce_jobs", coalesce)
    with pytest.raises(DatabaseTimeoutError):
        await profile.prepare_heads(cast(AsyncEngine, None), cast(AsyncEngine, None), {})
    coalesce.assert_awaited_once()
