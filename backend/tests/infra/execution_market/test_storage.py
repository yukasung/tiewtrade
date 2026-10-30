"""Real PostgreSQL roles, fencing, buffer corruption and private demand races."""

import asyncio
from dataclasses import replace
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.order_book_fixtures import capability, snapshot
from tiewtrade.core.order_book import BookState
from tiewtrade.core.orders import SourceUnavailableError
from tiewtrade.core.positions import PositionPair
from tiewtrade.infra.db import DatabaseRole, create_engine_for, user_session
from tiewtrade.infra.db.errors import NotPermittedError
from tiewtrade.infra.db.session import market_data_session
from tiewtrade.infra.market_data.order_book_storage import (
    BookLease,
    ExecutionInputGapError,
    ExecutionMetadata,
    acquire_book_writer,
    invalidate_book,
    publish_input,
    read_inputs,
    renew_book_writer,
    retained_pairs,
    set_pair_dependency,
)
from tiewtrade.infra.market_data.realtime_records import WriterLeaseLost
from tiewtrade.infra.paper_wallet import PaperWalletAction, admit_command, get_wallet
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot
from tiewtrade.infra.users import create_user
from tiewtrade.services.engine.paper_wallet import run_paper_wallet_round

PAIR = PositionPair("BTC", "USDT")


async def prepared(engine: AsyncEngine) -> tuple[BookLease, BookState, ExecutionMetadata]:
    async with market_data_session(engine) as session:
        await session.execute("""UPDATE market_execution_state
          SET lease_until=clock_timestamp()-interval '1 second'
          WHERE base='BTC' AND quote='USDT'""")
        lease = await acquire_book_writer(session, PAIR, uuid4())
        assert lease is not None
        now = (await session.execute("SELECT clock_timestamp()")).scalar_one()
    source = snapshot(now - timedelta(milliseconds=10))
    book = BookState(
        PAIR,
        lease.last_input_id + 1,
        lease.generation,
        source.received_at,
        source.received_at,
        source.bids,
        source.asks,
        True,
        True,
    )
    cap = capability(source.received_at)
    return (
        lease,
        book,
        ExecutionMetadata(cap.market, cap.limit, cap.observed_at, cap.source_document),
    )


async def test_public_inputs_roundtrip_replay_and_takeover_fence(
    engine_engine: AsyncEngine,
) -> None:
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        lease, book, metadata = await prepared(engine)
        async with market_data_session(engine) as session:
            assert await acquire_book_writer(session, PAIR, uuid4()) is None
            updated = await publish_input(session, lease, book, metadata)
            replayed = await publish_input(session, lease, book, metadata)
            assert updated.last_input_id == replayed.last_input_id == book.input_id
        async with user_session(engine_engine, uuid4(), role=DatabaseRole.ENGINE) as session:
            rows = await read_inputs(session, PAIR, after=book.input_id - 1)
            assert len(rows) == 1 and rows[0].market == book
            assert rows[0].metadata == metadata
        async with market_data_session(engine) as session:
            with pytest.raises(ExecutionInputGapError):
                await publish_input(session, lease, replace(book, rebase=False), metadata)
            await invalidate_book(session, lease, "DISCONNECTED")
        async with user_session(engine_engine, uuid4(), role=DatabaseRole.ENGINE) as session:
            with pytest.raises(SourceUnavailableError):
                await read_inputs(session, PAIR, after=book.input_id)
        async with market_data_session(engine) as session:
            await session.execute(
                """UPDATE market_execution_state
                  SET lease_until=clock_timestamp()-interval '1 second'"""
            )
        async with market_data_session(engine) as session:
            newer = await acquire_book_writer(session, PAIR, uuid4())
            assert newer is not None and newer.generation == lease.generation + 1
            with pytest.raises(WriterLeaseLost):
                await renew_book_writer(session, lease)
    finally:
        await engine.dispose()


