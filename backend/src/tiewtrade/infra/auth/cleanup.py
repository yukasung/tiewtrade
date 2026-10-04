"""เก็บกวาดแถวที่ไม่มีผลอะไรแล้ว (F-06 plan.md หัวข้อ 1.5)

**หนี้นี้มีมาก่อนงานนี้** — `roadmap.md` บันทึกไว้ตั้งแต่ F-05 ว่า `auth_throttle`
ไม่มีการลบแถวเก่า และต้องมีงานเก็บกวาดก่อนปล่อยผู้ใช้จริง · F-06 เพิ่มตารางให้มัน
อีกหนึ่งใบ (`login_challenges`) จึงเก็บกวาดทั้งสองใบในที่เดียวแทนการมาทำสองรอบ

**กฎเดียวที่ห้ามละเมิด: ห้ามลบแถวที่ยังมีผลจำกัดการเดา** (เงื่อนไขของการอนุมัติ
2026-10-03) การลบถังที่ยังหน่วงอยู่หรือที่โควตายังไม่เต็ม เท่ากับยกเลิกการคุมอัตรา
ให้ผู้โจมตีฟรี ๆ ซึ่งแย่กว่าการปล่อยให้แถวค้าง

วิธีตัดสินว่า "ไม่มีผลแล้ว" ต่างกันตามชนิดถัง:

- **หน้าต่างคงที่** — หมดผลเมื่อหน้าต่างผ่านไปแล้ว **และ** ไม่มีเวลาที่ต้องรอค้างอยู่
  เพราะ `claim()` รีเซ็ตตัวนับเองเมื่อหน้าต่างผ่าน ฉะนั้นแถวนั้นให้ผลเท่ากับไม่มีแถว
- **token bucket** — หมดผลเมื่อเวลาที่ผ่านไปพอเติมโควตาคืนจนเต็ม เพราะ `claim()`
  จะเติมคืนให้เต็มในการเรียกครั้งถัดไปอยู่แล้ว

**ไม่เขียนตัวเลขของกฎไว้ใน SQL** — ส่งมาจาก `RULES` ฝั่ง Python ที่เดียว
มิฉะนั้นการเปลี่ยนเพดานจะต้องแก้สองที่ แล้ววันหนึ่งจะไม่ตรงกัน
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast

from sqlalchemy import CursorResult

from tiewtrade.infra.auth.throttle import RULES, Bucket, TokenRule
from tiewtrade.infra.db.session import PresentedSession

# ลบถังแบบหน้าต่างคงที่ที่หน้าต่างผ่านไปแล้วและไม่มีเวลาที่ต้องรอค้างอยู่
_SWEEP_WINDOW_BUCKET = """
DELETE FROM auth_throttle
WHERE bucket_kind = :kind
  AND window_started_at <= :stale_before
  AND (next_allowed_at IS NULL OR next_allowed_at <= :now)
"""

# ลบถังแบบเติมคืนที่เวลาผ่านไปพอเติมโควตาคืนจนเต็มแล้ว
#
# `:capacity - tokens_left` คือจำนวนที่ต้องเติม และแต่ละหน่วยใช้เวลาหนึ่งช่วง
_SWEEP_TOKEN_BUCKET = """
DELETE FROM auth_throttle
WHERE bucket_kind = :kind
  AND refilled_at + ((:capacity - tokens_left) * make_interval(secs => :seconds)) <= :now
"""

# ลบ challenge ที่หมดอายุ — **ไม่มี `WHERE` โดยเจตนา**
#
# เงื่อนไข "หมดอายุแล้ว" อยู่ใน policy `login_challenges_sweep` ไม่ใช่ที่นี่
# เพราะคำสั่งที่อ้างคอลัมน์จะดึง SELECT policy มาใช้ด้วย แล้วลบได้ศูนย์แถวแบบเงียบ ๆ
# **ใส่ `WHERE` แล้วการเก็บกวาดจะพังโดยไม่มีใครรู้** (ข้อเดียวกับ `_END_ALL` ของ F-05)
_SWEEP_CHALLENGES = "DELETE FROM login_challenges"


@dataclass(frozen=True, slots=True)
class Swept:
    """จำนวนแถวที่ลบไป แยกตามตาราง — ใช้รายงานให้คนที่สั่งงานเห็น"""

    throttle_rows: int
    challenge_rows: int

    @property
    def total(self) -> int:
        """จำนวนแถวที่ลบไปทั้งหมด"""
        return self.throttle_rows + self.challenge_rows


async def sweep(session: PresentedSession, *, now: datetime) -> Swept:
    """ลบแถวที่ไม่มีผลอะไรแล้วจากทั้งสองตาราง — คืนจำนวนที่ลบ

    รับ `now` เข้ามาแทนการอ่านนาฬิกาเอง เพื่อให้เทสต์เดินเวลาได้ และเพื่อให้ทุกคำสั่ง
    ในรอบเดียวกันใช้เวลาเดียวกัน
    """
    throttle_rows = 0
    for bucket in Bucket:
        throttle_rows += await _swept_bucket(session, bucket, now=now)

    challenges = await session.execute(_SWEEP_CHALLENGES)
    return Swept(
        throttle_rows=throttle_rows,
        challenge_rows=_rows(challenges),
    )


async def _swept_bucket(session: PresentedSession, bucket: Bucket, *, now: datetime) -> int:
    """ลบแถวที่หมดผลของถังชนิดหนึ่ง"""
    rule = RULES[bucket]
    if isinstance(rule, TokenRule):
        result = await session.execute(
            _SWEEP_TOKEN_BUCKET,
            {
                "kind": bucket.value,
                "now": now,
                "capacity": rule.capacity,
                "seconds": int(rule.refill_interval.total_seconds()),
            },
        )
        return _rows(result)

    result = await session.execute(
        _SWEEP_WINDOW_BUCKET,
        {"kind": bucket.value, "now": now, "stale_before": now - rule.window},
    )
    return _rows(result)


def _rows(result: object) -> int:
    """จำนวนแถวที่คำสั่งลบไป

    ใช้ `rowcount` ไม่ใช่ `RETURNING` ด้วยเหตุผลเดียวกับ `sessions.py` ของ F-05:
    `RETURNING` อ้างคอลัมน์ ซึ่งดึง SELECT policy มาใช้ด้วย
    """
    return cast("CursorResult[Any]", result).rowcount
