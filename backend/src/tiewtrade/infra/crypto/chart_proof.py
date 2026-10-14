"""Display proofs reuse cursor key lifecycle with a distinct MAC domain."""

from uuid import UUID

from tiewtrade.infra.crypto.indicator_cursor import CursorClaims, issue, verify
from tiewtrade.infra.crypto.keys import KeySource


def issue_display(claims: CursorClaims, keys: KeySource, user: UUID, session: str) -> str:
    return issue(claims, keys, user, session, purpose="chart-display-v1")


def verify_display(raw: str, keys: KeySource, user: UUID, session: str) -> CursorClaims:
    return verify(raw, keys, user, session, purpose="chart-display-v1")
