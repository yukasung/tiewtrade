"""สองสัญญาของตัวเชื่อม — V-1, V-32 ถึง V-35

เขียนจาก **มุมผู้เรียก** ผู้เรียกเห็นแค่สัญญาของ F-33 ไม่เห็นว่าข้างในเรียกอะไร
"""

from __future__ import annotations

import json
from datetime import timedelta

import httpx
import pytest

from tests.venues.binance_th.conftest import (
    FakeClock,
    RecordingGuard,
    recorded_body,
    replying,
    requests_to,
    transport_for,
)
from tiewtrade.venues.binance_th.constraints import CONSTRAINTS_COST, BinanceThConstraints
from tiewtrade.venues.binance_th.prices import LATEST_PRICE_COST, BinanceThPrices
from tiewtrade.venues.constraints import SymbolConstraintSource
from tiewtrade.venues.errors import (
    RejectionReason,
    VenueProtocolError,
    VenueRejectedError,
    VenueUnavailableError,
)
from tiewtrade.venues.prices import PriceSource
from tiewtrade.venues.symbols import Symbol

BTC_THB = Symbol(base="BTC", quote="THB")
ETH_BTC = Symbol(base="ETH", quote="BTC")
NOT_LISTED = Symbol(base="DOGE", quote="THB")

TRADES = recorded_body("trades_btc_thb")
EXCHANGE_INFO = recorded_body("exchange_info")


def test_the_adapter_satisfies_both_contracts_of_the_venue_layer() -> None:
    """V-1 — ผู้เรียกเห็นตัวเชื่อมเป็นสองสัญญาของ F-33 ไม่ใช่ชนิดของตลาดนี้"""
    prices = BinanceThPrices(transport_for(replying(TRADES)))
    constraints = BinanceThConstraints(
        transport_for(replying(EXCHANGE_INFO)), ttl=timedelta(hours=1), clock=FakeClock()
    )
    assert isinstance(prices, PriceSource)
    assert isinstance(constraints, SymbolConstraintSource)


def test_the_adapter_never_holds_a_secret() -> None:
    """F-07 Q-2 — ตัวเชื่อม **ลงลายเซ็นเองไม่ได้** เพราะมันไม่มีความลับ

    F-35 เคยพิสูจน์ว่างานนั้นไม่มีกระเป๋าและไม่มีการลงลายเซ็นเลย · F-07 เพิ่มกระเป๋า
    ที่ต้องลงลายเซ็นเข้ามา แต่ข้อที่ยังต้องจริงอยู่คือ **ความลับไม่ข้ามเส้นเข้ามา**:
    ตัวเชื่อมรู้ว่าข้อความไหนต้องถูกเซ็นและ header ชื่ออะไร ส่วนตัวที่ถือ secret
    กับวิธีคำนวณลายเซ็นอยู่ใน `infra/api_keys` (`plan.md` ข้อ 6.1)

    ถ้าวันหนึ่งมีคนย้ายการคำนวณลายเซ็นกลับเข้ามาที่นี่ เทสต์นี้แดงทันที
    """
    import ast
    from pathlib import Path

    from tiewtrade.venues import binance_th

    adapter = Path(binance_th.__file__).parent
    for module in adapter.glob("*.py"):
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            # อ่านด้วย AST ไม่ใช่ค้นข้อความ เพราะคำว่า "secret" ในคำอธิบายที่บอกว่า
            # **ไม่มี** secret ก็จะโดนจับไปด้วย ซึ่งเป็นการแดงด้วยเหตุผลที่ไม่ใช่กฎ
            if isinstance(node, ast.Import):
                names = {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom):
                names = {(node.module or "").split(".")[0]}
            else:
                names = set()
            assert not names & {"hmac", "hashlib"}, f"{module.name} คำนวณลายเซ็นเอง"

            identifier = ""
            if isinstance(node, ast.Name):
                identifier = node.id
            elif isinstance(node, ast.arg):
                identifier = node.arg
            elif isinstance(node, ast.Attribute):
                identifier = node.attr
            elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                identifier = node.name
            assert "secret" not in identifier.lower(), f"{module.name} มีชื่อ {identifier!r}"


