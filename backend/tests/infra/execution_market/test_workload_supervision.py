"""The workload must preserve the first producer failure and join abandoned work."""

import asyncio
from pathlib import Path
from unittest.mock import Mock

import pytest

from tests.infra.execution_market.profile_workload import with_publisher


@pytest.mark.parametrize("fails", [True, False])
async def test_publisher_exit_stops_and_joins_workload(fails: bool) -> None:
    started = asyncio.Event()
    release = asyncio.Event()
    joined = asyncio.Event()
    failure = RuntimeError("injected publisher failure")

    async def publisher() -> None:
        await release.wait()
        if fails:
            raise failure

    async def workload() -> None:
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            joined.set()

    producer = asyncio.create_task(publisher())
    task = asyncio.create_task(with_publisher(workload(), producer))
    await started.wait()
    release.set()
    async with asyncio.timeout(1):
        with pytest.raises(RuntimeError) as caught:
            await task
    assert joined.is_set()
    if fails:
        assert caught.value is failure
    else:
        assert str(caught.value) == "F15_WORKLOAD_PUBLISHER_STOPPED_UNEXPECTEDLY"


async def test_completed_operation_keeps_publisher_alive() -> None:
    async def workload() -> int:
        return 42

    async def publisher() -> None:
        await asyncio.Event().wait()

    monitored = asyncio.create_task(publisher())
    try:
        assert await with_publisher(workload(), monitored) == 42
        assert not monitored.done()
    finally:
        monitored.cancel()
        await asyncio.gather(monitored, return_exceptions=True)


async def test_external_cancel_joins_operation_without_canceling_publisher() -> None:
    started = asyncio.Event()
    joined = asyncio.Event()

    async def publisher() -> None:
        await asyncio.Event().wait()

    async def workload() -> None:
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            joined.set()

    producer = asyncio.create_task(publisher())
    task = asyncio.create_task(with_publisher(workload(), producer))
    try:
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert joined.is_set() and not producer.done()
    finally:
        producer.cancel()
        await asyncio.gather(producer, return_exceptions=True)


def test_mac_resource_sample_preserves_cpu_seconds_and_rss_bytes() -> None:
    from tests.infra.execution_market.profile_workload import mac_process_sample

    assert mac_process_sample(" 123 01:02.50 2048\n456 1-02:03:04.00 1024\n", [123, 456]) == [
        {"Id": 123, "CPU": 62.5, "WorkingSet64": 2097152},
        {"Id": 456, "CPU": 93784.0, "WorkingSet64": 1048576},
    ]
    with pytest.raises(RuntimeError, match="INCOMPLETE"):
        mac_process_sample("123 00:00.01 1\n", [123, 456])


@pytest.mark.parametrize("existing", [None, "42"])
def test_interrupted_pid_publication_never_exposes_partial_value(
    tmp_path: object, monkeypatch: pytest.MonkeyPatch, existing: str | None
) -> None:
    import os
    from pathlib import Path

    from tests.infra.execution_market.profile_workload import publish_runtime_pid

    assert isinstance(tmp_path, Path)
    metrics = tmp_path / "worker.json"
    watched = metrics.with_suffix(".pid")
    if existing is not None:
        watched.write_text(existing)
    original = Path.write_text

    def interrupted(path: Path, data: str, **kwargs: object) -> int:
        original(path, "", encoding="ascii")
        raise OSError("interrupted PID publication")

    with monkeypatch.context() as patch:
        patch.setattr(Path, "write_text", interrupted)
        with pytest.raises(OSError, match="interrupted"):
            publish_runtime_pid(metrics)
    if existing is None:
        assert not watched.exists()
    else:
        assert watched.read_text() == existing
    publish_runtime_pid(metrics)
    assert int(watched.read_text()) == os.getpid()


@pytest.mark.parametrize("transient", ["missing", "empty"])
async def test_runtime_pid_wait_handles_delayed_file_visibility(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, transient: str
) -> None:
    from tests.infra.execution_market.profile_workload import wait_runtime_pid

    metrics = tmp_path / "worker.json"
    watched = metrics.with_suffix(".pid")
    watched.write_text("4242")
    process = Mock(spec=asyncio.subprocess.Process)
    process.returncode = None
    original = Path.read_text
    first = True

    def delayed(path: Path, **kwargs: object) -> str:
        nonlocal first
        if path == watched and first:
            first = False
            if transient == "missing":
                raise FileNotFoundError("metadata visible before readable file")
            return ""
        return original(path)

    monkeypatch.setattr(Path, "read_text", delayed)
    assert await wait_runtime_pid(process, metrics, timeout_seconds=1) == 4242


@pytest.mark.parametrize("pid", [0, -1])
async def test_runtime_pid_wait_rejects_invalid_process_identity(tmp_path: Path, pid: int) -> None:
    from tests.infra.execution_market.profile_workload import wait_runtime_pid

    metrics = tmp_path / "worker.json"
    metrics.with_suffix(".pid").write_text(str(pid))
    process = Mock(spec=asyncio.subprocess.Process)
    process.returncode = None
    with pytest.raises(RuntimeError, match="PID_INVALID"):
        await wait_runtime_pid(process, metrics)


async def test_dead_worker_cannot_reuse_a_preexisting_runtime_pid(tmp_path: Path) -> None:
    from tests.infra.execution_market.profile_workload import wait_runtime_pid

    metrics = tmp_path / "worker.json"
    metrics.with_suffix(".pid").write_text("4242")
    process = Mock(spec=asyncio.subprocess.Process)
    process.returncode = 1
    with pytest.raises(RuntimeError, match="EXITED_BEFORE_READY"):
        await wait_runtime_pid(process, metrics)
