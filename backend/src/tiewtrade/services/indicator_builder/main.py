"""Builder launcher and explicit migrator-only recovery command."""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from uuid import UUID, uuid4

from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.infra.db.engine import database_url
from tiewtrade.infra.indicators.maintenance import RetryResult, collect, retry_job
from tiewtrade.infra.indicators.recovery import ReapResult, reap_verified_container
from tiewtrade.infra.indicators.rollout import (
    Mode,
    inspect_rollout,
    load_inventory,
    orchestrate,
    retirement_ready,
)
from tiewtrade.services.indicator_builder.events import record
from tiewtrade.services.indicator_builder.supervisor import supervise
from tiewtrade.services.indicator_builder.worker import install_stop_handlers


async def launch() -> int:
    database_url(DatabaseRole.INDICATOR_BUILDER)  # Validate without printing a URL.
    owner = uuid4()
    stop = asyncio.Event()
    install_stop_handlers(stop)
    record("boot", owner)
    result = await supervise(owner, stop)
    status = (
        "FORCED"
        if result.forced
        else (
            "DRAINED"
            if result.exit_code == 0
            else "RECOVERY_REQUIRED"
            if result.exit_code == 12
            else "FAILED"
        )
    )
    record("stopped", owner, status)
    return result.exit_code if result.exit_code >= 0 else 12


async def recover(container: str, owner: UUID, epoch: UUID, fence: int) -> int:
    engine = create_engine_for(
        DatabaseRole.MIGRATOR, pool_size=1, max_overflow=0, pool_timeout=0.25
    )
    try:
        result = await reap_verified_container(engine, container, owner, epoch, fence)
        record("reap", owner, result.value)
        return 0 if result is ReapResult.REAPED else 12
    finally:
        async with asyncio.timeout(2):
            await engine.dispose()


async def maintenance(command: str, job: UUID | None = None, request: UUID | None = None) -> int:
    engine = create_engine_for(
        DatabaseRole.INDICATOR_BUILDER, pool_size=1, max_overflow=0, pool_timeout=0.25
    )
    try:
        if command == "retry":
            assert job is not None and request is not None
            result = await retry_job(engine, job, request)
            record("retry", None, result.value)
            return 0 if result is RetryResult.QUEUED else 12
        await collect(engine)
        record("gc", None, "COLLECTED")
        return 0
    finally:
        async with asyncio.timeout(2):
            await engine.dispose()


async def rollout(args: argparse.Namespace) -> int:
    engine = create_engine_for(
        DatabaseRole.MIGRATOR, pool_size=1, max_overflow=0, pool_timeout=0.25
    )
    try:
        if args.command == "rollout-status":
            result = await inspect_rollout(engine)
        elif args.command == "rollout-retire-check":
            result = await retirement_ready(engine, load_inventory(args.inventory))
        else:
            result = await orchestrate(
                engine,
                load_inventory(args.inventory),
                Mode(args.expected_mode),
                args.expected_epoch,
                Mode(args.target),
                evidence=args.evidence,
            )
        # Control identity contains no keys, cursor tokens, credentials or inputs.
        sys.stdout.write(json.dumps(result, default=str, sort_keys=True) + "\n")
        return (
            0
            if args.command == "rollout-status"
            or result.get("result") in ("APPLIED", "ALREADY_APPLIED", "RETIREMENT_READY")
            else 12
        )
    finally:
        async with asyncio.timeout(2):
            await engine.dispose()


def _uuid(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError:
        raise argparse.ArgumentTypeError("UUID_REQUIRED") from None


def _fence(value: str) -> int:
    try:
        parsed = int(value)
        if not 0 <= parsed <= 2**63 - 1:
            raise ValueError()
        return parsed
    except ValueError:
        raise argparse.ArgumentTypeError("FENCE_REQUIRED") from None


def main() -> int:
    parser = argparse.ArgumentParser(prog="indicator-builder")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("run")
    reap = commands.add_parser("reap")
    reap.add_argument("--container", required=True)
    reap.add_argument("--owner", type=_uuid, required=True)
    reap.add_argument("--slot-epoch", type=_uuid, required=True)
    reap.add_argument("--fence", type=_fence, required=True)
    retry = commands.add_parser("retry")
    retry.add_argument("--job-id", type=_uuid, required=True)
    retry.add_argument("--request-id", type=_uuid, required=True)
    commands.add_parser("gc")
    commands.add_parser("rollout-status")
    retire = commands.add_parser("rollout-retire-check")
    retire.add_argument("--inventory", type=Path, required=True)
    transition = commands.add_parser("rollout")
    transition.add_argument("--inventory", type=Path, required=True)
    transition.add_argument("--expected-mode", choices=list(Mode), required=True)
    transition.add_argument("--expected-epoch", type=_uuid, required=True)
    transition.add_argument("--target", choices=list(Mode), required=True)
    transition.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "run":
            return asyncio.run(launch())
        if args.command == "retry":
            return asyncio.run(maintenance("retry", args.job_id, args.request_id))
        if args.command == "gc":
            return asyncio.run(maintenance("gc"))
        if args.command in ("rollout", "rollout-status", "rollout-retire-check"):
            return asyncio.run(rollout(args))
        return asyncio.run(recover(args.container, args.owner, args.slot_epoch, args.fence))
    except (KeyboardInterrupt, asyncio.CancelledError):
        record("stop", None, "STOP_UNCONFIRMED")
        return 12
    except Exception:
        # Fixed operational category only: never print exceptions, config or driver text.
        record("failure", None, "OPERATIONAL_FAILURE")
        return 13


if __name__ == "__main__":
    raise SystemExit(main())