async def test_missing_corrupt_overwritten_and_stale_inputs_fail_closed(
    engine_engine: AsyncEngine,
) -> None:
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        lease, book, metadata = await prepared(engine)
        async with market_data_session(engine) as session:
            await publish_input(session, lease, book, metadata)
            await session.execute(
                """UPDATE market_execution_buffer SET digest=repeat('0',64)
              WHERE input_id=:input AND base='BTC'""",
                {"input": book.input_id},
            )
        async with user_session(engine_engine, uuid4(), role=DatabaseRole.ENGINE) as session:
            with pytest.raises(ExecutionInputGapError):
                await read_inputs(session, PAIR, after=book.input_id - 1)
        async with market_data_session(engine) as session:
            await session.execute(
                """UPDATE market_execution_buffer SET payload='{}'::jsonb
              WHERE base='BTC' AND input_id=:input""",
                {"input": book.input_id},
            )
        async with user_session(engine_engine, uuid4(), role=DatabaseRole.ENGINE) as session:
            with pytest.raises(ExecutionInputGapError):
                await read_inputs(session, PAIR, after=book.input_id - 1)
        async with market_data_session(engine) as session:
            await session.execute(
                """UPDATE market_execution_state SET last_input_id=:input
              WHERE base='BTC'""",
                {"input": book.input_id + 4096},
            )
        async with user_session(engine_engine, uuid4(), role=DatabaseRole.ENGINE) as session:
            with pytest.raises(ExecutionInputGapError):
                await read_inputs(session, PAIR, after=book.input_id - 1)
        async with market_data_session(engine) as session:
            await session.execute("""UPDATE market_execution_state
              SET verified_at=clock_timestamp()-interval '2 seconds' WHERE base='BTC'""")
            await renew_book_writer(session, lease)
        async with user_session(engine_engine, uuid4(), role=DatabaseRole.ENGINE) as session:
            with pytest.raises(SourceUnavailableError):
                await read_inputs(session, PAIR, after=0)
    finally:
        await engine.dispose()


