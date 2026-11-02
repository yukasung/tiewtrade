import asyncio
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.db.test_migrations import _failed_upgrade_or_downgrade
from tests.infra.positions.conftest import create_production_wallet
from tests.infra.risk_limits.test_concurrency import serialize
from tiewtrade.core.orders import OrderOrigin, TradingMode
from tiewtrade.core.trading_stops import StopAction, StopProgress
from tiewtrade.infra.db import (
    AppendOnlyViolationError,
    DatabaseRole,
    InfraError,
    NotPermittedError,
    user_session,
)
from tiewtrade.infra.db.session import UserSession
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot
from tiewtrade.infra.trading_account import AccountUse, select_use
from tiewtrade.infra.trading_stops import read_status, receipt_by_id, submit_request
from tiewtrade.infra.trading_stops.records import StopConflictError, StopReceipt
from tiewtrade.infra.trading_stops.storage import (
    current_opening_blocked,
    opening_interrupted,
)
from tiewtrade.infra.users import create_user
from tiewtrade.services.engine.kill_switch import (
    _apply_stop,
    run_platform_discovery_round,
    run_stop_request_round,
)
from tiewtrade.services.engine.risk_limit import run_risk_stop_round

pytestmark = pytest.mark.fresh_global_state


async def _touch_position_activity(
    migrator_engine: AsyncEngine,
    episode_id: UUID,
    *,
    commit: bool,
    availability: str | None = None,
) -> tuple[int, int]:
    """Exercise the reconciliation trigger without bypassing its RLS policies."""
    async with migrator_engine.connect() as connection:
        transaction = await connection.begin()
        try:
            before = int(
                (
                    await connection.execute(
                        text("SELECT revision FROM trading_reconciliation_clock WHERE singleton")
                    )
                ).scalar_one()
            )
            await connection.execute(
                text("ALTER TABLE paper_position_activity NO FORCE ROW LEVEL SECURITY")
            )
            await connection.execute(
                text("ALTER TABLE paper_position_activity DISABLE TRIGGER USER")
            )
            await connection.execute(
                text(
                    "ALTER TABLE paper_position_activity ENABLE TRIGGER "
                    "paper_position_activity_reconciliation_clock"
                )
            )
            changed = await connection.execute(
                text(
                    "UPDATE paper_position_activity SET revision=revision+1, "
                    "availability=coalesce(:availability,availability), "
                    "failure_code=CASE WHEN :availability='CONFLICTED' THEN 'INJECTED_CONFLICT' "
                    "WHEN :availability='READY' THEN NULL ELSE failure_code END "
                    "WHERE episode_id=:episode RETURNING revision"
                ),
                {"episode": episode_id, "availability": availability},
            )
            assert changed.scalar_one() > 1
            after = int(
                (
                    await connection.execute(
                        text("SELECT revision FROM trading_reconciliation_clock WHERE singleton")
                    )
                ).scalar_one()
            )
            if commit:
                await connection.execute(
                    text("ALTER TABLE paper_position_activity ENABLE TRIGGER USER")
                )
                await connection.execute(
                    text("ALTER TABLE paper_position_activity FORCE ROW LEVEL SECURITY")
                )
                await transaction.commit()
            else:
                await transaction.rollback()
            return before, after
        except BaseException:
            if transaction.is_active:
                await transaction.rollback()
            raise


async def _submit_platform_resume(
    session: UserSession,
    stop: StopReceipt,
    *,
    summary_revision: int,
    reconciliation_revision: int,
) -> StopReceipt:
    return await submit_request(
        session,
        mode=None,
        action=StopAction.RESUME,
        key=uuid4(),
        expected_stop_id=stop.stop_id,
        expected_revision=stop.revision,
        expected_summary_revision=summary_revision,
        expected_reconciliation_revision=reconciliation_revision,
        reason_code="PLATFORM_RESUME",
        platform=True,
    )


