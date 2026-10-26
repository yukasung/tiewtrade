import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from tests.services.indicator_builder.profile_capacity_gates import evaluate
from tests.services.indicator_builder.profile_capacity_s5 import S5_SERIES, evaluate_s5

TIMEFRAMES = ("1m", "5m", "15m", "1h", "4h", "1d", "1w", "1M")


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, default=str), encoding="utf-8")


def scope() -> dict[str, int]:
    return {
        "supported_runtime_pairs": 2,
        "runtime_readiness_series": 16,
        "profile_pairs": 1,
        "profile_series": 8,
    }


def result_rows(samples: int, probes: int) -> list[dict[str, object]]:
    return [
        {
            "base": "BTC",
            "timeframe": timeframe,
            "passed": True,
            "scheduled_samples": samples,
            "scheduled_probes": probes,
        }
        for timeframe in TIMEFRAMES
    ]


def fairness() -> dict[str, object]:
    return {
        "claim_metadata_complete": True,
        "observer_cadence_complete": True,
        "resources_within_limits": True,
        "series": [
            {
                "base": "BTC",
                "timeframe": timeframe,
                "claims": [
                    {
                        "status": "READY",
                        "first_eligible_at": "2026-10-25T18:00:00+00:00",
                        "queue_wait_seconds": 1,
                        "terminal_at": "2026-10-25T18:00:21+00:00",
                        "claim_to_terminal_seconds": 20,
                        "published_at": "2026-10-25T18:00:20+00:00",
                        "claim_to_publish_seconds": 20,
                        "deadline_missed_at": None,
                    }
                ],
                "max_unavailable_sample_upper_seconds": 30,
                "pause_or_failure_samples": [],
            }
            for timeframe in TIMEFRAMES
        ],
    }


def scheduler_xml(path: Path) -> None:
    cases = [
        ("profile_fair_scheduler", "test_two_replicas_serve_stable_b[False]"),
        ("profile_fair_scheduler", "test_two_replicas_serve_stable_b[True]"),
        ("test_scheduler_validation", "test_mixed_failures_share_three_attempts_exact_backoff"),
        *[
            (
                "test_scheduler_validation",
                f"test_post_failure_event_and_exact_cooldown_preserve_missed_episode[{i}]",
            )
            for i in range(18)
        ],
        *[
            ("test_scheduler_validation", f"test_round_advance_rollback_or_lost_ack[{i}]")
            for i in range(2)
        ],
        ("test_scheduler_validation", "test_locked_unserved_job_prevents_advancing_round"),
        *[
            (
                "test_scheduler_validation",
                f"test_idle_or_contended_scheduler_polls_once_then_waits[{i}]",
            )
            for i in range(2)
        ],
        ("profile_fair_scheduler", "test_crash_reap_and_coalesce"),
        *[
            (
                "test_scheduler_validation",
                f"test_concurrent_duplicate_cli_at_cooldown_boundary_is_durable[{i}]",
            )
            for i in range(3)
        ],
        ("profile_fair_scheduler", "test_expired_live_owner_requires_verified_reap"),
    ]
    body = "".join(f'<testcase classname="{module}" name="{name}" />' for module, name in cases)
    path.write_text(f"<testsuites><testsuite>{body}</testsuite></testsuites>", encoding="utf-8")


