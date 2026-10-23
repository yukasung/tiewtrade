"""Explicit F-12 V-17 runner on the isolated F-11 capacity services."""

import argparse
import asyncio
import base64
import json
import tempfile
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from pathlib import Path
from statistics import quantiles
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import make_url

from tiewtrade.core.market_data import Timeframe
from tiewtrade.infra.auth.sessions import issue, new_token
from tiewtrade.infra.db import DatabaseRole, create_engine_for, database_url
from tiewtrade.infra.db.session import market_data_session, user_session
from tiewtrade.infra.indicators.source import begin_source_write
from tiewtrade.infra.users import create_user_in
from tiewtrade.services.api.authentication import new_csrf_token

NETWORK = "tiewtrade-f11-capacity-net"
PG = "tiewtrade-f11-capacity-postgres"
REDIS = "tiewtrade-f11-capacity-redis"
PREFIX = "tiewtrade-f12-v17-"
FAULT_TIMEFRAMES = tuple(Timeframe)[:5]


def require_isolated_database() -> None:
    """Reject destructive fixture resets outside the dedicated capacity stack."""
    for role in (
        DatabaseRole.MIGRATOR,
        DatabaseRole.API,
        DatabaseRole.AUTH,
        DatabaseRole.MARKET_DATA,
    ):
        url = make_url(database_url(role))
        if (url.host, url.port, url.database) != ("127.0.0.1", 55434, "tiewtrade"):
            raise RuntimeError("F12_VALIDATION_REQUIRES_ISOLATED_DATABASE")


async def docker(*arguments: str, timeout: float = 300, include_stderr: bool = False) -> str:
    process = await asyncio.create_subprocess_exec(
        "docker", *arguments, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout)
    except BaseException:
        if process.returncode is None:
            process.kill()
        await process.wait()
        raise
    if process.returncode:
        diagnostic = (stderr.decode() + "\n" + stdout.decode())[-3000:]
        raise RuntimeError(f"F12_DOCKER_FAILED:{arguments[0]}:{diagnostic}")
    output = stdout + stderr if include_stderr else stdout
    return output.decode().strip()


async def wait_for_services() -> None:
    deadline = asyncio.get_running_loop().time() + 30
    engine = create_engine_for(DatabaseRole.MIGRATOR)
    while asyncio.get_running_loop().time() < deadline:
        try:
            await docker("exec", PG, "pg_isready", "-U", "postgres", "-d", "tiewtrade")
            redis_ready = await docker("exec", REDIS, "redis-cli", "PING") == "PONG"
            async with engine.connect() as connection:
                database_ready: bool = (
                    await connection.execute(text("SELECT 1"))
                ).scalar_one() == 1
            if redis_ready and database_ready:
                await engine.dispose()
                return
        except Exception:
            await engine.dispose()
            engine = create_engine_for(DatabaseRole.MIGRATOR)
            pass
        await asyncio.sleep(0.2)
    await engine.dispose()
    raise RuntimeError("F12_VALIDATION_SERVICES_NOT_READY")


def save(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, default=str, indent=2) + "\n", encoding="utf-8")


def percentile(values: list[float], percentage: int) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    return quantiles(values, n=100, method="inclusive")[percentage - 1]


async def create_accounts(path: Path) -> None:
    engine = create_engine_for(DatabaseRole.AUTH)
    accounts = []
    now = datetime.now(UTC)
    try:
        for _ in range(20):
            user_id = uuid4()
            token, token_hash = new_token()
            async with user_session(engine, user_id, role=DatabaseRole.AUTH) as session:
                await create_user_in(session, user_id)
                await issue(
                    session,
                    token_hash=token_hash,
                    idle_expires_at=now + timedelta(minutes=30),
                    absolute_expires_at=now + timedelta(hours=6),
                )
            accounts.append({"session": token, "csrf": new_csrf_token()})
        save(path, accounts)
    finally:
        await engine.dispose()


async def set_mode(mode: str) -> None:
    engine = create_engine_for(DatabaseRole.MIGRATOR)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "UPDATE indicator_rollout_control "
                    "SET mode=CAST(:mode AS indicator_rollout_mode) WHERE id=1"
                ),
                {"mode": mode},
            )
    finally:
        await engine.dispose()