@pytest.mark.asyncio
async def test_reconciliation_clock_is_not_a_normal_trading_hot_row(
    api_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    before, after = await _touch_position_activity(migrator_engine, wallet.episode_id, commit=True)
    assert after == before

    with pytest.raises(InfraError):
        async with user_session(api_engine, owner) as session:
            await session.execute(
                "UPDATE trading_reconciliation_clock SET revision=revision+1 WHERE singleton"
            )


async def test_resume_clock_lock_is_engine_only_and_serializes_transactions(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
) -> None:
    with pytest.raises(NotPermittedError):
        async with user_session(api_engine, owner) as session:
            await session.execute("SELECT lock_trading_reconciliation_clock()")

    async def take_lock(session: UserSession) -> None:
        await session.execute("SELECT lock_trading_reconciliation_clock()")

    await serialize(engine_engine, migrator_engine, owner, take_lock, take_lock)


@pytest.mark.asyncio
async def test_stop_intent_is_an_immediate_fence_and_engine_projects_it(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
) -> None:
    key = uuid4()
    async with user_session(api_engine, owner) as session:
        receipt = await submit_request(
            session,
            mode=TradingMode.PAPER,
            action=StopAction.STOP,
            key=key,
            reason_code="USER_REQUEST",
        )
        replay = await submit_request(
            session,
            mode=TradingMode.PAPER,
            action=StopAction.STOP,
            key=key,
            reason_code="USER_REQUEST",
        )
        assert replay.request_id == receipt.request_id
        assert replay.generation == 1
        assert await current_opening_blocked(session, TradingMode.PAPER, OrderOrigin.BOT)

    result = await run_stop_request_round(engine=engine_engine, scan_engine=scan_engine)
    assert result.processed >= 1
    assert result.deferred == 0

    async with user_session(api_engine, owner) as session:
        status = await read_status(session, TradingMode.PAPER)
        assert status.stop_id == receipt.stop_id
        assert status.progress is StopProgress.STOPPED
        assert status.target_set_complete
        assert not status.resume_ready


@pytest.mark.asyncio
async def test_stop_idempotency_conflict_and_new_generation_are_distinct(
    api_engine: AsyncEngine,
    owner: UUID,
) -> None:
    key = uuid4()
    async with user_session(api_engine, owner) as session:
        first = await submit_request(
            session,
            mode=TradingMode.PAPER,
            action=StopAction.STOP,
            key=key,
            reason_code="USER_REQUEST",
        )

    with pytest.raises(StopConflictError):
        async with user_session(api_engine, owner) as session:
            await submit_request(
                session,
                mode=TradingMode.PAPER,
                action=StopAction.STOP,
                key=key,
                reason_code="DIFFERENT_REASON",
            )

    async with user_session(api_engine, owner) as session:
        repeated = await submit_request(
            session,
            mode=TradingMode.PAPER,
            action=StopAction.STOP,
            key=uuid4(),
            reason_code="USER_REQUEST",
        )
        assert repeated.request_id != first.request_id
        assert repeated.generation == first.generation + 1
        assert await opening_interrupted(
            session,
            mode=TradingMode.PAPER,
            origin=OrderOrigin.MANUAL,
            admitted_global_revision=0,
            admitted_owner_revision=first.revision,
        )


@pytest.mark.asyncio
async def test_resuming_latest_generation_does_not_resurrect_an_older_stop(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    async with user_session(api_engine, owner) as session:
        await select_use(session, AccountUse.BOT)
        older = await submit_request(
            session,
            mode=TradingMode.PAPER,
            action=StopAction.STOP,
            key=uuid4(),
            reason_code="USER_REQUEST",
        )
        latest = await submit_request(
            session,
            mode=TradingMode.PAPER,
            action=StopAction.STOP,
            key=uuid4(),
            reason_code="USER_REQUEST",
        )
    assert latest.generation == older.generation + 1

    for _ in range(2):
        applied = await run_stop_request_round(engine=engine_engine, scan_engine=scan_engine)
        assert applied.processed >= 1
    for _ in range(2):
        await run_risk_stop_round(engine=engine_engine, scan_engine=scan_engine, limit=20)

    async with user_session(api_engine, owner) as session:
        status = await read_status(session, TradingMode.PAPER)
        assert status.stop_id == latest.stop_id
        assert status.generation == latest.generation
        assert status.resume_ready
        assert status.reconciliation_revision is not None
        resume = await submit_request(
            session,
            mode=TradingMode.PAPER,
            action=StopAction.RESUME,
            key=uuid4(),
            expected_stop_id=latest.stop_id,
            expected_revision=latest.revision,
            expected_summary_revision=status.summary_revision,
            expected_reconciliation_revision=status.reconciliation_revision,
            reason_code="USER_RESUME",
        )

    resumed = await run_stop_request_round(engine=engine_engine, scan_engine=scan_engine)
    assert resumed.processed >= 1
    async with user_session(api_engine, owner) as session:
        receipt = await receipt_by_id(session, resume.request_id)
        status = await read_status(session, TradingMode.PAPER)
        assert receipt is not None and receipt.state == "APPLIED"
        assert status.stop_id is None
        assert status.generation is None
        assert not status.resume_ready
        assert not await current_opening_blocked(session, TradingMode.PAPER, OrderOrigin.BOT)


@pytest.mark.asyncio
async def test_reordered_stop_projection_never_regresses_to_older_generation(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    owner: UUID,
) -> None:
    async with user_session(api_engine, owner) as session:
        older = await submit_request(
            session,
            mode=TradingMode.PAPER,
            action=StopAction.STOP,
            key=uuid4(),
            reason_code="USER_REQUEST",
        )
        newer = await submit_request(
            session,
            mode=TradingMode.PAPER,
            action=StopAction.STOP,
            key=uuid4(),
            reason_code="USER_REQUEST",
        )

    for request_id in (newer.request_id, older.request_id):
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            request = (
                (
                    await session.execute(
                        "SELECT * FROM trading_stop_requests WHERE id=:id", {"id": request_id}
                    )
                )
                .mappings()
                .one()
            )
            await _apply_stop(session, request)

    async with user_session(api_engine, owner) as session:
        projected = (
            await session.execute(
                """SELECT stop_id,revision FROM trading_stop_causes
                WHERE scope_key=:scope AND cause='USER'""",
                {"scope": f"PAPER:{owner}"},
            )
        ).one()
    assert projected.stop_id == newer.stop_id
    assert projected.revision == newer.revision


@pytest.mark.asyncio
async def test_api_role_cannot_forge_an_engine_result(
    api_engine: AsyncEngine,
    owner: UUID,
) -> None:
    async with user_session(api_engine, owner) as session:
        receipt = await submit_request(
            session,
            mode=TradingMode.PAPER,
            action=StopAction.STOP,
            key=uuid4(),
            reason_code="USER_REQUEST",
        )

    with pytest.raises(NotPermittedError):
        async with user_session(api_engine, owner) as session:
            await session.execute(
                """INSERT INTO trading_stop_results
                (request_id,user_id,state,stop_id,revision)
                VALUES(:request,:owner,'APPLIED',:stop,:revision)""",
                {
                    "request": receipt.request_id,
                    "owner": owner,
                    "stop": receipt.stop_id,
                    "revision": receipt.revision,
                },
            )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE trading_stop_requests SET reason_code=reason_code WHERE false",
        "DELETE FROM trading_stop_requests WHERE false",
        "INSERT INTO trading_stop_events(request_id,user_id,stop_id,cause,active,revision) "
        "VALUES(gen_random_uuid(),gen_random_uuid(),gen_random_uuid(),'USER',true,1)",
        "UPDATE trading_stop_causes SET revision=revision WHERE false",
        "UPDATE platform_stop_progress SET revision=revision WHERE false",
        "DELETE FROM platform_stop_targets WHERE false",
    ],
)
async def test_api_role_cannot_mutate_stop_history_or_engine_projections(
    api_engine: AsyncEngine,
    owner: UUID,
    statement: str,
) -> None:
    with pytest.raises((AppendOnlyViolationError, NotPermittedError)):
        async with user_session(api_engine, owner) as session:
            await session.execute(statement)


