"""ด่านเส้นทางที่ย้ายเงิน — V-32, V-32.1, V-32.2 (F-07 RQ-16)

**ไม่พอที่จะเขียวบนโค้ดที่ถูกอยู่แล้ว** ด่านต้องพิสูจน์ว่าจับของผิดได้จริง
ตามแบบแผนของ F-01 และ F-33
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.money_movement import FORBIDDEN_PATH_FRAGMENTS, check_no_money_paths, check_tree
from tiewtrade.venues.binance_th.endpoints import Endpoint

BACKEND_ROOT = Path(__file__).parents[1]
SOURCE_ROOT = BACKEND_ROOT / "src"
FIXTURES = Path(__file__).parent / "gates" / "fixtures" / "money_paths"


def test_the_whole_source_tree_is_clean() -> None:
    """V-32/V-33 — src ต้องไม่มีเส้นทางย้ายเงิน ทางลัด หรือการใช้ flag บัญชี"""
    violations = check_tree(SOURCE_ROOT)
    assert violations == [], "\n".join(str(violation) for violation in violations)


@pytest.mark.parametrize("name", ["bad_literal", "bad_built"])
def test_the_gate_catches_a_file_that_names_a_money_path(name: str) -> None:
    """V-32.2 — ด่านจับไฟล์ที่ผิดได้จริง ทั้งแบบเขียนตรงและแบบประกอบจากชิ้นส่วน"""
    violations = check_no_money_paths(FIXTURES / f"{name}.py")

    assert violations, f"ด่านไม่จับ {name}"
    assert all(violation.kind == "money-moving-path" for violation in violations)


def test_the_gate_leaves_a_correct_file_alone() -> None:
    """ด่านต้องไม่ดังกับเส้นทางที่อ่านอย่างเดียว และไม่ดังกับคำในคำอธิบาย"""
    assert check_no_money_paths(FIXTURES / "good.py") == []


def test_every_declared_endpoint_is_a_read() -> None:
    """V-32 — ทุกสมาชิกของรายการปิดต้องไม่ใช่เส้นทางที่ย้ายเงิน

    รายการปิดคือชั้นที่บังคับจริง ฉะนั้นมันเองต้องถูกตรวจด้วย — มิฉะนั้นการเพิ่ม
    สมาชิกที่ถอนเงินจะทำให้ทุกอย่างถูกต้องตามกฎทันที
    """
    for endpoint in Endpoint:
        lowered = endpoint.path.lower()
        for fragment in FORBIDDEN_PATH_FRAGMENTS:
            assert fragment not in lowered, f"{endpoint.name} เป็นเส้นทางที่ย้ายเงิน"


def test_only_the_transport_reaches_the_network() -> None:
    """V-32.1 — ไม่มีทางลัดรอบตัวส่งคำขอ

    ถ้าโมดูลอื่นต่อเครือข่ายเองได้ รายการปิดของ `Endpoint` ก็ไม่ได้ครอบคำขอทุกใบ
    และด่านนี้ทั้งด่านจะกลายเป็นของประดับ · กฎนี้มีอยู่แล้วใน import-linter
    (contract "การแปลข้อมูลของตัวเชื่อม…") เทสต์นี้ยืนยันว่ามันยังครอบโมดูลใหม่ด้วย
    """
    from tests.venue_isolation import modules_not_reaching

    adapter = SOURCE_ROOT / "tiewtrade" / "venues" / "binance_th"
    reaching = {path.name for path in adapter.glob("*.py")} - {
        path.name for path in modules_not_reaching(adapter, "transport")
    }
    assert reaching == {
        "__init__.py",
        "transport.py",
        "prices.py",
        "constraints.py",
        "wallets.py",
        "candles.py",
        "price_feed.py",  # F-10 REST recovery goes through the existing HTTP gateway.
    }
    stream_reaching = {path.name for path in adapter.glob("*.py")} - {
        path.name for path in modules_not_reaching(adapter, "stream_transport")
    }
    assert stream_reaching == {
        "__init__.py",
        "price_feed.py",
        "candle_feed.py",
        "stream_transport.py",
    }


def test_public_stream_gateway_and_feed_composition_are_allowed(tmp_path: Path) -> None:
    files = {
        "tiewtrade/venues/binance_th/stream_transport.py": (
            "from websockets.asyncio.client import connect\n"
            "STREAM_URL = 'wss://nbstream.binance.th/w3w/wsa/stream'\n"
        ),
        "tiewtrade/services/market_data/main.py": (
            "import httpx\nfrom tiewtrade.venues import live_price_feed as feed\n"
            "async def run():\n async with httpx.AsyncClient() as client:\n"
            "  feed(client=client)\n"
        ),
        "tiewtrade/services/api/settings.py": (
            "def price_origins():\n return value.startswith(('http://', 'https://'))\n"
        ),
    }
    for relative, source in files.items():
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source)
    assert check_tree(tmp_path) == []


@pytest.mark.parametrize(
    "relative",
    [
        "tiewtrade/venues/example/stream_transport.py",
        "tiewtrade/venues/binance_th/price_feed.py",
        "tiewtrade/services/market_data/main.py",
    ],
)
def test_stream_gateway_exception_does_not_allow_other_network_locations(
    tmp_path: Path,
    relative: str,
) -> None:
    target = tmp_path / relative
    target.parent.mkdir(parents=True)
    target.write_text("from websockets.asyncio.client import connect\n")
    assert any(v.kind == "network-outside-gateway" for v in check_tree(tmp_path))


@pytest.mark.parametrize(
    "source",
    [
        "ENDPOINT = 'wss://nbstream.binance.th/w3w/wsa/stream'\n",
        "def price_origins():\n return 'https://market.example'\n",
        "def other():\n return value.startswith(('http://', 'https://'))\n",
        "def price_origins():\n return ('http://', 'https://')\n",
    ],
)
def test_origin_prefix_exception_does_not_allow_url_construction(
    tmp_path: Path,
    source: str,
) -> None:
    target = tmp_path / "tiewtrade/services/api/settings.py"
    target.parent.mkdir(parents=True)
    target.write_text(source)
    assert any(v.kind == "market-url-outside-gateway" for v in check_tree(tmp_path))


def test_stream_gateway_does_not_add_an_http_gateway(tmp_path: Path) -> None:
    target = tmp_path / "tiewtrade/venues/binance_th/stream_transport.py"
    target.parent.mkdir(parents=True)
    target.write_text("import httpx\n")
    assert any(v.kind == "network-outside-gateway" for v in check_tree(tmp_path))


def test_public_feed_client_composition_is_market_data_only(tmp_path: Path) -> None:
    target = tmp_path / "tiewtrade/services/engine/main.py"
    target.parent.mkdir(parents=True)
    target.write_text(
        "import httpx\nfrom tiewtrade.venues import live_price_feed as feed\n"
        "async def run():\n async with httpx.AsyncClient() as client:\n  feed(client=client)\n"
    )
    assert any(v.kind == "network-outside-gateway" for v in check_tree(tmp_path))


DECODER_SOURCE = (
    "from websockets.server import ServerProtocol as Decoder\n"
    "from websockets.frames import CloseCode as Code\n"
    "class Incoming(Decoder):\n"
    " def fail(self, code: Code | int):\n"
    "  if code == Code.MESSAGE_TOO_BIG:\n"
    "   code = Code.POLICY_VIOLATION\n"
)


def test_server_decoder_exception_allows_only_the_approved_usage(tmp_path: Path) -> None:
    target = tmp_path / "tiewtrade/services/api/price_protocol.py"
    target.parent.mkdir(parents=True)
    target.write_text(DECODER_SOURCE)
    assert check_tree(tmp_path) == []


@pytest.mark.parametrize(
    "relative",
    [
        "tiewtrade/services/api/app.py",
        "tiewtrade/services/api/other_protocol.py",
        "tiewtrade/services/engine/main.py",
        "tiewtrade/infra/realtime/price_protocol.py",
    ],
)
def test_server_decoder_exception_does_not_extend_to_other_files(
    tmp_path: Path,
    relative: str,
) -> None:
    target = tmp_path / relative
    target.parent.mkdir(parents=True)
    target.write_text(DECODER_SOURCE)
    assert any(v.kind == "network-outside-gateway" for v in check_tree(tmp_path))


@pytest.mark.parametrize(
    "source",
    [
        "from websockets.asyncio.client import connect\n",
        "from websockets.server import ServerConnection\n",
        "from websockets.frames import Frame\n",
        "import websockets.server\n",
        "from .websockets.server import ServerProtocol\n",
        "from websockets.server import ServerProtocol\nx = ServerProtocol()\n",
        "from websockets.server import ServerProtocol\nExported = ServerProtocol\n",
        "from websockets.server import ServerProtocol\n__all__ = ['ServerProtocol']\n",
        "from websockets.frames import CloseCode\nx = CloseCode(1008)\n",
        "from websockets.frames import CloseCode\nExported = CloseCode\n",
        "from websockets.frames import CloseCode\nx = CloseCode.__class__\n",
        "from websockets.frames import CloseCode\nCloseCode.POLICY_VIOLATION = 1\n",
        "from websockets.frames import CloseCode\nx = getattr(CloseCode, 'POLICY_VIOLATION')\n",
        "import socket\n",
        "import httpx\n",
        "import asyncio\nasyncio.open_connection('example', 443)\n",
        "MARKET = 'wss://market.example/stream'\n",
    ],
)
def test_server_decoder_exception_does_not_allow_outbound_or_other_uses(
    tmp_path: Path,
    source: str,
) -> None:
    target = tmp_path / "tiewtrade/services/api/price_protocol.py"
    target.parent.mkdir(parents=True)
    target.write_text(DECODER_SOURCE + source)
    assert check_tree(tmp_path)
