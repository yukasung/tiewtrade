from decimal import Decimal

from fasttrade_core._decimal import calc


@calc
def trading_fee(quantity: Decimal, price: Decimal, fee_rate: Decimal) -> Decimal:
    """Fee = qty * price * rate, in the quote asset (calculation spec §2.8)."""
    return quantity * price * fee_rate


@calc
def funding_payment(quantity: Decimal, mark_price: Decimal, funding_rate: Decimal) -> Decimal:
    """Amount the position pays at a funding time; negative means it receives (§2.9).

    With a positive rate Longs pay and Shorts receive. Subtract the result from the
    wallet balance.
    """
    return quantity * mark_price * funding_rate
