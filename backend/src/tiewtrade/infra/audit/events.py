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


class AuditEventError(InfraError):
    """บันทึกที่ประกอบไม่ถูกต้อง — ชนิดที่ผู้เรียกดักได้ (RQ-12)"""

    code = "AUDIT_EVENT_INVALID"


class AuditAction(Enum):
    """ชนิดเหตุการณ์ที่ประกาศไว้แล้ว

    **ต้องตรงกับ `CHECK` ใน migration 0004** การเพิ่มชนิดใหม่ต้องแก้ทั้งสองที่
    ในงานเดียวกัน พร้อมประกาศรูปร่างของ `details` และเทสต์ (Q-1)
    """

    USER_CREATED = "USER_CREATED"


#: ชนิดเหตุการณ์ที่เป็นการเทรด — ต้องระบุ PAPER หรือ LIVE เสมอ (RQ-19)
#: ยังว่างเพราะยังไม่มีงานที่แตะการเทรด งานที่เพิ่มต้องใส่ชื่อเหตุการณ์ของตัวเองที่นี่
TRADING_ACTIONS: frozenset[AuditAction] = frozenset()


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


#: รูปร่างของ `details` ที่แต่ละชนิดเหตุการณ์ใช้ได้ — ตรวจตอนสร้าง `AuditEvent`
DETAILS_TYPES: dict[AuditAction, type[object]] = {
    AuditAction.USER_CREATED: UserCreatedDetails,
}

#: รหัสความล้มเหลวที่ประกาศไว้แล้ว — **ยังว่าง** เพราะยังไม่มีเหตุการณ์ที่ล้มเหลวได้
#:
#: `failure_code` เป็นรหัส ไม่ใช่ข้อความอิสระ (`backend.md` หัวข้อ 4) ช่องข้อความอิสระ
#: คือทางที่ค่าลับและข้อมูลระบุตัวตนเข้ามาได้ (RQ-4, RQ-18) จึงต้องประกาศทีละรหัส
#: พร้อม migration เหมือนการเพิ่มชนิดเหตุการณ์
ALLOWED_FAILURE_CODES: frozenset[str] = frozenset()


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


#: ข้อบังคับเฉพาะของแต่ละเหตุการณ์ — **ทุกชนิดที่เพิ่มใหม่ต้องมีตัวตรวจของตัวเองที่นี่**
#: ถ้าไม่มี การสร้างบันทึกของชนิดนั้นจะล้มเหลวทันที ซึ่งเป็นผลที่ต้องการ
#: (ดังตอนเขียนโค้ด ดีกว่าปล่อยให้บันทึกที่ไม่มีใครตรวจไหลลงตารางที่ลบไม่ได้)
_ACTION_INVARIANTS: dict[AuditAction, Callable[[AuditEvent], None]] = {
    AuditAction.USER_CREATED: _check_user_created,
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
