"""Validated F-21 configuration shared by API, storage and pure strategy."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from tiewtrade.core.market_data import Timeframe, align_floor
from tiewtrade.core.money import Money
from tiewtrade.core.positions import PositionPair
from tiewtrade.core.strategies import StrategyContractError, StrategyDocument

STRATEGY_NAME = "rsi-step-grid-ema-single-tp"


def initial_state() -> StrategyDocument:
    return StrategyDocument(
        1,
        (
            ("reset_close", None),
            ("reset_open_at", None),
            ("pending_id", None),
            ("pending_filled", False),
            ("entry_sequence", 0),
            ("last_candle", None),
        ),
    )


@dataclass(frozen=True, slots=True)
class RsiStepGridConfig:
    pair: PositionPair
    timeframe: Timeframe
    capital_per_entry: Money
    max_entries: int = 10

    def __post_init__(self) -> None:
        if type(self.pair) is not PositionPair or self.pair not in (
            PositionPair("BTC", "USDT"),
            PositionPair("ETH", "USDT"),
        ):
            raise StrategyContractError("unsupported strategy pair")
        if type(self.timeframe) is not Timeframe:
            raise StrategyContractError("explicit timeframe required")
        if (
            type(self.capital_per_entry) is not Money
            or self.capital_per_entry.currency != self.pair.quote
            or self.capital_per_entry.amount <= 0
        ):
            raise StrategyContractError("positive quote capital per entry required")
        if type(self.max_entries) is not int or not 1 <= self.max_entries <= 10:
            raise StrategyContractError("max_entries must be an integer from 1 to 10")

    def document(self) -> StrategyDocument:
        return StrategyDocument(
            1,
            (
                ("base", self.pair.base),
                ("quote", self.pair.quote),
                ("timeframe", self.timeframe.value),
                ("capital_per_entry", self.capital_per_entry),
                ("max_entries", self.max_entries),
            ),
        )

    @classmethod
    def from_document(cls, document: StrategyDocument) -> "RsiStepGridConfig":
        fields = dict(document.fields)
        if document.version != 1 or fields.keys() != {
            "base",
            "quote",
            "timeframe",
            "capital_per_entry",
            "max_entries",
        }:
            raise StrategyContractError("invalid strategy configuration")
        base, quote, timeframe = fields["base"], fields["quote"], fields["timeframe"]
        capital, count = fields["capital_per_entry"], fields["max_entries"]
        if not all(type(value) is str for value in (base, quote, timeframe)):
            raise StrategyContractError("invalid strategy market")
        if (
            not isinstance(base, str)
            or not isinstance(quote, str)
            or not isinstance(timeframe, str)
        ):
            raise StrategyContractError("invalid strategy market")
        if type(capital) is not Money or type(count) is not int:
            raise StrategyContractError("invalid strategy parameters")
        return cls(PositionPair(base, quote), Timeframe(timeframe), capital, count)

    def validate_checkpoint(self, state: StrategyDocument) -> None:
        values = dict(state.fields)
        if state.version != 1 or values.keys() != dict(initial_state().fields).keys():
            raise StrategyContractError("invalid strategy checkpoint")
        reset, pending = values["reset_close"], values["pending_id"]
        reset_at = values["reset_open_at"]
        sequence, last = values["entry_sequence"], values["last_candle"]
        if (
            (
                reset is not None
                and (
                    type(reset) is not Money
                    or reset.currency != self.pair.quote
                    or reset.amount <= 0
                )
            )
            or (pending is not None and type(pending) is not str)
            or type(values["pending_filled"]) is not bool
            or type(sequence) is not int
            or sequence < 0
            or (last is not None and type(last) is not str)
            or (pending is None and values["pending_filled"])
            or (reset is None) != (reset_at is None)
            or (reset_at is not None and type(reset_at) is not str)
        ):
            raise StrategyContractError("invalid strategy checkpoint values")
        try:
            if isinstance(pending, str) and (str(UUID(pending)) != pending or sequence == 0):
                raise ValueError("invalid pending identity")
            for identity in (last, reset_at):
                if not isinstance(identity, str):
                    continue
                opened = datetime.fromisoformat(identity)
                if (
                    opened.utcoffset() != timedelta(0)
                    or opened.isoformat() != identity
                    or align_floor(opened, self.timeframe) != opened
                ):
                    raise ValueError("invalid candle identity")
        except ValueError:
            raise StrategyContractError("invalid strategy checkpoint identities") from None


PAPER_TEST_STRATEGY = "paper-green-atr-test"
CANDLE_STRATEGIES = frozenset({STRATEGY_NAME, PAPER_TEST_STRATEGY})


def paper_test_initial_state() -> StrategyDocument:
    return StrategyDocument(
        1,
        tuple(
            field
            for field in initial_state().fields
            if field[0] not in {"reset_close", "reset_open_at"}
        ),
    )


@dataclass(frozen=True, slots=True)
class PaperTestConfig:
    pair: PositionPair
    timeframe: Timeframe
    capital_per_entry: Money

    def __post_init__(self) -> None:
        # Reuse approved market/amount validation, without RSI entry semantics.
        RsiStepGridConfig(self.pair, self.timeframe, self.capital_per_entry, 1)

    @property
    def max_entries(self) -> int:
        """Internal occupancy invariant; never a user parameter."""
        return 1

    def document(self) -> StrategyDocument:
        return StrategyDocument(
            1,
            (
                ("strategy_name", PAPER_TEST_STRATEGY),
                ("base", self.pair.base),
                ("quote", self.pair.quote),
                ("timeframe", self.timeframe.value),
                ("capital_per_entry", self.capital_per_entry),
            ),
        )

    @classmethod
    def from_document(cls, document: StrategyDocument) -> "PaperTestConfig":
        fields = dict(document.fields)
        if document.version != 1 or fields.keys() != {
            "strategy_name",
            "base",
            "quote",
            "timeframe",
            "capital_per_entry",
        }:
            raise StrategyContractError("invalid test strategy configuration")
        if fields["strategy_name"] != PAPER_TEST_STRATEGY:
            raise StrategyContractError("test strategy identity differs")
        base, quote, timeframe, capital = (
            fields[k] for k in ("base", "quote", "timeframe", "capital_per_entry")
        )
        if (
            not isinstance(base, str)
            or not isinstance(quote, str)
            or not isinstance(timeframe, str)
            or type(capital) is not Money
        ):
            raise StrategyContractError("invalid test strategy parameters")
        return cls(PositionPair(base, quote), Timeframe(timeframe), capital)

    def validate_checkpoint(self, state: StrategyDocument) -> None:
        if dict(state.fields).keys() != dict(paper_test_initial_state().fields).keys():
            raise StrategyContractError("invalid test strategy checkpoint")
        RsiStepGridConfig(self.pair, self.timeframe, self.capital_per_entry, 1).validate_checkpoint(
            StrategyDocument(
                state.version, (*state.fields, ("reset_close", None), ("reset_open_at", None))
            )
        )


def decode_strategy_config(
    name: str, document: StrategyDocument
) -> RsiStepGridConfig | PaperTestConfig:
    if name == STRATEGY_NAME:
        return RsiStepGridConfig.from_document(document)
    if name == PAPER_TEST_STRATEGY:
        return PaperTestConfig.from_document(document)
    raise StrategyContractError("unknown candle strategy")


def strategy_initial_state(name: str) -> StrategyDocument:
    if name == STRATEGY_NAME:
        return initial_state()
    if name == PAPER_TEST_STRATEGY:
        return paper_test_initial_state()
    raise StrategyContractError("unknown candle strategy")
