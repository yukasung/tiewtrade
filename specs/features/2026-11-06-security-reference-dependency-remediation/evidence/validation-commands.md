# Temporary validation commands — 2026-11-06

สถานะ: Executed; evidence only, not a permanent CI/test helper.

Python commands used Python 3.12 executable recorded in feature-candidate.md. All ran
from this feature worktree; Node scripts used Node v22.23.4. Temporary root was read
from `/tmp/tiewtrade-reference-remediation-active-path`. Script digests are in safe JSON.
The following source is retained as a reproduction record; it is not added to application
or security-helper runtime paths. No raw scanner reports or credentials are included.

## tiewtrade-reference-prepare-20261106.py

```python
from pathlib import Path
import concurrent.futures, urllib.request, subprocess, json, hashlib, shutil, datetime
root=Path.cwd(); temp=Path('/tmp/tiewtrade-reference-remediation-active-path').read_text().strip(); temp=Path(temp)
research=json.loads((root/'specs/features/2026-11-06-security-reference-dependency-remediation/evidence/requirements-research.json').read_text())
def fetch(target):
    with urllib.request.urlopen(target['target']['url'], timeout=30) as response:
        data=json.load(response)
    assert data['name']==target['name'] and data['version']==target['target']['version']
    return target['name'],data
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    metadata=dict(pool.map(fetch,research['targets']))
advisories=[]
for a in research['high_alert_records']:
    data=json.loads(subprocess.check_output(['gh','api','advisories/'+a['id']],text=True))
    assert data['withdrawn_at'] is None and data['severity']=='high',a['id']
    advisories.append({k:data[k] for k in ['ghsa_id','severity','withdrawn_at','vulnerabilities']})
(temp/'registry-metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
(temp/'advisory-metadata.json').write_text(json.dumps(advisories,indent=2)+'\n')
base=json.loads((root/'references/admin-template/package-lock.json').read_text()); candidate=json.loads(json.dumps(base))
fields=['license','engines','dependencies','optionalDependencies','peerDependencies','peerDependenciesMeta','bin','os','cpu','funding','deprecated']
for name,data in metadata.items():
    key='node_modules/'+name; row=candidate['packages'][key]
    row.update(version=data['version'],resolved=data['dist']['tarball'],integrity=data['dist']['integrity'])
    for field in fields:
        if field in data: row[field]=data[field]
        else: row.pop(field,None)
changes=[k for k in base['packages'] if base['packages'][k]!=candidate['packages'][k]]
assert set(changes)=={'node_modules/'+n for n in metadata}
assert base.keys()==candidate.keys() and base['packages'].keys()==candidate['packages'].keys()
for label,lock in [('baseline',base),('candidate',candidate)]:
    stage=temp/('scan-'+label)
    (stage/'backend').mkdir(parents=True); (stage/'frontend').mkdir()
    shutil.copy2(root/'backend/uv.lock',stage/'backend/uv.lock')
    path=stage/'frontend/package-lock.json'
    if label=='baseline': shutil.copy2(root/'references/admin-template/package-lock.json',path)
    else: path.write_text(json.dumps(lock,indent=2)+'\n')
    ledger=[{'path':k,'name':v.get('name',k.rsplit('node_modules/',1)[-1]),'version':v['version']} for k,v in lock['packages'].items() if k]
    (temp/(label+'-inventory.json')).write_text(json.dumps(ledger,indent=2)+'\n')
shutil.copytree(root/'references/admin-template',temp/'template',ignore=shutil.ignore_patterns('node_modules','dist','.git'))
shutil.copy2(temp/'scan-candidate/frontend/package-lock.json',temp/'template/package-lock.json')
summary={'checked_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'changes':[{ 'path':k,'before':base['packages'][k]['version'],'after':candidate['packages'][k]['version'],'fields':[f for f in set(base['packages'][k])|set(candidate['packages'][k]) if base['packages'][k].get(f)!=candidate['packages'][k].get(f)]} for k in changes],'candidate_lock_sha256':hashlib.sha256((temp/'template/package-lock.json').read_bytes()).hexdigest()}
(temp/'update-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
```

