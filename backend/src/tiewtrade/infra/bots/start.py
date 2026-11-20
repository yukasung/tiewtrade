"""Apply a claimed Paper start only after authoritative readiness checks."""

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from uuid import UUID, uuid5

from tiewtrade.core.orders import OrderOrigin, TradingMode
from tiewtrade.core.positions import PositionPair
from tiewtrade.core.risk_limits import RiskReason, RiskScope
from tiewtrade.core.strategies import StrategyDescriptor, StrategyDocument, document_payload
from tiewtrade.infra.bots.claims import BotRequestClaim, finish_control, require_control_claim
from tiewtrade.infra.db.session import UserSession
from tiewtrade.infra.paper_orders.storage import lock_pair_catalog
from tiewtrade.infra.paper_wallet import get_wallet
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot
from tiewtrade.infra.risk_limits.monitor import replay_monitor
from tiewtrade.infra.risk_limits.policy import paper_opening_protocol_enabled
from tiewtrade.infra.risk_limits.storage import read_setting
from tiewtrade.infra.risk_limits.views import read_evidence
from tiewtrade.infra.trading_stops.storage import current_opening_blocked


@dataclass(frozen=True, slots=True)
class PublishedConfiguration:
    """An executable strategy pin resolved by the deployment registry."""

    reference: str
    descriptor: StrategyDescriptor
    pair: PositionPair
    configuration: StrategyDocument
    initial_state: StrategyDocument

    def __post_init__(self) -> None:
        if (
            not self.reference.strip()
            or self.pair not in self.descriptor.pairs
            or self.configuration.version != self.descriptor.configuration_version
            or self.initial_state.version != self.descriptor.state_version
        ):
            raise ValueError("configuration does not match the published descriptor")


class BotReplacementRefusedError(ValueError):
    """The exact owner-approved replacement could not apply."""


type ClearReplacementStop = Callable[
    [UserSession, BotRequestClaim, dict[str, object]], Awaitable[None]
]


async def apply_paper_start(
    session: UserSession,
    claim: BotRequestClaim,
    definition: PublishedConfiguration,
    *,
    clear_replacement_stop: ClearReplacementStop | None = None,
) -> UUID | None:
    """Apply an ordinary start. Replacement uses a distinct F-19 proof path."""
    await require_control_claim(session, claim)
    if claim.hint.mode is not TradingMode.PAPER:
        await finish_control(session, claim, failure_code="LIVE_EXECUTION_UNAVAILABLE")
        return None
    request = (
        await session.execute(
            """SELECT payload FROM bot_control_requests
               WHERE id=:id AND user_id=:owner AND mode='PAPER'""",
            {"id": claim.hint.request_id, "owner": session.user_id},
        )
    ).scalar_one()
    if request.get("strategy_config_ref") != definition.reference:
        await finish_control(session, claim, failure_code="BOT_STRATEGY_UNAVAILABLE")
        return None
    replacement = request.get("replacement")
    if replacement is not None and (
        not isinstance(replacement, dict) or clear_replacement_stop is None
    ):
        await finish_control(session, claim, failure_code="BOT_REPLACEMENT_UNAVAILABLE")
        return None
    use = (
        await session.execute(
            "SELECT use FROM user_trading_preferences WHERE user_id=:owner",
            {"owner": session.user_id},
        )
    ).scalar_one_or_none()
    wallet = await get_wallet(session)
    if (
        use != "BOT"
        or wallet is None
        or not wallet.reset_available
        or (
            replacement is None
            and await current_opening_blocked(session, TradingMode.PAPER, OrderOrigin.BOT)
        )
    ):
        await finish_control(session, claim, failure_code="BOT_NOT_READY")
        return None
    catalog = await lock_pair_catalog(session, definition.pair)
    if (definition.pair.base, definition.pair.quote) not in catalog.snapshot.active_pairs:
        await finish_control(session, claim, failure_code="BOT_PAIR_UNAVAILABLE")
        return None
    scope = RiskScope(
        UUID(str(session.user_id)),
        TradingMode.PAPER,
        UUID(str(wallet.wallet_id)),
        UUID(str(wallet.episode_id)),
    )
    setting = await read_setting(session, scope)
    if (
        setting.limit is None
        or setting.latched
        or not await paper_opening_protocol_enabled(session)
    ):
        await finish_control(session, claim, failure_code="BOT_RISK_UNAVAILABLE")
        return None
    await replay_monitor(session, setting)
    setting = await read_setting(session, scope)
    evidence = await read_evidence(session, setting)
    current_price = any(
        price.pair == definition.pair
        and price.price_at(evidence.evaluation.evaluated_at) is not None
        for price in evidence.prices
    )
    if setting.latched or evidence.evaluation.reason is not RiskReason.READY or not current_price:
        await finish_control(session, claim, failure_code="BOT_RISK_UNAVAILABLE")
        return None

    if replacement is not None:
        assert clear_replacement_stop is not None
        await session.execute("SAVEPOINT bot_replacement")
        try:
            await clear_replacement_stop(session, claim, replacement)
            identity = await _create_run(
                session, claim, definition, wallet, catalog.snapshot.revision
            )
            if identity is None:
                raise BotReplacementRefusedError("replacement slot unavailable")
        except BotReplacementRefusedError:
            await session.execute("ROLLBACK TO SAVEPOINT bot_replacement")
            await session.execute("RELEASE SAVEPOINT bot_replacement")
            await finish_control(session, claim, failure_code="BOT_REPLACEMENT_NOT_READY")
            return None
        await session.execute("RELEASE SAVEPOINT bot_replacement")
    else:
        identity = await _create_run(session, claim, definition, wallet, catalog.snapshot.revision)
        if identity is None:
            await finish_control(session, claim, failure_code="BOT_SLOT_OCCUPIED")
            return None
    await finish_control(session, claim, run_id=identity)
    return identity


