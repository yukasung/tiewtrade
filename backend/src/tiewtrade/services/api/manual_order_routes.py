"""Authenticated Paper-only inbox admission and exact owner snapshots."""

from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response

from tiewtrade.core.money import MoneyError
from tiewtrade.core.orders import (
    AdmissionPolicy,
    OrderConflictError,
    OrderError,
    SafetyUnavailableError,
)
from tiewtrade.core.positions import PositionPair
from tiewtrade.infra.auth.throttle import Bucket
from tiewtrade.infra.db import DatabaseRole, InfraError, repeatable_user_session, user_session
from tiewtrade.infra.paper_orders.requests import (
    RequestIntegrityError,
    admit_cancel_request,
    admit_new_request,
    get_request_by_key,
    inspect_cancel_request,
    inspect_new_request,
)
from tiewtrade.infra.paper_orders.trade_views import order_page, order_view, trade_snapshot
from tiewtrade.infra.paper_orders.views import RequestView, request_view, unresolved_requests
from tiewtrade.services.api.db_resources import engine_for, paper_mutation_engine
from tiewtrade.services.api.manual_order_models import (
    ExpectedPaperEpisode,
    ManualOrderRefusal,
    ManualOrderSummary,
    ManualRequestPage,
    ManualRequestView,
    NewOrderInput,
    OrderCommandSnapshot,
    PaperOrderPage,
    PaperOrderView,
    PaperTradeView,
    manual_intent,
)
from tiewtrade.services.api.request_identity import Authenticated, current_user
from tiewtrade.services.api.safe_input_routes import SafeInputRoute
from tiewtrade.services.api.throttling import spend_token


class ManualInputRoute(SafeInputRoute):
    rejection_code = "MANUAL_ORDER_INPUT_REJECTED"


router = APIRouter(
    prefix="/paper",
    tags=["manual-orders"],
    route_class=ManualInputRoute,
    responses={code: {"model": ManualOrderRefusal} for code in (401, 403, 404, 409, 422, 429, 503)},
)
Who = Annotated[Authenticated, Depends(current_user)]
Key = Annotated[UUID, Header(alias="Idempotency-Key")]


def manual_admission_policy() -> AdmissionPolicy | None:
    """Production remains closed until approved F-18 integration. No env bypass."""
    return None


Policy = Annotated[AdmissionPolicy | None, Depends(manual_admission_policy)]


def _http_error(error: InfraError | OrderError | MoneyError) -> HTTPException:
    if isinstance(error, (InfraError, RequestIntegrityError, MoneyError)):
        return HTTPException(503, "MANUAL_ORDER_DEPENDENCY_UNAVAILABLE")
    if isinstance(error, SafetyUnavailableError):
        return HTTPException(503, error.code)
    if isinstance(error, OrderConflictError):
        return HTTPException(409, error.code)
    return HTTPException(
        422, error.code if isinstance(error, OrderError) else "MANUAL_ORDER_INPUT_REJECTED"
    )


async def _spend_order_token(request: Request, who: Authenticated, bucket: Bucket) -> None:
    try:
        await spend_token(paper_mutation_engine(request), who.user_id, bucket)
    except HTTPException as error:
        if error.status_code == 429:
            raise HTTPException(429, "MANUAL_ORDER_RATE_LIMITED", headers=error.headers) from None
        raise


def _view(value: RequestView) -> ManualRequestView:
    item = value.request
    payload = item.payload
    summary = (
        None
        if item.action == "CANCEL"
        else ManualOrderSummary(
            base=payload["base"],
            quote=payload["quote"],
            side=payload["side"],
            kind=payload["kind"],
            quote_budget=payload["budget"],
            base_quantity=payload["quantity"],
            limit_price=payload["limit"],
            time_in_force=payload["tif"],
        )
    )
    return ManualRequestView(
        request_id=item.request_id,
        wallet_id=item.wallet_id,
        episode_id=item.episode_id,
        order_id=item.order_id,
        action=item.action,
        idempotency_key=item.idempotency_key,
        request_summary=summary,
        recorded_at=item.recorded_at.isoformat(),
        intake_state=value.intake_state,
        intake_failure_code=value.intake_failure_code,
        command_id=value.command_id,
        command_state=value.command_state,
        command_failure_code=value.command_failure_code,
        command_snapshot=None
        if value.command_snapshot is None
        else OrderCommandSnapshot.model_validate(value.command_snapshot),
        order_state=value.order_state,
        snapshot_at=value.snapshot_at.isoformat(),
        status_url=f"/paper/order-requests/{item.request_id}",
    )


@router.get("/trade")
async def read_trade(
    request: Request,
    who: Who,
    policy: Policy,
    base: str | None = Query(default=None, pattern=r"^[A-Z][A-Z0-9]{0,19}$"),
) -> PaperTradeView:
    if base == "USDT":
        raise HTTPException(422, "MANUAL_ORDER_INPUT_REJECTED")
    try:
        async with repeatable_user_session(
            engine_for(request, DatabaseRole.API), who.user_id
        ) as session:
            value = await trade_snapshot(
                session,
                risk_policy_available=policy is not None,
                pair=None if base is None else PositionPair(base, "USDT"),
            )
        return PaperTradeView.model_validate(value)
    except (InfraError, OrderError, MoneyError) as error:
        raise _http_error(error) from None


