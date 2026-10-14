"""Bounded public observation for V-01, never part of normal tests."""

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from websockets.asyncio.client import connect


async def main() -> None:
    request = {
        "method": "SUBSCRIBE",
        "params": [
            f"{pair}@kline_{interval}"
            for pair in ("btcusdt", "ethusdt")
            for interval in ("1m", "5m", "15m", "1h", "4h", "1d")
        ],
        "id": 12,
    }
    frames: list[dict[str, str]] = []
    started = datetime.now(UTC).isoformat()
    outcome = "COMPLETE"
    try:
        async with asyncio.timeout(60):
            async with connect(
                "wss://nbstream.binance.th/w3w/wsa/stream",
                open_timeout=10,
                close_timeout=5,
                ping_interval=10,
                ping_timeout=5,
                max_size=65536,
                max_queue=16,
            ) as socket:
                await socket.send(json.dumps(request))
                while len(frames) < 100:
                    raw = await socket.recv()
                    frames.append({
                        "received_at": datetime.now(UTC).isoformat(),
                        "raw": raw.decode() if isinstance(raw, bytes) else raw,
                    })
    except (TimeoutError, OSError) as error:
        outcome = type(error).__name__
    destination = Path(__file__).with_name("kline-public.json")
    destination.write_text(json.dumps({
        "started_at": started,
        "ended_at": datetime.now(UTC).isoformat(),
        "connections": 1,
        "timeout_seconds": 60,
        "max_frames": 100,
        "request": request,
        "outcome": outcome,
        "frames": frames,
    }, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"outcome": outcome, "frames": len(frames)}))


if __name__ == "__main__":
    asyncio.run(main())