## tiewtrade-reference-scan-20261106.py

```python
from pathlib import Path
import sys, json, hashlib, concurrent.futures, copy, collections, time
root=Path.cwd();sys.path.insert(0,str(root))
from tools.security import scan, dependencies
from tools.security.model import PolicyError
from tools.security.system import configuration
base=Path(Path('/tmp/tiewtrade-reference-remediation-active-path').read_text().strip())
binary=Path('/tmp/tiewtrade-security-tools-20261106/osv')
pins=json.loads((root/'.github/security/tools.json').read_text())
assert hashlib.sha256(binary.read_bytes()).hexdigest()==pins['tools']['osv']['platforms']['Darwin-arm64']['sha256']
original_execute=scan.execute
def capture(args,cwd,output,allowed):
    result=original_execute(args,cwd,output,allowed)
    label='baseline' if any('scan-baseline' in a for a in args) else 'candidate'
    (base/(label+'-osv-raw.json')).write_bytes(output.read_bytes())
    return result
scan.execute=capture
def run(label):
    start=time.monotonic();stage=base/('scan-'+label)
    fingerprint=hashlib.sha256((stage/'frontend/package-lock.json').read_bytes()).hexdigest()
    expected=dependencies.inventory(stage)
    findings,coverage=scan.scan_dependencies(stage,root,binary)
    assert hashlib.sha256((stage/'frontend/package-lock.json').read_bytes()).hexdigest()==fingerprint
    records=[{'severity':f.severity,'locator':list(f.locator)} for f in findings]
    result={'label':label,'lock_sha256':fingerprint,'expected_template_unique_packages':len(expected['frontend/package-lock.json']),'expected_backend_unique_packages':len(expected['backend/uv.lock']),'coverage_total':coverage,'severity_counts':dict(collections.Counter(f.severity for f in findings)),'findings':records,'seconds':round(time.monotonic()-start,2),'configuration_digest':configuration(root)}
    (base/(label+'-scan-summary.json')).write_text(json.dumps(result,indent=2)+'\n')
    return result
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    results=list(pool.map(run,['baseline','candidate']))
print(json.dumps(results,indent=2))
raw=json.loads((base/'candidate-osv-raw.json').read_text()); expected=dependencies.inventory(base/'scan-candidate')
for result in raw['results']:
    if result['source']['path'].endswith('/frontend/package-lock.json'):
        result['packages'].pop()
        break
else: raise AssertionError('template source missing')
try:
    dependencies.evaluate(raw,base/'scan-candidate',expected)
except PolicyError as exc:
    assert str(exc)=='INCOMPLETE_DEPENDENCY_INVENTORY',str(exc)
    (base/'negative-coverage.json').write_text(json.dumps({'result':'Passed','error':str(exc)})+'\n')
    print('Negative missing-package coverage control: Passed')
else: raise AssertionError('coverage mutation accepted')
```

## tiewtrade-reference-amend-20261106.py

