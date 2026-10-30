import asyncio
from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.core.money import Money
from tiewtrade.core.orders import TradingMode
from tiewtrade.core.risk_limits import RiskScope
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.db.errors import AppendOnlyViolationError, NotPermittedError
from tiewtrade.infra.db.session import presented_session, scan_session_bypassing_rls
from tiewtrade.infra.paper_wallet import get_wallet
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot
from tiewtrade.infra.risk_limits.records import (
    RiskAction,
    RiskAuthorizationError,
    RiskConflictError,
    RiskSubmission,
)
from tiewtrade.infra.risk_limits.requests import (
    authorize_increase,
    receipt_by_id,
    receipt_by_key,
    submit_request,
)
from tiewtrade.infra.users import create_user


def submission(owner: UUID, wallet: PaperWalletSnapshot) -> RiskSubmission:
    return RiskSubmission(
        RiskScope(
            owner,
            TradingMode.PAPER,
            UUID(str(wallet.wallet_id)),
            UUID(str(wallet.episode_id)),
        ),
        RiskAction.SET,
        uuid4(),
        0,
        Money.of(100, "USDT"),
    )


async def seed_setting(
    engine: AsyncEngine, owner: UUID, mode: TradingMode = TradingMode.PAPER
) -> None:
    async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
        await session.execute(
            """INSERT INTO risk_limit_settings(user_id,mode,revision,amount)
            VALUES(:owner,:mode,1,100)""",
            {"owner": owner, "mode": mode.value},
        )


def live_increase(owner: UUID) -> RiskSubmission:
    return RiskSubmission(
        RiskScope(owner, TradingMode.LIVE),
        RiskAction.INCREASE,
        uuid4(),
        1,
        Money.of(200, "USDT"),
    )


