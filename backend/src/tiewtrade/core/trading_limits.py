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
    ABOVE_MAXIMUM_QUANTITY = "ABOVE_MAXIMUM_QUANTITY"
    ABOVE_MAXIMUM_NOTIONAL = "ABOVE_MAXIMUM_NOTIONAL"
    PRICE_NOT_ON_TICK = "PRICE_NOT_ON_TICK"
    BELOW_MINIMUM_PRICE = "BELOW_MINIMUM_PRICE"
    ABOVE_MAXIMUM_PRICE = "ABOVE_MAXIMUM_PRICE"
    BELOW_PERCENT_PRICE = "BELOW_PERCENT_PRICE"
    ABOVE_PERCENT_PRICE = "ABOVE_PERCENT_PRICE"
    TOO_MANY_OPEN_ORDERS = "TOO_MANY_OPEN_ORDERS"


def unmet_constraints(
    *,
    quantity: Quantity,
    notional: Money,
    minimum_quantity: Quantity,
    quantity_step: Quantity,
    minimum_notional: Money,
    maximum_quantity: Quantity | None = None,
    maximum_notional: Money | None = None,
    price: Money | None = None,
    price_tick: Money | None = None,
    minimum_price: Money | None = None,
    maximum_price: Money | None = None,
    percent_minimum_price: Money | None = None,
    percent_maximum_price: Money | None = None,
    active_orders: int = 0,
    maximum_open_orders: int | None = None,
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

    if maximum_quantity is not None and quantity > maximum_quantity:
        violations.append(ConstraintViolation.ABOVE_MAXIMUM_QUANTITY)
    if maximum_notional is not None and notional > maximum_notional:
        violations.append(ConstraintViolation.ABOVE_MAXIMUM_NOTIONAL)
    if price is not None:
        if price_tick is not None and not price.is_multiple_of(price_tick):
            violations.append(ConstraintViolation.PRICE_NOT_ON_TICK)
        if minimum_price is not None and price < minimum_price:
            violations.append(ConstraintViolation.BELOW_MINIMUM_PRICE)
        if maximum_price is not None and price > maximum_price:
            violations.append(ConstraintViolation.ABOVE_MAXIMUM_PRICE)
        if percent_minimum_price is not None and price < percent_minimum_price:
            violations.append(ConstraintViolation.BELOW_PERCENT_PRICE)
        if percent_maximum_price is not None and price > percent_maximum_price:
            violations.append(ConstraintViolation.ABOVE_PERCENT_PRICE)
    if maximum_open_orders is not None and active_orders >= maximum_open_orders:
        violations.append(ConstraintViolation.TOO_MANY_OPEN_ORDERS)

    return tuple(violations)
