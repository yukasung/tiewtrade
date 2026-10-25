from __future__ import annotations

from inspect import getsource
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.core.positions import PositionPair
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.paper_orders import dispatch
from tiewtrade.infra.paper_orders.dispatch import lock_opening_pair_catalog
from tiewtrade.infra.paper_orders.storage import lock_pair_catalog


def test_opening_submission_uses_wallet_then_pair_lock_order() -> None:
    source = getsource(dispatch._submit)
    assert source.index("lock_active_episode") < source.index("lock_opening_pair_catalog")


async def test_catalog_seeds_f38_pairs_with_mutations_disabled(
    migrator_engine: AsyncEngine,
) -> None:
    async with migrator_engine.connect() as connection:
        rows = (
            await connection.execute(
                text(
                    "SELECT base,quote,revision,current_revision "
                    "FROM active_supported_symbols ORDER BY base"
                )
            )
        ).all()
        gate = (
            await connection.execute(
                text(
                    "SELECT current_revision,mutations_enabled,protocol_version "
                    "FROM supported_symbol_catalog_control WHERE id=1"
                )
            )
        ).one()

    assert rows == [("BTC", "USDT", 1, 2), ("ETH", "USDT", 2, 2)]
    assert gate == (2, False, 1)


async def test_protocol_gate_rejects_missing_expired_and_mixed_heartbeats(
    migrator_engine: AsyncEngine,
) -> None:
    owner = uuid4()
    generation = uuid4()
    other_generation = uuid4()
    async with migrator_engine.connect() as connection:
        transaction = await connection.begin()
        try:
            await connection.execute(
                text("SELECT set_config('tiewtrade.current_user_id',:owner,true)"),
                {"owner": str(owner)},
            )
            await connection.execute(text("INSERT INTO users(id) VALUES(:owner)"), {"owner": owner})
            await connection.execute(
                text(
                    "INSERT INTO platform_memberships(user_id,role) VALUES(:owner,'PLATFORM_OWNER')"
                ),
                {"owner": owner},
            )

            async def rejected() -> None:
                savepoint = await connection.begin_nested()
                try:
                    with pytest.raises(DBAPIError, match="CATALOG_PROTOCOL_NOT_READY"):
                        await connection.execute(
                            text("SELECT enable_supported_symbol_mutations(:owner,:generation,2)"),
                            {"owner": owner, "generation": generation},
                        )
                finally:
                    await savepoint.rollback()

            await rejected()  # no process has reported the protocol yet
            await connection.execute(
                text(
                    """INSERT INTO catalog_protocol_heartbeats(
                    process_kind,instance_id,protocol_version,deployment_generation,
                    observed_at,lease_expires_at) VALUES
                    ('API',:api,1,:generation,clock_timestamp()-interval '2 minutes',
                      clock_timestamp()-interval '1 minute'),
                    ('ENGINE',:engine,1,:other,clock_timestamp(),
                      clock_timestamp()+interval '1 minute'),
                    ('MARKET_DATA',:market,1,:generation,clock_timestamp(),
                      clock_timestamp()+interval '1 minute'),
                    ('INDICATOR_BUILDER',:indicator,1,:generation,clock_timestamp(),
                      clock_timestamp()+interval '1 minute')"""
                ),
                {
                    "api": uuid4(),
                    "engine": uuid4(),
                    "market": uuid4(),
                    "indicator": uuid4(),
                    "generation": generation,
                    "other": other_generation,
                },
            )
            await rejected()  # API lease is expired
            await connection.execute(
                text(
                    "UPDATE catalog_protocol_heartbeats SET lease_expires_at="
                    "clock_timestamp()+interval '1 minute' WHERE process_kind='API'"
                )
            )
            await rejected()  # ENGINE still reports another deployment generation
            await connection.execute(
                text(
                    "UPDATE catalog_protocol_heartbeats SET deployment_generation=:generation "
                    "WHERE process_kind='ENGINE'"
                ),
                {"generation": generation},
            )
            await connection.execute(
                text("SELECT enable_supported_symbol_mutations(:owner,:generation,2)"),
                {"owner": owner, "generation": generation},
            )
            enabled: bool = (
                await connection.execute(
                    text(
                        "SELECT mutations_enabled FROM supported_symbol_catalog_control WHERE id=1"
                    )
                )
            ).scalar_one()
            assert enabled is True
        finally:
            await transaction.rollback()


