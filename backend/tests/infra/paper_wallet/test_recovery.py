from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Result
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.infra.db import (
    DatabaseRole,
    InfraError,
    UserSession,
    repeatable_user_session,
    scan_session_bypassing_rls,
    user_session,
)
from tiewtrade.infra.paper_wallet import (
    ClaimedPaperCommand,
    PaperCommand,
    PaperCommandState,
    PaperWalletAction,
    admit_command,
    claim_command,
    due_hints,
    get_command,
    get_wallet,
    process_claimed,
)
from tiewtrade.services.engine import paper_wallet as worker

from .test_storage import _submit


async def _force_due(engine: AsyncEngine, owner: UUID, command_id: UUID) -> None:
    async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
        await session.execute(
            """UPDATE paper_wallet_command_dispatch
               SET next_attempt_at=clock_timestamp()-interval '1 second',
                   claim_expires_at=CASE WHEN claim_id IS NULL THEN NULL
                                         ELSE clock_timestamp()-interval '1 second' END
               WHERE command_id=:command""",
            {"command": command_id},
        )


async def _financial_counts(
    engine: AsyncEngine, owner: UUID, command_id: UUID
) -> tuple[int, int, int, int, int, int]:
    async with user_session(engine, owner) as session:
        row = (
            await session.execute(
                """SELECT
                     (SELECT count(*) FROM paper_wallets WHERE user_id=:owner) wallets,
                     (SELECT count(*) FROM paper_wallet_episodes WHERE user_id=:owner) episodes,
                     (SELECT count(*) FROM paper_wallet_state WHERE user_id=:owner) states,
                     (SELECT count(*) FROM paper_wallet_ledger WHERE user_id=:owner) ledger,
                     (SELECT count(*) FROM paper_wallet_command_results
                        WHERE user_id=:owner AND command_id=:command) results,
                     (SELECT count(*) FROM audit_events
                        WHERE owner_user_id=:owner AND action='PAPER_WALLET_CREATED'
                          AND details->>'command_id'=:command_text) audits""",
                {
                    "owner": owner,
                    "command": command_id,
                    "command_text": str(command_id),
                },
            )
        ).one()
    return tuple(int(value) for value in row)  # type: ignore[return-value]


@pytest.mark.parametrize(
    "fault_after",
    [
        "INSERT INTO paper_wallets",
        "INSERT INTO paper_wallet_episodes",
        "INSERT INTO paper_wallet_state",
        "INSERT INTO paper_wallet_ledger",
        "INSERT INTO paper_wallet_command_results",
        "INSERT INTO audit_events",
    ],
)
async def test_create_rolls_back_every_financial_write_and_recovers(
    monkeypatch: pytest.MonkeyPatch,
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    fault_after: str,
) -> None:
    command = await _submit(api_engine, owner, uuid4())
    original_execute = UserSession.execute
    injected = False

    async def fail_after_write(
        session: UserSession,
        statement: str,
        parameters: Mapping[str, object] | None = None,
    ) -> Result[Any]:
        nonlocal injected
        result = await original_execute(session, statement, parameters)
        if session.user_id == owner and not injected and fault_after in statement:
            injected = True
            raise InfraError("injected paper-wallet write failure")
        return result

    monkeypatch.setattr(UserSession, "execute", fail_after_write)
    failed = await worker.run_paper_wallet_round(
        engine=engine_engine, scan_engine=scan_engine, worker="fault-worker"
    )

    assert injected
    assert failed.deferred == 1
    assert await _financial_counts(api_engine, owner, command.command_id) == (0, 0, 0, 0, 0, 0)

    await _force_due(engine_engine, owner, command.command_id)
    recovered = await worker.run_paper_wallet_round(
        engine=engine_engine, scan_engine=scan_engine, worker="recovery-worker"
    )

    assert recovered.processed == 1
    assert await _financial_counts(api_engine, owner, command.command_id) == (1, 1, 1, 1, 1, 1)


