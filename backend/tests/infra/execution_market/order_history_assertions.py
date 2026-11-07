"""Pin the pre-NC12§13 terminal lookup as an independent equivalence oracle."""

from uuid import UUID

from tiewtrade.core.orders import OrderState
from tiewtrade.infra.db.session import UserSession
from tiewtrade.infra.paper_orders.codec import order_from_payload
from tiewtrade.infra.paper_orders.matching_storage import load_order_state


async def assert_terminal_history(session: UserSession, order_id: UUID) -> OrderState:
    # Keep this reference query unchanged: it proves the optimized lookup's payload,
    # including precision, provenance and the latest correction, matches its predecessor.
    original = (
        await session.execute(
            """SELECT terminal.value FROM paper_orders o
            JOIN paper_order_events e ON e.episode_id=o.episode_id
              AND e.base=o.base AND e.quote=o.quote
            CROSS JOIN LATERAL jsonb_array_elements(e.payload->'terminal_orders') terminal(value)
            WHERE o.id=:order AND e.payload ? 'matching'
              AND terminal.value->'intent'->>'order_id'=CAST(:order AS text)
            ORDER BY ((e.payload->>'decision_sequence')::bigint) DESC LIMIT 1""",
            {"order": order_id},
        )
    ).scalar_one()
    assert original is not None
    current = await load_order_state(session, order_id)
    assert current == order_from_payload(original)
    return current
