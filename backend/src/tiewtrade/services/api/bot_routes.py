"""Owner-scoped bot status and durable receipt recovery."""

from datetime import datetime
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response

from tiewtrade.core.money import Quantity
from tiewtrade.core.orders import TradingMode
from tiewtrade.infra.auth.throttle import Bucket
from tiewtrade.infra.bots.requests import (
    BotReceipt,
    BotRequestConflictError,
    receipt_by_id,
    receipt_by_key,
    submit_start,
)
from tiewtrade.infra.db import DatabaseRole, InfraError, repeatable_user_session, user_session
from tiewtrade.infra.positions.views import ready_position_metadata
from tiewtrade.infra.protections.storage import stored
from tiewtrade.services.api.bot_models import (
    BotPositionView,
    BotProtectionView,
    BotReceiptView,
    BotStartInput,
    BotStatusView,
)
from tiewtrade.services.api.db_resources import engine_for, paper_mutation_engine
from tiewtrade.services.api.request_identity import Authenticated, current_user
from tiewtrade.services.api.safe_input_routes import SafeInputRoute
from tiewtrade.services.api.throttling import spend_token


class BotInputRoute(SafeInputRoute):
    rejection_code = "BOT_INPUT_INVALID"


router = APIRouter(tags=["bots"], route_class=BotInputRoute)
Who = Annotated[Authenticated, Depends(current_user)]
Key = Annotated[UUID, Header(alias="Idempotency-Key")]


def _mode(request: Request) -> TradingMode:
    return TradingMode.PAPER if request.url.path.startswith("/paper/") else TradingMode.LIVE


def _unavailable(mode: TradingMode) -> str:
    return "BOT_STRATEGY_UNAVAILABLE" if mode is TradingMode.PAPER else "LIVE_EXECUTION_UNAVAILABLE"


def _receipt(value: BotReceipt | None) -> BotReceiptView:
    if value is None:
        raise HTTPException(404, "BOT_REQUEST_NOT_FOUND")
    return BotReceiptView(
        request_id=value.request_id,
        mode=value.mode,
        key=value.key,
        run_id=value.run_id,
        failure_code=value.failure_code,
        pending=value.pending,
    )


@router.get("/paper/bots/status", response_model=BotStatusView)
@router.get("/live/bots/status", response_model=BotStatusView)
async def status(request: Request, who: Who) -> BotStatusView:
    mode = _mode(request)
    exposure_available = False
    positions: list[BotPositionView] = []
    protections: list[BotProtectionView] = []
    protections_more = False
    try:
        async with repeatable_user_session(
            engine_for(request, DatabaseRole.API), who.user_id
        ) as session:
            snapshot_at: datetime = (
                await session.execute("SELECT transaction_timestamp()")
            ).scalar_one()
            pending_request_id = (
                await session.execute(
                    """SELECT r.id FROM bot_control_requests r
                       WHERE r.user_id=:owner AND r.mode=:mode AND NOT EXISTS (
                         SELECT 1 FROM bot_control_results x
                         WHERE x.request_id=r.id AND x.user_id=r.user_id AND x.mode=r.mode)
                       ORDER BY r.requested_at DESC,r.id DESC LIMIT 1""",
                    {"owner": who.user_id, "mode": mode.value},
                )
            ).scalar_one_or_none()
            run = (
                await session.execute(
                    """SELECT r.id,r.status,r.revision,r.strategy_name,r.strategy_version,
                              r.configuration_version, s.reason,
                              CASE WHEN r.status IN ('PAUSED','STARTING','RECOVERING') THEN (
                                SELECT e.details->>'reason' FROM bot_run_events e
                                WHERE e.run_id=r.id AND e.user_id=r.user_id AND e.mode=r.mode
                                ORDER BY e.revision DESC LIMIT 1) END AS readiness_reason
                       FROM bot_runs r LEFT JOIN LATERAL (
                           SELECT CASE WHEN e.event IN ('PROTECTION_SETUP_FAILED','CATALOG_REMOVED')
                                 THEN e.event
                               WHEN e.event IN
                                 ('STRATEGY_VERSION_UNAVAILABLE','STRATEGY_EVALUATION_FAILED')
                                 THEN 'SYSTEM' ELSE e.details->>'cause' END AS reason
                           FROM bot_run_events e WHERE e.run_id=r.id AND e.user_id=r.user_id
                             AND e.mode=r.mode AND e.event IN
                               ('TRADING_STOP','PROTECTION_SETUP_FAILED','CATALOG_REMOVED',
                                'STRATEGY_VERSION_UNAVAILABLE','STRATEGY_EVALUATION_FAILED')
                           ORDER BY e.revision DESC LIMIT 1
                       ) s ON r.status='STOPPED'
                       WHERE r.user_id=:owner AND r.mode=:mode AND r.status<>'RETIRED'""",
                    {"owner": who.user_id, "mode": mode.value},
                )
            ).one_or_none()
            if (run is not None or pending_request_id is not None) and mode is TradingMode.PAPER:
                episode = (
                    await session.execute(
                        "SELECT active_episode_id FROM paper_wallet_state WHERE user_id=:owner",
                        {"owner": who.user_id},
                    )
                ).scalar_one_or_none()
                if episode is not None:
                    exposure_available = await ready_position_metadata(session, episode) is not None
                    if exposure_available:
                        rows = await session.execute(
                            """SELECT base,quote,held_quantity FROM paper_position_projections
                               WHERE episode_id=:episode AND held_quantity<>0
                               ORDER BY base,quote""",
                            {"episode": episode},
                        )
                        positions = [
                            BotPositionView(
                                base=row.base,
                                quote=row.quote,
                                quantity=Quantity.of(row.held_quantity, row.base).as_parts()[
                                    "quantity"
                                ],
                            )
                            for row in rows
                        ]
                    groups = await session.execute(
                        """SELECT *
                           FROM paper_protections WHERE episode_id=:episode AND quantity>0
                           ORDER BY CASE WHEN state='FAILED' OR document->>'conflicted'='true'
                              THEN 0 WHEN state IN ('ARMING','EXITING') THEN 1 ELSE 2 END,
                              base,id LIMIT 21""",
                        {"episode": episode},
                    )
                    group_rows = groups.all()
                    protections_more = len(group_rows) > 20
                    protections = [
                        BotProtectionView(
                            protection_id=group.value.protection_id,
                            base=group.value.prices.pair.base,
                            quantity=group.value.quantity.as_parts()["quantity"],
                            state=group.value.state,
                            conflicted=group.value.conflicted,
                            failure_code=group.failure_code,
                        )
                        for row in group_rows[:20]
                        for group in (stored(row),)
                    ]
    except InfraError:
        raise HTTPException(503, "BOT_STATUS_UNAVAILABLE") from None
    return BotStatusView(
        mode=mode,
        snapshot_at=snapshot_at,
        pending_request_id=pending_request_id,
        run_id=None if run is None else run.id,
        status=None if run is None else run.status,
        revision=None if run is None else run.revision,
        strategy_name=None if run is None else run.strategy_name,
        strategy_version=None if run is None else run.strategy_version,
        configuration_version=None if run is None else run.configuration_version,
        stop_reason=None if run is None else run.reason,
        can_start=False,
        unavailable_reason=_unavailable(mode),
        exposure_available=exposure_available,
        positions=positions,
        protections=protections,
        protections_more=protections_more,
        readiness_reason=None if run is None else run.readiness_reason,
    )


