import decimal
from concurrent.futures import ThreadPoolExecutor

from tiewtrade.decimal_context import configure_decimal_context


def _decimal_policy() -> tuple[int, str, bool, bool, bool]:
    context = decimal.getcontext()
    return (
        context.prec,
        context.rounding,
        context.traps[decimal.InvalidOperation],
        context.traps[decimal.DivisionByZero],
        context.traps[decimal.Overflow],
    )


def test_decimal_policy_is_shared_by_current_and_future_worker_threads() -> None:
    decimal.setcontext(decimal.Context(prec=7, rounding=decimal.ROUND_DOWN))

    configure_decimal_context()

    main_policy = _decimal_policy()
    with ThreadPoolExecutor(max_workers=1) as pool:
        worker_policy = pool.submit(_decimal_policy).result()

    assert main_policy == (28, decimal.ROUND_HALF_EVEN, True, True, True)
    assert worker_policy == main_policy
