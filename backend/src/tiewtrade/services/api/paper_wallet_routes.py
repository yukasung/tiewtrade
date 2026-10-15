"""Authenticated Paper-wallet command and snapshot API."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, StrictStr

from tiewtrade.core.money import Money
from tiewtrade.infra.auth.throttle import Bucket
from tiewtrade.infra.db import DatabaseRole, InfraError, repeatable_user_session, user_session
from tiewtrade.infra.paper_wallet import (
    PaperCommand,
    PaperCommandSnapshot,
    PaperCommandState,
    PaperWalletAction,
    PaperWalletSnapshot,
    admit_command,
    get_command,
    get_wallet,
    inspect_submission,
)
from tiewtrade.services.api.db_resources import engine_for, paper_mutation_engine
from tiewtrade.services.api.request_identity import Authenticated, current_user
from tiewtrade.services.api.safe_input_routes import SafeInputRoute
from tiewtrade.services.api.throttling import spend_token


class _PaperWalletInputRoute(SafeInputRoute):
    rejection_code = "PAPER_WALLET_INPUT_REJECTED"


router = APIRouter(
    prefix="/paper-wallet",
    tags=["paper-wallet"],
    route_class=_PaperWalletInputRoute,
)


class PaperWalletMutation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    initial_capital: StrictStr = Field(min_length=1, max_length=256)


class PaperWalletReset(PaperWalletMutation):
    expected_episode_id: UUID


class MoneyView(BaseModel):
    amount: str
    currency: Literal["USDT"] = "USDT"


class PaperCommandSnapshotView(BaseModel):
    wallet_id: UUID
    episode_id: UUID
    initial_capital: MoneyView
    balance: MoneyView


class PaperCommandView(BaseModel):
    command_id: UUID
    state: PaperCommandState
    failure_code: str | None
    snapshot: PaperCommandSnapshotView | None
    status_url: str


class PaperWalletView(BaseModel):
    mode: Literal["PAPER"] = "PAPER"
    wallet_id: UUID
    episode_id: UUID
    sequence: int
    initial_capital: MoneyView
    balance: MoneyView
    started_at: str
    snapshot_at: str
    revision: int
    reset_available: bool
    reset_reason: str | None


class PaperWalletEnvelope(BaseModel):
    wallet: PaperWalletView | None


def _dependency_unavailable() -> HTTPException:
    return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "PAPER_WALLET_DEPENDENCY_UNAVAILABLE")


def _money(value: Money) -> MoneyView:
    parts = value.as_parts()
    return MoneyView(amount=parts["amount"], currency="USDT")


def _wallet(snapshot: PaperWalletSnapshot) -> PaperWalletView:
    return PaperWalletView(
        wallet_id=snapshot.wallet_id,
        episode_id=snapshot.episode_id,
        sequence=snapshot.sequence,
        initial_capital=_money(snapshot.initial_capital),
        balance=_money(snapshot.balance),
        started_at=snapshot.started_at.isoformat(),
        snapshot_at=snapshot.snapshot_at.isoformat(),
        revision=snapshot.revision,
        reset_available=snapshot.reset_available,
        reset_reason=snapshot.reset_reason,
    )


def _command_snapshot(snapshot: PaperCommandSnapshot) -> PaperCommandSnapshotView:
    return PaperCommandSnapshotView(
        wallet_id=snapshot.wallet_id,
        episode_id=snapshot.episode_id,
        initial_capital=_money(snapshot.initial_capital),
        balance=_money(snapshot.balance),
    )


def _command(value: PaperCommand) -> PaperCommandView:
    return PaperCommandView(
        command_id=value.command_id,
        state=value.state,
        failure_code=value.failure_code,
        snapshot=None if value.snapshot is None else _command_snapshot(value.snapshot),
        status_url=f"/paper-wallet/commands/{value.command_id}",
    )


def _raise_rejection(command: PaperCommand) -> None:
    if command.state is not PaperCommandState.REJECTED:
        return
    code = command.failure_code or "PAPER_WALLET_REJECTED"
    status_code = (
        status.HTTP_422_UNPROCESSABLE_CONTENT
        if code in {"INITIAL_CAPITAL_INVALID", "INITIAL_CAPITAL_TOO_SMALL"}
        else status.HTTP_409_CONFLICT
    )
    raise HTTPException(status_code, code)


async def _submit(
    *,
    request: Request,
    who: Authenticated,
    action: PaperWalletAction,
    capital: str,
    expected_episode_id: UUID | None,
    idempotency_key: UUID,
    response: Response,
) -> PaperCommandView:
    engine = engine_for(request, DatabaseRole.API)
    rejected: PaperCommand | None = None
    try:
        async with user_session(engine, who.user_id) as session:
            previous = await inspect_submission(
                session,
                action=action,
                idempotency_key=idempotency_key,
                capital_text=capital,
                expected_episode_id=expected_episode_id,
            )
            if previous is not None:
                rejected = previous if previous.state is PaperCommandState.REJECTED else None
                result = previous
            else:
                await spend_token(
                    paper_mutation_engine(request),
                    who.user_id,
                    Bucket.PAPER_WALLET_MUTATION,
                )
                result = await admit_command(
                    session,
                    action=action,
                    idempotency_key=idempotency_key,
                    capital_text=capital,
                    expected_episode_id=expected_episode_id,
                )
                rejected = result if result.state is PaperCommandState.REJECTED else None
    except InfraError:
        raise _dependency_unavailable() from None
    # Domain rejection is a committed financial result.  Convert it to HTTP
    # only after the transaction containing its immutable result/audit closes.
    if rejected is not None:
        _raise_rejection(rejected)
    response.status_code = (
        status.HTTP_202_ACCEPTED
        if result.state is PaperCommandState.PENDING
        else status.HTTP_200_OK
    )
    return _command(result)


@router.get("")
async def read_paper_wallet(
    request: Request, who: Annotated[Authenticated, Depends(current_user)]
) -> PaperWalletEnvelope:
    try:
        async with repeatable_user_session(
            engine_for(request, DatabaseRole.API), who.user_id
        ) as session:
            snapshot = await get_wallet(session)
    except InfraError:
        raise _dependency_unavailable() from None
    return PaperWalletEnvelope(wallet=None if snapshot is None else _wallet(snapshot))


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def create_paper_wallet(
    body: PaperWalletMutation,
    response: Response,
    request: Request,
    who: Annotated[Authenticated, Depends(current_user)],
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
) -> PaperCommandView:
    return await _submit(
        request=request,
        who=who,
        action=PaperWalletAction.CREATE,
        capital=body.initial_capital,
        expected_episode_id=None,
        idempotency_key=idempotency_key,
        response=response,
    )


@router.post("/reset", status_code=status.HTTP_202_ACCEPTED)
async def reset_paper_wallet(
    body: PaperWalletReset,
    response: Response,
    request: Request,
    who: Annotated[Authenticated, Depends(current_user)],
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
) -> PaperCommandView:
    return await _submit(
        request=request,
        who=who,
        action=PaperWalletAction.RESET,
        capital=body.initial_capital,
        expected_episode_id=body.expected_episode_id,
        idempotency_key=idempotency_key,
        response=response,
    )


@router.get("/commands/{command_id}")
async def read_paper_command(
    command_id: UUID,
    request: Request,
    who: Annotated[Authenticated, Depends(current_user)],
) -> PaperCommandView:
    async with user_session(engine_for(request, DatabaseRole.API), who.user_id) as session:
        command = await get_command(session, command_id)
    if command is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "PAPER_COMMAND_NOT_FOUND")
    return _command(command)
