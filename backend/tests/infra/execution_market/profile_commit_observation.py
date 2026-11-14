"""Opt-in fixture worker completion evidence; never trading state or acceptance."""

import json
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from time import monotonic
from typing import Any

from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from tests.infra.execution_market.profile_workload import save
from tiewtrade.infra.db import session as db
from tiewtrade.infra.db.session import UserSession
from tiewtrade.infra.paper_orders.dispatch import ClaimedOrder
from tiewtrade.services.engine import paper_order

_KEY = "f15_completion_observation"
ROW_LIMIT = 5000


@contextmanager
def observe_commits(path: Path) -> Iterator[None]:
    """Capture owner-scoped status before exit, confirmation only after commit reply."""
    original_begin = db._begin
    original_process = vars(paper_order)["process_claimed_order"]
    rows: list[dict[str, Any]] = []
    truncated = False

    async def process(session: UserSession, claim: ClaimedOrder, **kwargs: Any) -> None:
        await original_process(session, claim, **kwargs)
        row = (
            (
                await session.execute(
                    """SELECT c.id AS command_id,c.order_id,p.status,r.state AS result_state
                FROM paper_order_commands c
                LEFT JOIN paper_order_projections p ON p.order_id=c.order_id
                LEFT JOIN paper_order_command_results r ON r.command_id=c.id
                WHERE c.id=:command""",
                    {"command": claim.command_id},
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is not None:
            session._connection.info[_KEY] = {
                "owner": str(session.user_id),
                "command_id": str(row["command_id"]),
                "order_id": str(row["order_id"]),
                "status": row["status"],
                "result_state": row["result_state"],
                "sampled": monotonic(),
            }

    @asynccontextmanager
    async def begin(
        engine: AsyncEngine, *, cleanup_seconds: float | None = None
    ) -> AsyncIterator[AsyncConnection]:
        nonlocal truncated
        metadata = None
        confirmed = False
        error_type = None
        started = monotonic()
        try:
            async with original_begin(engine, cleanup_seconds=cleanup_seconds) as connection:
                body_error: BaseException | None = None
                try:
                    yield connection
                except BaseException as error:
                    body_error = error
                    raise
                finally:
                    try:
                        metadata = connection.info.pop(_KEY, None)
                    except Exception as error:
                        if body_error is None:
                            raise
                        body_error.add_note(f"commit metadata read failed: {type(error).__name__}")
            confirmed = True
        except BaseException as error:
            error_type = type(error).__name__
            raise
        finally:
            if metadata is not None:
                if len(rows) >= ROW_LIMIT:
                    truncated = True
                    if error_type is None:
                        raise RuntimeError("completion observation bound exceeded")
                else:
                    rows.append(
                        {
                            **metadata,
                            "transaction_started": started,
                            "commit_confirmed": confirmed,
                            "finished": monotonic(),
                            "error_type": error_type,
                        }
                    )

    db._begin = begin
    vars(paper_order)["process_claimed_order"] = process
    primary: BaseException | None = None
    try:
        yield
    except BaseException as error:
        primary = error
        raise
    finally:
        vars(paper_order)["process_claimed_order"] = original_process
        db._begin = original_begin
        try:
            save(
                path,
                {
                    "acceptance_result": False,
                    "clock": "python_monotonic_same_runtime",
                    "commit_timestamp": "client confirmation upper bound, not server commit time",
                    "row_limit": ROW_LIMIT,
                    "truncated": truncated,
                    "rows": rows,
                },
            )
        except OSError as error:
            if primary is None:
                raise
            primary.add_note(f"commit observation write failed: {type(error).__name__}")


def correlate_observations(output: Path) -> dict[str, Any]:
    """Confirmation is an upper bound: preserve negative gaps and ambiguous deadlines."""
    receipts: list[dict[str, Any]] = []
    for path in sorted(output.glob("worker-*.commits.json")):
        document = json.loads(path.read_text())
        if document["truncated"]:
            raise ValueError("commit observation truncated")
        receipts.extend(row for row in document["rows"] if row["commit_confirmed"])
    command: dict[tuple[str, str], dict[str, Any]] = {}
    status: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in sorted(receipts, key=lambda row: row["finished"]):
        if row["result_state"] is not None:
            command.setdefault((row["owner"], row["command_id"]), row)
        if row["status"] is not None:
            status.setdefault((row["owner"], row["order_id"], row["status"]), row)
    phases = json.loads((output / "first-observations.json").read_text())["rows"]
    expired = output / "cycle-timeouts.json"
    if expired.exists():
        for cycle in json.loads(expired.read_text())["cycles"]:
            phases.extend(
                {**phase, "deadline": cycle["deadline_monotonic"]}
                for phase in cycle["phases"]
                if phase["phase"] in {"wait_command", "wait_status"}
                and phase["outcome"] != "returned"
            )
    joined = []
    missing = 0
    for phase in phases:
        kind = phase["phase"]
        if kind not in {"wait_command", "wait_status"}:
            continue
        if kind == "wait_command":
            commit = command.get((phase["owner"], phase["command_id"]))
        else:
            commit = status.get((phase["owner"], phase["order_id"], phase["expected_status"]))
        if commit is None:
            missing += 1
        observed = phase.get("finished_monotonic")
        deadline = phase.get("deadline")
        confirmation_vs_deadline = None
        if deadline is not None and commit is not None:
            if commit["finished"] <= deadline:
                confirmation_vs_deadline = "confirmed_before"
            elif commit["sampled"] > deadline:
                confirmation_vs_deadline = "commit_after"
            else:
                confirmation_vs_deadline = "ambiguous"
        joined.append(
            {
                "owner": phase["owner"],
                "kind": kind,
                "command_id": phase.get("command_id"),
                "order_id": phase.get("order_id"),
                "expected_status": phase.get("expected_status"),
                "phase_started": phase["started_monotonic"],
                "first_observed": observed,
                "worker_transaction_started": None
                if commit is None
                else commit["transaction_started"],
                "server_commit_lower_bound": None if commit is None else commit["sampled"],
                "client_confirmation_upper_bound": None if commit is None else commit["finished"],
                "observation_after_confirmation_seconds": None
                if observed is None or commit is None
                else observed - commit["finished"],
                "deadline": deadline,
                "confirmation_vs_deadline": confirmation_vs_deadline,
            }
        )
    return {
        "acceptance_result": False,
        "confirmed_worker_rows": len(receipts),
        "matched": len(joined) - missing,
        "missing": missing,
        "rows": joined,
    }
