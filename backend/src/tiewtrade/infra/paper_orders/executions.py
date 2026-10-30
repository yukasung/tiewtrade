"""Session-bound F-14/cash linkage; the order transition caller owns the transaction."""

import json
from datetime import timedelta
from uuid import UUID, uuid4

from tiewtrade.core.money import Money, MoneyError, Quantity
from tiewtrade.core.orders import OrderConflictError, standard_execution_fee
from tiewtrade.core.positions import ExecutionFact, ExecutionSide, PositionAvailability
from tiewtrade.infra.db import money_from_columns, money_to_columns, quantity_from_columns
from tiewtrade.infra.db.session import UserSession, require_user_session
from tiewtrade.infra.market_data.order_book_codec import canonical
from tiewtrade.infra.market_data.order_book_storage import read_inputs
from tiewtrade.infra.paper_orders.initialization import enable_financial_writer
from tiewtrade.infra.paper_orders.storage import (
    increment_wallet_revision,
    lock_active_episode,
    lock_episode,
    read_execution_inputs,
)
from tiewtrade.infra.paper_wallet import get_wallet
from tiewtrade.infra.positions import (
    PositionEventKind,
    PositionWriteResult,
    PositionWriteStatus,
    apply_position_event,
)
from tiewtrade.infra.risk_limits.boundaries import financial_boundary


def execution_payload(fact: ExecutionFact) -> dict[str, object]:
    """Exact event payload shared by the order writer and its financial linkage check."""
    fee = None
    if fact.fee is not None:
        fee = fact.fee.amount.as_parts()
    return {
        "execution_id": str(fact.execution_id),
        "base": fact.pair.base,
        "quote": fact.pair.quote,
        "side": fact.side.value,
        "quantity": fact.gross_quantity.as_parts(),
        "quote_amount": fact.quote_amount.as_parts(),
        "fee": fee,
        "source_sequence": fact.source_sequence,
        "occurred_at": fact.occurred_at.isoformat(),
    }


async def stage_fill_cash(
    session: UserSession,
    *,
    wallet_id: UUID,
    episode_id: UUID,
    order_event_id: UUID,
    position_event_id: UUID,
    fact: ExecutionFact,
) -> PositionWriteResult:
    async with financial_boundary(session, episode_id=episode_id, kind="FILL"):
        return await _stage_fill_cash(
            session,
            wallet_id=wallet_id,
            episode_id=episode_id,
            order_event_id=order_event_id,
            position_event_id=position_event_id,
            fact=fact,
        )


