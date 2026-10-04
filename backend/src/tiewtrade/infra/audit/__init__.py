"""บันทึกการกระทำที่แตะเงิน (F-04) — ของสาธารณะของชั้นนี้อยู่ที่นี่ที่เดียว"""

from tiewtrade.infra.audit.events import (
    DETAILS_TYPES,
    TRADING_ACTIONS,
    ActorKind,
    AllSessionsEndedDetails,
    AuditAction,
    AuditEvent,
    AuditEventError,
    AuditMode,
    AuditOutcome,
    PasswordChangedDetails,
    RecoveryCodesIssuedDetails,
    RecoveryCodeUsedDetails,
    SessionDetails,
    SubjectKind,
    TotpChangeDetails,
    UserCreatedDetails,
    money_detail,
    quantity_detail,
)
from tiewtrade.infra.audit.redaction import ForbiddenDetailError, ensure_no_forbidden_content
from tiewtrade.infra.audit.writer import record_event

__all__ = [
    "DETAILS_TYPES",
    "TRADING_ACTIONS",
    "ActorKind",
    "AllSessionsEndedDetails",
    "AuditAction",
    "AuditEvent",
    "AuditEventError",
    "AuditMode",
    "AuditOutcome",
    "ForbiddenDetailError",
    "PasswordChangedDetails",
    "RecoveryCodeUsedDetails",
    "RecoveryCodesIssuedDetails",
    "SessionDetails",
    "SubjectKind",
    "TotpChangeDetails",
    "UserCreatedDetails",
    "ensure_no_forbidden_content",
    "money_detail",
    "quantity_detail",
    "record_event",
]
