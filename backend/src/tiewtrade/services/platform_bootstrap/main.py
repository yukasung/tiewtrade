"""One-shot, interactive Platform Owner bootstrap command."""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import text

from tiewtrade.infra.db import DatabaseRole, create_engine_for


def _arguments(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="platform-owner-bootstrap")
    parser.add_argument("--user-id", required=True, type=UUID)
    return parser.parse_args(argv)


async def _bootstrap(user_id: UUID) -> None:
    engine = create_engine_for(DatabaseRole.PLATFORM_BOOTSTRAP)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text("SELECT public.bootstrap_platform_owner(:user_id)"),
                {"user_id": user_id},
            )
    finally:
        await engine.dispose()


def main(argv: Sequence[str] | None = None) -> None:
    args = _arguments(argv)
    if not sys.stdin.isatty():
        raise SystemExit("interactive terminal required")
    confirmation = input("Type the user UUID again to create the first Platform Owner: ").strip()
    if confirmation != str(args.user_id):
        raise SystemExit("confirmation did not match")
    asyncio.run(_bootstrap(args.user_id))
    sys.stdout.write("Platform Owner bootstrap completed\n")