async def prepare_mode_fixture() -> list[dict[str, Any]]:
    """Reset only isolated workload state and force the approved five source cases."""
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    prepared: list[dict[str, Any]] = []
    try:
        async with market_data_session(engine) as session:
            await begin_source_write(session)
            await session.execute("DELETE FROM market_candle_preview")
            # Persistent capacity services can retain unrelated work from an
            # earlier mode. Make every non-fault series ineligible before
            # scheduling the five controlled refreshes below.
            await session.execute(
                """UPDATE market_candle_demand SET status='COMPLETE',
                leased_start=desired_start,leased_end=desired_end,
                refresh_served_at=refresh_requested_at,next_attempt_at='infinity',
                token=NULL,worker=NULL,lease_until=NULL"""
            )
            for timeframe in FAULT_TIMEFRAMES:
                row = (
                    (
                        await session.execute(
                            """SELECT open_at,end_at FROM market_candles
                            WHERE source='primary_spot' AND base='BTC' AND quote='USDT'
                              AND timeframe=:timeframe ORDER BY open_at DESC LIMIT 1""",
                            {"timeframe": timeframe.value},
                        )
                    )
                    .mappings()
                    .one()
                )
                parameters = {
                    "timeframe": timeframe.value,
                    "start": row["open_at"],
                    "end": row["end_at"],
                }
                await session.execute(
                    """UPDATE market_candles SET finality='UNCONFIRMED',
                    fetch_started_at=least(fetch_started_at,end_at-interval '1 second'),
                    last_checked_at=least(fetch_started_at,end_at-interval '1 second')
                    WHERE source='primary_spot' AND base='BTC' AND quote='USDT'
                      AND timeframe=:timeframe AND open_at=:start""",
                    parameters,
                )
                await session.execute(
                    """UPDATE market_candle_demand SET status='COMPLETE',phase='REFRESH',
                    desired_start=:start,desired_end=:end,leased_start=:start,leased_end=:end,
                    cursor=:end,repair_cursor=NULL,repair_pass=0,refresh_cursor=:start,
                    refresh_as_of=NULL,refresh_requested_at=clock_timestamp(),
                    refresh_served_at=NULL,fetch_unit_id=NULL,fetch_start=NULL,fetch_end=NULL,
                    fetch_started_at=NULL,fetch_recent=false,attemptcount=0,
                    next_attempt_at='-infinity',checked_at=clock_timestamp()-interval '1 second',
                    failure_code=NULL,token=NULL,worker=NULL,lease_until=NULL
                    WHERE source='primary_spot' AND base='BTC' AND quote='USDT'
                      AND timeframe=:timeframe""",
                    parameters,
                )
                prepared.append(
                    {
                        "base": "BTC",
                        "timeframe": timeframe.value,
                        "start": row["open_at"],
                        "end": row["end_at"],
                    }
                )
    finally:
        await engine.dispose()
    return prepared


def environment(kind: str) -> dict[str, str]:
    if kind == "api":
        values = {
            "TIEWTRADE_DATABASE_URL_API": f"postgresql+asyncpg://tiewtrade_api:dev_api@{PG}:5432/tiewtrade",
            "TIEWTRADE_DATABASE_URL_AUTH": f"postgresql+asyncpg://tiewtrade_auth:dev_auth@{PG}:5432/tiewtrade",
            "TIEWTRADE_REDIS_URL_API": f"redis://{REDIS}:6379/0",
            "TIEWTRADE_COOKIE_SECURE": "0",
            "TIEWTRADE_CHART_ENABLED": "1",
            "TIEWTRADE_PRICE_ORIGINS": "http://frontend:5173",
        }
        for purpose, byte in (
            ("TOTP_SECRET", b"T"),
            ("VENUE_API_SECRET", b"V"),
            ("INDICATOR_CURSOR", b"I"),
        ):
            values["TIEWTRADE_SEALING_KEY_" + purpose] = "1:" + base64.b64encode(byte * 32).decode()
        return values
    if kind == "builder":
        return {
            "TIEWTRADE_DATABASE_URL_INDICATOR_BUILDER": (
                f"postgresql+asyncpg://tiewtrade_indicator_builder:dev_indicator_builder@{PG}:5432/tiewtrade"
            )
        }
    return {
        "TIEWTRADE_DATABASE_URL_MARKET_DATA": f"postgresql+asyncpg://tiewtrade_market_data:dev_market_data@{PG}:5432/tiewtrade",
        "TIEWTRADE_REDIS_URL_MARKET_DATA": f"redis://{REDIS}:6379/0",
    }


