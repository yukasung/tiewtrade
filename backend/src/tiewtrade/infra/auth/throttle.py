"""ตัวนับอัตราการเรียกของเส้นทางยืนยันตัวตน (F-05 plan.md ข้อ 4)

**เก็บในฐานข้อมูล ไม่ใช่ในกระบวนการ** เพราะตัวนับในกระบวนการเดียวหลบได้ด้วยการยิง
ไปอีกกระบวนการ (บทเรียนเดียวกับตัวกั้นอัตราของ F-35 ที่ยอมรับข้อจำกัดนี้ไว้)

**การหน่วงคือเวลาที่เร็วที่สุดที่ยอมรับคำขอถัดไป ไม่ใช่การตอบช้าทีละคำขอ** (RQ-23)
การตอบช้าขนานกันได้ จึงกันการเดารหัสผ่านไม่ได้เลย

`INSERT ... ON CONFLICT DO UPDATE` เป็นตัว **สร้างและล็อก** ในคำสั่งเดียว เพราะ
`SELECT ... FOR UPDATE` ล็อกได้เฉพาะแถวที่มีอยู่แล้ว คำขอแรกที่มาพร้อมกันบนตารางว่าง
จะไม่มีอะไรให้ล็อก

**ตัวนับต้องถูกบันทึกแม้คำขอนั้นถูกปฏิเสธ** จึงอยู่ใน transaction ของตัวเอง
ถ้าร่วม transaction กับการตรวจรหัสผ่านแล้วถูกยกเลิก การเดารหัสผ่านจะไม่ถูกนับเลย

**ตารางนี้ไม่อยู่ใต้ RLS** เพราะหน้าที่ของมันคือตัวนับร่วมของช่วงก่อนยืนยันตัวตน
(ต้องนับอีเมลที่ยังไม่มีบัญชี และ IP ที่หลายคนใช้ร่วมกัน) และขอบเขตความเสียหาย
ถูกจำกัดด้วยสิทธิ์ที่ให้เฉพาะบทบาท `auth` — เจ้าของอนุมัติข้อยกเว้นนี้ไว้

**ยังไม่มีการลบแถวเก่าโดยอัตโนมัติ** แถวของ IP ที่ไม่กลับมาอีกจะค้างอยู่
ต้องมีงานเก็บกวาดก่อนปล่อยผู้ใช้จริง
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Final

from sqlalchemy import Result

from tiewtrade.infra.db.session import PresentedSession

#: หน้าต่างเวลาและเพดานตามที่เจ้าของตัดสิน (requirements.md Q-4)
ACCOUNT_FAILURES_BEFORE_DELAY: Final[int] = 5
ACCOUNT_MAX_DELAY: Final[timedelta] = timedelta(seconds=10)
ACCOUNT_WINDOW: Final[timedelta] = timedelta(minutes=15)
IP_FAILURES_BEFORE_BLOCK: Final[int] = 20
IP_WINDOW: Final[timedelta] = timedelta(minutes=15)
SIGNUP_PER_HOUR: Final[int] = 5
SIGNUP_WINDOW: Final[timedelta] = timedelta(hours=1)


@dataclass(frozen=True, slots=True)
class Rule:
    """กฎของถังหนึ่งชนิด

    `max_delay` เป็นเพดาน **ต่อรอบ** ไม่ใช่เพดานเวลาที่เจ้าของบัญชีถูกกันออกจากระบบ
    — ข้อจำกัดนี้ยังไม่ถูกปิด ดู **NC-14** ใน `requirements.md` ของ F-05
    """

    threshold: int
    window: timedelta
    max_delay: timedelta
    doubling: bool


class Bucket(Enum):
    """สิ่งที่ถูกนับ — **นับแยกกัน ไม่รวมเป็นคู่**

    รวมเป็นคู่ `(บัญชี, IP)` แล้วเปลี่ยน IP ก็ได้ตัวนับใหม่สำหรับบัญชีเดิม
    และเปลี่ยนอีเมลก็ได้ตัวนับใหม่จาก IP เดิม (รีวิว 2026-10-02)
    """

    ACCOUNT = "ACCOUNT"
    IP = "IP"
    SIGNUP_IP = "SIGNUP_IP"

    @property
    def rule(self) -> Rule:
        """กฎของถังชนิดนี้ — อยู่ในตารางเดียว ไม่ใช่กระจายเป็นเงื่อนไขหลายที่"""
        return RULES[self]

    @property
    def window(self) -> timedelta:
        """หน้าต่างเวลาที่ตัวนับของชนิดนี้ใช้"""
        return self.rule.window


@dataclass(frozen=True, slots=True)
class BucketState:
    """สภาพของตัวนับหนึ่งถัง ณ เวลาที่ถาม"""

    failures: int
    next_allowed_at: datetime | None
    window_started_at: datetime

    def blocked_at(self, now: datetime) -> bool:
        """ยังอยู่ในช่วงที่ต้องรอหรือไม่"""
        return self.next_allowed_at is not None and now < self.next_allowed_at


def key_of(value: str) -> str:
    """แฮชของสิ่งที่ถูกนับ

    มีไว้เพื่อไม่ให้มีอีเมลหรือ IP เป็นตัวอักษรอยู่ในตาราง **ไม่ใช่การปกปิด**
    เพราะเดาอีเมลแล้วแฮชเทียบได้
    """
    return hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()


_CLAIM = """
INSERT INTO auth_throttle (bucket_kind, bucket_key)
VALUES (:kind, :key)
ON CONFLICT (bucket_kind, bucket_key)
DO UPDATE SET bucket_key = auth_throttle.bucket_key
RETURNING failures, next_allowed_at, window_started_at
"""

_RESET_WINDOW = """
UPDATE auth_throttle
SET failures = 0, next_allowed_at = NULL, window_started_at = now()
WHERE bucket_kind = :kind AND bucket_key = :key
"""

# **เป็น upsert ไม่ใช่ UPDATE เปล่า** — ถังอาจยังไม่มีแถว และการพึ่งว่า `claim`
# ถูกเรียกมาก่อนคือการพึ่งลำดับการเรียกซึ่งวันหนึ่งจะมีทางเข้าที่ไม่ผ่านตรงนั้น
_COUNT_FAILURE = """
INSERT INTO auth_throttle (bucket_kind, bucket_key, failures)
VALUES (:kind, :key, 1)
ON CONFLICT (bucket_kind, bucket_key)
DO UPDATE SET failures = auth_throttle.failures + 1
RETURNING failures, next_allowed_at, window_started_at
"""

_SET_DELAY = """
UPDATE auth_throttle
SET next_allowed_at = now() + :delay
WHERE bucket_kind = :kind AND bucket_key = :key
RETURNING failures, next_allowed_at, window_started_at
"""

_CLEAR = """
DELETE FROM auth_throttle
WHERE bucket_kind = :kind AND bucket_key = :key
"""


async def claim(
    session: PresentedSession, bucket: Bucket, key: str, *, now: datetime
) -> BucketState:
    """สร้างหรือล็อกถังนี้ แล้วคืนสภาพของมัน — **ล็อกจนจบ transaction**

    คำขอที่ยิงพร้อมกันเข้าคิวที่ล็อกของแถวนี้ จึงเห็นเวลาที่ต้องรอที่อัปเดตแล้ว
    """
    state = _state_of(await session.execute(_CLAIM, {"kind": bucket.value, "key": key}))
    if now - state.window_started_at >= bucket.window:
        await session.execute(_RESET_WINDOW, {"kind": bucket.value, "key": key})
        return BucketState(failures=0, next_allowed_at=None, window_started_at=now)
    return state


async def count_failure(session: PresentedSession, bucket: Bucket, key: str) -> BucketState:
    """นับความล้มเหลวหนึ่งครั้ง และตั้งเวลาที่ต้องรอถ้าถึงเกณฑ์

    กฎการเพิ่มเวลาหน่วงอยู่ใน `delay_after()` ฝั่ง Python ที่เดียว ฐานข้อมูลทำหน้าที่
    นับให้ถูกต้องตอนมีคำขอพร้อมกัน ส่วนการตัดสินว่าหน่วงนานเท่าไรเป็นกฎที่ทดสอบได้เอง
    """
    counted = _state_of(await session.execute(_COUNT_FAILURE, {"kind": bucket.value, "key": key}))
    delay = delay_after(counted.failures, bucket)
    if delay <= timedelta(0):
        return counted
    return _state_of(
        await session.execute(_SET_DELAY, {"kind": bucket.value, "key": key, "delay": delay})
    )


async def clear(session: PresentedSession, bucket: Bucket, key: str) -> None:
    """ล้างตัวนับของถังนี้

    **ใช้กับถังของบัญชีเท่านั้นเมื่อเข้าสู่ระบบสำเร็จ** ถังของ IP หมดตามหน้าต่างเวลา
    เท่านั้น มิฉะนั้นผู้โจมตีใช้บัญชีตัวเองเข้าสู่ระบบสำเร็จเพื่อล้างตัวนับ
    แล้วเดาบัญชีอื่นต่อได้ (รีวิว 2026-10-02)
    """
    await session.execute(_CLEAR, {"kind": bucket.value, "key": key})


def delay_after(failures: int, bucket: Bucket) -> timedelta:
    """เวลาที่ต้องรอหลังล้มเหลวครบจำนวนนั้น — ยังไม่ถึงเกณฑ์คือไม่ต้องรอ

    ถังที่เพิ่มเป็นสองเท่า (บัญชี): หน่วงนานขึ้นเรื่อย ๆ แต่ **ไม่เกินเพดานต่อรอบ**
    เพื่อให้คนกลั่นแกล้งหน่วงเจ้าของบัญชีได้จำกัด — **ยังไม่ใช่การรับประกันว่า
    เจ้าของกลับเข้ามาได้ทันตอนฉุกเฉิน ดู NC-14**
    ถังที่ไม่เพิ่ม (IP, การสมัคร): ปฏิเสธไปจนหมดหน้าต่างเวลา
    """
    rule = bucket.rule
    if failures < rule.threshold:
        return timedelta(0)
    if not rule.doubling:
        return rule.max_delay
    over = failures - rule.threshold
    return timedelta(seconds=min(2**over, int(rule.max_delay.total_seconds())))


def _state_of(result: Result[Any]) -> BucketState:
    """แปลงแถวที่ได้จากฐานข้อมูลเป็นสภาพของถัง พร้อมตรวจชนิด"""
    failures, next_allowed_at, window_started_at = tuple(result.one())
    if (
        not isinstance(failures, int)
        or not isinstance(window_started_at, datetime)
        or not (next_allowed_at is None or isinstance(next_allowed_at, datetime))
    ):
        raise TypeError("ฐานข้อมูลคืนชนิดข้อมูลที่ไม่คาดไว้สำหรับตาราง auth_throttle")
    return BucketState(
        failures=failures,
        next_allowed_at=next_allowed_at,
        window_started_at=window_started_at,
    )


#: กฎของทุกถัง — ตัวเลขตามที่เจ้าของตัดสิน (requirements.md Q-4)
#:
#: อยู่ท้ายไฟล์เพราะอ้างถึง `Bucket` ส่วน `Bucket.rule` อ่านตารางนี้ตอนถูกเรียก
#: จึงไม่เป็นปัญหา — ข้อดีคือ **กฎของทุกถังอยู่ในสายตาเดียว** เทียบกันได้ทันที
RULES: Final[dict[Bucket, Rule]] = {
    # บัญชี: ผิดห้าครั้งแล้วหน่วงเพิ่มเป็นสองเท่า เพดานต่อรอบสิบวินาที **ไม่ล็อกบัญชี**
    Bucket.ACCOUNT: Rule(
        threshold=ACCOUNT_FAILURES_BEFORE_DELAY,
        window=ACCOUNT_WINDOW,
        max_delay=ACCOUNT_MAX_DELAY,
        doubling=True,
    ),
    # IP: ผิดยี่สิบครั้งในสิบห้านาทีแล้วปฏิเสธจนหมดหน้าต่าง · **เข้าสู่ระบบสำเร็จไม่ล้าง**
    Bucket.IP: Rule(
        threshold=IP_FAILURES_BEFORE_BLOCK,
        window=IP_WINDOW,
        max_delay=IP_WINDOW,
        doubling=False,
    ),
    # การสมัคร: โควตาห้าครั้งต่อชั่วโมงต่อ IP
    Bucket.SIGNUP_IP: Rule(
        threshold=SIGNUP_PER_HOUR,
        window=SIGNUP_WINDOW,
        max_delay=SIGNUP_WINDOW,
        doubling=False,
    ),
}
