from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

from tiewtrade.application.paper_session_setup import (
    ConfiguredPaperSession,
    CreatePaperSession,
    PaperSessionCreateOutcome,
    PaperSessionSetupValues,
)

SESSION_ID = UUID("00000000-0000-0000-0000-000000000123")
CREATED_AT = datetime(2026, 7, 27, 8, 0, tzinfo=UTC)


def _configured(values: PaperSessionSetupValues) -> ConfiguredPaperSession:
    use_case = CreatePaperSession(
        create_active=lambda session: PaperSessionCreateOutcome(session, True),
        session_ids=lambda: SESSION_ID,
        clock=lambda: CREATED_AT,
    )
    return use_case.execute(values).session


def configured_spot_session(*, session_id: UUID = SESSION_ID) -> ConfiguredPaperSession:
    session = _configured(
        PaperSessionSetupValues(
            market_type="spot",
            symbol="BTCUSDT",
            timeframe="5m",
            available_capital="200000",
            max_entries="10",
            fee_percent="0.1",
            slippage_bps="5",
            spot_trading_capital_percent="80",
            futures_leverage=None,
        )
    )
    return replace(session, config=replace(session.config, session_id=session_id))


def configured_futures_session(
    leverage: int = 3,
    *,
    session_id: UUID = SESSION_ID,
) -> ConfiguredPaperSession:
    session = _configured(
        PaperSessionSetupValues(
            market_type="futures",
            symbol="BTCUSDT",
            timeframe="5m",
            available_capital="200000",
            max_entries="10",
            fee_percent="0.1",
            slippage_bps="5",
            spot_trading_capital_percent=None,
            futures_leverage=str(leverage),
        )
    )
    return replace(session, config=replace(session.config, session_id=session_id))
