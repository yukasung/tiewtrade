"""Analyze saved diagnostic telemetry; no workload or container mutations."""

import bisect
import json
import re
import statistics
import sys
from datetime import datetime
from itertools import pairwise
from pathlib import Path
from typing import Any


def rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def epoch(value: str) -> float:
    return datetime.fromisoformat(value).timestamp()


def counter(raw: str, name: str) -> int:
    match = re.search(r"^" + re.escape(name) + r":\s+(\d+)", raw, re.MULTILINE)
    if match is None:
        raise ValueError("missing VM counter: " + name)
    return int(match[1])


def distribution(values: list[float]) -> dict[str, float | int | None]:
    return {
        "count": len(values),
        "median": statistics.median(values) if values else None,
        "max": max(values) if values else None,
    }


def analyze(root: Path, seconds: float | None = None) -> dict[str, Any]:
    result = json.loads((root / "phase/result.json").read_text())
    start = epoch(result["T0"])
    if seconds is not None and seconds <= 0:
        raise ValueError("analysis duration must be positive")
    end = start + (
        min(seconds, result["measured_seconds"]) if seconds else result["measured_seconds"]
    )
    scheduling = rows(root / "metrics/diagnostic-scheduling.jsonl")
    vm = rows(root / "host-vm-stat.jsonl")
    callbacks = rows(root / "metrics/diagnostic-callbacks.jsonl")
    vm_times = [epoch(row["utc"]) for row in vm]
    sched_times = [row["at"] for row in scheduling]
    assert vm_times == sorted(vm_times) and sched_times == sorted(sched_times)
    intervals = []
    for left, right in pairwise(vm):
        lo, hi = epoch(left["utc"]), epoch(right["utc"])
        if lo < start or hi > end:
            continue
        page = re.search(r"page size of (\d+) bytes", left["vm_stat"])
        assert page is not None and hi > lo
        delta = {
            name: counter(right["vm_stat"], name) - counter(left["vm_stat"], name)
            for name in ("Compressions", "Decompressions", "Swapins", "Swapouts")
        }
        assert all(value >= 0 for value in delta.values())
        intervals.append(
            {
                "start": lo,
                "end": hi,
                "churn_mib_per_second": (delta["Compressions"] + delta["Decompressions"])
                * int(page[1])
                / (hi - lo)
                / 1024**2,
                "swapin_pages": delta["Swapins"],
                "swapout_pages": delta["Swapouts"],
                "gaps": 0,
            }
        )
    # Deduplicate repeated watchdog samples from one unchanged heartbeat.
    events: dict[float, dict[str, Any]] = {}
    for record in callbacks:
        if record["kind"] != "heartbeat_gap":
            continue
        key = round(record["at"] - record["wall_seconds"], 5)
        if key not in events or record["wall_seconds"] > events[key]["wall_seconds"]:
            events[key] = record
    phase_events = []
    for record in events.values():
        index = bisect.bisect_right(sched_times, record["at"]) - 1
        if index < 0:
            continue
        anchor = scheduling[index]
        at = epoch(anchor["utc"]) + record["at"] - anchor["at"]
        if not start <= at <= end:
            continue
        window = next(
            (window for window in intervals if window["start"] <= at < window["end"]), None
        )
        if window is not None:
            window["gaps"] += 1
        phase_events.append(
            {
                "utc_epoch": at,
                "wall_ms": record["wall_seconds"] * 1000,
                "thread_cpu_ms": record["thread_cpu_seconds"] * 1000,
                "top": record["stack"][0] if record["stack"] else None,
                "host_interval": window.copy() if window else None,
            }
        )
    gap_windows = [window for window in intervals if window["gaps"]]
    controls = [window for window in intervals if not window["gaps"]]
    over100 = [event for event in phase_events if event["wall_ms"] > 100]
    ranked = sorted(window["churn_mib_per_second"] for window in intervals)
    for event in over100:
        window = event["host_interval"]
        if window is not None:
            event["host_churn_percentile"] = (
                100 * bisect.bisect_right(ranked, window["churn_mib_per_second"]) / len(ranked)
            )
    phase_sched = [row for row in scheduling if start <= epoch(row["utc"]) <= end]
    quota = [dict(line.split() for line in row["cpu_stat"].splitlines()) for row in phase_sched]
    return {
        "diagnostic_only": True,
        "input": str(root),
        "phase_seconds": end - start,
        "deduplicated_phase_gaps": len(phase_events),
        "phase_gaps_over_100ms": over100,
        "host_intervals": len(intervals),
        "all_window_churn_mib_s": distribution([w["churn_mib_per_second"] for w in intervals]),
        "gap_window_churn_mib_s": distribution([w["churn_mib_per_second"] for w in gap_windows]),
        "control_window_churn_mib_s": distribution([w["churn_mib_per_second"] for w in controls]),
        "gap_windows_with_swapin": sum(w["swapin_pages"] > 0 for w in gap_windows),
        "control_windows_with_swapin": sum(w["swapin_pages"] > 0 for w in controls),
        "max_nr_throttled": max(int(row["nr_throttled"]) for row in quota),
        "max_throttled_usec": max(int(row["throttled_usec"]) for row in quota),
        "vm_steal_ticks_delta": int(phase_sched[-1]["vm_cpu_totals"].split()[8])
        - int(phase_sched[0]["vm_cpu_totals"].split()[8]),
        "limitations": [
            "Observational association does not establish causation.",
            "Host samples are about 2 seconds apart, VM samples about 1 second.",
            "Python stacks cannot resolve native uvloop waits.",
            "The original request-level API_RESOURCE_LIMIT did not recur.",
        ],
    }


if __name__ == "__main__":
    summary = analyze(Path(sys.argv[1]), float(sys.argv[3]) if len(sys.argv) == 4 else None)
    destination = Path(sys.argv[2])
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(summary, indent=2) + "\n")