@pytest.mark.parametrize(
    "fault_after,capital",
    [
        ("INSERT INTO paper_wallet_commands", "1500"),
        ("INSERT INTO paper_wallet_command_dispatch", "1500"),
        ("INSERT INTO paper_wallet_admission_results", "1000"),
        ("INSERT INTO audit_events", "1000"),
    ],
)
async def test_admission_fault_rolls_back_and_same_key_can_retry(
    monkeypatch: pytest.MonkeyPatch,
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    fault_after: str,
    capital: str,
) -> None:
    from tiewtrade.infra.paper_wallet import PaperWalletAction, admit_command

    key = uuid4()
    original_execute = UserSession.execute
    injected = False

    async def fail_after_write(
        session: UserSession,
        statement: str,
        parameters: Mapping[str, object] | None = None,
    ) -> Result[Any]:
        nonlocal injected
        result = await original_execute(session, statement, parameters)
        if not injected and fault_after in statement:
            injected = True
            raise InfraError("injected paper-wallet admission failure")
        return result

    monkeypatch.setattr(UserSession, "execute", fail_after_write)
    with pytest.raises(InfraError):
        async with user_session(api_engine, owner) as session:
            await admit_command(
                session,
                action=PaperWalletAction.CREATE,
                idempotency_key=key,
                capital_text=capital,
                expected_episode_id=None,
            )

    async with user_session(api_engine, owner) as session:
        counts = (
            await session.execute(
                """SELECT
                     (SELECT count(*) FROM paper_wallet_commands
                        WHERE user_id=:owner AND idempotency_key=:key),
                     (SELECT count(*) FROM paper_wallet_admission_results
                        WHERE user_id=:owner AND idempotency_key=:key),
                     (SELECT count(*) FROM audit_events
                        WHERE owner_user_id=:owner
                          AND action='PAPER_WALLET_CREATE_REJECTED')""",
                {"owner": owner, "key": key},
            )
        ).one()
    assert tuple(counts) == (0, 0, 0)

    async with user_session(api_engine, owner) as session:
        retry = await admit_command(
            session,
            action=PaperWalletAction.CREATE,
            idempotency_key=key,
            capital_text=capital,
            expected_episode_id=None,
        )
    assert retry.state is (
        PaperCommandState.PENDING if capital == "1500" else PaperCommandState.REJECTED
    )
    if retry.state is PaperCommandState.PENDING:
        processed = await worker.run_paper_wallet_round(
            engine=engine_engine, scan_engine=scan_engine, worker="admission-cleanup"
        )
        assert processed.processed == 1


async def test_expired_claim_recovers_after_worker_restart_without_duplicate_money(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
) -> None:
    command = await _submit(api_engine, owner, uuid4())
    async with scan_session_bypassing_rls(scan_engine) as scan:
        due = next(
            candidate
            for candidate in await due_hints(scan)
            if candidate.command_id == command.command_id
        )
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        abandoned = await claim_command(session, due, worker="worker-before-restart")
    assert abandoned is not None

    before_expiry = await worker.run_paper_wallet_round(
        engine=engine_engine, scan_engine=scan_engine, worker="worker-after-restart"
    )
    assert before_expiry == worker.PaperWalletRound()

    await _force_due(engine_engine, owner, command.command_id)
    recovered = await worker.run_paper_wallet_round(
        engine=engine_engine, scan_engine=scan_engine, worker="worker-after-restart"
    )
    replay_scan = await worker.run_paper_wallet_round(
        engine=engine_engine, scan_engine=scan_engine, worker="duplicate-scan"
    )

    assert recovered.processed == 1
    assert replay_scan == worker.PaperWalletRound()
    assert await _financial_counts(api_engine, owner, command.command_id) == (1, 1, 1, 1, 1, 1)


