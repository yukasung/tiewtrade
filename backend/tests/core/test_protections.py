from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.orders import OrderConflictError, OrderOrigin, OrderScope, TradingMode
from tiewtrade.core.positions import PositionPair
from tiewtrade.core.protections import (
    EntryAllocationEvidence,
    ManualSaleAllocation,
    Protection,
    ProtectionError,
    ProtectionLeg,
    ProtectionPrices,
    ProtectionState,
    SetupAction,
    SetupOutcome,
    TriggerEvidence,
    available_quantity,
    cancel_protection,
    decide_setup_result,
    evaluate_trigger,
    prepare_manual_sale,
    replace_protection,
)

NOW = datetime(2026, 11, 4, tzinfo=UTC)
PAIR = PositionPair("BTC", "USDT")


def protection(mode: TradingMode = TradingMode.PAPER) -> Protection:
    return Protection(
        UUID(int=1),
        OrderScope(UUID(int=2), UUID(int=3), mode),
        OrderOrigin.MANUAL,
        ProtectionPrices(PAIR, Money.of("110", "USDT"), Money.of("90", "USDT")),
        Quantity.of("1", "BTC"),
        ProtectionState.ARMED,
    )


def evidence(price: str) -> TriggerEvidence:
    return TriggerEvidence(UUID(int=4), 1, 1, Money.of(price, "USDT"), NOW, NOW, PAIR)


@pytest.mark.parametrize(
    ("price", "leg"),
    [
        ("109.99", None),
        ("110", ProtectionLeg.TAKE_PROFIT),
        ("120", ProtectionLeg.TAKE_PROFIT),
        ("90.01", None),
        ("90", ProtectionLeg.STOP_LOSS),
        ("80", ProtectionLeg.STOP_LOSS),
    ],
)
def test_trigger_boundaries_and_gaps(price: str, leg: ProtectionLeg | None) -> None:
    before = protection()
    after = evaluate_trigger(before, evidence(price), market_ready=True, authoritative_ready=True)
    assert after.winning_leg is leg
    assert after.state is (ProtectionState.ARMED if leg is None else ProtectionState.EXITING)
    assert after.quantity == before.quantity
    if leg is not None:
        assert (
            evaluate_trigger(after, evidence("80"), market_ready=True, authoritative_ready=True)
            is after
        )


@pytest.mark.parametrize("market_ready,authoritative_ready", [(False, True), (True, False)])
def test_unready_never_triggers(market_ready: bool, authoritative_ready: bool) -> None:
    before = protection()
    assert (
        evaluate_trigger(
            before,
            evidence("120"),
            market_ready=market_ready,
            authoritative_ready=authoritative_ready,
        )
        is before
    )


def test_conflict_preserves_allocations_and_blocks_trigger() -> None:
    before = replace(protection(), conflicted=True)
    assert (
        evaluate_trigger(before, evidence("120"), market_ready=True, authoritative_ready=True)
        is before
    )
    with pytest.raises(OrderConflictError):
        available_quantity(
            held=Quantity.of("0.8", "BTC"),
            reserved=Quantity.of("0", "BTC"),
            allocations=(Quantity.of("0.6", "BTC"), Quantity.of("0.4", "BTC")),
        )


@given(held=st.integers(min_value=0, max_value=100000), data=st.data())
def test_allocation_conservation(held: int, data: st.DataObject) -> None:
    reserved = data.draw(st.integers(min_value=0, max_value=held))
    allocated = data.draw(st.integers(min_value=0, max_value=held - reserved))
    result = available_quantity(
        held=Quantity.of(held, "BTC"),
        reserved=Quantity.of(reserved, "BTC"),
        allocations=(Quantity.of(allocated, "BTC"),),
    )
    assert result + Quantity.of(reserved, "BTC") + Quantity.of(allocated, "BTC") == Quantity.of(
        held, "BTC"
    )


