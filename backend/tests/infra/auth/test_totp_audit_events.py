"""บันทึกเหตุการณ์ของ TOTP และรหัสสำรอง — V-54 ถึง V-58

กฎของ F-04: **ชนิดเหตุการณ์ต้องประกาศครบสามที่** — `AuditAction`, ตัวตรวจ invariant
และ `CHECK` ใน migration · ชนิดที่ประกาศไม่ครบจะดังที่ใดที่หนึ่งในสามเทสต์แรก
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.auth.conftest import make_account
from tiewtrade.infra.audit import (
    DETAILS_TYPES,
    ActorKind,
    AuditAction,
    AuditEvent,
    AuditEventError,
    AuditOutcome,
    RecoveryCodesIssuedDetails,
    RecoveryCodeUsedDetails,
    SubjectKind,
    TotpChangeDetails,
    record_event,
)
from tiewtrade.infra.db import DatabaseRole
from tiewtrade.infra.db.errors import InfraError
from tiewtrade.infra.db.session import user_session

#: ห้าชนิดที่งานนี้เพิ่ม
NEW_ACTIONS = (
    AuditAction.TOTP_ENABLED,
    AuditAction.TOTP_DISABLED,
    AuditAction.TOTP_SECRET_REPLACED,
    AuditAction.RECOVERY_CODES_ISSUED,
    AuditAction.RECOVERY_CODE_USED,
)


def details_for(action: AuditAction) -> object:
    """รายละเอียดที่ถูกชนิดของเหตุการณ์นั้น"""
    if action is AuditAction.RECOVERY_CODES_ISSUED:
        return RecoveryCodesIssuedDetails(issued=8)
    if action is AuditAction.RECOVERY_CODE_USED:
        return RecoveryCodeUsedDetails(remaining=7)
    return TotpChangeDetails()


def test_every_new_action_declares_the_shape_of_its_details() -> None:
    """V-54 ที่หนึ่งในสาม — ประกาศในโค้ด: ชนิดเหตุการณ์คู่กับรูปร่างของ `details`"""
    for action in NEW_ACTIONS:
        assert action in DETAILS_TYPES, f"{action.value} ไม่ได้ประกาศรูปร่างของ details"


@pytest.mark.parametrize("action", NEW_ACTIONS, ids=lambda action: action.value)
def test_an_event_of_someone_else_is_refused_when_it_is_built(action: AuditAction) -> None:
    """V-57 ที่สองในสาม — ตัวตรวจ invariant ปฏิเสธบันทึกที่ผู้กระทำไม่ใช่เจ้าของบัญชี

    ดังตอนสร้างค่า ไม่ใช่ตอนเขียน จึงไม่มีทางหลุดไปถึงตารางที่ลบไม่ได้
    """
    owner, stranger = uuid4(), uuid4()

    with pytest.raises(AuditEventError):
        AuditEvent(
            owner_user_id=owner,
            action=action,
            actor_kind=ActorKind.USER,
            actor_id=stranger,
            subject_kind=SubjectKind.USER,
            subject_id=str(owner),
            outcome=AuditOutcome.SUCCEEDED,
            details=details_for(action),  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("action", NEW_ACTIONS, ids=lambda action: action.value)
async def test_each_new_action_can_be_written_to_the_database(
    auth_engine: AsyncEngine, action: AuditAction
) -> None:
    """V-54 ที่สามในสาม — `CHECK` ใน migration ยอมรับทั้งห้าชนิด

    ชนิดที่ประกาศในโค้ดแต่ลืมใน migration จะถูกฐานข้อมูลปฏิเสธที่นี่
    """
    user_id, _ = await make_account(auth_engine)

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
                details=details_for(action),  # type: ignore[arg-type]
            ),
        )
        written = (
            await session.execute(
                "SELECT count(*) FROM audit_events WHERE owner_user_id = :u AND action = :a",
                {"u": str(user_id), "a": action.value},
            )
        ).one()

    assert next(iter(written)) == 1


@pytest.mark.parametrize("action", NEW_ACTIONS, ids=lambda action: action.value)
async def test_the_database_refuses_a_mismatched_details_shape(
    auth_engine: AsyncEngine, action: AuditAction
) -> None:
    """V-55 ชั้นที่สอง — เขียนตรงเข้าฐานข้อมูลด้วยรูปร่างที่ไม่ตรง ต้องถูกปฏิเสธ

    ชั้นแรกคือชนิดข้อมูลของ `details` ซึ่งเทสต์ `test_details_type_must_match_the_action`
    ของ F-04 ครอบอยู่แล้ว · ชั้นนี้คือกรณีที่มีคนเขียนตรงโดยไม่ผ่านตัวเขียน
    """
    user_id, _ = await make_account(auth_engine)
    wrong = '{"note": "ข้อความอิสระที่ไม่ควรเขียนได้"}'

    async with user_session(auth_engine, user_id, role=DatabaseRole.AUTH) as session:
        with pytest.raises(InfraError):
            await session.execute(
                "INSERT INTO audit_events"
                " (id, owner_user_id, actor_kind, actor_id, action, subject_kind,"
                "  subject_id, mode, outcome, details)"
                " VALUES (:id, :u, 'USER', :u, :a, 'USER', :s, 'NOT_APPLICABLE',"
                "         'SUCCEEDED', :d::jsonb)",
                {
                    "id": str(uuid4()),
                    "u": str(user_id),
                    "a": action.value,
                    "s": str(user_id),
                    "d": wrong,
                },
            )


async def test_the_database_refuses_an_action_that_is_not_declared(
    auth_engine: AsyncEngine,
) -> None:
    """V-54 — ชนิดที่ไม่ได้ประกาศเขียนลงฐานข้อมูลไม่ได้เลย"""
    user_id, _ = await make_account(auth_engine)

    async with user_session(auth_engine, user_id, role=DatabaseRole.AUTH) as session:
        with pytest.raises(InfraError):
            await session.execute(
                "INSERT INTO audit_events"
                " (id, owner_user_id, actor_kind, actor_id, action, subject_kind,"
                "  subject_id, mode, outcome, details)"
                " VALUES (:id, :u, 'USER', :u, 'TOTP_GUESS_FAILED', 'USER', :s,"
                "         'NOT_APPLICABLE', 'SUCCEEDED', '{}'::jsonb)",
                {"id": str(uuid4()), "u": str(user_id), "s": str(user_id)},
            )


def test_the_counts_are_checked_when_they_are_built() -> None:
    """V-56 — จำนวนที่เป็นไปไม่ได้ต้องดังตอนสร้าง ไม่ใช่ลงบันทึกไปแล้วค่อยรู้"""
    assert RecoveryCodesIssuedDetails(issued=8).as_details() == {"issued": 8}
    assert RecoveryCodeUsedDetails(remaining=0).as_details() == {"remaining": 0}

    with pytest.raises(AuditEventError):
        RecoveryCodesIssuedDetails(issued=0)
    with pytest.raises(AuditEventError):
        RecoveryCodeUsedDetails(remaining=-1)


def test_the_details_carry_nothing_about_the_secret() -> None:
    """V-56 — **ไม่มี secret, แฮช, รุ่นของกุญแจ, อุปกรณ์ หรือ IP ในรายละเอียดใด**"""
    assert TotpChangeDetails().as_details() == {}
    assert set(RecoveryCodesIssuedDetails(issued=1).as_details()) == {"issued"}
    assert set(RecoveryCodeUsedDetails(remaining=1).as_details()) == {"remaining"}


def test_there_is_no_event_for_a_wrong_code() -> None:
    """V-58 — **ไม่มีชนิดเหตุการณ์สำหรับรหัสที่กรอกผิด**

    ตารางนี้เพิ่มได้อย่างเดียว ถ้าเขียนทุกครั้งที่ผิด ผู้โจมตีจะทำให้ตารางโตได้ตามใจ
    เทสต์นี้ตรึงการตัดสินใจนั้นไว้ ไม่ให้ใครเพิ่มภายหลังโดยไม่ทบทวนเหตุผล
    """
    names = {action.value for action in AuditAction}

    assert not {name for name in names if "FAILED" in name or "WRONG" in name}
