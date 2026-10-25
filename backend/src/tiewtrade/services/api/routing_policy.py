"""ขอบเขตของทุกเส้นทาง — **ตารางเดียวที่ทุกเส้นทางต้องมีแถวของตัวเอง** (F-06 RQ-6)

F-05 เก็บเรื่องนี้เป็นสองรายการแบบ allow-list ซึ่งพอสำหรับคำถาม "สาธารณะหรือไม่"
แต่ **ไม่พอสำหรับคำถาม "ต้องยืนยันซ้ำหรือไม่"** เพราะรายการแบบนั้นเงียบเมื่อมีคนลืม
ใส่เส้นทางที่เพิ่มความเสี่ยงลงไป — ความเงียบคือสิ่งที่ RQ-6 ห้าม

**ไม่มีค่าเริ่มต้นเงียบ** เส้นทางที่ไม่มีแถวในตารางนี้:

- ทำให้เทสต์ที่เดินทุกเส้นทางใน `app.routes` **แดง** (validation V-27)
- และถูก **ปฏิเสธตอนรัน** ที่ middleware ไม่ใช่ปล่อยผ่าน (validation V-28)

สองชั้นเพราะชั้นเดียวพังได้: เทสต์ครอบเฉพาะเส้นทางที่แอปประกาศตอนเทสต์รัน
ส่วน middleware ครอบทุกคำขอที่เข้ามาจริง

**`risk_reducing` ไม่ใช่ "ไม่ต้องยืนยันซ้ำ"** (RQ-7) — มันหมายถึง "เป็นคำสั่ง
ลดความเสี่ยงซึ่งต้องทำได้เร็วที่สุดเสมอ" ส่วนรีเซ็ตเพดานขาดทุนและเปิดบอทกลับ
เป็น **ข้อยกเว้นการยืนยันซ้ำที่เจ้าของอนุมัติไว้** ซึ่งคนละเรื่องกัน
สองอย่างนี้ต้องไม่ถูกรวมเป็นธงเดียว เพราะงานหลังจะหยิบไปใช้เป็นเกณฑ์ตัดสิน
ประเภทออเดอร์ผิด
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from starlette.routing import compile_path


@dataclass(frozen=True, slots=True)
class RouteRule:
    """การจัดประเภทของเส้นทางหนึ่ง — **ทุกช่องต้องตั้งใจ ไม่ใช่ปล่อยตามค่าปริยาย**

    ค่าปริยายของทุกช่องคือ "เข้มที่สุด": ต้องมี session, ไม่ต่ออายุ, ไม่ยืนยันซ้ำ,
    ไม่ใช่คำสั่งลดความเสี่ยง, และไม่รับสิทธิ์กู้บัญชี
    """

    #: เรียกได้โดยไม่ต้องมี session
    public: bool = False
    #: F-12 read-only POST validates browser Origin in addition to the shared CSRF check.
    checks_browser_origin: bool = False
    #: นับว่าเป็น "การใช้งาน" จึงเลื่อนเวลาหมดอายุของ session
    renews: bool = False
    #: ต้องยืนยันปัจจัยที่สองซ้ำ (`security.md` หัวข้อ 1)
    reverify: bool = False
    #: เป็นคำสั่งลดความเสี่ยง — **ห้ามบังคับยืนยันซ้ำ** (`trading-safety.md` หัวข้อ 8)
    risk_reducing: bool = False
    #: รับสิทธิ์กู้บัญชีแทนรหัส TOTP ได้ (Q-3.1 ช่อง ข และ ค)
    accepts_recovery_grant: bool = False

    def __post_init__(self) -> None:
        """ข้อที่ขัดกันเองต้องดังตอนประกาศ ไม่ใช่ตอนมีคนเรียกเส้นทางนั้น"""
        if self.risk_reducing and self.reverify:
            raise ValueError("คำสั่งลดความเสี่ยงต้องไม่ถูกบังคับยืนยันซ้ำ (RQ-7 ก.)")
        if self.public and self.renews:
            raise ValueError("เส้นทางสาธารณะไม่มี session ให้ต่ออายุ")
        if self.public and self.reverify:
            raise ValueError("เส้นทางสาธารณะยังไม่รู้ว่าเป็นใคร จึงยืนยันซ้ำไม่ได้")
        if self.accepts_recovery_grant and not self.reverify:
            raise ValueError("สิทธิ์กู้บัญชีใช้แทนรหัส TOTP ได้เฉพาะเส้นทางที่ต้องยืนยันซ้ำ")


#: เส้นทางที่ FastAPI สร้างให้เอง — **จัดประเภทไว้ด้วยโดยเจตนา**
#:
#: ใส่ไว้ในตารางเดียวกันแทนที่จะยกเว้นในเทสต์ เพราะรายการยกเว้นคือที่ที่เส้นทางจริง
#: แอบเข้าไปอยู่ได้ · ทั้งสี่เส้นทางนี้ต้องมี session เหมือนของ F-05
_GENERATED_RULE: Final[RouteRule] = RouteRule()

#: **ทุกเส้นทางของแอปต้องมีแถวที่นี่** — ที่เดียวที่ตอบคำถามเรื่องขอบเขตของเส้นทาง
#:
#: **กุญแจเป็น (เมธอด, path) ไม่ใช่ path เปล่า** (เจ้าของอนุมัติ 2026-10-04 พร้อม F-07)
#: — F-07 เป็นงานแรกที่ path เดียวมีสองเมธอดซึ่งมีกฎคนละอย่าง: `POST /api-keys`
#: เพิ่มความเสี่ยงจึงต้องยืนยันซ้ำ ส่วน `GET /api-keys` เป็นการอ่านที่หน้าเว็บเรียก
#: เป็นรอบ ๆ · ถ้ายังใช้ path เป็นกุญแจ กฎที่เข้มกว่าจะเหมารวมทั้งคู่ แล้วหน้าเว็บ
#: จะดูสถานะไม่ได้ถ้าไม่กรอกรหัสทุกรอบ
#:
#: **path ที่มีตัวแปรเขียนเป็นแม่แบบ** (`/api-keys/{key_id}`) ตามที่แอปประกาศ
#: ไม่ใช่ path จริงของคำขอ — ตัวหาแม่แบบอยู่ใน `authentication.py`
ROUTE_RULES: Final[dict[tuple[str, str], RouteRule]] = {
    # ── เส้นทางที่ FastAPI สร้างให้เอง ──
    ("GET", "/openapi.json"): _GENERATED_RULE,
    ("GET", "/docs"): _GENERATED_RULE,
    ("GET", "/docs/oauth2-redirect"): _GENERATED_RULE,
    ("GET", "/redoc"): _GENERATED_RULE,
    # ── สาธารณะ — สี่เส้นทางเท่านั้น (F-05) ──
    ("GET", "/health"): RouteRule(public=True),
    ("GET", "/auth/csrf"): RouteRule(public=True),
    ("POST", "/auth/register"): RouteRule(public=True),
    ("POST", "/auth/login"): RouteRule(public=True),
    # ── ต้องมี session และนับเป็นการใช้งาน (F-05) ──
    ("POST", "/auth/logout"): RouteRule(renews=True),
    ("POST", "/auth/logout-all"): RouteRule(renews=True),
    ("POST", "/auth/password"): RouteRule(renews=True),
    # ── ต้องมี session แต่ **ไม่ต่ออายุ** เพราะหน้าเว็บเรียกเป็นรอบ ๆ (Q-2) ──
    ("GET", "/auth/me"): RouteRule(),
    ("GET", "/market-data/candles"): RouteRule(),
    ("GET", "/market-data/candles/pages"): RouteRule(),
    ("GET", "/market-data/indicators"): RouteRule(),
    ("GET", "/market-data/prices"): RouteRule(),
    ("WEBSOCKET", "/market-data/prices/stream"): RouteRule(),
    ("POST", "/market-data/candles/requests"): RouteRule(),
    # ── ปัจจัยที่สอง (F-06) ──
    #
    # `setup` รับเฉพาะบัญชีที่ยังไม่เปิด TOTP โดยตรวจใต้ล็อกใน endpoint
    # และใช้รหัสผ่านปัจจุบันพิสูจน์ความเป็นเจ้าของ (RQ-3.1)
    # `confirm` ใช้รหัสจาก pending ที่ออกโดย setup หรือ replace ซึ่งยืนยันซ้ำแล้ว
    ("POST", "/auth/totp/setup"): RouteRule(renews=True),
    ("POST", "/auth/totp/confirm"): RouteRule(renews=True),
    # สามเส้นทางที่เปลี่ยนหรือถอนปัจจัยที่สอง **ต้องยืนยันซ้ำ**
    # · สองเส้นทางแรกรับสิทธิ์กู้บัญชีแทนรหัส TOTP ได้ เพราะเป็นทางออกของคนที่
    #   เสียเครื่อง (Q-3.1 ช่อง ข และ ค) ส่วนการขอชุดรหัสสำรองใหม่ไม่รับ
    #   เพราะรหัสสำรองต้องไม่ต่ออายุตัวเองได้
    ("POST", "/auth/totp/replace"): RouteRule(
        renews=True, reverify=True, accepts_recovery_grant=True
    ),
    ("POST", "/auth/totp/disable"): RouteRule(
        renews=True, reverify=True, accepts_recovery_grant=True
    ),
    ("POST", "/auth/totp/recovery-codes"): RouteRule(renews=True, reverify=True),
    # ── API key ของผู้ใช้ (F-07) ──
    #
    # **เพิ่ม key ต้องยืนยันซ้ำ และไม่รับรหัสสำรอง** — เป็นการกระทำที่เพิ่มความเสี่ยง
    # (`security.md` หัวข้อ 1) · `accepts_recovery_grant` ปล่อยเป็นค่าปริยายคือไม่รับ
    ("POST", "/api-keys"): RouteRule(renews=True, reverify=True),
    # **อ่านรายการไม่ต่ออายุและไม่ยืนยันซ้ำ** เพราะหน้าเว็บเรียกเป็นรอบ ๆ
    ("GET", "/api-keys"): RouteRule(),
    # **อ่านรายการไม่ต่ออายุ** เพราะหน้าเว็บเรียกเป็นรอบ ๆ เพื่อดูสถานะการตรวจ
    # (เหตุผลเดียวกับ `/auth/me` ของ F-05)
    ("DELETE", "/api-keys/{key_id}"): RouteRule(renews=True),
    ("POST", "/api-keys/{key_id}/retry"): RouteRule(renews=True),
    # Metadata only; initial account-use selection requires a fresh non-recovery TOTP.
    ("GET", "/market-data/chart/history"): RouteRule(),
    ("GET", "/market-data/chart/live"): RouteRule(),
    ("POST", "/market-data/chart/verify"): RouteRule(checks_browser_origin=True),
    ("GET", "/trading-account"): RouteRule(),
    ("POST", "/trading-account/use"): RouteRule(renews=True, reverify=True),
    ("GET", "/paper-wallet"): RouteRule(),
    ("POST", "/paper-wallet"): RouteRule(renews=True),
    ("POST", "/paper-wallet/reset"): RouteRule(renews=True),
    ("GET", "/paper-wallet/commands/{command_id}"): RouteRule(),
    # F-37 catalog reads do not extend sessions; every mutation requires a fresh
    # non-recovery TOTP and is authorized again by its stored function.
    ("GET", "/market-catalog"): RouteRule(),
    ("GET", "/admin/supported-symbols"): RouteRule(),
    ("GET", "/admin/supported-symbols/{base}/{quote}/impact"): RouteRule(),
    ("POST", "/admin/supported-symbols"): RouteRule(renews=True, reverify=True),
    ("DELETE", "/admin/supported-symbols/{base}/{quote}"): RouteRule(renews=True, reverify=True),
    ("POST", "/admin/supported-symbols/protocol/enable"): RouteRule(renews=True, reverify=True),
    # ขั้นที่สองของการเข้าสู่ระบบ — สาธารณะเพราะยังไม่มี session
    # และ **ไม่ต่ออายุ** เพราะยังไม่มี session ให้ต่อ
    ("POST", "/auth/totp/login"): RouteRule(public=True),
}

#: เส้นทางที่เรียกได้โดยไม่ต้องมี session — **คำนวณจากตารางเดียว**
#:
#: ยังมีชื่อนี้อยู่เพราะเทสต์และโค้ดของ F-05 อ้างถึง และความหมายไม่เปลี่ยน
#: (validation V-30) — เปลี่ยนแค่ว่าที่มาของมันคือแถวในตาราง ไม่ใช่รายการแยก
PUBLIC_ROUTES: Final[frozenset[tuple[str, str]]] = frozenset(
    key for key, rule in ROUTE_RULES.items() if rule.public
)

#: เส้นทางที่นับว่าเป็น "การใช้งาน" จึงเลื่อนเวลาหมดอายุ
RENEWING_ROUTES: Final[frozenset[tuple[str, str]]] = frozenset(
    key for key, rule in ROUTE_RULES.items() if rule.renews
)

#: เส้นทางที่ต้องยืนยันปัจจัยที่สองซ้ำ
REVERIFYING_ROUTES: Final[frozenset[tuple[str, str]]] = frozenset(
    key for key, rule in ROUTE_RULES.items() if rule.reverify
)

#: เส้นทางที่เป็นคำสั่งลดความเสี่ยง — **ยังว่างเพราะยังไม่มีเส้นทางเหล่านั้น**
#:
#: งานที่เพิ่มคำสั่งปิดไม้ ยกเลิกออเดอร์ หรือหยุดบอท ต้องใส่ชื่อของตัวเองที่นี่
#: ผ่านธง `risk_reducing` และ `RouteRule` จะปฏิเสธถ้าเผลอตั้ง `reverify` ด้วย
RISK_REDUCING_ROUTES: Final[frozenset[tuple[str, str]]] = frozenset(
    key for key, rule in ROUTE_RULES.items() if rule.risk_reducing
)


#: แม่แบบของ path ที่คอมไพล์เป็น regex ไว้แล้ว — **มาจากตารางเดียวกัน ไม่ใช่รายการที่สอง**
#:
#: เทียบเองแทนการถามเส้นทางที่ framework จับคู่ได้ เพราะ FastAPI รุ่นปัจจุบันห่อ
#: router ที่ `include_router` เข้ามาไว้ในตัวที่ไม่เปิดเผยแม่แบบของเส้นทางข้างใน
#: การพึ่งโครงสร้างภายในของมันคือการพึ่งสิ่งที่เปลี่ยนได้ทุกรุ่นโดยไม่มีสัญญา
#:
#: **ทิศทางที่อีกฝั่งยังถูกตรวจอยู่** — เทสต์ที่เดินทุกเส้นทางของแอปยืนยันว่า
#: ทุกเส้นทางมีแถวในตารางนี้ ฉะนั้นแม่แบบที่นี่กับเส้นทางจริงต้องตรงกันทั้งสองทาง
_COMPILED: Final[tuple[tuple[str, re.Pattern[str], str], ...]] = tuple(
    (method, compile_path(path)[0], path) for method, path in ROUTE_RULES
)


def classify(method: str, path: str) -> tuple[str, str] | None:
    """(เมธอด, แม่แบบ) ของคำขอนี้ — `None` เมื่อไม่มีแถวไหนรับ

    **เทียบแม่แบบ ไม่ใช่เทียบข้อความตรง ๆ** เพราะ path ที่มีตัวแปรมาถึงเป็นค่าจริง
    เสมอ (`/api-keys/8ac0…/retry`) การเทียบด้วยค่าจริงจะไม่เจอแถวของมันเลย
    """
    for candidate, pattern, template in _COMPILED:
        if candidate == method and pattern.fullmatch(path) is not None:
            return method, template
    return None


def rule_for(method: str, path: str) -> RouteRule | None:
    """การจัดประเภทของเส้นทางนั้น — `None` เมื่อยังไม่ถูกจัดประเภท

    ผู้เรียกต้อง **ปฏิเสธ** เมื่อได้ `None` ไม่ใช่เดาค่าให้ (RQ-6)
    """
    return ROUTE_RULES.get((method, path))


def is_public(method: str, path: str) -> bool:
    """เส้นทางนี้เรียกได้โดยไม่ต้องมี session หรือไม่

    เส้นทางที่ยังไม่ถูกจัดประเภทไม่ใช่สาธารณะ — ค่าเริ่มต้นคือปฏิเสธ
    """
    rule = rule_for(method, path)
    return rule is not None and rule.public


def renews_session(method: str, path: str) -> bool:
    """คำขอที่เส้นทางนี้รับ นับเป็นการใช้งานหรือไม่"""
    rule = rule_for(method, path)
    return rule is not None and rule.renews


def needs_reverification(method: str, path: str) -> bool:
    """เส้นทางนี้ต้องยืนยันปัจจัยที่สองซ้ำหรือไม่"""
    rule = rule_for(method, path)
    return rule is not None and rule.reverify


def accepts_recovery_grant(method: str, path: str) -> bool:
    """เส้นทางนี้รับสิทธิ์กู้บัญชีแทนรหัส TOTP ได้หรือไม่"""
    rule = rule_for(method, path)
    return rule is not None and rule.accepts_recovery_grant
