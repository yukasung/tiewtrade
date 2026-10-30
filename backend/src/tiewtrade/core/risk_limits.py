"""Shared pure loss accounting and admission; F-18 requirements NC-F18-01..08."""

from collections.abc import Iterator
from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum
from uuid import UUID

from tiewtrade.core.money import Money, Quantity, RoundingDirection, allocate_money
from tiewtrade.core.orders import (
    BaseSize,
    OrderConflictError,
    OrderIntent,
    SafetyUnavailableError,
    TradingMode,
    aware,
)
from tiewtrade.core.positions import (
    ExecutionFact,
    ExecutionSide,
    PositionPair,
    PositionSequenceError,
    PositionState,
    apply_execution,
    rebuild_position,
    unrealized_pnl,
)
from tiewtrade.core.realtime_prices import QuoteObservation, Readiness, readiness


class RiskInputError(ValueError):
    code = "RISK_INPUT_INVALID"


class RiskUnavailableError(SafetyUnavailableError):
    code = "RISK_SOURCE_UNAVAILABLE"


class LossLimitReachedError(SafetyUnavailableError):
    code = "RISK_LOSS_LIMIT_REACHED"


class RiskLimitUnsetError(RiskUnavailableError):
    code = "RISK_LIMIT_UNSET"


class RiskPriceUnavailableError(RiskUnavailableError):
    code = "RISK_PRICE_UNAVAILABLE"


class RiskReason(Enum):
    READY = "READY"
    UNSET = "RISK_LIMIT_UNSET"
    SOURCE_UNAVAILABLE = "RISK_SOURCE_UNAVAILABLE"
    PRICE_UNAVAILABLE = "RISK_PRICE_UNAVAILABLE"
    BREACHED = "RISK_LOSS_LIMIT_REACHED"


class RiskStopProgress(Enum):
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    PROBLEMS = "PROBLEMS"


def _usdt(value: Money) -> None:
    if type(value) is not Money or value.currency != "USDT":
        raise RiskInputError("risk accounting requires USDT Money")


def _revision(value: int) -> None:
    if type(value) is not int or value < 0:
        raise RiskInputError("nonnegative revision required")


def _loss(pnl: Money) -> Money:
    zero = Money.of(0, pnl.currency)
    return zero - pnl if pnl < zero else zero


@dataclass(frozen=True, slots=True)
class RiskScope:
    owner_id: UUID
    mode: TradingMode
    wallet_id: UUID | None = None
    episode_id: UUID | None = None

    def __post_init__(self) -> None:
        if type(self.owner_id) is not UUID or not isinstance(self.mode, TradingMode):
            raise RiskInputError("explicit risk owner and mode required")
        if self.mode is TradingMode.PAPER:
            if type(self.wallet_id) is not UUID or type(self.episode_id) is not UUID:
                raise RiskInputError("Paper wallet and episode required")
        elif self.wallet_id is not None or self.episode_id is not None:
            raise RiskInputError("Live cannot use Paper financial identities")


@dataclass(frozen=True, slots=True)
class RiskSetting:
    scope: RiskScope
    revision: int
    limit: Money | None
    latched: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.scope, RiskScope) or type(self.latched) is not bool:
            raise RiskInputError("invalid risk setting")
        _revision(self.revision)
        if self.limit is not None:
            _usdt(self.limit)
            if self.limit.amount <= 0:
                raise RiskInputError("loss limit must be positive")
        if self.latched and self.limit is None:
            raise RiskInputError("unset limit cannot have a breach latch")


@dataclass(frozen=True, slots=True)
class RiskPrice:
    pair: PositionPair
    observation: QuoteObservation | None
    connected: bool
    reconciled: bool
    lease_until: datetime
    generation: int
    revision: int

    def __post_init__(self) -> None:
        if not isinstance(self.pair, PositionPair) or self.pair.quote != "USDT":
            raise RiskInputError("USDT price pair required")
        if type(self.connected) is not bool or type(self.reconciled) is not bool:
            raise RiskInputError("explicit price readiness required")
        aware(self.lease_until)
        for value in (self.generation, self.revision):
            _revision(value)
            if value == 0:
                raise RiskInputError("positive price generation and revision required")
        if self.observation is not None and (
            not isinstance(self.observation, QuoteObservation)
            or (
                self.observation.base,
                self.observation.quote,
            )
            != (self.pair.base, self.pair.quote)
        ):
            raise RiskInputError("price observation pair mismatch")

    def price_at(self, now: datetime) -> Money | None:
        aware(now)
        state = readiness(
            quote=self.observation,
            connected=self.connected,
            reconciled=self.reconciled,
            producer_alive=self.lease_until > now,
            now=now,
        )
        return (
            self.observation.amount
            if state is Readiness.READY and self.observation is not None
            else None
        )


