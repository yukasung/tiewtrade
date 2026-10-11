"""One physical F-11 job per API process, without a waiting queue."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import HTTPException

from tiewtrade.infra.realtime.admission import AdmissionOutcome, RedisAdmission


class IndicatorBudget:
    def __init__(self) -> None:
        self.busy = False

    @asynccontextmanager
    async def reserve(self, admission: RedisAdmission, user_id: UUID) -> AsyncIterator[None]:
        if self.busy:
            raise HTTPException(503, "INDICATOR_BUSY", headers={"Retry-After": "1"})
        self.busy = True
        try:
            outcome = await admission.outcome(str(user_id))
            if outcome is AdmissionOutcome.DENIED:
                raise HTTPException(429, "INDICATOR_RATE_LIMITED", headers={"Retry-After": "60"})
            if outcome is AdmissionOutcome.UNAVAILABLE:
                raise HTTPException(503, "INDICATOR_ADMISSION_UNAVAILABLE")
            yield
        finally:
            self.busy = False