def test_creation_requires_untriggered_levels_but_existing_bracket_can_trigger() -> None:
    before = replace(protection(), state=ProtectionState.ARMING, entry_order_id=UUID(int=5))
    with pytest.raises(ProtectionError):
        before.prices.validate_creation(Money.of("110", "USDT"))
    assert (
        evaluate_trigger(before, evidence("120"), market_ready=True, authoritative_ready=True).state
        is ProtectionState.EXITING
    )


@pytest.mark.parametrize("tp,sl", [(None, "90"), ("110", None)])
def test_single_leg(tp: str | None, sl: str | None) -> None:
    prices = ProtectionPrices(
        PAIR,
        None if tp is None else Money.of(tp, "USDT"),
        None if sl is None else Money.of(sl, "USDT"),
    )
    prices.validate_creation(Money.of("100", "USDT"))
    assert prices.triggered_leg(Money.of("120" if tp else "80", "USDT")) is not None


def test_explicit_repair_requires_authority_and_revision() -> None:
    before = replace(protection(), conflicted=True)

    def repair(revision: int, ready: bool) -> Protection:
        return replace_protection(
            before,
            expected_revision=revision,
            prices=before.prices,
            quantity=Quantity.of("0.4", "BTC"),
            current_price=Money.of("100", "USDT"),
            available_including_current=Quantity.of("0.4", "BTC"),
            authoritative_ready=ready,
        )

    with pytest.raises(OrderConflictError):
        repair(2, True)
    with pytest.raises(ProtectionError):
        repair(1, False)
    after = repair(1, True)
    assert not after.conflicted
    assert after.quantity == Quantity.of("0.4", "BTC")
    assert after.state is ProtectionState.ARMING
    assert before.quantity == Quantity.of("1", "BTC")


def test_exit_cannot_be_canceled_as_protection() -> None:
    exiting = evaluate_trigger(
        protection(), evidence("110"), market_ready=True, authoritative_ready=True
    )
    with pytest.raises(ProtectionError):
        cancel_protection(exiting, expected_revision=exiting.revision)


@pytest.mark.parametrize("attempt,seconds", [(1, 1), (2, 2), (3, 4)])
def test_retry_schedule(attempt: int, seconds: int) -> None:
    decision = decide_setup_result(
        origin=OrderOrigin.MANUAL,
        attempt=attempt,
        outcome=SetupOutcome.TRANSIENT_FAILURE,
        observed_at=NOW,
    )
    assert decision.action is SetupAction.RETRY
    assert decision.next_attempt == attempt + 1
    assert decision.due_at == NOW + timedelta(seconds=seconds)


@pytest.mark.parametrize("origin", list(OrderOrigin))
@pytest.mark.parametrize("attempt", [1, 2, 3, 4])
def test_unknown_does_not_consume_a_retry(origin: OrderOrigin, attempt: int) -> None:
    result = decide_setup_result(
        origin=origin, attempt=attempt, outcome=SetupOutcome.UNKNOWN, observed_at=NOW
    )
    assert result.action is SetupAction.RECONCILE
    assert result.next_attempt is None and result.due_at is None


@pytest.mark.parametrize("origin", list(OrderOrigin))
@pytest.mark.parametrize(
    "outcome,attempt",
    [(SetupOutcome.PERMANENT_FAILURE, 1), (SetupOutcome.TRANSIENT_FAILURE, 4)],
)
def test_failure_policy(origin: OrderOrigin, outcome: SetupOutcome, attempt: int) -> None:
    result = decide_setup_result(origin=origin, attempt=attempt, outcome=outcome, observed_at=NOW)
    assert result.action is (
        SetupAction.NOTIFY_UNPROTECTED
        if origin is OrderOrigin.MANUAL
        else SetupAction.CLOSE_AND_STOP
    )


def test_paper_live_share_trigger_decisions() -> None:
    results = [
        evaluate_trigger(
            protection(mode), evidence("110"), market_ready=True, authoritative_ready=True
        )
        for mode in TradingMode
    ]
    assert results[0].winning_leg is results[1].winning_leg
    assert results[0].quantity == results[1].quantity
    assert results[0].trigger == results[1].trigger