async def create_runtime(image: str, kind: str, output: Path, seconds: int) -> str:
    name = PREFIX + kind
    source = Path(__file__).resolve().parent
    arguments = [
        "create",
        "--name",
        name,
        "--network",
        NETWORK,
        "--network-alias",
        kind,
        "--restart=no",
        "--cpus=2",
        "--memory=1g",
        "--mount",
        f"type=bind,source={source},target=/chartwork,readonly",
        "--mount",
        f"type=bind,source={output},target=/evidence",
        "-e",
        "PYTHONPATH=/chartwork",
    ]
    for key, value in environment(kind).items():
        arguments += ["-e", key + "=" + value]
    if kind == "api":
        command = [
            "uvicorn",
            "profile_chart_app:app",
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
            "--no-access-log",
        ]
    elif kind == "builder":
        command = ["python", "-m", "tiewtrade.services.indicator_builder.main", "run"]
    else:
        command = ["python", "-m", "profile_chart_runtime", "--seconds", str(seconds)]
    return await docker(*arguments, image, *command)


async def wait_for_preview() -> None:
    engine = create_engine_for(DatabaseRole.MIGRATOR)
    deadline = asyncio.get_running_loop().time() + 60
    try:
        while asyncio.get_running_loop().time() < deadline:
            async with engine.connect() as connection:
                ready: int = (
                    await connection.execute(
                        text(
                            "SELECT count(DISTINCT timeframe) FROM market_candle_preview "
                            "WHERE source='primary_spot' AND base='BTC' AND quote='USDT' "
                            "AND received_at >= clock_timestamp() - interval '3 seconds'"
                        )
                    )
                ).scalar_one()
            if ready == 8:
                return
            await asyncio.sleep(0.1)
    finally:
        await engine.dispose()
    raise RuntimeError("F12_PREVIEW_NOT_READY")


async def query_counts() -> dict[str, Any]:
    engine = create_engine_for(DatabaseRole.MIGRATOR)
    try:
        async with engine.connect() as connection:
            row = (
                (
                    await connection.execute(
                        text("""SELECT
                    (SELECT count(*) FROM market_candle_preview) preview_rows,
                    (SELECT count(*) FROM market_candle_demand
                      WHERE status IN ('PENDING','RUNNING')) active_demands,
                    (SELECT count(*) FROM indicator_build_jobs
                      WHERE status IN ('QUEUED','RUNNING')) active_jobs,
                    (SELECT count(*) FROM indicator_build_jobs
                      WHERE status='READY') ready_jobs,
                    (SELECT coalesce(sum(generation_sequence),0)
                      FROM indicator_build_jobs) generation_sequence,
                    (SELECT count(*) FROM pg_stat_activity
                      WHERE usename='tiewtrade_api') api_connections,
                    (SELECT count(*) FROM pg_stat_activity
                      WHERE usename='tiewtrade_market_data') market_connections""")
                    )
                )
                .mappings()
                .one()
            )
            return dict(row)
    finally:
        await engine.dispose()