async def test_intake_is_durable_replayable_and_does_not_change_applied_state_or_money(
    api_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    value = submission(owner, wallet)
    async with user_session(api_engine, owner) as session:
        first = await submit_request(session, value)
        assert await receipt_by_id(session, TradingMode.PAPER, first.receipt_id) == first
    async with user_session(api_engine, owner) as session:
        replay = await submit_request(session, value)
        assert replay == first and not first.authorization_only
        assert (await session.execute("SELECT count(*) FROM risk_limit_settings")).scalar_one() == 0
        snapshot = await get_wallet(session)
        assert snapshot is not None and snapshot.balance == wallet.balance
        assert (
            await session.execute(
                "SELECT count(*) FROM risk_limit_requests WHERE id=:id", {"id": first.receipt_id}
            )
        ).scalar_one() == 1
        assert (
            await session.execute(
                """SELECT count(*) FROM audit_events WHERE action='RISK_LIMIT_REQUESTED'
                AND details->>'request_id'=:id""",
                {"id": str(first.receipt_id)},
            )
        ).scalar_one() == 1


async def test_concurrent_replay_creates_one_request_dispatch_and_audit(
    api_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    value = submission(owner, wallet)

    async def submit() -> UUID:
        async with user_session(api_engine, owner) as session:
            return (await submit_request(session, value)).receipt_id

    first, second = await asyncio.gather(submit(), submit())
    assert first == second
    async with user_session(api_engine, owner) as session:
        assert (
            await session.execute(
                "SELECT count(*) FROM risk_limit_dispatch WHERE request_id=:id", {"id": first}
            )
        ).scalar_one() == 1


async def test_same_key_different_amount_or_action_conflicts(
    api_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    value = submission(owner, wallet)
    async with user_session(api_engine, owner) as session:
        await submit_request(session, value)
    for different in (
        replace(value, amount=Money.of(101, "USDT")),
        replace(value, action=RiskAction.DECREASE),
        replace(value, expected_revision=1),
    ):
        with pytest.raises(RiskConflictError):
            async with user_session(api_engine, owner) as session:
                await submit_request(session, different)


async def test_intake_and_audit_rollback_together_then_same_key_is_safe(
    api_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    value = submission(owner, wallet)
    with pytest.raises(RuntimeError):
        async with user_session(api_engine, owner) as session:
            await submit_request(session, value)
            raise RuntimeError("controlled failure before commit")
    async with user_session(api_engine, owner) as session:
        assert await receipt_by_key(session, TradingMode.PAPER, value.key) is None
        assert (await session.execute("SELECT count(*) FROM risk_limit_dispatch")).scalar_one() == 0
        await submit_request(session, value)


async def test_cross_owner_and_missing_owner_cannot_discover_receipts(
    api_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    value = submission(owner, wallet)
    async with user_session(api_engine, owner) as session:
        first = await submit_request(session, value)
    other = uuid4()
    await create_user(api_engine, other)
    async with user_session(api_engine, other) as session:
        assert await receipt_by_key(session, TradingMode.PAPER, value.key) is None
        assert await receipt_by_id(session, TradingMode.PAPER, first.receipt_id) is None
        with pytest.raises(RiskConflictError):
            await submit_request(session, value)
    async with presented_session(api_engine) as session:
        assert (await session.execute("SELECT count(*) FROM risk_limit_requests")).scalar_one() == 0


async def test_authorization_only_receipt_survives_gap_before_intake(
    api_engine: AsyncEngine,
    auth_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    await seed_setting(engine_engine, owner, TradingMode.LIVE)
    value = live_increase(owner)
    async with user_session(auth_engine, owner, role=DatabaseRole.AUTH) as session:
        authorized = await authorize_increase(session, value)
    # This models process death after AUTH commit: no request inbox exists yet.
    async with user_session(api_engine, owner) as session:
        found = await receipt_by_key(session, TradingMode.LIVE, value.key)
        assert found == authorized and found.authorization_only
        assert await receipt_by_id(session, TradingMode.LIVE, authorized.receipt_id) == authorized
        accepted = await submit_request(session, value)
        assert not accepted.authorization_only
        assert accepted.receipt_id == authorized.receipt_id
        assert accepted.authorization_id == authorized.authorization_id
    async with user_session(api_engine, owner) as session:
        assert await submit_request(session, value) == accepted
        assert (
            await session.execute("SELECT amount FROM risk_limit_settings")
        ).scalar_one() == Money.of(100, "USDT").amount


async def test_authorization_cannot_be_forged_from_api_role_or_reused_for_another_payload(
    api_engine: AsyncEngine,
    auth_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    await seed_setting(engine_engine, owner, TradingMode.LIVE)
    value = live_increase(owner)
    with pytest.raises(RiskAuthorizationError):
        async with user_session(api_engine, owner) as session:
            await submit_request(session, value)
    with pytest.raises(NotPermittedError):
        async with user_session(api_engine, owner) as session:
            await authorize_increase(session, value)
    async with user_session(auth_engine, owner, role=DatabaseRole.AUTH) as session:
        await authorize_increase(session, value)
    with pytest.raises(RiskConflictError):
        async with user_session(api_engine, owner) as session:
            await submit_request(session, replace(value, amount=Money.of(201, "USDT")))


async def test_paper_increase_needs_no_authorization_receipt(
    api_engine: AsyncEngine,
    auth_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    await seed_setting(engine_engine, owner)
    value = replace(
        submission(owner, wallet),
        action=RiskAction.INCREASE,
        expected_revision=1,
        amount=Money.of(200, "USDT"),
    )
    with pytest.raises(RiskAuthorizationError):
        async with user_session(auth_engine, owner, role=DatabaseRole.AUTH) as session:
            await authorize_increase(session, value)
    async with user_session(api_engine, owner) as session:
        accepted = await submit_request(session, value)
        assert accepted.authorization_id is None
        assert not accepted.authorization_only


@pytest.mark.parametrize("action", [RiskAction.SET, RiskAction.DECREASE])
async def test_non_reverified_intake_cannot_increase_an_existing_limit(
    action: RiskAction,
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    await seed_setting(engine_engine, owner)
    value = replace(
        submission(owner, wallet), action=action, expected_revision=1, amount=Money.of(200, "USDT")
    )
    with pytest.raises(RiskConflictError):
        async with user_session(api_engine, owner) as session:
            await submit_request(session, value)


async def test_stale_or_wrong_episode_is_rejected_without_inbox_side_effect(
    api_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    value = submission(owner, wallet)
    for different in (
        replace(value, expected_revision=1),
        replace(value, scope=replace(value.scope, episode_id=uuid4())),
    ):
        with pytest.raises(RiskConflictError):
            async with user_session(api_engine, owner) as session:
                await submit_request(session, different)
    async with user_session(api_engine, owner) as session:
        assert (await session.execute("SELECT count(*) FROM risk_limit_requests")).scalar_one() == 0


async def test_runtime_role_permissions_keep_inbox_and_settings_separate(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    value = submission(owner, wallet)
    async with user_session(api_engine, owner) as session:
        await submit_request(session, value)
    for statement in (
        "UPDATE risk_limit_requests SET expected_revision=9",
        "DELETE FROM risk_limit_requests",
        "TRUNCATE risk_limit_requests",
        "UPDATE risk_limit_settings SET amount=999",
    ):
        with pytest.raises((AppendOnlyViolationError, NotPermittedError)):
            async with user_session(api_engine, owner) as session:
                await session.execute(statement)
    with pytest.raises(NotPermittedError):
        async with scan_session_bypassing_rls(scan_engine) as session:
            await session.execute("SELECT fingerprint FROM risk_limit_authorizations")
    with pytest.raises(NotPermittedError):
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await session.execute("UPDATE risk_limit_authorizations SET expected_revision=10")
