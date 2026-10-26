"""Authenticated catalog reads and narrowly scoped Platform Admin mutations."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, cast
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field, ValidationInfo, field_validator

from tiewtrade.infra.db import (
    CatalogAuthorizationError,
    CatalogIdempotencyConflictError,
    CatalogProtocolError,
    CatalogRevisionConflictError,
    CatalogStateError,
    DatabaseRole,
    InfraError,
    user_session,
)
from tiewtrade.infra.platform import (
    CatalogAction,
    CatalogCommand,
    CatalogReason,
    CatalogView,
    ConstraintEvidence,
    enable_mutations,
    impact_preview,
    read_catalog,
    replay_command,
    request_add,
    request_remove,
    role_for,
)
from tiewtrade.services.api.authentication import Authenticated, current_user
from tiewtrade.services.api.resources import engine_for
from tiewtrade.venues import Symbol, VenueError, VenueRateLimitedError, VenueUnavailableError
from tiewtrade.venues.order_books import ExecutionCapabilitySource

router = APIRouter(tags=["supported-symbols"])


class CatalogPairView(BaseModel):
    base: str
    quote: str
    status: str
    revision: int
    updated_at: datetime
    cleanup: CatalogCleanupView | None = None


class CatalogCleanupView(BaseModel):
    status: str
    attempts: int
    bots_stopped: int
    commands_rejected: int
    orders_canceled: int
    orders_unresolved: int
    error_code: str | None
    updated_at: datetime


class CatalogResponse(BaseModel):
    revision: int
    active_pairs: list[tuple[str, str]]
    entries: list[CatalogPairView]
    mutations_enabled: bool


class PublicCatalogResponse(BaseModel):
    revision: int
    active_pairs: list[tuple[str, str]]


class CatalogMutation(BaseModel):
    base: str = Field(min_length=1, max_length=16)
    quote: str = Field(min_length=1, max_length=16)
    expected_revision: int = Field(ge=0)
    reason_code: CatalogReason

    @field_validator("base", "quote")
    @classmethod
    def normalize_asset(cls, value: str, info: ValidationInfo) -> str:
        try:
            symbol = Symbol(value, "USDT") if info.field_name == "base" else Symbol("BTC", value)
        except (TypeError, ValueError) as error:
            raise ValueError("CATALOG_SYMBOL_INVALID") from error
        return symbol.base if info.field_name == "base" else symbol.quote


class CatalogCommandResponse(BaseModel):
    command_id: UUID
    action: str
    base: str
    quote: str
    state: str
    revision: int | None
    created_at: datetime
    completed_at: datetime | None


class ProtocolEnableRequest(BaseModel):
    deployment_generation: UUID
    expected_revision: int = Field(ge=0)


class ImpactResponse(BaseModel):
    base: str
    quote: str
    bots: int
    open_entry_orders: int
    protective_orders: int
    reduce_risk_orders: int
    positions: int
    complete: bool
    snapshot_at: datetime


def _capability_source(request: Request) -> ExecutionCapabilitySource:
    source = getattr(request.app.state, "catalog_capability_source", None)
    if source is None or not hasattr(source, "capability"):
        raise RuntimeError("catalog capability source is not configured")
    return cast(ExecutionCapabilitySource, source)


def _catalog_response(view: CatalogView) -> CatalogResponse:
    return CatalogResponse(
        revision=view.snapshot.revision,
        active_pairs=sorted(view.snapshot.active_pairs),
        entries=[
            CatalogPairView(
                base=entry.base,
                quote=entry.quote,
                status=entry.status.value,
                revision=entry.revision,
                updated_at=entry.updated_at,
                cleanup=None
                if entry.effect is None
                else CatalogCleanupView(
                    status=entry.effect.status,
                    attempts=entry.effect.attempts,
                    bots_stopped=entry.effect.bots_stopped,
                    commands_rejected=entry.effect.commands_rejected,
                    orders_canceled=entry.effect.orders_canceled,
                    orders_unresolved=entry.effect.orders_unresolved,
                    error_code=entry.effect.error_code,
                    updated_at=entry.effect.updated_at,
                ),
            )
            for entry in view.entries
        ],
        mutations_enabled=view.mutations_enabled,
    )


def _command_response(command: CatalogCommand) -> CatalogCommandResponse:
    return CatalogCommandResponse(
        command_id=command.id,
        action=command.action.value,
        base=command.base,
        quote=command.quote,
        state=command.state,
        revision=command.revision,
        created_at=command.created_at,
        completed_at=command.completed_at,
    )


def _translate(error: InfraError) -> HTTPException:
    code = error.code
    status_code = {
        CatalogAuthorizationError.code: status.HTTP_403_FORBIDDEN,
        CatalogProtocolError.code: status.HTTP_503_SERVICE_UNAVAILABLE,
        CatalogRevisionConflictError.code: status.HTTP_409_CONFLICT,
        CatalogIdempotencyConflictError.code: status.HTTP_409_CONFLICT,
        CatalogStateError.code: status.HTTP_409_CONFLICT,
    }.get(code, status.HTTP_503_SERVICE_UNAVAILABLE)
    return HTTPException(status_code, code)


def _symbol(base: str, quote: str) -> Symbol:
    try:
        symbol = Symbol(base, quote)
    except (TypeError, ValueError):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "CATALOG_SYMBOL_INVALID"
        ) from None
    if symbol.quote != "USDT":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "CATALOG_QUOTE_INVALID")
    return symbol


def _idempotency_key(value: str) -> str:
    if not value.strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "IDEMPOTENCY_KEY_INVALID")
    return value


@router.get("/market-catalog")
async def catalog(
    request: Request, who: Annotated[Authenticated, Depends(current_user)]
) -> PublicCatalogResponse:
    async with user_session(engine_for(request, DatabaseRole.API), who.user_id) as session:
        view = await read_catalog(session)
    return PublicCatalogResponse(
        revision=view.snapshot.revision,
        active_pairs=sorted(view.snapshot.active_pairs),
    )


@router.get("/admin/supported-symbols")
async def admin_catalog(
    request: Request, who: Annotated[Authenticated, Depends(current_user)]
) -> CatalogResponse:
    async with user_session(engine_for(request, DatabaseRole.API), who.user_id) as session:
        if await role_for(session) is None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, CatalogAuthorizationError.code)
        return _catalog_response(await read_catalog(session))


@router.get("/admin/supported-symbols/{base}/{quote}/impact")
async def preview(
    base: str,
    quote: str,
    request: Request,
    who: Annotated[Authenticated, Depends(current_user)],
) -> ImpactResponse:
    symbol = _symbol(base, quote)
    async with user_session(engine_for(request, DatabaseRole.API), who.user_id) as session:
        try:
            found = await impact_preview(session, symbol.base, symbol.quote)
        except InfraError as error:
            raise _translate(error) from None
    return ImpactResponse(
        base=found.base,
        quote=found.quote,
        bots=found.bots,
        open_entry_orders=found.open_entry_orders,
        protective_orders=found.protective_orders,
        reduce_risk_orders=found.reduce_risk_orders,
        positions=found.positions,
        complete=found.complete,
        snapshot_at=found.snapshot_at,
    )


@router.post("/admin/supported-symbols", status_code=status.HTTP_202_ACCEPTED)
async def add_symbol(
    body: CatalogMutation,
    request: Request,
    who: Annotated[Authenticated, Depends(current_user)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128)],
) -> CatalogCommandResponse:
    if body.reason_code is not CatalogReason.LIQUIDITY_REVIEWED:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "CATALOG_REASON_INVALID")
    symbol = _symbol(body.base, body.quote)
    key = _idempotency_key(idempotency_key)
    async with user_session(engine_for(request, DatabaseRole.API), who.user_id) as session:
        if await role_for(session) is None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, CatalogAuthorizationError.code)
        try:
            replay = await replay_command(
                session,
                idempotency_key=key,
                action=CatalogAction.ADD,
                base=symbol.base,
                quote=symbol.quote,
                expected_revision=body.expected_revision,
                reason=body.reason_code,
            )
        except InfraError as error:
            raise _translate(error) from None
        if replay is not None:
            return _command_response(replay)
    started_at = datetime.now(UTC)
    try:
        capability = await _capability_source(request).capability(symbol)
    except (VenueRateLimitedError, VenueUnavailableError):
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "CATALOG_VENUE_UNAVAILABLE"
        ) from None
    except VenueError:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "CATALOG_VENUE_UNSUPPORTED"
        ) from None
    completed_at = datetime.now(UTC)
    if (
        capability.symbol != symbol
        or capability.observed_at < started_at
        or capability.observed_at > completed_at
        or capability.market.unsupported_rules
        or capability.limit.unsupported_rules
    ):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "CATALOG_VENUE_UNSUPPORTED")
    async with user_session(engine_for(request, DatabaseRole.API), who.user_id) as session:
        try:
            command = await request_add(
                session,
                command_id=uuid4(),
                idempotency_key=key,
                base=symbol.base,
                quote=symbol.quote,
                expected_revision=body.expected_revision,
                reason=body.reason_code,
                evidence=ConstraintEvidence(
                    venue_symbol=f"{symbol.base}{symbol.quote}",
                    observed_at=capability.observed_at,
                    source_document=capability.source_document,
                    digest=capability.version,
                ),
            )
        except InfraError as error:
            raise _translate(error) from None
    return _command_response(command)


@router.post("/admin/supported-symbols/protocol/enable", status_code=status.HTTP_204_NO_CONTENT)
async def enable_catalog_mutations(
    body: ProtocolEnableRequest,
    request: Request,
    who: Annotated[Authenticated, Depends(current_user)],
) -> None:
    async with user_session(engine_for(request, DatabaseRole.API), who.user_id) as session:
        try:
            await enable_mutations(
                session,
                deployment_generation=body.deployment_generation,
                expected_revision=body.expected_revision,
            )
        except InfraError as error:
            raise _translate(error) from None


@router.delete("/admin/supported-symbols/{base}/{quote}")
async def remove_symbol(
    base: str,
    quote: str,
    body: CatalogMutation,
    request: Request,
    who: Annotated[Authenticated, Depends(current_user)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128)],
) -> CatalogCommandResponse:
    if body.reason_code is not CatalogReason.RISK_REVIEW:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "CATALOG_REASON_INVALID")
    symbol = _symbol(base, quote)
    if (body.base, body.quote) != (symbol.base, symbol.quote):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "CATALOG_PAIR_MISMATCH")
    async with user_session(engine_for(request, DatabaseRole.API), who.user_id) as session:
        try:
            command = await request_remove(
                session,
                command_id=uuid4(),
                idempotency_key=_idempotency_key(idempotency_key),
                base=symbol.base,
                quote=symbol.quote,
                expected_revision=body.expected_revision,
                reason=body.reason_code,
            )
        except InfraError as error:
            raise _translate(error) from None
    return _command_response(command)
