"""FastAPI app ของระบบ

F-01 ส่งมอบเส้นทางเดียวเพื่อพิสูจน์ทางเดินถึงหน้าบ้าน · F-05 เพิ่มการยืนยันตัวตน

**ตัวตนตัดสินที่จุดเดียว** — middleware ตัวเดียวตรวจโทเคนกัน CSRF และตัวตนของทุกคำขอ
เส้นทางที่ไม่อยู่ใน `PUBLIC_ROUTES` จะถูกปฏิเสธที่นั่น ไม่ใช่ที่แต่ละ endpoint
(`security.md` หัวข้อ 2)

**หนึ่งบทบาทฐานข้อมูลหนึ่ง engine** — เส้นทางทั่วไปใช้ `api` ซึ่งแตะข้อมูลเข้าสู่ระบบ
ไม่ได้เลย ส่วนเส้นทางยืนยันตัวตนใช้ `auth` (`requirements.md` Q-8)
"""

import asyncio
import gc
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import cast

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from redis.asyncio import Redis
from starlette.responses import Response

from tiewtrade.infra.crypto import KeyPurpose, KeySource
from tiewtrade.infra.crypto.indicator_cursor import validate_keys
from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.infra.db.session import presented_session
from tiewtrade.infra.market_data.realtime_records import PriceSnapshot
from tiewtrade.infra.market_data.realtime_storage import read_snapshot
from tiewtrade.infra.realtime.admission import AdmissionRedis, RedisAdmission
from tiewtrade.infra.realtime.notifications import RedisNotifications
from tiewtrade.services.api.api_key_routes import router as api_key_router
from tiewtrade.services.api.auth_routes import router as auth_router
from tiewtrade.services.api.authentication import authenticate_request
from tiewtrade.services.api.candle_routes import router as candle_router
from tiewtrade.services.api.chart_routes import router as chart_router
from tiewtrade.services.api.indicator_admission import IndicatorBudget
from tiewtrade.services.api.indicator_routes import router as indicator_router
from tiewtrade.services.api.paper_wallet_routes import router as paper_wallet_router
from tiewtrade.services.api.price_admission import ProcessBudget
from tiewtrade.services.api.price_broadcast import PriceBroadcaster
from tiewtrade.services.api.price_guard import PriceScopeGuard
from tiewtrade.services.api.price_routes import router as price_router
from tiewtrade.services.api.safe_logging import install_query_redaction
from tiewtrade.services.api.settings import PRICE_SETTINGS, price_redis_url
from tiewtrade.services.api.throttling import AuthRejectedError
from tiewtrade.services.api.totp_routes import router as totp_router
from tiewtrade.services.api.trading_account_routes import router as trading_account_router

# Install before Uvicorn can log a request, including when lifespan is disabled.
install_query_redaction()


_heap_users = 0
_owns_frozen_heap = False


def _retain_stable_heap() -> None:
    """Keep startup objects out of latency-sensitive cyclic-GC scans."""
    global _heap_users, _owns_frozen_heap
    if _heap_users == 0 and gc.get_freeze_count() == 0:
        gc.collect()
        gc.freeze()
        _owns_frozen_heap = True
    _heap_users += 1


