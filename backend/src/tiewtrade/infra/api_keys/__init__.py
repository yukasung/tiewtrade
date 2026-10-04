"""API key ของผู้ใช้ — ที่เก็บ สถานะ และเพดาน (F-07)

**ของสาธารณะของชั้นนี้อยู่ที่นี่ที่เดียว** ตามแบบแผนของ `infra/crypto` และ `infra/auth`
"""

from tiewtrade.infra.api_keys.records import (
    MAX_KEYS_PER_USER,
    PUBLIC_TAIL_LENGTH,
    ApiKeyError,
    ApiKeyStatus,
    ApiKeySummary,
    TooManyKeysError,
    public_tail,
)
from tiewtrade.infra.api_keys.storage import (
    RetryOutcome,
    delete_key,
    request_retry,
    store_key,
    summaries_for,
)

__all__ = [
    "MAX_KEYS_PER_USER",
    "PUBLIC_TAIL_LENGTH",
    "ApiKeyError",
    "ApiKeyStatus",
    "ApiKeySummary",
    "RetryOutcome",
    "TooManyKeysError",
    "delete_key",
    "public_tail",
    "request_retry",
    "store_key",
    "summaries_for",
]
