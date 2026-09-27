"""รูปร่างของบันทึก — V-16 ถึง V-23

หลักประกันหลักของการห้ามข้อมูลลับคือ **รายการที่อนุญาต** ไม่ใช่รายการที่ห้าม
ฉะนั้นเทสต์ที่สำคัญที่สุดในไฟล์นี้คือกรณีที่ช่องซึ่งไม่ได้ประกาศไว้ต้องเขียนไม่ได้
ทั้งที่ชั้นโค้ดและที่ชั้นฐานข้อมูล
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.core.money import Money, Quantity
from tiewtrade.infra.audit import (
    ActorKind,
    AuditAction,
    AuditEvent,
    AuditEventError,
    AuditMode,
    AuditOutcome,
    SubjectKind,
    UserCreatedDetails,
    money_detail,
    quantity_detail,
)
from tiewtrade.infra.db import CURRENT_USER_SETTING, ValueRejectedError, user_session
from tiewtrade.infra.users import create_user

_INSERT_RAW = (
    "INSERT INTO audit_events"
    " (id, owner_user_id, actor_kind, actor_id, action, subject_kind,"
    "  subject_id, mode, outcome, details)"
    " VALUES (gen_random_uuid(), CAST(:owner AS uuid), :actor_kind, CAST(:owner AS uuid),"
    "  :action, 'USER', :subject, :mode, :outcome, CAST(:details AS jsonb))"
)


def _base_params(owner: str) -> dict[str, object]:
    return {
        "owner": owner,
        "actor_kind": "USER",
        "action": "USER_CREATED",
        "subject": owner,
        "mode": "NOT_APPLICABLE",
        "outcome": "SUCCEEDED",
        "details": "{}",
    }


async def test_recorded_event_has_all_five_things(api_engine: AsyncEngine) -> None:
    """V-16 — ใครทำ ทำอะไร กับอะไร เมื่อไหร่ ผลเป็นอย่างไร"""
    user_id = uuid4()
    await create_user(api_engine, user_id)

    async with user_session(api_engine, user_id) as session:
        row = (
            await session.execute(
                "SELECT actor_kind, actor_id, action, subject_kind, subject_id,"
                " recorded_at, outcome, mode, failure_code, details"
                " FROM audit_events WHERE owner_user_id = :id",
                {"id": str(user_id)},
            )
        ).one()

    actor_kind, actor_id, action, subject_kind, subject_id = tuple(row)[:5]
    recorded_at, outcome, mode, failure_code, details = tuple(row)[5:]

    assert actor_kind == "USER"
    assert actor_id == user_id
    assert action == "USER_CREATED"
    assert subject_kind == "USER"
    assert subject_id == str(user_id)
    assert isinstance(recorded_at, datetime)
    assert recorded_at <= datetime.now(UTC)
    assert outcome == "SUCCEEDED"
    assert mode == "NOT_APPLICABLE"
    assert failure_code is None
    assert details == {}


async def test_caller_cannot_set_recorded_at(api_engine: AsyncEngine) -> None:
    """V-17 — ผู้เรียกใส่เวลาเองไม่ได้"""
    user_id = uuid4()
    async with user_session(api_engine, user_id) as session:
        with pytest.raises(Exception) as caught:
            await session.execute(
                "INSERT INTO audit_events"
                " (id, recorded_at, owner_user_id, actor_kind, actor_id, action,"
                "  subject_kind, subject_id, mode, outcome, details)"
                " VALUES (gen_random_uuid(), :when, CAST(:owner AS uuid), 'USER',"
                "  CAST(:owner AS uuid), 'USER_CREATED', 'USER', :subject,"
                "  'NOT_APPLICABLE', 'SUCCEEDED', '{}'::jsonb)",
                {
                    "when": datetime(1999, 1, 1, tzinfo=UTC),
                    "owner": str(user_id),
                    "subject": str(user_id),
                },
            )
    assert caught.value.__class__.__name__ in {"NotPermittedError", "InfraError"}


async def test_unknown_action_is_rejected_by_the_database(api_engine: AsyncEngine) -> None:
    """V-18 — ชนิดเหตุการณ์ที่ไม่ได้ประกาศไว้ เขียนไม่ได้เลย"""
    user_id = uuid4()
    params = _base_params(str(user_id)) | {"action": "MONEY_MOVED"}
    async with user_session(api_engine, user_id) as session:
        with pytest.raises(ValueRejectedError):
            await session.execute(_INSERT_RAW, params)


async def test_details_with_unexpected_field_is_rejected_by_the_database(
    api_engine: AsyncEngine,
) -> None:
    """V-18.1, V-18.2 — `details` ที่มีช่องซึ่งไม่ได้ประกาศไว้ เขียนไม่ได้

    ทดสอบที่ชั้นฐานข้อมูล คือเส้นทางที่เลี่ยงตัวเขียนของเราได้
    """
    user_id = uuid4()
    params = _base_params(str(user_id)) | {"details": json.dumps({"note": "อะไรก็ได้"})}
    async with user_session(api_engine, user_id) as session:
        with pytest.raises(ValueRejectedError):
            await session.execute(_INSERT_RAW, params)


def test_details_type_must_match_the_action() -> None:
    """V-18.1 ที่ชั้นโค้ด — ผู้เรียกส่ง dict อิสระไม่ได้ ต้องเป็นชนิดของเหตุการณ์นั้น"""

    @dataclass(frozen=True)
    class Impostor:
        def as_details(self) -> dict[str, object]:
            return {"note": "ค่าลับ"}

    with pytest.raises(AuditEventError):
        AuditEvent(
            owner_user_id=uuid4(),
            action=AuditAction.USER_CREATED,
            actor_kind=ActorKind.SYSTEM,
            subject_kind=SubjectKind.USER,
            subject_id="x",
            outcome=AuditOutcome.SUCCEEDED,
            details=Impostor(),
        )


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("actor_kind", "ROBOT"),
        ("mode", "SEMI_LIVE"),
        ("outcome", "MAYBE"),
    ],
)
async def test_enumerated_columns_reject_unknown_values(
    api_engine: AsyncEngine, column: str, value: str
) -> None:
    """V-19 — คอลัมน์ที่มีชุดค่าจำกัด รับเฉพาะค่าที่ประกาศไว้"""
    user_id = uuid4()
    params = _base_params(str(user_id)) | {column: value}
    async with user_session(api_engine, user_id) as session:
        with pytest.raises(ValueRejectedError):
            await session.execute(_INSERT_RAW, params)


def test_non_trading_event_cannot_claim_a_mode() -> None:
    """V-20 — เหตุการณ์ที่ไม่เกี่ยวกับโหมด ระบุ PAPER หรือ LIVE ไม่ได้"""
    with pytest.raises(AuditEventError):
        AuditEvent(
            owner_user_id=uuid4(),
            action=AuditAction.USER_CREATED,
            actor_kind=ActorKind.SYSTEM,
            subject_kind=SubjectKind.USER,
            subject_id="x",
            outcome=AuditOutcome.SUCCEEDED,
            details=UserCreatedDetails(),
            mode=AuditMode.LIVE,
        )


async def test_details_must_be_an_object(api_engine: AsyncEngine) -> None:
    """V-21 — `details` ต้องเป็น object ไม่ใช่ array หรือตัวเลข"""
    user_id = uuid4()
    for bad in ("[]", "1", '"ข้อความ"'):
        params = _base_params(str(user_id)) | {"details": bad}
        async with user_session(api_engine, user_id) as session:
            with pytest.raises(ValueRejectedError):
                await session.execute(_INSERT_RAW, params)


#: ค่าที่คำนวณมือแล้วเทียบ — ที่มาเขียนกำกับไว้
MONEY_CASES = [
    # ทศนิยม 18 ตำแหน่งพอดี = หน่วยที่เล็กที่สุดที่ระบบเก็บได้
    ("0.000000000000000001", "USDT"),
    # ค่าลบ ต้องเก็บและอ่านกลับได้เหมือนกัน
    ("-1.23", "USDT"),
    # ศูนย์ ต้องไม่กลายเป็นลบศูนย์หรือรูปแบบอื่น
    ("0", "THB"),
]


@pytest.mark.parametrize(("amount", "unit"), MONEY_CASES)
async def test_money_in_details_survives_jsonb(
    migrator_engine: AsyncEngine, api_engine: AsyncEngine, amount: str, unit: str
) -> None:
    """V-22 — จำนวนเงินใน `details` เก็บเป็นข้อความคู่กับหน่วย และอ่านกลับได้ค่าเดิม

    เขียนลง `JSONB` จริงเพื่อพิสูจน์ว่ารูปแบบนี้รอดการเข้าออกฐานข้อมูล
    ใช้ตารางทดสอบเพราะเหตุการณ์ที่มีจำนวนเงินยังไม่มีในระบบ (RQ-16)
    """
    original = Money.of(amount, unit)
    encoded = money_detail(original)
    assert encoded["unit"] == unit
    assert Money.of(encoded["amount"], unit) == original
    assert "E" not in encoded["amount"], "ต้องไม่เป็นรูปแบบวิทยาศาสตร์"

    table = f"test_money_details_{uuid4().hex[:8]}"
    async with migrator_engine.begin() as connection:
        await connection.execute(text(f"CREATE TABLE {table} (payload jsonb NOT NULL)"))
        await connection.execute(text(f"GRANT SELECT, INSERT ON {table} TO tiewtrade_api"))
    try:
        async with api_engine.begin() as connection:
            await connection.execute(
                text(f"INSERT INTO {table} (payload) VALUES (CAST(:payload AS jsonb))"),
                {"payload": json.dumps(encoded)},
            )
            result = await connection.execute(text(f"SELECT payload FROM {table}"))
            stored: dict[str, object] = result.scalar_one()

        assert isinstance(stored, dict)
        assert Money.of(str(stored["amount"]), str(stored["unit"])) == original
    finally:
        async with migrator_engine.begin() as connection:
            await connection.execute(text(f"DROP TABLE IF EXISTS {table}"))


def test_quantity_keeps_its_asset() -> None:
    """V-22 — ปริมาณก็ผูกหน่วยมาเหมือนกัน"""
    assert quantity_detail(Quantity.of("0.00000001", "BTC")) == {
        "amount": "0.00000001",
        "unit": "BTC",
    }


def test_money_helper_refuses_plain_numbers() -> None:
    """V-23 — ส่งตัวเลขดิบเป็นจำนวนเงินไม่ได้ ต้องเป็น `Money`"""
    with pytest.raises(AttributeError):
        money_detail(Decimal("1.23"))  # type: ignore[arg-type]


async def test_identity_setting_name_is_shared(api_engine: AsyncEngine) -> None:
    """ชื่อตัวแปรที่ policy อ่านประกาศไว้ที่เดียว — ไม่มีใครเขียนสตริงซ้ำ"""
    user_id = uuid4()
    async with user_session(api_engine, user_id) as session:
        current = (
            await session.execute(
                "SELECT current_setting(:name, true)", {"name": CURRENT_USER_SETTING}
            )
        ).scalar_one()
    assert current == str(user_id)


# ─────────────────────────────────────────────────────────────
# คอลัมน์แกนก็ต้องจำกัดตามชนิดเหตุการณ์ (พบจากรีวิว 2026-09-27)
#
# ถ้าจำกัดแค่ `details` ช่องข้อความอย่าง `subject_id` และ `failure_code`
# จะกลายเป็นทางที่ค่าลับและข้อมูลระบุตัวตนเข้ามาได้ และบันทึกนั้นลบไม่ได้
# ─────────────────────────────────────────────────────────────


def test_user_created_requires_actor_to_be_the_created_user() -> None:
    """ผู้กระทำต้องเป็นผู้ใช้ที่ถูกสร้าง ไม่ใช่ระบบ และไม่ใช่คนอื่น"""
    owner = uuid4()

    with pytest.raises(AuditEventError):
        AuditEvent(
            owner_user_id=owner,
            action=AuditAction.USER_CREATED,
            actor_kind=ActorKind.SYSTEM,
            subject_kind=SubjectKind.USER,
            subject_id=str(owner),
            outcome=AuditOutcome.SUCCEEDED,
            details=UserCreatedDetails(),
        )

    with pytest.raises(AuditEventError):
        AuditEvent(
            owner_user_id=owner,
            action=AuditAction.USER_CREATED,
            actor_kind=ActorKind.USER,
            actor_id=uuid4(),  # UUID ถูกชนิด แต่เป็นคนละคน
            subject_kind=SubjectKind.USER,
            subject_id=str(owner),
            outcome=AuditOutcome.SUCCEEDED,
            details=UserCreatedDetails(),
        )


@pytest.mark.parametrize(
    "subject_id",
    ["someone@example.com", "ชื่อคนหนึ่ง", "not-a-uuid"],
)
def test_user_created_subject_must_be_the_created_user(subject_id: str) -> None:
    """เป้าหมายต้องเป็นรหัสของผู้ใช้ที่ถูกสร้าง — ช่องนี้จึงไม่ใช่ช่องข้อความอิสระ"""
    owner = uuid4()
    with pytest.raises(AuditEventError):
        AuditEvent(
            owner_user_id=owner,
            action=AuditAction.USER_CREATED,
            actor_kind=ActorKind.USER,
            actor_id=owner,
            subject_kind=SubjectKind.USER,
            subject_id=subject_id,
            outcome=AuditOutcome.SUCCEEDED,
            details=UserCreatedDetails(),
        )


def test_failure_code_must_be_declared_first() -> None:
    """รหัสความล้มเหลวที่ยังไม่ได้ประกาศ ใช้ไม่ได้ — กันช่องข้อความอิสระ"""
    owner = uuid4()
    with pytest.raises(AuditEventError):
        AuditEvent(
            owner_user_id=owner,
            action=AuditAction.USER_CREATED,
            actor_kind=ActorKind.USER,
            actor_id=owner,
            subject_kind=SubjectKind.USER,
            subject_id=str(owner),
            outcome=AuditOutcome.FAILED,
            details=UserCreatedDetails(),
            failure_code="ค่าลับที่แอบใส่มา",
        )


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("subject", "someone@example.com"),
        ("actor_kind", "SYSTEM"),
    ],
)
async def test_database_rejects_core_columns_that_do_not_match_the_action(
    api_engine: AsyncEngine, column: str, value: str
) -> None:
    """เส้นทางที่ไม่ผ่านตัวเขียนก็ต้องถูกปฏิเสธ — ฐานข้อมูลตรวจเอง"""
    user_id = uuid4()
    params = _base_params(str(user_id)) | {column: value}
    async with user_session(api_engine, user_id) as session:
        with pytest.raises(ValueRejectedError):
            await session.execute(_INSERT_RAW, params)


async def test_database_rejects_failure_code(api_engine: AsyncEngine) -> None:
    """เขียนตรงพร้อมรหัสความล้มเหลวที่ไม่ได้ประกาศ ก็ไม่ได้"""
    user_id = uuid4()
    async with user_session(api_engine, user_id) as session:
        with pytest.raises(ValueRejectedError):
            await session.execute(
                "INSERT INTO audit_events"
                " (id, owner_user_id, actor_kind, actor_id, action, subject_kind,"
                "  subject_id, mode, outcome, failure_code, details)"
                " VALUES (gen_random_uuid(), CAST(:owner AS uuid), 'USER',"
                "  CAST(:owner AS uuid), 'USER_CREATED', 'USER', :subject,"
                "  'NOT_APPLICABLE', 'SUCCEEDED', :code, '{}'::jsonb)",
                {"owner": str(user_id), "subject": str(user_id), "code": "LEAKED-SECRET"},
            )


async def test_writer_rejects_email_hidden_in_subject_id(api_engine: AsyncEngine) -> None:
    """ตาข่ายชั้นสองของตัวเขียนครอบคอลัมน์แกนที่เป็นข้อความด้วย"""
    from tiewtrade.infra.audit import ForbiddenDetailError, record_event

    owner = uuid4()

    # ประกอบวัตถุให้ผ่านข้อบังคับรายเหตุการณ์ก่อน แล้วเปลี่ยนค่าเฉพาะช่องที่ทดสอบ
    # เพื่อพิสูจน์ว่าตาข่ายชั้นสองทำงานจริง ไม่ใช่ถูกข้อบังคับชั้นแรกกันไปหมด
    event = AuditEvent(
        owner_user_id=owner,
        action=AuditAction.USER_CREATED,
        actor_kind=ActorKind.USER,
        actor_id=owner,
        subject_kind=SubjectKind.USER,
        subject_id=str(owner),
        outcome=AuditOutcome.SUCCEEDED,
        details=UserCreatedDetails(),
    )
    object.__setattr__(event, "subject_id", "someone@example.com")

    async with user_session(api_engine, owner) as session:
        with pytest.raises(ForbiddenDetailError):
            await record_event(session, event)
