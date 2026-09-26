"""ผิดโดยเจตนา: core พึ่งไลบรารีภายนอกที่ไม่ได้อยู่ในรายการห้ามเดิม (รีวิว S-3)"""
from pydantic import BaseModel


class Money(BaseModel):
    amount: str
