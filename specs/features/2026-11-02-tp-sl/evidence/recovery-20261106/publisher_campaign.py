"""One authorized diagnostic using existing fixtures and unchanged acceptance."""
import argparse,asyncio,hashlib,json,os,pathlib,shutil,subprocess,sys,time
from uuid import uuid4
ROOT=pathlib.Path('/Users/chainarongjaykeaw/Projects/TiewTrade/Projects/TiewTrade-paper-set4-recovery')
BACKEND=ROOT/'backend'
RECORDS=ROOT.parent/'f17-recovery-records-20261106'
sys.path[:0]=[str(BACKEND/'src'),str(BACKEND)]
from tests.infra.execution_market.profile_checkpoint_isolation import clone_database,database_environment,child,verify_databases
from tests.infra.execution_market import profile_workload as workload
EVIDENCE=ROOT/'specs/features/2026-11-02-tp-sl/evidence/recovery-20261106'
EVIDENCE.mkdir(exist_ok=False)
for pattern in ('recovery-*.log','recovery-tests.xml','publisher-*.log','publisher-*.xml','recovered-before-publisher-timing-sha256.json','recovery-test-selection.json'):
 for p in RECORDS.glob(pattern):shutil.copyfile(p,EVIDENCE/p.name)

def hashes():
 paths=[p for part in ('backend/src','backend/tests','backend/migrations') for p in (ROOT/part).rglob('*.py')]
 paths += [ROOT/p for p in ('backend/uv.lock','backend/pyproject.toml','compose.yaml','config/postgres.env')]
 return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}

async def main():
 database='tiewtrade_set4_iso_publisher_'+uuid4().hex[:8]
 env=database_environment(json.loads((RECORDS/'checks-env.json').read_text()),database)
 env['PYTHONPATH']=str(BACKEND/'src')+os.pathsep+str(BACKEND)
 private=RECORDS/'publisher-env.json';private.touch(mode=0o600,exist_ok=False);private.write_text(json.dumps(env))
 args=argparse.Namespace(parent_poll_limit=4,phase='SMOKE',owners=100,baseline_orders=20,cycles_per_owner=6,rate=10,workers=20,r8_claim_budget=True,coordinate_claims=True,publisher_heartbeat_per_book=True,final_tail_drain=True,diagnostics=True,worker_only=False,baseline_manifest=None,fault_schedule=None,redis_container=None,output=EVIDENCE/'publisher-diagnostic-1')
 candidate=hashes();workload.save(EVIDENCE/'candidate-sha256.json',candidate)
 free=shutil.disk_usage(ROOT).free
 if free<2*1024**3:raise RuntimeError('insufficient campaign disk headroom')
 running=subprocess.check_output(['docker','ps','--format','{{.Names}}\t{{.Status}}'],text=True).splitlines()
 workload.save(EVIDENCE/'campaign.json',{'authorization':'Owner approved baseline publisher timing and one unchanged diagnostic','database':database,'args':vars(args),'budget_seconds':1200,'started_wall':time.time(),'free_bytes_before':free,'host_load_before':os.getloadavg(),'docker_running_before':running,'acceptance_result':False})
 start=time.monotonic();status='INCOMPLETE';code=1;failure=None
 try:
  async with asyncio.timeout(1200):
   await clone_database(database,None,BACKEND,EVIDENCE/'create.log')
   await child([sys.executable,'-m','alembic','upgrade','head'],BACKEND,env,EVIDENCE/'migration.log')
   for key in list(os.environ):
    if key.startswith('TIEWTRADE_'):del os.environ[key]
   os.environ.update(env)
   workload.save(EVIDENCE/'database-identity.json',await verify_databases(database))
   code=await workload.run(args)
   status='OBSERVATION_COMPLETE' if code==0 else 'COMPLETED_WITH_FAILED_CRITERIA'
 except BaseException as error:
  failure={'type':type(error).__name__}
  raise
 finally:
  unchanged=candidate==hashes()
  workload.save(EVIDENCE/'campaign-result.json',{'status':status,'exit_code':code,'seconds':time.monotonic()-start,'database':database,'error':failure,'candidate_unchanged':unchanged,'free_bytes_after':shutil.disk_usage(ROOT).free,'acceptance_result':False})
  query=f"SELECT json_build_object('connections',(SELECT count(*) FROM pg_stat_activity WHERE datname='{database}'),'advisory_locks',(SELECT count(*) FROM pg_locks l JOIN pg_database d ON d.oid=l.database WHERE d.datname='{database}' AND l.locktype='advisory'))"
  check=subprocess.run(['docker','exec','tiewtrade-postgres-1','psql','-U','postgres','-At','-c',query],capture_output=True,text=True,timeout=15,check=True)
  workload.save(EVIDENCE/'cleanup.json',{'database':database,**json.loads(check.stdout)})
  if not unchanged:raise RuntimeError('candidate changed during diagnostic')
 return code
if __name__=='__main__':raise SystemExit(asyncio.run(main()))
