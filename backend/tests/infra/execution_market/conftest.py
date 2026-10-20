import pytest

from tests.infra.positions.conftest import legacy_wallet as legacy_wallet
from tests.infra.positions.conftest import owner as owner
from tests.infra.positions.conftest import production_wallet as production_wallet
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot


@pytest.fixture
def wallet(production_wallet: PaperWalletSnapshot) -> PaperWalletSnapshot:
    """Use production-created, F-15-managed wallets for execution-market tests."""
    return production_wallet
