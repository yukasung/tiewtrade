"""Immutable Paper-wallet records and typed failures."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Final
from uuid import UUID

from tiewtrade.core.money import Money
from tiewtrade.infra.db.errors import InfraError


class PaperWalletAction(Enum):
    CREATE = "CREATE"
    RESET = "RESET"


class PaperCommandState(Enum):
    PENDING = "PENDING"
    SUCCEEDED = "SUCCEEDED"
    REJECTED = "REJECTED"


class PaperWalletError(InfraError):
    code = "PAPER_WALLET_ERROR"


ACTIVITY_UNKNOWN: Final[str] = "ACTIVITY_UNKNOWN"
RESET_UNSAFE: Final[str] = "RESET_UNSAFE"


class PaperWalletIntegrityError(PaperWalletError):
    code = "PAPER_WALLET_INTEGRITY"


@dataclass(frozen=True, slots=True)
class PaperCommandSnapshot:
    wallet_id: UUID
    episode_id: UUID
    initial_capital: Money
    balance: Money


@dataclass(frozen=True, slots=True)
class PaperCommand:
    command_id: UUID
    state: PaperCommandState
    failure_code: str | None = None
    snapshot: PaperCommandSnapshot | None = None


@dataclass(frozen=True, slots=True)
class PaperWalletSnapshot:
    wallet_id: UUID
    episode_id: UUID
    sequence: int
    initial_capital: Money
    balance: Money
    started_at: datetime
    snapshot_at: datetime
    revision: int
    reset_available: bool = False
    reset_reason: str | None = ACTIVITY_UNKNOWN


@dataclass(frozen=True, slots=True)
class DuePaperCommand:
    command_id: UUID
    user_id: UUID


@dataclass(frozen=True, slots=True)
class ClaimedPaperCommand:
    command_id: UUID
    user_id: UUID
    claim_id: UUID
    action: PaperWalletAction
    initial_capital: Money
    expected_episode_id: UUID | None
    attempts: int