@dataclass(frozen=True, slots=True)
class PairRiskState:
    position: PositionState
    allowance: Money
    adjusted_realized: Money

    def __post_init__(self) -> None:
        if not isinstance(self.position, PositionState) or self.position.pair.quote != "USDT":
            raise RiskInputError("USDT position required")
        _usdt(self.allowance)
        _usdt(self.adjusted_realized)
        if self.allowance.amount < 0:
            raise RiskInputError("negative loss allowance")
        if self.position.held_quantity.amount == 0 and self.allowance.amount != 0:
            raise RiskInputError("closed position cannot retain allowance")


@dataclass(frozen=True, slots=True)
class RiskBook:
    scope: RiskScope
    source_revision: int
    pairs: tuple[PairRiskState, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.scope, RiskScope) or type(self.pairs) is not tuple:
            raise RiskInputError("immutable scoped risk book required")
        _revision(self.source_revision)
        seen: set[PositionPair] = set()
        sequences: set[int] = set()
        for item in self.pairs:
            if not isinstance(item, PairRiskState) or item.position.pair in seen:
                raise RiskInputError("invalid or duplicate risk pair")
            seen.add(item.position.pair)
            sequences.add(item.position.last_sequence)
        if len(sequences) > 1:
            raise RiskInputError("risk positions must share the authoritative source cursor")


@dataclass(frozen=True, slots=True)
class RiskBaseline:
    reset_id: UUID
    reset_at: datetime
    book: RiskBook
    prices: tuple[RiskPrice, ...]

    def __post_init__(self) -> None:
        if type(self.reset_id) is not UUID or not isinstance(self.book, RiskBook):
            raise RiskInputError("reset identity and book required")
        aware(self.reset_at)
        rows = _prices(self.prices)
        for item in self.book.pairs:
            row = rows.get(item.position.pair)
            pnl = unrealized_pnl(
                item.position, None if row is None else row.price_at(self.reset_at)
            )
            if pnl is None:
                raise RiskUnavailableError("reset baseline has no historical valuation")
            if item.adjusted_realized.amount != 0 or item.allowance != _loss(pnl):
                raise RiskInputError("reset baseline does not match its captured valuation")


@dataclass(frozen=True, slots=True)
class RiskEvaluation:
    scope: RiskScope
    setting_revision: int
    source_revision: int
    evaluated_at: datetime
    reason: RiskReason
    loss: Money | None
    latched: bool
    new_breach: bool

    def __post_init__(self) -> None:
        if not isinstance(self.scope, RiskScope) or not isinstance(self.reason, RiskReason):
            raise RiskInputError("invalid risk evaluation")
        _revision(self.setting_revision)
        _revision(self.source_revision)
        aware(self.evaluated_at)
        if type(self.latched) is not bool or type(self.new_breach) is not bool:
            raise RiskInputError("explicit breach state required")
        if self.loss is not None:
            _usdt(self.loss)
            if self.loss.amount < 0:
                raise RiskInputError("negative evaluated loss")
        if self.new_breach and (not self.latched or self.reason is not RiskReason.BREACHED):
            raise RiskInputError("invalid new breach")
        available = self.reason in (RiskReason.READY, RiskReason.UNSET, RiskReason.BREACHED)
        if available != (self.loss is not None):
            raise RiskInputError("valuation readiness and loss must agree")
        if self.reason is RiskReason.READY and self.latched:
            raise RiskInputError("latched evaluation cannot permit opening")
        if self.reason is RiskReason.BREACHED and not self.latched:
            raise RiskInputError("breach evaluation requires latch")


