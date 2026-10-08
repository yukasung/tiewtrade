"""ค่าตั้งของเส้นทางยืนยันตัวตน (F-05)

**ค่าเริ่มต้นของการเปิดให้สมัครคือปิด** (requirements.md Q-1) — `mission.md` หัวข้อ 2
ตัดสินไว้แล้วว่าผลิตภัณฑ์เปิดให้คนทั่วไปสมัครเอง งานนี้จึงสร้างความสามารถนั้น
ส่วนการ **เปิดใช้งาน** ยังติด NC-11 (กฎหมายไทย) จึงต้องเปิดด้วยการตั้งค่าโดยเจตนา
หลักเดียวกับ "Live ต้องไม่เปิดเองโดยปริยาย"
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Final

#: ชื่อ cookie — `httpOnly` ตัวหนึ่งสำหรับ session และตัวที่อ่านได้สำหรับโทเคนกัน CSRF
SESSION_COOKIE: Final[str] = "tiewtrade_session"
CSRF_COOKIE: Final[str] = "tiewtrade_csrf"

#: cookie ของ challenge ระหว่างรหัสผ่านกับปัจจัยที่สอง (F-06)
#:
#: **แยกจาก cookie ของ session โดยเจตนา** เพื่อให้สิ่งที่ยังไม่ผ่านปัจจัยที่สอง
#: ไม่มีทางถูกตีความเป็น session ได้เลย แม้โค้ดที่ไหนพลาด
CHALLENGE_COOKIE: Final[str] = "tiewtrade_challenge"
CSRF_HEADER: Final[str] = "X-CSRF-Token"

#: header ที่พารหัสยืนยันปัจจัยที่สองของคำขอนั้น (F-06 RQ-6)
#:
#: **มาทาง header ไม่ใช่ใน body** เพราะการตัดสินสิทธิ์อยู่ที่ middleware ตัวเดียว
#: (`security.md` หัวข้อ 2) และ middleware อ่าน body ไม่ได้โดยไม่กินมันไปจาก endpoint
#: · ข้อนี้ทำให้ทุกเส้นทางที่ต้องยืนยันซ้ำใช้ทางเดียวกัน ไม่ใช่แต่ละเส้นทางคิดเอง
TOTP_HEADER: Final[str] = "X-TiewTrade-TOTP"

_SIGNUP_VARIABLE: Final[str] = "TIEWTRADE_SIGNUP_OPEN"
_COOKIE_SECURE_VARIABLE: Final[str] = "TIEWTRADE_COOKIE_SECURE"


def signup_open() -> bool:
    """เปิดให้สมัครหรือไม่ — **ไม่ตั้งค่าคือปิด**"""
    return os.environ.get(_SIGNUP_VARIABLE, "") == "1"


def cookie_secure() -> bool:
    """ตั้งธง `Secure` บน cookie หรือไม่ — **ไม่ตั้งค่าคือตั้งธง**

    ปิดได้เฉพาะตอนพัฒนาและตอนรันเทสต์ที่ใช้ `http://` ซึ่งเบราว์เซอร์และไคลเอนต์
    จะไม่ส่ง cookie ที่มีธงนี้กลับมา — บนเครื่องจริงห้ามปิด
    """
    return os.environ.get(_COOKIE_SECURE_VARIABLE, "1") != "0"


def price_origins() -> frozenset[str]:
    """Explicit browser origins; missing configuration permits no browser connection."""
    origins = frozenset(filter(None, os.environ.get("TIEWTRADE_PRICE_ORIGINS", "").split(",")))
    if any("*" in value for value in origins) or any(
        not value.startswith(("http://", "https://")) for value in origins
    ):
        raise ValueError("price origins must be explicit HTTP origins")
    return origins


def price_redis_url() -> str:
    value = os.environ.get("TIEWTRADE_REDIS_URL_API", "")
    if not value:
        raise ValueError("TIEWTRADE_REDIS_URL_API is required")
    return value


@dataclass(frozen=True, slots=True)
class PriceSettings:
    """Approved resource defaults; the three user slots remain a database contract."""

    physical_limit: int = 100
    pending_limit: int = 16
    global_attempts: int = 200
    ip_attempts: int = 30
    coordinator_interval: float = 0.5
    authorization_age: float = 1
    query_timeout: float = 0.5
    send_timeout: float = 5
    inbound_max_bytes: int = 256

    def __post_init__(self) -> None:
        if not 1 <= self.pending_limit <= self.physical_limit:
            raise ValueError("invalid process socket budgets")
        if min(self.global_attempts, self.ip_attempts, self.inbound_max_bytes) < 1:
            raise ValueError("stream limits must be positive")
        if not 0 < self.query_timeout <= 0.5 or self.send_timeout <= 0:
            raise ValueError("invalid stream deadlines")


PRICE_SETTINGS: Final[PriceSettings] = PriceSettings()
