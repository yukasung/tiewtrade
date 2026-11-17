"""Small real fixture proof before the single20owner rebuild campaign."""

import asyncio
import hashlib
import json
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from tests.infra.execution_market import profile_internal as internal
from tests.infra.execution_market import profile_rebuild20 as rebuild
from tests.infra.execution_market import profile_workload as workload
from tests.infra.execution_market.profile_owned_pools import OwnedPools, validate_reports
from tests.infra.execution_market.profile_restore import economic_digest
from tests.infra.execution_market.test_evidence import source_record
from tests.infra.execution_market.test_tail_reads import market as market
from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.infra.market_data.order_book_codec import input_from_payload
from tiewtrade.infra.market_data.order_book_storage import metadata_from_payload, metadata_payload
from tiewtrade.infra.paper_orders import storage


@pytest.mark.parametrize("parallel_runtime", [False, True])
async def test_small_real_economic_history_full_replay(
    internal_database: None, tmp_path: Path, parallel_runtime: bool
) -> None:
    with OwnedPools(tmp_path / "pools.json", rebuild.POOL_CONFIGURATION):
        engines = [
            create_engine_for(role)
            for role in (
                DatabaseRole.API,
                DatabaseRole.ENGINE,
                DatabaseRole.ENGINE_SCAN,
                DatabaseRole.MARKET_DATA,
            )
        ]
        admin = internal.readonly_admin()
        try:
            owners, publisher, counters = await rebuild.prepare_economics(
                engines[0],
                engines[1],
                engines[2],
                engines[3],
                tmp_path,
                owners=2,
                cycles=1,
                baseline=1,
                parallel_runtime=parallel_runtime,
            )
            assert counters.completed == 10 and counters.cycles == 2
            before = await economic_digest(admin)
            head = max(50, publisher.journal.count + 20)
            await publisher.extend(head)
            await rebuild.pad_history(engines[1], owners, publisher.journal, head)
            assert await economic_digest(admin) == before
            report: dict[str, Any] = {}
            await rebuild.verify_rebuild(
                engines[1], admin, owners, tmp_path, cycles=1, baseline=1, report=report
            )
            assert all(item["passed"] for item in report["financial"])
            assert report["global"]["passed"] and report["global"]["input_lag"] == 0
            assert report["positions"]["passed"]
            assert len(report["positions"]["replays"]) == 2
            assert all(row["evidence_records"] == head for row in report["positions"]["replays"])
            # A valid new digest cannot replace an existing source identity.
            original_journal = publisher.journal.path.read_text()
            rows = original_journal.splitlines()
            row = json.loads(rows[0])
            changed = source_record()
            market = input_from_payload(row["market"])
            metadata = metadata_from_payload(row["metadata"])
            changed = replace(
                changed,
                market=market,
                metadata=replace(
                    metadata, observed_at=metadata.observed_at + timedelta(microseconds=1)
                ),
            )
            row.update(
                metadata=metadata_payload(changed.metadata), digest=storage._source_digest(changed)
            )
            rows[0] = json.dumps(row)
            publisher.journal.path.write_text("\n".join(rows) + "\n")
            with pytest.raises(ValueError, match="source differs"):
                await rebuild.pad_history(engines[1], owners, publisher.journal, head)
            publisher.journal.path.write_text(original_journal)
            assert await economic_digest(admin) == before
        finally:
            for engine in [*engines, admin]:
                await engine.dispose()
    assert json.loads((tmp_path / "pools.json").read_text())["passed"]
    progress = json.loads((tmp_path / "fixture-progress.json").read_text())
    assert progress["counters"]["completed"] == 10
    poll = json.loads((tmp_path / "parent-poll-gate.json").read_text())
    assert poll["active"] == 0 and not poll["truncated"]
    assert poll["attempt_count"] == poll["finished_count"] > 0
    assert poll["limit"] == 4 and poll["poll_seconds"] == 0.25 and poll["peak"] <= 4
    if parallel_runtime:
        trace = tmp_path / "parent-poll-attempts.jsonl"
        assert poll["attempts"] == []
        assert poll["attempts_jsonl"] == str(trace)
        assert len(trace.read_text().splitlines()) == poll["attempt_count"]
        paths = [
            Path(value).with_suffix(".owned-pools.json") for value in progress["worker_metrics"]
        ]
        assert len(paths) == len(progress["workers"]) == 20
        assert all(worker["returncode"] == 0 for worker in progress["workers"])
        assert len({worker["runtime_pid"] for worker in progress["workers"]}) == 20
        assert validate_reports(tmp_path / "pools.json", paths, 20, rebuild_fixture=True)["passed"]


