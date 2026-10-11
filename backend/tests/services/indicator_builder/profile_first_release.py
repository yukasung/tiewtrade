"""Approved R2-D1 first release; real immutable images, no legacy decoder stub."""

import json
import os
from collections.abc import AsyncIterator
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from time import monotonic
from typing import Any, cast
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.indicators.test_claims import builder_engine as builder_engine
from tests.infra.indicators.test_claims import clean_metadata
from tests.infra.indicators.test_rollout import control
from tests.services.indicator_builder.profile_container_recovery import docker
from tests.services.indicator_builder.profile_mixed_replicas import (
    PATH,
    QUERY,
    Replicas,
    authenticate,
)
from tests.services.indicator_builder.profile_mixed_replicas import (
    isolated_services as isolated_services,
)
from tests.services.indicator_builder.profile_mixed_replicas import (
    replicas as replicas,
)
from tiewtrade.core.market_data import CandleWindow, Timeframe
from tiewtrade.core.money import Money
from tiewtrade.infra.auth.sessions import hash_token, owner_of_presented
from tiewtrade.infra.crypto.indicator_cursor import CursorClaims, PreparedCursorClaims, verify
from tiewtrade.infra.crypto.keys import KeyPurpose, KeySource
from tiewtrade.infra.db.session import indicator_read_session, presented_session
from tiewtrade.infra.indicators.pinned import pinned_indicator_writer
from tiewtrade.infra.indicators.recovery import OwnerStopUnverifiedError
from tiewtrade.infra.indicators.rollout import (
    Container,
    Inventory,
    Mode,
    RolloutRejectedError,
    orchestrate,
    verify_inventory,
)
from tiewtrade.infra.market_data.indicator_reader import read_indicators
from tiewtrade.services.api.indicator_routes import IndicatorPointView, IndicatorValueView
from tiewtrade.services.api.settings import SESSION_COOKIE


@pytest_asyncio.fixture(autouse=True)
async def restore_first_release_fixture(migrator_engine: AsyncEngine) -> AsyncIterator[None]:
    assert "127.0.0.1:55433/" in os.environ["TIEWTRADE_DATABASE_URL_MIGRATOR"]
    try:
        yield
    finally:
        # Dependent replica/engine fixtures are closed before this privileged reset.
        await clean_metadata(migrator_engine)
        async with migrator_engine.begin() as c:
            await c.execute(text("SELECT begin_indicator_source_maintenance()"))
            await c.execute(text("DELETE FROM market_candles"))
            await c.execute(text("DELETE FROM market_candle_demand"))
            await c.execute(
                text("""DO $$ DECLARE p record; BEGIN
              FOR p IN SELECT relid FROM pg_partition_tree('market_candles'::regclass) LOOP
                EXECUTE format('DROP TRIGGER IF EXISTS indicator_source_statement ON %s',p.relid);
              END LOOP; END $$""")
            )
            await c.execute(text("DROP TRIGGER IF EXISTS indicator_source_rows ON market_candles"))
            await c.execute(text("DELETE FROM indicator_source_changes"))
            await c.execute(
                text("""UPDATE indicator_rollout_control SET
              mode='LEGACY',source_proof_state='PENDING' WHERE id=1""")
            )


