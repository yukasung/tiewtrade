"""Owner-scoped bot status and durable receipt recovery."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response

from tiewtrade.core.market_data import Timeframe
from tiewtrade.core.money import Money, MoneyError, Quantity
from tiewtrade.core.orders import TradingMode
from tiewtrade.core.positions import PositionPair
from tiewtrade.core.strategies import document_from_payload
from tiewtrade.core.strategy_config import (
    CANDLE_STRATEGIES,
    PAPER_TEST_STRATEGY,
    STRATEGY_NAME,
    PaperTestConfig,
    RsiStepGridConfig,
    decode_strategy_config,
)
from tiewtrade.infra.auth.throttle import Bucket
from tiewtrade.infra.bots.configurations import create_configuration, read_configuration
from tiewtrade.infra.bots.requests import (
    BotReceipt,
    BotRequestConflictError,
    receipt_by_id,
    receipt_by_key,
    submit_start,
)
from tiewtrade.infra.db import DatabaseRole, InfraError, repeatable_user_session, user_session
from tiewtrade.infra.paper_wallet import get_wallet
from tiewtrade.infra.positions.views import ready_position_metadata
from tiewtrade.infra.protections.storage import stored
from tiewtrade.infra.trading_stops import read_status
from tiewtrade.services.api.bot_models import (
    BotPositionView,
    BotProtectionView,
    BotReceiptView,
    BotReplacementInput,
    BotStartInput,
    BotStatusView,
    PaperTestConfigurationInput,
    PaperTestConfigurationView,
    StrategyCatalogView,
    StrategyConfigurationInput,
    StrategyConfigurationView,
)
from tiewtrade.services.api.db_resources import engine_for, paper_mutation_engine
from tiewtrade.services.api.request_identity import Authenticated, current_user
from tiewtrade.services.api.safe_input_routes import SafeInputRoute
from tiewtrade.services.api.throttling import spend_token


class BotInputRoute(SafeInputRoute):
    rejection_code = "BOT_INPUT_INVALID"


router = APIRouter(tags=["bots"], route_class=BotInputRoute)
Who = Annotated[Authenticated, Depends(current_user)]
Key = Annotated[UUID, Header(alias="Idempotency-Key")]


def _paper_test_input(config: PaperTestConfig) -> PaperTestConfigurationInput:
    return PaperTestConfigurationInput.model_validate(
        {
            "strategy_name": PAPER_TEST_STRATEGY,
            "base": config.pair.base,
            "timeframe": config.timeframe.value,
            "capital_per_entry": config.capital_per_entry.as_parts()["amount"],
        }
    )


@router.get("/paper/bots/strategy", response_model=StrategyCatalogView)
async def strategy_catalog(request: Request, who: Who) -> StrategyCatalogView:
    return StrategyCatalogView(
        strategy_name=STRATEGY_NAME,
        timeframes=list(Timeframe),
        strategies=[STRATEGY_NAME]
        + (
            [PAPER_TEST_STRATEGY]
            if getattr(request.app.state, "paper_test_strategy_enabled", False) is True
            else []
        ),
    )


@router.post(
    "/paper/bots/configurations",
    response_model=StrategyConfigurationView | PaperTestConfigurationView,
)
async def configure_strategy(
    request: Request,
    who: Who,
    key: Key,
    body: StrategyConfigurationInput | PaperTestConfigurationInput,
) -> StrategyConfigurationView | PaperTestConfigurationView:
    if (
        isinstance(body, PaperTestConfigurationInput)
        and getattr(request.app.state, "paper_test_strategy_enabled", False) is not True
    ):
        raise HTTPException(503, "BOT_PAPER_EXECUTION_UNAVAILABLE")
    try:
        config = (
            PaperTestConfig(
                PositionPair(body.base, "USDT"),
                Timeframe(body.timeframe),
                Money.of(body.capital_per_entry, "USDT"),
            )
            if isinstance(body, PaperTestConfigurationInput)
            else RsiStepGridConfig(
                PositionPair(body.base, "USDT"),
                Timeframe(body.timeframe),
                Money.of(body.capital_per_entry, "USDT"),
                body.max_entries,
            )
        )
    except (ValueError, MoneyError):
        raise HTTPException(422, "BOT_INPUT_INVALID") from None
    try:
        await spend_token(paper_mutation_engine(request), who.user_id, Bucket.PAPER_ORDER_NEW)
        async with user_session(engine_for(request, DatabaseRole.API), who.user_id) as session:
            identity = await create_configuration(session, key=key, configuration=config)
        return (
            PaperTestConfigurationView(**body.model_dump(), reference=f"paper-test:{identity}")
            if isinstance(body, PaperTestConfigurationInput)
            else StrategyConfigurationView(**body.model_dump(), reference=f"f21:{identity}")
        )
    except BotRequestConflictError:
        raise HTTPException(409, "BOT_REQUEST_IDEMPOTENCY_CONFLICT") from None
    except InfraError:
        raise HTTPException(503, "BOT_STATUS_UNAVAILABLE") from None


@router.get(
    "/paper/bots/configurations/{identity}",
    response_model=StrategyConfigurationView | PaperTestConfigurationView,
)
async def configuration_by_id(
    identity: UUID,
    request: Request,
    who: Who,
    strategy_name: Literal["paper-green-atr-test"] | None = None,
) -> StrategyConfigurationView | PaperTestConfigurationView:
    try:
        async with repeatable_user_session(
            engine_for(request, DatabaseRole.API), who.user_id
        ) as session:
            config = await read_configuration(
                session,
                f"{'paper-test' if strategy_name == PAPER_TEST_STRATEGY else 'f21'}:{identity}",
            )
        if config is None:
            raise HTTPException(404, "BOT_CONFIGURATION_NOT_FOUND")
        if isinstance(config, PaperTestConfig):
            return PaperTestConfigurationView.model_validate(
                _paper_test_input(config).model_dump() | {"reference": f"paper-test:{identity}"}
            )
        return StrategyConfigurationView.model_validate(
            {
                "reference": f"f21:{identity}",
                "base": config.pair.base,
                "timeframe": config.timeframe.value,
                "capital_per_entry": config.capital_per_entry.as_parts()["amount"],
                "max_entries": config.max_entries,
            }
        )
    except InfraError:
        raise HTTPException(503, "BOT_STATUS_UNAVAILABLE") from None


def _mode(request: Request) -> TradingMode:
    return TradingMode.PAPER if request.url.path.startswith("/paper/") else TradingMode.LIVE


def _unavailable(mode: TradingMode) -> str:
    return "BOT_STRATEGY_UNAVAILABLE" if mode is TradingMode.PAPER else "LIVE_EXECUTION_UNAVAILABLE"


def _receipt(value: BotReceipt | None) -> BotReceiptView:
    if value is None:
        raise HTTPException(404, "BOT_REQUEST_NOT_FOUND")
    return BotReceiptView(
        request_id=value.request_id,
        mode=value.mode,
        key=value.key,
        run_id=value.run_id,
        failure_code=value.failure_code,
        pending=value.pending,
    )


@router.get("/paper/bots/status", response_model=BotStatusView)
@router.get("/live/bots/status", response_model=BotStatusView)
async def status(request: Request, who: Who) -> BotStatusView:
    mode = _mode(request)
    exposure_available = False
    positions: list[BotPositionView] = []
    protections: list[BotProtectionView] = []
    protections_more = False
    pinned = None
    basket_target = None
    basket_triggered = False
    open_entries = 0
    replacement = None
    try:
        async with repeatable_user_session(
            engine_for(request, DatabaseRole.API), who.user_id
        ) as session:
            snapshot_at: datetime = (
                await session.execute("SELECT transaction_timestamp()")
            ).scalar_one()
            pending_request_id = (
                await session.execute(
                    """SELECT r.id FROM bot_control_requests r
                       WHERE r.user_id=:owner AND r.mode=:mode AND NOT EXISTS (
                         SELECT 1 FROM bot_control_results x
                         WHERE x.request_id=r.id AND x.user_id=r.user_id AND x.mode=r.mode)
                       ORDER BY r.requested_at DESC,r.id DESC LIMIT 1""",
                    {"owner": who.user_id, "mode": mode.value},
                )
            ).scalar_one_or_none()
            run = (
                await session.execute(
                    """SELECT r.id,r.status,r.revision,r.strategy_name,r.strategy_version,
                              r.configuration_version, s.reason,
                              CASE WHEN r.status IN ('PAUSED','STARTING','RECOVERING') THEN (
                                SELECT e.details->>'reason' FROM bot_run_events e
                                WHERE e.run_id=r.id AND e.user_id=r.user_id AND e.mode=r.mode
                                ORDER BY e.revision DESC LIMIT 1) END AS readiness_reason
                       FROM bot_runs r LEFT JOIN LATERAL (
                           SELECT CASE WHEN e.event IN ('PROTECTION_SETUP_FAILED','CATALOG_REMOVED')
                                 THEN e.event
                               WHEN e.event IN
                                 ('STRATEGY_VERSION_UNAVAILABLE','STRATEGY_EVALUATION_FAILED')
                                 THEN 'SYSTEM' ELSE e.details->>'cause' END AS reason
                           FROM bot_run_events e WHERE e.run_id=r.id AND e.user_id=r.user_id
                             AND e.mode=r.mode AND e.event IN
                               ('TRADING_STOP','PROTECTION_SETUP_FAILED','CATALOG_REMOVED',
                                'STRATEGY_VERSION_UNAVAILABLE','STRATEGY_EVALUATION_FAILED')
                           ORDER BY e.revision DESC LIMIT 1
                       ) s ON r.status='STOPPED'
                       WHERE r.user_id=:owner AND r.mode=:mode AND r.status<>'RETIRED'""",
                    {"owner": who.user_id, "mode": mode.value},
                )
            ).one_or_none()
            if run is not None and run.strategy_name in CANDLE_STRATEGIES:
                payload = (
                    await session.execute(
                        "SELECT configuration FROM bot_runs WHERE id=:run", {"run": run.id}
                    )
                ).scalar_one()
                config = decode_strategy_config(
                    run.strategy_name, document_from_payload(payload, expected_version=1)
                )
                pinned = (
                    _paper_test_input(config)
                    if isinstance(config, PaperTestConfig)
                    else StrategyConfigurationInput.model_validate(
                        {
                            "base": config.pair.base,
                            "timeframe": config.timeframe.value,
                            "capital_per_entry": config.capital_per_entry.as_parts()["amount"],
                            "max_entries": config.max_entries,
                        }
                    )
                )
                basket = (
                    await session.execute(
                        """SELECT b.status,b.target,
                  count(e.order_id) FILTER(WHERE e.quantity>0) AS open_entries
                  FROM bot_strategy_baskets b LEFT JOIN bot_strategy_entries e ON e.basket_id=b.id
                  WHERE b.run_id=:run AND b.status<>'CLOSED' GROUP BY b.id""",
                        {"run": run.id},
                    )
                ).one_or_none()
                if basket is not None:
                    open_entries = basket.open_entries
                    basket_triggered = basket.status == "TRIGGERED"
                    basket_target = (
                        None
                        if basket.target is None
                        else Money.of(basket.target, config.pair.quote).as_parts()["amount"]
                    )
            if (run is not None or pending_request_id is not None) and mode is TradingMode.PAPER:
                episode = (
                    await session.execute(
                        "SELECT active_episode_id FROM paper_wallet_state WHERE user_id=:owner",
                        {"owner": who.user_id},
                    )
                ).scalar_one_or_none()
                if episode is not None:
                    exposure_available = await ready_position_metadata(session, episode) is not None
                    if exposure_available:
                        rows = await session.execute(
                            """SELECT base,quote,held_quantity FROM paper_position_projections
                               WHERE episode_id=:episode AND held_quantity<>0
                               ORDER BY base,quote""",
                            {"episode": episode},
                        )
                        positions = [
                            BotPositionView(
                                base=row.base,
                                quote=row.quote,
                                quantity=Quantity.of(row.held_quantity, row.base).as_parts()[
                                    "quantity"
                                ],
                            )
                            for row in rows
                        ]
                    groups = await session.execute(
                        """SELECT *
                           FROM paper_protections WHERE episode_id=:episode AND quantity>0
                           ORDER BY CASE WHEN state='FAILED' OR document->>'conflicted'='true'
                              THEN 0 WHEN state IN ('ARMING','EXITING') THEN 1 ELSE 2 END,
                              base,id LIMIT 21""",
                        {"episode": episode},
                    )
                    group_rows = groups.all()
                    protections_more = len(group_rows) > 20
                    protections = [
                        BotProtectionView(
                            protection_id=group.value.protection_id,
                            base=group.value.prices.pair.base,
                            quantity=group.value.quantity.as_parts()["quantity"],
                            state=group.value.state,
                            conflicted=group.value.conflicted,
                            failure_code=group.failure_code,
                        )
                        for row in group_rows[:20]
                        for group in (stored(row),)
                    ]
            if (
                mode is TradingMode.PAPER
                and (
                    getattr(request.app.state, "bot_f21_enabled", False) is True
                    or getattr(request.app.state, "paper_test_strategy_enabled", False) is True
                )
                and run is not None
                and run.status == "STOPPED"
                and pending_request_id is None
            ):
                wallet = await get_wallet(session)
                stop = await read_status(session, mode)
                if (
                    wallet is not None
                    and wallet.reset_available
                    and stop.platform_stop_id is None
                    and (
                        stop.stop_id is None or (stop.resume_ready and len(stop.active_causes) == 1)
                    )
                ):
                    reconciliation = (
                        await session.execute(
                            "SELECT revision FROM paper_position_activity "
                            "WHERE episode_id=:episode AND availability='READY'",
                            {"episode": wallet.episode_id},
                        )
                    ).scalar_one_or_none()
                    if reconciliation is not None:
                        replacement = BotReplacementInput(
                            run_id=run.id,
                            run_revision=run.revision,
                            stop_id=stop.stop_id,
                            stop_revision=None if stop.stop_id is None else stop.revision,
                            summary_revision=stop.summary_revision,
                            reconciliation_revision=reconciliation,
                        )
    except InfraError:
        raise HTTPException(503, "BOT_STATUS_UNAVAILABLE") from None
    return BotStatusView(
        mode=mode,
        snapshot_at=snapshot_at,
        pending_request_id=pending_request_id,
        run_id=None if run is None else run.id,
        status=None if run is None else run.status,
        revision=None if run is None else run.revision,
        strategy_name=None if run is None else run.strategy_name,
        strategy_version=None if run is None else run.strategy_version,
        configuration_version=None if run is None else run.configuration_version,
        stop_reason=None if run is None else run.reason,
        can_start=(
            mode is TradingMode.PAPER
            and (
                getattr(request.app.state, "bot_f21_enabled", False) is True
                or getattr(request.app.state, "paper_test_strategy_enabled", False) is True
            )
            and (run is None or replacement is not None)
            and pending_request_id is None
        ),
        unavailable_reason=(
            None
            if mode is TradingMode.PAPER
            and (
                getattr(request.app.state, "bot_f21_enabled", False) is True
                or getattr(request.app.state, "paper_test_strategy_enabled", False) is True
            )
            else _unavailable(mode)
        ),
        exposure_available=exposure_available,
        positions=positions,
        protections=protections,
        protections_more=protections_more,
        readiness_reason=None if run is None else run.readiness_reason,
        pinned_configuration=pinned,
        basket_target=basket_target,
        basket_triggered=basket_triggered,
        open_entries=open_entries,
        replacement=replacement,
    )


@router.post("/paper/bots/requests", response_model=BotReceiptView, status_code=202)
@router.post("/live/bots/requests", response_model=BotReceiptView, status_code=202)
async def request_start(
    request: Request, response: Response, who: Who, key: Key, body: BotStartInput
) -> BotReceiptView:
    mode = _mode(request)
    if mode is TradingMode.LIVE:
        raise HTTPException(503, _unavailable(mode))
    try:
        async with user_session(engine_for(request, DatabaseRole.API), who.user_id) as session:
            previous = await receipt_by_key(session, mode, key)
            if previous is None:
                # A deployment-owned allowlist is installed only after the
                # scheduler and registry pass activation checks. Default closed.
                if (
                    body.strategy_config_ref.startswith("paper-test:")
                    and getattr(request.app.state, "paper_test_strategy_enabled", False) is not True
                ):
                    raise HTTPException(503, _unavailable(mode))
                refs = getattr(request.app.state, "bot_paper_configurations", None)
                allowed = isinstance(refs, frozenset) and body.strategy_config_ref in refs
                if not allowed and (
                    getattr(request.app.state, "bot_f21_enabled", False) is True
                    or getattr(request.app.state, "paper_test_strategy_enabled", False) is True
                ):
                    config = await read_configuration(session, body.strategy_config_ref)
                    allowed = (
                        isinstance(config, PaperTestConfig)
                        and getattr(request.app.state, "paper_test_strategy_enabled", False) is True
                    ) or (
                        isinstance(config, RsiStepGridConfig)
                        and getattr(request.app.state, "bot_f21_enabled", False) is True
                    )
                if not allowed:
                    raise HTTPException(503, _unavailable(mode))
                await spend_token(
                    paper_mutation_engine(request), who.user_id, Bucket.PAPER_ORDER_NEW
                )
            receipt = await submit_start(
                session,
                mode=mode,
                request_id=uuid4(),
                key=key,
                payload=body.model_dump(mode="json"),
            )
        response.status_code = 200 if previous is not None else 202
        return _receipt(receipt)
    except BotRequestConflictError:
        raise HTTPException(409, "BOT_REQUEST_IDEMPOTENCY_CONFLICT") from None
    except InfraError:
        raise HTTPException(503, "BOT_STATUS_UNAVAILABLE") from None


@router.get("/paper/bots/requests/by-key/{key}", response_model=BotReceiptView)
@router.get("/live/bots/requests/by-key/{key}", response_model=BotReceiptView)
async def request_by_key(key: UUID, request: Request, who: Who) -> BotReceiptView:
    try:
        async with repeatable_user_session(
            engine_for(request, DatabaseRole.API), who.user_id
        ) as session:
            return _receipt(await receipt_by_key(session, _mode(request), key))
    except InfraError:
        raise HTTPException(503, "BOT_STATUS_UNAVAILABLE") from None


@router.get("/paper/bots/requests/{request_id}", response_model=BotReceiptView)
@router.get("/live/bots/requests/{request_id}", response_model=BotReceiptView)
async def request_by_id(request_id: UUID, request: Request, who: Who) -> BotReceiptView:
    try:
        async with repeatable_user_session(
            engine_for(request, DatabaseRole.API), who.user_id
        ) as session:
            return _receipt(await receipt_by_id(session, _mode(request), request_id))
    except InfraError:
        raise HTTPException(503, "BOT_STATUS_UNAVAILABLE") from None