@pytest.mark.asyncio
async def test_audit_failure_rolls_back_stop_intent_and_same_key_can_retry(
    api_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
) -> None:
    key = uuid4()
    marker = "raw-reason-must-not-leak"
    async with migrator_engine.begin() as connection:
        await connection.execute(
            text(
                """CREATE FUNCTION f19_reject_stop_audit() RETURNS trigger
                LANGUAGE plpgsql AS $$ BEGIN
                  IF NEW.action IN ('STOP_REQUESTED','RESUME_REQUESTED') THEN
                    RAISE EXCEPTION 'injected audit failure';
                  END IF;
                  RETURN NEW;
                END $$"""
            )
        )
        await connection.execute(
            text(
                """CREATE TRIGGER f19_reject_stop_audit
                BEFORE INSERT ON audit_events FOR EACH ROW
                EXECUTE FUNCTION f19_reject_stop_audit()"""
            )
        )
    try:
        with pytest.raises(InfraError) as caught:
            async with user_session(api_engine, owner) as session:
                await submit_request(
                    session,
                    mode=TradingMode.PAPER,
                    action=StopAction.STOP,
                    key=key,
                    reason_code="USER_REQUEST",
                    reason_text=marker,
                )
        assert marker not in str(caught.value)
        async with migrator_engine.connect() as connection:
            counts = (
                await connection.execute(
                    text(
                        """SELECT
                          (SELECT count(*) FROM trading_stop_requests
                            WHERE idempotency_key=:key) requests,
                          (SELECT count(*) FROM trading_stop_dispatch d JOIN trading_stop_requests r
                            ON r.id=d.request_id WHERE r.idempotency_key=:key) dispatches,
                          (SELECT count(*) FROM audit_events
                            WHERE details->>'request_id' IN
                              (SELECT id::text FROM trading_stop_requests
                                WHERE idempotency_key=:key)) audits"""
                    ),
                    {"key": key},
                )
            ).one()
        assert counts == (0, 0, 0)
    finally:
        async with migrator_engine.begin() as connection:
            await connection.execute(text("DROP TRIGGER f19_reject_stop_audit ON audit_events"))
            await connection.execute(text("DROP FUNCTION f19_reject_stop_audit()"))

    async with user_session(api_engine, owner) as session:
        retried = await submit_request(
            session,
            mode=TradingMode.PAPER,
            action=StopAction.STOP,
            key=key,
            reason_code="USER_REQUEST",
            reason_text=marker,
        )
        persisted = (
            await session.execute(
                "SELECT count(*) FROM audit_events WHERE details->>'request_id'=:request",
                {"request": str(retried.request_id)},
            )
        ).scalar_one()
    assert persisted == 1


