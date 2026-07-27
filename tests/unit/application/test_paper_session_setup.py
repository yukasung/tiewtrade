from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from tiewtrade.application.paper_session_setup import (
    ConfiguredPaperSession,
    CreatePaperSession,
    PaperSessionCreateOutcome,
    PaperSessionSetupValues,
    PaperSessionUnavailableError,
    PaperSessionValidationError,
)
from tiewtrade.trading.session_config import MarketType, TradeMode

SESSION_ID = UUID("00000000-0000-0000-0000-000000000123")
CREATED_AT = datetime(2026, 7, 27, 8, 0, tzinfo=UTC)


def spot_values() -> PaperSessionSetupValues:
    return PaperSessionSetupValues(
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


def test_create_spot_session_builds_immutable_configuration() -> None:
    recorded: list[ConfiguredPaperSession] = []

    def create_active(session: ConfiguredPaperSession) -> PaperSessionCreateOutcome:
        recorded.append(session)
        return PaperSessionCreateOutcome(session=session, created=True)

    use_case = CreatePaperSession(
        create_active=create_active,
        session_ids=lambda: SESSION_ID,
        clock=lambda: CREATED_AT,
    )

    outcome = use_case.execute(spot_values())

    assert outcome.created is True
    assert outcome.session.config.session_id == SESSION_ID
    assert outcome.session.config.trade_mode is TradeMode.PAPER
    assert outcome.session.config.market_type is MarketType.SPOT
    assert outcome.session.market_data.symbol == "BTCUSDT"
    assert outcome.session.market_data.timeframe == "5m"
    assert outcome.session.config.fee_rate == Decimal("0.001")
    assert outcome.session.config.slippage_bps == Decimal("5")
    assert outcome.session.config.entry_policy.max_entries == 10
    assert outcome.session.config.spot_policy is not None
    assert outcome.session.config.spot_policy.trading_capital_ratio == Decimal("0.8")
    assert outcome.session.config.futures_policy is None
    assert outcome.session.created_at_utc == CREATED_AT
    assert recorded == [outcome.session]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("available_capital", "0"),
        ("max_entries", "3"),
        ("fee_percent", "100"),
        ("slippage_bps", "10000"),
        ("spot_trading_capital_percent", "100"),
    ],
)
def test_invalid_input_reports_the_exact_field(field: str, value: str) -> None:
    values = replace(spot_values(), **{field: value})
    use_case = CreatePaperSession(
        create_active=lambda session: pytest.fail("must not persist"),
        session_ids=lambda: SESSION_ID,
        clock=lambda: CREATED_AT,
    )

    with pytest.raises(PaperSessionValidationError) as caught:
        use_case.execute(values)

    assert caught.value.field == field


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("available_capital", "not-a-number"),
        ("max_entries", "10.5"),
        ("fee_percent", ""),
    ],
)
def test_malformed_input_reports_the_exact_field(field: str, value: str) -> None:
    values = replace(spot_values(), **{field: value})
    use_case = CreatePaperSession(
        create_active=lambda session: pytest.fail("must not persist"),
        session_ids=lambda: SESSION_ID,
        clock=lambda: CREATED_AT,
    )

    with pytest.raises(PaperSessionValidationError) as caught:
        use_case.execute(values)

    assert caught.value.field == field


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("available_capital", "Infinity"),
        ("available_capital", "NaN"),
        ("fee_percent", "NaN"),
        ("slippage_bps", "Infinity"),
        ("spot_trading_capital_percent", "NaN"),
    ],
)
def test_non_finite_input_reports_the_exact_field(field: str, value: str) -> None:
    values = replace(spot_values(), **{field: value})
    use_case = CreatePaperSession(
        create_active=lambda session: pytest.fail("must not persist"),
        session_ids=lambda: SESSION_ID,
        clock=lambda: CREATED_AT,
    )

    with pytest.raises(PaperSessionValidationError) as caught:
        use_case.execute(values)

    assert caught.value.field == field


def test_create_futures_session_builds_v1_policy() -> None:
    values = replace(
        spot_values(),
        market_type="futures",
        spot_trading_capital_percent=None,
        futures_leverage="3",
    )
    use_case = CreatePaperSession(
        create_active=lambda session: PaperSessionCreateOutcome(session, True),
        session_ids=lambda: SESSION_ID,
        clock=lambda: CREATED_AT,
    )

    outcome = use_case.execute(values)

    policy = outcome.session.config.futures_policy
    assert outcome.session.config.market_type is MarketType.FUTURES
    assert outcome.session.config.spot_policy is None
    assert policy is not None
    assert policy.leverage == 3
    assert policy.margin_mode.value == "cross"
    assert policy.position_mode.value == "one_way"


def test_futures_session_requires_leverage() -> None:
    values = replace(
        spot_values(),
        market_type="futures",
        spot_trading_capital_percent=None,
        futures_leverage=None,
    )
    use_case = CreatePaperSession(
        create_active=lambda session: pytest.fail("must not persist"),
        session_ids=lambda: SESSION_ID,
        clock=lambda: CREATED_AT,
    )

    with pytest.raises(PaperSessionValidationError) as caught:
        use_case.execute(values)

    assert caught.value.field == "futures_leverage"


def test_persistence_unavailable_error_is_not_reported_as_validation() -> None:
    def unavailable(session: ConfiguredPaperSession) -> PaperSessionCreateOutcome:
        raise PaperSessionUnavailableError("persistence unavailable")

    use_case = CreatePaperSession(
        create_active=unavailable,
        session_ids=lambda: SESSION_ID,
        clock=lambda: CREATED_AT,
    )

    with pytest.raises(PaperSessionUnavailableError, match="persistence unavailable"):
        use_case.execute(spot_values())
