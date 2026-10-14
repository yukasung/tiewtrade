"""Run checks against the dedicated local F-12 test DB, never the app database."""

import os
import subprocess
import sys

os.environ["PYTHONUTF8"] = "1"
host = "127.0.0.1" if sys.platform == "win32" else "host.docker.internal"
port = 55433
redis_host, redis_port = host, 56379
if os.environ.get("F12_TEST_CONTAINER_NETWORK") == "1":
    host, port = "tiewtrade-f11-test-postgres", 5432
    redis_host, redis_port = "tiewtrade-f11-test-redis", 6379
for name in ("MIGRATOR", "API", "AUTH", "ENGINE", "ENGINE_SCAN", "MARKET_DATA",
             "INDICATOR_BUILDER"):
    role = name.lower()
    os.environ[f"TIEWTRADE_DATABASE_URL_{name}"] = (
        f"postgresql+asyncpg://tiewtrade_{role}:dev_{role}@{host}:{port}/tiewtrade_f12_test"
    )
for name in ("API", "MARKET_DATA"):
    os.environ[f"TIEWTRADE_REDIS_URL_{name}"] = f"redis://{redis_host}:{redis_port}/0"
os.environ["TIEWTRADE_TEST_REDIS_URL"] = f"redis://{redis_host}:{redis_port}/0"
if sys.argv[1] == "alembic":
    from alembic import command
    from alembic.config import Config

    config = Config()
    config.set_main_option("script_location", "migrations")
    getattr(command, sys.argv[2])(config, sys.argv[3])
    raise SystemExit(0)
raise SystemExit(subprocess.run(
    [sys.executable, "-X", "utf8", "-m", *sys.argv[1:]], check=False,
).returncode)
