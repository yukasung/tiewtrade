"""Static market catalog approved for the current development scope."""

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
