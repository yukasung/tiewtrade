"""รายการรหัสผ่านที่ห้ามใช้ (F-05 plan.md ข้อ 5)

NIST SP 800-63B-4 กำหนดให้เทียบรหัสผ่านใหม่กับรายการที่พบบ่อยหรือที่เคยรั่ว
**เฉพาะตอนสร้างหรือเปลี่ยน** ไม่ใช่ตอนยืนยัน — ถ้าเทียบตอนยืนยันด้วย วันที่รายการ
อัปเดตแล้วรหัสผ่านเดิมของผู้ใช้ติดอยู่ในรายการ ผู้ใช้จะเข้าสู่ระบบไม่ได้และ
เปลี่ยนรหัสผ่านก็ไม่ได้ ซึ่งในงานนี้ไม่มีทางกู้บัญชีเลย (Q-6)

**เก็บเป็นแฮช ไม่ใช่รหัสผ่านต้นฉบับ** เพื่อไม่ให้ repo กลายเป็นคลังรหัสผ่าน
ที่มาและรุ่นของรายการอยู่ใน `password_blocklist/manifest.json` และอัปเดตด้วย
`scripts/refresh_password_blocklist.py` ที่คนสั่งเอง
"""

from __future__ import annotations

import hashlib
import json
from functools import cache
from pathlib import Path
from typing import Final

from tiewtrade.core.passwords import normalised
from tiewtrade.infra.db.errors import InfraError

_DIRECTORY: Final = Path(__file__).parent / "password_blocklist"
_HASHES: Final = _DIRECTORY / "hashes.txt"
_MANIFEST: Final = _DIRECTORY / "manifest.json"

#: ช่องที่ไฟล์กำกับต้องมีครบ — "มีรายการแล้ว" ไม่ได้แปลว่าตรงมาตรฐาน (validation V-28)
MANIFEST_FIELDS: Final[tuple[str, ...]] = (
    "source_url",
    "source_commit",
    "retrieved_on",
    "source_entries",
    "kept_entries",
    "licence",
)


class BlocklistUnavailableError(InfraError):
    """อ่านรายการที่ห้ามไม่ได้ — **ห้ามถือว่ารหัสผ่านผ่าน**

    รายการที่อ่านไม่ได้แล้วปล่อยผ่านคือการปิดการตรวจเงียบ ๆ ซึ่งแย่กว่าการดัง
    """

    code = "PASSWORD_BLOCKLIST_UNAVAILABLE"


def digest_of(password: str) -> str:
    """แฮชของรหัสผ่านในรูปที่รายการเก็บ — **normalise ก่อนแฮชเสมอ**

    ขั้นตอนนี้ต้องเหมือนกับที่สคริปต์ใช้ตอนสร้างรายการ มิฉะนั้นรหัสผ่านเดียวกัน
    จะได้แฮชต่างกันแล้วการตรวจก็ไม่มีผล
    """
    return hashlib.sha256(normalised(password).encode("utf-8")).hexdigest()


@cache
def blocked_digests() -> frozenset[str]:
    """แฮชทั้งหมดในรายการ — อ่านไฟล์ครั้งเดียวต่อกระบวนการ"""
    try:
        lines = _HASHES.read_text(encoding="utf-8").split()
    except OSError as error:
        raise BlocklistUnavailableError("อ่านไฟล์รายการรหัสผ่านที่ห้ามไม่ได้") from error
    return frozenset(lines)


@cache
def manifest() -> dict[str, object]:
    """ที่มาและรุ่นของรายการ"""
    try:
        loaded = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    except OSError as error:
        raise BlocklistUnavailableError("อ่านไฟล์กำกับรายการรหัสผ่านที่ห้ามไม่ได้") from error
    if not isinstance(loaded, dict):
        raise BlocklistUnavailableError("ไฟล์กำกับรายการรหัสผ่านที่ห้ามผิดรูป")
    return {str(key): value for key, value in loaded.items()}


def is_blocked(password: str) -> bool:
    """รหัสผ่านนี้อยู่ในรายการที่ห้ามหรือไม่ — ใช้เฉพาะตอนรับรหัสผ่านใหม่"""
    return digest_of(password) in blocked_digests()
