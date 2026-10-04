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
from functools import cache
from typing import Any, Final

from sqlalchemy import Result

from tiewtrade.infra.db.session import PresentedSession, UserSession

#: session ชนิดใดก็ได้ที่สั่ง query ได้ — **ตัวนับใช้ได้ทั้งก่อนและหลังรู้ว่าเป็นใคร**
#:
#: ถังของ F-05/F-06 ถูกใช้ก่อนรู้ตัวตน (`PresentedSession`) ส่วนถังของ F-07
#: ถูกใช้หลังรู้แล้ว (`UserSession`) — ตรรกะเดียวกัน ต่างแค่ขอบเขตของ session
Counting = PresentedSession | UserSession

#: ── ถังของปัจจัยที่สอง (F-06 Q-7, เจ้าของอนุมัติ 2026-10-03) ──
#:
#: **เพดานคือ 10 ครั้งต่อบัญชีในช่วง 60 นาทีใด ๆ** ซึ่งเป็นค่าที่เจ้าของตัดสิน
#: ความจุ + อัตราเติมคืนต่อชั่วโมง = เพดาน ฉะนั้น **เปลี่ยนตัวใดตัวหนึ่งต้องคิดเพดานใหม่**
#:
#: ใช้ token bucket ไม่ใช่หน้าต่างคงที่ เพราะหน้าต่างคงที่รีเซ็ตเมื่อครบเวลา
#: จึงเดาเต็มเพดานท้ายหน้าต่างแรกแล้วต่อต้นหน้าต่างถัดไปได้ = 20 ครั้งในช่วง 60 นาทีจริง
SECOND_FACTOR_CAPACITY: Final[int] = 4
SECOND_FACTOR_REFILL: Final[timedelta] = timedelta(minutes=10)

#: เพดานที่ตัวเลขสองตัวข้างบนให้ — **เทสต์ตรึงค่านี้ไว้** (validation V-62.6)
SECOND_FACTOR_CEILING_PER_HOUR: Final[int] = 10

#: หน้าต่างเวลาและเพดานตามที่เจ้าของตัดสิน (requirements.md Q-4)
ACCOUNT_FAILURES_BEFORE_DELAY: Final[int] = 5
ACCOUNT_MAX_DELAY: Final[timedelta] = timedelta(seconds=10)
ACCOUNT_WINDOW: Final[timedelta] = timedelta(minutes=15)
IP_FAILURES_BEFORE_BLOCK: Final[int] = 20
IP_WINDOW: Final[timedelta] = timedelta(minutes=15)
SIGNUP_PER_HOUR: Final[int] = 5
SIGNUP_WINDOW: Final[timedelta] = timedelta(hours=1)

#: ── ถังของ F-07 ──
#:
#: **ค่าตั้งต้นที่เจ้าของยืนยันเมื่อ 2026-10-04** ในฐานะ *จุดเริ่มต้นที่ระมัดระวัง*
#: — `security.md` หัวข้อ 3 บังคับว่าต้องคุมอัตราแต่ไม่ได้ให้ตัวเลข
#:
#: **ยังไม่มีข้อมูลการใช้งานพิสูจน์ว่าเหมาะที่สุด** และ **ห้ามอ้างว่าผู้ใช้เพิ่ม key
#: ไม่เกินหกใบตลอดอายุบัญชี** เพราะผู้ใช้หมุนเวียน key ได้ (เจ้าของทักเมื่อ 2026-10-04)
#: เหตุผลที่เหลืออยู่คือ: ทุกครั้งที่เพิ่มคือหนึ่งคำขอที่ยิงตลาดและหนึ่งความลับที่ถูกเก็บ
#: ฉะนั้นต้องมีเพดาน · **ทบทวนเมื่อมีข้อมูลการใช้งานจริง** (RQ-11.5)
API_KEY_ADD_CAPACITY: Final[int] = 3
API_KEY_ADD_REFILL: Final[timedelta] = timedelta(minutes=20)

