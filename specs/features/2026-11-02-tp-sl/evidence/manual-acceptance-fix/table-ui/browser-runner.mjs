import {chromium,expect} from '/Users/chainarongjaykeaw/Projects/TiewTrade/Projects/TiewTrade-f17-manual-fix/frontend/node_modules/@playwright/test/index.mjs';
import {writeFile,mkdir} from 'node:fs/promises';
const dir='/Users/chainarongjaykeaw/Projects/TiewTrade/Projects/TiewTrade-f17-manual-fix/specs/features/2026-11-02-tp-sl/evidence/manual-acceptance-fix/table-ui';
await mkdir(dir,{recursive:true});
const browser=await chromium.launch({headless:true});
const checks=[];let mutations=0;
try {
 const page=await browser.newPage();
 await page.route('**/api/**',async route=>{const r=route.request();if(r.method()!=='GET'){mutations++;await route.abort();return;}await route.fulfill({json:{requests:[],next_cursor:null}});});
 for(const locale of ['th','en']) {
 await page.goto('http://127.0.0.1:15118/__protection_table_preview.html');
 await expect(page.getByRole('button',{name:'ตั้ง TP/SL ให้เหรียญที่ถือ',exact:true})).toBeEnabled();
 await page.evaluate(locale=>window.preview.language(locale),locale);
 const english=locale==='en',current=english?'Current / Needs attention':'กำลังทำงาน / มีปัญหา',history=english?'Protection history':'ประวัติการป้องกัน',details=english?'Details':'รายละเอียด',close=english?'Close':'ปิด';
 await expect(page.getByRole('row')).toHaveCount(3);
 for(const width of [1440,375]) {
 await page.setViewportSize({width,height:1000});
 for(const dark of [false,true]) {
 await page.evaluate(dark=>document.documentElement.classList.toggle('dark',dark),dark);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 expect(await page.locator('#protection-table').evaluate(n=>n.scrollWidth>n.clientWidth)).toBe(true);
 await expect(page.getByText(english?'Unprotected quantity remains':'มีปริมาณที่ยังไม่ป้องกัน',{exact:true})).toBeVisible();
 await page.screenshot({path:`${dir}/${locale}-${width}-${dark?'dark':'light'}.png`,fullPage:true});
 const trigger=page.getByRole('button',{name:details,exact:true}).first(); await trigger.click();
 await expect(page.getByRole('dialog')).toBeVisible();
 await expect(page.getByRole('dialog').getByRole('button',{name:close,exact:true})).toBeVisible();
 await page.screenshot({path:`${dir}/${locale}-${width}-${dark?'dark':'light'}-details.png`,fullPage:true});
 await page.keyboard.press('Escape');await expect(trigger).toBeFocused();
 await page.locator('#protection-table').evaluate(n=>n.scrollLeft=0);
 checks.push({locale,width,dark,noDocumentOverflow:true,tableScroll:true});
 }
 }
 await page.setViewportSize({width:1440,height:1000});
 const currentTab=page.getByRole('tab',{name:current,exact:true});await currentTab.focus();await page.keyboard.press('ArrowRight');
 await expect(page.getByRole('tab',{name:history,exact:true})).toBeFocused();
 await expect(page.getByRole('row')).toHaveCount(2);
 await expect(page.getByRole('button',{name:english?'Edit':'แก้ไข',exact:true})).toHaveCount(0);
 await page.keyboard.press('Home');await expect(currentTab).toBeFocused();
 const trigger=page.getByRole('button',{name:details,exact:true}).first();await trigger.focus();await page.keyboard.press('Enter');
 const dialog=page.getByRole('dialog');await expect(dialog).toBeVisible();
 const button=dialog.getByRole('button',{name:close,exact:true});await expect(button).toBeFocused();
 await page.keyboard.press('Tab');await expect(button).toBeFocused();await page.keyboard.press('Shift+Tab');await expect(button).toBeFocused();
 await page.keyboard.press('Escape');await expect(dialog).toHaveCount(0);await expect(trigger).toBeFocused();
 await page.keyboard.press('Enter');await page.evaluate(()=>window.preview.update());
 await expect(dialog.getByText('0 BTC',{exact:true})).toBeVisible();
 await expect(dialog.getByText(english?'Coverage cannot be verified':'ยังยืนยันส่วนที่ป้องกันไม่ได้',{exact:true})).toBeVisible();
 await page.evaluate(()=>window.preview.remove());await expect(dialog).toHaveCount(0);
 checks.push({locale,history:true,keyboardFocus:true,liveDetails:true,removedRowCloses:true});
 }
 expect(mutations).toBe(0);
 await writeFile(`${dir}/browser-result.json`,JSON.stringify({scope:'isolated real component with synthetic read-only API discovery; no owner session or financial E2E claim',checks,mutations},null,2));
 console.log(JSON.stringify({passed:checks.length,mutations}));
}finally{await browser.close();}
