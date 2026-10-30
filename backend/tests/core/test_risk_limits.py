from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tiewtrade.core.money import Money, MoneyError, Quantity
from tiewtrade.core.orders import (
    BaseSize,
    OrderConflictError,
    OrderIntent,
    OrderOrigin,
    OrderScope,
    OrderType,
    QuoteBudget,
    TradingMode,
)
from tiewtrade.core.positions import (
    ExecutionFact,
    ExecutionSide,
    FeeEffect,
    PositionPair,
    PositionSequenceError,
    PositionState,
    apply_execution,
)
from tiewtrade.core.realtime_prices import ObservationKind, QuoteObservation
from tiewtrade.core.risk_limits import (
    LossLimitReachedError,
    PairRiskState,
    RiskBaseline,
    RiskBook,
    RiskEvaluation,
    RiskInputError,
    RiskPolicy,
    RiskPrice,
    RiskReason,
    RiskScope,
    RiskSetting,
    RiskStop,
    RiskStopProgress,
    RiskUnavailableError,
    apply_risk_execution,
    change_limit,
    evaluate_risk,
    initial_risk_book,
    iter_risk_evaluations,
    latch_risk,
    rebuild_pair_risk,
    reset_risk,
)

NOW = datetime(2026, 10, 26, tzinfo=UTC)
PAIR = PositionPair("BTC", "USDT")
ETH = PositionPair("ETH", "USDT")
OWNER = UUID(int=1)
EPISODE = UUID(int=2)
WALLET = UUID(int=3)
SCOPE = RiskScope(OWNER, TradingMode.PAPER, WALLET, EPISODE)


def money(value: str | int) -> Money:
    return Money.of(value, "USDT")


def price(value: str | int, pair: PositionPair = PAIR) -> RiskPrice:
    observation = QuoteObservation(
        "BINANCE_TH",
        pair.base,
        pair.quote,
        money(value),
        1,
        NOW,
        NOW,
        ObservationKind.STREAM,
    )
    return RiskPrice(pair, observation, True, True, NOW + timedelta(seconds=30), 1, 1)


def fact(
    sequence: int,
    side: ExecutionSide,
    quantity: str,
    amount: str,
    *,
    pair: PositionPair = PAIR,
    fee: Money | Quantity | None = None,
) -> ExecutionFact:
    return ExecutionFact(
        UUID(int=sequence),
        pair,
        side,
        Quantity.of(quantity, pair.base),
        money(amount),
        None if fee is None else FeeEffect(fee),
        sequence,
        NOW,
    )


def started(*, scope: RiskScope = SCOPE, quantity: str = "1", cost: str = "1000") -> RiskBook:
    return apply_risk_execution(
        initial_risk_book(scope, (), source_revision=0),
        fact(1, ExecutionSide.BUY, quantity, cost),
        source_revision=1,
    )


def reset_book(book: RiskBook, at: str = "900") -> tuple[RiskSetting, RiskBook]:
    setting, baseline = reset_risk(
        RiskSetting(book.scope, 1, money(100)),
        book,
        (price(at),),
        reset_id=UUID(int=4),
        now=NOW,
        source_ready=True,
    )
    return setting, baseline.book


@pytest.mark.parametrize("limit", ["0", "-1", "0.0000000000000000001"])
def test_limit_rejects_nonpositive_or_unrepresentable_values(limit: str) -> None:
    with pytest.raises((RiskInputError, MoneyError)):
        RiskSetting(SCOPE, 1, money(limit))


@pytest.mark.parametrize("limit", ["0.000000000000000001", "99999999999999999999"])
def test_limit_has_no_extra_business_cap(limit: str) -> None:
    assert RiskSetting(SCOPE, 1, money(limit)).limit == money(limit)


def test_hand_oracle_net_realized_and_losing_open_pairs_only() -> None:
    btc = PositionState(PAIR, Quantity.of(1, "BTC"), money(1030), money(100), 1)
    eth = PositionState(ETH, Quantity.of(1, "ETH"), money(950), money(-80), 1)
    book = initial_risk_book(SCOPE, (btc, eth), source_revision=2)
    result = evaluate_risk(
        RiskSetting(SCOPE, 1, money(10)),
        book,
        (price(1000), price(1000, ETH)),
        now=NOW,
        source_ready=True,
    )
    # +100 -80 -30 = -10. ETH's unrealized +50 does not offset BTC's -30.
    assert result.loss == money(10)
    assert result.new_breach and result.latched
    above = evaluate_risk(
        RiskSetting(SCOPE, 1, money("10.000000000000000001")),
        book,
        (price(1000), price(1000, ETH)),
        now=NOW,
        source_ready=True,
    )
    assert above.loss == money(10) and not above.latched


