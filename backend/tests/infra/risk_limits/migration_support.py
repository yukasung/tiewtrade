"""Test-only protocol shutdown for migration round trips."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

ProtocolFlags = tuple[bool, bool, bool]


async def stop_risk_protocol(engine: AsyncEngine) -> ProtocolFlags:
    """Stop writers before DDL and return the exact flags for later restoration."""
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
    return bool(row[0]), bool(row[1]), bool(row[2])


async def restore_risk_protocol(engine: AsyncEngine, flags: ProtocolFlags) -> None:
    """Restore the pre-test protocol state after the schema is back at head."""
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "UPDATE risk_protocol_control SET admission_enabled=:admission,"
                "financial_enabled=:financial,publication_enabled=:publication"
            ),
            {"admission": flags[0], "financial": flags[1], "publication": flags[2]},
        )