def load_json_lines(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def evaluate(mode: str, output: Path, lifecycle_cycles: int) -> dict[str, Any]:
    browser = json.loads((output / "browser.json").read_text(encoding="utf-8"))
    api = load_json_lines(output / "api-metrics.jsonl")
    market = load_json_lines(output / "market-metrics.jsonl")
    source = load_json_lines(output / "source-metrics.jsonl")
    ingestion = load_json_lines(output / "ingestion-metrics.jsonl")
    database_before = json.loads((output / "database-before.json").read_text(encoding="utf-8"))
    database_after = json.loads((output / "database-counts.json").read_text(encoding="utf-8"))
    started = datetime.fromisoformat(browser["measurement_started_at"])
    ended = datetime.fromisoformat(browser["measurement_ended_at"])
    api = [row for row in api if started <= datetime.fromisoformat(row["recorded_at"]) <= ended]
    market = [
        row for row in market if started <= datetime.fromisoformat(row["recorded_at"]) <= ended
    ]
    live_rows = [row for row in api if row["path"].endswith("/live")]
    live = [row["seconds"] for row in live_rows if row["status"] == 200]
    history_rows = [row for row in api if row["path"].endswith("/candles/pages")]
    histories = [row["seconds"] for row in history_rows if row["status"] == 200]
    commits = [row["commit_seconds"] for row in market]
    browser_text = [value for value in browser["browser_text_seconds"] if value >= 0]
    commit_p95 = percentile(commits, 95)
    browser_text_p95 = percentile(browser_text, 95)
    live_p95 = percentile(live, 95)
    history_p95 = percentile(histories, 95)
    live_failures_typed = all(
        row["status"] == 504 and row.get("error_code") == "CHART_DEADLINE_EXCEEDED"
        for row in live_rows
        if row["status"] != 200
    )
    successful_clients = {row["client"] for row in browser["live"] if row["status"] == 200}
    fault_outcomes = {(row["base"], row["timeframe"]): row["outcome"] for row in source}
    fault_series = {
        (row["base"], row["timeframe"]) for row in source if row["outcome"] == "SOURCE_UNAVAILABLE"
    }
    checks = {
        "clients_20": browser["clients"] == 20,
        "mount_unmount_cycles": browser["mount_unmount_cycles"] == lifecycle_cycles,
        "browser_slots_bounded": browser["maximum_retained_slots"] <= 12000,
        "preview_commit_p95": commit_p95 is not None and commit_p95 <= 3,
        "browser_text_p95": browser_text_p95 is not None and browser_text_p95 <= 5,
        "live_p95": live_p95 is not None and live_p95 <= 0.5,
        "live_max": bool(live) and max(live) <= 2,
        "live_failures_typed": live_failures_typed,
        "all_clients_received_live": len(successful_clients) == 20,
        "history_deadline": bool(histories)
        and max(histories) <= 30
        and all(
            row["status"] == 200 or isinstance(row.get("error_code"), str) for row in history_rows
        ),
        "prepared_history_p95": mode != "PREPARED"
        or (history_p95 is not None and history_p95 <= 3),
        "api_rss": bool(api)
        and max(row["rss_delta_upper_bytes"] for row in api) <= 128 * 1024 * 1024,
        "market_rss": bool(market)
        and max(row["rss_delta_upper_bytes"] for row in market) <= 128 * 1024 * 1024,
        "preview_rows_bounded": database_after["preview_rows"] <= 60,
        "process_queue_bounded": bool(market)
        and max(row["rows_in_memory"] for row in market) <= 16,
        "source_faults_five_series": len(fault_series) == 5,
        "source_recovered": all(
            fault_outcomes.get(series) == "COMPLETE" for series in fault_series
        ),
        "source_writes_progress": sum(row["stored"] for row in ingestion) > 0,
        "prepared_jobs_progress": mode != "PREPARED"
        or int(database_after["generation_sequence"]) > int(database_before["generation_sequence"]),
        "api_connections_bounded": database_after["api_connections"] <= 15,
        "market_connections_bounded": database_after["market_connections"] <= 15,
        "no_forbidden_requests": not browser["forbidden_requests"],
    }
    return {
        "mode": mode,
        "checks": checks,
        "passed": all(checks.values()),
        "metrics": {
            "preview_commit_p95_seconds": commit_p95,
            "browser_text_p95_seconds": browser_text_p95,
            "live_p95_seconds": live_p95,
            "live_max_seconds": max(live) if live else None,
            "history_p95_seconds": history_p95,
            "history_max_seconds": max(histories) if histories else None,
            "api_max_rss_delta_bytes": max(
                (row["rss_delta_upper_bytes"] for row in api), default=None
            ),
            "market_max_rss_delta_bytes": max(
                (row["rss_delta_upper_bytes"] for row in market), default=None
            ),
        },
    }


async def run_mode(
    mode: str,
    output: Path,
    image: str,
    seconds: int,
    warmup: int,
    lifecycle_cycles: int,
) -> bool:
    output.mkdir(parents=True)
    await set_mode(mode)
    save(output / "fixture.json", await prepare_mode_fixture())
    with tempfile.TemporaryDirectory(prefix="tiewtrade-f12-v17-") as temporary:
        accounts = Path(temporary) / "accounts.json"
        await create_accounts(accounts)
        await create_runtime(
            image,
            "api",
            output,
            seconds,
        )
        # The market runtime must outlive browser setup and lifecycle validation,
        # not only the timed measurement window. It is stopped explicitly once
        # Playwright finishes so evaluation reads a frozen evidence set.
        lifecycle_allowance = lifecycle_cycles * 15 + 300
        runtime_seconds = seconds + warmup + lifecycle_allowance
        await create_runtime(image, "market", output, runtime_seconds)
        runtime_kinds = ["api", "market"]
        if mode == "PREPARED":
            await create_runtime(image, "builder", output, seconds)
            runtime_kinds.append("builder")
        browser = PREFIX + "browser"
        root = Path(__file__).resolve().parents[4]
        try:
            await docker("start", *(PREFIX + kind for kind in runtime_kinds))
            await wait_for_preview()
            save(output / "database-before.json", await query_counts())
            await docker(
                "run",
                "--name",
                browser,
                "--network",
                NETWORK,
                "--ipc=host",
                "--mount",
                "type=bind,source="
                f"{root / 'frontend/e2e/chart-workload.workload.ts'},"
                "target=/app/e2e/chart-workload.workload.ts,readonly",
                "--mount",
                "type=bind,source="
                f"{root / 'frontend/playwright.chart-workload.config.ts'},"
                "target=/app/playwright.chart-workload.config.ts,readonly",
                "--mount",
                f"type=bind,source={accounts},target=/run/accounts.json,readonly",
                "--mount",
                f"type=bind,source={output},target=/evidence",
                "-e",
                "CHART_WORKLOAD_API_URL=http://api:8000",
                "-e",
                "CHART_WORKLOAD_ACCOUNTS=/run/accounts.json",
                "-e",
                "CHART_WORKLOAD_BROWSER_OUTPUT=/evidence/browser.json",
                "-e",
                f"CHART_WORKLOAD_SECONDS={seconds}",
                "-e",
                f"CHART_WORKLOAD_WARMUP_SECONDS={warmup}",
                "-e",
                f"CHART_WORKLOAD_LIFECYCLE_CYCLES={lifecycle_cycles}",
                "tiewtrade-f12-playwright:latest",
                "npx",
                "playwright",
                "test",
                "e2e/chart-workload.workload.ts",
                "--config=playwright.chart-workload.config.ts",
                timeout=runtime_seconds,
            )
            await docker("stop", "--timeout", "30", PREFIX + "market")
            if mode == "PREPARED":
                await docker("stop", "--timeout", "130", PREFIX + "builder")
            await docker("stop", "--timeout", "30", PREFIX + "api")
            for kind in runtime_kinds:
                logs = await docker("logs", PREFIX + kind, include_stderr=True)
                (output / f"{kind}.log").write_text(logs, encoding="utf-8")
            save(output / "database-counts.json", await query_counts())
            result = evaluate(mode, output, lifecycle_cycles)
            save(output / "result.json", result)
            return bool(result["passed"])
        finally:
            for kind in runtime_kinds:
                log_path = output / f"{kind}.log"
                if not log_path.exists():
                    logs = await docker("logs", PREFIX + kind, include_stderr=True)
                    log_path.write_text(logs, encoding="utf-8")
            await docker("stop", "--timeout", "130", *(PREFIX + kind for kind in runtime_kinds))
            with suppress(RuntimeError):
                await docker("rm", browser)
            await docker("rm", *(PREFIX + kind for kind in runtime_kinds))


async def main(
    output: Path,
    image: str,
    seconds: int,
    warmup: int,
    lifecycle_cycles: int,
    keep_services: bool,
) -> int:
    require_isolated_database()
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    save(
        output / "environment.json",
        {
            "candidate_image": await docker("image", "inspect", "--format", "{{.Id}}", image),
            "browser_image": await docker(
                "image",
                "inspect",
                "--format",
                "{{.Id}}",
                "tiewtrade-f12-playwright:latest",
            ),
            "docker": await docker(
                "info",
                "--format",
                "{{.OSType}} {{.Architecture}} CPUs={{.NCPU}} RAM={{.MemTotal}}",
            ),
            "browser_runtime": await docker(
                "run",
                "--rm",
                "tiewtrade-f12-playwright:latest",
                "sh",
                "-lc",
                "node --version && npx playwright --version",
            ),
            "api_market_limits": {"cpus": 2, "memory_bytes": 1024**3},
            "fixture_seed": "deterministic-sequence-0",
            "seconds": seconds,
            "warmup_seconds": warmup,
            "lifecycle_cycles": lifecycle_cycles,
            "lifecycle_allowance_seconds": lifecycle_cycles * 15 + 300,
        },
    )
    for container in (PG, REDIS):
        await docker("start", container)
    await wait_for_services()
    passed = True
    try:
        for mode in ("LEGACY", "PREPARED"):
            passed = (
                await run_mode(
                    mode,
                    output / mode.lower(),
                    image,
                    seconds,
                    warmup,
                    lifecycle_cycles,
                )
                and passed
            )
    finally:
        if not keep_services:
            await docker("stop", "--timeout", "30", PG, REDIS)
    return 0 if passed else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--seconds", type=int, default=600)
    parser.add_argument("--warmup", type=int, default=60)
    parser.add_argument("--lifecycle-cycles", type=int, default=100)
    parser.add_argument("--keep-services", action="store_true")
    arguments = parser.parse_args()
    raise SystemExit(
        asyncio.run(
            main(
                arguments.output,
                arguments.image,
                arguments.seconds,
                arguments.warmup,
                arguments.lifecycle_cycles,
                arguments.keep_services,
            )
        )
    )