def phase(directory: Path, kind: str) -> None:
    directory.mkdir()
    gates = (
        {"R2-C2": "PASSED", "R2-C5-steady": "PASSED"}
        if kind == "steady"
        else {"R2-C3": "PASSED", "R2-C5-dirty": "PASSED", "recovered_seconds": 590}
    )
    write(
        directory / "result.json",
        gates
        | scope()
        | {
            "measured_seconds": 3600,
            "failure": None,
            "series": result_rows(360, 60),
        },
    )
    series = [{"base": "BTC", "timeframe": timeframe, "valid": True} for timeframe in TIMEFRAMES]
    runtime_series = [
        {"base": base, "timeframe": timeframe, "valid": True}
        for base in ("BTC", "ETH")
        for timeframe in TIMEFRAMES
    ]
    write(
        directory / "observations.json",
        [{"seconds": index * 10, "series": runtime_series} for index in range(360)],
    )
    write(
        directory / "probes.json",
        [
            {
                "base": row["base"],
                "timeframe": row["timeframe"],
                "status": 200,
                "envelope_ok": True,
                "reference": "digest",
                "started_seconds": round_index * 60,
            }
            for round_index in range(60)
            for row in series
        ],
    )
    write(directory / "oracle.json", {"digest": True})
    write(
        directory / "rejected.json",
        [{"kind": "busy", "status": 503, "detail": "INDICATOR_BUSY"}] * 1200
        + [{"kind": "rate", "status": 429, "detail": "INDICATOR_RATE_LIMITED"}] * 1200,
    )
    write(
        directory / "api-metrics.json",
        [
            {
                "kind": "rejected-busy" if index < 1200 else "rejected-rate",
                "status": 503 if index < 1200 else 429,
                "candle_queries": 0,
                "max_lag_seconds": 0.01,
                "rss_delta_upper_bytes": 1,
            }
            for index in range(2400)
        ],
    )
    write(
        directory / "worker-attempts.json",
        [{"seconds_including_acquire_cleanup": 20, "rss_delta_upper_bytes": 1}],
    )
    write(directory / "fairness-resources.json", fairness())


def s5_fixture(directory: Path) -> None:
    directory.mkdir()
    started = datetime(2026, 10, 26, 1, 0, tzinfo=UTC)
    jobs = [
        {
            "base": base,
            "timeframe": timeframe,
            "first_eligible_at": started.isoformat(),
            "availability_deadline": (started + timedelta(seconds=600)).isoformat(),
            "deadline_missed_at": None,
        }
        for base, timeframe in S5_SERIES
    ]
    recovered = [
        {"base": base, "timeframe": timeframe, "valid": True} for base, timeframe in S5_SERIES
    ]
    recovering = [
        row | {"valid": (row["base"], row["timeframe"]) != ("BTC", "1m")} for row in recovered
    ]
    correct = [
        {"base": row["base"], "timeframe": row["timeframe"], "status": 200, "correct": True}
        for row in recovered
    ]
    recovering_probes = [
        row
        | {
            "status": 503 if (row["base"], row["timeframe"]) == ("BTC", "1m") else 200,
            "correct": (row["base"], row["timeframe"]) != ("BTC", "1m"),
        }
        for row in correct
    ]
    trace = [{"recorded_at": started + timedelta(seconds=1), "jobs": jobs}]
    observations = [
        {"recorded_at": started + timedelta(seconds=100), "series": recovering},
        {"recorded_at": started + timedelta(seconds=300), "series": recovered},
    ]
    probes = [
        {"recorded_at": started + timedelta(seconds=200), "series": recovering_probes},
        {"recorded_at": started + timedelta(seconds=360), "series": correct},
    ]
    attempts = [
        {
            "base": base,
            "timeframe": timeframe,
            "status": "READY",
            "owner": f"worker-{index % 2}",
            "seconds_including_acquire_cleanup": 30,
            "rss_delta_upper_bytes": 1024,
        }
        for index, (base, timeframe) in enumerate(S5_SERIES)
    ]
    writes = [
        *({"committed_at": started + timedelta(seconds=offset)} for offset in range(-1, 360, 5)),
        {"churn_stopped_at": started + timedelta(seconds=361)},
    ]
    result = evaluate_s5(trace, observations, probes, attempts, writes)
    write(
        directory / "environment.json",
        {
            "image": "sha256:" + "a" * 64,
            "capacity_prefix": "tiewtrade-f38-s5-test",
            "postgres_endpoint": "127.0.0.1:55470/tiewtrade",
            "redis_endpoint": "127.0.0.1:56420/0",
            "redis_dbsize_before_runtime": 0,
            "redis_url_mode": "plain-unauthenticated",
            "database_revision": "0038",
            "api_cpuset": "6-7",
            "builder_cpuset": "4-5",
            "runtime_containers_created": {
                "api": "api-container-id",
                "builder": "builder-container-id",
                "builder-s5-peer": "peer-container-id",
            },
            "source_fixture": "fresh 16-series source; empty derived/jobs before runtime start",
            "source_runtime_series": 16,
            "derived_counts_before_runtime": {
                "indicator_build_jobs": 0,
                "indicator_generations": 0,
                "indicator_checkpoints": 0,
            },
            "historical_series": "BTC/1m",
            "append_only_runtime_series": 15,
        }
        | scope(),
    )
    for name, value in (
        ("trace.json", trace),
        ("observations.json", observations),
        ("probes.json", probes),
        ("worker-attempts.json", attempts),
        ("historical-writes.json", writes),
        ("audit.json", {"database_timeout_retries": 0}),
        ("result.json", result),
    ):
        write(directory / name, value)


