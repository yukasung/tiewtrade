"""HTTP dev/preview assets in owned installs, with bounded process cleanup."""
from __future__ import annotations
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request


def check(root: Path, port: int) -> list[dict[str, object]]:
    results=[]
    for mode in ['dev','preview']:
        with (root/('smoke-'+mode+'.log')).open('w') as log:
            proc=subprocess.Popen(['npm','run',mode,'--','--host','127.0.0.1','--port',str(port),'--strictPort'],cwd=root,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            origin='http://127.0.0.1:'+str(port)
            try:
                deadline=time.monotonic()+20
                while True:
                    try:
                        with urllib.request.urlopen(origin,timeout=2) as response:html=response.read().decode()
                        break
                    except (OSError,urllib.error.URLError):
                        if time.monotonic()>deadline or proc.poll() is not None:raise
                        time.sleep(0.1)
                assets=re.findall(r'(?:src|href)="([^"#]+\.(?:js|tsx|css)(?:\?[^" ]*)?)"',html)
                assert assets,'no executable assets'
                rows=[]
                for asset in assets:
                    with urllib.request.urlopen(origin+asset,timeout=15) as response:
                        body=response.read();assert response.status==200 and body
                        rows.append({'path':asset,'status':response.status,'content_type':response.headers.get('Content-Type'),'bytes':len(body)})
                with urllib.request.urlopen(origin+'/login',timeout=3) as response:assert response.status==200 and '<html' in response.read().decode().lower()
                try:urllib.request.urlopen(urllib.request.Request(origin+'/missing-dependency-maintenance.js',headers={'Accept':'application/javascript'}),timeout=3)
                except urllib.error.HTTPError as error:assert error.code==404
                else:raise AssertionError('missing JS did not return 404')
                results.append({'mode':mode,'passed':True,'assets':rows,'route_status':200,'missing_asset_status':404})
            finally:
                os.killpg(proc.pid,signal.SIGTERM)
                try:proc.wait(timeout=5)
                except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait(timeout=5)
    return results

if __name__=='__main__':
    Path(sys.argv[3]).write_text(json.dumps(check(Path(sys.argv[1]),int(sys.argv[2])),indent=2)+'\n')
