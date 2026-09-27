"""การต่อฐานข้อมูล — หนึ่ง URL ต่อหนึ่งบทบาท (plan.md ข้อ 7)

**ไม่มี URL เดียวแล้วสลับบทบาททีหลัง** เพราะการสลับบทบาทในเวลาทำงานหมายความว่า
process ที่รับคำขอจากเว็บถือสิทธิ์ของบทบาทที่แรงกว่าอยู่ในมือตลอดเวลา
การแยก URL ทำให้สิทธิ์ที่ process หนึ่งถืออยู่คือสิทธิ์ที่มันควรมีเท่านั้น
"""

from __future__ import annotations

import os
from enum import Enum
from typing import Final

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from tiewtrade.infra.db.errors import DatabaseConfigurationError


class DatabaseRole(Enum):
    """บทบาทฐานข้อมูลตาม `standards/database.md` หัวข้อ 5"""

    #: เจ้าของโครงสร้าง ใช้เฉพาะตอนรัน migration (RQ-5.1)
    MIGRATOR = "tiewtrade_migrator"
    #: รับคำขอจากเว็บ ทำงานใต้ RLS เสมอ
    API = "tiewtrade_api"
    #: งานของผู้ใช้รายเดียวใน engine — ใต้ RLS (Q-3)
    ENGINE = "tiewtrade_engine"
    #: งานกวาดรายการข้ามผู้ใช้เท่านั้น — ข้าม RLS อ่านอย่างเดียว (Q-3)
    ENGINE_SCAN = "tiewtrade_engine_scan"
    #: เขียนได้เฉพาะตารางราคาและแท่งเทียน
    MARKET_DATA = "tiewtrade_market_data"

    @property
    def role_name(self) -> str:
        """ชื่อบทบาทในฐานข้อมูล"""
        return self.value

    @property
    def url_variable(self) -> str:
        """ชื่อตัวแปรสภาพแวดล้อมที่เก็บ URL ของบทบาทนี้"""
        return f"TIEWTRADE_DATABASE_URL_{self.name}"


#: บทบาทที่ต้องทำงานใต้ RLS — ใช้ในชั้น session ตรวจก่อนแตะข้อมูลผู้ใช้
ROLES_UNDER_RLS: Final[frozenset[DatabaseRole]] = frozenset({DatabaseRole.API, DatabaseRole.ENGINE})


def database_url(role: DatabaseRole) -> str:
    """อ่าน URL ของบทบาทจากสภาพแวดล้อม

    ข้อความข้อผิดพลาดบอกแค่ชื่อตัวแปร **ไม่บอกค่า** เพราะค่ามีรหัสผ่านอยู่ (RQ-15)
    """
    url = os.environ.get(role.url_variable, "")
    if not url:
        raise DatabaseConfigurationError(
            f"ไม่ได้ตั้ง {role.url_variable} — บทบาท {role.role_name} จึงต่อฐานข้อมูลไม่ได้"
        )
    return url


def create_engine_for(role: DatabaseRole) -> AsyncEngine:
    """สร้าง engine ของบทบาทนั้น

    `echo=False` และ `hide_parameters=True` เพื่อไม่ให้ค่าที่ bind หลุดลง log (RQ-15)
    """
    return create_async_engine(
        database_url(role),
        echo=False,
        echo_pool=False,
        hide_parameters=True,
        pool_pre_ping=True,
    )
