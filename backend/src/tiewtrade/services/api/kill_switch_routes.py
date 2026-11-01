"""Owner and platform kill-switch HTTP composition."""

import os
from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query, Request, Response

from tiewtrade.core.orders import TradingMode
from tiewtrade.core.trading_stops import StopAction
from tiewtrade.infra.auth.throttle import Bucket
from tiewtrade.infra.db import DatabaseRole, InfraError, repeatable_user_session, user_session
from tiewtrade.infra.platform import PlatformRole, role_for
from tiewtrade.infra.risk_limits.records import RiskConflictError
from tiewtrade.infra.risk_limits.stop_views import effect_page
from tiewtrade.infra.trading_stops import (
    read_status,
    receipt_by_id,
    receipt_by_key,
    submit_request,
)
from tiewtrade.infra.trading_stops.records import StopConflictError, StopReceipt, StopStatus
from tiewtrade.services.api.db_resources import engine_for, paper_mutation_engine
from tiewtrade.services.api.kill_switch_models import (
    KillSwitchStatusView,
    OwnerStopCause,
    PlatformStatusView,
    PlatformStopInput,
    ResumeStopInput,
    StopInput,
    StopRequestView,
    StopSummaryView,
)
from tiewtrade.services.api.request_identity import Authenticated, current_user
from tiewtrade.services.api.risk_limit_models import RiskEffectPage
from tiewtrade.services.api.safe_input_routes import SafeInputRoute
from tiewtrade.services.api.throttling import spend_token


class StopInputRoute(SafeInputRoute):
    rejection_code = "TRADING_STOP_INPUT_INVALID"


router = APIRouter(tags=["kill-switch"], route_class=StopInputRoute)
Who = Annotated[Authenticated, Depends(current_user)]
Key = Annotated[UUID, Header(alias="Idempotency-Key")]


def _require_authority_enabled() -> None:
    # Deployment enables this only after every order writer understands the
    # historical stop revisions introduced by migration 0061.
    if os.environ.get("TIEWTRADE_TRADING_STOP_AUTHORITY_ENABLED") != "1":
        raise HTTPException(503, "TRADING_STOP_UNAVAILABLE")


def _mode(request: Request) -> TradingMode:
    return TradingMode.PAPER if request.url.path.startswith("/paper/") else TradingMode.LIVE


def _request_view(receipt: StopReceipt) -> StopRequestView:
    return StopRequestView(
        request_id=receipt.request_id,
        stop_id=receipt.stop_id,
        mode="PLATFORM" if receipt.mode is None else receipt.mode.value,
        action=receipt.action.value,
        cause=receipt.cause.value,
        generation=receipt.generation,
        revision=receipt.revision,
        state=receipt.state,  # type: ignore[arg-type]
        failure_code=receipt.failure_code,
        recorded_at=receipt.recorded_at.isoformat(),
    )


def _status_view(status: StopStatus, mode: TradingMode) -> KillSwitchStatusView:
    return KillSwitchStatusView(
        mode=mode.value,
        stop_id=status.stop_id,
        cause=None if status.cause is None else status.cause.value,
        generation=status.generation,
        revision=status.revision,
        summary_revision=status.summary_revision,
        progress=None if status.progress is None else status.progress.value,
        target_set_complete=status.target_set_complete,
        target_count=status.target_count,
        pending_count=status.pending_count,
        failed_count=status.failed_count,
        platform_stop_id=status.platform_stop_id,
        platform_reason=status.platform_reason,
        resume_ready=status.resume_ready if mode is TradingMode.PAPER else False,
        reconciliation_revision=status.reconciliation_revision,
        capability="AVAILABLE" if mode is TradingMode.PAPER else "LIVE_EXECUTION_UNAVAILABLE",
        active_causes=[cast(OwnerStopCause, cause.value) for cause in status.active_causes],
    )


