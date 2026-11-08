"""Authenticated Paper-only protection intake and durable discovery."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request

from tiewtrade.core.money import Money, MoneyError, Quantity, align_quantity
from tiewtrade.core.orders import OrderError
from tiewtrade.core.positions import PositionPair
from tiewtrade.core.protections import (
    ProtectionPrices,
    ProtectionState,
    executable_protection_quantity,
)
from tiewtrade.infra.auth.throttle import Bucket
from tiewtrade.infra.db import DatabaseRole, InfraError, repeatable_user_session, user_session
from tiewtrade.infra.market_data.order_book_storage import read_latest_book
from tiewtrade.infra.protections.storage import admit_request, load, stored
from tiewtrade.infra.protections.worker import market_evidence
from tiewtrade.services.api.db_resources import engine_for, paper_mutation_engine
from tiewtrade.services.api.protection_models import (
    ProtectionCancelInput,
    ProtectionCreateInput,
    ProtectionPage,
    ProtectionReplaceInput,
    ProtectionRequestPage,
    ProtectionRequestView,
    ProtectionView,
)
from tiewtrade.services.api.request_identity import Authenticated, current_user
from tiewtrade.services.api.safe_input_routes import SafeInputRoute
from tiewtrade.services.api.throttling import spend_token


class ProtectionInputRoute(SafeInputRoute):
    rejection_code = "PROTECTION_INPUT_REJECTED"


router = APIRouter(prefix="/paper", tags=["protections"], route_class=ProtectionInputRoute)
Who = Annotated[Authenticated, Depends(current_user)]
Key = Annotated[UUID, Header(alias="Idempotency-Key")]


def refuse(error: OrderError | MoneyError | InfraError) -> HTTPException:
    if isinstance(error, MoneyError):
        return HTTPException(422, "PROTECTION_INPUT_REJECTED")
    if isinstance(error, OrderError):
        return HTTPException(
            409 if error.code in ("ORDER_CONFLICT", "PROTECTION_EPISODE_CLOSED") else 422,
            error.code,
        )
    return HTTPException(503, "PROTECTION_UNAVAILABLE")


def cursor_identity(value: str | None, owner: UUID, scope: str) -> UUID | None:
    if value is None:
        return None
    try:
        if len(value) > 160:
            raise ValueError("cursor too long")
        user, category, identity = value.split(":")
        if user != str(owner) or category != scope:
            raise ValueError("cursor scope mismatch")
        return UUID(identity)
    except ValueError:
        raise HTTPException(409, "PROTECTION_CURSOR_INVALID") from None


def make_cursor(owner: UUID, scope: str, identity: UUID) -> str:
    return f"{owner}:{scope}:{identity}"


def request_view(row: object) -> ProtectionRequestView:
    # Rows are decoded by the response model; no untrusted payload or DB errors escape.
    return ProtectionRequestView.model_validate(row, from_attributes=True)


_REQUEST = """SELECT q.id AS request_id,q.protection_id,q.episode_id,q.action,q.idempotency_key,
    coalesce(r.state,'PENDING') AS state,r.failure_code,clock_timestamp() AS snapshot_at
    FROM paper_protection_requests q LEFT JOIN paper_protection_results r ON r.request_id=q.id """


@router.get("/protection-requests/by-key/{key}")
async def lookup_key(
    key: UUID, action: Literal["CREATE", "REPLACE", "CANCEL"], request: Request, who: Who
) -> ProtectionRequestView:
    try:
        async with repeatable_user_session(
            engine_for(request, DatabaseRole.API), who.user_id
        ) as session:
            row = (
                await session.execute(
                    _REQUEST
                    + "WHERE q.user_id=:owner AND q.action=:action AND q.idempotency_key=:key",
                    {"owner": who.user_id, "action": action, "key": key},
                )
            ).one_or_none()
            if row is None:
                raise HTTPException(404, "PROTECTION_NOT_FOUND")
            return request_view(row)
    except (InfraError, OrderError, MoneyError) as error:
        raise refuse(error) from None


@router.get("/protection-requests/{request_id}")
async def lookup(request_id: UUID, request: Request, who: Who) -> ProtectionRequestView:
    try:
        async with repeatable_user_session(
            engine_for(request, DatabaseRole.API), who.user_id
        ) as session:
            row = (
                await session.execute(_REQUEST + "WHERE q.id=:id", {"id": request_id})
            ).one_or_none()
            if row is None:
                raise HTTPException(404, "PROTECTION_NOT_FOUND")
            return request_view(row)
    except (InfraError, OrderError, MoneyError) as error:
        raise refuse(error) from None


@router.get("/protection-requests")
async def discover(
    request: Request,
    who: Who,
    state: Literal["unresolved"] = "unresolved",
    cursor: str | None = Query(None, max_length=160),
    limit: int = Query(20, ge=1, le=100),
) -> ProtectionRequestPage:
    del state
    after = cursor_identity(cursor, who.user_id, "unresolved")
    try:
        async with repeatable_user_session(
            engine_for(request, DatabaseRole.API), who.user_id
        ) as session:
            rows = (
                await session.execute(
                    _REQUEST + "WHERE r.request_id IS NULL "
                    "AND (CAST(:cursor AS uuid) IS NULL OR q.id>CAST(:cursor AS uuid)) "
                    "ORDER BY q.id LIMIT :limit",
                    {"cursor": after, "limit": limit + 1},
                )
            ).all()
            return ProtectionRequestPage(
                requests=[request_view(r) for r in rows[:limit]],
                next_cursor=make_cursor(who.user_id, "unresolved", rows[limit - 1].request_id)
                if len(rows) > limit
                else None,
            )
    except (InfraError, OrderError, MoneyError) as error:
        raise refuse(error) from None


@router.get("/protections")
async def page(
    request: Request,
    who: Who,
    episode_id: UUID,
    cursor: str | None = Query(None, max_length=160),
    limit: int = Query(20, ge=1, le=100),
) -> ProtectionPage:
    after = cursor_identity(cursor, who.user_id, str(episode_id))
    try:
        async with repeatable_user_session(
            engine_for(request, DatabaseRole.API), who.user_id
        ) as session:
            rows = (
                await session.execute(
                    """SELECT g.*,clock_timestamp() AS snapshot_at,
                    x.order_id AS exit_order_id,x.quantity AS exit_quantity,
                    x.accounted AS exit_filled_quantity,x.status AS exit_order_state,
                    x.command_state AS exit_command_state
                FROM paper_protections g LEFT JOIN LATERAL (
                    SELECT e.order_id,e.quantity,s.accounted,p.status,
                        coalesce(r.state,'PENDING') AS command_state
                    FROM paper_protection_exits e
                    JOIN paper_protection_exit_progress s ON s.id=e.id
                    LEFT JOIN paper_order_projections p ON p.order_id=e.order_id
                    LEFT JOIN paper_order_command_results r ON r.command_id=e.command_id
                    WHERE e.protection_id=g.id
                    ORDER BY s.settled,r.completed_at DESC NULLS FIRST,e.id DESC LIMIT 1
                ) x ON true
                WHERE g.episode_id=:episode
                  AND (CAST(:cursor AS uuid) IS NULL OR g.id>CAST(:cursor AS uuid))
                ORDER BY g.id LIMIT :limit""",
                    {"episode": episode_id, "cursor": after, "limit": limit + 1},
                )
            ).all()
            output = []
            for row in rows[:limit]:
                group = stored(row)
                value = group.value
                ready = False
                executable = Quantity.of(0, value.prices.pair.base)
                residual = None
                try:
                    evidence = await market_evidence(session, value.prices.pair)
                    source = await read_latest_book(session, value.prices.pair)
                    residual = value.quantity - align_quantity(
                        value.quantity, source.metadata.market.quantity_step
                    )
                    ready = True
                    executable = executable_protection_quantity(
                        value,
                        source.metadata.market,
                        evidence,
                        filter_reference_price=source.metadata.average_price,
                    )
                except (OrderError, MoneyError):
                    pass
                if value.conflicted:
                    executable = Quantity.of(0, value.prices.pair.base)
                output.append(
                    ProtectionView(
                        protection_id=value.protection_id,
                        wallet_id=group.wallet_id,
                        episode_id=value.scope.episode_id,
                        base=value.prices.pair.base,
                        quantity=value.quantity.as_parts()["quantity"],
                        executable_quantity=executable.as_parts()["quantity"],
                        step_residual_quantity=None
                        if residual is None
                        else residual.as_parts()["quantity"],
                        protected_quantity=executable.as_parts()["quantity"]
                        if not value.conflicted and ready and value.state is ProtectionState.ARMED
                        else "0",
                        state=value.state.value,
                        revision=value.revision,
                        take_profit_price=None
                        if value.prices.take_profit is None
                        else value.prices.take_profit.as_parts()["amount"],
                        stop_loss_price=None
                        if value.prices.stop_loss is None
                        else value.prices.stop_loss.as_parts()["amount"],
                        entry_order_id=value.entry_order_id,
                        exit_order_id=row.exit_order_id,
                        exit_order_state=row.exit_order_state,
                        exit_command_state=row.exit_command_state,
                        exit_quantity=None
                        if row.exit_quantity is None
                        else Quantity.of(row.exit_quantity, value.prices.pair.base).as_parts()[
                            "quantity"
                        ],
                        exit_filled_quantity=None
                        if row.exit_filled_quantity is None
                        else Quantity.of(
                            row.exit_filled_quantity, value.prices.pair.base
                        ).as_parts()["quantity"],
                        conflicted=value.conflicted,
                        failure_code=group.failure_code,
                        market_ready=ready,
                        snapshot_at=row.snapshot_at.isoformat(),
                    )
                )
            return ProtectionPage(
                protections=output,
                next_cursor=make_cursor(who.user_id, str(episode_id), rows[limit - 1].id)
                if len(rows) > limit
                else None,
            )
    except (InfraError, OrderError, MoneyError) as error:
        raise refuse(error) from None


async def submit(
    body: ProtectionCreateInput | ProtectionReplaceInput | ProtectionCancelInput,
    action: str,
    target: UUID | None,
    key: UUID,
    request: Request,
    who: Authenticated,
) -> ProtectionRequestView:
    try:
        async with user_session(engine_for(request, DatabaseRole.API), who.user_id) as session:
            if target is not None:
                current = await load(session, target)
                if current is None or current.value.scope.episode_id != body.expected_episode_id:
                    raise HTTPException(404, "PROTECTION_NOT_FOUND")
                pair = current.value.prices.pair
            else:
                assert isinstance(body, ProtectionCreateInput)
                pair = PositionPair(body.base, "USDT")
            payload: dict[str, object] = {}
            if not isinstance(body, ProtectionCancelInput):
                levels = ProtectionPrices(
                    pair,
                    None
                    if body.take_profit_price is None
                    else Money.of(body.take_profit_price, pair.quote),
                    None
                    if body.stop_loss_price is None
                    else Money.of(body.stop_loss_price, pair.quote),
                )
                payload.update(
                    tp=None
                    if levels.take_profit is None
                    else levels.take_profit.as_parts()["amount"],
                    sl=None if levels.stop_loss is None else levels.stop_loss.as_parts()["amount"],
                    quantity=Quantity.of(body.quantity, pair.base).as_parts()["quantity"],
                )
            if isinstance(body, ProtectionCreateInput):
                payload["base"] = pair.base
            else:
                payload["expected_revision"] = body.expected_revision
            await spend_token(paper_mutation_engine(request), who.user_id, Bucket.PAPER_ORDER_NEW)
            request_id = await admit_request(
                session,
                wallet_id=body.expected_wallet_id,
                episode_id=body.expected_episode_id,
                action=action,
                key=key,
                protection_id=target,
                payload=payload,
            )
            row = (await session.execute(_REQUEST + "WHERE q.id=:id", {"id": request_id})).one()
            result = request_view(row)
        return result
    except (InfraError, OrderError, MoneyError) as error:
        raise refuse(error) from None


@router.post("/protections", status_code=202)
async def create_request(
    body: ProtectionCreateInput, request: Request, who: Who, idempotency_key: Key
) -> ProtectionRequestView:
    return await submit(body, "CREATE", None, idempotency_key, request, who)


@router.post("/protections/{protection_id}/replace", status_code=202)
async def replace_request(
    protection_id: UUID,
    body: ProtectionReplaceInput,
    request: Request,
    who: Who,
    idempotency_key: Key,
) -> ProtectionRequestView:
    return await submit(body, "REPLACE", protection_id, idempotency_key, request, who)


@router.post("/protections/{protection_id}/cancel", status_code=202)
async def cancel_request(
    protection_id: UUID,
    body: ProtectionCancelInput,
    request: Request,
    who: Who,
    idempotency_key: Key,
) -> ProtectionRequestView:
    return await submit(body, "CANCEL", protection_id, idempotency_key, request, who)
