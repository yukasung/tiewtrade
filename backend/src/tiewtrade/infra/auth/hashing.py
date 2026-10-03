"""การแฮชรหัสผ่านด้วย argon2 (F-05 plan.md ข้อ 5)

อยู่ใน `infra` เพราะพึ่งไลบรารีข้างนอก ส่วนกฎที่คำนวณได้เองอยู่ใน
`tiewtrade.core.passwords` (`architecture.md` หัวข้อ 1)

**ค่าความแรงอยู่ที่เดียวและเป็นค่าที่เจ้าของอนุมัติ** (plan.md ข้อ 5) —
ชุดที่สองที่ RFC 9106 แนะนำ · งบเวลาประมาณ 100 มิลลิวินาทีต่อครั้ง
**แรงกว่านี้คือการทำ DoS ใส่ตัวเอง** เพราะทุกการเข้าสู่ระบบจ่ายเวลานั้น

**ข้อความข้อผิดพลาดของที่นี่ไม่เคยพารหัสผ่านหรือแฮชไปด้วย** (`security.md` หัวข้อ 4)
"""

from __future__ import annotations

import secrets
from functools import cache
from typing import Final

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from tiewtrade.core.passwords import normalised
from tiewtrade.infra.db.errors import InfraError

#: ค่าความแรงที่อนุมัติไว้ — เปลี่ยนแล้วต้องแก้ `validation.md` V-30.1 ด้วย
TIME_COST: Final[int] = 3
MEMORY_COST_KIB: Final[int] = 65536
PARALLELISM: Final[int] = 4
HASH_LENGTH: Final[int] = 32
SALT_LENGTH: Final[int] = 16

_HASHER: Final = PasswordHasher(
    time_cost=TIME_COST,
    memory_cost=MEMORY_COST_KIB,
    parallelism=PARALLELISM,
    hash_len=HASH_LENGTH,
    salt_len=SALT_LENGTH,
)


class StoredHashUnreadableError(InfraError):
    """แฮชที่เก็บไว้อ่านไม่ออก — ข้อมูลของเราเสีย ไม่ใช่รหัสผ่านผิด

    แยกจาก "รหัสผ่านไม่ตรง" เพราะผลที่ต้องทำต่างกันคนละเรื่อง: ข้อนี้ต้องมีคนมาดู
    ส่วนรหัสผ่านไม่ตรงเป็นเรื่องปกติของหน้าเข้าสู่ระบบ
    """

    code = "STORED_HASH_UNREADABLE"


def hash_password(password: str) -> str:
    """แฮชรหัสผ่านที่ผ่านกฎแล้ว

    ผู้เรียกต้องส่งค่าที่ผ่าน `acceptable_new_password()` มาแล้ว — ที่นี่ normalise
    อีกครั้งเพราะการแฮชค่าที่ยังไม่ normalise ทำให้เข้าสู่ระบบด้วยรูปอื่นไม่ได้
    """
    return _HASHER.hash(normalised(password))


def password_matches(stored_hash: str, password: str) -> bool:
    """รหัสผ่านตรงกับแฮชที่เก็บไว้หรือไม่

    **ไม่ตรวจความยาวและไม่ตรวจรายการที่ห้าม** — รหัสผ่านที่ตั้งไว้ก่อนกฎเปลี่ยน
    ต้องยังเข้าสู่ระบบได้เพื่อไปเปลี่ยนรหัสผ่าน (plan.md ข้อ 5)
    """
    try:
        return _HASHER.verify(stored_hash, normalised(password))
    except VerifyMismatchError:
        return False
    except (InvalidHashError, UnicodeError):
        # `UnicodeError` เกิดเมื่อค่าที่เก็บไว้ไม่ใช่แฮชของ argon2 เลย (เช่นมีอักขระ
        # นอก ASCII) ซึ่งไลบรารีโยนก่อนจะได้ตรวจรูปแบบ — ถ้าไม่ดักที่นี่
        # ข้อผิดพลาดนั้นจะหลุดสัญญาออกไปเป็นชนิดที่ผู้เรียกไม่รู้จัก
        raise StoredHashUnreadableError("แฮชที่เก็บไว้อ่านไม่ออก") from None
    except VerificationError:
        return False


def spend_matching_time() -> None:
    """ใช้เวลาเท่าการตรวจรหัสผ่านหนึ่งครั้ง โดยไม่มีบัญชีให้ตรวจ

    เรียกเมื่อ **ไม่พบอีเมล** เพื่อให้เวลาตอบของสองกรณีไม่ต่างกันอย่างมีนัย
    ถ้าตอบกลับทันที ข้อความที่เหมือนกันก็ไร้ความหมาย เพราะเวลาบอกได้ว่าบัญชีมีอยู่
    (RQ-8, validation V-33.1)
    """
    try:
        _HASHER.verify(_dummy_hash(), _UNMATCHED)
    except (VerifyMismatchError, VerificationError):
        return


#: ค่าที่ไม่มีทางตรงกับแฮชหลอก — ทำให้ `verify` ทำงานครบเหมือนตอนรหัสผ่านผิดจริง
_UNMATCHED: Final[str] = "\u0000ไม่ใช่รหัสผ่านของใคร\u0000"


@cache
def _dummy_hash() -> str:
    """แฮชของค่าสุ่มที่ไม่มีใครรู้ — คิดครั้งเดียวตอนใช้ครั้งแรก

    สุ่มใหม่ทุกครั้งที่กระบวนการเริ่ม จึงไม่เป็นค่าคงที่ใน repo ให้ใครเอาไปเทียบ
    """
    return _HASHER.hash(secrets.token_urlsafe(32))