def accepted_fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    c1 = tmp_path / "c1"
    c1.mkdir()
    write(
        c1 / "result.json",
        {
            "R2-C1": "PASSED",
            "runtime_readiness_passed": True,
            "series": result_rows(60, 10),
        }
        | scope(),
    )
    write(
        c1 / "environment.json",
        {
            "image": "sha256:" + "a" * 64,
            "capacity_prefix": "tiewtrade-f38-c1-test",
            "postgres_endpoint": "127.0.0.1:55457/tiewtrade",
            "redis_endpoint": "127.0.0.1:56402/0",
        },
    )
    write(c1 / "r2-7.json", {"R2-7": "PASSED"})
    write(
        c1 / "exact-fixture-preparation.json",
        {
            "source_rows": 525600,
            "logical_slots": 525600,
            "released_retry_backoffs": 0,
            "generation": {"checkpoint_count": 527},
        },
    )
    write(
        c1 / "cold-warm.json",
        [
            {
                "base": "BTC",
                "timeframe": "1m",
                "run": "cold" if index == 0 else "warm",
                "status": 200,
                "correct": True,
                "calculation_slots": 525600,
                "response_rows": 1000,
                "elapsed_seconds": 0.2,
                "body_bytes": 458801,
                "response_rows_sha256": "rows-digest",
                "dataset_revision": "dataset-revision",
                "generation_id": "generation-id",
            }
            for index in range(6)
        ],
    )
    write(
        c1 / "cold-warm-metrics.json",
        [
            {
                "status": 200,
                "candle_queries": 8,
                "seconds": 0.19,
                "body_bytes": 458801,
                "max_lag_seconds": 0.01,
                "rss_delta_upper_bytes": 1,
            }
            for _ in range(6)
        ],
    )
    write(c1 / "audit.json", {"database_timeout_retries": 0})
    steady = tmp_path / "steady"
    dirty = tmp_path / "dirty"
    phase(steady, "steady")
    phase(dirty, "dirty")
    junit = tmp_path / "scheduler.xml"
    scheduler_xml(junit)
    s5 = tmp_path / "s5"
    s5_fixture(s5)
    return c1, steady, dirty, junit, s5


def test_evaluator_passes_only_complete_machine_evidence(tmp_path: Path) -> None:
    result = evaluate(*accepted_fixture(tmp_path))
    assert result["R2-C4"] == "PASSED"
    assert result["R2-C6"] == "PASSED"
    assert result["failures"] == []


def test_evaluator_fails_both_gates_when_fairness_starves(tmp_path: Path) -> None:
    c1, steady, dirty, junit, s5 = accepted_fixture(tmp_path)
    report = json.loads((dirty / "fairness-resources.json").read_text())
    report["series"][0]["claims"][0]["queue_wait_seconds"] = 581
    write(dirty / "fairness-resources.json", report)

    result = evaluate(c1, steady, dirty, junit, s5)

    assert result["R2-C4"] == "FAILED"
    assert result["R2-C6"] == "FAILED"
    assert "dirty_fairness" in result["failures"]


def test_evaluator_accepts_released_attempt_followed_by_ready_in_same_episode(
    tmp_path: Path,
) -> None:
    c1, steady, dirty, junit, s5 = accepted_fixture(tmp_path)
    for directory in (steady, dirty):
        report = json.loads((directory / "fairness-resources.json").read_text())
        first = report["series"][0]["claims"][0]
        first["status"] = "RELEASED"
        first["published_at"] = None
        first["claim_to_publish_seconds"] = None
        first["claim_to_terminal_seconds"] = 20
        retry = first | {
            "status": "READY",
            "queue_wait_seconds": 30,
            "terminal_at": "2026-10-25T18:00:51+00:00",
            "claim_to_terminal_seconds": 20,
            "published_at": "2026-10-25T18:00:50+00:00",
            "claim_to_publish_seconds": 20,
        }
        report["series"][0]["claims"].append(retry)
        write(directory / "fairness-resources.json", report)

    result = evaluate(c1, steady, dirty, junit, s5)

    assert result["R2-C4"] == "PASSED"
    assert result["R2-C6"] == "PASSED"


