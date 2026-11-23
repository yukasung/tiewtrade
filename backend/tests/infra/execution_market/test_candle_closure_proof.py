"""Real PostgreSQL source-scope, atomic proof and runtime role boundaries."""

import asyncio
import json
import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from tests.core.test_candle_closure import recorded
from tests.infra.execution_market.test_bot_decisions import (
    bot_bracket_protocol as bot_bracket_protocol,
)
from tests.infra.execution_market.test_process_recovery import marker
from tiewtrade.core.candle_closure import ClosureCandidate
from tiewtrade.core.market_data import Candle
from tiewtrade.infra.bots.evaluation import PreparedQuote
from tiewtrade.infra.db import DatabaseRole, create_engine_for, user_session
from tiewtrade.infra.db.errors import NotPermittedError
from tiewtrade.infra.db.session import UserSession, market_data_session
from tiewtrade.infra.indicators.source import begin_source_write
from tiewtrade.infra.market_data import candle_closure as closure
from tiewtrade.infra.market_data.candle_preview import (
    PreviewLease,
    PreviewLeaseLostError,
    acquire,
    connection,
)
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot
from tiewtrade.infra.platform import RuntimeSymbol

pytestmark = pytest.mark.usefixtures("internal_database")
INVENTORY = {
    "legacy_writers_drained": True,
    "legacy_restart_disabled": True,
    "readers_compatible": True,
    "candidate_sha": "a" * 40,
    "paper_only": True,
}

PROCESS_PUBLICATION = """
import asyncio, sys
from uuid import UUID
from tests.core.test_candle_closure import recorded
from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.infra.db.session import market_data_session
from tiewtrade.infra.market_data import candle_closure as closure
from tiewtrade.infra.market_data.candle_preview import PreviewLease

async def run():
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    lease = PreviewLease(UUID(sys.argv[1]), int(sys.argv[2]))
    candidate, _, _ = recorded("BTCUSDT")
    try:
        async with market_data_session(engine) as session:
            proof = await closure.record_candidate(session, lease, candidate.observation)
            assert (proof is None) == (sys.argv[3] == "pending")
            if sys.argv[4] == "before_commit":
                print("BEFORE_COMMIT", flush=True)
                await asyncio.Event().wait()
        print("AFTER_COMMIT", flush=True)
        await asyncio.Event().wait()
    finally:
        await engine.dispose()
asyncio.run(run())
"""


async def test_campaign_audit_sees_real_ledger_hidden_from_migrator(
    migrator_engine: AsyncEngine,
    wallet: PaperWalletSnapshot,
) -> None:
    from sqlalchemy.exc import DBAPIError

    from tests.infra.execution_market.profile_candle_closure import capture_evidence

    async with migrator_engine.connect() as connection:
        assert (
            await connection.execute(text("SELECT count(*) FROM paper_wallet_ledger"))
        ).scalar_one() == 0
    audit = create_async_engine(
        os.environ["TIEWTRADE_TEST_ADMIN_URL"],
        hide_parameters=True,
        execution_options={"postgresql_readonly": True},
    )
    try:
        report: dict[str, Any] = {}
        await capture_evidence(audit, report)
        assert len(report["users"]) == len(report["wallets"]) == len(report["ledger"]) == 1
        assert report["wallets"][0]["id"] == wallet.wallet_id
        assert report["ledger"][0]["kind"] == "EXTERNAL_CAPITAL"
        async with audit.begin() as connection:
            with pytest.raises(DBAPIError, match="read-only"):
                await connection.execute(text("UPDATE users SET id=id WHERE false"))
    finally:
        await audit.dispose()


@asynccontextmanager
async def ready(
    migrator: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
    *,
    symbol: str = "BTCUSDT",
) -> AsyncIterator[tuple[AsyncEngine, PreviewLease, ClosureCandidate, Candle, datetime]]:
    candidate, c, started = recorded(symbol)
    market = create_engine_for(DatabaseRole.MARKET_DATA)
    monkeypatch.setenv("TIEWTRADE_CANDLE_CLOSURE_ENABLED", "1")
    try:
        async with migrator.begin() as conn:
            await conn.execute(text("SELECT activate_indicator_source_proof()"))
        async with market_data_session(market) as session:
            await begin_source_write(session)
            await session.execute(
                """INSERT INTO market_candles
              (source,base,quote,timeframe,open_at,end_at,open,high,low,close,volume,finality,
               observed_at,fetch_started_at,last_checked_at,ingestion_generation)
              VALUES(:source,:base,:quote,:timeframe,:open_at,:end_at,:open,:high,:low,:close,
                :volume,'UNCONFIRMED',:observed,:fetch,clock_timestamp(),1)""",
                closure.payload(c)
                | closure.key(c)
                | {"end_at": c.end_at, "observed": c.observed_at, "fetch": started},
            )
            lease = await acquire(session, uuid4())
            assert lease is not None
            lease = await connection(session, lease, True)
            await session.execute(
                "UPDATE market_candle_feed_state SET bootstrapped=true,failure_code=NULL "
                "WHERE source='primary_spot'"
            )
        async with migrator.begin() as conn:
            await conn.execute(
                text("SELECT activate_candle_closure(true,CAST(:inventory AS jsonb))"),
                {"inventory": json.dumps(INVENTORY)},
            )
        yield market, lease, candidate, c, started
    finally:
        await market.dispose()


