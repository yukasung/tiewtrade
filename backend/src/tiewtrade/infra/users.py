"""ตารางผู้ใช้ — ผู้ใช้จริงรายแรกของกลไกใน `infra.db` (plan.md ข้อ 6)

ทุกทางเข้าในไฟล์นี้รับเฉพาะ `UserSession` และผ่าน `require_user_session`
ซึ่งเป็นตัวตรวจกลางตัวเดียวของทั้งระบบ — ไม่มีทางเข้าที่รับ connection ดิบ
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.infra.audit import (
    ActorKind,
    AuditAction,
    AuditEvent,
    AuditOutcome,
    SubjectKind,
    UserCreatedDetails,
    record_event,
)
from tiewtrade.infra.db.engine import DatabaseRole
from tiewtrade.infra.db.errors import SessionKindError
from tiewtrade.infra.db.session import UserSession, require_user_session, user_session


@dataclass(frozen=True, slots=True)
class UserRow:
    """แถวผู้ใช้หนึ่งแถว — `id` เป็นคอลัมน์เจ้าของของตัวเอง (Q-1.1)"""

    id: UUID
    created_at: datetime


async def create_user_in(session: UserSession, user_id: UUID) -> None:
    """เพิ่มแถวผู้ใช้ใหม่ **บน transaction ที่ผู้เรียกเปิดไว้แล้ว**

    **ไม่ส่ง `created_at`** เพราะบทบาทที่ใช้ตอนทำงานปกติไม่มีสิทธิ์เขียนคอลัมน์นั้น
    ส่งไปจะถูกฐานข้อมูลปฏิเสธ ไม่ใช่ถูกเมิน (F-03 RQ-10.1)

    มีไว้ให้เส้นทางสมัครของ F-05 ซึ่งต้องสร้างผู้ใช้ ข้อมูลเข้าสู่ระบบ และ session
    **ในก้อนเดียว** — ถ้าแต่ละขั้นเปิด transaction ของตัวเอง การล้มเหลวกลางทาง
    จะเหลือผู้ใช้ที่มีตัวตนแต่เข้าสู่ระบบไม่ได้ และสมัครอีเมลเดิมซ้ำก็ไม่ได้

    ผู้ใช้ปัจจุบันของ `session` ต้องเป็นแถวที่กำลังสร้าง เพราะ policy บังคับว่า `id`
    ต้องตรงกับผู้ใช้ปัจจุบัน — สร้างแถวให้คนอื่นจึงทำไม่ได้ (F-03 Q-1.1 ข้อ 3)
    """
    if session.user_id != user_id:
        raise SessionKindError("สร้างผู้ใช้ได้เฉพาะแถวที่เป็นผู้ใช้ปัจจุบันของ transaction")

    await session.execute("INSERT INTO users (id) VALUES (:id)", {"id": str(user_id)})
    await record_event(
        session,
        AuditEvent(
            owner_user_id=user_id,
            action=AuditAction.USER_CREATED,
            actor_kind=ActorKind.USER,
            actor_id=user_id,
            subject_kind=SubjectKind.USER,
            subject_id=str(user_id),
            outcome=AuditOutcome.SUCCEEDED,
            details=UserCreatedDetails(),
        ),
    )


async def create_user(
    engine: AsyncEngine, user_id: UUID, *, role: DatabaseRole = DatabaseRole.API
) -> None:
    """เพิ่มแถวผู้ใช้ใหม่ โดยเปิด transaction ให้เอง

    ผู้ใช้ปัจจุบันของ transaction คือแถวที่กำลังสร้าง เพราะ policy บังคับว่า
    `id` ต้องตรงกับผู้ใช้ปัจจุบัน — สร้างแถวให้คนอื่นจึงทำไม่ได้ (Q-1.1 ข้อ 3)

    **ไม่ส่ง `created_at`** เพราะบทบาทที่ใช้ตอนทำงานปกติไม่มีสิทธิ์เขียนคอลัมน์นั้น
    ส่งไปจะถูกฐานข้อมูลปฏิเสธ ไม่ใช่ถูกเมิน (RQ-10.1)

    ลงบันทึกใน transaction เดียวกัน (F-04 RQ-10) — ลงบันทึกไม่สำเร็จแปลว่า
    ผู้ใช้ไม่ถูกสร้าง และผู้ใช้ถูกสร้างแปลว่ามีบันทึกแล้วแน่นอน

    ตัวงานจริงอยู่ใน `create_user_in` — ที่นี่เพียงเปิด transaction ให้
    เพื่อไม่ให้มีขั้นตอนการสร้างผู้ใช้สองชุดที่ต้องแก้ให้ตรงกัน
    """
    async with user_session(engine, user_id, role=role) as session:
        await create_user_in(session, user_id)


async def fetch_user(session: object, user_id: UUID) -> UserRow | None:
    """อ่านแถวผู้ใช้ — คืน `None` เมื่อไม่พบ

    ขอแถวของผู้ใช้อื่นได้ผลว่า "ไม่พบ" ตามที่ RLS กรองให้ ไม่ใช่ "ไม่มีสิทธิ์"
    (`standards/security.md` หัวข้อ 2, RQ-16)
    """
    checked = require_user_session(session)
    result = await checked.execute(
        "SELECT id, created_at FROM users WHERE id = :id", {"id": str(user_id)}
    )
    row = result.one_or_none()
    if row is None:
        return None
    found_id, created_at = tuple(row)
    if not isinstance(found_id, UUID) or not isinstance(created_at, datetime):
        msg = "ฐานข้อมูลคืนชนิดข้อมูลที่ไม่คาดไว้สำหรับตาราง users"
        raise TypeError(msg)
    return UserRow(id=found_id, created_at=created_at)
