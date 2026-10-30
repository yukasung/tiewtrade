"""Bounded read-only publisher backend sampler; no query text or parameters logged."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from time import monotonic, time

import asyncpg  # type: ignore[import-untyped]

ACTIVITY = """SELECT pid,state,wait_event_type,wait_event,
    extract(epoch FROM query_start)::double precision AS query_started,
    extract(epoch FROM state_change)::double precision AS state_changed,
    extract(epoch FROM clock_timestamp())::double precision AS observed_at
  FROM pg_stat_activity WHERE datname=current_database() AND usename=current_user
    AND pid<>pg_backend_pid() ORDER BY pid LIMIT 16"""


async def sample(output: Path, deadline: float) -> None:
    connection = None
    rows: list[dict[str, object]] = []
    outcome = "COMPLETE"
    try:
        connection = await asyncpg.connect(
            os.environ.pop("F18_SOURCE_OBSERVER_DSN"),
            server_settings={"default_transaction_read_only": "on", "statement_timeout": "1000"},
            timeout=5,
        )
        while monotonic() < deadline and len(rows) < 3000:
            started = monotonic()
            records = await connection.fetch(ACTIVITY)
            if len(records) >= 16:
                outcome = "ROW_LIMIT"
                break
            rows.append(
                {
                    "started": started,
                    "finished": monotonic(),
                    "wall": time(),
                    "backends": [dict(row) for row in records],
                }
            )
            await asyncio.sleep(max(0, 0.02 - (monotonic() - started)))
        if len(rows) >= 3000 and monotonic() < deadline:
            outcome = "SAMPLE_LIMIT"
    except Exception as error:
        outcome = type(error).__name__  # never expose driver messages/credentials
    finally:
        if connection is not None:
            await connection.close(timeout=2)
        output.write_text(json.dumps({"outcome": outcome, "deadline": deadline, "samples": rows}))


if __name__ == "__main__":
    asyncio.run(sample(Path(sys.argv[1]), float(sys.argv[2])))