async def test_catalog_history_registry_and_membership_are_append_only(
    migrator_engine: AsyncEngine,
) -> None:
    async with migrator_engine.connect() as connection:
        protected: set[str] = set(
            (
                await connection.execute(
                    text(
                        "SELECT table_name FROM tiewtrade_append_only_tables "
                        "WHERE table_name IN ('supported_symbol_registry',"
                        "'supported_symbol_events','platform_memberships',"
                        "'supported_symbol_constraint_snapshots',"
                        "'supported_symbol_maintenance_proofs')"
                    )
                )
            ).scalars()
        )

    assert protected == {
        "supported_symbol_registry",
        "supported_symbol_events",
        "supported_symbol_maintenance_proofs",
        "platform_memberships",
        "supported_symbol_constraint_snapshots",
    }


async def test_catalog_mutation_definers_can_preserve_rls_and_deferred_invariants(
    migrator_engine: AsyncEngine,
) -> None:
    async with migrator_engine.connect() as connection:
        functions: dict[str, bool] = dict(
            (
                await connection.execute(
                    text(
                        "SELECT p.proname,p.prosecdef FROM pg_proc p "
                        "WHERE p.proname IN ('request_supported_symbol_add',"
                        "'request_supported_symbol_remove','prepare_supported_symbol',"
                        "'fail_supported_symbol_preparation','supported_symbol_projection_consistent',"
                        "'supported_symbol_revision_consistent','lock_supported_symbol_pair')"
                    )
                )
            ).all()
        )
        policy: int = (
            await connection.execute(
                text(
                    "SELECT count(*) FROM pg_policies WHERE schemaname='public' "
                    "AND tablename='supported_symbol_commands' "
                    "AND policyname='supported_symbol_commands_definer' "
                    "AND 'tiewtrade_migrator'=ANY(roles)"
                )
            )
        ).scalar_one()

    assert functions == {
        "request_supported_symbol_add": True,
        "request_supported_symbol_remove": True,
        "prepare_supported_symbol": True,
        "fail_supported_symbol_preparation": True,
        "supported_symbol_projection_consistent": True,
        "supported_symbol_revision_consistent": True,
        "lock_supported_symbol_pair": True,
    }
    assert policy == 1


async def test_catalog_idempotency_lookup_is_serialized_before_replay_decision(
    migrator_engine: AsyncEngine,
) -> None:
    async with migrator_engine.connect() as connection:
        result = await connection.execute(
            text(
                "SELECT pg_get_functiondef(p.oid) FROM pg_proc p WHERE p.oid IN ("
                "'request_supported_symbol_add(uuid,uuid,text,text,text,bigint,text,uuid,text,timestamptz,jsonb,text)'::regprocedure,"
                "'request_supported_symbol_remove(uuid,uuid,text,text,text,bigint,text)'::regprocedure)"
            )
        )
        definitions: list[str] = list(result.scalars().all())
        for definition in definitions:
            lock = definition.index("pg_advisory_xact_lock(737,2)")
            replay_lookup = definition.index("SELECT *", lock)
            assert lock < replay_lookup


async def test_engine_pair_fence_blocks_removal_writer_without_update_privilege(
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
) -> None:
    async with user_session(engine_engine, UUID(int=1), role=DatabaseRole.ENGINE) as session:
        fence = await lock_pair_catalog(session, PositionPair("BTC", "USDT"))
        assert fence.snapshot.supports("BTC", "USDT")
        async with migrator_engine.connect() as connection:
            transaction = await connection.begin()
            try:
                await connection.execute(text("SET LOCAL lock_timeout='100ms'"))
                with pytest.raises(DBAPIError, match="lock timeout"):
                    await connection.execute(
                        text(
                            "UPDATE supported_symbol_fences SET updated_at=updated_at "
                            "WHERE base='BTC' AND quote='USDT'"
                        )
                    )
            finally:
                await transaction.rollback()


async def test_api_opening_submission_fence_blocks_removal_update(
    api_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
) -> None:
    async with user_session(api_engine, UUID(int=2), role=DatabaseRole.API) as session:
        await lock_opening_pair_catalog(session, PositionPair("BTC", "USDT"))
        async with migrator_engine.connect() as connection:
            transaction = await connection.begin()
            try:
                await connection.execute(text("SET LOCAL lock_timeout='100ms'"))
                with pytest.raises(DBAPIError, match="lock timeout"):
                    await connection.execute(
                        text(
                            "UPDATE supported_symbol_fences SET updated_at=updated_at "
                            "WHERE base='BTC' AND quote='USDT'"
                        )
                    )
            finally:
                await transaction.rollback()


