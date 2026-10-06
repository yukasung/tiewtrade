"""กระเป๋าของ Binance TH — V-37 ถึง V-41 (F-07)

**ไม่ยิงตลาดจริง** ใช้คำตอบที่บันทึกรูปร่างไว้กับตัวดักคำขอ ส่วนการเทียบกับตลาดจริง
อยู่ในด่านแยกตามแบบแผนของ F-35

สิ่งที่ไฟล์นี้ปกป้อง: ลายเซ็นต้องตรงกับคำขอที่ส่งจริง และยอดที่อ่านมาต้องถูกต้อง
โดยไม่ผ่านทศนิยมลอยตัว · `FakeVenue` พิสูจน์สองข้อนี้ให้ไม่ได้ เพราะมันไม่ได้
ประกอบคำขอและไม่ได้อ่านคำตอบของตลาด
"""

from __future__ import annotations

import hashlib
import hmac
import json
from decimal import Decimal
from urllib.parse import parse_qsl

import pytest

from tiewtrade.core.money import Quantity
from tiewtrade.infra.api_keys import HmacRequestSigner
from tiewtrade.venues.binance_th.wallets import HOLDINGS_COST, BinanceThWallet
from tiewtrade.venues.errors import VenueCredentialRejectedError, VenueProtocolError

from .conftest import RecordingGuard, replying, requests_to, shaped_body, transport_for

PUBLIC = "PUBLICKEY000000ABCD"
SECRET = b"a-secret-only-the-engine-has"


def _signer() -> HmacRequestSigner:
    return HmacRequestSigner(public_identifier=PUBLIC, secret=SECRET)


async def test_the_signature_matches_the_request_that_was_actually_sent() -> None:
    """V-37 — คำนวณลายเซ็นของ query string ที่เห็นจริงซ้ำ แล้วต้องตรงกัน

    จับกรณีที่อันตรายที่สุดของการลงลายเซ็น: เซ็นก่อนแล้วต่อพารามิเตอร์เพิ่มทีหลัง
    ตลาดจะปฏิเสธด้วยรหัสที่อ่านเหมือน "คำรับรองผิด" แล้วเราจะไปปฏิเสธ key
    ที่ถูกต้องของผู้ใช้
    """
    handler, seen = requests_to(replying(shaped_body("account_shape")))
    wallet = BinanceThWallet(transport_for(handler), _signer())

    await wallet.holdings()

    sent = seen[0].url.query.decode()
    fields = dict(parse_qsl(sent))
    signature = fields.pop("signature")
    signed_part = sent.split("&signature=")[0]

    assert hmac.new(SECRET, signed_part.encode(), hashlib.sha256).hexdigest() == signature
    # ทุกช่องที่ส่งไปอยู่ในข้อความที่เซ็น — ไม่มีช่องไหนถูกต่อเพิ่มหลังเซ็น
    assert set(fields) == set(dict(parse_qsl(signed_part)))


async def test_the_credential_travels_in_the_header_not_the_query() -> None:
    """ส่วนที่เปิดเผยได้ไปทาง header ตามที่ตลาดกำหนด และ **ความลับไม่ไปไหนเลย**"""
    handler, seen = requests_to(replying(shaped_body("account_shape")))
    wallet = BinanceThWallet(transport_for(handler), _signer())

    await wallet.holdings()

    request = seen[0]
    assert request.headers["X-MBX-APIKEY"] == PUBLIC
    assert PUBLIC not in request.url.query.decode()
    assert SECRET.decode() not in str(request.url)


async def test_the_same_inputs_sign_the_same_text() -> None:
    """V-38 — ลำดับพารามิเตอร์และการเข้ารหัสอักขระคงที่ ไม่แกว่งตามรอบการเรียก"""
    handler, seen = requests_to(replying(shaped_body("account_shape")))
    transport = transport_for(handler)
    wallet = BinanceThWallet(transport, _signer())

    await wallet.holdings()
    await wallet.holdings()

    first, second = (request.url.query.decode().split("&signature=")[0] for request in seen)
    assert first == second
    assert seen[0].url.query == seen[1].url.query


async def test_the_balances_become_quantities_without_passing_through_a_float() -> None:
    """V-39 — ยอดทุกตัวถูกต้องและเป็น `Quantity` ไม่ใช่ `Money` (F-33)"""
    wallet = BinanceThWallet(transport_for(replying(shaped_body("account_shape"))), _signer())

    holdings = await wallet.holdings()

    assert holdings.assets == ("THB", "BTC", "USDT")
    thb = holdings.holding("THB")
    assert thb is not None
    assert thb.available == Quantity.of("1234.56", "THB")
    assert thb.reserved == Quantity.of("0", "THB")
    btc = holdings.holding("BTC")
    assert btc is not None
    assert btc.available == Quantity.of("0.00006000", "BTC")
    usdt = holdings.holding("USDT")
    assert usdt is not None
    assert usdt.available == Quantity.of("0", "USDT")
    assert usdt.reserved == Quantity.of("0", "USDT")
    # ค่าที่ทศนิยมลอยตัวทำพังได้ — เทียบกับ Decimal ของข้อความเดิมตรง ๆ
    assert btc.reserved == Quantity.of(Decimal("0.00001000"), "BTC")