@dataclass(frozen=True, slots=True)
class RiskStop:
    scope: RiskScope
    stop_id: UUID
    risk_revision: int
    target_count: int
    pending_count: int
    failed_count: int
    target_set_complete: bool

    def __post_init__(self) -> None:
        if not isinstance(self.scope, RiskScope) or type(self.stop_id) is not UUID:
            raise RiskInputError("scoped stop identity required")
        for value in (self.risk_revision, self.target_count, self.pending_count, self.failed_count):
            _revision(value)
        if (
            self.failed_count > self.pending_count
            or self.pending_count > self.target_count
            or type(self.target_set_complete) is not bool
        ):
            raise RiskInputError("inconsistent stop completeness/counts")

    @property
    def progress(self) -> RiskStopProgress:
        if self.failed_count:
            return RiskStopProgress.PROBLEMS
        if self.target_set_complete and self.pending_count == 0:
            return RiskStopProgress.STOPPED
        return RiskStopProgress.STOPPING


def _prices(prices: tuple[RiskPrice, ...]) -> dict[PositionPair, RiskPrice]:
    if type(prices) is not tuple:
        raise RiskInputError("immutable price frame required")
    result: dict[PositionPair, RiskPrice] = {}
    for price in prices:
        if not isinstance(price, RiskPrice) or price.pair in result:
            raise RiskInputError("invalid or duplicate price pair")
        result[price.pair] = price
    return result


def initial_risk_book(
    scope: RiskScope, positions: tuple[PositionState, ...], *, source_revision: int
) -> RiskBook:
    """Adopt authoritative episode facts without granting an implicit loss reset."""
    if type(positions) is not tuple:
        raise RiskInputError("immutable positions required")
    if any(not isinstance(p, PositionState) for p in positions):
        raise RiskInputError("invalid authoritative position")
    return RiskBook(
        scope,
        source_revision,
        tuple(PairRiskState(p, Money.of(0, "USDT"), p.realized_pnl) for p in positions),
    )


def _net_risk_money(values: tuple[Money, ...]) -> tuple[Money, ...]:
    """Cancel opposite signs before summing, preserving Money's existing bounds.

    Every cancellation lies between its two valid operands. A representable net
    must not fail merely because same-sign terms were encountered first.
    """
    positive: list[Money] = []
    negative: list[Money] = []
    for value in values:
        _usdt(value)
        if value.amount > 0:
            positive.append(value)
        elif value.amount < 0:
            negative.append(value)
    while positive and negative:
        value = positive.pop() + negative.pop()
        if value.amount > 0:
            positive.append(value)
        elif value.amount < 0:
            negative.append(value)
    return tuple(positive or negative)


def sum_risk_money(values: tuple[Money, ...]) -> Money:
    total = Money.of(0, "USDT")
    for value in _net_risk_money(values):
        total += value
    return total


def _valuation_loss(
    book: RiskBook, price_map: dict[PositionPair, RiskPrice], now: datetime
) -> Money | None:
    terms: list[Money] = []
    zero = Money.of(0, "USDT")
    for item in book.pairs:
        row = price_map.get(item.position.pair)
        pnl = unrealized_pnl(item.position, None if row is None else row.price_at(now))
        if pnl is None:
            return None
        terms.append(max(zero, _loss(pnl) - item.allowance))
        terms.append(zero - item.adjusted_realized)
    remaining = _net_risk_money(tuple(terms))
    return sum_risk_money(remaining) if remaining and remaining[0].amount > 0 else zero


def evaluate_risk(
    setting: RiskSetting,
    book: RiskBook,
    prices: tuple[RiskPrice, ...],
    *,
    now: datetime,
    source_ready: bool,
) -> RiskEvaluation:
    return _evaluate_risk(setting, book, prices, now=now, source_ready=source_ready, losses=None)


def iter_risk_evaluations(
    setting: RiskSetting,
    book: RiskBook,
    frames: tuple[tuple[datetime, tuple[RiskPrice, ...]], ...],
    *,
    source_ready: bool,
) -> Iterator[RiskEvaluation]:
    """Replay lazily, reusing only valuations of this immutable book within this call.

    Yield before advancing so callers can persist a transient breach even when a
    later frame fails. Latch transitions use the same single-frame domain rule.
    """
    if type(frames) is not tuple or len(frames) > 100:
        raise RiskInputError("bounded immutable risk frames required")
    losses: dict[tuple[Money | None, ...], Money] = {}
    for now, prices in frames:
        evaluation = _evaluate_risk(
            setting, book, prices, now=now, source_ready=source_ready, losses=losses
        )
        yield evaluation
        setting = latch_risk(setting, evaluation)


