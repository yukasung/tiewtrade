"""R11 real-role source hints, fenced one-shot claims and unchanged retry schedule."""

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, replace
from datetime import datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.risk_limits.migration_support import (
    restore_risk_protocol,
    stop_risk_protocol,
)
from tests.infra.risk_limits.test_execution import Runtime, runtime
from tests.infra.risk_limits.test_same_pair_dispatch import Queue, resting
from tests.infra.risk_limits.test_same_pair_dispatch import queue as queue
from tiewtrade.infra.db import DatabaseRole, scan_session_bypassing_rls, user_session
from tiewtrade.infra.db.session import market_data_session
from tiewtrade.infra.market_data.order_book_storage import invalidate_book
from tiewtrade.infra.market_data.realtime_storage import read_snapshot, set_connected
from tiewtrade.infra.paper_orders.dispatch import (
    ClaimedOrder,
    DueOrder,
    OrderClaimLostError,
    claim_order,
    defer_claim,
    due_orders,
    finish_claim,
    require_claim,
    submit_cancel,
    submit_order,
)
from tiewtrade.infra.paper_orders.worker import process_claimed_order
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot
from tiewtrade.infra.risk_limits.policy import TransactionalRiskPolicy


@dataclass(frozen=True)
class Waiting:
    owner: UUID
    command: UUID
    order: UUID
    due: datetime
    failed: ClaimedOrder
    sources: Runtime


@pytest.fixture
async def waiting(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> AsyncIterator[Waiting]:
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000"
    ) as sources:
        value = resting(owner, wallet.episode_id)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as s:
            command = await submit_order(s, wallet_id=wallet.wallet_id, intent=value)
            # Set up the third ordinary failure without spending six seconds per
            # scheduling invariant. The native 1/5/30 cadence is tested separately.
            due = (
                await s.execute(
                    """UPDATE paper_order_dispatch SET attempts=2
                WHERE command_id=:id RETURNING next_attempt_at""",
                    {"id": command.command_id},
                )
            ).scalar_one()
            failed = await claim_order(
                s, DueOrder(command.command_id, owner, due, source_resumption=True), worker="r11"
            )
        assert failed is not None
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as s:
            await defer_claim(s, failed, source_unavailable=True)
            due = (await s.execute("SELECT next_attempt_at FROM paper_order_dispatch")).scalar_one()
        try:
            yield Waiting(owner, command.command_id, value.order_id, due, failed, sources)
        finally:
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as s:
                await s.execute("""UPDATE paper_order_dispatch SET state='TERMINAL',
                  worker=NULL,claim_id=NULL,lease_until=NULL""")


async def hints(scan: AsyncEngine, waiting: Waiting, **options: bool) -> tuple[DueOrder, ...]:
    async with scan_session_bypassing_rls(scan) as s:
        found = await due_orders(s, source_resumption=True, **options)
    return tuple(d for d in found if d.user_id == waiting.owner)


async def resumed(scan: AsyncEngine, waiting: Waiting, **options: bool) -> DueOrder:
    await waiting.sources.next_book()
    await waiting.sources.price("100")
    found = await hints(scan, waiting, **options)
    assert len(found) == 1
    return found[0]


@pytest.mark.parametrize("mode", ["r8", "r9", "r10"])
async def test_both_publications_required_and_early_head_is_direct(
    waiting: Waiting, scan_engine: AsyncEngine, engine_engine: AsyncEngine, mode: str
) -> None:
    options = {"prefer_same_pair": mode != "r8", "admission_first": mode == "r10"}
    assert not await hints(scan_engine, waiting, **options)
    await waiting.sources.next_book()
    assert not await hints(scan_engine, waiting, **options)
    await waiting.sources.price("100")
    (due,) = await hints(scan_engine, waiting, **options)
    assert due.source_wait_revision == waiting.failed.revision
    assert due.anchor_command_id is None and due.next_attempt_at == waiting.due
    async with scan_session_bypassing_rls(scan_engine) as s:
        assert not any(d.user_id == waiting.owner for d in await due_orders(s))
    async with user_session(engine_engine, waiting.owner, role=DatabaseRole.ENGINE) as s:
        claim = await claim_order(s, due, worker="r11-probe")
        row = (
            await s.execute(
                "SELECT attempts,lease_until,next_attempt_at,source_resume_used,"
                "source_resume_claim FROM paper_order_dispatch"
            )
        ).one()
        assert claim is not None and claim.revision == waiting.failed.revision + 1
        assert row.attempts == 3 and row.source_resume_used and row.source_resume_claim
        assert row.lease_until == row.next_attempt_at == waiting.due
    async with user_session(engine_engine, waiting.owner, role=DatabaseRole.ENGINE) as s:
        assert await claim_order(s, due, worker="duplicate") is None
        await process_claimed_order(s, claim, policy=TransactionalRiskPolicy())
        row = (
            await s.execute(
                "SELECT attempts,source_wait_since,source_wait_revision,"
                "source_resume_used,source_resume_claim FROM paper_order_dispatch"
            )
        ).one()
        assert tuple(row) == (0, None, None, False, False)
        assert (await s.execute("SELECT count(*) FROM paper_orders")).scalar_one() == 1


