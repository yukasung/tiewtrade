"""Private supervised worker entry point. Runtime credentials cannot reap."""

import asyncio
import os
import signal
from uuid import UUID

from tiewtrade.services.indicator_builder.attempt import (
    CLEANUP_SECONDS,
    create_builder_engine,
)
from tiewtrade.services.indicator_builder.events import record
from tiewtrade.services.indicator_builder.scheduler import run_scheduler


def install_stop_handlers(stop: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            signal.signal(sig, lambda *_: loop.call_soon_threadsafe(stop.set))


async def serve(owner: UUID, stop: asyncio.Event) -> int:
    engine = create_builder_engine()
    try:
        result = await run_scheduler(engine, owner, stop)
        if result is not None:
            record("attempt", owner, "ORPHANED")
        return 12 if result is not None else 0  # ORPHANED: do not accept further work.
    finally:
        async with asyncio.timeout(CLEANUP_SECONDS):
            await engine.dispose()


async def _run() -> int:
    owner = UUID(os.environ.get("TIEWTRADE_INDICATOR_OWNER", ""))
    stop = asyncio.Event()
    install_stop_handlers(stop)
    record("worker_started", owner)  # Signals installed; not a prepared-data readiness claim.
    return await serve(owner, stop)


def main() -> int:
    try:
        return asyncio.run(_run())
    except (KeyboardInterrupt, asyncio.CancelledError):
        return 12
    except Exception:
        # Neither driver exception messages nor connection URLs reach stdout/stderr.
        return 13


if __name__ == "__main__":
    raise SystemExit(main())