```python
from pathlib import Path
import json,urllib.request,hashlib,shutil
root=Path.cwd();base=Path(Path('/tmp/tiewtrade-reference-remediation-active-path').read_text().strip())
for name in ['candidate-inventory.json','candidate-osv-raw.json','candidate-scan-summary.json','update-summary.json']:
    if (base/name).exists():shutil.copy2(base/name,base/('initial-'+name))
p=base/'template/package-lock.json';candidate=json.loads(p.read_text());baseline=json.loads((root/'references/admin-template/package-lock.json').read_text());metadata=json.loads((base/'registry-metadata.json').read_text())
fields=['license','engines','dependencies','optionalDependencies','peerDependencies','peerDependenciesMeta','bin','os','cpu','funding','deprecated']
for name,version in [('brace-expansion','5.0.11'),('zod','4.6.6')]:
    with urllib.request.urlopen(f'https://registry.npmjs.org/{name}/{version}',timeout=30) as response:d=json.load(response)
    assert d['name']==name and d['version']==version
    row=candidate['packages']['node_modules/'+name]
    row.update(version=version,resolved=d['dist']['tarball'],integrity=d['dist']['integrity'])
    for field in fields:
        if field in d:row[field]=d[field]
        else:row.pop(field,None)
    metadata[name]=d
changes=[k for k in baseline['packages'] if baseline['packages'][k]!=candidate['packages'][k]]
assert set(changes)=={'node_modules/'+n for n in metadata}
assert candidate['packages'].keys()==baseline['packages'].keys()
p.write_text(json.dumps(candidate,indent=2)+'\n');shutil.copy2(p,base/'scan-candidate/frontend/package-lock.json')
(base/'registry-metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
ledger=[{'path':k,'name':v.get('name',k.rsplit('node_modules/',1)[-1]),'version':v['version']} for k,v in candidate['packages'].items() if k]
(base/'candidate-inventory.json').write_text(json.dumps(ledger,indent=2)+'\n')
summary={'amendment':'NC-SEC-REF-01 Approved 2026-11-06','changes':[{'path':k,'before':baseline['packages'][k]['version'],'after':candidate['packages'][k]['version'],'fields':sorted(f for f in set(baseline['packages'][k])|set(candidate['packages'][k]) if baseline['packages'][k].get(f)!=candidate['packages'][k].get(f))} for k in changes],'candidate_lock_sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
(base/'update-summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
```

## tiewtrade-reference-rescan-20261106.py

```python
from pathlib import Path
import sys,json,hashlib,time,collections
root=Path.cwd();sys.path.insert(0,str(root))
from tools.security import scan,dependencies
from tools.security.model import PolicyError
from tools.security.system import configuration
base=Path(Path('/tmp/tiewtrade-reference-remediation-active-path').read_text().strip());binary=Path('/tmp/tiewtrade-security-tools-20261106/osv');stage=base/'scan-candidate'
pins=json.loads((root/'.github/security/tools.json').read_text());assert hashlib.sha256(binary.read_bytes()).hexdigest()==pins['tools']['osv']['platforms']['Darwin-arm64']['sha256']
original=scan.execute
def capture(args,cwd,output,allowed):
    status=original(args,cwd,output,allowed);(base/'candidate-osv-raw.json').write_bytes(output.read_bytes());return status
scan.execute=capture
expected=dependencies.inventory(stage);start=time.monotonic();findings,coverage=scan.scan_dependencies(stage,root,binary)
summary={'label':'candidate','amendment':'NC-SEC-REF-01 Approved','lock_sha256':hashlib.sha256((stage/'frontend/package-lock.json').read_bytes()).hexdigest(),'expected_template_unique_packages':len(expected['frontend/package-lock.json']),'expected_backend_unique_packages':len(expected['backend/uv.lock']),'coverage_total':coverage,'severity_counts':dict(collections.Counter(f.severity for f in findings)),'findings':[{'severity':f.severity,'locator':list(f.locator)} for f in findings],'seconds':round(time.monotonic()-start,2),'configuration_digest':configuration(root)}
(base/'candidate-scan-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
assert not any(f.severity in ['high','critical','unknown'] for f in findings),summary['severity_counts']
raw=json.loads((base/'candidate-osv-raw.json').read_text())
for result in raw['results']:
    if result['source']['path'].endswith('/frontend/package-lock.json'):result['packages'].pop();break
try:dependencies.evaluate(raw,stage,expected)
except PolicyError as exc:
    assert str(exc)=='INCOMPLETE_DEPENDENCY_INVENTORY';(base/'negative-coverage.json').write_text(json.dumps({'result':'Passed','error':str(exc)})+'\n')
else:raise AssertionError('Missing row was accepted')
print(json.dumps(summary,indent=2));print('candidate security gate and missing-row control passed')
```

## tiewtrade-reference-install-20261106.py

