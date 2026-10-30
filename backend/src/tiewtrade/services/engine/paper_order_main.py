"""Isolated Paper order process with transaction-scoped risk evidence."""

import asyncio
import logging
import os

from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.infra.risk_limits.policy import TransactionalRiskPolicy
from tiewtrade.services.engine.manual_order import run_manual_order_round
from tiewtrade.services.engine.paper_order import matching_round_modes, run_paper_order_round

# Approved F18-R8: bounded fallback hints, one claimed item per phase.
CANDIDATE_LIMIT = 20
CLAIM_LIMIT = 1
PREFER_SAME_PAIR_ADMISSION = False  # R9 W1 failed progress; retain approved R8 fallback.
ALTERNATE_ADMISSION_PRIORITY = True  # Approved R10; alternate with unchanged R8 fairness.
SOURCE_RESUMPTION = False  # R11 component proof passed; full qualification remains pending.


async def serve() -> None:
    modes = matching_round_modes(
        prefer_same_pair=PREFER_SAME_PAIR_ADMISSION,
        alternate_admission=ALTERNATE_ADMISSION_PRIORITY,
    )
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
                limit=CANDIDATE_LIMIT,
                claim_limit=CLAIM_LIMIT,
                policy=TransactionalRiskPolicy(),
            )
            prefer_same_pair, admission_first = next(modes)
            await run_paper_order_round(
                engine=engine,
                scan_engine=scan_engine,
                worker=worker,
                limit=CANDIDATE_LIMIT,
                claim_limit=CLAIM_LIMIT,
                prefer_same_pair=prefer_same_pair,
                admission_first=admission_first,
                source_resumption=SOURCE_RESUMPTION,
                policy=TransactionalRiskPolicy(),
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
