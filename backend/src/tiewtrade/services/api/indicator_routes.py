"""Authenticated, read-only F-11 API."""

from time import monotonic
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response

from tiewtrade.infra.market_data.storage import database_now
from tiewtrade.services.api.authentication import Authenticated, current_user
from tiewtrade.services.api.indicator_http import indicator_response, until_disconnect
from tiewtrade.services.api.indicator_read_controller import (
    IndicatorHistoryView as IndicatorHistoryView,
)
from tiewtrade.services.api.indicator_read_controller import (
    IndicatorPointView as IndicatorPointView,
)
from tiewtrade.services.api.indicator_read_controller import (
    IndicatorQuery as IndicatorQuery,
)
from tiewtrade.services.api.indicator_read_controller import (
    IndicatorValueView as IndicatorValueView,
)
from tiewtrade.services.api.indicator_read_controller import (
    read_history,
)
from tiewtrade.services.api.indicator_settings import INDICATOR_SETTINGS
from tiewtrade.services.api.safe_input_routes import SafeInputRoute


class IndicatorInputRoute(SafeInputRoute):
    rejection_code = "INPUT_REJECTED"


router = APIRouter(
    prefix="/market-data/indicators", tags=["market-data"], route_class=IndicatorInputRoute
)


async def _read(
    query: IndicatorQuery, request: Request, who: Authenticated, deadline: float
) -> IndicatorHistoryView:
    return (await read_history(query, request, who, deadline, clock=database_now)).view


async def _read_until_disconnect(
    query: IndicatorQuery, request: Request, who: Authenticated, deadline: float
) -> IndicatorHistoryView:
    return await until_disconnect(request, _read(query, request, who, deadline))


@router.get("", response_model=IndicatorHistoryView)
async def indicators(
    query: Annotated[IndicatorQuery, Query()],
    request: Request,
    who: Annotated[Authenticated, Depends(current_user)],
) -> Response:
    return await indicator_response(
        request,
        who,
        lambda deadline: _read(query, request, who, deadline),
        clock=monotonic,
        deadline_seconds=INDICATOR_SETTINGS.deadline_seconds,
    )
