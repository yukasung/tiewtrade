from datetime import UTC, datetime, timedelta

import pytest

from tests.services.indicator_builder.profile_capacity import (
    CAPACITY_API_HOST,
    CAPACITY_PREFIX,
    capacity_api_url,
    capacity_scope_metadata,
    exact_build_retry_is_eligible,
    exact_build_terminal_failure,
    exact_retry_requires_clock_release,
    runtime_name,
)
from tests.services.indicator_builder.profile_capacity_steady import (
    capacity_gates,
    capacity_prerequisites,
    readiness_baseline_is_quiescent,
    rejected_load_is_complete,
    workload_readiness,
)


def test_f38_capacity_scope_metadata_is_explicit() -> None:
    assert capacity_scope_metadata() == {
        "supported_runtime_pairs": 2,
        "runtime_readiness_series": 16,
        "profile_pairs": 1,
        "profile_series": 8,
    }


def test_capacity_runtime_names_share_the_configured_prefix() -> None:
    assert runtime_name("api") == CAPACITY_PREFIX + "-api"
    assert runtime_name("builder") == CAPACITY_PREFIX + "-builder"


def test_capacity_api_url_uses_the_configured_probe_host_after_restart() -> None:
    assert capacity_api_url("49152") == f"http://{CAPACITY_API_HOST}:49152"


def test_exact_fixture_allows_a_queued_transient_retry() -> None:
    assert (
        exact_build_terminal_failure(
            {
                "status": "QUEUED",
                "failure_category": "TRANSIENT",
                "failure_reason": "TRANSIENT",
            }
        )
        is None
    )


def test_exact_fixture_surfaces_a_terminal_failure() -> None:
    assert (
        exact_build_terminal_failure(
            {
                "status": "FAILED_TRANSIENT",
                "failure_category": "TRANSIENT",
                "failure_reason": "TRANSIENT",
            }
        )
        == "FAILED_TRANSIENT:TRANSIENT:TRANSIENT"
    )


def test_exact_fixture_restarts_only_when_a_queued_retry_is_eligible() -> None:
    observed = datetime(2026, 10, 24, 17, 5, tzinfo=UTC)

    assert exact_build_retry_is_eligible(
        {"status": "QUEUED", "retry_not_before": observed - timedelta(seconds=1)}, observed
    )
    assert not exact_build_retry_is_eligible(
        {"status": "QUEUED", "retry_not_before": observed + timedelta(seconds=1)}, observed
    )
    assert not exact_build_retry_is_eligible(
        {"status": "READY", "retry_not_before": observed - timedelta(seconds=1)}, observed
    )


def test_exact_fixture_releases_elapsed_backoff_hidden_by_its_pinned_clock() -> None:
    boundary = datetime(2026, 10, 24, 17, 0, tzinfo=UTC)
    observed = boundary + timedelta(minutes=6)

    assert exact_retry_requires_clock_release(
        {
            "status": "QUEUED",
            "retry_not_before": boundary + timedelta(minutes=5),
        },
        observed,
        boundary,
    )
    assert not exact_retry_requires_clock_release(
        {"status": "QUEUED", "retry_not_before": boundary}, observed, boundary
    )


def test_long_running_phase_decisions_use_only_btc_workload() -> None:
    rows = [
        {"base": base, "timeframe": timeframe, "valid": base == "BTC"}
        for base in ("BTC", "ETH")
        for timeframe in ("1m", "5m", "15m", "1h", "4h", "1d", "1w", "1M")
    ]

    selected = workload_readiness(rows)

    assert len(selected) == 8
    assert all(row["base"] == "BTC" and row["valid"] for row in selected)


def test_long_running_baseline_requires_all_runtime_jobs_to_be_quiescent() -> None:
    rows = [{"valid": True}] * 16
    metadata = {
        "jobs": [{"status": "READY"}] * 16,
        "slot": [{"state": "IDLE"}],
    }

    assert readiness_baseline_is_quiescent(rows, metadata)
    metadata["jobs"][0] = {"status": "RUNNING"}
    assert not readiness_baseline_is_quiescent(rows, metadata)


def test_combined_capacity_phases_emit_paired_gates() -> None:
    assert capacity_gates("steady", under_load=True, combined=True) == (
        "R2-C2",
        "R2-C5-steady",
    )
    assert capacity_gates("dirty", under_load=True, combined=True) == (
        "R2-C3",
        "R2-C5-dirty",
    )


def test_combined_dirty_requires_both_combined_steady_gates() -> None:
    assert capacity_prerequisites("steady", under_load=True, combined=True) == ()
    assert capacity_prerequisites("dirty", under_load=True, combined=True) == (
        "R2-C2",
        "R2-C5-steady",
    )


def test_combined_capacity_phase_rejects_missing_load() -> None:
    with pytest.raises(ValueError, match="combined capacity evidence requires rejected load"):
        capacity_gates("steady", under_load=False, combined=True)


def test_rejected_load_requires_exact_status_detail_and_zero_queries() -> None:
    rejected = [
        *[{"kind": "busy", "status": 503, "detail": "INDICATOR_BUSY"} for _ in range(1200)],
        *[{"kind": "rate", "status": 429, "detail": "INDICATOR_RATE_LIMITED"} for _ in range(1200)],
    ]
    metrics = [
        *[{"kind": "rejected-busy", "status": 503, "candle_queries": 0} for _ in range(1200)],
        *[{"kind": "rejected-rate", "status": 429, "candle_queries": 0} for _ in range(1200)],
    ]

    assert rejected_load_is_complete(rejected, metrics)
    rejected[-1]["status"] = 503
    assert not rejected_load_is_complete(rejected, metrics)
