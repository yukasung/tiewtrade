"""การแปลข้อผิดพลาด — V-20 ถึง V-26

ทุกบรรทัดในตารางแปลข้อผิดพลาดของ plan ข้อ 3 มีเทสต์ของตัวเอง
"""

from __future__ import annotations

import json
import logging
import traceback
from datetime import timedelta

import httpx
import pytest

from tests.venues.binance_th.conftest import (
    RecordingGuard,
    recorded,
    recorded_body,
    replying,
    requests_to,
    transport_for,
)
from tiewtrade.venues.binance_th.endpoints import Endpoint
from tiewtrade.venues.binance_th.failures import (
    Delivery,
    failure_for_delivery,
    failure_for_status,
)
from tiewtrade.venues.binance_th.prices import LATEST_PRICE_COST
from tiewtrade.venues.errors import (
    RejectionReason,
    VenueCredentialRejectedError,
    VenueError,
    VenueOutcomeUnknownError,
    VenueProtocolError,
    VenueRateLimitedError,
    VenueRejectedError,
    VenueUnavailableError,
)

#: ค่าที่แกล้งทำเป็นความลับ ใช้พิสูจน์ว่าไม่มีอะไรจากคำขอหลุดเข้าข้อความหรือ log
PRETEND_SECRET = "sEcReT-kEy-0123456789"


def test_not_sent_is_unavailable_and_sent_without_an_answer_is_unknown() -> None:
    """V-21 — สองกรณีนี้ต้องแยกกันด้วยชนิด เพราะข้อหลังห้ามส่งซ้ำ"""
    assert isinstance(failure_for_delivery(Delivery.NOT_SENT), VenueUnavailableError)
    assert isinstance(failure_for_delivery(Delivery.SENT_UNANSWERED), VenueOutcomeUnknownError)


@pytest.mark.parametrize(
    ("status", "market_code", "expected"),
    [
        (429, None, VenueRateLimitedError),
        (418, None, VenueRateLimitedError),
        (200, -1003, VenueRateLimitedError),
        (401, None, VenueCredentialRejectedError),
        (400, -1022, VenueCredentialRejectedError),
        (400, -2014, VenueCredentialRejectedError),
        (400, -2015, VenueCredentialRejectedError),
        (503, None, VenueUnavailableError),
        (400, -1121, VenueRejectedError),
        (400, -1013, VenueRejectedError),
        (400, -1111, VenueRejectedError),
        (403, None, VenueRejectedError),
        (400, -99999, VenueRejectedError),
        (404, None, VenueRejectedError),
    ],
)
def test_each_row_of_the_table_lands_on_its_own_kind(
    status: int, market_code: int | None, expected: type[VenueError]
) -> None:
    """V-20 — ตารางแปลข้อผิดพลาดถูกต้องทีละบรรทัด"""
    failure = failure_for_status(status=status, market_code=market_code, changes_state=False)
    assert isinstance(failure, expected)


def test_a_server_error_on_a_read_can_be_retried_but_on_a_write_cannot() -> None:
    """V-20 — `5xx` ของการอ่านคือ "ลองใหม่ได้" ของคำสั่งคือ "ไม่รู้ผล" """
    read = failure_for_status(status=500, market_code=None, changes_state=False)
    write = failure_for_status(status=500, market_code=None, changes_state=True)
    assert isinstance(read, VenueUnavailableError)
    assert isinstance(write, VenueOutcomeUnknownError)


def test_forbidden_is_not_a_credential_failure() -> None:
    """V-20.1 — `403` คือถูกไฟร์วอลล์ปฏิเสธ ไม่ได้พิสูจน์ว่ากุญแจผิด

    ถ้าแปลเป็นเรื่องกุญแจ ผู้เรียกจะหยุดบอทด้วยสาเหตุที่ผิด ตาม
    `trading-safety.md` หัวข้อ 2 ที่สั่งให้หยุดทันทีเมื่อกุญแจถูกปฏิเสธ
    """
    failure = failure_for_status(status=403, market_code=None, changes_state=False)
    assert not isinstance(failure, VenueCredentialRejectedError)
    assert isinstance(failure, VenueRejectedError)
    assert failure.reason is RejectionReason.UNEXPLAINED


