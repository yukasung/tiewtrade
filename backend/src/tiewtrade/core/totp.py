"""การคำนวณรหัส TOTP ตาม RFC 6238 (F-06 plan.md หัวข้อ 1)

อยู่ใน `core` เพราะเป็นการคำนวณล้วน — ใส่ secret กับลำดับช่วงเวลาเข้าไป
ได้รหัสเดิมทุกครั้ง · **การสร้าง secret การเข้ารหัส และการอ่านนาฬิกาอยู่ใน `infra`**
ตาม `architecture.md` หัวข้อ 1 แบบเดียวกับที่ `core/passwords.py` แยกจาก
`infra/auth/hashing.py`

**ไม่ใช้ไลบรารี TOTP สำเร็จ** เพราะหลายตัวสร้าง secret หรืออ่านนาฬิกาเอง
ซึ่งตัวตรวจความบริสุทธิ์ของ `core` ห้าม (`backend/tests/purity.py`) และเพราะ
**RFC 6238 มีชุดตัวเลขทดสอบมาให้** จึงพิสูจน์ความถูกต้องด้วยหลักฐานจากภายนอกได้
(validation V-1)

**ค่าที่เจ้าของตัดสินไว้** (`requirements.md` Q-8): ช่วงเวลา 30 วินาที, 6 หลัก,
ยอมรับช่วงก่อนหน้าหนึ่งช่วง · **อัลกอริทึมเป็น SHA-1 ตามค่าปริยายของ RFC 6238**
ซึ่งเป็นสิ่งที่แอป authenticator ทั่วไปใช้ — เปลี่ยนแล้วรหัสจากแอปจะใช้ไม่ได้

**การยอมรับสองช่วงเวลามีราคา** โอกาสที่การเดาหนึ่งครั้งจะตรงคือ **2 ใน 10⁶
ไม่ใช่ 1 ใน 10⁶** ซึ่งการคำนวณเพดานของถังต้องนับข้อนี้ (`plan.md` หัวข้อ 14.3)
"""

from __future__ import annotations

import base64
import hashlib
import hmac
from datetime import datetime, timedelta
from typing import Final

#: ความยาวของหนึ่งช่วงเวลา (`requirements.md` Q-8)
TIME_STEP: Final[timedelta] = timedelta(seconds=30)

#: จำนวนหลักของรหัสที่ผู้ใช้กรอก
DIGITS: Final[int] = 6

#: จำนวนช่วงเวลาก่อนหน้าที่ยังรับได้ — รองรับนาฬิกาเครื่องผู้ใช้ที่เดินช้า
#:
#: **เปลี่ยนค่านี้คือการเปลี่ยนพื้นที่การเดา** ไม่ใช่แค่ความสะดวก
STEPS_ACCEPTED_BACK: Final[int] = 1

#: ขั้นต่ำของ secret ตาม RFC 4226 หัวข้อ 4 ข้อ R6 — 128 บิต
MINIMUM_SECRET_BYTES: Final[int] = 16

#: ช่วงจำนวนหลักที่ RFC 4226 หัวข้อ 5.3 รองรับ
_MINIMUM_DIGITS: Final[int] = 6
_MAXIMUM_DIGITS: Final[int] = 8


class TotpError(Exception):
    """ค่าที่ส่งเข้ามาใช้คำนวณไม่ได้ — ชนิดเดียวที่โมดูลนี้โยน

    มีชนิดของตัวเองเพื่อให้ผู้เรียกแยกได้ว่าเป็นความผิดพลาดของการเรียก
    ไม่ใช่ "รหัสไม่ตรง" ซึ่งเป็นผลลัพธ์ปกติและคืนเป็นค่า ไม่ใช่โยน
    """