@pytest.mark.parametrize("source_error", [True, False])
async def test_failed_probe_preserves_due_attempts_and_cannot_probe_again(
    waiting: Waiting, scan_engine: AsyncEngine, engine_engine: AsyncEngine, source_error: bool
) -> None:
    due = await resumed(scan_engine, waiting)
    async with user_session(engine_engine, waiting.owner, role=DatabaseRole.ENGINE) as s:
        claim = await claim_order(s, due, worker="probe")
    assert claim is not None
    async with user_session(engine_engine, waiting.owner, role=DatabaseRole.ENGINE) as s:
        await defer_claim(s, claim, source_unavailable=source_error)
        row = (
            await s.execute(
                "SELECT attempts,next_attempt_at,source_resume_used,"
                "source_resume_claim FROM paper_order_dispatch"
            )
        ).one()
        assert tuple(row) == (3, waiting.due, True, False)
    await waiting.sources.next_book()
    await waiting.sources.price("100")
    assert not await hints(scan_engine, waiting)
    async with user_session(engine_engine, waiting.owner, role=DatabaseRole.ENGINE) as s:
        ordinary_due = (
            await s.execute(
                "UPDATE paper_order_dispatch SET next_attempt_at="
                "clock_timestamp() RETURNING next_attempt_at"
            )
        ).scalar_one()
        ordinary = await claim_order(
            s,
            DueOrder(waiting.command, waiting.owner, ordinary_due, source_resumption=True),
            worker="normal",
        )
        assert ordinary is not None
        await defer_claim(s, ordinary, source_unavailable=True)
        row = (
            await s.execute(
                "SELECT attempts,source_resume_used,source_wait_since,"
                "extract(epoch FROM next_attempt_at-clock_timestamp()) delay "
                "FROM paper_order_dispatch"
            )
        ).one()
        assert row.attempts == 4 and row.source_resume_used and row.source_wait_since is None
        assert 298 < row.delay <= 300
        await defer_claim(s, claim, source_unavailable=True)
        assert (await s.execute("SELECT attempts FROM paper_order_dispatch")).scalar_one() == 4


@pytest.mark.parametrize(
    "invalid", ["revision", "due", "pair", "cancel", "unknown", "book", "price"]
)
async def test_stale_scan_is_rechecked_under_owner_lock(
    waiting: Waiting,
    wallet: PaperWalletSnapshot,
    scan_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    invalid: str,
) -> None:
    due = await resumed(scan_engine, waiting)
    async with user_session(engine_engine, waiting.owner, role=DatabaseRole.ENGINE) as s:
        if invalid == "revision":
            await s.execute("UPDATE paper_order_dispatch SET source_wait_revision=0")
        elif invalid == "due":
            await s.execute(
                "UPDATE paper_order_dispatch "
                "SET next_attempt_at=next_attempt_at+interval '1 second'"
            )
        elif invalid == "pair":
            await s.execute("UPDATE paper_order_dispatch SET routing_base='ETH'")
        elif invalid == "cancel":
            await submit_cancel(
                s,
                wallet_id=wallet.wallet_id,
                episode_id=wallet.episode_id,
                order_id=waiting.order,
                idempotency_key=uuid4(),
            )
        elif invalid == "unknown":
            other = await submit_order(
                s, wallet_id=wallet.wallet_id, intent=resting(waiting.owner, wallet.episode_id)
            )
            await s.execute(
                "UPDATE paper_order_dispatch SET routing_action=NULL WHERE command_id=:id",
                {"id": other.command_id},
            )
    if invalid in ("book", "price"):
        async with market_data_session(waiting.sources.market) as s:
            if invalid == "book":
                await invalidate_book(s, waiting.sources.lease, "DISCONNECTED")
            else:
                snapshot = await read_snapshot(s)
                assert snapshot.feed is not None
                await set_connected(s, snapshot.feed, False)
    async with user_session(engine_engine, waiting.owner, role=DatabaseRole.ENGINE) as s:
        assert await claim_order(s, due, worker="stale") is None


