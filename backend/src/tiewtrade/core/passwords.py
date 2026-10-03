"""กฎของรหัสผ่านที่คำนวณได้โดยไม่ต้องรู้จักอะไรข้างนอก (F-05)

อยู่ใน `core` เพราะเป็นกฎที่ต้องให้ผลเหมือนกันทุกครั้งและทุกที่ — การแฮช การอ่านไฟล์
รายการที่ห้าม และฐานข้อมูล อยู่ใน `infra` ตาม `architecture.md` หัวข้อ 1

**แยกสองเรื่องที่รวมกันแล้วล็อกเจ้าของออกจากบัญชีได้**
(`requirements.md` Q-9, plan.md ข้อ 5):

- `acceptable_new_password()` — ใช้ตอน **รับรหัสผ่านใหม่** (สมัคร, เปลี่ยนรหัสผ่าน)
  ตรวจความยาวครบ
- `normalised()` — ใช้ตอน **ตรวจรหัสผ่านที่มีอยู่** (เข้าสู่ระบบ, ยืนยันค่าเดิม)
  **ไม่ตรวจความยาวและไม่ตรวจรายการที่ห้าม** เพราะรหัสผ่านที่ตั้งไว้ก่อนกฎเปลี่ยน
  หรือที่ถูกเพิ่มเข้ารายการภายหลัง ต้องยังเข้าสู่ระบบได้เพื่อไปเปลี่ยนรหัสผ่าน
  — งานนี้ไม่มีทางกู้บัญชีเลย (Q-6)

ขั้นต่ำ 15 ตัวอักษรมาจาก `security.md` หัวข้อ 1 ซึ่งอ้าง NIST SP 800-63B-4 ที่กำหนด
ขั้นต่ำนี้ **เมื่อรหัสผ่านเป็นปัจจัยเดียว** — ลดลงได้เมื่อ F-06 บังคับ TOTP แล้ว
"""

from __future__ import annotations

import unicodedata
from typing import Final, Literal

#: ขั้นต่ำเมื่อรหัสผ่านเป็นปัจจัยเดียว (`security.md` หัวข้อ 1)
MINIMUM_LENGTH: Final[int] = 15

#: เพดานมีไว้กันการใช้ต้นทุนของการแฮชถล่มเซิร์ฟเวอร์ ไม่ใช่กันผู้ใช้
MAXIMUM_LENGTH: Final[int] = 1024

#: รูปแบบที่ normalise — NFC ตามที่ NIST ระบุ **ไม่ใช่ NFKC** ซึ่งเปลี่ยนความหมาย
#: ของอักขระบางตัว (เช่น ตัวยกกลายเป็นตัวปกติ) และทำให้รหัสผ่านที่ต่างกันชนกัน
NORMALISATION_FORM: Final[Literal["NFC"]] = "NFC"


class PasswordPolicyError(Exception):
    """รหัสผ่านใหม่ไม่ผ่านกฎ — ข้อความบอกกฎที่ไม่ผ่าน **ไม่เคยพารหัสผ่านไปด้วย**"""


def normalised(password: str) -> str:
    """รหัสผ่านในรูปมาตรฐาน — ใช้ทั้งตอนตั้งและตอนตรวจ

    ต้องเป็นขั้นตอนเดียวกันทุกจุด มิฉะนั้นรหัสผ่านที่พิมพ์เหมือนกันแต่ประกอบอักขระ
    ต่างกันจะเข้าสู่ระบบไม่ได้ (`security.md` หัวข้อ 1)
    """
    if not isinstance(password, str):
        raise PasswordPolicyError(f"รหัสผ่านต้องเป็นข้อความ ไม่ใช่ {type(password).__name__}")
    return unicodedata.normalize(NORMALISATION_FORM, password)


def length_of(password: str) -> int:
    """ความยาวเป็น **จำนวน code point** ไม่ใช่จำนวนไบต์

    NIST กำหนดให้นับหนึ่ง code point เป็นหนึ่งอักขระ — การนับไบต์จะทำให้รหัสผ่าน
    ภาษาไทยที่มี 15 ตัวอักษรนับได้ 45 ซึ่งผ่านเกณฑ์ทั้งที่สั้นกว่าที่กฎต้องการ
    """
    return len(normalised(password))


def acceptable_new_password(password: str) -> str:
    """รหัสผ่านใหม่ในรูปมาตรฐาน — ปฏิเสธเมื่อความยาวไม่เข้าเกณฑ์

    **ไม่ตรวจชนิดอักขระ** NIST ห้ามกฎชนิดอักขระไว้ชัด ความยาวกันการเดาได้ดีกว่า
    ส่วนรายการรหัสผ่านที่ห้ามอยู่ใน `infra` เพราะต้องอ่านไฟล์
    """
    candidate = normalised(password)
    length = len(candidate)
    if length < MINIMUM_LENGTH:
        raise PasswordPolicyError(f"รหัสผ่านต้องยาวอย่างน้อย {MINIMUM_LENGTH} ตัวอักษร")
    if length > MAXIMUM_LENGTH:
        raise PasswordPolicyError(f"รหัสผ่านต้องยาวไม่เกิน {MAXIMUM_LENGTH} ตัวอักษร")
    return candidate
