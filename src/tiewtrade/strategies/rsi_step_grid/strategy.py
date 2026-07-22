from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
from uuid import UUID

from tiewtrade.market_data.candle import Candle
from tiewtrade.strategies.rsi_step_grid.indicators import IndicatorSnapshot
from tiewtrade.strategies.rsi_step_grid.preset import RsiStepGridPreset


@dataclass(frozen=True, slots=True)
class EntryIntent:
    intent_id: str
    session_id: UUID
    preset_version: str
    entry_number: int
    signal_candle: Candle
    atr: Decimal


class RsiStepGridStrategy:
    def __init__(self, session_id: UUID, preset: RsiStepGridPreset) -> None:
        self._session_id = session_id
        self._preset = preset
        self._reset_close: Decimal | None = None
        self._pending_intent: EntryIntent | None = None

    def evaluate(
        self,
        candle: Candle,
        indicators: IndicatorSnapshot,
        entry_number: int,
        can_enter: bool,
    ) -> EntryIntent | None:
        if entry_number <= 0:
            raise ValueError("entry_number must be positive")
        if self._pending_intent is not None:
            return None

        if indicators.rsi < self._preset.rsi_reset_threshold:
            self._reset_close = candle.close
            return None

        if (
            self._reset_close is None
            or indicators.rsi <= self._preset.rsi_entry_threshold
            or candle.close <= candle.open
            or candle.close <= self._reset_close
            or not can_enter
        ):
            return None

        intent = EntryIntent(
            intent_id=self._intent_id(candle, entry_number),
            session_id=self._session_id,
            preset_version=self._preset.version,
            entry_number=entry_number,
            signal_candle=candle,
            atr=indicators.atr,
        )
        self._pending_intent = intent
        return intent

    def on_entry_filled(self, intent_id: str) -> None:
        if self._pending_intent is None or self._pending_intent.intent_id != intent_id:
            raise ValueError("fill does not match pending intent")
        self._pending_intent = None
        self._reset_close = None

    def on_entry_rejected(self, intent_id: str) -> None:
        if self._pending_intent is None or self._pending_intent.intent_id != intent_id:
            raise ValueError("rejection does not match pending intent")
        self._pending_intent = None

    def _intent_id(self, candle: Candle, entry_number: int) -> str:
        identity = "\n".join(
            (
                str(self._session_id),
                self._preset.version,
                candle.symbol,
                candle.timeframe,
                candle.open_time.isoformat(),
                str(entry_number),
            )
        )
        return sha256(identity.encode("utf-8")).hexdigest()
