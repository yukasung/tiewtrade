"""การแปลข้อมูลของตลาดเป็นชนิดกลาง — V-13 ถึง V-19

ค่าที่คาดหวังคิดขึ้นใหม่จากไฟล์ที่บันทึกไว้ **ไม่ลอกจากโค้ดที่กำลังทดสอบ**
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from tests.venue_isolation import code_strings, identifiers
from tests.venues.binance_th.conftest import recorded_body
from tiewtrade.core.money import Money, Quantity
from tiewtrade.venues.binance_th.mapping import (
    constraints_from_pair,
    market_symbol,
    moment_from_millis,
    pairs_from_exchange_info,
    price_from_trades,
)
from tiewtrade.venues.errors import (
    VenueProtocolError,
    VenueRejectedError,
    VenueUnavailableError,
)
from tiewtrade.venues.symbols import Symbol

BTC_THB = Symbol(base="BTC", quote="THB")
ETH_BTC = Symbol(base="ETH", quote="BTC")

#: โค้ดของตัวเชื่อมที่เทสต์บางข้ออ่านเพื่อยืนยันว่า "ไม่มีทางสำรอง" และ "ไม่มี float"
ADAPTER = Path(__file__).parents[3] / "src" / "tiewtrade" / "venues" / "binance_th"

#: เวลาที่ระบบรับข้อมูล — ตั้งให้ห่างจากเวลาของรายการซื้อขายอย่างชัดเจน (V-14)
RECEIVED_AT = datetime(2026, 12, 25, tzinfo=UTC)


def test_price_comes_from_the_latest_trade_with_the_markets_own_time() -> None:
    """V-13 — ราคาและ **เวลาของราคา** มาจากรายการซื้อขายที่บันทึกไว้

    ค่าที่คาดหวังอ่านจาก **ช่องในไฟล์** แล้วแปลงด้วยวิธีที่เทสต์คิดเอง (แยกวินาที
    กับเศษมิลลิวินาทีออกจากกัน) ไม่ใช่เรียกตัวแปลงตัวเดียวกับที่กำลังทดสอบ
    และไม่ผูกกับราคาของวันที่เก็บข้อมูล — ไม่เช่นนั้นการเก็บข้อมูลใหม่จะทำให้
    เทสต์แดงทั้งที่การแปลงยังถูกทุกอย่าง

    ตัวแปลงเวลาเองมีเทสต์ที่ใช้ตัวเลขตายตัวแยกไว้ข้างล่าง
    """
    latest = json.loads(recorded_body("trades_btc_thb"))[-1]
    millis = latest["time"]
    expected_time = datetime.fromtimestamp(millis // 1000, UTC).replace(
        microsecond=millis % 1000 * 1000
    )

    price = price_from_trades(
        symbol=BTC_THB,
        payload=json.loads(recorded_body("trades_btc_thb")),
        received_at=RECEIVED_AT,
    )

    assert price.amount == Money.of(latest["price"], "THB")
    assert price.amount > Money.of(0, "THB")
    assert price.venue_time == expected_time
    assert price.received_at == RECEIVED_AT


def test_the_time_we_received_the_data_is_never_the_price_time() -> None:
    """V-14 — ห้ามใช้เวลาที่ระบบรับเป็นเวลาของราคา

    ถ้าสองค่านี้สลับกันได้ ราคาที่ตลาดค้างส่งมานานจะดูใหม่เอี่ยมทันทีที่เรารับ
    แล้วกฎ "ราคาเก่าห้ามเปิดไม้ใหม่" จะไม่ทำงานเลย
    """
    price = price_from_trades(
        symbol=BTC_THB,
        payload=json.loads(recorded_body("trades_btc_thb")),
        received_at=RECEIVED_AT,
    )
    assert price.venue_time != price.received_at

    # อายุนับจากเวลาของตลาด ไม่ใช่จากเวลาที่เรารับ — วัดเทียบกับเวลาที่ห่างจาก
    # เวลาของตลาดเท่าที่กำหนด ไม่ผูกกับวันที่เก็บข้อมูล
    five_days_later = price.venue_time + timedelta(days=5)
    assert price.age(five_days_later) == timedelta(days=5)


def test_no_trades_at_all_means_the_data_is_unavailable() -> None:
    """V-15 — array ว่าง → `VenueUnavailableError` (เจ้าของตัดสิน 2026-10-01)"""
    with pytest.raises(VenueUnavailableError):
        price_from_trades(symbol=BTC_THB, payload=[], received_at=RECEIVED_AT)


def test_no_trades_is_not_an_unknown_symbol_and_not_a_broken_protocol() -> None:
    """V-15.2, V-15.3 — ดักสองชนิดนั้นแล้วต้องไม่จับ

    คู่เทรดมีจริงในรายการของตลาด การบอกว่าไม่รู้จักจะทำให้ผู้เรียกถอดคู่นั้นออก
    และ array ว่างเป็นคำตอบที่ถูกตามสัญญาของตลาด ไม่ใช่สัญญาที่เปลี่ยน
    """
    for wrong_kind in (VenueRejectedError, VenueProtocolError):
        with pytest.raises(VenueUnavailableError):
            try:
                price_from_trades(symbol=BTC_THB, payload=[], received_at=RECEIVED_AT)
            except wrong_kind:  # pragma: no cover - ต้องไม่เข้าทางนี้
                pytest.fail(f"array ว่างถูกแปลเป็น {wrong_kind.__name__}")


def test_no_fallback_price_is_returned_from_anywhere() -> None:
    """V-15.1 — ไม่มีราคาคือไม่มีราคา ไม่มีทางสำรองในโค้ด

    ตรวจ **ข้อความที่โค้ดใช้จริง** ไม่ใช่ทั้งไฟล์ เพราะ docstring ของตัวเชื่อมอธิบายไว้
    โดยเจตนาว่าทำไมไม่ใช้ `/ticker/price` การห้ามคำในเอกสารจะทำให้เหตุผลนั้นหายไป
    """
    for module in ADAPTER.glob("*.py"):
        for text in code_strings(module):
            assert "ticker" not in text, f"{module.name} อ้าง endpoint ราคาอื่นเป็นทางสำรอง"
            assert "avgPrice" not in text, f"{module.name} อ้างราคาเฉลี่ยเป็นทางสำรอง"


def test_missing_fields_are_a_protocol_error() -> None:
    """V-23 — ฟิลด์ที่ต้องมีหาย → `VenueProtocolError` ไม่ใช่ "ตลาดใช้ไม่ได้" """
    without_time = [{"price": "100.0"}]
    with pytest.raises(VenueProtocolError):
        try:
            price_from_trades(symbol=BTC_THB, payload=without_time, received_at=RECEIVED_AT)
        except VenueUnavailableError:  # pragma: no cover - ต้องไม่เข้าทางนี้
            pytest.fail("ฟิลด์หายถูกแปลเป็น VenueUnavailableError")


@pytest.mark.parametrize(
    "payload",
    [
        {"price": "1.0"},
        [{"price": 100.0, "time": 1}],
        [{"price": "1.0", "time": "1790864472475"}],
        [{"price": "ไม่ใช่ตัวเลข", "time": 1790864472475}],
        [{"price": "1.0", "time": -1}],
        ["ไม่ใช่วัตถุ"],
        [{"price": "0", "time": 1}],
        [{"price": "-1", "time": 1}],
        [{"price": "1.0", "time": 10**20}],
    ],
    ids=[
        "ไม่ใช่รายการ",
        "ราคาเป็นตัวเลข",
        "เวลาเป็นข้อความ",
        "ราคาอ่านไม่ออก",
        "เวลาติดลบ",
        "สมาชิกผิดชนิด",
        "ราคาเป็นศูนย์",
        "ราคาติดลบ",
        "เวลาใหญ่เกินช่วงที่เก็บได้",
    ],
)
def test_every_shape_we_cannot_read_is_a_protocol_error(payload: object) -> None:
    """V-23 — ทุกรูปที่อ่านไม่ออกลงที่ชนิดเดียวกัน ไม่มีทางหลุดเป็นข้อผิดพลาดอื่น

    สามแถวท้ายคือค่าที่ **รูปถูกแต่ค่าผิดกฎของชนิดกลาง** — ราคาศูนย์หรือติดลบ
    และเวลาที่ใหญ่เกินช่วงที่ `datetime` เก็บได้ ถ้าไม่ดัก ผู้เรียกจะได้ `ValueError`
    กับ `OverflowError` ซึ่งการดัก `VenueError` ตามสัญญาจับไม่ได้เลย
    """
    with pytest.raises(VenueProtocolError):
        price_from_trades(symbol=BTC_THB, payload=payload, received_at=RECEIVED_AT)


def test_every_pair_the_market_lists_rebuilds_its_own_name_exactly() -> None:
    """V-19 (คุณสมบัติ) — ประกอบชื่อจากสองส่วนแล้วต้องได้ชื่อเดิมของตลาดทุกคู่

    เทียบกับช่อง `symbol` ที่ตลาดส่งมาเอง ไม่ใช่กับผลของฟังก์ชันเดียวกัน
    ถ้าวันหนึ่งตลาดเขียนชื่อคู่เทรดด้วยกฎอื่น (เช่นมีขีดคั่น) เทสต์นี้จะดัง
    """
    payload = json.loads(recorded_body("exchange_info"))
    pairs = payload["symbols"]
    assert pairs, "ไฟล์ที่บันทึกไว้ไม่มีคู่เทรดเลย"

    for pair in pairs:
        symbol = Symbol(base=pair["baseAsset"], quote=pair["quoteAsset"])
        assert market_symbol(symbol) == pair["symbol"]
        assert constraints_from_pair(pair).symbol == symbol


def test_no_float_appears_anywhere_on_the_conversion_path() -> None:
    """V-17 — ไม่มี `float` ในเส้นทางการแปลงเลย

    ตรวจชื่อที่โค้ดอ้างถึงจริง ไม่ใช่ข้อความในเอกสาร — ค่าที่ผ่าน `float` แล้วกลับมา
    ไม่เท่าเดิม และการตรวจผลลัพธ์ทีละค่าจับได้แค่ค่าที่เทสต์นึกถึง
    """
    for module in ADAPTER.glob("*.py"):
        assert "float" not in identifiers(module), f"{module.name} ใช้ float บนเส้นทางการแปลง"


def test_symbol_names_round_trip_through_the_markets_own_fields() -> None:
    """V-19 — ประกอบชื่อเองได้ แต่ **ถอดชื่อด้วย `baseAsset`/`quoteAsset` ของตลาด**

    `ETHBTC` คือกรณีที่ตัดสตริงเองแล้วผิดได้ง่าย เพราะตัดเป็น `ETH`+`BTC`
    หรือ `E`+`THBTC` ก็เป็นไปได้ทั้งคู่ถ้าไม่มีข้อมูลจากตลาด
    """
    known = pairs_from_exchange_info(json.loads(recorded_body("exchange_info")))
    assert market_symbol(ETH_BTC) == "ETHBTC"
    assert constraints_from_pair(known["ETHBTC"]).symbol == ETH_BTC


def test_constraints_come_from_the_markets_own_filters() -> None:
    """V-18 — ตัวเลขตรงกับไฟล์ที่บันทึกไว้ทุกหลัก

    ค่าที่คาดหวังอ่านด้วยตาจาก `exchange_info.json`: `BTCTHB` มีขั้นปริมาณ 0.000010
    และมูลค่าขั้นต่ำ 100.0 บาท
    """
    known = pairs_from_exchange_info(json.loads(recorded_body("exchange_info")))
    btc = constraints_from_pair(known["BTCTHB"])

    assert btc.minimum_quantity == Quantity.of("0.000010", "BTC")
    assert btc.quantity_step == Quantity.of("0.000010", "BTC")
    assert btc.minimum_notional == Money.of("100.0", "THB")


def test_numbers_crossing_the_boundary_are_money_and_quantity_only() -> None:
    """V-16 — เงินและปริมาณเป็น `Money`/`Quantity` เวลาเป็น `datetime` ที่มี timezone"""
    known = pairs_from_exchange_info(json.loads(recorded_body("exchange_info")))
    btc = constraints_from_pair(known["BTCTHB"])
    assert isinstance(btc.minimum_quantity, Quantity)
    assert isinstance(btc.quantity_step, Quantity)
    assert isinstance(btc.minimum_notional, Money)

    price = price_from_trades(
        symbol=BTC_THB,
        payload=json.loads(recorded_body("trades_btc_thb")),
        received_at=RECEIVED_AT,
    )
    assert isinstance(price.amount, Money)
    assert price.venue_time.tzinfo is not None
    assert price.venue_time.utcoffset() is not None


def test_eighteen_decimal_places_survive_without_a_single_digit_lost() -> None:
    """V-17 — ค่าที่ `float` เก็บไม่ครบต้องตรงทุกหลัก

    `0.123456789012345678` ผ่าน `float` แล้วกลับมาไม่เท่าเดิม ถ้าเทสต์นี้ผ่าน
    แปลว่าเส้นทางการแปลงไม่เคยผ่านทศนิยมลอยตัว
    """
    exact = "0.123456789012345678"
    assert str(float(exact)) != exact

    price = price_from_trades(
        symbol=BTC_THB,
        payload=[{"price": exact, "time": 1}],
        received_at=RECEIVED_AT,
    )
    assert price.amount.amount == Decimal(exact)
    assert price.amount.as_parts()["amount"] == exact


@pytest.mark.parametrize(
    "pair",
    [
        {
            "symbol": "BTC-THB",
            "baseAsset": "BTC-",
            "quoteAsset": "THB",
            "filters": [
                {"filterType": "LOT_SIZE", "minQty": "1", "stepSize": "1"},
                {"filterType": "MIN_NOTIONAL", "minNotional": "1"},
            ],
        },
        {
            "symbol": "BTCTHB",
            "baseAsset": "BTC",
            "quoteAsset": "THB",
            "filters": [{"filterType": "LOT_SIZE", "minQty": "1", "stepSize": "1"}],
        },
        {
            "symbol": "HYPEUSDT",
            "baseAsset": "HYPE",
            "quoteAsset": "USDT",
            "filters": [
                {"filterType": "LOT_SIZE", "minQty": "0.001", "stepSize": "0.0"},
                {"filterType": "MIN_NOTIONAL", "minNotional": "5.0"},
            ],
        },
        {
            "symbol": "ETHUSDT",
            "baseAsset": "ETH",
            "quoteAsset": "BTC",
            "filters": [
                {"filterType": "LOT_SIZE", "minQty": "1", "stepSize": "1"},
                {"filterType": "MIN_NOTIONAL", "minNotional": "1"},
            ],
        },
    ],
    ids=["ชื่อสินทรัพย์ผิดกฎ", "ไม่มี MIN_NOTIONAL", "ขั้นของปริมาณเป็นศูนย์", "ชื่อประกอบกลับไม่ตรง"],
)
def test_a_pair_we_cannot_read_is_a_protocol_error(pair: dict[str, object]) -> None:
    """NC-13 — คู่ที่อ่านไม่ได้ต้องดัง **ไม่ข้ามเงียบ ๆ และไม่บอกว่าไม่รู้จักคู่นั้น**

    `stepSize` เป็นศูนย์คือของจริงที่ตลาดส่งมาในคู่ที่เปิดเทรด (`HYPEUSDT` ตอนที่พบ)
    ส่วนแถวสุดท้ายคือกรณีที่ชื่อสองส่วนประกอบกลับไม่ได้เป็นชื่อเดิม ซึ่งแปลว่า
    เราเข้าใจกฎการตั้งชื่อของตลาดผิด
    """
    with pytest.raises(VenueProtocolError):
        constraints_from_pair(pair)


def test_one_unreadable_pair_does_not_hide_the_others() -> None:
    """NC-13 — คู่เดียวที่อ่านไม่ได้ต้องไม่ทำให้อ่านคู่อื่นไม่ได้

    นี่คือเหตุผลทั้งหมดที่การแปลงเกิดตอนมีคนถาม ไม่ใช่ตอนอ่านทั้งชุด
    """
    payload = json.loads(recorded_body("exchange_info"))
    payload["symbols"].append(
        {
            "symbol": "HYPEUSDT",
            "baseAsset": "HYPE",
            "quoteAsset": "USDT",
            "filters": [
                {"filterType": "LOT_SIZE", "minQty": "0.001", "stepSize": "0.0"},
                {"filterType": "MIN_NOTIONAL", "minNotional": "5.0"},
            ],
        }
    )

    known = pairs_from_exchange_info(payload)
    assert constraints_from_pair(known["BTCTHB"]).symbol == BTC_THB
    with pytest.raises(VenueProtocolError):
        constraints_from_pair(known["HYPEUSDT"])


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"symbols": "ไม่ใช่รายการ"},
        {"symbols": [{"baseAsset": "BTC", "quoteAsset": "THB"}]},
    ],
    ids=["ไม่มีรายการคู่เทรด", "รายการผิดชนิด", "คู่เทรดไม่มีชื่อ"],
)
def test_an_envelope_we_cannot_read_fails_the_whole_set(payload: object) -> None:
    """รูปของซองจดหมายผิดแปลว่าสัญญาของตลาดเปลี่ยนจริง ทั้งชุดจึงเชื่อถือไม่ได้"""
    with pytest.raises(VenueProtocolError):
        pairs_from_exchange_info(payload)


def test_market_time_is_read_as_milliseconds_since_the_epoch() -> None:
    """เวลาของตลาดเป็นมิลลิวินาที — ค่าที่คาดหวังคิดด้วยมือจากตัวเลขที่เขียนไว้ที่นี่

    ไม่ผูกกับตัวเลขในไฟล์ที่บันทึกไว้ เพราะไฟล์นั้นเปลี่ยนทุกครั้งที่เก็บใหม่
    ส่วนที่ไฟล์ต้องยืนยันคือ **รูปร่าง** ของข้อมูล ไม่ใช่ค่าของนาฬิกาวันนั้น
    """
    assert moment_from_millis(1790864480882) == datetime(
        2026, 10, 1, 14, 21, 20, 882_000, tzinfo=UTC
    )

    payload = json.loads(recorded_body("server_time"))
    assert isinstance(payload, dict)
    assert isinstance(payload["serverTime"], int)
