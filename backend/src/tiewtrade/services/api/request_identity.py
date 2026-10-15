"""Authenticated request identity without credential or persistence dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Final
from uuid import UUID

from fastapi import HTTPException, Request, status

NOT_AUTHENTICATED: Final[str] = "ต้องเข้าสู่ระบบก่อน"


class SecondFactor(Enum):
    """Second factor that authenticated the current request, when required."""

    TOTP_CODE = "TOTP_CODE"
    RECOVERY_GRANT = "RECOVERY_GRANT"


@dataclass(frozen=True, slots=True)
class Authenticated:
    """Server-established identity attached to one request."""

    user_id: UUID
    token_hash: str
    absolute_expires_at: datetime
    second_factor: SecondFactor | None = None


def current_user(request: Request) -> Authenticated:
    """Return middleware-authenticated identity or fail closed."""
    found = getattr(request.state, "authenticated", None)
    if not isinstance(found, Authenticated):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, NOT_AUTHENTICATED)
    return found