async def _submit(
    *,
    request: Request,
    response: Response,
    who: Authenticated,
    key: UUID,
    mode: TradingMode | None,
    action: StopAction,
    reason_code: str,
    expected_stop_id: UUID | None = None,
    expected_revision: int | None = None,
    expected_summary_revision: int | None = None,
    expected_reconciliation_revision: int | None = None,
    reason_text: str | None = None,
    platform: bool = False,
) -> StopRequestView:
    async with user_session(engine_for(request, DatabaseRole.API), who.user_id) as session:
        previous = await receipt_by_key(session, mode=mode, action=action, key=key)
        if previous is None:
            await spend_token(
                paper_mutation_engine(request), who.user_id, Bucket.TRADING_STOP_MUTATION
            )
        receipt = await submit_request(
            session,
            mode=mode,
            action=action,
            key=key,
            expected_stop_id=expected_stop_id,
            expected_revision=expected_revision,
            expected_summary_revision=expected_summary_revision,
            expected_reconciliation_revision=expected_reconciliation_revision,
            reason_code=reason_code,
            reason_text=reason_text,
            platform=platform,
        )
    response.status_code = 200 if previous is not None else 202
    return _request_view(receipt)


@router.get("/paper/kill-switch", response_model=KillSwitchStatusView)
@router.get("/live/kill-switch", response_model=KillSwitchStatusView)
async def status(request: Request, who: Who) -> KillSwitchStatusView:
    mode = _mode(request)
    try:
        async with repeatable_user_session(
            engine_for(request, DatabaseRole.API), who.user_id
        ) as session:
            value = await read_status(session, mode)
        return _status_view(value, mode)
    except InfraError:
        raise HTTPException(503, "TRADING_STOP_UNAVAILABLE") from None


@router.post("/paper/kill-switch/stop", response_model=StopRequestView, status_code=202)
@router.post("/live/kill-switch/stop", response_model=StopRequestView, status_code=202)
async def stop(
    request: Request,
    response: Response,
    who: Who,
    key: Key,
    _body: Annotated[StopInput | None, Body()] = None,
) -> StopRequestView:
    _require_authority_enabled()
    mode = _mode(request)
    try:
        return await _submit(
            request=request,
            response=response,
            who=who,
            key=key,
            mode=mode,
            action=StopAction.STOP,
            reason_code="USER_REQUEST",
        )
    except StopConflictError:
        raise HTTPException(409, "TRADING_STOP_IDEMPOTENCY_CONFLICT") from None
    except InfraError:
        raise HTTPException(503, "TRADING_STOP_UNAVAILABLE") from None


@router.post("/paper/kill-switch/resume", response_model=StopRequestView, status_code=202)
@router.post("/live/kill-switch/resume", response_model=StopRequestView, status_code=202)
async def resume(
    body: ResumeStopInput, request: Request, response: Response, who: Who, key: Key
) -> StopRequestView:
    _require_authority_enabled()
    mode = _mode(request)
    try:
        return await _submit(
            request=request,
            response=response,
            who=who,
            key=key,
            mode=mode,
            action=StopAction.RESUME,
            expected_stop_id=body.expected_stop_id,
            expected_revision=body.expected_revision,
            expected_summary_revision=body.expected_summary_revision,
            expected_reconciliation_revision=body.expected_reconciliation_revision,
            reason_code="USER_RESUME",
        )
    except StopConflictError:
        raise HTTPException(409, "TRADING_STOP_IDEMPOTENCY_CONFLICT") from None
    except InfraError:
        raise HTTPException(503, "TRADING_STOP_UNAVAILABLE") from None


@router.get("/paper/kill-switch/requests/by-key/{key}", response_model=StopRequestView)
@router.get("/live/kill-switch/requests/by-key/{key}", response_model=StopRequestView)
async def request_by_key(
    key: UUID, action: StopAction, request: Request, who: Who
) -> StopRequestView:
    try:
        async with repeatable_user_session(
            engine_for(request, DatabaseRole.API), who.user_id
        ) as session:
            receipt = await receipt_by_key(session, mode=_mode(request), action=action, key=key)
        if receipt is None:
            raise HTTPException(404, "TRADING_STOP_REQUEST_NOT_FOUND")
        return _request_view(receipt)
    except InfraError:
        raise HTTPException(503, "TRADING_STOP_UNAVAILABLE") from None


@router.get("/paper/kill-switch/requests/{request_id}", response_model=StopRequestView)
@router.get("/live/kill-switch/requests/{request_id}", response_model=StopRequestView)
async def request_by_id(request_id: UUID, request: Request, who: Who) -> StopRequestView:
    try:
        async with repeatable_user_session(
            engine_for(request, DatabaseRole.API), who.user_id
        ) as session:
            receipt = await receipt_by_id(session, request_id)
        if receipt is None or receipt.mode is not _mode(request):
            raise HTTPException(404, "TRADING_STOP_REQUEST_NOT_FOUND")
        return _request_view(receipt)
    except InfraError:
        raise HTTPException(503, "TRADING_STOP_UNAVAILABLE") from None


