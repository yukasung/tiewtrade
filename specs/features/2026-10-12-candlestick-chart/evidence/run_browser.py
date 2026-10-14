"""Launch the dedicated chart browser checks with disposable local credentials."""

import base64
import os
import subprocess
import sys
from pathlib import Path

from tiewtrade.infra.crypto import KeyPurpose

for name in ("MIGRATOR", "API", "AUTH", "ENGINE", "ENGINE_SCAN", "MARKET_DATA"):
    role = name.lower()
    os.environ[f"TIEWTRADE_DATABASE_URL_{name}"] = (
        f"postgresql+asyncpg://tiewtrade_{role}:dev_{role}@127.0.0.1:55433/tiewtrade_e2e_f12"
    )
for name in ("API", "MARKET_DATA"):
    os.environ[f"TIEWTRADE_REDIS_URL_{name}"] = "redis://127.0.0.1:56379/0"
for purpose, byte in ((KeyPurpose.TOTP_SECRET,b"T"),(KeyPurpose.VENUE_API_SECRET,b"V"),
                      (KeyPurpose.INDICATOR_CURSOR,b"I")):
    os.environ[purpose.environment_variable] = "1:"+base64.b64encode(byte*32).decode()
os.environ["TIEWTRADE_E2E_DATABASE_NAME"] = "tiewtrade_e2e_f12"
os.environ["TIEWTRADE_SIGNUP_OPEN"] = "1"
os.environ["TIEWTRADE_COOKIE_SECURE"] = "0"
os.environ["TIEWTRADE_CHART_ENABLED"] = "1"
os.environ["VITE_CHART_ENABLED"] = "1"
frontend = Path(__file__).resolve().parents[4]/"frontend"
node = Path(sys.argv[1])
os.environ["PATH"] = str(node.parent)+os.pathsep+os.environ["PATH"]
raise SystemExit(subprocess.run([str(node), str(frontend/"node_modules/@playwright/test/cli.js"),
                                "test", "--config", "playwright.chart.config.ts", *sys.argv[2:]],
                               cwd=frontend,check=False).returncode)
