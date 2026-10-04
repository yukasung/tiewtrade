"""ชั้นเรียก HTTP ของ Binance TH — **ที่เดียวที่รู้จักเครือข่าย** (plan.md ข้อ 2)

ทุกการเรียกผ่านทางเดียวที่ทำสามอย่างตามลำดับ: **จองโควตา → เรียก → แปลผล**
ส่วนอื่นของตัวเชื่อมจึงไม่มีทางเรียกตลาดโดยข้ามตัวกั้นอัตรา

**timeout เป็นค่าที่ผู้เรียกกำหนด** ไม่ใช่ค่าตายตัวที่นี่ เพราะสเปกยังไม่มีตัวเลขนั้น
และงานที่ด่วนต่างกันรอได้ไม่เท่ากัน

**ไม่ลองใหม่อัตโนมัติเลย** การอ่านลองใหม่ได้ปลอดภัย แต่ยังไม่มีใครขอ (RQ-14)
และผู้เรียกเป็นคนเดียวที่รู้ว่างานนั้นด่วนแค่ไหน

**log ได้เฉพาะสามอย่าง**: ชื่อ endpoint แบบย่อ, สถานะ HTTP, รหัสของตลาด
ไม่มี URL เต็ม ไม่มี query string ไม่มี header ตาม `security.md` หัวข้อ 4 (RQ-9)
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final
from urllib.parse import urlencode

import httpx

from tiewtrade.venues.binance_th.endpoints import Endpoint
from tiewtrade.venues.binance_th.failures import (
    Delivery,
    failure_for_delivery,
    failure_for_status,
)
from tiewtrade.venues.binance_th.rate_limit import UsedWeightObserver
from tiewtrade.venues.errors import VenueProtocolError
from tiewtrade.venues.limits import CallCost, RateLimitGuard
from tiewtrade.venues.moments import require_aware
from tiewtrade.venues.signing import RequestSigner

#: ที่อยู่ของตลาดตามเอกสาร — Spot เท่านั้น ยังไม่มี Futures (NC-12)
BASE_URL: Final = "https://api.binance.th/api/v1"

#: header ที่ตลาดใช้รับส่วนที่เปิดเผยได้ของคำรับรอง (F-07)
_CREDENTIAL_HEADER: Final = "X-MBX-APIKEY"

#: ช่วงเวลาที่ตลาดยอมรับคำขอที่ลงลายเซ็นหนึ่งใบ
#:
#: ค่าของตลาดเอง ไม่ใช่ timeout ของเรา — มีไว้กันคำขอเก่าที่ถูกดักไว้แล้วส่งซ้ำทีหลัง
_RECEIVE_WINDOW: Final = timedelta(seconds=5)

_LOGGER = logging.getLogger(__name__)


class _WithoutQueryStrings(logging.Filter):
    """ตัดทุกอย่างหลัง `?` ออกจากข้อความ log

    **มีไว้กันไลบรารี HTTP เอง ไม่ใช่กันโค้ดของเรา** `httpx` เขียนบรรทัดระดับ INFO
    ที่มี URL เต็มพร้อม query string ทุกคำขอ และคำขอที่ลงลายเซ็นของตลาดนี้
    **พาลายเซ็นไปใน query string** ถ้าแอปเปิด log ระดับ INFO ของไลบรารีนั้น
    ความลับจะลงไฟล์ log ทันทีโดยที่โค้ดของเราไม่ได้เขียนอะไรเลย
    (`security.md` หัวข้อ 4, RQ-9)

    ตัดจากข้อความที่ประกอบเสร็จแล้ว ไม่ใช่จากค่าแต่ละตัว เพราะ URL โผล่ได้ทั้งใน
    รูปแบบและในค่าที่ส่งมาแทน และงานนี้ต้องไม่พลาดแม้แบบเดียว
    """

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        if "?" not in message:
            return True
        record.msg = _without_query_strings(message)
        record.args = None
        return True


def _without_query_strings(message: str) -> str:
    """ข้อความเดิมโดยตัดช่วงตั้งแต่ `?` ถึงช่องว่างถัดไปออก"""
    return re.sub(r"\?\S*", "?<ตัดออก>", message)


def _hide_query_strings_from(logger_name: str) -> None:
    """ติดตัวกรองให้ logger ของไลบรารีหนึ่ง แบบติดซ้ำไม่ได้"""
    logger = logging.getLogger(logger_name)
    if not any(isinstance(existing, _WithoutQueryStrings) for existing in logger.filters):
        logger.addFilter(_WithoutQueryStrings())


# ติดตั้งตอน import โดยเจตนา — ถ้าเป็นฟังก์ชันที่แอปต้องเรียกเอง วันหนึ่งจะมีคนลืมเรียก
# แล้วความลับจะหลุดลง log โดยไม่มีใครรู้ ตัวกรองนี้ไม่เปลี่ยนระดับ log ของใคร
# และไม่ปิดบรรทัดไหน มันตัดแค่ query string ออกจากข้อความ
_hide_query_strings_from("httpx")
_hide_query_strings_from("httpcore")

#: header ที่ตลาดใช้บอกยอดน้ำหนักสะสมของ IP ในหน้าต่างนั้น เช่น `x-mbx-used-weight-1m`
_USED_WEIGHT_HEADER = re.compile(r"^x-mbx-used-weight-(\d+)([smhd])$")

_SPAN_UNITS: Final[Mapping[str, str]] = {
    "s": "seconds",
    "m": "minutes",
    "h": "hours",
    "d": "days",
}

#: ข้อผิดพลาดที่เกิด **ก่อน** คำขอออกไปครบ — ลองใหม่ได้ปลอดภัยเพราะยังไม่มีอะไรถึงตลาด
_NOT_SENT_ERRORS: Final = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.PoolTimeout,
    httpx.ProxyError,
    httpx.UnsupportedProtocol,
    httpx.WriteError,
    httpx.WriteTimeout,
)


@dataclass(frozen=True, slots=True)
class VenueResponse:
    """คำตอบที่อ่านสำเร็จแล้วหนึ่งคำตอบ

    มีเท่าที่ผู้เรียกใช้จริง — สถานะ HTTP กับ body ดิบไม่อยู่ที่นี่ เพราะคำตอบที่
    ไม่สำเร็จไม่เคยมาถึงชนิดนี้ (ถูกแปลเป็นชนิดกลางไปแล้ว) และสคริปต์เก็บข้อมูล
    บันทึกคำตอบดิบจากฝั่งของมันเอง ช่องที่ไม่มีใครอ่านคือช่องที่ต้องดูแลเปล่า ๆ
    """

    #: โครงสร้างที่อ่านจาก JSON โดย **ไม่มีทศนิยมลอยตัว** — ตัวเลขที่มีจุดเป็นข้อความ
    payload: object
    #: ยอดน้ำหนักสะสมของ IP ที่ตลาดรายงาน แยกตามหน้าต่างเวลา
    used_weight: Mapping[timedelta, int]
    received_at: datetime


class BinanceThTransport:
    """ทางเดียวที่ตัวเชื่อมใช้คุยกับตลาด"""

    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        guard: RateLimitGuard,
        clock: Callable[[], datetime],
        timeout: timedelta,
        base_url: str = BASE_URL,
    ) -> None:
        if timeout <= timedelta(0):
            raise ValueError("timeout ต้องมากกว่าศูนย์")
        self._client = client
        self._guard = guard
        self._clock = clock
        self._timeout = timeout
        self._base_url = base_url.rstrip("/")

    async def get(
        self,
        endpoint: Endpoint,
        *,
        cost: CallCost,
        params: Mapping[str, str] | None = None,
        changes_state: bool = False,
    ) -> VenueResponse:
        """เรียก endpoint หนึ่งแบบอ่านข้อมูล แล้วคืนคำตอบที่อ่านสำเร็จ

        ล้มเหลวเมื่อไรก็โยนชนิดกลางของ F-33 เสมอ — **ไม่ปล่อยข้อผิดพลาดของไลบรารี
        HTTP ออกไปข้างนอก** เพราะชั้นข้างนอกต้องไม่รู้ว่าเราต่อตลาดด้วยอะไร
        """
        if endpoint.needs_signature:
            raise ValueError(f"{endpoint.name} ต้องลงลายเซ็น — ใช้ signed_get")

        await self._guard.reserve(cost)
        response = await self._fetch(endpoint, params)

        received_at = self._now()
        used_weight = used_weight_of(response.headers)
        self._feed_back(used_weight, received_at)

        self._reject_if_failed(endpoint, response, changes_state=changes_state)
        return VenueResponse(
            payload=_parsed(response.text),
            used_weight=used_weight,
            received_at=received_at,
        )

    async def signed_get(
        self,
        endpoint: Endpoint,
        *,
        signer: RequestSigner,
        cost: CallCost,
        params: Mapping[str, str] | None = None,
    ) -> VenueResponse:
        """เรียก endpoint ที่ต้องลงลายเซ็น — **ที่นี่ไม่เคยเห็น secret** (F-07 Q-2)

        ประกอบ query string ให้ครบก่อน แล้วค่อยลงลายเซ็นของสิ่งที่จะส่งจริง
        **ห้ามต่อพารามิเตอร์เพิ่มหลังลงลายเซ็นเด็ดขาด** — ลายเซ็นจะไม่ตรงกับคำขอ
        และตลาดจะปฏิเสธด้วยรหัสที่อ่านเหมือน "คำรับรองผิด" ซึ่งทำให้เราไปปฏิเสธ
        key ที่ถูกต้องของผู้ใช้ (validation V-37)

        ส่ง query string ที่ลงลายเซ็นไว้ไปทั้งก้อน ไม่ใช่ส่งเป็นพจนานุกรมให้ไลบรารี
        ประกอบใหม่ เพราะการประกอบใหม่อาจเรียงหรือเข้ารหัสอักขระต่างออกไป
        """
        signed = self._signed_query(params)
        await self._guard.reserve(cost)
        response = await self._fetch(
            endpoint,
            None,
            query=f"{signed}&signature={signer.sign(signed)}",
            headers={_CREDENTIAL_HEADER: signer.public_identifier},
        )

        received_at = self._now()
        used_weight = used_weight_of(response.headers)
        self._feed_back(used_weight, received_at)

        self._reject_if_failed(endpoint, response, changes_state=False)
        return VenueResponse(
            payload=_parsed(response.text),
            used_weight=used_weight,
            received_at=received_at,
        )

    def _signed_query(self, params: Mapping[str, str] | None) -> str:
        """ข้อความที่จะถูกลงลายเซ็น — **เท่ากับ query string ที่ส่งจริงทุกตัวอักษร**"""
        fields = dict(params or {})
        fields["timestamp"] = str(int(self._now().timestamp() * 1000))
        fields["recvWindow"] = str(int(_RECEIVE_WINDOW.total_seconds() * 1000))
        return urlencode(fields)

    async def _fetch(
        self,
        endpoint: Endpoint,
        params: Mapping[str, str] | None,
        *,
        query: str | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> httpx.Response:
        """เรียกออกไปจริง — ความล้มเหลวที่ชั้นเครือข่ายกลายเป็นชนิดกลางที่นี่"""
        url = f"{self._base_url}{endpoint.path}"
        try:
            return await self._client.get(
                f"{url}?{query}" if query is not None else url,
                params=None if query is not None else dict(params or {}),
                headers=dict(headers or {}),
                timeout=self._timeout.total_seconds(),
            )
        except httpx.HTTPError as error:
            delivery = (
                Delivery.NOT_SENT
                if isinstance(error, _NOT_SENT_ERRORS)
                else Delivery.SENT_UNANSWERED
            )
            # **ชื่อชนิดเท่านั้น ไม่เอาข้อความ** ข้อความของไลบรารี HTTP พา URL เต็ม
            # (รวม query string ที่คำขอลงลายเซ็นพาความลับไป) ติดมาด้วย
            _LOGGER.warning(
                "เรียก %s ไม่สำเร็จ (%s/%s)", endpoint.name, delivery.value, type(error).__name__
            )

        # โยน **นอก** บล็อกที่ดัก: `from None` ปิดแค่การแสดงผล แต่ยังเก็บ exception
        # ต้นทางไว้ใน `__context__` ให้เครื่องมือที่เดินตามสายนั้นเห็นข้อความเดิมทั้งหมด
        # การโยนหลังออกจากบล็อกทำให้ไม่มีสายให้เดินตั้งแต่ต้น (V-25.1)
        raise failure_for_delivery(delivery)

    def _reject_if_failed(
        self, endpoint: Endpoint, response: httpx.Response, *, changes_state: bool
    ) -> None:
        """คำตอบที่ไม่สำเร็จกลายเป็นชนิดกลางที่นี่

        **จัดกลุ่มตามสถานะ HTTP ก่อนอ่าน body** คำตอบ `429` หรือ `5xx` ที่มาจาก
        ไฟร์วอลล์หรือตัวกลางเป็นหน้า HTML ได้ ถ้าอ่าน JSON ก่อน คำตอบเหล่านั้น
        จะกลายเป็น "สัญญาไม่ตรง" ทั้งหมด แล้วเสีย `Retry-After` ไปด้วย
        """
        if response.status_code == httpx.codes.OK:
            return

        market_code = _market_code(response.text)
        _LOGGER.warning(
            "ตลาดปฏิเสธการเรียก %s สถานะ %s รหัสของตลาด %s",
            endpoint.name,
            response.status_code,
            market_code,
        )
        raise failure_for_status(
            status=response.status_code,
            market_code=market_code,
            retry_after=_retry_after(response.headers),
            changes_state=changes_state,
        )

    def _now(self) -> datetime:
        now = self._clock()
        require_aware("เวลาที่ระบบรับข้อมูลจากตลาด", now)
        return now

    def _feed_back(self, used_weight: Mapping[timedelta, int], at: datetime) -> None:
        """ส่งยอดที่ตลาดนับเองกลับไปให้ตัวกั้น — **ทำก่อนตรวจสถานะ**

        คำตอบ `429` ก็พา header นี้มาด้วย และเป็นจังหวะที่ตัวกั้นต้องรู้มากที่สุด
        """
        if not isinstance(self._guard, UsedWeightObserver):
            return
        for span, used in used_weight.items():
            self._guard.observe_used_weight(span=span, used=used, at=at)


def _parsed(body: str) -> object:
    """อ่าน JSON โดย **ไม่สร้างทศนิยมลอยตัวแม้ชั่วคราว**

    `parse_float=str` ทำให้ตัวเลขที่มีจุดคงเป็นตัวหนังสือเดิมทุกตัวอักษร
    การปล่อยให้เป็น `float` ก่อนแล้วแปลงกลับเป็นข้อความทีหลังคือการเสียค่าไปแล้ว

    **ไม่ผูกข้อผิดพลาดต้นทางไว้** ข้อความของตัวอ่าน JSON พาเนื้อ body ส่วนหนึ่ง
    ติดมาด้วย ซึ่งเป็นค่าที่มาจากข้างนอกและเราไม่ได้ควบคุม (RQ-9)
    """
    if not body:
        raise VenueProtocolError()
    try:
        return json.loads(body, parse_float=str)
    except ValueError:
        pass

    # โยนนอกบล็อกที่ดัก ด้วยเหตุผลเดียวกับใน `get` — ข้อความของตัวอ่าน JSON
    # พาเนื้อ body ส่วนหนึ่งติดมา
    raise VenueProtocolError()


def _market_code(body: str) -> int | None:
    """รหัสของตลาดจากคำตอบที่ไม่สำเร็จ — รูป `{"code": -1121, "msg": "..."}`

    อ่าน body เองที่นี่เพราะคำตอบที่ไม่สำเร็จอ่านเป็น JSON ไม่ได้ก็มี (หน้า HTML
    ของไฟร์วอลล์) **อ่านไม่ออกคือไม่มีรหัส ไม่ใช่สัญญาไม่ตรง** การจัดกลุ่มยังอยู่
    ที่สถานะ HTTP ซึ่งเชื่อถือได้เสมอ

    **ไม่อ่าน `msg`** เพราะข้อความของตลาดพาค่าที่ส่งไปติดมาได้ (RQ-9)
    """
    try:
        payload = json.loads(body) if body else None
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None
    code = payload.get("code")
    if isinstance(code, bool) or not isinstance(code, int):
        return None
    return code


def _retry_after(headers: httpx.Headers) -> timedelta | None:
    """เวลาที่ตลาดบอกให้รอ — ไม่มีก็เป็นค่าว่าง **ห้ามเดาแทนตลาด**"""
    raw = headers.get("retry-after")
    if raw is None:
        return None
    try:
        seconds = int(raw.strip())
    except ValueError:
        # รูปแบบวันที่ตาม HTTP ก็ถูกตามมาตรฐาน แต่แปลงแล้วต้องใช้นาฬิกาของเรา
        # เทียบกับของตลาด ซึ่งเป็นการเดาเวลาที่เราไม่มีสิทธิ์เดา
        return None
    return timedelta(seconds=seconds) if seconds >= 0 else None


def used_weight_of(headers: Mapping[str, str]) -> Mapping[timedelta, int]:
    """ยอดน้ำหนักสะสมที่ตลาดรายงาน แยกตามหน้าต่างเวลาที่ตลาดบอก

    เปิดให้เรียกจากข้างนอกเพราะสคริปต์เก็บข้อมูลต้องอ่าน header ชุดเดียวกัน
    **รูปแบบชื่อ header ของตลาดจึงอยู่ที่นี่ที่เดียว** ไม่ใช่ที่นี่กับในสคริปต์

    **เป็นยอดสะสมของ IP ในหน้าต่างนั้น ไม่ใช่ต้นทุนของคำขอเดียว** — การพิสูจน์ว่า
    weight ที่เราประกาศถูกต้องจึงต้องดูผลต่างระหว่างคำขอ (plan.md ข้อ 2.1)
    """
    found: dict[timedelta, int] = {}
    for name, value in headers.items():
        matched = _USED_WEIGHT_HEADER.match(name.lower())
        if matched is None:
            continue
        try:
            used = int(value)
        except ValueError:
            continue
        span = timedelta(**{_SPAN_UNITS[matched.group(2)]: int(matched.group(1))})
        found[span] = used
    return found
