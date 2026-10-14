"""The sole WSS gateway: one reader, bounded buffers and finite subscription gate."""

from __future__ import annotations

import asyncio
import json
from collections import deque
from collections.abc import AsyncGenerator, Callable
from contextlib import aclosing
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import cast

from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import InvalidStatus, WebSocketException

from tiewtrade.core.realtime_prices import QuoteObservation
from tiewtrade.venues.binance_th.failures import retry_after_of
from tiewtrade.venues.binance_th.mapping import market_symbol
from tiewtrade.venues.binance_th.stream_mapping import quote_from_stream, subscription_ack
from tiewtrade.venues.errors import VenueProtocolError
from tiewtrade.venues.price_streams import FeedConnected, FeedDisconnected, FeedEvent, FeedQuote
from tiewtrade.venues.symbols import Symbol

STREAM_URL = "wss://nbstream.binance.th/w3w/wsa/stream"
ROTATION_SECONDS = 23 * 3600 + 50 * 60


class _ControlBoundConnection(ClientConnection):
    """Count automatic pongs, probes and subscription together before writing.

    A peer exceeding our control budget is disconnected instead of building an
    unbounded pong backlog or transmitting more than five frames per second.
    """

    def send_data(self) -> None:
        if not hasattr(self, "_control_times"):
            self._control_times: deque[timedelta] = deque()
        for data in self.protocol.data_to_send():
            if data and data[0] & 15 in (1, 9, 10) and not data.startswith(b"GET "):
                now = timedelta(seconds=self.loop.time())
                while self._control_times and self._control_times[0] <= now - timedelta(seconds=1):
                    self._control_times.popleft()
                if len(self._control_times) >= 5:
                    self.transport.abort()
                    raise ConnectionError("control budget exceeded")
                self._control_times.append(now)
            if data:
                self.transport.write(data)
            elif self.transport.can_write_eof():
                try:
                    self.transport.write_eof()
                except OSError:
                    self.transport.close()
            else:
                self.transport.close()


@dataclass(frozen=True, slots=True)
class StreamFrame:
    generation: int
    value: object


class BinanceThStreamTransport:
    def __init__(
        self,
        *,
        clock: Callable[[], datetime],
        endpoint: str = STREAM_URL,
        ack_timeout: timedelta = timedelta(seconds=5),
    ) -> None:
        self._clock = clock
        self._endpoint = endpoint
        self._ack_timeout = ack_timeout

    async def connection(
        self, symbols: tuple[Symbol, ...], *, generation: int
    ) -> AsyncGenerator[FeedEvent, None]:
        def decode(payload: object, received_at: datetime) -> object:
            return quote_from_stream(payload=payload, symbols=symbols, received_at=received_at)

        params = tuple(f"{market_symbol(pair).lower()}@trade" for pair in symbols)
        async with aclosing(self.frames(params, generation=generation, decode=decode)) as events:
            async for event in events:
                if isinstance(event, StreamFrame):
                    yield FeedQuote(event.generation, cast(QuoteObservation, event.value))
                else:
                    yield event

    async def frames(
        self,
        params: tuple[str, ...],
        *,
        generation: int,
        decode: Callable[[object, datetime], object],
    ) -> AsyncGenerator[FeedConnected | FeedDisconnected | StreamFrame, None]:
        failure = "VENUE_UNAVAILABLE"
        retry_after = None
        try:
            async with connect(
                self._endpoint,
                open_timeout=10,
                close_timeout=5,
                ping_interval=10,
                ping_timeout=5,
                max_size=65536,
                max_queue=16,
                create_connection=_ControlBoundConnection,
            ) as socket:
                try:
                    loop = asyncio.get_running_loop()
                    deadline = loop.time() + self._ack_timeout.total_seconds()
                    expires = loop.time() + ROTATION_SECONDS
                    # Deadline includes send/control reservation, not just receive.
                    try:
                        async with asyncio.timeout_at(deadline):
                            await socket.send(
                                json.dumps(
                                    {
                                        "method": "SUBSCRIBE",
                                        "params": list(params),
                                        "id": generation,
                                    }
                                )
                            )
                            while True:
                                payload = _decode(await socket.recv())
                                if loop.time() >= deadline:
                                    raise TimeoutError
                                if isinstance(payload, dict) and "stream" in payload:
                                    # Validate but discard pre-ack trades; no unbounded queue.
                                    decode(payload, self._clock())
                                    continue
                                if subscription_ack(payload, generation):
                                    if loop.time() >= deadline:
                                        raise TimeoutError
                                    break
                    except TimeoutError:
                        failure = "SUBSCRIPTION_ACK_TIMEOUT"
                        # Yield invalidation before awaiting the bounded context cleanup.
                        yield FeedDisconnected(generation, failure)
                        return
                    yield FeedConnected(generation)
                    async with asyncio.timeout_at(expires):
                        while True:
                            payload = _decode(await socket.recv())
                            if loop.time() >= expires:
                                raise TimeoutError
                            if isinstance(payload, dict) and "stream" in payload:
                                quote = decode(payload, self._clock())
                                yield StreamFrame(generation, quote)
                            else:
                                # Duplicate success ack doesn't restart recovery/deadline.
                                subscription_ack(payload, generation)
                except VenueProtocolError:
                    yield FeedDisconnected(generation, "VENUE_PROTOCOL")
                    return
                except (WebSocketException, OSError, TimeoutError):
                    yield FeedDisconnected(generation, "VENUE_UNAVAILABLE")
                    return
        except InvalidStatus as error:
            if error.response.status_code in (429, 418):
                try:
                    retry_after = retry_after_of(
                        error.response.headers.get("retry-after"), at=self._clock()
                    )
                    failure = "VENUE_RATE_LIMITED"
                except VenueProtocolError:
                    failure = "VENUE_PROTOCOL"
        except VenueProtocolError:
            failure = "VENUE_PROTOCOL"
        except (WebSocketException, OSError, TimeoutError):
            failure = "VENUE_UNAVAILABLE"
        # Cancellation closes context but never emits misleading new callbacks.
        yield FeedDisconnected(generation, failure, retry_after)


def _decode(raw: str | bytes) -> object:
    try:
        return json.loads(raw, parse_float=str)
    except (ValueError, UnicodeError) as error:
        raise VenueProtocolError() from error
