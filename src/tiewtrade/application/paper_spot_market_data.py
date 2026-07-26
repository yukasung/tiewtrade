from datetime import datetime

from tiewtrade.application.paper_spot_session import (
    PaperSpotSession,
    PaperSpotSessionSnapshot,
)
from tiewtrade.market_data.candle import Candle


class PaperSpotMarketDataSink:
    def __init__(self, session: PaperSpotSession) -> None:
        self._session = session
        self.last_snapshot: PaperSpotSessionSnapshot | None = None
        self.live_candle_count = 0

    async def warm_up(
        self,
        candles: tuple[Candle, ...],
        *,
        received_at: datetime,
    ) -> None:
        self._session.warm_up_completed_candles(
            candles,
            received_at=received_at,
        )

    async def process_completed(
        self,
        candle: Candle,
        *,
        received_at: datetime,
    ) -> None:
        self.last_snapshot = self._session.process_completed_candle(
            candle,
            received_at=received_at,
        )
        self.live_candle_count += 1
