"""Sanitized validation responses for routes carrying sensitive user input."""

from collections.abc import Callable, Coroutine
from typing import Any, ClassVar

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from starlette.responses import Response


class SafeInputRoute(APIRoute):
    """Return only the route's fixed error code, never Pydantic input/errors."""

    rejection_code: ClassVar[str]

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        original = super().get_route_handler()

        async def without_raw_input(request: Request) -> Response:
            try:
                return await original(request)
            except RequestValidationError:
                return JSONResponse(
                    {"detail": self.rejection_code},
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                )

        return without_raw_input
