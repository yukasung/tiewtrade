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


def test_decimal_policy_is_shared_by_current_and_future_worker_threads() -> None:
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
        configure_decimal_context()

        default_policy = _decimal_policy(decimal.DefaultContext)
        current_policy = _decimal_policy()
        with ThreadPoolExecutor(max_workers=1) as pool:
            worker_policy = pool.submit(_decimal_policy).result()

        expected_policy = (28, decimal.ROUND_HALF_EVEN, True, True, True, True)
        assert default_policy == expected_policy
        assert current_policy == expected_policy
        assert worker_policy == expected_policy
    finally:
        configure_decimal_context()
