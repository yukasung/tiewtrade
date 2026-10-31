"""Test-only state management for risk migration round trips."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


@dataclass(frozen=True)
class MigrationRoundtripState:
    protocol_flags: tuple[bool, bool, bool]
    temporary_settings: tuple[UUID, ...]


async def prepare_migration_roundtrip(engine: AsyncEngine) -> MigrationRoundtripState:
    """Stop writers and make shared-suite history representable by pre-0060 schemas."""
    async with engine.begin() as connection:
        row = (
            await connection.execute(
                text(
                    "SELECT admission_enabled,financial_enabled,publication_enabled "
                    "FROM risk_protocol_control"
                )
            )
        ).one()
        await connection.execute(
            text(
                "UPDATE risk_protocol_control SET admission_enabled=false,"
                "financial_enabled=false,publication_enabled=false"
            )
        )
        await connection.execute(
            text("ALTER TABLE paper_position_events NO FORCE ROW LEVEL SECURITY")
        )
        await connection.execute(
            text("ALTER TABLE risk_limit_settings NO FORCE ROW LEVEL SECURITY")
        )
        inserted = await connection.execute(
            text(
                """WITH unconfigured AS (
                  SELECT DISTINCT e.user_id FROM paper_position_events e
                  WHERE e.event_kind='RECORD' AND e.side='BUY' AND NOT EXISTS (
                    SELECT 1 FROM risk_limit_settings s
                    WHERE s.user_id=e.user_id AND s.mode='PAPER'))
                INSERT INTO risk_limit_settings(user_id,mode,revision,amount)
                SELECT user_id,'PAPER',1,1 FROM unconfigured
                RETURNING user_id"""
            )
        )
        await connection.execute(text("ALTER TABLE risk_limit_settings FORCE ROW LEVEL SECURITY"))
        await connection.execute(text("ALTER TABLE paper_position_events FORCE ROW LEVEL SECURITY"))
    return MigrationRoundtripState(
        protocol_flags=(bool(row[0]), bool(row[1]), bool(row[2])),
        temporary_settings=tuple(inserted.scalars()),
    )


async def restore_migration_roundtrip(engine: AsyncEngine, state: MigrationRoundtripState) -> None:
    """Remove test compatibility rows and restore protocol flags after upgrading to head."""
    async with engine.begin() as connection:
        await connection.execute(
            text("ALTER TABLE risk_limit_settings NO FORCE ROW LEVEL SECURITY")
        )
        for owner in state.temporary_settings:
            await connection.execute(
                text("DELETE FROM risk_limit_settings WHERE user_id=:owner AND mode='PAPER'"),
                {"owner": owner},
            )
        await connection.execute(text("ALTER TABLE risk_limit_settings FORCE ROW LEVEL SECURITY"))
        await connection.execute(
            text(
                "UPDATE risk_protocol_control SET admission_enabled=:admission,"
                "financial_enabled=:financial,publication_enabled=:publication"
            ),
            {
                "admission": state.protocol_flags[0],
                "financial": state.protocol_flags[1],
                "publication": state.protocol_flags[2],
            },
        )