@router.get("/paper/kill-switch/stops/{stop_id}/effects", response_model=RiskEffectPage)
@router.get("/live/kill-switch/stops/{stop_id}/effects", response_model=RiskEffectPage)
async def effects(
    stop_id: UUID,
    request: Request,
    who: Who,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    state_filter: Annotated[Literal["ALL", "PENDING", "FAILED"], Query(alias="filter")] = "ALL",
) -> RiskEffectPage:
    try:
        async with repeatable_user_session(
            engine_for(request, DatabaseRole.API), who.user_id
        ) as session:
            page = await effect_page(
                session,
                _mode(request),
                stop_id,
                cursor=cursor,
                limit=limit,
                state_filter=state_filter,
            )
        if page is None:
            raise HTTPException(404, "TRADING_STOP_NOT_FOUND")
        return RiskEffectPage.model_validate(page)
    except RiskConflictError:
        raise HTTPException(422, "TRADING_STOP_EFFECT_CURSOR_INVALID") from None
    except InfraError:
        raise HTTPException(503, "TRADING_STOP_UNAVAILABLE") from None


@router.get("/paper/kill-switch/stops/{stop_id}/resume-summary", response_model=StopSummaryView)
@router.get("/live/kill-switch/stops/{stop_id}/resume-summary", response_model=StopSummaryView)
async def resume_summary(stop_id: UUID, request: Request, who: Who) -> StopSummaryView:
    mode = _mode(request)
    try:
        async with repeatable_user_session(
            engine_for(request, DatabaseRole.API), who.user_id
        ) as session:
            value = await read_status(session, mode)
            if value.stop_id != stop_id:
                raise HTTPException(404, "TRADING_STOP_NOT_FOUND")
            positions = []
            reconciled_at = None
            if mode is TradingMode.PAPER:
                rows = await session.execute(
                    """SELECT p.base,p.quote,p.held_quantity::text quantity
                  FROM paper_position_projections p JOIN paper_wallet_state w
                    ON w.active_episode_id=p.episode_id AND w.user_id=p.user_id
                  WHERE p.held_quantity<>0 ORDER BY p.base,p.quote"""
                )
                positions = [
                    {"base": str(row.base), "quote": str(row.quote), "quantity": str(row.quantity)}
                    for row in rows
                ]
                reconciled_at = (
                    await session.execute(
                        """SELECT a.observed_at FROM paper_wallet_state w
                        LEFT JOIN paper_position_activity a ON a.episode_id=w.active_episode_id
                        WHERE w.user_id=:owner""",
                        {"owner": who.user_id},
                    )
                ).scalar_one_or_none()
        return StopSummaryView(
            status=_status_view(value, mode),
            positions=positions,
            snapshot_revision=value.summary_revision,
            reconciled_at=None if reconciled_at is None else reconciled_at.isoformat(),
        )
    except InfraError:
        raise HTTPException(503, "TRADING_STOP_UNAVAILABLE") from None


async def _platform_role(request: Request, who: Authenticated) -> PlatformRole:
    try:
        async with user_session(engine_for(request, DatabaseRole.API), who.user_id) as session:
            role = await role_for(session)
    except InfraError:
        raise HTTPException(503, "TRADING_STOP_UNAVAILABLE") from None
    if role is None:
        raise HTTPException(403, "PLATFORM_NOT_AUTHORIZED")
    return role


