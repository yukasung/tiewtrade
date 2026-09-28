"""ถูกต้อง: ส่วนกลางพึ่งเฉพาะสิ่งที่อยู่ในรายการที่อนุญาต"""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Reading:
    value: Decimal
