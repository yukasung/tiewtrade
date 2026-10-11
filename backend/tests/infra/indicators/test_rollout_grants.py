"""D6 partial installs reject activation without preventing safe pause."""

from collections.abc import Sequence
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from alembic.util import load_python_file
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.indicators.test_claims import prepared as prepared
from tests.infra.indicators.test_rollout import synthetic_heads
from tests.infra.indicators.test_source import active as active

MIGRATION = load_python_file(
    Path(__file__).resolve().parents[3] / "migrations/versions", "0023_indicator_rollout.py"
)


async def test_privilege_manifest_covers_installed_feature_grants(
    migrator_engine: AsyncEngine,
) -> None:
    # Independent catalog inventory catches omissions from the generated fault matrix.
    async with migrator_engine.connect() as c:
        observed = set(
            (
                await c.execute(
                    text("""SELECT r.rolname,p.oid,'EXECUTE'
          FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
          CROSS JOIN pg_roles r WHERE n.nspname='public' AND p.proname LIKE '%indicator%'
          AND r.rolname IN ('tiewtrade_api','tiewtrade_market_data','tiewtrade_indicator_builder')
          AND has_function_privilege(r.oid,p.oid,'EXECUTE')
          UNION ALL SELECT r.rolname,c.oid,'SELECT' FROM pg_class c
          JOIN pg_namespace n ON n.oid=c.relnamespace CROSS JOIN pg_roles r
          WHERE n.nspname='public' AND c.relkind IN ('r','p','v')
          AND (c.relname LIKE 'indicator_%' OR c.relname='market_candles')
          AND r.rolname IN ('tiewtrade_api','tiewtrade_market_data','tiewtrade_indicator_builder')
          AND has_table_privilege(r.oid,c.oid,'SELECT')""")
                )
            ).all()
        )
        # F-09's pre-existing candle SELECT is not an F-11 grant.
        observed = {
            row
            for row in observed
            if not (
                row[0] == "tiewtrade_market_data"
                and row[2] == "SELECT"
                and row[1]
                == (await c.execute(text("SELECT 'market_candles'::regclass::oid"))).scalar_one()
            )
        }
        required = set()
        for role, name, privilege in MIGRATION.required_privileges():
            resolver = "to_regprocedure" if privilege == "EXECUTE" else "to_regclass"
            oid: int = (
                await c.execute(text(f"SELECT {resolver}(:name)::oid"), {"name": "public." + name})
            ).scalar_one()
            required.add((role, oid, privilege))
        assert required == observed


@pytest.mark.parametrize("role,name,privilege", MIGRATION.required_privileges())
async def test_missing_grant_preserves_state_pause_and_restored_activation(
    prepared: None, migrator_engine: AsyncEngine, role: str, name: str, privilege: str
) -> None:
    await synthetic_heads(migrator_engine)
    async with migrator_engine.connect() as c:
        transaction = await c.begin()
        try:
            kind = "FUNCTION" if privilege == "EXECUTE" else "TABLE"
            await c.execute(text(f"REVOKE {privilege} ON {kind} {name} FROM {role}"))
            allowed: bool = (
                await c.execute(
                    text(f"SELECT has_{kind.lower()}_privilege(:role,:name,:privilege)"),
                    {"role": role, "name": name, "privilege": privilege},
                )
            ).scalar_one()
            assert not allowed
            state = text("SELECT to_jsonb(c) FROM indicator_rollout_control c")
            before: dict[str, Any] = (await c.execute(state)).scalar_one()
            command = text(
                "SELECT transition_indicator_rollout('PREPARING',CAST(:epoch AS uuid),'PREPARED')"
            )
            args = {"epoch": before["rollout_epoch"]}
            rejected: dict[str, Any] = (await c.execute(command, args)).scalar_one()
            assert rejected["result"] == "POLICY_UNSUPPORTED"
            after: dict[str, Any] = (await c.execute(state)).scalar_one()
            assert after == before
            pause = await c.begin_nested()
            result: dict[str, Any] = (
                await c.execute(
                    text(
                        "SELECT transition_indicator_rollout("
                        "'PREPARING',CAST(:epoch AS uuid),'PAUSED')"
                    ),
                    args,
                )
            ).scalar_one()
            assert result["result"] == "APPLIED"
            await pause.rollback()
            await c.execute(text(f"GRANT {privilege} ON {kind} {name} TO {role}"))
            result = (await c.execute(command, args)).scalar_one()
            assert result["result"] == "APPLIED"
            replay: dict[str, Any] = (await c.execute(command, args)).scalar_one()
            assert replay["result"] == "ALREADY_APPLIED" and replay["epoch"] == result["epoch"]
        finally:
            await transaction.rollback()


@pytest.mark.parametrize("fault", ["trigger", "control", "codec", "protocol"])
async def test_partial_control_or_trigger_fails_closed(
    prepared: None, migrator_engine: AsyncEngine, fault: str
) -> None:
    await synthetic_heads(migrator_engine)
    async with migrator_engine.connect() as c:
        transaction = await c.begin()
        try:
            epoch: UUID = (
                await c.execute(text("SELECT rollout_epoch FROM indicator_rollout_control"))
            ).scalar_one()
            if fault == "trigger":
                await c.execute(text("SELECT begin_indicator_source_maintenance()"))
                await c.execute(text("DROP TRIGGER indicator_source_rows ON market_candles"))
            elif fault == "control":
                await c.execute(text("DELETE FROM indicator_rollout_control"))
            else:
                await c.execute(text(f"UPDATE indicator_rollout_control SET {fault}_version=2"))
            state = text("SELECT to_jsonb(c) FROM indicator_rollout_control c")
            before: Sequence[dict[str, Any]] = (await c.execute(state)).scalars().all()
            attempt = await c.begin_nested()
            command = text("SELECT transition_indicator_rollout('PREPARING',:epoch,'PREPARED')")
            if fault == "control":
                with pytest.raises(DBAPIError):
                    await c.execute(command, {"epoch": epoch})
                await attempt.rollback()
            else:
                assert (await c.execute(command, {"epoch": epoch})).scalar_one()[
                    "result"
                ] == "POLICY_UNSUPPORTED"
                await attempt.commit()
            assert (await c.execute(state)).scalars().all() == before
        finally:
            await transaction.rollback()