@pytest.mark.parametrize("fault", ["hole", "digest", "missing"])
def test_journal_rejects_missing_or_changed_source(tmp_path: Path, fault: str) -> None:
    journal = rebuild.SourceJournal(tmp_path / "journal")
    journal.append(source_record())
    journal.flush()
    if fault != "missing":
        row = json.loads(journal.path.read_text())
        if fault == "hole":
            market = json.loads(row["market"])
            market["input_id"] = 2
            row["market"] = json.dumps(market)
        else:
            row["digest"] = "0" * 64
        journal.path.write_text(json.dumps(row) + "\n")
    with pytest.raises(ValueError):
        list(journal.batches(2 if fault == "missing" else 1))


def test_journal_retention_and_output_reuse(tmp_path: Path) -> None:
    journal = rebuild.SourceJournal(tmp_path / "journal")
    original = source_record()
    for number in range(1, 1002):
        record = replace(original, market=replace(original.market, input_id=number))
        record = replace(record, digest=storage._source_digest(record))
        journal.append(record)
        assert len(journal.pending) < rebuild.BATCH
    assert [len(batch) for batch in journal.batches(1001)] == [500, 500, 1]
    with pytest.raises(FileExistsError):
        rebuild.SourceJournal(journal.path)


async def test_publisher_does_not_journal_unknown_commit(tmp_path: Path) -> None:
    journal = rebuild.SourceJournal(tmp_path / "journal")
    publisher = rebuild.FixturePublisher(None, journal)  # type: ignore[arg-type]
    record = source_record()
    original = AsyncMock(return_value=object())

    async def fail_exit(*args: object, **kwargs: object) -> None:
        await vars(workload)["publish_input"](None, None, record.market, record.metadata)
        raise ConnectionError("ambiguous fixture commit")

    with (
        patch.object(rebuild, "guard_engines"),
        patch.object(workload, "acquire_sources", AsyncMock(return_value=(object(), object()))),
        patch.object(rebuild, "publish_input", original),
        patch.object(workload, "publish_market", fail_exit),
        pytest.raises(ConnectionError),
    ):
        await publisher.tick()
    original.assert_awaited_once()
    assert journal.count == 0 and journal.path.read_text() == ""


@pytest.mark.parametrize("cancelled", [False, True])
async def test_cleanup_joins_and_keeps_primary(tmp_path: Path, cancelled: bool) -> None:
    stop = asyncio.Event()
    done = asyncio.Event()
    journal = rebuild.SourceJournal(tmp_path / "journal")

    async def worker() -> None:
        await stop.wait()
        await asyncio.sleep(0)
        done.set()

    task = asyncio.create_task(worker())
    primary = asyncio.CancelledError() if cancelled else TimeoutError()
    with (
        patch.object(journal, "flush", side_effect=OSError("fixture IO")),
        pytest.raises(type(primary)) as caught,
    ):
        try:
            raise primary
        finally:
            await rebuild.finish_mutators((task,), stop, journal, primary=primary)
    assert caught.value is primary and task.done() and done.is_set()
    assert primary.__notes__ == ["rebuild mutator cleanup failed: OSError"]


