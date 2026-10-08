"""Keep request queries and verbose transport data out of Uvicorn logs."""

import logging
import re
import traceback

_QUERY = re.compile(r"\?\S*")


def _redact(value: str) -> str:
    return _QUERY.sub("?[REDACTED]", value)


class QueryStringRedactor(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # DEBUG wire dumps include headers, frames and peer-provided close reasons;
        # TRACE includes ASGI scopes/messages. Header-name redaction cannot cover
        # arbitrary payloads. Keep operational INFO+ logs, never verbose dumps,
        # even when the operator enables a lower Uvicorn logging level.
        if record.levelno < logging.INFO:
            return False
        # Uvicorn's AccessFormatter needs its five arguments to format request_line
        # and status_code. Flattening these records would break HTTP logging.
        if (
            record.name == "uvicorn.access"
            and isinstance(record.args, tuple)
            and len(record.args) == 5
        ):
            record.args = tuple(
                _redact(value) if isinstance(value, str) else value for value in record.args
            )
        else:
            record.msg = _redact(record.getMessage())
            record.args = ()
        if record.exc_info:
            record.exc_text = _redact("".join(traceback.format_exception(*record.exc_info)))
            record.exc_info = None
        elif record.exc_text is not None:
            record.exc_text = _redact(record.exc_text)
        return True


def install_query_redaction() -> None:
    """Logger filters run before handlers, including propagated/capture handlers."""
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "uvicorn.asgi"):
        logger = logging.getLogger(name)
        if not any(isinstance(item, QueryStringRedactor) for item in logger.filters):
            logger.addFilter(QueryStringRedactor())
