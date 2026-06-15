"""Logging foundation with conservative redaction defaults."""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from tiewtrade.shared.services.configuration import AppConfig

LOGGER_NAME = "tiewtrade"
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s - %(message)s"
REDACTED_VALUE = "[REDACTED]"

_SENSITIVE_FIELD_PATTERN = r"(?:api[_-]?key|api[_-]?secret|secret|license|token|signature)"
_SENSITIVE_VALUE_PATTERN = re.compile(
    rf"(?i)([\"']?\b{_SENSITIVE_FIELD_PATTERN}\b[\"']?)"
    rf"(\s*[:=]\s*)"
    rf"(\"[^\"]*\"|'[^']*'|[^,\s}}]+)"
)
_SENSITIVE_KEY_PATTERN = re.compile(rf"(?i){_SENSITIVE_FIELD_PATTERN}")


class RedactingFilter(logging.Filter):
    """Remove sensitive values from log records before handlers write them."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = _redact(record.msg)
        if record.args:
            record.args = _redact_args(record.args)
        return True


def configure_logging(config: AppConfig) -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(_level(config.log_level))
    logger.propagate = False

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    redaction_filter = RedactingFilter()
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    stream_handler.addFilter(redaction_filter)
    logger.addHandler(stream_handler)

    file_handler = _file_handler(config.log_file)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    file_handler.addFilter(redaction_filter)
    logger.addHandler(file_handler)

    return logger


def _file_handler(path: Path) -> logging.FileHandler:
    path.parent.mkdir(parents=True, exist_ok=True)
    return logging.FileHandler(path, encoding="utf-8")


def _level(value: str) -> int:
    return logging.getLevelNamesMapping().get(value.upper(), logging.INFO)


def _redact(value: Any) -> Any:
    if isinstance(value, str):
        return _SENSITIVE_VALUE_PATTERN.sub(rf"\1\2{REDACTED_VALUE}", value)
    if isinstance(value, Mapping):
        return _redact_mapping(value)
    if isinstance(value, tuple):
        return tuple(_redact(item) for item in value)
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def _redact_args(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _redact_mapping(value)
    if isinstance(value, tuple):
        return tuple(_redact(item) for item in value)
    return (_redact(value),)


def _redact_mapping(value: Mapping[Any, Any]) -> dict[Any, Any]:
    return {
        key: REDACTED_VALUE if _is_sensitive_key(key) else _redact(item)
        for key, item in value.items()
    }


def _is_sensitive_key(key: Any) -> bool:
    return isinstance(key, str) and bool(_SENSITIVE_KEY_PATTERN.search(key))