@pytest.mark.usefixtures("internal_database")
async def test_guard_rejects_other_database_before_mutation() -> None:
    engine = create_async_engine("postgresql+asyncpg://localhost/owner_database")
    try:
        with pytest.raises(ValueError, match="differs"):
            rebuild.guard_engines(engine)
    finally:
        await engine.dispose()


async def test_repeated_cancellation_waits_for_owned_mutator(tmp_path: Path) -> None:
    stop, release = asyncio.Event(), asyncio.Event()
    journal = rebuild.SourceJournal(tmp_path / "journal")

    async def worker() -> None:
        await stop.wait()
        await release.wait()

    task = asyncio.create_task(worker())
    closing = asyncio.create_task(rebuild.finish_mutators((task,), stop, journal))
    await stop.wait()
    closing.cancel()
    await asyncio.sleep(0)
    closing.cancel()
    await asyncio.sleep(0)
    assert not closing.done() and not task.done()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await closing
    assert task.done()


async def test_partial_worker_startup_stops_only_remembered_child(tmp_path: Path) -> None:
    child = Mock(returncode=None)
    stop_path = tmp_path / "child.stop"
    started = AsyncMock(side_effect=[([child], stop_path, [tmp_path / "child.json"]), OSError()])
    stopping = AsyncMock()
    processes: list[Any] = []
    with (
        patch.object(workload, "start_worker_processes", started),
        patch.object(workload, "stop_worker_processes", stopping),
        patch.object(workload, "worker_process_failures", return_value=[]),
        pytest.raises(OSError),
    ):
        await rebuild.parallel_workers(tmp_path, asyncio.Event(), processes, [])
    assert processes == [child] and stop_path.exists()
    stopping.assert_awaited_once_with(processes, tmp_path / "prep-all.stop")
    assert started.call_args_list[0].kwargs["coordinate_claims"] is True
    assert started.call_args_list[0].kwargs["r8_claim_budget"] is True


@pytest.mark.parametrize("hz", [0, 2, True])
async def test_invalid_cadence_rejected_before_publication(tmp_path: Path, hz: int) -> None:
    publisher = rebuild.FixturePublisher(None, rebuild.SourceJournal(tmp_path / "journal"))  # type: ignore[arg-type]
    with patch.object(publisher, "tick", AsyncMock()) as tick, pytest.raises(ValueError):
        await publisher.paced(asyncio.Event(), hz=hz)
    tick.assert_not_awaited()


@pytest.mark.parametrize("fault", ["normal", "remote", "mismatch"])
def test_fixture_worker_role_guard(fault: str) -> None:
    environment = {
        "TIEWTRADE_DATABASE_URL_ENGINE": "postgresql://localhost/tiewtrade_internal20_test_guard",
        "TIEWTRADE_DATABASE_URL_ENGINE_SCAN": "postgresql://localhost/tiewtrade_internal20_test_guard",
    }
    if fault == "normal":
        environment["TIEWTRADE_DATABASE_URL_ENGINE"] = "postgresql://localhost/owner_data"
    elif fault == "remote":
        environment["TIEWTRADE_DATABASE_URL_ENGINE"] = (
            "postgresql://example.com/tiewtrade_internal20_test_guard"
        )
    else:
        environment["TIEWTRADE_DATABASE_URL_ENGINE_SCAN"] += "_different"
    with pytest.raises(ValueError):
        rebuild.guard_fixture_worker(environment)


@pytest.mark.parametrize(
    "options",
    [
        {"rebuild_fixture": True, "acceptance_profile": internal.NAME},
        {"rebuild_fixture": True, "r8_claim_budget": False},
        {"rebuild_fixture": True, "coordinate_claims": False},
        {"rebuild_fixture": "yes"},
    ],
)
async def test_fixture_launcher_rejects_profile_mix_before_spawn(
    tmp_path: Path, options: dict[str, Any]
) -> None:
    with (
        patch.object(asyncio, "create_subprocess_exec", AsyncMock()) as spawn,
        pytest.raises(ValueError),
    ):
        await workload.start_worker_processes(
            1,
            tmp_path,
            **{
                "r8_claim_budget": True,
                "coordinate_claims": True,
                **options,
            },
        )
    spawn.assert_not_awaited()


