from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest

from tests.services.indicator_builder.profile_capacity_s5 import (
    S5_SERIES,
    evaluate_s5,
    s5_environment_valid,
)

START = datetime(2026, 10, 26, 1, 0, tzinfo=UTC)


def environment() -> tuple[dict[str, object], dict[str, object]]:
    image = "sha256:" + "a" * 64
    return (
        {
            "image": image,
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
            "supported_runtime_pairs": 2,
            "runtime_readiness_series": 16,
            "profile_pairs": 1,
            "profile_series": 8,
        },
        {"image": image},
    )


def evidence() -> tuple[
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
]:
    jobs = [
        {
            "base": base,
            "timeframe": timeframe,
            "first_eligible_at": START.isoformat(),
            "availability_deadline": (START + timedelta(seconds=600)).isoformat(),
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
    recovered_probes = [
        {"base": row["base"], "timeframe": row["timeframe"], "status": 200, "correct": True}
        for row in recovered
    ]
    recovering_probes = [
        row
        | {
            "status": 503 if (row["base"], row["timeframe"]) == ("BTC", "1m") else 200,
            "correct": (row["base"], row["timeframe"]) != ("BTC", "1m"),
        }
        for row in recovered_probes
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
    historical_writes: list[dict[str, object]] = []
    for offset in range(-1, 360, 5):
        historical_writes.append({"committed_at": START + timedelta(seconds=offset)})
    historical_writes.append({"churn_stopped_at": START + timedelta(seconds=361)})
    return (
        [{"recorded_at": START + timedelta(seconds=1), "jobs": jobs}],
        [
            {"recorded_at": START + timedelta(seconds=100), "series": recovering},
            {"recorded_at": START + timedelta(seconds=300), "series": recovered},
        ],
        [
            {"recorded_at": START + timedelta(seconds=200), "series": recovering_probes},
            {"recorded_at": START + timedelta(seconds=360), "series": recovered_probes},
        ],
        attempts,
        historical_writes,
    )


def test_s5_passes_complete_eight_series_episode() -> None:
    result = evaluate_s5(*evidence())

    assert result["R2-S5"] == "PASSED"
    assert result["failures"] == []
    assert len(result["series"]) == 8


def test_s5_environment_records_complete_fresh_runtime_provenance() -> None:
    actual, c1 = environment()

    assert s5_environment_valid(actual, c1)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("image", "sha256:different"),
        ("redis_dbsize_before_runtime", 1),
        ("redis_url_mode", "authenticated-or-unknown"),
        ("database_revision", ""),
        ("database_revision", "0030"),
        ("source_fixture", "unknown"),
        ("source_runtime_series", 15),
        ("append_only_runtime_series", 14),
        ("runtime_containers_created", {"api": "one", "builder": "two"}),
        (
            "runtime_containers_created",
            {"api": "same", "builder": "same", "builder-s5-peer": "peer"},
        ),
    ],
)
def test_s5_environment_fails_closed_on_missing_or_wrong_provenance(
    field: str, value: object
) -> None:
    actual, c1 = environment()
    actual[field] = value

    assert not s5_environment_valid(actual, c1)


def test_s5_fails_when_retry_resets_eligibility_deadline() -> None:
    trace, observations, probes, attempts, writes = evidence()
    changed = [dict(row) for row in cast(list[dict[str, Any]], trace[0]["jobs"])]
    changed[0]["first_eligible_at"] = (START + timedelta(seconds=30)).isoformat()
    changed[0]["availability_deadline"] = (START + timedelta(seconds=630)).isoformat()
    trace.append({"recorded_at": START + timedelta(seconds=40), "jobs": changed})

    result = evaluate_s5(trace, observations, probes, attempts, writes)

    assert result["R2-S5"] == "FAILED"
    assert "SERIES_STARVED_OR_EPISODE_RESET" in result["failures"]


def test_s5_allows_a_new_append_episode_after_initial_recovery() -> None:
    trace, observations, probes, attempts, writes = evidence()
    changed = [dict(row) for row in cast(list[dict[str, Any]], trace[0]["jobs"])]
    for row in changed:
        if (row["base"], row["timeframe"]) != ("BTC", "1m"):
            row["first_eligible_at"] = (START + timedelta(seconds=330)).isoformat()
            row["availability_deadline"] = (START + timedelta(seconds=930)).isoformat()
    trace.append({"recorded_at": START + timedelta(seconds=340), "jobs": changed})

    result = evaluate_s5(trace, observations, probes, attempts, writes)

    assert result["R2-S5"] == "PASSED"
    assert result["failures"] == []


def test_s5_fails_when_churn_stops_before_other_series_get_200() -> None:
    trace, observations, probes, attempts, writes = evidence()
    retained: list[dict[str, object]] = []
    for row in writes:
        moment = row.get("committed_at")
        if not isinstance(moment, datetime) or moment <= START + timedelta(seconds=199):
            retained.append(row)
    writes[:] = retained
    writes.append({"churn_stopped_at": START + timedelta(seconds=199)})

    result = evaluate_s5(trace, observations, probes, attempts, writes)

    assert result["R2-S5"] == "FAILED"
    assert "CHURN_DID_NOT_COVER_OTHER_SERIES_RECOVERY" in result["failures"]


def test_s5_fails_incorrect_get_even_when_status_is_200() -> None:
    trace, observations, probes, attempts, writes = evidence()
    target = next(
        row
        for row in cast(list[dict[str, Any]], probes[-1]["series"])
        if (row["base"], row["timeframe"]) != ("BTC", "1m")
    )
    target["correct"] = False

    result = evaluate_s5(trace, observations, probes, attempts, writes)

    assert result["R2-S5"] == "FAILED"
    assert "SERIES_STARVED_OR_EPISODE_RESET" in result["failures"]


def test_s5_fails_when_series_becomes_unhealthy_after_recovery() -> None:
    trace, observations, probes, attempts, writes = evidence()
    target = next(
        row
        for row in cast(list[dict[str, Any]], observations[-1]["series"])
        if (row["base"], row["timeframe"]) != ("BTC", "1m")
    )
    observations.append(
        {
            "recorded_at": START + timedelta(seconds=370),
            "series": [
                row | {"valid": False} if row is target else row
                for row in cast(list[dict[str, Any]], observations[-1]["series"])
            ],
        }
    )

    result = evaluate_s5(trace, observations, probes, attempts, writes)

    assert result["R2-S5"] == "FAILED"
    assert "SERIES_STARVED_OR_EPISODE_RESET" in result["failures"]


def test_s5_reports_churn_unavailability_per_series() -> None:
    result = evaluate_s5(*evidence())
    churn = next(
        row for row in result["series"] if (row["base"], row["timeframe"]) == ("BTC", "1m")
    )
    others = [row for row in result["series"] if row is not churn]

    assert churn["unavailable_samples"] == 1
    assert churn["valid_samples"] == 1
    assert all(row["unavailable_samples"] == 0 for row in others)


def test_s5_fails_when_a_never_recovers_after_continuous_supersession() -> None:
    trace, observations, probes, attempts, writes = evidence()
    for sample in observations:
        for row in cast(list[dict[str, Any]], sample["series"]):
            if (row["base"], row["timeframe"]) == ("BTC", "1m"):
                row["valid"] = False
    for sample in probes:
        for row in cast(list[dict[str, Any]], sample["series"]):
            if (row["base"], row["timeframe"]) == ("BTC", "1m"):
                row["status"] = 503
                row["correct"] = False
    churn_attempt = next(
        row for row in attempts if (row["base"], row["timeframe"]) == ("BTC", "1m")
    )
    churn_attempt["status"] = "SUPERSEDED"

    result = evaluate_s5(trace, observations, probes, attempts, writes)
    churn = next(row for row in result["series"] if row["role"] == "continuous-historical")

    assert result["R2-S5"] == "FAILED"
    assert "SERIES_STARVED_OR_EPISODE_RESET" in result["failures"]
    assert churn["valid_samples"] == 0
    assert churn["unavailable_samples"] == len(observations)
    assert churn["passed"] is False
    assert all(row["passed"] for row in result["series"] if row["role"] == "append-only")


def test_s5_accepts_released_attempt_only_when_series_also_publishes_ready() -> None:
    trace, observations, probes, attempts, writes = evidence()
    released = dict(attempts[0])
    released["status"] = "RELEASED"
    attempts.insert(0, released)

    assert evaluate_s5(trace, observations, probes, attempts, writes)["R2-S5"] == "PASSED"

    ready = attempts[1]
    attempts.remove(ready)
    result = evaluate_s5(trace, observations, probes, attempts, writes)
    assert result["R2-S5"] == "FAILED"
    assert "SERIES_STARVED_OR_EPISODE_RESET" in result["failures"]


def test_s5_fails_worker_attempt_over_120_seconds() -> None:
    trace, observations, probes, attempts, writes = evidence()
    attempts[0]["seconds_including_acquire_cleanup"] = 120.001

    result = evaluate_s5(trace, observations, probes, attempts, writes)

    assert result["R2-S5"] == "FAILED"
    assert "ATTEMPT_STATUS_OR_RESOURCE_LIMIT" in result["failures"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("seconds_including_acquire_cleanup", -0.001),
        ("seconds_including_acquire_cleanup", float("nan")),
        ("rss_delta_upper_bytes", -1),
        ("rss_delta_upper_bytes", True),
    ],
)
def test_s5_fails_invalid_worker_resource_value(field: str, value: object) -> None:
    trace, observations, probes, attempts, writes = evidence()
    attempts[0][field] = value

    result = evaluate_s5(trace, observations, probes, attempts, writes)

    assert result["R2-S5"] == "FAILED"
    assert "ATTEMPT_STATUS_OR_RESOURCE_LIMIT" in result["failures"]


