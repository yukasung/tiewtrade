"""Approved F-11 resource limits."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class IndicatorSettings:
    deadline_seconds: int = 30
    cleanup_seconds: int = 2
    response_bytes: int = 2 * 1024 * 1024


INDICATOR_SETTINGS = IndicatorSettings()