def sale_preview(
    before: Protection,
    *,
    sell: str = "0.4",
    selected: str = "0.4",
    held: str = "1",
    revision: int = 1,
) -> Protection:
    result = prepare_manual_sale(
        scope=before.scope,
        pair=PAIR,
        quantity=Quantity.of(sell, "BTC"),
        held=Quantity.of(held, "BTC"),
        reserved=Quantity.of("0", "BTC"),
        protections=(before,),
        selections=(
            ManualSaleAllocation(before.protection_id, revision, Quantity.of(selected, "BTC")),
        ),
        authoritative_ready=True,
    )
    return result[0]


def test_manual_sale_a_does_not_restore_after_partial_cancel() -> None:
    before = protection()
    after = sale_preview(before)
    assert before.quantity == Quantity.of("1", "BTC")  # Pure preview; rollback can discard it.
    assert after.quantity == Quantity.of("0.6", "BTC")
    assert after.state is ProtectionState.ARMED
    # Accepted 0.4 reservation -> filled 0.1 -> confirmed cancel of 0.3.
    # Only the order reservation is released. The protection revision is unchanged.
    assert available_quantity(
        held=Quantity.of("0.9", "BTC"),
        reserved=Quantity.of("0.3", "BTC"),
        allocations=(after.quantity,),
    ) == Quantity.of("0", "BTC")
    assert available_quantity(
        held=Quantity.of("0.9", "BTC"),
        reserved=Quantity.of("0", "BTC"),
        allocations=(after.quantity,),
    ) == Quantity.of("0.3", "BTC")
    assert after.quantity == Quantity.of("0.6", "BTC")


def test_manual_sale_a_full_release_cancels_selected_protection() -> None:
    before = protection()
    after = sale_preview(before, sell="1", selected="1")
    assert after.state is ProtectionState.CANCELED
    assert after.quantity == Quantity.of("0", "BTC")
    assert (
        evaluate_trigger(after, evidence("80"), market_ready=True, authoritative_ready=True)
        is after
    )


def test_manual_sale_preserves_other_group_and_stale_retry_cannot_reduce_twice() -> None:
    first = replace(protection(), quantity=Quantity.of("0.6", "BTC"))
    second = replace(protection(), protection_id=UUID(int=6), quantity=Quantity.of("0.4", "BTC"))
    selection = ManualSaleAllocation(first.protection_id, 1, Quantity.of("0.2", "BTC"))
    after = prepare_manual_sale(
        scope=first.scope,
        pair=PAIR,
        quantity=Quantity.of("0.2", "BTC"),
        held=Quantity.of("1", "BTC"),
        reserved=Quantity.of("0", "BTC"),
        protections=(first, second),
        selections=(selection,),
        authoritative_ready=True,
    )
    assert after[1] is second
    assert after[0].quantity == Quantity.of("0.4", "BTC")
    with pytest.raises(OrderConflictError):
        prepare_manual_sale(
            scope=first.scope,
            pair=PAIR,
            quantity=Quantity.of("0.2", "BTC"),
            held=Quantity.of("1", "BTC"),
            reserved=Quantity.of("0.2", "BTC"),
            protections=after,
            selections=(selection,),
            authoritative_ready=True,
        )


def test_manual_sale_uses_unprotected_quantity_first() -> None:
    before = replace(protection(), quantity=Quantity.of("0.8", "BTC"))
    after = sale_preview(before, sell="0.4", selected="0.2")
    assert after.quantity == Quantity.of("0.6", "BTC")
    with pytest.raises(ProtectionError):
        sale_preview(before, sell="0.4", selected="0.4")


@pytest.mark.parametrize("selected", ["0.3", "0.5", "1.1"])
def test_manual_sale_rejects_inexact_or_excess_selection(selected: str) -> None:
    with pytest.raises(ProtectionError):
        sale_preview(protection(), selected=selected)