async def test_probe_rollback_does_not_consume_guard_and_commit_ack_loss_does(
    waiting: Waiting, scan_engine: AsyncEngine, engine_engine: AsyncEngine
) -> None:
    due = await resumed(scan_engine, waiting)
    with pytest.raises(RuntimeError, match="rollback"):
        async with user_session(engine_engine, waiting.owner, role=DatabaseRole.ENGINE) as s:
            assert await claim_order(s, due, worker="rollback") is not None
            raise RuntimeError("rollback")
    async with user_session(engine_engine, waiting.owner, role=DatabaseRole.ENGINE) as s:
        won = await claim_order(s, due, worker="committed-ack-lost")
    assert won is not None
    async with user_session(engine_engine, waiting.owner, role=DatabaseRole.ENGINE) as s:
        assert await claim_order(s, due, worker="retry-ack") is None
        # Simulate worker loss and original due becoming eligible, without a30s sleep.
        new_due = (
            await s.execute(
                "UPDATE paper_order_dispatch SET lease_until=clock_timestamp(),"
                "next_attempt_at=clock_timestamp() RETURNING next_attempt_at"
            )
        ).scalar_one()
        recovered = await claim_order(
            s,
            DueOrder(waiting.command, waiting.owner, new_due, source_resumption=True),
            worker="recover",
        )
        assert recovered is not None and recovered.revision == won.revision + 1
        await defer_claim(s, won, source_unavailable=True)
        await require_claim(s, recovered)
    with pytest.raises(OrderClaimLostError):
        async with user_session(engine_engine, waiting.owner, role=DatabaseRole.ENGINE) as s:
            await require_claim(s, won)


async def test_concurrent_claims_have_one_winner(
    waiting: Waiting, scan_engine: AsyncEngine, engine_engine: AsyncEngine
) -> None:
    due = await resumed(scan_engine, waiting)

    async def attempt() -> ClaimedOrder | None:
        async with user_session(engine_engine, waiting.owner, role=DatabaseRole.ENGINE) as s:
            return await claim_order(s, due, worker="race")

    claims = await asyncio.gather(attempt(), attempt())
    assert sum(c is not None for c in claims) == 1


async def test_healthy_old_writer_finish_clears_marker(
    waiting: Waiting, engine_engine: AsyncEngine
) -> None:
    async with user_session(engine_engine, waiting.owner, role=DatabaseRole.ENGINE) as s:
        due = (
            await s.execute(
                "UPDATE paper_order_dispatch SET next_attempt_at=clock_timestamp() "
                "RETURNING next_attempt_at"
            )
        ).scalar_one()
        old = await claim_order(s, DueOrder(waiting.command, waiting.owner, due), worker="old")
        assert old is not None and not old.source_resumption
        await finish_claim(s, old, terminal=False)
        row = (
            await s.execute(
                "SELECT attempts,source_wait_since,source_wait_revision,"
                "source_resume_used,source_resume_claim FROM paper_order_dispatch"
            )
        ).one()
        assert tuple(row) == (0, None, None, False, False)


