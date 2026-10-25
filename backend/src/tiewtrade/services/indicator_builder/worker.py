"""Private supervised worker entry point. Runtime credentials cannot reap."""

import asyncio
import os
import signal
from datetime import UTC, datetime, timedelta
from uuid import UUID

from tiewtrade.infra.indicators.session import indicator_writer_session
from tiewtrade.infra.platform import record_protocol_heartbeat
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
    generation_text = os.environ.get("TIEWTRADE_CATALOG_DEPLOYMENT_GENERATION")
    heartbeat: asyncio.Task[None] | None = None
    try:
        if generation_text:
            generation = UUID(generation_text)

            async def beat() -> None:
                while not stop.is_set():
                    now = datetime.now(UTC)
                    async with indicator_writer_session(engine) as session:
                        await record_protocol_heartbeat(
                            session,
                            process_kind="INDICATOR_BUILDER",
                            instance_id=owner,
                            protocol_version=1,
                            deployment_generation=generation,
                            lease_expires_at=now + timedelta(seconds=30),
                        )
                    await asyncio.sleep(10)

            heartbeat = asyncio.create_task(beat())
        result = await run_scheduler(engine, owner, stop)
        if result is not None:
            record("attempt", owner, "ORPHANED")
        return 12 if result is not None else 0  # ORPHANED: do not accept further work.
    finally:
        if heartbeat is not None:
            heartbeat.cancel()
            await asyncio.gather(heartbeat, return_exceptions=True)
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
