"""ตัวตัดสินสามสถานะ — V-40 ถึง V-40.3

เทสต์นี้อยู่ในชุดปกติ (ไม่ต้องมีเน็ต) เพราะตรรกะการจัดกลุ่มคือสิ่งที่ต้องเชื่อถือได้
ก่อนจะปล่อยให้งานรายวันใช้มันตัดสิน
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest

from tests.venue_contract.verdict import (
    ContractReport,
    Verdict,
    verdict_for,
    weight_verdict,
)
from tiewtrade.venues.errors import (
    RejectionReason,
    VenueCredentialRejectedError,
    VenueError,
    VenueOutcomeUnknownError,
    VenueProtocolError,
    VenueRateLimitedError,
    VenueRejectedError,
    VenueUnavailableError,
)

#: ข้อผิดพลาดทั้งหกชนิดคู่กับสถานะที่ต้องได้ — **ครบทุกชนิดโดยเจตนา** (V-40)
EVERY_KIND: tuple[tuple[VenueError, Verdict], ...] = (
    (VenueUnavailableError(), Verdict.SKIPPED),
    (VenueRateLimitedError(timedelta(seconds=1)), Verdict.SKIPPED),
    (VenueOutcomeUnknownError(), Verdict.SKIPPED),
    (VenueProtocolError(), Verdict.FAILED),
    (VenueRejectedError(RejectionReason.UNKNOWN_SYMBOL), Verdict.FAILED),
    (VenueRejectedError(RejectionReason.UNEXPLAINED), Verdict.FAILED),
    (VenueCredentialRejectedError(), Verdict.FAILED),
)


@pytest.mark.parametrize(("error", "expected"), EVERY_KIND)
def test_every_error_kind_lands_in_the_right_group(error: VenueError, expected: Verdict) -> None:
    """V-40 — ป้อนข้อผิดพลาดทั้งหกชนิดให้ตัวตัดสิน แล้วตรวจสถานะที่ได้"""
    assert verdict_for(error) is expected


def test_every_kind_there_is_has_a_group() -> None:
    """ชนิดใหม่ที่เพิ่มในอนาคตต้องถูกจัดกลุ่มโดยเจตนา ไม่ใช่ตกเป็นแดงโดยปริยาย"""
    covered = {type(error) for error, _ in EVERY_KIND}
    assert covered == set(VenueError.__subclasses__())


def test_an_unknown_outcome_is_a_skip_because_every_request_here_is_a_read() -> None:
    """V-40.1 — "ไม่รู้ผล" ของงานนี้คือการอ่านที่ล้มเหลว ไม่ได้ทำให้เกิดอะไรที่ตลาด"""
    assert verdict_for(VenueOutcomeUnknownError()) is Verdict.SKIPPED


def test_the_read_only_condition_is_written_next_to_the_grouping() -> None:
    """V-40.1 — เงื่อนไขที่ทำให้ข้ามได้ต้องเขียนกำกับไว้ ไม่ใช่อยู่ในหัวใครคนเดียว

    ถ้าวันหนึ่งมีคำขอที่เปลี่ยนสถานะเข้ามาในงานนี้ คนที่อ่านโค้ดต้องเห็นทันทีว่า
    การจัดกลุ่มนี้ตั้งอยู่บนเงื่อนไขอะไร
    """
    source = (Path(__file__).parent / "verdict.py").read_text(encoding="utf-8")
    assert "ทุกคำขอของงานนี้เป็นการอ่าน" in source
    assert "ไม่ใช่กฎทั่วไป" in source


def test_a_protocol_error_is_red_because_someone_has_to_change_the_code() -> None:
    """V-40 — สัญญาไม่ตรงกันต้องแดง ไม่ใช่ข้าม"""
    assert verdict_for(VenueProtocolError()) is Verdict.FAILED


@pytest.mark.parametrize(
    ("readings", "why"),
    [
        ([10, 20, None, 40, 50], "ไม่มี header"),
        ([10, 20, 30, 5, 15], "หน้าต่างรีเซ็ต"),
        ([10, 20, 31, 41, 51], "ผลต่างไม่เท่ากัน"),
        ([10, 20], "วัดไม่พอ"),
    ],
)
def test_an_inconclusive_weight_measurement_is_a_skip(readings: list[int | None], why: str) -> None:
    """V-40.2 — สรุปไม่ได้ต้องเป็นข้าม ไม่ใช่แดง

    ถ้ากรณีเหล่านี้แดง งานรายวันจะแดงเพราะจังหวะของหน้าต่างเวลา
    แล้วคนจะเลิกเชื่อสีแดง ซึ่งแพงกว่าการพลาดการวัดไปหนึ่งรอบ
    """
    verdict, note = weight_verdict(readings, declared=10)
    assert verdict is Verdict.SKIPPED, f"{why}: {note}"
    assert note


def test_a_real_mismatch_is_red() -> None:
    """V-40.3 — ผลต่างเท่ากันทุกรอบแต่มากกว่าที่ประกาศ → แดง"""
    verdict, note = weight_verdict([0, 12, 24, 36, 48], declared=10)
    assert verdict is Verdict.FAILED
    assert "12" in note
    assert "10" in note


def test_a_matching_weight_passes() -> None:
    """V-40.3 คู่กัน — ตรงกันต้องผ่าน มิฉะนั้นงานจะแดงตลอดและไม่มีความหมาย"""
    verdict, _ = weight_verdict([0, 10, 20, 30, 40], declared=10)
    assert verdict is Verdict.PASSED


def test_reserving_more_than_the_market_counts_does_not_break_the_job() -> None:
    """ประกาศไว้สูงกว่าที่ตลาดนับคือการจองเผื่อ ปลอดภัยแต่ไม่ตรง — plan ไม่ได้ระบุกรณีนี้"""
    verdict, note = weight_verdict([0, 1, 2, 3, 4], declared=10)
    assert verdict is Verdict.SKIPPED
    assert "น้อยกว่า" in note


def test_the_summary_reads_as_a_table_without_any_url() -> None:
    """V-41 — ผู้ดูแลอ่านสรุปได้โดยไม่ต้องเปิด log และสรุปไม่พา URL ไปด้วย"""
    report = ContractReport()
    report.record("ราคาล่าสุด", Verdict.PASSED)
    report.record("weight ของการอ่านราคา", Verdict.SKIPPED, "ยอดสะสมลดลงระหว่างรอบ")

    summary = report.as_markdown()
    assert report.worst is Verdict.SKIPPED
    assert "| ราคาล่าสุด | ผ่าน |" in summary
    assert "ยอดสะสมลดลงระหว่างรอบ" in summary
    assert "://" not in summary


def test_one_red_row_makes_the_whole_job_red() -> None:
    """สถานะรวมต้องเป็นค่าที่แย่ที่สุด ไม่ใช่ค่าของแถวสุดท้าย"""
    report = ContractReport()
    report.record("ราคาล่าสุด", Verdict.PASSED)
    report.record("ข้อจำกัดของเหรียญ", Verdict.FAILED, "ฟิลด์ stepSize หายไป")
    report.record("weight", Verdict.SKIPPED)
    assert report.worst is Verdict.FAILED