```python
from pathlib import Path
import json,os,subprocess,time,hashlib
base=Path(Path('/tmp/tiewtrade-reference-remediation-active-path').read_text().strip()); template=base/'template'
scan=json.loads((base/'candidate-scan-summary.json').read_text());assert not any(scan['severity_counts'].get(k,0) for k in ['high','critical','unknown'])
assert hashlib.sha256((template/'package-lock.json').read_bytes()).hexdigest()==scan['lock_sha256']
for name in ['empty-user-npmrc','empty-global-npmrc']:(base/name).write_text('')
env={k:os.environ[k] for k in ['PATH','HOME','TMPDIR','LANG','SHELL'] if k in os.environ}
env.update(npm_config_userconfig=str(base/'empty-user-npmrc'),npm_config_globalconfig=str(base/'empty-global-npmrc'),npm_config_audit='false',npm_config_fund='false')
start=time.monotonic()
with (base/'npm-ci.log').open('w') as log:result=subprocess.run(['npm','ci','--include=dev','--include=optional'],cwd=template,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=600)
summary={'command':'npm ci --include=dev --include=optional','exit_code':result.returncode,'seconds':round(time.monotonic()-start,2),'lock_sha256_after':hashlib.sha256((template/'package-lock.json').read_bytes()).hexdigest(),'credentials_environment':'minimal PATH/HOME/TMPDIR/LANG/SHELL; empty user/global npmrc; no token/password/secret variables'}
(base/'install-summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2));assert result.returncode==0
with (base/'npm-ls.json').open('w') as log:result=subprocess.run(['npm','ls','--all','--json'],cwd=template,env=env,stdout=log,stderr=subprocess.PIPE,timeout=90)
assert result.returncode==0,result.stderr.decode()[:1000]
print('npm ls --all --json: Passed')
```

## tiewtrade-reference-build-20261106.py

```python
from pathlib import Path
import subprocess,json,os,time,hashlib
base=Path(Path('/tmp/tiewtrade-reference-remediation-active-path').read_text().strip());template=base/'template'
env={k:os.environ[k] for k in ['PATH','HOME','TMPDIR','LANG','SHELL'] if k in os.environ};env.update(npm_config_userconfig=str(base/'empty-user-npmrc'),npm_config_globalconfig=str(base/'empty-global-npmrc'))
start=time.monotonic()
with (base/'build.log').open('w') as output:r=subprocess.run(['npm','run','build'],cwd=template,env=env,stdout=output,stderr=subprocess.STDOUT,timeout=600)
result={'exit_code':r.returncode,'seconds':round(time.monotonic()-start,2),'lock_sha256_after':hashlib.sha256((template/'package-lock.json').read_bytes()).hexdigest()}
(base/'build-summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));
if r.returncode:print((base/'build.log').read_text()[-3500:])
raise SystemExit(r.returncode)
```

## tiewtrade-reference-callers-20261106.cjs

