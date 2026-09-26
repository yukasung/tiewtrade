"""ถูกต้อง: ต้องผ่านตัวตรวจความบริสุทธิ์ภายใต้กฎเดียวกัน"""
from decimal import Decimal
def add(left: Decimal, right: Decimal) -> Decimal:
    return left + right