#: การกดลองใหม่ไม่ได้สร้างแถวและไม่ได้เก็บความลับเพิ่ม จึงผ่อนกว่า
#: แต่ยังต้องมีเพดาน เพราะทุกครั้งที่กดคือหนึ่งบันทึกในตารางที่ลบแถวไม่ได้
#:
#: **ทั้งสองถังนับต่อผู้ใช้ รวมทุก key** (RQ-11.1) — ถังต่อ key ทำให้การเพิ่ม key ใหม่
#: กลายเป็นวิธีได้โควตาใหม่
API_KEY_RETRY_CAPACITY: Final[int] = 6
API_KEY_RETRY_REFILL: Final[timedelta] = timedelta(minutes=5)


@dataclass(frozen=True, slots=True)
class TokenRule:
    """กฎของถังแบบ token bucket — ความจุก้อนแรก และอัตราเติมคืนตามเวลา

    ต่างจาก `Rule` ที่เป็นหน้าต่างคงที่: ถังนี้ **ไม่รีเซ็ตเป็นก้อน** แต่เติมคืนทีละหนึ่ง
    ฉะนั้นเพดานในช่วงเวลาเลื่อนเท่ากับ `capacity` บวกจำนวนที่เติมคืนในช่วงนั้น
    ซึ่งคำนวณได้แน่นอน ไม่ขึ้นกับว่าช่วงเวลานั้นเริ่มตรงไหน
    """

    capacity: int
    refill_interval: timedelta

    @property
    def ceiling_per_hour(self) -> int:
        """จำนวนครั้งสูงสุดในช่วง 60 นาทีใด ๆ — ความจุบวกที่เติมคืนได้ในหนึ่งชั่วโมง"""
        per_hour = int(timedelta(hours=1) / self.refill_interval)
        return self.capacity + per_hour


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
    #: สามถังของ F-06 — **เป็น token bucket ทั้งสามใบ**
    #:
    #: `TOTP_ACCOUNT` มีคีย์เป็นบัญชี จึงนับข้ามรอบ login และข้าม IP ตาม RQ-8
    #: ส่วนรหัสสำรองมีถังของตัวเองเพราะยาวกว่าและมีจำนวนจำกัด เกณฑ์ที่เหมาะจึงต่างกัน
    TOTP_ACCOUNT = "TOTP_ACCOUNT"
    TOTP_IP = "TOTP_IP"
    RECOVERY_ACCOUNT = "RECOVERY_ACCOUNT"
    #: สองถังของ F-07 — **อยู่คนละตารางกับถังข้างบน** (เจ้าของอนุมัติ 2026-10-04)
    #:
    #: เส้นทางของ F-07 รันบนบทบาท `api` ซึ่งเขียน `auth_throttle` ไม่ได้ และไม่ควรเขียนได้
    #: เพราะตารางนั้นคุมการเดารหัสผ่าน · แยกกันสองใบเพราะต้นทุนต่างกัน: การเพิ่ม key
    #: ยิงตลาดและกินที่เก็บความลับ ส่วนการกดลองใหม่แค่ปลุกงานที่มีอยู่แล้ว
    API_KEY_ADD = "API_KEY_ADD"
    API_KEY_RETRY = "API_KEY_RETRY"

    @property
    def table(self) -> str:
        """ตารางที่เก็บถังชนิดนี้ — **สิทธิ์ของสองตารางนี้แยกขาดกัน**"""
        if self in (Bucket.API_KEY_ADD, Bucket.API_KEY_RETRY):
            return "api_throttle"
        return "auth_throttle"

    @property
    def rule(self) -> Rule | TokenRule:
        """กฎของถังชนิดนี้ — อยู่ในตารางเดียว ไม่ใช่กระจายเป็นเงื่อนไขหลายที่"""
        return RULES[self]

    @property
    def is_token_bucket(self) -> bool:
        """ถังนี้เติมคืนตามเวลา หรือรีเซ็ตเป็นหน้าต่าง"""
        return isinstance(self.rule, TokenRule)

    @property
    def window(self) -> timedelta:
        """หน้าต่างเวลาที่ตัวนับของชนิดนี้ใช้ — ถัง token bucket ไม่มีหน้าต่าง"""
        rule = self.rule
        if isinstance(rule, TokenRule):
            raise TypeError(f"ถัง {self.value} เป็น token bucket จึงไม่มีหน้าต่างเวลา")
        return rule.window


