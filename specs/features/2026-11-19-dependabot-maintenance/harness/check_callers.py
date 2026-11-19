"""Bounded installed LP04 callers; case/script reuse recorded in helper-provenance.json."""
from __future__ import annotations
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

from verify_candidate import verify_candidate

HERE = Path(__file__).resolve().parent


def main(app: Path, output: Path) -> None:
    policy = json.loads((HERE.parents[3] / 'tools/security/trusted-sources.json').read_text())['sources'][0]
    verify_candidate(app, artifact_sha256=policy['artifact_sha256'], parser_sha256=policy['parser_sha256'], artifact_relative_path='vendor/picomatch-4.0.7-lp04.tgz')
    resolution = subprocess.run(['node', str(HERE / 'installed_resolution.mjs'), str(app), policy['parser_sha256'], policy['manifest_sha256'], policy['license_sha256']], capture_output=True, text=True, timeout=30, check=True)
    graph = json.loads(resolution.stdout)
    assert all(row['version'] == {'vite':'6.4.6','vitest':'4.1.12'}.get(row['name'],row['version']) for row in graph['rows'])
    fixtures = app / 'caller-fixtures'
    assert not fixtures.exists()
    files = fixtures / 'files'
    files.mkdir(parents=True)
    (files / 'a.ts').write_text('export {};')
    (files / ('a'*32+'!')).write_text('synthetic')
    spec = fixtures / 'spec'
    spec.mkdir()
    (spec/'example.test.js').write_text("import{test,expect}from'vitest';test('fixture',()=>expect(1).toBe(1));")
    results=[]
    configs=[]
    deadline=time.monotonic()+30
    try:
        for caller in ['vite','tinyglobby','fdir','vitest']:
            for kind,pattern in [('benign','**/*.ts'),('single','+(*a)'),('multi','+(*a|b)')]:
                case={'caller':caller,'pattern':pattern,'subject':'a.ts' if kind=='benign' else 'a'*32+'!','fixture':str(files),'expected_files':['a.ts'] if kind=='benign' else []}
                if caller=='vitest':
                    config=app/('vitest.caller.'+kind+'.mjs');configs.append(config)
                    assert not config.exists()
                    include=['caller-fixtures/spec/**/*.test.js' if kind=='benign' else pattern]
                    config.write_text('export default {test:{environment:"node",pool:"threads",maxWorkers:1,fileParallelism:false,include:'+json.dumps(include)+'}};')
                    args=['node','--max-old-space-size=256','node_modules/vitest/vitest.mjs','run','--config',config.name]
                else:
                    args=['node','--max-old-space-size=256','--input-type=module','-e',(HERE/'caller_script.mjs').read_text(),json.dumps(case)]
                start=time.monotonic()
                budget=min(2,deadline-start)
                if budget<=0:raise TimeoutError('caller stage budget')
                proc=subprocess.Popen(args,cwd=app,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
                try:out,err=proc.communicate(timeout=budget)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid,signal.SIGKILL);proc.communicate();raise
                if caller=='vitest':
                    passed=(proc.returncode==0 and '1 passed' in out) if kind=='benign' else (proc.returncode==1 and 'No test files found' in err and pattern in err)
                else:passed=proc.returncode==0 and json.loads(out)['matched']==(kind=='benign')
                results.append({'caller':caller,'kind':kind,'exit_code':proc.returncode,'passed':passed,'seconds':round(time.monotonic()-start,4)})
                assert passed,(caller,kind)
        output.write_text(json.dumps({'status':'PASSED','graph':graph,'cases':results,'limits':{'child_seconds':2,'stage_seconds':30,'heap_MiB':256}},indent=2)+'\n')
    finally:
        shutil.rmtree(fixtures)
        for config in configs:config.unlink(missing_ok=True)

if __name__=='__main__':main(Path(sys.argv[1]).resolve(),Path(sys.argv[2]).resolve())