@router.get("/order-requests")
async def read_unresolved(
    request: Request,
    who: Who,
    state: Literal["unresolved"] = "unresolved",
    cursor: str | None = Query(default=None, max_length=512),
    limit: int = Query(default=20, ge=1, le=100),
) -> ManualRequestPage:
    del state
    try:
        async with repeatable_user_session(
            engine_for(request, DatabaseRole.API), who.user_id
        ) as session:
            page = await unresolved_requests(session, cursor=cursor, limit=limit)
            return ManualRequestPage(
                requests=[_view(v) for v in page.requests], next_cursor=page.next_cursor
            )
    except (InfraError, OrderError) as error:
        raise _http_error(error) from None


# Static by-key route precedes the UUID lookup route.
@router.get("/order-requests/by-key/{key}")
async def read_request_key(
    key: UUID, action: Literal["NEW", "CANCEL"], request: Request, who: Who
) -> ManualRequestView:
    try:
        async with repeatable_user_session(
            engine_for(request, DatabaseRole.API), who.user_id
        ) as session:
            receipt = await get_request_by_key(session, action=action, key=key)
            value = None if receipt is None else await request_view(session, receipt.request_id)
            if value is None:
                raise HTTPException(404, "MANUAL_REQUEST_NOT_FOUND")
            return _view(value)
    except (InfraError, OrderError) as error:
        raise _http_error(error) from None


@router.get("/order-requests/{request_id}")
async def read_request(request_id: UUID, request: Request, who: Who) -> ManualRequestView:
    try:
        async with repeatable_user_session(
            engine_for(request, DatabaseRole.API), who.user_id
        ) as session:
            value = await request_view(session, request_id)
            if value is None:
                raise HTTPException(404, "MANUAL_REQUEST_NOT_FOUND")
            return _view(value)
    except (InfraError, OrderError) as error:
        raise _http_error(error) from None


@router.post("/orders", status_code=202)
async def new_order(
    body: NewOrderInput,
    response: Response,
    request: Request,
    who: Who,
    idempotency_key: Key,
    policy: Policy,
) -> ManualRequestView:
    try:
        intent = manual_intent(
            body, owner_id=who.user_id, order_id=uuid4(), idempotency_key=idempotency_key
        )
    except (MoneyError, OrderError):
        raise HTTPException(422, "MANUAL_ORDER_INPUT_REJECTED") from None
    try:
        async with user_session(engine_for(request, DatabaseRole.API), who.user_id) as session:
            await session.execute("SET LOCAL statement_timeout='5s'")
            await session.execute("SET LOCAL lock_timeout='5s'")
            receipt = await inspect_new_request(
                session, wallet_id=body.expected_wallet_id, intent=intent
            )
            if receipt is None:
                if policy is None:
                    raise HTTPException(503, "ORDER_SAFETY_UNAVAILABLE")
                await _spend_order_token(request, who, Bucket.PAPER_ORDER_NEW)
                receipt = await admit_new_request(
                    session, wallet_id=body.expected_wallet_id, intent=intent
                )
            else:
                response.status_code = 200
            value = await request_view(session, receipt.request_id)
            if value is None:
                raise RequestIntegrityError("committed request unavailable")
            result = _view(value)
        return result
    except (InfraError, OrderError, MoneyError) as error:
        raise _http_error(error) from None


@router.post("/orders/{order_id}/cancel", status_code=202)
async def cancel_order(
    order_id: UUID,
    body: ExpectedPaperEpisode,
    response: Response,
    request: Request,
    who: Who,
    idempotency_key: Key,
) -> ManualRequestView:
    try:
        async with user_session(engine_for(request, DatabaseRole.API), who.user_id) as session:
            await session.execute("SET LOCAL statement_timeout='5s'")
            await session.execute("SET LOCAL lock_timeout='5s'")
            receipt = await inspect_cancel_request(
                session,
                wallet_id=body.expected_wallet_id,
                episode_id=body.expected_episode_id,
                order_id=order_id,
                key=idempotency_key,
            )
            if receipt is None:
                owned = await order_view(session, order_id)
                if owned is None:
                    raise HTTPException(404, "PAPER_ORDER_NOT_FOUND")
                await _spend_order_token(request, who, Bucket.PAPER_ORDER_CANCEL)
                receipt = await admit_cancel_request(
                    session,
                    wallet_id=body.expected_wallet_id,
                    episode_id=body.expected_episode_id,
                    order_id=order_id,
                    idempotency_key=idempotency_key,
                )
            else:
                response.status_code = 200
            value = await request_view(session, receipt.request_id)
            if value is None:
                raise RequestIntegrityError("committed request unavailable")
            result = _view(value)
        return result
    except (InfraError, OrderError) as error:
        raise _http_error(error) from None


@router.get("/orders")
async def read_orders(
    request: Request,
    who: Who,
    episode_id: UUID,
    cursor: str | None = Query(default=None, max_length=128),
    limit: int = Query(default=20, ge=1, le=100),
) -> PaperOrderPage:
    try:
        async with repeatable_user_session(
            engine_for(request, DatabaseRole.API), who.user_id
        ) as session:
            page = await order_page(session, episode_id=episode_id, cursor=cursor, limit=limit)
            return PaperOrderPage.model_validate(page)
    except (InfraError, OrderError, MoneyError) as error:
        raise _http_error(error) from None


@router.get("/orders/{order_id}")
async def read_order(order_id: UUID, request: Request, who: Who) -> PaperOrderView:
    try:
        async with repeatable_user_session(
            engine_for(request, DatabaseRole.API), who.user_id
        ) as session:
            value = await order_view(session, order_id)
            if value is None:
                raise HTTPException(404, "PAPER_ORDER_NOT_FOUND")
            return PaperOrderView.model_validate(value)
    except (InfraError, OrderError, MoneyError) as error:
        raise _http_error(error) from None