async def _install_outcome_audit_failure(migrator_engine: AsyncEngine) -> None:
    async with migrator_engine.begin() as connection:
        await connection.execute(
            text(
                """CREATE FUNCTION f19_reject_stop_outcome_audit() RETURNS trigger
                LANGUAGE plpgsql AS $$ BEGIN
                  IF NEW.action IN ('STOP_UPDATED','RESUMED') THEN
                    RAISE EXCEPTION 'injected stop outcome audit failure';
                  END IF;
                  RETURN NEW;
                END $$"""
            )
        )
        await connection.execute(
            text(
                """CREATE TRIGGER f19_reject_stop_outcome_audit
                BEFORE INSERT ON audit_events FOR EACH ROW
                EXECUTE FUNCTION f19_reject_stop_outcome_audit()"""
            )
        )


async def _remove_outcome_audit_failure(migrator_engine: AsyncEngine) -> None:
    async with migrator_engine.begin() as connection:
        await connection.execute(
            text("DROP TRIGGER IF EXISTS f19_reject_stop_outcome_audit ON audit_events")
        )
        await connection.execute(text("DROP FUNCTION IF EXISTS f19_reject_stop_outcome_audit()"))


async def _make_stop_request_due(engine_engine: AsyncEngine, owner: UUID, request_id: UUID) -> None:
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await session.execute(
            """UPDATE trading_stop_dispatch SET next_attempt_at=clock_timestamp()
            WHERE request_id=:request""",
            {"request": request_id},
        )


