import pathlib,json,subprocess,time,os,hashlib
root=pathlib.Path.cwd();scratch=pathlib.Path(pathlib.Path('/tmp/tiewtrade-lp01-location').read_text());e=root/'specs/features/2026-11-17-picomatch-remediation/evidence/lp01'
cases=[
('adversarial-star','+(*)','a'*32+'/',{},False,None),
('adversarial-star-a28','+(*a)','a'*28+'!',{},False,None),
('adversarial-star-a36','+(*a)','a'*36+'!',{},False,None),
('risky-literal','+(*a)','+(*a)',{},True,False),
('intentional-semantic-change','+(*a)','aaaa',{},False,True),
('js-positive','*.js','index.js',{},True,True),
('js-negative','*.js','index.ts',{},False,False),
('test-discovery','tests/**/*.test.ts','tests/unit/a.test.ts',{},True,True),
('negation','!**/*.test.ts','src/index.ts',{},True,True),
('dependency-exclusion','**/node_modules/**','frontend/node_modules/p/a.js',{},True,True),
('dotfile','**/.env','.env',{'dot':True},True,True),
('slash','**/*.ts','src/sub/a.ts',{},True,True),
('escaped-star',r'+(\*)','**',{},True,True),
('bracket-star','+([*])','**',{},True,True),
('quoted-star','+("*")','**',{},True,True),
('capture-literal-plus','+(a)','aaa',{'capture':True},True,True),
('literal-star','*(a)','aaa',{},True,True),
('existing-nested-safe','+(*(a)|*(b))','abba',{},True,True),
('nested-wildcard','+(@(*a))','a'*32+'!',{},False,None),
('explicit-opt-out','+(*a)','aaaa',{'maxExtglobRecursion':False},True,True)]
matrix=[{'id':i+1,'category':cat,'pattern':pat,'subject':subject,'options':opts,'expected_patched':expected,'expected_original':orig,'compare_original':orig is not None} for i,(cat,pat,subject,opts,expected,orig) in enumerate(cases)]
(e/'probe-matrix.json').write_text(json.dumps(matrix,indent=2)+'\n');script=r'''const [patched, original, raw] = process.argv.slice(1);
const c=JSON.parse(raw);const start=performance.now();
const value=require(patched)(c.pattern,c.options)(c.subject);
let baseline=null;if(c.compare_original) baseline=require(original)(c.pattern,c.options)(c.subject);
console.log(JSON.stringify({matched:value,baseline,elapsed_ms:performance.now()-start}));'''
(e/'probe-child.js').write_text(script);(e/'probe-runner.py').write_bytes(pathlib.Path(__file__).read_bytes())
rows=[];start=time.monotonic()
for c in matrix:
 t=time.monotonic();p=subprocess.Popen(['node','--max-old-space-size=256','-e',script,str(scratch/'patched/package'),str(scratch/'original/package'),json.dumps(c)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env={'PATH':os.environ['PATH']})
 try:
  stdout,stderr=p.communicate(timeout=2);outcome='RETURNED' if p.returncode==0 else 'ERROR';v=json.loads(stdout) if p.returncode==0 else {'stderr':stderr[:500]}
 except subprocess.TimeoutExpired:
  p.kill();stdout,stderr=p.communicate(timeout=2);outcome='TIMEOUT';v={}
 row={'id':c['id'],'category':c['category'],'outcome':outcome,'exit_code':p.returncode,'seconds':time.monotonic()-t,'joined':p.poll() is not None,**v}
 row['passed']=outcome=='RETURNED' and v.get('matched')==c['expected_patched'] and (not c['compare_original'] or v.get('baseline')==c['expected_original']);rows.append(row)
report={'status':'PASSED' if all(r['passed'] for r in rows) else 'FAILED','seconds':time.monotonic()-start,'cases':rows,'node':subprocess.check_output(['node','--version'],text=True).strip(),'maximum_children':1,'maximum_heap_mib':256,'per_child_deadline_seconds':2,'budget_seconds':60}
(e/'probe-results.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
