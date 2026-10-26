"""Fail-closed machine evaluator for the F-38 R2-C4 and R2-C6 gates."""

import argparse
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any, TypeGuard
from xml.etree import ElementTree

from tests.services.indicator_builder.profile_capacity_s5 import (
    EXPECTED_DATABASE_REVISION,
    RUNTIME_ROLES,
    evaluate_s5,
    s5_environment_valid,
)

WORKLOAD_SERIES = {
    ("BTC", timeframe) for timeframe in ("1m", "5m", "15m", "1h", "4h", "1d", "1w", "1M")
}
RUNTIME_SERIES = {
    (base, timeframe)
    for base in ("BTC", "ETH")
    for timeframe in ("1m", "5m", "15m", "1h", "4h", "1d", "1w", "1M")
}
SCOPE = {
    "supported_runtime_pairs": 2,
    "runtime_readiness_series": 16,
    "profile_pairs": 1,
    "profile_series": 8,
}
RSS_LIMIT = 128 * 1024**2


def bounded_number(value: object, upper: float) -> TypeGuard[int | float]:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and 0 <= value <= upper
    )


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def load_array(path: Path) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, list) or not all(isinstance(row, dict) for row in value):
        raise ValueError(f"{path} must contain an array of JSON objects")
    return value


def series_key(row: dict[str, Any]) -> tuple[str, str]:
    return str(row.get("base")), str(row.get("timeframe"))


def exact_workload(rows: list[dict[str, Any]]) -> bool:
    return (
        len(rows) == len(WORKLOAD_SERIES) and {series_key(row) for row in rows} == WORKLOAD_SERIES
    )


def scope_ok(result: dict[str, Any]) -> bool:
    return all(result.get(name) == expected for name, expected in SCOPE.items())


def junit_scheduler_gates(path: Path) -> dict[str, bool]:
    root = ElementTree.parse(path).getroot()
    cases = root.findall(".//testcase")
    green = bool(cases) and not root.findall(".//failure") and not root.findall(".//error")
    green = green and not root.findall(".//skipped")
    names = [f"{case.get('classname', '')}::{case.get('name', '')}" for case in cases]

    def count(fragment: str) -> int:
        return sum(fragment in name for name in names)

    return {
        "scheduler_junit_green": green,
        "R2-S1": count("profile_fair_scheduler::test_two_replicas_serve_stable_b") == 2,
        "R2-S2": count("test_mixed_failures_share_three_attempts_exact_backoff") == 1
        and count("test_post_failure_event_and_exact_cooldown_preserve_missed_episode") == 18,
        "R2-S3": count("test_round_advance_rollback_or_lost_ack") == 2
        and count("test_locked_unserved_job_prevents_advancing_round") == 1
        and count("test_idle_or_contended_scheduler_polls_once_then_waits") == 2
        and count("profile_fair_scheduler::test_crash_reap_and_coalesce") == 1,
        "R2-S4": count("test_concurrent_duplicate_cli_at_cooldown_boundary_is_durable") == 3
        and count("profile_fair_scheduler::test_expired_live_owner_requires_verified_reap") == 1,
    }


def result_series_ok(result: dict[str, Any], *, samples: int, probes: int) -> bool:
    rows = result.get("series")
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        return False
    return exact_workload(rows) and all(
        row.get("passed") is True
        and row.get("scheduled_samples") == samples
        and row.get("scheduled_probes") == probes
        for row in rows
    )


