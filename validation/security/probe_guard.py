"""Disposable validation harness only; never merged into the application."""
import hashlib
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EXPECTED = {'entry.py': '8368e3512d28c4ea0b0cb6143f26dfc5a94d65f260e395e9fbe144aa537091da', 'entry.js': 'c638c870e8ecbb669df67525e12487be808fec1d441c58f6830bd6a734994f64', 'package.json': '0fb0550e232979376c47b227e7311ebff864d15f44f111aa633b29582936361b'}
for name, expected in EXPECTED.items():
    assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, "FIXTURE_CHANGED"
for name in ("python", "javascript", "lifecycle"):
    assert not (Path(os.environ["RUNNER_TEMP"]) / ("security-probe-" + name)).exists(), "FIXTURE_EXECUTED"
print("SECURITY_MARKERS_ABSENT: python/javascript/lifecycle")
