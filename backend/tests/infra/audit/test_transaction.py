"""บันทึกก่อน แล้วค่อยทำ — V-28 ถึง V-31

เจ้าของตัดสินว่า **ลงบันทึกไม่ได้ก็ไม่ทำการนั้น** (Q-7) ขอบเขตคือการเปลี่ยนข้อมูล
ใน PostgreSQL ซึ่งทำได้จริงด้วย transaction เดียวกัน การส่งคำสั่งออกนอกระบบ
เป็นอีกเรื่องที่ต้องออกแบบแยก และยังไม่มีในงานนี้
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.infra.audit import (
    ActorKind,
    AuditAction,
    AuditEvent,
    AuditEventError,
    AuditOutcome,
    SubjectKind,
    UserCreatedDetails,
    record_event,
)
from tiewtrade.infra.db import InfraError, SessionKindError, ValueRejectedError, user_session
from tiewtrade.infra.db.session import scan_session_bypassing_rls
from tiewtrade.infra.users import create_user


def _event(owner: object) -> AuditEvent:
    from uuid import UUID

    assert isinstance(owner, UUID)
    return AuditEvent(
        owner_user_id=owner,
        action=AuditAction.USER_CREATED,
        actor_kind=ActorKind.USER,
        actor_id=owner,
        subject_kind=SubjectKind.USER,
        subject_id=str(owner),
        outcome=AuditOutcome.SUCCEEDED,
        details=UserCreatedDetails(),
    )


async def _count_events(engine: AsyncEngine, owner: object) -> int:
    from uuid import UUID

    assert isinstance(owner, UUID)
    async with user_session(engine, owner) as session:
        result = await session.execute(
            "SELECT count(*) FROM audit_events WHERE owner_user_id = :id", {"id": str(owner)}
        )
        count: int = result.scalar_one()
    return count


async def test_failed_action_leaves_no_event_behind(api_engine: AsyncEngine) -> None:
    """V-28 — การกระทำล้มเหลวหลังลงบันทึก → ไม่มีบันทึกค้าง"""
    user_id = uuid4()
    with pytest.raises(InfraError):
        async with user_session(api_engine, user_id) as session:
            await record_event(session, _event(user_id))
            # ทำให้ transaction ล้มเหลวหลังลงบันทึกไปแล้ว
            await session.execute("SELECT 1 / 0")

    assert await _count_events(api_engine, user_id) == 0


async def test_failed_event_write_cancels_the_action(api_engine: AsyncEngine) -> None:
    """V-29 — ลงบันทึกไม่สำเร็จ → การกระทำไม่เกิด

    บังคับให้การลงบันทึกล้มเหลวด้วยชนิดเหตุการณ์ที่ฐานข้อมูลไม่รู้จัก
    แล้วตรวจว่าแถวผู้ใช้ที่เขียนไปก่อนหน้าในเดียวกันไม่เหลืออยู่
    """
    user_id = uuid4()
    with pytest.raises(ValueRejectedError):
        async with user_session(api_engine, user_id) as session:
            await session.execute("INSERT INTO users (id) VALUES (:id)", {"id": str(user_id)})
            await session.execute(
                "INSERT INTO audit_events"
                " (id, owner_user_id, actor_kind, actor_id, action, subject_kind,"
                "  subject_id, mode, outcome, details)"
                " VALUES (gen_random_uuid(), CAST(:owner AS uuid), 'USER',"
                "  CAST(:owner AS uuid), 'UNKNOWN_ACTION', 'USER', :subject,"
                "  'NOT_APPLICABLE', 'SUCCEEDED', '{}'::jsonb)",
                {"owner": str(user_id), "subject": str(user_id)},
            )

    # นับด้วย identity ของผู้ใช้เอง เพราะเจ้าของตารางก็อยู่ใต้ policy
    async with user_session(api_engine, user_id) as session:
        result = await session.execute(
            "SELECT count(*) FROM users WHERE id = :id", {"id": str(user_id)}
        )
        users: int = result.scalar_one()
    assert users == 0, "ผู้ใช้ถูกสร้างทั้งที่บันทึกล้มเหลว"


async def test_writer_refuses_scan_session(scan_engine: AsyncEngine) -> None:
    """V-30 — ทางเขียนรับเฉพาะ `UserSession`"""
    async with scan_session_bypassing_rls(scan_engine) as scan:
        with pytest.raises(SessionKindError):
            await record_event(scan, _event(uuid4()))


async def test_writer_refuses_raw_connection(api_engine: AsyncEngine) -> None:
    """V-30 — connection ดิบก็เข้าไม่ได้"""
    async with api_engine.connect() as connection:
        with pytest.raises(SessionKindError):
            await record_event(connection, _event(uuid4()))


async def test_writer_refuses_event_of_another_user(api_engine: AsyncEngine) -> None:
    """เจ้าของบันทึกต้องเป็นผู้ใช้เดียวกับ session — ดังก่อนถึงฐานข้อมูล"""
    async with user_session(api_engine, uuid4()) as session:
        with pytest.raises(AuditEventError):
            await record_event(session, _event(uuid4()))


async def test_create_user_always_records(api_engine: AsyncEngine) -> None:
    """V-31 — ผู้ผลิตรายแรกลงบันทึกทุกครั้ง"""
    user_id = uuid4()
    await create_user(api_engine, user_id)

    async with user_session(api_engine, user_id) as session:
        result = await session.execute(
            "SELECT action, subject_id FROM audit_events WHERE owner_user_id = :id",
            {"id": str(user_id)},
        )
        rows = [tuple(row) for row in result.all()]

    assert rows == [("USER_CREATED", str(user_id))]


async def test_user_row_and_event_appear_together(api_engine: AsyncEngine) -> None:
    """ผู้ใช้กับบันทึกเกิดพร้อมกัน — ไม่มีสถานะที่มีผู้ใช้แต่ไม่มีบันทึก"""
    user_id = uuid4()
    await create_user(api_engine, user_id)

    async with user_session(api_engine, user_id) as session:
        users = (
            await session.execute("SELECT count(*) FROM users WHERE id = :id", {"id": str(user_id)})
        ).scalar_one()
        events = (
            await session.execute(
                "SELECT count(*) FROM audit_events WHERE owner_user_id = :id",
                {"id": str(user_id)},
            )
        ).scalar_one()

    assert (users, events) == (1, 1)
