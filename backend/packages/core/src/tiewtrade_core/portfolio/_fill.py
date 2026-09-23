from decimal import Decimal


def require_positive_fill(quantity: Decimal, price: Decimal) -> None:
    """Reject fills that cannot happen: every fill has a positive quantity and price."""
    if quantity <= 0 or price <= 0:
        raise ValueError("fill quantity and price must be positive")
