import asyncio,json
from pathlib import Path
from uuid import UUID
from tiewtrade.infra.db import DatabaseRole,create_engine_for,user_session
from tests.infra.execution_market.profile_workload import measured_transaction_seconds,percentile
ROOT=Path('/Users/chainarongjaykeaw/Projects/TiewTrade/Projects/TiewTrade-paper-set4-recovery')
r=ROOT/'specs/features/2026-11-02-tp-sl/evidence/recovery-20261106/nc12-w1'
async def main():
 w=json.loads((r/'run/processing-window.json').read_text()); paths=list((r/'run').glob('worker-*.json'));end=w['failure_observed'];bins=[]
 for offset in range(0,int(end-w['started'])+1,300):
  a=w['started']+offset;b=min(a+300,end);v=measured_transaction_seconds(paths,started=a,ended=b)
  if v:bins.append({'from_seconds':offset,'to_seconds':b-w['started'],'samples':len(v),'p95_ms':percentile(v,.95)*1000,'p99_ms':percentile(v,.99)*1000,'max_seconds':max(v)})
 resources=json.loads((r/'run/resources.json').read_text());v=measured_transaction_seconds(paths,started=w['started'],ended=end)
 summary={'scope':'post-stop read-only evidence; partial timing is not W1 acceptance','measured_until_failure_seconds':end-w['started'],'samples':len(v),'p95_ms':percentile(v,.95)*1000,'p99_ms':percentile(v,.99)*1000,'max_seconds':max(v),'bins':bins,'resource_samples':len(resources),'connections_start':resources[0]['connections'],'connections_last_incomplete':resources[-1]['connections'],'connections_peak':max(x['connections'] for x in resources),'lock_waits_peak':max(x['lock_waits'] for x in resources),'database_growth_bytes':resources[-1]['database_bytes']-resources[0]['database_bytes']}
 (r/'partial-metrics.json').write_text(json.dumps(summary,indent=2)+'\n'); print(json.dumps(summary,indent=2))
 engine=create_engine_for(DatabaseRole.ENGINE)
 try:
  async with user_session(engine,UUID('a33d332f-12d7-479e-b445-646dc6b8f18c'),role=DatabaseRole.ENGINE) as session:
   await session.execute('SET TRANSACTION READ ONLY')
   statement='''EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) SELECT terminal.value FROM paper_orders o
    JOIN paper_order_events e ON e.episode_id=o.episode_id AND e.base=o.base AND e.quote=o.quote
    CROSS JOIN LATERAL jsonb_array_elements(e.payload->'terminal_orders') terminal(value)
    WHERE o.id=:order AND e.payload ? 'matching'
    AND terminal.value->'intent'->>'order_id'=CAST(:order AS text)
    ORDER BY ((e.payload->>'decision_sequence')::bigint) DESC LIMIT 1'''
   plan=(await session.execute(statement,{'order':UUID('ccff0e57-e156-4033-a538-6e3d5e605d3d')})).scalar_one()
   (r/'terminal-query-poststop-plan.json').write_text(json.dumps({'scope':'same engine role and owner RLS, read-only, after workers stopped; not in-run timing','plan':plan},indent=2)+'\n'); print('poststop query execution_ms',plan[0]['Execution Time'])
 finally:await engine.dispose()
asyncio.run(main())
