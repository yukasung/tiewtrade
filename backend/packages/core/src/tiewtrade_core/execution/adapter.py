from typing import Protocol, runtime_checkable

from tiewtrade_core.orders.order import Order


@runtime_checkable
class ExecutionAdapter(Protocol):
    """The single port through which orders reach a venue (FR-ORD-04, architecture §4.2-4.3).

    This is what lets Paper and Live share the Trading Core: the core talks to this port
    and never learns which side of P-03/P-04 it is on. ``PaperExecutionAdapter`` implements
    it with the Fill Model in ``tiewtrade_core.execution``; ``BinanceExecutionAdapter``
    implements it in the engine and forwards a command to the ``execution`` service, which
    is the only place an API secret is ever decrypted (P-10).

    Neither method returns a result. An order's outcome comes back asynchronously as an
    execution report the engine applies with ``Order.apply_fill``, ``Order.accept`` or
    ``Order.reject`` — a venue can reject, partially fill or fill long after the call
    returns, so a return value could only ever be a half-truth.

    Implementations are addressed by ``client_order_id`` rather than by the exchange's id
    because the platform assigns it before sending: after a timeout the order may exist at
    the venue without the platform knowing its exchange id, and the recorded Client Order
    ID is what makes the state recoverable instead of retried blindly (NFR-05, FR-LIVE-07).
    """

    def submit(self, order: Order) -> None:
        """Send an order the venue has not seen yet.

        The caller guarantees the order is ``PENDING_NEW``; an implementation may reject
        anything else but owes no policy beyond that. Deciding whether an order should be
        sent at all — including resolving an uncertain state after a timeout by querying
        the Client Order ID before retrying — belongs to the Order Manager, which owns the
        lifecycle and idempotency (FR-ORD-03, FR-LIVE-07).

        That split matters because the two venues cannot answer the question the same way.
        Under Paper the platform's record *is* the venue, so the order's status settles it;
        against Binance it does not, and inferring from the record is exactly what causes a
        duplicate order (R-06). One rule at one level, implemented once.

        Every outcome arrives as an ``ExecutionReport``, so a submission that produces no
        report is a programming error rather than a silent success.
        """
        ...

    def cancel(self, client_order_id: str) -> None:
        """Ask the venue to cancel an order. Cancelling an order that is already gone is
        not an error: the execution report decides the final status."""
        ...
