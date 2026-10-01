"""ชิ้นส่วนของเทสต์สัญญารายวัน — ตรวจด้วยตลาดจำลอง ไม่เรียกตลาดจริง

เทสต์นี้อยู่ใน **ชุดปกติ** โดยเจตนา เพราะสิ่งที่ต้องเชื่อถือได้คือ "งานรายวันจัดสถานะ
ถูกกลุ่มไหม" ซึ่งถ้าไปพิสูจน์ในงานรายวันเองจะรู้ก็ตอนที่มันรายงานผิดไปแล้ว

ใช้ตัวช่วยจาก conftest ของเทสต์ตัวเชื่อม เพื่อไม่ให้มีตลาดจำลองสองชุดที่ต่างกัน
"""

from __future__ import annotations

from tests.venue_contract.test_live_contract import (
    _check_price,
    _check_weight,
    _missing_fields,
)
from tests.venue_contract.verdict import ContractReport, Verdict
from tests.venues.binance_th.conftest import replying, transport_for

#: คำตอบที่ถูกต้องหนึ่งรายการ ตามรูปที่ตลาดส่งมาจริง
ONE_TRADE = '[{"id":1,"price":"2822198.00","qty":"0.02","time":1790864472475}]'


def test_an_empty_list_of_trades_is_not_a_missing_field() -> None:
    """V-15.3 — array ว่างคือคำตอบที่ถูกตามสัญญาของตลาด ไม่ใช่ฟิลด์หาย"""
    assert _missing_fields([], ("price", "time")) == []


def test_a_field_that_really_is_missing_is_reported_by_name() -> None:
    """V-41 — ผู้ดูแลต้องเห็นชื่อฟิลด์ที่หายในสรุป ไม่ต้องไปอ่าน log"""
    assert _missing_fields([{"price": "1"}], ("price", "time")) == ["time"]


async def test_a_pair_with_no_trades_makes_the_job_skip_not_fail() -> None:
    """V-15.3 — คู่เทรดเงียบต้องไม่ทำให้งานรายวันแดง

    ถ้ากรณีนี้แดง งานจะแดงทุกครั้งที่เจอคู่ที่ยังไม่มีใครเทรด แล้วคนจะเลิกเชื่อสีแดง
    """
    report = ContractReport()
    await _check_price(transport_for(replying("[]")), report, {})

    assert [row[1] for row in report.rows] == [Verdict.SKIPPED]
    assert report.worst is Verdict.SKIPPED


async def test_a_market_that_cannot_answer_makes_the_job_skip() -> None:
    """V-40 — ตลาดจำกัดอัตราคือ "ยังไม่ได้คำตอบ" ไม่ใช่ "สัญญาไม่ตรง" """
    report = ContractReport()
    await _check_price(transport_for(replying("{}", status=429)), report, {})
    assert [row[1] for row in report.rows] == [Verdict.SKIPPED]


async def test_a_field_that_disappeared_makes_the_job_fail() -> None:
    """V-40 — สัญญาไม่ตรงต้องแดง และต้องบอกชื่อฟิลด์"""
    report = ContractReport()
    await _check_price(transport_for(replying('[{"id":1,"qty":"0.02"}]')), report, {})

    assert [row[1] for row in report.rows] == [Verdict.FAILED]
    assert "price" in report.rows[0][2]
    assert "time" in report.rows[0][2]


async def test_a_readable_market_makes_the_job_pass() -> None:
    """กรณีที่ถูกต้องคู่กัน — มิฉะนั้นเทสต์ข้างบนก็แค่พิสูจน์ว่าทุกอย่างแดง"""
    report = ContractReport()
    captured: dict[str, object] = {}
    await _check_price(transport_for(replying(ONE_TRADE)), report, captured)

    assert [row[1] for row in report.rows] == [Verdict.PASSED]
    assert "trades" in captured


async def test_the_weight_check_skips_instead_of_raising_when_the_market_refuses() -> None:
    """คำขอที่ใช้วัด weight ต้องอยู่ในการดักด้วย ไม่ใช่ทำให้งานล้มก่อนเขียนสรุป"""
    report = ContractReport()
    await _check_weight(transport_for(replying("{}", status=503)), report, {})
    assert [row[1] for row in report.rows] == [Verdict.SKIPPED]


async def test_the_weight_check_reads_the_header_of_every_request() -> None:
    """ผลต่างของยอดสะสมต้องมาจาก header ของทุกคำขอที่วัด"""
    report = ContractReport()
    captured: dict[str, object] = {}
    await _check_weight(
        transport_for(replying(ONE_TRADE, headers={"x-mbx-used-weight-1m": "7"})),
        report,
        captured,
    )
    assert captured["used_weight"] == [7, 7, 7, 7]
    # ยอดสะสมไม่ขยับระหว่างรอบ แปลว่าผลต่างเป็นศูนย์ ซึ่งน้อยกว่าที่ประกาศ → สรุปไม่ได้
    assert [row[1] for row in report.rows] == [Verdict.SKIPPED]