def step_at(moment: datetime) -> int:
    """ลำดับช่วงเวลาของเวลานั้น — ตัวนับที่ RFC 6238 ใช้แทนตัวนับของ HOTP

    **ปฏิเสธเวลาที่ไม่มีเขตเวลา** เพราะ `timestamp()` ของเวลาแบบนั้นตีความเป็น
    เวลาท้องถิ่นของเครื่อง ซึ่งทำให้รหัสที่คำนวณได้ต่างกันตามเครื่องที่รัน
    — เป็นสิ่งที่ `architecture.md` ห้ามโดยตรง (ผลต้องเหมือนกันทุกที่)
    """
    if moment.tzinfo is None or moment.tzinfo.utcoffset(moment) is None:
        raise TotpError("เวลาที่ใช้คำนวณต้องมีเขตเวลา")
    return int(moment.timestamp() // TIME_STEP.total_seconds())


def accepted_steps(step: int) -> tuple[int, ...]:
    """ลำดับช่วงเวลาที่รับได้ ณ ลำดับนั้น — เรียงจากใหม่ไปเก่า

    เรียงแบบนี้เพื่อให้ผู้เรียกที่หยุดเมื่อเจอ ได้ลำดับที่ใหม่ที่สุดก่อน
    ซึ่งเป็นค่าที่ควรบันทึกเป็น "ช่วงล่าสุดที่รับแล้ว"
    """
    if step < 0:
        raise TotpError("ลำดับช่วงเวลาติดลบไม่ได้")
    return tuple(step - back for back in range(STEPS_ACCEPTED_BACK + 1) if step - back >= 0)


def code_for(secret: bytes, step: int, *, digits: int = DIGITS) -> str:
    """รหัสของ secret นั้นที่ลำดับช่วงเวลานั้น — เติมศูนย์หน้าให้ครบจำนวนหลักเสมอ

    `digits` รับค่าได้เพราะ **ชุดตัวเลขทดสอบของ RFC 6238 เป็นแบบ 8 หลัก**
    การตรวจกับหลักฐานจากภายนอกจึงต้องส่งค่านี้ได้ — ของจริงใช้ค่าปริยาย 6 หลัก

    การเติมศูนย์หน้าไม่ใช่เรื่องความสวยงาม: รหัส `001234` กับ `1234` ต้องไม่ถูกมองว่า
    เป็นค่าเดียวกัน มิฉะนั้นการเทียบจะพลาดหนึ่งในหมื่นครั้ง
    """
    if len(secret) < MINIMUM_SECRET_BYTES:
        raise TotpError(f"secret ต้องยาวอย่างน้อย {MINIMUM_SECRET_BYTES} ไบต์")
    if not _MINIMUM_DIGITS <= digits <= _MAXIMUM_DIGITS:
        raise TotpError(f"จำนวนหลักต้องอยู่ระหว่าง {_MINIMUM_DIGITS} ถึง {_MAXIMUM_DIGITS}")
    if step < 0:
        raise TotpError("ลำดับช่วงเวลาติดลบไม่ได้")

    # ตัวนับเป็นจำนวนเต็ม 8 ไบต์เรียงจากไบต์สูง ตาม RFC 4226 หัวข้อ 5.1
    counter = step.to_bytes(8, "big")
    digest = hmac.new(secret, counter, hashlib.sha1).digest()
    # การตัดแบบไดนามิกของ RFC 4226 หัวข้อ 5.3 — สี่บิตท้ายบอกว่าเริ่มอ่านที่ไบต์ไหน
    # และบิตสูงสุดถูกตัดออกเพื่อไม่ให้ค่าติดลบในภาษาที่จำนวนเต็มมีเครื่องหมาย
    offset = digest[-1] & 0x0F
    chunk = int.from_bytes(digest[offset : offset + 4], "big") & 0x7FFFFFFF
    # เอาหลักท้ายตามจำนวนที่ต้องการ ซึ่งให้ผลเท่ากับ `chunk % 10**digits` ของ RFC
    # แต่ไม่ต้องยกกำลัง จึงไม่มีจุดที่ชนิดข้อมูลกลายเป็นค่าที่ตรวจชนิดไม่ได้
    return str(chunk).zfill(digits)[-digits:]


def matching_step(
    secret: bytes, presented: str, *, at_step: int, digits: int = DIGITS
) -> int | None:
    """ลำดับช่วงเวลาที่รหัสนี้ตรง หรือ `None` เมื่อไม่ตรงเลย

    คืน **ลำดับ** ไม่ใช่ค่าจริงเท็จ เพราะผู้เรียกต้องบันทึกว่ารับลำดับไหนไปแล้ว
    เพื่อกันการใช้ซ้ำ (RQ-4 · `plan.md` หัวข้อ 1.2)

    เทียบด้วย `compare_digest` ทุกครั้ง **รวมกรณีที่ความยาวไม่ตรง** เพื่อไม่ให้
    เวลาที่ใช้เทียบบอกว่ารหัสถูกกี่ตัว

    **เทียบเป็นไบต์ ไม่ใช่เป็นข้อความ** เพราะ `compare_digest` โยน `TypeError`
    เมื่อข้อความมีอักขระนอก ASCII — และ **เลขไทยคืออินพุตที่เกิดขึ้นจริง**
    (`๑๒๓๔๕๖` จากแป้นพิมพ์ไทย) ค่าแบบนั้นต้องได้ "ไม่ตรง" ไม่ใช่ทำให้คำขอพัง
    · การแปลงเลขไทยเป็นเลขอารบิกให้เป็นเรื่องของข้อกำหนด ไม่ใช่สิ่งที่ที่นี่เดาเอง
    """
    offered = presented.encode("utf-8")
    found: int | None = None
    for step in accepted_steps(at_step):
        # ไม่ `return` ทันทีเพื่อให้จำนวนครั้งที่เทียบไม่ขึ้นกับว่าตรงที่ลำดับไหน
        matched = hmac.compare_digest(
            code_for(secret, step, digits=digits).encode("ascii"), offered
        )
        if matched and found is None:
            found = step
    return found


def base32_secret(secret: bytes) -> str:
    """secret ในรูป base32 ที่แอป authenticator อ่านได้ — **ไม่มี `=` ต่อท้าย**

    ตัด `=` ออกเพราะแอปหลายตัวอ่านไม่ผ่านเมื่อมีอักขระนั้นใน query string
    และ base32 ถอดได้โดยไม่ต้องมีมัน
    """
    if len(secret) < MINIMUM_SECRET_BYTES:
        raise TotpError(f"secret ต้องยาวอย่างน้อย {MINIMUM_SECRET_BYTES} ไบต์")
    return base64.b32encode(secret).decode("ascii").rstrip("=")
