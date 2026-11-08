import {chromium,expect} from '/Users/chainarongjaykeaw/Projects/TiewTrade/Projects/TiewTrade-f17-manual-fix/frontend/node_modules/@playwright/test/index.mjs';
import {mkdir,writeFile} from 'node:fs/promises';
const dir='/Users/chainarongjaykeaw/Projects/TiewTrade/Projects/TiewTrade-f17-manual-fix/specs/features/2026-11-02-tp-sl/evidence/manual-acceptance-fix/unified-ui';await mkdir(dir,{recursive:true});
const stamp='2026-11-08T04:00:00Z';
const row={protection_id:'armed',wallet_id:'wallet',episode_id:'episode',mode:'PAPER',base:'BTC',quote:'USDT',quantity:'0.00131868',protected_quantity:'0.00131',executable_quantity:'0.00131',step_residual_quantity:'0.00000868',state:'ARMED',revision:4,take_profit_price:'76500',stop_loss_price:'75000',conflicted:false,failure_code:null,market_ready:true,entry_order_id:null,snapshot_at:stamp};
const rows=[row,{...row,protection_id:'failed',state:'FAILED',protected_quantity:'0',failure_code:'PROTECTION_SETUP_REJECTED'},{...row,protection_id:'canceled',state:'CANCELED',quantity:'0',protected_quantity:'0',step_residual_quantity:'0'}];
const wallet={wallet_id:'wallet',episode_id:'episode',balance:'10000',reserved_quote:'0',available_quote:'10000',base_balances:[],source_availability:'READY',revision:1};
const order={accepted_at:stamp,base:'BTC',episode_id:'episode',failure_code:null,filled_quantity:'0',kind:'LIMIT',limit_price:'75000',mode:'PAPER',order_id:'normal',quantity:'0.001',quote:'USDT',quote_budget:null,remaining_budget:null,remaining_quantity:'0.001',reserved_base:'0',reserved_quote:'75',sequence:1,side:'BUY',snapshot_at:stamp,spent:'0',status:'ACCEPTED',time_in_force:'GTC',wallet_id:'wallet'};
let mutations=0;const checks=[];const browser=await chromium.launch({headless:true});
try{const page=await browser.newPage();const pageErrors=[];page.on('pageerror',e=>pageErrors.push(e.message));
await page.route('**/src/CandlestickChartPanel.tsx',r=>r.fulfill({contentType:'application/javascript',body:'export function CandlestickChartPanel(){return null;}'}));
await page.route('**/api/**',async route=>{const req=route.request();if(req.method()!=='GET'){mutations++;await route.abort();return;}const url=new URL(req.url());let data;
if(url.pathname.includes('market-catalog'))data={active_pairs:[['BTC','USDT']]};
else if(url.pathname==='/api/paper/trade')data={mode:'PAPER',protection_enabled:true,wallet,account_use:'MANUAL',base:url.searchParams.get('base')||null,quote:'USDT',snapshot_at:stamp,admission_ready:true,admission_reasons:[]};
else if(url.pathname.includes('risk-limit'))data={mode:'PAPER',amount:'500',latched:false};
else if(url.pathname==='/api/paper/protections')data={protections:rows,next_cursor:null};
else if(url.pathname==='/api/paper/orders')data={orders:[order,{...order,order_id:'filled',status:'FILLED',filled_quantity:'0.001',remaining_quantity:'0'}],next_cursor:null};
else data={requests:[],next_cursor:null};await route.fulfill({json:data});});
for(const locale of ['th','en']){
 await page.goto('http://127.0.0.1:5173/__unified_trade_preview.html');await page.getByLabel('คู่เทรด',{exact:true}).selectOption('BTC');
 await page.evaluate(locale=>window.preview.language(locale),locale);const en=locale==='en';
 const normal=en?'Normal orders':'คำสั่งปกติ',open=en?'Open orders':'ออเดอร์ที่เปิดอยู่',history=en?'Order history':'ประวัติออเดอร์',attention=en?'Check current TP/SL':'ตรวจ TP/SL ปัจจุบัน',details=en?'Details':'รายละเอียด',close=en?'Close':'ปิด';
 const activity=page.locator('.trade-workspace-orders');await expect(activity.getByRole('tablist')).toHaveCount(2);await expect(activity.getByText('BUY',{exact:true})).toBeVisible();
 await expect(page.getByRole('button',{name:attention,exact:true})).toBeVisible();
 for(const width of [1440,375]){await page.setViewportSize({width,height:1000});
 for(const dark of [false,true]){await page.evaluate(d=>document.documentElement.classList.toggle('dark',d),dark);
 await page.getByRole('tab',{name:normal,exact:true}).click();await expect(page.getByRole('button',{name:attention,exact:true})).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await activity.screenshot({path:`${dir}/${locale}-${width}-${dark?'dark':'light'}-normal.png`});
 await page.getByRole('button',{name:attention,exact:true}).click();await expect(page.getByRole('tab',{name:open,exact:true})).toHaveAttribute('aria-selected','true');
 await expect(activity.getByText(en?'Unprotected quantity remains':'มีปริมาณที่ยังไม่ป้องกัน',{exact:true})).toBeVisible();
 await expect(activity.getByText(en?'No automatic remainder sale':'ไม่ขายเศษอัตโนมัติ',{exact:true})).toHaveCount(2);
 await activity.screenshot({path:`${dir}/${locale}-${width}-${dark?'dark':'light'}-tp-sl.png`});
 const trigger=page.getByRole('button',{name:details,exact:true}).first();await trigger.click();const modal=page.getByRole('dialog');await expect(modal).toBeVisible();
 await expect(modal.getByRole('button',{name:close,exact:true})).toBeFocused();await page.keyboard.press('Tab');await expect(modal.getByRole('button',{name:close,exact:true})).toBeFocused();await page.keyboard.press('Escape');await expect(trigger).toBeFocused();
 await page.getByRole('tab',{name:history,exact:true}).click();await expect(activity.getByText(en?'Protection canceled':'ยกเลิกการป้องกันแล้ว',{exact:true})).toBeVisible();
 await expect(activity.getByRole('button',{name:en?'Edit':'แก้ไข',exact:true})).toHaveCount(0);
 await page.getByRole('tab',{name:normal,exact:true}).click();await expect(activity.getByRole('cell',{name:en?'Filled':'จับคู่ครบ',exact:true})).toBeVisible();
 await page.getByRole('tab',{name:open,exact:true}).click();checks.push({locale,width,dark,routing:true,attention:true,detailsFocus:true,noDocumentOverflow:true});
 }}
 const top=page.getByRole('tab',{name:open,exact:true});await top.focus();await page.keyboard.press('ArrowRight');await expect(page.getByRole('tab',{name:history,exact:true})).toBeFocused();
 const sub=page.getByRole('tab',{name:normal,exact:true});await sub.focus();await page.keyboard.press('End');await expect(page.getByRole('tab',{name:'TP / SL',exact:true})).toBeFocused();
 }
 expect(mutations).toBe(0);expect(pageErrors).toEqual([]);await writeFile(`${dir}/browser-result.json`,JSON.stringify({scope:'real PaperTradePage/navigation/recovery components; synthetic intercepted reads, chart module excluded; not owner financial E2E',checks,mutations,pageErrors},null,2));console.log(JSON.stringify({checks:checks.length,mutations,pageErrors}));
}finally{await browser.close();}
