"""รอบตรวจ API key หนึ่งรอบ — worker ตัวแรกของ `engine` (F-07 `plan.md` ข้อ 7)

**ตรรกะอยู่ที่นี่ การวนอยู่ที่ `main.py`** เทสต์จึงไม่ต้องรอเวลาจริงและไม่ต้องมี loop
(`architecture.md` หัวข้อ 2 — เวลาเป็นค่าที่ผู้เรียกส่งเข้ามา)

**ไม่เปิด transaction คร่อมการเรียกตลาด** การถือ transaction ไว้ข้ามการรอเครือข่าย
คือการให้ตลาดกำหนดว่าเราถือล็อกนานแค่ไหน · การจองจึงเป็นคอลัมน์ที่มีอายุของตัวเอง
(`infra/api_keys/claims.py`)

**ผลของการตรวจมีสามแบบ ไม่ใช่สองแบบ** (Q-7 ที่เจ้าของตัดสิน):
key ผิดจริง · ตรวจไม่ได้ชั่วคราว · ตลาดตอบไม่ตรงสัญญา — แบบสุดท้ายนับเป็นชั่วคราว
**แต่ต้องแจ้งผู้ดูแลแยก** เพราะมันต้องการคนแก้โค้ด ไม่ใช่แค่รอ
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.infra.api_keys import ApiKeyError, HmacRequestSigner, accepted_public_identifier
from tiewtrade.infra.api_keys.claims import (
    EXPIRED_CODE,
    ClaimedKey,
    DueKey,
    claim,
    due_hints,
    expire_if_overdue,
    mark_active,
    mark_deferred,
    mark_rejected,
)
from tiewtrade.infra.audit import (
    ActorKind,
    ApiKeyDetails,
    AuditAction,
    AuditEvent,
    AuditOutcome,
    SubjectKind,
    record_event,
)
from tiewtrade.infra.crypto import KeySource, Sealed, SealingError, unseal
from tiewtrade.infra.db import DatabaseRole, scan_session_bypassing_rls, user_session
from tiewtrade.infra.db.session import UserSession
from tiewtrade.venues.errors import (
    VenueCredentialRejectedError,
    VenueError,
    VenueProtocolError,
    VenueRateLimitedError,
    VenueRejectedError,
)
from tiewtrade.venues.signing import RequestSigner
from tiewtrade.venues.wallets import WalletSource

_LOGGER = logging.getLogger(__name__)

#: รหัสที่ใช้เมื่อเปิดผนึกไม่ออก — กุญแจผิดรุ่น ข้อมูลถูกแก้ หรือกุญแจหาย
#:
#: นับเป็น **ชั่วคราว** โดยเจตนา: ถ้ากุญแจบนเครื่องถูกตั้งผิด การลบ secret ของผู้ใช้
#: ทุกคนทิ้งคือความเสียหายที่กู้ไม่ได้ ส่วนการรอให้คนมาแก้การตั้งค่านั้นกู้ได้เสมอ
UNSEALABLE_CODE = "VENUE_PROTOCOL"

#: รหัสของผลแต่ละแบบ — ต้องตรงกับที่ migration `0009` ประกาศไว้
_PERMANENT: dict[type[VenueError], str] = {
    VenueCredentialRejectedError: "VENUE_CREDENTIAL_REJECTED",
}


class WalletFactory(Protocol):
    """สร้างตัวอ่านกระเป๋าจากคำรับรองหนึ่งชุด

    มีไว้ให้เทสต์ใส่ตลาดปลอมเข้ามาได้ โดยที่โค้ดจริงไม่ต้องรู้ว่าตลาดไหน
    """

    def __call__(self, signer: RequestSigner, /) -> WalletSource: ...


@dataclass(frozen=True, slots=True)
class RoundSummary:
    """ผลของหนึ่งรอบ — มีไว้ให้เทสต์และคนดูแลอ่าน ไม่ได้ใช้ตัดสินใจอะไรต่อ"""

    expired: int = 0
    verified: int = 0
    rejected: int = 0
    deferred: int = 0
    skipped: int = 0


async def run_round(
    *,
    engine: AsyncEngine,
    scan_engine: AsyncEngine,
    keys: KeySource,
    wallet_for: WalletFactory,
    worker: str,
    limit: int = 100,
) -> RoundSummary:
    """ตรวจแถวที่ถึงคิวหนึ่งรอบ แล้วคืนสรุป

    ลำดับสำคัญ: **ปิดแถวที่หมดอายุก่อนจอง** มิฉะนั้นเราจะไปเรียกตลาดด้วย key
    ที่หมดอายุไปแล้ว และผลที่ได้กลับมาจะพยายามเปิดใช้งานมัน
    """
    async with scan_session_bypassing_rls(scan_engine) as scanning:
        candidates = await due_hints(scanning, limit=limit)

    summary = RoundSummary()
    for candidate in candidates:
        summary = _merged(summary, await _handle(candidate, engine, keys, wallet_for, worker))
    return summary


def _merged(total: RoundSummary, one: RoundSummary) -> RoundSummary:
    return RoundSummary(
        expired=total.expired + one.expired,
        verified=total.verified + one.verified,
        rejected=total.rejected + one.rejected,
        deferred=total.deferred + one.deferred,
        skipped=total.skipped + one.skipped,
    )


async def _handle(
    candidate: DueKey,
    engine: AsyncEngine,
    keys: KeySource,
    wallet_for: WalletFactory,
    worker: str,
) -> RoundSummary:
    """หนึ่งแถว — สาม transaction สั้น ๆ โดยไม่มีอันไหนคร่อมการเรียกตลาด"""
    async with user_session(engine, candidate.user_id, role=DatabaseRole.ENGINE) as session:
        if await _expire_and_record(session, candidate):
            return RoundSummary(expired=1)
        claimed = await claim(session, candidate, worker=worker)

    if claimed is None:
        return RoundSummary(skipped=1)

    signer = _signer_for(claimed, keys)
    if signer is None:
        return await _write(engine, claimed, worker, deferred=UNSEALABLE_CODE)

    try:
        await wallet_for(signer).holdings()
    except VenueError as error:
        return await _after_failure(engine, claimed, worker, error)

    return await _write(engine, claimed, worker, verified=True)


def _signer_for(claimed: ClaimedKey, keys: KeySource) -> RequestSigner | None:
    """เปิดผนึกแล้วสร้างตัวลงลายเซ็น — `None` เมื่อเปิดไม่ออก

    **ค่าดิบอยู่ในตัวลงลายเซ็นเท่านั้น** ไม่ถูกคืนออกมาและไม่ถูกเก็บที่อื่น
    """
    try:
        public_identifier = accepted_public_identifier(claimed.key_public)
    except ApiKeyError:
        # ข้อมูลเก่าผิดรูปต้องไม่ฆ่า process หรือส่งค่าที่ผิดไปยัง HTTP client
        _LOGGER.error("คำรับรองของ key %s ผิดรูป (VENUE_PROTOCOL)", claimed.id)
        return None
    try:
        secret = unseal(
            keys,
            Sealed(key_version=claimed.key_version, blob=claimed.secret_sealed),
            owner=claimed.user_id,
        )
    except SealingError:
        # **ไม่ log รายละเอียด** — เหตุผลของการเปิดผนึกไม่สำเร็จช่วยผู้โจมตีมากกว่า
        _LOGGER.error("เปิดผนึกคำรับรองของ key %s ไม่สำเร็จ", claimed.id)
        return None
    return HmacRequestSigner(public_identifier=public_identifier, secret=secret)


async def _after_failure(
    engine: AsyncEngine, claimed: ClaimedKey, worker: str, error: VenueError
) -> RoundSummary:
    """แปลความล้มเหลวหนึ่งครั้งเป็นผลที่เขียนลงแถว"""
    permanent = _PERMANENT.get(type(error))
    if permanent is not None:
        return await _write(engine, claimed, worker, rejected=permanent)

    if isinstance(error, VenueRejectedError):
        # ปฏิเสธคำขอไม่เท่ากับปฏิเสธ credential · ห้ามลบหรือส่งซ้ำเอง (NC-20)
        _LOGGER.error(
            "คำขอตรวจ key %s ถูกปฏิเสธ ต้องให้ผู้ดูแลตรวจสอบ (VENUE_REJECTED)",
            claimed.id,
        )
        return await _write(engine, claimed, worker, deferred=error.code, automatic_retry=False)

    if isinstance(error, VenueProtocolError):
        # **แยกจาก "เน็ตหรือตลาดมีปัญหา" ให้เห็นชัด** — อย่างนั้นรอได้ อย่างนี้มีคนต้องแก้โค้ด
        # (บทเรียนจาก F-35) · ช่องทางที่คนเห็นวันนี้คือบันทึกระดับ ERROR ที่มีรหัสของตัวเอง
        # การต่อเข้ากับช่องทางแจ้งเตือนจริงเป็นงาน F-31
        _LOGGER.error(
            "ตลาดตอบไม่ตรงสัญญาตอนตรวจ key %s — ต้องมีคนตรวจสอบตัวเชื่อม (VENUE_PROTOCOL)",
            claimed.id,
        )

    retry_after = error.retry_after if isinstance(error, VenueRateLimitedError) else None
    return await _write(engine, claimed, worker, deferred=error.code, retry_after=retry_after)


async def _write(
    engine: AsyncEngine,
    claimed: ClaimedKey,
    worker: str,
    *,
    verified: bool = False,
    rejected: str | None = None,
    deferred: str | None = None,
    retry_after: timedelta | None = None,
    automatic_retry: bool = True,
) -> RoundSummary:
    """เขียนผลใน transaction ของตัวเอง — **ผูกกับการจองและกับเส้นตายเสมอ**

    **บันทึกลง audit ใน transaction เดียวกับการเปลี่ยนสถานะ** (`plan.md` ข้อ 7.2)
    ถ้าแยก transaction จะมีช่วงที่สถานะเปลี่ยนแล้วแต่ไม่มีบันทึก หรือกลับกัน

    **ไม่บันทึกผลตลาดเมื่อเขียนไม่สำเร็จ** — ผลนี้ถูกทิ้ง แต่ถ้าแถวหมดอายุแล้ว
    ต้องปิดสถานะ ลบ secret และบันทึกการหมดอายุใน transaction เดียวกัน
    """
    async with user_session(engine, claimed.user_id, role=DatabaseRole.ENGINE) as session:
        if verified:
            written = await mark_active(session, claimed, worker=worker)
            action, outcome, code = AuditAction.API_KEY_VERIFIED, AuditOutcome.SUCCEEDED, None
            summary = RoundSummary(verified=1)
        elif rejected is not None:
            written = await mark_rejected(session, claimed, worker=worker, code=rejected)
            action, outcome, code = AuditAction.API_KEY_REJECTED, AuditOutcome.REJECTED, rejected
            summary = RoundSummary(rejected=1)
        else:
            assert deferred is not None
            written = await mark_deferred(
                session,
                claimed,
                worker=worker,
                code=deferred,
                retry_after=retry_after,
                automatic_retry=automatic_retry,
            )
            action, outcome, code = (
                AuditAction.API_KEY_VERIFICATION_DEFERRED,
                AuditOutcome.FAILED,
                deferred,
            )
            summary = RoundSummary(deferred=1)

        if written:
            await _record(session, claimed, action, outcome, code)
            return summary
        # UPDATE ของผลตรวจบังคับเวลา ณ ตอนเขียนแล้ว · เมื่อเลยเส้นตายให้ปิด
        # แถวใน transaction นี้เลย ไม่ทิ้ง secret ไว้รอรอบ scan ถัดไป
        if await _expire_and_record(session, claimed):
            return RoundSummary(expired=1)
        return RoundSummary(skipped=1)


async def _expire_and_record(session: UserSession, key: DueKey | ClaimedKey) -> bool:
    """ปิดแถวที่ยังไม่ผ่านและหมดอายุพร้อม audit · UPDATE เป็นผู้ตัดสินใต้ล็อก"""
    if not await expire_if_overdue(session, key.id):
        return False
    await _record(session, key, AuditAction.API_KEY_REJECTED, AuditOutcome.REJECTED, EXPIRED_CODE)
    return True


async def _record(
    session: UserSession,
    claimed: DueKey | ClaimedKey,
    action: AuditAction,
    outcome: AuditOutcome,
    failure_code: str | None,
) -> None:
    """บันทึกผลหนึ่งครั้ง — **ผู้กระทำคือระบบ ไม่ใช่ผู้ใช้**

    งานนี้เกิดใน `engine` ที่ไม่มีคนนั่งอยู่ปลายสาย การบันทึกว่าเป็นผู้ใช้จะทำให้
    บันทึกที่ลบไม่ได้โกหกว่าใครเป็นคนทำ
    """
    await record_event(
        session,
        AuditEvent(
            owner_user_id=claimed.user_id,
            action=action,
            actor_kind=ActorKind.SYSTEM,
            subject_kind=SubjectKind.API_KEY,
            subject_id=str(claimed.id),
            outcome=outcome,
            failure_code=failure_code,
            details=ApiKeyDetails(),
        ),
    )


__all__ = ["RoundSummary", "WalletFactory", "run_round"]
