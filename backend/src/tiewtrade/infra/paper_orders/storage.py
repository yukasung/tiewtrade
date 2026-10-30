"""Paper replay evidence; financial admission and F-14 orchestration follow in M3."""

import hashlib
import json
from dataclasses import dataclass, replace
from typing import Any
from uuid import UUID

from tiewtrade.core.market_catalog import CatalogSnapshot
from tiewtrade.core.money import MoneyError
from tiewtrade.core.order_book import BookState, MarketInput
from tiewtrade.core.orders import OrderConflictError, SimulationProfile, SourceUnavailableError
from tiewtrade.core.positions import PositionPair
from tiewtrade.infra.db.session import UserSession, require_user_session
from tiewtrade.infra.market_data.order_book_codec import (
    canonical,
    input_from_payload,
    input_payload,
)
from tiewtrade.infra.market_data.order_book_storage import (
    StoredExecutionInput,
    metadata_from_payload,
    metadata_payload,
)
from tiewtrade.infra.paper_orders.records import SavedExecutionInput


@dataclass(frozen=True, slots=True)
class LockedPairCatalog:
    snapshot: CatalogSnapshot
    latest_removed_revision: int | None


async def lock_active_episode(session: UserSession, wallet_id: UUID, episode_id: UUID) -> None:
    await lock_episode(session, wallet_id, episode_id)


async def lock_episode(
    session: UserSession, wallet_id: UUID, episode_id: UUID, *, require_active: bool = True
) -> None:
    """Serialize owner work and validate episode ownership; closed episodes allow reads only."""
    session = require_user_session(session)
    await session.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(:key,0))",
        {"key": f"paper-wallet:{session.user_id}"},
    )
    row = (
        await session.execute(
            """SELECT 1 FROM paper_wallet_state s
      JOIN paper_wallet_episodes e ON e.wallet_id=s.wallet_id AND e.user_id=s.user_id
      WHERE s.wallet_id=:wallet AND s.user_id=:user AND e.id=:episode
      AND (NOT :require_active OR (s.active_episode_id=:episode
        AND NOT EXISTS(SELECT 1 FROM paper_wallet_episode_closures c WHERE c.episode_id=:episode)))
      FOR UPDATE OF s""",
            {
                "wallet": wallet_id,
                "user": session.user_id,
                "episode": episode_id,
                "require_active": require_active,
            },
        )
    ).first()
    if row is None:
        raise OrderConflictError("Paper episode is not active")


async def lock_pair_catalog(session: UserSession, pair: PositionPair) -> LockedPairCatalog:
    """Pin one pair fence after the wallet lock and hold it through transaction commit."""
    session = require_user_session(session)
    row = (
        await session.execute(
            "SELECT * FROM lock_supported_symbol_pair(:base,:quote)",
            {"base": pair.base, "quote": pair.quote},
        )
    ).one_or_none()
    if row is None or row.protocol_version != 1:
        raise SourceUnavailableError("supported-symbol pair fence is unavailable")
    return LockedPairCatalog(
        CatalogSnapshot(
            int(row.current_revision),
            frozenset({(pair.base, pair.quote)}) if row.status == "ACTIVE" else frozenset(),
        ),
        None if row.latest_removed_revision is None else int(row.latest_removed_revision),
    )


async def increment_wallet_revision(session: UserSession, wallet_id: UUID) -> None:
    """Advance the wallet snapshot revision inside the caller's transaction."""
    await session.execute(
        "UPDATE paper_wallet_state SET revision=revision+1 WHERE wallet_id=:wallet",
        {"wallet": wallet_id},
    )


