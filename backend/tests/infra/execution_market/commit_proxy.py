"""Local PostgreSQL proxy that drops one real COMMIT acknowledgement."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager


@asynccontextmanager
async def drop_commit_reply(
    host: str, port: int, armed: asyncio.Event, dropped: asyncio.Event
) -> AsyncIterator[int]:
    """Forward plaintext test traffic, disconnect after the server commits, and clean up."""
    tasks: set[asyncio.Task[None]] = set()

    async def client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        upstream: asyncio.StreamWriter | None = None
        sender: asyncio.Task[None] | None = None
        try:
            response, upstream = await asyncio.open_connection(host, port)

            async def send() -> None:
                assert upstream is not None
                while data := await reader.read(65536):
                    upstream.write(data)
                    await upstream.drain()

            sender = asyncio.create_task(send())
            while True:
                header = await response.readexactly(5)
                size = int.from_bytes(header[1:], "big")
                if not 4 <= size <= 16 * 1024 * 1024:
                    raise AssertionError("invalid PostgreSQL test-proxy frame")
                body = await response.readexactly(size - 4)
                if (
                    header[:1] == b"C"
                    and body == b"COMMIT\x00"
                    and armed.is_set()
                    and not dropped.is_set()
                ):
                    dropped.set()
                    return
                writer.write(header + body)
                await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionError):
            pass
        finally:
            if sender is not None:
                sender.cancel()
                await asyncio.gather(sender, return_exceptions=True)
            writer.close()
            if upstream is not None:
                upstream.close()
                await upstream.wait_closed()
            await writer.wait_closed()

    def connected(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        task = asyncio.create_task(client(reader, writer))
        tasks.add(task)

    server = await asyncio.start_server(connected, "127.0.0.1", 0)
    try:
        yield int(server.sockets[0].getsockname()[1])
    finally:
        server.close()
        await server.wait_closed()
        for task in tasks:
            if not task.done():
                task.cancel()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, BaseException) and not isinstance(result, asyncio.CancelledError):
                raise result
