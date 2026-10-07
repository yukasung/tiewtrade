"""Shared pure timezone validation."""

from datetime import datetime


def require_aware(label: str, moment: datetime) -> None:
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError(f"{label}ต้องมี timezone กำกับ")
