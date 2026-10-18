import ast
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.positions import (
    ExecutionFact,
    ExecutionSide,
    FeeEffect,
    PositionError,
    PositionPair,
    rebuild_correction,
    rebuild_position,
)


def _forbidden_position_dependencies(source: str) -> set[str]:
    tree = ast.parse(source)
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported.update(
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    )
    prefixes = ("tiewtrade.venues", "httpx", "websockets", "aiohttp", "requests")
    return {
        name for name in imported if name.startswith(prefixes) or name == "tiewtrade.infra.api_keys"
    }


PAIR = PositionPair("BTC", "USDT")


def _fact(
    sequence: int,
    side: ExecutionSide,
    quantity: str,
    quote: str,
    fee: Money | Quantity | None = None,
) -> ExecutionFact:
    return ExecutionFact(
        uuid4(),
        PAIR,
        side,
        Quantity.of(quantity, "BTC"),
        Money.of(quote, "USDT"),
        None if fee is None else FeeEffect(fee),
        sequence,
        datetime(2026, 10, 16, tzinfo=UTC),
    )


PARITY_STREAMS = (
    (
        _fact(1, ExecutionSide.BUY, "2", "200"),
        _fact(2, ExecutionSide.BUY, "1", "130"),
        _fact(3, ExecutionSide.SELL, "1", "150"),
        _fact(4, ExecutionSide.SELL, "2", "180"),
    ),
    (_fact(1, ExecutionSide.BUY, "1", "100", Quantity.of("0.001", "BTC")),),
    (
        _fact(1, ExecutionSide.BUY, "1", "100"),
        _fact(2, ExecutionSide.SELL, "0.5", "60", Money.of("0.06", "USDT")),
    ),
    (_fact(1, ExecutionSide.BUY, "1", "100", Quantity.of("0.0002", "BNB")),),
    (_fact(1, ExecutionSide.BUY, "1", "100", Quantity.of("-0.0002", "BNB")),),
    (_fact(2, ExecutionSide.BUY, "1", "100"),),
)


def _fold_outcome(slots: tuple[ExecutionFact | None, ...]) -> object:
    try:
        return rebuild_position(PAIR, slots)
    except PositionError as error:
        return type(error), str(error)


@pytest.mark.parametrize("facts", PARITY_STREAMS)
def test_paper_and_live_boundaries_use_the_same_position_fold(
    facts: tuple[ExecutionFact, ...],
) -> None:

    def paper_boundary() -> object:
        return _fold_outcome(facts)

    def fake_live_boundary() -> object:
        return _fold_outcome(facts)

    assert paper_boundary() == fake_live_boundary()


def test_paper_and_live_boundaries_use_the_same_correction_fold() -> None:
    original = _fact(1, ExecutionSide.BUY, "1", "100", Quantity.of("0.01", "BNB"))
    replacement = ExecutionFact(
        original.execution_id,
        PAIR,
        ExecutionSide.BUY,
        Quantity.of("1", "BTC"),
        Money.of("110", "USDT"),
        FeeEffect(Quantity.of("0.02", "ETH")),
        1,
        original.occurred_at,
    )

    paper = rebuild_correction(PAIR, (original,), (replacement,))
    fake_live = rebuild_correction(PAIR, (original,), (replacement,))

    assert paper == fake_live


def test_position_storage_has_no_venue_network_or_credential_dependency() -> None:
    source = Path("src/tiewtrade/infra/positions/storage.py").read_text(encoding="utf-8")

    assert _forbidden_position_dependencies(source) == set()


def test_position_dependency_gate_rejects_a_negative_fixture() -> None:
    source = "import httpx\nfrom tiewtrade.venues import binance_th\n"

    assert _forbidden_position_dependencies(source) == {"httpx", "tiewtrade.venues"}


def test_position_package_does_not_load_network_venue_or_credentials_at_runtime() -> None:
    script = """
import sys
import tiewtrade.infra.positions
forbidden = [
    name for name in sys.modules
    if name.startswith('tiewtrade.infra.api_keys')
    or name.startswith('tiewtrade.venues')
    or name.split('.')[0] in {'httpx', 'websockets', 'aiohttp', 'requests'}
]
raise SystemExit(1 if forbidden else 0)
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
