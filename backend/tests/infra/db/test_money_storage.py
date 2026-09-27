"""เงินในฐานข้อมูล — V-22 ถึง V-27

กฎที่พิสูจน์ที่นี่: **ฐานข้อมูลต้องไม่ปัดเศษเงินให้เอง** ค่าที่เก็บไม่ได้ต้องถูกปฏิเสธ
(F-02 RQ-9, F-03 RQ-9.1) และขอบเขตของฐานข้อมูลต้องตรงกับขอบเขตของ `Money`
ไม่ใช่กว้างกว่าหรือแคบกว่า เพราะสองด่านที่ไม่ตรงกันจะเถียงกันเองในวันที่มีคนพลาด

เส้นทางที่ทดสอบมีสองแบบ:

1. ผ่านตัวแปลงของชั้น `infra`
2. **เขียนตรงด้วยข้อความ** ซึ่งเลี่ยงตัวแปลงได้ — เป็นเส้นทางที่ RQ-9.1 สั่งให้ครอบ
"""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.core.money import Money, MoneyError, Quantity
from tiewtrade.infra.db import (
    ValueRejectedError,
    money_from_columns,
    money_to_columns,
    quantity_from_columns,
    quantity_to_columns,
)
from tiewtrade.infra.db.errors import translate_database_error

#: ค่าที่คำนวณมือแล้วเทียบ — ที่มาของแต่ละค่าเขียนกำกับไว้ (testing.md หัวข้อ 2)
HAND_CHECKED = [
    # ศูนย์ — ต้องไม่กลายเป็นค่าลบศูนย์หรือข้อความอื่น
    "0",
    # ค่าธรรมดาสองตำแหน่ง
    "1.23",
    # ค่าลบ ต้องเก็บและอ่านกลับได้เหมือนกัน
    "-1.23",
    # ทศนิยม 18 ตำแหน่งพอดี = หน่วยที่เล็กที่สุดที่ NUMERIC(38,18) เก็บได้
    "0.000000000000000001",
    # 20 หลักหน้าจุด ลบหนึ่งหน่วยที่เล็กที่สุด = ค่าที่ใหญ่ที่สุดที่เก็บได้
    "99999999999999999999.999999999999999999",
    # ศูนย์ท้ายไม่นับเป็นทศนิยมจริง — min_scale() ของ PostgreSQL เห็นเป็น 0 ตำแหน่ง
    "1.000000000000000000",
]


async def _insert_via_adapter(engine: AsyncEngine, table: str, value: Money) -> None:
    amount, unit = money_to_columns(value)
    async with engine.begin() as connection:
        await connection.execute(
            text(f"INSERT INTO {table} (id, amount, unit) VALUES (:id, :amount, :unit)"),
            {"id": str(uuid4()), "amount": amount, "unit": unit},
        )


async def _insert_raw_text(engine: AsyncEngine, table: str, amount_text: str) -> None:
    """เขียนตรงด้วยข้อความ โดยไม่ผ่านตัวแปลงของเรา

    ค่าดิบจึงไปถึง `CHECK` ของ domain ครบ ไม่ถูกปัดก่อนตรวจ
    """
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    f"INSERT INTO {table} (id, amount, unit)"
                    " VALUES (:id, CAST(:amount AS tiewtrade_money_amount), 'USDT')"
                ),
                {"id": str(uuid4()), "amount": amount_text},
            )
    except SQLAlchemyError as error:
        # เส้นทางนี้ไม่ผ่าน UserSession จึงต้องแปลงข้อผิดพลาดเอง
        # เพื่อให้เทสต์ดักชนิดเดียวกับที่ผู้เรียกจริงเห็น
        raise translate_database_error(error) from None


@pytest.mark.parametrize("amount_text", HAND_CHECKED)
async def test_round_trip_keeps_the_value(
    api_engine: AsyncEngine, money_table: str, amount_text: str
) -> None:
    """V-22 — เขียนลงแล้วอ่านกลับได้ค่าเดิม"""
    original = Money.of(amount_text, "USDT")
    await _insert_via_adapter(api_engine, money_table, original)

    async with api_engine.connect() as connection:
        row = (await connection.execute(text(f"SELECT amount, unit FROM {money_table}"))).one()
    amount, unit = tuple(row)

    assert isinstance(amount, Decimal), f"อ่านกลับได้ชนิด {type(amount).__name__} ไม่ใช่ Decimal"
    assert money_from_columns(amount, unit) == original


