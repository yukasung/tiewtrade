# Paper Spot Bot Panel — Validation

สถานะ: **Approved — เจ้าของ approve วันที่ 2026-11-13 รวม V11–V12**
วันที่: 2026-11-13
อ้างอิง: [requirements](requirements.md), [plan](plan.md)

## เสร็จหมายถึง

| ID | ระยะ | เกณฑ์ / วิธีตรวจ | ผล |
|---|---|---|---|
| V01 | Feature | Component/page: หัวข้อ/selector Grid Close System/ยอด/งบ/Start ตามลำดับ; Start disabled ทุก state; ไม่มี manual form/BUY/SELL/MARKET/LIMIT ในแผงใหม่ | Passed — local checkpoint |
| V02 | Feature | กรอกงบ เปลี่ยน selector Enter คลิก disabled resize และเปิดเมนู: request spy ไม่มี POST/PUT/PATCH/DELETE จาก interaction เหล่านี้ ไม่มี journal ใหม่/account-use change | Passed — local checkpoint |
| V03 | Feature | ready/loading/refresh/error/no-wallet/source unavailable/placeholder: ไม่เอาค่าเก่าหรือศูนย์แทนยอด; แสดง decimal string เดิมไม่ปัด/คำนวณ | Passed — local checkpoint |
| V04 | Feature | draft คงอยู่เมื่อ rerender/poll/resize/menu; ล้างเมื่อ owner/wallet/episode/base เปลี่ยน; delayed response ของ owner/scope ก่อนหน้าไม่รั่วในหน้าใหม่ | Passed — local checkpoint |
| V05 | Feature | PaperTradePage/ManualOrderSession: discovery หลายหน้า, storage failure, UNKNOWN/reload/retry key และ scope เดิม, polling terminal/hidden/unmount, owner isolation และ cancel ใช้งานเหมือนเดิม | Passed — local checkpoint |
| V06 | Feature | PaperTradingActivity/TP-SL/STOP: ออเดอร์/ประวัติ/แก้/ยกเลิก/คำขอ pending และ risk latch ยังอ่านได้; ไม่เปลี่ยน assertions เงิน ไม่มี SELL เกินเจตนา และไม่เปลี่ยน KillSwitch mount/key | Passed — local checkpoint |
| V07 | Feature | Browser fixture ที่ 375/768/1280/1440 × th/en × light/dark (16 combinations): labels/keyboard/focus/scroll/ไม่มี horizontal overflow; กราฟ timeframe/reset และ Settings ใช้ได้; draft resize ไม่หาย | Passed — local checkpoint |
| V08 | Feature | E2E ที่กระทบ manual-orders/risk-limits/protections/top-navigation: เตรียม orders ผ่าน API fixture แล้วคง assertions เงิน/order/cancel/risk/recovery; browser journal fault cases ยังตรวจผ่าน UI จริง; Live ยัง disabled | Passed — local checkpoint |
| V09 | Feature | frontend lint/typecheck/build และ diff check ผ่าน ไม่มี generated API/schema/dependency เปลี่ยน; targeted ManualOrderForm/AccountSession/KillSwitch regression ผ่าน | Passed — local checkpoint |
| V11 | Feature | RQ-13: modal SELL-only ผ่าน MARKET/LIMIT เดิม, ไม่ส่ง BUY, ต้องยืนยัน, qty/protection allocations/revision ส่งตรงเดิม; backend ปฏิเสธยอดเกิน/ข้อมูล stale ตาม gates เดิม; ปิด modal ไม่ลบ journal; focus/STOP ไม่ขัดกัน | Passed — local checkpoint |
| V12 | Feature | Hook send จริง: journal-before-POST, storage failure POST=0, duplicate send POST=1, network failure/reload ไม่ auto-post, retry key/payload เดิม และ owner mismatch ไม่ส่ง; ไม่ใช้ seeded journal แทนขั้นก่อน POST | Passed — local checkpoint |
| V10 | Feature | แจ้ง Ready for Code Review → owner-directed review/fixes/refactor ตาม workflow → final candidate required CI ผ่าน; บันทึก SHA/links เมื่อมีคำสั่ง publication | Not Run |

## การเลือกตรวจและหลักฐาน

- เริ่ม PaperBotPanel tests ใหม่ และปรับ frontend/tests/PaperTradePage.test.tsx
- ใช้ ManualOrderForm, ManualOrderSession, PaperTradingActivity, KillSwitchControls,
  AccountSession tests เดิมก่อนเพิ่มกรณีที่ขาด
- แยก no-mutation checks ของ panel ออกจาก tests ที่ตั้งใจกด cancel/retry/TP-SL/STOP:
  อย่างหลังอนุญาตเฉพาะคำขอที่ assertions เดิมคาดไว้และบัญชี fixture