async def legacy_write_cleanup(image: str) -> dict[str, Any]:
    program = """
import asyncio,json
from tiewtrade.infra.db import DatabaseRole,create_engine_for
from tiewtrade.infra.db.session import market_data_session
from tiewtrade.infra.market_data.claims import cleanup
async def run():
    engine=create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        async with market_data_session(engine) as s:
            await s.execute('''INSERT INTO market_candles
              (source,base,quote,timeframe,open_at,end_at,open,high,low,close,volume,
               finality,observed_at,fetch_started_at,last_checked_at,ingestion_generation)
              SELECT 'primary_spot','BTC','USDT','4h',moment,moment+interval '4 hours',
                100,102,99,100.5,1,'UNCONFIRMED',clock_timestamp(),clock_timestamp(),
                clock_timestamp(),1 FROM generate_series(
                  date_trunc('day',clock_timestamp())-interval '60 days',
                  date_trunc('day',clock_timestamp())-interval '4 hours',
                  interval '4 hours') moment
              ON CONFLICT(source,base,quote,timeframe,open_at) DO NOTHING''')
            await s.execute('''INSERT INTO market_candles
              (source,base,quote,timeframe,open_at,end_at,open,high,low,close,volume,
               finality,observed_at,fetch_started_at,last_checked_at,ingestion_generation)
              SELECT 'primary_spot','DOGE','USDT','1m',moment,moment+interval '1 minute',
                1,2,1,1,0,'CLOSED',clock_timestamp(),clock_timestamp(),clock_timestamp(),1
              FROM (SELECT date_trunc('minute',clock_timestamp()-interval '365 days 1 hour')
                    AS moment) t
              ON CONFLICT(source,base,quote,timeframe,open_at) DO NOTHING''')
            count=await cleanup(s)
        print(json.dumps({'result':'CLEANED','count':count}))
    except Exception as e:
        stack=[e]; seen=set(); blocked=False
        while stack:
            current=stack.pop()
            if id(current) in seen: continue
            seen.add(id(current))
            blocked |= (getattr(current,'sqlstate',None)=='TT011'
                        or getattr(current,'pgcode',None)=='TT011')
            for name in ('orig','__cause__','__context__'):
                nested=getattr(current,name,None)
                if isinstance(nested,BaseException): stack.append(nested)
        result={'result':'REJECTED','sqlstate':'TT011'} if blocked else {'result':'FAILED'}
        print(json.dumps(result))
    finally: await engine.dispose()
asyncio.run(run())
"""
    return cast(
        dict[str, Any],
        json.loads(
            await docker(
                "run",
                "--rm",
                "--network",
                "tiewtrade-f11-test-net",
                "-e",
                "TIEWTRADE_DATABASE_URL_MARKET_DATA="
                "postgresql+asyncpg://tiewtrade_market_data:dev_market_data@"
                "tiewtrade-f11-test-postgres:5432/tiewtrade",
                image,
                "python",
                "-c",
                program,
            )
        ),
    )


async def compatible_cleanup(image: str) -> dict[str, Any]:
    program = """
import asyncio,json
from tiewtrade.infra.db import DatabaseRole,create_engine_for
from tiewtrade.infra.db.session import market_data_session
from tiewtrade.infra.market_data.claims import cleanup
async def run():
    e=create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        async with market_data_session(e) as s:
            count=await cleanup(s)
        print(json.dumps({'count':count}))
    finally: await e.dispose()
asyncio.run(run())
"""
    raw = await docker(
        "run",
        "--rm",
        "--network",
        "tiewtrade-f11-test-net",
        "-e",
        "TIEWTRADE_DATABASE_URL_MARKET_DATA="
        "postgresql+asyncpg://tiewtrade_market_data:dev_market_data@"
        "tiewtrade-f11-test-postgres:5432/tiewtrade",
        image,
        "python",
        "-c",
        program,
    )
    return cast(dict[str, Any], json.loads(raw))


