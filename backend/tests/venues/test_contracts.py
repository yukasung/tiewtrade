"""สัญญา ข้อผิดพลาด ตัวกั้นอัตรา และตัวแทนปลอม — V-19 ถึง V-37

เขียนจาก **มุมผู้เรียก** ตามที่ `validation.md` กำหนด — ถ้าเทสต์ต้องรู้ข้างในของ
ตัวแทนปลอมจึงจะเขียนได้ แปลว่าสัญญายังออกแบบผิด
"""

from __future__ import annotations

import socket
from datetime import timedelta

import pytest

from tests.venues.conftest import BTC_USDT, CONSTRAINTS, ETH_USDT, HOLDINGS, PRICE
from tiewtrade.venues import (
    CallCost,
    FakeVenue,
    NoRateLimit,
    Price,
    PriceSource,
    RejectionReason,
    Symbol,
    SymbolConstraintSource,
    VenueCredentialRejectedError,
    VenueError,
    VenueOutcomeUnknownError,
    VenueRateLimitedError,
    VenueRejectedError,
    VenueUnavailableError,
    WalletSource,
)

ALL_ERRORS = (
    VenueRejectedError(RejectionReason.CONSTRAINT_NOT_MET),
    VenueOutcomeUnknownError(),
    VenueRateLimitedError(timedelta(seconds=3)),
    VenueUnavailableError(),
    VenueCredentialRejectedError(),
)


class RecordingGuard:
    """ตัวกั้นที่จดต้นทุนที่ได้รับ — ใช้พิสูจน์ว่าต้นทุนที่ถูกต้องถึงตัวกั้นจริง"""

    def __init__(self, *, refuse: bool = False) -> None:
        self.reserved: list[CallCost] = []
        self._refuse = refuse

    async def reserve(self, cost: CallCost) -> None:
        self.reserved.append(cost)
        if self._refuse:
            raise VenueRateLimitedError(timedelta(seconds=1))


def _venue(**kwargs: object) -> FakeVenue:
    defaults: dict[str, object] = {
        "prices": {BTC_USDT: PRICE},
        "constraints": {BTC_USDT: CONSTRAINTS},
        "holdings": HOLDINGS,
    }
    return FakeVenue(**(defaults | kwargs))  # type: ignore[arg-type]


def test_the_fake_satisfies_all_three_contracts() -> None:
    """V-24, V-26 — สามสัญญาแยกกัน และตัวปลอมทำตามครบทั้งสาม"""
    venue = _venue()
    assert isinstance(venue, PriceSource)
    assert isinstance(venue, WalletSource)
    assert isinstance(venue, SymbolConstraintSource)


def test_contracts_are_separate_from_each_other() -> None:
    """V-24 — ตัวที่ทำตามสัญญาหนึ่งไม่ถูกนับเป็นอีกสัญญา"""

    class PricesOnly:
        async def latest_price(self, symbol: Symbol) -> Price:
            return PRICE

    prices_only = PricesOnly()
    assert isinstance(prices_only, PriceSource)
    assert not isinstance(prices_only, WalletSource)
    assert not isinstance(prices_only, SymbolConstraintSource)


async def test_reading_prices_constraints_and_holdings() -> None:
    """V-34 — ค่าที่คืนพาตัวระบุของผลมาด้วย ผู้เรียกจึงบันทึกได้ว่า "กับอะไร" """
    venue = _venue()

    price = await venue.latest_price(BTC_USDT)
    constraints = await venue.constraints(BTC_USDT)
    holdings = await venue.holdings()

    assert price.symbol == BTC_USDT
    assert constraints.symbol == BTC_USDT
    assert holdings.assets == ("BTC",)


async def test_unknown_symbol_is_rejected_with_a_reason() -> None:
    """V-21 — เหตุผลเป็นรหัสกลาง ไม่ใช่ข้อความของตลาด"""
    venue = _venue()
    with pytest.raises(VenueRejectedError) as caught:
        await venue.latest_price(ETH_USDT)
    assert caught.value.reason is RejectionReason.UNKNOWN_SYMBOL