@router.get("/admin/kill-switch", response_model=PlatformStatusView)
async def platform_status(request: Request, who: Who) -> PlatformStatusView:
    role = await _platform_role(request, who)
    try:
        async with repeatable_user_session(
            engine_for(request, DatabaseRole.API), who.user_id
        ) as session:
            row = (
                await session.execute(
                    """WITH latest AS (SELECT * FROM trading_stop_requests
              WHERE cause='PLATFORM' AND action='STOP' ORDER BY revision DESC LIMIT 1)
            SELECT s.id,s.revision,s.reason_text,p.discovery_complete,p.owner_count,
              p.pending_count,p.failed_count,p.revision progress_revision,
              p.reconciliation_revision,
              (p.reconciliation_revision=(SELECT revision
                FROM trading_reconciliation_clock WHERE singleton)) snapshot_current,
              EXISTS(SELECT 1 FROM trading_stop_requests r JOIN trading_stop_results x
                ON x.request_id=r.id AND x.state='APPLIED'
                WHERE r.action='RESUME' AND r.expected_stop_id=s.id) resumed
            FROM latest s LEFT JOIN platform_stop_progress p ON p.stop_id=s.id"""
                )
            ).one_or_none()
    except InfraError:
        raise HTTPException(503, "TRADING_STOP_UNAVAILABLE") from None
    if row is None or row.resumed:
        return PlatformStatusView(
            stop_id=None,
            revision=0,
            summary_revision=0,
            reconciliation_revision=0,
            reason=None,
            progress=None,
            discovery_complete=False,
            owner_count=0,
            pending_count=0,
            failed_count=0,
            can_resume=False,
        )
    complete = bool(row.discovery_complete and row.snapshot_current)
    pending = int(row.pending_count or 0)
    failed = int(row.failed_count or 0)
    progress = "PROBLEMS" if failed else "STOPPED" if complete and pending == 0 else "STOPPING"
    return PlatformStatusView(
        stop_id=row.id,
        revision=int(row.revision),
        summary_revision=int(row.progress_revision or 0),
        reconciliation_revision=int(row.reconciliation_revision or 0),
        reason=row.reason_text,
        progress=progress,  # type: ignore[arg-type]
        discovery_complete=complete,
        owner_count=int(row.owner_count or 0),
        pending_count=pending,
        failed_count=failed,
        can_resume=bool(role is PlatformRole.OWNER and complete and pending == 0 and failed == 0),
    )


@router.get("/admin/kill-switch/requests/{request_id}", response_model=StopRequestView)
async def platform_request_by_id(request_id: UUID, request: Request, who: Who) -> StopRequestView:
    await _platform_role(request, who)
    try:
        async with repeatable_user_session(
            engine_for(request, DatabaseRole.API), who.user_id
        ) as session:
            receipt = await receipt_by_id(session, request_id)
        if receipt is None or receipt.mode is not None:
            raise HTTPException(404, "TRADING_STOP_REQUEST_NOT_FOUND")
        return _request_view(receipt)
    except InfraError:
        raise HTTPException(503, "TRADING_STOP_UNAVAILABLE") from None


@router.post("/admin/kill-switch/stop", response_model=StopRequestView, status_code=202)
async def platform_stop(
    body: PlatformStopInput, request: Request, response: Response, who: Who, key: Key
) -> StopRequestView:
    _require_authority_enabled()
    await _platform_role(request, who)
    try:
        return await _submit(
            request=request,
            response=response,
            who=who,
            key=key,
            mode=None,
            action=StopAction.STOP,
            reason_code="PLATFORM_INCIDENT",
            reason_text=body.reason,
            platform=True,
        )
    except StopConflictError:
        raise HTTPException(409, "TRADING_STOP_IDEMPOTENCY_CONFLICT") from None
    except InfraError:
        raise HTTPException(503, "TRADING_STOP_UNAVAILABLE") from None


@router.post("/admin/kill-switch/resume", response_model=StopRequestView, status_code=202)
async def platform_resume(
    body: ResumeStopInput, request: Request, response: Response, who: Who, key: Key
) -> StopRequestView:
    _require_authority_enabled()
    role = await _platform_role(request, who)
    if role is not PlatformRole.OWNER:
        raise HTTPException(403, "PLATFORM_OWNER_REQUIRED")
    try:
        return await _submit(
            request=request,
            response=response,
            who=who,
            key=key,
            mode=None,
            action=StopAction.RESUME,
            expected_stop_id=body.expected_stop_id,
            expected_revision=body.expected_revision,
            expected_summary_revision=body.expected_summary_revision,
            expected_reconciliation_revision=body.expected_reconciliation_revision,
            reason_code="PLATFORM_RESUME",
            platform=True,
        )
    except StopConflictError:
        raise HTTPException(409, "TRADING_STOP_IDEMPOTENCY_CONFLICT") from None
    except InfraError:
        raise HTTPException(503, "TRADING_STOP_UNAVAILABLE") from None
