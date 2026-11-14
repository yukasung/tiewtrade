"""Only proven read-only public price deadlines may be separated from pool faults."""

import asyncio
import json
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest
from sqlalchemy import text

from tests.infra.execution_market.profile_owned_pools import (
    CURRENT,
    OwnedPools,
    expected_public_read_deadline,
)
from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.infra.db.session import presented_session
from tiewtrade.services.api.app import app, lifespan
from tiewtrade.services.api.settings import PRICE_SETTINGS


def deadline_detail() -> dict[str, Any]:
    return {
        "error_type": "CancelledError",
        "sqlstate": "",
        "role": "API",
        "pool_size": 3,
        "max_overflow": 0,
        "configured_readonly": True,
        "deadline_context": "public_price_read",
        "deadline_expired": True,
        "deadline_at": 9.0,
        "monotonic": 10.0,
        "cancellation_requests": 1,
    }


def test_known_public_read_deadline() -> None:
    assert expected_public_read_deadline(deadline_detail())


async def test_missing_execution_engine_remains_a_resource_failure(tmp_path: Path) -> None:
    path = tmp_path / "no-execution-engine.json"
    with OwnedPools(path, [("API", 3, 0)]):
        engine = create_engine_for(DatabaseRole.API, pool_size=3, max_overflow=0)
        engine.sync_engine.dialect.dispatch.handle_error(
            Mock(is_disconnect=True, original_exception=OSError("PRIVATE"), engine=None)
        )
        await engine.dispose()
    result = json.loads(path.read_text())
    assert not result["passed"] and result["errors"] == {"ConnectionResourceError": 1}
    assert result["resource_errors"][0]["configured_readonly"] is False
    assert result["expected_read_deadline_cancellations"] == 0
    assert "PRIVATE" not in path.read_text()


@pytest.mark.parametrize(
    "key,value",
    [
        ("error_type", "TimeoutError"),
        ("sqlstate", "08006"),
        ("role", "ENGINE"),
        ("role", "ADMIN_OBSERVER"),
        ("pool_size", 5),
        ("max_overflow", 10),
        ("configured_readonly", False),
        ("configured_readonly", None),
        ("deadline_context", "not_observed"),
        ("deadline_expired", False),
        ("deadline_expired", None),
        ("deadline_at", 11.0),
        ("deadline_at", None),
        ("deadline_at", float("nan")),
        ("deadline_at", float("inf")),
        ("monotonic", float("nan")),
        ("monotonic", None),
        ("cancellation_requests", 0),
        ("cancellation_requests", 2),
        ("cancellation_requests", True),
    ],
)
def test_unknown_write_disconnect_or_external_cancel_is_not_expected(key: str, value: Any) -> None:
    detail = deadline_detail()
    detail[key] = value
    assert not expected_public_read_deadline(detail)
    assert not expected_public_read_deadline({})


@pytest.mark.usefixtures("internal_database")
@pytest.mark.parametrize("leak,external", [(False, False), (True, False), (False, True)])
async def test_actual_public_read_deadline_and_readonly_pool_return(
    tmp_path: Path, leak: bool, external: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    import importlib

    module = importlib.import_module("tiewtrade.services.api.app")
    original_read = module.read_public_snapshot
    readonly_observations = []
    waiting_read = asyncio.Event()
    target = None

    async def checked_read(session: Any) -> Any:
        readonly = (await session.execute("SHOW transaction_read_only")).scalar_one()
        readonly_observations.append(readonly)
        assert readonly == "on"
        if asyncio.current_task() is target:
            waiting_read.set()
        return await original_read(session)

    monkeypatch.setattr(module, "read_public_snapshot", checked_read)
    path = tmp_path / "public-read-pools.json"
    configuration = [("API", 5, 10), ("AUTH", 5, 10), ("API", 3, 0)] + [("API", 1, 0)] * 3
    # The lock belongs only to the isolated test database. This engine is outside
    # the app observer and is always disposed independently.
    locker = create_engine_for(DatabaseRole.MIGRATOR)
    loan = None
    try:
        with OwnedPools(path, configuration) as tracker:
            async with lifespan(app):
                assert PRICE_SETTINGS.query_timeout == 0.5
                async with presented_session(app.state.price_engine) as session:
                    assert (
                        await session.execute("SHOW transaction_read_only")
                    ).scalar_one() == "off"
                for name in ("api_engine", "paper_mutation_engine", "auth_engine"):
                    assert (
                        not getattr(app.state, name)
                        .get_execution_options()
                        .get("postgresql_readonly", False)
                    )
                async with locker.begin() as connection:
                    await connection.execute(
                        text("LOCK TABLE market_latest_prices IN ACCESS EXCLUSIVE MODE")
                    )
                    if external:
                        target = asyncio.create_task(app.state.price_broadcaster.read())
                        async with asyncio.timeout(5):
                            await waiting_read.wait()
                            target.cancel()
                            with pytest.raises(asyncio.CancelledError):
                                await target
                    else:
                        with pytest.raises(TimeoutError):
                            async with asyncio.timeout(5):
                                await app.state.price_broadcaster.read()
                # A new transaction must work after the canceled connection was invalidated.
                await app.state.price_broadcaster.read()
                assert readonly_observations and set(readonly_observations) == {"on"}
                async with presented_session(app.state.price_engine) as session:
                    assert (
                        await session.execute("SHOW transaction_read_only")
                    ).scalar_one() == "off"
                if leak:
                    loan = await app.state.price_engine.connect()
                tracker.begin_quiescence()
        result = json.loads(path.read_text())
        assert result["passed"] is (not leak and not external)
        if external:
            assert result["errors"]["ConnectionResourceError"] >= 1
            detail = result["resource_errors"][0]
            assert detail["deadline_expired"] is False
            assert not expected_public_read_deadline(detail)
        else:
            assert result["errors"] == {} and result["resource_errors"] == []
            assert result["expected_read_deadline_cancellations"] >= 1
            detail = result["expected_read_deadlines"][0]
            assert expected_public_read_deadline(detail)
        assert detail["task_id"] is not None
        assert any(frame["function"] == "public_read" for frame in detail["await_chain"])
        assert "LOCK TABLE" not in path.read_text() and "postgresql+asyncpg" not in path.read_text()
        assert CURRENT.get() is None
    finally:
        if loan is not None:
            await loan.invalidate()
            await loan.close()
        await locker.dispose()