@pytest.mark.parametrize("conflicted", [True, False])
def test_manual_sale_cannot_take_conflicted_or_exiting_allocation(conflicted: bool) -> None:
    before = protection()
    unavailable = (
        replace(before, conflicted=True)
        if conflicted
        else evaluate_trigger(before, evidence("110"), market_ready=True, authoritative_ready=True)
    )
    with pytest.raises(OrderConflictError):
        sale_preview(unavailable)


def test_manual_sale_rejects_duplicate_and_cross_owner_selections() -> None:
    before = protection()
    selection = ManualSaleAllocation(before.protection_id, 1, Quantity.of("0.2", "BTC"))
    for scope, selections in (
        (before.scope, (selection, selection)),
        (replace(before.scope, owner_id=UUID(int=8)), (selection,)),
    ):
        with pytest.raises(OrderConflictError):
            prepare_manual_sale(
                scope=scope,
                pair=PAIR,
                quantity=Quantity.of("0.4", "BTC"),
                held=Quantity.of("1", "BTC"),
                reserved=Quantity.of("0", "BTC"),
                protections=(before,),
                selections=selections,
                authoritative_ready=True,
            )


def test_another_usdt_pair_cannot_trigger_btc_protection() -> None:
    wrong = replace(evidence("120"), pair=PositionPair("ETH", "USDT"))
    with pytest.raises(ProtectionError, match="another pair"):
        evaluate_trigger(protection(), wrong, market_ready=True, authoritative_ready=True)
    triggered = evaluate_trigger(
        protection(), evidence("120"), market_ready=True, authoritative_ready=True
    )
    with pytest.raises(ProtectionError, match="pair differs"):
        replace(triggered, trigger=wrong)


@pytest.mark.parametrize("amount", ["0.40000001", "1"])
def test_bracket_replacement_is_capped_by_its_own_remaining_net_entry(amount: str) -> None:
    before = replace(protection(), quantity=Quantity.of("0.4", "BTC"), entry_order_id=UUID(int=5))
    proof = EntryAllocationEvidence(before.scope, PAIR, UUID(int=5), before.quantity, 10)
    with pytest.raises(ProtectionError, match="remaining entry"):
        replace_protection(
            before,
            expected_revision=1,
            prices=before.prices,
            quantity=Quantity.of(amount, "BTC"),
            current_price=Money.of("100", "USDT"),
            available_including_current=Quantity.of("2", "BTC"),
            authoritative_ready=True,
            entry_evidence=proof,
        )


@pytest.mark.parametrize("wrong", ["missing", "owner", "entry", "pair"])
def test_bracket_replacement_requires_bound_entry_evidence(wrong: str) -> None:
    before = replace(protection(), quantity=Quantity.of("0.4", "BTC"), entry_order_id=UUID(int=5))
    proof = EntryAllocationEvidence(before.scope, PAIR, UUID(int=5), before.quantity, 10)
    if wrong == "owner":
        proof = replace(proof, scope=replace(proof.scope, owner_id=UUID(int=9)))
    elif wrong == "entry":
        proof = replace(proof, entry_order_id=UUID(int=9))
    elif wrong == "pair":
        proof = replace(proof, pair=PositionPair("BTC", "THB"))
    with pytest.raises(ProtectionError, match="remaining entry"):
        replace_protection(
            before,
            expected_revision=1,
            prices=before.prices,
            quantity=before.quantity,
            current_price=Money.of("100", "USDT"),
            available_including_current=Quantity.of("2", "BTC"),
            authoritative_ready=True,
            entry_evidence=None if wrong == "missing" else proof,
        )


