"""Transaction scope and snapshot source proof; no financial arithmetic."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from tiewtrade.infra.db.session import MarketDataSession, require_market_data_session


async def source_write_timeouts(session: MarketDataSession) -> None:
    """Bound lock/query waits for this transaction, including scope acquisition."""
    session = require_market_data_session(session)
    await session.execute("""SELECT set_config('lock_timeout','200ms',true),
        set_config('statement_timeout','500ms',true)""")


async def begin_source_write(session: MarketDataSession) -> None:
    session = require_market_data_session(session)
    await source_write_timeouts(session)
    await session.execute("SELECT public.begin_indicator_source_write()")


async def require_source_write(session: MarketDataSession) -> None:
    session = require_market_data_session(session)
    # Expand stage deliberately permits legacy writers. Strict activation rejects
    # missing scopes; this check never acquires a guard after caller row locks.
    await session.execute("""SELECT CASE WHEN source_proof_state='READY'
        THEN public.require_indicator_source_write() END
        FROM public.indicator_rollout_control WHERE id=1""")


@dataclass(frozen=True, slots=True)
class SourceFence:
    epoch: UUID
    revision: int


PROOF_SQL = """SELECT g.epoch=:epoch AND g.journal_floor<=:fence
    AND g.revision>=:fence AND c.source_proof_state='READY'
    AND public.indicator_source_triggers_valid()
    AND NOT EXISTS (SELECT 1 FROM public.indicator_source_changes e
      WHERE e.epoch=g.epoch AND e.revision>:fence
      AND (e.kind='RESET' OR
        (e.source=:source AND e.base=:base AND e.quote=:quote AND e.timeframe=:timeframe
          AND e.open_at>=:start AND e.open_at<:end))) AS valid
    FROM public.indicator_source_guard g CROSS JOIN public.indicator_rollout_control c
    WHERE g.id=1 AND c.id=1"""


def proof_parameters(
    fence: SourceFence,
    *,
    source: str,
    base: str,
    quote: str,
    timeframe: str,
    start: datetime,
    end: datetime,
) -> dict[str, object]:
    return {
        "epoch": fence.epoch,
        "fence": fence.revision,
        "source": source,
        "base": base,
        "quote": quote,
        "timeframe": timeframe,
        "start": start,
        "end": end,
    }