async def _stage_fill_cash(
    session: UserSession,
    *,
    wallet_id: UUID,
    episode_id: UUID,
    order_event_id: UUID,
    position_event_id: UUID,
    fact: ExecutionFact,
) -> PositionWriteResult:
    """Link one immutable FILL to F-14 and exact cash; commit with the order transition.

    Requires its full source evidence and order event staged in the same transaction.
    This helper does not complete a command or update the caller's order/reservation projection.
    """
    session = require_user_session(session)
    await lock_episode(session, wallet_id, episode_id, require_active=False)
    await enable_financial_writer(session)
    source = (
        (
            await session.execute(
                """SELECT e.*,o.wallet_id,o.side,o.accepted_at,o.budget,o.quantity,
                   i.digest AS evidence_digest,i.source_digest,i.input_id,i.generation,
                   a.availability,init.position_proof,pa.source_proof AS live_position_proof
                FROM paper_order_events e JOIN paper_orders o ON o.id=e.order_id
                JOIN paper_execution_inputs i
                  ON (i.recorded_at,i.id)=(e.input_recorded_at,e.input_evidence_id)
                JOIN paper_order_activity a ON a.episode_id=e.episode_id
                JOIN paper_order_initializations init ON init.episode_id=e.episode_id
                JOIN paper_position_activity pa ON pa.episode_id=e.episode_id
                WHERE e.id=:event AND e.episode_id=:episode AND e.event_kind='FILL'""",
                {"event": order_event_id, "episode": episode_id},
            )
        )
        .mappings()
        .one_or_none()
    )
    if (
        source is None
        or source["wallet_id"] != wallet_id
        or (source["execution_id"], source["base"], source["quote"], source["side"])
        != (fact.execution_id, fact.pair.base, fact.pair.quote, fact.side.value)
    ):
        raise OrderConflictError("fill scope or execution identity mismatch")

    payload = (
        json.loads(source["payload"]) if isinstance(source["payload"], str) else source["payload"]
    )
    if canonical(payload) != canonical({"execution": execution_payload(fact)}):
        raise OrderConflictError("immutable order fill does not match financial execution")
    if source["occurred_at"] != fact.occurred_at:
        raise OrderConflictError("fill execution time mismatch")
    if source["live_position_proof"] != source["position_proof"]:
        raise OrderConflictError("position baseline proof changed")
    evidence = await read_execution_inputs(
        session,
        episode_id=episode_id,
        pair=fact.pair,
        after_input_id=source["input_id"] - 1,
        limit=1,
    )
    if not evidence or (evidence[0].evidence_id, evidence[0].recorded_at, evidence[0].digest) != (
        source["input_evidence_id"],
        source["input_recorded_at"],
        source["evidence_digest"],
    ):
        raise OrderConflictError("private execution evidence is missing or inconsistent")
    projection = (
        await session.execute(
            """SELECT filled_quantity,spent,last_event_id FROM paper_order_projections
            WHERE order_id=:order""",
            {"order": source["order_id"]},
        )
    ).first()
    if projection is None:
        rows = (
            await session.execute(
                """SELECT payload FROM paper_order_events
                WHERE order_id=:order AND event_kind='FILL'""",
                {"order": source["order_id"]},
            )
        ).all()
        gross = Quantity.of(0, fact.pair.base)
        spent = Money.of(0, fact.pair.quote)
    else:
        rows = (
            await session.execute(
                """SELECT e.payload FROM paper_order_events e
                WHERE e.order_id=:order AND e.event_kind='FILL'
                  AND e.sequence>(SELECT sequence FROM paper_order_events
                                  WHERE id=:checkpoint)""",
                {"order": source["order_id"], "checkpoint": projection.last_event_id},
            )
        ).all()
        gross = quantity_from_columns(projection.filled_quantity, fact.pair.base)
        spent = money_from_columns(projection.spent, fact.pair.quote)
    try:
        for row in rows:
            content = json.loads(row.payload) if isinstance(row.payload, str) else row.payload
            execution = content["execution"]
            quantity, quote = execution["quantity"], execution["quote_amount"]
            q = Quantity.of(quantity["quantity"], quantity["asset"])
            m = Money.of(quote["amount"], quote["currency"])
            if q.amount <= 0 or m.amount <= 0 or execution["side"] != fact.side.value:
                raise OrderConflictError("invalid cumulative fill")
            gross, spent = gross + q, spent + m
    except (KeyError, TypeError, ValueError, MoneyError):
        raise OrderConflictError("order fill history is invalid") from None
    if (
        source["budget"] is not None
        and spent > money_from_columns(source["budget"], fact.pair.quote)
    ) or (
        source["quantity"] is not None
        and gross > quantity_from_columns(source["quantity"], fact.pair.base)
    ):
        raise OrderConflictError("cumulative fills exceed the immutable order size")
    # A completed linkage can replay after source expiry, without another economic write.
    prior = (
        (
            await session.execute(
                """SELECT l.*,w.amount,w.currency FROM paper_execution_links l
                LEFT JOIN paper_wallet_ledger w ON w.source_position_event_id=l.position_event_id
                WHERE l.user_id=:user AND l.episode_id=:episode AND l.execution_id=:execution
                  AND l.position_event_kind='RECORD'""",
                {"user": session.user_id, "episode": episode_id, "execution": fact.execution_id},
            )
        )
        .mappings()
        .one_or_none()
    )
    if prior is not None:
        if (
            prior["order_event_id"] != order_event_id
            or prior["position_event_id"] != position_event_id
        ):
            raise OrderConflictError("economic source identity conflict")
        result = await apply_position_event(
            session, episode_id, position_event_id, PositionEventKind.RECORD, fact
        )
        zero_cash = (
            fact.side is ExecutionSide.SELL
            and fact.fee is not None
            and fact.fee.amount == fact.quote_amount
        )
        if result.status is not PositionWriteStatus.REPLAYED or (
            (prior["amount"] is None) != zero_cash
        ):
            raise OrderConflictError("economic linkage replay is incomplete")
        return result
    await lock_active_episode(session, wallet_id, episode_id)
    if source["availability"] != "READY":
        raise OrderConflictError("order source is not ready")
    records = await read_inputs(session, fact.pair, after=source["input_id"] - 1, limit=1)
    if not records or records[0].digest != source["source_digest"]:
        raise OrderConflictError("execution input is unavailable or changed")
    market = records[0].market
    if market.generation != source["generation"] or (
        market.received_at <= source["accepted_at"] + timedelta(milliseconds=100)
        or fact.occurred_at != market.received_at
    ):
        raise OrderConflictError("execution input is not eligible")
    # STANDARD_V1 fees are paid in the received asset, exactly as the matcher emits.
    if fact.fee != standard_execution_fee(fact.side, fact.gross_quantity, fact.quote_amount):
        raise OrderConflictError("fill fee asset disagrees with the pinned profile")
    wallet = await get_wallet(session)
    if wallet is None:
        raise OrderConflictError("wallet unavailable")
    result = await apply_position_event(
        session, episode_id, position_event_id, PositionEventKind.RECORD, fact
    )
    if result.status is PositionWriteStatus.CONFLICTED:
        await session.execute(
            """UPDATE paper_order_activity SET availability='CONFLICTED',revision=revision+1,
            failure_code=:failure,observed_at=clock_timestamp() WHERE episode_id=:episode""",
            {"episode": episode_id, "failure": result.failure_code},
        )
        await increment_wallet_revision(session, wallet_id)
        return result
    if result.status is not PositionWriteStatus.APPLIED or result.effects is None:
        raise OrderConflictError("position replay has no matching cash linkage")
    if result.activity.availability is not PositionAvailability.READY:
        raise OrderConflictError("position source is not ready")
    delta = result.effects.quote_cash_delta
    if (wallet.balance + delta).amount < 0:
        raise OrderConflictError("invalid quote cash effect")
    await session.execute(
        """INSERT INTO paper_execution_links
        (position_event_id,user_id,episode_id,base,quote,order_id,order_event_id,execution_id,
         position_event_kind,cash_kind)
        VALUES(:position,:user,:episode,:base,:quote,:order,:event,:execution,'RECORD','TRADE_CASH')""",
        {
            "position": position_event_id,
            "user": session.user_id,
            "episode": episode_id,
            "base": fact.pair.base,
            "quote": fact.pair.quote,
            "order": source["order_id"],
            "event": order_event_id,
            "execution": fact.execution_id,
        },
    )
    amount, currency = money_to_columns(delta)
    if delta.amount != 0:
        await session.execute(
            """INSERT INTO paper_wallet_ledger
        (id,user_id,wallet_id,episode_id,kind,amount,currency,source_position_event_id)
        VALUES(:id,:user,:wallet,:episode,'TRADE_CASH',:amount,:currency,:position)""",
            {
                "id": uuid4(),
                "user": session.user_id,
                "wallet": wallet_id,
                "episode": episode_id,
                "amount": amount,
                "currency": currency,
                "position": position_event_id,
            },
        )
    await increment_wallet_revision(session, wallet_id)
    return result


