"""เส้นทางของปัจจัยที่สอง (F-06)

**ทุกเส้นทางที่นี่อยู่บนบทบาท `tiewtrade_auth`** เพราะตารางของปัจจัยยืนยันตัวตน
แตะได้ด้วยบทบาทนี้เท่านั้น

**การตัดสินว่าคำขอผ่านปัจจัยที่สองหรือไม่ไม่ได้อยู่ที่นี่** — middleware ตัดสินที่
จุดเดียวตามตารางจัดประเภทใน `routing_policy.py` (`security.md` หัวข้อ 2)
ที่นี่เพียง **ใช้** ผลนั้น และใช้สิทธิ์กู้บัญชีใน transaction เดียวกับการกระทำ

**การเปิดครั้งแรกและการเปลี่ยนเครื่องใช้กลไกเดียวกัน** คือเขียน `user_totp_pending`
แล้วสลับเป็นตัวจริงตอนยืนยัน · ปัจจัยเดิมทำงานปกติตลอดช่วงที่ยังไม่ยืนยัน
ฉะนั้นทิ้งกลางทางได้โดยไม่เสียอะไร (`plan.md` หัวข้อ 1.6)
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Final
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from tiewtrade.core.passwords import normalised
from tiewtrade.infra.audit import (
    AllSessionsEndedDetails,
    AuditAction,
    RecoveryCodesIssuedDetails,
    RecoveryCodeUsedDetails,
    SessionDetails,
    TotpChangeDetails,
    record_own_action,
)
from tiewtrade.infra.auth import (
    Bucket,
    challenges,
    deadlines_for_new_session,
    email_of,
    end_others,
    issue,
    key_of,
    locked_credential,
    new_token,
    password_matches,
    recovery_codes,
    recovery_grants,
    totp,
)
from tiewtrade.infra.db import DatabaseRole
from tiewtrade.infra.db.session import UserSession, presented_session, user_session
from tiewtrade.services.api.authentication import (
    Authenticated,
    SecondFactor,
    current_user,
    new_csrf_token,
    set_session_cookies,
)
from tiewtrade.services.api.resources import client_key, engine_for, totp_keys
from tiewtrade.services.api.settings import CHALLENGE_COOKIE, cookie_secure
from tiewtrade.services.api.throttling import AuthRejectedError, refuse_if_throttled, throttled

router = APIRouter(prefix="/auth/totp", tags=["auth"])

#: ข้อความเดียวสำหรับทุกกรณีที่ขั้นที่สองไม่ผ่าน — ไม่บอกว่ารหัสผิดหรือหมดอายุ
SECOND_STEP_FAILED: Final[str] = "รหัสยืนยันไม่ถูกต้อง"

#: ข้อความเดียวสำหรับรหัสผ่านที่ไม่ตรง
PASSWORD_FAILED: Final[str] = "รหัสผ่านไม่ถูกต้อง"


class CurrentPassword(BaseModel):
    """รหัสผ่านปัจจุบัน — ทุกเส้นทางที่เปลี่ยนปัจจัยที่สองต้องการค่านี้ (Q-4)"""

    password: str = Field(min_length=1, max_length=4096)


class Confirmation(BaseModel):
    """รหัสจาก secret ที่เพิ่งตั้งค่า"""

    code: str = Field(min_length=1, max_length=16)


class SecondStep(BaseModel):
    """ขั้นที่สองของการเข้าสู่ระบบ — รหัสจากแอป **หรือ** รหัสสำรองหนึ่งใบ"""

    code: str | None = Field(default=None, max_length=16)
    recovery_code: str | None = Field(default=None, max_length=32)


class Enrollment(BaseModel):
    """ของที่ผู้ใช้ต้องเอาไปใส่แอป — **ส่งครั้งเดียวต่อการเรียกหนึ่งครั้ง**"""

    otpauth_uri: str


class Enabled(BaseModel):
    """ผลของการเปิดใช้ — รหัสสำรองชุดใหม่ และจำนวน session ที่ถูกเพิกถอน"""

    recovery_codes: list[str]
    ended: int


class CodesIssued(BaseModel):
    """ชุดรหัสสำรองใหม่ — **แสดงครั้งเดียว ไม่มีทางอ่านกลับ**"""

    recovery_codes: list[str]


class Disabled(BaseModel):
    """ผลของการปิด TOTP"""

    ended: int


class SignedIn(BaseModel):
    """ผลของขั้นที่สอง — รหัสผู้ใช้ และจำนวนรหัสสำรองที่เหลือถ้าใช้ไปใบหนึ่ง"""

    user_id: UUID
    recovery_codes_left: int | None = None


async def live_trading_enabled(session: UserSession) -> bool:
    """บัญชีนี้เปิด Live Trading อยู่หรือไม่

    **ยังไม่มี Live ในระบบ จึงคืนเท็จเสมอ** — ฟังก์ชันนี้มีอยู่เพื่อให้กฎ
    "ปิด TOTP ขณะที่ Live เปิดอยู่ไม่ได้" (Q-4) ถูกบังคับไว้ที่จุดเดียวตั้งแต่ตอนนี้
    **F-24 ต้องแทนที่ด้วยของจริง** และเทสต์ของงานนี้แทนค่าของมันเพื่อพิสูจน์ว่า
    เส้นทางปิดจะปฏิเสธจริง (validation V-60)
    """
    return False


async def _checked_password(session: UserSession, user_id: UUID, raw: str) -> None:
    """ตรวจรหัสผ่านปัจจุบันใต้ล็อก — ดังเมื่อไม่ตรง

    ล็อกตามลำดับของ `plan.md` หัวข้อ 1.1 คือข้อมูลเข้าสู่ระบบก่อน `user_totp`
    """
    stored = await locked_credential(session, user_id)
    if stored is None or not password_matches(stored.password_hash, normalised(raw)):
        raise AuthRejectedError(status.HTTP_401_UNAUTHORIZED, PASSWORD_FAILED)


async def _spend_grant_if_used(session: UserSession, who: Authenticated) -> None:
    """ใช้สิทธิ์กู้บัญชีถ้าคำขอนี้ผ่านด้วยมัน — **ในก้อนเดียวกับการกระทำ**

    middleware แค่ตรวจว่ามีสิทธิ์ ไม่ใช้มัน เพื่อไม่ให้คำขอที่ล้มเหลวทีหลัง
    เผาสิทธิ์ใบเดียวที่ผู้ใช้มีไปฟรี ๆ (`plan.md` หัวข้อ 1.8)
    """
    if who.second_factor is not SecondFactor.RECOVERY_GRANT:
        return
    if not await recovery_grants.spend(session, session_token_hash=who.token_hash):
        # แข่งกับคำขออื่นแล้วแพ้ — ปฏิเสธ ไม่ใช่ทำต่อโดยไม่มีปัจจัยที่สอง
        raise AuthRejectedError(status.HTTP_403_FORBIDDEN, SECOND_STEP_FAILED)


def set_challenge_cookie(response: Response, token: str) -> None:
    """ตั้ง cookie ของ challenge — `httpOnly` เหมือนของ session"""
    response.set_cookie(
        CHALLENGE_COOKIE,
        token,
        httponly=True,
        secure=cookie_secure(),
        samesite="strict",
        path="/",
    )


def clear_challenge_cookie(response: Response) -> None:
    """ลบ cookie ของ challenge — **ไม่ใช่การเพิกถอน** การเพิกถอนคือการลบแถว"""
    response.delete_cookie(CHALLENGE_COOKIE, path="/")


@router.post("/setup", status_code=status.HTTP_200_OK)
async def start_setup(
    request: Request,
    body: CurrentPassword,
    who: Annotated[Authenticated, Depends(current_user)],
) -> Enrollment:
    """เริ่มตั้งค่า TOTP — **ต้องกรอกรหัสผ่านปัจจุบัน** (RQ-3.1)

    session ที่กำลังใช้อยู่ **ไม่พอ** เพราะการกรอกรหัสจาก secret ที่ระบบเพิ่งแจกให้
    พิสูจน์แค่ว่าตั้งค่าแอปสำเร็จ ไม่ได้พิสูจน์ว่าเป็นเจ้าของบัญชี — ถ้าไม่มีข้อนี้
    คนที่ขโมย session ไปจะผูกแอปของตัวเองแล้วกันเจ้าของออกตอน login ครั้งถัดไป
    """
    engine = engine_for(request, DatabaseRole.AUTH)
    now = datetime.now(UTC)
    account = who.user_id

    async with throttled(engine, [(Bucket.ACCOUNT, key_of(str(account)))], now=now) as guard:
        refuse_if_throttled(guard)
        async with user_session(engine, account, role=DatabaseRole.AUTH) as session:
            try:
                await _checked_password(session, account, body.password)
            except AuthRejectedError:
                await guard.count_attempt()
                raise
            label = await email_of(session, account)
            secret = totp.new_secret()
            await totp.stage_secret(session, totp_keys(request), secret)
        await guard.forget_account()

    return Enrollment(otpauth_uri=totp.otpauth_uri(secret, account=label or str(account)))


@router.post("/confirm", status_code=status.HTTP_200_OK)
async def confirm_setup(
    request: Request,
    body: Confirmation,
    who: Annotated[Authenticated, Depends(current_user)],
) -> Enabled:
    """ยืนยันแล้วเปิดใช้ — **ทั้งก้อนสำเร็จหรือล้มเหลวด้วยกัน** (validation V-11.2)

    ในก้อนเดียวกัน: สลับ secret, ยกเลิกรหัสสำรองชุดเก่า, ออกชุดใหม่,
    เพิกถอน session อื่นทั้งหมด และลงบันทึก

    **รหัสสำรองชุดเก่าถูกยกเลิกที่นี่ ไม่ใช่ตอนเริ่มเปลี่ยนเครื่อง** เพราะผู้ใช้ที่
    ทิ้งกลางทางต้องไม่เสียทั้งรหัสสำรองและเครื่องใหม่
    """
    engine = engine_for(request, DatabaseRole.AUTH)
    now = datetime.now(UTC)
    account = who.user_id

    async with throttled(
        engine,
        [(Bucket.TOTP_ACCOUNT, key_of(str(account))), (Bucket.TOTP_IP, client_key(request))],
        now=now,
    ) as guard:
        refuse_if_throttled(guard)
        async with user_session(engine, account, role=DatabaseRole.AUTH) as session:
            replacing = await totp.is_enabled(session)
            if not await totp.confirm_secret(
                session, totp_keys(request), presented=body.code, now=now
            ):
                await guard.count_attempt()
                raise AuthRejectedError(status.HTTP_403_FORBIDDEN, SECOND_STEP_FAILED)

            codes = await recovery_codes.issue_set(session)
            ended = await end_others(session, keep_token_hash=who.token_hash)
            await record_own_action(
                session,
                account,
                AuditAction.TOTP_SECRET_REPLACED if replacing else AuditAction.TOTP_ENABLED,
                TotpChangeDetails(),
            )
            await record_own_action(
                session,
                account,
                AuditAction.RECOVERY_CODES_ISSUED,
                RecoveryCodesIssuedDetails(issued=len(codes.codes)),
            )
            await record_own_action(
                session,
                account,
                AuditAction.ALL_SESSIONS_ENDED,
                AllSessionsEndedDetails(ended=ended),
            )

    return Enabled(recovery_codes=list(codes.codes), ended=ended)


@router.post("/replace", status_code=status.HTTP_200_OK)
async def replace_secret(
    request: Request,
    body: CurrentPassword,
    who: Annotated[Authenticated, Depends(current_user)],
) -> Enrollment:
    """ออก secret ใหม่สำหรับเครื่องใหม่ — **ปัจจัยเดิมยังใช้ได้จนยืนยันสำเร็จ**

    middleware บังคับปัจจัยที่สองของเส้นทางนี้แล้ว (รหัส TOTP หรือสิทธิ์กู้บัญชี)
    ที่นี่จึงเหลือแค่รหัสผ่านปัจจุบัน และการใช้สิทธิ์กู้ถ้าคำขอนี้ผ่านด้วยมัน
    """
    engine = engine_for(request, DatabaseRole.AUTH)
    account = who.user_id

    async with user_session(engine, account, role=DatabaseRole.AUTH) as session:
        await _checked_password(session, account, body.password)
        await _spend_grant_if_used(session, who)
        label = await email_of(session, account)
        secret = totp.new_secret()
        await totp.stage_secret(session, totp_keys(request), secret)

    return Enrollment(otpauth_uri=totp.otpauth_uri(secret, account=label or str(account)))


@router.post("/disable", status_code=status.HTTP_200_OK)
async def disable_totp(
    request: Request,
    body: CurrentPassword,
    who: Annotated[Authenticated, Depends(current_user)],
) -> Disabled:
    """ปิด TOTP — **ปิดไม่ได้ขณะที่ Live เปิดอยู่** (Q-4)

    เพราะ R-19 บังคับว่า Live ต้องมี 2FA ถ้ายอมให้ปิดโดย Live ยังเปิด จะเกิดสถานะ
    ที่ spec ห้าม · **ไม่ปิด Live ให้อัตโนมัติ** เพราะกระทบไม้ที่เปิดอยู่ ซึ่งเป็น
    ผลข้างเคียงที่ผู้ใช้ไม่ได้สั่ง
    """
    engine = engine_for(request, DatabaseRole.AUTH)
    account = who.user_id

    async with user_session(engine, account, role=DatabaseRole.AUTH) as session:
        await _checked_password(session, account, body.password)
        if await live_trading_enabled(session):
            raise AuthRejectedError(
                status.HTTP_409_CONFLICT,
                "ปิดการยืนยันสองชั้นขณะที่ Live Trading เปิดอยู่ไม่ได้ — ปิด Live ก่อน",
            )
        await _spend_grant_if_used(session, who)
        await totp.disable(session)
        await recovery_codes.revoke_all(session)
        ended = await end_others(session, keep_token_hash=who.token_hash)
        await record_own_action(session, account, AuditAction.TOTP_DISABLED, TotpChangeDetails())
        await record_own_action(
            session, account, AuditAction.ALL_SESSIONS_ENDED, AllSessionsEndedDetails(ended=ended)
        )

    return Disabled(ended=ended)


@router.post("/recovery-codes", status_code=status.HTTP_200_OK)
async def reissue_recovery_codes(
    request: Request,
    body: CurrentPassword,
    who: Annotated[Authenticated, Depends(current_user)],
) -> CodesIssued:
    """ออกชุดรหัสสำรองใหม่ — **ชุดเก่าใช้ไม่ได้ทันที** (RQ-15)"""
    engine = engine_for(request, DatabaseRole.AUTH)
    account = who.user_id

    async with user_session(engine, account, role=DatabaseRole.AUTH) as session:
        await _checked_password(session, account, body.password)
        codes = await recovery_codes.issue_set(session)
        await record_own_action(
            session,
            account,
            AuditAction.RECOVERY_CODES_ISSUED,
            RecoveryCodesIssuedDetails(issued=len(codes.codes)),
        )

    return CodesIssued(recovery_codes=list(codes.codes))


@router.post("/login", status_code=status.HTTP_200_OK)
async def complete_sign_in(request: Request, response: Response, body: SecondStep) -> SignedIn:
    """ขั้นที่สองของการเข้าสู่ระบบ — รหัสจากแอป หรือรหัสสำรองหนึ่งใบ

    **ออก session ที่นี่เท่านั้น** ขั้นแรกคืน challenge ซึ่งใช้เรียกเส้นทางอื่นไม่ได้เลย
    ฉะนั้น RQ-5 เป็นจริงโดยโครงสร้าง ไม่ใช่เพราะ middleware ขยัน

    **เทียบรุ่นของรหัสผ่านใต้ล็อก** ฉะนั้น challenge ที่ออกด้วยรหัสผ่านเก่าใช้ต่อไม่ได้
    แม้จะยังไม่หมดอายุ (RQ-22 ของ F-05 · `plan.md` หัวข้อ 1.4)
    """
    token = request.cookies.get(CHALLENGE_COOKIE, "")
    if not token:
        raise HTTPException(status.HTTP_403_FORBIDDEN, SECOND_STEP_FAILED)

    engine = engine_for(request, DatabaseRole.AUTH)
    now = datetime.now(UTC)
    token_hash = challenges.hash_of(token)
    using_recovery = body.recovery_code is not None

    async with presented_session(engine, token_hash=token_hash, role=DatabaseRole.AUTH) as finder:
        waiting = await challenges.presented(finder)
        if waiting is None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, SECOND_STEP_FAILED)
        account = waiting.user_id

    bucket = Bucket.RECOVERY_ACCOUNT if using_recovery else Bucket.TOTP_ACCOUNT
    async with throttled(
        engine,
        [(bucket, key_of(str(account))), (Bucket.TOTP_IP, client_key(request))],
        now=now,
    ) as guard:
        refuse_if_throttled(guard)
        async with presented_session(
            engine, token_hash=token_hash, role=DatabaseRole.AUTH
        ) as finder:
            waiting = await challenges.presented(finder)
            if waiting is None:
                raise AuthRejectedError(status.HTTP_403_FORBIDDEN, SECOND_STEP_FAILED)
            session = await finder.assume_user(waiting.user_id)

            stored = await locked_credential(session, waiting.user_id)
            if stored is None or stored.updated_at != waiting.credential_updated_at:
                # รหัสผ่านเปลี่ยนไปหลัง challenge ถูกออก → ใบนี้ตายแล้ว
                await challenges.end_all(session)
                raise AuthRejectedError(status.HTTP_403_FORBIDDEN, SECOND_STEP_FAILED)

            left = await _passed_second_step(session, request, body, now=now)
            if left is None:
                await guard.count_attempt()
                raise AuthRejectedError(status.HTTP_403_FORBIDDEN, SECOND_STEP_FAILED)

            await challenges.spend(session, token_hash=token_hash)
            token, session_hash = new_token()
            deadlines = deadlines_for_new_session(now)
            await issue(
                session,
                token_hash=session_hash,
                idle_expires_at=deadlines.idle_expires_at,
                absolute_expires_at=deadlines.absolute_expires_at,
            )
            await record_own_action(
                session, waiting.user_id, AuditAction.SESSION_STARTED, SessionDetails()
            )
            if using_recovery:
                await recovery_grants.grant(session, session_token_hash=session_hash)
                await record_own_action(
                    session,
                    waiting.user_id,
                    AuditAction.RECOVERY_CODE_USED,
                    RecoveryCodeUsedDetails(remaining=left),
                )

    clear_challenge_cookie(response)
    set_session_cookies(response, token=token, csrf_token=new_csrf_token())
    return SignedIn(user_id=account, recovery_codes_left=left if using_recovery else None)


async def _passed_second_step(
    session: UserSession, request: Request, body: SecondStep, *, now: datetime
) -> int | None:
    """ผ่านขั้นที่สองหรือไม่ — คืนจำนวนรหัสสำรองที่เหลือ หรือ `None` เมื่อไม่ผ่าน

    **รับทางเดียวต่อคำขอ** ส่งมาทั้งสองอย่างถือว่าไม่ผ่าน เพราะคำขอที่กำกวม
    ไม่ควรได้ประโยชน์จากการเดาสองทางในโควตาเดียว
    """
    if (body.code is None) == (body.recovery_code is None):
        return None
    if body.recovery_code is not None:
        return await recovery_codes.spend(session, body.recovery_code)
    if await totp.verify(session, totp_keys(request), presented=body.code or "", now=now):
        return await recovery_codes.remaining(session)
    return None
