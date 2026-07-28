import decimal


def configure_decimal_context() -> None:
    decimal.DefaultContext.prec = 28
    decimal.DefaultContext.rounding = decimal.ROUND_HALF_EVEN
    decimal.DefaultContext.traps[decimal.InvalidOperation] = True
    decimal.DefaultContext.traps[decimal.DivisionByZero] = True
    decimal.DefaultContext.traps[decimal.Overflow] = True
    decimal.DefaultContext.clear_flags()
    decimal.setcontext(decimal.DefaultContext)