@pytest.mark.parametrize("source_error", [True, False])
async def test_native_round_marks_only_source_errors_and_keeps_claim_budget(
    waiting: Waiting,
    scan_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
    source_error: bool,
) -> None:
    from unittest.mock import AsyncMock

    from tiewtrade.core.orders import SourceUnavailableError
    from tiewtrade.services.engine import paper_order

    async with user_session(engine_engine, waiting.owner, role=DatabaseRole.ENGINE) as s:
        scheduled = (
            await s.execute(
                "UPDATE paper_order_dispatch SET attempts=0,next_attempt_at=clock_timestamp() "
                "RETURNING next_attempt_at"
            )
        ).scalar_one()
    # This test covers exception classification and claim budgeting, not global
    # scan fairness. Retained commands from other tests must not be its subject.
    monkeypatch.setattr(
        paper_order,
        "due_orders",
        AsyncMock(
            return_value=(
                DueOrder(waiting.command, waiting.owner, scheduled, source_resumption=True),
            )
        ),
    )
    process = AsyncMock(
        side_effect=SourceUnavailableError("controlled")
        if source_error
        else RuntimeError("controlled")
    )
    monkeypatch.setattr(paper_order, "process_claimed_order", process)
    result = await paper_order.run_paper_order_round(
        engine=engine_engine,
        scan_engine=scan_engine,
        worker="source-classification",
        policy=TransactionalRiskPolicy(),
        source_resumption=True,
        claim_limit=1,
    )
    assert result.deferred == 1 and process.await_count == 1
    async with user_session(engine_engine, waiting.owner, role=DatabaseRole.ENGINE) as s:
        row = (
            await s.execute(
                "SELECT source_wait_since,source_wait_revision,claim_revision,attempts,"
                "extract(epoch FROM next_attempt_at-clock_timestamp()) delay "
                "FROM paper_order_dispatch"
            )
        ).one()
        assert (row.source_wait_since is not None) is source_error
        assert (row.source_wait_revision == row.claim_revision) is source_error
        assert row.attempts == 1 and 0 < row.delay <= 1


async def test_short_probe_lease_cannot_publish_after_original_due(
    waiting: Waiting,
    scan_engine: AsyncEngine,
    engine_engine: AsyncEngine,
) -> None:
    await resumed(scan_engine, waiting)
    async with user_session(engine_engine, waiting.owner, role=DatabaseRole.ENGINE) as s:
        due = (
            await s.execute(
                "UPDATE paper_order_dispatch SET next_attempt_at="
                "clock_timestamp()+interval '100 milliseconds' RETURNING next_attempt_at"
            )
        ).scalar_one()
    (hint,) = await hints(scan_engine, waiting)
    async with user_session(engine_engine, waiting.owner, role=DatabaseRole.ENGINE) as s:
        claim = await claim_order(s, hint, worker="short-lease")
        assert claim is not None
        assert (await s.execute("SELECT lease_until FROM paper_order_dispatch")).scalar_one() == due
    await asyncio.sleep(0.12)
    with pytest.raises(OrderClaimLostError):
        async with user_session(engine_engine, waiting.owner, role=DatabaseRole.ENGINE) as s:
            await process_claimed_order(s, claim, policy=TransactionalRiskPolicy())
    async with user_session(engine_engine, waiting.owner, role=DatabaseRole.ENGINE) as s:
        assert (await s.execute("SELECT count(*) FROM paper_orders")).scalar_one() == 0
        ordinary = await claim_order(
            s,
            DueOrder(waiting.command, waiting.owner, due, source_resumption=True),
            worker="normal",
        )
        assert ordinary is not None
        await defer_claim(s, claim, source_unavailable=True)
        await require_claim(s, ordinary)


async def test_scan_grants_are_public_metadata_only(scan_engine: AsyncEngine) -> None:
    from tiewtrade.infra.db.errors import NotPermittedError

    async with scan_session_bypassing_rls(scan_engine) as s:
        await s.execute("SELECT verified_at FROM market_execution_state")
        await s.execute("SELECT received_at FROM market_latest_prices")
        await s.execute("SELECT connected FROM market_price_feed")
    for query in (
        "SELECT book_payload FROM market_execution_state",
        "SELECT amount FROM market_latest_prices",
        "SELECT payload FROM paper_order_commands",
        "UPDATE paper_order_dispatch SET source_resume_used=false",
    ):
        with pytest.raises(NotPermittedError):
            async with scan_session_bypassing_rls(scan_engine) as s:
                await s.execute(query)


async def test_source_hint_never_bypasses_native_gate_or_publishes_partial_order(
    waiting: Waiting,
    scan_engine: AsyncEngine,
    engine_engine: AsyncEngine,
) -> None:
    from tiewtrade.core.orders import SourceUnavailableError

    due = await resumed(scan_engine, waiting)
    async with user_session(engine_engine, waiting.owner, role=DatabaseRole.ENGINE) as s:
        claim = await claim_order(s, due, worker="native-gate")
    assert claim is not None
    async with market_data_session(waiting.sources.market) as s:
        await invalidate_book(s, waiting.sources.lease, "DISCONNECTED")
    with pytest.raises(SourceUnavailableError):
        async with user_session(engine_engine, waiting.owner, role=DatabaseRole.ENGINE) as s:
            await process_claimed_order(s, claim, policy=TransactionalRiskPolicy())
    async with user_session(engine_engine, waiting.owner, role=DatabaseRole.ENGINE) as s:
        await defer_claim(s, claim, source_unavailable=True)
        assert (await s.execute("SELECT count(*) FROM paper_orders")).scalar_one() == 0
        assert (
            await s.execute("SELECT count(*) FROM paper_order_command_results")
        ).scalar_one() == 0
        assert (
            await s.execute("SELECT next_attempt_at FROM paper_order_dispatch")
        ).scalar_one() == waiting.due


