"""ตัวกั้นน้ำหนักต่อ IP — V-28 ถึง V-31

เดินเวลาเองทุกเทสต์ **ไม่มีการรอจริงแม้วินาทีเดียว**
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import cast

import httpx
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tests.venues.binance_th.conftest import START, FakeClock, transport_for
from tiewtrade.venues.binance_th.endpoints import Endpoint
from tiewtrade.venues.binance_th.rate_limit import (
    IP_WEIGHT_WINDOWS,
    IpWeightLimiter,
    WeightWindow,
)
from tiewtrade.venues.errors import VenueRateLimitedError, VenueUnavailableError
from tiewtrade.venues.limits import CallCost

TEN_SECONDS = timedelta(seconds=10)
ONE_MINUTE = timedelta(seconds=60)


@pytest.mark.parametrize("floor", [True, False, 0, -1, "10", 1.5, None])
def test_floor_requires_positive_integer_excluding_bool(floor: object) -> None:
    with pytest.raises(ValueError):
        IpWeightLimiter(clock=FakeClock(), reservation_weight_floor=cast(int, floor))


async def test_published_cost_above_floor_is_not_lowered() -> None:
    limiter = IpWeightLimiter(
        clock=FakeClock(), windows=[WeightWindow(20, TEN_SECONDS)], reservation_weight_floor=10
    )
    await limiter.reserve(CallCost(weight=15))
    with pytest.raises(VenueRateLimitedError):
        await limiter.reserve(CallCost(weight=1))


async def test_second_window_refusal_never_partially_charges_first_window() -> None:
    clock = FakeClock()
    limiter = IpWeightLimiter(
        clock=clock,
        windows=[WeightWindow(20, ONE_MINUTE), WeightWindow(10, TEN_SECONDS)],
        reservation_weight_floor=10,
    )
    await limiter.reserve(CallCost(weight=1))
    clock.advance(timedelta(seconds=1))
    with pytest.raises(VenueRateLimitedError):
        await limiter.reserve(CallCost(weight=1))
    clock.advance(timedelta(seconds=9))
    # First window still contains the original ten. A rejected partial charge
    # would make this successful ten-weight probe exceed its twenty ceiling.
    await limiter.reserve(CallCost(weight=1))


async def test_floor_wait_uses_reserved_weight_and_recovers() -> None:
    clock = FakeClock()
    limiter = IpWeightLimiter(
        clock=clock, windows=[WeightWindow(20, TEN_SECONDS)], reservation_weight_floor=10
    )
    await limiter.reserve(CallCost(weight=15))
    clock.advance(timedelta(seconds=3))
    with pytest.raises(VenueRateLimitedError) as caught:
        await limiter.reserve(CallCost(weight=1))
    assert caught.value.retry_after == timedelta(seconds=7)
    clock.advance(timedelta(seconds=7))
    await limiter.reserve(CallCost(weight=1))


async def test_observer_below_floor_never_refunds_and_higher_adds_only_delta() -> None:
    clock = FakeClock()
    limiter = IpWeightLimiter(
        clock=clock, windows=[WeightWindow(30, TEN_SECONDS)], reservation_weight_floor=10
    )
    await limiter.reserve(CallCost(weight=1))
    limiter.observe_used_weight(span=TEN_SECONDS, used=1, at=clock.now)
    limiter.observe_used_weight(span=TEN_SECONDS, used=15, at=clock.now)
    await limiter.reserve(CallCost(weight=1))
    with pytest.raises(VenueRateLimitedError):
        await limiter.reserve(CallCost(weight=1))


async def test_impossible_floor_refuses_before_http() -> None:
    calls: list[httpx.Request] = []
    limiter = IpWeightLimiter(
        clock=FakeClock(), windows=[WeightWindow(9, TEN_SECONDS)], reservation_weight_floor=10
    )

    def reply(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json=[])

    transport = transport_for(reply, guard=limiter)
    with pytest.raises(ValueError):
        await transport.get(Endpoint.KLINES, cost=CallCost(weight=1))
    assert calls == []


async def test_failed_http_keeps_floor_until_expiry() -> None:
    clock = FakeClock()
    calls: list[httpx.Request] = []
    limiter = IpWeightLimiter(
        clock=clock, windows=[WeightWindow(10, TEN_SECONDS)], reservation_weight_floor=10
    )

    def reply(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(500, json={})

    transport = transport_for(reply, guard=limiter, clock=clock)
    with pytest.raises(VenueUnavailableError):
        await transport.get(Endpoint.KLINES, cost=CallCost(weight=1))
    with pytest.raises(VenueRateLimitedError):
        await transport.get(Endpoint.KLINES, cost=CallCost(weight=1))
    assert len(calls) == 1
    clock.advance(TEN_SECONDS)
    with pytest.raises(VenueUnavailableError):
        await transport.get(Endpoint.KLINES, cost=CallCost(weight=1))
    assert len(calls) == 2


async def test_default_floor_preserves_published_one_weight_price_accounting() -> None:
    from tiewtrade.venues.binance_th.prices import BinanceThPrices
    from tiewtrade.venues.symbols import Symbol

    clock = FakeClock()
    limiter = IpWeightLimiter(clock=clock, windows=[WeightWindow(2, TEN_SECONDS)])

    def reply(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"price": "2", "time": 0}])

    source = BinanceThPrices(transport_for(reply, guard=limiter, clock=clock))
    await source.latest_price(Symbol("BTC", "USDT"))
    await source.latest_price(Symbol("BTC", "USDT"))
    with pytest.raises(VenueRateLimitedError):
        await source.latest_price(Symbol("BTC", "USDT"))


def test_the_windows_are_the_ones_the_market_documents() -> None:
    """V-28 — 1,000 ต่อ 10 วินาที และ 6,000 ต่อ 60 วินาที (`mission.md` หัวข้อ 6)"""
    expected = (
        WeightWindow(limit=1_000, span=TEN_SECONDS),
        WeightWindow(limit=6_000, span=ONE_MINUTE),
    )
    assert expected == IP_WEIGHT_WINDOWS


async def test_the_short_window_refuses_once_it_is_full() -> None:
    """V-28 — เต็มแล้วโยน `VenueRateLimitedError` ไม่หลับรอเงียบ ๆ"""
    clock = FakeClock()
    limiter = IpWeightLimiter(clock=clock)

    for _ in range(100):
        await limiter.reserve(CallCost(weight=10))

    with pytest.raises(VenueRateLimitedError):
        await limiter.reserve(CallCost(weight=1))


async def test_the_quota_comes_back_when_the_window_moves_on() -> None:
    """V-29 — เวลามาจากตัวอ่านเวลาที่ผู้เรียกส่งเข้ามา

    เดินนาฬิกาไปพ้นหน้าต่างสั้นแล้วโควตาต้องคืน — ถ้าตัวกั้นอ่านนาฬิกาจริงเอง
    เทสต์นี้จะต้องรอสิบวินาที ซึ่งไม่มีใครยอมรออยู่ในชุดเทสต์
    """
    clock = FakeClock()
    limiter = IpWeightLimiter(clock=clock)
    await limiter.reserve(CallCost(weight=1_000))

    with pytest.raises(VenueRateLimitedError):
        await limiter.reserve(CallCost(weight=1))

    clock.advance(TEN_SECONDS)
    await limiter.reserve(CallCost(weight=1))


async def test_the_long_window_still_holds_after_the_short_one_resets() -> None:
    """V-28 — สองหน้าต่างบังคับแยกกัน ไม่ใช่ตัวเดียวที่หลวมที่สุดชนะ"""
    clock = FakeClock()
    limiter = IpWeightLimiter(clock=clock)

    for index in range(6):
        if index:
            clock.advance(TEN_SECONDS)
        await limiter.reserve(CallCost(weight=1_000))

    # ยอดรวมในหนึ่งนาทีเต็มเพดานแล้ว ทั้งที่หน้าต่างสิบวินาทีว่างสนิท
    with pytest.raises(VenueRateLimitedError):
        await limiter.reserve(CallCost(weight=1))


async def test_the_wait_it_reports_is_long_enough_to_actually_help() -> None:
    """V-28 — เวลาที่บอกต้องรอได้ผลจริง ไม่ใช่ตัวเลขที่รอแล้วยังถูกปฏิเสธซ้ำ"""
    clock = FakeClock()
    limiter = IpWeightLimiter(clock=clock)
    await limiter.reserve(CallCost(weight=1_000))

    with pytest.raises(VenueRateLimitedError) as caught:
        await limiter.reserve(CallCost(weight=1))
    wait = caught.value.retry_after
    assert wait is not None

    clock.advance(wait)
    await limiter.reserve(CallCost(weight=1))


async def test_a_cost_bigger_than_the_ceiling_is_a_mistake_not_a_wait() -> None:
    """ต้นทุนที่เกินเพดานรอเท่าไรก็ไม่พอ — ต้องดังทันทีแทนการชวนให้ลองใหม่ตลอดไป"""
    limiter = IpWeightLimiter(clock=FakeClock())
    with pytest.raises(ValueError, match="เกินเพดาน"):
        await limiter.reserve(CallCost(weight=1_001))


async def test_order_counts_are_refused_because_they_belong_to_an_account() -> None:
    """เพดานจำนวนออเดอร์ของตลาดนี้นับ **ต่อบัญชี** ไม่ใช่ต่อ IP (`mission.md` หัวข้อ 6)

    ตัวกั้นที่นับแต่ IP จึงต้องปฏิเสธต้นทุนที่มีออเดอร์ติดมา ไม่ใช่นับผ่านไปเงียบ ๆ
    แล้วทำให้คนเชื่อว่าเพดานออเดอร์ถูกคุมอยู่
    """
    limiter = IpWeightLimiter(clock=FakeClock())
    with pytest.raises(ValueError, match="ต่อบัญชี"):
        await limiter.reserve(CallCost(weight=1, orders=1))


async def test_the_market_count_wins_when_it_is_higher_than_ours() -> None:
    """V-30 — IP เดียวอาจถูกใช้โดยอย่างอื่นด้วย ยอดของเราจึงต่ำกว่าความจริงได้"""
    clock = FakeClock()
    limiter = IpWeightLimiter(clock=clock)
    await limiter.reserve(CallCost(weight=10))

    # ตลาดบอกว่าใช้ไป 995 แล้วทั้งที่เรานับได้ 10
    limiter.observe_used_weight(span=TEN_SECONDS, used=995, at=clock.now)

    await limiter.reserve(CallCost(weight=5))
    with pytest.raises(VenueRateLimitedError):
        await limiter.reserve(CallCost(weight=1))


async def test_a_lower_market_count_never_gives_us_quota_back() -> None:
    """V-30 — เชื่อตลาดเฉพาะเมื่อสูงกว่า ไม่ใช่เชื่อทุกค่าที่ตลาดบอก

    ถ้าลดตามค่าที่ต่ำกว่า เราจะยิงเกินเพดานในจังหวะที่หน้าต่างของสองฝั่งไม่ตรงกัน
    """
    clock = FakeClock()
    limiter = IpWeightLimiter(clock=clock)
    await limiter.reserve(CallCost(weight=1_000))

    limiter.observe_used_weight(span=TEN_SECONDS, used=1, at=clock.now)

    with pytest.raises(VenueRateLimitedError):
        await limiter.reserve(CallCost(weight=1))


async def test_the_count_of_one_window_does_not_fill_another() -> None:
    """V-30 — ยอดที่ตลาดรายงานนับเข้า **หน้าต่างของมันเท่านั้น**

    ยอดหนึ่งนาทีไม่ได้บอกว่าสิบวินาทีที่ผ่านมาใช้ไปเท่าไร ถ้านับรวมกัน ยอดหนึ่งนาที
    2,000 จะบล็อกคำขอด้วยเพดานสิบวินาทีที่ 1,000 ทั้งที่หน้าต่างนั้นว่างสนิท
    """
    clock = FakeClock()
    limiter = IpWeightLimiter(clock=clock)
    limiter.observe_used_weight(span=ONE_MINUTE, used=2_000, at=clock.now)

    await limiter.reserve(CallCost(weight=1))


async def test_the_count_of_one_window_still_fills_that_window() -> None:
    """คู่กันของกรณีข้างบน — ยอดหนึ่งนาทีต้องยังบังคับเพดานหนึ่งนาทีจริง"""
    clock = FakeClock()
    limiter = IpWeightLimiter(clock=clock)
    limiter.observe_used_weight(span=ONE_MINUTE, used=6_000, at=clock.now)

    with pytest.raises(VenueRateLimitedError):
        await limiter.reserve(CallCost(weight=1))


async def test_a_window_we_do_not_enforce_is_ignored() -> None:
    """header ของหน้าต่างที่เราไม่ได้บังคับต้องไม่ถูกนับเข้าหน้าต่างอื่น

    การแปลงหน่วยแบบนั้นไม่มีใครสั่ง และจะทำให้โควตาหายไปโดยอธิบายไม่ได้
    """
    clock = FakeClock()
    limiter = IpWeightLimiter(clock=clock)
    limiter.observe_used_weight(span=timedelta(hours=1), used=5_000, at=clock.now)
    await limiter.reserve(CallCost(weight=1_000))


async def test_the_market_count_expires_like_our_own() -> None:
    """ส่วนต่างที่รับจากตลาดต้องหมดอายุไปตามหน้าต่างเดียวกัน ไม่ค้างอยู่ตลอดไป"""
    clock = FakeClock()
    limiter = IpWeightLimiter(clock=clock)
    limiter.observe_used_weight(span=TEN_SECONDS, used=1_000, at=clock.now)

    with pytest.raises(VenueRateLimitedError):
        await limiter.reserve(CallCost(weight=1))

    clock.advance(TEN_SECONDS)
    await limiter.reserve(CallCost(weight=1))


async def test_the_clock_must_carry_a_timezone() -> None:
    """เวลาที่ไม่มี timezone เทียบข้ามเครื่องไม่ได้ (`database.md` หัวข้อ 2)"""
    limiter = IpWeightLimiter(clock=lambda: datetime(2026, 10, 1, 12, 0))
    with pytest.raises(ValueError, match="timezone"):
        await limiter.reserve(CallCost(weight=1))


@settings(max_examples=50, deadline=None)
@given(
    weights=st.lists(st.integers(min_value=1, max_value=300), min_size=1, max_size=40),
    steps=st.lists(st.integers(min_value=0, max_value=30), min_size=1, max_size=40),
)
async def test_no_sequence_of_calls_ever_exceeds_a_window(
    weights: list[int], steps: list[int]
) -> None:
    """คุณสมบัติ: ไม่ว่าลำดับและจังหวะเป็นอย่างไร ยอดในทุกหน้าต่างไม่เกินเพดาน

    นับยอดด้วยวิธีที่เทสต์คิดเอง ไม่ได้ถามตัวกั้น — ไม่เช่นนั้นก็แค่เทียบโค้ดกับตัวเอง
    """
    clock = FakeClock(START)
    limiter = IpWeightLimiter(clock=clock)
    accepted: list[tuple[datetime, int]] = []

    for weight, step in zip(weights, steps, strict=False):
        try:
            await limiter.reserve(CallCost(weight=weight))
        except VenueRateLimitedError:
            pass
        else:
            accepted.append((clock.now, weight))

        for window in IP_WEIGHT_WINDOWS:
            used = sum(amount for moment, amount in accepted if clock.now - moment < window.span)
            assert used <= window.limit, f"หน้าต่าง {window.span} ใช้ไป {used}"

        clock.advance(timedelta(seconds=step))
