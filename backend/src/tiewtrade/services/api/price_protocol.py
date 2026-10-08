"""Push-only price sockets: bounded decoding with the approved policy close code."""

import asyncio
from typing import Any

from uvicorn.config import Config
from uvicorn.protocols.websockets.websockets_sansio_impl import WebSocketsSansIOProtocol
from uvicorn.server import ServerState
from websockets.frames import CloseCode
from websockets.server import ServerProtocol

INBOUND_MESSAGE_LIMIT = 256


class _PushOnlyServerProtocol(ServerProtocol):
    def fail(self, code: CloseCode | int, reason: str = "") -> None:
        # Every application message is forbidden; keep native bounded decoding,
        # but classify a size violation as the same policy failure as ASGI does.
        if code == CloseCode.MESSAGE_TOO_BIG:
            code, reason = CloseCode.POLICY_VIOLATION, "application messages are forbidden"
        super().fail(code, reason)


class PriceWebSocketProtocol(WebSocketsSansIOProtocol):
    """Uvicorn --ws entry point; preserves its ASGI, flow-control and keepalive glue."""

    def __init__(
        self,
        config: Config,
        server_state: ServerState,
        app_state: dict[str, Any],
        _loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        super().__init__(config, server_state, app_state, _loop)
        # Uvicorn creates its Sans-I/O decoder before receiving any wire data.
        # Replace only that decoder, carrying over its handshake configuration.
        self.conn = _PushOnlyServerProtocol(
            origins=self.conn.origins,
            extensions=self.conn.available_extensions,
            subprotocols=self.conn.available_subprotocols,
            max_size=INBOUND_MESSAGE_LIMIT,
            logger=self.conn.logger,
        )