def test_realized_partial_fill_is_counted_without_waiting_for_full_close() -> None:
    book = apply_risk_execution(
        started(),
        fact(2, ExecutionSide.SELL, ".9", "800"),
        source_revision=2,
    )
    result = evaluate_risk(
        RiskSetting(SCOPE, 1, money(100)),
        book,
        (price(1000),),
        now=NOW,
        source_ready=True,
    )
    assert book.pairs[0].position.held_quantity == Quantity.of(".1", "BTC")
    assert result.loss == money(100) and result.latched


@pytest.mark.parametrize(
    ("sale", "expected"),
    [("870", "-30"), ("930", "0"), ("1020", "20")],
)
def test_reset_exemption_never_creates_realized_profit(sale: str, expected: str) -> None:
    _, book = reset_book(started())
    closed = apply_risk_execution(
        book,
        fact(2, ExecutionSide.SELL, "1", sale),
        source_revision=2,
    )
    # Original -100 is exempt; closing -130/-70/+20 counts -30/0/+20.
    assert closed.pairs[0].adjusted_realized == money(expected)
    assert closed.pairs[0].allowance == money(0)
    assert closed.pairs[0].position.held_quantity == Quantity.of(0, "BTC")


@pytest.mark.parametrize(("mark", "expected"), [("870", "30"), ("930", "0")])
def test_open_position_after_reset_counts_only_additional_loss(mark: str, expected: str) -> None:
    setting, book = reset_book(started())
    result = evaluate_risk(setting, book, (price(mark),), now=NOW, source_ready=True)
    assert result.loss == money(expected)


def test_reset_of_winning_position_does_not_turn_lost_paper_profit_into_loss() -> None:
    setting, book = reset_book(started(cost="900"), at="1000")
    assert book.pairs[0].allowance == money(0)
    marked = evaluate_risk(setting, book, (price(920),), now=NOW, source_ready=True)
    assert marked.loss == money(0)
    closed = apply_risk_execution(
        book,
        fact(2, ExecutionSide.SELL, "1", "920"),
        source_revision=2,
    )
    assert closed.pairs[0].adjusted_realized == money(20)


def test_partial_sale_allocates_allowance_and_unused_portion_expires() -> None:
    _, book = reset_book(started())
    half = apply_risk_execution(
        book,
        fact(2, ExecutionSide.SELL, ".5", "480"),
        source_revision=2,
    )
    # Half's real loss is20, allowance50: remaining30 expires, not transferred.
    assert half.pairs[0].allowance == money(50)
    assert half.pairs[0].adjusted_realized == money(0)
    closed = apply_risk_execution(
        half,
        fact(3, ExecutionSide.SELL, ".5", "400"),
        source_revision=3,
    )
    assert closed.pairs[0].adjusted_realized == money(-50)
    assert closed.pairs[0].allowance == money(0)


def test_partial_loss_then_remaining_close_is_not_double_counted() -> None:
    setting, book = reset_book(started())
    half = apply_risk_execution(
        book,
        fact(2, ExecutionSide.SELL, ".5", "450"),
        source_revision=2,
    )
    marked = evaluate_risk(setting, half, (price(800),), now=NOW, source_ready=True)
    assert marked.loss == money(50)
    closed = apply_risk_execution(
        half,
        fact(3, ExecutionSide.SELL, ".5", "400"),
        source_revision=3,
    )
    after = evaluate_risk(setting, closed, (), now=NOW, source_ready=True)
    assert after.loss == money(50)


def test_buying_more_does_not_add_reset_allowance() -> None:
    setting, book = reset_book(started())
    more = apply_risk_execution(
        book,
        fact(2, ExecutionSide.BUY, "1", "900"),
        source_revision=2,
    )
    assert more.pairs[0].allowance == money(100)
    assert more.pairs[0].position.total_cost == money(1900)
    assert evaluate_risk(setting, more, (price(900),), now=NOW, source_ready=True).loss == money(0)
    assert evaluate_risk(setting, more, (price(850),), now=NOW, source_ready=True).loss == money(
        100
    )


