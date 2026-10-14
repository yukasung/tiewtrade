from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from tiewtrade.core.market_data import Timeframe
from tiewtrade.infra.crypto.chart_proof import issue_display, verify_display
from tiewtrade.infra.crypto.indicator_cursor import (
    CursorClaims,
    CursorRejectedError,
    DatasetChangedError,
    PreparedCursorClaims,
    check_expiry,
    issue,
    verify,
)
from tiewtrade.infra.crypto.keys import KeyPurpose, KeySource


@pytest.mark.parametrize("prepared", [False, True])
def test_proof_and_cursor_domains_never_interchange(prepared: bool) -> None:
    now = datetime(2026, 10, 12, tzinfo=UTC)
    claims = CursorClaims(
        source="primary_spot",
        base="BTC",
        quote="USDT",
        timeframe=Timeframe.H1,
        dataset_revision="a" * 64,
        as_of=now,
        calculation_start=now - timedelta(days=365),
        calculation_end=now,
        result_start=now - timedelta(hours=1),
        result_end=now,
        next_open_at=now - timedelta(hours=1),
        page_size=1000,
        issued_at=now,
        expires_at=now + timedelta(hours=6),
    )
    if prepared:
        claims = PreparedCursorClaims(
            **claims.model_dump(exclude={"format_version"}),
            generation_id=uuid4(),
            rollout_epoch=uuid4(),
        )
    keys = KeySource(KeyPurpose.INDICATOR_CURSOR, "a", {"a": b"a" * 32})
    user = uuid4()
    proof = issue_display(claims, keys, user, "session")
    cursor = issue(claims, keys, user, "session")
    assert verify_display(proof, keys, user, "session") == claims
    with pytest.raises(CursorRejectedError):
        verify(proof, keys, user, "session")
    with pytest.raises(CursorRejectedError):
        verify_display(cursor, keys, user, "session")
    for wrong_user, wrong_session in ((uuid4(), "session"), (user, "other")):
        with pytest.raises(CursorRejectedError):
            verify_display(proof, keys, wrong_user, wrong_session)
    rotated = KeySource(KeyPurpose.INDICATOR_CURSOR, "b", {"b": b"b" * 32, "a": b"a" * 32})
    assert verify_display(proof, rotated, user, "session") == claims
    for malformed in (" " + proof, proof + " ", proof[:-1] + "!", "a." + "x" * 100_000):
        with pytest.raises(CursorRejectedError) as rejected:
            verify_display(malformed, keys, user, "session")
        assert malformed not in str(rejected.value)
    with pytest.raises(CursorRejectedError):
        verify_display(
            proof, KeySource(KeyPurpose.INDICATOR_CURSOR, "a", {"a": b"b" * 32}), user, "session"
        )
    with pytest.raises(DatasetChangedError):
        verify_display(
            proof, KeySource(KeyPurpose.INDICATOR_CURSOR, "b", {"b": b"b" * 32}), user, "session"
        )
    check_expiry(claims, claims.expires_at - timedelta(microseconds=1))
    with pytest.raises(DatasetChangedError):
        check_expiry(claims, claims.expires_at)
