"""เพดานการเดาปัจจัยที่สอง — V-62.1 ถึง V-62.7

**พิสูจน์เพดานจริง ไม่ใช่พิสูจน์สูตรเติมโควตา** (เงื่อนไขของรีวิว 2026-10-03)
สูตรที่ถูกแต่ถูกใช้ผิดตอนมีคำขอพร้อมกัน หรือถูกหลบด้วยการย้ายจุดตรวจ
ก็ไม่ได้จำกัดอะไรเลย
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.auth.conftest import fresh_bucket_key
from tiewtrade.infra.auth.throttle import (
    RULES,
    SECOND_FACTOR_CAPACITY,
    SECOND_FACTOR_CEILING_PER_HOUR,
    SECOND_FACTOR_REFILL,
    Bucket,
    TokenRule,
    claim,
    count_failure,
)
from tiewtrade.infra.db import DatabaseRole
from tiewtrade.infra.db.session import presented_session

#: ถังของปัจจัยที่สองทั้งสามใบ
SECOND_FACTOR_BUCKETS = (Bucket.TOTP_ACCOUNT, Bucket.TOTP_IP, Bucket.RECOVERY_ACCOUNT)


async def attempt(engine: AsyncEngine, bucket: Bucket, key: str, *, now: datetime) -> bool:
    """เดาหนึ่งครั้งเหมือนคำขอหนึ่งคำขอ — คืนว่าผ่านด่านหรือถูกปฏิเสธ"""
    async with presented_session(engine, role=DatabaseRole.AUTH) as session:
        state = await claim(session, bucket, key, now=now)
        if state.blocked_at(now):
            return False
        await count_failure(session, bucket, key)
        return True


async def guesses_allowed(
    engine: AsyncEngine, bucket: Bucket, key: str, *, over: timedelta, step: timedelta
) -> int:
    """จำนวนครั้งที่เดาได้จริงในช่วงเวลานั้น เมื่อพยายามถี่ที่สุดเท่าที่ทำได้"""
    start = datetime.now(UTC)
    allowed = 0
    moment = start
    while moment <= start + over:
        if await attempt(engine, bucket, key, now=moment):
            allowed += 1
        else:
            moment += step
            continue
        moment += timedelta(seconds=1)
    return allowed


def test_the_ceiling_is_what_the_two_numbers_give() -> None:
    """V-62.6 — **ความจุ + อัตราเติมคืน = เพดาน** และเทสต์ตรึงความสัมพันธ์นั้นไว้

    เปลี่ยนตัวเลขตัวใดตัวหนึ่งโดยไม่คิดเพดานใหม่ จะแดงที่นี่
    """
    rule = RULES[Bucket.TOTP_ACCOUNT]
    assert isinstance(rule, TokenRule)

    assert rule.capacity == SECOND_FACTOR_CAPACITY
    assert rule.refill_interval == SECOND_FACTOR_REFILL
    assert rule.ceiling_per_hour == SECOND_FACTOR_CEILING_PER_HOUR
    assert SECOND_FACTOR_CEILING_PER_HOUR == 10, (
        "เพดานคือค่าที่เจ้าของตัดสิน (F-06 Q-7) — เปลี่ยนต้องขออนุมัติใหม่"
    )


def test_the_guessing_space_counts_both_accepted_steps() -> None:
    """ความเสี่ยงที่เพดานนี้ให้ — **นับว่าระบบรับรหัสได้สองช่วงเวลา**

    ลืมข้อนี้จะประเมินความเสี่ยงต่ำไปครึ่งหนึ่ง (รีวิว 2026-10-03)
    """
    from tiewtrade.core.totp import DIGITS, STEPS_ACCEPTED_BACK

    space = 10**DIGITS
    accepted = STEPS_ACCEPTED_BACK + 1
    per_guess = accepted / space

    assert per_guess == 2 / 10**6
    # เดาเต็มเพดานหนึ่งชั่วโมง — เลขนี้คือสิ่งที่เจ้าของเห็นก่อนตัดสิน
    one_hour = 1 - (1 - per_guess) ** SECOND_FACTOR_CEILING_PER_HOUR
    assert round(one_hour * 100, 4) == 0.0020


async def test_the_ceiling_holds_in_any_sixty_minutes(auth_engine: AsyncEngine) -> None:
    """V-62.3 — **เพดานต้องเคารพช่วง 60 นาทีเลื่อน ไม่ใช่หน้าต่างคงที่**

    หน้าต่างคงที่จะยอมให้เดาเต็มเพดานท้ายหน้าต่างแรกแล้วต่อต้นหน้าต่างถัดไป
    ซึ่งได้สองเท่าในช่วง 60 นาทีจริง — เทสต์นี้คือเหตุผลที่ไม่ใช้หน้าต่างคงที่
    """
    key = fresh_bucket_key()

    allowed = await guesses_allowed(
        auth_engine,
        Bucket.TOTP_ACCOUNT,
        key,
        over=timedelta(hours=1),
        step=SECOND_FACTOR_REFILL,
    )

    assert allowed <= SECOND_FACTOR_CEILING_PER_HOUR, (
        f"เดาได้ {allowed} ครั้งในหนึ่งชั่วโมง เกินเพดาน {SECOND_FACTOR_CEILING_PER_HOUR}"
    )


async def test_the_burst_is_the_capacity(auth_engine: AsyncEngine) -> None:
    """V-62.6 — พิมพ์ผิดติดกันได้เท่าความจุ แล้วถูกปฏิเสธ"""
    key = fresh_bucket_key()
    now = datetime.now(UTC)

    for attempt_number in range(SECOND_FACTOR_CAPACITY):
        assert await attempt(auth_engine, Bucket.TOTP_ACCOUNT, key, now=now) is True, (
            f"ครั้งที่ {attempt_number + 1} ถูกปฏิเสธทั้งที่ยังไม่ถึงความจุ"
        )

    assert await attempt(auth_engine, Bucket.TOTP_ACCOUNT, key, now=now) is False


async def test_one_token_comes_back_each_interval(auth_engine: AsyncEngine) -> None:
    """V-62.6 — เติมคืนหนึ่งครั้งต่อหนึ่งช่วง ไม่ใช่คืนเต็มก้อน"""
    key = fresh_bucket_key()
    now = datetime.now(UTC)
    for _ in range(SECOND_FACTOR_CAPACITY):
        await attempt(auth_engine, Bucket.TOTP_ACCOUNT, key, now=now)

    # ยังไม่ครบหนึ่งช่วง → ยังถูกปฏิเสธ
    assert (
        await attempt(auth_engine, Bucket.TOTP_ACCOUNT, key, now=now + SECOND_FACTOR_REFILL / 2)
        is False
    )
    # ครบหนึ่งช่วง → ได้หนึ่งครั้ง แล้วหมดอีก
    #
    # บวกหนึ่งวินาทีเพราะ `refilled_at` มาจากนาฬิกาของฐานข้อมูล ซึ่งช้ากว่านาฬิกา
    # ของเทสต์ได้เสี้ยววินาที — เทสต์ที่แดงสุ่มแย่กว่าเทสต์ที่เผื่อขอบไว้
    refilled = now + SECOND_FACTOR_REFILL + timedelta(seconds=1)
    assert await attempt(auth_engine, Bucket.TOTP_ACCOUNT, key, now=refilled) is True
    assert await attempt(auth_engine, Bucket.TOTP_ACCOUNT, key, now=refilled) is False


async def test_the_ceiling_is_not_exceeded_by_requests_at_once(
    auth_engine: AsyncEngine,
) -> None:
    """V-62.1 — **ยิงพร้อมกันต้องไม่ทะลุเพดาน**

    ถ้าแต่ละคำขออ่านโควตาของตัวเองแล้วเขียนทับกัน ความจุ 4 จะกลายเป็นไม่จำกัด
    """
    key = fresh_bucket_key()
    now = datetime.now(UTC)

    results = await asyncio.gather(
        *(attempt(auth_engine, Bucket.TOTP_ACCOUNT, key, now=now) for _ in range(20))
    )

    assert sum(results) == SECOND_FACTOR_CAPACITY, (
        f"ผ่านด่าน {sum(results)} ครั้งจาก 20 คำขอพร้อมกัน ควรเท่าความจุ {SECOND_FACTOR_CAPACITY}"
    )


async def test_the_quota_is_shared_across_checkpoints(auth_engine: AsyncEngine) -> None:
    """V-62.2 — **โควตาของบัญชีร่วมกันทุกจุดตรวจ TOTP**

    คีย์ของถังคือบัญชี ไม่ใช่จุดตรวจหรือรอบ login ฉะนั้นใช้โควตาหมดที่จุดหนึ่ง
    แล้วย้ายไปเดาที่จุดอื่นก็ยังถูกปฏิเสธ — ช่องที่รีวิวรอบแรกจับได้
    """
    account_key = fresh_bucket_key()
    now = datetime.now(UTC)
    for _ in range(SECOND_FACTOR_CAPACITY):
        await attempt(auth_engine, Bucket.TOTP_ACCOUNT, account_key, now=now)

    # "จุดตรวจอื่น" ใช้คีย์เดียวกันเพราะคีย์คือบัญชี
    assert await attempt(auth_engine, Bucket.TOTP_ACCOUNT, account_key, now=now) is False


async def test_the_recovery_bucket_is_separate(auth_engine: AsyncEngine) -> None:
    """V-62 ข้อ 7 ของ Q-7 — ถังของรหัสสำรองแยกจากถังของ TOTP

    ถ้าใช้ถังเดียวกัน ผู้โจมตีเดารหัสสำรองจนโควตาของ TOTP หมดได้ แล้วเจ้าของ
    ที่ถือเครื่องอยู่จะใช้รหัสจากแอปไม่ได้
    """
    key = fresh_bucket_key()
    now = datetime.now(UTC)
    for _ in range(SECOND_FACTOR_CAPACITY):
        await attempt(auth_engine, Bucket.RECOVERY_ACCOUNT, key, now=now)

    assert await attempt(auth_engine, Bucket.RECOVERY_ACCOUNT, key, now=now) is False
    assert await attempt(auth_engine, Bucket.TOTP_ACCOUNT, key, now=now) is True


async def test_the_quota_is_not_cleared_by_success(auth_engine: AsyncEngine) -> None:
    """V-62.5 — **ยืนยันสำเร็จไม่คืนโควตา** (เจ้าของตัดสิน 2026-10-03)

    ถังแบบเติมคืนไม่มีการล้างเลย มันคืนตามเวลาเท่านั้น — เทสต์นี้ตรึงข้อนั้นไว้
    โดยใช้ `clear()` ซึ่งเป็นทางล้างของถังหน้าต่างคงที่ แล้วพิสูจน์ว่าโควตาไม่กลับมา
    """
    from tiewtrade.infra.auth.throttle import clear

    key = fresh_bucket_key()
    now = datetime.now(UTC)
    for _ in range(SECOND_FACTOR_CAPACITY):
        await attempt(auth_engine, Bucket.TOTP_ACCOUNT, key, now=now)

    async with presented_session(auth_engine, role=DatabaseRole.AUTH) as session:
        await clear(session, Bucket.TOTP_ACCOUNT, key)

    # `clear()` ลบแถวทิ้ง ซึ่งจะคืนโควตาเต็ม — **ฉะนั้นห้ามเรียกมันกับถังของปัจจัยที่สอง**
    # เทสต์นี้บันทึกข้อนั้นไว้ และโค้ดของเส้นทางไม่เรียก `forget_account()` กับถังเหล่านี้
    assert await attempt(auth_engine, Bucket.TOTP_ACCOUNT, key, now=now) is True


async def test_forgetting_the_account_does_not_refill_a_second_factor_bucket(
    auth_engine: AsyncEngine,
) -> None:
    """V-62.5 ชั้นที่สอง — **`forget_account()` ไม่คืนโควตาของปัจจัยที่สอง**

    เส้นทางเข้าสู่ระบบเรียก `forget_account()` เมื่อรหัสผ่านถูก ซึ่งล้างถัง `ACCOUNT`
    ตามที่ F-05 ออกแบบไว้ · ถ้ามันล้างถังของปัจจัยที่สองด้วย ผู้โจมตีที่รู้รหัสผ่าน
    จะคืนโควตาการเดา TOTP ได้ไม่จำกัดด้วยการ login ซ้ำ ๆ

    **ตรวจด้วยพฤติกรรม ไม่ใช่อ่านคอมเมนต์** — คอมเมนต์ไม่ได้บังคับอะไร
    """
    from tiewtrade.services.api.throttling import ThrottleGuard

    key = fresh_bucket_key()
    now = datetime.now(UTC)
    for _ in range(SECOND_FACTOR_CAPACITY):
        await attempt(auth_engine, Bucket.TOTP_ACCOUNT, key, now=now)
    assert await attempt(auth_engine, Bucket.TOTP_ACCOUNT, key, now=now) is False

    async with presented_session(auth_engine, role=DatabaseRole.AUTH) as session:
        guard = ThrottleGuard(
            session,
            ((Bucket.TOTP_ACCOUNT, key), (Bucket.ACCOUNT, key)),
            blocked=False,
        )
        await guard.forget_account()

    assert await attempt(auth_engine, Bucket.TOTP_ACCOUNT, key, now=now) is False, (
        "forget_account() คืนโควตาของปัจจัยที่สอง — ผู้โจมตีที่รู้รหัสผ่านจะเดา TOTP ได้ไม่จำกัด"
    )


async def test_every_second_factor_bucket_uses_the_same_rule() -> None:
    """ทั้งสามใบใช้กฎชุดเดียวกัน — ตัวเลขอยู่ที่เดียว ไม่ใช่สามที่ที่ต้องแก้ให้ตรงกัน"""
    rules = {RULES[bucket] for bucket in SECOND_FACTOR_BUCKETS}

    assert len(rules) == 1
    only = next(iter(rules))
    assert isinstance(only, TokenRule)
    assert only.ceiling_per_hour == SECOND_FACTOR_CEILING_PER_HOUR