async def test_first_release_expand_v1_paging_drain_and_proof(
    replicas: Replicas,
    migrator_engine: AsyncEngine,
    api_engine: AsyncEngine,
    builder_engine: AsyncEngine,
) -> None:
    trace: list[dict[str, Any]] = []
    before = await control(migrator_engine)
    assert before["mode"] == "LEGACY" and before["source_proof_state"] == "PENDING"
    async with migrator_engine.begin() as c:
        schema_revision: str = (
            await c.execute(text("SELECT version_num FROM alembic_version"))
        ).scalar_one()
        assert (
            await c.execute(text("SELECT indicator_source_triggers_valid()"))
        ).scalar_one() is False
        assert (
            await c.execute(text("SELECT count(*) FROM indicator_build_jobs"))
        ).scalar_one() == 0
        await c.execute(text("DELETE FROM market_candles"))
    legacy = await docker("image", "inspect", "--format", "{{.Id}}", "tiewtrade-api:latest")
    old = await replicas.start(legacy)
    assert (await old.get("/health")).status_code == 200
    # Use the real old auth route, sharing its actual session with both new releases.
    replicas.clients[0], replicas.clients[2] = replicas.clients[2], replicas.clients[0]
    try:
        await authenticate(replicas)
        cookies = dict(old.cookies)
    finally:
        replicas.clients[0], replicas.clients[2] = replicas.clients[2], replicas.clients[0]
    for client in replicas.clients[:2]:
        client.cookies.update(cookies)
    schema = await old.get("/openapi.json")
    assert schema.status_code == 200 and PATH not in schema.json()["paths"]
    assert (await old.get(PATH, params=QUERY)).status_code == 403
    assert await legacy_write_cleanup(legacy) == {"result": "CLEANED", "count": 1}
    candle_query = {name: value for name, value in QUERY.items() if name != "page_size"}
    history = await old.get("/market-data/candles", params=candle_query)
    assert history.status_code == 200
    assert len(history.json()["rows"]) == 360
    assert all(
        Money.of(row["close"], "USDT") == Money.of("100.5", "USDT")
        for row in history.json()["rows"]
    )
    a, b = replicas.clients[:2]
    # Anchor to the inserted source, avoiding clock/day rollover and empty pages.
    source_start = min(datetime.fromisoformat(row["open_at"]) for row in history.json()["rows"])
    result_start = source_start + 300 * Timeframe.H4.span
    result_end = result_start + 12 * Timeframe.H4.span
    query = {**QUERY, "start": result_start.isoformat(), "end": result_end.isoformat()}
    first = await a.get(PATH, params=query)
    assert first.status_code == 200
    token = first.json()["next_cursor"]
    hashed = hash_token(str(a.cookies.get(SESSION_COOKIE)))
    async with presented_session(api_engine, token_hash=hashed) as s:
        owner = await owner_of_presented(s)
        assert owner is not None
    keys = KeySource.from_environment(KeyPurpose.INDICATOR_CURSOR)
    claims = verify(token, keys, owner.user_id, hashed)
    assert isinstance(claims, CursorClaims) and not isinstance(claims, PreparedCursorClaims)
    async with indicator_read_session(api_engine, owner.user_id) as source:
        reference = await read_indicators(
            source,
            "BTC",
            "USDT",
            Timeframe.H4,
            CandleWindow(claims.calculation_start, claims.calculation_end),
            CandleWindow(claims.result_start, claims.result_start + 8 * Timeframe.H4.span),
            claims.as_of,
            monotonic() + 30,
        )
    expected = [
        IndicatorPointView(
            open_at=p.open_at,
            seed_open_at=p.seed_open_at,
            finality=p.finality.value if p.finality else None,
            values={
                name: IndicatorValueView(
                    value=v.value.as_parts()["amount"]
                    if v.value is not None and hasattr(v.value, "as_parts")
                    else v.value.as_text()
                    if v.value is not None
                    else None,
                    unit=getattr(v.value, "currency", None),
                    status=v.status.value,
                )
                for name, v in p.values.items()
            },
        ).model_dump(mode="json")
        for p in reference.points
    ]
    assert len(expected) == 8
    assert all(
        point["seed_open_at"] is not None
        and all(
            value["value"] is not None and value["status"] == "READY"
            for value in point["values"].values()
        )
        for point in expected
    )

    def check(body: dict[str, Any], offset: int) -> str:
        assert len(body["rows"]) == 2 and body["rows"] == expected[offset : offset + 2]
        assert body["dataset_revision"] == reference.revision
        next_token: str = body["next_cursor"]
        assert verify(next_token, keys, owner.user_id, hashed) == claims.model_copy(
            update={
                "next_open_at": claims.result_start + (offset + 2) * Timeframe.H4.span,
            }
        )
        return next_token

    corrupted = deepcopy(first.json())
    value = next(iter(corrupted["rows"][0]["values"].values()))
    value["value"] = "999999"
    with pytest.raises(AssertionError):
        check(corrupted, 0)
    trace.append({"step": "numeric_mutation", "result": "rejected"})
    token = check(first.json(), 0)
    trace.append(
        {
            "step": "page",
            "replica": "A",
            "offset": 0,
            "http": first.status_code,
            "numeric_parity": True,
            "cursor_version": 1,
        }
    )
    for offset, client in ((2, b), (4, a)):
        response = await client.get(PATH, params={"cursor": token})
        assert response.status_code == 200
        token = check(response.json(), offset)
        trace.append(
            {
                "step": "page",
                "replica": "B" if offset == 2 else "A",
                "offset": offset,
                "http": response.status_code,
                "numeric_parity": True,
                "cursor_version": 1,
            }
        )
    await docker("restart", "--time", "2", replicas.containers[1])
    await replicas.refresh_address(1)
    await replicas.ready(b)
    response = await b.get(PATH, params={"cursor": token})
    assert response.status_code == 200
    check(response.json(), 6)
    trace.append(
        {
            "step": "page_after_restart",
            "replica": "B",
            "offset": 6,
            "http": response.status_code,
            "numeric_parity": True,
            "cursor_version": 1,
        }
    )
    async with pinned_indicator_writer(builder_engine, connection_mode="direct") as writer:
        assert writer is not None
        seeded = await writer.seed()
        claimed = await writer.claim(uuid4())
        assert seeded == 0 and claimed is None
        trace.append({"step": "before_stage", "seeded": seeded, "claim": claimed})
    await builder_engine.dispose()
    await api_engine.dispose()
    await replicas.stop_all()
    current = [
        Container(container_id=c, image_id=replicas.image_ids[i], service="api")
        for i, c in enumerate(replicas.containers[:2])
    ]
    current.append(Container(container_id=replicas.containers[2], image_id=legacy, service="api"))
    for service in ("market-data", "indicator-builder"):
        ident = await docker(
            "create",
            "--restart=no",
            "--network=none",
            "--label",
            f"com.docker.compose.project={replicas.project}",
            "--label",
            f"com.docker.compose.service={service}",
            replicas.image_ids[1],
            "sleep",
            "infinity",
        )
        replicas.containers.append(ident)
        current.append(
            Container(container_id=ident, image_id=replicas.image_ids[1], service=service)
        )
    inventory = Inventory(
        version=1,
        project=replicas.project,
        containers=tuple(current),
        external_paths_drained=True,
        legacy_restart_disabled=True,
        verification_keyring_verified=True,
        keyring_config_id="isolated-first-release",
    )
    # Missing/offline old replica cannot be hidden; included old image fails capability gate.
    with pytest.raises(RolloutRejectedError):
        await verify_inventory(
            inventory.model_copy(update={"containers": tuple(current[:2] + current[3:])})
        )
    trace.append({"step": "missing_offline_inventory", "result": "rejected"})
    await verify_inventory(inventory)
    await docker("update", "--restart=always", replicas.containers[2])
    with pytest.raises(RolloutRejectedError):
        await verify_inventory(inventory)
    trace.append({"step": "legacy_restart_policy", "result": "rejected"})
    await docker("update", "--restart=no", replicas.containers[2])
    with pytest.raises(OwnerStopUnverifiedError):
        await orchestrate(
            migrator_engine, inventory, Mode.LEGACY, before["rollout_epoch"], Mode.PREPARING
        )
    rejected = await control(migrator_engine)
    assert all(
        rejected[key] == before[key] for key in ("mode", "rollout_epoch", "source_proof_state")
    )
    trace.append({"step": "legacy_capability", "result": "rejected", "control_unchanged": True})
    await docker("rm", replicas.containers[2])
    replicas.containers.pop(2)
    inventory = inventory.model_copy(update={"containers": tuple(current[:2] + current[3:])})
    result = await orchestrate(
        migrator_engine, inventory, Mode.LEGACY, before["rollout_epoch"], Mode.PREPARING
    )
    assert result["result"] == "APPLIED"
    after = await control(migrator_engine)
    assert after["mode"] == "PREPARING" and after["source_proof_state"] == "READY"
    assert str(after["rollout_epoch"]) == result["epoch"]
    async with migrator_engine.connect() as c:
        assert (
            await c.execute(text("SELECT indicator_source_triggers_valid()"))
        ).scalar_one() is True
    assert await legacy_write_cleanup(legacy) == {"result": "REJECTED", "sqlstate": "TT011"}
    trace.append({"step": "legacy_write_after_proof", "sqlstate": "TT011"})
    for image in replicas.image_ids:
        assert await compatible_cleanup(image) == {"count": 0}
        trace.append({"step": "compatible_cleanup", "image": image, "count": 0})
    # Restart only compatible APIs after proof; LEGACY paging must now stop at stage gate.
    for index in range(2):
        await docker("start", replicas.containers[index])
        await replicas.refresh_address(index)
        await replicas.ready(replicas.clients[index])
        response = await replicas.clients[index].get(PATH, params=query)
        assert response.status_code == 503
        assert response.json() == {"detail": "INDICATOR_DATA_NOT_READY"}
        trace.append(
            {
                "step": "after_stage",
                "replica": "A" if index == 0 else "B",
                "http": response.status_code,
                "detail": response.json()["detail"],
            }
        )
    await replicas.stop_all()
    evidence = os.environ.get("TIEWTRADE_FIRST_RELEASE_EVIDENCE")
    if evidence:
        Path(evidence).write_text(
            json.dumps(
                {
                    "baseline": "owner-approved-first-release",
                    "legacy_image": legacy,
                    "compatible_images": replicas.image_ids,
                    "v1_pages": 4,
                    "stage": result,
                    "schema_revision": schema_revision,
                    "control": {
                        label: {
                            key: state[key]
                            for key in ("mode", "rollout_epoch", "source_proof_state")
                        }
                        for label, state in (("before", before), ("after", after))
                    },
                    "result_bounds": {"start": result_start, "end": result_end},
                    "dataset_revision": reference.revision,
                    "numeric_rows_verified": len(expected),
                    "trace": trace,
                    "production_activation": False,
                },
                default=str,
                indent=2,
            ),
            encoding="utf-8",
        )
