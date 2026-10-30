"""Financial markers share the owner's existing transaction and publication fence."""

import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

from tiewtrade.core.money import MoneyError
from tiewtrade.core.orders import TradingMode
from tiewtrade.core.positions import PositionError
from tiewtrade.core.risk_limits import (
    RiskEvaluation,
    RiskInputError,
    RiskReason,
    RiskScope,
)
from tiewtrade.infra.db.errors import InfraError
from tiewtrade.infra.db.session import UserSession, require_user_session
from tiewtrade.infra.risk_limits.dispatch import lock_risk_owner

_LOGGER = logging.getLogger(__name__)


async def financial_snapshot(session: UserSession, episode_id: UUID) -> dict[str, object]:
    """Exact source references and amounts, including closed/delisted pair rows.

    Amounts are text before JSON encoding so the driver cannot round through float.
    The marker is evidence for replay, never a substitute for F-14 completeness checks.
    """
    row = (
        await session.execute(
            """SELECT jsonb_build_object(
          'episode_id',a.episode_id,'wallet_id',a.wallet_id,'availability',a.availability,
          'source_sequence',a.source_sequence,'revision',a.revision,'source_proof',a.source_proof,
          'positions',coalesce((SELECT jsonb_agg(jsonb_build_object(
            'base',p.base,'quote',p.quote,'held_quantity',p.held_quantity::text,
            'total_cost',p.total_cost::text,'realized_pnl',p.realized_pnl::text,
            'last_sequence',p.last_sequence,'revision',p.revision) ORDER BY p.base,p.quote)
            FROM paper_position_projections p WHERE p.episode_id=a.episode_id),'[]'::jsonb),
          'event_count',(SELECT count(*) FROM paper_position_events e
            WHERE e.episode_id=a.episode_id),
          'ledger_count',(SELECT count(*) FROM paper_wallet_ledger l
            WHERE l.episode_id=a.episode_id)
        ) FROM paper_position_activity a WHERE a.episode_id=:episode""",
            {"episode": episode_id},
        )
    ).scalar_one_or_none()
    return {} if row is None else dict(row)


@asynccontextmanager
async def financial_boundary(
    session: UserSession,
    *,
    episode_id: UUID,
    kind: str,
    after_episode_id: UUID | None = None,
) -> AsyncIterator[None]:
    checked = require_user_session(session)
    if kind not in {"INIT", "FILL", "CORRECTION", "RESET", "EPISODE", "SETTING"}:
        raise RiskInputError("invalid financial boundary kind")
    await lock_risk_owner(checked, TradingMode.PAPER)
    managed = (
        await checked.execute(
            """SELECT e.wallet_id FROM paper_wallet_episodes e
        CROSS JOIN risk_protocol_control c
        WHERE e.id=:episode AND c.publication_enabled""",
            {"episode": episode_id},
        )
    ).scalar_one_or_none()
    if managed is None:
        yield
        return
    previous = (
        await checked.execute(
            "SELECT nullif(current_setting('tiewtrade.risk_boundary_id',true),'')"
        )
    ).scalar_one_or_none()
    if previous is not None:
        valid = (
            await checked.execute(
                """SELECT 1 FROM risk_boundary_claims WHERE id=CAST(:id AS uuid)
            AND wallet_id=:wallet AND (episode_id=:episode OR after_episode_id=:episode)
            AND transaction_id=pg_current_xact_id()::text AND NOT finalized""",
                {"id": previous, "wallet": managed, "episode": episode_id},
            )
        ).first()
        if valid is None:
            raise RiskInputError("nested financial boundary scope mismatch")
        yield
        return
    watermark = (await checked.execute("SELECT risk_financial_fence()")).scalar_one()
    before = await financial_snapshot(checked, episode_id)
    identity = uuid4()
    params = {
        "id": identity,
        "owner": checked.user_id,
        "wallet": managed,
        "episode": episode_id,
        "after_episode": after_episode_id,
        "kind": kind,
        "watermark": watermark,
        "before": json.dumps(before),
    }
    await checked.execute(
        """INSERT INTO risk_boundary_claims
        (id,user_id,mode,wallet_id,episode_id,after_episode_id,kind,price_watermark,before_state)
        VALUES(:id,:owner,'PAPER',:wallet,:episode,:after_episode,:kind,:watermark,
          CAST(:before AS jsonb))""",
        params,
    )
    await checked.execute(
        "SELECT set_config('tiewtrade.risk_boundary_id',:id,true)",
        {"id": str(identity)},
    )
    yield
    after = await financial_snapshot(checked, after_episode_id or episode_id)
    await checked.execute(
        """INSERT INTO risk_financial_boundaries
        (id,user_id,mode,wallet_id,episode_id,after_episode_id,kind,price_watermark,
          before_state,after_state,replay_pending)
        VALUES(:id,:owner,'PAPER',:wallet,:episode,:after_episode,:kind,:watermark,
          CAST(:before AS jsonb),CAST(:after AS jsonb),true)""",
        {**params, "after": json.dumps(after)},
    )
    await checked.execute("UPDATE risk_boundary_claims SET finalized=true WHERE id=:id", params)
    # Risk replay failure never turns an authoritative bounded SELL into an
    # opening, and never rolls back its money merely because the cursor lags.
    await checked.execute(
        """UPDATE risk_owner_state SET replay_pending=true,due_at=clock_timestamp()
        WHERE mode='PAPER'"""
    )
    await checked.execute("SELECT set_config('tiewtrade.risk_boundary_id','',true)")
    # Evaluate the complete financial marker in this same commit when possible.
    # Imports are local because the existing F14 writer calls this boundary too.
    from tiewtrade.infra.risk_limits.monitor import replay_monitor
    from tiewtrade.infra.risk_limits.storage import read_setting

    scope = RiskScope(
        UUID(str(checked.user_id)),
        TradingMode.PAPER,
        UUID(str(managed)),
        UUID(str(after_episode_id or episode_id)),
    )
    setting = await read_setting(checked, scope)
    if setting.limit is not None:
        previous_timeout = (await checked.execute("SHOW statement_timeout")).scalar_one()
        await checked.execute("SAVEPOINT optional_risk_replay")
        try:
            await checked.execute("SET LOCAL statement_timeout='100ms'")
            await replay_monitor(checked, setting)
        except (InfraError, MoneyError, PositionError, ValueError, KeyError, TypeError):
            await checked.execute("ROLLBACK TO SAVEPOINT optional_risk_replay")
            _LOGGER.warning("derived risk replay deferred boundary=%s", identity)
            from tiewtrade.infra.risk_limits.monitor import persist_evaluation

            setting = await read_setting(checked, scope)
            now = (await checked.execute("SELECT clock_timestamp()")).scalar_one()
            evaluation = RiskEvaluation(
                scope,
                setting.revision,
                int(str(after.get("revision", 0))),
                now,
                RiskReason.SOURCE_UNAVAILABLE,
                None,
                setting.latched,
                False,
            )
            await persist_evaluation(
                checked, setting, evaluation, watermark=int(watermark), replay_pending=True
            )
            await checked.execute("""UPDATE risk_owner_state SET replay_pending=true,
              due_at=clock_timestamp() WHERE mode='PAPER'""")
        finally:
            await checked.execute("RELEASE SAVEPOINT optional_risk_replay")
            await checked.execute(
                "SELECT set_config('statement_timeout',:previous,true)",
                {"previous": previous_timeout},
            )