def test_evaluator_fails_closed_on_missing_or_invalid_input(tmp_path: Path) -> None:
    c1, steady, dirty, junit, s5 = accepted_fixture(tmp_path)
    (steady / "rejected.json").unlink()

    result = evaluate(c1, steady, dirty, junit, s5)

    assert result["R2-C4"] == "FAILED"
    assert result["R2-C6"] == "FAILED"
    assert result["failures"][0].startswith("EVALUATOR_INPUT_ERROR")


def test_c6_fails_without_changing_c4_when_resource_bound_fails(tmp_path: Path) -> None:
    c1, steady, dirty, junit, s5 = accepted_fixture(tmp_path)
    metrics = json.loads((steady / "api-metrics.json").read_text())
    metrics[0]["max_lag_seconds"] = 0.100001
    write(steady / "api-metrics.json", metrics)

    result = evaluate(c1, steady, dirty, junit, s5)

    assert result["R2-C4"] == "PASSED"
    assert result["R2-C6"] == "FAILED"
    assert "steady_api_resources" in result["failures"]


@pytest.mark.parametrize(
    ("artifact", "field", "value", "failed_check"),
    [
        ("cold-warm-metrics.json", "candle_queries", 9, "R2-7_queries"),
        ("cold-warm-metrics.json", "max_lag_seconds", 0.100001, "R2-7_resources"),
        ("cold-warm.json", "response_rows_sha256", "different", "R2-7_parity"),
    ],
)
def test_c6_recomputes_raw_r2_7_evidence(
    tmp_path: Path, artifact: str, field: str, value: object, failed_check: str
) -> None:
    c1, steady, dirty, junit, s5 = accepted_fixture(tmp_path)
    rows = json.loads((c1 / artifact).read_text())
    rows[0][field] = value
    write(c1 / artifact, rows)

    result = evaluate(c1, steady, dirty, junit, s5)

    assert result["R2-C4"] == "PASSED"
    assert result["R2-C6"] == "FAILED"
    assert failed_check in result["failures"]


@pytest.mark.parametrize("detail", [None, "WRONG_ERROR"])
def test_c6_requires_rejected_error_detail_contract(tmp_path: Path, detail: object) -> None:
    c1, steady, dirty, junit, s5 = accepted_fixture(tmp_path)
    rejected = json.loads((steady / "rejected.json").read_text())
    rejected[0]["detail"] = detail
    write(steady / "rejected.json", rejected)

    result = evaluate(c1, steady, dirty, junit, s5)

    assert result["R2-C4"] == "PASSED"
    assert result["R2-C6"] == "FAILED"
    assert "steady_rejected" in result["failures"]


@pytest.mark.parametrize(
    ("artifact", "field", "value"),
    [
        ("cold-warm.json", "elapsed_seconds", 30.000001),
        ("cold-warm.json", "body_bytes", 2 * 1024**2 + 1),
        ("cold-warm-metrics.json", "seconds", 30.000001),
        ("cold-warm-metrics.json", "body_bytes", 458802),
    ],
)
def test_c6_enforces_r2_7_response_budget_and_metric_consistency(
    tmp_path: Path, artifact: str, field: str, value: object
) -> None:
    c1, steady, dirty, junit, s5 = accepted_fixture(tmp_path)
    rows = json.loads((c1 / artifact).read_text())
    rows[0][field] = value
    write(c1 / artifact, rows)

    result = evaluate(c1, steady, dirty, junit, s5)

    assert result["R2-C4"] == "PASSED"
    assert result["R2-C6"] == "FAILED"
    assert "R2-7_response_budget" in result["failures"]


