import os
import subprocess
import sys
from pathlib import Path

FIXTURE_PATH = Path("tests/fixtures/btcusdt_5m_tracer.csv")
EXPECTED_JSON = (
    '{"accepted_candles":40,"closed_baskets":1,"current_entries":0,'
    '"realized_pnl":"13.84062222"}\n'
)


def test_replay_cli_prints_stable_json() -> None:
    completed = _run_cli(FIXTURE_PATH)

    assert completed.returncode == 0
    assert completed.stdout == EXPECTED_JSON
    assert completed.stderr == ""


def test_replay_cli_reports_a_missing_csv_file() -> None:
    completed = _run_cli(Path("tests/fixtures/missing.csv"))

    assert completed.returncode == 2
    assert completed.stdout == ""
    assert completed.stderr.startswith("error:")


def _run_cli(csv_path: Path) -> subprocess.CompletedProcess[str]:
    environment = os.environ | {"PYTHONPATH": "src"}
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "tiewtrade.paper_replay_main",
            str(csv_path),
            "--available-capital",
            "1000",
            "--trading-capital-ratio",
            "0.6",
            "--max-entries",
            "4",
        ],
        capture_output=True,
        check=False,
        env=environment,
        text=True,
    )
