"""Atomic fixed-window pre-auth attempts. Redis downtime fails closed."""

import asyncio
import hashlib
from typing import Protocol


class AdmissionRedis(Protocol):
    async def eval(self, script: str, numkeys: int, *args: object) -> object: ...


# TIME anchors windows in Redis. Global check precedes all per-IP key creation.
# IP strings are hashed outside Redis; no tokens or cookies reach this store.
SCRIPT = """
local t = redis.call('TIME')
local window = math.floor(tonumber(t[1]) / 60)
local global = KEYS[1] .. ':' .. window
local total = tonumber(redis.call('GET', global) or '0')
if total >= tonumber(ARGV[1]) then return 0 end
redis.call('INCR', global)
redis.call('EXPIRE', global, 120)
local ip = KEYS[2] .. ':' .. window
local count = redis.call('INCR', ip)
redis.call('EXPIRE', ip, 120)
if count > tonumber(ARGV[2]) then return 0 end
return 1
"""


class RedisAdmission:
    def __init__(
        self,
        client: AdmissionRedis,
        *,
        global_limit: int = 200,
        ip_limit: int = 30,
        timeout: float = 0.5,
    ) -> None:
        if global_limit < 1 or ip_limit < 1 or not 0 < timeout <= 0.5:
            raise ValueError("invalid admission limits")
        self.client = client
        self.global_limit = global_limit
        self.ip_limit = ip_limit
        self.timeout = timeout

    async def admit(self, peer_ip: str | None) -> bool:
        peer_hash = hashlib.sha256((peer_ip or "unknown").encode()).hexdigest()
        try:
            async with asyncio.timeout(self.timeout):
                result = await self.client.eval(
                    SCRIPT,
                    2,
                    "market.ws.admission:global",
                    "market.ws.admission:ip:" + peer_hash,
                    self.global_limit,
                    self.ip_limit,
                )
                return result == 1
        except (TimeoutError, OSError):
            return False
        except Exception:
            # Redis errors are intentionally not exposed/logged with connection URLs.
            return False
