import ast, collections, hashlib, json, pathlib, statistics
from sqlalchemy import text
from sqlalchemy.dialects.postgresql.asyncpg import dialect
ROOT=pathlib.Path('/Users/chainarongjaykeaw/Projects/TiewTrade/Projects/TiewTrade-paper-set4-recovery')
E=ROOT/'specs/features/2026-11-02-tp-sl/evidence/recovery-20261106'
RUN=E/'publisher-diagnostic-1'
paths=['backend/src/tiewtrade/infra/db/session.py','backend/src/tiewtrade/infra/market_data/order_book_storage.py','backend/src/tiewtrade/infra/market_data/realtime_storage.py','backend/tests/infra/execution_market/profile_workload.py']
known=collections.defaultdict(list)
for name in paths:
 tree=ast.parse((ROOT/name).read_text())
 for node in ast.walk(tree):
  if not isinstance(node,ast.Constant) or not isinstance(node.value,str):continue
  sql=node.value
  if sql.lstrip().split(' ',1)[0].split('\n',1)[0].upper() not in {'WITH','SELECT','INSERT','UPDATE','DELETE','SET'}:continue
  try:fingerprint=hashlib.sha256(str(text(sql).compile(dialect=dialect())).encode()).hexdigest()
  except Exception:continue
  known[fingerprint].append({'file':name,'line':node.lineno})
rows=[];closed=None
with (RUN/'parent.transactions.jsonl').open() as stream:
 for line in stream:
  row=json.loads(line)
  if row.get('event')=='CLOSED':closed=row
  if row.get('phase') in {'publish_market','acquire_sources'}:rows.append(row)
def quantiles(values):
 if not values:return None
 values=sorted(values)
 return {'count':len(values),'total':sum(values),'mean':statistics.mean(values),'p95':values[int((len(values)-1)*.95)],'max':values[-1]}
summary={'publisher_transactions':len(rows),'closed':closed,'outcomes':dict(collections.Counter(r['outcome'] for r in rows)),'metrics':{key:quantiles([r[key] for r in rows if key in r]) for key in ('seconds','pool_wait_seconds','body_seconds','finalization_seconds')},'query_detail_truncated':any(r.get('query_detail_truncated') for r in rows),'slowest_transactions':[]}
for row in sorted(rows,key=lambda r:r['seconds'],reverse=True)[:10]:
 query_rows=[{**q,'source':known.get(q['hash'],[])} for q in row.get('query_details',[])]
 summary['slowest_transactions'].append({k:v for k,v in row.items() if k!='queries' and k!='query_details'}|{'queries':query_rows})
by_query=collections.defaultdict(list)
for row in rows:
 for q in row.get('query_details',[]):by_query[q['hash']].append(q['seconds'])
summary['queries']=sorted([{'hash':h,'source':known.get(h,[]),**quantiles(v)} for h,v in by_query.items()],key=lambda r:r['total'],reverse=True)
pubs=[r for r in rows if r.get('phase')=='publish_market']
summary['between_publications']=quantiles([right['started_monotonic']-left['finished_monotonic'] for left,right in zip(pubs,pubs[1:])])
summary['last_publications']=[{k:v for k,v in r.items() if k not in {'queries','query_details'}} for r in pubs[-5:]]
(E/'publisher-analysis.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k not in {'slowest_transactions','queries','last_publications'}},indent=2))
print('dominant queries',json.dumps(summary['queries'][:4],indent=2))
