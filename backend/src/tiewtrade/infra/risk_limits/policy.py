"""Resolve production risk evidence inside each owner transaction; never cache a policy."""

from datetime import datetime
from uuid import UUID

from tiewtrade.core.money import Quantity
from tiewtrade.core.orders import AdmissionPolicy, OrderConflictError, OrderIntent, TradingMode
from tiewtrade.core.positions import ExecutionSide
from tiewtrade.core.risk_limits import (
    PaperUnsetRiskPolicy,
    RiskEvaluation,
    RiskExecutionContext,
    RiskPolicy,
    RiskPriceUnavailableError,
    RiskReason,
    RiskScope,
    RiskUnavailableError,
)
from tiewtrade.infra.db.session import UserSession, require_user_session
from tiewtrade.infra.paper_orders.storage import lock_pair_catalog
from tiewtrade.infra.paper_wallet import get_wallet
from tiewtrade.infra.risk_limits.dispatch import lock_risk_owner
from tiewtrade.infra.risk_limits.monitor import replay_monitor
from tiewtrade.infra.risk_limits.storage import read_setting
from tiewtrade.infra.risk_limits.views import read_evidence


async def paper_opening_protocol_enabled(session: UserSession) -> bool:
    """Require every global gate used by Paper intake and financial writers."""
    checked = require_user_session(session)
    return bool(
        (
            await checked.execute(
                "SELECT publication_enabled AND financial_enabled AND admission_enabled "
                "FROM risk_protocol_control"
            )
        ).scalar_one()
    )


class TransactionalRiskPolicy:
    """Composition dependency resolved before passing the immutable policy to core."""

    def check(self, intent: OrderIntent) -> None:
        raise RiskUnavailableError("risk policy must be resolved inside the owner transaction")

    async def resolve(
        self,
        session: UserSession,
        intent: OrderIntent,
        *,
        held: Quantity,
        reserved: Quantity,
    ) -> AdmissionPolicy:
        checked = require_user_session(session)
        await lock_risk_owner(checked, TradingMode.PAPER)
        scope = await _scope(checked, intent)
        setting = await read_setting(checked, scope)
        if intent.side is ExecutionSide.SELL:
            now: datetime = (await checked.execute("SELECT clock_timestamp()")).scalar_one()
            return RiskPolicy(
                RiskEvaluation(
                    scope,
                    setting.revision,
                    0,
                    now,
                    RiskReason.SOURCE_UNAVAILABLE,
                    None,
                    setting.latched,
                    False,
                ),
                held,
                reserved,
            )
        if intent.side is ExecutionSide.BUY:
            await lock_pair_catalog(checked, intent.pair)
        if intent.side is ExecutionSide.BUY and setting.limit is None:
            if not await paper_opening_protocol_enabled(checked):
                raise RiskUnavailableError("risk admission has not passed activation validation")
            return PaperUnsetRiskPolicy(scope, held, reserved)
        role = (await checked.execute("SELECT current_user")).scalar_one()
        if role == "tiewtrade_engine" and setting.limit is not None:
            await replay_monitor(checked, setting)
            setting = await read_setting(checked, scope)
        evidence = await read_evidence(checked, setting, api_price_tail=role == "tiewtrade_api")
        evaluation = evidence.evaluation
        enabled = evidence.admission_enabled
        if intent.side is ExecutionSide.BUY and not enabled:
            raise RiskUnavailableError("risk admission has not passed activation validation")
        if intent.side is ExecutionSide.BUY and not evaluation.latched:
            price = next((row for row in evidence.prices if row.pair == intent.pair), None)
            if price is None or price.price_at(evaluation.evaluated_at) is None:
                raise RiskPriceUnavailableError("order pair has no authoritative current price")
        return RiskPolicy(evaluation, held, reserved)

    async def execution_context(
        self,
        session: UserSession,
        intent: OrderIntent,
        *,
        publication_fence: bool = True,
    ) -> RiskExecutionContext:
        checked = require_user_session(session)
        await lock_risk_owner(checked, TradingMode.PAPER)
        scope = await _matching_scope(checked, intent)
        if intent.side is ExecutionSide.BUY:
            await lock_pair_catalog(checked, intent.pair)
        setting = await read_setting(checked, scope)
        if intent.side is ExecutionSide.SELL:
            return RiskExecutionContext(setting, None, (), False)
        if publication_fence:
            await checked.execute("SELECT risk_financial_fence()")
        if setting.limit is None:
            return RiskExecutionContext(
                setting,
                None,
                (),
                await paper_opening_protocol_enabled(checked),
            )
        await replay_monitor(checked, setting, publication_fence=publication_fence)
        setting = await read_setting(checked, scope)
        evidence = await read_evidence(checked, setting)
        return RiskExecutionContext(
            setting,
            evidence.book,
            evidence.prices,
            evidence.admission_enabled and evidence.evaluation.reason is RiskReason.READY,
        )


async def _matching_scope(session: UserSession, intent: OrderIntent) -> RiskScope:
    """Resolve identity without rebuilding unrelated cash/reset presentation.

    Matching pins this owner/episode before calling us. Position completeness
    and exact risk-book agreement are checked by read_evidence; the F15 cash
    writer independently validates the full wallet ledger before every fill.
    Intake/admission still use the full wallet snapshot below.
    """
    if intent.scope.owner_id != session.user_id or intent.scope.mode is not TradingMode.PAPER:
        raise OrderConflictError("Paper risk owner/mode mismatch")
    row = (
        await session.execute(
            """SELECT s.wallet_id,s.active_episode_id FROM paper_wallet_state s
            JOIN paper_wallet_episodes e ON (e.id,e.wallet_id,e.user_id)=
              (s.active_episode_id,s.wallet_id,s.user_id)
            WHERE s.user_id=:owner AND s.active_episode_id=:episode
              AND NOT EXISTS(SELECT 1 FROM paper_wallet_episode_closures c
                WHERE c.episode_id=e.id)""",
            {"owner": session.user_id, "episode": intent.scope.episode_id},
        )
    ).one_or_none()
    if row is None:
        raise OrderConflictError("active Paper risk scope is unavailable")
    return RiskScope(
        UUID(str(session.user_id)),
        TradingMode.PAPER,
        UUID(str(row.wallet_id)),
        UUID(str(row.active_episode_id)),
    )


async def _scope(session: UserSession, intent: OrderIntent) -> RiskScope:
    if intent.scope.owner_id != session.user_id or intent.scope.mode is not TradingMode.PAPER:
        raise OrderConflictError("Paper risk owner/mode mismatch")
    wallet = await get_wallet(session)
    if wallet is None or wallet.episode_id != intent.scope.episode_id:
        raise OrderConflictError("active Paper risk scope is unavailable")
    return RiskScope(
        UUID(str(session.user_id)),
        TradingMode.PAPER,
        UUID(str(wallet.wallet_id)),
        UUID(str(wallet.episode_id)),
    )
