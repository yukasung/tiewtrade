"""ที่มาของกุญแจเข้ารหัส — รอยต่อของ **T-03** (F-06 plan.md หัวข้อ 4.1)

**T-03 ยังไม่ปิด** เอกสารนี้ตัดสินเฉพาะที่มาของกุญแจบน **เครื่องพัฒนาและ CI**
ส่วนที่มาบนเครื่องจริงเป็นงาน **F-31** — ผู้เรียกรู้จักแต่สัญญา `KeySource`
และทุกค่าที่ปิดผนึกพา `key_version` ติดไปในแถว จึงเปลี่ยนที่มาและหมุนกุญแจได้
ภายหลังโดยไม่ต้องรื้อของเก่า

**กุญแจของแต่ละงานแยกกันเด็ดขาด** (RQ-14) — `KeyPurpose` เป็นตัวบังคับข้อนี้
ที่ระดับชนิดข้อมูล ไม่ใช่ที่ระดับวินัยของคนเขียน · `tech-stack.md` หัวข้อ 8 บังคับว่า
API secret ของตลาดถอดได้เฉพาะใน `engine` ฉะนั้นมันต้องไม่ใช้กุญแจเดียวกับ TOTP
ซึ่งฝั่งที่รับคำขอจากเว็บต้องถอดได้

**กุญแจไม่ครบ = กระบวนการไม่เริ่ม** ไม่ใช่ล้มตอนมีผู้ใช้คนแรกมาเปิด TOTP
(validation V-10) — เป็นเหตุที่ `from_environment()` ตรวจทุกอย่างตอนสร้าง
"""

from __future__ import annotations

import base64
import binascii
import os
from dataclasses import dataclass
from enum import Enum
from typing import ClassVar, Final

from tiewtrade.infra.db.errors import InfraError

#: ความยาวกุญแจของ AES-256-GCM
KEY_BYTES: Final[int] = 32

#: ตัวคั่นระหว่างรุ่นกับค่ากุญแจในตัวแปรสภาพแวดล้อม
_VERSION_SEPARATOR: Final[str] = ":"

#: ตัวคั่นระหว่างกุญแจหลายรุ่น — รุ่นแรกคือรุ่นที่ใช้ปิดผนึกของใหม่
_KEY_SEPARATOR: Final[str] = ","


class KeyConfigurationError(InfraError):
    """ตั้งกุญแจไม่ครบหรือไม่ถูกรูป — **บอกชื่อตัวแปร ไม่บอกค่า**

    เหตุผลเดียวกับ `DatabaseConfigurationError` ของ F-03: ข้อความข้อผิดพลาด
    ไปจบที่ log ได้ และ `security.md` หัวข้อ 4 ห้าม secret อยู่ใน log
    """

    code: ClassVar[str] = "KEY_CONFIGURATION"


class KeyPurpose(Enum):
    """งานที่กุญแจหนึ่งดอกใช้ได้ — **หนึ่งงานหนึ่งกุญแจ ปนกันไม่ได้** (RQ-14)

    ค่าของสมาชิกถูกผูกเข้าไปใน associated data ของการปิดผนึก ฉะนั้นค่าที่ปิดผนึก
    ไว้เพื่องานหนึ่ง **ถอดด้วยกุญแจของอีกงานไม่ได้ แม้กุญแจจะถูกตั้งสลับกัน**

    **สองงานนี้ต้องใช้กุญแจคนละดอก** — `tech-stack.md` หัวข้อ 8 บังคับว่า API secret
    ของตลาดถอดได้เฉพาะใน `engine` ส่วน secret ของ TOTP ต้องถอดได้ที่ฝั่งที่รับคำขอ
    จากเว็บ ถ้าใช้กุญแจเดียวกัน ฝั่งเว็บที่ถอด TOTP ได้ก็ถอด API secret ได้ด้วย
    ซึ่งลบข้อบังคับนั้นทิ้งทั้งข้อ
    """

    TOTP_SECRET = "TOTP_SECRET"
    #: secret ของ API key ที่ผู้ใช้ให้ไว้ (F-07 RQ-4) — **เปิดผนึกได้เฉพาะใน `engine`**
    VENUE_API_SECRET = "VENUE_API_SECRET"

    @property
    def environment_variable(self) -> str:
        """ชื่อตัวแปรสภาพแวดล้อมที่เก็บกุญแจของงานนี้"""
        return f"TIEWTRADE_SEALING_KEY_{self.name}"


