import asyncio
import json
from pathlib import Path
from time import monotonic
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market.profile_workload import OwnerState, market_buy, seed_owners
from tests.infra.risk_limits.profile_stop_runtime import UserStopScheduleRunner
from tests.infra.risk_limits.profile_stop_schedule import build_stop_schedule
from tiewtrade.core.orders import TradingMode
from tiewtrade.infra.db import user_session
from tiewtrade.infra.paper_orders.requests import admit_new_request
from tiewtrade.infra.trading_stops import read_status
from tiewtrade.services.engine.kill_switch import run_stop_request_round
from tiewtrade.services.engine.risk_limit import run_risk_stop_round


async def _run_stop_workers(
    engine_engine: AsyncEngine, scan_engine: AsyncEngine, stopped: asyncio.Event
) -> None:
    while not stopped.is_set():
        await run_stop_request_round(engine=engine_engine, scan_engine=scan_engine)
        await run_risk_stop_round(engine=engine_engine, scan_engine=scan_engine, limit=100)
        await asyncio.sleep(0.005)


@pytest.mark.parametrize(("phase", "owner_count"), [("W1", 2), ("W2", 10)])
@pytest.mark.asyncio
async def test_user_stop_schedule_runs_real_inbox_recovery_and_resume(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    tmp_path: Path,
    phase: str,
    owner_count: int,
) -> None:
    owners = await seed_owners(api_engine, engine_engine, scan_engine, owner_count)
    for index, owner in enumerate(owners):
        use = "BOT" if phase == "W2" or index == 1 else "MANUAL"
        async with user_session(api_engine, owner.user_id) as session:
            await session.execute(
                "INSERT INTO user_trading_preferences(user_id,use) VALUES(:owner,:use)",
                {"owner": owner.user_id, "use": use},
            )

    stopped = asyncio.Event()
    worker = asyncio.create_task(_run_stop_workers(engine_engine, scan_engine, stopped))
    journal = tmp_path / f"{phase.lower()}-stop-schedule.jsonl"

    async def post_cutoff(owner: OwnerState) -> dict[str, object]:
        return {"probe_owner": str(owner.user_id), "command_state": "SUCCEEDED"}

    async def prepare_queued(owner: OwnerState) -> UUID:
        async with migrator_engine.begin() as connection:
            await connection.execute(
                text(
                    f"""CREATE FUNCTION f19_test_defer_request() RETURNS trigger
                    LANGUAGE plpgsql AS $$ BEGIN
                      IF NEW.user_id='{owner.user_id}'::uuid THEN
                        NEW.next_attempt_at=clock_timestamp()+interval '5 minutes';
                      END IF;
                      RETURN NEW;
                    END $$"""
                )
            )
            await connection.execute(
                text(
                    """CREATE TRIGGER f19_test_defer_request BEFORE INSERT
                    ON paper_order_request_dispatch FOR EACH ROW
                    EXECUTE FUNCTION f19_test_defer_request()"""
                )
            )
        try:
            async with user_session(api_engine, owner.user_id) as session:
                request = await admit_new_request(
                    session,
                    wallet_id=owner.wallet.wallet_id,
                    intent=market_buy(owner, uuid4(), -1),
                )
        finally:
            async with migrator_engine.begin() as connection:
                await connection.execute(
                    text(
                        "DROP TRIGGER IF EXISTS f19_test_defer_request "
                        "ON paper_order_request_dispatch"
                    )
                )
                await connection.execute(text("DROP FUNCTION IF EXISTS f19_test_defer_request()"))
        return request.request_id

    async def prepare_partial(owner: OwnerState) -> dict[str, object]:
        partial_lifecycle.append("PREPARED")
        return {"partially_filled": True, "prepared_owner": str(owner.user_id)}

    async def finish_partial(owner: OwnerState) -> None:
        partial_lifecycle.append(f"EFFECTS_COMPLETE:{owner.user_id}")

    partial_lifecycle: list[str] = []

    try:
        runner = UserStopScheduleRunner(
            api_engine=api_engine,
            schedule=build_stop_schedule(phase, [owner.user_id for owner in owners]),
            owners=owners,
            journal=journal,
            offset_scale=0.001,
        )
        await runner.run(
            started=monotonic(),
            post_cutoff_probe=post_cutoff,
            prepare_queued=prepare_queued if phase == "W1" else None,
            prepare_partial=prepare_partial if phase == "W1" else None,
            finish_partial=finish_partial if phase == "W1" else None,
        )
    finally:
        stopped.set()
        await worker

    rows = [json.loads(line) for line in journal.read_text().splitlines()]
    assert rows
    expected_resumes = 1 if phase == "W1" else owner_count
    assert sum(row["action"] == "RESUME_APPLIED" for row in rows) == expected_resumes
    if phase == "W1":
        assert partial_lifecycle == ["PREPARED", f"EFFECTS_COMPLETE:{owners[1].user_id}"]
        generations = [
            int(row["generation"])
            for row in rows
            if row["action"] == "STOP_SUBMITTED" and row["owner"] == str(owners[0].user_id)
        ]
        assert generations == [1, 2]
    else:
        assert sum(row["action"] == "EXACT_DUPLICATE_RECOVERED" for row in rows) == 3
        assert sum(row["action"] == "LOST_ACK_RECOVERED" for row in rows) == 3
        assert sum(row["action"] == "STALE_RESUME_REJECTED" for row in rows) == 2

    for index, owner in enumerate(owners):
        async with user_session(api_engine, owner.user_id) as session:
            status = await read_status(session, TradingMode.PAPER)
        if phase == "W1" and index == 0:
            assert status.stop_id is not None and status.generation == 2
            assert not status.resume_ready
        else:
            assert status.stop_id is None
            assert not status.resume_ready


def test_user_stop_schedule_rejects_invalid_runtime_binding(tmp_path: Path) -> None:
    owners = [UUID(int=1), UUID(int=2)]
    schedule = build_stop_schedule("W1", owners)

    with pytest.raises(ValueError, match="runtime owners"):
        UserStopScheduleRunner(
            api_engine=None,  # type: ignore[arg-type]
            schedule=schedule,
            owners=[],
            journal=tmp_path / "journal.jsonl",
        )
    with pytest.raises(ValueError, match="offset scale"):
        UserStopScheduleRunner(
            api_engine=None,  # type: ignore[arg-type]
            schedule=schedule,
            owners=[
                OwnerState(owner, None)  # type: ignore[arg-type]
                for owner in owners
            ],
            journal=tmp_path / "journal.jsonl",
            offset_scale=0,
        )