async def test_infrastructure_backoff_is_bounded_and_command_recovers(
    monkeypatch: pytest.MonkeyPatch,
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
) -> None:
    command = await _submit(api_engine, owner, uuid4())

    async def unavailable(_session: UserSession, _claimed: ClaimedPaperCommand) -> PaperCommand:
        raise InfraError("injected infrastructure outage")

    monkeypatch.setattr(worker, "process_claimed", unavailable)
    observed: list[tuple[int, float]] = []
    for attempt in range(1, 6):
        result = await worker.run_paper_wallet_round(
            engine=engine_engine, scan_engine=scan_engine, worker=f"backoff-{attempt}"
        )
        assert result.deferred == 1
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            row = (
                await session.execute(
                    """SELECT attempts,
                              extract(epoch FROM (next_attempt_at-clock_timestamp())) delay,
                              claim_id,claim_expires_at
                       FROM paper_wallet_command_dispatch WHERE command_id=:command""",
                    {"command": command.command_id},
                )
            ).one()
        observed.append((row.attempts, float(row.delay)))
        assert row.claim_id is None and row.claim_expires_at is None
        await _force_due(engine_engine, owner, command.command_id)

    assert [attempts for attempts, _ in observed] == [1, 2, 3, 4, 5]
    for (_, actual), expected in zip(observed, (1, 5, 30, 300, 300), strict=True):
        assert expected - 1 <= actual <= expected

    monkeypatch.setattr(worker, "process_claimed", process_claimed)
    recovered = await worker.run_paper_wallet_round(
        engine=engine_engine, scan_engine=scan_engine, worker="backoff-recovered"
    )
    assert recovered.processed == 1
    assert await _financial_counts(api_engine, owner, command.command_id) == (1, 1, 1, 1, 1, 1)


async def test_unknown_failure_does_not_starve_another_owner_and_expires_safely(
    monkeypatch: pytest.MonkeyPatch,
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
) -> None:
    from tiewtrade.infra.users import create_user

    healthy_owner = uuid4()
    await create_user(api_engine, healthy_owner)
    broken = await _submit(api_engine, owner, uuid4())
    healthy = await _submit(api_engine, healthy_owner, uuid4())

    async def crash_one(session: UserSession, claimed: ClaimedPaperCommand) -> PaperCommand:
        if claimed.user_id == owner:
            raise RuntimeError("injected programming error")
        return await process_claimed(session, claimed)

    monkeypatch.setattr(worker, "process_claimed", crash_one)
    result = await worker.run_paper_wallet_round(
        engine=engine_engine, scan_engine=scan_engine, worker="fairness-worker"
    )
    assert result.deferred == 1 and result.processed == 1
    async with user_session(api_engine, healthy_owner) as session:
        healthy_result = await get_command(session, healthy.command_id)
    assert healthy_result is not None
    assert healthy_result.state is PaperCommandState.SUCCEEDED
    assert healthy_result.snapshot is not None
    assert await _financial_counts(api_engine, owner, broken.command_id) == (0, 0, 0, 0, 0, 0)

    monkeypatch.setattr(worker, "process_claimed", process_claimed)
    await _force_due(engine_engine, owner, broken.command_id)
    recovered = await worker.run_paper_wallet_round(
        engine=engine_engine, scan_engine=scan_engine, worker="fairness-recovery"
    )
    assert recovered.processed == 1


async def test_parallel_different_keys_create_one_wallet_and_one_rejection(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
) -> None:
    first, second = await asyncio.gather(
        _submit(api_engine, owner, uuid4(), "1500"),
        _submit(api_engine, owner, uuid4(), "2500"),
    )
    for round_number in range(3):
        await asyncio.gather(
            worker.run_paper_wallet_round(
                engine=engine_engine,
                scan_engine=scan_engine,
                worker=f"parallel-a-{round_number}",
            ),
            worker.run_paper_wallet_round(
                engine=engine_engine,
                scan_engine=scan_engine,
                worker=f"parallel-b-{round_number}",
            ),
        )

    async with user_session(api_engine, owner) as session:
        first_result = await get_command(session, first.command_id)
        second_result = await get_command(session, second.command_id)
        assert first_result is not None and second_result is not None
        states = {first_result.state, second_result.state}
        counts = (
            await session.execute(
                """SELECT
                     (SELECT count(*) FROM paper_wallets WHERE user_id=:owner),
                     (SELECT count(*) FROM paper_wallet_ledger WHERE user_id=:owner),
                     (SELECT count(*) FROM paper_wallet_command_results WHERE user_id=:owner)""",
                {"owner": owner},
            )
        ).one()
    assert states == {PaperCommandState.SUCCEEDED, PaperCommandState.REJECTED}
    assert counts == (1, 1, 2)


