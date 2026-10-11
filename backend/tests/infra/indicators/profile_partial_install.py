"""D6 partial-grant fault on the isolated DB; synthetic heads are predicate-only."""

import os
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.indicators.test_claims import prepared as prepared
from tests.infra.indicators.test_rollout import synthetic_heads
from tests.infra.indicators.test_source import active as active


async def test_missing_api_payload_grant_blocks_prepared_activation(
    prepared: None, migrator_engine: AsyncEngine
) -> None:
    assert "127.0.0.1:55433/" in os.environ["TIEWTRADE_DATABASE_URL_MIGRATOR"]
    await synthetic_heads(migrator_engine)
    async with migrator_engine.connect() as connection:
        transaction = await connection.begin()
        try:
            await connection.execute(
                text("REVOKE SELECT ON indicator_ready_generations FROM tiewtrade_api")
            )
            allowed: bool = (
                await connection.execute(
                    text(
                        "SELECT has_table_privilege('tiewtrade_api',"
                        "'indicator_ready_generations','SELECT')"
                    )
                )
            ).scalar_one()
            assert not allowed
            before = dict(
                (await connection.execute(text("SELECT * FROM indicator_rollout_control")))
                .mappings()
                .one()
            )
            result: dict[str, Any] = (
                await connection.execute(
                    text("SELECT transition_indicator_rollout('PREPARING',:epoch,'PREPARED')"),
                    {"epoch": before["rollout_epoch"]},
                )
            ).scalar_one()
            after = dict(
                (await connection.execute(text("SELECT * FROM indicator_rollout_control")))
                .mappings()
                .one()
            )
            assert result["result"] == "POLICY_UNSUPPORTED", result
            assert after == before
        finally:
            # Restore grants/control even when the regression assertion fails.
            await transaction.rollback()
