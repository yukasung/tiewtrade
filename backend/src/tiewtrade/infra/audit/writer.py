"""ทางเขียนบันทึก — มีที่เดียว และอยู่ใน transaction เดียวกับการกระทำ (RQ-10, RQ-11)

รับเฉพาะ `UserSession` ผ่านตัวตรวจกลางของ F-03 จึงอยู่ใน transaction เดียวกับ
การกระทำ **โดยปริยาย ไม่ใช่โดยความตั้งใจของผู้เรียก** — ผู้เรียกที่ลืมคิดเรื่องนี้
ก็ยังได้พฤติกรรมที่ถูก

ผลที่ตามมาตามที่เจ้าของตัดสิน (Q-7): ลงบันทึกไม่สำเร็จ = การกระทำนั้นไม่เกิด
เพราะทั้งสองอย่างล้มเหลวหรือสำเร็จด้วยกัน
"""

from __future__ import annotations

import json
from uuid import UUID, uuid4

from tiewtrade.infra.audit.events import (
    ActorKind,
    AuditDetails,
    AuditEvent,
    AuditEventError,
    AuditOutcome,
    SubjectKind,
)
from tiewtrade.infra.audit.events import AuditAction as AuditAction
from tiewtrade.infra.audit.redaction import ensure_no_forbidden_content
from tiewtrade.infra.db.session import UserSession, require_user_session

_INSERT = (
    "INSERT INTO audit_events"
    " (id, owner_user_id, actor_kind, actor_id, action,"
    "  subject_kind, subject_id, mode, outcome, failure_code, details)"
    " VALUES (:id, :owner_user_id, :actor_kind, :actor_id, :action,"
    "  :subject_kind, :subject_id, :mode, :outcome, :failure_code,"
    "  CAST(:details AS jsonb))"
)


async def record_event(session: object, event: AuditEvent) -> None:
    """ลงบันทึกหนึ่งรายการในขอบเขตของผู้ใช้ที่ session นั้นถืออยู่

    เจ้าของบันทึกต้องเป็นผู้ใช้เดียวกับ session — RLS บังคับข้อนี้ที่ฐานข้อมูลอยู่แล้ว
    แต่ตรวจที่นี่ด้วยเพื่อให้ข้อผิดพลาดบอกสาเหตุตรง ๆ แทนที่จะเป็น "ไม่มีสิทธิ์"
    """
    checked = require_user_session(session)
    if event.owner_user_id != checked.user_id:
        raise AuditEventError("บันทึกต้องเป็นของผู้ใช้เดียวกับ session ที่ใช้เขียน")

    details = event.details.as_details()
    ensure_no_forbidden_content(details)
    # คอลัมน์แกนที่เป็นข้อความก็ต้องผ่านตาข่ายเดียวกัน — ไม่ใช่ตรวจแค่ `details`
    # ข้อบังคับรายเหตุการณ์ใน `events.py` กันไว้ชั้นแรกแล้ว ชั้นนี้กันเหตุการณ์ในอนาคต
    # ที่ `subject_id` เป็นรหัสจากภายนอก (เช่น รหัสออเดอร์ของ Binance)
    ensure_no_forbidden_content({"subject_id": event.subject_id})
    if event.failure_code is not None:
        ensure_no_forbidden_content({"failure_code": event.failure_code})

    await checked.execute(
        _INSERT,
        {
            "id": str(uuid4()),
            "owner_user_id": str(event.owner_user_id),
            "actor_kind": event.actor_kind.value,
            "actor_id": None if event.actor_id is None else str(event.actor_id),
            "action": event.action.value,
            "subject_kind": event.subject_kind.value,
            "subject_id": event.subject_id,
            "mode": event.mode.value,
            "outcome": event.outcome.value,
            "failure_code": event.failure_code,
            "details": json.dumps(details, ensure_ascii=False, sort_keys=True),
        },
    )


async def record_own_action(
    session: UserSession, user_id: UUID, action: AuditAction, details: AuditDetails
) -> None:
    """ลงบันทึกเหตุการณ์ที่ผู้ใช้ทำกับบัญชีตัวเอง — คอลัมน์แกนชุดเดียวกันทุกชนิด

    เหตุการณ์ของ F-05 และ F-06 เกือบทั้งหมดมีรูปนี้ (ผู้กระทำและเป้าหมายคือเจ้าของ
    บันทึก ผลคือสำเร็จ) **เขียนแยกทุกที่คือทุกที่ที่ต้องแก้ให้ตรงกันเมื่อกฎเปลี่ยน**
    · ตัวตรวจ invariant ของ `events.py` บังคับรูปเดียวกันนี้อยู่แล้ว ฟังก์ชันนี้จึง
    เป็นความสะดวก ไม่ใช่ที่ที่กฎอยู่
    """
    await record_event(
        session,
        AuditEvent(
            owner_user_id=user_id,
            action=action,
            actor_kind=ActorKind.USER,
            actor_id=user_id,
            subject_kind=SubjectKind.USER,
            subject_id=str(user_id),
            outcome=AuditOutcome.SUCCEEDED,
            details=details,
        ),
    )