async def test_the_price_asks_for_exactly_one_latest_trade() -> None:
    """Q-7 — ใช้ `/trades?limit=1` เพราะรายการซื้อขายพาเวลาของตัวเองมาด้วย"""
    handler, seen = requests_to(replying(TRADES))
    guard = RecordingGuard()
    prices = BinanceThPrices(transport_for(handler, guard=guard))

    price = await prices.latest_price(BTC_THB)

    assert price.symbol == BTC_THB
    assert len(seen) == 1
    assert seen[0].url.path.endswith("/trades")
    assert dict(seen[0].url.params) == {"symbol": "BTCTHB", "limit": "1"}
    assert guard.reserved == [LATEST_PRICE_COST]


async def test_an_empty_list_of_trades_reaches_the_caller_as_unavailable() -> None:
    """V-15 — คู่เทรดที่ยังไม่มีใครเทรด → `VenueUnavailableError` ตลอดทางถึงผู้เรียก"""
    prices = BinanceThPrices(transport_for(replying("[]")))
    with pytest.raises(VenueUnavailableError):
        await prices.latest_price(BTC_THB)


async def test_no_second_request_is_made_when_there_is_no_price() -> None:
    """V-15.1 — ไม่มีราคาแล้วต้องไม่ไปหาราคาจากที่อื่นมาแทน"""
    handler, seen = requests_to(replying("[]"))
    prices = BinanceThPrices(transport_for(handler))

    with pytest.raises(VenueUnavailableError):
        await prices.latest_price(BTC_THB)
    assert len(seen) == 1, "มีคำขอที่สองออกไป ซึ่งแปลว่ามีทางสำรอง"


async def test_an_unknown_symbol_reaches_the_caller_as_a_rejection() -> None:
    """รหัสจริงของตลาด (`-1121`) → `VenueRejectedError(UNKNOWN_SYMBOL)`"""
    prices = BinanceThPrices(
        transport_for(replying(recorded_body("rejected_unknown_symbol"), status=400))
    )
    with pytest.raises(VenueRejectedError) as caught:
        await prices.latest_price(NOT_LISTED)
    assert caught.value.reason is RejectionReason.UNKNOWN_SYMBOL


async def test_constraints_come_from_one_call_for_every_pair() -> None:
    """`/exchangeInfo` คืนทุกคู่ในคำขอเดียว weight 10 ตามที่ประกาศไว้"""
    handler, seen = requests_to(replying(EXCHANGE_INFO))
    guard = RecordingGuard()
    constraints = BinanceThConstraints(
        transport_for(handler, guard=guard), ttl=timedelta(hours=1), clock=FakeClock()
    )

    first = await constraints.constraints(BTC_THB)
    second = await constraints.constraints(ETH_BTC)

    assert first.symbol == BTC_THB
    assert second.symbol == ETH_BTC
    assert len(seen) == 1, "cache ไม่ทำงาน เรียกซ้ำทั้งที่ยังไม่หมดอายุ"
    assert guard.reserved == [CONSTRAINTS_COST]


async def test_a_pair_the_market_does_not_list_is_rejected() -> None:
    """คู่ที่ไม่มีในรายการของตลาด → ไม่รู้จัก ไม่ใช่คืนข้อจำกัดว่าง ๆ"""
    constraints = BinanceThConstraints(
        transport_for(replying(EXCHANGE_INFO)), ttl=timedelta(hours=1), clock=FakeClock()
    )
    with pytest.raises(VenueRejectedError) as caught:
        await constraints.constraints(NOT_LISTED)
    assert caught.value.reason is RejectionReason.UNKNOWN_SYMBOL


async def test_the_cache_is_read_again_once_it_expires() -> None:
    """V-32, V-35 — อายุมาจากผู้เรียก และหมดอายุแล้วต้องเรียกใหม่จริง"""
    handler, seen = requests_to(replying(EXCHANGE_INFO))
    clock = FakeClock()
    constraints = BinanceThConstraints(
        transport_for(handler, clock=clock), ttl=timedelta(minutes=5), clock=clock
    )

    await constraints.constraints(BTC_THB)
    clock.advance(timedelta(minutes=4))
    await constraints.constraints(BTC_THB)
    assert len(seen) == 1

    clock.advance(timedelta(minutes=2))
    await constraints.constraints(BTC_THB)
    assert len(seen) == 2