@pytest.mark.parametrize("consumed", [False, True])
async def test_0056_default_off_roundtrip_preserves_schedule_and_does_not_rearm(
    waiting: Waiting,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    consumed: bool,
) -> None:
    from tests.infra.db.test_migrations import _alembic
    from tiewtrade.infra.db import create_engine_for

    if consumed:
        due = await resumed(scan_engine, waiting)
        async with user_session(engine_engine, waiting.owner, role=DatabaseRole.ENGINE) as s:
            probe = await claim_order(s, due, worker="consumed-before-downgrade")
            assert probe is not None
            await defer_claim(s, probe, source_unavailable=True)
    flags = await stop_risk_protocol(migrator_engine)
    try:
        _alembic("downgrade", "0056")
        async with scan_session_bypassing_rls(scan_engine) as s:
            assert not any(d.user_id == waiting.owner for d in await due_orders(s))
        async with user_session(engine_engine, waiting.owner, role=DatabaseRole.ENGINE) as s:
            row = (
                await s.execute("SELECT next_attempt_at,attempts FROM paper_order_dispatch")
            ).one()
            assert tuple(row) == (waiting.due, 3)
    finally:
        _alembic("upgrade", "head")
        await restore_risk_protocol(migrator_engine, flags)
    fresh = create_engine_for(DatabaseRole.ENGINE)
    try:
        async with user_session(fresh, waiting.owner, role=DatabaseRole.ENGINE) as s:
            row = (
                await s.execute(
                    "SELECT next_attempt_at,attempts,source_wait_since,source_resume_used "
                    "FROM paper_order_dispatch"
                )
            ).one()
            assert tuple(row) == (waiting.due, 3, None, True)
            assert (
                await s.execute(
                    "SELECT relforcerowsecurity FROM pg_class "
                    "WHERE oid='paper_order_dispatch'::regclass"
                )
            ).scalar_one()
            due = (
                await s.execute(
                    "UPDATE paper_order_dispatch SET next_attempt_at=clock_timestamp() "
                    "RETURNING next_attempt_at"
                )
            ).scalar_one()
            ordinary = await claim_order(
                s,
                DueOrder(waiting.command, waiting.owner, due, source_resumption=True),
                worker="post-upgrade",
            )
            assert ordinary is not None
            await defer_claim(s, ordinary, source_unavailable=True)
            assert (
                await s.execute("SELECT source_wait_since FROM paper_order_dispatch")
            ).scalar_one() is None
    finally:
        await fresh.dispose()


async def test_real_lost_probe_commit_ack_preserves_consumed_guard(
    waiting: Waiting,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
) -> None:
    from sqlalchemy.ext.asyncio import create_async_engine

    from tests.infra.execution_market.commit_proxy import drop_commit_reply
    from tiewtrade.infra.db import InfraError

    chosen = await resumed(scan_engine, waiting)
    armed, dropped = asyncio.Event(), asyncio.Event()
    async with drop_commit_reply(
        engine_engine.url.host or "localhost", engine_engine.url.port or 5432, armed, dropped
    ) as port:
        proxy = create_async_engine(
            engine_engine.url.set(host="127.0.0.1", port=port),
            connect_args={"ssl": False},
            hide_parameters=True,
        )
        try:
            with pytest.raises(InfraError):
                async with user_session(proxy, waiting.owner, role=DatabaseRole.ENGINE) as s:
                    claim = await claim_order(s, chosen, worker="lost-probe-ack")
                    assert claim is not None
                    armed.set()
            assert dropped.is_set()
        finally:
            await proxy.dispose()
    assert claim is not None
    async with user_session(engine_engine, waiting.owner, role=DatabaseRole.ENGINE) as s:
        assert await claim_order(s, chosen, worker="ack-replay") is None
        row = (
            await s.execute(
                "SELECT attempts,next_attempt_at,lease_until,source_resume_used "
                "FROM paper_order_dispatch"
            )
        ).one()
        assert tuple(row) == (3, waiting.due, waiting.due, True)
        await defer_claim(s, claim, source_unavailable=False)
        row = (
            await s.execute(
                "SELECT attempts,next_attempt_at,source_resume_used FROM paper_order_dispatch"
            )
        ).one()
        assert tuple(row) == (3, waiting.due, True)


