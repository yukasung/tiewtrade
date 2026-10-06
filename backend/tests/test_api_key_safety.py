"""V-32.1/V-33 — พิสูจน์ว่าด่านจับทางลัดและ flag บัญชีได้จริง"""

from __future__ import annotations

from pathlib import Path
from shutil import copyfile

import pytest

from tests.money_movement import check_tree

FIXTURES = Path(__file__).parent / "gates" / "fixtures" / "api_key_safety"


@pytest.mark.parametrize(
    ("fixture", "relative", "rule"),
    [
        ("bad_network_import", "venues/example/shortcut.py", "network-outside-gateway"),
        ("bad_network_from", "venues/example/shortcut.py", "network-outside-gateway"),
        ("bad_network_import", "venues/example/nested/transport.py", "network-outside-gateway"),
        ("bad_url_literal", "venues/example/shortcut.py", "market-url-outside-gateway"),
        ("bad_url_built", "venues/example/shortcut.py", "market-url-outside-gateway"),
        ("bad_url_alias", "venues/example/shortcut.py", "market-url-outside-gateway"),
        ("bad_url_attribute", "venues/example/shortcut.py", "market-url-outside-gateway"),
        ("bad_flags_read", "venues/example/mapping.py", "account-flag"),
        ("bad_flags_attribute", "venues/example/mapping.py", "account-flag"),
        ("bad_flags_alias", "services/api/shortcut.py", "account-flag"),
        ("bad_flags_read", "services/api/shortcut.py", "account-flag"),
        ("bad_network_import", "services/engine/shortcut.py", "network-outside-gateway"),
        ("bad_network_from", "infra/shortcut.py", "network-outside-gateway"),
        ("bad_url_literal", "services/engine/shortcut.py", "market-url-outside-gateway"),
        ("bad_url_built", "infra/shortcut.py", "market-url-outside-gateway"),
        ("bad_url_alias", "services/engine/shortcut.py", "market-url-outside-gateway"),
        ("bad_url_literal", "services/engine/main.py", "market-url-outside-gateway"),
        ("bad_url_literal", "infra/auth/totp.py", "market-url-outside-gateway"),
    ],
)
def test_the_gate_rejects_unsafe_code(
    tmp_path: Path, fixture: str, relative: str, rule: str
) -> None:
    """ใช้ด่านเดียวกับ src จริง และต้องแดงด้วยเหตุผลที่ตั้งใจทดสอบ"""
    adapter = tmp_path / "tiewtrade" / "venues" / "example"
    adapter.mkdir(parents=True)
    (adapter / "__init__.py").write_text("", encoding="utf-8")
    target = tmp_path / "tiewtrade" / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    copyfile(FIXTURES / f"{fixture}.py", target)

    violations = check_tree(tmp_path)

    assert violations, f"ด่านไม่จับ {fixture} ที่ {relative}"
    assert all(item.kind == rule for item in violations)
    assert all(item.path == target and item.line > 0 for item in violations)


def test_the_gate_allows_the_gateway_and_documentation(tmp_path: Path) -> None:
    """transport ตัวจริงใช้เครือข่ายได้ · re-export และ docstring ไม่ใช่ทางลัด"""
    adapter = tmp_path / "tiewtrade" / "venues" / "example"
    adapter.mkdir(parents=True)
    copyfile(FIXTURES / "good_gateway.py", adapter / "transport.py")
    copyfile(FIXTURES / "good_reexport.py", adapter / "__init__.py")
    copyfile(FIXTURES / "good_documentation.py", adapter / "mapping.py")

    assert check_tree(tmp_path) == []


@pytest.mark.parametrize("flag", ["canTrade", "canWithdraw", "canDeposit"])
@pytest.mark.parametrize("fixture", ["bad_flags_read", "bad_flags_attribute", "bad_flags_alias"])
def test_each_account_flag_is_forbidden(tmp_path: Path, flag: str, fixture: str) -> None:
    """ทดสอบแยกทุกชื่อ ไม่ให้การจับชื่อหนึ่งซ่อนการพลาดอีกชื่อหนึ่ง"""
    target = tmp_path / "mapping.py"
    source = (FIXTURES / f"{fixture}.py").read_text(encoding="utf-8")
    target.write_text(source.replace("canTrade", flag), encoding="utf-8")

    violations = check_tree(tmp_path)

    assert violations
    assert all(item.kind == "account-flag" for item in violations)


