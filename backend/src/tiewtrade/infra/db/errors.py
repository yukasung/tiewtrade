"""ข้อผิดพลาดของชั้นฐานข้อมูล — ชนิดที่ระบุได้ ไม่ใช่ข้อความอิสระ (RQ-14)

**ข้อความของข้อผิดพลาดในโมดูลนี้ต้องไม่มี URL, รหัสผ่าน, ค่าที่ bind หรือข้อความดิบ
ของ driver** (RQ-15) การแปลงข้อผิดพลาดจึงตัด exception chain ทิ้งด้วย `from None`
เพราะ traceback ของ driver พา DETAIL และค่าที่ส่งไปด้วย
"""

from __future__ import annotations

from typing import ClassVar, Final

from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError


class InfraError(Exception):
    """ฐานร่วมของข้อผิดพลาดทั้งหมดในชั้นนี้ — ผู้เรียกดักตัวนี้ตัวเดียวได้"""

    #: รหัสที่หน้าบ้านแปลเป็นไทย/อังกฤษได้ (`standards/backend.md` หัวข้อ 4)
    code: ClassVar[str] = "INFRA_ERROR"


class DatabaseConfigurationError(InfraError):
    """ตั้งค่าการเชื่อมต่อไม่ครบ — บอกชื่อตัวแปร ไม่บอกค่า"""

    code: ClassVar[str] = "DATABASE_CONFIGURATION"


class DatabaseRoleError(InfraError):
    """ต่อฐานข้อมูลด้วยบทบาทที่ไม่ตรงกับงานที่ขอ

    เกิดเมื่อ URL ของบทบาทถูกตั้งสลับกัน หรือบทบาทมีสิทธิ์เกินกว่าที่งานนั้นควรใช้
    เช่น เป็น superuser หรือข้าม RLS ได้ (Q-3, RQ-5.1)
    """

    code: ClassVar[str] = "DATABASE_ROLE"


class SessionKindError(InfraError):
    """ใช้ session ผิดชนิดในเส้นทางที่แตะข้อมูลของผู้ใช้

    เส้นทางรายผู้ใช้รับเฉพาะ `UserSession` — `ScanSession` ข้าม RLS จึงห้ามเข้ามา
    """

    code: ClassVar[str] = "SESSION_KIND"


class AppendOnlyViolationError(InfraError):
    """พยายามแก้หรือลบของในตารางที่แก้ย้อนหลังไม่ได้"""

    code: ClassVar[str] = "APPEND_ONLY_VIOLATION"


class NotPermittedError(InfraError):
    """ฐานข้อมูลปฏิเสธเพราะไม่มีสิทธิ์"""

    code: ClassVar[str] = "NOT_PERMITTED"


class ValueRejectedError(InfraError):
    """ค่าที่ส่งมาเก็บไม่ได้ — ละเอียดเกิน เกินช่วง หรือผิดข้อจำกัดของคอลัมน์"""

    code: ClassVar[str] = "VALUE_REJECTED"


class DuplicateValueError(InfraError):
    """ค่าซ้ำกับแถวที่มีอยู่ — ชนิดแยกเพราะผู้เรียกต้องตอบผู้ใช้ต่างจากข้อผิดพลาดอื่น

    เพิ่มใน F-05: การสมัครด้วยอีเมลที่มีบัญชีแล้วต้องตอบว่าอีเมลถูกใช้แล้ว
    ไม่ใช่ "ฐานข้อมูลปฏิเสธคำสั่ง" ซึ่งผู้ใช้ทำอะไรต่อไม่ได้
    """

    code: ClassVar[str] = "DUPLICATE_VALUE"


class DatabaseUnavailableError(InfraError):
    """ต่อฐานข้อมูลไม่ได้"""

    code: ClassVar[str] = "DATABASE_UNAVAILABLE"


class SourceWriteScopeError(InfraError):
    code: ClassVar[str] = "SOURCE_WRITE_SCOPE_REQUIRED"


class DatabaseTimeoutError(InfraError):
    code: ClassVar[str] = "DATABASE_TIMEOUT"


class DatabaseRetryableError(InfraError):
    code: ClassVar[str] = "DATABASE_RETRYABLE"


