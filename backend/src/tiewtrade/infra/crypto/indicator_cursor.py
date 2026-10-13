"""Session-bound signed read cursors; F-11 token lifecycle."""

import base64
import binascii
import hmac
import json
import re
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from tiewtrade.core.indicators import FORMULA_VERSION
from tiewtrade.core.market_data import Timeframe, align_floor
from tiewtrade.infra.crypto.keys import KeyConfigurationError, KeyPurpose, KeySource


class CursorRejectedError(ValueError):
    pass


class DatasetChangedError(ValueError):
    pass


class CursorClaims(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    format_version: Literal[1] = 1
    formula_version: str = FORMULA_VERSION
    dataset_revision: str
    source: str
    base: str
    quote: str
    timeframe: Timeframe
    calculation_start: datetime
    calculation_end: datetime
    as_of: datetime
    result_start: datetime
    result_end: datetime
    next_open_at: datetime
    page_size: int = Field(ge=1, le=1000)
    issued_at: datetime
    expires_at: datetime


class PreparedCursorClaims(CursorClaims):
    format_version: Literal[2] = 2  # type: ignore[assignment]
    generation_id: UUID
    codec_version: Literal[2] = 2
    rollout_epoch: UUID
    dataset_revision: str = Field(pattern=r"^[0-9a-f]{64}$")


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value: str) -> bytes:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise CursorRejectedError()
    result = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
    if _encode(result) != value:
        raise CursorRejectedError()
    return result


def _canonical(claims: CursorClaims) -> bytes:
    data = claims.model_dump(mode="json")
    for name in (
        "calculation_start",
        "calculation_end",
        "as_of",
        "result_start",
        "result_end",
        "next_open_at",
        "issued_at",
        "expires_at",
    ):
        moment = getattr(claims, name)
        if moment.tzinfo is None:
            raise CursorRejectedError()
        data[name] = moment.astimezone(UTC).isoformat(timespec="microseconds")
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def _message(
    signed: str,
    user_id: UUID,
    token_hash: str,
    format_version: int = 1,
    *,
    purpose: Literal["cursor", "chart-display-v1"] = "cursor",
) -> bytes:
    return (
        (
            b"tiewtrade.chart.display.v1\0"
            if purpose == "chart-display-v1"
            else b"tiewtrade.indicator.cursor.v1\0"
            if format_version == 1
            else b"tiewtrade.indicator.cursor.v2\0"
        )
        + signed.encode("ascii")
        + b"\0"
        + str(user_id).encode()
        + b"\0"
        + token_hash.encode()
    )


def validate_keys(keys: KeySource, others: tuple[KeySource, ...]) -> None:
    if keys.purpose is not KeyPurpose.INDICATOR_CURSOR or not 1 <= len(keys._keys) <= 3:
        raise KeyConfigurationError("INDICATOR_CURSOR configuration")
    seen = {key for other in others for key in other._keys.values()}
    for version, key in keys._keys.items():
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", version) or len(key) != 32 or key in seen:
            raise KeyConfigurationError("INDICATOR_CURSOR configuration")
        seen.add(key)


def issue(
    claims: CursorClaims,
    keys: KeySource,
    user_id: UUID,
    token_hash: str,
    *,
    purpose: Literal["cursor", "chart-display-v1"] = "cursor",
) -> str:
    version, key = keys.current()
    signed = version + "." + _encode(_canonical(claims))
    return (
        signed
        + "."
        + _encode(
            hmac.digest(
                key,
                _message(signed, user_id, token_hash, claims.format_version, purpose=purpose),
                "sha256",
            )
        )
    )


def verify(
    raw: str,
    keys: KeySource,
    user_id: UUID,
    token_hash: str,
    *,
    purpose: Literal["cursor", "chart-display-v1"] = "cursor",
) -> CursorClaims:
    try:
        if not raw.isascii() or len(raw) > 4096:
            raise CursorRejectedError()
        version, payload, mac = raw.split(".")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", version):
            raise CursorRejectedError()
        signature, encoded = _decode(mac), _decode(payload)
        if len(signature) != 32:
            raise CursorRejectedError()
        selector = json.loads(encoded)
        if not isinstance(selector, dict) or type(selector.get("format_version")) is not int:
            raise CursorRejectedError()
        format_version = selector["format_version"]
        if format_version not in (1, 2):
            raise CursorRejectedError()
        if format_version == 2 and type(selector.get("codec_version")) is not int:
            raise CursorRejectedError()
        try:
            key = keys.for_version(version)
        except KeyConfigurationError:
            raise DatasetChangedError() from None
        expected = hmac.digest(
            key,
            _message(version + "." + payload, user_id, token_hash, format_version, purpose=purpose),
            "sha256",
        )
        if not hmac.compare_digest(signature, expected):
            raise CursorRejectedError()
        claims = (
            CursorClaims if format_version == 1 else PreparedCursorClaims
        ).model_validate_json(encoded)
        if _canonical(claims) != encoded:
            raise CursorRejectedError()
        for moment in (
            claims.calculation_start,
            claims.calculation_end,
            claims.result_start,
            claims.result_end,
            claims.next_open_at,
        ):
            if moment.tzinfo is None or align_floor(moment, claims.timeframe) != moment:
                raise CursorRejectedError()
        if not (
            claims.calculation_start
            <= claims.result_start
            <= claims.next_open_at
            < claims.result_end
            <= claims.calculation_end
        ):
            raise CursorRejectedError()
        if not claims.issued_at < claims.expires_at <= claims.issued_at + timedelta(hours=6):
            raise CursorRejectedError()
        if claims.formula_version != FORMULA_VERSION:
            raise DatasetChangedError()
        return claims
    except (ValueError, TypeError, ValidationError, binascii.Error) as error:
        if isinstance(error, DatasetChangedError):
            raise
        raise CursorRejectedError() from None


def check_expiry(claims: CursorClaims, now: datetime) -> None:
    if claims.issued_at > now:
        raise CursorRejectedError()
    if now >= claims.expires_at:
        raise DatasetChangedError()
