"""แปลข้อมูลของ Binance TH เป็นชนิดกลางของ F-33 (plan.md ข้อ 3)

ที่เดียวที่รู้รูปแบบข้อมูลของตลาด — ส่วนอื่นเห็นแต่ `Symbol`, `Price`, `SymbolConstraints`

**ตัวเลขทุกตัวอ่านเป็นข้อความก่อน** แล้วส่งเข้า `Money`/`Quantity` (RQ-4, RQ-5)
ไม่มีจุดไหนที่ค่าของตลาดกลายเป็นทศนิยมลอยตัวแม้ชั่วคราว เพราะการแปลงกลับไม่คืนค่าเดิม

**อ่านคำตอบไม่ออกคือ `VenueProtocolError`** ไม่ใช่การเดาค่าที่ขาดไป — คำตอบที่เราอ่าน
ไม่ออกหมายถึงความเข้าใจของเราไม่ตรงกับตลาด ซึ่งต้องแก้โค้ด ไม่ใช่ลองใหม่

ชนิดนั้นไม่พาชื่อฟิลด์ที่หายไปด้วย เพราะไม่มีชนิดไหนในสัญญารับข้อความอิสระ (F-33 RQ-8)
**คนที่ต้องรู้ว่าฟิลด์ไหนหายคือเทสต์สัญญารายวัน** ซึ่งตรวจฟิลด์ทีละตัวด้วยตัวเอง
แล้วรายงานชื่อฟิลด์ลง job summary (plan.md ข้อ 6) ไม่ใช่รอให้ข้อผิดพลาดพามา
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Final

from tiewtrade.core.money import Money, MoneyError, Quantity
from tiewtrade.venues.errors import VenueProtocolError, VenueUnavailableError
from tiewtrade.venues.prices import Price
from tiewtrade.venues.symbols import Symbol, SymbolConstraints
from tiewtrade.venues.wallets import Holding, WalletHoldings

#: ชื่อ filter ของตลาดที่งานนี้อ่าน — **ไม่อ่าน `PRICE_FILTER` เพราะยังไม่มีใครใช้** (RQ-14)
_LOT_SIZE: Final = "LOT_SIZE"
_MIN_NOTIONAL: Final = "MIN_NOTIONAL"

_EPOCH: Final = datetime(1970, 1, 1, tzinfo=UTC)


@contextmanager
def _readable() -> Iterator[None]:
    """ค่าที่ตลาดส่งมาแล้วชนิดกลางไม่รับ ถือว่า **เราอ่านคำตอบนี้ไม่ได้**

    **ที่เดียว** ที่แปลข้อผิดพลาดของ `Money`/`Quantity`/`Price`/`SymbolConstraints`
    เป็นชนิดกลาง ทุกจุดที่สร้างชนิดเหล่านั้นจากค่าของตลาดต้องผ่านที่นี่
    ถ้ากระจายไปเขียนตามจุด จุดที่ลืมจะปล่อย `ValueError` หลุดสัญญาออกไปหาผู้เรียก
    ซึ่งผู้เรียกที่ดัก `VenueError` ตามสัญญาจับไม่ได้

    `OverflowError` อยู่ด้วยเพราะเวลาที่ตลาดส่งมาใหญ่เกินช่วงที่ `datetime` เก็บได้
    ครอบบล็อกเล็ก ๆ เท่านั้น เพื่อไม่ให้บั๊กของเราเองกลายเป็น "สัญญาไม่ตรง"
    """
    try:
        yield
    except (MoneyError, ValueError, OverflowError) as error:
        raise VenueProtocolError() from error


def market_symbol(symbol: Symbol) -> str:
    """ชื่อคู่เทรดในรูปของตลาด — ติดกันเป็นคำเดียว เช่น `BTC` กับ `THB` เป็น `BTCTHB`"""
    return f"{symbol.base}{symbol.quote}"


def price_from_trades(*, symbol: Symbol, payload: object, received_at: datetime) -> Price:
    """ราคาจากรายการซื้อขายล่าสุด (`/trades?limit=1`) — Q-7

    **รายการว่างไม่ใช่ความผิดพลาดของรูปแบบ** ตลาดตอบถูกตามสัญญาของมัน แต่ยังไม่มี
    ราคาให้ ผู้เรียกจึงได้ `VenueUnavailableError` ตามความหมายที่ขยายไว้ใน F-33
    (plan.md ข้อ 1.3, 4.1) — **ไม่คืนราคาสำรองจากที่อื่น ไม่บอกว่าไม่รู้จักคู่เทรด
    และไม่ถือว่า response ผิดรูป**

    `received_at` มาจากผู้เรียก ไม่ใช่จากนาฬิกาที่โมดูลนี้อ่านเอง และ **เวลาของราคา
    คือ `time` ของรายการนั้น** ไม่ใช่เวลาที่เรารับหรือเวลาของเซิร์ฟเวอร์ (Q-7)
    """
    trades = _sequence(payload)
    if not trades:
        raise VenueUnavailableError()

    latest = _mapping(trades[-1])
    # ราคาศูนย์หรือติดลบผิดกฎของ `Price` และเวลาที่ใหญ่เกินช่วงก็อ่านไม่ได้เหมือนกัน
    with _readable():
        return Price(
            symbol=symbol,
            amount=Money.of(_text(latest.get("price")), symbol.quote),
            venue_time=moment_from_millis(latest.get("time")),
            received_at=received_at,
        )


def pairs_from_exchange_info(payload: object) -> dict[str, dict[str, object]]:
    """รายการคู่เทรดดิบจาก `/exchangeInfo` เก็บตามชื่อที่ตลาดเรียกมันเอง

    **ยังไม่แปลงเป็น `SymbolConstraints` ที่นี่** การแปลงเกิดตอนมีคนถามถึงคู่นั้น
    (ดู `constraints_from_pair`) เพราะคู่เดียวที่อ่านไม่ได้ต้องไม่ทำให้อ่านคู่อื่นไม่ได้
    ตาม **NC-13** ที่เจ้าของตัดสิน 2026-10-01:

    ตลาดรายงาน `stepSize` เป็น `"0.0"` ในคู่ที่สถานะ `TRADING` จริง (`HYPEUSDC`,
    `HYPEUSDT` ตอนที่พบ) ซึ่ง `SymbolConstraints` ของ F-33 ไม่รับ ถ้าแปลงทั้งชุด
    ตั้งแต่ตอนอ่าน คู่สองคู่นั้นจะทำให้ **อ่านข้อจำกัดของคู่ไหนไม่ได้เลย**

    ที่ยังตรวจตั้งแต่ตอนนี้คือ **รูปของซองจดหมาย**: ต้องเป็นวัตถุที่มีรายการคู่เทรด
    และทุกคู่ต้องมีชื่อของตัวเอง — สามข้อนี้ผิดแปลว่าสัญญาของตลาดเปลี่ยนจริง
    """
    body = _mapping(payload)
    listed = _sequence(body.get("symbols"))

    pairs: dict[str, dict[str, object]] = {}
    for entry in listed:
        pair = _mapping(entry)
        pairs[_text(pair.get("symbol"))] = pair
    return pairs


def constraints_from_pair(pair: Mapping[str, object]) -> SymbolConstraints:
    """ข้อจำกัดของคู่เทรดหนึ่งคู่ จาก filter ที่ตลาดรายงาน

    ใช้ `baseAsset`/`quoteAsset` ที่ตลาดส่งมา **ไม่ตัดชื่อคู่เทรดเอง** เพราะชื่ออย่าง
    `ETHBTC` ตัดได้หลายแบบและเดาผิดคือการเทรดผิดเหรียญ — แล้ว **ยืนยันว่าสองส่วนนั้น
    ประกอบกลับได้เป็นชื่อเดิมของตลาด** ถ้าไม่ตรง แปลว่าเราเข้าใจกฎการตั้งชื่อผิด

    คู่ที่อ่านไม่ได้ **ดังตอนที่มีคนถามถึงมัน ไม่ใช่ตอนอ่านทั้งชุด และไม่ข้ามเงียบ ๆ**
    (NC-13 — เจ้าของตัดสิน 2026-10-01)
    """
    with _readable():
        symbol = Symbol(base=_text(pair.get("baseAsset")), quote=_text(pair.get("quoteAsset")))
    if market_symbol(symbol) != _text(pair.get("symbol")):
        raise VenueProtocolError()

    filters = _filters_of(pair)
    lot = _mapping(filters.get(_LOT_SIZE))
    notional = _mapping(filters.get(_MIN_NOTIONAL))
    # ตัวเลขที่ตลาดส่งมาผิดกฎของ F-33 เช่นขั้นของปริมาณเป็นศูนย์ ก็อ่านไม่ได้เหมือนกัน
    with _readable():
        return SymbolConstraints(
            symbol=symbol,
            minimum_quantity=Quantity.of(_text(lot.get("minQty")), symbol.base),
            quantity_step=Quantity.of(_text(lot.get("stepSize")), symbol.base),
            minimum_notional=Money.of(_text(notional.get("minNotional")), symbol.quote),
        )


def moment_from_millis(value: object) -> datetime:
    """เวลาของตลาดที่ส่งมาเป็นมิลลิวินาทีนับจาก epoch → เวลาที่มี timezone กำกับ

    บวกด้วย `timedelta` ของจำนวนเต็ม ไม่หารด้วยพันเป็นทศนิยม เพราะการหารด้วยพัน
    ผ่านทศนิยมลอยตัวทำให้มิลลิวินาทีคลาดได้
    """
    millis = _integer(value)
    if millis < 0:
        raise VenueProtocolError()
    with _readable():
        return _EPOCH + timedelta(milliseconds=millis)


def _filters_of(pair: Mapping[str, object]) -> dict[str, object]:
    found: dict[str, object] = {}
    for item in _sequence(pair.get("filters")):
        entry = _mapping(item)
        found[_text(entry.get("filterType"))] = entry
    return found


def _mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise VenueProtocolError()
    # คีย์ของ JSON เป็นข้อความเสมอตามรูปแบบ แต่ยืนยันไว้เพื่อให้ชนิดที่ประกาศเป็นจริง
    return {str(key): item for key, item in value.items()}


def _sequence(value: object) -> list[object]:
    if not isinstance(value, list):
        raise VenueProtocolError()
    return list(value)


def _text(value: object) -> str:
    if not isinstance(value, str):
        raise VenueProtocolError()
    return value


def _integer(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise VenueProtocolError()
    return value


# NC-19: รูปร่าง account เดิมที่ยืนยันแล้ว · ตรวจชื่อช่อง ไม่อ่านค่าของ account flags
_ACCOUNT_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "makerCommission",
        "takerCommission",
        "buyerCommission",
        "sellerCommission",
        "canTrade",
        "canWithdraw",
        "canDeposit",
        "updateTime",
        "balances",
    }
)


def holdings_from_account(*, payload: object, received_at: datetime) -> WalletHoldings:
    """ยอดในกระเป๋าจากคำตอบของ endpoint ข้อมูลบัญชี (F-07)

    **อ่านเฉพาะ `balances`** — ช่องอื่นของคำตอบนี้ (`canTrade`, `canWithdraw`,
    `canDeposit`) **ห้ามแตะเด็ดขาด** เพราะเป็นสถานะของ **บัญชี** ไม่ใช่สิทธิ์ของ key
    พิสูจน์แล้วด้วยการเรียกจริงเมื่อ 2026-10-04: `canWithdraw` คืนค่าจริงทั้งที่
    หน้าสร้าง key ของตลาดนี้ไม่มีสิทธิ์ถอนเงินให้เปิดเลย (NC-16 · RQ-6.1)
    ชื่อของมันอ่านเหมือนสิทธิ์ของ key ทุกประการ ซึ่งเป็นเหตุผลที่ต้องเขียนห้ามไว้ตรงนี้

    **ยอดเป็น `Quantity` ไม่ใช่ `Money`** ตามที่ F-33 ตัดสิน และแปลงจากข้อความตรง ๆ
    โดยไม่ผ่านทศนิยมลอยตัว — ตัวอ่าน JSON ของ `transport` คงตัวเลขที่มีจุดไว้เป็นข้อความ
    """
    account = _mapping(payload)
    if account.keys() - _ACCOUNT_FIELDS:
        raise VenueProtocolError()
    holdings: list[Holding] = []
    for item in _sequence(account.get("balances")):
        entry = _mapping(item)
        asset = _text(entry.get("asset"))
        with _readable():
            holdings.append(
                Holding(
                    available=Quantity.of(_text(entry.get("free")), asset),
                    reserved=Quantity.of(_text(entry.get("locked")), asset),
                )
            )

    with _readable():
        return WalletHoldings(received_at=received_at, holdings=tuple(holdings))
