"""Paper-owned code must never gain a path to Live credentials or network clients."""

from __future__ import annotations

import ast
from pathlib import Path

SOURCE = Path(__file__).parents[2] / "src"
PAPER_FILES = (
    SOURCE / "tiewtrade/core/paper_wallet.py",
    *(SOURCE / "tiewtrade/infra/paper_wallet").glob("*.py"),
    SOURCE / "tiewtrade/services/api/paper_wallet_routes.py",
    SOURCE / "tiewtrade/services/engine/paper_wallet.py",
    SOURCE / "tiewtrade/services/engine/paper_wallet_main.py",
)
FORBIDDEN = (
    "aiohttp",
    "httpx",
    "requests",
    "socket",
    "websockets",
    "tiewtrade.infra.api_keys.claims",
    "tiewtrade.infra.api_keys.signing",
    "tiewtrade.infra.api_keys.storage",
    "tiewtrade.infra.crypto",
    "tiewtrade.venues",
)
FORBIDDEN_MARKERS = (
    "create_connection(",
    "live_wallet_factory",
    "open_connection(",
    "secret_sealed",
    "unseal(",
    "user_api_keys",
    "venue_keys(",
)
ALLOWED_INTERNAL_IMPORTS = frozenset(
    {
        "tiewtrade.core.money",
        "tiewtrade.core.paper_wallet",
        "tiewtrade.infra.audit",
        "tiewtrade.infra.auth",
        "tiewtrade.infra.auth.throttle",
        "tiewtrade.infra.db",
        "tiewtrade.infra.db.errors",
        "tiewtrade.infra.db.session",
        "tiewtrade.infra.paper_wallet",
        "tiewtrade.infra.paper_wallet.records",
        "tiewtrade.infra.paper_wallet.storage",
        "tiewtrade.services.api.db_resources",
        "tiewtrade.services.api.request_identity",
        "tiewtrade.services.api.safe_input_routes",
        "tiewtrade.services.api.throttling",
        "tiewtrade.services.engine.paper_wallet",
    }
)


def _imported_modules(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.append(node.module)
    return tuple(imported)


def _violations(paths: tuple[Path, ...]) -> list[str]:
    violations: list[str] = []
    pending = list(paths)
    paper_owned = set(paths)
    inspected: set[Path] = set()
    while pending:
        path = pending.pop()
        if path in inspected:
            continue
        inspected.add(path)
        source = path.read_text(encoding="utf-8")
        for imported in _imported_modules(path):
            if any(imported == item or imported.startswith(f"{item}.") for item in FORBIDDEN):
                violations.append(f"{path}:{imported}")
            if (
                path in paper_owned
                and imported.startswith("tiewtrade.")
                and imported not in ALLOWED_INTERNAL_IMPORTS
            ):
                violations.append(f"{path}:unexpected internal dependency {imported}")
            if imported.startswith("tiewtrade."):
                target = SOURCE / imported.replace(".", "/")
                module = target.with_suffix(".py")
                package = target / "__init__.py"
                if module.exists():
                    pending.append(module)
                elif package.exists():
                    pending.append(package)
            sibling = path.parent / f"{imported.replace('.', '/')}.py"
            if sibling.exists():
                pending.append(sibling)
        for marker in FORBIDDEN_MARKERS:
            if marker in source:
                violations.append(f"{path}:{marker}")
    return violations


def test_paper_owned_modules_cannot_import_live_or_network_code() -> None:
    assert _violations(tuple(PAPER_FILES)) == []


def test_gate_rejects_alias_and_transitive_helper_fixtures(tmp_path: Path) -> None:
    alias_fixture = tmp_path / "alias.py"
    alias_fixture.write_text(
        "from tiewtrade.infra.crypto import unseal as reveal\n", encoding="utf-8"
    )
    entry_fixture = tmp_path / "entry.py"
    entry_fixture.write_text("import helper\n", encoding="utf-8")
    helper_fixture = tmp_path / "helper.py"
    helper_fixture.write_text("import httpx\n", encoding="utf-8")
    direct_read_fixture = tmp_path / "direct_read.py"
    direct_read_fixture.write_text(
        'query = "SELECT secret_sealed FROM user_api_keys"\n', encoding="utf-8"
    )

    violations = _violations((alias_fixture, entry_fixture, direct_read_fixture))

    assert any("tiewtrade.infra.crypto" in item for item in violations)
    assert any("httpx" in item for item in violations)
    assert any("user_api_keys" in item for item in violations)
