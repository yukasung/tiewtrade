"""Application bootstrap for foundation services."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from tiewtrade.application.context import AppContext
from tiewtrade.shared.services.configuration import load_app_config
from tiewtrade.shared.services.logging import configure_logging


class ApplicationBootstrap:
    """Initialize configuration, directories, and logging for the desktop app."""

    def __init__(
        self,
        config_path: Path | None = None,
        environ: Mapping[str, str] | None = None,
    ) -> None:
        self._config_path = config_path
        self._environ = environ

    def initialize(self) -> AppContext:
        config = load_app_config(config_path=self._config_path, environ=self._environ)
        config.data_dir.mkdir(parents=True, exist_ok=True)
        config.log_dir.mkdir(parents=True, exist_ok=True)

        logger = configure_logging(config)
        logger.debug("Application bootstrap initialized")

        return AppContext(config=config, logger=logger)
