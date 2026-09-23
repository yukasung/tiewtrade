import re
from typing import Final

# Binance accepts a limited alphabet for client order ids; the separator must stay outside
# the portfolio and sequence parts so parsing back is unambiguous.
SEPARATOR: Final = "-"
_PART = re.compile(r"\A[0-9A-Za-z_]+\Z")

# Verify (architecture §4.4): Binance's maximum client order id length is unconfirmed.
# 36 is the documented limit for USDⓈ-M futures at the time of writing; keep the marker
# until a golden test against the venue confirms it.
MAX_LENGTH: Final = 36


def build_client_order_id(prefix: str, portfolio_ref: str, sequence: int) -> str:
    """Build the Client Order ID recorded before an order is sent (architecture §4.4).

    ``prefix`` carries the platform tag and its version (``tt1``) and is supplied by the
    caller rather than hardcoded, because it is deployment configuration and the core
    reads none. ``portfolio_ref`` is a short stable reference to the Portfolio, and
    ``sequence`` is the caller's monotonic counter — the core neither invents ids nor
    reads a clock, so the same inputs always produce the same id (NFR-05).
    """
    if sequence < 0:
        raise ValueError("sequence must not be negative")
    for name, part in (("prefix", prefix), ("portfolio_ref", portfolio_ref)):
        if not _PART.match(part):
            raise ValueError(f"{name} must be non-empty and alphanumeric or underscore")
    candidate = f"{prefix}{SEPARATOR}{portfolio_ref}{SEPARATOR}{sequence}"
    if len(candidate) > MAX_LENGTH:
        raise ValueError(f"client order id exceeds {MAX_LENGTH} characters")
    return candidate


def is_platform_client_order_id(client_order_id: str, prefix: str) -> bool:
    """Whether the venue reported an order this platform created (D-14).

    An order whose id does not match the platform's shape was placed by the user on
    Binance directly and is recorded with ``OwnerType.EXTERNAL`` (FR-LIVE-06). Matching is
    deliberately structural rather than a bare ``startswith``: a user order that happens to
    begin with the same letters must not be mistaken for one of ours.
    """
    head = f"{prefix}{SEPARATOR}"
    if not client_order_id.startswith(head):
        return False
    rest = client_order_id[len(head) :]
    portfolio_ref, separator, sequence = rest.partition(SEPARATOR)
    if not separator:
        return False
    return bool(_PART.match(portfolio_ref)) and sequence.isdigit()