def _evaluate_risk(
    setting: RiskSetting,
    book: RiskBook,
    prices: tuple[RiskPrice, ...],
    *,
    now: datetime,
    source_ready: bool,
    losses: dict[tuple[Money | None, ...], Money] | None,
) -> RiskEvaluation:
    aware(now)
    if setting.scope != book.scope:
        raise RiskInputError("risk setting/book scope mismatch")
    if type(source_ready) is not bool:
        raise RiskInputError("explicit source availability required")
    price_map = _prices(prices)
    reason = RiskReason.READY if source_ready else RiskReason.SOURCE_UNAVAILABLE
    loss = None
    if source_ready:
        marks = None
        if losses is not None:
            # Readiness is checked at this frame's time even when amounts repeat.
            marks = tuple(
                None if (row := price_map.get(item.position.pair)) is None else row.price_at(now)
                for item in book.pairs
            )
            loss = losses.get(marks)
        if loss is None:
            loss = _valuation_loss(book, price_map, now)
            if losses is not None and marks is not None and loss is not None:
                losses[marks] = loss
        if loss is None:
            reason = RiskReason.PRICE_UNAVAILABLE
    reached = loss is not None and setting.limit is not None and not loss < setting.limit
    latched = setting.latched or reached
    if reason is RiskReason.READY:
        reason = (
            RiskReason.BREACHED
            if latched
            else RiskReason.UNSET
            if setting.limit is None
            else RiskReason.READY
        )
    return RiskEvaluation(
        setting.scope,
        setting.revision,
        book.source_revision,
        now,
        reason,
        loss,
        latched,
        reached and not setting.latched,
    )


def _advance_pair(previous: PairRiskState, fact: ExecutionFact) -> PairRiskState:
    transition = apply_execution(previous.position, fact)
    allowance = previous.allowance
    increment = transition.realized_increment
    if fact.side is ExecutionSide.SELL:
        removed = previous.position.held_quantity - transition.state.held_quantity
        allocated = (
            allowance
            if transition.state.held_quantity.amount == 0
            else allocate_money(
                allowance,
                removed,
                previous.position.held_quantity,
                rounding=RoundingDirection.TOWARD_ZERO,
            )
        )
        increment += min(allocated, _loss(increment))
        allowance -= allocated
    return PairRiskState(transition.state, allowance, previous.adjusted_realized + increment)


def _pair_key(item: PairRiskState) -> str:
    return item.position.pair.base


def apply_risk_execution(book: RiskBook, fact: ExecutionFact, *, source_revision: int) -> RiskBook:
    """Consume an F-14 execution once; its sequence guard rejects duplicate effects."""
    _revision(source_revision)
    if source_revision <= book.source_revision:
        raise RiskInputError("risk source revision must advance")
    if not isinstance(fact, ExecutionFact):
        raise RiskInputError("execution fact required")
    sequence = max((p.position.last_sequence for p in book.pairs), default=0)
    if fact.source_sequence != sequence + 1:
        raise PositionSequenceError("risk execution source sequence is not contiguous")
    previous = next((p for p in book.pairs if p.position.pair == fact.pair), None)
    if previous is None:
        previous = PairRiskState(
            replace(PositionState.empty(fact.pair), last_sequence=sequence),
            Money.of(0, "USDT"),
            Money.of(0, "USDT"),
        )
    updated = _advance_pair(previous, fact)
    pairs: tuple[PairRiskState, ...] = (
        *(
            replace(p, position=replace(p.position, last_sequence=fact.source_sequence))
            for p in book.pairs
            if p.position.pair != fact.pair
        ),
        updated,
    )
    return RiskBook(book.scope, source_revision, tuple(sorted(pairs, key=_pair_key)))


