"""ยืนยันตัวตน: รหัสผ่าน, ข้อมูลเข้าสู่ระบบ, session, ตัวนับอัตราการเรียก (F-05)

ของสาธารณะของชั้นนี้อยู่ที่นี่ที่เดียว — ส่วน `services/api` เรียกผ่านที่นี่

**บทบาท `tiewtrade_auth` เท่านั้นที่แตะข้อมูลเข้าสู่ระบบและออก session ได้**
ส่วน `tiewtrade_api` ทำได้เท่าที่ถือโทเคนอยู่ (`requirements.md` Q-8)

เปิดเท่าที่มีคนใช้จริง — ชนิดที่เป็นแค่ผลลัพธ์ของฟังก์ชัน (`SessionOwner`,
`BucketState`, `Deadlines`) และชนิดข้อผิดพลาดที่ยังไม่มีใครดัก อยู่ในโมดูลของตัวเอง
ใครต้องใช้ก็ import จากที่นั่น **ชื่อที่ส่งออกไว้เผื่อคือชื่อที่ต้องรักษาความเข้ากันได้
ทั้งที่ยังไม่มีใครเรียก**
"""

from tiewtrade.infra.auth.blocklist import (
    MANIFEST_FIELDS,
    blocked_digests,
    digest_of,
    is_blocked,
    manifest,
)
from tiewtrade.infra.auth.challenges import (
    CHALLENGE_LIFETIME,
    IssuedChallenge,
    PresentedChallenge,
)
from tiewtrade.infra.auth.credentials import (
    LockedCredential,
    create_credential,
    email_of,
    locked_credential,
    owner_of_email,
    replace_password_hash,
)
from tiewtrade.infra.auth.hashing import (
    StoredHashUnreadableError,
    hash_password,
    password_matches,
    spend_matching_time,
)
from tiewtrade.infra.auth.lifetimes import (
    ABSOLUTE_LIFETIME,
    IDLE_LIFETIME,
    deadlines_for_new_session,
    renewed_idle_deadline,
)
from tiewtrade.infra.auth.recovery_codes import CODES_PER_SET, IssuedCodes
from tiewtrade.infra.auth.sessions import (
    end_all,
    end_one,
    end_others,
    hash_token,
    issue,
    new_token,
    owner_of_presented,
    renew,
)
from tiewtrade.infra.auth.throttle import (
    Bucket,
    claim,
    clear,
    count_failure,
    delay_after,
    key_of,
)

__all__ = [
    "ABSOLUTE_LIFETIME",
    "CHALLENGE_LIFETIME",
    "CODES_PER_SET",
    "IDLE_LIFETIME",
    "MANIFEST_FIELDS",
    "Bucket",
    "IssuedChallenge",
    "IssuedCodes",
    "LockedCredential",
    "PresentedChallenge",
    "StoredHashUnreadableError",
    "blocked_digests",
    "claim",
    "clear",
    "count_failure",
    "create_credential",
    "deadlines_for_new_session",
    "delay_after",
    "digest_of",
    "email_of",
    "end_all",
    "end_one",
    "end_others",
    "hash_password",
    "hash_token",
    "is_blocked",
    "issue",
    "key_of",
    "locked_credential",
    "manifest",
    "new_token",
    "owner_of_email",
    "owner_of_presented",
    "password_matches",
    "renew",
    "renewed_idle_deadline",
    "replace_password_hash",
    "spend_matching_time",
]