@dataclass(frozen=True, slots=True)
class BucketState:
    """สภาพของตัวนับหนึ่งถัง ณ เวลาที่ถาม

    `tokens_left` มีค่าเฉพาะถังแบบเติมคืน และ `next_allowed_at` มีค่าเฉพาะถัง
    แบบหน้าต่างคงที่ — สองชนิดนี้ตอบคำถาม "ถูกปฏิเสธหรือยัง" ด้วยกลไกต่างกัน
    """

    failures: int
    next_allowed_at: datetime | None
    window_started_at: datetime
    tokens_left: int | None = None

    def blocked_at(self, now: datetime) -> bool:
        """ยังอยู่ในช่วงที่ต้องรอหรือไม่

        ถังแบบเติมคืนถูกปฏิเสธเมื่อโควตาหมด ไม่ใช่เมื่อยังไม่ถึงเวลาที่อนุญาต
        """
        if self.tokens_left is not None:
            return self.tokens_left <= 0
        return self.next_allowed_at is not None and now < self.next_allowed_at


def key_of(value: str) -> str:
    """แฮชของสิ่งที่ถูกนับ

    มีไว้เพื่อไม่ให้มีอีเมลหรือ IP เป็นตัวอักษรอยู่ในตาราง **ไม่ใช่การปกปิด**
    เพราะเดาอีเมลแล้วแฮชเทียบได้
    """
    return hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()


#: สร้างหรือล็อกถังแบบเติมคืน — ค่าเริ่มต้นคือโควตาเต็ม
_claim_tokens_sql = """
INSERT INTO {table} (bucket_kind, bucket_key, tokens_left, refilled_at)
VALUES (:kind, :key, :capacity, now())
ON CONFLICT (bucket_kind, bucket_key)
DO UPDATE SET bucket_key = {table}.bucket_key
RETURNING tokens_left, refilled_at
"""

#: เติมคืนตามเวลาที่ผ่านไป — **เลื่อน `refilled_at` ไปทีละช่วง ไม่ใช่ไปที่ `now()`**
#: มิฉะนั้นเวลาที่ผ่านไปแต่ยังไม่ครบหนึ่งช่วงจะถูกทิ้ง และการเรียกถี่ ๆ จะไม่เติมคืนเลย
_refill_sql = """
UPDATE {table}
SET tokens_left = least(:capacity, tokens_left + :gained),
    refilled_at = refilled_at + (:gained * make_interval(secs => :seconds))
WHERE bucket_kind = :kind AND bucket_key = :key
RETURNING tokens_left, refilled_at
"""

_spend_token_sql = """
UPDATE {table}
SET tokens_left = greatest(0, tokens_left - 1)
WHERE bucket_kind = :kind AND bucket_key = :key
RETURNING tokens_left, refilled_at
"""

_claim_sql = """
INSERT INTO {table} (bucket_kind, bucket_key)
VALUES (:kind, :key)
ON CONFLICT (bucket_kind, bucket_key)
DO UPDATE SET bucket_key = {table}.bucket_key
RETURNING failures, next_allowed_at, window_started_at
"""

_reset_window_sql = """
UPDATE {table}
SET failures = 0, next_allowed_at = NULL, window_started_at = now()
WHERE bucket_kind = :kind AND bucket_key = :key
"""

# **เป็น upsert ไม่ใช่ UPDATE เปล่า** — ถังอาจยังไม่มีแถว และการพึ่งว่า `claim`
# ถูกเรียกมาก่อนคือการพึ่งลำดับการเรียกซึ่งวันหนึ่งจะมีทางเข้าที่ไม่ผ่านตรงนั้น
_count_failure_sql = """
INSERT INTO {table} (bucket_kind, bucket_key, failures)
VALUES (:kind, :key, 1)
ON CONFLICT (bucket_kind, bucket_key)
DO UPDATE SET failures = {table}.failures + 1
RETURNING failures, next_allowed_at, window_started_at
"""

_set_delay_sql = """
UPDATE {table}
SET next_allowed_at = now() + :delay
WHERE bucket_kind = :kind AND bucket_key = :key
RETURNING failures, next_allowed_at, window_started_at
"""

_clear_sql = """
DELETE FROM {table}
WHERE bucket_kind = :kind AND bucket_key = :key
"""