async def test_two_different_lifetimes_behave_differently() -> None:
    """V-32 — ไม่มีอายุตายตัวในตัวเชื่อม ผู้เรียกกำหนดแล้วผลต่างกันจริง"""
    counts = []
    for ttl in (timedelta(seconds=30), timedelta(hours=1)):
        handler, seen = requests_to(replying(EXCHANGE_INFO))
        clock = FakeClock()
        constraints = BinanceThConstraints(
            transport_for(handler, clock=clock), ttl=ttl, clock=clock
        )
        await constraints.constraints(BTC_THB)
        clock.advance(timedelta(minutes=1))
        await constraints.constraints(BTC_THB)
        counts.append(len(seen))
    assert counts == [2, 1]


async def test_a_lifetime_that_is_not_positive_is_refused() -> None:
    """อายุศูนย์หรือติดลบหมายถึงไม่เคยเชื่อ cache เลย ซึ่งต้องบอกตรง ๆ ไม่ใช่เขียนศูนย์"""
    with pytest.raises(ValueError, match="มากกว่าศูนย์"):
        BinanceThConstraints(
            transport_for(replying(EXCHANGE_INFO)), ttl=timedelta(0), clock=FakeClock()
        )


async def test_expired_data_is_never_served_when_the_refresh_fails() -> None:
    """V-33 — หมดอายุแล้วอ่านใหม่ไม่สำเร็จ → โยนข้อผิดพลาด **ห้ามคืนของเก่าเงียบ ๆ**

    ข้อจำกัดที่เปลี่ยนไปแล้วทำให้จุดตรวจก่อนส่งออเดอร์อนุมัติคำสั่งที่ตลาดจะปฏิเสธ
    หรือห้ามคำสั่งที่ควรผ่าน (Q-3 — เจ้าของตัดสิน)
    """
    calls = {"count": 0}

    def flaky(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(200, text=EXCHANGE_INFO)
        raise httpx.ConnectError("ต่อไม่ติด", request=request)

    clock = FakeClock()
    constraints = BinanceThConstraints(
        transport_for(flaky, clock=clock), ttl=timedelta(minutes=5), clock=clock
    )
    first = await constraints.constraints(BTC_THB)
    assert first.symbol == BTC_THB

    clock.advance(timedelta(minutes=6))
    with pytest.raises(VenueUnavailableError):
        await constraints.constraints(BTC_THB)


async def test_a_successful_refresh_replaces_the_whole_set() -> None:
    """V-34 — คู่เทรดที่หายจากชุดใหม่ต้องหายจาก cache ด้วย (Q-3)"""
    full = json.loads(EXCHANGE_INFO)
    without_eth = dict(full)
    without_eth["symbols"] = [pair for pair in full["symbols"] if pair["symbol"] != "ETHBTC"]
    bodies = [EXCHANGE_INFO, json.dumps(without_eth)]
    served = {"n": 0}

    def serving(request: httpx.Request) -> httpx.Response:
        body = bodies[min(served["n"], len(bodies) - 1)]
        served["n"] += 1
        return httpx.Response(200, text=body)

    clock = FakeClock()
    constraints = BinanceThConstraints(
        transport_for(serving, clock=clock), ttl=timedelta(minutes=5), clock=clock
    )
    assert (await constraints.constraints(ETH_BTC)).symbol == ETH_BTC

    clock.advance(timedelta(minutes=6))
    with pytest.raises(VenueRejectedError) as caught:
        await constraints.constraints(ETH_BTC)
    assert caught.value.reason is RejectionReason.UNKNOWN_SYMBOL


async def test_a_half_readable_refresh_does_not_replace_good_data_with_rubbish() -> None:
    """ชุดใหม่ที่แปลไม่ผ่านต้องไม่ทำให้ cache กลายเป็นชุดที่อ่านมาได้ครึ่ง ๆ"""
    bodies = [EXCHANGE_INFO, '{"symbols":[{"symbol":"BTCTHB"}]}']
    served = {"n": 0}

    def serving(request: httpx.Request) -> httpx.Response:
        body = bodies[min(served["n"], len(bodies) - 1)]
        served["n"] += 1
        return httpx.Response(200, text=body)

    clock = FakeClock()
    constraints = BinanceThConstraints(
        transport_for(serving, clock=clock), ttl=timedelta(minutes=5), clock=clock
    )
    await constraints.constraints(BTC_THB)

    clock.advance(timedelta(minutes=6))
    with pytest.raises(VenueProtocolError):
        await constraints.constraints(BTC_THB)