def test_reset_replaces_allowance_and_does_not_accumulate_previous_exemptions() -> None:
    setting, book = reset_book(started())
    again, baseline = reset_risk(
        setting,
        book,
        (price(850),),
        reset_id=UUID(int=5),
        now=NOW,
        source_ready=True,
    )
    assert baseline.book.pairs[0].allowance == money(150)
    assert again.revision == setting.revision + 1
    assert evaluate_risk(
        again, baseline.book, (price(850),), now=NOW, source_ready=True
    ).loss == money(0)


@pytest.mark.parametrize(
    "kind", ["missing", "stale", "disconnected", "lease", "recovery", "future"]
)
def test_price_unavailability_never_falls_back_to_zero(kind: str) -> None:
    quote = price(900)
    quotes: tuple[RiskPrice, ...]
    if kind == "missing":
        quotes = ()
    else:
        if kind == "stale":
            assert quote.observation is not None
            quote = replace(
                quote,
                observation=replace(quote.observation, trade_time=NOW - timedelta(seconds=11)),
            )
        elif kind == "disconnected":
            quote = replace(quote, connected=False)
        elif kind == "lease":
            quote = replace(quote, lease_until=NOW)
        elif kind == "recovery":
            quote = replace(quote, reconciled=False)
        elif kind == "future":
            assert quote.observation is not None
            quote = replace(
                quote, observation=replace(quote.observation, trade_time=NOW + timedelta(seconds=1))
            )
        quotes = (quote,)
    result = evaluate_risk(
        RiskSetting(SCOPE, 1, money(100), True), started(), quotes, now=NOW, source_ready=True
    )
    assert result.loss is None and result.reason is RiskReason.PRICE_UNAVAILABLE
    assert result.latched and not result.new_breach
    with pytest.raises(RiskUnavailableError):
        reset_risk(
            RiskSetting(SCOPE, 1, money(100), True),
            started(),
            quotes,
            reset_id=UUID(int=4),
            now=NOW,
            source_ready=True,
        )


def test_freshness_boundary_is_the_existing_ten_second_rule() -> None:
    quote = price(900)
    assert quote.observation is not None
    quote = replace(
        quote, observation=replace(quote.observation, trade_time=NOW - timedelta(seconds=10))
    )
    assert quote.price_at(NOW) == money(900)
    assert quote.price_at(NOW + timedelta(microseconds=1)) is None


def test_latch_survives_recovery_limit_edit_and_day_change_until_reset() -> None:
    setting = RiskSetting(SCOPE, 1, money(100))
    book = started()
    evaluation = evaluate_risk(setting, book, (price(900),), now=NOW, source_ready=True)
    latched = latch_risk(setting, evaluation)
    edited = change_limit(latched, money(10000))
    recovered = evaluate_risk(edited, book, (price(1100),), now=NOW, source_ready=True)
    assert recovered.loss == money(0) and recovered.latched and not recovered.new_breach
    tomorrow = evaluate_risk(edited, book, (), now=NOW + timedelta(days=1), source_ready=False)
    assert tomorrow.latched and tomorrow.loss is None
    reset, baseline = reset_risk(
        edited, book, (price(900),), reset_id=UUID(int=4), now=NOW, source_ready=True
    )
    assert not reset.latched
    assert evaluate_risk(
        reset, baseline.book, (price(900),), now=NOW, source_ready=True
    ).loss == money(0)
    with pytest.raises(RiskInputError):
        latch_risk(edited, evaluation)


def test_closed_pair_does_not_require_a_price_but_its_realized_loss_is_kept() -> None:
    book = apply_risk_execution(
        started(), fact(2, ExecutionSide.SELL, "1", "900"), source_revision=2
    )
    result = evaluate_risk(RiskSetting(SCOPE, 1, money(100)), book, (), now=NOW, source_ready=True)
    assert result.loss == money(100) and result.latched


def test_unknown_source_is_not_an_empty_or_safe_wallet() -> None:
    book = initial_risk_book(SCOPE, (), source_revision=0)
    result = evaluate_risk(RiskSetting(SCOPE, 1, money(100)), book, (), now=NOW, source_ready=False)
    assert result.loss is None and result.reason is RiskReason.SOURCE_UNAVAILABLE


