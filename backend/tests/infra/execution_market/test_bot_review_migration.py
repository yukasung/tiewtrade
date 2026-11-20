"""New safety migration keeps narrow grants and refuses loss of provenance."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.db.test_migrations import _alembic, _failed_upgrade_or_downgrade, _snapshot
from tests.infra.execution_market.test_bot_review_safety import DOC, seed_input_run
from tiewtrade.core.strategies import StrategyDecision
from tiewtrade.infra.bots.decisions import EvaluatedDecision, record_paper_decision
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot

pytestmark = pytest.mark.usefixtures("internal_database")


async def test_review_migration_roundtrip_preserves_schema_and_narrow_source_privileges(
    migrator_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    owner: UUID,
) -> None:
    before = await _snapshot(migrator_engine)
    _alembic("downgrade", "0071")
    _alembic("upgrade", "head")
    assert await _snapshot(migrator_engine) == before
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        privileges = (
            await session.execute("""SELECT
          has_table_privilege('tiewtrade_engine','indicator_source_guard','SELECT'),
          has_table_privilege('tiewtrade_engine','indicator_source_guard','UPDATE'),
          has_table_privilege('tiewtrade_engine','indicator_generations','INSERT'),
          has_function_privilege('tiewtrade_engine','hold_bot_indicator_source()','EXECUTE'),
          has_function_privilege('tiewtrade_api','hold_bot_indicator_source()','EXECUTE'),
          has_function_privilege('tiewtrade_engine_scan','hold_bot_indicator_source()','EXECUTE'),
          has_column_privilege('tiewtrade_engine_scan','bot_recovery_schedule','user_id','SELECT')""")
        ).one()
        assert tuple(privileges) == (True, False, False, True, False, False, False)
        assert not (
            await session.execute("SELECT admission_enabled FROM risk_protocol_control")
        ).scalar_one()
        assert (
            await session.execute("SELECT mode::text FROM indicator_rollout_control")
        ).scalar_one() == "LEGACY"


async def test_populated_provenance_refuses_downgrade_without_losing_rls_or_facts(
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    # The following refusal belongs to 0072; Alembic commits earlier reversible
    # revisions independently. Roundtrip of the head index is checked above.
    _alembic("downgrade", "0072")
    async with migrator_engine.connect() as connection:
        candidate_revision: str = (
            await connection.execute(text("SELECT version_num FROM alembic_version"))
        ).scalar_one()
    run = await seed_input_run(engine_engine, owner, wallet)
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await record_paper_decision(
            session,
            EvaluatedDecision(
                run,
                uuid4(),
                "provenance",
                1,
                1,
                1,
                DOC,
                StrategyDecision(DOC),
                {"market_revision": 1, "account_revision": wallet.revision},
            ),
        )
    refused = _failed_upgrade_or_downgrade("downgrade", "0071")
    assert "bot review safety history prevents downgrade" in refused.stderr
    async with migrator_engine.connect() as connection:
        after_revision: str = (
            await connection.execute(text("SELECT version_num FROM alembic_version"))
        ).scalar_one()
        assert after_revision == candidate_revision
        forced: object = (
            await connection.execute(
                text("SELECT relforcerowsecurity FROM pg_class WHERE relname='bot_decisions'")
            )
        ).scalar_one()
        assert forced is True
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        provenance = (
            await session.execute("SELECT input_provenance FROM bot_decisions")
        ).scalar_one()
        assert provenance == {"market_revision": 1, "account_revision": wallet.revision}
        assert (await session.execute("SELECT count(*) FROM bot_run_events")).scalar_one() == 2
    _alembic("upgrade", "head")
