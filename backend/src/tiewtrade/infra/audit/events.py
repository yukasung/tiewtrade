"""รูปร่างของเหตุการณ์ในบันทึก (F-04)

**รูปร่างของ `details` กำหนดต่อเหตุการณ์ด้วยชนิดข้อมูลของตัวเอง ไม่ใช่ dict อิสระ**
(plan.md ข้อ 2 และ 6) ผู้เรียกจึงใส่ช่องที่ไม่ได้ประกาศไว้ไม่ได้เลย และฐานข้อมูล
ปฏิเสธซ้ำอีกชั้นด้วย `CHECK` แม้มีคนเขียนตรงโดยไม่ผ่านตัวเขียน

ทำไมต้องเป็นรายการที่อนุญาต ไม่ใช่รายการที่ห้าม: รายการที่ห้ามครอบไม่ได้จริง
`{"note": "ชื่อคนหรือค่าลับ"}` ผ่านทุกรายการที่ห้าม ซึ่งขัดกับ RQ-4 และ RQ-18
และบันทึกที่เขียนแล้วลบไม่ได้ ความผิดพลาดจึงถาวร

อยู่ใน `infra` ไม่ใช่ `core` เพราะเป็นรูปแบบของบันทึกในฐานข้อมูล ไม่ใช่ตรรกะโดเมน
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable
from uuid import UUID

from tiewtrade.core.money import Money, Quantity
from tiewtrade.infra.db.errors import InfraError
from tiewtrade.infra.trading_account.records import AccountUse


class AuditEventError(InfraError):
    """บันทึกที่ประกอบไม่ถูกต้อง — ชนิดที่ผู้เรียกดักได้ (RQ-12)"""

    code = "AUDIT_EVENT_INVALID"


class AuditAction(Enum):
    """ชนิดเหตุการณ์ที่ประกาศไว้แล้ว

    **ต้องตรงกับ `CHECK` ใน migration 0004** การเพิ่มชนิดใหม่ต้องแก้ทั้งสองที่
    ในงานเดียวกัน พร้อมประกาศรูปร่างของ `details` และเทสต์ (Q-1)
    """

    USER_CREATED = "USER_CREATED"
    #: สี่ชนิดของ F-05 — ทั้งหมดเป็นการกระทำที่ผู้ใช้ทำกับบัญชีตัวเอง
    SESSION_STARTED = "SESSION_STARTED"
    SESSION_ENDED = "SESSION_ENDED"
    ALL_SESSIONS_ENDED = "ALL_SESSIONS_ENDED"
    PASSWORD_CHANGED = "PASSWORD_CHANGED"
    #: ห้าชนิดของ F-06 — การจัดการปัจจัยที่สองของบัญชีตัวเอง
    #:
    #: **ไม่มีชนิดสำหรับรหัสที่กรอกผิด** ตารางนี้เพิ่มได้อย่างเดียว ถ้าเขียนทุกครั้ง
    #: ที่ผิด ผู้โจมตีจะทำให้ตารางโตได้ตามใจ — แบบแผนเดียวกับที่ F-05 ไม่ลงบันทึก
    #: การเข้าสู่ระบบที่ล้มเหลว
    TOTP_ENABLED = "TOTP_ENABLED"
    TOTP_DISABLED = "TOTP_DISABLED"
    TOTP_SECRET_REPLACED = "TOTP_SECRET_REPLACED"
    RECOVERY_CODES_ISSUED = "RECOVERY_CODES_ISSUED"
    RECOVERY_CODE_USED = "RECOVERY_CODE_USED"
    #: หกชนิดของ F-07 — **สามชนิดแรกผู้ใช้ทำ สามชนิดหลังระบบทำ**
    #:
    #: ผลการตรวจเป็นของระบบเพราะมันเกิดใน `engine` ที่ไม่มีคนนั่งอยู่ปลายสาย
    #: การบันทึกว่าเป็น `USER` จะทำให้บันทึกโกหกว่าใครเป็นคนทำ
    API_KEY_ADDED = "API_KEY_ADDED"
    API_KEY_RETRY_REQUESTED = "API_KEY_RETRY_REQUESTED"
    API_KEY_DELETED = "API_KEY_DELETED"
    API_KEY_VERIFIED = "API_KEY_VERIFIED"
    API_KEY_REJECTED = "API_KEY_REJECTED"
    API_KEY_VERIFICATION_DEFERRED = "API_KEY_VERIFICATION_DEFERRED"
    TRADING_USE_SELECTED = "TRADING_USE_SELECTED"
    PAPER_WALLET_CREATED = "PAPER_WALLET_CREATED"
    PAPER_WALLET_CREATE_REJECTED = "PAPER_WALLET_CREATE_REJECTED"
    PAPER_WALLET_RESET_REJECTED = "PAPER_WALLET_RESET_REJECTED"


#: ชนิดเหตุการณ์ที่เป็นการเทรด — ต้องระบุ PAPER หรือ LIVE เสมอ (RQ-19)
#: ยังว่างเพราะยังไม่มีงานที่แตะการเทรด งานที่เพิ่มต้องใส่ชื่อเหตุการณ์ของตัวเองที่นี่
TRADING_ACTIONS: frozenset[AuditAction] = frozenset(
    {
        AuditAction.PAPER_WALLET_CREATED,
        AuditAction.PAPER_WALLET_CREATE_REJECTED,
        AuditAction.PAPER_WALLET_RESET_REJECTED,
    }
)


class ActorKind(Enum):
    """ผู้กระทำเป็นใคร — ไม่ใช่คนก็ได้ (Q-8)"""

    USER = "USER"
    BOT = "BOT"
    SYSTEM = "SYSTEM"
    PLATFORM = "PLATFORM"


class AuditMode(Enum):
    """โหมดของเหตุการณ์ — มีค่าที่สามสำหรับเหตุการณ์ที่ไม่เกี่ยวกับโหมด (RQ-19)"""

    PAPER = "PAPER"
    LIVE = "LIVE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class AuditOutcome(Enum):
    """ผลของการกระทำ — "ผลเป็นอย่างไร" ตาม RQ-1"""

    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    REJECTED = "REJECTED"


class SubjectKind(Enum):
    """สิ่งที่ถูกกระทำ — "กับอะไร" ตาม RQ-1"""

    USER = "USER"
    #: API key หนึ่งใบ — `subject_id` คือรหัสของแถว **ไม่ใช่ค่าของ key** (F-07 RQ-9.1)
    API_KEY = "API_KEY"
    PAPER_WALLET = "PAPER_WALLET"
    PAPER_WALLET_COMMAND = "PAPER_WALLET_COMMAND"


@runtime_checkable
class AuditDetails(Protocol):
    """สัญญาของรายละเอียดต่อเหตุการณ์ — แต่ละชนิดประกาศช่องของตัวเอง"""

    def as_details(self) -> dict[str, object]:
        """คืนรูปแบบที่จะเก็บลง `JSONB` — ช่องที่ไม่ได้ประกาศจึงเกิดขึ้นไม่ได้"""
        ...


@dataclass(frozen=True, slots=True)
class UserCreatedDetails:
    """รายละเอียดของ `USER_CREATED` — **ไม่มีช่องใดเลย**

    ทุกอย่างที่ต้องรู้อยู่ในคอลัมน์แกนแล้ว (ใครทำ กับอะไร เมื่อไหร่ ผลเป็นอย่างไร)
    การเพิ่มช่องที่ไม่จำเป็นคือการเพิ่มที่ให้ข้อมูลระบุตัวตนเข้ามา
    """

    def as_details(self) -> dict[str, object]:
        return {}


@dataclass(frozen=True, slots=True)
class SessionDetails:
    """รายละเอียดของการเริ่มและจบ session หนึ่งใบ — **ไม่มีช่องใดเลย**

    **ห้ามมีโทเคน แฮชของโทเคน อุปกรณ์ หรือ IP** — บันทึกที่ลบไม่ได้ไม่ใช่ที่เก็บ
    ร่องรอยการใช้งาน และแฮชของโทเคนคือสิ่งที่ใช้ค้นหา session ได้ (`security.md` หัวข้อ 4)
    """

    def as_details(self) -> dict[str, object]:
        return {}


@dataclass(frozen=True, slots=True)
class AllSessionsEndedDetails:
    """รายละเอียดของการออกจากระบบทุกเครื่อง — จำนวนใบที่ถูกเพิกถอน

    จำนวนมีประโยชน์ตอนอ่านย้อนหลัง (ออกจากกี่เครื่อง) และไม่ระบุตัวบุคคล
    """

    ended: int

    def __post_init__(self) -> None:
        if self.ended < 0:
            raise AuditEventError("จำนวน session ที่ถูกเพิกถอนติดลบไม่ได้")

    def as_details(self) -> dict[str, object]:
        return {"ended": self.ended}


@dataclass(frozen=True, slots=True)
class PasswordChangedDetails:
    """รายละเอียดของการเปลี่ยนรหัสผ่าน — **ไม่มีช่องใดเลย**

    ไม่เก็บแฮชเก่า ไม่เก็บความยาว ไม่เก็บอะไรที่ช่วยเดารหัสผ่าน
    """

    def as_details(self) -> dict[str, object]:
        return {}


@dataclass(frozen=True, slots=True)
class TotpChangeDetails:
    """รายละเอียดของการเปิด ปิด หรือเปลี่ยน secret ของ TOTP — **ไม่มีช่องใดเลย**

    **ห้ามมี secret, แฮชของ secret, รุ่นของกุญแจ, อุปกรณ์ หรือ IP** — บันทึกที่ลบไม่ได้
    ไม่ใช่ที่เก็บร่องรอยการใช้งาน และรุ่นของกุญแจบอกเรื่องการเข้ารหัสของเราให้คนอ่าน
    บันทึกรู้โดยไม่จำเป็น (`security.md` หัวข้อ 4)
    """

    def as_details(self) -> dict[str, object]:
        return {}


@dataclass(frozen=True, slots=True)
class RecoveryCodesIssuedDetails:
    """จำนวนรหัสสำรองที่ออกในชุดนั้น

    เก็บจำนวนเพราะอ่านย้อนหลังแล้วเห็นว่าชุดที่ออกมีกี่ใบ และไม่ระบุตัวบุคคล
    — เหตุผลเดียวกับ `AllSessionsEndedDetails`
    """

    issued: int

    def __post_init__(self) -> None:
        if self.issued <= 0:
            raise AuditEventError("ชุดรหัสสำรองที่ออกต้องมีอย่างน้อยหนึ่งใบ")

    def as_details(self) -> dict[str, object]:
        return {"issued": self.issued}


@dataclass(frozen=True, slots=True)
class RecoveryCodeUsedDetails:
    """จำนวนใบที่เหลือหลังใช้ไปหนึ่งใบ

    **ไม่เก็บว่าใช้ใบไหน** เพราะไม่มีใครต้องรู้ และการรู้ก็ช่วยผู้โจมตีมากกว่า
    · จำนวนที่เหลือทำให้เห็นตอนอ่านย้อนหลังว่าบัญชีใกล้หมดทางกู้
    """

    remaining: int

    def __post_init__(self) -> None:
        if self.remaining < 0:
            raise AuditEventError("จำนวนรหัสสำรองที่เหลือติดลบไม่ได้")

    def as_details(self) -> dict[str, object]:
        return {"remaining": self.remaining}


#: รูปร่างของ `details` ที่แต่ละชนิดเหตุการณ์ใช้ได้ — ตรวจตอนสร้าง `AuditEvent`
@dataclass(frozen=True, slots=True)
class ApiKeyDetails:
    """รายละเอียดของเหตุการณ์ที่แตะ API key — **ไม่มีช่องใดเลย**

    ทุกอย่างที่ต้องรู้อยู่ในคอลัมน์แกนแล้ว: `subject_id` บอกว่า key ใบไหน
    และ `failure_code` บอกว่าทำไม · **ห้ามมี `key_public` เด็ดขาด** เพราะนั่นคือ
    การเอา API key ไปไว้ในบันทึกที่ลบไม่ได้ ซึ่ง `security.md` หัวข้อ 4 ห้าม (RQ-9.1)
    """

    def as_details(self) -> dict[str, object]:
        return {}


@dataclass(frozen=True, slots=True)
class TradingUseDetails:
    """The selected account use; no credential data."""

    use: AccountUse

    def __post_init__(self) -> None:
        if not isinstance(self.use, AccountUse):
            raise AuditEventError("account use must be a declared AccountUse")

    def as_details(self) -> dict[str, object]:
        return {"use": self.use.value}


@dataclass(frozen=True, slots=True)
class PaperWalletCreatedDetails:
    command_id: UUID
    episode_id: UUID
    capital: Money

    def as_details(self) -> dict[str, object]:
        amount = money_detail(self.capital)
        return {
            "command_id": str(self.command_id),
            "episode_id": str(self.episode_id),
            "amount": amount["amount"],
            "currency": amount["unit"],
        }


@dataclass(frozen=True, slots=True)
class PaperWalletRejectedDetails:
    def as_details(self) -> dict[str, object]:
        return {}


DETAILS_TYPES: dict[AuditAction, type[object]] = {
    AuditAction.TRADING_USE_SELECTED: TradingUseDetails,
    AuditAction.PAPER_WALLET_CREATED: PaperWalletCreatedDetails,
    AuditAction.PAPER_WALLET_CREATE_REJECTED: PaperWalletRejectedDetails,
    AuditAction.PAPER_WALLET_RESET_REJECTED: PaperWalletRejectedDetails,
    AuditAction.USER_CREATED: UserCreatedDetails,
    AuditAction.SESSION_STARTED: SessionDetails,
    AuditAction.SESSION_ENDED: SessionDetails,
    AuditAction.ALL_SESSIONS_ENDED: AllSessionsEndedDetails,
    AuditAction.PASSWORD_CHANGED: PasswordChangedDetails,
    AuditAction.TOTP_ENABLED: TotpChangeDetails,
    AuditAction.TOTP_DISABLED: TotpChangeDetails,
    AuditAction.TOTP_SECRET_REPLACED: TotpChangeDetails,
    AuditAction.RECOVERY_CODES_ISSUED: RecoveryCodesIssuedDetails,
    AuditAction.RECOVERY_CODE_USED: RecoveryCodeUsedDetails,
    AuditAction.API_KEY_ADDED: ApiKeyDetails,
    AuditAction.API_KEY_RETRY_REQUESTED: ApiKeyDetails,
    AuditAction.API_KEY_DELETED: ApiKeyDetails,
    AuditAction.API_KEY_VERIFIED: ApiKeyDetails,
    AuditAction.API_KEY_REJECTED: ApiKeyDetails,
    AuditAction.API_KEY_VERIFICATION_DEFERRED: ApiKeyDetails,
}

#: รหัสความล้มเหลวที่ประกาศไว้แล้ว — **ยังว่าง** เพราะยังไม่มีเหตุการณ์ที่ล้มเหลวได้
#:
#: `failure_code` เป็นรหัส ไม่ใช่ข้อความอิสระ (`backend.md` หัวข้อ 4) ช่องข้อความอิสระ
#: คือทางที่ค่าลับและข้อมูลระบุตัวตนเข้ามาได้ (RQ-4, RQ-18) จึงต้องประกาศทีละรหัส
#: พร้อม migration เหมือนการเพิ่มชนิดเหตุการณ์
#: รหัสความล้มเหลวที่ประกาศไว้ — **ต้องตรงกับ `CHECK` ใน migration `0009`**
#:
#: หกรหัสแรกเป็นชนิดข้อผิดพลาดกลางของ F-33 ส่วนรหัสสุดท้ายเป็นของ F-07 เอง
#: (ครบเส้นตาย 24 ชั่วโมงโดยยังตรวจไม่ผ่าน)
ALLOWED_FAILURE_CODES: frozenset[str] = frozenset(
    {
        "VENUE_CREDENTIAL_REJECTED",
        "VENUE_REJECTED",
        "VENUE_RATE_LIMITED",
        "VENUE_UNAVAILABLE",
        "VENUE_OUTCOME_UNKNOWN",
        "VENUE_PROTOCOL",
        "VERIFICATION_EXPIRED",
        "INITIAL_CAPITAL_INVALID",
        "INITIAL_CAPITAL_TOO_SMALL",
        "IDEMPOTENCY_CONFLICT",
        "WALLET_EXISTS",
        "ACTIVITY_UNKNOWN",
        "EPISODE_CONFLICT",
        "RESET_UNSAFE",
    }
)


def _check_user_created(event: AuditEvent) -> None:
    """`USER_CREATED` — ผู้กระทำและเป้าหมายต้องเป็นผู้ใช้ที่ถูกสร้าง (plan.md ข้อ 5)

    เงื่อนไขทั่วไปไม่พอ เพราะ `subject_id` เป็นข้อความ จึงรับอะไรก็ได้ถ้าไม่ผูกกับ
    เหตุการณ์ — และนั่นคือช่องที่ข้อมูลระบุตัวตนเข้ามาได้ (RQ-18)
    """
    if event.actor_kind is not ActorKind.USER:
        raise AuditEventError("USER_CREATED ต้องมีผู้กระทำเป็นผู้ใช้")
    if event.actor_id != event.owner_user_id:
        raise AuditEventError("USER_CREATED ต้องมีผู้กระทำเป็นผู้ใช้ที่ถูกสร้าง")
    if event.subject_kind is not SubjectKind.USER:
        raise AuditEventError("USER_CREATED ต้องมีเป้าหมายเป็นผู้ใช้")
    if event.subject_id != str(event.owner_user_id):
        raise AuditEventError("USER_CREATED ต้องมีเป้าหมายเป็นรหัสของผู้ใช้ที่ถูกสร้าง")
    if event.outcome is not AuditOutcome.SUCCEEDED:
        raise AuditEventError("USER_CREATED บันทึกเฉพาะกรณีที่สร้างสำเร็จ")


def _check_own_account_action(event: AuditEvent) -> None:
    """เหตุการณ์ที่ผู้ใช้ทำกับบัญชีตัวเอง — ผู้กระทำและเป้าหมายต้องเป็นเจ้าของบันทึก

    ใช้ร่วมกันสี่ชนิดของ F-05 และห้าชนิดของ F-06 เพราะเงื่อนไขเดียวกันทุกข้อ —
    เขียนแยกเก้าชุดคือเก้าชุดที่ต้องแก้ให้ตรงกันทุกครั้งที่กฎเปลี่ยน
    """
    name = event.action.value
    if event.actor_kind is not ActorKind.USER:
        raise AuditEventError(f"{name} ต้องมีผู้กระทำเป็นผู้ใช้")
    if event.actor_id != event.owner_user_id:
        raise AuditEventError(f"{name} ต้องมีผู้กระทำเป็นเจ้าของบัญชีนั้น")
    if event.subject_kind is not SubjectKind.USER:
        raise AuditEventError(f"{name} ต้องมีเป้าหมายเป็นผู้ใช้")
    if event.subject_id != str(event.owner_user_id):
        raise AuditEventError(f"{name} ต้องมีเป้าหมายเป็นรหัสของเจ้าของบัญชีนั้น")
    if event.outcome is not AuditOutcome.SUCCEEDED:
        raise AuditEventError(f"{name} บันทึกเฉพาะกรณีที่สำเร็จ")


def _check_own_api_key_action(event: AuditEvent) -> None:
    """เหตุการณ์ที่ผู้ใช้ทำกับ key ของตัวเอง — เป้าหมายเป็น key ไม่ใช่ผู้ใช้"""
    name = event.action.value
    if event.actor_kind is not ActorKind.USER:
        raise AuditEventError(f"{name} ต้องมีผู้กระทำเป็นผู้ใช้")
    if event.actor_id != event.owner_user_id:
        raise AuditEventError(f"{name} ต้องมีผู้กระทำเป็นเจ้าของบัญชีนั้น")
    if event.subject_kind is not SubjectKind.API_KEY:
        raise AuditEventError(f"{name} ต้องมีเป้าหมายเป็น API key")
    if event.outcome is not AuditOutcome.SUCCEEDED:
        raise AuditEventError(f"{name} บันทึกเฉพาะกรณีที่สำเร็จ")


def _check_system_api_key_outcome(event: AuditEvent) -> None:
    """ผลการตรวจที่ระบบเป็นผู้ทำ — **ไม่มีผู้กระทำที่เป็นคน**

    `API_KEY_VERIFIED` สำเร็จและไม่มีรหัสเหตุผล ส่วนอีกสองชนิดต้องมีรหัสเสมอ
    เพราะผู้ใช้ต้องรู้ว่าต้องไปแก้อะไรหรือแค่รอ (Q-7)
    """
    name = event.action.value
    if event.actor_kind is not ActorKind.SYSTEM:
        raise AuditEventError(f"{name} ต้องมีผู้กระทำเป็นระบบ")
    if event.subject_kind is not SubjectKind.API_KEY:
        raise AuditEventError(f"{name} ต้องมีเป้าหมายเป็น API key")

    if event.action is AuditAction.API_KEY_VERIFIED:
        if event.outcome is not AuditOutcome.SUCCEEDED:
            raise AuditEventError(f"{name} บันทึกเฉพาะกรณีที่ผ่าน")
        return

    expected = (
        AuditOutcome.REJECTED
        if event.action is AuditAction.API_KEY_REJECTED
        else AuditOutcome.FAILED
    )
    if event.outcome is not expected:
        raise AuditEventError(f"{name} ต้องมีผลเป็น {expected.value}")
    if event.failure_code is None:
        raise AuditEventError(f"{name} ต้องมีรหัสเหตุผล")


def _check_paper_wallet_event(event: AuditEvent) -> None:
    if event.actor_kind is not ActorKind.USER or event.actor_id != event.owner_user_id:
        raise AuditEventError("เหตุการณ์ Paper wallet ต้องระบุผู้ใช้เจ้าของเป็นผู้กระทำ")
    if event.mode is not AuditMode.PAPER:
        raise AuditEventError("เหตุการณ์ Paper wallet ต้องอยู่ในโหมด PAPER")
    if event.action is AuditAction.PAPER_WALLET_CREATED:
        if event.subject_kind is not SubjectKind.PAPER_WALLET:
            raise AuditEventError("ผลสร้างกระเป๋าต้องมีเป้าหมายเป็น Paper wallet")
        if event.outcome is not AuditOutcome.SUCCEEDED:
            raise AuditEventError("PAPER_WALLET_CREATED ต้องสำเร็จ")
        return
    if event.subject_kind is not SubjectKind.PAPER_WALLET_COMMAND:
        raise AuditEventError("ผลปฏิเสธต้องมีเป้าหมายเป็นคำขอ Paper wallet")
    if event.outcome is not AuditOutcome.REJECTED or event.failure_code is None:
        raise AuditEventError("ผลปฏิเสธ Paper wallet ต้องมีรหัสเหตุผล")


#: ข้อบังคับเฉพาะของแต่ละเหตุการณ์ — **ทุกชนิดที่เพิ่มใหม่ต้องมีตัวตรวจของตัวเองที่นี่**
#: ถ้าไม่มี การสร้างบันทึกของชนิดนั้นจะล้มเหลวทันที ซึ่งเป็นผลที่ต้องการ
#: (ดังตอนเขียนโค้ด ดีกว่าปล่อยให้บันทึกที่ไม่มีใครตรวจไหลลงตารางที่ลบไม่ได้)
_ACTION_INVARIANTS: dict[AuditAction, Callable[[AuditEvent], None]] = {
    AuditAction.TRADING_USE_SELECTED: _check_own_account_action,
    AuditAction.USER_CREATED: _check_user_created,
    AuditAction.SESSION_STARTED: _check_own_account_action,
    AuditAction.SESSION_ENDED: _check_own_account_action,
    AuditAction.ALL_SESSIONS_ENDED: _check_own_account_action,
    AuditAction.PASSWORD_CHANGED: _check_own_account_action,
    AuditAction.TOTP_ENABLED: _check_own_account_action,
    AuditAction.TOTP_DISABLED: _check_own_account_action,
    AuditAction.TOTP_SECRET_REPLACED: _check_own_account_action,
    AuditAction.RECOVERY_CODES_ISSUED: _check_own_account_action,
    AuditAction.RECOVERY_CODE_USED: _check_own_account_action,
    AuditAction.API_KEY_ADDED: _check_own_api_key_action,
    AuditAction.API_KEY_RETRY_REQUESTED: _check_own_api_key_action,
    AuditAction.API_KEY_DELETED: _check_own_api_key_action,
    AuditAction.API_KEY_VERIFIED: _check_system_api_key_outcome,
    AuditAction.API_KEY_REJECTED: _check_system_api_key_outcome,
    AuditAction.API_KEY_VERIFICATION_DEFERRED: _check_system_api_key_outcome,
    AuditAction.PAPER_WALLET_CREATED: _check_paper_wallet_event,
    AuditAction.PAPER_WALLET_CREATE_REJECTED: _check_paper_wallet_event,
    AuditAction.PAPER_WALLET_RESET_REJECTED: _check_paper_wallet_event,
}


def money_detail(value: Money) -> dict[str, str]:
    """แปลงจำนวนเงินเป็นรูปแบบที่เก็บใน `details` ได้

    เก็บเป็น **ข้อความคู่กับหน่วย ไม่ใช่ตัวเลขของ JSON** เพราะตัวเลขของ JSON
    เป็นทศนิยมลอยตัว (`security.md` หัวข้อ 3, RQ-9)

    ใช้ข้อความมาตรฐานของ F-02 ไม่ใช่ `str()` ของ `Decimal` เพราะ `str()`
    ให้รูปแบบวิทยาศาสตร์กับค่าเล็ก ๆ (`1E-8`) ซึ่งเป็นค่าเดียวกันแต่หน้าตาต่างกัน
    บันทึกที่อ่านย้อนหลังต้องมีหน้าตาเดียวสำหรับค่าเดียว
    """
    parts = value.as_parts()
    return {"amount": parts["amount"], "unit": parts["currency"]}


def quantity_detail(value: Quantity) -> dict[str, str]:
    """แปลงปริมาณเป็นรูปแบบที่เก็บใน `details` ได้"""
    parts = value.as_parts()
    return {"amount": parts["quantity"], "unit": parts["asset"]}


@dataclass(frozen=True, slots=True)
class AuditEvent:
    """หนึ่งบันทึก — สร้างแล้วแก้ไม่ได้ และตรวจความถูกต้องตั้งแต่ตอนสร้าง

    ไม่มีช่องเวลา เพราะเวลามาจากฐานข้อมูลและผู้เรียกใส่เองไม่ได้ (RQ-6)
    """

    owner_user_id: UUID
    action: AuditAction
    actor_kind: ActorKind
    subject_kind: SubjectKind
    subject_id: str
    outcome: AuditOutcome
    details: AuditDetails
    mode: AuditMode = AuditMode.NOT_APPLICABLE
    actor_id: UUID | None = None
    failure_code: str | None = None

    def __post_init__(self) -> None:
        """จุดตรวจเดียวที่ทุกบันทึกต้องผ่าน

        เขียนไว้ที่นี่เพื่อให้การสร้างค่าโดยตรงก็เลี่ยงการตรวจไม่ได้
        (`backend.md` หัวข้อ 3 — ตรวจตั้งแต่ตอนสร้าง)
        """
        expected = DETAILS_TYPES[self.action]
        if not isinstance(self.details, expected):
            raise AuditEventError(
                f"เหตุการณ์ {self.action.value} ต้องใช้รายละเอียดชนิด {expected.__name__}"
                f" ไม่ใช่ {type(self.details).__name__}"
            )

        if self.action in TRADING_ACTIONS and self.mode is AuditMode.NOT_APPLICABLE:
            raise AuditEventError(f"เหตุการณ์การเทรด {self.action.value} ต้องระบุ PAPER หรือ LIVE")
        if self.action not in TRADING_ACTIONS and self.mode is not AuditMode.NOT_APPLICABLE:
            raise AuditEventError(
                f"เหตุการณ์ {self.action.value} ไม่เกี่ยวกับโหมด จึงระบุ {self.mode.value} ไม่ได้"
            )

        if self.actor_kind is ActorKind.SYSTEM and self.actor_id is not None:
            raise AuditEventError("ผู้กระทำที่เป็นระบบไม่มีรหัส")
        if self.actor_kind is not ActorKind.SYSTEM and self.actor_id is None:
            raise AuditEventError(f"ผู้กระทำชนิด {self.actor_kind.value} ต้องมีรหัส")

        if not self.subject_id:
            raise AuditEventError("ต้องระบุว่าทำกับอะไร")

        if self.outcome is AuditOutcome.SUCCEEDED and self.failure_code is not None:
            raise AuditEventError("เหตุการณ์ที่สำเร็จต้องไม่มีรหัสความล้มเหลว")

        if self.failure_code is not None and self.failure_code not in ALLOWED_FAILURE_CODES:
            raise AuditEventError(
                f"รหัสความล้มเหลว {self.failure_code!r} ยังไม่ได้ประกาศไว้"
                " — ต้องเพิ่มทั้งในโค้ดและใน migration ก่อนใช้"
            )

        _ACTION_INVARIANTS[self.action](self)