#: คำสั่งที่เติมชื่อตารางแล้ว — **ตรรกะเดียว สองที่เก็บ** (F-07 `plan.md` ข้อ 12.1)
#:
#: เติมชื่อตารางด้วยการแทนที่ข้อความได้ เพราะชื่อมาจาก `Bucket.table` ซึ่งเป็น
#: ค่าคงที่ในโค้ด ไม่ใช่ค่าที่มาจากผู้ใช้ · ชื่อตารางเป็นตัวระบุของ SQL จึงส่งเป็น
#: พารามิเตอร์ไม่ได้อยู่แล้ว
@cache
def _statement(template: str, table: str) -> str:
    return template.format(table=table)


async def claim(session: Counting, bucket: Bucket, key: str, *, now: datetime) -> BucketState:
    """สร้างหรือล็อกถังนี้ แล้วคืนสภาพของมัน — **ล็อกจนจบ transaction**

    คำขอที่ยิงพร้อมกันเข้าคิวที่ล็อกของแถวนี้ จึงเห็นสภาพที่อัปเดตแล้ว
    ไม่ใช่แต่ละใบเห็นถังเต็ม (validation V-62.1)
    """
    rule = bucket.rule
    if isinstance(rule, TokenRule):
        return await _claim_tokens(session, bucket, key, rule=rule, now=now)

    state = _state_of(
        await session.execute(
            _statement(_claim_sql, bucket.table), {"kind": bucket.value, "key": key}
        )
    )
    if now - state.window_started_at >= rule.window:
        await session.execute(
            _statement(_reset_window_sql, bucket.table), {"kind": bucket.value, "key": key}
        )
        return BucketState(failures=0, next_allowed_at=None, window_started_at=now)
    return state


