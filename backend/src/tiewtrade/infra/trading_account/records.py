"""Single-account metadata never grants permission to trade."""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import ClassVar

from tiewtrade.infra.api_keys.records import ApiKeySummary
from tiewtrade.infra.db.errors import InfraError


class AccountUse(StrEnum):
    MANUAL = "MANUAL"
    BOT = "BOT"


class TradingAccountError(InfraError):
    code: ClassVar[str] = "TRADING_ACCOUNT_INPUT_REJECTED"


class TradingAccountKeyUnavailableError(TradingAccountError):
    code: ClassVar[str] = "TRADING_ACCOUNT_KEY_UNAVAILABLE"


class TradingAccountActivityUnknownError(TradingAccountError):
    code: ClassVar[str] = "TRADING_ACCOUNT_ACTIVITY_UNKNOWN"


@dataclass(frozen=True, slots=True)
class TradingAccountSummary:
    use: AccountUse | None
    key: ApiKeySummary | None
    may_trade: bool = field(default=False, init=False)
    may_change_use: bool = field(default=False, init=False)