@pytest.mark.parametrize("error", ALL_ERRORS, ids=lambda error: type(error).__name__)
async def test_every_error_kind_can_be_forced(error: VenueError) -> None:
    """V-27 — ตัวปลอมบังคับให้เกิดข้อผิดพลาดได้ทุกชนิดในห้าชนิด"""
    venue = _venue()
    venue.queue_errors([error])
    with pytest.raises(type(error)):
        await venue.latest_price(BTC_USDT)


async def test_errors_happen_in_the_order_they_were_queued() -> None:
    """V-27 — ลำดับคือสิ่งที่เทสต์ของกฎความปลอดภัยต้องใช้: พลาดก่อน แล้วสำเร็จ"""
    venue = _venue()
    venue.queue_errors([VenueUnavailableError(), VenueOutcomeUnknownError()])

    with pytest.raises(VenueUnavailableError):
        await venue.latest_price(BTC_USDT)
    with pytest.raises(VenueOutcomeUnknownError):
        await venue.latest_price(BTC_USDT)

    assert await venue.latest_price(BTC_USDT) == PRICE


async def test_unknown_outcome_is_not_caught_as_unavailable() -> None:
    """V-20 — "ต่อไม่ได้" กับ "ส่งไปแล้วไม่รู้ผล" ต้องดักแยกกันด้วยชนิดอย่างเดียว

    ข้อแรกลองใหม่ได้ ข้อหลังห้ามลองใหม่และต้องไปถามสถานะ
    ถ้าดักปนกันได้ ผู้เรียกจะลองส่งซ้ำในกรณีที่ห้ามส่งซ้ำ
    """
    venue = _venue()
    venue.queue_errors([VenueOutcomeUnknownError()])

    with pytest.raises(VenueOutcomeUnknownError):
        try:
            await venue.latest_price(BTC_USDT)
        except VenueUnavailableError:  # pragma: no cover - ต้องไม่เข้าทางนี้
            pytest.fail("ดัก VenueUnavailableError แล้วจับ 'ไม่รู้ผล' ไปด้วย")


def test_every_error_carries_a_distinct_stable_code() -> None:
    """V-33 — รหัสเอาไปใส่ `failure_code` ของ audit log ได้ตรง ๆ และไม่ซ้ำกัน"""
    codes = [type(error).code for error in ALL_ERRORS]
    assert len(codes) == len(set(codes))
    assert all(code.isupper() for code in codes)
    assert VenueError.code == "VENUE_ERROR"


def test_error_messages_never_carry_secrets_or_urls() -> None:
    """V-23 — ไม่มีชนิดไหนรับข้อความอิสระ จึงไม่มีทางพา secret หรือ URL ออกมา"""
    for error in ALL_ERRORS:
        message = str(error)
        assert "http" not in message
        assert "://" not in message
        assert "key" not in message.lower()


def test_rate_limited_error_does_not_invent_a_wait() -> None:
    """V-22 — ไม่มีใครบอกเวลามา ต้องเป็นค่าว่าง ไม่ใช่เดาแทนตลาด"""
    assert VenueRateLimitedError().retry_after is None
    assert VenueRateLimitedError(timedelta(seconds=5)).retry_after == timedelta(seconds=5)


async def test_declared_cost_reaches_the_guard() -> None:
    """V-36 — ต้นทุนที่ถูกต้องของแต่ละเมธอดถึงตัวกั้นจริง"""
    guard = RecordingGuard()
    venue = _venue(
        guard=guard,
        latest_price_cost=CallCost(weight=2),
        holdings_cost=CallCost(weight=5),
        constraints_cost=CallCost(weight=7),
    )

    await venue.latest_price(BTC_USDT)
    await venue.holdings()
    await venue.constraints(BTC_USDT)

    assert guard.reserved == [CallCost(weight=2), CallCost(weight=5), CallCost(weight=7)]


