"""Paper-wallet persistence API."""

from tiewtrade.infra.paper_wallet.records import (
    ACTIVITY_UNKNOWN,
    ClaimedPaperCommand,
    DuePaperCommand,
    PaperCommand,
    PaperCommandSnapshot,
    PaperCommandState,
    PaperWalletAction,
    PaperWalletError,
    PaperWalletIntegrityError,
    PaperWalletSnapshot,
)
from tiewtrade.infra.paper_wallet.storage import (
    admit_command,
    claim_command,
    due_hints,
    get_command,
    get_wallet,
    inspect_submission,
    process_claimed,
    schedule_failure,
)

__all__ = [
    "ACTIVITY_UNKNOWN",
    "ClaimedPaperCommand",
    "DuePaperCommand",
    "PaperCommand",
    "PaperCommandSnapshot",
    "PaperCommandState",
    "PaperWalletAction",
    "PaperWalletError",
    "PaperWalletIntegrityError",
    "PaperWalletSnapshot",
    "admit_command",
    "claim_command",
    "due_hints",
    "get_command",
    "get_wallet",
    "inspect_submission",
    "process_claimed",
    "schedule_failure",
]
