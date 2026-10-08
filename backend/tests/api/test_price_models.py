from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from tiewtrade.services.api.price_models import PriceRow, PricesView


def test_snapshot_prices_are_exact_strings_and_checked_time_is_explicit() -> None:
    now = datetime(2026, 10, 7, tzinfo=UTC)
    row = PriceRow(
        source="primary_spot",
        base="BTC",
        quote="USDT",
        amount="9007199254740993.12345678",
        trade_at=now,
        received_at=now,
        revision="9007199254740994",
        generation="1",
        readiness="READY",
        reason="READY",
        valid_until=now,
        unavailable_since=None,
        alert_due=False,
    )
    view = PricesView(server_time=now, delivery_status="CONNECTED", rows=[row])
    assert view.model_dump(mode="json")["rows"][0]["amount"] == "9007199254740993.12345678"
    assert view.model_dump(mode="json")["server_time"].endswith("Z")
    with pytest.raises(ValidationError):
        PriceRow.model_validate(row.model_dump() | {"amount": 1.2})


@pytest.mark.parametrize(
    "failure", ["SUBSCRIPTION_ACK_TIMEOUT", "VENUE_RATE_LIMITED", "VENUE_PROTOCOL"]
)
def test_snapshot_preserves_current_recovery_failure(failure: str) -> None:
    from uuid import UUID

    from tiewtrade.infra.market_data.realtime_records import FeedLease, PriceSnapshot, StoredPrice
    from tiewtrade.services.api.price_routes import snapshot_view

    now = datetime(2026, 10, 7, tzinfo=UTC)
    feed = FeedLease("primary_spot", 1, UUID(int=1), now, False, failure)
    row = StoredPrice(
        "primary_spot",
        "BTC",
        "USDT",
        reason=failure,
        order_ambiguous_at=now if failure == "VENUE_PROTOCOL" else None,
    )
    view = snapshot_view(PriceSnapshot(feed, (row,), now), delivery_connected=True)
    assert next(r for r in view.rows if r.base == "BTC").reason == failure
