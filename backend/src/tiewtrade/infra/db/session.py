"""ทางเข้าฐานข้อมูล — ระบุตัวผู้ใช้ทุกครั้ง ลืมไม่ได้เพราะไม่มีทางลืม (plan.md ข้อ 7)

สองชนิดที่ **ไม่สืบทอดกัน** เพื่อให้เอาไปใช้สลับกันไม่ได้:

- `UserSession` — งานของผู้ใช้รายเดียว อยู่ใต้ RLS
- `ScanSession` — งานกวาดรายการข้ามผู้ใช้ **ข้าม RLS** อ่านอย่างเดียว (Q-3)

ไม่มี API ที่คืน connection ดิบ เพราะ connection ดิบคือทางที่ลืมระบุผู้ใช้ได้
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from typing import Any, Final
from uuid import UUID

from sqlalchemy import Result, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine
from sqlalchemy.pool import PoolProxiedConnection

from tiewtrade.infra.db.engine import ROLES_UNDER_RLS, DatabaseRole
from tiewtrade.infra.db.errors import (
    DatabaseRoleError,
    DatabaseTimeoutError,
    SessionKindError,
    translate_database_error,
)

#: ชื่อตัวแปรที่ policy ของทุกตารางอ่าน ประกาศไว้ที่เดียว
CURRENT_USER_SETTING: Final[str] = "tiewtrade.current_user_id"

#: ตัวแปรสำหรับช่วง **ก่อนรู้ว่าเป็นผู้ใช้คนไหน** (F-05) — policy ของ `sessions`
#: และ `user_credentials` อ่านสองตัวนี้
#:
#: **เก็บแฮชของโทเคน ไม่ใช่โทเคนจริง** ฐานข้อมูลจึงไม่เคยเห็นโทเคนเลย
PRESENTED_TOKEN_SETTING: Final[str] = "tiewtrade.presented_token_hash"
PRESENTED_EMAIL_SETTING: Final[str] = "tiewtrade.presented_email"

_ROLE_FACTS = text(
    """
    SELECT current_user AS role_name,
           r.rolsuper AS is_superuser,
           r.rolbypassrls AS bypasses_rls
    FROM pg_roles AS r
    WHERE r.rolname = current_user
    """
)

# `set_config(..., is_local => true)` คือ SET LOCAL ในรูปที่ส่งค่าแบบ bind ได้
# ต้องเป็น LOCAL เท่านั้น: ค่าหมดอายุเมื่อ transaction จบ จึงไม่ค้างไปถึงผู้ใช้
# คนถัดไปที่ได้ connection เดิมจาก pool (Q-2 เงื่อนไข ข)
_SET_LOCAL = text("SELECT set_config(:setting, :value, true)")


async def _execute(
    connection: AsyncConnection, statement: str, parameters: Mapping[str, object] | None
) -> Result[Any]:
    try:
        return await connection.execute(text(statement), dict(parameters or {}))
    except SQLAlchemyError as error:
        raise translate_database_error(error) from None


@dataclass(frozen=True, slots=True)
class UserSession:
    """งานของผู้ใช้รายเดียว — ทุก query อยู่ใต้ RLS ของผู้ใช้คนนี้"""

    _connection: AsyncConnection
    user_id: UUID

    async def execute(
        self, statement: str, parameters: Mapping[str, object] | None = None
    ) -> Result[Any]:
        """สั่ง query ในขอบเขตของผู้ใช้คนนี้"""
        return await _execute(self._connection, statement, parameters)


@dataclass(frozen=True, slots=True)
class PresentedSession:
    """ช่วงก่อนรู้ว่าเป็นผู้ใช้คนไหน — เห็นได้เท่าที่ **ของที่ผู้เรียกพามา** เปิดให้ (F-05)

    มีอยู่เพราะสองงานต้องทำก่อนรู้ตัวตน: หาเจ้าของ session จากแฮชโทเคน และหา
    ข้อมูลเข้าสู่ระบบจากอีเมล · **ไม่ตั้งตัวแปร = อ่านศูนย์แถว** จึงพลาดแบบปิดประตู

    `assume_user()` ทำให้ transaction เดียวกันเดินต่อในฐานะผู้ใช้ที่ตรวจแล้วได้
    ซึ่งจำเป็นสองที่: การล็อกแถวข้อมูลเข้าสู่ระบบ (ต้องผ่าน policy ของ `UPDATE`
    ที่ต้องการผู้ใช้ปัจจุบัน) และการรับคำขอต่อหลังตรวจ session ผ่าน
    """

    _connection: AsyncConnection

    async def execute(
        self, statement: str, parameters: Mapping[str, object] | None = None
    ) -> Result[Any]:
        """สั่ง query ในขอบเขตของสิ่งที่ผู้เรียกพามา"""
        return await _execute(self._connection, statement, parameters)

    async def assume_user(self, user_id: UUID) -> UserSession:
        """เดินต่อใน transaction เดิมในฐานะผู้ใช้ที่ตรวจตัวตนแล้ว

        **ผู้เรียกต้องตรวจตัวตนมาก่อนแล้ว** — ฟังก์ชันนี้ไม่ตรวจอะไร มันเพียงตั้ง
        ผู้ใช้ปัจจุบันให้ policy ของตารางอื่นทำงานได้ (F-03 Q-2)
        """
        try:
            await self._connection.execute(
                _SET_LOCAL,
                {"setting": CURRENT_USER_SETTING, "value": str(user_id)},
            )
        except SQLAlchemyError as error:
            raise translate_database_error(error) from None
        return UserSession(self._connection, user_id)


@dataclass(frozen=True, slots=True)
class ScanSession:
    """งานกวาดรายการข้ามผู้ใช้ — **ข้าม RLS** ใช้ได้กับงานจัดคิวเท่านั้น

    บทบาทที่อยู่ข้างหลังนี้ไม่มีสิทธิ์เขียนข้อมูลผู้ใช้และไม่มีสิทธิ์อ่านคอลัมน์ secret
    ฉะนั้นแม้โค้ดพลาด ความเสียหายก็ถูกจำกัดด้วยสิทธิ์ของฐานข้อมูลเอง
    """

    _connection: AsyncConnection

    async def execute(
        self, statement: str, parameters: Mapping[str, object] | None = None
    ) -> Result[Any]:
        """สั่ง query แบบข้าม RLS"""
        return await _execute(self._connection, statement, parameters)


@dataclass(frozen=True, slots=True)
class MarketDataSession:
    """Public market observations and ingestion metadata only."""

    _connection: AsyncConnection

    async def execute(
        self, statement: str, parameters: Mapping[str, object] | None = None
    ) -> Result[Any]:
        return await _execute(self._connection, statement, parameters)


@asynccontextmanager
async def market_data_session(engine: AsyncEngine) -> AsyncIterator[MarketDataSession]:
    async with _begin(engine) as connection:
        await _assert_role(connection, DatabaseRole.MARKET_DATA)
        yield MarketDataSession(connection)


def require_market_data_session(candidate: object) -> MarketDataSession:
    if isinstance(candidate, MarketDataSession):
        return candidate
    raise SessionKindError("market data requires MarketDataSession")


async def _assert_role(connection: AsyncConnection, expected: DatabaseRole) -> None:
    """ตรวจว่าที่ปลายสายคือบทบาทที่ขอจริง ก่อนแตะข้อมูลใด ๆ

    ถ้า URL ถูกตั้งสลับกัน งานรายผู้ใช้อาจไปวิ่งอยู่บนบทบาทที่ข้าม RLS
    ซึ่งเป็นความผิดที่เงียบที่สุดของการออกแบบนี้ จึงต้องดังตรงนี้ (Q-3, RQ-5.1)
    """
    try:
        row = (await connection.execute(_ROLE_FACTS)).one()
    except SQLAlchemyError as error:
        raise translate_database_error(error) from None

    role_name, is_superuser, bypasses_rls = row
    if role_name != expected.role_name:
        raise DatabaseRoleError(
            f"ต่อฐานข้อมูลด้วยบทบาทอื่น ไม่ใช่ {expected.role_name} — ตรวจ {expected.url_variable}"
        )
    if is_superuser:
        raise DatabaseRoleError(f"บทบาท {expected.role_name} เป็น superuser ซึ่งห้ามตาม RQ-5.1")
    if (
        expected in ROLES_UNDER_RLS
        or expected in {DatabaseRole.MARKET_DATA, DatabaseRole.INDICATOR_BUILDER}
    ) and bypasses_rls:
        raise DatabaseRoleError(f"บทบาท {expected.role_name} ข้าม RLS ได้ จึงใช้กับงานของผู้ใช้ไม่ได้")
    if expected is DatabaseRole.ENGINE_SCAN and not bypasses_rls:
        raise DatabaseRoleError(f"บทบาท {expected.role_name} ต้องข้าม RLS ได้ เพราะงานกวาดอ่านข้ามผู้ใช้")


@asynccontextmanager
async def _begin(
    engine: AsyncEngine, *, cleanup_seconds: float | None = None
) -> AsyncIterator[AsyncConnection]:
    """เปิด transaction แล้วแปลงข้อผิดพลาดทุกชนิดตอนต่อและตอนปิดให้เป็นชนิดของเรา

    ครอบตั้งแต่ **ตอนขอ connection** ไม่ใช่แค่ตอน query เพราะข้อผิดพลาดตอนต่อ
    (รหัสผ่านผิด ต่อไม่ติด) พา URL และรหัสผ่านติดมาใน traceback ของ driver
    ซึ่งเป็นสิ่งที่ `security.md` หัวข้อ 4 ห้ามไว้

    จับ `OSError` ด้วย ไม่ใช่แค่ข้อผิดพลาดของ SQLAlchemy เพราะการต่อพอร์ตที่ปิดอยู่
    โยน `ConnectionRefusedError` ขึ้นมาตรง ๆ ถ้าไม่จับ ผู้เรียกที่ดัก `InfraError`
    จะรับมือกรณี "ฐานข้อมูลล่ม" ไม่ได้เลย ซึ่งเป็นกรณีที่ต้องรับมือได้ที่สุด

    ข้อผิดพลาดที่เกิด **ในตัวงานของผู้เรียก** ไม่ถูกแปลง — ของจาก query ถูกแปลง
    ที่ `execute` ไปแล้ว และของอื่นเป็นเรื่องของผู้เรียก ไม่ใช่ของชั้นนี้
    """
    transaction = engine.begin()
    try:
        connection = await transaction.__aenter__()
    except (SQLAlchemyError, OSError) as error:
        raise translate_database_error(error) from None

    assert connection.sync_connection is not None
    raw = connection.sync_connection.connection if cleanup_seconds is not None else None
    try:
        yield connection
    except BaseException as error:
        # ปิด transaction ให้เรียบร้อยก่อนส่งข้อผิดพลาดของผู้เรียกต่อ
        # ถ้าการ rollback ล้มเหลวด้วย ให้ข้อผิดพลาดตัวแรกชนะ เพราะมันบอกสาเหตุจริง
        # ส่วนความล้มเหลวของ rollback เป็นผลพลอยได้ของสาเหตุนั้น
        with suppress(SQLAlchemyError, OSError):
            if cleanup_seconds is None:
                await transaction.__aexit__(type(error), error, error.__traceback__)
            else:
                cleanup = asyncio.create_task(
                    transaction.__aexit__(type(error), error, error.__traceback__)
                )
                # Preserve the original failure, especially deadline cancellation.
                with suppress(DatabaseTimeoutError):
                    assert raw is not None
                    await _bounded_cleanup(connection, raw, cleanup, cleanup_seconds)
        raise
    try:
        if cleanup_seconds is None:
            await transaction.__aexit__(None, None, None)
        else:
            assert raw is not None
            cleanup = asyncio.create_task(transaction.__aexit__(None, None, None))
            await _bounded_cleanup(connection, raw, cleanup, cleanup_seconds)
    except (SQLAlchemyError, OSError) as error:
        raise translate_database_error(error) from None


async def _bounded_cleanup(
    connection: AsyncConnection,
    raw: PoolProxiedConnection,
    cleanup: asyncio.Task[Any],
    seconds: float,
) -> None:
    """Bound graceful close, then quarantine and synchronously abort asyncpg.

    As in indicator_source_session, abort uses the saved driver, never a new
    checkout. ORM bookkeeping cannot retain a live transport after this point.
    """
    driver = raw.driver_connection
    abort_join_seconds = 0.05
    try:
        await asyncio.wait_for(asyncio.shield(cleanup), max(0, seconds - 2 * abort_join_seconds))
        return
    except (TimeoutError, asyncio.CancelledError) as error:
        # Detach before abort: even stalled invalidation cannot return this
        # physical connection to another caller through the pool.
        if raw.driver_connection is driver and driver is not None:
            raw.detach()
            driver.terminate()
        cleanup.cancel()
        discard = asyncio.create_task(connection.invalidate())
        tasks = {cleanup, discard}
        try:
            await asyncio.wait(tasks, timeout=abort_join_seconds)
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
                task.add_done_callback(_consume_cleanup_result)
        await asyncio.wait(tasks, timeout=abort_join_seconds)
        if isinstance(error, asyncio.CancelledError):
            raise
        raise DatabaseTimeoutError("indicator transaction cleanup failed") from None


def _consume_cleanup_result(task: asyncio.Task[Any]) -> None:
    if not task.cancelled():
        task.exception()


@asynccontextmanager
async def user_session(
    engine: AsyncEngine, user_id: UUID, *, role: DatabaseRole = DatabaseRole.API
) -> AsyncIterator[UserSession]:
    """เปิด transaction ที่ผูกกับผู้ใช้คนหนึ่ง

    **ไม่มีทางได้ session ของผู้ใช้โดยไม่ระบุตัวผู้ใช้** — ตัวผู้ใช้เป็นพารามิเตอร์บังคับ
    """
    if role not in ROLES_UNDER_RLS:
        raise DatabaseRoleError(f"บทบาท {role.role_name} ไม่ใช่บทบาทที่ทำงานใต้ RLS")

    async with _begin(engine) as connection:
        await _assert_role(connection, role)
        try:
            await connection.execute(
                _SET_LOCAL,
                {"setting": CURRENT_USER_SETTING, "value": str(user_id)},
            )
        except SQLAlchemyError as error:
            raise translate_database_error(error) from None
        yield UserSession(connection, user_id)


@asynccontextmanager
async def indicator_read_session(engine: AsyncEngine, user_id: UUID) -> AsyncIterator[UserSession]:
    """F-11 snapshot: transaction characteristics precede every SELECT."""
    async with _begin(engine, cleanup_seconds=2) as connection:
        await _execute(
            connection, "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY", None
        )
        await _assert_role(connection, DatabaseRole.API)
        await _execute(
            connection,
            "SELECT set_config(:setting, :value, true)",
            {"setting": CURRENT_USER_SETTING, "value": str(user_id)},
        )
        yield UserSession(connection, user_id)


@asynccontextmanager
async def repeatable_user_session(engine: AsyncEngine, user_id: UUID) -> AsyncIterator[UserSession]:
    """Owner-scoped repeatable-read snapshot for multi-statement financial reads."""
    async with _begin(engine) as connection:
        await _execute(
            connection,
            "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY",
            None,
        )
        await _assert_role(connection, DatabaseRole.API)
        await _execute(
            connection,
            "SELECT set_config(:setting, :value, true)",
            {"setting": CURRENT_USER_SETTING, "value": str(user_id)},
        )
        yield UserSession(connection, user_id)


@asynccontextmanager
async def presented_session(
    engine: AsyncEngine,
    *,
    token_hash: str | None = None,
    email: str | None = None,
    role: DatabaseRole = DatabaseRole.API,
) -> AsyncIterator[PresentedSession]:
    """เปิด transaction สำหรับช่วงก่อนรู้ว่าเป็นผู้ใช้คนไหน (F-05)

    ตั้งเฉพาะตัวแปรที่ผู้เรียกส่งมา — ไม่ส่งเลยก็เปิดได้ แต่จะอ่านอะไรไม่ได้
    ซึ่งเป็นพฤติกรรมที่ต้องการ: สิทธิ์มาจากของที่พามา ไม่ใช่จากการเปิด session

    ค่าหมดอายุเมื่อ transaction จบ (`set_config(..., is_local => true)`)
    จึงไม่ค้างไปถึงผู้ใช้คนถัดไปที่ได้ connection เดิมจาก pool
    """
    if role not in ROLES_UNDER_RLS:
        raise DatabaseRoleError(f"บทบาท {role.role_name} ไม่ใช่บทบาทที่ทำงานใต้ RLS")

    async with _begin(engine) as connection:
        await _assert_role(connection, role)
        for setting, value in (
            (PRESENTED_TOKEN_SETTING, token_hash),
            (PRESENTED_EMAIL_SETTING, email),
        ):
            if value is None:
                continue
            try:
                await connection.execute(_SET_LOCAL, {"setting": setting, "value": value})
            except SQLAlchemyError as error:
                raise translate_database_error(error) from None
        yield PresentedSession(connection)


@asynccontextmanager
async def scan_session_bypassing_rls(engine: AsyncEngine) -> AsyncIterator[ScanSession]:
    """เปิด session ของงานกวาดรายการข้ามผู้ใช้

    ชื่อฟังก์ชันบอกตรง ๆ ว่าข้าม RLS เพื่อให้เห็นตอนรีวิวว่าโค้ดตรงไหนใช้ทางนี้
    (Q-3 เงื่อนไข ค)
    """
    async with _begin(engine) as connection:
        await _assert_role(connection, DatabaseRole.ENGINE_SCAN)
        yield ScanSession(connection)


def require_user_session(candidate: object) -> UserSession:
    """ตัวตรวจกลางของทุกเส้นทางที่แตะข้อมูลของผู้ใช้

    อยู่ที่เดียวเพื่อไม่ให้แต่ละ repository เขียนเงื่อนไขของตัวเอง แล้วลืมทีละที่
    (`standards/security.md` หัวข้อ 2 — ตรวจสิทธิ์ที่จุดเดียว)
    """
    if isinstance(candidate, UserSession):
        return candidate
    raise SessionKindError(f"เส้นทางของผู้ใช้รับเฉพาะ UserSession ไม่รับ {type(candidate).__name__}")
