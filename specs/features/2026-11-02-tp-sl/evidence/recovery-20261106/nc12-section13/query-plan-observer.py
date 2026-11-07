import asyncio,json
from pathlib import Path
from uuid import UUID
from unittest.mock import patch
from tiewtrade.infra.db import DatabaseRole,create_engine_for,user_session
from tiewtrade.infra.db.session import UserSession
from tiewtrade.infra.paper_orders.codec import order_payload
from tests.infra.execution_market.order_history_assertions import assert_terminal_history
ROOT=Path('/Users/chainarongjaykeaw/Projects/TiewTrade/Projects/TiewTrade-paper-set4-recovery')
OUT=ROOT/'specs/features/2026-11-02-tp-sl/evidence/recovery-20261106/nc12-section13'
async def main():
 OUT.mkdir(exist_ok=True);engine=create_engine_for(DatabaseRole.ENGINE);original=UserSession.execute;captured=[]
 async def observe(session,statement,parameters=None):
  if 'SELECT matched.value FROM paper_orders o' in statement:captured.append((statement,parameters))
  return await original(session,statement,parameters)
 try:
  async with user_session(engine,UUID('a33d332f-12d7-479e-b445-646dc6b8f18c'),role=DatabaseRole.ENGINE) as session:
   await session.execute('SET TRANSACTION READ ONLY')
   with patch.object(UserSession,'execute',observe):
    value=await assert_terminal_history(session,UUID('ccff0e57-e156-4033-a538-6e3d5e605d3d'))
   assert len(captured)==1
   statement,parameters=captured[0];plan=(await session.execute('EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) '+statement,parameters)).scalar_one()
   (OUT/'actual-query-plan.json').write_text(json.dumps({'scope':'read-only archived W1 data, actual production SELECT, original engine role and owner RLS; diagnostic only','old_new_state_equal':True,'state':order_payload(value),'statement':statement,'plan':plan},indent=2)+'\n')
   print('Old/new state equal; actual query execution_ms',plan[0]['Execution Time'])
 finally:await engine.dispose()
asyncio.run(main())
