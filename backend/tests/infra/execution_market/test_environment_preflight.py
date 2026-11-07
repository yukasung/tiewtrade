"""NC12 admission is bounded, fail closed and separate from workload acceptance."""

import asyncio
import json
import os
import shutil
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, Mock

import pytest

from tests.infra.execution_market import profile_internal as internal
from tests.infra.execution_market import profile_workload as workload


@pytest.fixture
def host(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    state = SimpleNamespace(now=100.0, sleeps=[])

    async def sleep(seconds: float) -> None:
        state.sleeps.append(seconds)
        state.now += seconds

    monkeypatch.setattr(internal, "monotonic", lambda: state.now)
    monkeypatch.setattr(asyncio, "sleep", sleep)
    monkeypatch.setattr(os, "cpu_count", lambda: 8)
    monkeypatch.setattr(os, "getloadavg", lambda: (99.0, 99.0, 99.0))
    monkeypatch.setattr(
        internal,
        "mac_readiness",
        AsyncMock(return_value={"cpu_idle_percent": 20.0, "memory_pressure_level": 2}),
    )
    monkeypatch.setattr(shutil, "disk_usage", lambda path: SimpleNamespace(free=2 * 1024**3))
    return state


async def test_fixed_window_accepts_exact_boundaries_and_runs_fixture_once(
    tmp_path: Path, host: SimpleNamespace
) -> None:
    services = AsyncMock(return_value={"ready": True})
    fixture = AsyncMock(return_value=7)
    assert (
        await internal.run_preflighted(tmp_path / "preflight.json", tmp_path, services, fixture)
        == 7
    )
    document = json.loads((tmp_path / "preflight.json").read_text())
    assert document["status"] == "PASSED"
    assert document["mean_cpu_idle_percent"] == 20.0
    assert document["samples"][0]["load"][0] == 99.0
    assert document["samples"][0]["memory_pressure_level"] == 2
    assert [s["scheduled_offset_seconds"] for s in document["samples"]] == list(range(0, 121, 20))
    assert [s["monotonic"] for s in document["samples"]] == list(range(100, 221, 20))
    assert host.sleeps == [0, 20, 20, 20, 20, 20, 20]
    assert services.await_count == 2 and fixture.await_count == 1
    assert not (tmp_path / "run").exists()  # The gate does not pre-create workload output.


@pytest.mark.parametrize("failure", ["cpu", "memory", "disk", "before", "after", "observation"])
async def test_failure_never_invokes_workload_or_retries(
    tmp_path: Path, host: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    error = OSError("PRIVATE_NOT_RECORDED")
    services = AsyncMock(return_value={"ready": True})
    if failure in {"cpu", "memory"}:
        monkeypatch.setattr(
            internal,
            "mac_readiness",
            AsyncMock(
                return_value={
                    "cpu_idle_percent": 19.99 if failure == "cpu" else 20.0,
                    "memory_pressure_level": 4 if failure == "memory" else 1,
                }
            ),
        )
    elif failure == "disk":
        monkeypatch.setattr(
            shutil, "disk_usage", lambda path: SimpleNamespace(free=2 * 1024**3 - 1)
        )
    elif failure == "before":
        services.side_effect = error
    elif failure == "after":
        services.side_effect = [{"ready": True}, error]
    else:
        monkeypatch.setattr(os, "getloadavg", Mock(side_effect=error))
    fixture = AsyncMock()
    with pytest.raises((OSError, internal.EnvironmentNotReadyError)):
        await internal.run_preflighted(tmp_path / "preflight.json", tmp_path, services, fixture)
    document = json.loads((tmp_path / "preflight.json").read_text())
    assert document["status"] == "INCOMPLETE"
    assert "PRIVATE" not in (tmp_path / "preflight.json").read_text()
    assert fixture.await_count == 0
    assert len(document["samples"]) == (
        7 if failure in {"after", "cpu"} else 1 if failure in {"memory", "disk"} else 0
    )
    assert services.await_count == (2 if failure == "after" else 1)


@pytest.mark.parametrize(
    "load",
    [
        None,
        (),
        (1.0,),
        (1.0, 2.0, float("nan")),
        (float("inf"), 0, 0),
        (-1, 0, 0),
        (True, 0, 0),
        ("1", 0, 0),
    ],
)
def test_invalid_load_is_rejected(monkeypatch: pytest.MonkeyPatch, load: Any) -> None:
    monkeypatch.setattr(os, "getloadavg", lambda: load)
    with pytest.raises(internal.EnvironmentNotReadyError):
        internal.host_load()


@pytest.mark.parametrize("cpu", [None, 0, -1, True, 8.0])
def test_invalid_cpu_is_rejected(
    tmp_path: Path, host: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, cpu: Any
) -> None:
    monkeypatch.setattr(os, "cpu_count", lambda: cpu)
    with pytest.raises(internal.EnvironmentNotReadyError):
        internal.host_observation(tmp_path)


@pytest.mark.parametrize("free", [None, -1, True, 2147483648.0])
def test_invalid_disk_is_rejected(
    tmp_path: Path, host: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, free: Any
) -> None:
    monkeypatch.setattr(shutil, "disk_usage", lambda path: SimpleNamespace(free=free))
    with pytest.raises(internal.EnvironmentNotReadyError):
        internal.host_observation(tmp_path)


async def test_cancellation_records_incomplete_and_preserves_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    error = asyncio.CancelledError()
    services = AsyncMock(side_effect=error)
    fixture = AsyncMock()
    with pytest.raises(asyncio.CancelledError) as caught:
        await internal.run_preflighted(tmp_path / "preflight.json", tmp_path, services, fixture)
    assert caught.value is error and fixture.await_count == 0
    assert json.loads((tmp_path / "preflight.json").read_text())["error_type"] == "CancelledError"


async def test_cancellation_during_window_retains_partial_evidence(
    tmp_path: Path, host: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    error = asyncio.CancelledError()
    services = AsyncMock(return_value={"ready": True})
    fixture = AsyncMock()

    async def cancel_sleep(seconds: float) -> None:
        if seconds:
            raise error

    monkeypatch.setattr(asyncio, "sleep", cancel_sleep)
    with pytest.raises(asyncio.CancelledError) as caught:
        await internal.run_preflighted(tmp_path / "preflight.json", tmp_path, services, fixture)
    document = json.loads((tmp_path / "preflight.json").read_text())
    assert caught.value is error and fixture.await_count == 0
    assert document["status"] == "INCOMPLETE" and len(document["samples"]) == 1
    assert services.await_count == 1


@pytest.mark.parametrize("observe", [True, False])
async def test_resource_sampling_records_high_load_without_applying_admission_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, observe: bool
) -> None:
    stop = asyncio.Event()
    samples: list[dict[str, object]] = []
    database = {"bytes": 1, "connections": 1, "lock_waits": 0}
    result = Mock()
    result.mappings.return_value.one.return_value = database

    @asynccontextmanager
    async def connect() -> Any:
        yield SimpleNamespace(exec_driver_sql=AsyncMock(return_value=result))

    @asynccontextmanager
    async def market_session(engine: object) -> Any:
        async def execute(statement: str) -> Any:
            stop.set()
            return SimpleNamespace(scalar_one=lambda: 1)

        yield SimpleNamespace(execute=execute)

    def load() -> tuple[float, float, float]:
        assert observe, "default resource caller must not sample host load"
        return (99.0, 98.0, 97.0)

    monkeypatch.setattr(workload, "market_data_session", market_session)
    monkeypatch.setattr(internal, "host_load", load)
    await workload.resource_sampler(
        cast(Any, SimpleNamespace(connect=connect)),
        cast(Any, object()),
        [],
        asyncio.Lock(),
        stop,
        samples,
        observe_host=observe,
    )
    assert len(samples) == 1
    assert samples[0].get("host_load") == ((99.0, 98.0, 97.0) if observe else None)
    assert samples[0]["connections"] == 1


@pytest.mark.parametrize("idle", ["0", "20", "100"])
def test_cpu_parser_uses_second_interval_only(idle: str) -> None:
    assert internal.parse_cpu_idle(
        f"CPU usage: 0% user, 0% sys, 999% idle\nCPU usage: 0% user, 0% sys, {idle}% idle\n"
    ) == float(idle)


@pytest.mark.parametrize(
    "output",
    [
        "",
        "CPU usage: 100% idle",
        "CPU usage: 0% idle\nCPU usage: -1% idle",
        "CPU usage: 0% idle\nCPU usage: 101% idle",
        "CPU usage: 0% idle\nCPU usage: nan% idle",
        "CPU usage: 0% idle\nCPU usage: inf% idle",
    ],
)
def test_cpu_parser_rejects_missing_or_invalid_interval(output: str) -> None:
    with pytest.raises(internal.EnvironmentNotReadyError):
        internal.parse_cpu_idle(output)


@pytest.mark.parametrize("pressure", ["1", "2", "4"])
async def test_native_pressure_levels_are_preserved(
    monkeypatch: pytest.MonkeyPatch, pressure: str
) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")
    reader = AsyncMock(side_effect=["CPU usage: 0% idle\nCPU usage: 20% idle", pressure])
    monkeypatch.setattr(internal, "read_host_command", reader)
    assert await internal.mac_readiness() == {
        "cpu_idle_percent": 20.0,
        "memory_pressure_level": int(pressure),
    }
    assert reader.await_count == 2


@pytest.mark.parametrize("pressure", ["", "0", "3", "8", "Normal", "PRIVATE_ERROR"])
async def test_missing_unknown_pressure_cannot_admit_workload(
    monkeypatch: pytest.MonkeyPatch, pressure: str
) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(
        internal,
        "read_host_command",
        AsyncMock(
            side_effect=[
                "CPU usage: 0% idle\nCPU usage: 20% idle",
                pressure,
            ]
        ),
    )
    with pytest.raises(internal.EnvironmentNotReadyError, match="HOST_MEMORY_PRESSURE_INVALID"):
        await internal.mac_readiness()


@pytest.mark.parametrize("failure", [TimeoutError(), asyncio.CancelledError()])
async def test_native_observer_failure_reaps_only_its_child(
    monkeypatch: pytest.MonkeyPatch, failure: BaseException
) -> None:
    process = SimpleNamespace(
        returncode=None, communicate=AsyncMock(side_effect=failure), kill=Mock(), wait=AsyncMock()
    )
    start = AsyncMock(return_value=process)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", start)
    with pytest.raises(type(failure)) as caught:
        await internal.read_host_command("top", "-l", "2")
    assert caught.value is failure
    process.kill.assert_called_once()
    process.wait.assert_awaited_once()
    assert start.call_args.kwargs["env"]["LC_ALL"] == "C"


async def test_native_command_failure_omits_stderr(monkeypatch: pytest.MonkeyPatch) -> None:
    process = SimpleNamespace(
        returncode=1, communicate=AsyncMock(return_value=(b"", b"PRIVATE_ERROR"))
    )
    monkeypatch.setattr(asyncio, "create_subprocess_exec", AsyncMock(return_value=process))
    with pytest.raises(internal.EnvironmentNotReadyError) as caught:
        await internal.read_host_command("sysctl", "-n", "key")
    assert str(caught.value) == "HOST_SENSOR_COMMAND_FAILED"


async def test_cpu_mean_retains_brief_busy_samples(
    tmp_path: Path, host: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        internal,
        "mac_readiness",
        AsyncMock(
            side_effect=[
                {"cpu_idle_percent": idle, "memory_pressure_level": 1}
                for idle in [0, 0, 20, 20, 20, 40, 40]
            ]
        ),
    )
    fixture = AsyncMock(return_value=0)
    await internal.run_preflighted(
        tmp_path / "preflight.json", tmp_path, AsyncMock(return_value={"ready": True}), fixture
    )
    document = json.loads((tmp_path / "preflight.json").read_text())
    assert document["mean_cpu_idle_percent"] == 20.0
    assert [s["cpu_idle_percent"] for s in document["samples"]] == [0, 0, 20, 20, 20, 40, 40]
    assert fixture.await_count == 1
