from __future__ import annotations

import pytest

from tiewtrade.core.market_catalog import COMPATIBILITY_SNAPSHOT, CatalogSnapshot


def test_catalog_snapshot_is_immutable_and_supports_dynamic_pair() -> None:
    snapshot = CatalogSnapshot(7, frozenset({("BTC", "USDT"), ("SOL", "USDT")}))

    assert snapshot.supports("SOL", "USDT")
    assert not snapshot.supports("ETH", "USDT")
    with pytest.raises(AttributeError):
        snapshot.revision = 8  # type: ignore[misc]


@pytest.mark.parametrize(
    ("revision", "pairs", "error"),
    [
        (-1, frozenset(), ValueError),
        (True, frozenset(), ValueError),
        (0, {("BTC", "USDT")}, TypeError),
        (0, frozenset({("btc", "USDT")}), ValueError),
        (0, frozenset({("BTC", "THB")}), ValueError),
    ],
)
def test_catalog_snapshot_rejects_invalid_values(
    revision: object, pairs: object, error: type[Exception]
) -> None:
    with pytest.raises(error):
        CatalogSnapshot(revision, pairs)  # type: ignore[arg-type]


def test_compatibility_snapshot_preserves_f38_seed() -> None:
    assert COMPATIBILITY_SNAPSHOT.revision == 0
    assert COMPATIBILITY_SNAPSHOT.active_pairs == frozenset({("BTC", "USDT"), ("ETH", "USDT")})