def intent(side: ExecutionSide, quantity: str = "1", scope: RiskScope = SCOPE) -> OrderIntent:
    return OrderIntent(
        UUID(int=7),
        UUID(int=8),
        OrderScope(scope.owner_id, scope.episode_id or EPISODE, scope.mode),
        PAIR,
        OrderOrigin.MANUAL,
        side,
        OrderType.MARKET,
        BaseSize(Quantity.of(quantity, "BTC"))
        if side is ExecutionSide.SELL
        else QuoteBudget(money(10)),
    )


@pytest.mark.parametrize("source_ready", [True, False])
@pytest.mark.parametrize("latched", [True, False])
def test_bounded_reduction_bypasses_loss_gate_but_oversized_sell_does_not(
    source_ready: bool,
    latched: bool,
) -> None:
    result = evaluate_risk(
        RiskSetting(SCOPE, 1, money(100), latched),
        started(),
        (),
        now=NOW,
        source_ready=source_ready,
    )
    policy = RiskPolicy(result, Quantity.of(1, "BTC"), Quantity.of(".25", "BTC"))
    policy.check(intent(ExecutionSide.SELL, ".75"))
    for order in (intent(ExecutionSide.SELL, ".76"), intent(ExecutionSide.BUY)):
        with pytest.raises((RiskUnavailableError, LossLimitReachedError)):
            policy.check(order)
    with pytest.raises(RiskUnavailableError):
        RiskPolicy(result, None, None).check(intent(ExecutionSide.SELL))


def test_opening_is_permitted_only_for_ready_configured_policy() -> None:
    book = started()
    for limit in (None, money(100)):
        result = evaluate_risk(
            RiskSetting(SCOPE, 1, limit), book, (price(1000),), now=NOW, source_ready=True
        )
        policy = RiskPolicy(result, Quantity.of(1, "BTC"), Quantity.of(0, "BTC"))
        if limit is None:
            with pytest.raises(RiskUnavailableError):
                policy.check(intent(ExecutionSide.BUY))
        else:
            policy.check(intent(ExecutionSide.BUY))


def test_scope_and_reservation_conflicts_cannot_be_treated_as_reductions() -> None:
    result = evaluate_risk(
        RiskSetting(SCOPE, 1, money(100)), started(), (price(1000),), now=NOW, source_ready=True
    )
    policy = RiskPolicy(result, Quantity.of(1, "BTC"), Quantity.of(0, "BTC"))
    for scope in (replace(SCOPE, owner_id=UUID(int=9)), replace(SCOPE, episode_id=UUID(int=9))):
        with pytest.raises(OrderConflictError):
            policy.check(intent(ExecutionSide.SELL, scope=scope))
    with pytest.raises(RiskUnavailableError):
        RiskPolicy(result, Quantity.of(1, "BTC"), Quantity.of(2, "BTC")).check(
            intent(ExecutionSide.SELL)
        )


def test_correction_rebuild_uses_the_reset_price_and_preserves_void_sequence() -> None:
    buy = fact(1, ExecutionSide.BUY, "1", "1000")
    sell = fact(2, ExecutionSide.SELL, ".5", "450")
    final = fact(3, ExecutionSide.SELL, ".5", "400")
    result = rebuild_pair_risk(PAIR, (buy, sell, final), cutoff=1, reset_price=money(900))
    assert result.adjusted_realized == money(-50) and result.allowance == money(0)
    replacement = replace(buy, quote_amount=money(1100))
    # Corrected pre-reset cost1100 means allowance200. The final half loses150,
    # consumes its100 allowance and therefore still counts only50 after reset.
    corrected = rebuild_pair_risk(
        PAIR, (replacement, sell, final), cutoff=1, reset_price=money(900)
    )
    assert corrected.adjusted_realized == money(-50)
    voided = rebuild_pair_risk(PAIR, (buy, None, None), cutoff=1, reset_price=money(900))
    assert voided.position.last_sequence == 3 and voided.allowance == money(100)
    with pytest.raises(RiskUnavailableError):
        rebuild_pair_risk(PAIR, (buy, sell), cutoff=1)


def test_duplicate_reordered_or_stale_events_cannot_change_the_original_book() -> None:
    book = started()
    with pytest.raises(PositionSequenceError):
        apply_risk_execution(book, fact(1, ExecutionSide.BUY, "1", "1000"), source_revision=2)
    with pytest.raises(RiskInputError):
        apply_risk_execution(book, fact(2, ExecutionSide.SELL, "1", "900"), source_revision=1)
    assert book.pairs[0].position.held_quantity == Quantity.of(1, "BTC")
    assert book.pairs[0].allowance == money(0)