@dataclass(frozen=True, slots=True)
class KeySource:
    """กุญแจทุกรุ่นของงานหนึ่ง — รุ่นปัจจุบันหนึ่งรุ่น และรุ่นที่ปลดแล้วอ่านได้

    **แยกสองหน้าที่** เพราะการหมุนกุญแจต้องการทั้งสองอย่างคนละเวลา:
    ปิดผนึกของใหม่ด้วยรุ่นปัจจุบันเท่านั้น แต่ถอดของเก่าต้องหารุ่นที่แถวนั้นระบุได้
    """

    purpose: KeyPurpose
    current_version: str
    _keys: dict[str, bytes]

    @classmethod
    def from_environment(cls, purpose: KeyPurpose) -> KeySource:
        """อ่านกุญแจของงานนั้นจากสภาพแวดล้อม — **ดังทันทีเมื่อไม่ครบ**

        รูปแบบคือ `รุ่น:กุญแจแบบ base64` คั่นหลายรุ่นด้วยจุลภาค
        **รุ่นแรกคือรุ่นที่ใช้ปิดผนึกของใหม่** ที่เหลืออ่านของเก่าได้เท่านั้น

        เลือกเก็บหลายรุ่นในตัวแปรเดียวเพราะการหมุนกุญแจต้องมีช่วงที่ของเก่ายังอ่านได้
        ถ้าเก็บรุ่นเดียว การหมุนจะทำให้แถวเก่าอ่านไม่ออกทันที ซึ่งคือการล็อกผู้ใช้
        ออกจากบัญชีทั้งระบบ
        """
        variable = purpose.environment_variable
        raw = os.environ.get(variable, "").strip()
        if not raw:
            raise KeyConfigurationError(f"ยังไม่ได้ตั้ง {variable}")

        keys: dict[str, bytes] = {}
        order: list[str] = []
        for entry in raw.split(_KEY_SEPARATOR):
            version, key = _parsed(entry.strip(), variable=variable)
            if version in keys:
                raise KeyConfigurationError(f"{variable} มีรุ่น {version} ซ้ำกัน")
            keys[version] = key
            order.append(version)

        return cls(purpose=purpose, current_version=order[0], _keys=keys)

    def current(self) -> tuple[str, bytes]:
        """รุ่นและกุญแจที่ใช้ปิดผนึกของใหม่"""
        return self.current_version, self._keys[self.current_version]

    def for_version(self, version: str) -> bytes:
        """กุญแจของรุ่นที่ระบุ — ใช้ถอดของที่ปิดผนึกไว้ก่อนการหมุน

        **ไม่คืนกุญแจรุ่นปัจจุบันแทนเมื่อหารุ่นที่ขอไม่เจอ** การเดาแบบนั้นทำให้
        ข้อมูลที่อ่านไม่ออกกลายเป็น "รหัสไม่ตรง" ซึ่งซ่อนปัญหาการตั้งค่าไว้
        """
        if version not in self._keys:
            raise KeyConfigurationError(f"{self.purpose.environment_variable} ไม่มีกุญแจรุ่น {version}")
        return self._keys[version]


def _parsed(entry: str, *, variable: str) -> tuple[str, bytes]:
    """แยก `รุ่น:กุญแจ` หนึ่งรายการ และตรวจความยาวกุญแจ

    **ข้อความข้อผิดพลาดไม่พาค่ากุญแจหรือส่วนของมันไปด้วย** ไม่ว่าผิดแบบใด
    """
    version, separator, encoded = entry.partition(_VERSION_SEPARATOR)
    if not separator or not version or not encoded:
        raise KeyConfigurationError(f"{variable} ต้องอยู่ในรูป รุ่น:กุญแจ")

    try:
        key = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        raise KeyConfigurationError(f"{variable} รุ่น {version} ไม่ใช่ base64 ที่ถูกรูป") from None

    if len(key) != KEY_BYTES:
        raise KeyConfigurationError(
            f"{variable} รุ่น {version} ต้องยาว {KEY_BYTES} ไบต์ก่อนเข้ารหัส base64"
        )
    return version, key