async def test_source_mode_preserves_ordinary_r9_r10_selection(
    queue: Queue,
    scan_engine: AsyncEngine,
    engine_engine: AsyncEngine,
) -> None:
    options = {"prefer_same_pair": True, "admission_first": queue.admission_first}
    async with scan_session_bypassing_rls(scan_engine) as s:
        ordinary = await due_orders(s, **options)
        enabled = await due_orders(s, source_resumption=True, **options)
    assert tuple(replace(d, source_resumption=False) for d in enabled) == ordinary
    chosen = next(d for d in enabled if d.user_id == queue.owner)
    async with user_session(engine_engine, queue.owner, role=DatabaseRole.ENGINE) as s:
        claim = await claim_order(s, chosen, worker="source-normal")
    assert claim is not None and claim.source_resumption
    await queue.sources.next_book()
    async with user_session(engine_engine, queue.owner, role=DatabaseRole.ENGINE) as s:
        await process_claimed_order(s, claim, policy=TransactionalRiskPolicy())


async def test_probe_rechecks_latch_without_an_order_or_reservation(
    waiting: Waiting,
    scan_engine: AsyncEngine,
    engine_engine: AsyncEngine,
) -> None:
    due = await resumed(scan_engine, waiting)
    async with user_session(engine_engine, waiting.owner, role=DatabaseRole.ENGINE) as s:
        claim = await claim_order(s, due, worker="latch-probe")
        assert claim is not None
        await s.execute("UPDATE risk_limit_settings SET latched=true")
    async with user_session(engine_engine, waiting.owner, role=DatabaseRole.ENGINE) as s:
        await process_claimed_order(s, claim, policy=TransactionalRiskPolicy())
        assert (
            await s.execute("SELECT state FROM paper_order_command_results")
        ).scalar_one() == "REJECTED"
        assert (await s.execute("SELECT count(*) FROM paper_orders")).scalar_one() == 0
        assert (await s.execute("SELECT count(*) FROM paper_reservations")).scalar_one() == 0


async def test_reset_waits_for_pending_order_then_invalidates_probe_identity(
    waiting: Waiting,
    wallet: PaperWalletSnapshot,
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
) -> None:
    from tiewtrade.infra.paper_wallet import PaperWalletAction, admit_command, get_wallet
    from tiewtrade.services.engine.paper_wallet import run_paper_wallet_round

    due = await resumed(scan_engine, waiting)
    async with user_session(api_engine, waiting.owner) as s:
        await admit_command(
            s,
            action=PaperWalletAction.RESET,
            idempotency_key=uuid4(),
            capital_text="20000",
            expected_episode_id=wallet.episode_id,
        )
    await run_paper_wallet_round(engine=engine_engine, scan_engine=scan_engine, worker="r11-reset")
    async with user_session(engine_engine, waiting.owner, role=DatabaseRole.ENGINE) as s:
        current = await get_wallet(s)
        assert current is not None and current.episode_id == wallet.episode_id
        assert current.reset_reason == "RESET_UNSAFE"
        # Existing reset safety rejects a pending command. Settle through the
        # native latched-admission path before retrying reset with a new key.
        await s.execute("UPDATE risk_limit_settings SET latched=true")
        claim = await claim_order(s, due, worker="settle-before-reset")
        assert claim is not None
        await process_claimed_order(s, claim, policy=TransactionalRiskPolicy())
    async with user_session(api_engine, waiting.owner) as s:
        await admit_command(
            s,
            action=PaperWalletAction.RESET,
            idempotency_key=uuid4(),
            capital_text="20000",
            expected_episode_id=wallet.episode_id,
        )
    await run_paper_wallet_round(engine=engine_engine, scan_engine=scan_engine, worker="r11-reset")
    async with user_session(engine_engine, waiting.owner, role=DatabaseRole.ENGINE) as s:
        current = await get_wallet(s)
        assert current is not None and current.episode_id != wallet.episode_id
        assert await claim_order(s, due, worker="old-episode") is None
        assert (await s.execute("SELECT count(*) FROM paper_orders")).scalar_one() == 0