async def _claim_tokens(
    session: Counting, bucket: Bucket, key: str, *, rule: TokenRule, now: datetime
) -> BucketState:
    """ล็อกถังแบบเติมคืน แล้วเติมคืนตามเวลาที่ผ่านไปจริง"""
    state = _tokens_of(
        await session.execute(
            _statement(_claim_tokens_sql, bucket.table),
            {
                "kind": bucket.value,
                "key": key,
                "capacity": rule.capacity,
            },
        )
    )
    gained = int((now - state.window_started_at) // rule.refill_interval)
    if gained <= 0:
        return state
    return _tokens_of(
        await session.execute(
            _statement(_refill_sql, bucket.table),
            {
                "kind": bucket.value,
                "key": key,
                "capacity": rule.capacity,
                "gained": gained,
                "seconds": int(rule.refill_interval.total_seconds()),
            },
        )
    )


async def count_failure(session: Counting, bucket: Bucket, key: str) -> BucketState:
    """นับความล้มเหลวหนึ่งครั้ง และตั้งเวลาที่ต้องรอถ้าถึงเกณฑ์

    กฎการเพิ่มเวลาหน่วงอยู่ใน `delay_after()` ฝั่ง Python ที่เดียว ฐานข้อมูลทำหน้าที่
    นับให้ถูกต้องตอนมีคำขอพร้อมกัน ส่วนการตัดสินว่าหน่วงนานเท่าไรเป็นกฎที่ทดสอบได้เอง
    """
    if bucket.is_token_bucket:
        # ถังแบบเติมคืนไม่มีเวลาหน่วง — มันปฏิเสธเมื่อโควตาหมด ไม่ใช่ให้รอ
        return _tokens_of(
            await session.execute(
                _statement(_spend_token_sql, bucket.table), {"kind": bucket.value, "key": key}
            )
        )

    counted = _state_of(
        await session.execute(
            _statement(_count_failure_sql, bucket.table), {"kind": bucket.value, "key": key}
        )
    )
    delay = delay_after(counted.failures, bucket)
    if delay <= timedelta(0):
        return counted
    return _state_of(
        await session.execute(
            _statement(_set_delay_sql, bucket.table),
            {"kind": bucket.value, "key": key, "delay": delay},
        )
    )


async def clear(session: Counting, bucket: Bucket, key: str) -> None:
    """ล้างตัวนับของถังนี้

    **ใช้กับถังของบัญชีเท่านั้นเมื่อเข้าสู่ระบบสำเร็จ** ถังของ IP หมดตามหน้าต่างเวลา
    เท่านั้น มิฉะนั้นผู้โจมตีใช้บัญชีตัวเองเข้าสู่ระบบสำเร็จเพื่อล้างตัวนับ
    แล้วเดาบัญชีอื่นต่อได้ (รีวิว 2026-10-02)
    """
    await session.execute(_statement(_clear_sql, bucket.table), {"kind": bucket.value, "key": key})


def _tokens_of(result: Result[Any]) -> BucketState:
    """แปลงแถวของถังแบบเติมคืนเป็นสภาพของถัง

    ใช้ `window_started_at` เก็บ `refilled_at` เพื่อไม่ให้ชนิดข้อมูลมีสองช่องเวลา
    ที่ความหมายทับกัน — ชื่อช่องอ่านจาก `tokens_left` ว่าเป็นถังชนิดไหน
    """
    tokens_left, refilled_at = tuple(result.one())
    if not isinstance(tokens_left, int) or not isinstance(refilled_at, datetime):
        raise TypeError("ฐานข้อมูลคืนชนิดข้อมูลที่ไม่คาดไว้สำหรับถังแบบเติมคืน")
    return BucketState(
        failures=0,
        next_allowed_at=None,
        window_started_at=refilled_at,
        tokens_left=tokens_left,
    )


def delay_after(failures: int, bucket: Bucket) -> timedelta:
    """เวลาที่ต้องรอหลังล้มเหลวครบจำนวนนั้น — ยังไม่ถึงเกณฑ์คือไม่ต้องรอ

    ถังที่เพิ่มเป็นสองเท่า (บัญชี): หน่วงนานขึ้นเรื่อย ๆ แต่ **ไม่เกินเพดานต่อรอบ**
    เพื่อให้คนกลั่นแกล้งหน่วงเจ้าของบัญชีได้จำกัด — **ยังไม่ใช่การรับประกันว่า
    เจ้าของกลับเข้ามาได้ทันตอนฉุกเฉิน ดู NC-14**
    ถังที่ไม่เพิ่ม (IP, การสมัคร): ปฏิเสธไปจนหมดหน้าต่างเวลา
    """
    rule = bucket.rule
    if isinstance(rule, TokenRule):
        raise TypeError(f"ถัง {bucket.value} เป็น token bucket จึงไม่มีเวลาหน่วง")
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
RULES: Final[dict[Bucket, Rule | TokenRule]] = {
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
    # เพิ่ม key: ทำติดกันได้สามครั้ง แล้วเติมคืนทีละหนึ่งทุกยี่สิบนาที
    Bucket.API_KEY_ADD: TokenRule(
        capacity=API_KEY_ADD_CAPACITY,
        refill_interval=API_KEY_ADD_REFILL,
    ),
    # กดลองใหม่: ผ่อนกว่าเพราะไม่ได้สร้างของใหม่ แต่ยังมีเพดาน
    Bucket.API_KEY_RETRY: TokenRule(
        capacity=API_KEY_RETRY_CAPACITY,
        refill_interval=API_KEY_RETRY_REFILL,
    ),
    # ปัจจัยที่สอง: พิมพ์ผิดติดกันได้เท่าความจุ แล้วเติมคืนทีละหนึ่ง
    # **เพดานในช่วง 60 นาทีใด ๆ = ความจุ + ที่เติมคืนได้ในหนึ่งชั่วโมง**
    Bucket.TOTP_ACCOUNT: TokenRule(
        capacity=SECOND_FACTOR_CAPACITY,
        refill_interval=SECOND_FACTOR_REFILL,
    ),
    Bucket.TOTP_IP: TokenRule(
        capacity=SECOND_FACTOR_CAPACITY,
        refill_interval=SECOND_FACTOR_REFILL,
    ),
    # รหัสสำรองใช้กฎเดียวกันแต่แยกถัง จึงใช้โควตาของกันและกันไม่ได้
    # — มิฉะนั้นผู้โจมตีเดารหัสสำรองจนโควตาของ TOTP หมดได้
    Bucket.RECOVERY_ACCOUNT: TokenRule(
        capacity=SECOND_FACTOR_CAPACITY,
        refill_interval=SECOND_FACTOR_REFILL,
    ),
}
