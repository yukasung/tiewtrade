const c=JSON.parse(process.argv[1]);let matched,files;
if(c.caller==='vite'){const {createFilter}=await import('vite');matched=createFilter(c.pattern,null,{resolve:false})(c.subject);}
else if(c.caller==='tinyglobby'){const {glob}=await import('tinyglobby');files=(await glob(c.pattern,{cwd:c.fixture})).sort();matched=files.length>0;}
else {const {fdir}=await import('fdir');files=new fdir().withRelativePaths().glob(c.pattern).crawl(c.fixture).sync().sort();matched=files.length>0;}
if(files&&JSON.stringify(files)!==JSON.stringify(c.expected_files))throw new Error('unexpected files');
console.log(JSON.stringify({matched,files}));
