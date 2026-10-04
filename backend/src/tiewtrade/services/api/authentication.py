"""จุดเดียวที่ตอบว่า "คำขอนี้เป็นของผู้ใช้คนไหน" (F-05 plan.md ข้อ 2)

**ค่าเริ่มต้นคือปฏิเสธ** คำขอที่เส้นทางไม่อยู่ในรายการสาธารณะและไม่มี session ที่ใช้ได้
จะถูกปฏิเสธที่นี่ ไม่ใช่ที่แต่ละ endpoint — `security.md` หัวข้อ 2 สั่งให้ตรวจสิทธิ์
ที่จุดเดียว

**ไม่เชื่อสิ่งที่หน้าบ้านส่งมา** ตัวตนมาจากโทเคนในcookie ที่ฐานข้อมูลยืนยันว่ายังใช้ได้
เท่านั้น ไม่ใช่จากค่าใน header หรือใน body

**โทเคนกัน CSRF** ต้องมากับทุกคำขอที่ไม่ใช่ `GET`/`HEAD` และต้องตรงกับ cookie
เทียบแบบ constant-time (`security.md` หัวข้อ 1)

**เส้นทางที่ยังไม่ถูกจัดประเภทถูกปฏิเสธ ไม่ใช่ปล่อยผ่าน** (F-06 RQ-6, validation V-28)
และ **การยืนยันปัจจัยที่สองซ้ำตัดสินที่นี่ที่เดียว** ไม่ใช่ที่แต่ละ endpoint
— เพราะ `security.md` หัวข้อ 2 สั่งให้ตรวจสิทธิ์ที่จุดเดียว
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import Enum
from typing import Final
from uuid import UUID

from fastapi import HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.infra.auth import (
    hash_token,
    owner_of_presented,
    recovery_grants,
    renew,
    renewed_idle_deadline,
    totp,
)
from tiewtrade.infra.crypto import KeySource
from tiewtrade.infra.db import DatabaseRole
from tiewtrade.infra.db.session import presented_session, user_session
from tiewtrade.services.api.routing_policy import (
    accepts_recovery_grant,
    is_public,
    needs_reverification,
    renews_session,
    rule_for,
)
from tiewtrade.services.api.settings import (
    CSRF_COOKIE,
    CSRF_HEADER,
    SESSION_COOKIE,
    TOTP_HEADER,
    cookie_secure,
)

#: ข้อความเดียวสำหรับทุกกรณีที่ไม่มีสิทธิ์ — ไม่บอกว่าเพราะไม่มี session,
#: session หมดอายุ หรือโทเคนไม่มีในระบบ
NOT_AUTHENTICATED: Final[str] = "ต้องเข้าสู่ระบบก่อน"

#: ข้อความเดียวสำหรับทุกกรณีที่ปัจจัยที่สองไม่ผ่าน — ไม่บอกว่าเพราะไม่ได้เปิด TOTP,
#: รหัสผิด, รหัสถูกใช้แล้ว หรือไม่มีสิทธิ์กู้ (RQ-11 เจตนาเดียวกัน)
SECOND_FACTOR_REQUIRED: Final[str] = "ต้องยืนยันด้วยรหัสจากแอปยืนยันตัวตน"

#: ข้อความของเส้นทางที่ยังไม่ถูกจัดประเภท — **ความผิดของเรา ไม่ใช่ของผู้เรียก**
UNCLASSIFIED_ROUTE: Final[str] = "เส้นทางนี้ยังไม่ถูกจัดประเภท"

#: จำนวนไบต์ของโทเคนกัน CSRF
CSRF_BYTES: Final[int] = 32

_SAFE_METHODS: Final[frozenset[str]] = frozenset({"GET", "HEAD", "OPTIONS"})


class SecondFactor(Enum):
    """ปัจจัยที่สองที่คำขอนี้ใช้ผ่าน

    `RECOVERY_GRANT` **ยังไม่ถูกใช้ไป** — `usable()` แค่ตรวจ ส่วนการใช้เกิดใน
    transaction ของ endpoint เพื่อไม่ให้คำขอที่ล้มเหลวทีหลังเผาสิทธิ์ใบเดียว
    ที่ผู้ใช้มีไปฟรี ๆ
    """

    TOTP_CODE = "TOTP_CODE"
    RECOVERY_GRANT = "RECOVERY_GRANT"


@dataclass(frozen=True, slots=True)
class Authenticated:
    """ตัวตนของคำขอหนึ่ง — **ชนิดนี้เพิ่มช่องได้โดยผู้เรียกเดิมไม่ต้องแก้**

    F-06 เพิ่ม `second_factor` ซึ่ง **มีค่าเฉพาะคำขอที่เส้นทางบังคับให้ยืนยันซ้ำ**
    และผ่านแล้ว · ผู้เรียกเดิมไม่ต้องแก้เพราะมีค่าปริยาย
    """

    user_id: UUID
    token_hash: str
    absolute_expires_at: datetime
    second_factor: SecondFactor | None = None


def current_user(request: Request) -> Authenticated:
    """ตัวตนของคำขอ — ใช้ใน endpoint ที่ต้องรู้ว่าใครเรียก

    ถ้า middleware ปล่อยคำขอที่ไม่มีตัวตนมาถึง endpoint ที่เรียกฟังก์ชันนี้
    ให้ดังทันที เพราะหมายถึงรายการเส้นทางสาธารณะกับโค้ดไม่ตรงกัน
    """
    found = getattr(request.state, "authenticated", None)
    if not isinstance(found, Authenticated):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, NOT_AUTHENTICATED)
    return found


def new_csrf_token() -> str:
    """โทเคนกัน CSRF ใหม่"""
    return secrets.token_urlsafe(CSRF_BYTES)


def set_csrf_cookie(response: Response, token: str) -> None:
    """ตั้ง cookie ของโทเคนกัน CSRF

    **ไม่** `httpOnly` โดยเจตนา เพราะหน้าเว็บต้องอ่านไปใส่ header
    มีฟังก์ชันนี้เพื่อให้ธงของ cookie อยู่ที่เดียว — ธงที่เขียนสองที่คือธงที่
    วันหนึ่งจะต่างกันแล้วไม่มีใครรู้ว่าที่ไหนถูก
    """
    _set_cookie(response, CSRF_COOKIE, token, http_only=False)


def set_session_cookies(response: Response, *, token: str, csrf_token: str) -> None:
    """ตั้ง cookie ทั้งสองใบ — `httpOnly` บนใบของ session เพื่อให้สคริปต์อ่านไม่ได้"""
    _set_cookie(response, SESSION_COOKIE, token, http_only=True)
    set_csrf_cookie(response, csrf_token)


def _set_cookie(response: Response, name: str, value: str, *, http_only: bool) -> None:
    """ตั้ง cookie ด้วยธงชุดเดียวกันทุกใบ ยกเว้น `httpOnly` ที่ต่างกันตามหน้าที่

    `Secure` เปิดเป็นค่าเริ่มต้นและปิดได้เฉพาะตอนพัฒนา (`settings.cookie_secure`)
    `SameSite=strict` ทุกใบ เพราะไม่มีเส้นทางใดที่ต้องถูกเรียกข้ามเว็บ
    """
    response.set_cookie(
        name,
        value,
        httponly=http_only,
        secure=cookie_secure(),
        samesite="strict",
        path="/",
    )


def clear_session_cookies(response: Response) -> None:
    """ลบ cookie ทั้งสองใบ — **ไม่ใช่การเพิกถอน session** การเพิกถอนคือการลบแถว"""
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")


def ensure_csrf(request: Request) -> None:
    """คำขอที่เปลี่ยนสถานะต้องพาโทเคนกัน CSRF ที่ตรงกับ cookie มาด้วย"""
    if request.method in _SAFE_METHODS:
        return
    cookie = request.cookies.get(CSRF_COOKIE, "")
    header = request.headers.get(CSRF_HEADER, "")
    if not cookie or not header or not secrets.compare_digest(cookie, header):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "โทเคนกัน CSRF ไม่ถูกต้อง")


async def identify(engine: AsyncEngine, request: Request) -> Authenticated | None:
    """หาตัวตนจากโทเคนในcookie และต่ออายุถ้าเส้นทางนี้นับเป็นการใช้งาน

    ใช้บทบาท `api` ซึ่งเห็น session ได้เท่าที่โทเคนที่พามาเปิดให้ — ไม่ตั้งตัวแปร
    ก็อ่านศูนย์แถว จึงพลาดแบบปิดประตู
    """
    token = request.cookies.get(SESSION_COOKIE, "")
    if not token:
        return None

    token_hash = hash_token(token)
    now = datetime.now(UTC)
    async with presented_session(engine, token_hash=token_hash, role=DatabaseRole.API) as session:
        owner = await owner_of_presented(session)
        if owner is None:
            return None
        if renews_session(request.url.path):
            await renew(
                session,
                token_hash=token_hash,
                idle_expires_at=renewed_idle_deadline(now, owner.absolute_expires_at),
            )
    return Authenticated(
        user_id=owner.user_id,
        token_hash=token_hash,
        absolute_expires_at=owner.absolute_expires_at,
    )


async def second_factor_of(request: Request, who: Authenticated) -> SecondFactor:
    """ปัจจัยที่สองของคำขอนี้ — ดังเมื่อไม่ผ่าน

    **ไม่มีช่วงผ่อนผัน** (`requirements.md` Q-6) ฉะนั้นทุกคำขอที่เส้นทางบังคับ
    ต้องพารหัสของตัวเองมา · รหัสที่ผ่านแล้วถูกทำเครื่องหมายว่าใช้แล้วในคำสั่งเดียวกัน
    ฉะนั้นผู้ใช้ที่ทำสองรายการติดกันต้องรอรหัสของช่วงใหม่ — ต้นทุนที่เจ้าของรับไว้

    **ข้อความเมื่อไม่ผ่านเหมือนกันทุกกรณี** ไม่บอกว่าเพราะยังไม่เปิด TOTP, รหัสผิด,
    รหัสถูกใช้แล้ว หรือไม่มีสิทธิ์กู้
    """
    presented = request.headers.get(TOTP_HEADER, "")
    engine = _auth_engine(request)
    keys = _totp_keys(request)
    now = datetime.now(UTC)

    async with user_session(engine, who.user_id, role=DatabaseRole.AUTH) as session:
        if presented and await totp.verify(session, keys, presented=presented, now=now):
            return SecondFactor.TOTP_CODE
        if accepts_recovery_grant(request.url.path) and await recovery_grants.usable(
            session, session_token_hash=who.token_hash
        ):
            return SecondFactor.RECOVERY_GRANT

    raise HTTPException(status.HTTP_403_FORBIDDEN, SECOND_FACTOR_REQUIRED)


async def authenticate_request(engine: AsyncEngine, request: Request) -> None:
    """ตรวจ CSRF, ตัวตน และปัจจัยที่สอง แล้วติดผลไว้กับคำขอ — ที่เดียวที่ตัดสินสิทธิ์

    เส้นทางสาธารณะก็ยังตรวจ CSRF เพราะการเข้าสู่ระบบแบบถูกหลอกให้กด (login CSRF)
    ก็เป็นการเปลี่ยนสถานะของเบราว์เซอร์ผู้ใช้

    **เส้นทางที่ยังไม่ถูกจัดประเภทถูกปฏิเสธก่อนทุกอย่าง** (RQ-6) — เป็นชั้นที่สอง
    ของเทสต์ที่เดินทุกเส้นทาง เพราะเทสต์เห็นเฉพาะเส้นทางที่แอปประกาศตอนเทสต์รัน
    ส่วนคำขอจริงมาที่ path อะไรก็ได้
    """
    if rule_for(request.url.path) is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, UNCLASSIFIED_ROUTE)

    ensure_csrf(request)
    found = await identify(engine, request)
    request.state.authenticated = found
    if found is None:
        if not is_public(request.url.path):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, NOT_AUTHENTICATED)
        return

    if needs_reverification(request.url.path):
        request.state.authenticated = replace(
            found, second_factor=await second_factor_of(request, found)
        )


def _auth_engine(request: Request) -> AsyncEngine:
    """engine ของบทบาท `auth` — ตารางของปัจจัยที่สองแตะได้ด้วยบทบาทนี้เท่านั้น"""
    engine = getattr(request.app.state, "auth_engine", None)
    if not isinstance(engine, AsyncEngine):  # pragma: no cover - ตั้งค่าแอปผิด
        raise RuntimeError("แอปยังไม่ได้ตั้ง engine ของบทบาท auth")
    return engine


def _totp_keys(request: Request) -> KeySource:
    """กุญแจของ TOTP ที่ lifespan อ่านมาตอนเปิดแอป

    อ่านตอนเปิดแอปเพื่อให้ **กุญแจไม่ครบ = กระบวนการไม่เริ่ม** ไม่ใช่ล้มตอนมีผู้ใช้
    คนแรกมาเปิด TOTP (validation V-10)
    """
    keys = getattr(request.app.state, "totp_keys", None)
    if not isinstance(keys, KeySource):  # pragma: no cover - ตั้งค่าแอปผิด
        raise RuntimeError("แอปยังไม่ได้อ่านกุญแจของ TOTP")
    return keys
