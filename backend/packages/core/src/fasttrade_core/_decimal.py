"""Decimal arithmetic context for all core calculations (P-07, FR-MRG-08).

Money values can reach NUMERIC(38,18) in the database, which exceeds the
default 28-digit Decimal context. Every public calculation runs inside
``CALC`` so results do not depend on the caller's thread-local context.
Code outside the core that does its own Decimal arithmetic on these values
(services, tests) should run in the same context, exported as
``fasttrade_core.DECIMAL_CONTEXT``.
"""

from collections.abc import Callable
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext
from functools import wraps

CALC = Context(prec=50, rounding=ROUND_HALF_EVEN)

ZERO = Decimal(0)
ONE = Decimal(1)


def calc[**P, R](func: Callable[P, R]) -> Callable[P, R]:
    """Run ``func`` inside the core Decimal context."""

    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        with localcontext(CALC):
            return func(*args, **kwargs)

    return wrapper
