"""เส้นทางยืนยันตัวตน (F-05)

**ทุกอย่างที่แตะข้อมูลเข้าสู่ระบบอยู่บนบทบาท `tiewtrade_auth`** ส่วนเส้นทางที่อ่าน
ตัวตนของคำขออยู่บนบทบาท `api` ซึ่งแตะ `user_credentials` ไม่ได้เลย

**ข้อความตอบกลับตอนเข้าสู่ระบบล้มเหลวเหมือนกันทุกกรณี** และกรณีที่ไม่พบอีเมล
ก็ยังใช้เวลาแฮชเท่ากัน มิฉะนั้นเวลาตอบจะบอกว่าบัญชีมีอยู่ (RQ-8)
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Final
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from tiewtrade.core.passwords import PasswordPolicyError, acceptable_new_password, normalised
from tiewtrade.infra.audit import (
    AllSessionsEndedDetails,
    AuditAction,
    PasswordChangedDetails,
    SessionDetails,
    record_own_action,
)
from tiewtrade.infra.auth import (
    Bucket,
    create_credential,
    deadlines_for_new_session,
    end_all,
    end_one,
    end_others,
    hash_password,
    is_blocked,
    issue,
    key_of,
    locked_credential,
    new_token,
    owner_of_email,
    password_matches,
    replace_password_hash,
    spend_matching_time,
    totp,
)
from tiewtrade.infra.auth.challenges import end_all as end_all_challenges
from tiewtrade.infra.auth.challenges import issue as issue_challenge
from tiewtrade.infra.db import DatabaseRole
from tiewtrade.infra.db.errors import DuplicateValueError
from tiewtrade.infra.db.session import UserSession, presented_session, user_session
from tiewtrade.infra.users import create_user_in
from tiewtrade.services.api.authentication import (
    Authenticated,
    clear_session_cookies,
    current_user,
    new_csrf_token,
    set_csrf_cookie,
    set_session_cookies,
)
from tiewtrade.services.api.resources import client_key, engine_for
from tiewtrade.services.api.settings import signup_open
from tiewtrade.services.api.throttling import AuthRejectedError, refuse_if_throttled, throttled
from tiewtrade.services.api.totp_routes import set_challenge_cookie

router = APIRouter(prefix="/auth", tags=["auth"])

#: ข้อความเดียวสำหรับทั้ง "ไม่มีบัญชีนี้" และ "รหัสผ่านผิด" (RQ-8)
LOGIN_FAILED: Final[str] = "อีเมลหรือรหัสผ่านไม่ถูกต้อง"

#: ความยาวอีเมลสูงสุดตามขอบที่ใช้ได้จริงของ RFC 5321
EMAIL_MAX_LENGTH: Final[int] = 254


class Me(BaseModel):
    """ตัวตนของคำขอ พร้อมสถานะปัจจัยที่สอง (F-06 RQ-12)"""

    user_id: UUID
    totp_enabled: bool


class SignInStarted(BaseModel):
    """ผลของขั้นแรกของการเข้าสู่ระบบ (F-06)

    **รูปร่างเดียวกันทั้งสองกรณี** ต่างกันแค่ค่าในช่อง และ cookie ที่แนบกลับไป
    ฉะนั้นคนที่ยังไม่ผ่านรหัสผ่านแยกสองกรณีไม่ได้ — เขาได้ `LOGIN_FAILED` เหมือนเดิม
    **ก่อน** ที่โค้ดจะแตะข้อมูล TOTP เลย (RQ-11)
    """

    user_id: UUID
    second_step_required: bool


class Credentials(BaseModel):
    """อีเมลกับรหัสผ่านที่ผู้ใช้กรอก"""

    email: str = Field(min_length=3, max_length=EMAIL_MAX_LENGTH)
    password: str = Field(min_length=1, max_length=4096)


class PasswordChange(BaseModel):
    """การเปลี่ยนรหัสผ่าน — ต้องยืนยันค่าปัจจุบัน (Q-5)"""

    current_password: str = Field(min_length=1, max_length=4096)
    new_password: str = Field(min_length=1, max_length=4096)


class Identity(BaseModel):
    """ตัวตนของคำขอ — **ไม่คืนอีเมลหรืออะไรที่ไม่จำเป็น** (RQ-10)"""

    user_id: UUID


class CsrfToken(BaseModel):
    """โทเคนกัน CSRF ที่หน้าเว็บต้องส่งกลับมาใน header"""

    csrf_token: str


class SessionsEnded(BaseModel):
    """จำนวน session ที่ถูกเพิกถอน"""

    ended: int


def normalise_email(raw: str) -> str:
    """อีเมลในรูปที่เก็บ — ตัดช่องว่างและทำเป็นตัวพิมพ์เล็ก

    **การไม่แยกตัวพิมพ์เป็นนโยบายที่เราเลือก ไม่ใช่สิ่งที่มาตรฐานกำหนด**
    (RFC 5321 §2.4 ยอมให้ส่วนก่อน `@` แยกตัวพิมพ์ได้) เลือกแบบนี้เพราะผู้ให้บริการ
    อีเมลในทางปฏิบัติไม่แยก และการแยกจะทำให้ผู้ใช้สร้างบัญชีซ้ำโดยไม่รู้ตัว
    """
    candidate = raw.strip().lower()
    if "@" not in candidate or len(candidate) > EMAIL_MAX_LENGTH:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "อีเมลไม่ถูกรูปแบบ")
    return candidate


def _accepted_new_password(raw: str) -> str:
    """รหัสผ่านใหม่ที่ผ่านกฎครบ — ความยาวและรายการที่ห้าม

    **ใช้เฉพาะตอนรับรหัสผ่านใหม่** การตรวจตอนเข้าสู่ระบบจะล็อกเจ้าของออกจากบัญชี
    เมื่อรายการที่ห้ามอัปเดตแล้วรหัสผ่านเดิมติดอยู่ในนั้น (plan.md ข้อ 5)
    """
    try:
        candidate = acceptable_new_password(raw)
    except PasswordPolicyError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from None
    if is_blocked(candidate):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "รหัสผ่านนี้อยู่ในรายการที่พบบ่อยหรือเคยรั่ว กรุณาใช้ค่าอื่น",
        )
    return candidate


async def _start_session(session: UserSession, user_id: UUID, now: datetime) -> str:
    """ออก session ใหม่และลงบันทึก — คืน **โทเคนจริง** ที่ส่งให้เบราว์เซอร์ครั้งเดียว"""
    token, token_hash = new_token()
    deadlines = deadlines_for_new_session(now)
    await issue(
        session,
        token_hash=token_hash,
        idle_expires_at=deadlines.idle_expires_at,
        absolute_expires_at=deadlines.absolute_expires_at,
    )
    await record_own_action(session, user_id, AuditAction.SESSION_STARTED, SessionDetails())
    return token


@router.get("/csrf")
async def read_csrf_token(response: Response) -> CsrfToken:
    """ออกโทเคนกัน CSRF ให้หน้าเว็บก่อนส่งคำขอที่เปลี่ยนสถานะ"""
    token = new_csrf_token()
    set_csrf_cookie(response, token)
    return CsrfToken(csrf_token=token)


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(request: Request, response: Response, body: Credentials) -> Identity:
    """สมัครบัญชีใหม่ — ผู้ใช้ ข้อมูลเข้าสู่ระบบ session และบันทึก **ในก้อนเดียว**"""
    if not signup_open():
        raise HTTPException(status.HTTP_403_FORBIDDEN, "ยังไม่เปิดให้สมัครในขณะนี้")

    email = normalise_email(body.email)
    password = _accepted_new_password(body.password)
    engine = engine_for(request, DatabaseRole.AUTH)
    now = datetime.now(UTC)

    async with throttled(engine, [(Bucket.SIGNUP_IP, client_key(request))], now=now) as guard:
        refuse_if_throttled(guard)
        user_id = uuid4()
        try:
            async with user_session(engine, user_id, role=DatabaseRole.AUTH) as session:
                await create_user_in(session, user_id)
                await create_credential(
                    session, user_id, email=email, password_hash=hash_password(password)
                )
                token = await _start_session(session, user_id, now)
        except DuplicateValueError:
            await guard.count_attempt()
            raise AuthRejectedError(status.HTTP_409_CONFLICT, "อีเมลนี้มีบัญชีอยู่แล้ว") from None
        await guard.count_attempt()

    set_session_cookies(response, token=token, csrf_token=new_csrf_token())
    return Identity(user_id=user_id)


@router.post("/login")
async def login(request: Request, response: Response, body: Credentials) -> SignInStarted:
    """เข้าสู่ระบบ — ลำดับการล็อกแถวข้อมูลเข้าสู่ระบบมีสามขั้นตามที่ plan ข้อ 1.6 กำหนด"""
    email = normalise_email(body.email)
    password = normalised(body.password)
    engine = engine_for(request, DatabaseRole.AUTH)
    now = datetime.now(UTC)
    account_key = key_of(email)

    async with throttled(
        engine,
        [(Bucket.ACCOUNT, account_key), (Bucket.IP, client_key(request))],
        now=now,
    ) as guard:
        refuse_if_throttled(guard)

        async with presented_session(engine, email=email, role=DatabaseRole.AUTH) as finder:
            # ขั้นที่หนึ่ง: หาเจ้าของจากอีเมล — ยังไม่ใช่การยืนยันตัวตน
            user_id = await owner_of_email(finder, email)
            if user_id is None:
                # ใช้เวลาเท่าการตรวจจริง มิฉะนั้นเวลาตอบบอกว่าบัญชีมีอยู่ (RQ-8)
                spend_matching_time()
                await guard.count_attempt()
                raise AuthRejectedError(status.HTTP_401_UNAUTHORIZED, LOGIN_FAILED)

            # ขั้นที่สอง: ตั้งผู้ใช้ปัจจุบัน แล้วขั้นที่สาม: ล็อกและอ่านแฮชใหม่
            session = await finder.assume_user(user_id)
            stored = await locked_credential(session, user_id)
            if stored is None or not password_matches(stored.password_hash, password):
                await guard.count_attempt()
                raise AuthRejectedError(status.HTTP_401_UNAUTHORIZED, LOGIN_FAILED)

            # ผู้ใช้ที่เปิด TOTP แล้ว **ไม่ได้ session จากรหัสผ่านอย่างเดียว** (RQ-5)
            # — ได้ challenge ที่ใช้เรียกเส้นทางอื่นไม่ได้เลย
            if await totp.is_enabled(session):
                waiting = await issue_challenge(
                    session, credential_updated_at=stored.updated_at, now=now
                )
                await guard.forget_account()
                set_challenge_cookie(response, waiting.token)
                return SignInStarted(user_id=user_id, second_step_required=True)

            token = await _start_session(session, user_id, now)

        await guard.forget_account()

    set_session_cookies(response, token=token, csrf_token=new_csrf_token())
    return SignInStarted(user_id=user_id, second_step_required=False)


async def _end_sessions(
    request: Request,
    response: Response,
    who: Authenticated,
    *,
    everywhere: bool,
) -> SessionsEnded:
    """เพิกถอน session แล้วลงบันทึก — โครงเดียวกันทั้งออกเครื่องเดียวและออกทุกเครื่อง

    **รูปของคำสั่งลบต่างกันโดยเจตนา** และอยู่ใน `infra.auth.sessions` ที่เดียว:
    ออกเครื่องเดียวอ้างคอลัมน์ได้ ส่วนออกทุกเครื่องต้องไม่อ้างคอลัมน์ มิฉะนั้น
    PostgreSQL จะนำ SELECT policy มาใช้ด้วยแล้วลบได้แถวเดียว (RQ-19)
    """
    engine = engine_for(request, DatabaseRole.API)
    async with presented_session(
        engine, token_hash=who.token_hash, role=DatabaseRole.API
    ) as session:
        ended = (
            await end_all(session)
            if everywhere
            else await end_one(session, token_hash=who.token_hash)
        )
        owned = await session.assume_user(who.user_id)
        await record_own_action(
            owned,
            who.user_id,
            AuditAction.ALL_SESSIONS_ENDED if everywhere else AuditAction.SESSION_ENDED,
            AllSessionsEndedDetails(ended=ended) if everywhere else SessionDetails(),
        )
    clear_session_cookies(response)
    return SessionsEnded(ended=ended)


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    request: Request,
    response: Response,
    who: Annotated[Authenticated, Depends(current_user)],
) -> SessionsEnded:
    """ออกจากระบบเครื่องนี้ — **ลบแถว** ไม่ใช่แค่ลบ cookie (RQ-15)"""
    return await _end_sessions(request, response, who, everywhere=False)


@router.post("/logout-all", status_code=status.HTTP_200_OK)
async def logout_everywhere(
    request: Request,
    response: Response,
    who: Annotated[Authenticated, Depends(current_user)],
) -> SessionsEnded:
    """ออกจากระบบทุกเครื่องของผู้ใช้นี้"""
    return await _end_sessions(request, response, who, everywhere=True)


@router.post("/password", status_code=status.HTTP_200_OK)
async def change_password(
    request: Request,
    body: PasswordChange,
    who: Annotated[Authenticated, Depends(current_user)],
) -> SessionsEnded:
    """เปลี่ยนรหัสผ่าน — ทั้งก้อนสำเร็จหรือล้มเหลวด้วยกัน (RQ-22)

    ล็อกแถวข้อมูลเข้าสู่ระบบก่อนตรวจค่าปัจจุบัน จึงไม่มีช่องที่การเข้าสู่ระบบด้วย
    รหัสผ่านเก่าซึ่งกำลังดำเนินอยู่พร้อมกันจะได้ session ที่รอดหลังการเพิกถอนเสร็จ
    """
    new_password = _accepted_new_password(body.new_password)
    current = normalised(body.current_password)
    engine = engine_for(request, DatabaseRole.AUTH)
    account = who.user_id

    async with throttled(
        engine, [(Bucket.ACCOUNT, key_of(str(account)))], now=datetime.now(UTC)
    ) as guard:
        refuse_if_throttled(guard)
        async with user_session(engine, account, role=DatabaseRole.AUTH) as session:
            stored = await locked_credential(session, account)
            if stored is None or not password_matches(stored.password_hash, current):
                await guard.count_attempt()
                raise AuthRejectedError(status.HTTP_401_UNAUTHORIZED, "รหัสผ่านปัจจุบันไม่ถูกต้อง")

            await replace_password_hash(session, account, password_hash=hash_password(new_password))
            # **ลบ challenge ทุกใบด้วย** มิฉะนั้นใบที่ออกด้วยรหัสผ่านเก่าจะยังผ่าน
            # ปัจจัยที่สองแล้วได้ session ใหม่ทีหลัง ซึ่งขัด RQ-22 (F-06 plan.md 1.4)
            await end_all_challenges(session)
            ended = await end_others(session, keep_token_hash=who.token_hash)
            await record_own_action(
                session, account, AuditAction.PASSWORD_CHANGED, PasswordChangedDetails()
            )
        await guard.forget_account()

    return SessionsEnded(ended=ended)


@router.get("/me")
async def read_me(request: Request, who: Annotated[Authenticated, Depends(current_user)]) -> Me:
    """ตัวตนของคำขอนี้ และสถานะปัจจัยที่สอง

    **`totp_enabled` คือคำตอบที่ F-24 ใช้** (RQ-12) — secret ที่ยังไม่ยืนยัน
    นับว่ายังไม่เปิด เพราะมันไม่มีผลกับการยืนยันตัวตนเลย

    **ไม่ต่ออายุ session** เพราะหน้าเว็บเรียกเส้นทางนี้เป็นรอบ ๆ (Q-2 ของ F-05)
    """
    engine = engine_for(request, DatabaseRole.AUTH)
    async with user_session(engine, who.user_id, role=DatabaseRole.AUTH) as session:
        enabled = await totp.is_enabled(session)
    return Me(user_id=who.user_id, totp_enabled=enabled)
