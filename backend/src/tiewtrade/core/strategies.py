"""Deterministic strategy inputs and outputs shared by Paper and Live (F-20)."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from tiewtrade.core.indicators import IndicatorStatus, IndicatorValue
from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.orders import OrderIntent, OrderOrigin, OrderScope, OrderStatus, aware
from tiewtrade.core.positions import ExecutionFact, ExecutionSide, PositionPair
from tiewtrade.core.protections import EntryAtrProtection, ProtectionPrices
from tiewtrade.core.strategy_candles import StrategyCandleInput


class StrategyContractError(ValueError):
    """Strategy data does not satisfy the shared contract."""


type StrategyValue = str | int | bool | Money | Quantity | None


@dataclass(frozen=True, slots=True)
class StrategyDocument:
    """Immutable validated configuration or checkpoint with exact numeric values."""

    version: int
    fields: tuple[tuple[str, StrategyValue], ...]

    def __post_init__(self) -> None:
        if type(self.version) is not int or self.version < 1 or type(self.fields) is not tuple:
            raise StrategyContractError("invalid document version or fields")
        names: set[str] = set()
        for field in self.fields:
            if type(field) is not tuple or len(field) != 2:
                raise StrategyContractError("invalid strategy field")
            key, value = field
            if type(key) is not str or not key or key in names:
                raise StrategyContractError("empty or duplicate field name")
            if type(value) not in (str, int, bool, Money, Quantity, type(None)):
                raise StrategyContractError("invalid strategy field value")
            names.add(key)


@dataclass(frozen=True, slots=True)
class StrategyDescriptor:
    name: str
    version: int
    configuration_version: int
    state_version: int
    pairs: frozenset[PositionPair]
    timeframe: str | None
    required_indicators: frozenset[str]
    requires_protection: bool
    quote_trigger: bool = False
    execution_feedback_trigger: bool = False
    feedback_requires_indicators: bool = True

    def __post_init__(self) -> None:
        if type(self.name) is not str or not self.name.strip():
            raise StrategyContractError("strategy identity is required")
        for version in (self.version, self.configuration_version, self.state_version):
            if type(version) is not int or version < 1:
                raise StrategyContractError("positive strategy versions required")
        if (
            type(self.pairs) is not frozenset
            or not self.pairs
            or any(type(pair) is not PositionPair for pair in self.pairs)
            or type(self.required_indicators) is not frozenset
            or any(type(name) is not str or not name for name in self.required_indicators)
            or (
                self.timeframe is not None
                and (type(self.timeframe) is not str or not self.timeframe)
            )
            or type(self.requires_protection) is not bool
            or type(self.quote_trigger) is not bool
            or type(self.execution_feedback_trigger) is not bool
            or type(self.feedback_requires_indicators) is not bool
        ):
            raise StrategyContractError("invalid strategy dependencies")


@dataclass(frozen=True, slots=True)
class ExecutionFeedback:
    order_id: UUID
    revision: int
    status: OrderStatus | None
    execution: ExecutionFact | None = None

    def __post_init__(self) -> None:
        if (
            type(self.order_id) is not UUID
            or type(self.revision) is not int
            or self.revision < 1
            or (self.status is not None and not isinstance(self.status, OrderStatus))
        ):
            raise StrategyContractError("invalid execution feedback")
        if self.execution is not None and (
            type(self.execution) is not ExecutionFact
            or self.status not in (None, OrderStatus.PARTIALLY_FILLED, OrderStatus.FILLED)
        ):
            raise StrategyContractError("execution fact requires a fill result")


@dataclass(frozen=True, slots=True)
class StrategyInput:
    pair: PositionPair
    observed_at: datetime
    market_revision: int
    account_revision: int
    price: Money
    available_quote: Money
    held_base: Quantity
    scope: OrderScope
    run_id: UUID
    input_identity: str
    indicators: tuple[tuple[str, IndicatorValue], ...] = ()
    feedback: ExecutionFeedback | None = None
    indicator_revision: str | None = None
    candle_input: StrategyCandleInput | None = None


@dataclass(frozen=True, slots=True)
class StrategyDecision:
    state: StrategyDocument
    intents: tuple[OrderIntent, ...] = ()
    brackets: tuple[tuple[UUID, ProtectionPrices | EntryAtrProtection], ...] = ()

    def __post_init__(self) -> None:
        if type(self.brackets) is not tuple or type(self.intents) is not tuple:
            raise StrategyContractError("immutable intent and bracket lists required")
        entries = {i.order_id: i for i in self.intents if type(i) is OrderIntent}
        used: set[UUID] = set()
        for bracket in self.brackets:
            if type(bracket) is not tuple or len(bracket) != 2:
                raise StrategyContractError("invalid bracket declaration")
            order_id, protection = bracket
            if type(order_id) is not UUID:
                raise StrategyContractError("bracket order identity required")
            entry = entries.get(order_id)
            if (
                order_id in used
                or entry is None
                or entry.side is not ExecutionSide.BUY
                or type(protection) not in (ProtectionPrices, EntryAtrProtection)
                or entry.pair != protection.pair
            ):
                raise StrategyContractError("bracket must match one BUY intent")
            used.add(order_id)


class Strategy(Protocol):
    @property
    def descriptor(self) -> StrategyDescriptor: ...

    def evaluate(
        self,
        snapshot: StrategyInput,
        configuration: StrategyDocument,
        state: StrategyDocument,
    ) -> StrategyDecision: ...


def evaluate_strategy(
    strategy: Strategy,
    snapshot: StrategyInput,
    configuration: StrategyDocument,
    state: StrategyDocument,
    *,
    scope: OrderScope,
) -> StrategyDecision:
    """Validate strategy boundaries before handing a decision to orchestration."""
    descriptor = strategy.descriptor
    aware(snapshot.observed_at)
    if (
        snapshot.scope != scope
        or type(snapshot.run_id) is not UUID
        or type(snapshot.input_identity) is not str
        or not snapshot.input_identity
        or snapshot.pair not in descriptor.pairs
        or configuration.version != descriptor.configuration_version
        or state.version != descriptor.state_version
        or type(snapshot.market_revision) is not int
        or snapshot.market_revision < 1
        or type(snapshot.account_revision) is not int
        or snapshot.account_revision < 1
    ):
        raise StrategyContractError("strategy input does not match pinned versions or scope")
    if (
        type(snapshot.price) is not Money
        or snapshot.price.currency != snapshot.pair.quote
        or snapshot.price.amount <= 0
        or type(snapshot.available_quote) is not Money
        or snapshot.available_quote.currency != snapshot.pair.quote
        or snapshot.available_quote.amount < 0
        or type(snapshot.held_base) is not Quantity
        or snapshot.held_base.asset != snapshot.pair.base
        or snapshot.held_base.amount < 0
    ):
        raise StrategyContractError("invalid market or account snapshot")
    indicators = dict(snapshot.indicators)
    if len(indicators) != len(snapshot.indicators) or (
        (snapshot.feedback is None or descriptor.feedback_requires_indicators)
        and any(
            name not in indicators
            or indicators[name].status is not IndicatorStatus.READY
            or indicators[name].value is None
            for name in descriptor.required_indicators
        )
    ):
        raise StrategyContractError("required indicators are not ready")
    decision = strategy.evaluate(snapshot, configuration, state)
    if (
        type(decision) is not StrategyDecision
        or type(decision.state) is not StrategyDocument
        or decision.state.version != descriptor.state_version
        or type(decision.intents) is not tuple
    ):
        raise StrategyContractError("invalid decision or checkpoint")
    order_ids: set[UUID] = set()
    keys: set[UUID] = set()
    for intent in decision.intents:
        if (
            type(intent) is not OrderIntent
            or intent.origin is not OrderOrigin.BOT
            or intent.scope != scope
            or intent.pair != snapshot.pair
            or intent.order_id in order_ids
            or intent.idempotency_key in keys
        ):
            raise StrategyContractError("invalid or duplicate strategy intent")
        order_ids.add(intent.order_id)
        keys.add(intent.idempotency_key)
    bracket_ids = {order_id for order_id, _ in decision.brackets}
    if descriptor.requires_protection and any(
        intent.side is ExecutionSide.BUY and intent.order_id not in bracket_ids
        for intent in decision.intents
    ):
        raise StrategyContractError("strategy requires a bracket for each opening intent")
    return decision


def document_payload(document: StrategyDocument) -> dict[str, object]:
    fields = []
    for name, value in document.fields:
        if isinstance(value, Money):
            encoded: object = {"money": value.as_parts()}
        elif isinstance(value, Quantity):
            encoded = {"quantity": value.as_parts()}
        else:
            encoded = value
        fields.append([name, encoded])
    return {"version": document.version, "fields": fields}


def document_from_payload(payload: object, *, expected_version: int) -> StrategyDocument:
    if not isinstance(payload, dict) or payload.keys() != {"version", "fields"}:
        raise StrategyContractError("invalid strategy document")
    version = payload["version"]
    fields = payload["fields"]
    if type(version) is not int or version != expected_version or not isinstance(fields, list):
        raise StrategyContractError("unsupported strategy document version")
    decoded: list[tuple[str, StrategyValue]] = []
    for field in fields:
        if not isinstance(field, list) or len(field) != 2 or not isinstance(field[0], str):
            raise StrategyContractError("invalid encoded strategy field")
        name, encoded = field
        value: StrategyValue
        if isinstance(encoded, dict):
            if encoded.keys() == {"money"}:
                value = Money.from_parts(encoded["money"])
            elif encoded.keys() == {"quantity"}:
                value = Quantity.from_parts(encoded["quantity"])
            else:
                raise StrategyContractError("invalid encoded numeric value")
        elif encoded is None or isinstance(encoded, (str, bool, int)):
            value = encoded
        else:
            raise StrategyContractError("invalid encoded strategy value")
        decoded.append((name, value))
    return StrategyDocument(version, tuple(decoded))
