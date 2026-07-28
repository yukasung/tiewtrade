import decimal
from concurrent.futures import ThreadPoolExecutor

from tiewtrade.decimal_context import configure_decimal_context


def _decimal_policy(
    context: decimal.Context | None = None,
) -> tuple[int, str, bool, bool, bool, bool]:
    context = context or decimal.getcontext()
    return (
        context.prec,
        context.rounding,
        context.traps[decimal.InvalidOperation],
        context.traps[decimal.DivisionByZero],
        context.traps[decimal.Overflow],
        not any(context.flags.values()),
    )


def _restore_context(target: decimal.Context, snapshot: decimal.Context) -> None:
    target.prec = snapshot.prec
    target.rounding = snapshot.rounding
    target.Emin = snapshot.Emin
    target.Emax = snapshot.Emax
    target.capitals = snapshot.capitals
    target.clamp = snapshot.clamp
    for signal, enabled in snapshot.traps.items():
        target.traps[signal] = enabled
    for signal, raised in snapshot.flags.items():
        target.flags[signal] = raised


def test_decimal_policy_is_shared_by_current_and_future_worker_threads() -> None:
    original_default = decimal.DefaultContext.copy()
    original_current = decimal.getcontext().copy()

    decimal.DefaultContext.prec = 7
    decimal.DefaultContext.rounding = decimal.ROUND_DOWN
    decimal.DefaultContext.traps[decimal.InvalidOperation] = False
    decimal.DefaultContext.traps[decimal.DivisionByZero] = False
    decimal.DefaultContext.traps[decimal.Overflow] = False
    decimal.DefaultContext.flags[decimal.Inexact] = True

    current_context = decimal.Context(prec=9, rounding=decimal.ROUND_UP)
    current_context.traps[decimal.InvalidOperation] = False
    current_context.traps[decimal.DivisionByZero] = False
    current_context.traps[decimal.Overflow] = False
    current_context.flags[decimal.Rounded] = True
    decimal.setcontext(current_context)

    try:
        configure_decimal_context()
        first_default_policy = _decimal_policy(decimal.DefaultContext)
        first_current_policy = _decimal_policy()

        expected_policy = (28, decimal.ROUND_HALF_EVEN, True, True, True, True)
        assert first_default_policy == expected_policy
        assert first_current_policy == expected_policy

        configure_decimal_context()
        second_default_policy = _decimal_policy(decimal.DefaultContext)
        second_current_policy = _decimal_policy()

        assert second_default_policy == first_default_policy
        assert second_current_policy == first_current_policy

        with ThreadPoolExecutor(max_workers=1) as pool:
            worker_policy = pool.submit(_decimal_policy).result()

        assert worker_policy == expected_policy
    finally:
        _restore_context(decimal.DefaultContext, original_default)
        decimal.setcontext(original_current)
