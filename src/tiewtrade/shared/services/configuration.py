"""Configuration loading for the application foundation."""

from __future__ import annotations

import os
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_APP_NAME = "TiewTrade"
DEFAULT_ENVIRONMENT = "development"
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOG_FILE_NAME = "tiewtrade.log"


@dataclass(frozen=True)
class AppConfig:
    """Validated foundation configuration."""

    app_name: str
    environment: str
    data_dir: Path
    log_dir: Path
    log_file: Path
    log_level: str


def load_app_config(
    config_path: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> AppConfig:
    env = os.environ if environ is None else environ
    file_path = config_path or _optional_path(env.get("TIEWTRADE_CONFIG_FILE"))
    file_values = _read_toml(file_path) if file_path else {}

    environment = _string_value(
        env.get("TIEWTRADE_ENV"),
        _nested_value(file_values, "app", "environment"),
        DEFAULT_ENVIRONMENT,
    )
    data_dir = _path_value(
        env.get("TIEWTRADE_DATA_DIR"),
        _nested_value(file_values, "app", "data_dir"),
        _default_data_dir(),
    )
    log_dir = _path_value(
        env.get("TIEWTRADE_LOG_DIR"),
        _nested_value(file_values, "logging", "log_dir"),
        data_dir / "logs",
    )
    log_level = _string_value(
        env.get("TIEWTRADE_LOG_LEVEL"),
        _nested_value(file_values, "logging", "level"),
        DEFAULT_LOG_LEVEL,
    ).upper()
    log_file_name = _string_value(
        None,
        _nested_value(file_values, "logging", "file_name"),
        DEFAULT_LOG_FILE_NAME,
    )

    return AppConfig(
        app_name=DEFAULT_APP_NAME,
        environment=environment,
        data_dir=data_dir,
        log_dir=log_dir,
        log_file=log_dir / log_file_name,
        log_level=log_level,
    )


def _read_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    with path.open("rb") as config_file:
        data = tomllib.load(config_file)

    return data if isinstance(data, dict) else {}


def _nested_value(values: Mapping[str, Any], section: str, key: str) -> Any:
    section_value = values.get(section, {})
    if not isinstance(section_value, Mapping):
        return None
    return section_value.get(key)


def _string_value(*candidates: Any) -> str:
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    raise ValueError("Expected at least one non-empty string candidate")


def _path_value(*candidates: Any) -> Path:
    for candidate in candidates:
        if isinstance(candidate, Path):
            return candidate.expanduser()
        if isinstance(candidate, str) and candidate.strip():
            return Path(candidate).expanduser()
    raise ValueError("Expected at least one path candidate")


def _optional_path(value: str | None) -> Path | None:
    if value is None or not value.strip():
        return None
    return Path(value).expanduser()


def _default_data_dir() -> Path:
    return Path.home() / ".tiewtrade"
