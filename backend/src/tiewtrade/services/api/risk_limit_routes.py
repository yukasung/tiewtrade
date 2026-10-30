"""Owner-scoped risk settings inbox; API never writes an applied trading setting."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response

from tiewtrade.core.money import Money, MoneyError
from tiewtrade.core.orders import TradingMode
from tiewtrade.core.risk_limits import RiskInputError, RiskScope, RiskSetting, sum_risk_money
from tiewtrade.infra.auth.throttle import Bucket
from tiewtrade.infra.db import DatabaseRole, InfraError, repeatable_user_session, user_session
from tiewtrade.infra.db.session import UserSession
from tiewtrade.infra.paper_wallet import get_wallet
from tiewtrade.infra.risk_limits.records import RiskConflictError, RiskReceipt, RiskSubmission
from tiewtrade.infra.risk_limits.requests import receipt_by_id, receipt_by_key, submit_request
from tiewtrade.infra.risk_limits.stop_views import effect_page, stop_summary
from tiewtrade.infra.risk_limits.views import read_evidence
from tiewtrade.services.api.db_resources import engine_for, paper_mutation_engine
from tiewtrade.services.api.request_identity import Authenticated, current_user
from tiewtrade.services.api.risk_limit_models import (
    RiskEffectPage,
    RiskExpectedScope,
    RiskLimitMutation,
    RiskLimitView,
    RiskRequestView,
    risk_submission,
)
from tiewtrade.services.api.safe_input_routes import SafeInputRoute
from tiewtrade.services.api.throttling import spend_token


class RiskInputRoute(SafeInputRoute):
    rejection_code = "RISK_INPUT_INVALID"


router = APIRouter(tags=["risk-limits"], route_class=RiskInputRoute)
Who = Annotated[Authenticated, Depends(current_user)]
Key = Annotated[UUID, Header(alias="Idempotency-Key")]


def _mode(request: Request) -> TradingMode:
    return TradingMode.PAPER if request.url.path.startswith("/paper/") else TradingMode.LIVE


async def _view(session: UserSession, receipt: RiskReceipt) -> RiskRequestView:
    result = (
        await session.execute(
            "SELECT state,revision,failure_code FROM risk_limit_results WHERE request_id=:id",
            {"id": receipt.receipt_id},
        )
    ).one_or_none()
    value = receipt.submission
    return RiskRequestView(
        receipt_id=receipt.receipt_id,
        mode=value.scope.mode.value,
        action=value.action.value,
        idempotency_key=value.key,
        amount=None if value.amount is None else value.amount.as_parts()["amount"],
        expected_revision=value.expected_revision,
        expected_wallet_id=value.scope.wallet_id,
        expected_episode_id=value.scope.episode_id,
        state=("AUTHORIZATION_ONLY" if receipt.authorization_only else "REQUEST_PENDING")
        if result is None
        else result.state,
        applied_revision=None if result is None else result.revision,
        failure_code=None if result is None else result.failure_code,
        recorded_at=receipt.recorded_at.isoformat(),
    )


async def _submit(
    request: Request,
    response: Response,
    who: Authenticated,
    value: RiskSubmission,
) -> RiskRequestView:
    engine = engine_for(request, DatabaseRole.API)
    try:
        async with user_session(engine, who.user_id) as session:
            previous = await receipt_by_key(session, value.scope.mode, value.key)
        if previous is None:
            await spend_token(
                paper_mutation_engine(request), who.user_id, Bucket.RISK_LIMIT_MUTATION
            )
        async with user_session(engine, who.user_id) as session:
            receipt = await submit_request(session, value)
            result = await _view(session, receipt)
        response.status_code = (
            200 if previous is not None and not previous.authorization_only else 202
        )
        return result
    except RiskConflictError as error:
        raise HTTPException(409, error.code) from None
    except InfraError:
        raise HTTPException(503, "RISK_SOURCE_UNAVAILABLE") from None


@router.get("/paper/risk-limit", response_model=RiskLimitView)
@router.get("/live/risk-limit", response_model=RiskLimitView)
async def risk_status(request: Request, who: Who) -> RiskLimitView:
    mode = _mode(request)
    try:
        async with repeatable_user_session(
            engine_for(request, DatabaseRole.API), who.user_id
        ) as session:
            row = (
                await session.execute(
                    """SELECT s.*,e.reason,e.loss,e.source_revision,e.evaluated_at,
                      e.price_watermark,e.input_ready_at,e.unavailable_since,e.pause_alert_due,
                      b.source_revision AS baseline_source_revision,
                      b.snapshot->>'reset_at' baseline_at
                FROM risk_limit_settings s LEFT JOIN risk_limit_evaluations e
                  ON e.user_id=s.user_id AND e.mode=s.mode
                LEFT JOIN risk_limit_baselines b
                  ON (b.id,b.user_id,b.mode)=(s.baseline_id,s.user_id,s.mode)
                WHERE s.mode=:mode""",
                    {"mode": mode.value},
                )
            ).one_or_none()
            wallet = await get_wallet(session) if mode is TradingMode.PAPER else None
            now = (await session.execute("SELECT clock_timestamp()")).scalar_one()
            stop = await stop_summary(session, mode)
            evaluation = None
            evidence = None
            allowance = realized = None
            if row is not None and (mode is TradingMode.LIVE or wallet is not None):
                scope = RiskScope(
                    UUID(str(who.user_id)),
                    mode,
                    None if wallet is None else UUID(str(wallet.wallet_id)),
                    None if wallet is None else UUID(str(wallet.episode_id)),
                )
                evidence = await read_evidence(
                    session,
                    RiskSetting(
                        scope,
                        int(row.revision),
                        Money.of(row.amount, "USDT"),
                        bool(row.latched),
                    ),
                    api_price_tail=True,
                )
                evaluation = evidence.evaluation
                if evidence.book is not None:
                    allowance = sum_risk_money(
                        tuple(pair.allowance for pair in evidence.book.pairs)
                    )
                    realized = sum_risk_money(
                        tuple(pair.adjusted_realized for pair in evidence.book.pairs)
                    )
        return RiskLimitView(
            mode=mode.value,
            amount=None if row is None else Money.of(row.amount, "USDT").as_parts()["amount"],
            revision=0 if row is None else int(row.revision),
            wallet_id=None if wallet is None else wallet.wallet_id,
            episode_id=None if wallet is None else wallet.episode_id,
            latched=False if row is None else bool(row.latched),
            loss=None
            if evaluation is None or evaluation.loss is None
            else evaluation.loss.as_parts()["amount"],
            reason="RISK_LIMIT_UNSET"
            if row is None
            else "RISK_SOURCE_UNAVAILABLE"
            if evaluation is None
            else evaluation.reason.value,
            source_revision=None
            if evaluation is None or evaluation.source_revision == 0
            else evaluation.source_revision,
            evaluated_at=None if evaluation is None else evaluation.evaluated_at.isoformat(),
            snapshot_at=(now if evaluation is None else evaluation.evaluated_at).isoformat(),
            stop_id=None if stop is None else stop["stop_id"],
            effects_revision=None if stop is None else int(stop["effects_revision"]),
            target_count=None if stop is None else int(stop["target_count"]),
            pending_count=None if stop is None else int(stop["pending_count"]),
            failed_count=None if stop is None else int(stop["failed_count"]),
            target_set_complete=None if stop is None else bool(stop["target_set_complete"]),
            stop_progress=None
            if stop is None
            else "PROBLEMS"
            if stop["failed_count"]
            else "STOPPED"
            if stop["target_set_complete"] and stop["pending_count"] == 0
            else "STOPPING",
            stop_alert_due=False if stop is None else bool(stop["alert_due"]),
            baseline_id=None if row is None else row.baseline_id,
            baseline_source_revision=None if row is None else row.baseline_source_revision,
            baseline_at=None if row is None else row.baseline_at,
            current_allowance=None if allowance is None else allowance.as_parts()["amount"],
            adjusted_realized=None if realized is None else realized.as_parts()["amount"],
            price_watermark=None if evidence is None else evidence.price_watermark,
            input_ready_at=None
            if evidence is None or evidence.input_ready_at is None
            else evidence.input_ready_at.isoformat(),
            unavailable_since=None
            if evidence is None or evidence.unavailable_since is None
            else evidence.unavailable_since.isoformat(),
            pause_alert_due=False if evidence is None else evidence.pause_alert_due,
        )
    except (InfraError, MoneyError):
        raise HTTPException(503, "RISK_SOURCE_UNAVAILABLE") from None


@router.get("/paper/risk-limit/stops/{stop_id}/effects", response_model=RiskEffectPage)
@router.get("/live/risk-limit/stops/{stop_id}/effects", response_model=RiskEffectPage)
async def risk_effects(
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
                raise HTTPException(404, "RISK_STOP_NOT_FOUND")
            return RiskEffectPage.model_validate(page)
    except RiskConflictError:
        raise HTTPException(422, "RISK_EFFECT_CURSOR_INVALID") from None
    except InfraError:
        raise HTTPException(503, "RISK_SOURCE_UNAVAILABLE") from None


@router.post("/paper/risk-limit")
@router.post("/live/risk-limit")
async def set_limit(
    body: RiskLimitMutation, request: Request, response: Response, who: Who, key: Key
) -> RiskRequestView:
    return await mutate(body, request, response, who, key)


@router.post("/paper/risk-limit/increase")
@router.post("/live/risk-limit/increase")
async def increase_limit(
    body: RiskLimitMutation, request: Request, response: Response, who: Who, key: Key
) -> RiskRequestView:
    return await mutate(body, request, response, who, key, increase=True)


@router.post("/paper/risk-limit/reset")
@router.post("/live/risk-limit/reset")
async def reset_limit(
    body: RiskExpectedScope, request: Request, response: Response, who: Who, key: Key
) -> RiskRequestView:
    return await mutate(body, request, response, who, key)


async def mutate(
    body: RiskExpectedScope,
    request: Request,
    response: Response,
    who: Authenticated,
    key: UUID,
    *,
    increase: bool = False,
) -> RiskRequestView:
    try:
        value = risk_submission(
            owner=who.user_id, mode=_mode(request), key=key, body=body, increase=increase
        )
    except (MoneyError, RiskInputError):
        raise HTTPException(422, "RISK_INPUT_INVALID") from None
    return await _submit(request, response, who, value)


@router.get("/paper/risk-limit/requests/by-key/{key}")
@router.get("/live/risk-limit/requests/by-key/{key}")
async def by_key(key: UUID, request: Request, who: Who) -> RiskRequestView:
    try:
        async with repeatable_user_session(
            engine_for(request, DatabaseRole.API), who.user_id
        ) as session:
            receipt = await receipt_by_key(session, _mode(request), key)
            if receipt is None:
                raise HTTPException(404, "RISK_REQUEST_NOT_FOUND")
            return await _view(session, receipt)
    except InfraError:
        raise HTTPException(503, "RISK_SOURCE_UNAVAILABLE") from None


@router.get("/paper/risk-limit/requests/{receipt_id}")
@router.get("/live/risk-limit/requests/{receipt_id}")
async def by_id(receipt_id: UUID, request: Request, who: Who) -> RiskRequestView:
    try:
        async with repeatable_user_session(
            engine_for(request, DatabaseRole.API), who.user_id
        ) as session:
            receipt = await receipt_by_id(session, _mode(request), receipt_id)
            if receipt is None:
                raise HTTPException(404, "RISK_REQUEST_NOT_FOUND")
            return await _view(session, receipt)
    except InfraError:
        raise HTTPException(503, "RISK_SOURCE_UNAVAILABLE") from None