@pytest.mark.asyncio
async def test_stop_and_resume_outcomes_rollback_with_audit_then_restart_once(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    async with user_session(api_engine, owner) as session:
        await select_use(session, AccountUse.BOT)
        stop = await submit_request(
            session,
            mode=TradingMode.PAPER,
            action=StopAction.STOP,
            key=uuid4(),
            reason_code="USER_REQUEST",
        )

    try:
        await _install_outcome_audit_failure(migrator_engine)
        failed_stop = await run_stop_request_round(engine=engine_engine, scan_engine=scan_engine)
        assert failed_stop.deferred >= 1
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as connection:
            rolled_back = (
                await connection.execute(
                    """SELECT
                          (SELECT count(*) FROM trading_stop_results
                            WHERE request_id=:request) results,
                          (SELECT count(*) FROM trading_stop_events
                            WHERE request_id=:request) events,
                          (SELECT count(*) FROM risk_stop_requests
                            WHERE authority_request_id=:request) jobs,
                          (SELECT count(*) FROM audit_events
                            WHERE action='STOP_UPDATED'
                              AND details->>'request_id'=:request_text) audits""",
                    {"request": stop.request_id, "request_text": str(stop.request_id)},
                )
            ).one()
        assert rolled_back == (0, 0, 0, 0)

        await _remove_outcome_audit_failure(migrator_engine)
        await _make_stop_request_due(engine_engine, owner, stop.request_id)
        recovered_stop = await run_stop_request_round(engine=engine_engine, scan_engine=scan_engine)
        assert recovered_stop.processed >= 1
        await run_stop_request_round(engine=engine_engine, scan_engine=scan_engine)
        consumed = await run_risk_stop_round(
            engine=engine_engine, scan_engine=scan_engine, limit=20
        )
        assert consumed.processed >= 1

        async with user_session(api_engine, owner) as session:
            status = await read_status(session, TradingMode.PAPER)
            assert status.resume_ready
            assert status.reconciliation_revision is not None
            resume = await submit_request(
                session,
                mode=TradingMode.PAPER,
                action=StopAction.RESUME,
                key=uuid4(),
                expected_stop_id=stop.stop_id,
                expected_revision=stop.revision,
                expected_summary_revision=status.summary_revision,
                expected_reconciliation_revision=status.reconciliation_revision,
                reason_code="USER_RESUME",
            )

        await _install_outcome_audit_failure(migrator_engine)
        failed_resume = await run_stop_request_round(engine=engine_engine, scan_engine=scan_engine)
        assert failed_resume.deferred >= 1
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as connection:
            rolled_back_resume = (
                await connection.execute(
                    """SELECT
                          (SELECT count(*) FROM trading_stop_results
                            WHERE request_id=:request) results,
                          (SELECT count(*) FROM trading_stop_events
                            WHERE request_id=:request) events,
                          (SELECT count(*) FROM audit_events WHERE action='RESUMED'
                            AND details->>'request_id'=:request_text) audits,
                          (SELECT active FROM trading_stop_causes
                            WHERE stop_id=:stop AND cause='USER') active""",
                    {
                        "request": resume.request_id,
                        "request_text": str(resume.request_id),
                        "stop": stop.stop_id,
                    },
                )
            ).one()
        assert rolled_back_resume == (0, 0, 0, True)

        await _remove_outcome_audit_failure(migrator_engine)
        await _make_stop_request_due(engine_engine, owner, resume.request_id)
        recovered_resume = await run_stop_request_round(
            engine=engine_engine, scan_engine=scan_engine
        )
        assert recovered_resume.processed >= 1
        await run_stop_request_round(engine=engine_engine, scan_engine=scan_engine)

        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as connection:
            committed_once = (
                await connection.execute(
                    """SELECT
                          (SELECT count(*) FROM trading_stop_results
                            WHERE request_id IN (:stop_request,:resume_request)) results,
                          (SELECT count(*) FROM trading_stop_events
                            WHERE request_id IN (:stop_request,:resume_request)) events,
                          (SELECT count(*) FROM risk_stop_requests
                            WHERE authority_request_id=:stop_request) jobs,
                          (SELECT count(*) FROM audit_events
                            WHERE action IN ('STOP_UPDATED','RESUMED')
                              AND details->>'request_id' IN (:stop_text,:resume_text)) audits,
                          (SELECT active FROM trading_stop_causes
                            WHERE stop_id=:stop AND cause='USER') active""",
                    {
                        "stop_request": stop.request_id,
                        "resume_request": resume.request_id,
                        "stop_text": str(stop.request_id),
                        "resume_text": str(resume.request_id),
                        "stop": stop.stop_id,
                    },
                )
            ).one()
        assert committed_once == (2, 2, 1, 2, False)
    finally:
        await _remove_outcome_audit_failure(migrator_engine)


@pytest.mark.asyncio
async def test_locked_owner_is_deferred_without_starving_another_stop(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
) -> None:
    other = uuid4()
    await create_user(api_engine, other)
    async with user_session(api_engine, owner) as session:
        first = await submit_request(
            session,
            mode=TradingMode.PAPER,
            action=StopAction.STOP,
            key=uuid4(),
            reason_code="USER_REQUEST",
        )
    async with user_session(api_engine, other) as session:
        second = await submit_request(
            session,
            mode=TradingMode.PAPER,
            action=StopAction.STOP,
            key=uuid4(),
            reason_code="USER_REQUEST",
        )

    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as held:
        await held.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(:key,0))",
            {"key": f"trading-stop-request:{first.request_id}"},
        )
        result = await run_stop_request_round(engine=engine_engine, scan_engine=scan_engine)

    assert result.deferred >= 1
    async with user_session(api_engine, other) as session:
        applied = (
            await session.execute(
                "SELECT state FROM trading_stop_results WHERE request_id=:id",
                {"id": second.request_id},
            )
        ).scalar_one_or_none()
    assert applied == "APPLIED"


