"""ตัวกั้นน้ำหนักต่อ IP ของ Binance TH (F-35 plan.md ข้อ 2.1)

เพดานเป็นของตลาดนี้ ไม่ใช่ของกลาง จึงอยู่ใน package ของตัวเชื่อม ไม่ใช่ใน `venues/limits.py`
ที่มีแต่สัญญา

**ข้อจำกัดที่ยอมรับแล้ว:** นับได้แค่ในกระบวนการเดียว หลายกระบวนการบนเครื่องเดียวกัน
ยังชนเพดานต่อ IP ร่วมกันได้ — **ตัวกั้นที่มีสภาพร่วมกันต้องมาก่อนปล่อยผู้ใช้จริง**

**นับแต่น้ำหนักต่อ IP** เพดานจำนวนออเดอร์ของ Binance TH นับ **ต่อบัญชี** ไม่ใช่ต่อ IP
(`mission.md` หัวข้อ 6) จึงต้องมีตัวนับอีกตัวที่รู้จักบัญชี ซึ่งเป็นงานของงานที่ส่งออเดอร์
ตัวนี้จึงปฏิเสธต้นทุนที่มีออเดอร์ติดมา แทนที่จะนับผ่านไปเงียบ ๆ
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final, NamedTuple, Protocol, runtime_checkable

from tiewtrade.venues.errors import VenueRateLimitedError
from tiewtrade.venues.limits import CallCost
from tiewtrade.venues.moments import require_aware


@dataclass(frozen=True, slots=True)
class WeightWindow:
    """เพดานน้ำหนักหนึ่งหน้าต่างเวลา"""

    limit: int
    span: timedelta

    def __post_init__(self) -> None:
        if self.limit < 1:
            raise ValueError("เพดานน้ำหนักต้องไม่น้อยกว่า 1")
        if self.span <= timedelta(0):
            raise ValueError("ช่วงเวลาของหน้าต่างต้องมากกว่าศูนย์")


#: สองหน้าต่างตามเอกสารของ Binance TH — นับ **ต่อ IP** (`mission.md` หัวข้อ 6)
IP_WEIGHT_WINDOWS: Final[tuple[WeightWindow, ...]] = (
    WeightWindow(limit=1_000, span=timedelta(seconds=10)),
    WeightWindow(limit=6_000, span=timedelta(seconds=60)),
)


class _Spent(NamedTuple):
    """น้ำหนักที่ใช้ไปแล้วหนึ่งรายการ

    `scope` เป็น `None` เมื่อรายการนี้นับเข้า **ทุกหน้าต่าง** ซึ่งเป็นกรณีของคำขอ
    ที่เราเรียกเอง ส่วนยอดที่ตลาดรายงานนับเข้าหน้าต่างของมันเท่านั้น
    """

    at: datetime
    weight: int
    scope: timedelta | None


@runtime_checkable
class UsedWeightObserver(Protocol):
    """ตัวกั้นที่รับยอดน้ำหนักที่ **ตลาดนับเอง** มาปรับตัวได้"""

    def observe_used_weight(self, *, span: timedelta, used: int, at: datetime) -> None:
        """ยอดสะสมที่ตลาดรายงานสำหรับหน้าต่างนั้น ณ เวลานั้น"""
        ...


class IpWeightLimiter:
    """นับน้ำหนักตามหน้าต่างเวลาจริง และปฏิเสธเมื่อจะเกินเพดาน

    **ไม่หลับรอเงียบ ๆ** — เต็มแล้วโยน `VenueRateLimitedError` พร้อมเวลาที่ต้องรอ
    ตามสัญญาของ F-33 เพราะผู้เรียกเป็นคนตัดสินว่าจะรอ จะทิ้งงาน หรือจะแจ้งผู้ใช้

    **ผู้เรียกส่งตัวอ่านเวลาเข้ามา** เพื่อให้เทสต์เดินเวลาเองได้โดยไม่ต้องรอจริง
    """

    def __init__(
        self,
        *,
        clock: Callable[[], datetime],
        windows: Iterable[WeightWindow] = IP_WEIGHT_WINDOWS,
        reservation_weight_floor: int = 1,
    ) -> None:
        self._clock = clock
        if (
            isinstance(reservation_weight_floor, bool)
            or not isinstance(reservation_weight_floor, int)
            or reservation_weight_floor < 1
        ):
            raise ValueError("reservation weight floor must be a positive integer")
        self._reservation_weight_floor = reservation_weight_floor
        self._windows: Final[tuple[WeightWindow, ...]] = tuple(windows)
        if not self._windows:
            raise ValueError("ตัวกั้นต้องมีหน้าต่างเวลาอย่างน้อยหนึ่งหน้าต่าง")
        #: น้ำหนักที่ใช้ไปแล้ว เรียงตามเวลา
        self._spent: list[_Spent] = []

    async def reserve(self, cost: CallCost) -> None:
        """จองโควตาสำหรับการเรียกที่มีต้นทุนเท่านี้ — จองไม่ได้ก็โยน"""
        if cost.orders:
            raise ValueError("ตัวกั้นนี้นับน้ำหนักต่อ IP เท่านั้น เพดานจำนวนออเดอร์นับต่อบัญชี ต้องใช้ตัวกั้นที่รู้จักบัญชี")

        reserved_weight = max(cost.weight, self._reservation_weight_floor)
        for window in self._windows:
            if reserved_weight > window.limit:
                # รอเท่าไรก็ไม่พอ — เป็นความผิดของค่าที่ประกาศ ไม่ใช่ของจังหวะเวลา
                # จึงดังทันทีแทนการโยน "ถูกจำกัดอัตรา" ที่ชวนให้ผู้เรียกลองใหม่ตลอดไป
                raise ValueError(
                    f"ต้นทุน {reserved_weight} weight เกินเพดานของหน้าต่าง {window.span} "
                    f"ที่ {window.limit} จึงไม่มีทางจองสำเร็จ"
                )

        now = self._now()
        self._forget_older_than(now)

        for window in self._windows:
            used = self._used_within(window.span, now)
            if used + reserved_weight > window.limit:
                raise VenueRateLimitedError(self._wait_for(window, reserved_weight, now))

        self._spent.append(_Spent(at=now, weight=reserved_weight, scope=None))

    def observe_used_weight(self, *, span: timedelta, used: int, at: datetime) -> None:
        """รับยอดที่ตลาดนับเอง — **ค่าที่ตลาดนับสูงกว่า ให้เชื่อตลาด**

        IP เดียวอาจถูกใช้โดยกระบวนการอื่นด้วย ยอดของเราจึงต่ำกว่าความจริงได้
        แต่สูงกว่าไม่ได้ — ถ้าตลาดนับได้น้อยกว่าเรา ไม่ลดของเราลง เพราะการลดลง
        จะทำให้เรายิงเกินเพดานในจังหวะที่หน้าต่างของตลาดกับของเราไม่ตรงกัน

        ส่วนต่างบันทึกเป็นน้ำหนักที่ใช้ไปแล้ว ณ เวลาที่ได้ค่ามา เพื่อให้มันหมดอายุ
        ไปตามหน้าต่างเดียวกับของเราเอง
        """
        require_aware("เวลาที่ตลาดรายงานยอดน้ำหนัก", at)
        if used < 0:
            raise ValueError("ยอดน้ำหนักที่ตลาดรายงานติดลบไม่ได้")
        if not any(window.span == span for window in self._windows):
            # หน้าต่างที่เราไม่ได้บังคับ เก็บไว้ก็ไม่มีใครใช้ และถ้านับเข้าหน้าต่างอื่น
            # จะเป็นการแปลงหน่วยที่ไม่มีใครสั่ง
            return
        self._forget_older_than(at)
        shortfall = used - self._used_within(span, at)
        if shortfall > 0:
            self._spent.append(_Spent(at=at, weight=shortfall, scope=span))
            self._spent.sort(key=lambda spent: spent.at)

    def _now(self) -> datetime:
        now = self._clock()
        require_aware("เวลาของตัวกั้นอัตรา", now)
        return now

    def _used_within(self, span: timedelta, now: datetime) -> int:
        return sum(
            weight for at, weight, scope in self._spent if now - at < span and scope in (None, span)
        )

    def _counts(self, spent: _Spent, span: timedelta, now: datetime) -> bool:
        """รายการนี้นับเข้าหน้าต่างนั้น ณ เวลานั้นหรือไม่"""
        return now - spent.at < span and spent.scope in (None, span)

    def _forget_older_than(self, now: datetime) -> None:
        longest = max(window.span for window in self._windows)
        self._spent = [spent for spent in self._spent if now - spent.at < longest]

    def _wait_for(self, window: WeightWindow, weight: int, now: datetime) -> timedelta:
        """เวลาที่ต้องรอจนน้ำหนักที่จะขอพอดีกับที่ว่างในหน้าต่างนั้น

        คำนวณจากรายการของเราเอง ไม่ใช่การเดาแทนตลาด — รายการแรกที่หลุดหน้าต่างไป
        คือจังหวะแรกที่โควตาคืนมา
        """
        used = self._used_within(window.span, now)
        for spent in self._spent:
            if not self._counts(spent, window.span, now):
                continue
            used -= spent.weight
            if used + weight <= window.limit:
                return spent.at + window.span - now
        # ต้นทุนก้อนเดียวใหญ่กว่าเพดานของหน้าต่าง — รอเท่าไรก็ไม่พอ
        return window.span