def r2_7_raw_checks(directory: Path) -> dict[str, bool]:
    """Recompute R2-7 from retained fixture, parity, query, and resource evidence."""
    summary = load_object(directory / "r2-7.json")
    fixture = load_object(directory / "exact-fixture-preparation.json")
    responses = load_array(directory / "cold-warm.json")
    metrics = load_array(directory / "cold-warm-metrics.json")
    audit = load_object(directory / "audit.json")
    generation = fixture.get("generation")
    digests = {row.get("response_rows_sha256") for row in responses}
    revisions = {row.get("dataset_revision") for row in responses}
    generations = {row.get("generation_id") for row in responses}
    return {
        "R2-7": summary.get("R2-7") == "PASSED",
        "R2-7_fixture": fixture.get("source_rows") == 525600
        and fixture.get("logical_slots") == 525600
        and fixture.get("released_retry_backoffs") == 0
        and isinstance(generation, dict)
        and generation.get("checkpoint_count") == 527,
        "R2-7_parity": len(responses) == 6
        and [row.get("run") for row in responses] == ["cold", *("warm" for _ in range(5))]
        and all(
            series_key(row) == ("BTC", "1m")
            and row.get("status") == 200
            and row.get("correct") is True
            and row.get("calculation_slots") == 525600
            and row.get("response_rows") == 1000
            for row in responses
        )
        and len(digests) == len(revisions) == len(generations) == 1
        and all(
            next(iter(values), None) not in {None, ""}
            for values in (digests, revisions, generations)
        ),
        "R2-7_response_budget": len(responses) == len(metrics) == 6
        and all(
            isinstance(response.get("elapsed_seconds"), (int, float))
            and 0 <= response["elapsed_seconds"] <= 30
            and isinstance(response.get("body_bytes"), int)
            and 0 < response["body_bytes"] <= 2 * 1024**2
            and isinstance(metric.get("seconds"), (int, float))
            and 0 <= metric["seconds"] <= 30
            and metric.get("body_bytes") == response["body_bytes"]
            for response, metric in zip(responses, metrics, strict=True)
        ),
        "R2-7_queries": len(metrics) == 6
        and all(
            row.get("status") == 200
            and isinstance(row.get("candle_queries"), int)
            and 0 <= row["candle_queries"] <= 8
            for row in metrics
        ),
        "R2-7_resources": len(metrics) == 6
        and all(
            isinstance(row.get("max_lag_seconds"), (int, float))
            and 0 <= row["max_lag_seconds"] <= 0.1
            and isinstance(row.get("rss_delta_upper_bytes"), int)
            and 0 <= row["rss_delta_upper_bytes"] <= RSS_LIMIT
            for row in metrics
        ),
        "R2-7_audit": isinstance(audit.get("database_timeout_retries"), int)
        and audit["database_timeout_retries"] >= 0,
    }


