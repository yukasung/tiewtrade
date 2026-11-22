"""Local protocol matrix; deployment inventory still requires actual operator evidence."""

import asyncio
import json
import os
import sys
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market.test_candle_closure_proof import INVENTORY, ready
from tests.infra.execution_market.test_process_recovery import marker
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.db.session import market_data_session
from tiewtrade.infra.market_data import candle_closure as closure

pytestmark = pytest.mark.usefixtures("internal_database")

WRITER = """
import asyncio, sys
from uuid import UUID
from tests.core.test_candle_closure import recorded
from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.infra.db.errors import NotPermittedError
from tiewtrade.infra.db.session import market_data_session
from tiewtrade.infra.indicators.source import begin_source_write
from tiewtrade.infra.market_data import candle_closure as closure
from tiewtrade.infra.market_data.candle_preview import PreviewLease

async def run():
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        try:
            async with market_data_session(engine) as session:
                if sys.argv[3] == "v1":
                    candidate, _, _ = recorded("BTCUSDT")
                    proof = await closure.record_candidate(
                        session, PreviewLease(UUID(sys.argv[1]), int(sys.argv[2])),
                        candidate.observation)
                    assert proof is not None
                else:
                    await begin_source_write(session)
                    await session.execute(
                        "UPDATE market_candles SET last_checked_at=clock_timestamp()")
        except NotPermittedError:
            print("REJECTED", flush=True)
        else:
            print("COMMITTED", flush=True)
    finally:
        await engine.dispose()
asyncio.run(run())
"""


async def reject_activation(migrator: AsyncEngine, inventory: dict[str, object]) -> None:
    async with migrator.connect() as connection:
        before = tuple(
            (await connection.execute(text("SELECT * FROM market_candle_closure_control"))).one()
        )
    with pytest.raises(DBAPIError, match="activation evidence incomplete"):
        async with migrator.begin() as connection:
            await connection.execute(
                text("SELECT activate_candle_closure(true,CAST(:i AS jsonb))"),
                {"i": json.dumps(inventory)},
            )
    async with migrator.connect() as connection:
        assert (
            tuple(
                (
                    await connection.execute(text("SELECT * FROM market_candle_closure_control"))
                ).one()
            )
            == before
        )


@pytest.mark.parametrize(
    "field",
    ["legacy_writers_drained", "legacy_restart_disabled", "readers_compatible", "paper_only"],
)
@pytest.mark.parametrize("value", [None, False, "true"])
async def test_activation_requires_each_typed_attestation(
    migrator_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
) -> None:
    async with ready(migrator_engine, monkeypatch):
        inventory = dict(INVENTORY)
        if value is None:
            inventory.pop(field)
        else:
            inventory[field] = value
        await reject_activation(migrator_engine, inventory)


@pytest.mark.parametrize("candidate", [None, "", "g" * 40, "a" * 39])
async def test_activation_rejects_invalid_candidate_identity(
    migrator_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
    candidate: str | None,
) -> None:
    async with ready(migrator_engine, monkeypatch):
        inventory = dict(INVENTORY)
        if candidate is None:
            inventory.pop("candidate_sha")
        else:
            inventory["candidate_sha"] = candidate
        await reject_activation(migrator_engine, inventory)


async def test_activation_rejects_unready_source_proof(
    migrator_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with ready(migrator_engine, monkeypatch):
        async with migrator_engine.begin() as connection:
            await connection.execute(text("SELECT begin_indicator_source_write()"))
            await connection.execute(
                text("UPDATE indicator_rollout_control SET source_proof_state='PENDING' WHERE id=1")
            )
        await reject_activation(migrator_engine, INVENTORY)


@pytest.mark.parametrize(
    ("enabled", "writer", "outcome"),
    [(False, "legacy", b"COMMITTED"), (True, "legacy", b"REJECTED"), (True, "v1", b"COMMITTED")],
)
async def test_separate_writer_process_obeys_current_protocol(
    migrator_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
    enabled: bool,
    writer: str,
    outcome: bytes,
) -> None:
    async with ready(migrator_engine, monkeypatch) as (market, lease, _, c, _):
        if not enabled:
            async with migrator_engine.begin() as connection:
                await connection.execute(
                    text("SELECT activate_candle_closure(false, :i)"),
                    {"i": '{"admission_paused":true}'},
                )
        environment = dict(os.environ)
        if writer == "legacy":
            environment.pop("TIEWTRADE_CANDLE_CLOSURE_ENABLED", None)
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            WRITER,
            str(lease.owner),
            str(lease.epoch),
            writer,
            env=environment,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            await marker(process, outcome)
            assert await asyncio.wait_for(process.wait(), 5) == 0
            async with market_data_session(market) as session:
                row = (
                    await session.execute(
                        """SELECT finality,closure_proof_id,
                        (SELECT count(*) FROM market_candle_closure_results) AS results
                        FROM market_candles"""
                    )
                ).one()
                published = writer == "v1"
                assert row.finality == ("CLOSED" if published else "UNCONFIRMED")
                assert row.results == int(published)
                assert (row.closure_proof_id is not None) == published
            async with user_session(engine_engine, uuid4(), role=DatabaseRole.ENGINE) as session:
                if published:
                    proof = await closure.current_proof(session, c)
                    assert proof is not None and proof["id"] == row.closure_proof_id
        finally:
            if process.returncode is None:
                process.kill()
            await asyncio.wait_for(process.wait(), 5)


async def test_deactivation_requires_paused_admission_and_retains_evidence(
    migrator_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with ready(migrator_engine, monkeypatch) as (market, lease, candidate, c, _):
        async with market_data_session(market) as session:
            proof = await closure.record_candidate(session, lease, candidate.observation)
            assert proof is not None
        with pytest.raises(DBAPIError, match="pause admission before deactivation"):
            async with migrator_engine.begin() as connection:
                await connection.execute(text("SELECT activate_candle_closure(false,'{}')"))
        async with migrator_engine.begin() as connection:
            await connection.execute(
                text("SELECT activate_candle_closure(false,CAST(:i AS jsonb))"),
                {"i": json.dumps({"admission_paused": True})},
            )
        async with user_session(engine_engine, uuid4(), role=DatabaseRole.ENGINE) as session:
            with pytest.raises(closure.ClosureUnavailableError, match="protocol disabled"):
                await closure.current_proof(session, c)
            assert (
                await session.execute("SELECT id FROM market_candle_closure_results")
            ).scalar_one() == proof
            assert (
                await session.execute("SELECT closure_proof_id FROM market_candles")
            ).scalar_one() == proof