def test_c4_fails_closed_when_s5_raw_evidence_recomputes_failed(tmp_path: Path) -> None:
    c1, steady, dirty, junit, s5 = accepted_fixture(tmp_path)
    observations = json.loads((s5 / "observations.json").read_text())
    observations[-1]["series"][0]["valid"] = False
    write(s5 / "observations.json", observations)

    result = evaluate(c1, steady, dirty, junit, s5)

    assert result["R2-C4"] == "FAILED"
    assert result["R2-C6"] == "FAILED"
    assert "R2-S5_raw" in result["failures"]
    assert "R2-S5_exact" in result["failures"]


def test_c4_fails_closed_when_saved_s5_differs_from_recomputed(tmp_path: Path) -> None:
    c1, steady, dirty, junit, s5 = accepted_fixture(tmp_path)
    saved = json.loads((s5 / "result.json").read_text())
    saved["historical_writes"] += 1
    write(s5 / "result.json", saved)

    result = evaluate(c1, steady, dirty, junit, s5)

    assert result["R2-C4"] == "FAILED"
    assert result["R2-C6"] == "FAILED"
    assert result["checks"]["R2-S5"] is True
    assert "R2-S5_exact" in result["failures"]


def test_c4_requires_s5_scope_and_nonnegative_audit_count(tmp_path: Path) -> None:
    c1, steady, dirty, junit, s5 = accepted_fixture(tmp_path)
    saved = json.loads((s5 / "result.json").read_text())
    saved["profile_series"] = 7
    write(s5 / "result.json", saved)
    write(s5 / "audit.json", {"database_timeout_retries": -1})

    result = evaluate(c1, steady, dirty, junit, s5)

    assert result["R2-C4"] == "FAILED"
    assert result["R2-C6"] == "FAILED"
    assert "R2-S5_scope" in result["failures"]
    assert "R2-S5_audit" in result["failures"]


def test_c4_fails_closed_when_s5_raw_artifact_is_missing(tmp_path: Path) -> None:
    c1, steady, dirty, junit, s5 = accepted_fixture(tmp_path)
    (s5 / "historical-writes.json").unlink()

    result = evaluate(c1, steady, dirty, junit, s5)

    assert result["R2-C4"] == "FAILED"
    assert result["R2-C6"] == "FAILED"
    assert result["failures"][0].startswith("EVALUATOR_INPUT_ERROR")


@pytest.mark.parametrize(
    ("field", "value", "check"),
    [
        ("image", "sha256:different", "R2-S5_image_match"),
        ("redis_dbsize_before_runtime", 1, "R2-S5_fresh_fixture"),
        ("database_revision", "0030", "R2-S5_fresh_fixture"),
        ("append_only_runtime_series", 14, "R2-S5_runtime_shape"),
        (
            "runtime_containers_created",
            {"api": "same", "builder": "same", "builder-s5-peer": "peer"},
            "R2-S5_runtime_instances",
        ),
        ("capacity_prefix", "tiewtrade-f38-c1-test", "R2-S5_isolation"),
        ("builder_cpuset", "6-7", "R2-S5_cpu_isolation"),
    ],
)
def test_c4_requires_complete_s5_environment_provenance(
    tmp_path: Path, field: str, value: object, check: str
) -> None:
    c1, steady, dirty, junit, s5 = accepted_fixture(tmp_path)
    environment = json.loads((s5 / "environment.json").read_text())
    environment[field] = value
    write(s5 / "environment.json", environment)

    result = evaluate(c1, steady, dirty, junit, s5)

    assert result["R2-C4"] == "FAILED"
    assert result["R2-C6"] == "FAILED"
    assert check in result["failures"]


@pytest.mark.parametrize("mutation", ["false", "missing"])
def test_c6_requires_true_oracle_for_every_accepted_probe_reference(
    tmp_path: Path, mutation: str
) -> None:
    c1, steady, dirty, junit, s5 = accepted_fixture(tmp_path)
    oracle = json.loads((steady / "oracle.json").read_text())
    if mutation == "false":
        oracle["digest"] = False
    else:
        del oracle["digest"]
    write(steady / "oracle.json", oracle)

    result = evaluate(c1, steady, dirty, junit, s5)

    assert result["R2-C4"] == "FAILED"
    assert result["R2-C6"] == "FAILED"
    assert "steady_oracle" in result["failures"]
    assert "steady_raw_acceptance" in result["failures"]