async def pin_execution_profile(
    session: UserSession,
    *,
    wallet_id: UUID,
    episode_id: UUID,
    profile: SimulationProfile,
) -> None:
    """Pin policy, without claiming source initialization, completeness or READY."""
    await lock_active_episode(session, wallet_id, episode_id)
    params = {
        "user": session.user_id,
        "wallet": wallet_id,
        "episode": episode_id,
        "fee": profile.fee_version,
        "model": profile.liquidity_version,
    }
    await session.execute(
        """INSERT INTO paper_execution_profiles
      (episode_id,wallet_id,user_id,fee_version,model_version)
      VALUES(:episode,:wallet,:user,:fee,:model)
      ON CONFLICT(episode_id) DO NOTHING""",
        params,
    )
    row = (
        (
            await session.execute(
                """SELECT fee_version,model_version FROM paper_execution_profiles
                  WHERE episode_id=:episode""",
                params,
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None or (row["fee_version"], row["model_version"]) != (
        profile.fee_version,
        profile.liquidity_version,
    ):
        raise OrderConflictError("Paper policy already pinned differently")


def _source_digest(record: StoredExecutionInput) -> str:
    return hashlib.sha256(
        (input_payload(record.market) + "\n" + metadata_payload(record.metadata)).encode()
    ).hexdigest()


def _decode_checked(row: Any) -> SavedExecutionInput:
    payload = json.loads(row["payload"]) if isinstance(row["payload"], str) else row["payload"]
    if hashlib.sha256(canonical(payload).encode()).hexdigest() != row["digest"]:
        raise OrderConflictError("Paper evidence digest mismatch")
    market = input_from_payload(payload["market"])
    source_market = input_from_payload(payload.get("source_market", payload["market"]))
    metadata = metadata_from_payload(payload["metadata"])
    source = StoredExecutionInput(source_market, metadata, row["source_digest"])
    if _source_digest(source) != source.digest:
        raise OrderConflictError("Paper source evidence mismatch")
    if market != source_market and not (
        isinstance(market, BookState)
        and isinstance(source_market, BookState)
        and market == replace(source_market, rebase=True)
    ):
        raise OrderConflictError("Paper decision evidence changed source content")
    record = StoredExecutionInput(market, metadata, row["source_digest"])
    if (market.input_id, market.generation, market.pair) != (
        row["input_id"],
        row["generation"],
        PositionPair(row["base"], row["quote"]),
    ) or metadata.market.pair != market.pair:
        raise OrderConflictError("Paper evidence provenance mismatch")
    SimulationProfile(payload["fee_version"], payload["model_version"])
    return SavedExecutionInput(
        row["id"], row["recorded_at"], row["episode_id"], record, row["digest"]
    )


def _decode(row: Any) -> SavedExecutionInput:
    try:
        return _decode_checked(row)
    except (KeyError, TypeError, ValueError, MoneyError):
        raise OrderConflictError("Paper execution evidence is invalid") from None


async def append_execution_input(
    session: UserSession,
    *,
    wallet_id: UUID,
    episode_id: UUID,
    evidence_id: UUID,
    record: StoredExecutionInput,
    decision_market: MarketInput | None = None,
) -> SavedExecutionInput:
    """Copy one input through the same bounded, owner-locked batch path."""
    return (
        await append_execution_inputs(
            session,
            wallet_id=wallet_id,
            episode_id=episode_id,
            inputs=((evidence_id, record, decision_market),),
        )
    )[0]


async def append_execution_inputs(
    session: UserSession,
    *,
    wallet_id: UUID,
    episode_id: UUID,
    inputs: tuple[tuple[UUID, StoredExecutionInput, MarketInput | None], ...],
) -> tuple[SavedExecutionInput, ...]:
    """Copy every input before decisions, pinning episode/profile once per transaction.

    The owner/episode lock remains held through commit. Profiles are immutable;
    each source identity, digest and permanent deduplication key is still checked.
    No input is dropped or merged and a conflict rolls back the whole batch.
    """
    if not 1 <= len(inputs) <= 20:
        raise ValueError("bounded execution evidence batch required")
    await lock_active_episode(session, wallet_id, episode_id)
    profile = (
        (
            await session.execute(
                """SELECT fee_version,model_version FROM paper_execution_profiles
      WHERE episode_id=:episode AND user_id=:user""",
                {"episode": episode_id, "user": session.user_id},
            )
        )
        .mappings()
        .one_or_none()
    )
    if profile is None:
        raise OrderConflictError("Paper profile not initialized")
    prepared = tuple(
        _prepare_execution_input(
            session,
            wallet_id=wallet_id,
            episode_id=episode_id,
            evidence_id=identity,
            record=record,
            decision_market=market,
            fee_version=profile["fee_version"],
            model_version=profile["model_version"],
        )
        for identity, record, market in inputs
    )
    unique: dict[tuple[object, ...], dict[str, object]] = {}
    for value in prepared:
        key = _input_key(value)
        if key in unique and unique[key]["digest"] != value["digest"]:
            raise OrderConflictError("Paper input identity payload conflict")
        unique.setdefault(key, value)
    params = {
        "episode": episode_id,
        "rows": json.dumps(
            [
                {
                    name: value[name]
                    for name in ("base", "quote", "generation", "input_id", "decision_kind")
                }
                for value in unique.values()
            ]
        ),
    }
    prior = (
        (
            await session.execute(
                """SELECT e.* FROM jsonb_to_recordset(CAST(:rows AS jsonb)) AS r(
                base text,quote text,generation bigint,input_id bigint,decision_kind text)
                JOIN paper_execution_input_keys k ON k.episode_id=:episode
                  AND k.base=r.base AND k.quote=r.quote AND k.generation=r.generation
                  AND k.input_id=r.input_id AND k.decision_kind=r.decision_kind
                JOIN paper_execution_inputs e
                  ON (e.id,e.recorded_at)=(k.evidence_id,k.recorded_at)""",
                params,
            )
        )
        .mappings()
        .all()
    )
    saved: dict[tuple[object, ...], SavedExecutionInput] = {}
    for row in prior:
        key = _input_key(row)
        if row["digest"] != unique[key]["digest"]:
            raise OrderConflictError("Paper input identity payload conflict")
        saved[key] = _decode(row)
    pending = tuple(value for key, value in unique.items() if key not in saved)
    if pending:
        rows = (
            (
                await session.execute(
                    """INSERT INTO paper_execution_inputs
                    (id,user_id,wallet_id,episode_id,base,quote,input_id,generation,
                     decision_kind,payload,digest,source_digest)
                    SELECT id,user_id,wallet_id,episode_id,base,quote,input_id,generation,
                      decision_kind,payload,digest,source_digest
                    FROM jsonb_to_recordset(CAST(:rows AS jsonb)) AS r(
                      id uuid,user_id uuid,wallet_id uuid,episode_id uuid,base text,quote text,
                      input_id bigint,generation bigint,decision_kind text,payload jsonb,
                      digest text,source_digest text)
                    RETURNING *""",
                    {"rows": json.dumps(pending, default=str)},
                )
            )
            .mappings()
            .all()
        )
        await session.execute(
            """INSERT INTO paper_execution_input_keys
            (user_id,wallet_id,episode_id,base,quote,generation,input_id,
             decision_kind,recorded_at,evidence_id)
            SELECT user_id,wallet_id,episode_id,base,quote,generation,input_id,
              decision_kind,recorded_at,id
            FROM jsonb_to_recordset(CAST(:rows AS jsonb)) AS r(
              user_id uuid,wallet_id uuid,episode_id uuid,base text,quote text,
              generation bigint,input_id bigint,decision_kind text,
              recorded_at timestamptz,id uuid)""",
            {
                "rows": json.dumps(
                    [
                        {
                            name: row[name]
                            for name in (
                                "user_id",
                                "wallet_id",
                                "episode_id",
                                "base",
                                "quote",
                                "generation",
                                "input_id",
                                "decision_kind",
                                "recorded_at",
                                "id",
                            )
                        }
                        for row in rows
                    ],
                    default=str,
                )
            },
        )
        for row in rows:
            saved[_input_key(row)] = _decode(row)
    return tuple(saved[_input_key(value)] for value in prepared)


def _input_key(value: Any) -> tuple[object, ...]:
    return tuple(
        value[name] for name in ("base", "quote", "generation", "input_id", "decision_kind")
    )


def _prepare_execution_input(
    session: UserSession,
    *,
    wallet_id: UUID,
    episode_id: UUID,
    evidence_id: UUID,
    record: StoredExecutionInput,
    decision_market: MarketInput | None,
    fee_version: str,
    model_version: str,
) -> dict[str, object]:
    if _source_digest(record) != record.digest:
        raise OrderConflictError("public source input digest mismatch")
    market = record.market if decision_market is None else decision_market
    if (
        market.pair != record.market.pair
        or market.input_id != record.market.input_id
        or market.generation != record.market.generation
        or market.received_at != record.market.received_at
    ):
        raise OrderConflictError("consumer rebase changed source identity")
    if market != record.market and not (
        isinstance(market, BookState)
        and isinstance(record.market, BookState)
        and market == replace(record.market, rebase=True)
    ):
        raise OrderConflictError("consumer rebase changed source content")
    evidence = {
        "market": json.loads(input_payload(market)),
        "metadata": json.loads(metadata_payload(record.metadata)),
        "fee_version": fee_version,
        "model_version": model_version,
    }
    if market != record.market:
        evidence["source_market"] = json.loads(input_payload(record.market))
    payload = canonical(evidence)
    digest = hashlib.sha256(payload.encode()).hexdigest()
    pair = market.pair
    return {
        "user_id": session.user_id,
        "wallet_id": wallet_id,
        "episode_id": episode_id,
        "base": pair.base,
        "quote": pair.quote,
        "input_id": market.input_id,
        "generation": market.generation,
        "decision_kind": "REBASE" if isinstance(market, BookState) and market.rebase else "INPUT",
        "id": evidence_id,
        "payload": evidence,
        "digest": digest,
        "source_digest": record.digest,
    }


async def read_execution_inputs(
    session: UserSession,
    *,
    episode_id: UUID,
    pair: PositionPair,
    after_input_id: int = 0,
    limit: int = 100,
) -> tuple[SavedExecutionInput, ...]:
    session = require_user_session(session)
    if (
        type(limit) is not int
        or not 1 <= limit <= 4096
        or type(after_input_id) is not int
        or after_input_id < 0
    ):
        raise ValueError("bounded evidence cursor required")
    rows = (
        (
            await session.execute(
                """SELECT e.* FROM paper_execution_input_keys k
      JOIN paper_execution_inputs e ON (e.id,e.recorded_at)=(k.evidence_id,k.recorded_at)
      WHERE k.episode_id=:episode AND k.base=:base AND k.quote=:quote AND k.input_id>:after
      ORDER BY k.input_id LIMIT :limit""",
                {
                    "episode": episode_id,
                    "base": pair.base,
                    "quote": pair.quote,
                    "after": after_input_id,
                    "limit": limit,
                },
            )
        )
        .mappings()
        .all()
    )
    return tuple(_decode(row) for row in rows)