async def test_public_recordings_match_or_conflict_without_forged_finality(
    migrator_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with ready(migrator_engine, monkeypatch, symbol="ETHUSDT") as (
        market,
        lease,
        candidate,
        _,
        _,
    ):
        async with market_data_session(market) as session:
            assert await closure.record_candidate(session, lease, candidate.observation) is None
        async with market_data_session(market) as session:
            row = (
                await session.execute("SELECT finality,closure_proof_id FROM market_candles")
            ).one()
            assert row.finality == "UNCONFIRMED" and row.closure_proof_id is None
            assert (
                await session.execute("SELECT status FROM market_candle_closure_state")
            ).scalar_one() == "CONFLICT"


async def test_concurrent_duplicate_proofs_publish_once_and_survive_new_pool(
    migrator_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with ready(migrator_engine, monkeypatch) as (market, lease, candidate, c, _):

        async def submit() -> UUID | None:
            async with market_data_session(market) as session:
                return await closure.record_candidate(session, lease, candidate.observation)

        results = await asyncio.gather(submit(), submit(), return_exceptions=True)
        assert all(not isinstance(value, BaseException) for value in results), results
        a, b = results
        assert a is not None and a == b
        # Replaying the exact authorized activation must retain proof authority.
        async with migrator_engine.begin() as conn:
            await conn.execute(
                text("SELECT activate_candle_closure(true,CAST(:i AS jsonb))"),
                {"i": json.dumps(INVENTORY)},
            )
        async with user_session(engine_engine, uuid4(), role=DatabaseRole.ENGINE) as session:
            proof = await closure.current_proof(session, c)
            assert proof is not None and proof["id"] == a
            assert (
                await session.execute("SELECT count(*) FROM market_candle_closure_observations")
            ).scalar_one() == 1
            assert (
                await session.execute("SELECT count(*) FROM market_candle_closure_results")
            ).scalar_one() == 1
            assert (
                await session.execute("SELECT finality FROM market_candles")
            ).scalar_one() == "CLOSED"


@pytest.mark.parametrize("fault", ["result", "promotion"])
async def test_resolution_failure_rolls_back_native_proof_and_promotion_together(
    fault: str,
    migrator_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with ready(migrator_engine, monkeypatch) as (market, lease, candidate, _, _):
        target = "_resolve" if fault == "result" else "reconcile"
        original = getattr(closure, target)
        async with market_data_session(market) as session:
            before = tuple(
                (await session.execute("SELECT epoch,revision FROM indicator_source_guard")).one()
            )

        async def fail_after_result(*args: object, **kwargs: object) -> UUID:
            await original(*args, **kwargs)
            raise RuntimeError("injected after accepted result")

        with monkeypatch.context() as patch:
            patch.setattr(closure, target, fail_after_result)
            with pytest.raises(RuntimeError, match="injected"):
                async with market_data_session(market) as session:
                    await closure.record_candidate(session, lease, candidate.observation)
        async with market_data_session(market) as session:
            assert (
                tuple(
                    (
                        await session.execute("SELECT epoch,revision FROM indicator_source_guard")
                    ).one()
                )
                == before
            )
            assert (
                await session.execute("SELECT count(*) FROM market_candle_closure_results")
            ).scalar_one() == 0
            assert (
                await session.execute("SELECT count(*) FROM market_candle_closure_observations")
            ).scalar_one() == 0
            assert (
                await session.execute("SELECT finality FROM market_candles")
            ).scalar_one() == "UNCONFIRMED"
            assert await closure.record_candidate(session, lease, candidate.observation) is not None


async def test_runtime_roles_cannot_forge_closure_or_rewrite_evidence(
    migrator_engine: AsyncEngine,
    api_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with ready(migrator_engine, monkeypatch) as (market, lease, candidate, _, _):
        with pytest.raises(NotPermittedError):
            async with market_data_session(market) as session:
                await begin_source_write(session)
                await closure.prepare_write(session)
                await session.execute("UPDATE market_candles SET finality='CLOSED'")
        async with market_data_session(market) as session:
            await closure.record_candidate(session, lease, candidate.observation)
        with pytest.raises(NotPermittedError):
            async with user_session(api_engine, uuid4()) as session:
                await session.execute("DELETE FROM market_candle_closure_results")
        with pytest.raises(NotPermittedError):
            async with market_data_session(market) as session:
                await session.execute("UPDATE market_candle_closure_results SET outcome='CONFLICT'")


async def test_closed_source_invalidation_demotes_atomically_and_fences_readers(
    migrator_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tiewtrade.core.money import Quantity

    async with ready(migrator_engine, monkeypatch) as (market, lease, candidate, c, started):
        async with market_data_session(market) as session:
            await closure.record_candidate(session, lease, candidate.observation)
        changed = replace(c, volume=c.volume + Quantity.of("0.00001", c.base))
        async with market_data_session(market) as session:
            await begin_source_write(session)
            assert await closure.invalidate(
                session, changed, fetch_started_at=started, reason="REST_CONFLICT"
            )
        async with user_session(engine_engine, uuid4(), role=DatabaseRole.ENGINE) as session:
            assert (
                await session.execute("SELECT finality FROM market_candles")
            ).scalar_one() == "UNCONFIRMED"
            assert (
                await session.execute("SELECT count(*) FROM market_candle_closure_results")
            ).scalar_one() == 2
            with pytest.raises(closure.ClosureUnavailableError):
                await closure.current_proof(session, c)


async def test_rest_correction_is_not_hidden_by_closed_skip(
    migrator_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tiewtrade.core.money import Quantity
    from tiewtrade.infra.market_data.claims import claim_next, write_candles

    async with ready(migrator_engine, monkeypatch) as (market, lease, candidate, c, started):
        async with market_data_session(market) as session:
            await closure.record_candidate(session, lease, candidate.observation)
            await session.execute(
                """INSERT INTO market_candle_demand
                (source,base,quote,timeframe,desired_start,desired_end,requested_at)
                VALUES(:source,:base,:quote,:timeframe,:open_at,:end_at,clock_timestamp())""",
                closure.key(c) | {"end_at": c.end_at},
            )
        async with market_data_session(market) as session:
            claim = await claim_next(session, "closure-correction-test")
            assert claim is not None
        changed = replace(c, volume=c.volume + Quantity.of("0.00001", c.base))
        async with market_data_session(market) as session:
            await begin_source_write(session)
            await write_candles(session, claim, (changed,), started)
        async with market_data_session(market) as session:
            row = (await session.execute("SELECT * FROM market_candles")).mappings().one()
            assert row["finality"] == "UNCONFIRMED" and row["closure_proof_id"] is None
            assert Quantity.of(row["volume"], c.base) == c.volume
            result = (
                (
                    await session.execute(
                        "SELECT * FROM market_candle_closure_results WHERE outcome='INVALIDATED'"
                    )
                )
                .mappings()
                .one()
            )
            assert result["canonical"]["volume"] == changed.volume.as_parts()["quantity"]
            assert result["canonical"]["details"]["reason"] == "REST_CONFLICT"


async def test_native_close_only_change_is_persisted_before_next_slot(
    migrator_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from typing import cast

    from tiewtrade.infra.realtime.notifications import RedisNotifications
    from tiewtrade.services.market_data.candle_realtime import CandleSupervisor
    from tiewtrade.venues.candle_streams import FeedCandle
    from tiewtrade.venues.fake import FakeCandleFeed

    async with ready(migrator_engine, monkeypatch) as (market, lease, candidate, c, _):
        native = candidate.observation
        # Same OHLCV/progress, false -> true; display revision must not change.
        feed = FakeCandleFeed((FeedCandle(1, native), FeedCandle(1, native)))
        supervisor = CandleSupervisor(market, feed, cast(RedisNotifications, None))
        supervisor.lease, supervisor.epoch = lease, 1
        supervisor.catalog = await _catalog(market)
        supervisor.observe(FeedCandle(1, replace(native, closed_hint=False)))
        revision = supervisor.rows[(c.base, c.quote, c.timeframe)][1]
        await supervisor._consume()
        assert supervisor.rows[(c.base, c.quote, c.timeframe)][1] == revision
        async with market_data_session(market) as session:
            assert (
                await session.execute("SELECT count(*) FROM market_candle_closure_observations")
            ).scalar_one() == 1
            assert (
                await session.execute("SELECT count(*) FROM market_candle_closure_results")
            ).scalar_one() == 1
            assert (
                await session.execute("SELECT finality FROM market_candles")
            ).scalar_one() == "CLOSED"


async def _catalog(market: AsyncEngine) -> dict[tuple[str, str], RuntimeSymbol]:
    from tiewtrade.infra.market_data.catalog import runtime_symbol_map

    async with market_data_session(market) as session:
        return await runtime_symbol_map(session)


async def test_disconnected_or_old_epoch_cannot_supply_current_proof(
    migrator_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with ready(migrator_engine, monkeypatch) as (market, lease, candidate, c, _):
        async with market_data_session(market) as session:
            await closure.record_candidate(session, lease, candidate.observation)
        async with market_data_session(market) as session:
            await closure.prepare_write(session, acquire=True)
            await connection(session, lease, False)
            await closure.connection_changed(session)
        async with user_session(engine_engine, uuid4(), role=DatabaseRole.ENGINE) as session:
            with pytest.raises(closure.ClosureUnavailableError, match="not ready"):
                await closure.current_proof(session, c)
        async with market_data_session(market) as session:
            with pytest.raises(PreviewLeaseLostError):
                await closure.record_candidate(session, lease, candidate.observation)


async def test_pending_close_survives_pool_restart_and_claimed_rest_completion(
    migrator_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import timedelta

    from tiewtrade.infra.market_data.claims import claim_next, write_candles

    async with ready(migrator_engine, monkeypatch) as (market, lease, candidate, c, started):
        async with market_data_session(market) as session:
            await closure.prepare_write(session, acquire=True)
            await session.execute(
                "UPDATE market_candles SET fetch_started_at=:before_end",
                {"before_end": c.end_at - timedelta(microseconds=1)},
            )
            assert await closure.record_candidate(session, lease, candidate.observation) is None
            assert (
                await session.execute("SELECT status FROM market_candle_closure_state")
            ).scalar_one() == "WAITING_REST"
        await market.dispose()
        recovered = create_engine_for(DatabaseRole.MARKET_DATA)
        try:
            async with market_data_session(recovered) as session:
                assert (
                    await session.execute("SELECT count(*) FROM market_candle_closure_observations")
                ).scalar_one() == 1
                assert (
                    await session.execute("SELECT count(*) FROM market_candle_closure_results")
                ).scalar_one() == 0
                claim = await claim_next(session, "restarted-closure-rest")
                assert claim is not None
            async with market_data_session(recovered) as session:
                await begin_source_write(session)
                await write_candles(session, claim, (c,), started)
            async with market_data_session(recovered) as session:
                receipt = await closure.current_proof(session, c)
                assert receipt is not None
                assert (
                    await closure.record_candidate(session, lease, candidate.observation)
                    == receipt["id"]
                )
                assert (
                    await session.execute("SELECT count(*) FROM market_candle_closure_observations")
                ).scalar_one() == 1
                assert (
                    await session.execute("SELECT count(*) FROM market_candle_closure_results")
                ).scalar_one() == 1
                row = (
                    await session.execute("SELECT finality,closure_proof_id FROM market_candles")
                ).one()
                assert row.finality == "CLOSED" and row.closure_proof_id == receipt["id"]
        finally:
            await recovered.dispose()


@pytest.mark.parametrize("stage", ["pending", "published"])
@pytest.mark.parametrize("boundary", ["before_commit", "after_commit"])
async def test_process_death_preserves_atomic_closure_and_idempotent_recovery(
    migrator_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
    stage: str,
    boundary: str,
) -> None:
    from datetime import timedelta

    from tiewtrade.infra.market_data.claims import claim_next, write_candles

    async with ready(migrator_engine, monkeypatch) as (market, lease, candidate, c, started):
        async with market_data_session(market) as session:
            if stage == "pending":
                await closure.prepare_write(session, acquire=True)
                await session.execute(
                    "UPDATE market_candles SET fetch_started_at=:before_end",
                    {"before_end": c.end_at - timedelta(microseconds=1)},
                )
            before = tuple(
                (await session.execute("SELECT epoch,revision FROM indicator_source_guard")).one()
            )
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            PROCESS_PUBLICATION,
            str(lease.owner),
            str(lease.epoch),
            stage,
            boundary,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            await marker(process, boundary.upper().encode())
            process.kill()
            await asyncio.wait_for(process.wait(), 5)
            assert process.returncode != 0
            async with market_data_session(market) as session:
                row = (
                    await session.execute(
                        """SELECT finality,closure_proof_id,
                        (SELECT count(*) FROM market_candle_closure_observations) AS observations,
                        (SELECT count(*) FROM market_candle_closure_results) AS results
                        FROM market_candles"""
                    )
                ).one()
                committed = boundary == "after_commit"
                published = committed and stage == "published"
                assert row.observations == int(committed)
                assert row.results == int(published)
                assert row.finality == ("CLOSED" if published else "UNCONFIRMED")
                assert (row.closure_proof_id is not None) == published
                if not committed:
                    assert (
                        tuple(
                            (
                                await session.execute(
                                    "SELECT epoch,revision FROM indicator_source_guard"
                                )
                            ).one()
                        )
                        == before
                    )
                    # REST cannot invent native evidence lost before commit.
                    await closure.prepare_write(session, acquire=True)
                    assert await closure.reconcile(session, c) is None
                persisted_proof = row.closure_proof_id

            if stage == "pending":
                if not committed:
                    async with market_data_session(market) as session:
                        assert (
                            await closure.record_candidate(session, lease, candidate.observation)
                            is None
                        )
                async with market_data_session(market) as session:
                    claim = await claim_next(session, "process-closure-recovery")
                    assert claim is not None
                async with market_data_session(market) as session:
                    await begin_source_write(session)
                    await write_candles(session, claim, (c,), started)
            else:
                async with market_data_session(market) as session:
                    proof = await closure.record_candidate(session, lease, candidate.observation)
                    assert proof is not None
                    if committed:
                        assert proof == persisted_proof

            async with market_data_session(market) as session:
                receipt = await closure.current_proof(session, c)
                assert receipt is not None
                revision = tuple(
                    (
                        await session.execute("SELECT epoch,revision FROM indicator_source_guard")
                    ).one()
                )
                assert (
                    await closure.record_candidate(session, lease, candidate.observation)
                    == receipt["id"]
                )
                assert (
                    tuple(
                        (
                            await session.execute(
                                "SELECT epoch,revision FROM indicator_source_guard"
                            )
                        ).one()
                    )
                    == revision
                )
                row = (
                    await session.execute(
                        """SELECT finality,closure_proof_id,
                        (SELECT count(*) FROM market_candle_closure_observations) AS observations,
                        (SELECT count(*) FROM market_candle_closure_results) AS results
                        FROM market_candles"""
                    )
                ).one()
                assert row.finality == "CLOSED" and row.closure_proof_id == receipt["id"]
                assert row.observations == row.results == 1
        finally:
            if process.returncode is None:
                process.kill()
            await asyncio.wait_for(process.wait(), 5)


async def test_expired_writer_pending_close_requires_current_writer_evidence(
    migrator_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import timedelta

    from tiewtrade.infra.market_data.claims import claim_next, write_candles

    async with ready(migrator_engine, monkeypatch) as (market, lease, candidate, c, started):
        async with market_data_session(market) as session:
            await closure.prepare_write(session, acquire=True)
            await session.execute(
                "UPDATE market_candles SET fetch_started_at=:before_end",
                {"before_end": c.end_at - timedelta(microseconds=1)},
            )
            assert await closure.record_candidate(session, lease, candidate.observation) is None
            await session.execute(
                "UPDATE market_candle_feed_state "
                "SET lease_until=clock_timestamp()-interval '1 second'"
            )
        recovered = create_engine_for(DatabaseRole.MARKET_DATA)
        try:
            async with market_data_session(recovered) as session:
                await closure.prepare_write(session, acquire=True)
                replacement = await acquire(session, uuid4())
                assert replacement is not None and replacement.epoch > lease.epoch
                replacement = await connection(session, replacement, True)
                await session.execute(
                    "UPDATE market_candle_feed_state SET bootstrapped=true,failure_code=NULL"
                )
                await closure.connection_changed(session)
            with pytest.raises(PreviewLeaseLostError):
                async with market_data_session(market) as session:
                    await closure.record_candidate(session, lease, candidate.observation)
            async with market_data_session(recovered) as session:
                claim = await claim_next(session, "takeover-closure-rest")
                assert claim is not None
            async with market_data_session(recovered) as session:
                await begin_source_write(session)
                await write_candles(session, claim, (c,), started)
                assert await closure.reconcile(session, c) is None
                with pytest.raises(closure.ClosureUnavailableError, match="not current"):
                    await closure.current_proof(session, c)
                assert (
                    await session.execute("SELECT finality FROM market_candles")
                ).scalar_one() == "UNCONFIRMED"
                assert (
                    await session.execute("SELECT count(*) FROM market_candle_closure_results")
                ).scalar_one() == 0
            async with market_data_session(recovered) as session:
                now = (await session.execute("SELECT clock_timestamp()")).scalar_one()
                fresh_native = replace(candidate.observation, event_at=now, received_at=now)
                proof = await closure.record_candidate(session, replacement, fresh_native)
                assert proof is not None
                receipt = await closure.current_proof(session, c)
                assert receipt is not None and receipt["id"] == proof
                assert (
                    await session.execute("SELECT count(*) FROM market_candle_closure_observations")
                ).scalar_one() == 2
                assert (
                    await session.execute("SELECT count(*) FROM market_candle_closure_results")
                ).scalar_one() == 1
        finally:
            await recovered.dispose()


async def test_duplicate_conflict_refresh_cannot_revive_exhausted_claim(
    migrator_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tiewtrade.core.market_data import CandleWindow
    from tiewtrade.infra.market_data.claims import claim_next
    from tiewtrade.infra.market_data.storage import coalesce_demand

    async with ready(migrator_engine, monkeypatch, symbol="ETHUSDT") as (
        market,
        lease,
        candidate,
        c,
        _,
    ):
        async with market_data_session(market) as session:
            await closure.record_candidate(session, lease, candidate.observation)
            await session.execute(
                """UPDATE market_candle_demand SET status='FAILED',attemptcount=3,
                checked_at=clock_timestamp(),next_attempt_at=clock_timestamp(),
                token=NULL,worker=NULL,lease_until=NULL"""
            )
        for _ in range(2):
            async with market_data_session(market) as session:
                await begin_source_write(session)
                await coalesce_demand(
                    session, c.base, c.quote, c.timeframe, CandleWindow(c.open_at, c.end_at)
                )
                await closure.record_candidate(session, lease, candidate.observation)
                assert await claim_next(session, "must-not-revive") is None
        async with market_data_session(market) as session:
            assert (
                await session.execute("SELECT attemptcount FROM market_candle_demand")
            ).scalar_one() == 3


@pytest.mark.parametrize(
    "stage",
    [
        "unchanged",
        "commit",
        "queued",
        "expired",
        "accepted",
        "accepted_sell",
        "filled",
        "awaiting_proof",
        "awaiting_proof_reconnect",
    ],
)
async def test_proof_to_prepared_indicators_strategy_and_paper_admission(
    stage: str,
    migrator_engine: AsyncEngine,
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    monkeypatch: pytest.MonkeyPatch,
    bot_bracket_protocol: None,
) -> None:
    """Synthetic green fixture: real adapter/PG/F11/strategy/matcher; no venue trades."""
    from datetime import UTC, timedelta
    from typing import cast

    from tests.infra.execution_market.test_bot_indicator_inputs import seed_prepared
    from tests.infra.execution_market.test_strategy_baskets import f21_run
    from tests.infra.execution_market.test_strategy_commit_fences import verify_queued_result
    from tests.infra.risk_limits.test_execution import runtime
    from tiewtrade.core.market_data import CandleSeries, Timeframe, advance, align_floor
    from tiewtrade.core.money import Money, Quantity
    from tiewtrade.core.positions import PositionPair
    from tiewtrade.core.strategy_config import PaperTestConfig
    from tiewtrade.infra.market_data.storage import _stored
    from tiewtrade.infra.paper_wallet import get_wallet
    from tiewtrade.infra.realtime.notifications import RedisNotifications
    from tiewtrade.services.engine import bot
    from tiewtrade.services.market_data.candle_realtime import CandleSupervisor
    from tiewtrade.venues.binance_th.candle_stream_mapping import candle_from_stream
    from tiewtrade.venues.candle_streams import FeedCandle
    from tiewtrade.venues.fake import FakeCandleFeed

    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000", account_use="BOT"
    ) as source:
        async with migrator_engine.begin() as conn:
            await conn.execute(text("SELECT activate_indicator_source_proof()"))
            now: datetime = (await conn.execute(text("SELECT clock_timestamp()"))).scalar_one()
        end = align_floor(now, Timeframe.M1)
        await seed_prepared(
            migrator_engine,
            251,
            end,
            closes=(*(Money.of(100, "USDT") for _ in range(250)), Money.of(110, "USDT")),
        )
        async with market_data_session(source.market) as market_session:
            await begin_source_write(market_session)
            # Actual source warm-up remains UNCONFIRMED (F11 NC31), including
            # a signal within the old head. The reader must restore/replay.
            await market_session.execute("UPDATE market_candles SET finality='UNCONFIRMED'")
            row = (
                (
                    await market_session.execute(
                        "SELECT * FROM market_candles ORDER BY open_at DESC LIMIT 1"
                    )
                )
                .mappings()
                .one()
            )
            c = _stored(row).candle
            lease = await acquire(market_session, uuid4())
            assert lease is not None
            lease = await connection(market_session, lease, True)
            await market_session.execute(
                "UPDATE market_candle_feed_state SET bootstrapped=true,failure_code=NULL"
            )
        monkeypatch.setenv("TIEWTRADE_CANDLE_CLOSURE_ENABLED", "1")
        async with migrator_engine.begin() as conn:
            await conn.execute(
                text("SELECT activate_candle_closure(true,CAST(:v AS jsonb))"),
                {"v": json.dumps(INVENTORY)},
            )
        run = await f21_run(
            engine_engine,
            owner,
            wallet,
            configuration=PaperTestConfig(
                PositionPair("BTC", "USDT"), Timeframe.M1, Money.of(100, "USDT")
            ),
        )
        worker = uuid4()
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            # Explicit synthetic initial boundary; public campaign never sets these.
            await session.execute(
                """UPDATE bot_strategy_progress SET eligible_after=:eligible,
                indicator_source_epoch=(SELECT epoch FROM indicator_source_guard),
                source_recovery_at=(SELECT recovery_at FROM market_candle_closure_control)
                WHERE run_id=:run""",
                {"run": run, "eligible": advance(end, Timeframe.M1, -2)},
            )
            await session.execute(
                """INSERT INTO bot_run_leases(run_id,user_id,mode,worker_id,generation,lease_until)
                VALUES(:run,:owner,'PAPER',:worker,1,clock_timestamp()+interval '60 seconds')""",
                {"run": run, "owner": owner, "worker": worker},
            )
        epoch = datetime(1970, 1, 1, tzinfo=UTC)

        def millis(at: datetime) -> int:
            return (at - epoch) // timedelta(milliseconds=1)

        payload = {
            "stream": "btcusdt@kline_1m",
            "data": {
                "e": "kline",
                "E": millis(now),
                "s": "BTCUSDT",
                "k": {
                    "s": "BTCUSDT",
                    "i": "1m",
                    "t": millis(c.open_at),
                    "T": millis(c.end_at) - 1,
                    "o": c.open.as_parts()["amount"],
                    "h": c.high.as_parts()["amount"],
                    "l": c.low.as_parts()["amount"],
                    "c": c.close.as_parts()["amount"],
                    "v": c.volume.as_parts()["quantity"],
                    "n": 10,
                    "f": 1,
                    "L": 10,
                    "x": True,
                },
            },
        }
        registry = bot.StrategyRegistry(enable_f21=True, enable_paper_test=True)
        if stage in ("awaiting_proof", "awaiting_proof_reconnect"):
            await source.price("110", trade_time=now)
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                progress_before = (
                    await session.execute(
                        "SELECT eligible_after,recovery_required FROM bot_strategy_progress"
                    )
                ).one()
            for _ in range(2):
                assert (
                    await bot.run_bot_quote(
                        engine=engine_engine,
                        owner=owner,
                        run_id=run,
                        registry=registry,
                        worker_id=worker,
                    )
                    is None
                )
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                progress_after = (
                    await session.execute(
                        "SELECT eligible_after,recovery_required FROM bot_strategy_progress"
                    )
                ).one()
                assert progress_after == progress_before
                assert (
                    await session.execute(
                        "SELECT details->>'reason' FROM bot_run_events "
                        "WHERE event='SOURCE_NOT_READY' ORDER BY revision DESC LIMIT 1"
                    )
                ).scalar_one() == "BOT_CANDLE_UNCONFIRMED"
                assert (
                    await session.execute("SELECT count(*) FROM paper_order_commands")
                ).scalar_one() == 0
                current = await get_wallet(session, include_reset_readiness=False)
                assert current is not None and current.balance == wallet.balance
            if stage == "awaiting_proof_reconnect":
                from tiewtrade.infra.market_data.candle_preview import complete_bootstrap

                async with market_data_session(source.market) as market_session:
                    await closure.prepare_write(market_session, acquire=True)
                    lease = await connection(market_session, lease, False)
                    await closure.connection_changed(market_session)
                async with market_data_session(source.market) as market_session:
                    await closure.prepare_write(market_session, acquire=True)
                    lease = await connection(market_session, lease, True)
                    await closure.connection_changed(market_session)
                    await complete_bootstrap(market_session, lease)
        native = candle_from_stream(
            payload=payload, series=(CandleSeries("BTC", "USDT", Timeframe.M1),), received_at=now
        )
        supervisor = CandleSupervisor(
            source.market, FakeCandleFeed((FeedCandle(1, native),)), cast(RedisNotifications, None)
        )
        supervisor.lease, supervisor.epoch = lease, 1
        supervisor.catalog = await _catalog(source.market)
        await supervisor._consume()
        async with market_data_session(source.market) as market_session:
            assert (
                await market_session.execute(
                    "SELECT finality FROM market_candles ORDER BY open_at DESC LIMIT 1"
                )
            ).scalar_one() == "CLOSED"
            assert await closure.current_proof(market_session, c) is not None
        # Keep this synthetic quote in the seeded candle window across a wall-clock
        # minute rollover; source.price still records the actual receipt time.
        await source.price("110", trade_time=now)
        from tiewtrade.infra.bots.evaluation import evaluate_published_quote

        original = evaluate_published_quote

        async def invalidate_source() -> None:
            async with market_data_session(source.market) as market_session:
                await begin_source_write(market_session)
                await closure.invalidate(
                    market_session,
                    replace(c, volume=c.volume + Quantity.of(1, "BTC")),
                    fetch_started_at=end,
                    reason="TEST_CORRECTION",
                )

        async def commit(
            session: UserSession, run_id: UUID, **kwargs: Any
        ) -> UUID | PreparedQuote | None:
            if stage == "commit" and kwargs.get("evaluation") is not None:
                await invalidate_source()
            return await original(session, run_id, **kwargs)

        monkeypatch.setattr(bot, "evaluate_published_quote", commit)
        decision = await bot.run_bot_quote(
            engine=engine_engine, owner=owner, run_id=run, registry=registry, worker_id=worker
        )

        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            commands = (
                (await session.execute("SELECT id FROM paper_order_commands")).scalars().all()
            )
            if stage == "commit":
                assert not commands
                return
            if stage == "awaiting_proof_reconnect":
                diagnostics = (
                    await session.execute(
                        "SELECT event,details FROM bot_run_events ORDER BY revision"
                    )
                ).all()
                assert decision is not None and not commands, diagnostics
                progress = (
                    await session.execute(
                        "SELECT eligible_after,recovery_required,source_recovery_at "
                        "FROM bot_strategy_progress"
                    )
                ).one()
                assert not progress.recovery_required
                assert progress.eligible_after >= progress.source_recovery_at > c.end_at
                assert (
                    await session.execute("SELECT count(*) FROM paper_execution_links")
                ).scalar_one() == 0
                return
            diagnostics = (
                await session.execute("SELECT event,details FROM bot_run_events ORDER BY revision")
            ).all()
            assert decision is not None and len(commands) == 1, diagnostics
            provenance = (
                await session.execute(
                    "SELECT input_provenance FROM bot_decisions WHERE id=:id", {"id": decision}
                )
            ).scalar_one()
            assert provenance["closure_proof_id"]
            assert provenance["closure_policy_version"] == 1
            assert provenance["indicator_prefix_end"]
        if stage == "awaiting_proof":
            assert (
                await bot.run_bot_quote(
                    engine=engine_engine,
                    owner=owner,
                    run_id=run,
                    registry=registry,
                    worker_id=worker,
                )
                == decision
            )
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                assert (
                    await session.execute("SELECT count(*) FROM paper_order_commands")
                ).scalar_one() == 1
        if stage == "queued":
            await invalidate_source()
        if stage == "expired":
            # All authority except the entry window stays healthy. Return a
            # deterministic DB timestamp at end(B), without waiting a minute.
            from collections.abc import Mapping

            from sqlalchemy.engine import Result

            from tiewtrade.infra.bots.authority import _queued_signal_current

            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                await session.execute(
                    "UPDATE bot_run_leases SET lease_until=clock_timestamp()+interval '5 minutes'"
                )
                assert await _queued_signal_current(session, commands[0])
            execute = UserSession.execute

            async def at_boundary(
                self: UserSession, statement: str, parameters: Mapping[str, object] | None = None
            ) -> Result[Any]:
                if statement == "SELECT clock_timestamp()":
                    return await execute(
                        self,
                        "SELECT CAST(:boundary AS timestamptz)",
                        {"boundary": next(clocks)},
                    )
                return await execute(self, statement, parameters)

            boundary = advance(c.end_at, c.timeframe, 1)
            just_before = boundary - timedelta(microseconds=1)
            for first, last, expected in (
                (just_before, just_before, True),
                (boundary, boundary, False),
                (boundary + timedelta(microseconds=1), boundary, False),
                (just_before, boundary, False),
            ):
                clocks = iter((first, last))
                with monkeypatch.context() as patch:
                    patch.setattr(UserSession, "execute", at_boundary)
                    async with user_session(
                        engine_engine, owner, role=DatabaseRole.ENGINE
                    ) as session:
                        assert await _queued_signal_current(session, commands[0]) is expected
                        assert (
                            await session.execute("SELECT count(*) FROM paper_orders")
                        ).scalar_one() == 0
            return
        if stage in ("accepted", "accepted_sell"):
            from tests.infra.risk_limits.test_execution import drive

            await drive(engine_engine, owner, commands[0])
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                assert (
                    await session.execute("SELECT status FROM paper_order_projections")
                ).scalar_one() == "ACCEPTED"
                assert (
                    await session.execute("SELECT count(*) FROM paper_execution_links")
                ).scalar_one() == 0
            await invalidate_source()
            await asyncio.sleep(0.12)
            await source.next_book()
            await drive(engine_engine, owner, commands[0])
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                # The bot has not paused: matching itself must fence the proof.
                assert (
                    await session.execute("SELECT status FROM bot_runs")
                ).scalar_one() == "RUNNING"
                assert (
                    await session.execute("SELECT count(*) FROM paper_execution_links")
                ).scalar_one() == 0
                assert (
                    await session.execute("SELECT count(*) FROM paper_position_events")
                ).scalar_one() == 0
                after = await get_wallet(session, include_reset_readiness=False)
                assert after is not None and after.balance == wallet.balance
            if stage == "accepted_sell":
                from tests.infra.execution_market.test_dispatch import intent
                from tiewtrade.core.orders import BaseSize
                from tiewtrade.core.positions import ExecutionSide
                from tiewtrade.infra.paper_orders.dispatch import submit_order

                # Build free manual inventory through actual matching, then
                # restore BOT use before a reducing SELL drives the shared book.
                async def fixture_use(value: str) -> None:
                    admin = create_async_engine(
                        os.environ["TIEWTRADE_TEST_ADMIN_URL"], hide_parameters=True
                    )
                    try:
                        async with admin.begin() as conn:
                            await conn.execute(
                                text(
                                    "UPDATE user_trading_preferences SET use=:use "
                                    "WHERE user_id=:owner"
                                ),
                                {"use": value, "owner": owner},
                            )
                    finally:
                        await admin.dispose()

                await fixture_use("MANUAL")
                manual = intent(owner, wallet.episode_id)
                async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                    bought = await submit_order(session, wallet_id=wallet.wallet_id, intent=manual)
                await drive(engine_engine, owner, bought.command_id)
                await asyncio.sleep(0.12)
                await source.next_book()
                await drive(engine_engine, owner, bought.command_id)
                await fixture_use("BOT")
                sell = replace(
                    intent(owner, wallet.episode_id),
                    side=ExecutionSide.SELL,
                    size=BaseSize(Quantity.of("0.1", "BTC")),
                )
                async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                    sold = await submit_order(session, wallet_id=wallet.wallet_id, intent=sell)
                await drive(engine_engine, owner, sold.command_id)
                await asyncio.sleep(0.12)
                await source.next_book()
                await drive(engine_engine, owner, sold.command_id)
                async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                    assert (
                        await session.execute("SELECT status FROM bot_runs")
                    ).scalar_one() == "RUNNING"
                    assert (
                        await session.execute(
                            "SELECT count(*) FROM paper_execution_links WHERE order_id=:order",
                            {"order": sell.order_id},
                        )
                    ).scalar_one() > 0
                    bot_order = (
                        await session.execute(
                            "SELECT order_id FROM bot_order_links WHERE command_id=:command",
                            {"command": commands[0]},
                        )
                    ).scalar_one()
                    assert (
                        await session.execute(
                            "SELECT count(*) FROM paper_execution_links WHERE order_id=:order",
                            {"order": bot_order},
                        )
                    ).scalar_one() == 0
            return
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            admission_wallet = await get_wallet(session, include_reset_readiness=False)
            assert admission_wallet is not None and admission_wallet.balance == wallet.balance
        await verify_queued_result(
            engine_engine,
            owner,
            commands[0],
            admission_wallet,
            source,
            should_fill=stage in ("unchanged", "filled", "awaiting_proof"),
        )
        if stage == "filled":

            async def financial_snapshot() -> tuple[object, ...]:
                async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                    return tuple(
                        (
                            await session.execute(
                                "SELECT (SELECT jsonb_agg(to_jsonb(a)) "
                                "FROM bot_test_entry_anchors a), "
                                "(SELECT jsonb_agg(to_jsonb(p)) "
                                "FROM paper_position_projections p), "
                                "(SELECT count(*) FROM paper_wallet_ledger)"
                            )
                        ).one()
                    )

            before = await financial_snapshot()
            await invalidate_source()
            assert await financial_snapshot() == before


async def test_default_off_empty_migration_roundtrip(migrator_engine: AsyncEngine) -> None:
    from tests.infra.db.test_migrations import _alembic, _snapshot

    before = await _snapshot(migrator_engine)
    _alembic("downgrade", "0075")
    _alembic("upgrade", "head")
    assert await _snapshot(migrator_engine) == before
    async with migrator_engine.connect() as conn:
        enabled: bool = (
            await conn.execute(text("SELECT enabled FROM market_candle_closure_control"))
        ).scalar_one()
        assert enabled is False
        privileges = (
            await conn.execute(
                text("""SELECT
            has_column_privilege('tiewtrade_market_data','market_candle_closure_control',
                                 'recovery_at','UPDATE'),
            has_column_privilege('tiewtrade_market_data','market_candle_closure_control',
                                 'enabled','UPDATE'),
            has_table_privilege('tiewtrade_api','market_candle_closure_results','INSERT'),
            has_table_privilege('tiewtrade_engine','market_candle_closure_results','UPDATE')
        """)
            )
        ).one()
        assert tuple(privileges) == (True, False, False, False)


async def test_accepted_history_prevents_destructive_downgrade(
    migrator_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.infra.db.test_migrations import _failed_upgrade_or_downgrade

    async with ready(migrator_engine, monkeypatch) as (market, lease, candidate, _, _):
        async with market_data_session(market) as session:
            await closure.record_candidate(session, lease, candidate.observation)
        async with migrator_engine.begin() as conn:
            await conn.execute(
                text("SELECT activate_candle_closure(false, :inventory)"),
                {"inventory": '{"admission_paused":true}'},
            )
        failure = _failed_upgrade_or_downgrade("downgrade", "0075")
        assert "closure history or activation prevents downgrade" in failure.stderr
        async with migrator_engine.connect() as conn:
            assert (
                await conn.execute(text("SELECT count(*) FROM market_candle_closure_results"))
            ).scalar_one() == 1


async def test_missing_inventory_and_disabled_guard_reject_activation_and_reads(
    migrator_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sqlalchemy.exc import DBAPIError

    async with ready(migrator_engine, monkeypatch) as (market, lease, candidate, c, _):
        for inventory in ({}, INVENTORY | {"readers_compatible": "true"}):
            with pytest.raises(DBAPIError, match="activation evidence incomplete"):
                async with migrator_engine.begin() as conn:
                    await conn.execute(
                        text("SELECT activate_candle_closure(true,CAST(:i AS jsonb))"),
                        {"i": json.dumps(inventory)},
                    )
        async with market_data_session(market) as session:
            await closure.record_candidate(session, lease, candidate.observation)
        async with migrator_engine.begin() as conn:
            await conn.execute(text("SELECT begin_indicator_source_maintenance()"))
            await conn.execute(
                text("ALTER TABLE market_candles DISABLE TRIGGER candle_closure_write_guard")
            )
        async with user_session(engine_engine, uuid4(), role=DatabaseRole.ENGINE) as session:
            with pytest.raises(closure.ClosureUnavailableError, match="guards unavailable"):
                await closure.current_proof(session, c)
        with pytest.raises(DBAPIError, match="activation evidence incomplete"):
            async with migrator_engine.begin() as conn:
                await conn.execute(
                    text("SELECT activate_candle_closure(true,CAST(:i AS jsonb))"),
                    {"i": json.dumps(INVENTORY)},
                )


async def test_known_conflict_blocks_later_entry_until_fresh_matching_repair(
    migrator_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import timedelta

    from tiewtrade.core.money import Quantity
    from tiewtrade.core.positions import PositionPair
    from tiewtrade.infra.bots.candle_sources import candle_source_state
    from tiewtrade.infra.market_data.claims import claim_next, write_candles
    from tiewtrade.infra.market_data.storage import database_now

    async with ready(migrator_engine, monkeypatch) as (market, lease, candidate, c, started):
        async with market_data_session(market) as session:
            first = await closure.record_candidate(session, lease, candidate.observation)
            await session.execute(
                """INSERT INTO market_candle_demand
                (source,base,quote,timeframe,desired_start,desired_end,requested_at)
                VALUES(:source,:base,:quote,:timeframe,:open_at,:end_at,clock_timestamp())""",
                closure.key(c) | {"end_at": c.end_at},
            )
        async with market_data_session(market) as session:
            await begin_source_write(session)
            await closure.invalidate(
                session,
                replace(c, volume=c.volume + Quantity.of(1, c.base)),
                fetch_started_at=started,
                reason="REST_CONFLICT",
            )
            # Re-reading the retained canonical row is not fresh repair evidence.
            assert await closure.reconcile(session, c) is None
        async with user_session(engine_engine, uuid4(), role=DatabaseRole.ENGINE) as session:
            state = await candle_source_state(session, PositionPair(c.base, c.quote), c.timeframe)
            assert not state.ready
            conflicted_at = state.recovery_at
            assert conflicted_at is not None
        async with market_data_session(market) as session:
            claim = await claim_next(session, "fresh-repair")
            assert claim is not None
        fresh = replace(c, observed_at=c.observed_at + timedelta(seconds=2))
        async with market_data_session(market) as session:
            await begin_source_write(session)
            await write_candles(session, claim, (fresh,), started + timedelta(seconds=1))
            receipt = await closure.current_proof(session, fresh)
            assert receipt is not None and receipt["id"] != first
            healthy, repaired = await closure.series_health(
                session, c.base, c.quote, c.timeframe, await database_now(session)
            )
            assert healthy and repaired is not None and repaired >= conflicted_at


@pytest.mark.parametrize("progression", ["conflict", "older"])
async def test_conflicting_open_to_close_never_publishes_a_tradable_proof(
    progression: str,
    migrator_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from typing import cast

    from tiewtrade.core.money import Money
    from tiewtrade.infra.realtime.notifications import RedisNotifications
    from tiewtrade.services.market_data.candle_realtime import CandleConflictError, CandleSupervisor
    from tiewtrade.venues.candle_streams import FeedCandle
    from tiewtrade.venues.fake import FakeCandleFeed

    async with ready(migrator_engine, monkeypatch) as (market, lease, candidate, c, _):
        native = candidate.observation
        prior = replace(
            native,
            closed_hint=False,
            candle=replace(
                c, open=c.open + Money.of(1, c.quote), high=c.high + Money.of(1, c.quote)
            ),
        )
        if progression == "older":
            from tiewtrade.core.money import Quantity

            prior = replace(
                native,
                closed_hint=False,
                trade_count=native.trade_count + 1,
                last_trade_id=native.last_trade_id + 1,
                candle=replace(c, volume=c.volume + Quantity.of(1, c.base)),
            )
        supervisor = CandleSupervisor(
            market, FakeCandleFeed((FeedCandle(1, native),)), cast(RedisNotifications, None)
        )
        supervisor.lease, supervisor.epoch = lease, 1
        supervisor.catalog = await _catalog(market)
        supervisor.observe(FeedCandle(1, prior))
        staged, release = asyncio.Event(), asyncio.Event()
        original = closure.record_candidate

        async def stage_candidate(*args: Any, **kwargs: Any) -> UUID | None:
            result = await original(*args, **kwargs)
            staged.set()
            await release.wait()
            return result

        monkeypatch.setattr(closure, "record_candidate", stage_candidate)

        # Any attempt to match before persisting the contradiction fails this test.
        async def no_promotion(*args: Any, **kwargs: Any) -> UUID | None:
            raise AssertionError("conflicting close must not be reconciled/promoted")

        monkeypatch.setattr(closure, "reconcile", no_promotion)
        consumer = asyncio.create_task(supervisor._consume())
        try:
            await asyncio.wait_for(staged.wait(), 3)
            async with user_session(engine_engine, uuid4(), role=DatabaseRole.ENGINE) as session:
                with pytest.raises(closure.ClosureUnavailableError):
                    await closure.current_proof(session, c)
            release.set()
            with pytest.raises(CandleConflictError):
                await asyncio.wait_for(consumer, 3)
        finally:
            release.set()
            if not consumer.done():
                consumer.cancel()
            await asyncio.gather(consumer, return_exceptions=True)
        async with user_session(engine_engine, uuid4(), role=DatabaseRole.ENGINE) as session:
            with pytest.raises(closure.ClosureUnavailableError):
                await closure.current_proof(session, c)
            row = (
                await session.execute("SELECT finality,closure_proof_id FROM market_candles")
            ).one()
            assert row.finality == "UNCONFIRMED" and row.closure_proof_id is None
            assert (
                await session.execute("SELECT status FROM market_candle_closure_state")
            ).scalar_one() == "INVALIDATED"
            result = (
                await session.execute("SELECT outcome,canonical FROM market_candle_closure_results")
            ).one()
            assert result.outcome == "INVALIDATED"
            assert (
                result.canonical["details"]["native"]["open"]
                == prior.candle.open.as_parts()["amount"]
            )
