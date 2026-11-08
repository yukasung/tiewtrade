import asyncio
import os
import sys
import pytest
from tiewtrade.services.engine import paper_wallet

@pytest.fixture(autouse=True)
def slow_setup(monkeypatch):
    original = paper_wallet.run_paper_wallet_round
    async def delayed_round(*args, **kwargs):
        if kwargs.get("worker") == "reset-timeout":
            await asyncio.sleep(0.1)
        return await original(*args, **kwargs)
    monkeypatch.setattr(paper_wallet, "run_paper_wallet_round", delayed_round)

os.chdir("../backend")
raise SystemExit(pytest.main(["tests/infra/paper_wallet/test_recovery.py::test_reset_interruption_rolls_back_and_same_command_recovers[timeout]"], plugins=[sys.modules[__name__]]))
