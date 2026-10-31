"""Typed identities and canonical fingerprints for the F-18 durable inbox."""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID

from tiewtrade.core.money import Money
from tiewtrade.core.orders import OrderConflictError
from tiewtrade.core.risk_limits import RiskInputError, RiskScope

MAX_RISK_REVISION = 2**63 - 1  # PostgreSQL bigint transport bound, not a trading limit.


class RiskAction(Enum):
    SET = "SET"
    DECREASE = "DECREASE"
    INCREASE = "INCREASE"
    RESET = "RESET"


class RiskConflictError(OrderConflictError):
    code = "RISK_REVISION_CONFLICT"


class RiskAuthorizationError(OrderConflictError):
    code = "RISK_AUTHORIZATION_REQUIRED"


@dataclass(frozen=True, slots=True)
class RiskSubmission:
    scope: RiskScope
    action: RiskAction
    key: UUID
    expected_revision: int
    amount: Money | None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.scope, RiskScope)
            or not isinstance(self.action, RiskAction)
            or type(self.key) is not UUID
            or type(self.expected_revision) is not int
            or not 0 <= self.expected_revision <= MAX_RISK_REVISION
        ):
            raise RiskInputError("invalid risk submission")
        if self.action is RiskAction.RESET:
            if self.amount is not None:
                raise RiskInputError("loss reset does not accept a new limit")
        elif (
            type(self.amount) is not Money
            or self.amount.currency != "USDT"
            or self.amount.amount <= 0
        ):
            raise RiskInputError("positive USDT limit required")

    def payload(self) -> dict[str, str | int | None]:
        return {
            "owner": str(self.scope.owner_id),
            "mode": self.scope.mode.value,
            "wallet": None if self.scope.wallet_id is None else str(self.scope.wallet_id),
            "episode": None if self.scope.episode_id is None else str(self.scope.episode_id),
            "action": self.action.value,
            "key": str(self.key),
            "expected_revision": self.expected_revision,
            "amount": None if self.amount is None else self.amount.as_parts()["amount"],
        }

    @property
    def fingerprint(self) -> str:
        canonical = json.dumps(self.payload(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class RiskReceipt:
    receipt_id: UUID
    submission: RiskSubmission
    recorded_at: datetime
    authorization_id: UUID | None
    authorization_only: bool = False