@pytest.mark.asyncio
async def test_paper_resume_requires_completed_snapshot_and_closes_only_expected_stop(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    async with user_session(api_engine, owner) as session:
        await select_use(session, AccountUse.BOT)
        stop = await submit_request(
            session,
            mode=TradingMode.PAPER,
            action=StopAction.STOP,
            key=uuid4(),
            reason_code="USER_REQUEST",
        )

    applied = await run_stop_request_round(engine=engine_engine, scan_engine=scan_engine)
    assert applied.processed >= 1
    consumed = await run_risk_stop_round(engine=engine_engine, scan_engine=scan_engine, limit=20)
    assert consumed.processed >= 1

    async with user_session(api_engine, owner) as session:
        status = await read_status(session, TradingMode.PAPER)
        assert status.stop_id == stop.stop_id
        assert status.progress is StopProgress.STOPPED
        assert status.resume_ready
        assert status.reconciliation_revision is not None
        stale = await submit_request(
            session,
            mode=TradingMode.PAPER,
            action=StopAction.RESUME,
            key=uuid4(),
            expected_stop_id=stop.stop_id,
            expected_revision=stop.revision,
            expected_summary_revision=status.summary_revision,
            expected_reconciliation_revision=status.reconciliation_revision + 1,
            reason_code="USER_RESUME",
        )

    rejected = await run_stop_request_round(engine=engine_engine, scan_engine=scan_engine)
    assert rejected.processed >= 1
    async with user_session(api_engine, owner) as session:
        stale_result = await session.execute(
            "SELECT state,failure_code FROM trading_stop_results WHERE request_id=:id",
            {"id": stale.request_id},
        )
        assert stale_result.one() == ("REJECTED", "TRADING_STOP_NOT_READY")
        await submit_request(
            session,
            mode=TradingMode.PAPER,
            action=StopAction.RESUME,
            key=uuid4(),
            expected_stop_id=stop.stop_id,
            expected_revision=stop.revision,
            expected_summary_revision=0,
            expected_reconciliation_revision=status.reconciliation_revision,
            reason_code="USER_RESUME",
        )

    resumed = await run_stop_request_round(engine=engine_engine, scan_engine=scan_engine)
    assert resumed.processed >= 1
    async with user_session(api_engine, owner) as session:
        status = await read_status(session, TradingMode.PAPER)
        assert status.stop_id is None
        assert not status.resume_ready


@pytest.mark.asyncio
async def test_platform_fence_discovers_targets_and_owner_can_resume_exact_snapshot(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    async with migrator_engine.begin() as connection:
        # Fixture setup only; production membership changes use the deployment
        # bootstrap and platform lifecycle contracts.
        await connection.execute(
            text("ALTER TABLE platform_memberships NO FORCE ROW LEVEL SECURITY")
        )
        try:
            await connection.execute(
                text(
                    "INSERT INTO platform_memberships(user_id,role) VALUES(:owner,'PLATFORM_OWNER')"
                ),
                {"owner": owner},
            )
        finally:
            await connection.execute(
                text("ALTER TABLE platform_memberships FORCE ROW LEVEL SECURITY")
            )

    async with user_session(api_engine, owner) as session:
        stop = await submit_request(
            session,
            mode=None,
            action=StopAction.STOP,
            key=uuid4(),
            reason_code="PLATFORM_INCIDENT",
            reason_text="integration incident",
            platform=True,
        )
        assert await current_opening_blocked(session, TradingMode.PAPER, OrderOrigin.MANUAL)

    applied = await run_stop_request_round(engine=engine_engine, scan_engine=scan_engine)
    assert applied.processed >= 1
    await run_platform_discovery_round(engine=engine_engine, scan_engine=scan_engine)
    async with user_session(api_engine, owner) as session:
        initial = (
            await session.execute(
                "SELECT discovery_complete FROM platform_stop_progress WHERE stop_id=:stop",
                {"stop": stop.stop_id},
            )
        ).scalar_one()
    assert not initial, "owner inventory alone must not mark incomplete child jobs stopped"
    summary_revision = 0
    reconciliation_revision = 0
    for _ in range(20):
        await run_platform_discovery_round(engine=engine_engine, scan_engine=scan_engine)
        await run_risk_stop_round(engine=engine_engine, scan_engine=scan_engine, limit=100)
        await run_platform_discovery_round(engine=engine_engine, scan_engine=scan_engine)
        async with user_session(api_engine, owner) as session:
            progress = (
                await session.execute(
                    """SELECT p.discovery_complete,p.pending_count,p.failed_count,p.revision,
                      c.revision reconciliation_revision
                    FROM platform_stop_progress p CROSS JOIN trading_reconciliation_clock c
                    WHERE p.stop_id=:stop AND c.singleton""",
                    {"stop": stop.stop_id},
                )
            ).one()
        if progress.discovery_complete and progress.pending_count == 0:
            assert progress.failed_count == 0
            summary_revision = int(progress.revision)
            reconciliation_revision = int(progress.reconciliation_revision)
            break
    else:
        pytest.fail("platform stop did not reach a resumable snapshot")

    rolled_back_before, rolled_back_inside = await _touch_position_activity(
        migrator_engine, wallet.episode_id, commit=False
    )
    assert rolled_back_before == reconciliation_revision
    assert rolled_back_inside == reconciliation_revision + 1
    async with migrator_engine.connect() as connection:
        after_rollback = int(
            (
                await connection.execute(
                    text("SELECT revision FROM trading_reconciliation_clock WHERE singleton")
                )
            ).scalar_one()
        )
    assert after_rollback == reconciliation_revision

    committed_before, committed_after = await _touch_position_activity(
        migrator_engine, wallet.episode_id, commit=True
    )
    assert committed_before == reconciliation_revision
    assert committed_after == reconciliation_revision + 1

    async with user_session(api_engine, owner) as session:
        stale = await submit_request(
            session,
            mode=None,
            action=StopAction.RESUME,
            key=uuid4(),
            expected_stop_id=stop.stop_id,
            expected_revision=stop.revision,
            expected_summary_revision=summary_revision,
            expected_reconciliation_revision=reconciliation_revision,
            reason_code="PLATFORM_RESUME",
            platform=True,
        )
    rejected = await run_stop_request_round(engine=engine_engine, scan_engine=scan_engine)
    assert rejected.processed >= 1
    async with user_session(api_engine, owner) as session:
        stale_result = await receipt_by_id(session, stale.request_id)
        assert stale_result is not None
        assert stale_result.state == "REJECTED"
        assert stale_result.failure_code == "TRADING_STOP_NOT_READY"
        fresh_clock_stale_summary = await _submit_platform_resume(
            session,
            stop,
            summary_revision=summary_revision,
            reconciliation_revision=committed_after,
        )
    await run_stop_request_round(engine=engine_engine, scan_engine=scan_engine)
    async with user_session(api_engine, owner) as session:
        rejected_snapshot = await receipt_by_id(session, fresh_clock_stale_summary.request_id)
        assert rejected_snapshot is not None and rejected_snapshot.state == "REJECTED"

    await _touch_position_activity(
        migrator_engine, wallet.episode_id, commit=True, availability="CONFLICTED"
    )
    await run_platform_discovery_round(engine=engine_engine, scan_engine=scan_engine)
    async with user_session(api_engine, owner) as session:
        invalid = (
            await session.execute(
                "SELECT revision,reconciliation_revision,discovery_complete "
                "FROM platform_stop_progress WHERE stop_id=:stop",
                {"stop": stop.stop_id},
            )
        ).one()
        assert not invalid.discovery_complete
        conflicted_resume = await _submit_platform_resume(
            session,
            stop,
            summary_revision=invalid.revision,
            reconciliation_revision=invalid.reconciliation_revision,
        )
    await run_stop_request_round(engine=engine_engine, scan_engine=scan_engine)
    async with user_session(api_engine, owner) as session:
        rejected_conflict = await receipt_by_id(session, conflicted_resume.request_id)
        assert rejected_conflict is not None and rejected_conflict.state == "REJECTED"
        assert await current_opening_blocked(session, TradingMode.PAPER, OrderOrigin.MANUAL)

    await _touch_position_activity(
        migrator_engine, wallet.episode_id, commit=True, availability="READY"
    )
    await run_platform_discovery_round(engine=engine_engine, scan_engine=scan_engine)
    async with user_session(api_engine, owner) as session:
        refreshed = (
            await session.execute(
                "SELECT revision,reconciliation_revision FROM platform_stop_progress "
                "WHERE stop_id=:stop",
                {"stop": stop.stop_id},
            )
        ).one()
        await _submit_platform_resume(
            session,
            stop,
            summary_revision=refreshed.revision,
            reconciliation_revision=refreshed.reconciliation_revision,
        )
    resumed = await run_stop_request_round(engine=engine_engine, scan_engine=scan_engine)
    assert resumed.processed >= 1
    async with user_session(api_engine, owner) as session:
        assert not await current_opening_blocked(session, TradingMode.PAPER, OrderOrigin.MANUAL)
    other_owner = uuid4()
    await create_user(api_engine, other_owner)
    async with user_session(api_engine, other_owner) as session:
        assert not await current_opening_blocked(session, TradingMode.PAPER, OrderOrigin.MANUAL)
    refused = _failed_upgrade_or_downgrade("downgrade", "0061")
    assert "platform reconciliation snapshot history prevents downgrade" in refused.stderr
    async with migrator_engine.connect() as connection:
        assert (
            await connection.execute(text("SELECT version_num FROM alembic_version"))
        ).scalar_one() == "0062"


@pytest.mark.parametrize("cause", ["LOSS_LIMIT", "SYSTEM"])
@pytest.mark.parametrize("user_first", [False, True])
async def test_resuming_one_cause_keeps_other_cause_visible(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    cause: str,
    user_first: bool,
) -> None:
    async with user_session(api_engine, owner) as session:
        await select_use(session, AccountUse.BOT)

    async def stop_user() -> UUID:
        async with user_session(api_engine, owner) as session:
            receipt = await submit_request(
                session,
                mode=TradingMode.PAPER,
                action=StopAction.STOP,
                key=uuid4(),
                reason_code="USER_REQUEST",
            )
        return receipt.stop_id

    async def stop_system() -> UUID:
        identity = uuid4()
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await session.execute(
                """INSERT INTO trading_stop_requests
                (id,user_id,scope_owner_id,mode,action,cause,actor_role,idempotency_key,
                 fingerprint,reason_code,generation)
                VALUES(:id,:owner,:owner,'PAPER','STOP',:cause,'SYSTEM',:id,
                  repeat('0',64),'SOURCE_STOP',1)""",
                {"id": identity, "owner": owner, "cause": cause},
            )
            await session.execute(
                "INSERT INTO trading_stop_dispatch(request_id,user_id) VALUES(:id,:owner)",
                {"id": identity, "owner": owner},
            )
        return identity

    if user_first:
        user_stop, system_stop = await stop_user(), await stop_system()
    else:
        system_stop, user_stop = await stop_system(), await stop_user()
    for _ in range(2):
        await run_stop_request_round(engine=engine_engine, scan_engine=scan_engine)
    async with user_session(api_engine, owner) as session:
        before = await read_status(session, TradingMode.PAPER)
        assert {item.value for item in before.active_causes} == {"USER", cause}
        # The inbox accepts an exact cause-specific resume independently of
        # which unresolved cause currently owns the primary UI summary.
        revision = (
            await session.execute(
                "SELECT revision FROM trading_stop_requests WHERE id=:id", {"id": user_stop}
            )
        ).scalar_one()
        resume = await submit_request(
            session,
            mode=TradingMode.PAPER,
            action=StopAction.RESUME,
            key=uuid4(),
            expected_stop_id=user_stop,
            expected_revision=revision,
            expected_summary_revision=0,
            expected_reconciliation_revision=0,
            reason_code="USER_RESUME",
        )
    await run_stop_request_round(engine=engine_engine, scan_engine=scan_engine)
    async with user_session(api_engine, owner) as session:
        outcome = await receipt_by_id(session, resume.request_id)
        assert outcome is not None and outcome.state == "APPLIED"
        remaining = await read_status(session, TradingMode.PAPER)
        assert remaining.stop_id == system_stop
        assert remaining.cause is not None and remaining.cause.value == cause
        assert [item.value for item in remaining.active_causes] == [cause]
        assert remaining.progress is StopProgress.STOPPED
        assert not remaining.resume_ready
        assert await current_opening_blocked(session, TradingMode.PAPER, OrderOrigin.BOT)


async def test_platform_discovery_skips_locked_owner_then_retries_without_losing_it(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
) -> None:
    other = uuid4()
    await create_user(api_engine, other)
    await create_production_wallet(api_engine, engine_engine, scan_engine, owner)
    await create_production_wallet(api_engine, engine_engine, scan_engine, other)
    locked, available = sorted((owner, other))
    async with migrator_engine.begin() as connection:
        await connection.execute(
            text("ALTER TABLE platform_memberships NO FORCE ROW LEVEL SECURITY")
        )
        await connection.execute(
            text("""INSERT INTO platform_memberships(user_id,role,created_by)
              SELECT :owner,'PLATFORM_ADMIN',user_id FROM platform_memberships
              WHERE role='PLATFORM_OWNER' ORDER BY user_id LIMIT 1"""),
            {"owner": owner},
        )
        await connection.execute(text("ALTER TABLE platform_memberships FORCE ROW LEVEL SECURITY"))
    async with user_session(api_engine, owner) as session:
        stop = await submit_request(
            session,
            mode=None,
            action=StopAction.STOP,
            key=uuid4(),
            reason_code="PLATFORM_INCIDENT",
            reason_text="locked owner regression",
            platform=True,
        )
    await run_stop_request_round(engine=engine_engine, scan_engine=scan_engine)
    async with user_session(engine_engine, locked, role=DatabaseRole.ENGINE) as held:
        await held.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(:key,0))",
            {"key": f"paper-wallet:{locked}"},
        )
        result = await asyncio.wait_for(
            run_platform_discovery_round(engine=engine_engine, scan_engine=scan_engine, limit=100),
            timeout=3,
        )
        assert result.deferred == 1
        async with user_session(api_engine, available) as session:
            assert (
                await session.execute(
                    "SELECT count(*) FROM platform_stop_targets WHERE stop_id=:stop",
                    {"stop": stop.stop_id},
                )
            ).scalar_one() == 1
        async with user_session(api_engine, locked) as session:
            assert (
                await session.execute(
                    "SELECT count(*) FROM platform_stop_targets WHERE stop_id=:stop",
                    {"stop": stop.stop_id},
                )
            ).scalar_one() == 0
        async with user_session(api_engine, owner) as session:
            assert not (
                await session.execute(
                    "SELECT discovery_complete FROM platform_stop_progress WHERE stop_id=:stop",
                    {"stop": stop.stop_id},
                )
            ).scalar_one()
    recovered = await asyncio.gather(
        *(
            run_platform_discovery_round(engine=engine_engine, scan_engine=scan_engine)
            for _ in range(2)
        )
    )
    assert sum(result.discovered for result in recovered) == 1
    async with user_session(api_engine, locked) as session:
        assert (
            await session.execute(
                "SELECT count(*) FROM platform_stop_targets WHERE stop_id=:stop",
                {"stop": stop.stop_id},
            )
        ).scalar_one() == 1
