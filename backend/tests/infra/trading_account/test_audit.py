"""Single-account use audit is a narrow UUID-and-use record."""

from typing import cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.infra.audit import (
    ActorKind,
    AuditAction,
    AuditEvent,
    AuditEventError,
    AuditOutcome,
    SubjectKind,
    TradingUseDetails,
    record_event,
)
from tiewtrade.infra.db import user_session
from tiewtrade.infra.trading_account import AccountUse, get_account, select_use

from .conftest import active_key


def selected_event(owner: UUID, use: AccountUse) -> AuditEvent:
    return AuditEvent(
        owner_user_id=owner,
        actor_kind=ActorKind.USER,
        actor_id=owner,
        action=AuditAction.TRADING_USE_SELECTED,
        subject_kind=SubjectKind.USER,
        subject_id=str(owner),
        outcome=AuditOutcome.SUCCEEDED,
        details=TradingUseDetails(use=use),
    )


@pytest.mark.parametrize("use", list(AccountUse))
def test_use_details(use: AccountUse) -> None:
    assert selected_event(uuid4(), use).details.as_details() == {"use": use.value}
    with pytest.raises(AuditEventError):
        TradingUseDetails(use=cast(AccountUse, "foreign-secret"))


async def test_audit_and_preference_atomic(
    api_engine: AsyncEngine, engine_engine: AsyncEngine, owner: UUID
) -> None:
    await active_key(api_engine, engine_engine, owner)
    with pytest.raises(RuntimeError):
        async with user_session(api_engine, owner) as session:
            await select_use(session, AccountUse.MANUAL)
            await record_event(session, selected_event(owner, AccountUse.MANUAL))
            raise RuntimeError("injected audit failure")
    async with user_session(api_engine, owner) as session:
        assert (await get_account(session)).use is None
        assert (
            await session.execute(
                "SELECT count(*) FROM audit_events WHERE action='TRADING_USE_SELECTED'"
            )
        ).scalar_one() == 0
        await select_use(session, AccountUse.BOT)
        await record_event(session, selected_event(owner, AccountUse.BOT))


@pytest.mark.parametrize(
    "field",
    ["actor_id", "actor_kind", "subject_id", "subject_kind", "mode", "outcome", "failure_code"],
)
def test_python_selected_use_shape_rejects_invalid_core(field: str) -> None:
    from dataclasses import replace
    from typing import Any

    from tiewtrade.infra.audit import AuditMode

    owner = uuid4()
    valid = selected_event(owner, AccountUse.MANUAL)
    bad: dict[str, object] = {
        "actor_id": uuid4(),
        "actor_kind": ActorKind.SYSTEM,
        "subject_id": str(uuid4()),
        "subject_kind": SubjectKind.API_KEY,
        "mode": AuditMode.LIVE,
        "outcome": AuditOutcome.FAILED,
        "failure_code": "VENUE_PROTOCOL",
    }
    with pytest.raises(AuditEventError):
        replace(valid, **{field: cast(Any, bad[field])})
