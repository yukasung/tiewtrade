"""Regression for Uvicorn's real WS logger, not only the ASGI response body."""

import asyncio
import logging
import socket
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
import uvicorn
from starlette.types import Receive, Scope, Send
from uvicorn.logging import AccessFormatter
from websockets.asyncio.client import connect
from websockets.exceptions import InvalidStatus

from tiewtrade.services.api.safe_logging import QueryStringRedactor, install_query_redaction

CANARY = "F10_QUERY_TOKEN_CANARY"


def test_formatted_error_log_redacts_the_whole_query() -> None:
    record = logging.LogRecord(
        "uvicorn.error",
        logging.INFO,
        "",
        1,
        '%s - "WebSocket %s" [accepted]',
        ("peer", f"/market-data/prices/stream?token={CANARY}&other=private"),
        None,
    )
    assert QueryStringRedactor().filter(record)
    assert CANARY not in record.getMessage()
    assert "other=private" not in record.getMessage()
    assert "/market-data/prices/stream" in record.getMessage()


def test_access_formatter_keeps_its_structured_arguments() -> None:
    record = logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        "",
        1,
        '%s - "%s %s HTTP/%s" %d',
        ("peer", "GET", f"/market-data/prices?token={CANARY}", "1.1", 200),
        None,
    )
    QueryStringRedactor().filter(record)
    rendered = AccessFormatter("%(request_line)s %(status_code)s", use_colors=False).format(record)
    assert CANARY not in rendered
    assert "GET /market-data/prices" in rendered and "200" in rendered


def test_filter_install_is_idempotent() -> None:
    install_query_redaction()
    install_query_redaction()
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "uvicorn.asgi"):
        assert sum(isinstance(f, QueryStringRedactor) for f in logging.getLogger(name).filters) == 1


@asynccontextmanager
async def real_server(accepted: bool, log_level: str = "info") -> AsyncIterator[int]:
    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        assert scope["type"] == "websocket"
        await receive()
        if accepted:
            await send({"type": "websocket.accept"})
            await send({"type": "websocket.close", "code": 1000})
        else:
            await send({"type": "websocket.close", "code": 1008})

    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            log_config=None,
            lifespan="off",
            log_level=log_level,
            ws="tiewtrade.services.api.price_protocol:PriceWebSocketProtocol",
        )
    )
    task = asyncio.create_task(server.serve(sockets=[listener]))
    try:
        async with asyncio.timeout(2):
            while not server.started:
                if task.done():
                    task.result()
                await asyncio.sleep(0.001)
        yield port
    finally:
        server.should_exit = True
        await asyncio.wait_for(task, 3)
        listener.close()


@pytest.mark.parametrize("accepted", [False, True])
async def test_real_uvicorn_ws_query_never_reaches_logs(
    accepted: bool,
    caplog: pytest.LogCaptureFixture,
) -> None:
    install_query_redaction()
    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        async with real_server(accepted) as port:
            url = (
                f"ws://127.0.0.1:{port}/market-data/prices/stream?token={CANARY}&signature=private"
            )
            if accepted:
                async with connect(url):
                    pass
            else:
                with pytest.raises(InvalidStatus) as error:
                    async with connect(url):
                        pass
                assert error.value.response.status_code == 403
    assert "/market-data/prices/stream" in caplog.text
    assert CANARY not in caplog.text and "signature=private" not in caplog.text


def test_exception_query_is_redacted_before_formatting() -> None:
    try:
        raise RuntimeError(f"request /market-data/prices/stream?token={CANARY}")
    except RuntimeError as error:
        record = logging.LogRecord(
            "uvicorn.error",
            logging.ERROR,
            "",
            1,
            "WebSocket exception",
            (),
            (type(error), error, error.__traceback__),
        )
    QueryStringRedactor().filter(record)
    rendered = logging.Formatter("%(message)s").format(record)
    assert CANARY not in rendered
    assert "RuntimeError" in rendered and "[REDACTED]" in rendered


def test_query_without_credentials_is_also_hidden_and_path_is_kept() -> None:
    record = logging.LogRecord(
        "uvicorn.error",
        logging.INFO,
        "",
        1,
        "/market-data/prices/stream?custom=private-value",
        (),
        None,
    )
    QueryStringRedactor().filter(record)
    assert record.getMessage() == "/market-data/prices/stream?[REDACTED]"


@pytest.mark.parametrize("accepted", [False, True])
@pytest.mark.parametrize("log_level", ["debug", "trace"])
async def test_transport_verbose_logs_never_expose_credentials(
    accepted: bool, log_level: str, caplog: pytest.LogCaptureFixture
) -> None:
    install_query_redaction()
    secret = "F10_SYNTHETIC_COOKIE_CANARY"
    with caplog.at_level(5, logger="uvicorn.error"):
        async with real_server(accepted, log_level) as port:
            connection = connect(
                f"ws://127.0.0.1:{port}/market-data/prices/stream",
                additional_headers={
                    "Cookie": f"tiewtrade_session={secret}",
                    "Authorization": f"Bearer {secret}",
                },
            )
            if accepted:
                async with connection:
                    pass
            else:
                with pytest.raises(InvalidStatus):
                    async with connection:
                        pass
    assert secret not in caplog.text
    assert "/market-data/prices/stream" in caplog.text


@pytest.mark.parametrize("level", [5, logging.DEBUG])
@pytest.mark.parametrize("logger_name", ["uvicorn.error", "uvicorn.asgi"])
def test_verbose_transport_payload_is_dropped_before_formatting(
    level: int, logger_name: str
) -> None:
    record = logging.LogRecord(logger_name, level, "", 1, "%s", (CANARY,), None)
    assert not QueryStringRedactor().filter(record)


@pytest.mark.parametrize("level", [logging.INFO, logging.WARNING, logging.ERROR])
def test_operational_logs_remain_available(level: int) -> None:
    record = logging.LogRecord("uvicorn.error", level, "", 1, "connection failed", (), None)
    assert QueryStringRedactor().filter(record)
    assert record.getMessage() == "connection failed"
