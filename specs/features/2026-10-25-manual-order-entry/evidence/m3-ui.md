# M3 — Manual order UI checkpoint

วันที่: 2026-10-25 · branch `feat/f16-manual-order-entry` · uncommitted working tree

## Implementation และ source mapping

- `/paper/trade` และ `/live/trade` อยู่ใน authenticated shell/navigation เดิม, reload และ
  back/forward ใช้ URL จริง. มี PAPER/LIVE badge ในหน้าและ sticky account header.
- `ManualOrderForm.tsx` ใช้ shared Input/Select/Label/Button/ComponentCard ตาม
  `references/admin-template/src/components/form/form-elements/DefaultInputs.tsx`;
  ไม่ใช้ native appearance ใหม่, input type=number, slider/max หรือ financial math ใน browser.
  MARKET BUY ใช้งบ USDT, SELL ใช้ base, LIMIT ใช้ base+price/GTC; switch หน่วยหรือคู่ล้างจำนวน/ราคาเก่า; terminalแล้วต้องกรอกdraftใหม่.
- `PaperOrderList.tsx` ใช้ shared Table/Modal และ pattern จาก BasicTables/BasicTableOne.tsx:
  horizontal scroll, whitespace-nowrap, template spacing/borders. ไม่มีการคืน balance หรือ
  เปลี่ยน fill/cancel status แบบ optimistic. จำนวน original/filled/remaining/reserved มาจาก API.
- `components/ui/Badge.tsx` ปรับจาก template badge light/md; `components/OrderStatus.tsx`
  รวม presentation ของสถานะ. Money/time ใช้ MarketValue/MarketTime เดิม.
- `manualOrders.ts` ใช้ generated contracts และ owner/PAPER/episode/resource query keys.
  Snapshot/list poll5s, pending request/detail poll1s เฉพาะหน้าที่เปิดและ document visible;
  AbortSignal ยกเลิก reads เมื่อออก route. ไม่ต่อ session ด้วย polling GET.
- `manualOrderJournal.ts` บันทึก version/owner/PAPER/action/key/exact serialized payload
  ใน tab sessionStorage พร้อม read-back ก่อน POST; ไม่มี cookie/credential/secret.
  Restore ไม่ POST เอง, lookup404/transport/503 ยัง UNKNOWN, explicit retry ใช้ key/payload
  เดิมรวม episode เดิม. Definitive documented422 จึงปล่อยให้แก้ draft ได้; proxy422 ที่ไม่รู้จัก
  ยังเก็บ identity. Storage ใช้ไม่ได้ไม่ POST.
- `useManualAttempt.ts` แยก effects/journal จาก local form; server state อยู่ TanStack Query.
  Discovery ทุก episode ต้องอ่านครบทุกหน้าก่อนปล่อย new request. แสดง intake/command/order
  แยกกัน; TRANSFERRED ยัง poll ต่อ, command rejection ไม่มี order row ยังแสดงได้.
- AccountSession cleanup ล้าง journal/cache ของ owner เดิมเมื่อ logout/สลับ owner;
  StrictMode effect replay ไม่ล้าง recovery ตอน mount. Route unmount ไม่ล้าง journal.
- Live ใช้ form เดียวกัน disabled และไม่มี query/mutation binding; บอกให้จัดการ Live เดิม
  ตรงตลาด. Production Paper ยังคง fail closed ตาม M2/F-18.
- ไทย/อังกฤษอยู่ `manualOrderMessages.ts` กับ navigation messages; สี/theme/breakpoint
  ใช้ template tokens ไม่มี style exception ใหม่.

## Verification และ failures ที่แก้