@pytest.mark.parametrize(
    "source",
    [
        "import httpx\nhttpx.get(target)",
        "import httpx as network\nnetwork.post(target)",
        "from httpx import get as fetch\nfetch(target)",
        "import socket\nsocket.create_connection(address)",
        "import httpx\nclient = httpx.AsyncClient()\nclient.get(target)",
        "import httpx\nclient = httpx.AsyncClient()\nsender = client\nsender.send(request)",
        "import httpx\nasync def run():\n async with httpx.AsyncClient() as client:\n"
        "  await client.request(method, target)",
        "import httpx\ndef send(client: httpx.AsyncClient):\n return client.get(target)",
        "import httpx\ndef send(sender):\n return sender.get(target)\n"
        "client = httpx.AsyncClient()\nsend(client)",
        "import httpx\ndef send(*senders):\n return senders[0].get(target)\n"
        "client = httpx.AsyncClient()\nsend(client)",
        "import httpx\ndef send(**senders):\n return senders['client'].get(target)\n"
        "client = httpx.AsyncClient()\nsend(client=client)",
        "import httpx\nfactory = httpx.AsyncClient\nclient = factory()",
        "import httpx\nclient = httpx.AsyncClient()\nsenders = [client]\nsenders[0].get(target)",
        "import httpx\nclient = httpx.AsyncClient()\nexternal_sender(client)",
        "import httpx\ndef leak():\n return httpx.AsyncClient()",
        "import httpx\nstate.client = httpx.AsyncClient()\nstate.client.get(target)",
        "import httpx\ndef send(sender, /):\n return sender.get(target)\n"
        "client = httpx.AsyncClient()\nsend(client)",
    ],
)
def test_the_engine_exception_does_not_allow_network_shortcuts(tmp_path: Path, source: str) -> None:
    target = tmp_path / "tiewtrade/services/engine/main.py"
    target.parent.mkdir(parents=True)
    target.write_text(source, encoding="utf-8")
    assert check_tree(tmp_path), source


def test_only_the_approved_composition_operations_are_allowed(tmp_path: Path) -> None:
    for relative, source in {
        "services/engine/main.py": (
            "import httpx\nimport socket\n"
            "from tiewtrade.venues import live_wallet_factory as venue\n"
            "def worker_name():\n return socket.gethostname()\n"
            "def build(client: httpx.AsyncClient):\n return venue(client=client)\n"
            "async def serve():\n async with httpx.AsyncClient() as client:\n  build(client)\n"
            "metadata = {}\nmetadata.get('worker')\n"
        ),
        "infra/auth/totp.py": "from urllib.parse import quote as encode\nlabel = encode(account)",
    }.items():
        target = tmp_path / "tiewtrade" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source, encoding="utf-8")
    assert check_tree(tmp_path) == []


def test_the_totp_exception_does_not_allow_other_network_imports(tmp_path: Path) -> None:
    target = tmp_path / "tiewtrade/infra/auth/totp.py"
    target.parent.mkdir(parents=True)
    target.write_text(
        "from urllib.request import urlopen as fetch\nfetch(target)", encoding="utf-8"
    )
    assert check_tree(tmp_path)


@pytest.mark.parametrize(
    "read", ["", "account.get('canTrade')", "account['canWithdraw']", "account.canDeposit"]
)
@pytest.mark.parametrize("inline", [False, True])
def test_account_schema_names_are_allowed_but_flag_reads_are_not(
    tmp_path: Path, read: str, inline: bool
) -> None:
    import json

    shape = Path(__file__).parent / "venues/binance_th/shapes/account_shape.json"
    fields = set(json.loads(json.loads(shape.read_text())["body"]))
    target = tmp_path / "tiewtrade/venues/binance_th/mapping.py"
    target.parent.mkdir(parents=True)
    declaration = f"_ACCOUNT_FIELDS: Final[frozenset[str]] = frozenset({fields!r})"
    separator = "; " if inline and read else "\n"
    target.write_text(f"{declaration}{separator}{read}\n")
    violations = check_tree(tmp_path)
    if read:
        assert any(
            item.kind == "account-flag" and item.line == (1 if inline else 2) for item in violations
        )
    else:
        assert violations == []


@pytest.mark.parametrize("variation", ["wrong-file", "extra-field", "wrong-name"])
def test_account_schema_exception_is_restricted(tmp_path: Path, variation: str) -> None:
    import json

    shape = Path(__file__).parent / "venues/binance_th/shapes/account_shape.json"
    fields = set(json.loads(json.loads(shape.read_text())["body"]))
    if variation == "extra-field":
        fields.add("permissions")
    relative = (
        "tiewtrade/venues/binance_th/mapping.py" if variation != "wrong-file" else "elsewhere.py"
    )
    target = tmp_path / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    name = "_ACCOUNT_FIELDS" if variation != "wrong-name" else "_OTHER_FIELDS"
    target.write_text(f"{name}: Final[frozenset[str]] = frozenset({fields!r})\n")
    assert any(item.kind == "account-flag" for item in check_tree(tmp_path))
