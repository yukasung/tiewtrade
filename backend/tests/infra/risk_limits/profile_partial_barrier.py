"""NC17 test-only interleaving at a naturally selected recovery read boundary."""

from __future__ import annotations

import asyncio
import json
import tempfile
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager, suppress
from contextvars import ContextVar
from datetime import timedelta
from pathlib import Path
from time import monotonic, time
from typing import Any

from tests.infra.risk_limits.profile_publisher_process import MAX_MESSAGE, encode, receive
from tiewtrade.core.money import Quantity
from tiewtrade.core.orders import TradingMode
from tiewtrade.infra.paper_orders import worker
from tiewtrade.services.engine import paper_order

_RECOVERY: ContextVar[dict[str, Any] | None] = ContextVar("partial_recovery", default=None)
_CLAIM: ContextVar[Any] = ContextVar("partial_claim", default=None)


class PartialBarrier:
    def __init__(self, output: Path) -> None:
        self.control = output / "partial-barrier.json"
        self.journal = output / "partial-barrier.jsonl"
        self.directory: tempfile.TemporaryDirectory[str] | None = None
        self.server: asyncio.Server | None = None
        self.handlers: set[asyncio.Task[Any]] = set()
        self.identity: dict[str, Any] | None = None
        self.done: asyncio.Future[dict[str, Any]] | None = None
        self.publish: Callable[[], Awaitable[dict[str, Any]]] | None = None
        self.attempted = False

    def record(self, event: str, **values: Any) -> None:
        with self.journal.open("a") as stream:
            stream.write(
                json.dumps({"stage": event, "at": time(), "monotonic": monotonic(), **values})
                + "\n"
            )

    async def deliver(
        self,
        identity: dict[str, Any],
        publish: Callable[[], Awaitable[dict[str, Any]]],
        *,
        deadline: float,
    ) -> dict[str, Any]:
        if self.identity is not None:
            raise RuntimeError("F19_BARRIER_ALREADY_ARMED")
        self.identity, self.publish = identity, publish
        self.done = asyncio.get_running_loop().create_future()
        self.directory = tempfile.TemporaryDirectory(prefix="f19-partial-")
        endpoint = str(Path(self.directory.name) / "consumer.sock")
        self.server = await asyncio.start_unix_server(self.handle, path=endpoint, limit=MAX_MESSAGE)
        temporary = self.control.with_suffix(".tmp")
        temporary.write_text(json.dumps({"endpoint": endpoint, "identity": identity}))
        temporary.replace(self.control)
        self.record("ARMED", identity=identity, deadline=deadline)
        try:
            async with asyncio.timeout_at(deadline):
                return await self.done
        except BaseException as error:
            self.record("FAILED", error_type=type(error).__name__, attempted=self.attempted)
            raise
        finally:
            await self.close()

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        task = asyncio.current_task()
        assert task is not None
        self.handlers.add(task)
        try:
            async with asyncio.timeout(1):
                ready = await receive(reader)
                if ready.get("identity") != self.identity or self.identity is None:
                    raise RuntimeError("F19_BARRIER_IDENTITY_MISMATCH")
                if ready.get("stage") != "READY" or self.attempted:
                    raise RuntimeError("F19_BARRIER_DUPLICATE_OR_INVALID_READY")
                if ready.get("generation") != self.identity["generation"]:
                    raise RuntimeError("F19_BARRIER_GENERATION_MISMATCH")
                self.record("READY", **ready)
                self.attempted = True  # Unknown publication/ACK never allows another attempt.
                self.record("PUBLICATION_REQUESTED", key=self.identity["key"])
                assert self.publish is not None
                receipt = await self.publish()
                if (
                    receipt.get("key") != self.identity["key"]
                    or receipt.get("generation") != ready["generation"]
                    or not 0 < receipt["input_id"] - ready["book_input"] <= 19
                ):
                    raise RuntimeError("F19_BARRIER_RECEIPT_MISMATCH")
                self.record("COMMITTED", receipt=receipt)
                writer.write(
                    encode({"stage": "COMMITTED", "identity": self.identity, "receipt": receipt})
                )
                await writer.drain()
                consumed = await receive(reader)
                if (
                    consumed.get("stage") != "CONSUMED"
                    or consumed.get("identity") != self.identity
                    or receipt["input_id"] not in consumed.get("inputs", [])
                ):
                    raise RuntimeError("F19_BARRIER_TRADE_NOT_CONSUMED")
                self.record("CONSUMED", inputs=consumed["inputs"], key=self.identity["key"])
                assert self.done is not None
                if not self.done.done():
                    self.done.set_result(receipt)
        except BaseException as error:
            self.record("HANDLER_FAILED", error_type=type(error).__name__)
            if self.done is not None and not self.done.done():
                self.done.set_exception(
                    RuntimeError("F19_BARRIER_DELIVERY_FAILED:" + type(error).__name__)
                )
        finally:
            writer.close()
            with suppress(ConnectionError, TimeoutError):
                async with asyncio.timeout(0.2):
                    await writer.wait_closed()
            self.handlers.discard(task)

    async def close(self) -> None:
        self.control.unlink(missing_ok=True)
        if self.server is not None:
            self.server.close()
            await self.server.wait_closed()
            self.server = None
        tasks = list(self.handlers)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        if self.done is not None:
            if not self.done.done():
                self.done.cancel()
            elif not self.done.cancelled():
                self.done.exception()
        if self.directory is not None:
            self.directory.cleanup()
            self.directory = None
            self.record("CLOSED", attempted=self.attempted)