| Check | Result |
|---|---|
| Initial component/session/navigation checks |20 passed /1.89s |
| เพิ่ม polling/discovery/input-refusal/session tests |26 passed /2.98s |
| Final affected component/session/navigation/layout tests หลังเพิ่ม expiry/visibility/abort |37 passed /3.91s; final presentation follow-up ดู M4 |
| Browser harness real PostgreSQL/API/inbox/bridge/F-15 |5 passed /36.4s ก่อนขยายภาพครบ language/theme/breakpoint; final follow-up ดู M4 |
| Full frontend suite ณ candidate แรก |283 passed /25.06s; tests ที่เพิ่มและ code ที่แก้ภายหลังอยู่ใน affected follow-up ไม่อ้างว่า283คือจำนวน final full suite |
| Frontend lint/typecheck/build + generated API type comparison |Passed; final candidate checks อยู่ M4 |

Browser harness อยู่ `backend/tests/e2e_manual_order_app.py`, config
`frontend/playwright.manual-orders.config.ts`, tests `frontend/e2e/manual-orders.spec.ts`.
ใช้ PostgreSQL `tiewtrade_e2e_f16` ใน isolated F-16 container, separate ports18016/15116,
explicit injected test policy และ recorded public book เท่านั้น. Startup ปฏิเสธ DB นอก
E2E/local convention; production ไม่มี import, endpoint หรือ environment bypass นี้.
เพิ่ม dedicated CI hook โดย generic E2E ไม่ collect test-only composition นี้.

Browser asserts DB command identities และ exact server amounts รวม:
MARKET BUY1100→10.5BTC/cash8900; SELL1; LIMIT11@100 partial10/remaining1/reserved100;
cancel คง confirmed fill10 และ reservation0. Recorded replenishment เพิ่ม liquidity จริง
เพื่อไม่ใช้ shadow liquidity ที่ MARKET BUY ใช้แล้วซ้ำ; ไม่เปลี่ยน matching logic.
Receipt response หายหลังcommit→reload/lookup404→explicit same-key replay ได้ request เดิม
และcommand count1; downstream insufficient funds ไม่มี order rowแต่ยังเห็นเหตุปฏิเสธ.
Logout→owner2เห็น404/ไม่มีข้อมูลowner1→loginowner1พบpendingด้วยdiscovery;
storage denialไม่มีPOST; Live/reload/backไม่มีPaper mutation.
Cancel แข่ง fill แสดงFILLEDแม้cancel commandSUCCEEDED; resetระหว่างpending inboxได้RESET_UNSAFE.

Failures ที่แก้: ติดตั้ง Chromium ที่เครื่องยังไม่มี; locator refresh เดิมตรงสองปุ่มจึง scope
ตาม wallet region; harness LIMIT แรกไม่partialเพราะ liquidity เคยถูกใช้แล้ว จึงเพิ่ม recorded
replenishment ให้ตรง scenario โดยคงกฎ F-15; format/mypy ของ harnessและ exact optional prop
ผ่านหลังแก้. Visual inspection พบ table mobileแตกเป็นตัวอักษร จึงใช้ horizontal-scroll/
nowrap/padding ตาม template; Modal close callback stable และคืน focus ให้ trigger.

ภาพอยู่ [ui/](ui/) — final Thai/English/light/dark/375px/1440px ดู M4;
ภาพระหว่างพัฒนาไม่ใช้ยืนยัน production freshness. Shared header/control styles กับ focus
ใช้ template เดิม; browser ตรวจ modal Escape/return focus และ horizontal overflow ของตาราง.

เวลาเป็น elapsed ที่เครื่องมือวัดจริง; ช่วงเขียน/อ่าน/reviewไม่ได้จับแยกครบ ไม่แต่งเวลารวม
และไม่บวกเวลาของงานที่รันพร้อมกัน.

## Scope status

M3 implemented. Ready for Code Review แจ้งใน session ก่อน formal M4 review พร้อม files/tests/
pending/risks. ยังไม่ Completed/พร้อม merge. V-18 Pending F-18; V-20 Pending Full Validation.
M4 ต้องรักษาผล failed/partial จริงและ required CI ก่อน merge; ไม่มี commit/push/merge.


Final M4 follow-ups: source price observation time is shown separately from account snapshot;
actual DB connection termination before commit was tested in the browser; pair-unit and completed-
draft protections passed final targeted tests. See M4 for the6 passing browser scenarios, current
contract/static/build evidence and remaining pre-merge gates.
