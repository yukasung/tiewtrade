"""เส้นทางจัดการ API key ของผู้ใช้ (F-07 `plan.md` ข้อ 8)

**เส้นทางที่นี่อยู่บนบทบาท `tiewtrade_api`** ซึ่ง **เขียนความลับลงไปได้แต่อ่านกลับไม่ได้**
(migration `0009`) — การรับ secret มาเพื่อเข้ารหัสทันทีแล้วส่งต่อคือสิ่งที่
`tech-stack.md` หัวข้อ 8 อนุญาตไว้ และเป็นทางเดียวที่มี เพราะผู้ใช้กรอกผ่านหน้าเว็บ

**ผลการตรวจไม่ได้ตัดสินที่นี่** — `engine` เป็นผู้ตรวจ เพราะมันเป็นที่เดียวที่เปิดผนึกได้
ที่นี่แค่บันทึกคำขอแล้วให้ผู้ใช้เห็นสถานะ (Q-1 ที่เจ้าของตัดสิน)

**การยืนยันปัจจัยที่สองซ้ำตัดสินที่ middleware** ตามตารางใน `routing_policy.py`
ไม่ใช่ที่นี่ · เส้นทางเพิ่ม key **ไม่รับรหัสสำรอง** เพราะเป็นการกระทำที่เพิ่มความเสี่ยง
(`security.md` หัวข้อ 1)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator

from tiewtrade.infra.api_keys import (
    ApiKeyError,
    ApiKeyStatus,
    ApiKeySummary,
    RetryOutcome,
    TooManyKeysError,
    accepted_label_text,
    accepted_public_identifier,
    delete_key,
    request_retry,
    store_key,
    summaries_for,
)
from tiewtrade.infra.audit import (
    ActorKind,
    ApiKeyDetails,
    AuditAction,
    AuditEvent,
    AuditOutcome,
    record_event,
)
from tiewtrade.infra.audit import SubjectKind as AuditSubject
from tiewtrade.infra.auth import Bucket
from tiewtrade.infra.db import DatabaseRole
from tiewtrade.infra.db.errors import DuplicateValueError
from tiewtrade.infra.db.session import UserSession, user_session
from tiewtrade.services.api.authentication import Authenticated, current_user
from tiewtrade.services.api.resources import engine_for, venue_keys
from tiewtrade.services.api.safe_input_routes import SafeInputRoute
from tiewtrade.services.api.throttling import spend_token


class RejectedKeyInput(BaseModel):
    """คำตอบ validation ที่มีแค่รหัส ไม่มีค่าที่ผู้ใช้ส่งมา"""

    detail: str


class _CredentialRoute(SafeInputRoute):
    """Keep the existing F-07 validation response unchanged."""

    rejection_code = ApiKeyError.code


router = APIRouter(
    prefix="/api-keys",
    tags=["api-keys"],
    route_class=_CredentialRoute,
    responses={422: {"model": RejectedKeyInput}},
)


class AddKeyRequest(BaseModel):
    """ของที่ผู้ใช้กรอก — **`secret` เข้ามาทางเดียวและไม่เคยออกไปทางไหน**"""

    label: str = Field(min_length=1, max_length=40)
    key: str = Field(min_length=1, max_length=256)
    secret: str = Field(min_length=1, max_length=256)

    @field_validator("label")
    @classmethod
    def storable_label(cls, value: str) -> str:
        try:
            return accepted_label_text(value)
        except ApiKeyError:
            raise ValueError(ApiKeyError.code) from None

    @field_validator("key")
    @classmethod
    def usable_header(cls, value: str) -> str:
        try:
            return accepted_public_identifier(value)
        except ApiKeyError:
            raise ValueError(ApiKeyError.code) from None


class AddedKey(BaseModel):
    """คำตอบของการเพิ่ม — มีแค่รหัสของแถวกับสถานะเริ่มต้น"""

    id: UUID
    status: str


class KeyView(BaseModel):
    """สิ่งที่หน้าจอได้เห็นของ key หนึ่งใบ

    **ไม่มีช่องสำหรับ key เต็มและไม่มีช่องสำหรับ secret** — ความลับไม่หลุดเพราะ
    ไม่มีที่ให้มันอยู่ ไม่ใช่เพราะผู้เขียน endpoint จำได้ว่าอย่าใส่
    """

    id: UUID
    label: str
    public_tail: str
    status: str
    created_at: datetime
    failure_code: str | None = None
    verified_at: datetime | None = None
    not_before: datetime | None = None
    next_attempt_at: datetime | None = None
    may_retry: bool = False


def key_view(summary: ApiKeySummary) -> KeyView:
    return KeyView(
        id=summary.id,
        label=summary.label,
        public_tail=summary.public_tail,
        status=summary.status.value,
        created_at=summary.created_at,
        failure_code=summary.failure_code,
        verified_at=summary.verified_at,
        not_before=summary.not_before,
        next_attempt_at=summary.next_attempt_at,
        may_retry=summary.may_retry,
    )


async def _record(
    session: UserSession, who: Authenticated, action: AuditAction, key_id: UUID
) -> None:
    """บันทึกการกระทำของผู้ใช้กับ key หนึ่งใบ — ใน transaction เดียวกับการกระทำ

    `subject_id` เป็น **รหัสของแถว ไม่ใช่ค่าของ key** (RQ-9.1) และ `details` ว่างเสมอ
    """
    await record_event(
        session,
        AuditEvent(
            owner_user_id=who.user_id,
            action=action,
            actor_kind=ActorKind.USER,
            actor_id=who.user_id,
            subject_kind=AuditSubject.API_KEY,
            subject_id=str(key_id),
            outcome=AuditOutcome.SUCCEEDED,
            details=ApiKeyDetails(),
        ),
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def add_key(
    body: AddKeyRequest,
    request: Request,
    who: Annotated[Authenticated, Depends(current_user)],
) -> AddedKey:
    """รับคำรับรองหนึ่งชุด ปิดผนึกทันที แล้วรอให้ `engine` ตรวจ

    **คุมอัตราก่อนแตะอะไร** — มิฉะนั้นระบบนี้กลายเป็นเครื่องมือทดสอบคำรับรอง
    ของคนอื่นกับตลาด (`security.md` หัวข้อ 3 · RQ-11)
    """
    engine = engine_for(request, DatabaseRole.API)
    await spend_token(engine, who.user_id, Bucket.API_KEY_ADD)

    async with user_session(engine, who.user_id) as session:
        try:
            key_id = await store_key(
                session,
                venue_keys(request),
                user_id=who.user_id,
                label=body.label,
                key_public=body.key,
                secret=body.secret,
            )
        except TooManyKeysError as error:
            raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from None
        except DuplicateValueError:
            raise HTTPException(status.HTTP_409_CONFLICT, DuplicateValueError.code) from None
        except ApiKeyError as error:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error)) from None

        await _record(session, who, AuditAction.API_KEY_ADDED, key_id)

    return AddedKey(id=key_id, status=ApiKeyStatus.PENDING.value)


@router.get("")
async def list_keys(
    request: Request,
    who: Annotated[Authenticated, Depends(current_user)],
) -> list[KeyView]:
    """รายการ key ของผู้ใช้คนนี้ — หน้าเว็บเรียกเป็นรอบ ๆ เพื่อดูสถานะ

    เส้นทางนี้ **ไม่ต่ออายุ session** (`routing_policy.py`) เพราะการ poll
    ไม่ควรทำให้ session ไม่มีวันหมดอายุ
    """
    engine = engine_for(request, DatabaseRole.API)
    async with user_session(engine, who.user_id) as session:
        summaries = await summaries_for(session, who.user_id)
    return [key_view(summary) for summary in summaries]


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_key(
    key_id: UUID,
    request: Request,
    who: Annotated[Authenticated, Depends(current_user)],
) -> None:
    """ลบ key ของตัวเอง — ของคนอื่นได้ "ไม่พบ" (RLS เป็นผู้กัน ไม่ใช่เงื่อนไขที่นี่)"""
    engine = engine_for(request, DatabaseRole.API)
    async with user_session(engine, who.user_id) as session:
        if not await delete_key(session, key_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบ key นี้")
        await _record(session, who, AuditAction.API_KEY_DELETED, key_id)


class RetryAccepted(BaseModel):
    """ผลของการกดลองใหม่"""

    id: UUID
    status: str


@router.post("/{key_id}/retry", status_code=status.HTTP_202_ACCEPTED)
async def retry_key(
    key_id: UUID,
    request: Request,
    who: Annotated[Authenticated, Depends(current_user)],
) -> RetryAccepted:
    """ขอให้ตรวจ key ใบนี้ใหม่

    **ไม่ต้องยืนยันปัจจัยที่สองซ้ำ** (เจ้าของตัดสิน 2026-10-04) เพราะความลับเข้าระบบ
    ไปแล้วตอนเพิ่ม ซึ่งผ่านการยืนยันแล้ว การลองใหม่ไม่ได้เพิ่มความเสี่ยงใหม่

    **เวลาที่ตลาดสั่งให้รอข้ามไม่ได้** — ที่นี่ปฏิเสธเพื่อให้ผู้ใช้รู้ตัวเร็ว
    ส่วนด่านจริงอยู่ในคำสั่งจองของ worker (`plan.md` ข้อ 7.5)
    """
    engine = engine_for(request, DatabaseRole.API)
    await spend_token(engine, who.user_id, Bucket.API_KEY_RETRY)

    async with user_session(engine, who.user_id) as session:
        decision = await request_retry(session, key_id)
        if decision.outcome is RetryOutcome.NOT_FOUND:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบ key นี้")
        if decision.outcome is RetryOutcome.NOT_RETRYABLE:
            raise HTTPException(status.HTTP_409_CONFLICT, "สถานะนี้สั่งตรวจใหม่ไม่ได้")
        if decision.outcome is RetryOutcome.MUST_WAIT:
            if decision.not_before is None:
                raise HTTPException(
                    status.HTTP_409_CONFLICT, "สถานะเปลี่ยนระหว่างคำขอ กรุณาดึงรายการใหม่"
                )
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                f"ตลาดขอให้รอถึง {_as_text(decision.not_before)}",
                headers={"Retry-After": _retry_after_header(decision.not_before)},
            )
        await _record(session, who, AuditAction.API_KEY_RETRY_REQUESTED, key_id)

    return RetryAccepted(id=key_id, status=ApiKeyStatus.UNVERIFIABLE.value)


def _retry_after_header(moment: datetime) -> str:
    """HTTP-date จากเวลาของ DB · ปัดขึ้น ไม่ชวนให้ลองก่อนตลาดอนุญาต."""
    rounded = moment.astimezone(UTC)
    if rounded.microsecond:
        rounded += timedelta(seconds=1)
    return format_datetime(rounded.replace(microsecond=0), usegmt=True)


def _as_text(moment: datetime | None) -> str:
    """เวลาที่บอกผู้ใช้ — ไม่มีค่าก็บอกว่าไม่รู้ ดีกว่าเดาเวลาแทนตลาด"""
    if moment is None:
        return "อีกสักครู่"
    return moment.astimezone(UTC).isoformat()
