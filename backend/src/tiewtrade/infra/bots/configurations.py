"""Owner-scoped immutable user configurations; no executable user input."""

import hashlib
import json
from uuid import UUID, uuid5

from tiewtrade.core.strategies import document_from_payload, document_payload
from tiewtrade.core.strategy_config import PaperTestConfig, RsiStepGridConfig
from tiewtrade.infra.bots.requests import BotRequestConflictError
from tiewtrade.infra.db.session import UserSession, require_user_session


async def create_configuration(
    session: UserSession, *, key: UUID, configuration: RsiStepGridConfig | PaperTestConfig
) -> UUID:
    checked = require_user_session(session)
    body = json.dumps(
        document_payload(configuration.document()), sort_keys=True, separators=(",", ":")
    )
    fingerprint = hashlib.sha256(body.encode()).hexdigest()
    test = isinstance(configuration, PaperTestConfig)
    table = "bot_test_strategy_configurations" if test else "bot_strategy_configurations"
    other = "bot_strategy_configurations" if test else "bot_test_strategy_configurations"
    await checked.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(:identity,0))",
        {"identity": f"strategy-config:{checked.user_id}:{key}"},
    )
    if (
        await checked.execute("SELECT to_regclass(:table)", {"table": "public." + other})
    ).scalar_one_or_none() is not None and (
        await checked.execute(
            f"SELECT EXISTS(SELECT 1 FROM {other} WHERE user_id=:owner AND idempotency_key=:key)",
            {"owner": checked.user_id, "key": key},
        )
    ).scalar_one():
        raise BotRequestConflictError("configuration strategy identity differs")
    identity = uuid5(checked.user_id, f"{'PAPER_TEST' if test else 'F21'}:config:{key}")
    await checked.execute(
        f"""INSERT INTO {table}
        (id,user_id,mode,idempotency_key,fingerprint,configuration)
        VALUES(:id,:owner,'PAPER',:key,:fingerprint,CAST(:body AS jsonb))
        ON CONFLICT(user_id,mode,idempotency_key) DO NOTHING""",
        {
            "id": identity,
            "owner": checked.user_id,
            "key": key,
            "fingerprint": fingerprint,
            "body": body,
        },
    )
    row = (
        await checked.execute(
            f"""SELECT id,fingerprint FROM {table}
        WHERE user_id=:owner AND mode='PAPER' AND idempotency_key=:key""",
            {"owner": checked.user_id, "key": key},
        )
    ).one()
    if row.fingerprint != fingerprint:
        raise BotRequestConflictError("configuration idempotency conflict")
    return UUID(str(row.id))


async def read_configuration(
    session: UserSession, reference: str
) -> RsiStepGridConfig | PaperTestConfig | None:
    require_user_session(session)
    prefix, _, value = reference.partition(":")
    if prefix not in ("f21", "paper-test"):
        return None
    table = "bot_strategy_configurations" if prefix == "f21" else "bot_test_strategy_configurations"
    try:
        identity = UUID(value)
    except ValueError:
        return None
    payload = (
        await session.execute(
            f"SELECT configuration FROM {table} WHERE id=:id AND mode='PAPER'",
            {"id": identity},
        )
    ).scalar_one_or_none()
    return (
        None
        if payload is None
        else (RsiStepGridConfig if prefix == "f21" else PaperTestConfig).from_document(
            document_from_payload(payload, expected_version=1)
        )
    )
