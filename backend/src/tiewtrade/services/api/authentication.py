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
from dataclasses import replace
from datetime import UTC, datetime
from typing import Final
from uuid import UUID

from fastapi import HTTPException, Request, Response, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.core.money import MoneyError
from tiewtrade.core.orders import TradingMode
from tiewtrade.core.risk_limits import RiskInputError
from tiewtrade.infra.auth import (
    Bucket,
    hash_token,
    key_of,
    locked_credential,
    owner_of_presented,
    recovery_grants,
    renew,
    renewed_idle_deadline,
    totp,
)
from tiewtrade.infra.auth.sessions import SessionOwner
from tiewtrade.infra.db import DatabaseRole, InfraError
from tiewtrade.infra.db.session import PresentedSession, presented_session, user_session
from tiewtrade.infra.risk_limits.records import RiskConflictError, RiskSubmission
from tiewtrade.infra.risk_limits.requests import (
    authorization_for,
    authorize_increase,
    receipt_by_key,
)
from tiewtrade.services.api.request_identity import NOT_AUTHENTICATED
from tiewtrade.services.api.request_identity import Authenticated as Authenticated
from tiewtrade.services.api.request_identity import SecondFactor as SecondFactor
from tiewtrade.services.api.request_identity import current_user as current_user
from tiewtrade.services.api.resources import client_key, engine_for, totp_keys
from tiewtrade.services.api.risk_limit_models import RiskLimitMutation, risk_submission
from tiewtrade.services.api.routing_policy import (
    accepts_recovery_grant,
    classify,
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
    price_origins,
)
from tiewtrade.services.api.throttling import AuthRejectedError, refuse_if_throttled, throttled

#: ข้อความเดียวสำหรับทุกกรณีที่ไม่มีสิทธิ์ — ไม่บอกว่าเพราะไม่มี session,
#: session หมดอายุ หรือโทเคนไม่มีในระบบ
#: ข้อความเดียวสำหรับทุกกรณีที่ปัจจัยที่สองไม่ผ่าน — ไม่บอกว่าเพราะไม่ได้เปิด TOTP,
#: รหัสผิด, รหัสถูกใช้แล้ว หรือไม่มีสิทธิ์กู้ (RQ-11 เจตนาเดียวกัน)
SECOND_FACTOR_REQUIRED: Final[str] = "ต้องยืนยันด้วยรหัสจากแอปยืนยันตัวตน"

#: ข้อความของรหัสที่ถูกต้องแต่ถูกใช้ไปแล้ว — **ต้องต่างจากข้อความของรหัสผิด**
#:
#: เป็นต้นทุนของการไม่มีช่วงผ่อนผัน (Q-6) ที่เจ้าของรับไว้: ทำสองรายการติดกัน
#: ต้องรอรหัสของช่วงใหม่ · ถ้าตอบเหมือนรหัสผิด ผู้ใช้จะพิมพ์ซ้ำจนโควตาหมด
CODE_ALREADY_USED: Final[str] = "รหัสนี้ถูกใช้ไปแล้ว — รอรหัสชุดใหม่จากแอปแล้วลองอีกครั้ง"

#: ข้อความของเส้นทางที่ยังไม่ถูกจัดประเภท — **ความผิดของเรา ไม่ใช่ของผู้เรียก**
UNCLASSIFIED_ROUTE: Final[str] = "เส้นทางนี้ยังไม่ถูกจัดประเภท"

#: จำนวนไบต์ของโทเคนกัน CSRF
CSRF_BYTES: Final[int] = 32

_SAFE_METHODS: Final[frozenset[str]] = frozenset({"GET", "HEAD", "OPTIONS"})


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
        owner = await presented_owner(session)
        if owner is None:
            return None
        route_key: tuple[str, str] | None = getattr(request.state, "route_key", None)
        if route_key is not None and renews_session(*route_key):
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