def reset_risk(
    setting: RiskSetting,
    book: RiskBook,
    prices: tuple[RiskPrice, ...],
    *,
    reset_id: UUID,
    now: datetime,
    source_ready: bool,
) -> tuple[RiskSetting, RiskBaseline]:
    evaluation = evaluate_risk(setting, book, prices, now=now, source_ready=source_ready)
    if evaluation.loss is None:
        raise RiskUnavailableError("complete valuation required for loss reset")
    if setting.limit is None:
        raise RiskInputError("cannot reset an unset loss limit")
    rows = _prices(prices)
    pairs = []
    for item in book.pairs:
        row = rows.get(item.position.pair)
        pnl = unrealized_pnl(item.position, None if row is None else row.price_at(now))
        if pnl is None:
            raise RiskUnavailableError("reset price unavailable")
        pairs.append(PairRiskState(item.position, _loss(pnl), Money.of(0, "USDT")))
    baseline = RiskBaseline(
        reset_id, now, RiskBook(book.scope, book.source_revision, tuple(pairs)), prices
    )
    return replace(setting, revision=setting.revision + 1, latched=False), baseline


def latch_risk(setting: RiskSetting, evaluation: RiskEvaluation) -> RiskSetting:
    if setting.scope != evaluation.scope or setting.revision != evaluation.setting_revision:
        raise RiskInputError("stale or cross-scope risk decision")
    return (
        replace(setting, revision=setting.revision + 1, latched=True)
        if evaluation.new_breach and not setting.latched
        else setting
    )


def change_limit(setting: RiskSetting, limit: Money) -> RiskSetting:
    """Change the amount without changing any accounting baseline or breach latch."""
    return RiskSetting(setting.scope, setting.revision + 1, limit, setting.latched)


def rebuild_pair_risk(
    pair: PositionPair,
    slots: tuple[ExecutionFact | None, ...],
    *,
    cutoff: int = 0,
    reset_price: Money | None = None,
) -> PairRiskState:
    """Rebuild effective corrections using the reset's captured source cutoff/price."""
    if type(cutoff) is not int or not 0 <= cutoff <= len(slots):
        raise RiskInputError("reset cutoff outside the complete stream")
    position = rebuild_position(pair, slots[:cutoff]).state
    zero = Money.of(0, "USDT")
    pnl = unrealized_pnl(position, reset_price)
    if pnl is None:
        raise RiskUnavailableError("historical reset price required after correction")
    item = PairRiskState(position, _loss(pnl), zero)
    for sequence, fact in enumerate(slots[cutoff:], start=cutoff + 1):
        if fact is None:
            item = replace(item, position=replace(item.position, last_sequence=sequence))
        else:
            if fact.pair != pair or fact.source_sequence != sequence:
                raise RiskInputError("correction stream has an invalid source slot")
            item = _advance_pair(item, fact)
    return item


@dataclass(frozen=True, slots=True)
class RiskPolicy:
    evaluation: RiskEvaluation
    held: Quantity | None
    reserved: Quantity | None

    def check(self, intent: OrderIntent) -> None:
        scope = self.evaluation.scope
        if (scope.owner_id, scope.mode) != (intent.scope.owner_id, intent.scope.mode) or (
            scope.mode is TradingMode.PAPER and scope.episode_id != intent.scope.episode_id
        ):
            raise OrderConflictError("risk/order scope mismatch")
        if type(self.held) is not Quantity or type(self.reserved) is not Quantity:
            raise RiskUnavailableError("authoritative holdings unavailable")
        if self.held.asset != intent.pair.base or self.reserved.asset != intent.pair.base:
            raise RiskInputError("risk holdings pair mismatch")
        if self.held.amount < 0 or self.reserved.amount < 0 or self.reserved > self.held:
            raise RiskUnavailableError("invalid authoritative reservations")
        reducing = (
            intent.side is ExecutionSide.SELL
            and isinstance(intent.size, BaseSize)
            and not intent.size.quantity > self.held - self.reserved
        )
        if reducing:
            return
        if self.evaluation.latched:
            raise LossLimitReachedError("loss limit remains latched until owner reset")
        if self.evaluation.reason is not RiskReason.READY:
            raise RiskUnavailableError("risk policy is unavailable")


@dataclass(frozen=True, slots=True)
class RiskExecutionContext:
    setting: RiskSetting
    book: RiskBook | None
    prices: tuple[RiskPrice, ...]
    source_ready: bool

    def __post_init__(self) -> None:
        if not isinstance(self.setting, RiskSetting) or type(self.source_ready) is not bool:
            raise RiskInputError("explicit execution risk evidence required")
        if self.book is not None and self.book.scope != self.setting.scope:
            raise RiskInputError("execution risk scope mismatch")
        if self.source_ready and self.book is None:
            raise RiskInputError("ready execution risk requires a complete book")
        _prices(self.prices)