def _release_stable_heap() -> None:
    """Restore process GC state after the final API lifespan closes."""
    global _heap_users, _owns_frozen_heap
    _heap_users -= 1
    if _heap_users == 0 and _owns_frozen_heap:
        gc.unfreeze()
        _owns_frozen_heap = False


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """สร้าง engine ของสองบทบาทและอ่านกุญแจตอนเปิด แล้วปิดให้เรียบร้อยตอนจบ

    **อ่านกุญแจของ TOTP ที่นี่เพื่อให้กุญแจไม่ครบ = กระบวนการไม่เริ่ม** ไม่ใช่ล้ม
    ตอนมีผู้ใช้คนแรกมาเปิด TOTP (F-06 validation V-10)
    """
    # Reapply after server logging configuration/repeated application startups.
    install_query_redaction()
    app.state.api_engine = create_engine_for(DatabaseRole.API)
    app.state.paper_mutation_engine = create_engine_for(
        DatabaseRole.API, pool_size=1, max_overflow=0, pool_timeout=0.5
    )
    app.state.auth_engine = create_engine_for(DatabaseRole.AUTH)
    app.state.totp_keys = KeySource.from_environment(KeyPurpose.TOTP_SECRET)
    # **กุญแจของ API key เป็นคนละดอก** และฝั่งนี้ใช้ปิดผนึกอย่างเดียว —
    # การเปิดผนึกทำได้เฉพาะใน `engine` (`tech-stack.md` หัวข้อ 8 · F-07 RQ-4)
    app.state.venue_keys = KeySource.from_environment(KeyPurpose.VENUE_API_SECRET)
    app.state.price_engine = create_engine_for(
        DatabaseRole.API, pool_size=3, max_overflow=0, pool_timeout=0.5
    )
    redis = Redis.from_url(price_redis_url())
    app.state.indicator_keys = KeySource.from_environment(KeyPurpose.INDICATOR_CURSOR)
    validate_keys(app.state.indicator_keys, (app.state.totp_keys, app.state.venue_keys))
    app.state.indicator_engine = create_engine_for(
        DatabaseRole.API, pool_size=1, max_overflow=0, pool_timeout=0.25
    )
    app.state.indicator_budget = IndicatorBudget()
    app.state.chart_engine = create_engine_for(
        DatabaseRole.API, pool_size=1, max_overflow=0, pool_timeout=0.5
    )
    app.state.chart_admission = RedisAdmission(
        cast(AdmissionRedis, redis),
        global_limit=6000,
        ip_limit=120,
        namespace="chart.live",
        subject="user",
    )
    app.state.indicator_admission = RedisAdmission(
        cast(AdmissionRedis, redis),
        global_limit=30,
        ip_limit=6,
        namespace="market.indicator.admission",
        subject="user",
    )
    app.state.price_budget = ProcessBudget()
    app.state.price_admission = RedisAdmission(
        cast(AdmissionRedis, redis),
        global_limit=PRICE_SETTINGS.global_attempts,
        ip_limit=PRICE_SETTINGS.ip_attempts,
        timeout=PRICE_SETTINGS.query_timeout,
    )

    async def public_read() -> PriceSnapshot:
        async with asyncio.timeout(PRICE_SETTINGS.query_timeout):
            async with presented_session(app.state.price_engine) as session:
                await session.execute("SET LOCAL statement_timeout = '500ms'")
                await session.execute("SET LOCAL lock_timeout = '500ms'")
                return await read_snapshot(session)

    app.state.price_broadcaster = PriceBroadcaster(RedisNotifications(redis), public_read)
    broadcast_task = asyncio.create_task(app.state.price_broadcaster.run())
    _retain_stable_heap()
    try:
        yield
    finally:
        try:
            broadcast_task.cancel()
            await asyncio.gather(broadcast_task, return_exceptions=True)
            await redis.aclose()
            await app.state.indicator_engine.dispose()
            await app.state.chart_engine.dispose()
            await app.state.price_engine.dispose()
            await app.state.paper_mutation_engine.dispose()
            await app.state.api_engine.dispose()
            await app.state.auth_engine.dispose()
        finally:
            _release_stable_heap()


app = FastAPI(
    title="TiewTrade API",
    version="0.2.0",
    # **ไม่เอ่ยชื่อตลาดในคำอธิบาย** ด่านคำศัพท์ของ F-33 ห้ามชื่อตลาดออกนอกชั้น `venues`
    # และคำอธิบายนี้ไปโผล่ใน OpenAPI ที่หน้าบ้านอ่านด้วย
    description="เทรดคริปโตแบบ Spot — ยืนยันตัวตนด้วย session ฝั่งเซิร์ฟเวอร์",
    lifespan=lifespan,
)


app.add_middleware(PriceScopeGuard)


@app.middleware("http")
async def identify_caller(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """จุดเดียวที่ตัดสินว่าคำขอนี้เป็นของใคร และปฏิเสธเมื่อไม่มีสิทธิ์

    **ค่าเริ่มต้นคือปฏิเสธ** เส้นทางใหม่ที่ไม่ได้ประกาศว่าเป็นสาธารณะจะต้องมี session
    โดยที่คนเขียน endpoint ไม่ต้องจำอะไร
    """
    try:
        await authenticate_request(request.app.state.api_engine, request)
    except (HTTPException, AuthRejectedError) as refusal:
        return JSONResponse({"detail": refusal.detail}, status_code=refusal.status_code)
    return await call_next(request)


@app.exception_handler(AuthRejectedError)
async def refused(_: Request, rejection: AuthRejectedError) -> JSONResponse:
    """แปลง "คำขอถูกปฏิเสธตามกฎ" เป็นคำตอบ — **ที่เดียว**

    มีตัวแปลงที่ระดับแอปเพื่อให้เส้นทางที่ไม่ได้อยู่ใน `throttled()` โยนชนิดนี้ได้
    โดยไม่หลุดเป็น 500 · ถ้าต้องแปลงเองทุกที่ วันหนึ่งจะมีที่ที่ลืมแปลง
    """
    return JSONResponse({"detail": rejection.detail}, status_code=rejection.status_code)


app.include_router(auth_router)
app.include_router(totp_router)
app.include_router(api_key_router)
app.include_router(trading_account_router)
app.include_router(paper_wallet_router)
app.include_router(candle_router)
app.include_router(chart_router)
app.include_router(indicator_router)
app.include_router(price_router)


class Health(BaseModel):
    """สถานะของเซิร์ฟเวอร์ — ชนิดนี้เป็นต้นทางของชนิดข้อมูลฝั่งหน้าบ้าน"""

    status: str
    server_time: datetime
    version: str


@app.get("/health")
def read_health() -> Health:
    """คืนสถานะและเวลาของเซิร์ฟเวอร์

    หน้าบ้านใช้ endpoint นี้พิสูจน์ว่าชนิดข้อมูลสองฝั่งตรงกัน (F-01 RQ-16, RQ-17)
    """
    return Health(
        status="ok",
        server_time=datetime.now(UTC),
        version=app.version,
    )
