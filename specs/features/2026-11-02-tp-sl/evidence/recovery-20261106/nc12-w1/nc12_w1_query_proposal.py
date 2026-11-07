import asyncio,json
from pathlib import Path
from uuid import UUID
from tiewtrade.infra.db import DatabaseRole,create_engine_for,user_session
from tests.infra.execution_market.profile_workload import measured_transaction_seconds,percentile
ROOT=Path('/Users/chainarongjaykeaw/Projects/TiewTrade/Projects/TiewTrade-paper-set4-recovery')
r=ROOT/'specs/features/2026-11-02-tp-sl/evidence/recovery-20261106/nc12-w1'
async def main():
 engine=create_engine_for(DatabaseRole.ENGINE)
 try:
  async with user_session(engine,UUID('a33d332f-12d7-479e-b445-646dc6b8f18c'),role=DatabaseRole.ENGINE) as session:
   await session.execute('SET TRANSACTION READ ONLY')
   statement="""EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)
    SELECT matched.value FROM paper_orders o
    CROSS JOIN LATERAL (
     SELECT terminal.value FROM paper_order_events e
     CROSS JOIN LATERAL jsonb_array_elements(e.payload->'terminal_orders') terminal(value)
     WHERE e.episode_id=o.episode_id AND e.base=o.base AND e.quote=o.quote
       AND e.payload ? 'matching'
       AND terminal.value->'intent'->>'order_id'=CAST(o.id AS text)
     ORDER BY ((e.payload->>'decision_sequence')::bigint) DESC LIMIT 1
    ) matched WHERE o.id=:order"""
   plan=(await session.execute(statement,{'order':UUID('ccff0e57-e156-4033-a538-6e3d5e605d3d')})).scalar_one()
   (r/'terminal-query-proposed-poststop-plan.json').write_text(json.dumps({'scope':'one proposed SELECT only, same engine role and RLS after workers stopped; no production edit or campaign rerun','plan':plan},indent=2)+'\n'); print('proposed query execution_ms',plan[0]['Execution Time'])

 finally:await engine.dispose()
asyncio.run(main())
