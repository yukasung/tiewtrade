"""ผิดโดยเจตนา: core แตะฐานข้อมูล ซึ่งขัดกับ architecture.md หัวข้อ 1-2 (F-03 RQ-11)"""

from sqlalchemy import text


def query() -> object:
    return text("SELECT 1")
