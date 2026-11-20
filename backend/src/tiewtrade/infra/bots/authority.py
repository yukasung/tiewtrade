"""Paper order lineage checks executed under the existing owner lock."""

from enum import StrEnum
from uuid import UUID

from tiewtrade.infra.db.session import UserSession, require_user_session


class BotOrderAuthority(StrEnum):
    UNLINKED = "UNLINKED"
    BLOCKED = "BLOCKED"
    READY = "READY"


async def blocked_paper_openings(
    session: UserSession, *, episode_id: UUID, order_ids: tuple[UUID, ...]
) -> frozenset[UUID]:
    """Fence all BOT buys in a shared matcher, including another command's orders."""
    checked = require_user_session(session)
    if not order_ids:
        return frozenset()
    rows = await checked.execute(
        """SELECT o.id FROM paper_orders o
           LEFT JOIN bot_order_links b ON b.command_id=o.command_id AND b.order_id=o.id
             AND b.user_id=o.user_id AND b.episode_id=o.episode_id AND b.mode='PAPER'
           LEFT JOIN bot_runs r ON r.id=b.run_id AND r.user_id=b.user_id AND r.mode=b.mode
           LEFT JOIN user_trading_preferences p ON p.user_id=o.user_id
           LEFT JOIN paper_wallet_state w ON w.user_id=o.user_id AND w.wallet_id=r.wallet_id
           WHERE o.user_id=:owner AND o.episode_id=:episode AND o.id=ANY(:orders)
             AND o.origin='BOT'
             AND (r.status='RUNNING' AND p.use='BOT'
                  AND w.active_episode_id=r.episode_id) IS NOT TRUE""",
        {"owner": checked.user_id, "episode": episode_id, "orders": list(order_ids)},
    )
    return frozenset(UUID(str(row.id)) for row in rows)


async def paper_bot_authority(
    session: UserSession, *, command_id: UUID, episode_id: UUID
) -> BotOrderAuthority:
    """Check linked authority while the parent worker holds the owner lock."""
    checked = require_user_session(session)
    row = (
        await checked.execute(
            """SELECT (r.status='RUNNING' AND u.use='BOT'
                        AND s.active_episode_id=r.episode_id) IS TRUE AS ready
              FROM bot_order_links b
              JOIN bot_runs r ON (r.id,r.user_id,r.mode,r.episode_id)=
                                  (b.run_id,b.user_id,b.mode,b.episode_id)
              LEFT JOIN user_trading_preferences u ON u.user_id=b.user_id
              LEFT JOIN paper_wallet_state s ON s.user_id=b.user_id AND s.wallet_id=r.wallet_id
              WHERE b.command_id=:command AND b.user_id=:owner
                AND b.episode_id=:episode AND b.mode='PAPER'""",
            {"command": command_id, "owner": checked.user_id, "episode": episode_id},
        )
    ).one_or_none()
    if row is None:
        return BotOrderAuthority.UNLINKED
    return BotOrderAuthority.READY if row.ready else BotOrderAuthority.BLOCKED