@pytest.mark.parametrize(
    "fee", [money(".5"), Quantity.of(".001", "BTC"), Quantity.of(".01", "BNB")]
)
def test_risk_uses_f14_position_effects_including_confirmed_fees(fee: Money | Quantity) -> None:
    buy = fact(1, ExecutionSide.BUY, "1", "1000", fee=fee)
    expected = apply_execution(PositionState.empty(PAIR), buy)
    result = apply_risk_execution(
        initial_risk_book(SCOPE, (), source_revision=0), buy, source_revision=1
    )
    assert result.pairs[0].position == expected.state


@given(cost=st.integers(1, 10**12), drawdown=st.integers(0, 10**9), sale=st.integers(1, 10**12))
def test_exemption_never_creates_profit_and_full_close_consumes_exact_remainder(
    cost: int,
    drawdown: int,
    sale: int,
) -> None:
    loss = min(drawdown, cost - 1)
    _, book = reset_book(started(cost=str(cost)), at=str(cost - loss))
    result = apply_risk_execution(
        book, fact(2, ExecutionSide.SELL, "1", str(sale)), source_revision=2
    )
    # Integer oracle: exemption covers original loss only; it cannot create profit.
    actual_pnl = sale - cost
    expected = actual_pnl if actual_pnl >= 0 else min(0, actual_pnl + loss)
    assert result.pairs[0].adjusted_realized == money(expected)
    assert result.pairs[0].allowance == money(0)


@given(allowance=st.integers(0, 1000), units=st.integers(2, 50), sold=st.integers(1, 49))
def test_partial_allowance_is_conserved_at_the_smallest_money_unit(
    allowance: int,
    units: int,
    sold: int,
) -> None:
    sold = min(sold, units - 1)
    position = PositionState(PAIR, Quantity.of(units, "BTC"), money(10000), money(0), 1)
    exempt = money(f"0.{allowance:018d}")
    book = RiskBook(SCOPE, 1, (PairRiskState(position, exempt, money(0)),))
    half = apply_risk_execution(
        book, fact(2, ExecutionSide.SELL, str(sold), "1"), source_revision=2
    )
    # Integer coefficients at stored scale give a floor allocation, not a float.
    expected_remaining = allowance - allowance * sold // units
    assert half.pairs[0].allowance == money(f"0.{expected_remaining:018d}")
    closed = apply_risk_execution(
        half, fact(3, ExecutionSide.SELL, str(units - sold), "1"), source_revision=3
    )
    assert closed.pairs[0].allowance == money(0)


def test_mode_parity_uses_the_same_accounting_policy_and_reset_implementation() -> None:
    outcomes = []
    for scope in (SCOPE, RiskScope(OWNER, TradingMode.LIVE)):
        setting, book = reset_book(started(scope=scope))
        book = apply_risk_execution(
            book, fact(2, ExecutionSide.SELL, ".5", "450"), source_revision=2
        )
        evaluation = evaluate_risk(setting, book, (price(800),), now=NOW, source_ready=True)
        RiskPolicy(evaluation, Quantity.of(".5", "BTC"), Quantity.of(0, "BTC")).check(
            intent(ExecutionSide.SELL, ".5", scope)
        )
        outcomes.append((book.pairs, evaluation.loss, evaluation.reason, evaluation.latched))
    assert outcomes[0] == outcomes[1]


def test_corrupted_or_ambiguous_snapshots_fail_closed() -> None:
    book = started()
    with pytest.raises(RiskInputError):
        replace(book, pairs=(book.pairs[0], book.pairs[0]))
    with pytest.raises(RiskInputError):
        evaluate_risk(
            RiskSetting(SCOPE, 1, money(100)),
            book,
            (price(900), price(1000)),
            now=NOW,
            source_ready=True,
        )
    with pytest.raises(RiskInputError):
        PairRiskState(book.pairs[0].position, Money.of(1, "THB"), money(0))
    with pytest.raises(RiskInputError):
        RiskBaseline(UUID(int=4), NOW, book, (price(900),))
    with pytest.raises(RiskInputError):
        RiskEvaluation(SCOPE, 1, 1, NOW, RiskReason.READY, None, False, False)
    with pytest.raises(RiskInputError):
        RiskEvaluation(SCOPE, 1, 1, NOW, RiskReason.READY, money(0), True, False)