@contextmanager
def consumer_barrier(control: Path | None) -> Iterator[None]:
    if control is None:
        yield
        return
    original_recovery = worker._recovery_inputs
    original_book = vars(worker)["read_latest_book"]
    original_process = vars(paper_order)["process_claimed_order"]

    async def process(*args: Any, **kwargs: Any) -> Any:
        token = _CLAIM.set(args[1])
        try:
            return await original_process(*args, **kwargs)
        finally:
            _CLAIM.reset(token)

    async def recovery(session: Any, state: Any) -> Any:
        context = None
        try:
            configuration = json.loads(control.read_text())
        except FileNotFoundError:
            configuration = None
        if configuration is not None:
            identity = configuration["identity"]
            target = next(
                (o for o in state.orders if str(o.intent.order_id) == identity["order"]), None
            )
            if (
                str(session.user_id) == identity["owner"]
                and str(state.scope.episode_id) == identity["episode"]
                and state.scope.mode is TradingMode.PAPER
                and (state.pair.base, state.pair.quote) == (identity["base"], identity["quote"])
                and target is not None
                and target.resting
                and not target.status.terminal
                and target.queue_ahead == Quantity.of(0, state.pair.base)
            ):
                context = configuration
        token = _RECOVERY.set(context)
        try:
            result = await original_recovery(session, state)
            if context is not None and "writer" in context:
                async with asyncio.timeout_at(context["deadline"]):
                    inputs = [value.market.input_id for value in result]
                    if context["receipt"]["input_id"] not in inputs:
                        raise RuntimeError("F19_BARRIER_TRADE_NOT_IN_FOLLOWING_READ")
                    context["writer"].write(
                        encode(
                            {"stage": "CONSUMED", "identity": context["identity"], "inputs": inputs}
                        )
                    )
                    await context["writer"].drain()
            return result
        finally:
            _RECOVERY.reset(token)
            if context is not None and "writer" in context:
                context["writer"].close()
                with suppress(ConnectionError, TimeoutError):
                    async with asyncio.timeout(0.2):
                        await context["writer"].wait_closed()

    async def book(session: Any, pair: Any) -> Any:
        record = await original_book(session, pair)
        configuration = _RECOVERY.get()
        if configuration is None:
            return record
        identity = configuration["identity"]
        row = (
            await session.execute(
                "SELECT pg_backend_pid() AS pid,clock_timestamp() AS now,wallet_id "
                "FROM paper_orders WHERE id=:id",
                {"id": identity["order"]},
            )
        ).one()
        claim = _CLAIM.get()
        if str(row.wallet_id) != identity["wallet"] or claim is None:
            raise RuntimeError("F19_BARRIER_WORKER_IDENTITY_MISMATCH")
        seconds = (record.market.received_at + timedelta(seconds=1) - row.now).total_seconds()
        if seconds <= 0:
            raise TimeoutError("F19_BARRIER_CAPTURED_BOOK_STALE")
        configuration["deadline"] = monotonic() + seconds
        async with asyncio.timeout_at(configuration["deadline"]):
            reader, writer = await asyncio.open_unix_connection(
                configuration["endpoint"], limit=MAX_MESSAGE
            )
            try:
                writer.write(
                    encode(
                        {
                            "stage": "READY",
                            "identity": identity,
                            "generation": record.market.generation,
                            "book_input": record.market.input_id,
                            "book_received_at": record.market.received_at.isoformat(),
                            "backend_pid": row.pid,
                            "claim": str(claim.claim_id),
                            "command": str(claim.command_id),
                        }
                    )
                )
                await writer.drain()
                message = await receive(reader)
                if message.get("stage") != "COMMITTED" or message.get("identity") != identity:
                    raise RuntimeError("F19_BARRIER_COMMIT_ACK_MISMATCH")
                # Observe the original following read, without replacing its return values.
                configuration["writer"] = writer
                configuration["receipt"] = message["receipt"]
                return record
            except BaseException:
                writer.close()
                raise

    worker._recovery_inputs = recovery
    vars(worker)["read_latest_book"] = book
    vars(paper_order)["process_claimed_order"] = process
    try:
        yield
    finally:
        worker._recovery_inputs = original_recovery
        vars(worker)["read_latest_book"] = original_book
        vars(paper_order)["process_claimed_order"] = original_process
