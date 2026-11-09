"""Identity evidence must never waive a nonempty or malformed cleanup snapshot."""

import copy
import json
import os
from typing import Any

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
