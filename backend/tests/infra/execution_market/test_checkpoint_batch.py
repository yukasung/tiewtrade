"""Real PostgreSQL checkpoint batching preserves authority and whole-transaction rollback."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market.profile_checkpoint_fixture import checkpoint_snapshot, prepare
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.db.errors import DuplicateValueError, NotPermittedError, ValueRejectedError
from tiewtrade.infra.db.session import UserSession
from tiewtrade.infra.paper_orders.codec import state_from_payload
from tiewtrade.infra.paper_orders.matching_storage import persist_checkpoint


@dataclass
class CheckpointFixture:
    owner: UUID
    wallet: UUID
    operation: dict[str, Any]


@pytest.fixture
async def checkpoint_fixture(
    tmp_path: Path, engine_engine: AsyncEngine
) -> AsyncIterator[CheckpointFixture]:
    path = tmp_path / "fixture.json"
    await prepare(path)
    document = json.loads(path.read_text())
    fixture = CheckpointFixture(
        UUID(document["owner"]), UUID(document["wallet"]), document["operations"][0]
    )
    try:
        yield fixture
    finally:
        # Owner-local schedule cleanup only; financial/audit/evidence facts remain.
        async with user_session(engine_engine, fixture.owner, role=DatabaseRole.ENGINE) as session:
            await session.execute("""UPDATE paper_order_dispatch SET state='TERMINAL',
              worker=NULL,claim_id=NULL,lease_until=NULL""")


async def persist(session: UserSession, fixture: CheckpointFixture) -> None:
    value = fixture.operation
    await persist_checkpoint(
        session,
        wallet_id=fixture.wallet,
        state=state_from_payload(value["state"]),
        anchor_order_id=UUID(value["order"]),
        event_kind=value["kind"],
        decision_kind=value["decision"],
        occurred_at=datetime.fromisoformat(value["at"]),
        decision_id=UUID(value["id"]),
    )


@pytest.mark.parametrize(
    "table",
    [
        "paper_order_events",
        "paper_order_projections",
        "paper_reservations",
        "paper_order_activity",
        "paper_wallet_state",
        "audit_events",
    ],
)
async def test_each_internal_write_and_outer_audit_failure_roll_back_all_state(
    checkpoint_fixture: CheckpointFixture,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    table: str,
) -> None:
    fixture = checkpoint_fixture
    async with user_session(engine_engine, fixture.owner, role=DatabaseRole.ENGINE) as session:
        before = await checkpoint_snapshot(session)
    name = "checkpoint_test_" + uuid4().hex
    async with migrator_engine.begin() as connection:
        await connection.execute(
            text(f"""CREATE FUNCTION public.{name}() RETURNS trigger
          LANGUAGE plpgsql AS $$ BEGIN
              IF current_setting('tiewtrade.test_checkpoint_failpoint',true)=TG_ARGV[0] THEN
            RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='controlled checkpoint failure';
          END IF; RETURN NEW; END $$""")
        )
        await connection.execute(
            text(f"""CREATE TRIGGER {name} AFTER INSERT OR UPDATE
              ON public.{table} FOR EACH ROW EXECUTE FUNCTION public.{name}('{table}')""")
        )
    try:
        with pytest.raises(ValueRejectedError):
            async with user_session(
                engine_engine, fixture.owner, role=DatabaseRole.ENGINE
            ) as session:
                await session.execute(
                    "SELECT set_config('tiewtrade.test_checkpoint_failpoint',:value,true)",
                    {"value": table},
                )
                await persist(session, fixture)
        async with user_session(engine_engine, fixture.owner, role=DatabaseRole.ENGINE) as session:
            assert await checkpoint_snapshot(session) == before
    finally:
        async with migrator_engine.begin() as connection:
            await connection.execute(text(f"DROP TRIGGER {name} ON public.{table}"))
            await connection.execute(text(f"DROP FUNCTION public.{name}()"))


@pytest.mark.parametrize(
    "corruption",
    [
        "wallet",
        "episode",
        "order",
        "base",
        "sequence",
        "revision",
        "payload_owner",
        "rows_identity",
        "negative_reservation",
        "rows_shape",
        "disabled_writer",
    ],
)
async def test_function_rechecks_bound_identity_metadata_and_writer_scope(
    checkpoint_fixture: CheckpointFixture,
    engine_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
    corruption: str,
) -> None:
    fixture = checkpoint_fixture
    async with user_session(engine_engine, fixture.owner, role=DatabaseRole.ENGINE) as session:
        before = await checkpoint_snapshot(session)
    original = UserSession.execute

    async def execute(self: UserSession, statement: str, parameters: Any = None) -> Any:
        if "SELECT public.paper_persist_checkpoint_v1" in statement:
            parameters = dict(parameters)
            if corruption in {"wallet", "episode", "order"}:
                parameters[corruption] = uuid4()
            elif corruption in {"sequence", "revision"}:
                parameters[corruption] += 1
            elif corruption == "base":
                parameters["base"] = "ETH"
            elif corruption == "payload_owner":
                value = json.loads(parameters["payload"])
                value["matching"]["owner"] = str(uuid4())
                parameters["payload"] = json.dumps(value)
            elif corruption in {"rows_identity", "negative_reservation", "rows_shape"}:
                rows = json.loads(parameters["rows"])
                if corruption == "rows_identity":
                    rows[0]["order_id"] = str(uuid4())
                elif corruption == "negative_reservation":
                    rows[0]["reserved_quote"] = "-1"
                else:
                    rows = {}
                parameters["rows"] = json.dumps(rows)
            else:
                await original(self, "SELECT set_config('tiewtrade.paper_writer_version','',true)")
        return await original(self, statement, parameters)

    monkeypatch.setattr(UserSession, "execute", execute)
    error = NotPermittedError if corruption == "disabled_writer" else ValueRejectedError
    with pytest.raises(error):
        async with user_session(engine_engine, fixture.owner, role=DatabaseRole.ENGINE) as session:
            await persist(session, fixture)
    async with user_session(engine_engine, fixture.owner, role=DatabaseRole.ENGINE) as session:
        assert await checkpoint_snapshot(session) == before


async def test_duplicate_decision_does_not_duplicate_effects_or_audit(
    checkpoint_fixture: CheckpointFixture,
    engine_engine: AsyncEngine,
) -> None:
    fixture = checkpoint_fixture
    async with user_session(engine_engine, fixture.owner, role=DatabaseRole.ENGINE) as session:
        await persist(session, fixture)
    async with user_session(engine_engine, fixture.owner, role=DatabaseRole.ENGINE) as session:
        before = await checkpoint_snapshot(session)
    with pytest.raises(DuplicateValueError):
        async with user_session(engine_engine, fixture.owner, role=DatabaseRole.ENGINE) as session:
            await persist(session, fixture)
    async with user_session(engine_engine, fixture.owner, role=DatabaseRole.ENGINE) as session:
        assert await checkpoint_snapshot(session) == before


async def test_batch_has_only_engine_invoker_rights_and_fixed_search_path(
    migrator_engine: AsyncEngine,
) -> None:
    async with migrator_engine.connect() as connection:
        row = (
            await connection.execute(
                text("""SELECT p.prosecdef,p.provolatile::text AS provolatile,p.proconfig,
          EXISTS(SELECT 1 FROM aclexplode(p.proacl) a WHERE a.grantee=0
            AND a.privilege_type='EXECUTE') public_execute
          FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
          WHERE n.nspname='public' AND p.proname='paper_persist_checkpoint_v1'""")
            )
        ).one()
        assert not row.prosecdef and row.provolatile == "v" and not row.public_execute
        assert row.proconfig == ["search_path=pg_catalog"]
        for role in ["engine", "api", "market_data", "engine_scan"]:
            allowed: bool = (
                await connection.execute(
                    text("""SELECT has_function_privilege(
              :role,(SELECT oid FROM pg_proc
                WHERE proname='paper_persist_checkpoint_v1'),'EXECUTE')"""),
                    {"role": "tiewtrade_" + role},
                )
            ).scalar_one()
            assert allowed is (role == "engine")
