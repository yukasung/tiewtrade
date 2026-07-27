from enum import StrEnum


class PersistenceState(StrEnum):
    READY = "ready"
    BLOCKED = "blocked"


class SessionPersistenceBlockedError(RuntimeError):
    pass
