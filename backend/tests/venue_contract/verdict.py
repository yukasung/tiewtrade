"""ตัวตัดสินสามสถานะของเทสต์สัญญากับตลาดจริง (F-35 plan.md ข้อ 6)

**แยก "ยังไม่ได้คำตอบจากตลาด" ออกจาก "สัญญาไม่ตรงกัน"** เพราะงานรายวันที่แดงเพราะ
เน็ตมีปัญหาจะสอนให้คนเลิกเชื่อสีแดง แล้ววันที่สัญญาเปลี่ยนจริงจะไม่มีใครดู

อยู่ในโมดูลของตัวเอง ไม่ฝังในไฟล์เทสต์ เพราะการจัดกลุ่มนี้คือสิ่งที่ `validation.md`
สั่งให้ทดสอบทีละกรณี (V-40 ถึง V-40.3) ตรรกะที่ฝังในไฟล์เทสต์ทดสอบไม่ได้
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum
from itertools import pairwise

from tiewtrade.venues.errors import (
    VenueError,
    VenueOutcomeUnknownError,
    VenueRateLimitedError,
    VenueUnavailableError,
)


class Verdict(Enum):
    """สามสถานะ ไม่ใช่สองสถานะ"""

    PASSED = "ผ่าน"
    SKIPPED = "ข้าม"
    FAILED = "แดง"


#: ชนิดที่หมายถึง "ยังไม่ได้คำตอบจากตลาด" — ทั้งสามข้าม
#:
#: `VenueOutcomeUnknownError` อยู่ในกลุ่มนี้ **เพราะทุกคำขอของงานนี้เป็นการอ่าน**
#: การอ่านที่ไม่รู้ผลคือการอ่านที่ล้มเหลว ไม่ได้ทำให้เกิดอะไรที่ตลาด
#: **ข้อนี้ใช้ได้เฉพาะงาน CI สัญญานี้ ไม่ใช่กฎทั่วไป** — วันที่มีคำขอที่เปลี่ยนสถานะ
#: การจัดกลุ่มนี้ต้องทบทวน และชนิดนั้นที่นั่นห้ามข้าม (plan.md ข้อ 6)
UNANSWERED: tuple[type[VenueError], ...] = (
    VenueUnavailableError,
    VenueRateLimitedError,
    VenueOutcomeUnknownError,
)


def verdict_for(error: VenueError) -> Verdict:
    """สถานะของงานเมื่อเจอข้อผิดพลาดชนิดนั้น

    ชนิดที่เหลือทั้งหมดเป็น **แดง** รวม `VenueRejectedError` ทุกเหตุผล เพราะคำขอ
    ในงานนี้เป็นคำขออ่านอย่างเดียวและคงที่ ถ้าตลาดปฏิเสธ แปลว่าเราเข้าใจผิด
    """
    return Verdict.SKIPPED if isinstance(error, UNANSWERED) else Verdict.FAILED


#: จำนวนผลต่างที่ต้องวัดได้ก่อนจะสรุปเรื่อง weight ได้ (plan.md ข้อ 2.1)
REQUIRED_SAMPLES = 3


def weight_verdict(readings: Sequence[int | None], declared: int) -> tuple[Verdict, str]:
    """สรุปว่า weight ที่เราประกาศตรงกับที่ตลาดนับหรือไม่

    `readings` คือ **ยอดสะสมของ IP** ที่ตลาดรายงานในแต่ละคำขอที่ต้นทุนเท่ากัน
    ค่าว่างหมายถึงคำขอนั้นไม่มี header กลับมา

    ยอดสะสมเทียบตรง ๆ กับต้นทุนของคำขอเดียวไม่ได้ จึงดู **ผลต่างระหว่างคำขอ**
    และยอมสรุปเฉพาะเมื่อผลต่างเท่ากันทุกรอบ มิฉะนั้นถือว่า **สรุปไม่ได้ ไม่ใช่ผิด**
    """
    if any(reading is None for reading in readings):
        return Verdict.SKIPPED, "ตลาดไม่ได้ส่ง header น้ำหนักมาทุกรอบ จึงสรุปไม่ได้"

    counts = [reading for reading in readings if reading is not None]
    deltas = [later - earlier for earlier, later in pairwise(counts)]

    if len(deltas) < REQUIRED_SAMPLES:
        return Verdict.SKIPPED, f"วัดได้ {len(deltas)} รอบ ต้องมี {REQUIRED_SAMPLES} รอบจึงสรุปได้"
    if any(delta < 0 for delta in deltas):
        return Verdict.SKIPPED, "ยอดสะสมลดลงระหว่างรอบ (หน้าต่างเวลารีเซ็ต) จึงสรุปไม่ได้"
    if len(set(deltas)) != 1:
        return Verdict.SKIPPED, f"ผลต่างไม่เท่ากันในรอบที่วัด {deltas} — มีผู้อื่นใช้ IP เดียวกัน"

    measured = deltas[0]
    if measured == declared:
        return Verdict.PASSED, f"ตลาดนับ {measured} ต่อคำขอ เท่ากับที่ประกาศไว้"
    if measured > declared:
        return Verdict.FAILED, f"ตลาดนับ {measured} ต่อคำขอ แต่เราประกาศไว้ {declared}"
    # น้อยกว่าที่ประกาศ = เราจองเผื่อไว้มากกว่าที่ตลาดคิด ซึ่งปลอดภัยแต่ไม่ตรง
    # **plan ไม่ได้ระบุกรณีนี้** จึงไม่ทำให้งานแดง แต่บอกไว้ให้คนเห็นในสรุป
    return Verdict.SKIPPED, f"ตลาดนับ {measured} ต่อคำขอ น้อยกว่าที่ประกาศไว้ {declared}"


@dataclass(slots=True)
class ContractReport:
    """สรุปผลที่ผู้ดูแลอ่านได้โดยไม่ต้องเปิด log (plan.md ข้อ 6 ข้อ 2)"""

    rows: list[tuple[str, Verdict, str]] = field(default_factory=list)

    def record(self, what: str, verdict: Verdict, note: str = "") -> None:
        self.rows.append((what, verdict, note))

    @property
    def worst(self) -> Verdict:
        """สถานะรวม — แดงชนะข้าม ข้ามชนะผ่าน"""
        for verdict in (Verdict.FAILED, Verdict.SKIPPED):
            if any(row[1] is verdict for row in self.rows):
                return verdict
        return Verdict.PASSED

    def as_markdown(self) -> str:
        """ตารางสั้น ๆ สำหรับ job summary — ไม่มี URL และไม่มีค่าจากคำขอ"""
        lines = [
            f"### สัญญาของตลาด: {self.worst.value}",
            "",
            "| ตรวจอะไร | ผล | หมายเหตุ |",
            "|---|---|---|",
        ]
        lines.extend(f"| {what} | {verdict.value} | {note} |" for what, verdict, note in self.rows)
        return "\n".join(lines) + "\n"