async def test_round_trip_keeps_quantity_and_its_asset(
    api_engine: AsyncEngine, money_table: str
) -> None:
    """V-22 — ปริมาณก็ผูกหน่วยกลับมาเหมือนเดิม"""
    original = Quantity.of("0.00000001", "BTC")
    amount, unit = quantity_to_columns(original)
    async with api_engine.begin() as connection:
        await connection.execute(
            text(f"INSERT INTO {money_table} (id, amount, unit) VALUES (:id, :amount, :unit)"),
            {"id": str(uuid4()), "amount": amount, "unit": unit},
        )

    async with api_engine.connect() as connection:
        row = (await connection.execute(text(f"SELECT amount, unit FROM {money_table}"))).one()

    assert quantity_from_columns(*tuple(row)) == original


async def test_value_with_too_many_decimals_is_rejected_not_rounded(
    api_engine: AsyncEngine, money_table: str
) -> None:
    """V-23 — ทศนิยมเกิน 18 ตำแหน่งถูกปฏิเสธ ไม่ใช่ถูกปัดเป็นศูนย์เงียบ ๆ

    ค่านี้คือกรณีที่ `NUMERIC(38,18)` จะปัดให้เป็น 0 โดยไม่บอกใคร
    """
    with pytest.raises(ValueRejectedError):
        await _insert_raw_text(api_engine, money_table, "0.0000000000000000001")

    async with api_engine.connect() as connection:
        count: int = (
            await connection.execute(text(f"SELECT count(*) FROM {money_table}"))
        ).scalar_one()
    assert count == 0, "ค่าที่เก็บไม่ได้ถูกเขียนลงไปแล้ว (อาจถูกปัดเป็น 0)"


@pytest.mark.parametrize(
    ("amount_text", "accepted"),
    [
        ("99999999999999999999.999999999999999999", True),
        ("100000000000000000000", False),
        ("-100000000000000000000", False),
    ],
)
async def test_range_limit_matches_the_money_type(
    api_engine: AsyncEngine, money_table: str, amount_text: str, accepted: bool
) -> None:
    """V-24 — ค่าที่เกินช่วงถูกปฏิเสธ ที่ขอบเดียวกับ `Money`"""
    if accepted:
        await _insert_raw_text(api_engine, money_table, amount_text)
        Money.of(amount_text, "USDT")
        return

    with pytest.raises(ValueRejectedError):
        await _insert_raw_text(api_engine, money_table, amount_text)
    with pytest.raises(MoneyError):
        Money.of(amount_text, "USDT")


@pytest.mark.parametrize("bad_value", ["NaN", "Infinity", "-Infinity"])
async def test_not_a_number_is_rejected(
    api_engine: AsyncEngine, money_table: str, bad_value: str
) -> None:
    """V-24 — ค่าที่ไม่ใช่จำนวนจริงเก็บไม่ได้ ทั้งที่ `NUMERIC` เปล่ารับไว้ได้เอง"""
    with pytest.raises(ValueRejectedError):
        await _insert_raw_text(api_engine, money_table, bad_value)


def _amount_texts() -> st.SearchStrategy[str]:
    """สร้างข้อความตัวเลขที่คร่อมขอบทั้งสองด้าน

    จำนวนหลักหน้าจุดถึง 21 หลัก และทศนิยมถึง 20 ตำแหน่ง เพื่อให้มีทั้งค่าที่ควรผ่าน
    และค่าที่ควรถูกปฏิเสธในชุดเดียวกัน — ไม่ใช่ทดสอบแต่ค่าที่รู้ว่าผ่าน
    """
    digits = st.text(alphabet="0123456789", min_size=1, max_size=21)
    fraction = st.text(alphabet="0123456789", max_size=20)
    sign = st.sampled_from(["", "-"])
    return st.builds(
        lambda s, w, f: f"{s}{w}.{f}" if f else f"{s}{w}",
        sign,
        digits,
        fraction,
    )


