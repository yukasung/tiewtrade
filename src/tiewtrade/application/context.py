"""Application context shared after bootstrap."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from tiewtrade.shared.services.configuration import AppConfig


@dataclass(frozen=True)
class AppContext:
    """Container for foundation services initialized at application startup."""

    config: AppConfig
    logger: logging.Logger