def test_bracket_replacement_with_valid_entry_proof() -> None:
    before = replace(protection(), quantity=Quantity.of("0.4", "BTC"), entry_order_id=UUID(int=5))
    after = replace_protection(
        before,
        expected_revision=1,
        prices=before.prices,
        quantity=Quantity.of("0.3", "BTC"),
        current_price=Money.of("100", "USDT"),
        available_including_current=Quantity.of("2", "BTC"),
        authoritative_ready=True,
        entry_evidence=EntryAllocationEvidence(
            before.scope, PAIR, UUID(int=5), before.quantity, 10
        ),
    )
    assert after.quantity == Quantity.of("0.3", "BTC")


@pytest.mark.parametrize("state", [ProtectionState.CANCELED, ProtectionState.CLOSED])
def test_terminal_protection_cannot_keep_active_quantity(state: ProtectionState) -> None:
    before = protection()
    if state is ProtectionState.CLOSED:
        before = evaluate_trigger(
            before, evidence("120"), market_ready=True, authoritative_ready=True
        )
    with pytest.raises(ProtectionError, match="terminal protection"):
        replace(before, state=state)
    assert replace(before, state=state, quantity=Quantity.of(0, "BTC")).quantity.amount == 0


@given(
    a=st.integers(min_value=1, max_value=10**12),
    b=st.integers(min_value=0, max_value=10**12),
    c=st.integers(min_value=1, max_value=10**12),
    data=st.data(),
)
def test_manual_sale_preserves_smallest_stored_quantum(
    a: int, b: int, c: int, data: st.DataObject
) -> None:
    def q(coefficient: int) -> Quantity:
        return Quantity.of(f"0.{coefficient:018d}", "BTC")

    selected = data.draw(st.integers(min_value=1, max_value=a))
    before = replace(protection(), quantity=q(a))
    after = prepare_manual_sale(
        scope=before.scope,
        pair=PAIR,
        quantity=q(c + selected),
        held=q(a + b + c),
        reserved=q(b),
        protections=(before,),
        selections=(ManualSaleAllocation(before.protection_id, 1, q(selected)),),
        authoritative_ready=True,
    )[0]
    assert after.quantity == q(a - selected)
    assert available_quantity(
        held=q(a + b + c), reserved=q(b + c + selected), allocations=(after.quantity,)
    ) == q(0)


@pytest.mark.parametrize("quantity", ["0.000999", "0.000001"])
def test_setup_rejects_net_quantity_whose_aligned_portion_is_too_small(quantity: str) -> None:
    from tiewtrade.core.orders import OrderConstraintError, OrderConstraints
    from tiewtrade.core.protections import validate_setup

    constraints = OrderConstraints(
        PAIR,
        "fixture",
        Quantity.of("0.001", "BTC"),
        Quantity.of("0.001", "BTC"),
        Money.of("0.01", "USDT"),
        Money.of("5", "USDT"),
    )
    before = replace(protection(), quantity=Quantity.of(quantity, "BTC"))
    with pytest.raises(OrderConstraintError):
        validate_setup(before, constraints, evidence("100"))
    assert before.quantity == Quantity.of(quantity, "BTC")


