"""Single-account metadata; selecting a use never grants trading capability."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict

from tiewtrade.infra.audit import (
    ActorKind,
    AuditAction,
    AuditEvent,
    AuditOutcome,
    SubjectKind,
    TradingUseDetails,
    record_event,
)
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.trading_account import (
    AccountUse,
    TradingAccountActivityUnknownError,
    TradingAccountKeyUnavailableError,
    TradingAccountSummary,
    get_account,
    select_use,
)
from tiewtrade.services.api.api_key_routes import KeyView, key_view
from tiewtrade.services.api.authentication import Authenticated, current_user
from tiewtrade.services.api.resources import engine_for
from tiewtrade.services.api.safe_input_routes import SafeInputRoute


class _TradingAccountInputRoute(SafeInputRoute):
    rejection_code = "TRADING_ACCOUNT_INPUT_REJECTED"


class RejectedTradingAccountInput(BaseModel):
    detail: str


router = APIRouter(
    prefix="/trading-account",
    tags=["trading-account"],
    route_class=_TradingAccountInputRoute,
    responses={422: {"model": RejectedTradingAccountInput}},
)


class SelectTradingUseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    use: AccountUse


class TradingAccountView(BaseModel):
    use: AccountUse | None
    key: KeyView | None
    may_trade: Literal[False] = False
    may_change_use: Literal[False] = False


def _view(summary: TradingAccountSummary) -> TradingAccountView:
    return TradingAccountView(
        use=summary.use,
        key=key_view(summary.key) if summary.key is not None else None,
    )


@router.get("")
async def read_account(
    request: Request, who: Annotated[Authenticated, Depends(current_user)]
) -> TradingAccountView:
    async with user_session(engine_for(request, DatabaseRole.API), who.user_id) as session:
        summary = await get_account(session)
    return _view(summary)


@router.post("/use", status_code=status.HTTP_201_CREATED)
async def select_account_use(
    body: SelectTradingUseRequest,
    request: Request,
    who: Annotated[Authenticated, Depends(current_user)],
) -> TradingAccountView:
    async with user_session(engine_for(request, DatabaseRole.API), who.user_id) as session:
        try:
            summary = await select_use(session, body.use)
        except (TradingAccountKeyUnavailableError, TradingAccountActivityUnknownError) as error:
            raise HTTPException(status.HTTP_409_CONFLICT, error.code) from None
        await record_event(
            session,
            AuditEvent(
                owner_user_id=who.user_id,
                action=AuditAction.TRADING_USE_SELECTED,
                actor_kind=ActorKind.USER,
                actor_id=who.user_id,
                subject_kind=SubjectKind.USER,
                subject_id=str(who.user_id),
                outcome=AuditOutcome.SUCCEEDED,
                details=TradingUseDetails(use=body.use),
            ),
        )
    return _view(summary)