@settings(max_examples=200, deadline=None)
@given(amount_text=_amount_texts())
async def test_database_and_money_agree_on_every_value(amount_text: str) -> None:
    """V-25 — สิ่งที่ `Money` รับ ฐานข้อมูลต้องรับ และสิ่งที่ `Money` ปฏิเสธ ฐานข้อมูลต้องปฏิเสธ

    เทสต์นี้ไม่เรียกฐานข้อมูลจริงทีละค่าเพราะจะช้าเกินจะรันทุกครั้ง แต่เทียบกับกฎที่
    domain ใช้จริง — ทศนิยมจริงไม่เกิน 18 ตำแหน่งและค่าสัมบูรณ์น้อยกว่า 1E+20
    ซึ่งกฎนี้ถูกยืนยันกับฐานข้อมูลจริงแล้วในเทสต์ข้างบน
    """
    # คิดเองจากข้อความ ไม่เรียกโค้ดที่กำลังทดสอบ และไม่ใช้ normalize()
    # เพราะ normalize() ปัดตาม context ของผู้เรียก ซึ่งจะทำให้เทสต์ตัดสินผิดเอง
    unsigned = amount_text.lstrip("-")
    whole, _, fraction = unsigned.partition(".")
    real_scale = len(fraction.rstrip("0"))
    magnitude = Decimal(amount_text).copy_abs()
    within_database = real_scale <= 18 and magnitude < Decimal("1E+20")
    assert whole != "" or fraction != ""

    try:
        Money.of(amount_text, "USDT")
    except MoneyError:
        accepted_by_money = False
    else:
        accepted_by_money = True

    assert accepted_by_money == within_database, (
        f"{amount_text}: Money รับ={accepted_by_money} แต่ฐานข้อมูลรับ={within_database}"
    )


@pytest.mark.parametrize("bad", [0.1, True, None, b"1"])
def test_adapter_refuses_types_that_cannot_be_money(bad: object) -> None:
    """V-26 — ไม่มีทศนิยมลอยตัวในเส้นทางเข้าออกฐานข้อมูล"""
    with pytest.raises(ValueRejectedError):
        money_from_columns(bad, "USDT")


def test_adapter_does_not_round(money_table: str) -> None:
    """V-27 — ตัวแปลงไม่ปัดอะไรเลย ค่าที่ออกไปคือค่าที่เข้ามา"""
    amount, unit = money_to_columns(Money.of("1.500000000000000000", "USDT"))
    assert amount == Decimal("1.5")
    assert unit == "USDT"


async def _database_accepts(amount_text: str) -> bool:
    """ลองเขียนค่าลงฐานข้อมูลจริง แล้วบอกว่ารับหรือไม่รับ"""
    from tiewtrade.infra.db import DatabaseRole, create_engine_for

    migrator = create_engine_for(DatabaseRole.MIGRATOR)
    table = f"test_money_prop_{uuid4().hex[:10]}"
    try:
        async with migrator.begin() as connection:
            await connection.execute(
                text(
                    f"CREATE TABLE {table} ("
                    " id uuid PRIMARY KEY,"
                    " amount tiewtrade_money_amount NOT NULL,"
                    " unit tiewtrade_unit_code NOT NULL)"
                )
            )
        try:
            await _insert_raw_text(migrator, table, amount_text)
        except ValueRejectedError:
            return False
        return True
    finally:
        async with migrator.begin() as connection:
            await connection.execute(text(f"DROP TABLE IF EXISTS {table}"))
        await migrator.dispose()


@settings(max_examples=25, deadline=None)
@given(amount_text=_amount_texts())
def test_real_database_and_money_agree(amount_text: str) -> None:
    """V-25 กับฐานข้อมูลจริง — สุ่มค่ามาลองทั้งสองฝั่ง แล้วผลต้องตรงกัน

    สร้าง engine เองในเทสต์นี้แทนการใช้ fixture เพราะ hypothesis เรียกตัวทดสอบ
    หลายรอบใน test เดียว ซึ่ง fixture ระดับ function ครอบไม่ถึง
    """
    import asyncio

    try:
        Money.of(amount_text, "USDT")
    except MoneyError:
        accepted_by_money = False
    else:
        accepted_by_money = True

    accepted_by_database = asyncio.run(_database_accepts(amount_text))

    assert accepted_by_money == accepted_by_database, (
        f"{amount_text}: Money รับ={accepted_by_money} ฐานข้อมูลรับ={accepted_by_database}"
    )