def test_paper_live_share_replace_sale_cancel_and_trigger_lifecycle() -> None:
    traces = []
    for mode in TradingMode:
        before = protection(mode)
        resized = replace_protection(
            before,
            expected_revision=1,
            prices=ProtectionPrices(PAIR, Money.of("120", "USDT"), Money.of("80", "USDT")),
            quantity=Quantity.of("0.6", "BTC"),
            current_price=Money.of("100", "USDT"),
            available_including_current=Quantity.of("1", "BTC"),
            authoritative_ready=True,
        )
        # Sell0.6 uses0.4 unprotected plus the explicitly selected0.2.
        reduced = prepare_manual_sale(
            scope=before.scope,
            pair=PAIR,
            quantity=Quantity.of("0.6", "BTC"),
            held=Quantity.of("1", "BTC"),
            reserved=Quantity.of(0, "BTC"),
            protections=(resized,),
            selections=(ManualSaleAllocation(resized.protection_id, 2, Quantity.of("0.2", "BTC")),),
            authoritative_ready=True,
        )[0]
        canceled = cancel_protection(reduced, expected_revision=3)
        triggered = evaluate_trigger(
            reduced, evidence("120"), market_ready=True, authoritative_ready=True
        )
        assert resized.quantity == Quantity.of("0.6", "BTC") and resized.revision == 2
        assert reduced.quantity == Quantity.of("0.4", "BTC") and reduced.revision == 3
        assert canceled.state is ProtectionState.CANCELED
        assert canceled.quantity == Quantity.of(0, "BTC") and canceled.revision == 4
        assert triggered.state is ProtectionState.EXITING and triggered.revision == 4
        assert triggered.quantity == Quantity.of("0.4", "BTC")
        assert triggered.winning_leg is ProtectionLeg.TAKE_PROFIT
        assert (
            evaluate_trigger(triggered, evidence("80"), market_ready=True, authoritative_ready=True)
            is triggered
        )
        with pytest.raises(OrderConflictError):
            cancel_protection(reduced, expected_revision=2)
        assert all(value.scope.mode is mode for value in (resized, reduced, canceled, triggered))
        # Mode is the only permitted difference; identities and financial facts agree.
        traces.append(
            tuple(
                replace(value, scope=protection().scope)
                for value in (resized, reduced, canceled, triggered)
            )
        )
    assert traces[0] == traces[1]


@pytest.mark.parametrize("tp,sl", [("100", None), ("99", None), (None, "100"), (None, "101")])
def test_standalone_creation_refuses_already_crossed_or_equal_levels(
    tp: str | None, sl: str | None
) -> None:
    prices = ProtectionPrices(
        PAIR,
        None if tp is None else Money.of(tp, "USDT"),
        None if sl is None else Money.of(sl, "USDT"),
    )
    with pytest.raises(ProtectionError):
        prices.validate_creation(Money.of("100", "USDT"))


@pytest.mark.parametrize("mode", [TradingMode.PAPER, TradingMode.LIVE])
@pytest.mark.parametrize(
    "amount,expected,residual",
    [
        ("0.00131868", "0.00131", "0.00000868"),
        ("0.00131", "0.00131", "0"),
        ("0.001319999999999999", "0.00131", "0.000009999999999999"),
    ],
)
def test_net_fee_protection_preserves_allocation_and_exposes_step_residual(
    mode: TradingMode, amount: str, expected: str, residual: str
) -> None:
    from tiewtrade.core.orders import OrderConstraints
    from tiewtrade.core.protections import executable_protection_quantity, validate_setup

    constraints = OrderConstraints(
        PAIR,
        "fixture",
        Quantity.of("0.00001", "BTC"),
        Quantity.of("0.00001", "BTC"),
        Money.of("5", "USDT"),
        Money.of("0.01", "USDT"),
    )
    before = replace(protection(mode), quantity=Quantity.of(amount, "BTC"))
    actual = executable_protection_quantity(before, constraints, evidence("75000"))
    assert actual == Quantity.of(expected, "BTC")
    assert before.quantity - actual == Quantity.of(residual, "BTC")
    assert not before.quantity < actual
    assert actual.is_multiple_of(constraints.quantity_step)
    validate_setup(before, constraints, evidence("75000"))
    assert before.quantity == Quantity.of(amount, "BTC")


def test_aligned_protection_still_enforces_minimum_notional() -> None:
    from tiewtrade.core.orders import OrderConstraintError, OrderConstraints
    from tiewtrade.core.protections import executable_protection_quantity

    constraints = OrderConstraints(
        PAIR,
        "fixture",
        Quantity.of("0.00001", "BTC"),
        Quantity.of("0.00001", "BTC"),
        Money.of("5", "USDT"),
        Money.of("0.01", "USDT"),
    )
    before = replace(protection(), quantity=Quantity.of("0.000019", "BTC"))
    with pytest.raises(OrderConstraintError):
        executable_protection_quantity(before, constraints, evidence("100"))
