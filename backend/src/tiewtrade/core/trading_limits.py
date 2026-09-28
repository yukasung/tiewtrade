"""การตรวจว่าคำสั่งผ่านข้อจำกัดของเหรียญหรือไม่ (F-33)

อยู่ใน `core` เพราะเป็น **การคำนวณ** ซึ่ง `standards/backend.md` หัวข้อ 3 สั่งให้อยู่ที่นี่
ที่เดียว ส่วนตัวเลขข้อจำกัดเป็นข้อมูลที่ตลาดรายงาน ซึ่งอยู่ในชั้น `venues`

สามข้อที่ตรวจมาจาก `standards/trading-safety.md` หัวข้อ 3 ตรง ๆ — ไม่มากไม่น้อยกว่านั้น
จุดตรวจก่อนส่งออเดอร์ของ F-16 และ F-22 จะใช้ฟังก์ชันนี้ตัวเดียวกัน เพื่อไม่ให้มีสองที่
ที่ตรวจเรื่องเดียวกันด้วยกฎที่อาจไม่ตรงกัน

**ไม่ปัดค่าให้** ค่าที่ไม่ตรงขั้นถูกรายงานว่าไม่ผ่าน การปัดเป็นการตัดสินใจของผู้เรียก
ที่ต้องระบุทิศทางชัดเจน (`standards/backend.md` หัวข้อ 1, F-33 Q-7)
"""

from __future__ import annotations

from enum import Enum

from tiewtrade.core.money import Money, Quantity


class ConstraintViolation(Enum):
    """ข้อที่ไม่ผ่าน — คืนเป็นรายการ ไม่ใช่แค่จริง/เท็จ

    เพราะจุดตรวจต้องบอกผู้ใช้ได้ว่าไม่ผ่านเพราะอะไร และผู้ใช้แก้ได้ต่างกันในแต่ละข้อ
    """

    #: ปริมาณน้อยกว่าที่ตลาดยอมรับ
    BELOW_MINIMUM_QUANTITY = "BELOW_MINIMUM_QUANTITY"
    #: ปริมาณไม่ได้เป็นจำนวนเท่าของขั้นที่ตลาดยอมรับ
    QUANTITY_NOT_ON_STEP = "QUANTITY_NOT_ON_STEP"
    #: มูลค่ารวมน้อยกว่าที่ตลาดยอมรับ
    BELOW_MINIMUM_NOTIONAL = "BELOW_MINIMUM_NOTIONAL"


def unmet_constraints(
    *,
    quantity: Quantity,
    notional: Money,
    minimum_quantity: Quantity,
    quantity_step: Quantity,
    minimum_notional: Money,
) -> tuple[ConstraintViolation, ...]:
    """คืนข้อที่ไม่ผ่านทั้งหมด — ว่างเปล่าแปลว่าผ่านทุกข้อ

    **ตรวจทุกข้อแล้วคืนครบ ไม่หยุดที่ข้อแรก** เพราะผู้ใช้ที่แก้ทีละข้อตามที่ระบบบอก
    จะต้องลองใหม่หลายรอบโดยไม่จำเป็น

    ทุกพารามิเตอร์เป็น keyword เพราะสี่ค่ามีชนิดใกล้กัน การสลับตำแหน่ง
    `quantity` กับ `minimum_quantity` จะไม่มีอะไรเตือนเลยถ้าเรียกแบบตำแหน่งได้
    """
    violations: list[ConstraintViolation] = []

    if quantity < minimum_quantity:
        violations.append(ConstraintViolation.BELOW_MINIMUM_QUANTITY)

    if not quantity.is_multiple_of(quantity_step):
        violations.append(ConstraintViolation.QUANTITY_NOT_ON_STEP)

    if notional < minimum_notional:
        violations.append(ConstraintViolation.BELOW_MINIMUM_NOTIONAL)

    return tuple(violations)
