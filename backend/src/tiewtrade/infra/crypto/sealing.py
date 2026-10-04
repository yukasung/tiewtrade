"""ปิดผนึกและเปิดผนึก secret ด้วย AES-GCM (F-06 plan.md หัวข้อ 4.3)

**ผูกค่าที่ปิดผนึกไว้กับเจ้าของและกับงาน** ผ่าน associated data ฉะนั้นค่าที่ถูกคัดลอก
ไปใส่แถวของผู้ใช้คนอื่น หรือถูกเอาไปใช้ในงานอื่น **เปิดผนึกไม่ออก** ไม่ใช่เปิดออก
แล้วได้ของผิดคน (validation V-9) — การผูกแบบนี้ไม่มีค่าใช้จ่ายเพิ่มเลยเพราะ AEAD
รองรับอยู่แล้ว แต่ถ้าไม่ผูก การสลับแถวในฐานข้อมูลจะกลายเป็นการสวมรอย

**ข้อความข้อผิดพลาดไม่พา plaintext, ciphertext หรือกุญแจไปด้วย** (`security.md`
หัวข้อ 4) และไม่บอกว่าล้มเหลวเพราะอะไรในเชิงรหัสลับ เพราะรายละเอียดนั้นช่วยผู้โจมตี
มากกว่าช่วยคนแก้ปัญหา
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import ClassVar, Final
from uuid import UUID

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from tiewtrade.infra.crypto.keys import KeyPurpose, KeySource
from tiewtrade.infra.db.errors import InfraError

#: ความยาว nonce ที่ NIST SP 800-38D แนะนำสำหรับ GCM
NONCE_BYTES: Final[int] = 12


class SealingError(InfraError):
    """เปิดผนึกไม่สำเร็จ — ข้อมูลถูกแก้ ผิดเจ้าของ ผิดงาน หรือกุญแจไม่ตรง

    **ไม่แยกสาเหตุให้ผู้เรียก** เพราะทุกกรณีมีผลเหมือนกันคือใช้ค่านั้นต่อไม่ได้
    และการแยกสาเหตุคือการบอกผู้โจมตีว่าเดาถูกส่วนไหนไปแล้ว
    """

    code: ClassVar[str] = "SEALING_FAILED"


@dataclass(frozen=True, slots=True)
class Sealed:
    """ค่าที่ปิดผนึกแล้ว พร้อมรุ่นของกุญแจที่ใช้

    เก็บสองช่องนี้ลงสองคอลัมน์ในแถวเดียวกัน — รุ่นต้องเดินทางไปกับค่า มิฉะนั้น
    การหมุนกุญแจจะทำให้ไม่รู้ว่าแถวไหนปิดผนึกด้วยกุญแจอะไร
    """

    key_version: str
    blob: bytes


def seal(source: KeySource, plaintext: bytes, *, owner: UUID) -> Sealed:
    """ปิดผนึกด้วยกุญแจรุ่นปัจจุบันของงานนั้น

    `nonce` สุ่มใหม่ทุกครั้งและเก็บไว้หน้า ciphertext — **ห้ามใช้ nonce ซ้ำกับกุญแจเดิม**
    เพราะ GCM เสียความปลอดภัยทันทีเมื่อซ้ำ การสุ่ม 12 ไบต์ต่อครั้งจึงเป็นเงื่อนไข
    ไม่ใช่รายละเอียด
    """
    version, key = source.current()
    nonce = secrets.token_bytes(NONCE_BYTES)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, _bound(source.purpose, owner))
    return Sealed(key_version=version, blob=nonce + ciphertext)


def unseal(source: KeySource, sealed: Sealed, *, owner: UUID) -> bytes:
    """เปิดผนึกด้วยกุญแจรุ่นที่ค่านั้นระบุ — ไม่ใช่รุ่นปัจจุบัน"""
    if len(sealed.blob) <= NONCE_BYTES:
        raise SealingError("ค่าที่ปิดผนึกไว้สั้นเกินกว่าจะถูกต้อง")

    key = source.for_version(sealed.key_version)
    nonce, ciphertext = sealed.blob[:NONCE_BYTES], sealed.blob[NONCE_BYTES:]
    try:
        return AESGCM(key).decrypt(nonce, ciphertext, _bound(source.purpose, owner))
    except InvalidTag:
        raise SealingError("เปิดผนึกค่าที่เก็บไว้ไม่สำเร็จ") from None


def _bound(purpose: KeyPurpose, owner: UUID) -> bytes:
    """สิ่งที่ค่านี้ถูกผูกไว้กับ — งานและเจ้าของ

    ใส่ชื่อ **งาน** ด้วย ไม่ใช่แค่เจ้าของ เพราะกุญแจของสองงานอาจถูกตั้งสลับกัน
    ตอนนำขึ้นเครื่อง การผูกชื่องานทำให้ความผิดพลาดนั้นดังทันทีแทนที่จะเงียบ
    """
    return f"{purpose.value}|{owner}".encode()
