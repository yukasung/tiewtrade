"""การคุมอัตราการเรียกของเส้นทางยืนยันตัวตน (F-05 plan.md ข้อ 4)

**ล็อกถังไว้ตลอดช่วงที่ตรวจรหัสผ่าน** คำขอที่ยิงพร้อมกันบนบัญชีเดียวกันจึงเข้าคิว
ไม่ใช่วิ่งขนาน — ถ้าปล่อยล็อกก่อนตรวจ การยิง 20 คำขอพร้อมกันจะผ่านด่านทั้งหมด

**ตัวนับอยู่ใน transaction ของตัวเอง** จึงถูกบันทึกแม้คำขอนั้นถูกปฏิเสธ
ถ้าร่วม transaction กับการตรวจรหัสผ่านแล้วถูกยกเลิก การเดารหัสผ่านจะไม่ถูกนับเลย

**แต่ "transaction ของตัวเอง" ยังไม่พอ** (แก้ใน F-06 — `plan.md` หัวข้อ 2):
`presented_session()` ย้อน transaction เมื่อมีข้อผิดพลาด **ชนิดใดก็ตาม** หลุดออกมา
ซึ่งรวม `HTTPException` ที่เส้นทางโยนตอนปฏิเสธคำขอ ผลคือการนับหายไปทุกครั้งที่
คำขอถูกปฏิเสธ — การคุมอัตราการเรียกจึงไม่ทำงานเลย

ทางแก้คือแยก **การปฏิเสธตามกฎ** ออกจาก **ความผิดพลาดของระบบ**:
เส้นทางโยน `AuthRejectedError` ซึ่งถูกจับ **ภายใน** transaction (จึง commit ตามปกติ)
แล้วแปลงเป็น `HTTPException` **หลัง** transaction จบ · ส่วน bug, ฐานข้อมูลล่ม
และ `HTTPException` ที่เป็น 500/503 ไม่ใช่ชนิดนี้ จึงยังย้อนตามเดิม
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.infra.auth import Bucket, claim, clear, count_failure, key_of
from tiewtrade.infra.db import DatabaseRole
from tiewtrade.infra.db.session import PresentedSession, presented_session, user_session


class AuthRejectedError(Exception):
    """คำขอยืนยันตัวตนถูกปฏิเสธตามกฎ — **ผลลัพธ์ปกติ ไม่ใช่ความล้มเหลวของ transaction**

    มีชนิดนี้เพื่อให้ `throttled()` แยกได้ว่าอะไรควร commit ตัวนับแล้วค่อยปฏิเสธ
    และอะไรควรย้อนทุกอย่าง · **ห้ามใช้ชนิดนี้กับความผิดพลาดของระบบ**
    เพราะมันทำให้สิ่งที่เขียนไว้ก่อนหน้าถูก commit

    เส้นทางที่อยู่ **นอก** `throttled()` โยน `HTTPException` ได้ตามปกติ
    """

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail

    def as_http_exception(self) -> HTTPException:
        """รูปที่ส่งกลับให้ผู้เรียก — ข้อความและสถานะไม่เปลี่ยนจากที่เส้นทางตั้งไว้

        **แอปแปลงชนิดนี้เป็นคำตอบที่จุดเดียว** (`app.py`) ฉะนั้นเส้นทางที่ไม่ได้
        อยู่ใน `throttled()` ก็โยนชนิดนี้ได้ โดยไม่หลุดเป็น 500
        """
        return HTTPException(self.status_code, self.detail)


@dataclass(frozen=True, slots=True)
class ThrottleGuard:
    """ถังที่ถูกล็อกไว้แล้วสำหรับคำขอหนึ่ง"""

    _session: PresentedSession
    _buckets: tuple[tuple[Bucket, str], ...]
    blocked: bool

    async def count_attempt(self) -> None:
        """นับหนึ่งครั้งให้ทุกถังของคำขอนี้

        ใช้ทั้งกับการเข้าสู่ระบบที่ล้มเหลว และกับโควตาการสมัครต่อ IP ซึ่งนับทุกครั้ง
        ที่สมัคร ไม่ใช่นับแต่ครั้งที่ล้มเหลว
        """
        for bucket, key in self._buckets:
            await count_failure(self._session, bucket, key)

    async def forget_account(self) -> None:
        """ล้างตัวนับ — **เฉพาะถังของบัญชี**

        ถังของ IP หมดตามหน้าต่างเวลาเท่านั้น มิฉะนั้นผู้โจมตีใช้บัญชีตัวเอง
        เข้าสู่ระบบสำเร็จเพื่อล้างตัวนับ แล้วเดาบัญชีอื่นต่อได้ (รีวิว 2026-10-02)
        """
        for bucket, key in self._buckets:
            if bucket is Bucket.ACCOUNT:
                await clear(self._session, bucket, key)


#: ข้อความเดียวสำหรับทุกเส้นทางที่ถูกปฏิเสธเพราะเรียกถี่เกิน
TOO_MANY_ATTEMPTS: Final[str] = "ลองมากเกินไป กรุณารอแล้วลองอีกครั้ง"


def refuse_if_throttled(guard: ThrottleGuard) -> None:
    """ปฏิเสธคำขอที่ติดหน่วงอยู่หรือโควตาหมด — **ที่เดียวสำหรับทุกเส้นทาง**

    **ปฏิเสธก่อนตรวจรหัสผ่าน** ฉะนั้นเจ้าของที่กรอกถูกก็ถูกปฏิเสธด้วย — ข้อจำกัดนี้
    ยังไม่ถูกปิด ดู **NC-14** ใน `requirements.md` ของ F-05

    โยน `AuthRejectedError` ไม่ใช่ `HTTPException` เพราะอยู่ **ข้างใน** `throttled()`
    และตัวนับต้องรอด (F-06 `plan.md` หัวข้อ 2)
    """
    if guard.blocked:
        raise AuthRejectedError(status.HTTP_429_TOO_MANY_REQUESTS, TOO_MANY_ATTEMPTS)


@asynccontextmanager
async def throttled(
    engine: AsyncEngine,
    buckets: Sequence[tuple[Bucket, str]],
    *,
    now: datetime,
) -> AsyncIterator[ThrottleGuard]:
    """เปิด transaction ของตัวนับ ล็อกทุกถัง แล้วบอกว่าคำขอนี้ถูกปฏิเสธหรือยัง

    **การปฏิเสธถูกจับไว้ข้างในแล้วโยนหลัง transaction จบ** จึงไม่ย้อนตัวนับทิ้ง
    (F-06 `plan.md` หัวข้อ 2.4 · เกณฑ์ V-63 ถึง V-69)
    """
    rejection: AuthRejectedError | None = None
    async with presented_session(engine, role=DatabaseRole.AUTH) as session:
        blocked = False
        for bucket, key in buckets:
            state = await claim(session, bucket, key, now=now)
            blocked = blocked or state.blocked_at(now)
        try:
            yield ThrottleGuard(session, tuple(buckets), blocked)
        except AuthRejectedError as caught:
            # ไม่โยนต่อที่นี่โดยเจตนา — ปล่อยให้ transaction จบปกติเพื่อให้ตัวนับรอด
            # ข้อผิดพลาดชนิดอื่นไม่ถูกจับ จึงยังย้อนตามเดิม (V-68)
            rejection = caught
    if rejection is not None:
        # โยนชนิดเดิมต่อ ไม่แปลงที่นี่ — ตัวแปลงอยู่ที่ `app.py` ที่เดียว
        raise rejection


async def spend_token(engine: AsyncEngine, user_id: UUID, bucket: Bucket) -> None:
    """ใช้โควตาหนึ่งหน่วยของถังนั้น — ปฏิเสธเมื่อหมด (F-07 RQ-11)

    **ต่างจาก `throttled()` ของ F-05 ตรงที่นับทุกคำขอ ไม่ใช่นับเฉพาะที่ล้มเหลว** —
    ที่นั่นเรานับการเดารหัสผ่านซึ่งผิดเท่านั้นที่น่าสงสัย ส่วนที่นี่ **ทุกครั้งที่เพิ่ม key
    คือหนึ่งคำขอที่ยิงตลาดและหนึ่งความลับที่ถูกเก็บ** การสำเร็จจึงมีต้นทุนพอ ๆ กับการล้มเหลว

    **ตัวนับอยู่ใน transaction ของตัวเอง** ด้วยเหตุผลเดียวกับ F-05/F-06:
    ถ้าร่วม transaction กับการกระทำแล้วการกระทำถูกย้อน การนับจะหายไปด้วย
    แล้วการคุมอัตราจะไม่ทำงานเลยเวลาที่คำขอถูกปฏิเสธ
    """
    now = datetime.now(UTC)
    async with user_session(engine, user_id, role=DatabaseRole.API) as session:
        state = await claim(session, bucket, key_of(str(user_id)), now=now)
        if state.tokens_left is not None and state.tokens_left <= 0:
            raise _too_many(bucket)
        await count_failure(session, bucket, key_of(str(user_id)))


def _too_many(bucket: Bucket) -> HTTPException:
    """ข้อความเดียวสำหรับทุกถัง — **ไม่บอกว่าเหลือเท่าไร**

    จำนวนที่เหลือบอกผู้โจมตีว่าควรรอนานแค่ไหนก่อนลองอีกครั้ง ซึ่งเป็นข้อมูลที่
    ไม่ได้ช่วยผู้ใช้จริงเลย (แบบแผนเดียวกับข้อความของ F-06)
    """
    return HTTPException(
        status.HTTP_429_TOO_MANY_REQUESTS,
        "ทำรายการถี่เกินไป กรุณารอสักครู่แล้วลองใหม่",
    )