async def test_the_account_flags_are_not_read_at_all() -> None:
    """RQ-6.1 — `canTrade`/`canWithdraw`/`canDeposit` ต้องไม่ถูกใช้ตัดสินอะไรเลย

    คำตอบที่ตั้งค่าทั้งสามเป็นเท็จต้องให้ผลเหมือนกันทุกประการ — ถ้าวันหนึ่งมีคน
    เอาช่องพวกนี้มาใช้ เทสต์นี้แดงทันที (ช่องพวกนี้เป็นสถานะของบัญชี ไม่ใช่ของ key)
    """
    body = json.loads(shaped_body("account_shape"))
    body["canTrade"] = body["canWithdraw"] = body["canDeposit"] = False
    wallet = BinanceThWallet(transport_for(replying(json.dumps(body))), _signer())

    holdings = await wallet.holdings()

    assert holdings.assets == ("THB", "BTC", "USDT")


async def test_the_guard_reserves_before_the_call() -> None:
    """สัญญาของ F-33 — ต้องจองโควตาก่อนเรียกตลาดเสมอ"""
    guard = RecordingGuard()
    wallet = BinanceThWallet(
        transport_for(replying(shaped_body("account_shape")), guard=guard), _signer()
    )

    await wallet.holdings()

    assert guard.reserved == [HOLDINGS_COST]


@pytest.mark.parametrize(
    "body",
    [
        "{}",
        '{"balances": "ไม่ใช่รายการ"}',
        '{"balances": [{"asset": "BTC", "free": "0.1"}]}',
        '{"balances": [{"asset": "BTC", "free": "", "locked": "0"}]}',
        '{"balances": [{"asset": "BTC", "free": "-1", "locked": "0"}]}',
        '{"balances": [{"asset": 1, "free": "1", "locked": "0"}]}',
        '{"balances": [{"asset": "BTC", "free": "1", "locked": "0"},'
        ' {"asset": "BTC", "free": "2", "locked": "0"}]}',
    ],
)
async def test_a_malformed_answer_becomes_a_protocol_error(body: str) -> None:
    """V-40 — คำตอบที่ผิดรูปกลายเป็น "สัญญาไม่ตรง" ไม่ใช่ข้อมูลที่ผิด

    ข้อนี้สำคัญกับ F-07 มากกว่าปกติ เพราะ `plan.md` ข้อ 7.3 ให้ "สัญญาไม่ตรง"
    เป็นผลแบบ **ชั่วคราว** ที่ห้ามลบ secret ถ้ามันกลายเป็นข้อมูลที่ผิดแทน
    เราจะไปรายงานยอดที่ไม่จริง
    """
    wallet = BinanceThWallet(transport_for(replying(body)), _signer())

    with pytest.raises(VenueProtocolError):
        await wallet.holdings()


async def test_a_rejected_credential_is_reported_as_such() -> None:
    """V-41 — รหัสของตลาดที่แปลว่าคำรับรองใช้ไม่ได้ ต้องมาถึงผู้เรียกเป็นชนิดนั้น

    นี่คือกรณีเดียวที่ `plan.md` ข้อ 7.3 สั่งให้ **ลบ secret ทันที** ฉะนั้นมันต้อง
    แยกออกจากความล้มเหลวชั่วคราวได้จริง ไม่ใช่เดาจากข้อความ
    """
    wallet = BinanceThWallet(
        transport_for(replying('{"code":-2015,"msg":"..."}', status=401)), _signer()
    )

    with pytest.raises(VenueCredentialRejectedError):
        await wallet.holdings()


@pytest.mark.parametrize(
    "name,value",
    [
        ("permissions", ["SPOT"]),
        ("permissions", None),
        ("newMetadata", {"private": "synthetic-canary"}),
    ],
)
async def test_unknown_top_level_account_fields_fail_closed(name: str, value: object) -> None:
    body = json.loads(shaped_body("account_shape"))
    body[name] = value
    wallet = BinanceThWallet(transport_for(replying(json.dumps(body))), _signer())
    with pytest.raises(VenueProtocolError) as caught:
        await wallet.holdings()
    assert caught.value.__cause__ is caught.value.__context__ is None
    assert name not in str(caught.value)
    assert "synthetic-canary" not in str(caught.value)
