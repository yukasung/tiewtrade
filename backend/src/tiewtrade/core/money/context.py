"""ขอบเขตของการคำนวณ (RQ-2, RQ-7)

`Decimal` ปัดตาม context ของผู้เรียก โดยที่โค้ดไม่ต้องสั่งปัดเลย และ context
แยกตาม thread หรือ coroutine การตั้งค่าตอนโปรแกรมเริ่มจึงไม่พอ

**ขอบเขตอยู่ที่ทางเข้าสาธารณะ ไม่ใช่ที่นิพจน์เลขคณิตแต่ละตัว**
ทุกฟังก์ชันที่คนนอกโมดูลเรียกได้ ถูกครอบด้วย `guarded` ข้างในจึงไม่ต้องรู้ว่า
operation ไหนผ่าน context บ้าง — การเทียบค่า เครื่องหมายลบ `abs` `quantize`
`as_tuple` ได้รับการคุ้มครองเท่ากันหมด

ก่อนหน้านี้ขอบเขตอยู่ที่นิพจน์ ทำให้กฎบังคับตัวเองไม่ได้ ใครเพิ่มเมธอดใหม่
ต้องจำให้ได้ว่า operation ไหนปลอดภัย ซึ่งเป็นรากของบั๊ก `-MAX_ABS` ที่เคยเกิด
"""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from decimal import (
    ROUND_HALF_EVEN,
    Clamped,
    Context,
    DecimalException,
    DivisionByZero,
    Inexact,
    InvalidOperation,
    Overflow,
    Rounded,
    Underflow,
    localcontext,
)
from functools import wraps

from tiewtrade.core.money.errors import ArithmeticFailureError, MoneyError
from tiewtrade.core.money.limits import COMPUTE_PRECISION

#: ขอบเขตเลขชี้กำลัง กว้างพอสำหรับผลคูณของค่าที่เก็บได้ (สูงสุดราว 10^40)
#: โดยไม่กว้างจนค่าที่ผิดปกติผ่านไปเงียบ ๆ
_EXPONENT_LIMIT = 200

#: ข้อผิดพลาดที่ต้องดักเสมอ ไม่ว่าจะอยู่ในโหมดปัดหรือไม่
_ALWAYS_TRAPPED = [InvalidOperation, DivisionByZero, Overflow, Underflow, Clamped]

#: ข้อผิดพลาดที่ดักเฉพาะตอนที่ไม่อนุญาตให้ปัด
#: ที่ความละเอียด 80 หลักกับค่าที่อยู่ในช่วง บวก ลบ คูณ ต้องได้ผลเป๊ะเสมอ
#: ถ้ามีการปัดเกิดขึ้นแปลว่ามีอะไรผิด ไม่ใช่เรื่องปกติที่ควรปล่อยผ่าน
_ROUNDING_SIGNALS = [Inexact, Rounded]


def _context(*, allow_rounding: bool = False) -> Context:
    """สร้าง context ใหม่จากศูนย์ ไม่คัดลอกของผู้เรียก

    การคัดลอกจะพา rounding, traps และ Emin/Emax จากภายนอกติดมาด้วย
    ซึ่งเปลี่ยนได้ทั้งผลลัพธ์และชนิดข้อผิดพลาด
    """
    traps = list(_ALWAYS_TRAPPED)
    if not allow_rounding:
        traps.extend(_ROUNDING_SIGNALS)
    return Context(
        prec=COMPUTE_PRECISION,
        rounding=ROUND_HALF_EVEN,
        Emin=-_EXPONENT_LIMIT,
        Emax=_EXPONENT_LIMIT,
        capitals=1,
        clamp=0,
        traps=traps,
    )


def guarded[**Params, Result](
    function: Callable[Params, Result],
) -> Callable[Params, Result]:
    """ครอบทางเข้าสาธารณะด้วย context ของโมดูล

    `localcontext` คืน context เดิมของผู้เรียกให้เสมอเมื่อออกจากบล็อก
    รวมถึงตอนที่เกิดข้อผิดพลาด (P-3)
    """

    @wraps(function)
    def wrapper(*args: Params.args, **kwargs: Params.kwargs) -> Result:
        with localcontext(_context()):
            try:
                return function(*args, **kwargs)
            except MoneyError:
                # ข้อผิดพลาดของโมดูลเองส่งต่อตามเดิม ไม่ห่อซ้ำ
                raise
            except DecimalException as cause:
                # สัญญาณของ `Decimal` ที่หลุดออกมาจากการคำนวณ ต้องไม่ถึงผู้เรียก
                # ผู้เรียกดักด้วยชนิดของโมดูลชนิดเดียว (RQ-14, P-3.2)
                raise ArithmeticFailureError(f"การคำนวณล้มเหลว: {cause}") from cause

    return wrapper


@contextmanager
def allowing_rounding() -> Iterator[None]:
    """หน้าต่างแคบข้างในที่อนุญาตให้ปัดได้

    ซ้อนอยู่ในขอบเขตของ `guarded` อีกที ใช้เฉพาะจุดที่ข้อกำหนดอนุญาตให้ปัด
    """
    with localcontext(_context(allow_rounding=True)):
        yield
