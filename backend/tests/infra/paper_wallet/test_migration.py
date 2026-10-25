"""F-13 migration safety at the populated downgrade boundary."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.paper_orders.initialization import initialize_order_source
from tiewtrade.infra.paper_wallet import get_command, get_wallet
from tiewtrade.services.engine.paper_wallet import run_paper_wallet_round

from .test_storage import _reset, _submit

_BACKEND_ROOT = Path(__file__).parents[3]


async def test_populated_downgrade_is_refused_without_deleting_command(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
) -> None:
    await _submit(api_engine, owner, uuid4())
    await run_paper_wallet_round(
        engine=engine_engine, scan_engine=scan_engine, worker="migration-reset-create"
    )
    async with user_session(api_engine, owner) as session:
        wallet = await get_wallet(session)
    assert wallet is not None
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await initialize_order_source(
            session,
            wallet_id=wallet.wallet_id,
            episode_id=wallet.episode_id,
            initialization_id=uuid4(),
        )
    command = await _reset(api_engine, owner, uuid4(), wallet.episode_id, "2500")
    await run_paper_wallet_round(
        engine=engine_engine, scan_engine=scan_engine, worker="migration-reset"
    )
    async with user_session(api_engine, owner) as session:
        terminal = await get_command(session, command.command_id)
    assert terminal is not None and terminal.state.value == "SUCCEEDED"
    await api_engine.dispose()

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from alembic import command\n"
            "from alembic.config import Config\n"
            "import sys\n"
            "config = Config()\n"
            "config.set_main_option('script_location', sys.argv[1])\n"
            "command.downgrade(config, '0030')\n",
            str(_BACKEND_ROOT / "migrations"),
        ],
        cwd=_BACKEND_ROOT,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    # A newer schema can stop earlier; require its specific safety guard, not any error.
    guards = {
        "supported-symbol runtime history prevents downgrade": "0039",
        "historical Paper order revisions prevent downgrade": "0038",
        "Paper reset audit history prevents downgrade": "0037",
        "matching decision history prevents downgrade": "0036",
        "managed Paper episodes prevent writer fence downgrade": "0035",
        "paper wallet data exists; downgrade refused": "0032",
        "Paper financial history prevents downgrade": "0034",
        "Paper cash effects prevent downgrade": "0034",
        "stop execution producers before downgrade": "0033",
        "active execution dependencies prevent downgrade": "0033",
    }
    refused_at = {revision for reason, revision in guards.items() if reason in result.stderr}
    assert len(refused_at) == 1, result.stderr
    async with migrator_engine.connect() as connection:
        assert (
            await connection.execute(text("SELECT version_num FROM alembic_version"))
        ).scalar_one() in refused_at
        assert (
            await connection.execute(text("SELECT to_regclass('public.paper_position_activity')"))
        ).scalar_one() == "paper_position_activity"
    async with user_session(api_engine, owner) as session:
        assert await get_command(session, command.command_id) == terminal
