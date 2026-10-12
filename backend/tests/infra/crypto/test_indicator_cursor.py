from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from tiewtrade.core.market_data import Timeframe
from tiewtrade.infra.crypto.indicator_cursor import (
    CursorClaims,
    CursorRejectedError,
    DatasetChangedError,
    check_expiry,
    issue,
    validate_keys,
    verify,
)
from tiewtrade.infra.crypto.keys import KeyPurpose, KeySource


def test_cursor_roundtrip_binding_expiry_and_rotation() -> None:
    now = datetime(2026, 10, 10, tzinfo=UTC)
    who = uuid4()
    keys = KeySource(KeyPurpose.INDICATOR_CURSOR, "a", {"a": b"a" * 32})
    validate_keys(keys, ())
    claims = CursorClaims(
        source="primary_spot",
        base="BTC",
        quote="USDT",
        timeframe=Timeframe.M1,
        dataset_revision="abc",
        calculation_start=now - timedelta(days=365),
        calculation_end=now,
        result_start=now - timedelta(hours=1),
        result_end=now,
        next_open_at=now - timedelta(hours=1),
        page_size=1000,
        as_of=now,
        issued_at=now,
        expires_at=now + timedelta(hours=6),
    )
    token = issue(claims, keys, who, "test-session-hash")
    assert verify(token, keys, who, "test-session-hash") == claims
    with pytest.raises(CursorRejectedError):
        verify(token, keys, uuid4(), "test-session-hash")
    with pytest.raises(CursorRejectedError):
        verify(token[:-1] + "!", keys, who, "test-session-hash")
    check_expiry(claims, claims.expires_at - timedelta(microseconds=1))
    with pytest.raises(DatasetChangedError):
        check_expiry(claims, claims.expires_at)
    rotated = KeySource(KeyPurpose.INDICATOR_CURSOR, "b", {"b": b"b" * 32, "a": b"a" * 32})
    assert verify(token, rotated, who, "test-session-hash") == claims
    with pytest.raises(DatasetChangedError):
        verify(
            token,
            KeySource(KeyPurpose.INDICATOR_CURSOR, "b", {"b": b"b" * 32}),
            who,
            "test-session-hash",
        )


def test_v2_domain_schema_and_v1_bytes_are_compatible() -> None:
    import base64
    import hmac
    import json

    from tiewtrade.infra.crypto.indicator_cursor import PreparedCursorClaims

    now = datetime(2026, 10, 10, tzinfo=UTC)
    user = uuid4()
    keys = KeySource(KeyPurpose.INDICATOR_CURSOR, "a", {"a": b"a" * 32})
    legacy = CursorClaims(
        source="primary_spot",
        base="BTC",
        quote="USDT",
        timeframe=Timeframe.M1,
        dataset_revision="a" * 64,
        calculation_start=now - timedelta(days=365),
        calculation_end=now,
        as_of=now,
        result_start=now - timedelta(hours=1),
        result_end=now,
        next_open_at=now - timedelta(hours=1),
        page_size=20,
        issued_at=now,
        expires_at=now + timedelta(hours=6),
    )
    data = legacy.model_dump(mode="json")
    for field in (
        "calculation_start",
        "calculation_end",
        "as_of",
        "result_start",
        "result_end",
        "next_open_at",
        "issued_at",
        "expires_at",
    ):
        data[field] = getattr(legacy, field).isoformat(timespec="microseconds")

    def encode(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).decode().rstrip("=")

    payload = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    signed = "a." + encode(payload)
    message = (
        b"tiewtrade.indicator.cursor.v1\0"
        + signed.encode()
        + b"\0"
        + str(user).encode()
        + b"\0session"
    )
    assert issue(legacy, keys, user, "session") == signed + "." + encode(
        hmac.digest(b"a" * 32, message, "sha256")
    )
    prepared = PreparedCursorClaims.model_validate(
        legacy.model_dump()
        | {
            "format_version": 2,
            "generation_id": uuid4(),
            "rollout_epoch": uuid4(),
            "codec_version": 1,
        }
    )
    token = issue(prepared, keys, user, "session")
    assert verify(token, keys, user, "session") == prepared
    with pytest.raises(CursorRejectedError):
        verify(token, keys, user, "other-session")
    kid, body, _ = token.split(".")
    v1_message = (
        b"tiewtrade.indicator.cursor.v1\0"
        + (kid + "." + body).encode()
        + b"\0"
        + str(user).encode()
        + b"\0session"
    )
    wrong_domain = kid + "." + body + "." + encode(hmac.digest(b"a" * 32, v1_message, "sha256"))
    with pytest.raises(CursorRejectedError):
        verify(wrong_domain, keys, user, "session")
    for changed in ({"codec_version": True}, {"format_version": 3}, {"dataset_revision": "bad"}):
        with pytest.raises(CursorRejectedError):
            verify(
                issue(prepared.model_copy(update=changed), keys, user, "session"),
                keys,
                user,
                "session",
            )