- E2E ที่เคยเปิด NEW ผ่าน UI: บันทึก mapping เป็น API setup + server/UI outcome assertions
  และ unit/session proof; ห้ามลบ coverage เงิน/idempotency/UNKNOWN เพราะปุ่มถูกถอด
- ฐานข้อมูลจริงสำหรับ E2E ใช้ fixture ที่แยกจาก owner; ไม่ mock เงินเพื่ออ้าง safety ผ่าน
  browser geometry ใช้ read-only fixtures ได้ แต่ไม่ถือเป็นหลักฐาน financial correctness
- ไม่ส่งออเดอร์ Live หรือคำสั่งในบัญชีเจ้าของ ไม่เปิด runtime bot หรือแก้ DB เจ้าของ
- บันทึก command/candidate/ผล/หลักฐานใน evidence หลังรัน; Failed/Incomplete คงประวัติ

## ตรวจด้วยมือ

เปิด Paper Spot ตรวจหัวข้อ เลือก Grid Close System ใส่งบ กด Enter และสลับขนาดหน้าจอ
ปุ่มเริ่มต้องยัง disabled ข้อความยังไม่เปิดใช้งานชัดเจน ไม่มีฟอร์มเทรดมือ
เปิด Settings และกลับมา ร่างยังอยู่; เปลี่ยนคู่เทรดร่างถูกล้าง
ดูออเดอร์/ประวัติเดิมได้โดยไม่ต้องส่งคำสั่งใหม่ ไม่ทดสอบ STOP/ซื้อขายบัญชีเจ้าของอัตโนมัติ
owner visual acceptance ยัง Not Run จนมีหลักฐานจริง ไม่ใช้ screenshot fixture แทน

## Batch / Release และข้อจำกัด

งานนี้ไม่มี strategy/runtime หรือ money backend change จึงไม่สร้าง workload/DB migration gate ใหม่
ผลเดิมที่ยัง valid ใช้ต่อได้; ด่าน Batch/Release และ dependency ของ F-17/F-20/F-21
คงสถานะตาม roadmap ไม่ถือว่าผ่านจาก UI นี้; หากพบผลกระทบใหม่ต้องระบุและเพิ่ม targeted proof
ยังห้ามกล่าวว่า UI พร้อม merge จน V10 ผ่าน และห้ามกล่าวว่าบอทใช้งานได้แม้ UI ผ่านครบ


## Review corrections — 2026-11-13

V11 ขึ้นกับการอนุมัติ RQ-13; V12 แก้ช่องว่างการอ้างหลักฐานของ journal
เพิ่ม browser case ผ่าน modal SELL จริงบนบัญชี fixture เพื่อพิสูจน์ก่อน POST และหลัง reload
ส่วน legacy BUY ที่ไม่ได้ให้สร้างใหม่แล้วทดสอบ recovery ด้วย seed journal และ server outcome
V02 ตรวจเฉพาะ bot-panel interactions; ไม่ปะปนกับการยืนยันขาย/cancel/retry โดยตั้งใจ
คงการทดสอบเงิน/ยอดจอง/protection revision ในฐานจริง ไม่มีการผ่อน assertions
ณ เวลาตรวจเอกสาร เกณฑ์ยัง Not Run; ผล implementation ปัจจุบันอ่านจากตารางด้านบนและ checkpoint ไม่ถือว่าการตรวจเอกสารเป็น code review

## Implementation evidence

[Local checkpoint](evidence/implementation-checkpoint.md) — V01–V09/V11–V12 ผ่าน; V10 ยัง Not Run (รอ review/required CI). Owner visual acceptance ยัง Not Run.

## Review-fix validation

[Review fixes R1–R3](evidence/review-fixes.md): เพิ่มหลักฐาน SELL recovery ฐานจริง, long-modal geometry และ exact safety assertions ผ่านแล้ว. V07/V08/V11 ใช้หลักฐานรอบนี้แทนส่วนที่รีวิวพบช่องว่าง. V10 ยัง Pending — รอคำสั่ง refactor และ required CI; ไม่ถือว่าพร้อม merge.

Display amendment 2026-11-13: ถอดข้อมูล ณ/วันเวลาจากแผงบอทแล้ว; PaperBotPanel+PaperTradePage 35 tests ผ่าน (2.33s), targeted ESLint/typecheck/diff check ผ่าน. Vite5173 เสิร์ฟ component ใหม่แล้ว. คำสั่ง lint แรกใช้ cwd ผิดและไม่ได้ตรวจ; รันใหม่จาก frontend ผ่าน. ไม่มีการเปลี่ยน API/เกณฑ์ความสดหรือคำขอซื้อขาย.

Compact panel amendment 2026-11-13: หัวข้อ Paper Spot, ยอดใช้ได้บรรทัดเดียว, spacing กระชับ; ถอด summary สามส่วนตามคำสั่ง. Component/page tests 35 ผ่าน (2.22s), targeted ESLint/typecheck/diff check ผ่าน. ปรับ E2E heading/setup locators ตามข้อความใหม่เท่านั้น; ไม่รัน financial E2E ซ้ำเพราะ mutation/gates ไม่เปลี่ยน. Local preview5173 ใช้ worktree นี้ต่อ.

