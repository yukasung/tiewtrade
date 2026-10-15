"""F-13 migration safety at the populated downgrade boundary."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.infra.db import user_session
from tiewtrade.infra.paper_wallet import get_command

from .test_storage import _submit

_BACKEND_ROOT = Path(__file__).parents[3]


async def test_populated_downgrade_is_refused_without_deleting_command(
    api_engine: AsyncEngine,
    owner: UUID,
) -> None:
    command = await _submit(api_engine, owner, uuid4())
    await api_engine.dispose()

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "0030"],
        cwd=_BACKEND_ROOT,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "paper wallet data exists; downgrade refused" in result.stderr
    async with user_session(api_engine, owner) as session:
        assert await get_command(session, command.command_id) == command
