"""Isolated Paper order process; production admission remains closed until F-18."""

import asyncio
import logging
import os

from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.services.engine.manual_order import run_manual_order_round
from tiewtrade.services.engine.paper_order import run_paper_order_round


async def serve() -> None:
    engine = create_engine_for(DatabaseRole.ENGINE)
    scan_engine = create_engine_for(DatabaseRole.ENGINE_SCAN)
    host = os.environ.get("HOSTNAME") or os.environ.get("COMPUTERNAME") or "local"
    worker = f"paper-order:{host}:{os.getpid()}"
    try:
        while True:
            await run_manual_order_round(
                engine=engine,
                scan_engine=scan_engine,
                worker=worker,
                policy=None,
            )
            await run_paper_order_round(
                engine=engine,
                scan_engine=scan_engine,
                worker=worker,
                policy=None,
            )
            await asyncio.sleep(0.02)
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
