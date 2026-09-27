"""ค่าคงที่และ context ที่เทสต์ของโมดูลเงินใช้ร่วมกัน

รวมไว้ที่เดียวเพื่อไม่ให้ไฟล์เทสต์แต่ละไฟล์เขียนค่าขอบเองแล้ว drift
ออกจาก `limits.py` โดยไม่มีอะไรเตือน
"""

from decimal import (
    ROUND_CEILING,
    ROUND_DOWN,
    ROUND_FLOOR,
    ROUND_HALF_UP,
    ROUND_UP,
    Context,
    Decimal,
    Inexact,
    Overflow,
    Rounded,
)

import pytest

from tiewtrade.core.money.limits import MAX_ABS, SMALLEST_UNIT, STORED_SCALE

#: ค่าสูงสุดที่เก็บได้ — หน้าจุด 20 หลัก หลังจุด 18 หลัก ทุกหลักเป็นเก้า
#: สร้างจากค่ากลางใน limits.py ไม่ได้เขียนตัวเลขซ้ำ
MAX_STORABLE = Decimal(f"{'9' * (len(str(int(MAX_ABS))) - 1)}.{'9' * STORED_SCALE}")

#: ค่าต่ำสุดที่เก็บได้ สร้างจากข้อความ ไม่ใช่จากการใส่เครื่องหมายลบ
#: เพราะการใส่เครื่องหมายลบในเทสต์รันใต้ context ของเทสต์เอง ซึ่งปัดค่า 38 หลัก
MIN_STORABLE = Decimal(f"-{MAX_STORABLE}")

#: หน่วยที่เล็กที่สุดที่เก็บได้ และค่าลบของมัน
SMALLEST = SMALLEST_UNIT
NEGATIVE_SMALLEST = Decimal(f"-{SMALLEST_UNIT}")

#: context ภายนอกที่ผิดปกติในหลายมิติ ไม่ใช่แค่ precision
#: เทสต์ทุกไฟล์ที่ต้องพิสูจน์ความเป็นอิสระจาก context ใช้รายการเดียวกันนี้
#: เพิ่ม context ที่นี่ที่เดียว แล้วทุกไฟล์ได้ใช้ทันที
HOSTILE_SETTINGS = [
    Context(prec=6),
    Context(prec=28),
    Context(prec=80),
    Context(prec=9, rounding=ROUND_UP),
    Context(prec=9, rounding=ROUND_DOWN),
    Context(prec=9, rounding=ROUND_CEILING),
    Context(prec=9, rounding=ROUND_FLOOR),
    Context(prec=9, rounding=ROUND_HALF_UP),
    Context(prec=28, traps=[Inexact]),
    Context(prec=28, traps=[Rounded]),
    Context(prec=28, traps=[Overflow]),
    Context(prec=28, Emin=-6, Emax=6),
    Context(prec=28, Emin=-2, Emax=2),
]

#: รูปแบบเดียวกัน แต่ห่อด้วย `pytest.param` เพื่อให้ชื่อกรณีอ่านออก
HOSTILE_CONTEXTS = [
    pytest.param(Context(prec=6), id="prec-6"),
    pytest.param(Context(prec=28), id="prec-28"),
    pytest.param(Context(prec=80), id="prec-80"),
    pytest.param(Context(prec=9, rounding=ROUND_UP), id="rounding-up"),
    pytest.param(Context(prec=9, rounding=ROUND_DOWN), id="rounding-down"),
    pytest.param(Context(prec=9, rounding=ROUND_CEILING), id="rounding-ceiling"),
    pytest.param(Context(prec=9, rounding=ROUND_FLOOR), id="rounding-floor"),
    pytest.param(Context(prec=9, rounding=ROUND_HALF_UP), id="rounding-half-up"),
    pytest.param(Context(prec=28, traps=[Inexact]), id="trap-inexact"),
    pytest.param(Context(prec=28, traps=[Rounded]), id="trap-rounded"),
    pytest.param(Context(prec=28, traps=[Overflow]), id="trap-overflow"),
    pytest.param(Context(prec=28, Emin=-6, Emax=6), id="narrow-exponents"),
    pytest.param(Context(prec=28, Emin=-2, Emax=2), id="very-narrow-exponents"),
]
