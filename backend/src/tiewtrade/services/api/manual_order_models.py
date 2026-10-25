"""Strict manual order inputs; decimal text is parsed only by Money/Quantity."""

from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictStr, model_validator

from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.orders import (
    BaseSize,
    OrderIntent,
    OrderOrigin,
    OrderScope,
    OrderType,
    QuoteBudget,
    TimeInForce,
    TradingMode,
)
from tiewtrade.core.positions import ExecutionSide, PositionPair

AmountText = Annotated[StrictStr, Field(min_length=1, max_length=256)]


class ExpectedPaperEpisode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_wallet_id: UUID
    expected_episode_id: UUID


class _NewOrderBase(ExpectedPaperEpisode):
    base: Annotated[StrictStr, Field(pattern=r"^[A-Z][A-Z0-9]{0,19}$")]
    quote: Literal["USDT"]

    @model_validator(mode="after")
    def distinct_assets(self) -> Self:
        if self.base == self.quote:
            raise ValueError("base and quote must differ")
        return self


class MarketBuyInput(_NewOrderBase):
    kind: Literal["MARKET"]
    side: Literal["BUY"]
    quote_budget: AmountText


class MarketSellInput(_NewOrderBase):
    kind: Literal["MARKET"]
    side: Literal["SELL"]
    base_quantity: AmountText


class LimitOrderInput(_NewOrderBase):
    kind: Literal["LIMIT"]
    side: Literal["BUY", "SELL"]
    base_quantity: AmountText
    limit_price: AmountText
    time_in_force: Literal["GTC"]


NewOrderInput = MarketBuyInput | MarketSellInput | LimitOrderInput


def manual_intent(
    body: NewOrderInput, *, owner_id: UUID, order_id: UUID, idempotency_key: UUID
) -> OrderIntent:
    pair = PositionPair(body.base, body.quote)
    size: QuoteBudget | BaseSize = (
        QuoteBudget(Money.of(body.quote_budget, pair.quote))
        if isinstance(body, MarketBuyInput)
        else BaseSize(Quantity.of(body.base_quantity, pair.base))
    )
    return OrderIntent(
        order_id=order_id,
        idempotency_key=idempotency_key,
        scope=OrderScope(UUID(str(owner_id)), body.expected_episode_id, TradingMode.PAPER),
        pair=pair,
        origin=OrderOrigin.MANUAL,
        side=ExecutionSide(body.side),
        kind=OrderType(body.kind),
        size=size,
        limit_price=Money.of(body.limit_price, pair.quote)
        if isinstance(body, LimitOrderInput)
        else None,
        time_in_force=TimeInForce.GTC if isinstance(body, LimitOrderInput) else None,
    )


class ManualOrderSummary(BaseModel):
    base: str
    quote: Literal["USDT"]
    side: Literal["BUY", "SELL"]
    kind: Literal["MARKET", "LIMIT"]
    quote_budget: str | None
    base_quantity: str | None
    limit_price: str | None
    time_in_force: Literal["GTC"] | None


class CommandAmount(BaseModel):
    amount: str
    currency: Literal["USDT"]


class CommandQuantity(BaseModel):
    quantity: str
    asset: str


class OrderCommandSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    order_id: UUID
    status: str
    filled: CommandQuantity | None = None
    spent: CommandAmount | None = None


class ManualRequestView(BaseModel):
    mode: Literal["PAPER"] = "PAPER"
    request_id: UUID
    wallet_id: UUID
    episode_id: UUID
    order_id: UUID
    action: Literal["NEW", "CANCEL"]
    idempotency_key: UUID
    request_summary: ManualOrderSummary | None
    recorded_at: str
    intake_state: Literal["PENDING", "TRANSFERRED", "REJECTED"]
    intake_failure_code: str | None
    command_id: UUID | None
    command_state: Literal["PENDING", "SUCCEEDED", "REJECTED"] | None
    command_failure_code: str | None
    command_snapshot: OrderCommandSnapshot | None
    order_state: str | None
    snapshot_at: str
    status_url: str


class ManualRequestPage(BaseModel):
    requests: list[ManualRequestView]
    next_cursor: str | None


class BaseBalanceView(BaseModel):
    asset: str
    held: str
    reserved: str
    available: str


class TradeWalletView(BaseModel):
    wallet_id: UUID
    episode_id: UUID
    balance: str
    reserved_quote: str | None
    available_quote: str | None
    base_balances: list[BaseBalanceView]
    source_availability: Literal["READY", "UNKNOWN"]
    revision: int


class PaperTradeView(BaseModel):
    market_observed_at: str | None = None
    mode: Literal["PAPER"]
    wallet: TradeWalletView | None
    account_use: Literal["MANUAL", "BOT"] | None
    base: str | None
    quote: Literal["USDT"]
    catalog_revision: int | None
    snapshot_at: str
    admission_ready: bool
    admission_reasons: list[str]


class PaperOrderView(BaseModel):
    order_id: UUID
    wallet_id: UUID
    episode_id: UUID
    sequence: int
    mode: Literal["PAPER"]
    base: str
    quote: Literal["USDT"]
    side: Literal["BUY", "SELL"]
    kind: Literal["MARKET", "LIMIT"]
    status: str
    quantity: str | None
    quote_budget: str | None
    limit_price: str | None
    time_in_force: Literal["GTC"] | None
    failure_code: str | None
    filled_quantity: str
    spent: str
    remaining_quantity: str | None
    remaining_budget: str | None
    reserved_quote: str
    reserved_base: str
    accepted_at: str
    snapshot_at: str


class PaperOrderPage(BaseModel):
    orders: list[PaperOrderView]
    snapshot_at: str
    next_cursor: str | None


class ManualOrderRefusal(BaseModel):
    detail: str
