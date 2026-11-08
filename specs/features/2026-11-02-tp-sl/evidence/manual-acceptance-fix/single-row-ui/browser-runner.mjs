import {chromium,expect} from '/Users/chainarongjaykeaw/Projects/TiewTrade/Projects/TiewTrade-f17-manual-fix/frontend/node_modules/@playwright/test/index.mjs';
import {mkdir,writeFile} from 'node:fs/promises';
const dir='/Users/chainarongjaykeaw/Projects/TiewTrade/Projects/TiewTrade-f17-manual-fix/specs/features/2026-11-02-tp-sl/evidence/manual-acceptance-fix/single-row-ui';await mkdir(dir,{recursive:true});
const stamp='2026-11-08T04:00:00Z';
const row={protection_id:'armed',wallet_id:'wallet',episode_id:'episode',mode:'PAPER',base:'BTC',quote:'USDT',quantity:'0.00131868',protected_quantity:'0.00131',executable_quantity:'0.00131',step_residual_quantity:'0.00000868',state:'ARMED',revision:4,take_profit_price:'76500',stop_loss_price:'75000',conflicted:false,failure_code:null,market_ready:true,entry_order_id:null,snapshot_at:stamp};
const rows=[row,{...row,base:'ETH',protection_id:'failed',state:'FAILED',protected_quantity:'0',failure_code:'PROTECTION_SETUP_REJECTED'},{...row,protection_id:'canceled',state:'CANCELED',quantity:'0',protected_quantity:'0',step_residual_quantity:'0'}];
const wallet={wallet_id:'wallet',episode_id:'episode',balance:'10000',reserved_quote:'0',available_quote:'10000',base_balances:[],source_availability:'READY',revision:1};
const order={accepted_at:stamp,base:'BTC',episode_id:'episode',failure_code:null,filled_quantity:'0',kind:'LIMIT',limit_price:'75000',mode:'PAPER',order_id:'armed',quantity:'0.001',quote:'USDT',quote_budget:null,remaining_budget:null,remaining_quantity:'0.001',reserved_base:'0',reserved_quote:'75',sequence:1,side:'BUY',snapshot_at:stamp,spent:'0',status:'ACCEPTED',time_in_force:'GTC',wallet_id:'wallet'};
let mutations=0;const checks=[];const browser=await chromium.launch({headless:true});
try{const page=await browser.newPage();const pageErrors=[];page.on('pageerror',e=>pageErrors.push(e.message));
await page.route('**/src/CandlestickChartPanel.tsx',r=>r.fulfill({contentType:'application/javascript',body:'export function CandlestickChartPanel(){return null;}'}));
await page.route('**/api/**',async route=>{const req=route.request();if(req.method()!=='GET'){mutations++;await route.abort();return;}const url=new URL(req.url());let data;
if(url.pathname.includes('market-catalog'))data={active_pairs:[['BTC','USDT'],['ETH','USDT']]};
else if(url.pathname==='/api/paper/trade')data={mode:'PAPER',protection_enabled:true,wallet,account_use:'MANUAL',base:url.searchParams.get('base')||null,quote:'USDT',snapshot_at:stamp,admission_ready:true,admission_reasons:[]};
else if(url.pathname.includes('risk-limit'))data={mode:'PAPER',amount:'500',latched:false};
else if(url.pathname==='/api/paper/protections')data={protections:rows,next_cursor:null};
else if(url.pathname==='/api/paper/orders')data={orders:[order,{...order,order_id:'filled',status:'FILLED',filled_quantity:'0.001',remaining_quantity:'0'}],next_cursor:null};
else data={requests:[],next_cursor:null};await route.fulfill({json:data});});
for(const locale of ['th','en']){
 await page.goto('http://127.0.0.1:5173/__single_row_preview.html');await page.getByLabel('คู่เทรด',{exact:true}).selectOption('BTC');
 await page.evaluate(locale=>window.preview.language(locale),locale);const en=locale==='en';
 const open=en?'Open orders':'ออเดอร์ที่เปิดอยู่',history=en?'Order history':'ประวัติออเดอร์',details=en?'Details':'รายละเอียด',close=en?'Close':'ปิด',create=en?'Protect held assets':'ตั้ง TP/SL ให้เหรียญที่ถือ',edit=en?'Edit':'แก้ไข';
 const activity=page.locator('.trade-workspace-orders');await expect(activity.getByRole('tablist')).toHaveCount(1);await expect(activity.getByRole('table')).toHaveCount(1);await expect(activity.getByRole('row')).toHaveCount(4);
 await expect(activity.getByText('LIMIT · BUY',{exact:true})).toBeVisible();await expect(activity.getByText('ETH/USDT',{exact:true})).toBeVisible();
 for(const width of [1440,375]){await page.setViewportSize({width,height:1000});
 for(const dark of [false,true]){await page.evaluate(d=>document.documentElement.classList.toggle('dark',d),dark);
 await page.getByRole('tab',{name:open,exact:true}).click();
 await expect(activity.getByText(en?'Unprotected quantity remains':'มีปริมาณที่ยังไม่ป้องกัน',{exact:true})).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 const toolbar=activity.locator('header.paper-order-toolbar');await expect(toolbar).toHaveCount(1);
 if(width===1440){const tab=await activity.getByRole('tablist').boundingBox(),button=await activity.getByRole('button',{name:create,exact:true}).boundingBox();expect(Math.abs((tab.y+tab.height/2)-(button.y+button.height/2))).toBeLessThan(2);}
 await activity.locator('#trading-activity-table').evaluate(n=>n.scrollLeft=0);await activity.evaluate(n=>n.scrollTop=0);
 await activity.screenshot({path:`${dir}/${locale}-${width}-${dark?'dark':'light'}-open.png`});
 const eth=activity.getByRole('row').filter({hasText:'ETH/USDT'});const editTrigger=eth.getByRole('button',{name:edit,exact:true});await editTrigger.click();
 const editModal=page.getByRole('dialog');await expect(editModal.getByLabel(en?'Quantity (ETH)':'จำนวนเหรียญ (ETH)',{exact:true})).toHaveValue('0.00131868');await page.keyboard.press('Escape');await expect(editTrigger).toBeFocused();
 await activity.getByRole('button',{name:create,exact:true}).click();const createModal=page.getByRole('dialog');await expect(createModal.getByLabel(en?'Quantity (BTC)':'จำนวนเหรียญ (BTC)',{exact:true})).toBeFocused();await page.keyboard.press('Escape');
 const trigger=eth.getByRole('button',{name:details,exact:true});await trigger.click();const modal=page.getByRole('dialog');await expect(modal).toBeVisible();await expect(modal.getByRole('button',{name:close,exact:true})).toBeFocused();await page.keyboard.press('Tab');await expect(modal.getByRole('button',{name:close,exact:true})).toBeFocused();await page.keyboard.press('Escape');await expect(trigger).toBeFocused();
 await activity.getByRole('tab',{name:history,exact:true}).click();await expect(activity.getByRole('row')).toHaveCount(3);await expect(activity.getByText(en?'Protection canceled':'ยกเลิกการป้องกันแล้ว',{exact:true})).toBeVisible();
 await expect(activity.getByRole('cell',{name:en?'Filled':'จับคู่ครบ',exact:true})).toBeVisible();await expect(activity.getByRole('button',{name:edit,exact:true})).toHaveCount(0);await expect(activity.getByRole('button',{name:create,exact:true})).toBeDisabled();
 await activity.locator('#trading-activity-table').evaluate(n=>n.scrollLeft=0);await activity.evaluate(n=>n.scrollTop=0);await activity.screenshot({path:`${dir}/${locale}-${width}-${dark?'dark':'light'}-history.png`});
 checks.push({locale,width,dark,singleToolbar:true,singleTable:true,desktopAligned:width===1440,crossSymbolEdit:true,createChartSymbol:true,history:true,modalFocus:true,noDocumentOverflow:true});
 }}
 const hist=activity.getByRole('tab',{name:history,exact:true});await hist.focus();await page.keyboard.press('Home');await expect(activity.getByRole('tab',{name:open,exact:true})).toBeFocused();await page.keyboard.press('End');await expect(hist).toBeFocused();
 }
 expect(mutations).toBe(0);expect(pageErrors).toEqual([]);await writeFile(`${dir}/browser-result.json`,JSON.stringify({scope:'real PaperTradePage/query/recovery and mixed table; synthetic GET reads and chart module stub; not owner financial E2E',checks,mutations,pageErrors},null,2));console.log(JSON.stringify({checks:checks.length,mutations,pageErrors}));
}finally{await browser.close();}