async def test_guard_refusal_surfaces_as_rate_limited() -> None:
    """V-37 — จองไม่ได้ต้องโยน `VenueRateLimitedError` ไม่ใช่รอเงียบ ๆ ข้างใน"""
    venue = _venue(guard=RecordingGuard(refuse=True))
    with pytest.raises(VenueRateLimitedError):
        await venue.latest_price(BTC_USDT)


async def test_quota_is_reserved_even_when_the_call_fails() -> None:
    """ตัวจริงจองก่อนแตะเครือข่าย ตัวปลอมจึงต้องจองก่อนเหมือนกัน

    ไม่เช่นนั้นเทสต์เรื่องโควตาจะพิสูจน์พฤติกรรมที่ไม่เหมือนของจริง
    """
    guard = RecordingGuard()
    venue = _venue(guard=guard)
    venue.queue_errors([VenueUnavailableError()])

    with pytest.raises(VenueUnavailableError):
        await venue.latest_price(BTC_USDT)

    assert len(guard.reserved) == 1


def test_call_cost_rejects_meaningless_values() -> None:
    with pytest.raises(ValueError, match="weight"):
        CallCost(weight=0)
    with pytest.raises(ValueError, match="ออเดอร์"):
        CallCost(weight=1, orders=-1)


@pytest.mark.parametrize("bad", [1.5, float("nan"), True, "1", None])
def test_call_cost_requires_whole_numbers(bad: object) -> None:
    """โควตานับด้วยจำนวนเต็ม — `NaN` ผ่านการตรวจช่วงค่าได้ทั้งที่นับไม่ได้

    ตัวกั้นที่ได้ `NaN` ไปจะเทียบกับเพดานแล้วได้เท็จเสมอ คือไม่เคยถึงเพดานเลย
    """
    with pytest.raises(TypeError):
        CallCost(weight=bad)  # type: ignore[arg-type]


async def test_null_guard_does_not_change_behaviour() -> None:
    """V-30 — ตัวกั้นที่ไม่ทำอะไรต้องไม่เปลี่ยนพฤติกรรม"""
    venue = _venue(guard=NoRateLimit())
    assert await venue.latest_price(BTC_USDT) == PRICE


async def test_the_fake_never_changes_holdings_by_itself() -> None:
    """V-28 — ไม่จับคู่ออเดอร์ ไม่มีบัญชี และไม่เปลี่ยนยอดเอง"""
    venue = _venue()
    first = await venue.holdings()
    second = await venue.holdings()

    assert first == second
    method_names = {name for name in dir(venue) if not name.startswith("_")}
    assert not {
        name for name in method_names if any(word in name for word in ("place", "order", "fill"))
    }


def test_the_fake_says_it_is_not_the_paper_simulator() -> None:
    """V-29 — docstring บอกว่าการจำลองของ Paper เป็นงาน F-15"""
    documentation = FakeVenue.__doc__ or ""
    module_documentation = __import__("tiewtrade.venues.fake", fromlist=["x"]).__doc__ or ""
    combined = documentation + module_documentation
    assert "F-15" in combined
    assert "Paper" in combined


def test_no_order_placing_contract_exists_yet() -> None:
    """V-32 — ยังไม่มีสัญญาส่งออเดอร์ เพราะ NC-08 ยังไม่ปิด"""
    import tiewtrade.venues as venues

    exported = set(venues.__all__)
    assert not {name for name in exported if "Order" in name}


async def test_nothing_touches_the_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """V-5 — ปิดการสร้าง socket ทั้งกระบวนการ แล้วทุกอย่างของงานนี้ยังทำงานได้"""

    def refuse(*args: object, **kwargs: object) -> None:
        pytest.fail("ชั้นแยก venue พยายามเปิดการเชื่อมต่อเครือข่าย")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)

    venue = _venue()
    assert await venue.latest_price(BTC_USDT) == PRICE
    assert await venue.constraints(BTC_USDT) == CONSTRAINTS
    assert await venue.holdings() == HOLDINGS
