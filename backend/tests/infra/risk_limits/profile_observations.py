"""R30 acceptance receipts; observations never authorize financial operations."""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from pathlib import Path
from time import monotonic
from typing import Any

from tests.infra.execution_market.profile_workload import percentile

# F18-R32 only; standalone F15 and production feeds keep their own contracts.
SOURCE_HZ = 5
SOURCE_PERIOD_SECONDS = 1 / SOURCE_HZ


class PhaseJournal:
    """Persist transitions immediately, including on an interrupted run."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.phase = "setup"
        self.load_start: datetime | None = None
        self.load_end: datetime | None = None
        self.rows: list[dict[str, Any]] = []
        self.mark("setup")

    def mark(self, phase: str, **details: object) -> dict[str, Any]:
        self.phase = phase
        row = {
            "phase": phase,
            "monotonic": monotonic(),
            "at": datetime.now(UTC).isoformat(),
            **details,
        }
        self.rows.append(row)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row) + "\n")
        return row

    def begin_load(self, duration: int) -> dict[str, Any]:
        row = self.mark("load", duration_seconds=duration)
        self.load_start = datetime.fromisoformat(row["at"])
        self.load_end = self.load_start + timedelta(seconds=duration)
        return row

    def at(self, committed: datetime) -> str:
        # A recorder can observe an injection commit only after restart. Classify
        # by its durable time, never by the phase in which it was read back.
        boundaries = [(datetime.fromisoformat(row["at"]), row["phase"]) for row in self.rows]
        if self.load_end is not None:
            boundaries.append((self.load_end, "drain"))
        eligible = [point for point in boundaries if point[0] <= committed]
        return str(max(eligible, key=lambda point: point[0])[1]) if eligible else "setup"


def cadence_summary(
    path: Path,
    *,
    start: datetime,
    end: datetime,
    price_suspensions: list[tuple[datetime, datetime]],
    missing_commit_allowance: int = 0,
) -> dict[str, Any]:
    """Unique durable observations in [start,end); catch-up cannot fill nominal demand."""
    if missing_commit_allowance not in (0, 1):
        raise ValueError("only strict or R34 one-commit allowance supported")
    seconds = (end - start).total_seconds()
    if seconds <= 0:
        raise ValueError("positive nominal window required")
    intervals = sorted(
        (max(start, a), min(end, b)) for a, b in price_suspensions if a < end and b > start
    )
    merged: list[tuple[datetime, datetime]] = []
    for a, b in intervals:
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(b, merged[-1][1]))
        else:
            merged.append((a, b))
    exempt = sum((b - a).total_seconds() for a, b in merged)
    times: dict[str, list[datetime]] = {
        "BOOK:BTC/USDT": [],
        "PRICE:BTC/USDT": [],
        "PRICE:ETH/USDT": [],
    }
    seen: set[tuple[str, str]] = set()
    phases: Counter[str] = Counter()
    phase_times: dict[str, list[datetime]] = {}
    for line in path.read_text().splitlines():
        row = json.loads(line)
        key = f"{row['kind']}:{row['pair']}"
        identity = (key, str(row["identity"]))
        if identity in seen:
            continue
        seen.add(identity)
        phases[f"{row['phase']}:{key}"] += 1
        at = datetime.fromisoformat(row["committed_at"])
        phase_times.setdefault(f"{row['phase']}:{key}", []).append(at)
        if start <= at < end:
            times[key].append(at)
    channels = {}
    for key, values in times.items():
        values.sort()
        active = seconds - exempt if key.startswith("PRICE:") else seconds
        gaps = [(b - a).total_seconds() for a, b in pairwise(values)]
        gaps.sort()
        channels[key] = {
            "count": len(values),
            "expected": active * SOURCE_HZ,
            "minimum_count": max(0, active * SOURCE_HZ - missing_commit_allowance),
            "missing_commit_allowance": missing_commit_allowance,
            "active_seconds": active,
            "observed_hz": len(values) / active if active else None,
            "gap_seconds": {
                "max": max(gaps, default=None),
                "samples": len(gaps),
                "p50": percentile(gaps, 0.5) if gaps else None,
                "p95": percentile(gaps, 0.95) if gaps else None,
                "p99": percentile(gaps, 0.99) if gaps else None,
                "over_100ms": sum(gap > 0.1 for gap in gaps),
                "over_target_period": sum(gap > SOURCE_PERIOD_SECONDS for gap in gaps),
            },
            "passed": len(values) + missing_commit_allowance >= active * SOURCE_HZ,
        }
    phase_summary = {}
    for key, values in phase_times.items():
        values.sort()
        span = (values[-1] - values[0]).total_seconds()
        gaps = [(b - a).total_seconds() for a, b in pairwise(values)]
        phase_summary[key] = {
            "count": len(values),
            "first_commit": values[0].isoformat(),
            "last_commit": values[-1].isoformat(),
            "commit_span_seconds": span,
            "observed_span_hz": (len(values) - 1) / span if span else None,
            "max_gap_seconds": max(gaps, default=None),
            "acceptance_demand": "fixed nominal load only; see channels",
        }
    return {
        "target_hz": SOURCE_HZ,
        "target_period_seconds": SOURCE_PERIOD_SECONDS,
        "phase_summaries": phase_summary,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "channels": channels,
        "phase_counts": dict(phases),
        "price_exempt_seconds": exempt,
        "passed": all(row["passed"] for row in channels.values()),
    }


def live_progress(rows: list[dict[str, Any]], expected: set[str], captured: int) -> dict[str, Any]:
    """Evaluate one SQL snapshot, rejecting missing, duplicate or stale evidence."""
    inventory = [str(row["owner_id"]) for row in rows]
    complete = len(inventory) == len(expected) and set(inventory) == expected
    passed = (
        complete
        and bool(rows)
        and all(
            row["source_ready"]
            and row["availability"] == "READY"
            and captured <= row["input_id"] <= row["watermark"]
            and row["watermark"] - row["input_id"] <= 20
            for row in rows
        )
    )
    return {
        "passed": passed,
        "captured_watermark": captured,
        "inventory_complete": complete,
        "owners": rows,
        "observed_at": datetime.now(UTC).isoformat(),
        "monotonic": monotonic(),
    }


def busy_intervals(output: Path) -> dict[str, list[tuple[float, float]]]:
    """Use completed cycle/RESET receipts, including failed operations, as busy intervals."""
    result: dict[str, list[tuple[float, float]]] = {}
    for name, field in (
        ("cycle-timing.jsonl", "started_at"),
        ("scheduled-resets.jsonl", "offered_at"),
    ):
        path = output / name
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            row = json.loads(line)
            if "seconds" not in row:
                continue
            start = float(row[field])
            result.setdefault(row["owner"], []).append((start, start + float(row["seconds"])))
    return result


def overflow_timings(
    *,
    before: float,
    injection: float,
    recovery: float,
    recovered: float,
    finished: float,
) -> dict[str, float]:
    """Recovery includes restart/observation; excludes injection and verification."""
    if not before <= injection <= recovery <= recovered <= finished:
        raise ValueError("overflow phase timestamps are out of order")
    return {
        "injection_seconds": recovery - injection,
        "recovery_seconds": recovered - recovery,
        "verification_seconds": injection - before + finished - recovered,
        "total_seconds": finished - before,
    }