def test_unauthorized_is_a_credential_failure() -> None:
    """V-20.1 — คู่กันของกรณีข้างบน `401` ต้องเป็นเรื่องกุญแจจริง"""
    failure = failure_for_status(status=401, market_code=None, changes_state=False)
    assert isinstance(failure, VenueCredentialRejectedError)


def test_an_unknown_market_code_is_unexplained_not_squeezed_into_another_reason() -> None:
    """V-22 — รหัสที่ไม่รู้จักต้องไม่ถูกยัดเข้าเหตุผลที่บอกสาเหตุชัดเจน"""
    failure = failure_for_status(status=400, market_code=-31337, changes_state=False)
    assert isinstance(failure, VenueRejectedError)
    assert failure.reason is RejectionReason.UNEXPLAINED


def test_the_recorded_rejection_becomes_an_unknown_symbol() -> None:
    """V-20 — รหัสจริงที่ตลาดส่งมา (`-1121`) แปลเป็นเหตุผลที่ตรงตัว"""
    body = json.loads(recorded_body("rejected_unknown_symbol"))
    assert body["code"] == -1121
    failure = failure_for_status(status=400, market_code=-1121, changes_state=False)
    assert isinstance(failure, VenueRejectedError)
    assert failure.reason is RejectionReason.UNKNOWN_SYMBOL


def test_the_recorded_malformed_request_is_unexplained() -> None:
    """V-22 — `-1102` (คำขอผิดรูป) ไม่มีเหตุผลกลางที่ตรงตัว จึงต้องให้คนมาดู"""
    body = json.loads(recorded_body("rejected_bad_limit"))
    assert body["code"] == -1102
    failure = failure_for_status(status=400, market_code=-1102, changes_state=False)
    assert isinstance(failure, VenueRejectedError)
    assert failure.reason is RejectionReason.UNEXPLAINED


@pytest.mark.parametrize("status", [429, 418])
async def test_retry_after_is_carried_when_the_market_sends_it(status: int) -> None:
    """V-24 — มีเวลาให้ก็พาไป"""
    transport = transport_for(replying("{}", status=status, headers={"Retry-After": "7"}))
    with pytest.raises(VenueRateLimitedError) as caught:
        await transport.get(Endpoint.TRADES, cost=LATEST_PRICE_COST)
    assert caught.value.retry_after == timedelta(seconds=7)


async def test_retry_after_stays_empty_when_the_market_does_not_send_it() -> None:
    """V-24 — ไม่มีก็เป็นค่าว่าง **ห้ามเดาเวลาแทนตลาด**"""
    transport = transport_for(replying("{}", status=429))
    with pytest.raises(VenueRateLimitedError) as caught:
        await transport.get(Endpoint.TRADES, cost=LATEST_PRICE_COST)
    assert caught.value.retry_after is None


async def test_a_retry_after_we_cannot_read_stays_empty() -> None:
    """รูปแบบวันที่ตาม HTTP ก็ถูก แต่แปลงแล้วต้องใช้นาฬิกาของเราเทียบ ซึ่งเป็นการเดา"""
    transport = transport_for(
        replying("{}", status=429, headers={"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"})
    )
    with pytest.raises(VenueRateLimitedError) as caught:
        await transport.get(Endpoint.TRADES, cost=LATEST_PRICE_COST)
    assert caught.value.retry_after is None


async def test_a_connection_that_never_opened_is_unavailable() -> None:
    """V-21 — ต่อไม่ติด → ยังไม่ได้ส่งอะไรออกไป ลองใหม่ได้ปลอดภัย"""

    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("ต่อไม่ติด", request=request)

    transport = transport_for(refuse)
    with pytest.raises(VenueUnavailableError):
        await transport.get(Endpoint.TRADES, cost=LATEST_PRICE_COST)


