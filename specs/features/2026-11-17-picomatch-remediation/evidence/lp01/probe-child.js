const [patched, original, raw] = process.argv.slice(1);
const c=JSON.parse(raw);const start=performance.now();
const value=require(patched)(c.pattern,c.options)(c.subject);
let baseline=null;if(c.compare_original) baseline=require(original)(c.pattern,c.options)(c.subject);
console.log(JSON.stringify({matched:value,baseline,elapsed_ms:performance.now()-start}));