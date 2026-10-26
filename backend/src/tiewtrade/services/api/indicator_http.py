"""Shared indicator admission, cancellation, error and response boundaries."""

import asyncio
import gc
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from time import monotonic
from typing import Self, cast

from fastapi import HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel
from pydantic_core import to_json

from tiewtrade.core.money import MoneyError
from tiewtrade.infra.crypto.indicator_cursor import CursorRejectedError, DatasetChangedError
from tiewtrade.infra.db.errors import InfraError
from tiewtrade.infra.indicators.codec import CheckpointCodecError
from tiewtrade.infra.indicators.prepared import PreparedNotReadyError, PreparedNumericError
from tiewtrade.infra.market_data.records import MarketDataInputError
from tiewtrade.infra.realtime.admission import RedisAdmission
from tiewtrade.services.api.authentication import Authenticated
from tiewtrade.services.api.indicator_admission import IndicatorBudget
from tiewtrade.services.api.indicator_settings import INDICATOR_SETTINGS


class ClientDisconnectedError(asyncio.CancelledError):
    """A peer disconnect, distinct from cancellation of the server task."""


JSON_YIELD_ITEMS = 8


@dataclass(frozen=True, slots=True)
class JSONFragments:
    items: tuple[bytes, ...]


@dataclass(frozen=True, slots=True)
class ChunkedJSON:
    """A schema-validated model whose large arrays are already encoded by row."""

    fields: tuple[tuple[str, object], ...]

    @classmethod
    def from_model(cls, model: BaseModel, **fragments: JSONFragments) -> Self:
        return cls(
            tuple(
                (name, fragments[name] if name in fragments else getattr(model, name))
                for name in type(model).model_fields
            )
        )

    def extended(self, *fields: tuple[str, object]) -> Self:
        return type(self)(self.fields + fields)


def _json_value(value: object) -> bytes:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return to_json(value)


def encode_json_fragment(value: object) -> bytes:
    return _json_value(value)


async def _without_automatic_gc[T](work: Awaitable[T]) -> T:
    """Keep cyclic GC away from a bounded large graph, then collect after it is released."""
    enabled = gc.isenabled()
    if enabled:
        gc.disable()
    try:
        return await work
    finally:
        if enabled:
            try:
                # Reset young-generation pressure without scanning the long-lived
                # heap. A full collection here scales with the retained dataset and
                # becomes an event-loop pause on maximum-size indicator reads.
                gc.collect(0)
            finally:
                gc.enable()


async def _model_json_bytes(
    result: BaseModel | ChunkedJSON, deadline: float, clock: Callable[[], float]
) -> bytes:
    """Serialize bounded slices without sending a partial HTTP body."""
    body = bytearray(b"{")
    fields = (
        result.fields
        if isinstance(result, ChunkedJSON)
        else tuple((name, getattr(result, name)) for name in type(result).model_fields)
    )
    for field_index, (name, value) in enumerate(fields):
        if field_index:
            body.extend(b",")
        body.extend(to_json(name))
        body.extend(b":")
        if isinstance(value, JSONFragments):
            body.extend(b"[")
            for item_index, item in enumerate(value.items):
                if item_index:
                    body.extend(b",")
                body.extend(item)
                if (item_index + 1) % JSON_YIELD_ITEMS == 0:
                    if clock() >= deadline:
                        raise TimeoutError()
                    await asyncio.sleep(0)
            body.extend(b"]")
            continue
        if not isinstance(value, list):
            body.extend(_json_value(value))
            continue
        body.extend(b"[")
        for item_index, item in enumerate(value):
            if item_index:
                body.extend(b",")
            body.extend(_json_value(item))
            if (item_index + 1) % JSON_YIELD_ITEMS == 0:
                if clock() >= deadline:
                    raise TimeoutError()
                await asyncio.sleep(0)
        body.extend(b"]")
    body.extend(b"}")
    return bytes(body)


async def until_disconnect[T](request: Request, work: Awaitable[T]) -> T:
    stopping = False

    async def disconnected() -> None:
        while not stopping:
            if (await request.receive())["type"] == "http.disconnect":
                return

    reader = asyncio.ensure_future(work)
    watcher = asyncio.create_task(disconnected())
    try:
        done, _ = await asyncio.wait((reader, watcher), return_when=asyncio.FIRST_COMPLETED)
        if watcher in done:
            watcher.result()
            raise ClientDisconnectedError()
        return reader.result()
    finally:
        stopping = True
        for task in (reader, watcher):
            if not task.done():
                task.cancel()
        joined = asyncio.gather(reader, watcher, return_exceptions=True)
        cancelled = False
        while not joined.done():
            try:
                await asyncio.shield(joined)
            except asyncio.CancelledError:
                cancelled = True
        if cancelled:
            raise asyncio.CancelledError()


async def indicator_response(
    request: Request,
    who: Authenticated,
    work: Callable[[float], Awaitable[BaseModel | ChunkedJSON]],
    *,
    clock: Callable[[], float] = monotonic,
    deadline_seconds: float = INDICATOR_SETTINGS.deadline_seconds,
    disconnect_response: bool = False,
) -> Response:
    deadline = clock() + deadline_seconds
    budget = cast(IndicatorBudget, request.app.state.indicator_budget)
    admission = cast(RedisAdmission, request.app.state.indicator_admission)
    try:
        async with asyncio.timeout_at(deadline):
            async with budget.reserve(admission, who.user_id):
                result = await until_disconnect(
                    request,
                    _without_automatic_gc(work(deadline)),
                )
                body = (
                    await _model_json_bytes(result, deadline, clock)
                    if isinstance(result, (BaseModel, ChunkedJSON))
                    else result.model_dump_json().encode()
                )
                if clock() >= deadline:
                    raise TimeoutError()
                if len(body) > INDICATOR_SETTINGS.response_bytes:
                    raise HTTPException(503, "INDICATOR_RESOURCE_LIMIT")
                return Response(
                    body,
                    media_type="application/json",
                    headers={"Cache-Control": "private, no-store"},
                )
    except ClientDisconnectedError:
        if not disconnect_response:
            raise
        # Reader cleanup completed before responding to the already closed peer.
        return Response(status_code=499, headers={"Cache-Control": "private, no-store"})
    except DatasetChangedError:
        raise HTTPException(409, "INDICATOR_DATASET_CHANGED") from None
    except CursorRejectedError:
        raise HTTPException(422, "INPUT_REJECTED") from None
    except (MoneyError, PreparedNumericError):
        raise HTTPException(422, "INDICATOR_NUMERIC_ERROR") from None
    except (PreparedNotReadyError, CheckpointCodecError):
        raise HTTPException(
            503, "INDICATOR_DATA_NOT_READY", headers={"Retry-After": "10"}
        ) from None
    except MarketDataInputError as error:
        raise HTTPException(422, error.code) from None
    except TimeoutError:
        raise HTTPException(504, "INDICATOR_DEADLINE_EXCEEDED") from None
    except InfraError:
        raise HTTPException(503, "INDICATOR_DATA_UNAVAILABLE") from None