class SourceMaintenanceScopeError(InfraError):
    code: ClassVar[str] = "SOURCE_MAINTENANCE_SCOPE_REQUIRED"


class SourceProofStateError(InfraError):
    code: ClassVar[str] = "SOURCE_PROOF_STATE"


class IndicatorBuildOwnershipError(InfraError):
    code: ClassVar[str] = "INDICATOR_BUILD_OWNERSHIP_LOST"


class IndicatorBuildConfigurationError(InfraError):
    code: ClassVar[str] = "INDICATOR_BUILD_CONFIGURATION"


class IndicatorBuildCounterError(InfraError):
    code: ClassVar[str] = "INDICATOR_BUILD_COUNTER_EXHAUSTED"


#: SQLSTATE ที่กลไกของ F-03 ใช้ ประกาศไว้ที่เดียว
SQLSTATE_APPEND_ONLY: Final[str] = "TT001"
SQLSTATE_INSUFFICIENT_PRIVILEGE: Final[str] = "42501"
SQLSTATE_CHECK_VIOLATION: Final[str] = "23514"
SQLSTATE_NUMERIC_VALUE_OUT_OF_RANGE: Final[str] = "22003"
SQLSTATE_INVALID_TEXT_REPRESENTATION: Final[str] = "22P02"
SQLSTATE_UNIQUE_VIOLATION: Final[str] = "23505"

_BY_SQLSTATE: Final[dict[str, type[InfraError]]] = {
    "40001": DatabaseRetryableError,
    "40P01": DatabaseRetryableError,
    "55P03": DatabaseTimeoutError,
    "57014": DatabaseTimeoutError,
    "TT011": SourceWriteScopeError,
    "TT012": SourceMaintenanceScopeError,
    "TT013": SourceProofStateError,
    "TT014": IndicatorBuildOwnershipError,
    "TT015": IndicatorBuildConfigurationError,
    "TT016": IndicatorBuildCounterError,
    SQLSTATE_APPEND_ONLY: AppendOnlyViolationError,
    SQLSTATE_INSUFFICIENT_PRIVILEGE: NotPermittedError,
    SQLSTATE_CHECK_VIOLATION: ValueRejectedError,
    SQLSTATE_NUMERIC_VALUE_OUT_OF_RANGE: ValueRejectedError,
    SQLSTATE_INVALID_TEXT_REPRESENTATION: ValueRejectedError,
    SQLSTATE_UNIQUE_VIOLATION: DuplicateValueError,
}


def sqlstate_of(error: BaseException) -> str | None:
    """อ่าน SQLSTATE จากข้อผิดพลาดของ driver โดยไม่พึ่งข้อความ

    ข้อความของ driver เปลี่ยนได้ทุกเวอร์ชันและมีค่าที่ส่งไปติดมาด้วย
    รหัส SQLSTATE เป็นสัญญาที่ PostgreSQL รักษาไว้
    """
    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        code = getattr(current, "sqlstate", None)
        if isinstance(code, str):
            return code
        code = getattr(current, "pgcode", None)
        if isinstance(code, str):
            return code
        current = getattr(current, "orig", None) or current.__cause__
    return None


def translate_database_error(error: BaseException) -> InfraError:
    """แปลงข้อผิดพลาดของ driver เป็นชนิดของเรา **โดยไม่พาข้อความดิบออกไป**

    ผู้เรียกต้อง `raise ... from None` เพื่อไม่ให้ traceback ของ driver ติดไปด้วย
    """
    if isinstance(error, SQLAlchemyTimeoutError):
        return DatabaseTimeoutError("หมดเวลารอฐานข้อมูล")
    code = sqlstate_of(error)
    if code is not None:
        kind = _BY_SQLSTATE.get(code)
        if kind is not None:
            return kind(f"ฐานข้อมูลปฏิเสธคำสั่ง (SQLSTATE {code})")
        return InfraError(f"ฐานข้อมูลปฏิเสธคำสั่ง (SQLSTATE {code})")
    return DatabaseUnavailableError("ติดต่อฐานข้อมูลไม่สำเร็จ")
