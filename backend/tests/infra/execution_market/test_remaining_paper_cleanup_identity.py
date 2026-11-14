"""Identity evidence must never waive a nonempty or malformed cleanup snapshot."""

import asyncio
import copy
import json
import os
from typing import Any
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from tests.infra.execution_market import remaining_paper_campaign as campaign
from tiewtrade.infra.db import DatabaseRole, create_engine_for


def empty() -> dict[str, Any]:
    return {
        "observed_at": "2026-11-09T00:00:00+00:00",
        "connections": 0,
        "backends": [],
        "advisory_locks": 0,
    }


def test_empty_only_passes_without_wait_or_retry() -> None:
    assert campaign.cleanup_passed(empty())
    value = empty()
    value["advisory_locks"] = 1
    assert not campaign.cleanup_passed(value)
    value = empty()
    value.update(
        connections=1,
        backends=[
            {
                "pid": 123,
                "role": "tiewtrade_engine",
                "state": "idle",
                "backend_type": "client backend",
                "transaction_open": False,
            }
        ],
    )
    assert not campaign.cleanup_passed(value)


@pytest.mark.parametrize(
    "change",
    [
        "missing",
        "timestamp",
        "naive",
        "count",
        "bool",
        "negative",
        "identity_count",
        "extra",
        "private",
        "pid",
        "role",
        "duplicate",
    ],
)
def test_malformed_identity_cannot_pass(change: str) -> None:
    value = empty()
    if change == "missing":
        del value["backends"]
    elif change == "timestamp":
        value["observed_at"] = "bad"
    elif change == "naive":
        value["observed_at"] = "2026-11-09T00:00:00"
    elif change == "count":
        value["connections"] = "0"
    elif change == "bool":
        value["connections"] = False
    elif change == "negative":
        value["advisory_locks"] = -1
    elif change == "identity_count":
        value["connections"] = 1
    elif change == "extra":
        value["private"] = "not allowed"
    else:
        row = {
            "pid": 123,
            "role": "tiewtrade_engine",
            "state": "idle",
            "backend_type": "client backend",
            "transaction_open": False,
        }
        if change == "private":
            row["query"] = "not allowed"
        elif change == "pid":
            row["pid"] = False
        elif change == "role":
            row["role"] = None
        value.update(connections=1, backends=[row])
        if change == "duplicate":
            value.update(connections=2, backends=[row, copy.deepcopy(row)])
    with pytest.raises(ValueError):
        campaign.cleanup_passed(value)


@pytest.mark.parametrize("name", ["tiewtrade", "tiewtrade_internal20_x';--", "other"])
def test_cleanup_query_rejects_nonfixture_or_injected_target(name: str) -> None:
    with pytest.raises(ValueError):
        campaign.cleanup_query(name)


@pytest.mark.usefixtures("internal_database")
async def test_real_snapshot_counts_exact_target_backend_and_still_blocks() -> None:
    target = make_url(os.environ[DatabaseRole.MIGRATOR.url_variable]).database
    assert target is not None
    observer = create_async_engine(
        make_url(os.environ["TIEWTRADE_TEST_ADMIN_URL"]).set(database="postgres"),
        isolation_level="AUTOCOMMIT",
        hide_parameters=True,
        connect_args={"server_settings": {"default_transaction_read_only": "on"}},
    )
    peer = create_engine_for(DatabaseRole.MIGRATOR)
    try:
        async with observer.connect() as connection:

            async def document() -> Any:
                value = (
                    await connection.exec_driver_sql(campaign.cleanup_query(target))
                ).scalar_one()
                return json.loads(value) if isinstance(value, str) else value

            assert campaign.cleanup_passed(await document())
            async with peer.connect() as active:
                pid = (await active.exec_driver_sql("SELECT pg_backend_pid()")).scalar_one()
                value = await document()
                assert value["connections"] == 1
                assert value["backends"][0]["pid"] == pid
                assert value["backends"][0]["role"] == "tiewtrade_migrator"
                assert not campaign.cleanup_passed(value)
                assert "query" not in value["backends"][0]
    finally:
        await peer.dispose()
        await observer.dispose()


def autovacuum() -> dict[str, Any]:
    value = empty()
    value.update(
        connections=1,
        backends=[
            {
                "pid": 123,
                "role": None,
                "state": "active",
                "backend_type": "autovacuum worker",
                "transaction_open": True,
            }
        ],
    )
    return value


@pytest.mark.parametrize("scenario", ["transient", "persistent", "client", "lock", "malformed"])
async def test_cleanup_waits_only_for_bounded_known_maintenance(
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
) -> None:
    value = autovacuum()
    if scenario == "client":
        value["backends"][0].update(role="tiewtrade_engine", backend_type="client backend")
    elif scenario == "lock":
        value["advisory_locks"] = 1
    elif scenario == "malformed":
        value["backends"][0]["backend_type"] = "unknown"
    count = 0

    def capture(*args: Any) -> str:
        nonlocal count
        count += 1
        return json.dumps(empty() if scenario == "transient" and count == 2 else value)

    sleep = AsyncMock()
    monkeypatch.setattr(campaign, "capture", capture)
    monkeypatch.setattr(asyncio, "sleep", sleep)
    observations: list[Any] = []
    result = await campaign.capture_cleanup("tiewtrade_internal20_cleanup_test", observations)
    assert count == (2 if scenario == "transient" else 11 if scenario == "persistent" else 1)
    assert sleep.await_count == count - 1 and len(observations) == count
    if scenario == "malformed":
        with pytest.raises(ValueError):
            campaign.cleanup_passed(result)
    else:
        assert campaign.cleanup_passed(result) is (scenario == "transient")


async def test_cleanup_wait_cancellation_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(campaign, "capture", lambda *args: json.dumps(autovacuum()))
    monkeypatch.setattr(asyncio, "sleep", AsyncMock(side_effect=asyncio.CancelledError))
    observations: list[Any] = []
    with pytest.raises(asyncio.CancelledError):
        await campaign.capture_cleanup("tiewtrade_internal20_cleanup_test", observations)
    assert len(observations) == 1
