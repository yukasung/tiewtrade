"""กฎเรื่องเวลาที่ชั้น venue ใช้ร่วมกัน (F-33)

`database.md` หัวข้อ 2 บังคับว่าเวลาในระบบเป็น UTC เสมอ และเวลาที่ไม่มี timezone กำกับ
เทียบข้ามเครื่องไม่ได้ ชนิดข้อมูลในชั้นนี้จึงต้องปฏิเสธเวลาที่ไม่มี timezone ทุกช่อง

อยู่ที่เดียวเพราะกฎเดียวกันมีสามที่ที่ต้องใช้ (ราคาสองช่อง กระเป๋าหนึ่งช่อง)
และตัวเชื่อมจริงของ F-35 จะเป็นที่ที่สี่ — สามข้อความที่ต่างกันสำหรับกฎเดียวกัน
คือสิ่งที่ทำให้คนอ่าน log แล้วคิดว่าเป็นคนละเรื่อง
"""

from __future__ import annotations

from datetime import datetime


def require_aware(label: str, moment: datetime) -> None:
    """ปฏิเสธเวลาที่ไม่มี timezone กำกับ

    `label` มีไว้บอกว่าช่องไหนผิด เพราะชนิดข้อมูลหนึ่งตัวมีเวลาได้หลายช่อง
    """
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError(f"{label}ต้องมี timezone กำกับ")
