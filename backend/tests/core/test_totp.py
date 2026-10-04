"""การคำนวณรหัส TOTP — V-1, V-3, V-4 และคุณสมบัติของรูปแบบรหัส

**หลักฐานหลักมาจากภายนอก** คือชุดตัวเลขทดสอบใน RFC 6238 Appendix B
ไม่ใช่ค่าที่เราคิดขึ้นเองแล้วยืนยันตัวเอง (`validation.md` V-1)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tiewtrade.core.totp import (
    DIGITS,
    MINIMUM_SECRET_BYTES,
    STEPS_ACCEPTED_BACK,
    TIME_STEP,
    TotpError,
    accepted_steps,
    base32_secret,
    code_for,
    matching_step,
    step_at,
)

#: secret ของชุดตัวเลขทดสอบ SHA-1 ใน RFC 6238 Appendix B — `"12345678901234567890"`
RFC_SECRET = b"12345678901234567890"

#: (วินาทีแบบ Unix, ลำดับช่วงเวลาที่ RFC ระบุ, รหัส 8 หลักที่ RFC ระบุ)
#:
#: ค่าทั้งหมดคัดจากตารางของ RFC 6238 Appendix B แถวที่เป็น SHA-1
RFC_VECTORS = (
    (59, 0x0000000000000001, "94287082"),
    (1111111109, 0x00000000023523EC, "07081804"),
    (1111111111, 0x00000000023523ED, "14050471"),
    (1234567890, 0x000000000273EF07, "89005924"),
    (2000000000, 0x0000000003F940AA, "69279037"),
    (20000000000, 0x0000000027BC86AA, "65353130"),
)


@pytest.mark.parametrize(("unix_seconds", "expected_step", "expected_code"), RFC_VECTORS)
def test_the_rfc_test_vectors_all_match(
    unix_seconds: int, expected_step: int, expected_code: str
) -> None:
    """V-1 — ทุกแถวของ RFC 6238 Appendix B ต้องตรง ทั้งลำดับช่วงเวลาและรหัส

    ตรวจลำดับช่วงเวลาด้วย เพราะถ้าการแปลงเวลาผิดแต่การคำนวณรหัสถูก เทสต์ที่ดูแค่
    รหัสจะยังเขียวตอนส่งลำดับเข้าไปตรง ๆ แล้วพลาดของจริงที่ส่งเวลาเข้ามา
    """
    moment = datetime.fromtimestamp(unix_seconds, tz=UTC)

    assert step_at(moment) == expected_step
    assert code_for(RFC_SECRET, expected_step, digits=8) == expected_code


def test_a_naive_time_is_refused() -> None:
    """V-3 ที่ระดับพฤติกรรม — เวลาที่ไม่มีเขตเวลาให้ผลต่างกันตามเครื่อง จึงต้องถูกปฏิเสธ"""
    with pytest.raises(TotpError):
        step_at(datetime(2026, 10, 3, 12, 0, 0))


def test_the_step_advances_once_per_time_step() -> None:
    """ลำดับเดินหน้าหนึ่งครั้งต่อหนึ่งช่วงเวลา และไม่เดินก่อนครบ"""
    start = datetime.fromtimestamp(1_700_000_010, tz=UTC)
    first = step_at(start)

    assert step_at(start + TIME_STEP - timedelta(seconds=1)) == first
    assert step_at(start + TIME_STEP) == first + 1


def test_the_accepted_steps_are_the_current_one_and_one_back() -> None:
    """Q-8 — รับช่วงปัจจุบันและช่วงก่อนหน้าหนึ่งช่วง เรียงจากใหม่ไปเก่า"""
    assert accepted_steps(100) == (100, 99)
    assert len(accepted_steps(100)) == STEPS_ACCEPTED_BACK + 1
    assert accepted_steps(0) == (0,)


def test_a_code_from_the_previous_step_is_accepted() -> None:
    """รหัสของช่วงก่อนหน้าใช้ได้ และผู้เรียกรู้ว่ามันมาจากลำดับไหน"""
    older = code_for(RFC_SECRET, 99)

    assert matching_step(RFC_SECRET, older, at_step=100) == 99


def test_a_code_from_two_steps_back_is_refused() -> None:
    """ช่วงที่เก่ากว่าที่ยอมรับต้องไม่ผ่าน — ขอบของหน้าต่างต้องมีเทสต์ของตัวเอง"""
    too_old = code_for(RFC_SECRET, 98)

    assert matching_step(RFC_SECRET, too_old, at_step=100) is None


def test_a_code_from_the_next_step_is_refused() -> None:
    """ไม่รับช่วงอนาคต — นาฬิกาเครื่องผู้ใช้ที่เดินเร็วไม่ได้รับการผ่อนผัน (Q-8)"""
    ahead = code_for(RFC_SECRET, 101)

    assert matching_step(RFC_SECRET, ahead, at_step=100) is None


def test_a_code_of_another_secret_is_refused() -> None:
    """secret คนละตัวให้รหัสคนละค่า"""
    other = b"09876543210987654321"

    assert matching_step(RFC_SECRET, code_for(other, 100), at_step=100) is None


@pytest.mark.parametrize("presented", ["", "123", "1234567", "abcdef", "๑๒๓๔๕๖"])
def test_a_malformed_code_is_refused_without_raising(presented: str) -> None:
    """ค่าที่ไม่ใช่รหัสต้องได้ `None` ไม่ใช่ข้อผิดพลาด — มันเป็นข้อมูลจากผู้ใช้"""
    assert matching_step(RFC_SECRET, presented, at_step=100) is None


def test_a_short_secret_is_refused() -> None:
    """RFC 4226 ข้อ R6 — secret ต้องยาวอย่างน้อย 128 บิต"""
    with pytest.raises(TotpError):
        code_for(b"x" * (MINIMUM_SECRET_BYTES - 1), 1)

    with pytest.raises(TotpError):
        base32_secret(b"x" * (MINIMUM_SECRET_BYTES - 1))


@pytest.mark.parametrize("digits", [5, 9, 0, -1])
def test_an_unsupported_number_of_digits_is_refused(digits: int) -> None:
    """RFC 4226 หัวข้อ 5.3 รองรับ 6 ถึง 8 หลัก"""
    with pytest.raises(TotpError):
        code_for(RFC_SECRET, 1, digits=digits)


def test_a_negative_step_is_refused() -> None:
    """ลำดับติดลบไม่มีความหมาย และเป็นสัญญาณว่าผู้เรียกคำนวณผิด"""
    with pytest.raises(TotpError):
        code_for(RFC_SECRET, -1)

    with pytest.raises(TotpError):
        accepted_steps(-1)


def test_the_base32_form_has_no_padding() -> None:
    """แอป authenticator หลายตัวอ่าน `=` ใน query string ไม่ผ่าน"""
    encoded = base32_secret(RFC_SECRET)

    assert "=" not in encoded
    assert encoded == "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"


@given(
    secret=st.binary(min_size=MINIMUM_SECRET_BYTES, max_size=64),
    step=st.integers(min_value=0, max_value=2**40),
)
def test_a_code_always_has_the_declared_number_of_digits(secret: bytes, step: int) -> None:
    """คุณสมบัติ — จำนวนหลักคงที่เสมอ **รวมกรณีที่ค่าขึ้นต้นด้วยศูนย์**

    ข้อนี้เป็นคุณสมบัติ ไม่ใช่ตัวอย่าง เพราะรหัสที่ขึ้นต้นด้วยศูนย์เกิดหนึ่งในสิบครั้ง
    และโค้ดที่ลืมเติมศูนย์จะผ่านเทสต์แบบตัวอย่างไปได้เกือบทุกครั้ง
    """
    code = code_for(secret, step)

    assert len(code) == DIGITS
    assert code.isdigit()


@given(
    secret=st.binary(min_size=MINIMUM_SECRET_BYTES, max_size=64),
    step=st.integers(min_value=1, max_value=2**40),
)
def test_a_code_matches_itself_at_its_own_step(secret: bytes, step: int) -> None:
    """คุณสมบัติ — รหัสที่คำนวณจากลำดับหนึ่ง ต้องตรงที่ลำดับนั้นเสมอ"""
    assert matching_step(secret, code_for(secret, step), at_step=step) == step