@router.post("/paper/bots/requests", response_model=BotReceiptView, status_code=202)
@router.post("/live/bots/requests", response_model=BotReceiptView, status_code=202)
async def request_start(
    request: Request, response: Response, who: Who, key: Key, body: BotStartInput
) -> BotReceiptView:
    mode = _mode(request)
    if mode is TradingMode.LIVE:
        raise HTTPException(503, _unavailable(mode))
    try:
        async with user_session(engine_for(request, DatabaseRole.API), who.user_id) as session:
            previous = await receipt_by_key(session, mode, key)
            if previous is None:
                # A deployment-owned allowlist is installed only after the
                # scheduler and registry pass activation checks. Default closed.
                refs = getattr(request.app.state, "bot_paper_configurations", None)
                if not isinstance(refs, frozenset) or body.strategy_config_ref not in refs:
                    raise HTTPException(503, _unavailable(mode))
                await spend_token(
                    paper_mutation_engine(request), who.user_id, Bucket.PAPER_ORDER_NEW
                )
            receipt = await submit_start(
                session,
                mode=mode,
                request_id=uuid4(),
                key=key,
                payload=body.model_dump(mode="json"),
            )
        response.status_code = 200 if previous is not None else 202
        return _receipt(receipt)
    except BotRequestConflictError:
        raise HTTPException(409, "BOT_REQUEST_IDEMPOTENCY_CONFLICT") from None
    except InfraError:
        raise HTTPException(503, "BOT_STATUS_UNAVAILABLE") from None


@router.get("/paper/bots/requests/by-key/{key}", response_model=BotReceiptView)
@router.get("/live/bots/requests/by-key/{key}", response_model=BotReceiptView)
async def request_by_key(key: UUID, request: Request, who: Who) -> BotReceiptView:
    try:
        async with repeatable_user_session(
            engine_for(request, DatabaseRole.API), who.user_id
        ) as session:
            return _receipt(await receipt_by_key(session, _mode(request), key))
    except InfraError:
        raise HTTPException(503, "BOT_STATUS_UNAVAILABLE") from None


@router.get("/paper/bots/requests/{request_id}", response_model=BotReceiptView)
@router.get("/live/bots/requests/{request_id}", response_model=BotReceiptView)
async def request_by_id(request_id: UUID, request: Request, who: Who) -> BotReceiptView:
    try:
        async with repeatable_user_session(
            engine_for(request, DatabaseRole.API), who.user_id
        ) as session:
            return _receipt(await receipt_by_id(session, _mode(request), request_id))
    except InfraError:
        raise HTTPException(503, "BOT_STATUS_UNAVAILABLE") from None