def test_s5_fails_when_historical_writes_do_not_cover_recovery_continuously() -> None:
    trace, observations, probes, attempts, writes = evidence()
    writes[:] = [
        {"committed_at": START + timedelta(seconds=359)},
        {"committed_at": START + timedelta(seconds=359, milliseconds=1)},
        {"churn_stopped_at": START + timedelta(seconds=361)},
    ]

    result = evaluate_s5(trace, observations, probes, attempts, writes)

    assert result["R2-S5"] == "FAILED"
    assert "CHURN_DID_NOT_COVER_OTHER_SERIES_RECOVERY" in result["failures"]


def test_s5_fails_when_historical_write_cadence_has_a_gap() -> None:
    trace, observations, probes, attempts, writes = evidence()
    del writes[20:24]

    result = evaluate_s5(trace, observations, probes, attempts, writes)

    assert result["R2-S5"] == "FAILED"
    assert "CHURN_DID_NOT_COVER_OTHER_SERIES_RECOVERY" in result["failures"]


def test_s5_fails_when_recovery_precedes_eligibility() -> None:
    trace, observations, probes, attempts, writes = evidence()
    observations[0]["recorded_at"] = START - timedelta(seconds=20)
    observations[1]["recorded_at"] = START - timedelta(seconds=10)
    probes[0]["recorded_at"] = START - timedelta(seconds=15)
    probes[1]["recorded_at"] = START - timedelta(seconds=5)

    result = evaluate_s5(trace, observations, probes, attempts, writes)

    assert result["R2-S5"] == "FAILED"
    assert "SERIES_STARVED_OR_EPISODE_RESET" in result["failures"]