async def _create_run(
    session: UserSession,
    claim: BotRequestClaim,
    definition: PublishedConfiguration,
    wallet: PaperWalletSnapshot,
    catalog_revision: int,
) -> UUID | None:
    revision = definition.descriptor
    identity = uuid5(claim.hint.request_id, "bot-run")
    row = (
        await session.execute(
            """INSERT INTO bot_runs(id,user_id,mode,wallet_id,episode_id,strategy_name,
                 strategy_version,configuration_version,state_version,configuration,
                 strategy_state,status)
               VALUES(:id,:owner,'PAPER',:wallet,:episode,:name,:strategy,:config_version,
                      :state_version,CAST(:configuration AS jsonb),CAST(:state AS jsonb),
                      'STARTING')
               ON CONFLICT(user_id,mode) WHERE status<>'RETIRED' DO NOTHING RETURNING id""",
            {
                "id": identity,
                "owner": session.user_id,
                "wallet": wallet.wallet_id,
                "episode": wallet.episode_id,
                "name": revision.name,
                "strategy": revision.version,
                "config_version": revision.configuration_version,
                "state_version": revision.state_version,
                "configuration": json.dumps(document_payload(definition.configuration)),
                "state": json.dumps(document_payload(definition.initial_state)),
            },
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    await session.execute(
        """INSERT INTO bot_run_events(id,run_id,user_id,mode,revision,event,details)
           VALUES(:id,:run,:owner,'PAPER',1,'START_REQUEST_APPLIED',
                  jsonb_build_object('request_id',CAST(:request AS uuid),
                                     'catalog_revision',CAST(:catalog AS bigint),
                                     'base',CAST(:base AS text),'quote',CAST(:quote AS text)))""",
        {
            "id": uuid5(identity, "created"),
            "run": identity,
            "owner": session.user_id,
            "request": claim.hint.request_id,
            "catalog": catalog_revision,
            "base": definition.pair.base,
            "quote": definition.pair.quote,
        },
    )
    return identity
