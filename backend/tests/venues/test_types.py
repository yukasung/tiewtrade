"""ชนิดข้อมูลกลางของชั้น venue — V-8 ถึง V-14, V-16, V-17

ชนิดเหล่านี้คือสิ่งที่ข้ามชั้นออกไป ถ้ามันพาคำศัพท์หรือรูปแบบของตลาดติดไปด้วย
กฎ "โค้ดนอก venues ต้องไม่รู้ว่าคุยกับตลาดไหน" ก็พังทันที
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta

import pytest

from tests.venues.conftest import BTC_USDT, MARKET_TIME
from tiewtrade.core.money import InvalidUnitError, Money, MoneyError, Quantity
from tiewtrade.venues import Holding, Price, Symbol, SymbolConstraints, WalletHoldings


def _price(amount: str = "70000", *, venue_time: datetime = MARKET_TIME) -> Price:
    return Price(
        symbol=BTC_USDT,
        amount=Money.of(amount, "USDT"),
        venue_time=venue_time,
        received_at=venue_time + timedelta(milliseconds=50),
    )


def test_symbol_keeps_the_two_sides_apart() -> None:
    """V-10 — เก็บสองส่วนแยกกัน และรูปแบบข้อความไม่ใช่ชื่อคู่เทรดของตลาดไหน"""
    assert BTC_USDT.base == "BTC"
    assert BTC_USDT.quote == "USDT"
    assert str(BTC_USDT) == "BTC/USDT"


def test_symbol_rejects_a_joined_pair() -> None:
    """V-10 — ชื่อคู่เทรดแบบติดกันเป็นคำเดียวใส่เข้ามาไม่ได้

    ส่งเป็นสินทรัพย์ฐานล้วนไม่ได้ เพราะต้องมีสองส่วนและสองส่วนต้องต่างกัน
    """
    with pytest.raises(TypeError):
        Symbol("BTCUSDT")  # type: ignore[call-arg]
    with pytest.raises(MoneyError):
        Symbol(base="BTCUSDT", quote="")


def test_symbol_rejects_the_same_asset_on_both_sides() -> None:
    with pytest.raises(InvalidUnitError):
        Symbol(base="USDT", quote="USDT")


def test_types_cannot_be_changed_after_creation() -> None:
    """V-8 — สร้างแล้วแก้ไม่ได้"""
    price = _price()
    with pytest.raises(FrozenInstanceError):
        price.amount = Money.of("1", "USDT")  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        BTC_USDT.base = "ETH"  # type: ignore[misc]


def test_price_must_be_in_the_quote_asset() -> None:
    """V-11 — ราคาเป็น `Money` ของสินทรัพย์ที่ใช้อ้างราคา"""
    with pytest.raises(InvalidUnitError):
        Price(
            symbol=BTC_USDT,
            amount=Money.of("70000", "THB"),
            venue_time=MARKET_TIME,
            received_at=MARKET_TIME,
        )


@pytest.mark.parametrize("field", ["venue_time", "received_at"])
def test_price_times_must_carry_a_timezone(field: str) -> None:
    """V-12 — เวลาที่ไม่มี timezone เทียบข้ามเครื่องไม่ได้"""
    naive = datetime(2026, 9, 28, 10, 0)
    times = {"venue_time": MARKET_TIME, "received_at": MARKET_TIME} | {field: naive}
    with pytest.raises(ValueError, match="timezone"):
        Price(symbol=BTC_USDT, amount=Money.of("70000", "USDT"), **times)


def test_staleness_uses_the_venue_time_not_the_time_we_received_it() -> None:
    """V-13 — ราคาที่ตลาดส่งช้า 10 วินาทีแต่เราเพิ่งรับ ต้องถือว่าเก่า

    นี่คือกรณีที่การใช้เวลาที่เรารับจะตอบผิด และเป็นเหตุผลที่ต้องเก็บสองเวลา
    """
    now = datetime(2026, 9, 28, 10, 0, 10, tzinfo=UTC)
    delayed = Price(
        symbol=BTC_USDT,
        amount=Money.of("70000", "USDT"),
        venue_time=MARKET_TIME,
        received_at=now,
    )

    assert delayed.age(now) == timedelta(seconds=10)
    assert delayed.is_stale(max_age=timedelta(seconds=5), as_of=now)
    assert not delayed.is_stale(max_age=timedelta(seconds=30), as_of=now)


def test_staleness_threshold_comes_from_the_caller() -> None:
    """V-14 — เกณฑ์เป็นค่าที่ผู้เรียกส่งเข้ามา ชั้นนี้ไม่มีตัวเลขของตัวเอง"""
    now = MARKET_TIME + timedelta(seconds=3)
    price = _price()
    assert price.is_stale(max_age=timedelta(seconds=1), as_of=now)
    assert not price.is_stale(max_age=timedelta(seconds=5), as_of=now)


def test_age_requires_an_explicit_moment() -> None:
    """V-15 — ชั้นนี้ไม่อ่านนาฬิกาเอง เวลาปัจจุบันต้องส่งเข้ามา"""
    with pytest.raises(TypeError):
        _price().age()  # type: ignore[call-arg]


def test_constraints_hold_exactly_the_three_rules() -> None:
    """V-16 — สามข้อตาม `trading-safety.md` หัวข้อ 3 ไม่มากไม่น้อยกว่านั้น"""
    constraints = SymbolConstraints(
        symbol=BTC_USDT,
        minimum_quantity=Quantity.of("0.001", "BTC"),
        quantity_step=Quantity.of("0.0001", "BTC"),
        minimum_notional=Money.of("10", "USDT"),
    )
    assert set(constraints.__dataclass_fields__) == {
        "symbol",
        "minimum_quantity",
        "quantity_step",
        "minimum_notional",
    }


def test_constraints_have_no_checking_method_of_their_own() -> None:
    """V-15.1 — การตรวจอยู่ใน `core` ที่เดียว ไม่ใช่สองที่ที่ดูเหมือนตรวจได้ทั้งคู่"""
    method_names = {name for name in dir(SymbolConstraints) if not name.startswith("_")}
    assert not {name for name in method_names if "check" in name or "unmet" in name}


@pytest.mark.parametrize(
    ("minimum_quantity", "step", "notional"),
    [
        (Quantity.of("0.001", "ETH"), Quantity.of("0.0001", "BTC"), Money.of("10", "USDT")),
        (Quantity.of("0.001", "BTC"), Quantity.of("0.0001", "ETH"), Money.of("10", "USDT")),
        (Quantity.of("0.001", "BTC"), Quantity.of("0.0001", "BTC"), Money.of("10", "THB")),
    ],
)
def test_constraints_reject_units_that_do_not_match_the_symbol(
    minimum_quantity: Quantity, step: Quantity, notional: Money
) -> None:
    """หน่วยที่ไม่ตรงคู่เทรดต้องดัง ไม่ใช่เก็บไว้ให้พลาดตอนคำนวณ"""
    with pytest.raises(InvalidUnitError):
        SymbolConstraints(
            symbol=BTC_USDT,
            minimum_quantity=minimum_quantity,
            quantity_step=step,
            minimum_notional=notional,
        )


def test_constraints_reject_a_zero_step() -> None:
    with pytest.raises(ValueError, match="ขั้นของปริมาณ"):
        SymbolConstraints(
            symbol=BTC_USDT,
            minimum_quantity=Quantity.of("0.001", "BTC"),
            quantity_step=Quantity.of(0, "BTC"),
            minimum_notional=Money.of("10", "USDT"),
        )


def test_wallet_holdings_expose_their_assets_and_reject_duplicates() -> None:
    """V-34 — ยอดกระเป๋าบอกได้ว่าเป็นของสินทรัพย์อะไร เพื่อใช้บันทึก audit log"""
    holdings = WalletHoldings(
        received_at=MARKET_TIME,
        holdings=(
            Holding(available=Quantity.of("0.5", "BTC"), reserved=Quantity.of("0.1", "BTC")),
            Holding(available=Quantity.of("100", "USDT"), reserved=Quantity.of(0, "USDT")),
        ),
    )

    assert holdings.assets == ("BTC", "USDT")
    btc = holdings.holding("BTC")
    assert btc is not None
    assert btc.available == Quantity.of("0.5", "BTC")
    assert btc.reserved == Quantity.of("0.1", "BTC")
    assert holdings.holding("SOL") is None

    duplicated = (
        Holding(available=Quantity.of("1", "BTC"), reserved=Quantity.of(0, "BTC")),
        Holding(available=Quantity.of("2", "BTC"), reserved=Quantity.of(0, "BTC")),
    )
    with pytest.raises(ValueError, match="ยอดเดียว"):
        WalletHoldings(received_at=MARKET_TIME, holdings=duplicated)


def test_holdings_reject_negative_amounts_and_mixed_assets() -> None:
    with pytest.raises(InvalidUnitError):
        Holding(available=Quantity.of("1", "BTC"), reserved=Quantity.of("1", "ETH"))
    with pytest.raises(ValueError, match="ติดลบ"):
        Holding(available=Quantity.of("-1", "BTC"), reserved=Quantity.of(0, "BTC"))


def test_holdings_are_copied_so_the_caller_cannot_change_them_later() -> None:
    """ผู้เรียกส่ง list เข้ามาแล้วแก้ทีหลังได้ — ชนิดที่ประกาศว่าแก้ไม่ได้ต้องไม่เปลี่ยนตาม"""
    mutable = [Holding(available=Quantity.of("1", "BTC"), reserved=Quantity.of(0, "BTC"))]
    holdings = WalletHoldings(received_at=MARKET_TIME, holdings=mutable)  # type: ignore[arg-type]

    mutable.clear()
    mutable.append(Holding(available=Quantity.of("999", "ETH"), reserved=Quantity.of(0, "ETH")))

    assert holdings.assets == ("BTC",)
    assert isinstance(holdings.holdings, tuple)


def test_symbol_keeps_the_canonical_asset_names() -> None:
    """ชื่อที่ต่างกันแค่ตัวพิมพ์ต้องเป็นสินทรัพย์ตัวเดียวกัน ทั้งตอนเทียบและตอนใช้เป็นคีย์"""
    assert Symbol(base="btc", quote="usdt") == BTC_USDT
    assert {Symbol(base="btc", quote="usdt"): 1}[BTC_USDT] == 1

    with pytest.raises(InvalidUnitError):
        Symbol(base="btc", quote="BTC")


def test_symbol_that_was_lowercased_still_works_with_money() -> None:
    """ชื่อที่ปรับเป็นมาตรฐานแล้วต้องใช้กับ `Money` ได้ทันที ไม่ใช่พังตอนสร้างราคา"""
    symbol = Symbol(base="btc", quote="usdt")
    price = Price(
        symbol=symbol,
        amount=Money.of("70000", "USDT"),
        venue_time=MARKET_TIME,
        received_at=MARKET_TIME,
    )
    assert price.amount.currency == symbol.quote
