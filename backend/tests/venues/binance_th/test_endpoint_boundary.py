"""V-32 — รายการ endpoint ต้องถูกบังคับตอนรัน ไม่ใช่แค่ตอนตรวจชนิดข้อมูล"""

from __future__ import annotations

from enum import Enum
from types import SimpleNamespace
from typing import cast

import pytest

from tiewtrade.infra.api_keys import HmacRequestSigner
from tiewtrade.venues.binance_th.endpoints import Endpoint
from tiewtrade.venues.limits import CallCost

from .conftest import RecordingGuard, replying, requests_to, transport_for


class OtherEndpoint(Enum):
    """มี path เหมือนสมาชิกจริง แต่ไม่ได้อยู่ในรายการที่อนุญาต"""

    ACCOUNT = Endpoint.ACCOUNT.path

    @property
    def path(self) -> str:
        return self.value

    @property
    def needs_signature(self) -> bool:
        return False


@pytest.mark.parametrize("signed", [False, True], ids=["public", "signed"])
@pytest.mark.parametrize("kind", ["string", "lookalike", "other_enum"])
async def test_undeclared_endpoints_are_refused_before_any_request(signed: bool, kind: str) -> None:
    """เส้นทางที่ประกอบจากตัวแปรและ object ที่เลียนแบบต้องส่งออกไปไม่ได้"""
    path = "/" + "/".join(("capital", "withdraw"))
    candidate: object
    if kind == "string":
        candidate = path
    elif kind == "lookalike":
        candidate = SimpleNamespace(path=path, name="UNDECLARED", needs_signature=False)
    else:
        candidate = OtherEndpoint.ACCOUNT

    # ตั้งใจข้าม static typing เพื่อพิสูจน์ด่านจริงตอนรัน (plan.md ข้อ 6.4)
    endpoint = cast(Endpoint, candidate)
    handler, seen = requests_to(replying("{}"))
    guard = RecordingGuard()
    transport = transport_for(handler, guard=guard)

    with pytest.raises(TypeError, match="Endpoint") as caught:
        if signed:
            await transport.signed_get(
                endpoint,
                signer=HmacRequestSigner(public_identifier="PUBLIC", secret=b"test-secret"),
                cost=CallCost(weight=1),
            )
        else:
            await transport.get(endpoint, cost=CallCost(weight=1))

    assert seen == []
    assert guard.reserved == []
    assert path not in str(caught.value)
