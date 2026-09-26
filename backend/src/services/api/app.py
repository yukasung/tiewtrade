"""FastAPI app ของ F-01 — มี endpoint เดียวเพื่อพิสูจน์ทางเดินถึงหน้าบ้าน

ยังไม่มีตรรกะธุรกิจ ไม่แตะเงิน ไม่ต่อตลาด (ขอบเขต F-01)
"""

from datetime import UTC, datetime

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(
    title="TiewTrade API",
    version="0.1.0",
    description="โครงเริ่มต้น F-01 ยังไม่มีความสามารถด้านการเทรด",
)


class Health(BaseModel):
    """สถานะของเซิร์ฟเวอร์ — ชนิดนี้เป็นต้นทางของชนิดข้อมูลฝั่งหน้าบ้าน"""

    status: str
    server_time: datetime
    version: str


@app.get("/health")
def read_health() -> Health:
    """คืนสถานะและเวลาของเซิร์ฟเวอร์

    หน้าบ้านใช้ endpoint นี้พิสูจน์ว่าชนิดข้อมูลสองฝั่งตรงกัน (RQ-16, RQ-17)
    """
    return Health(
        status="ok",
        server_time=datetime.now(UTC),
        version=app.version,
    )