async def test_market_data_and_api_cannot_read_private_dependencies(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    pair = PositionPair("WITHDRAWN", "USDT")
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await set_pair_dependency(
            session,
            wallet_id=wallet.wallet_id,
            episode_id=wallet.episode_id,
            pair=pair,
            needed=True,
        )
    async with user_session(engine_engine, uuid4(), role=DatabaseRole.ENGINE) as session:
        assert (await session.execute("SELECT * FROM paper_market_dependencies")).all() == []
    async with user_session(api_engine, owner) as session:
        with pytest.raises(NotPermittedError):
            await session.execute("SELECT * FROM paper_market_dependencies")
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        async with market_data_session(engine) as session:
            assert pair in await retained_pairs(session)
            with pytest.raises(NotPermittedError):
                await session.execute("SELECT * FROM paper_market_dependencies")
        async with market_data_session(engine) as session:
            with pytest.raises(NotPermittedError):
                await session.execute("UPDATE market_execution_demand SET references_count=0")
    finally:
        await engine.dispose()
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await set_pair_dependency(
            session,
            wallet_id=wallet.wallet_id,
            episode_id=wallet.episode_id,
            pair=pair,
            needed=False,
        )


async def test_two_owner_demand_count_cannot_be_released_by_one_owner(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    other = uuid4()
    await create_user(api_engine, other)
    async with user_session(api_engine, other) as session:
        await admit_command(
            session,
            action=PaperWalletAction.CREATE,
            idempotency_key=uuid4(),
            capital_text="10000",
            expected_episode_id=None,
        )
    await run_paper_wallet_round(
        engine=engine_engine, scan_engine=scan_engine, worker="demand-test"
    )
    async with user_session(api_engine, other) as session:
        other_wallet = await get_wallet(session)
    assert other_wallet is not None
    pair = PositionPair("RETAINED", "USDT")

    async def change(user: UUID, record: PaperWalletSnapshot, needed: bool) -> None:
        async with user_session(engine_engine, user, role=DatabaseRole.ENGINE) as session:
            await set_pair_dependency(
                session,
                wallet_id=record.wallet_id,
                episode_id=record.episode_id,
                pair=pair,
                needed=needed,
            )

    await asyncio.gather(change(owner, wallet, True), change(other, other_wallet, True))
    await asyncio.gather(change(owner, wallet, False), change(other, other_wallet, True))
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        count = (
            await session.execute(
                "SELECT references_count FROM market_execution_demand WHERE base='RETAINED'"
            )
        ).scalar_one()
        assert count == 1
    await change(other, other_wallet, False)
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        async with market_data_session(engine) as public_session:
            assert pair not in await retained_pairs(public_session)
    finally:
        await engine.dispose()


async def test_ring_wrap_is_bounded_and_slow_consumer_must_recover(
    engine_engine: AsyncEngine,
) -> None:
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        lease, book, metadata = await prepared(engine)
        start = lease.last_input_id
        async with market_data_session(engine) as session:
            for offset in range(1, 4098):
                if offset % 100 == 0:
                    lease = await renew_book_writer(session, lease)
                # This case proves bounded wrap/gap behavior, not the one-second
                # freshness boundary. A host pause between reading the server
                # clock and publication can consume that entire window, so renew
                # the same input proof and retry without advancing the sequence.
                for attempt in range(3):
                    now = (await session.execute("SELECT clock_timestamp()")).scalar_one()
                    current = replace(
                        book,
                        input_id=start + offset,
                        received_at=now,
                        verified_at=now,
                        source_at=now,
                        rebase=offset == 1,
                    )
                    try:
                        lease = await publish_input(session, lease, current, metadata)
                    except SourceUnavailableError:
                        if attempt == 2:
                            raise
                    else:
                        break
            count = (
                await session.execute("""SELECT count(*) FROM market_execution_buffer
              WHERE base='BTC' AND quote='USDT'""")
            ).scalar_one()
            assert count == 4096
        async with user_session(engine_engine, uuid4(), role=DatabaseRole.ENGINE) as session:
            with pytest.raises(ExecutionInputGapError):
                await read_inputs(session, PAIR, after=start)
            recent = await read_inputs(session, PAIR, after=start + 4097 - 20)
            assert len(recent) == 20 and recent[-1].market.input_id == start + 4097
    finally:
        await engine.dispose()


async def test_book_lease_expiry_is_checked_after_row_lock_wait() -> None:
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    task = None
    try:
        lease, _, _ = await prepared(engine)
        async with market_data_session(engine) as session:
            await session.execute("""UPDATE market_execution_state
              SET lease_until=clock_timestamp()+interval '1 second'
              WHERE base='BTC' AND quote='USDT'""")
        pid_ready = asyncio.get_running_loop().create_future()

        async def renew() -> None:
            async with market_data_session(engine) as session:
                pid_ready.set_result(
                    (await session.execute("SELECT pg_backend_pid()")).scalar_one()
                )
                await renew_book_writer(session, lease)

        async with market_data_session(engine) as observer:
            async with market_data_session(engine) as blocker:
                await blocker.execute("""SELECT * FROM market_execution_state
                  WHERE base='BTC' AND quote='USDT' FOR UPDATE""")
                task = asyncio.create_task(renew())
                pid = await asyncio.wait_for(pid_ready, 3)
                async with asyncio.timeout(3):
                    while not (
                        await observer.execute(
                            "SELECT cardinality(pg_blocking_pids(:pid)) > 0", {"pid": pid}
                        )
                    ).scalar_one():
                        if task.done():
                            task.result()
                            pytest.fail("renewal did not wait for the row lock")
                        await asyncio.sleep(0.01)
                    while not (
                        await observer.execute("""SELECT lease_until<=clock_timestamp()
                      FROM market_execution_state WHERE base='BTC' AND quote='USDT'""")
                    ).scalar_one():
                        await asyncio.sleep(0.01)
            with pytest.raises(WriterLeaseLost):
                await asyncio.wait_for(task, 3)
    finally:
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        await engine.dispose()