```javascript
const fs=require('node:fs');const path=require('node:path');const {createRequire}=require('node:module');const assert=require('node:assert/strict');const {spawnSync}=require('node:child_process');
const base=fs.readFileSync('/tmp/tiewtrade-reference-remediation-active-path','utf8').trim();const template=path.join(base,'template');const req=createRequire(path.join(template,'package.json'));const checks=[];const versions={};
function versionFromEntry(entry,name){let p=path.dirname(entry);while(!fs.existsSync(path.join(p,'package.json'))||JSON.parse(fs.readFileSync(path.join(p,'package.json'))).name!==name){let next=path.dirname(p);assert.notEqual(next,p);p=next;}return JSON.parse(fs.readFileSync(path.join(p,'package.json'))).version;}
function check(name,fn){fn();checks.push(name);}
const postcssReq=createRequire(req.resolve('postcss'));const sm=postcssReq('source-map-js');versions['source-map-js']=versionFromEntry(postcssReq.resolve('source-map-js'),'source-map-js');assert.equal(versions['source-map-js'],'1.2.2');
const gen=new sm.SourceMapGenerator({file:'out.js'});gen.addMapping({generated:{line:1,column:0},original:{line:7,column:2},source:'fixture.ts'});
check('source-map generator/consumer round trip',()=>{const got=new sm.SourceMapConsumer(gen.toJSON()).originalPositionFor({line:1,column:0});assert.equal(got.source,'fixture.ts');assert.equal(got.line,7);assert.equal(got.column,2);});
check('source-map indexed sections',()=>{const consumer=new sm.SourceMapConsumer({version:3,sections:[{offset:{line:0,column:0},map:gen.toJSON()},{offset:{line:2,column:0},map:gen.toJSON()}]});assert.equal(consumer.originalPositionFor({line:3,column:1}).line,7);});
const cosReq=createRequire(req.resolve('cosmiconfig'));const yaml=cosReq('js-yaml');versions['js-yaml']=versionFromEntry(cosReq.resolve('js-yaml'),'js-yaml');assert.equal(versions['js-yaml'],'4.3.2');
const text='defaults: &defaults { retries: 2 }\njob:\n  <<: *defaults\n  enabled: true\nvalues: [a, b]\nordered: !!omap\n  - a: 1\n  - b: 2\n';const obj=yaml.load(text);
check('YAML mapping/sequence/anchor/merge/omap',()=>{assert.equal(obj.job.retries,2);assert.equal(obj.job.enabled,true);assert.deepEqual(obj.values,['a','b']);assert.deepEqual(obj.ordered,[{a:1},{b:2}]);});
check('YAML dump/load',()=>assert.deepEqual(yaml.load(yaml.dump(obj)),obj));
check('invalid YAML rejection',()=>assert.throws(()=>yaml.load('a: 1\na: 2\n')));
const yamlFile=path.join(base,'probe.yaml');fs.writeFileSync(yamlFile,text);check('cosmiconfig actual YAML loader',()=>assert.deepEqual(req('cosmiconfig').cosmiconfigSync('security-probe').load(yamlFile).config,obj));
const mm=req('minimatch');const mmReq=createRequire(req.resolve('minimatch'));versions['brace-expansion']=versionFromEntry(mmReq.resolve('brace-expansion'),'brace-expansion');assert.equal(versions['brace-expansion'],'5.0.11');
check('minimatch nested brace caller',()=>assert.deepEqual(mm.braceExpand('a{b,{c,d}}'),['ab','ac','ad']));
check('minimatch literal/escaped brace caller',()=>{assert.deepEqual(mm.braceExpand('plain'),['plain']);assert.deepEqual(mm.braceExpand('x\\{a,b\\}'),['x{a,b}']);assert.equal(mm.minimatch('ab','a{b,c}'),true);assert.equal(mm.minimatch('ad','a{b,c}'),false);});
const hooksReq=createRequire(req.resolve('eslint-plugin-react-hooks'));const zod=hooksReq('zod');versions.zod=versionFromEntry(hooksReq.resolve('zod'),'zod');assert.equal(versions.zod,'4.6.6');
check('Zod constrained valid/invalid collection via plugin resolution',()=>{const schema=zod.array(zod.string().max(4)).max(2);assert.equal(schema.safeParse(['a','bb']).success,true);assert.equal(schema.safeParse(['a','b','c']).success,false);assert.equal(schema.safeParse(['oversized']).success,false);});
const fixtureDir=path.join(template,'probe-fixtures');fs.mkdirSync(fixtureDir,{recursive:true});fs.writeFileSync(path.join(fixtureDir,'valid.tsx'),'import {useState} from "react"; export function Probe(){ const [value]=useState(1); return <span>{value}</span>; }\n');fs.writeFileSync(path.join(fixtureDir,'invalid.tsx'),'import {useState} from "react"; export function Probe({flag}:{flag:boolean}){ if(flag){useState(1);} return <span>probe</span>; }\n');
const environment={};for(const k of ['PATH','HOME','TMPDIR','LANG','SHELL'])if(process.env[k])environment[k]=process.env[k];
const lint=spawnSync(process.execPath,[path.join(template,'node_modules/eslint/bin/eslint.js'),'--format','json','probe-fixtures/valid.tsx','probe-fixtures/invalid.tsx'],{cwd:template,env:environment,encoding:'utf8',timeout:60000});fs.writeFileSync(path.join(base,'eslint-probe-raw.json'),lint.stdout||'');
check('actual ESLint config/plugin: valid fixture accepted, invalid hook rejected',()=>{assert.equal(lint.status,1,lint.stderr);const records=JSON.parse(lint.stdout);const valid=records.find(r=>r.filePath.endsWith('valid.tsx')&&!r.filePath.endsWith('invalid.tsx'));const invalid=records.find(r=>r.filePath.endsWith('invalid.tsx'));assert.equal(valid.errorCount,0);assert.equal(invalid.fatalErrorCount,0);assert(invalid.messages.some(m=>m.ruleId==='react-hooks/rules-of-hooks'));assert(records.every(r=>r.fatalErrorCount===0));});
fs.rmSync(fixtureDir,{recursive:true});const result={versions,checks,passed:checks.length};fs.writeFileSync(path.join(base,'callers-summary.json'),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result,null,2));
```