@pytest.mark.parametrize("fixture", [False, True])
async def test_fixture_launcher_selects_entry_and_keeps_role_environment(
    tmp_path: Path, fixture: bool
) -> None:
    child = Mock(pid=999000)
    try:
        with (
            patch.object(asyncio, "create_subprocess_exec", AsyncMock(return_value=child)) as spawn,
            patch.object(workload, "wait_runtime_pid", AsyncMock(return_value=999001)),
        ):
            await workload.start_worker_processes(
                1, tmp_path, rebuild_fixture=fixture, r8_claim_budget=True, coordinate_claims=True
            )
        expected = "profile_rebuild20" if fixture else "profile_workload"
        assert spawn.call_args.args[2] == "tests.infra.execution_market." + expected
        assert {k for k in spawn.call_args.kwargs["env"] if k.startswith("TIEWTRADE_")} <= {
            "TIEWTRADE_DATABASE_URL_ENGINE",
            "TIEWTRADE_DATABASE_URL_ENGINE_SCAN",
        }
    finally:
        workload.WORKER_RUNTIME_PIDS.pop(999000, None)


async def test_fixture_shutdown_bounds_stuck_child_and_reports_pid(tmp_path: Path) -> None:
    child = Mock(pid=123, returncode=None)

    child.wait = never_finishes
    with (
        patch.object(workload, "stop_worker_processes", side_effect=never_finishes),
        pytest.raises(TimeoutError) as caught,
    ):
        await rebuild.stop_fixture_workers(
            [child], tmp_path / "stop", graceful_seconds=0.01, termination_seconds=0.01
        )
    child.terminate.assert_called_once()
    assert "fixture workers remain: [123]" in caught.value.__notes__


async def never_finishes(*args: object) -> None:
    await asyncio.Event().wait()


async def test_fixture_shutdown_keeps_error_and_continues_after_signal_failure(
    tmp_path: Path,
) -> None:
    primary = OSError("stop file unavailable")
    failed = Mock(pid=123, returncode=None)
    failed.terminate.side_effect = PermissionError()
    failed.wait = AsyncMock(return_value=0)
    sibling = Mock(pid=456, returncode=None)

    async def exit_sibling() -> int:
        sibling.returncode = 0
        return 0

    sibling.wait = exit_sibling
    with (
        patch.object(workload, "stop_worker_processes", AsyncMock(side_effect=primary)),
        pytest.raises(OSError) as caught,
    ):
        await rebuild.stop_fixture_workers([failed, sibling], tmp_path / "stop")
    assert caught.value is primary
    sibling.terminate.assert_called_once()
    failed.wait.assert_awaited_once()
    assert any("PermissionError" in note for note in primary.__notes__)
    assert "fixture workers remain: [123]" in primary.__notes__


def test_fixture_helpers_are_pinned_before_execution(tmp_path: Path) -> None:
    source = tmp_path / "external.py"
    content = "raise RuntimeError('top-level must not execute')\n" + "\n".join(
        f"def {name}(): return '{name}'"
        for name in ("run", "sql", "environment", "create", "cleanup")
    )
    source.write_text(content)
    output = tmp_path / "campaign"
    output.mkdir()
    namespace: dict[str, Any] = {}
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    rebuild.load_fixture_helpers(source, output, digest, namespace)
    source.write_text("changed external source")
    assert namespace["create"]() == "create"
    assert (output / "fixture-helpers.py").read_text() == content
    assert (output / "fixture-helpers.sha256").read_text().strip() == digest
    with pytest.raises(ValueError, match="digest"):
        rebuild.load_fixture_helpers(source, output, digest, {})


