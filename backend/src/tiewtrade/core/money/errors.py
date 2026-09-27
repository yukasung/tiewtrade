"""ชนิดข้อผิดพลาดของโมดูลเงิน

ทุกชนิดสืบทอดจาก `MoneyError` เพื่อให้ผู้เรียกดักรวมได้ด้วยชนิดฐาน (RQ-14)
ข้อผิดพลาดของ `Decimal` ต้องไม่รั่วออกไปหาผู้เรียก ต้องแปลงเป็นชนิดในโมดูลนี้
"""


class MoneyError(Exception):
    """ฐานของข้อผิดพลาดทั้งหมดในโมดูลนี้"""


class InvalidInputTypeError(MoneyError):
    """ชนิดของค่าที่ส่งเข้ามาไม่รองรับ — รับเฉพาะ str, int และ Decimal"""


class InvalidNumberFormatError(MoneyError):
    """ข้อความที่ส่งเข้ามาไม่ใช่ตัวเลขที่อ่านได้"""


class NotFiniteValueError(MoneyError):
    """ค่าไม่ใช่จำนวนจำกัด เช่น NaN หรือค่าอนันต์"""


class TooManyDecimalPlacesError(MoneyError):
    """ทศนิยมจริงเกินจำนวนตำแหน่งที่เก็บได้"""


class OutOfRangeError(MoneyError):
    """ค่าอยู่นอกช่วงที่เก็บได้ ทั้งตอนสร้าง ตอนคำนวณ และหลังปัด"""


class UnitMismatchError(MoneyError):
    """คำนวณหรือเทียบค่าข้ามหน่วย"""


class InvalidUnitError(MoneyError):
    """หน่วยผิดรูปแบบหรือหายไป"""


class RoundingRequiredError(MoneyError):
    """ผลลัพธ์ต้องปัดแต่ผู้เรียกไม่ได้ระบุทิศทาง"""


class ArithmeticFailureError(MoneyError):
    """การคำนวณล้มเหลวด้วยเหตุที่ไม่คาดไว้ — แปลงมาจากข้อผิดพลาดของ Decimal"""
