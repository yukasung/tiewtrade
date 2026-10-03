"""FastAPI app ของระบบ

F-01 ส่งมอบเส้นทางเดียวเพื่อพิสูจน์ทางเดินถึงหน้าบ้าน · F-05 เพิ่มการยืนยันตัวตน

**ตัวตนตัดสินที่จุดเดียว** — middleware ตัวเดียวตรวจโทเคนกัน CSRF และตัวตนของทุกคำขอ
เส้นทางที่ไม่อยู่ใน `PUBLIC_ROUTES` จะถูกปฏิเสธที่นั่น ไม่ใช่ที่แต่ละ endpoint
(`security.md` หัวข้อ 2)

**หนึ่งบทบาทฐานข้อมูลหนึ่ง engine** — เส้นทางทั่วไปใช้ `api` ซึ่งแตะข้อมูลเข้าสู่ระบบ
ไม่ได้เลย ส่วนเส้นทางยืนยันตัวตนใช้ `auth` (`requirements.md` Q-8)
"""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.responses import Response

from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.services.api.auth_routes import router as auth_router
from tiewtrade.services.api.authentication import authenticate_request


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """สร้าง engine ของสองบทบาทตอนเปิด และปิดให้เรียบร้อยตอนจบ"""
    app.state.api_engine = create_engine_for(DatabaseRole.API)
    app.state.auth_engine = create_engine_for(DatabaseRole.AUTH)
    try:
        yield
    finally:
        await app.state.api_engine.dispose()
        await app.state.auth_engine.dispose()


app = FastAPI(
    title="TiewTrade API",
    version="0.2.0",
    # **ไม่เอ่ยชื่อตลาดในคำอธิบาย** ด่านคำศัพท์ของ F-33 ห้ามชื่อตลาดออกนอกชั้น `venues`
    # และคำอธิบายนี้ไปโผล่ใน OpenAPI ที่หน้าบ้านอ่านด้วย
    description="เทรดคริปโตแบบ Spot — ยืนยันตัวตนด้วย session ฝั่งเซิร์ฟเวอร์",
    lifespan=lifespan,
)


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
    except HTTPException as refusal:
        return JSONResponse({"detail": refusal.detail}, status_code=refusal.status_code)
    return await call_next(request)


app.include_router(auth_router)


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
