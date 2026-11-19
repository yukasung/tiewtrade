// Resolve without executing package modules or hostile patterns.
import {createRequire} from 'node:module';
import {readFileSync, realpathSync, readdirSync, statSync} from 'node:fs';
import {join, dirname, relative} from 'node:path';
import {createHash} from 'node:crypto';
const app = realpathSync(process.argv[2]);
const expected = process.argv[3];
const read = p => JSON.parse(readFileSync(p, 'utf8'));
const lock = read(join(app, 'package-lock.json'));
const wanted = new Set(['vite', 'vitest', 'tinyglobby', 'fdir', 'picomatch']);
const rows = [];
const inside = p => { const r=relative(app,p); if(r==='..'||r.startsWith('../')||r.startsWith('/')) throw new Error('outside owned install'); return r; };
function packageFor(entry) {
  let dir=dirname(realpathSync(entry));
  for (;;) {
    inside(dir);
    try { const value=read(join(dir,'package.json')); if(value.name) return {dir,value}; }
    catch(e) { if(e.code!=='ENOENT') throw e; }
    const parent=dirname(dir); if(parent===dir) throw new Error('missing package root'); dir=parent;
  }
}
for (const [location, info] of Object.entries(lock.packages)) {
  if(!location) continue;
  const name=info.name ?? location.split('node_modules/').at(-1);
  if(!wanted.has(name)) continue;
  const pkgdir=realpathSync(join(app, location)); inside(pkgdir);
  const manifest=read(join(pkgdir,'package.json'));
  const req=createRequire(join(pkgdir,'package.json'));
  const edges=[];
  for(const dep of new Set([...Object.keys(manifest.dependencies??{}),...Object.keys(manifest.optionalDependencies??{}),...Object.keys(manifest.peerDependencies??{})])) {
    if(!wanted.has(dep)) continue;
    const target=packageFor(req.resolve(dep));
    edges.push({dependency:dep,entry:inside(realpathSync(req.resolve(dep))),package:inside(target.dir),version:target.value.version});
    if(target.value.name!==dep) throw new Error('unexpected resolved package');
  }
  let parser_sha256=null;
  if(name==='picomatch') {
    if(createHash('sha256').update(readFileSync(join(pkgdir,'package.json'))).digest('hex')!==process.argv[4] || createHash('sha256').update(readFileSync(join(pkgdir,'LICENSE'))).digest('hex')!==process.argv[5]) throw new Error('manifest or license differs');
    parser_sha256=createHash('sha256').update(readFileSync(join(pkgdir,'lib/parse.js'))).digest('hex');
    if(parser_sha256!==expected||manifest.version!=='4.0.7') throw new Error('unexpected installed parser');
  }
  // Retain relevant import lines; declarations alone are not runtime execution proof.
  const imports=[];
  function scan(dir) {
    for(const file of readdirSync(dir)) {
      if(file==='node_modules'||file==='package-lock.json') continue;
      const path=join(dir,file); const stat=statSync(path);
      if(stat.isDirectory()) scan(path);
      else if(/\.(cjs|mjs|js)$/.test(file)) {
        const lines=readFileSync(path,'utf8').split('\n');
        lines.forEach((line,i)=>{if(/(?:require\s*\(|from\s+|import\s*\()\s*['"](?:picomatch|tinyglobby|fdir)['"]/.test(line)) imports.push({file:inside(path),line:i+1,text:line.slice(0,500)});});
      }
    }
  }
  if(name!=='picomatch') scan(pkgdir);
  rows.push({name,location,realpath:inside(pkgdir),version:manifest.version,edges,imports,parser_sha256});
}
for(const name of wanted) if(!rows.some(r=>r.name===name)) throw new Error('missing expected caller');
const byPath=new Map(rows.map(r=>[r.realpath,r]));
function reachesParser(row,seen=new Set()) {
  if(row.name==='picomatch') return true;
  if(seen.has(row.realpath)) return false;
  seen.add(row.realpath);
  return row.edges.some(e=>byPath.has(e.package)&&reachesParser(byPath.get(e.package),seen));
}
for(const row of rows) if(!reachesParser(row)) throw new Error('caller has no resolved chain to parser: '+row.name);
console.log(JSON.stringify({status:'PASSED',rows,limits:'Resolution and static import proof; no runtime public call or bundle execution. Earlier public caller evidence retained.'}));
