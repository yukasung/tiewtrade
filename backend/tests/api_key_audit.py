"""Shared audit assertions, independently based on F-07 plan section 4.4."""

from typing import Literal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.infra.db import DatabaseRole, user_session


async def read_key_audit_events(
    engine: AsyncEngine,
    owner: UUID,
    key_id: UUID,
    *,
    role: DatabaseRole,
) -> list[dict[str, object]]:
    async with user_session(engine, owner, role=role) as session:
        result = await session.execute(
            "SELECT owner_user_id, action, actor_kind, actor_id, subject_kind, subject_id, "
            "outcome, failure_code, details FROM audit_events "
            "WHERE subject_kind = 'API_KEY' AND subject_id = :id ORDER BY recorded_at, id",
            {"id": str(key_id)},
        )
        return [dict(row) for row in result.mappings().all()]


def expected_key_audit_event(
    owner: UUID,
    key_id: UUID,
    *,
    action: str,
    actor_kind: Literal["USER", "SYSTEM"],
    outcome: str,
    failure_code: str | None = None,
) -> dict[str, object]:
    return {
        "owner_user_id": owner,
        "action": action,
        "actor_kind": actor_kind,
        "actor_id": owner if actor_kind == "USER" else None,
        "subject_kind": "API_KEY",
        "subject_id": str(key_id),
        "outcome": outcome,
        "failure_code": failure_code,
        "details": {},
    }
