"""Generation-bound display checks never select a newer prepared head."""

from datetime import datetime
from typing import Literal

from tiewtrade.infra.crypto.indicator_cursor import PreparedCursorClaims
from tiewtrade.infra.db.session import UserSession
from tiewtrade.infra.indicators.codec import CODEC_VERSION
from tiewtrade.infra.indicators.prepared import proof_valid, rollout_control
from tiewtrade.infra.market_data.indicator_reader import query_budget


async def verify_prepared(
    session: UserSession,
    claims: PreparedCursorClaims,
    now: datetime,
    deadline: float,
) -> Literal["MATCHED", "CHANGED", "UNVERIFIABLE"]:
    control = await rollout_control(session, deadline)
    if control["mode"] != "PREPARED" or control["rollout_epoch"] != claims.rollout_epoch:
        return "CHANGED"
    if (
        control["source_proof_state"] != "READY"
        or control["protocol_version"] != 1
        or control["codec_version"] != CODEC_VERSION
        or control["retention_policy"] != "GRACE"
    ):
        return "UNVERIFIABLE"
    await query_budget(session, deadline)
    generation = (
        (
            await session.execute(
                "SELECT * FROM indicator_ready_generations WHERE id=:id",
                {"id": claims.generation_id},
            )
        )
        .mappings()
        .first()
    )
    if generation is None:
        return "UNVERIFIABLE"
    for name in (
        "source",
        "base",
        "quote",
        "formula_version",
        "dataset_revision",
        "as_of",
        "calculation_start",
        "calculation_end",
    ):
        if generation[name] != getattr(claims, name):
            return "CHANGED"
    if generation["timeframe"] != claims.timeframe.value or generation["expires_at"] <= now:
        return "CHANGED"
    await query_budget(session, deadline)
    guard = (
        (
            await session.execute("""SELECT epoch,journal_floor,revision,
      public.indicator_source_triggers_valid() AS triggers_valid
      FROM indicator_source_guard WHERE id=1""")
        )
        .mappings()
        .first()
    )
    if guard is None or not guard["triggers_valid"] or generation["codec_version"] != CODEC_VERSION:
        return "UNVERIFIABLE"
    if guard["epoch"] != generation["source_epoch"]:
        return "CHANGED"
    if not guard["journal_floor"] <= generation["source_fence"] <= guard["revision"]:
        return "UNVERIFIABLE"
    await query_budget(session, deadline)
    return "MATCHED" if await proof_valid(session, generation, now) else "CHANGED"