async def test_catalog_removes_hard_coded_pair_logic_from_live_schema(
    migrator_engine: AsyncEngine,
) -> None:
    async with migrator_engine.connect() as connection:
        functions: list[str] = list(
            (
                await connection.execute(
                    text(
                        "SELECT pg_get_functiondef(p.oid) FROM pg_proc p WHERE p.oid IN ("
                        "'seed_indicator_build_jobs()'::regprocedure,"
                        "'coalesce_indicator_build_jobs()'::regprocedure,"
                        "'claim_indicator_build_job(uuid)'::regprocedure,"
                        "'transition_indicator_rollout("
                        "indicator_rollout_mode,uuid,indicator_rollout_mode)'::regprocedure)"
                    )
                )
            ).scalars()
        )
        hard_coded_constraints: int = (
            await connection.execute(
                text(
                    "SELECT count(*) FROM pg_constraint WHERE conrelid IN ("
                    "'market_candles'::regclass,'market_candle_demand'::regclass,"
                    "'market_latest_prices'::regclass,'market_candle_preview'::regclass,"
                    "'indicator_build_jobs'::regclass,'indicator_generations'::regclass) "
                    "AND (position('BTC' in pg_get_constraintdef(oid))>0 "
                    "OR position('ETH' in pg_get_constraintdef(oid))>0)"
                )
            )
        ).scalar_one()
        runtime_view: str = (
            await connection.execute(text("SELECT pg_get_viewdef('runtime_supported_symbols')"))
        ).scalar_one()

    for definition in functions:
        assert "'BTC'" not in definition
        assert "'ETH'" not in definition
        assert "supported_symbol_fences" in definition
    claim = next(
        definition for definition in functions if "claim_indicator_build_job" in definition
    )
    assert "PREPARING" in claim
    assert "pair_fence.status" in claim and "ACTIVE" in claim and "PREPARING" in claim
    coalesce = next(
        definition for definition in functions if "coalesce_indicator_build_jobs" in definition
    )
    assert "FOR j IN SELECT jobs.*" in coalesce
    assert "pair_fence.status" in coalesce and "ACTIVE" in coalesce and "PREPARING" in coalesce
    assert "REQUESTED" in runtime_view and "FAILED" in runtime_view
    assert "supported_symbol_requires_maintenance" in runtime_view
    assert hard_coded_constraints == 0


async def test_third_pair_can_use_dynamic_storage_without_persisting_fixture(
    migrator_engine: AsyncEngine,
) -> None:
    async with migrator_engine.connect() as connection:
        transaction = await connection.begin()
        try:
            await connection.execute(
                text("INSERT INTO supported_symbol_registry(base,quote) VALUES('SOL','USDT')")
            )
            await connection.execute(
                text(
                    "INSERT INTO supported_symbol_events("
                    "revision,command_id,base,quote,status,reason_code) VALUES("
                    "3,'00000000-0000-0000-0000-000000000003',"
                    "'SOL','USDT','ACTIVE','F38_INITIAL_CATALOG')"
                )
            )
            await connection.execute(
                text(
                    "INSERT INTO supported_symbol_fences("
                    "base,quote,status,revision,command_id) VALUES("
                    "'SOL','USDT','ACTIVE',3,"
                    "'00000000-0000-0000-0000-000000000003')"
                )
            )
            await connection.execute(
                text("UPDATE supported_symbol_catalog_control SET current_revision=3 WHERE id=1")
            )
            await connection.execute(
                text(
                    "INSERT INTO market_latest_prices(source,base,quote) "
                    "VALUES('primary_spot','SOL','USDT')"
                )
            )
            await connection.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
            assert (
                await connection.execute(
                    text("SELECT revision FROM active_supported_symbols WHERE base='SOL'")
                )
            ).scalar_one() == 3
        finally:
            await transaction.rollback()


