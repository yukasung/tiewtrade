"""Exact fixture changes bounds, never the lifecycle snapshot timestamp."""

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.services.indicator_builder import profile_capacity as capacity
from tests.services.indicator_builder.capacity_instrumentation import sitecustomize as clock
from tiewtrade.core.market_data import CandleWindow, Timeframe, slot_count
from tiewtrade.infra.indicators.claims import BuildClaim
from tiewtrade.infra.indicators.session import IndicatorSourceSession
from tiewtrade.infra.indicators.source import SourceFence
from tiewtrade.infra.indicators.staging import StagingSnapshot


@pytest.mark.parametrize("elapsed", [1, 30, 60, 121])
async def test_exact_bounds_preserve_real_snapshot_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, elapsed: int
) -> None:
    boundary = datetime(2026, 10, 24, 0, 0, tzinfo=UTC)
    now = boundary + timedelta(seconds=elapsed)
    original = StagingSnapshot(
        now, SourceFence(uuid4(), 1), CandleWindow(boundary, boundary + timedelta(minutes=1))
    )
    marker = tmp_path / "clock"
    marker.write_text(boundary.isoformat(), encoding="ascii")
    monkeypatch.setattr(clock, "EXACT_CLOCK_MARKER", marker)
    monkeypatch.setattr(clock, "CAPTURE_SNAPSHOT", AsyncMock(return_value=original))
    result = await clock.capture_snapshot(
        cast(IndicatorSourceSession, object()),
        cast(BuildClaim, SimpleNamespace(timeframe=Timeframe.M1)),
    )
    assert result.as_of == now
    assert result.fence == original.fence
    assert result.calculation.end == boundary
    assert slot_count(result.calculation, Timeframe.M1) == 525600
    # The scan's existing deadline calculation consumes real elapsed time.
    assert (boundary + timedelta(seconds=120) - result.as_of).total_seconds() == 120 - elapsed


async def test_without_marker_snapshot_is_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    snapshot = object()
    monkeypatch.setattr(clock, "EXACT_CLOCK_MARKER", tmp_path / "absent")
    monkeypatch.setattr(clock, "CAPTURE_SNAPSHOT", AsyncMock(return_value=snapshot))
    assert (
        await clock.capture_snapshot(
            cast(IndicatorSourceSession, object()), cast(BuildClaim, object())
        )
        is snapshot
    )


@pytest.mark.parametrize("outcome", ["ready", "failed", "cancelled"])
async def test_exact_fixture_retry_and_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, outcome: str
) -> None:
    boundary = datetime(2026, 10, 24, tzinfo=UTC)
    definition = "CREATE FUNCTION indicator_calculation_bounds() IMMUTABLE AS $$BEGIN\nEND$$"
    statements: list[str] = []
    polls = 0

    async def execute(statement: object, *args: object) -> MagicMock:
        nonlocal polls
        sql = str(statement)
        statements.append(sql)
        result = MagicMock()
        if (
            sql == "SELECT clock_timestamp()"
            or "SELECT max(end_at)" in sql
            or "SELECT g.calculation_end" in sql
        ):
            result.scalar_one.return_value = boundary
        elif "SELECT count(*)" in sql:
            result.scalar_one.return_value = 525600
        elif "pg_get_functiondef" in sql:
            result.scalars.return_value = [definition]
        elif "SELECT g.id,g.calculation_start" in sql:
            polls += 1
            if polls == 2 and outcome == "cancelled":
                raise asyncio.CancelledError
            result.mappings.return_value.one_or_none.return_value = (
                {"calculation_start": boundary - timedelta(days=365), "calculation_end": boundary}
                if polls == 2 and outcome == "ready"
                else None
            )
        elif "SELECT id,status,attempts_used" in sql:
            result.mappings.return_value.one.return_value = {
                "id": 1,
                "status": "FAILED_TRANSIENT" if polls == 2 and outcome == "failed" else "QUEUED",
                "attempts_used": 1,
                "retry_not_before": boundary,
                "failure_category": "TRANSIENT",
                "failure_reason": "TRANSIENT",
                "observed": boundary,
            }
        else:
            result.scalar_one.return_value = 1
        return result

    connection = MagicMock()
    connection.execute = AsyncMock(side_effect=execute)
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=connection)
    context.__aexit__ = AsyncMock(return_value=False)
    engine = MagicMock(spec=AsyncEngine)
    engine.connect.return_value = context
    engine.begin.return_value = context
    monkeypatch.setattr(capacity, "market_data_session", lambda _: context)
    docker = AsyncMock()
    monkeypatch.setattr(capacity, "docker", docker)
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    marker = tmp_path / "clock"
    if outcome == "ready":
        result = await capacity.prepare_exact_r2_7_generation(engine, engine, "worker", marker)
        assert result["logical_slots"] == 525600
    else:
        error = asyncio.CancelledError if outcome == "cancelled" else RuntimeError
        with pytest.raises(error):
            await capacity.prepare_exact_r2_7_generation(engine, engine, "worker", marker)
    assert polls == 2  # QUEUED with a previous failure must remain retryable.
    assert not marker.exists()
    assert statements[-3:] == [
        definition,
        "DROP FUNCTION capacity_indicator_clock()",
        "DROP TABLE capacity_indicator_clock_state",
    ]
    docker.assert_any_await("stop", "--time", "130", "worker", timeout=140)