@pytest.mark.parametrize("extra", [True, "not-a-boolean"])
def test_c6_rejects_extra_or_invalid_oracle_shape(tmp_path: Path, extra: object) -> None:
    c1, steady, dirty, junit, s5 = accepted_fixture(tmp_path)
    oracle = json.loads((steady / "oracle.json").read_text())
    oracle["unused-reference"] = extra
    write(steady / "oracle.json", oracle)

    result = evaluate(c1, steady, dirty, junit, s5)

    assert result["R2-C4"] == "PASSED"
    assert result["R2-C6"] == "FAILED"
    assert "steady_oracle" in result["failures"]


@pytest.mark.parametrize(
    ("artifact", "field", "value", "failed_check"),
    [
        ("api-metrics.json", "max_lag_seconds", -0.001, "steady_api_resources"),
        ("api-metrics.json", "rss_delta_upper_bytes", -1, "steady_api_resources"),
        (
            "worker-attempts.json",
            "seconds_including_acquire_cleanup",
            -0.001,
            "steady_worker_resources",
        ),
        ("worker-attempts.json", "rss_delta_upper_bytes", -1, "steady_worker_resources"),
    ],
)
def test_c6_rejects_negative_resource_measurement(
    tmp_path: Path, artifact: str, field: str, value: object, failed_check: str
) -> None:
    c1, steady, dirty, junit, s5 = accepted_fixture(tmp_path)
    rows = json.loads((steady / artifact).read_text())
    rows[0][field] = value
    write(steady / artifact, rows)

    result = evaluate(c1, steady, dirty, junit, s5)

    assert result["R2-C4"] == "PASSED"
    assert result["R2-C6"] == "FAILED"
    assert failed_check in result["failures"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("max_unavailable_sample_upper_seconds", -1),
        ("claim_to_publish_seconds", -1),
        ("queue_wait_seconds", float("nan")),
    ],
)
def test_c4_rejects_invalid_fairness_timing(tmp_path: Path, field: str, value: object) -> None:
    c1, steady, dirty, junit, s5 = accepted_fixture(tmp_path)
    report = json.loads((steady / "fairness-resources.json").read_text())
    if field == "max_unavailable_sample_upper_seconds":
        report["series"][0][field] = value
    else:
        report["series"][0]["claims"][0][field] = value
    write(steady / "fairness-resources.json", report)

    result = evaluate(c1, steady, dirty, junit, s5)

    assert result["R2-C4"] == "FAILED"
    assert result["R2-C6"] == "FAILED"
    assert "steady_fairness" in result["failures"]


def test_c6_rejects_negative_dirty_recovery(tmp_path: Path) -> None:
    c1, steady, dirty, junit, s5 = accepted_fixture(tmp_path)
    result_file = json.loads((dirty / "result.json").read_text())
    result_file["recovered_seconds"] = -1
    write(dirty / "result.json", result_file)

    result = evaluate(c1, steady, dirty, junit, s5)

    assert result["R2-C4"] == "FAILED"
    assert result["R2-C6"] == "FAILED"
    assert "dirty_recovery" in result["failures"]


def test_c4_rejects_nonfinite_phase_duration(tmp_path: Path) -> None:
    c1, steady, dirty, junit, s5 = accepted_fixture(tmp_path)
    result_file = json.loads((steady / "result.json").read_text())
    result_file["measured_seconds"] = float("inf")
    write(steady / "result.json", result_file)

    result = evaluate(c1, steady, dirty, junit, s5)

    assert result["R2-C4"] == "FAILED"
    assert result["R2-C6"] == "FAILED"
    assert "steady_duration" in result["failures"]


@pytest.mark.parametrize(
    "extra",
    [
        {"base": "BTC", "timeframe": "1m", "valid": False},
        {"base": "SOL", "timeframe": "1m", "valid": True},
    ],
)
def test_c4_rejects_extra_observation_series(tmp_path: Path, extra: dict[str, object]) -> None:
    c1, steady, dirty, junit, s5 = accepted_fixture(tmp_path)
    observations = json.loads((steady / "observations.json").read_text())
    observations[0]["series"].append(extra)
    write(steady / "observations.json", observations)

    result = evaluate(c1, steady, dirty, junit, s5)

    assert result["R2-C4"] == "FAILED"
    assert result["R2-C6"] == "FAILED"
    assert "steady_observations" in result["failures"]