async def test_repeatable_snapshot_cannot_mix_episodes_during_pointer_race(
    monkeypatch: pytest.MonkeyPatch,
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
) -> None:
    create = await _submit(api_engine, owner, uuid4(), "1500")
    await worker.run_paper_wallet_round(
        engine=engine_engine, scan_engine=scan_engine, worker="snapshot-setup"
    )
    async with repeatable_user_session(api_engine, owner) as session:
        original = await get_wallet(session)
    assert original is not None
    async with user_session(api_engine, owner) as session:
        reset = await admit_command(
            session,
            action=PaperWalletAction.RESET,
            idempotency_key=uuid4(),
            capital_text="2500",
            expected_episode_id=original.episode_id,
        )

    first_select_done = asyncio.Event()
    writer_done = asyncio.Event()
    paused = False
    original_execute = UserSession.execute

    async def pause_between_snapshot_queries(
        session: UserSession,
        statement: str,
        parameters: Mapping[str, object] | None = None,
    ) -> Result[Any]:
        nonlocal paused
        result = await original_execute(session, statement, parameters)
        if not paused and "FROM paper_wallets w LEFT JOIN" in statement:
            paused = True
            first_select_done.set()
            await writer_done.wait()
        return result

    monkeypatch.setattr(UserSession, "execute", pause_between_snapshot_queries)

    async def read_during_change() -> Any:
        async with repeatable_user_session(api_engine, owner) as session:
            return await get_wallet(session)

    reader = asyncio.create_task(read_during_change())
    await first_select_done.wait()
    new_episode = uuid4()
    reset_command = reset.command_id
    new_ledger = uuid4()
    try:
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as writer_session:
            parameters = {
                "command": reset_command,
                "owner": owner,
                "old_episode": original.episode_id,
                "new_episode": new_episode,
                "wallet": original.wallet_id,
                "ledger": new_ledger,
            }
            statements = (
                """INSERT INTO paper_wallet_episodes
                   (id,wallet_id,user_id,sequence,initial_capital,currency)
                   VALUES (:new_episode,:wallet,:owner,2,2500,'USDT')""",
                """INSERT INTO paper_wallet_episode_closures
                   (episode_id,wallet_id,user_id,reset_command_id)
                   VALUES (:old_episode,:wallet,:owner,:command)""",
                """INSERT INTO paper_wallet_ledger
                   (id,user_id,wallet_id,episode_id,kind,amount,currency,source_command_id)
                   VALUES (:ledger,:owner,:wallet,:new_episode,'EXTERNAL_CAPITAL',
                           2500,'USDT',:command)""",
                """UPDATE paper_wallet_state SET active_episode_id=:new_episode,
                          revision=revision+1 WHERE wallet_id=:wallet""",
                """INSERT INTO paper_wallet_command_results
                   (command_id,user_id,state,wallet_id,episode_id,
                    initial_capital,balance,currency)
                   VALUES (:command,:owner,'SUCCEEDED',:wallet,:new_episode,
                           2500,2500,'USDT')""",
            )
            for statement in statements:
                await writer_session.execute(statement, parameters)
    finally:
        writer_done.set()

    during = await reader
    assert during is not None
    assert during.episode_id == original.episode_id
    assert during.initial_capital.as_parts()["amount"] == "1500"
    assert during.balance.as_parts()["amount"] == "1500"
    assert during.revision == original.revision

    async with repeatable_user_session(api_engine, owner) as session:
        after = await get_wallet(session)
    assert after is not None
    assert after.episode_id == new_episode
    assert after.initial_capital.as_parts()["amount"] == "2500"
    assert after.balance.as_parts()["amount"] == "2500"
    assert after.revision == original.revision + 1
    async with user_session(api_engine, owner) as session:
        create_replay = await get_command(session, create.command_id)
        replay = await get_command(session, reset_command)
    assert create_replay is not None
    assert create_replay.state is PaperCommandState.SUCCEEDED
    assert create_replay.snapshot is not None
    assert create_replay.snapshot.wallet_id == original.wallet_id
    assert create_replay.snapshot.episode_id == original.episode_id
    assert create_replay.snapshot.initial_capital.as_parts()["amount"] == "1500"
    assert create_replay.snapshot.balance.as_parts()["amount"] == "1500"
    assert replay is not None
    assert replay.state is PaperCommandState.SUCCEEDED
    assert replay.snapshot is not None
    assert replay.snapshot.wallet_id == original.wallet_id
    assert replay.snapshot.episode_id == new_episode
    assert replay.snapshot.initial_capital.as_parts()["amount"] == "2500"
    assert replay.snapshot.balance.as_parts()["amount"] == "2500"
