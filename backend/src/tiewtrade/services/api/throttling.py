"""การคุมอัตราการเรียกของเส้นทางยืนยันตัวตน (F-05 plan.md ข้อ 4)

**ล็อกถังไว้ตลอดช่วงที่ตรวจรหัสผ่าน** คำขอที่ยิงพร้อมกันบนบัญชีเดียวกันจึงเข้าคิว
ไม่ใช่วิ่งขนาน — ถ้าปล่อยล็อกก่อนตรวจ การยิง 20 คำขอพร้อมกันจะผ่านด่านทั้งหมด

**ตัวนับอยู่ใน transaction ของตัวเอง** จึงถูกบันทึกแม้คำขอนั้นถูกปฏิเสธ
ถ้าร่วม transaction กับการตรวจรหัสผ่านแล้วถูกยกเลิก การเดารหัสผ่านจะไม่ถูกนับเลย
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.infra.auth import Bucket, claim, clear, count_failure
from tiewtrade.infra.db import DatabaseRole
from tiewtrade.infra.db.session import PresentedSession, presented_session


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


@asynccontextmanager
async def throttled(
    engine: AsyncEngine,
    buckets: Sequence[tuple[Bucket, str]],
    *,
    now: datetime,
) -> AsyncIterator[ThrottleGuard]:
    """เปิด transaction ของตัวนับ ล็อกทุกถัง แล้วบอกว่าคำขอนี้ถูกปฏิเสธหรือยัง"""
    async with presented_session(engine, role=DatabaseRole.AUTH) as session:
        blocked = False
        for bucket, key in buckets:
            state = await claim(session, bucket, key, now=now)
            blocked = blocked or state.blocked_at(now)
        yield ThrottleGuard(session, tuple(buckets), blocked)
