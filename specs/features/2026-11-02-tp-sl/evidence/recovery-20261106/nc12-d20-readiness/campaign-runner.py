"""Record one approved NC12 phase using the existing profile runners."""
import argparse, asyncio, base64, hashlib, json, os, pathlib, platform, shutil, subprocess, sys, time
from datetime import datetime
from zoneinfo import ZoneInfo
ROOT=pathlib.Path('/Users/chainarongjaykeaw/Projects/TiewTrade/Projects/TiewTrade-paper-set4-recovery')
BACKEND=ROOT/'backend'
sys.path[:0]=[str(BACKEND/'src'),str(BACKEND)]
from tests.infra.execution_market import profile_internal as internal, profile_workload as workload, profile_protections as protection
from tiewtrade.infra.crypto import KEY_BYTES, KeyPurpose
from tiewtrade.infra.db import DatabaseRole, create_engine_for

def capture(*command):
 return subprocess.check_output(command,text=True,timeout=30).strip()
def hashes():
 paths=[p for part in ('backend/src','backend/tests','backend/migrations','frontend/src') for p in (ROOT/part).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
 paths += [ROOT/p for p in ('backend/uv.lock','backend/pyproject.toml','compose.yaml','config/postgres.env','frontend/package-lock.json') if (ROOT/p).exists()]
 return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}

async def main():
 parser=argparse.ArgumentParser();parser.add_argument('phase',choices=('CONTROLLED20','SMOKE','W1','W2','W3'));parser.add_argument('output',type=pathlib.Path);args=parser.parse_args()
 root=args.output;root.mkdir(parents=True,exist_ok=False)
 for purpose,value in ((KeyPurpose.TOTP_SECRET,b'T'),(KeyPurpose.VENUE_API_SECRET,b'V'),(KeyPurpose.INDICATOR_CURSOR,b'I')):
  os.environ[purpose.environment_variable]='1:'+base64.b64encode(value*KEY_BYTES).decode('ascii')
 database=internal.guard_database(dict(os.environ));candidate=hashes()
 workload.save(root/'candidate-sha256.json',candidate)
 free=shutil.disk_usage(ROOT).free
 containers=json.loads(capture('docker','inspect','tiewtrade-postgres-1','tiewtrade-f18-release-redis'))
 state=[{'name':c['Name'],'state':c['State']['Status'],'health':c['State'].get('Health',{}).get('Status'),'restart_count':c['RestartCount'],'nano_cpus':c['HostConfig']['NanoCpus'],'memory_limit':c['HostConfig']['Memory']} for c in containers]
 db_settings=json.loads(capture('docker','exec','tiewtrade-postgres-1','psql','-U','postgres','-d',database,'-At','-c',"SELECT json_object_agg(name,setting) FROM pg_settings WHERE name IN ('server_version','max_connections','shared_buffers','work_mem','maintenance_work_mem','synchronous_commit','fsync','full_page_writes','wal_level','max_wal_size','checkpoint_timeout')"))
 pools={}
 for role in (DatabaseRole.API,DatabaseRole.AUTH,DatabaseRole.ENGINE,DatabaseRole.ENGINE_SCAN,DatabaseRole.MARKET_DATA):
  engine=create_engine_for(role);pool=engine.pool
  pools[role.name]={'size':pool.size(),'max_overflow':pool._max_overflow,'timeout_seconds':pool.timeout()}
  await engine.dispose()
 options=argparse.Namespace(acceptance_profile=internal.NAME,parent_poll_limit=4,phase=args.phase,owners=20,baseline_orders=20,cycles_per_owner=0,rate=2,workers=20,r8_claim_budget=True,coordinate_claims=True,publisher_heartbeat_per_book=True,final_tail_drain=True,diagnostics=False,worker_only=False,baseline_manifest=None,fault_schedule=None,redis_container=None,output=root/'run')
 if args.phase!='CONTROLLED20':
  phase=internal.PHASES[args.phase];options.cycles_per_owner=phase.cycles_per_owner;options.rate=phase.rate
  if args.phase=='W3':
   options.fault_schedule=BACKEND/'tests/infra/execution_market/w3_fault_schedule.json';options.redis_container='tiewtrade-f18-release-redis'
  internal.validate(options)
 schema=capture('docker','exec','tiewtrade-postgres-1','pg_dump','-U','postgres','--schema-only',database)
 workload.save(root/'manifest.json',{'phase':args.phase,'profile':internal.NAME,'started_at':datetime.now(ZoneInfo('Asia/Bangkok')).isoformat(),'git_head':capture('git','-C',str(ROOT),'rev-parse','HEAD'),'database':database,'schema_sha256':hashlib.sha256(schema.encode()).hexdigest(),'python':sys.version,'platform':platform.platform(),'host_cpu':int(capture('sysctl','-n','hw.logicalcpu')),'host_ram_bytes':int(capture('sysctl','-n','hw.memsize')),'docker_vm':json.loads(capture('docker','info','--format','{"cpu":{{.NCPU}},"memory_bytes":{{.MemTotal}}}')),'containers':state,'all_containers':capture('docker','ps','-a','--format','{{.Names}} {{.Status}}').splitlines(),'free_bytes':free,'load':os.getloadavg(),'processes':capture('ps','-axo','pid,pcpu,rss,comm').splitlines(),'db_settings':db_settings,'pool_defaults':pools,'api_pool_overrides':{'paper_mutation':[1,0,0.5],'price':[3,0,0.5],'indicator':[1,0,0.25],'chart':[1,0,0.5]},'api_instances':0 if args.phase=='CONTROLLED20' else 1,'workers':20,'bridge_rounds_per_worker':True,'protection_rounds_per_worker':True,'claim_limit':1,'round_limit':20,'coordination':'SERIALIZED_CLAIM_V2','busy_backoff_seconds':0.250,'args':vars(options),'dataset':'fresh database; fixture/oracle pinned by source hashes; owner IDs emitted by runner','authorization':'NC12 sections5,9,11,12 approved; preserve all criteria'})
 status='INCOMPLETE';code=1;start=time.monotonic();error=None
 try:
  if free<2*1024**3:raise RuntimeError('insufficient campaign disk headroom')
  if any(c['state']!='running' for c in state) or state[0]['health']!='healthy':raise RuntimeError('campaign services not healthy')
  if any('Restarting' in line for line in capture('docker','ps','--format','{{.Status}}').splitlines()):raise RuntimeError('restarting shared service')
  await internal.require_empty_database()
  code=await (protection.run(root/'run') if args.phase=='CONTROLLED20' else workload.run(options))
  status='PASSED' if code==0 else 'FAILED'
 except BaseException as failure:
  error=type(failure).__name__;raise
 finally:
  unchanged=candidate==hashes()
  workload.save(root/'campaign-result.json',{'status':status,'exit_code':code,'seconds':time.monotonic()-start,'error_type':error,'candidate_unchanged':unchanged,'free_bytes_after':shutil.disk_usage(ROOT).free})
  query=f"SELECT json_build_object('connections',(SELECT count(*) FROM pg_stat_activity WHERE datname='{database}'),'advisory_locks',(SELECT count(*) FROM pg_locks l JOIN pg_database d ON d.oid=l.database WHERE d.datname='{database}' AND l.locktype='advisory'))"
  cleanup=json.loads(capture('docker','exec','tiewtrade-postgres-1','psql','-U','postgres','-d','postgres','-At','-c',query))
  workload.save(root/'cleanup.json',cleanup)
  if not unchanged:raise RuntimeError('candidate changed during campaign')
 return code
if __name__=='__main__':raise SystemExit(asyncio.run(main()))
