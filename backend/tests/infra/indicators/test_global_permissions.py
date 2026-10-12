"""Actual runtime roles cannot bypass the complete indicator function ACL surface."""

from collections.abc import Sequence

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.infra.db import DatabaseRole, create_engine_for

BUILDER = {
    "append_indicator_checkpoint",
    "claim_indicator_build_job",
    "coalesce_indicator_build_jobs",
    "gc_indicator_data",
    "heartbeat_indicator_build_claim",
    "initialize_indicator_staging",
    "publish_indicator_numeric_failure",
    "publish_indicator_ready",
    "release_indicator_build_claim",
    "retry_indicator_build_job",
    "seal_indicator_staging",
    "seed_indicator_build_jobs",
    "try_indicator_build_lock",
    "unlock_indicator_build_lock",
    "indicator_source_triggers_valid",
}
ALLOWED = {
    DatabaseRole.INDICATOR_BUILDER: BUILDER,
    DatabaseRole.API: {"indicator_source_triggers_valid"},
    DatabaseRole.MARKET_DATA: {"begin_indicator_source_write", "require_indicator_source_write"},
}


@pytest.mark.parametrize("role", list(ALLOWED))
async def test_all_indicator_function_acls_and_direct_mutation_denials(
    migrator_engine: AsyncEngine,
    role: DatabaseRole,
) -> None:
    async with migrator_engine.connect() as c:
        functions = (
            (
                await c.execute(
                    text("""SELECT p.oid,p.proname,
              ARRAY(SELECT t::regtype::text FROM unnest(p.proargtypes) t) AS types,
              NOT EXISTS(SELECT 1 FROM aclexplode(coalesce(p.proacl,
                acldefault('f',p.proowner))) a WHERE a.grantee=0
                AND a.privilege_type='EXECUTE') AS private
              FROM pg_proc p WHERE p.pronamespace='public'::regnamespace
                AND p.proname LIKE '%indicator%' ORDER BY p.proname""")
                )
            )
            .mappings()
            .all()
        )
        tables: Sequence[str] = (
            (
                await c.execute(
                    text("""SELECT relname FROM pg_class
              WHERE relnamespace='public'::regnamespace AND relkind='r'
                AND relname LIKE 'indicator_%' ORDER BY relname""")
                )
            )
            .scalars()
            .all()
        )
        columns: dict[str, list[str]] = {
            table: list(
                (
                    await c.execute(
                        text("""SELECT attname FROM pg_attribute
              WHERE attrelid=CAST(:table AS regclass) AND attnum>0 AND NOT attisdropped
                AND attgenerated='' ORDER BY attnum"""),
                        {"table": "public." + table},
                    )
                )
                .scalars()
                .all()
            )
            for table in tables
        }
    assert len(functions) >= 34 and len(tables) >= 7
    assert ALLOWED[role] <= {row["proname"] for row in functions}
    engine = create_engine_for(role, pool_size=1, max_overflow=0)
    try:
        async with engine.connect() as c:
            for row in functions:
                assert row["private"], row["proname"]
                allowed = row["proname"] in ALLOWED[role]
                actual: bool = (
                    await c.execute(
                        text(
                            "SELECT has_function_privilege("
                            "current_user,CAST(:oid AS oid),'EXECUTE')"
                        ),
                        {"oid": row["oid"]},
                    )
                ).scalar_one()
                assert actual == allowed
                if not allowed:
                    args = ",".join("NULL::" + kind for kind in row["types"])
                    with pytest.raises(DBAPIError) as denied:
                        async with c.begin_nested():
                            await c.execute(text(f"SELECT public.{row['proname']}({args}) IS NULL"))
                    assert getattr(denied.value.orig, "sqlstate", None) == "42501", denied.value
            for table in tables:
                granted: bool = (
                    await c.execute(
                        text("""SELECT
                  has_table_privilege(current_user,:table,'INSERT,UPDATE,DELETE,TRUNCATE')
                  OR has_any_column_privilege(current_user,:table,'INSERT,UPDATE')"""),
                        {"table": "public." + table},
                    )
                ).scalar_one()
                assert not granted, table
                names = [f'"{name}"' for name in columns[table]]
                assert names
                # Zero-row statements remain harmless even if an accidental grant exists.
                for statement in (
                    f"DELETE FROM public.{table} WHERE false",
                    f"UPDATE public.{table} SET "
                    + ",".join(name + "=NULL" for name in names)
                    + " WHERE false",
                    f"INSERT INTO public.{table} ("
                    + ",".join(names)
                    + ") SELECT "
                    + ",".join("NULL" for _ in names)
                    + " WHERE false",
                ):
                    with pytest.raises(DBAPIError) as denied:
                        async with c.begin_nested():
                            await c.execute(text(statement))
                    assert getattr(denied.value.orig, "sqlstate", None) == "42501", denied.value
    finally:
        await engine.dispose()