## tiewtrade-reference-map-baseline-20261106.py

```python
from pathlib import Path
import urllib.request,json,tarfile,io,subprocess
base=Path(Path('/tmp/tiewtrade-reference-remediation-active-path').read_text().strip())
with urllib.request.urlopen('https://registry.npmjs.org/source-map-js/1.2.1',timeout=30) as response:metadata=json.load(response)
with urllib.request.urlopen(metadata['dist']['tarball'],timeout=30) as response:data=response.read()
import hashlib,base64
assert 'sha512-'+base64.b64encode(hashlib.sha512(data).digest()).decode()==metadata['dist']['integrity']
dest=base/'source-map-baseline';dest.mkdir()
with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as archive:archive.extractall(dest,filter='data')
print('Baseline source-map-js 1.2.1 downloaded and integrity verified for bounded caller comparison.')
```

## tiewtrade-reference-browser-20261106.cjs

```javascript
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('/Users/chainarongjaykeaw/Projects/TiewTrade/Projects/TiewTrade/frontend/node_modules/playwright');
const base=fs.readFileSync('/tmp/tiewtrade-reference-remediation-active-path','utf8').trim();const servers=JSON.parse(fs.readFileSync(path.join(base,'servers.json')));const root=path.join(base,'browser');fs.mkdirSync(root,{recursive:true});
(async()=>{const browser=await chromium.launch({headless:true});const results=[];const denied=new Set();try{
 for(const server of servers){for(const viewport of [{width:1440,height:900},{width:390,height:844}]){
 const context=await browser.newContext({viewport});await context.route('**/*',route=>{const u=new URL(route.request().url());if(['127.0.0.1','localhost'].includes(u.hostname))return route.continue();denied.add(u.origin+u.pathname);return route.abort('blockedbyclient');});
 for(const [route,heading] of [['/','Monthly Sales'],['/form-elements','Form Elements'],['/basic-tables','Basic Tables'],['/buttons','Buttons'],['/signin','Sign In']]){
 const page=await context.newPage();const errors=[],failures=[],badResponses=[],consoleErrors=[];page.on('pageerror',e=>errors.push(e.message));page.on('requestfailed',req=>{if(new URL(req.url()).hostname==='127.0.0.1')failures.push({url:new URL(req.url()).pathname,error:req.failure()?.errorText});});page.on('response',r=>{if(new URL(r.url()).hostname==='127.0.0.1'&&r.status()>=400)badResponses.push({url:new URL(r.url()).pathname,status:r.status()});});page.on('console',msg=>{if(msg.type()==='error')consoleErrors.push(msg.text().slice(0,400));});
 const result={mode:server.mode,viewport,route,errors,failures,badResponses,consoleErrors};try{
 const response=await page.goto(server.url+route,{waitUntil:'networkidle',timeout:45000});assert.equal(response.status(),200);
 await page.getByRole('heading',{name:heading,exact:true}).first().waitFor({state:'visible',timeout:15000});
 if(route==='/form-elements'){const input=page.locator('main input:not([type]),main input[type="text"]').first();await input.fill('security-probe');assert.equal(await input.inputValue(),'security-probe');}
 if(route==='/buttons'){const button=page.getByRole('button',{name:'Button Text',exact:true}).first();await button.click();}
 if(route==='/basic-tables'){assert((await page.locator('table').count())>0);}
 if(route==='/signin'){const email=page.getByPlaceholder('info@gmail.com');await email.fill('probe@example.invalid');assert.equal(await email.inputValue(),'probe@example.invalid');}
 const metrics=await page.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,bodyText:document.body.innerText.length,styles:document.styleSheets.length,images:[...document.images].filter(i=>i.complete&&i.naturalWidth===0).map(i=>new URL(i.src).pathname)}));result.metrics=metrics;assert(metrics.bodyText>100);assert(metrics.styles>0);assert.equal(metrics.images.length,0,'broken images');assert.equal(errors.length,0,'page errors');assert.equal(failures.length,0,'failed local requests');assert.equal(badResponses.length,0,'local HTTP errors');
 if((server.mode==='preview'&&route==='/'&&viewport.width===1440)||(server.mode==='preview'&&route==='/form-elements'&&viewport.width===390)||(server.mode==='dev'&&route==='/buttons'&&viewport.width===1440)||(server.mode==='preview'&&route==='/signin'&&viewport.width===390)){const filename=server.mode+'-'+(route==='/'?'home':route.slice(1))+'-'+viewport.width+'.png';await page.screenshot({path:path.join(root,filename),fullPage:false});result.screenshot=filename;}
 result.passed=true;
 }catch(error){result.passed=false;result.failure=error.message.slice(0,700);await page.screenshot({path:path.join(root,'failed-'+server.mode+'-'+route.replaceAll('/','_')+'-'+viewport.width+'.png')}).catch(()=>{});}
 results.push(result);await page.close();}await context.close();}}
 }finally{await browser.close();}
 const result={results,passed:results.filter(r=>r.passed).length,total:results.length,denied_external_resources:[...denied]};fs.writeFileSync(path.join(base,'browser-summary.json'),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result,null,2));process.exitCode=results.every(r=>r.passed)?0:1;
})().catch(error=>{console.error(error);process.exitCode=1;});
```

