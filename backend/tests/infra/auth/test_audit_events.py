"""บันทึกเหตุการณ์ของการยืนยันตัวตน — V-46 ถึง V-50

กฎของ F-04: **ชนิดเหตุการณ์ต้องประกาศครบสามที่** — `AuditAction`, ตัวตรวจ invariant
และ `CHECK` ใน migration ชนิดที่ไม่ได้ประกาศเขียนลงฐานข้อมูลไม่ได้เลย
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.auth.conftest import make_account
from tiewtrade.infra.audit import (
    DETAILS_TYPES,
    ActorKind,
    AllSessionsEndedDetails,
    AuditAction,
    AuditEvent,
    AuditEventError,
    AuditOutcome,
    SessionDetails,
    SubjectKind,
    record_event,
)
from tiewtrade.infra.db import DatabaseRole
from tiewtrade.infra.db.session import user_session

#: สี่ชนิดที่งานนี้เพิ่ม
NEW_ACTIONS = (
    AuditAction.SESSION_STARTED,
    AuditAction.SESSION_ENDED,
    AuditAction.ALL_SESSIONS_ENDED,
    AuditAction.PASSWORD_CHANGED,
)


def test_every_new_action_declares_the_shape_of_its_details() -> None:
    """V-47 — ประกาศครบในโค้ด: ชนิดเหตุการณ์คู่กับรูปร่างของ `details`"""
    for action in NEW_ACTIONS:
        assert action in DETAILS_TYPES, f"{action.value} ไม่ได้ประกาศรูปร่างของ details"


def test_ending_all_sessions_records_how_many_were_ended() -> None:
    """V-48 — ออกทุกเครื่องมีจำนวนติดไปด้วย ซึ่งอ่านย้อนหลังได้ว่าออกจากกี่เครื่อง"""
    assert AllSessionsEndedDetails(ended=3).as_details() == {"ended": 3}
    with pytest.raises(AuditEventError):
        AllSessionsEndedDetails(ended=-1)


def test_the_two_kinds_of_logout_are_different_events() -> None:
    """V-48 — ออกเครื่องเดียวกับออกทุกเครื่องแยกกัน เพราะผลต่างกัน"""
    assert {AuditAction.SESSION_ENDED, AuditAction.ALL_SESSIONS_ENDED} <= set(NEW_ACTIONS)
    assert DETAILS_TYPES[AuditAction.SESSION_ENDED] is SessionDetails
    assert DETAILS_TYPES[AuditAction.ALL_SESSIONS_ENDED] is AllSessionsEndedDetails


@pytest.mark.parametrize("action", NEW_ACTIONS, ids=lambda action: action.value)
def test_an_event_of_someone_else_is_refused_when_it_is_built(action: AuditAction) -> None:
    """V-47 — ตัวตรวจ invariant ปฏิเสธบันทึกที่ผู้กระทำไม่ใช่เจ้าของบัญชี

    ดังตอนสร้างค่า ไม่ใช่ตอนเขียนลงฐานข้อมูล จึงไม่มีทางหลุดไปถึงตารางที่ลบไม่ได้
    """
    owner, stranger = uuid4(), uuid4()
    details = (
        AllSessionsEndedDetails(ended=1)
        if action is AuditAction.ALL_SESSIONS_ENDED
        else DETAILS_TYPES[action]()
    )
    with pytest.raises(AuditEventError):
        AuditEvent(
            owner_user_id=owner,
            action=action,
            actor_kind=ActorKind.USER,
            actor_id=stranger,
            subject_kind=SubjectKind.USER,
            subject_id=str(owner),
            outcome=AuditOutcome.SUCCEEDED,
            details=details,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("action", NEW_ACTIONS, ids=lambda action: action.value)
async def test_each_new_action_can_be_written_to_the_database(
    auth_engine: AsyncEngine, action: AuditAction
) -> None:
    """V-47 — `CHECK` ใน migration ยอมรับทั้งสี่ชนิด

    ถ้าชนิดใดประกาศในโค้ดแต่ลืมใน migration ฐานข้อมูลจะปฏิเสธ ซึ่งเทสต์นี้จะจับได้
    """
    user_id, _ = await make_account(auth_engine)
    details = (
        AllSessionsEndedDetails(ended=2)
        if action is AuditAction.ALL_SESSIONS_ENDED
        else DETAILS_TYPES[action]()
    )
    async with user_session(auth_engine, user_id, role=DatabaseRole.AUTH) as session:
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
                details=details,  # type: ignore[arg-type]
            ),
        )
        written = (
            await session.execute(
                "SELECT count(*) FROM audit_events WHERE owner_user_id = :u AND action = :a",
                {"u": str(user_id), "a": action.value},
            )
        ).one()
    assert written[0] == 1


def test_the_details_of_the_new_events_carry_nothing_identifying() -> None:
    """V-50 — ไม่มีอีเมล โทเคน หรือแฮชของโทเคนใน `details` ของเหตุการณ์ใด"""
    assert SessionDetails().as_details() == {}
    assert set(AllSessionsEndedDetails(ended=1).as_details()) == {"ended"}
