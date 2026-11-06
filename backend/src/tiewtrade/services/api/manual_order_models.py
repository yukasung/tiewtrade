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


class ProtectionPricesInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    take_profit_price: AmountText | None = None
    stop_loss_price: AmountText | None = None

    @model_validator(mode="after")
    def one_leg(self) -> Self:
        if self.take_profit_price is None and self.stop_loss_price is None:
            raise ValueError("at least one protection leg required")
        return self


class ManualProtectionAllocationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    protection_id: UUID
    expected_revision: Annotated[int, Field(strict=True, ge=1)]
    quantity: AmountText


class _NewOrderBase(ExpectedPaperEpisode):
    base: Annotated[StrictStr, Field(pattern=r"^[A-Z][A-Z0-9]{0,19}$")]
    quote: Literal["USDT"]
    protection: ProtectionPricesInput | None = None
    protection_allocations: tuple[ManualProtectionAllocationInput, ...] = Field(
        default_factory=tuple
    )

    @model_validator(mode="after")
    def distinct_assets(self) -> Self:
        if self.base == self.quote:
            raise ValueError("base and quote must differ")
        if self.protection is not None and getattr(self, "side", None) != "BUY":
            raise ValueError("bracket requires a BUY entry")
        if self.protection_allocations and getattr(self, "side", None) != "SELL":
            raise ValueError("protection allocations require a SELL")
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
    protection: ProtectionPricesInput | None = None
    protection_allocations: tuple[ManualProtectionAllocationInput, ...] = Field(
        default_factory=tuple
    )
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
    protection_allocated: str | None = None
    asset: str
    held: str
    reserved: str
    available: str | None


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
    protection_enabled: bool = False
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


def manual_attachments(
    body: NewOrderInput,
) -> tuple[dict[str, object] | None, tuple[dict[str, object], ...]]:
    from tiewtrade.core.protections import ProtectionPrices

    price = body.protection
    bracket: dict[str, object] | None = None
    if price is not None:
        prices = ProtectionPrices(
            PositionPair(body.base, body.quote),
            None
            if price.take_profit_price is None
            else Money.of(price.take_profit_price, body.quote),
            None if price.stop_loss_price is None else Money.of(price.stop_loss_price, body.quote),
        )
        bracket = {
            "tp": None if prices.take_profit is None else prices.take_profit.as_parts()["amount"],
            "sl": None if prices.stop_loss is None else prices.stop_loss.as_parts()["amount"],
        }
    allocations = tuple(
        {
            "protection_id": str(v.protection_id),
            "expected_revision": v.expected_revision,
            "quantity": Quantity.of(v.quantity, body.base).as_parts()["quantity"],
        }
        for v in body.protection_allocations
    )
    return bracket, allocations
