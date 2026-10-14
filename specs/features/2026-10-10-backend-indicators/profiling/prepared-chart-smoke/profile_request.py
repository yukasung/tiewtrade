"""Instrument one isolated PREPARED request; overhead excludes it from latency claims."""
import asyncio
import cProfile
import io
import json
import os
from pathlib import Path
import pstats
from time import process_time, monotonic

import httpx

from tiewtrade.services.api.app import app
from tiewtrade.services.api.settings import CSRF_COOKIE, CSRF_HEADER


async def main():
    assert "tiewtrade-f11-capacity-postgres" in os.environ["TIEWTRADE_DATABASE_URL_API"]
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://fixture") as client:
            await client.get("/auth/csrf")
            response = await client.post("/auth/login", json={
                "email": os.environ["SMOKE_EMAIL"], "password": "capacity fixture password only"
            }, headers={CSRF_HEADER: client.cookies.get(CSRF_COOKIE)})
            assert response.status_code == 200
            profile = cProfile.Profile()
            started, cpu = monotonic(), process_time()
            profile.enable()
            response = await client.get("/market-data/chart/history", params={
                "base": os.environ.get("SMOKE_BASE", "BTC"), "quote": "USDT", "timeframe": "1m"
            })
            profile.disable()
            stats = io.StringIO()
            pstats.Stats(profile, stream=stats).sort_stats("cumulative").print_stats(45)
            Path("/evidence/request-profile.txt").write_text(stats.getvalue())
            result = {"status": response.status_code, "wall_seconds": monotonic() - started,
                      "cpu_seconds": process_time() - cpu,
                      "note": "Instrumented in-process ASGI, not browser/HTTP latency or parity acceptance"}
            Path("/evidence/request-profile.json").write_text(json.dumps(result, indent=2))
            print(json.dumps(result))


if __name__ == "__main__":
    asyncio.run(main())