async def test_a_timeout_after_the_request_went_out_is_an_unknown_outcome() -> None:
    """V-21 — ส่งครบแล้วไม่ได้คำตอบ → **ไม่รู้ผล** ห้ามถือว่าไม่เกิดอะไร"""

    def stall(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("รอคำตอบนานเกินไป", request=request)

    transport = transport_for(stall)
    with pytest.raises(VenueOutcomeUnknownError):
        try:
            await transport.get(Endpoint.TRADES, cost=LATEST_PRICE_COST)
        except VenueUnavailableError:  # pragma: no cover - ต้องไม่เข้าทางนี้
            pytest.fail("timeout หลังส่งครบถูกแปลเป็น VenueUnavailableError")


async def test_nothing_from_the_http_library_survives_in_the_traceback() -> None:
    """V-25 — `raise ... from error` เก็บข้อความต้นทางไว้ใน traceback

    ข้อความของไลบรารี HTTP พา URL เต็มพร้อม query string ติดมาได้ ซึ่งเป็นที่ที่
    คำขอลงลายเซ็นพาความลับไป traceback ถูกพิมพ์ลง log และลงหน้าจอได้ทุกที่
    ตัวกรองของ logger จึงครอบไม่ถึง — ทางเดียวคือไม่ผูก exception ต้นทางไว้เลย
    """

    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(
            f"ต่อ https://example.invalid/trades?signature={PRETEND_SECRET} ไม่ติด",
            request=request,
        )

    transport = transport_for(refuse)
    with pytest.raises(VenueUnavailableError) as caught:
        await transport.get(Endpoint.TRADES, cost=LATEST_PRICE_COST)

    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    written = "".join(traceback.format_exception(caught.value))
    assert PRETEND_SECRET not in written
    assert "signature" not in written


async def test_the_log_names_the_http_failure_by_type_not_by_message(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """ชื่อชนิดช่วยหาสาเหตุได้และไม่พาค่าจากคำขอไปด้วย"""

    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"signature={PRETEND_SECRET}", request=request)

    transport = transport_for(refuse)
    with caplog.at_level(logging.DEBUG), pytest.raises(VenueUnavailableError):
        await transport.get(Endpoint.TRADES, cost=LATEST_PRICE_COST)

    assert "ConnectError" in caplog.text
    assert PRETEND_SECRET not in caplog.text


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (429, VenueRateLimitedError),
        (503, VenueUnavailableError),
        (403, VenueRejectedError),
    ],
)
async def test_a_failure_page_that_is_not_json_is_still_grouped_by_status(
    status: int, expected: type[VenueError]
) -> None:
    """V-20 — คำตอบที่ไม่สำเร็จเป็นหน้า HTML ได้ (ไฟร์วอลล์หรือตัวกลางของตลาด)

    ถ้าอ่าน JSON ก่อนตรวจสถานะ คำตอบเหล่านี้จะกลายเป็น "สัญญาไม่ตรง" ทั้งหมด
    ซึ่งทำให้งาน CI รายวันแดงตอนตลาดล่ม และทำให้ผู้เรียกไม่รู้ว่าต้องรอ
    """
    transport = transport_for(
        replying("<html><body>Service Unavailable</body></html>", status=status)
    )
    with pytest.raises(expected):
        await transport.get(Endpoint.TRADES, cost=LATEST_PRICE_COST)


async def test_a_rate_limit_page_that_is_not_json_still_carries_the_wait() -> None:
    """V-24 — `Retry-After` ต้องไม่หายไปเพราะ body อ่านไม่ออก"""
    transport = transport_for(
        replying("<html>too many requests</html>", status=429, headers={"Retry-After": "30"})
    )
    with pytest.raises(VenueRateLimitedError) as caught:
        await transport.get(Endpoint.TRADES, cost=LATEST_PRICE_COST)
    assert caught.value.retry_after == timedelta(seconds=30)


async def test_a_body_we_cannot_parse_is_a_protocol_error() -> None:
    """V-23 — อ่านคำตอบไม่ออก → `VenueProtocolError`"""
    transport = transport_for(replying("ไม่ใช่ JSON"))
    with pytest.raises(VenueProtocolError):
        await transport.get(Endpoint.TRADES, cost=LATEST_PRICE_COST)


async def test_an_empty_body_with_a_success_status_is_a_protocol_error() -> None:
    """คำตอบว่างเปล่าที่บอกว่าสำเร็จคือสัญญาที่เราอ่านไม่ออก ไม่ใช่ข้อมูลที่ไม่มี"""
    transport = transport_for(replying(""))
    with pytest.raises(VenueProtocolError):
        await transport.get(Endpoint.TRADES, cost=LATEST_PRICE_COST)