async def second_factor_of(
    request: Request, who: Authenticated, *, risk_action: RiskSubmission | None = None
) -> SecondFactor:
    """ปัจจัยที่สองของคำขอนี้ — ดังเมื่อไม่ผ่าน

    **ไม่มีช่วงผ่อนผัน** (`requirements.md` Q-6) ฉะนั้นทุกคำขอที่เส้นทางบังคับ
    ต้องพารหัสของตัวเองมา · รหัสที่ผ่านแล้วถูกทำเครื่องหมายว่าใช้แล้วในคำสั่งเดียวกัน
    ฉะนั้นผู้ใช้ที่ทำสองรายการติดกันต้องรอรหัสของช่วงใหม่ — ต้นทุนที่เจ้าของรับไว้

    **ข้อความเมื่อไม่ผ่านเหมือนกันทุกกรณี** ไม่บอกว่าเพราะยังไม่เปิด TOTP, รหัสผิด,
    รหัสถูกใช้แล้ว หรือไม่มีสิทธิ์กู้
    """
    presented = request.headers.get(TOTP_HEADER, "")
    engine = engine_for(request, DatabaseRole.AUTH)
    keys = totp_keys(request)
    now = datetime.now(UTC)

    async with throttled(
        engine,
        [(Bucket.TOTP_ACCOUNT, key_of(str(who.user_id))), (Bucket.TOTP_IP, client_key(request))],
        now=now,
    ) as guard:
        async with user_session(engine, who.user_id, role=DatabaseRole.AUTH) as session:
            route_key: tuple[str, str] = request.state.route_key
            grant_usable = accepts_recovery_grant(*route_key) and await recovery_grants.usable(
                session, session_token_hash=who.token_hash
            )
            # สิทธิ์กู้ไม่ใช่การเดารหัส TOTP จึงยังใช้ได้เมื่อถัง TOTP หมด
            if grant_usable and (not presented or guard.blocked):
                return SecondFactor.RECOVERY_GRANT
            if risk_action is not None:
                await locked_credential(session, who.user_id)
                # A concurrent request may have committed its receipt after the
                # API preflight. Recheck under the existing F-06 auth lock order.
                if await authorization_for(session, risk_action) is not None:
                    return SecondFactor.TOTP_CODE
                refuse_if_throttled(guard)
            else:
                refuse_if_throttled(guard)
                await locked_credential(session, who.user_id)
            if presented:
                outcome = await totp.verify(session, keys, presented=presented, now=now)
                if outcome is totp.CodeOutcome.ACCEPTED:
                    if risk_action is not None:
                        await authorize_increase(session, risk_action)
                    return SecondFactor.TOTP_CODE
                if outcome is totp.CodeOutcome.ALREADY_USED:
                    # **บอกให้รอรหัสใหม่** มิฉะนั้นผู้ใช้จะคิดว่าเครื่องตัวเองเพี้ยน
                    # แล้วพิมพ์รหัสเดิมซ้ำจนโควตาหมด (validation V-61.2)
                    raise HTTPException(status.HTTP_403_FORBIDDEN, CODE_ALREADY_USED)
            if grant_usable:
                return SecondFactor.RECOVERY_GRANT
        await guard.count_attempt()
        raise AuthRejectedError(status.HTTP_403_FORBIDDEN, SECOND_FACTOR_REQUIRED)


def classified_route(request: Request) -> tuple[str, str] | None:
    """(เมธอด, แม่แบบของ path) ของคำขอนี้ — `None` เมื่อไม่มีแถวไหนรับ

    ถามตารางกฎโดยตรง ไม่ใช่ถาม framework ว่าเส้นทางไหนจับคู่ได้ (เหตุผลอยู่ใน
    `routing_policy.py`) · ทิศทางตรงข้ามถูกตรวจด้วยเทสต์ที่เดินทุกเส้นทางของแอป
    """
    return classify(request.method, request.url.path)


async def authenticate_request(engine: AsyncEngine, request: Request) -> None:
    """ตรวจ CSRF, ตัวตน และปัจจัยที่สอง แล้วติดผลไว้กับคำขอ — ที่เดียวที่ตัดสินสิทธิ์

    เส้นทางสาธารณะก็ยังตรวจ CSRF เพราะการเข้าสู่ระบบแบบถูกหลอกให้กด (login CSRF)
    ก็เป็นการเปลี่ยนสถานะของเบราว์เซอร์ผู้ใช้

    **เส้นทางที่ยังไม่ถูกจัดประเภทถูกปฏิเสธก่อนทุกอย่าง** (RQ-6) — เป็นชั้นที่สอง
    ของเทสต์ที่เดินทุกเส้นทาง เพราะเทสต์เห็นเฉพาะเส้นทางที่แอปประกาศตอนเทสต์รัน
    ส่วนคำขอจริงมาที่ path อะไรก็ได้
    """
    classified = classified_route(request)
    if classified is None or rule_for(*classified) is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, UNCLASSIFIED_ROUTE)
    request.state.route_key = classified

    ensure_csrf(request)
    rule = rule_for(*classified)
    origin = request.headers.get("origin")
    if (
        rule is not None
        and rule.checks_browser_origin
        and origin is not None
        and origin not in price_origins()
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "CSRF_ORIGIN_REJECTED")
    found = await identify(engine, request)
    request.state.authenticated = found
    if found is None:
        if not is_public(*classified):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, NOT_AUTHENTICATED)
        return

    if classified in {
        ("POST", "/paper/risk-limit/increase"),
        ("POST", "/live/risk-limit/increase"),
    }:
        try:
            raw = await request.body()
            if len(raw) > 4096:
                raise HTTPException(422, "RISK_INPUT_INVALID")
            body = RiskLimitMutation.model_validate_json(raw)
            value = risk_submission(
                owner=found.user_id,
                mode=TradingMode.PAPER if classified[1].startswith("/paper/") else TradingMode.LIVE,
                key=UUID(request.headers.get("Idempotency-Key", "")),
                body=body,
                increase=True,
            )
            async with user_session(engine, found.user_id) as session:
                prior = await receipt_by_key(session, value.scope.mode, value.key)
            if prior is not None:
                if prior.submission != value:
                    raise RiskConflictError("risk replay payload mismatch")
                factor = SecondFactor.TOTP_CODE
            else:
                factor = await second_factor_of(request, found, risk_action=value)
            request.state.authenticated = replace(found, second_factor=factor)
        except RiskConflictError as error:
            raise HTTPException(409, error.code) from None
        except (ValidationError, MoneyError, RiskInputError, ValueError):
            raise HTTPException(422, "RISK_INPUT_INVALID") from None
        except InfraError:
            raise HTTPException(503, "RISK_SOURCE_UNAVAILABLE") from None
    elif needs_reverification(*classified):
        request.state.authenticated = replace(
            found, second_factor=await second_factor_of(request, found)
        )


async def presented_owner(session: PresentedSession) -> SessionOwner | None:
    """Shared HTTP/WS identity lookup; never extends a session by itself."""
    return await owner_of_presented(session)