def test_interleaved_pairs_share_f14_global_source_sequence_without_changing_other_values() -> None:
    book = started()
    book = apply_risk_execution(
        book,
        fact(2, ExecutionSide.BUY, "2", "2000", pair=ETH),
        source_revision=2,
    )
    assert {p.position.last_sequence for p in book.pairs} == {2}
    book = apply_risk_execution(
        book,
        fact(3, ExecutionSide.SELL, ".5", "450"),
        source_revision=3,
    )
    book = apply_risk_execution(
        book,
        fact(4, ExecutionSide.SELL, "1", "1100", pair=ETH),
        source_revision=4,
    )
    btc, eth = book.pairs
    assert btc.position.pair == PAIR and btc.position.held_quantity == Quantity.of(".5", "BTC")
    assert btc.adjusted_realized == money(-50)
    assert eth.position.pair == ETH and eth.adjusted_realized == money(100)
    assert {p.position.last_sequence for p in book.pairs} == {4}
    result = evaluate_risk(
        RiskSetting(SCOPE, 1, money(100)),
        book,
        (price(800), price(1000, ETH)),
        now=NOW,
        source_ready=True,
    )
    assert result.loss == money(50)
    with pytest.raises(RiskInputError):
        replace(book, pairs=(replace(btc, position=replace(btc.position, last_sequence=3)), eth))


@pytest.mark.parametrize(
    ("complete", "pending", "failed", "expected"),
    [
        (False, 0, 0, RiskStopProgress.STOPPING),
        (True, 1, 0, RiskStopProgress.STOPPING),
        (True, 0, 0, RiskStopProgress.STOPPED),
        (True, 1, 1, RiskStopProgress.PROBLEMS),
    ],
)
def test_stop_is_not_complete_until_all_targets_are_known_and_resolved(
    complete: bool,
    pending: int,
    failed: int,
    expected: RiskStopProgress,
) -> None:
    stop = RiskStop(SCOPE, UUID(int=10), 1, 2, pending, failed, complete)
    assert stop.progress is expected
    with pytest.raises(RiskInputError):
        replace(stop, pending_count=0, failed_count=1)


@given(
    st.permutations(
        (
            "60000000000000000000",
            "60000000000000000000",
            "-60000000000000000000",
            "-60000000000000000000",
            "-10",
        )
    )
)
def test_representable_net_loss_does_not_depend_on_aggregate_order(values: list[str]) -> None:
    # Independent integer oracle: the four large terms cancel, leaving -10 realized.
    pairs = tuple(
        PairRiskState(
            PositionState(
                PositionPair(base, "USDT"), Quantity.of(0, base), money(0), money(value), 5
            ),
            money(0),
            money(value),
        )
        for base, value in zip(("AAA", "BBB", "CCC", "DDD", "EEE"), values, strict=True)
    )
    result = evaluate_risk(
        RiskSetting(SCOPE, 1, money(10)), RiskBook(SCOPE, 5, pairs), (), now=NOW, source_ready=True
    )
    assert result.loss == money(10) and result.new_breach


def _assert_replay_parity(
    setting: RiskSetting,
    book: RiskBook,
    frames: tuple[tuple[datetime, tuple[RiskPrice, ...]], ...],
    *,
    source_ready: bool = True,
) -> list[RiskEvaluation]:
    expected = []
    current = setting
    for now, quotes in frames:
        evaluation = evaluate_risk(current, book, quotes, now=now, source_ready=source_ready)
        expected.append(evaluation)
        current = latch_risk(current, evaluation)
    actual = list(iter_risk_evaluations(setting, book, frames, source_ready=source_ready))
    assert actual == expected
    return actual


@pytest.mark.parametrize("source_ready", [True, False])
@pytest.mark.parametrize("limit", [None, "0.000000000000000001", "100", "100.000000000000000001"])
def test_replay_checks_same_amount_readiness_and_preserves_transient_latch(
    source_ready: bool, limit: str | None
) -> None:
    quote = price(900)
    setting = RiskSetting(SCOPE, 1, None if limit is None else money(limit))
    frames = (
        (NOW, (quote,)),
        (NOW, (quote,)),
        (NOW, (replace(quote, connected=False),)),
        (NOW, (replace(quote, reconciled=False, generation=2),)),
        (NOW, (replace(quote, lease_until=NOW),)),
        (NOW + timedelta(seconds=10), (quote,)),
        (NOW + timedelta(seconds=10, microseconds=1), (quote,)),
        (NOW, (replace(quote, generation=3, revision=7),)),
        (NOW, (price(1100),)),
    )
    results = _assert_replay_parity(setting, started(), frames, source_ready=source_ready)
    if source_ready:
        assert results[0].loss == money(100)
        assert all(results[i].loss is None for i in (2, 3, 4, 6))
        assert results[5].loss == money(100) and results[7].loss == money(100)
        assert results[-1].loss == money(0)
        assert sum(result.new_breach for result in results) == int(
            limit is not None and not money(100) < money(limit)
        )