async def test_nothing_from_the_request_reaches_the_message_or_the_log(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """V-25 — ไม่มี key, query string หรือ URL เต็มในข้อความ error และใน log"""
    transport = transport_for(replying('{"code":-1121,"msg":"Invalid symbol."}', status=400))

    with caplog.at_level(logging.DEBUG), pytest.raises(VenueError) as caught:
        await transport.get(
            Endpoint.TRADES,
            cost=LATEST_PRICE_COST,
            params={"symbol": "BTCTHB", "signature": PRETEND_SECRET},
        )

    ours = "\n".join(
        record.getMessage() for record in caplog.records if record.name.startswith("tiewtrade")
    )
    others = "\n".join(
        record.getMessage() for record in caplog.records if not record.name.startswith("tiewtrade")
    )

    # ข้อความ error และ log ของเราเอง: ไม่มีความลับ ไม่มี query string และไม่มี URL
    everything_ours = str(caught.value) + ours
    assert PRETEND_SECRET not in everything_ours
    assert "signature" not in everything_ours
    assert "symbol=" not in everything_ours
    assert "api.binance.th" not in everything_ours
    assert "://" not in everything_ours

    # ที่ต้องมีคือสามอย่างที่อนุญาต: endpoint แบบย่อ สถานะ และรหัสของตลาด
    assert Endpoint.TRADES.name in ours
    assert "400" in ours
    assert "-1121" in ours

    # log ของไลบรารี HTTP เขียนที่อยู่ของตลาดเองได้ (ที่อยู่นั้นอยู่ในซอร์สโค้ดอยู่แล้ว)
    # แต่ **ต้องไม่มี query string** ซึ่งเป็นที่ที่คำขอที่ลงลายเซ็นพาความลับไป
    assert PRETEND_SECRET not in others
    assert "signature" not in others
    assert "symbol=" not in others


async def test_the_market_message_never_leaves_the_adapter() -> None:
    """V-25 — ข้อความของตลาดพาค่าที่ส่งไปติดมาได้ จึงไม่ถูกอ่านเลย"""
    leaky = f'{{"code":-1105,"msg":"Parameter signature={PRETEND_SECRET} was empty."}}'
    transport = transport_for(replying(leaky, status=400))

    with pytest.raises(VenueError) as caught:
        await transport.get(Endpoint.TRADES, cost=LATEST_PRICE_COST)
    assert PRETEND_SECRET not in str(caught.value)


@pytest.mark.parametrize(
    "handler_status",
    [400, 401, 403, 429, 500, 503],
)
async def test_a_failed_call_is_never_retried(handler_status: int) -> None:
    """V-26 — ไม่ลองใหม่อัตโนมัติเลยในงานนี้ — นับจำนวนคำขอที่ออกไปจริง"""
    handler, seen = requests_to(replying('{"code":-1}', status=handler_status))
    transport = transport_for(handler)

    with pytest.raises(VenueError):
        await transport.get(Endpoint.TRADES, cost=LATEST_PRICE_COST)
    assert len(seen) == 1


async def test_the_quota_is_reserved_before_the_call_even_when_it_fails() -> None:
    """V-27 — จองก่อนเรียกทุกครั้ง รวมกรณีที่การเรียกนั้นล้มเหลว"""
    guard = RecordingGuard()

    def refuse(request: httpx.Request) -> httpx.Response:
        assert guard.reserved == [LATEST_PRICE_COST], "เรียกออกไปก่อนจองโควตา"
        raise httpx.ConnectError("ต่อไม่ติด", request=request)

    transport = transport_for(refuse, guard=guard)
    with pytest.raises(VenueUnavailableError):
        await transport.get(Endpoint.TRADES, cost=LATEST_PRICE_COST)
    assert guard.reserved == [LATEST_PRICE_COST]


def test_the_recorded_rejections_cover_both_a_known_and_an_unknown_code() -> None:
    """V-36 — ข้อมูลที่บันทึกไว้มีกรณีที่ตลาดปฏิเสธจริง ไม่ใช่กรณีสำเร็จอย่างเดียว"""
    for name in ("rejected_unknown_symbol", "rejected_bad_limit"):
        entry = recorded(name)
        assert entry["status"] == 400
        assert "code" in json.loads(str(entry["body"]))
