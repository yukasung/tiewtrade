"""Bounded acknowledged local control channel for the R31 fixture publisher."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from tests.infra.execution_market import profile_workload as f15
from tests.infra.risk_limits.profile_publisher import (
    FAILURE_CATEGORIES,
    FAILURE_STAGES,
    SourcePublisher,
)
from tests.infra.risk_limits.profile_source_timing import SourceTimeline
from tiewtrade.infra.db import DatabaseRole

MAX_MESSAGE = 65536
QUEUE_LIMIT = 256
CONTROL_TIMEOUT = 5


def encode(message: dict[str, Any]) -> bytes:
    result = (json.dumps(message) + "\n").encode()
    if len(result) > MAX_MESSAGE:
        raise RuntimeError("F18_SOURCE_MESSAGE_LIMIT")
    return result


async def receive(reader: asyncio.StreamReader) -> dict[str, Any]:
    data = await reader.readline()
    if not data:
        raise RuntimeError("F18_SOURCE_CHANNEL_CLOSED")
    result = json.loads(data)
    if not isinstance(result, dict):
        raise RuntimeError("F18_SOURCE_MESSAGE_INVALID")
    return result


class PublisherLink:
    def __init__(
        self,
        output: Path,
        emit: Callable[[dict[str, Any]], None],
        processes: list[asyncio.subprocess.Process],
    ) -> None:
        self.output, self.emit, self.processes = output, emit, processes
        self.trace = False
        self.process: asyncio.subprocess.Process | None = None
        self.writer: asyncio.StreamWriter | None = None
        self.receiver: asyncio.Task[None] | None = None
        self.sequence = 0
        self.pending: dict[int, asyncio.Future[None]] = {}
        self.running: asyncio.Future[None] | None = None
        self.lock = asyncio.Lock()
        self.closing = False
        self.error: BaseException | None = None

    async def connect(self) -> None:
        if self.process is not None:
            return
        parent, child = socket.socketpair()
        parent.setblocking(False)
        environment = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("TIEWTRADE_") or key == DatabaseRole.MARKET_DATA.url_variable
        }
        try:
            self.process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-m",
                "tests.infra.risk_limits.profile_publisher_process",
                "--fd",
                str(child.fileno()),
                "--output",
                str(self.output),
                *(["--trace"] if self.trace else []),
                pass_fds=(child.fileno(),),
                env=environment,
            )
            self.processes.append(self.process)
            f15.WORKER_RUNTIME_PIDS[self.process.pid] = self.process.pid
            (self.output / "publisher.pid").write_text(str(self.process.pid))
            reader, self.writer = await asyncio.open_connection(sock=parent, limit=MAX_MESSAGE)
            self.receiver = asyncio.create_task(self.read_events(reader))
        except BaseException:
            parent.close()
            raise
        finally:
            child.close()

    async def read_events(self, reader: asyncio.StreamReader) -> None:
        try:
            while True:
                event = await receive(reader)
                if event["kind"] == "ack":
                    future = self.pending.get(event["sequence"])
                    if future is None or future.done():
                        raise RuntimeError("F18_SOURCE_ACK_ORDER")
                    future.set_result(None)
                elif event["kind"] == "done":
                    if self.running is not None and not self.running.done():
                        if event["ok"]:
                            self.running.set_result(None)
                        else:
                            failure = event.get("failure")
                            code = "F18_SOURCE_CHILD_FAILED"
                            if isinstance(failure, dict):
                                stage, category = failure.get("stage"), failure.get("category")
                                if stage in FAILURE_STAGES and category in FAILURE_CATEGORIES:
                                    code += f":{stage}:{category}"
                            self.running.set_exception(RuntimeError(code))
                else:
                    self.emit(event)
        except BaseException as error:
            if not self.closing:
                self.error = error
                for future in [*self.pending.values(), self.running]:
                    if future is not None and not future.done():
                        future.set_exception(RuntimeError("F18_SOURCE_CHANNEL_FAILED"))
                if not isinstance(error, asyncio.CancelledError):
                    return
            raise

    async def request(self, operation: str, values: dict[str, Any] | None = None) -> None:
        async with self.lock, asyncio.timeout(CONTROL_TIMEOUT):
            await self.connect()
            if self.error is not None:
                raise RuntimeError("F18_SOURCE_CHANNEL_FAILED") from None
            assert self.writer is not None
            self.sequence += 1
            future: asyncio.Future[None] = asyncio.get_running_loop().create_future()
            self.pending[self.sequence] = future
            try:
                self.writer.write(
                    encode(
                        {"operation": operation, "sequence": self.sequence, "values": values or {}}
                    )
                )
                await self.writer.drain()
                try:
                    await future
                except RuntimeError:
                    raise RuntimeError("F18_SOURCE_CHANNEL_FAILED") from self.error
            finally:
                self.pending.pop(self.sequence, None)

    async def control(self, values: dict[str, Any]) -> None:
        await self.request("SET", values)

    async def run(self, stop: asyncio.Event) -> None:
        self.running = asyncio.get_running_loop().create_future()
        waiter = asyncio.create_task(stop.wait())
        try:
            await self.request("START")
            done, _ = await asyncio.wait(
                (waiter, self.running), return_when=asyncio.FIRST_COMPLETED
            )
            if self.running in done:
                await self.running
                if not stop.is_set():
                    raise RuntimeError("F18_SOURCE_PUBLISHER_STOPPED_UNEXPECTEDLY")
            await self.request("STOP")
            await self.running
        finally:
            waiter.cancel()
            await asyncio.gather(waiter, return_exceptions=True)

    async def close(self) -> None:
        if self.process is None:
            return
        try:
            if self.process.returncode is None and self.error is None:
                await self.request("CLOSE")
            self.closing = True
            async with asyncio.timeout(CONTROL_TIMEOUT):
                await self.process.wait()
        finally:
            self.closing = True
            if self.process.returncode is None:
                self.process.terminate()
                try:
                    async with asyncio.timeout(2):
                        await self.process.wait()
                except TimeoutError:
                    self.process.kill()
                    await self.process.wait()
            if self.receiver is not None:
                self.receiver.cancel()
                await asyncio.gather(self.receiver, return_exceptions=True)
            if self.writer is not None:
                self.writer.close()
                await self.writer.wait_closed()
            if self.running is not None and self.running.done() and not self.running.cancelled():
                # Failure is delivered through run(); retrieve to avoid orphan warnings.
                self.running.exception()


async def serve(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter, output: Path, trace: bool = False
) -> None:
    outgoing: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=QUEUE_LIMIT)
    source = SourcePublisher(output, outgoing.put)
    if trace:
        source.source_timeline = SourceTimeline(output, source.source_market, observe_backend=True)
    publication: asyncio.Task[None] | None = None
    last_sequence = 0

    async def send() -> None:
        while True:
            message = await outgoing.get()
            try:
                writer.write(encode(message))
                await writer.drain()
            finally:
                outgoing.task_done()

    async def publish() -> None:
        ok = False
        try:
            await source.publish()
            ok = True
        except Exception as error:
            source.record_failure(error, "PUBLISH")
            raise
        finally:
            await outgoing.put({"kind": "done", "ok": ok, "failure": source.failure})

    async def controls() -> None:
        nonlocal publication, last_sequence
        while True:
            message = await receive(reader)
            if message["sequence"] != last_sequence + 1:
                raise RuntimeError("F18_SOURCE_CONTROL_ORDER")
            last_sequence = message["sequence"]
            operation = message["operation"]
            if operation == "SET":
                source.configure(message["values"])
            elif operation == "DISPOSE":
                await source.source_market.dispose()
            elif operation == "START":
                if publication is not None and not publication.done():
                    raise RuntimeError("F18_SOURCE_DUPLICATE_START")
                source.stop_market.clear()
                publication = asyncio.create_task(publish())
            elif operation in ("STOP", "CLOSE"):
                source.stop_market.set()
                if publication is not None:
                    if operation == "CLOSE":
                        await asyncio.gather(publication, return_exceptions=True)
                    else:
                        await publication
            else:
                raise RuntimeError("F18_SOURCE_CONTROL_UNKNOWN")
            await outgoing.put({"kind": "ack", "sequence": last_sequence})
            if operation == "CLOSE":
                await outgoing.join()
                return

    sender = asyncio.create_task(send())
    controller = asyncio.create_task(controls())
    try:
        done, _ = await asyncio.wait((sender, controller), return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
    finally:
        if publication is not None:
            publication.cancel()
            await asyncio.gather(publication, return_exceptions=True)
        for task in (controller, sender):
            task.cancel()
        await asyncio.gather(controller, sender, return_exceptions=True)
        await source.close_source()
        writer.close()
        await writer.wait_closed()


async def main_async(fd: int, output: Path, trace: bool) -> None:
    sock = socket.socket(fileno=fd)
    sock.setblocking(False)
    reader, writer = await asyncio.open_connection(sock=sock, limit=MAX_MESSAGE)
    await serve(reader, writer, output, trace)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fd", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--trace", action="store_true")
    args = parser.parse_args()
    try:
        asyncio.run(main_async(args.fd, args.output, args.trace))
    except Exception:
        sys.stderr.write("F18_SOURCE_CHILD_FAILED\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
