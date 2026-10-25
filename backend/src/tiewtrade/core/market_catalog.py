"""Pure supported-symbol catalog contracts and the rolling compatibility snapshot."""

from dataclasses import dataclass
from typing import Final, Literal

type MarketSource = Literal["primary_spot"]
type SupportedBase = Literal["BTC", "ETH"]
type SupportedQuote = Literal["USDT"]

SOURCE: Final[MarketSource] = "primary_spot"
QUOTE: Final[SupportedQuote] = "USDT"
SUPPORTED_BASES: Final[tuple[SupportedBase, ...]] = ("BTC", "ETH")
PAIRS: Final[frozenset[tuple[SupportedBase, SupportedQuote]]] = frozenset(
    (base, QUOTE) for base in SUPPORTED_BASES
)

type CatalogPair = tuple[str, str]


@dataclass(frozen=True, slots=True)
class CatalogSnapshot:
    """Immutable catalog input supplied to pure domain decisions by their caller."""

    revision: int
    active_pairs: frozenset[CatalogPair]

    def __post_init__(self) -> None:
        if type(self.revision) is not int or self.revision < 0:
            raise ValueError("catalog revision must be a nonnegative integer")
        if type(self.active_pairs) is not frozenset:
            raise TypeError("active_pairs must be an immutable frozenset")
        for pair in self.active_pairs:
            if type(pair) is not tuple or len(pair) != 2:
                raise ValueError("catalog pairs must be (base, quote) tuples")
            base, quote = pair
            if (
                type(base) is not str
                or not base
                or base != base.upper()
                or type(quote) is not str
                or quote != QUOTE
            ):
                raise ValueError("catalog pairs must be normalized BASE/USDT symbols")

    def supports(self, base: str, quote: str) -> bool:
        """Return whether an opening-risk decision may use the normalized pair."""
        return (base, quote) in self.active_pairs


# Readers use this only while the ADR-005 protocol gate remains disabled.
COMPATIBILITY_SNAPSHOT: Final[CatalogSnapshot] = CatalogSnapshot(
    revision=0,
    active_pairs=frozenset((str(base), str(quote)) for base, quote in PAIRS),
)