def normalized(value: Any) -> Any:
    """Match the harness JSON encoding before comparing recomputed evidence."""
    if isinstance(value, dict):
        return {key: normalized(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalized(item) for item in value]
    if hasattr(value, "isoformat"):
        return str(value)
    return value


def s5_raw_checks(directory: Path, c1_directory: Path) -> dict[str, bool]:
    """Recompute S5 from all retained raw inputs and compare the exact result."""
    saved = load_object(directory / "result.json")
    recomputed = evaluate_s5(
        load_array(directory / "trace.json"),
        load_array(directory / "observations.json"),
        load_array(directory / "probes.json"),
        load_array(directory / "worker-attempts.json"),
        load_array(directory / "historical-writes.json"),
    )
    audit = load_object(directory / "audit.json")
    environment = load_object(directory / "environment.json")
    c1_environment = load_object(c1_directory / "environment.json")
    retries = audit.get("database_timeout_retries")
    containers = environment.get("runtime_containers_created")
    derived = environment.get("derived_counts_before_runtime")
    image = environment.get("image")
    c1_image = c1_environment.get("image")
    prefix = environment.get("capacity_prefix")
    c1_prefix = c1_environment.get("capacity_prefix")
    postgres = environment.get("postgres_endpoint")
    c1_postgres = c1_environment.get("postgres_endpoint")
    redis = environment.get("redis_endpoint")
    c1_redis = c1_environment.get("redis_endpoint")
    api_cpuset = environment.get("api_cpuset")
    builder_cpuset = environment.get("builder_cpuset")
    return {
        "R2-S5": saved.get("R2-S5") == "PASSED",
        "R2-S5_raw": recomputed.get("R2-S5") == "PASSED",
        "R2-S5_exact": normalized(recomputed) == normalized(saved),
        "R2-S5_scope": scope_ok(saved),
        "R2-S5_audit": isinstance(retries, int) and retries >= 0,
        "R2-S5_environment": s5_environment_valid(environment, c1_environment),
        "R2-S5_image_match": isinstance(image, str) and bool(image) and image == c1_image,
        "R2-S5_fresh_fixture": derived
        == {
            "indicator_build_jobs": 0,
            "indicator_generations": 0,
            "indicator_checkpoints": 0,
        }
        and environment.get("source_fixture")
        == "fresh 16-series source; empty derived/jobs before runtime start"
        and environment.get("redis_dbsize_before_runtime") == 0
        and environment.get("redis_url_mode") == "plain-unauthenticated"
        and environment.get("database_revision") == EXPECTED_DATABASE_REVISION
        and environment.get("source_runtime_series") == 16,
        "R2-S5_runtime_shape": environment.get("historical_series") == "BTC/1m"
        and environment.get("append_only_runtime_series") == 15
        and scope_ok(environment),
        "R2-S5_runtime_instances": isinstance(containers, dict)
        and set(containers) == set(RUNTIME_ROLES)
        and all(
            isinstance(containers[role], str) and bool(containers[role]) for role in RUNTIME_ROLES
        )
        and len(set(containers.values())) == len(RUNTIME_ROLES),
        "R2-S5_isolation": isinstance(prefix, str)
        and bool(prefix)
        and prefix != c1_prefix
        and isinstance(postgres, str)
        and bool(postgres)
        and postgres != c1_postgres
        and isinstance(redis, str)
        and bool(redis)
        and redis != c1_redis,
        "R2-S5_cpu_isolation": isinstance(api_cpuset, str)
        and bool(api_cpuset)
        and isinstance(builder_cpuset, str)
        and bool(builder_cpuset)
        and api_cpuset != builder_cpuset,
    }


def fairness_ok(report: dict[str, Any]) -> bool:
    rows = report.get("series")
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        return False
    if not (
        exact_workload(rows)
        and report.get("claim_metadata_complete") is True
        and report.get("observer_cadence_complete") is True
        and report.get("resources_within_limits") is True
    ):
        return False
    for row in rows:
        claims = row.get("claims")
        if not isinstance(claims, list) or not claims:
            return False
        if row.get("pause_or_failure_samples") != []:
            return False
        unavailable = row.get("max_unavailable_sample_upper_seconds")
        if not bounded_number(unavailable, 600):
            return False
        episodes: dict[str, list[dict[str, Any]]] = {}
        for claim in claims:
            if not isinstance(claim, dict):
                return False
            eligible = claim.get("first_eligible_at")
            queue = claim.get("queue_wait_seconds")
            terminal = claim.get("claim_to_terminal_seconds")
            status = claim.get("status")
            if (
                not isinstance(eligible, str)
                or not bounded_number(queue, 600)
                or not bounded_number(terminal, 600)
                or queue + terminal > 600
                or status not in {"READY", "RELEASED"}
                or claim.get("deadline_missed_at") is not None
            ):
                return False
            if status == "READY" and (
                not isinstance(claim.get("published_at"), str)
                or not bounded_number(claim.get("claim_to_publish_seconds"), 600)
            ):
                return False
            episodes.setdefault(eligible, []).append(claim)
        if any(
            not any(
                claim["status"] == "READY"
                and claim["queue_wait_seconds"] + claim["claim_to_publish_seconds"] <= 600
                for claim in episode
            )
            for episode in episodes.values()
        ):
            return False
    return True


def raw_phase_ok(directory: Path, phase: str) -> dict[str, bool]:
    result = load_object(directory / "result.json")
    observations = load_array(directory / "observations.json")
    probes = load_array(directory / "probes.json")
    oracle = load_object(directory / "oracle.json")
    rejected = load_array(directory / "rejected.json")
    metrics = load_array(directory / "api-metrics.json")
    workers = load_array(directory / "worker-attempts.json")
    expected_gates = ("R2-C2", "R2-C5-steady") if phase == "steady" else ("R2-C3", "R2-C5-dirty")
    observation_scope = all(
        isinstance(sample.get("series"), list)
        and len(sample["series"]) == len(RUNTIME_SERIES)
        and {series_key(row) for row in sample["series"]} == RUNTIME_SERIES
        for sample in observations
    )
    probe_counts = Counter(series_key(row) for row in probes)
    accepted_references = {
        row["reference"]
        for row in probes
        if row.get("status") == 200 and isinstance(row.get("reference"), str)
    }
    oracle_ok = (
        set(oracle) == accepted_references
        and all(isinstance(key, str) and value is True for key, value in oracle.items())
        and all(
            row.get("status") != 200
            or (isinstance(row.get("reference"), str) and oracle.get(row["reference"]) is True)
            for row in probes
        )
    )
    correct_probe_counts = Counter(
        series_key(row)
        for row in probes
        if row.get("status") == 200
        and row.get("envelope_ok") is True
        and isinstance(row.get("reference"), str)
        and oracle.get(row["reference"]) is True
    )
    valid_sample_counts = Counter(
        series_key(row)
        for sample in observations
        for row in sample.get("series", [])
        if series_key(row) in WORKLOAD_SERIES and row.get("valid") is True
    )
    recovered = result.get("recovered_seconds")
    measured = result.get("measured_seconds")
    post_recovery_probes = [
        row
        for row in probes
        if isinstance(recovered, (int, float))
        and isinstance(row.get("started_seconds"), (int, float))
        and row["started_seconds"] >= recovered
    ]
    post_recovery_observations = [
        row
        for sample in observations
        if isinstance(recovered, (int, float))
        and isinstance(sample.get("seconds"), (int, float))
        and sample["seconds"] >= recovered
        for row in sample.get("series", [])
        if series_key(row) in WORKLOAD_SERIES
    ]
    reject_counts = Counter(
        (row.get("kind"), row.get("status"), row.get("detail")) for row in rejected
    )
    negative_metrics = [row for row in metrics if str(row.get("kind", "")).startswith("rejected-")]
    negative_metric_counts = Counter(
        (row.get("kind"), row.get("status")) for row in negative_metrics
    )
    raw_acceptance = (
        all(valid_sample_counts[key] == 360 for key in WORKLOAD_SERIES)
        and all(correct_probe_counts[key] == 60 for key in WORKLOAD_SERIES)
        if phase == "steady"
        else all(valid_sample_counts[key] >= 288 for key in WORKLOAD_SERIES)
        and all(correct_probe_counts[key] >= 48 for key in WORKLOAD_SERIES)
        and bool(post_recovery_probes)
        and all(
            row.get("status") == 200
            and row.get("envelope_ok") is True
            and isinstance(row.get("reference"), str)
            for row in post_recovery_probes
        )
        and bool(post_recovery_observations)
        and all(row.get("valid") is True for row in post_recovery_observations)
    )
    return {
        f"{phase}_gates": all(result.get(gate) == "PASSED" for gate in expected_gates),
        f"{phase}_scope": scope_ok(result),
        f"{phase}_duration": bounded_number(measured, float("inf")) and measured >= 3600,
        f"{phase}_no_failure": result.get("failure") is None,
        f"{phase}_series": result_series_ok(result, samples=360, probes=60),
        f"{phase}_observations": len(observations) == 360 and observation_scope,
        f"{phase}_probes": len(probes) == 480
        and set(probe_counts) == WORKLOAD_SERIES
        and all(probe_counts[key] == 60 for key in WORKLOAD_SERIES),
        f"{phase}_oracle": oracle_ok,
        f"{phase}_raw_acceptance": raw_acceptance,
        f"{phase}_rejected": len(rejected) == 2400
        and reject_counts
        == Counter(
            {
                ("busy", 503, "INDICATOR_BUSY"): 1200,
                ("rate", 429, "INDICATOR_RATE_LIMITED"): 1200,
            }
        ),
        f"{phase}_rejected_metrics": len(negative_metrics) == 2400
        and negative_metric_counts
        == Counter({("rejected-busy", 503): 1200, ("rejected-rate", 429): 1200})
        and all(row.get("candle_queries") == 0 for row in negative_metrics),
        f"{phase}_api_resources": bool(metrics)
        and all(
            bounded_number(row.get("max_lag_seconds"), 0.1)
            and bounded_number(row.get("rss_delta_upper_bytes"), RSS_LIMIT)
            for row in metrics
        ),
        f"{phase}_worker_resources": bool(workers)
        and all(
            bounded_number(row.get("seconds_including_acquire_cleanup"), 120)
            and bounded_number(row.get("rss_delta_upper_bytes"), RSS_LIMIT)
            for row in workers
        ),
        f"{phase}_fairness": fairness_ok(load_object(directory / "fairness-resources.json")),
        **(
            {"dirty_recovery": bounded_number(result.get("recovered_seconds"), 600)}
            if phase == "dirty"
            else {}
        ),
    }


def evaluate(
    c1: Path, steady: Path, dirty: Path, scheduler_junit: Path, s5: Path
) -> dict[str, Any]:
    checks: dict[str, bool] = {}
    try:
        c1_result = load_object(c1 / "result.json")
        checks.update(
            {
                "c1_gate": c1_result.get("R2-C1") == "PASSED",
                "c1_scope": scope_ok(c1_result),
                "c1_runtime_readiness": c1_result.get("runtime_readiness_passed") is True,
                "c1_series": result_series_ok(c1_result, samples=60, probes=10),
            }
        )
        checks.update(r2_7_raw_checks(c1))
        checks.update(junit_scheduler_gates(scheduler_junit))
        checks.update(s5_raw_checks(s5, c1))
        checks.update(raw_phase_ok(steady, "steady"))
        checks.update(raw_phase_ok(dirty, "dirty"))
    except (
        OSError,
        ValueError,
        TypeError,
        AttributeError,
        KeyError,
        json.JSONDecodeError,
        ElementTree.ParseError,
    ) as exc:
        return {
            "R2-C4": "FAILED",
            "R2-C6": "FAILED",
            "checks": checks,
            "failures": [f"EVALUATOR_INPUT_ERROR: {type(exc).__name__}: {exc}"],
        }

    c4_names = {
        "scheduler_junit_green",
        "R2-S1",
        "R2-S2",
        "R2-S3",
        "R2-S4",
        "R2-S5",
        "R2-S5_raw",
        "R2-S5_exact",
        "R2-S5_scope",
        "R2-S5_audit",
        "R2-S5_environment",
        "R2-S5_image_match",
        "R2-S5_fresh_fixture",
        "R2-S5_runtime_shape",
        "R2-S5_runtime_instances",
        "R2-S5_isolation",
        "R2-S5_cpu_isolation",
        "c1_gate",
        "c1_runtime_readiness",
        "c1_series",
        "steady_gates",
        "steady_duration",
        "steady_no_failure",
        "steady_series",
        "steady_observations",
        "steady_raw_acceptance",
        "dirty_gates",
        "dirty_duration",
        "dirty_no_failure",
        "dirty_series",
        "dirty_observations",
        "dirty_raw_acceptance",
        "dirty_recovery",
        "steady_fairness",
        "dirty_fairness",
    }
    c4_passed = all(checks.get(name) is True for name in c4_names)
    c6_passed = c4_passed and bool(checks) and all(checks.values())
    failures = sorted(name for name, passed in checks.items() if not passed)
    return {
        "R2-C4": "PASSED" if c4_passed else "FAILED",
        "R2-C6": "PASSED" if c6_passed else "FAILED",
        "checks": checks,
        "failures": failures,
        "inputs": {
            "c1": str(c1),
            "steady": str(steady),
            "dirty": str(dirty),
            "scheduler_junit": str(scheduler_junit),
            "s5": str(s5),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--c1", type=Path, required=True)
    parser.add_argument("--steady", type=Path, required=True)
    parser.add_argument("--dirty", type=Path, required=True)
    parser.add_argument("--scheduler-junit", type=Path, required=True)
    parser.add_argument("--s5", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(args.c1, args.steady, args.dirty, args.scheduler_junit, args.s5)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if result["R2-C4"] == result["R2-C6"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