@pytest.mark.parametrize("kind", ["empty", "closed", "mixed", "reset", "partial", "new_owner"])
def test_replay_valuation_isolated_between_books_and_calls(kind: str) -> None:
    book = started()
    if kind == "empty":
        book = initial_risk_book(SCOPE, (), source_revision=0)
    elif kind == "closed":
        book = apply_risk_execution(
            book, fact(2, ExecutionSide.SELL, "1", "950"), source_revision=2
        )
    elif kind == "mixed":
        btc = PositionState(PAIR, Quantity.of(1, "BTC"), money(1030), money(100), 1)
        eth = PositionState(ETH, Quantity.of(1, "ETH"), money(950), money(-80), 1)
        book = initial_risk_book(SCOPE, (btc, eth), source_revision=1)
    elif kind in ("reset", "partial"):
        _, book = reset_book(book)
        if kind == "partial":
            book = apply_risk_execution(
                book, fact(2, ExecutionSide.SELL, ".5", "450"), source_revision=2
            )
    elif kind == "new_owner":
        book = replace(book, scope=replace(SCOPE, owner_id=UUID(int=9)))
    # The prior call may have filled its memo with the same mark and a different loss.
    _assert_replay_parity(RiskSetting(SCOPE, 1, money(100)), started(), ((NOW, (price(900),)),) * 4)
    frames = ((NOW, (price(900), price(1000, ETH))),) * 4 + ((NOW, ()),) * 2
    _assert_replay_parity(RiskSetting(book.scope, 1, money(100)), book, frames)


@given(
    marks=st.lists(
        st.sampled_from(["800", "900", "1000", "1100", "900.000000000000000001"]),
        min_size=1,
        max_size=100,
    ),
    cost=st.integers(min_value=1, max_value=10000),
)
def test_replay_batch_matches_each_single_frame_across_price_changes(
    marks: list[str], cost: int
) -> None:
    book = started(cost=str(cost))
    frames = tuple((NOW, (price(mark),)) for mark in marks)
    _assert_replay_parity(RiskSetting(SCOPE, 1, money(100)), book, frames)


def test_replay_yields_breach_before_rejecting_a_later_bad_frame() -> None:
    quote = price(900)
    setting = RiskSetting(SCOPE, 1, money(100))
    replay = iter_risk_evaluations(
        setting, started(), ((NOW, (quote,)), (NOW, (quote, quote))), source_ready=True
    )
    first = next(replay)
    assert first.new_breach and first.loss == money(100)
    with pytest.raises(RiskInputError, match="duplicate"):
        next(replay)


def test_replay_rejects_changed_scope_and_over_budget() -> None:
    setting = RiskSetting(SCOPE, 1, money(100))
    frames = ((NOW, (price(900),)),)
    with pytest.raises(RiskInputError, match="scope mismatch"):
        list(
            iter_risk_evaluations(
                replace(setting, scope=replace(SCOPE, owner_id=UUID(int=9))),
                started(),
                frames,
                source_ready=True,
            )
        )
    with pytest.raises(RiskInputError, match="bounded"):
        list(iter_risk_evaluations(setting, started(), frames * 101, source_ready=True))


def test_replay_does_not_reuse_a_loss_for_an_overflowing_mark() -> None:
    book = started(quantity="2")
    setting = RiskSetting(SCOPE, 1, money(100))
    valid = (price(900),)
    too_large = (price("99999999999999999999"),)
    replay = iter_risk_evaluations(
        setting, book, ((NOW, valid), (NOW, valid), (NOW, too_large)), source_ready=True
    )
    assert next(replay).loss == money(0)
    assert next(replay).loss == money(0)
    with pytest.raises(MoneyError):
        next(replay)
    with pytest.raises(MoneyError):
        evaluate_risk(setting, book, too_large, now=NOW, source_ready=True)