@pytest.mark.parametrize("fault", ["digest", "missing", "reuse"])
def test_fixture_helper_failure_prevents_execution(tmp_path: Path, fault: str) -> None:
    source = tmp_path / "external.py"
    source.write_text("def run(): pass\n")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    output = tmp_path / "campaign"
    output.mkdir()
    if fault == "digest":
        digest = "0" * 64
    elif fault == "reuse":
        (output / "fixture-helpers.py").touch()
    namespace: dict[str, Any] = {}
    with pytest.raises((ValueError, FileExistsError)):
        rebuild.load_fixture_helpers(source, output, digest, namespace)
    assert namespace == {}


@pytest.mark.parametrize("fixture", [False, True])
async def test_worker_startup_failure_uses_matching_cleanup(tmp_path: Path, fixture: bool) -> None:
    child = Mock(pid=999000)
    primary = RuntimeError("runtime PID unavailable")
    try:
        with (
            patch.object(asyncio, "create_subprocess_exec", AsyncMock(return_value=child)),
            patch.object(workload, "wait_runtime_pid", AsyncMock(side_effect=primary)),
            patch.object(rebuild, "stop_fixture_workers", AsyncMock()) as fixture_stop,
            patch.object(workload, "stop_worker_processes", AsyncMock()) as ordinary_stop,
            pytest.raises(RuntimeError) as caught,
        ):
            await workload.start_worker_processes(
                1, tmp_path, rebuild_fixture=fixture, r8_claim_budget=True, coordinate_claims=True
            )
        assert caught.value is primary
        selected, unused = (
            (fixture_stop, ordinary_stop) if fixture else (ordinary_stop, fixture_stop)
        )
        selected.assert_awaited_once_with([child], tmp_path / "worker.stop")
        unused.assert_not_awaited()
    finally:
        workload.WORKER_RUNTIME_PIDS.pop(child.pid, None)


async def test_fixture_shutdown_preserves_cancellation_and_exit_race(tmp_path: Path) -> None:
    primary = asyncio.CancelledError()
    child = Mock(pid=123, returncode=None)
    child.terminate.side_effect = ProcessLookupError()

    async def exited() -> int:
        child.returncode = 0
        return 0

    child.wait = exited
    with (
        patch.object(workload, "stop_worker_processes", AsyncMock(side_effect=primary)),
        pytest.raises(asyncio.CancelledError) as caught,
    ):
        await rebuild.stop_fixture_workers([child], tmp_path / "stop")
    assert caught.value is primary
    assert child.returncode == 0


async def test_fixture_shutdown_success_does_not_signal(tmp_path: Path) -> None:
    child = Mock(pid=123, returncode=0)
    with patch.object(workload, "stop_worker_processes", AsyncMock()) as stop:
        await rebuild.stop_fixture_workers([child], tmp_path / "stop")
    stop.assert_awaited_once_with([child], tmp_path / "stop")
    child.terminate.assert_not_called()


async def test_fixture_startup_keeps_remaining_pid_evidence(tmp_path: Path) -> None:
    primary = RuntimeError("runtime PID unavailable")
    cleanup = TimeoutError()
    cleanup.add_note("fixture workers remain: [999000]")
    child = Mock(pid=999000)
    with (
        patch.object(asyncio, "create_subprocess_exec", AsyncMock(return_value=child)),
        patch.object(workload, "wait_runtime_pid", AsyncMock(side_effect=primary)),
        patch.object(rebuild, "stop_fixture_workers", AsyncMock(side_effect=cleanup)),
        pytest.raises(RuntimeError) as caught,
    ):
        await workload.start_worker_processes(
            1, tmp_path, rebuild_fixture=True, r8_claim_budget=True, coordinate_claims=True
        )
    assert caught.value is primary
    assert "fixture workers remain: [999000]" in primary.__notes__
