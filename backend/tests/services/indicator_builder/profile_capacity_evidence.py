"""Summarize retained capacity evidence without manufacturing missing gates."""

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from tests.services.indicator_builder.profile_capacity import SERIES, save


def moment(value: str) -> datetime:
    return datetime.fromisoformat(value)


def failure_occurs_in_phase(job: dict[str, Any], start: datetime, end: datetime) -> bool:
    """Exclude retained failures from before T0 while failing closed on missing timestamps."""
    deadline = job.get("deadline_missed_at")
    failed = job.get("failed_at")
    deadline_in_phase = deadline is not None and start <= moment(deadline) <= end
    if not str(job.get("status", "")).startswith("FAILED"):
        return deadline_in_phase
    return failed is None or start <= moment(failed) <= end or deadline_in_phase


def report(phase: Path, metrics: Path) -> None:
    result = json.loads((phase / "result.json").read_text(encoding="utf-8-sig"))
    start = moment(result["T0"])
    duration = result.get("measured_seconds", 600)
    end = start + timedelta(seconds=duration)
    samples = json.loads((phase / "observations.json").read_text())
    trace = (
        json.loads((phase / "trace.json").read_text())
        if (phase / "trace.json").exists()
        else [json.loads(line) for line in (phase / "metadata.jsonl").read_text().splitlines()]
    )
    if (phase / "drained-metadata.json").exists():
        drained = json.loads((phase / "drained-metadata.json").read_text())
        trace.append(drained | {"seconds": duration + 140})
    generations = {g["id"]: g for sample in trace for g in sample["generations"]}
    attempts = [
        row
        for line in (metrics / "worker-attempts.jsonl").read_text().splitlines()
        if (row := json.loads(line))
        and moment(row["claimed_at"]) <= end
        and moment(row["finished_at"]) >= start
    ]
    api = [
        row
        for line in (metrics / "api-metrics.jsonl").read_text().splitlines()
        if (row := json.loads(line)) and start <= moment(row["recorded_at"]) <= end
    ]
    rows: list[dict[str, Any]] = []
    for base, tf in SERIES:

        def same(row: dict[str, Any], symbol: str = base, timeframe: str = tf.value) -> bool:
            return bool(row["base"] == symbol and row["timeframe"] == timeframe)

        claims = []
        for attempt in filter(same, attempts):
            claimed = moment(attempt["claimed_at"])
            candidates = [
                (sample["seconds"], job)
                for sample in trace
                for job in sample["jobs"]
                if same(job)
                and job["first_eligible_at"] is not None
                and moment(job["first_eligible_at"]) <= claimed
                and start + timedelta(seconds=sample["seconds"]) >= claimed
            ]
            job = min(candidates, key=lambda entry: entry[0])[1] if candidates else None
            generation = generations.get(attempt["generation_id"])
            published = generation.get("prepared_at") if generation else None
            claims.append(
                attempt
                | {
                    "first_eligible_at": job["first_eligible_at"] if job else None,
                    "availability_deadline": job["availability_deadline"] if job else None,
                    "queue_wait_seconds": (
                        claimed - moment(job["first_eligible_at"])
                    ).total_seconds()
                    if job
                    else None,
                    "published_at": published,
                    "terminal_at": attempt.get("finished_at"),
                    "claim_to_terminal_seconds": (
                        moment(attempt["finished_at"]) - claimed
                    ).total_seconds()
                    if attempt.get("finished_at")
                    else None,
                    "claim_to_publish_seconds": (moment(published) - claimed).total_seconds()
                    if published
                    else None,
                    "deadline_missed_at": job["deadline_missed_at"] if job else None,
                    "deadline_miss_before_phase": bool(
                        job
                        and job["deadline_missed_at"]
                        and moment(job["deadline_missed_at"]) < start
                    ),
                }
            )
        observed = [
            (sample["seconds"], row) for sample in samples for row in sample["series"] if same(row)
        ]
        unavailable: float | None = None
        maximum = 0.0
        for seconds, row in observed:
            if not row["valid"] and unavailable is None:
                unavailable = max(0, seconds - 10)
            elif row["valid"] and unavailable is not None:
                maximum = max(maximum, seconds - unavailable)
                unavailable = None
        if unavailable is not None:
            maximum = max(maximum, duration - unavailable)
        rows.append(
            {
                "base": base,
                "timeframe": tf.value,
                "claims": claims,
                "dispatch_rounds": sorted({claim["dispatch_round"] for claim in claims}),
                "max_head_age_seconds": max(
                    (row["age_seconds"] for _, row in observed if row["age_seconds"] is not None),
                    default=None,
                ),
                "max_unavailable_sample_upper_seconds": maximum,
                "pause_or_failure_samples": [
                    {
                        "seconds": sample["seconds"],
                        **job,
                        "deadline_miss_before_phase": bool(
                            job["deadline_missed_at"] and moment(job["deadline_missed_at"]) < start
                        ),
                    }
                    for sample in trace
                    for job in sample["jobs"]
                    if same(job) and failure_occurs_in_phase(job, start, end)
                ],
            }
        )
    complete = len(rows) == len(SERIES) and all(
        row["claims"]
        and all(
            claim["first_eligible_at"]
            and claim["terminal_at"]
            and claim["status"] in {"READY", "RELEASED"}
            and (claim["status"] != "READY" or claim["published_at"])
            for claim in row["claims"]
        )
        and all(
            any(
                claim["status"] == "READY"
                and claim["first_eligible_at"] == episode
                and claim["published_at"]
                for claim in row["claims"]
            )
            for episode in {claim["first_eligible_at"] for claim in row["claims"]}
        )
        for row in rows
    )
    save(
        phase / "fairness-resources.json",
        {
            "series": rows,
            "claim_metadata_complete": complete,
            "observer_cadence_complete": len(samples) == (60 if "R2-C1" in result else 360)
            and all(abs(sample["seconds"] - i * 10) < 10 for i, sample in enumerate(samples)),
            "max_observer_schedule_skew_seconds": max(
                (abs(sample["seconds"] - i * 10) for i, sample in enumerate(samples)),
                default=None,
            ),
            "api_requests": len(api),
            "max_api_lag_seconds": max((m["max_lag_seconds"] for m in api), default=None),
            "max_api_rss_upper_bytes": max((m["rss_delta_upper_bytes"] for m in api), default=None),
            "worker_attempts": len(attempts),
            "max_worker_seconds_including_cleanup": max(
                (m["seconds_including_acquire_cleanup"] for m in attempts), default=None
            ),
            "max_worker_rss_upper_bytes": max(
                (m["rss_delta_upper_bytes"] for m in attempts), default=None
            ),
            "resources_within_limits": bool(api)
            and bool(attempts)
            and all(
                m["max_lag_seconds"] <= 0.1 and m["rss_delta_upper_bytes"] <= 128 * 1024**2
                for m in api
            )
            and all(
                m["seconds_including_acquire_cleanup"] <= 120
                and m["rss_delta_upper_bytes"] <= 128 * 1024**2
                for m in attempts
            ),
            "note": "10s observer resolution; claim/publication use DB timestamps. "
            "This report does not substitute for R2-S1..S5 or approve R2-C4/C6.",
        },
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", type=Path, required=True)
    parser.add_argument("--metrics", type=Path, required=True)
    args = parser.parse_args()
    report(args.phase, args.metrics)
