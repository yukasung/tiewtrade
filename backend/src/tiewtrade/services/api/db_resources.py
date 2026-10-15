"""Database engines prepared by the API lifespan, without credential dependencies."""

from typing import Final

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.infra.db import DatabaseRole

_ENGINE_ATTRIBUTE: Final[dict[DatabaseRole, str]] = {
    DatabaseRole.API: "api_engine",
    DatabaseRole.AUTH: "auth_engine",
}


def engine_for(request: Request, role: DatabaseRole) -> AsyncEngine:
    """Return the lifespan-owned engine for one database role."""
    attribute = _ENGINE_ATTRIBUTE[role]
    engine = getattr(request.app.state, attribute, None)
    if not isinstance(engine, AsyncEngine):  # pragma: no cover - app misconfiguration
        raise RuntimeError(f"แอปยังไม่ได้ตั้ง engine ของบทบาท {role.role_name}")
    return engine


def paper_mutation_engine(request: Request) -> AsyncEngine:
    """Return the bounded API-role pool reserved for Paper mutation throttling."""
    engine = getattr(request.app.state, "paper_mutation_engine", None)
    if not isinstance(engine, AsyncEngine):  # pragma: no cover - app misconfiguration
        raise RuntimeError("แอปยังไม่ได้ตั้ง engine สำหรับ Paper mutation")
    return engine
