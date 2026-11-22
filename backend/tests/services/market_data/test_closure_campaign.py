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
from tiewtrade.infra.indicators.scheduling import POLL_SECONDS
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