async def test_projection_mismatch_fails_at_transaction_boundary(
    migrator_engine: AsyncEngine,
) -> None:
    async with migrator_engine.connect() as connection:
        transaction = await connection.begin()
        try:
            await connection.execute(
                text("INSERT INTO supported_symbol_registry(base,quote) VALUES('SOL','USDT')")
            )
            await connection.execute(
                text(
                    "INSERT INTO supported_symbol_events("
                    "revision,command_id,base,quote,status,reason_code) VALUES("
                    "3,'00000000-0000-0000-0000-000000000003',"
                    "'SOL','USDT','ACTIVE','F38_INITIAL_CATALOG')"
                )
            )
            with pytest.raises(DBAPIError, match="CATALOG_PROJECTION_MISMATCH"):
                await connection.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
        finally:
            await transaction.rollback()


async def test_global_revision_mismatch_fails_at_transaction_boundary(
    migrator_engine: AsyncEngine,
) -> None:
    async with migrator_engine.connect() as connection:
        transaction = await connection.begin()
        try:
            await connection.execute(
                text("INSERT INTO supported_symbol_registry(base,quote) VALUES('SOL','USDT')")
            )
            await connection.execute(
                text(
                    "INSERT INTO supported_symbol_events("
                    "revision,command_id,base,quote,status,reason_code) VALUES("
                    "3,'00000000-0000-0000-0000-000000000003',"
                    "'SOL','USDT','ACTIVE','F38_INITIAL_CATALOG')"
                )
            )
            await connection.execute(
                text(
                    "INSERT INTO supported_symbol_fences("
                    "base,quote,status,revision,command_id) VALUES("
                    "'SOL','USDT','ACTIVE',3,"
                    "'00000000-0000-0000-0000-000000000003')"
                )
            )
            with pytest.raises(DBAPIError, match="CATALOG_REVISION_MISMATCH"):
                await connection.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
        finally:
            await transaction.rollback()


async def test_bootstrap_is_atomic_one_shot_and_narrowly_privileged(
    migrator_engine: AsyncEngine,
) -> None:
    owner = UUID("11111111-1111-1111-1111-111111111111")
    async with migrator_engine.connect() as connection:
        transaction = await connection.begin()
        try:
            await connection.execute(
                text("SELECT set_config('tiewtrade.current_user_id',:owner,true)"),
                {"owner": str(owner)},
            )
            await connection.execute(text("INSERT INTO users(id) VALUES(:owner)"), {"owner": owner})
            # Test fixture setup only: runtime creates TOTP through tiewtrade_auth.
            # Re-enable FORCE before exercising the production bootstrap function.
            await connection.execute(text("ALTER TABLE user_totp NO FORCE ROW LEVEL SECURITY"))
            await connection.execute(
                text(
                    "INSERT INTO user_totp("
                    "user_id,secret_sealed,key_version,secret_version,last_accepted_step) "
                    "VALUES(:owner,decode('00','hex'),'test',1,0)"
                ),
                {"owner": owner},
            )
            await connection.execute(text("ALTER TABLE user_totp FORCE ROW LEVEL SECURITY"))
            await connection.execute(
                text("SELECT bootstrap_platform_owner(:owner)"), {"owner": owner}
            )
            membership = (
                await connection.execute(
                    text("SELECT role,created_by FROM platform_memberships WHERE user_id=:owner"),
                    {"owner": owner},
                )
            ).one()
            audit = (
                await connection.execute(
                    text(
                        "SELECT actor_kind,actor_id,owner_user_id,details FROM audit_events "
                        "WHERE action='PLATFORM_OWNER_BOOTSTRAPPED' AND owner_user_id=:owner"
                    ),
                    {"owner": owner},
                )
            ).one()
            assert membership == ("PLATFORM_OWNER", None)
            assert audit == ("SYSTEM", None, owner, {"role": "PLATFORM_OWNER"})

            nested = await connection.begin_nested()
            with pytest.raises(DBAPIError, match="PLATFORM_OWNER_ALREADY_EXISTS"):
                await connection.execute(
                    text("SELECT bootstrap_platform_owner(:owner)"), {"owner": owner}
                )
            await nested.rollback()
        finally:
            await transaction.rollback()

    async with migrator_engine.connect() as connection:
        privileges = (
            await connection.execute(
                text(
                    "SELECT r.rolsuper,r.rolbypassrls,"
                    "has_table_privilege(r.rolname,'supported_symbol_registry','SELECT'),"
                    "has_function_privilege(r.rolname,'bootstrap_platform_owner(uuid)','EXECUTE') "
                    "FROM pg_roles r WHERE r.rolname='tiewtrade_platform_bootstrap'"
                )
            )
        ).one()
    assert privileges == (False, False, False, True)