## tiewtrade-reference-serve-20261106.py

```python
from pathlib import Path
import subprocess,os,json,socket,time,urllib.request
base=Path(Path('/tmp/tiewtrade-reference-remediation-active-path').read_text().strip());template=base/'template';processes=[];streams=[];servers=[]
env={k:os.environ[k] for k in ['PATH','HOME','TMPDIR','LANG','SHELL'] if k in os.environ}
try:
    for mode in ['dev','preview']:
        with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        log=(base/(mode+'-server.log')).open('w');streams.append(log)
        args=['node','node_modules/vite/bin/vite.js']+(['preview'] if mode=='preview' else [])+['--host','127.0.0.1','--port',str(port),'--strictPort']
        process=subprocess.Popen(args,cwd=template,env=env,stdout=log,stderr=subprocess.STDOUT);processes.append(process)
        url=f'http://127.0.0.1:{port}'
        for i in range(100):
            if process.poll() is not None:raise RuntimeError(mode+' server exited')
            try:
                with urllib.request.urlopen(url,timeout=2) as response:
                    if response.status==200:break
            except Exception:time.sleep(0.2)
        else:raise RuntimeError(mode+' server not ready')
        servers.append({'mode':mode,'url':url})
    (base/'servers.json').write_text(json.dumps(servers)+'\n')
    with (base/'browser.log').open('w') as output:result=subprocess.run(['node','/tmp/tiewtrade-reference-browser-20261106.cjs'],cwd=template,env=env,stdout=output,stderr=subprocess.STDOUT,timeout=600)
    print('Browser harness exit:',result.returncode)
    summary=base/'browser-summary.json'
    if summary.exists():
        d=json.loads(summary.read_text());print(json.dumps({'passed':d['passed'],'total':d['total'],'denied_external_resources':d['denied_external_resources'],'failed':[r for r in d['results'] if not r['passed']]},indent=2))
    else:print((base/'browser.log').read_text()[-2000:])
    raise SystemExit(result.returncode)
finally:
    for p in processes:
        if p.poll() is None:
            p.terminate()
            try:p.wait(timeout=10)
            except subprocess.TimeoutExpired:p.kill();p.wait()
    for stream in streams:stream.close()
```
