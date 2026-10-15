"""Isolated Paper worker: no credential, HTTP client or venue dependency."""

from __future__ import annotations

import asyncio
import logging
import os

from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.services.engine.paper_wallet import run_paper_wallet_round


async def serve() -> None:
    engine = create_engine_for(DatabaseRole.ENGINE)
    scan_engine = create_engine_for(DatabaseRole.ENGINE_SCAN)
    host = os.environ.get("HOSTNAME") or os.environ.get("COMPUTERNAME") or "local"
    worker = f"paper:{host}:{os.getpid()}"
    try:
        while True:
            await run_paper_wallet_round(engine=engine, scan_engine=scan_engine, worker=worker)
            await asyncio.sleep(0.5)
    finally:
        await engine.dispose()
        await scan_engine.dispose()


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