async def stage_correction_cash(
    session: UserSession,
    *,
    wallet_id: UUID,
    episode_id: UUID,
    order_event_id: UUID,
    correction_event_id: UUID,
    supersedes_position_event_id: UUID,
    kind: PositionEventKind,
    fact: ExecutionFact,
) -> PositionWriteResult:
    async with financial_boundary(session, episode_id=episode_id, kind="CORRECTION"):
        return await _stage_correction_cash(
            session,
            wallet_id=wallet_id,
            episode_id=episode_id,
            order_event_id=order_event_id,
            correction_event_id=correction_event_id,
            supersedes_position_event_id=supersedes_position_event_id,
            kind=kind,
            fact=fact,
        )


async def _stage_correction_cash(
    session: UserSession,
    *,
    wallet_id: UUID,
    episode_id: UUID,
    order_event_id: UUID,
    correction_event_id: UUID,
    supersedes_position_event_id: UUID,
    kind: PositionEventKind,
    fact: ExecutionFact,
) -> PositionWriteResult:
    """Stage one F-14 REPLACE/VOID and its exact compensating quote-cash effect."""
    session = require_user_session(session)
    if kind not in (PositionEventKind.REPLACE, PositionEventKind.VOID):
        raise OrderConflictError("correction kind required")
    await lock_episode(session, wallet_id, episode_id, require_active=False)
    await enable_financial_writer(session)
    source = (
        (
            await session.execute(
                """SELECT l.*,e.execution_id AS order_execution_id
                FROM paper_execution_links l JOIN paper_order_events e ON e.id=l.order_event_id
                WHERE l.position_event_id=:target AND l.episode_id=:episode""",
                {"target": supersedes_position_event_id, "episode": episode_id},
            )
        )
        .mappings()
        .one_or_none()
    )
    if (
        source is None
        or source["order_event_id"] != order_event_id
        or source["execution_id"] != fact.execution_id
        or source["order_execution_id"] != fact.execution_id
        or (source["base"], source["quote"]) != (fact.pair.base, fact.pair.quote)
    ):
        raise OrderConflictError("correction does not identify an original order fill")
    prior = (
        (
            await session.execute(
                """SELECT l.*,w.amount,w.currency FROM paper_execution_links l
                LEFT JOIN paper_wallet_ledger w ON w.source_position_event_id=l.position_event_id
                WHERE l.position_event_id=:event""",
                {"event": correction_event_id},
            )
        )
        .mappings()
        .one_or_none()
    )
    if prior is None:
        await lock_active_episode(session, wallet_id, episode_id)
    result = await apply_position_event(
        session,
        episode_id,
        correction_event_id,
        kind,
        fact,
        supersedes_position_event_id,
    )
    if prior is not None:
        if (
            result.status is not PositionWriteStatus.REPLAYED
            or prior["order_event_id"] != order_event_id
            or prior["position_event_kind"] != kind.value
        ):
            raise OrderConflictError("correction replay linkage mismatch")
        return result
    if result.status is not PositionWriteStatus.APPLIED or result.effects is None:
        return result
    wallet = await get_wallet(session)
    if wallet is None or (wallet.balance + result.effects.quote_cash_delta).amount < 0:
        raise OrderConflictError("invalid correction quote cash effect")
    await session.execute(
        """INSERT INTO paper_execution_links
        (position_event_id,user_id,episode_id,base,quote,order_id,order_event_id,execution_id,
         position_event_kind,cash_kind)
        VALUES(:position,:user,:episode,:base,:quote,:order,:event,:execution,
               :kind,'CORRECTION_CASH')""",
        {
            "position": correction_event_id,
            "user": session.user_id,
            "episode": episode_id,
            "base": fact.pair.base,
            "quote": fact.pair.quote,
            "order": source["order_id"],
            "event": order_event_id,
            "execution": fact.execution_id,
            "kind": kind.value,
        },
    )
    delta = result.effects.quote_cash_delta
    if delta.amount != 0:
        amount, currency = money_to_columns(delta)
        await session.execute(
            """INSERT INTO paper_wallet_ledger
            (id,user_id,wallet_id,episode_id,kind,amount,currency,source_position_event_id)
            VALUES(:id,:user,:wallet,:episode,'CORRECTION_CASH',:amount,:currency,:position)""",
            {
                "id": uuid4(),
                "user": session.user_id,
                "wallet": wallet_id,
                "episode": episode_id,
                "amount": amount,
                "currency": currency,
                "position": correction_event_id,
            },
        )
    await increment_wallet_revision(session, wallet_id)
    return result