Admission-warning placement 2026-11-13: PaperTradePage 34 tests ผ่าน (2.48s) รวมตรวจคำเตือนอยู่เฉพาะ SELL dialog และ direct submit ถูกบล็อก/POST0. Targeted ESLint/typecheck/diff check ผ่าน; recovery/error regressions เดิมผ่าน. Vite5173 อัปเดตจาก worktree เดิม; ไม่เปลี่ยน safety gates หรือ API.

Stable balance refresh 2026-11-13: 36 component/page regression tests ผ่าน (2.76s) และ test ใหม่ delayed refresh/DOM node เดิม/SELL gate ผ่าน1 (1.22s; อีก34กรณี filtered โดยใช้ผลเดิม). Targeted ESLint/typecheck/diff check ผ่าน. Initial/error/owner/episode guards เดิมยังผ่าน; ไม่มีการคำนวณยอดหรือเปลี่ยน financial gates. คำสั่งเพิ่ม test ครั้งแรกใช้ cwd ผิดและไม่แก้ไฟล์; เพิ่มใหม่และตรวจผ่านแล้ว. Local Vite5173 อัปเดตแล้ว.

Refresh-label amendment: targeted balance/draft tests3ผ่าน (อีก34filtered ใช้ผลเดิม), ESLint ผ่าน. ซ่อนเฉพาะสถานะ background ด้วย sr-only; ตัวเลขและ scope/error behavior ไม่เปลี่ยน.


Refactor checkpoint 2026-11-13: [หลักฐาน](evidence/refactor-checkpoint.md) — 80 unit tests, 3 real-DB browser tests, lint/typecheck/diff check Passed. คำสั่ง refactor ได้รับและดำเนินการแล้ว; V10 ยัง Pending required CI. ใช้หลักฐาน unaffected เดิมต่อ.


## Publication candidate f239ef4 — PR69

[CI](https://github.com/yukasung/tiewtrade/actions/runs/43459512564) Failed: backend/API contract/Docker Passed; frontend 686 tests Passed but Node suite failed on browserSetup window access; E2E 33 Passed/3 Failed (wallet horizontal overflow, shorter-panel scroll expectation, account-menu locator). [Security](https://github.com/yukasung/tiewtrade/actions/runs/43459506546) Passed on same SHA. V10 Failed, no rerun/merge. PR69 is stacked on unmerged navigation4a9b46a; final checks after retargeting still required. See [proposed corrections](publication-ci-corrections-proposal.md).

Publication corrections: local67 unit tests +3 browser cases, lint/typecheck Passed. Dependency14c62e6 integrated; previous CI Failed remains. Wallet overflow cause not proven locally; strict-width check plus failure bounds await new CI. See approved correction proposal.


## Corrected publication checkpoint — 2026-11-14

Candidate `63e8c2b`, dependency `14c62e6`: [CI Passed](https://github.com/yukasung/tiewtrade/actions/runs/43467926864), [Security Passed](https://github.com/yukasung/tiewtrade/actions/runs/43467915031). Frontend709/42files, browser59 and backend5006 across stages Passed; API contract/Docker Passed. Local targeted67 unit/3browser and lint/types Passed. Previous f239ef4 failures remain historical. Wallet360px check passed on Linux; exact original root cause remains unproven, no speculative CSS change. Only harness/tests/docs changed in correction; no new refactor gate. V10 candidate checks Passed, but final main-base dependency/retarget checks and owner acceptance remain pending; not merge-ready or Completed. No additional commit merely to record CI.


## Main-base integration — 2026-11-14

Owner instructed proceeding with PR69 base integration/checks after PR70 and PR71
merged. Integrated main60dd945 without conflicts; preserved the pre-existing
63e8c2b CI evidence edits. STOP test changes already agree across both branches.
No new bot production logic or acceptance changes. Remaining diff versus main
contains only the bot panel feature and its existing tests/specs.

Targeted combined validation:8 files/107 tests Passed (PaperBotPanel,
PaperTradePage, ManualOrderForm, useManualAttempt, PaperTradingActivity,
KillSwitchControls, TopNavigation, CompactMarketNavigation). Frontend lint and
TypeScript Passed; working/staged diff checks Passed. Existing browser proofs
remain historical; final required CI after retarget to main is pending. No
additional local financial workload or owner/Live commands. Publish one combined
candidate, monitor required CI, stop/report failures; no automatic merge.

Prior main67b02ff indicator5m lock timeout remains unresolved despite passing
subsequent candidates; integration introduces no backend fix. F17/F20/F21 and
owner visual acceptance retain their existing status.
