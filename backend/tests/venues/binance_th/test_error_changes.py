"""สองการเปลี่ยนในสัญญาของ F-33 ที่งานนี้ขออนุมัติ — V-8 ถึง V-12, V-15.4

เทสต์นี้อ่านทั้งโค้ดและเอกสาร เพราะข้อที่เจ้าของอนุมัติคือ **ความหมาย** ของชนิด
ไม่ใช่แค่การมีชนิดนั้นอยู่ ถ้อยคำที่ไม่ตรงกับพฤติกรรมคือหนี้ที่งานถัดไปจะจ่าย
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pytest

from tiewtrade.venues.errors import (
    RejectionReason,
    VenueError,
    VenueProtocolError,
    VenueRejectedError,
    VenueUnavailableError,
)

SPECS: Final = Path(__file__).parents[3].parent / "specs"
F33_VALIDATION: Final = SPECS / "features" / "2026-09-28-venue-layer" / "validation.md"
F35_PLAN: Final = SPECS / "features" / "2026-10-01-binance-th-adapter" / "plan.md"


def test_unexplained_is_a_reason_not_a_new_kind() -> None:
    """V-8 — ดักด้วย `VenueRejectedError` ชนิดเดิมได้ แล้วค่อยอ่านเหตุผล"""
    error = VenueRejectedError(RejectionReason.UNEXPLAINED)
    assert isinstance(error, VenueRejectedError)
    with pytest.raises(VenueRejectedError) as caught:
        raise error
    assert caught.value.reason is RejectionReason.UNEXPLAINED


def test_a_protocol_error_is_not_caught_by_catching_unavailable() -> None:
    """V-9 — ดักแยกจากทุกชนิดเดิมได้ด้วยชนิดอย่างเดียว

    ถ้าปนกันได้ ผู้เรียกจะรอแล้วลองใหม่ในกรณีที่ต้องแก้โค้ด
    """
    with pytest.raises(VenueProtocolError):
        try:
            raise VenueProtocolError()
        except VenueUnavailableError:  # pragma: no cover - ต้องไม่เข้าทางนี้
            pytest.fail("ดัก VenueUnavailableError แล้วจับ VenueProtocolError ไปด้วย")


def test_the_new_kind_still_answers_to_the_shared_base() -> None:
    """ผู้เรียกที่ดัก `VenueError` ตัวเดียวต้องยังได้ครบ"""
    assert isinstance(VenueProtocolError(), VenueError)
    assert VenueProtocolError.code == "VENUE_PROTOCOL"


def test_there_are_six_kinds_and_four_reasons() -> None:
    """V-10.1 — จำนวนที่โค้ดบอกคือหกและสี่"""
    assert len(VenueError.__subclasses__()) == 6
    assert len(RejectionReason) == 4
    codes = {kind.code for kind in VenueError.__subclasses__()}
    assert len(codes) == 6, "มีรหัสซ้ำกัน ซึ่งทำให้ `failure_code` ของ audit log กำกวม"


def test_the_counts_match_what_the_two_documents_say() -> None:
    """V-10.1, V-12 — เอกสารของ F-33 และ plan ของงานนี้ต้องเขียนจำนวนเดียวกับโค้ด

    สามที่ที่เขียนจำนวนเดียวกันจะขัดกันเองในที่สุด เทสต์นี้คือสิ่งที่ทำให้ขัดกันแล้วดัง
    """
    f33 = F33_VALIDATION.read_text(encoding="utf-8")
    assert "**หกชนิด**" in f33
    assert "**สี่ค่า**" in f33
    assert "ห้าชนิด" not in f33, "ยังมีถ้อยคำเดิมที่ขัดกับจำนวนจริง"

    plan = F35_PLAN.read_text(encoding="utf-8")
    assert "| **ชนิดข้อผิดพลาด** | 5 | **6**" in plan


def test_the_wider_meaning_of_unavailable_is_written_in_the_code() -> None:
    """V-15.4 — ความหมายใหม่อยู่ใน docstring ของชนิด ไม่ใช่อยู่แต่ในสเปก

    คนที่อ่านโค้ดตอนแก้บั๊กไม่ได้เปิดสเปกอ่านด้วยทุกครั้ง
    """
    meaning = VenueUnavailableError.__doc__ or ""
    assert "ข้อมูลที่ร้องขอ" in meaning
    assert "ไม่พร้อมใช้งานชั่วคราว" in meaning
    assert str(VenueUnavailableError()) == "ตลาดหรือข้อมูลที่ร้องขอไม่พร้อมใช้งานชั่วคราว"


def test_the_wider_meaning_is_recorded_in_the_closed_specification_too() -> None:
    """V-15.4 — และบันทึกไว้ในเอกสารของงานที่ปิดแล้ว พร้อมเหตุผล"""
    f33 = F33_VALIDATION.read_text(encoding="utf-8")
    assert "การเปลี่ยนแปลงหลังปิดงาน" in f33
    assert "ข้อมูลที่ร้องขอไม่พร้อม" in f33


def test_the_rule_for_state_changing_requests_is_written_before_anyone_needs_it() -> None:
    """plan ข้อ 1.2 — คำขอที่เปลี่ยนสถานะแล้วอ่านคำตอบไม่ออกต้องเป็น "ไม่รู้ผล"

    งานนี้ยังไม่มีคำขอแบบนั้น กฎจึงต้องอยู่ในโค้ดก่อน ไม่ใช่รอให้งานที่ส่งออเดอร์
    ตีความเอาเอง
    """
    meaning = VenueProtocolError.__doc__ or ""
    assert "VenueOutcomeUnknownError" in meaning
    assert "เปลี่ยนสถานะ" in meaning
