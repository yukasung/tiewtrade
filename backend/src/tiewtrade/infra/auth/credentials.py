"""ข้อมูลเข้าสู่ระบบในฐานข้อมูล (F-05 plan.md ข้อ 1.2, 1.6)

**บทบาท `tiewtrade_auth` เท่านั้นที่แตะตารางนี้ได้** และ policy เปิดให้เห็น
ทีละอีเมลที่ระบุ หรือแถวของผู้ใช้ปัจจุบัน — `SELECT` ครั้งเดียว dump ทั้งตารางไม่ได้

**ลำดับการล็อกมีข้อบังคับที่มองจากภายนอกไม่เห็น** `SELECT ... FOR UPDATE` ต้องผ่าน
policy ของ `UPDATE` ด้วย ซึ่งต้องการผู้ใช้ปัจจุบัน ตอนเข้าสู่ระบบเรารู้แค่อีเมล
**การล็อกจึงได้ศูนย์แถวโดยไม่มีข้อผิดพลาด** (ทดลองกับ PostgreSQL 16 แล้ว)
ลำดับที่ใช้ได้มีสามขั้น: `owner_of_email()` → `assume_user()` → `locked_hash()`
"""

from __future__ import annotations

from uuid import UUID

from tiewtrade.infra.db.session import PresentedSession, UserSession

_OWNER_OF_EMAIL = """
SELECT user_id
FROM user_credentials
WHERE email = :email
"""

# อ่านซ้ำใต้ล็อก — **ห้ามใช้ค่าจากขั้นแรก** เพราะอาจเก่าไปแล้ว
_LOCKED_HASH = """
SELECT password_hash
FROM user_credentials
WHERE user_id = :user_id
FOR UPDATE
"""

_INSERT = """
INSERT INTO user_credentials (user_id, email, password_hash)
VALUES (:user_id, :email, :password_hash)
"""

_REPLACE_HASH = """
UPDATE user_credentials
SET password_hash = :password_hash, updated_at = now()
WHERE user_id = :user_id
"""


async def owner_of_email(session: PresentedSession, email: str) -> UUID | None:
    """เจ้าของอีเมลนี้ — **ยังไม่ได้ตรวจรหัสผ่าน** จึงยังไม่ใช่การยืนยันตัวตน

    ต้องตั้งตัวแปรอีเมลไว้ก่อนเปิด session มิฉะนั้น policy กรองทุกแถวออกและได้ `None`
    ซึ่งแยกจาก "ไม่มีบัญชีนี้" ไม่ได้ — เป็นเหตุผลที่ `presented_session()`
    รับอีเมลเป็นพารามิเตอร์ ไม่ใช่ให้ตั้งทีหลัง
    """
    row = (await session.execute(_OWNER_OF_EMAIL, {"email": email})).one_or_none()
    if row is None:
        return None
    (found,) = tuple(row)
    if not isinstance(found, UUID):
        raise TypeError("ฐานข้อมูลคืนชนิดข้อมูลที่ไม่คาดไว้สำหรับ user_credentials.user_id")
    return found


async def locked_hash(session: UserSession, user_id: UUID) -> str | None:
    """แฮชรหัสผ่านของผู้ใช้ปัจจุบัน **ใต้ล็อกของแถว**

    ล็อกไว้เพื่อให้การเข้าสู่ระบบและการเปลี่ยนรหัสผ่านเข้าคิวกัน ไม่ใช่แข่งกัน
    (RQ-22)
    """
    row = (await session.execute(_LOCKED_HASH, {"user_id": str(user_id)})).one_or_none()
    if row is None:
        return None
    (found,) = tuple(row)
    if not isinstance(found, str):
        raise TypeError("ฐานข้อมูลคืนชนิดข้อมูลที่ไม่คาดไว้สำหรับ user_credentials.password_hash")
    return found


async def create_credential(
    session: UserSession, user_id: UUID, *, email: str, password_hash: str
) -> None:
    """เพิ่มข้อมูลเข้าสู่ระบบของผู้ใช้ที่เพิ่งสร้าง

    อยู่ใน transaction เดียวกับการสร้างผู้ใช้ — ล้มเหลวแล้วต้องไม่เหลือผู้ใช้
    ที่เข้าสู่ระบบไม่ได้ (plan.md ข้อ 1.7)
    """
    await session.execute(
        _INSERT,
        {"user_id": str(user_id), "email": email, "password_hash": password_hash},
    )


async def replace_password_hash(session: UserSession, user_id: UUID, *, password_hash: str) -> None:
    """เปลี่ยนแฮชรหัสผ่าน — ต้องเรียกหลังล็อกแถวแล้วเท่านั้น"""
    await session.execute(_REPLACE_HASH, {"user_id": str(user_id), "password_hash": password_hash})
