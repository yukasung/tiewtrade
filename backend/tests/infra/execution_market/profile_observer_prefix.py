"""OBS-05 bounded W3 observation, never four-hour acceptance."""

from __future__ import annotations

import asyncio
import json
import math
from collections.abc import Awaitable, Callable
from pathlib import Path
from time import monotonic
from typing import Any

SECONDS = 2400
BUDGET_SECONDS = 3600


class PrefixCutoffError(RuntimeError):
    """Only the owned measurement timer may request this diagnostic stop."""


async def cutoff(started: float) -> None:
    if not math.isfinite(started):
        raise ValueError("invalid prefix measurement start")
    await asyncio.sleep(max(0, started + SECONDS - monotonic()))


def completion_errors(result: dict[str, Any], lease: dict[str, Any]) -> list[str]:
    errors = []
    if result.get("worker_failures"):
        errors.append("WorkerFailure")
    if result.get("stop_reason") != "PLANNED_PREFIX_CUTOFF":
        errors.append("CutoffNotProven")
    elapsed = result.get("elapsed_seconds")
    if (
        not isinstance(elapsed, (int, float))
        or isinstance(elapsed, bool)
        or not math.isfinite(elapsed)
        or elapsed < SECONDS
    ):
        errors.append("MeasurementIncomplete")
    faults = result.get("fault_observations", [])
    if len(faults) != 1 or not all(
        faults[0].get(k) == v
        for k, v in {
            "kind": "WORKER_RESTART",
            "status": "RECOVERED",
            "scheduled_offset_seconds": 1800,
        }.items()
    ):
        errors.append("FirstRestartNotProven")
    if result.get("pool_contract", {}).get("passed") is not True:
        errors.append("PoolEvidenceIncomplete")
    scheduled = lease.get("scheduled_observation") or {}
    if scheduled.get("status") != "RECORDED" or scheduled.get("expected_samples") != 40:
        errors.append("ScheduledEvidenceIncomplete")
    if lease.get("independent_failure_witness") is None:
        errors.append("IndependentWitnessMissing")
    natural = lease.get("fence_observation") or {}
    if natural.get("errors") or natural.get("task_joined") is not True:
        errors.append("NaturalEvidenceIncomplete")
    return errors


async def close_owned(
    tasks: list[tuple[str, asyncio.Task[Any] | None]],
    resources: list[tuple[str, Callable[[], Awaitable[None]]]],
    *,
    output: Path,
    save: Callable[[Path, Any], None],
    primary: BaseException | None,
) -> None:
    """Join everything, retain failures, and never accept a failed prefix cleanup."""
    errors: list[tuple[str, BaseException]] = []
    for name, task in tasks:
        if task is None:
            continue
        cancelled_here = not task.done() and task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        if task.cancelled():
            if not cancelled_here:
                errors.append((name, asyncio.CancelledError()))
        elif (error := task.exception()) is not None:
            errors.append((name, error))
    for name, operation in resources:
        try:
            await operation()
        except BaseException as error:
            errors.append((name, error))
    if not errors:
        return
    _save_cleanup_failure(output, save, errors)
    original = primary if primary is not None else errors[0][1]
    for name, cleanup_error in errors:
        if cleanup_error is not original:
            original.add_note(f"prefix cleanup {name} failed: {type(cleanup_error).__name__}")
    if primary is None:
        raise original


def _save_cleanup_failure(
    output: Path,
    save: Callable[[Path, Any], None],
    errors: list[tuple[str, BaseException]],
) -> None:
    """Publish failure evidence, retaining IO failures alongside cleanup failures."""
    receipt = {
        "status": "INCOMPLETE",
        "reason": "PREFIX_CLEANUP_FAILED",
        "errors": [{"phase": name, "error_type": type(error).__name__} for name, error in errors],
    }
    try:
        save(output / "prefix-cleanup-failure.json", receipt)
    except BaseException as error:
        errors.append(("cleanup_receipt", error))
    try:
        result_path = output / "result.json"
        if result_path.exists():
            result = json.loads(result_path.read_text())
            result.update(
                status="FAILED" if result.get("status") == "FAILED" else "INCOMPLETE",
                diagnostic_status="INCOMPLETE",
                cleanup_failure=receipt,
            )
            save(result_path, result)
    except BaseException as error:
        errors.append(("result_receipt", error))
