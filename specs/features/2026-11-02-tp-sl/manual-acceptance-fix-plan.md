# F-17 — Net-fee quantity and local stop readiness — Plan

สถานะ: **Approved — เจ้าของตอบ approve วันที่ 2026-11-08; implementation/checks ตามขอบเขตนี้ได้รับอนุมัติแล้ว**
วันที่: 2026-11-08 (Asia/Bangkok)
Requirements: [MR-01–11 Approved A](manual-acceptance-fix-proposal.md)
Validation: [manual-acceptance-fix-validation.md](manual-acceptance-fix-validation.md)

## 1. Candidate และขอบเขต

ใช้ main ล่าสุดเป็นฐานเมื่อเริ่ม implementation ตรวจ diff กับ recovery branch ก่อน
รวม main; คง local edits ที่มีอยู่และไม่แก้งานอื่น. งานนี้อยู่ใน F-17/spec เดิม.
ไม่ commit/push/เปิด PR/merge จนมีคำสั่ง Git จากเจ้าของ.

เปลี่ยนเฉพาะการคำนวณ executable protection quantity, การสร้าง exit, response/UI
ที่ต้องบอก partial coverage และ configuration local stop authority. ไม่แก้ matching,
fee, PnL, risk thresholds, session storage, load criteria หรือเปิด Live.

## 2. ใช้ของเดิมซ้ำ

| ของเดิม | การใช้ |
|---|---|
| `backend/src/tiewtrade/core/money/order_arithmetic.py::align_quantity` | ปัด quantity ลงตาม explicit step ไม่เขียนสูตรใหม่ |
| `core/protections.py::{validate_setup,evaluate_trigger}`; `core/orders.py::OrderConstraints.check` | วาง calculation บริสุทธิ์ใน domain และตรวจ minimum/notional/capability เดิม |
| `infra/protections/worker.py::{process_group,queue_exit}`; `storage.py`, `codec.py` | ใช้ owner lock, transaction, immutable events, replay และ durable exit identity เดิม |
| `services/api/protection_routes.py`, `protection_models.py`; `backend/openapi.json`, `frontend/src/api-types.ts` | response เดิมและ generated contract |
| `frontend/src/{ProtectionPanel.tsx,protections.ts,protectionMessages.ts}` | แสดงจำนวนป้องกันได้/เศษด้วย MarketValue และ UI กลางเดิม |
| `frontend/src/components/ui/`; `references/admin-template/src/components/ui/{alert/Alert.tsx,badge/Badge.tsx}` | ใช้ pattern เดิม ไม่เพิ่ม appearance ใหม่ |
| `services/api/kill_switch_routes.py`; `services/engine/{paper_order_main,risk_limit_main,paper_wallet_main}.py` | authority flag/stop processing และ compatible writer proof เดิม |
| `frontend/src/{KillSwitchControls.tsx,killSwitchJournal.ts}` | คง idempotency journal และ unknown-result semantics |

เพิ่ม helper เฉพาะ calculation ที่ setup/exit/API ต้องใช้ซ้ำใน core/protections.py;
รับ constraints/reference เป็น arguments ไม่อ่าน DB/clock/global cache ใน core.
ใช้ Quantity/Money ตลอด ไม่มี Decimal/float หรือ rounding policy ใหม่.

## 3. Quantity และความจริงของ allocation

1. `Protection.quantity` ยังคือ remaining allocation ทั้งก้อนของกลุ่ม ไม่เปลี่ยน
   net acquired, held, fee, ledger หรือ position. ส่วนเศษยังผูกกับกลุ่มเดิมจน explicit
   cancel/replace/manual selected sale; ไม่ปล่อยเป็น free quantity อัตโนมัติ.
2. คำนวณ executable portion ด้วย align_quantity(allocation, market.quantity_step).
   เศษ = allocation − aligned ผ่าน Quantity. ถ้า aligned เป็นศูนย์/ไม่ผ่าน constraints
   เดิม ให้ fail closed โดยไม่สร้าง exit และไม่แสดง protected.
3. setup ตรวจ aligned quantity และ notional ด้วย market constraints/average price
   เดิม. ปัดลงไม่ได้ยกเว้น minimum/notional/unsupported rules หรือ price freshness.
4. ARMING→ARMED อนุญาตเมื่อ aligned portion ขายได้; covered quantity รับรองเฉพาะ
   aligned portion. ไม่แก้เอกสารประวัติของกลุ่ม FAILED เดิมและไม่ re-arm อัตโนมัติ.
5. ก่อน trigger/create exit ภายใต้ owner lock ใช้ authoritative allocation และ
   verified market metadata ล่าสุด แล้วคำนวณ/ตรวจ aligned portion ซ้ำด้วย helper เดียว.
   อ่าน/ตรวจ/เปลี่ยน state/queue exit ภายใน transaction เดียว; ถ้าข้อมูลไม่พร้อมไม่ queue.
6. durable exit row/command เก็บ quantity ที่เลือกจริงครั้งนั้น. หลัง queue แล้ว
   replay/retry/ACK-loss ใช้ quantity กับ identity เดิม ไม่ resize คำสั่งที่ส่งแล้วตาม
   metadata ใหม่. Matching/execution ยังใช้ filter และ reconciliation contract เดิม.
7. late entry fill ใช้กลไก extra_exit เดิมเฉพาะส่วนที่มาจาก fill ใหม่จริง พร้อม align/check
   ส่วนที่จะออกโดยไม่เกิน allocation. ห้ามนำเศษจาก terminal exit มาสร้าง MARKET ใหม่วน.
   ถ้า late quantity ปิดไม่ได้ให้เหลือเป็น residual ที่แสดงจริง ไม่สร้าง zero order.
8. terminal exit ที่ยังมี quantity เหลือคง lifecycle residual เดิมและไม่แสดง CLOSED.
   การลด allocation จาก fill/correction ยังอาศัย effective executions และ conservation
   เดิม; ไม่ทำ accounting delta จาก quantity ที่เพียงคำนวณว่าจะขายได้.

ไม่เสนอ migration หรือ persist derived coverage เพิ่มในรอบนี้. หากจำเป็นต้องเปลี่ยน
schema/persistence protocol หรือพบ spec ขัดกัน ให้หยุดเสนอ amendment ก่อนลงมือ.

## 4. API / UI

- คง `quantity` เป็น allocation เต็ม. `protected_quantity` ใน ARMED ต้องใช้ validated
  executable quantity; ข้อมูลตลาดไม่พร้อมให้0 ไม่อ้าง protection ที่พิสูจน์ไม่ได้.
- เพิ่ม response fields string `executable_quantity` และ `step_residual_quantity`
  แบบ additive; API ใช้ helper เดียวกันและ statement/transaction snapshot ของ owner.
  เมื่ออ่าน constraints ไม่ได้ให้ executable0 และแสดง allocation ว่ายังยืนยันไม่ได้
  ไม่เรียกทั้งหมดว่า step dust โดยไม่มี metadata: เพิ่ม nullable residual สำหรับกรณีนี้.
- EXITING แสดง linked exit quantity/status เดิม ไม่อ้าง latest metadata ว่า resize
  exit สำเร็จ. ค่าคำนวณปัจจุบันแยกจากคำสั่งที่ส่งไปแล้วอย่างชัดเจน.
- UI แสดง allocation, covered และเศษแยกกัน พร้อมข้อความไทย/อังกฤษว่าขนาดเศษยังไม่
  ป้องกัน/ไม่ขายเพิ่มอัตโนมัติ. ใช้ formatters/components/template เดิม ไม่แก้ layout อื่น.
- ไม่เพิ่ม mutation endpoint, ไม่คำนวณเงินด้วย JS number และไม่ให้ client อนุมัติ quantity.

## 5. Local stop readiness และ operational scope

ใช้ launcher local ที่มีอยู่ใน operator state นอก repo; เพิ่ม explicit
TIEWTRADE_TRADING_STOP_AUTHORITY_ENABLED=1 เฉพาะหลังตรวจ schema0066 และทุก active
financial writer เป็น candidate ที่รองรับ stop revision/protection allocation แล้ว.
ไม่เปลี่ยน default-off ของ source หรือ compose deployment ทั่วไป ไม่เพิ่ม infrastructure.
Worker รับเฉพาะ engine/scan role credentials เดิม ไม่รับ API sealing/venue keys.

### Browser storage failure (review finding R3)

เพิ่มขอบเขตแก้ `KillSwitchControls.tsx` และ journal helpers ที่ caller นี้ใช้:
จับ storage access ทั้ง getItem/setItem/removeItem รวม getter ที่อาจโยน SecurityError.
อย่าให้ storage cleanup หลัง API สำเร็จเปลี่ยน receipt ที่รู้ผลแล้วกลับเป็น unknown.
ใช้ attempt key เดิมใน component ref เป็น scheduling/retry hint เท่านั้น ไม่ใช้เป็น
session หรือแหล่ง business truth; durable request/ผลหยุดยังอยู่ PostgreSQL ตามเดิม.
Storage write failure ต้องไม่ขวางการส่ง STOP ครั้งแรกหรือซ่อน error จากผู้ใช้.
ขณะ component ยังอยู่ retry หลังผลไม่แน่นอนต้องใช้ key เดิม และกัน repeated click
ระหว่าง pending ตาม pattern เดิม. ห้ามสร้าง key ใหม่เงียบ ๆ เมื่อส่งแล้วแต่ยังไม่รู้ผล.
หลัง reload/remount/owner switch ใช้ owner/mode-scoped server status/receipt เดิม
เพื่อแสดงผลจริง; ถ้ากู้ identity เดิมไม่ได้ให้บอกข้อจำกัด ไม่ส่งใหม่อัตโนมัติหรืออ้างว่า
หยุดสำเร็จ. การกดใหม่โดย owner ต้องแยกจาก automatic retry ของ intent ที่กู้ key ไม่ได้.
คง auth/CSRF, known4xx/unknown5xx semantics และ revision-checked resume เดิม.
ใช้ UI Alert/shared controls และ journal utilities เดิมก่อนเพิ่ม helper; เปลี่ยน shared
helper เฉพาะพฤติกรรมที่จำเป็นและตรวจ resume/platform callers ที่ได้รับผลกระทบ.

ก่อนเปิด Paper ต้องเห็น wallet/risk evaluation READY, publication watermark เดิน,
source พร้อม และ stop worker พร้อม. ต้องตรวจ effective API stop authority ของ process
ที่จะใช้จริง พร้อมหลักฐาน default-off/opt-in durable STOP และ completion ก่อนเปิด
admission; worker PID หรือ risk READY อย่างเดียวใช้แทนไม่ได้.
เปิด publication→financial→admission และ protection
ตาม approved procedure; ถ้าด่านไม่พร้อมคง admission ปิด. Restart API ไม่อ่าน/ส่งคำขอ
STOP จาก browser journal แทน owner. คง5xx unknown-result behavior จนมี durable proof.

หลัง review/refactor/affected checks ผ่าน ให้เตรียม manual acceptance บน local สำหรับ
owner หนึ่งรอบ: ตรวจ READY, owner เรียก Paper STOP ผ่าน UI ด้วย key เดิมเมื่อ retry,
ตรวจ receipt/completion/zero duplicate และยืนยันว่า MANUAL resume ใช้ไม่ได้ตาม contract.
ใช้หลักฐาน BOT resume ที่ผ่านแล้วแยกต่างหากตาม [Approved A mapping](manual-profile-clarification.md).
จากนั้น owner เลือกคำสั่ง Paper/TP/SL เอง; agent ไม่เลือกขนาด/ราคา/ส่ง BUY/SELL แทน.
ใช้ controlled fixture real-DB/browser เพื่อพิสูจน์ trigger/exit deterministic ก่อน;
manual real-price observation ไม่ต้องรอราคาไปแตะ TP/SL เพื่อสร้างผลผ่าน.

ถ้าต้องแก้หรือจัดสรร position/กลุ่ม FAILED เดิม ต้องให้ owner สั่งผ่าน UI เอง ไม่ reset
หรือเปลี่ยนประวัติ. จบ manual acceptance ปิด admission→financial→publication และปิด
protection เมื่อไม่มี unresolved protection work; หากยังมีงาน/position ที่ต้องดูแล
รายงานสถานะก่อน ไม่ auto-liquidate หรือประกาศว่าไม่มี exposure.
นี่เป็น local manual acceptance ไม่ใช่ internal pilot release หรือ public activation.

## 6. ลำดับและจุดหยุด

1. รออนุมัติ plan และ validation นี้ก่อนแก้ source/config; บันทึก candidate/config.
2. ทำ domain→DB/worker→API/UI และ targeted safety tests ตาม validation. เปลี่ยน test
   เดิมเฉพาะ off-step ที่มี executable portion; retain below-minimum rejection.
   รวม storage failure/recovery และ operational stop-readiness proof ก่อนเปิด manual.
3. รัน affected Ruff/format/mypy/import checks, frontend lint/types/tests และ generated
   API consistency ตาม diff; ไม่รัน workload/full suite ซ้ำเป็นพิธี.
4. implementation ครบแจ้ง **Ready for Code Review** พร้อมผล/ความเสี่ยง แล้วหยุดรอ
   `review code`. หลัง review/fix รอ `refactor the code` ตาม AGENTS.md.
5. หลัง authorized refactor ทำ affected validation ต่อ; local manual round ตาม§5
   และ required CI เมื่อได้รับคำสั่งเผยแพร่ candidate. หากล้มไม่รัน manual ซ้ำอัตโนมัติ.
6. owner สั่ง commit/push/merge แยกตาม Git gates; ติดตาม required/post-merge CI ตามเดิม.
7. ถ้าล้มเกณฑ์เดิม3รอบ/owner แจ้งว่าใช้เวลามาก หยุดเสนอทางเลือก; ไม่ลด correctness.

ไม่มี workload100accounts/4h หรือ bot/notification/Live campaign ใน amendment นี้.
ผล Failed manual เดิมยังอยู่; successful fix ไม่เปลี่ยน F-17 เป็น Completed.

## Review disposition — 2026-11-08

| Finding | การแก้ที่วางแผน / สถานะจริง |
|---|---|
| R1 High: net-fee quantity rejected | §3–4 / MF-01–08; source ยังไม่แก้ |
| R2 High: admission without stop authority | §5 effective-process authority/STOP proof ก่อน admission / MF-09,13; config ยังไม่แก้ |
| R3 High: storage blocks STOP silently | §5 browser storage failure / MF-10; source ยังไม่แก้ |
| R4 Medium: roadmap misses current blockers | roadmap เพิ่ม current-blocker checkpoint; ไม่เปลี่ยน historical Passed |

เจ้าของสั่ง “แก้ไข” หลัง review: ปรับเอกสารและขอบเขตตาม findings แล้วในรอบนี้.
Plan/validation ยัง Proposed; ต้องอนุมัติฉบับปรับนี้ก่อนแก้ source/config.


## Implementation checkpoint — 2026-11-08

Owner approved the revised plan/validation. Implementation and scoped checks are
recorded in [checkpoint](evidence/manual-acceptance-fix/implementation-checkpoint.md).
Earlier Proposed/approval-wait statements are historical boundaries superseded by
that approval. No owner manual replacement or active local deployment has occurred.


## UI readability correction — 2026-11-08

Owner reported unreadable TP/SL warning during MF-13. Within approved MR-03/UI
scope, restore shared Alert template colors rather than redesigning the panel.
Reuse references/admin-template/src/components/ui/alert/Alert.tsx and existing
frontend/src/components/ui/Alert.tsx. Add a shared CSS marker and exclude that
component from the legacy generic role=alert skin in styles/admin-theme.css.
Preserve role semantics, all variants, existing plain error paragraphs, translations,
financial fields and interactions. No layout/business/authorization changes.
Validate real-browser computed warning/error appearance in light/dark plus plain
legacy error appearance, affected types/lint and existing Paper component tests.
No owner actions, timed workloads or financial revalidation for this style fix;
existing functional owner evidence remains valid.


## Owner-requested review corrections — 2026-11-08

Owner instructed “แก้ไข” after High/Medium findings. Resolve persisted STOP hints
with an existing read-only receipt query on mount before labeling an action fresh
STOP. Durable received receipts (including pending) retire the recovered hint, as
a successful receipt did before; this is not an automatic POST. Unknown/not-found
retains the original identity for explicit retry. Lookup failures remain unknown,
with a clearly labeled recovery action; storage unavailable without a readable
hint still permits STOP. Once the prior receipt is known, a normal explicit STOP
uses a fresh key even if USER remains active and MANUAL never resumed. Preserve
owner/mode scope guards and do not allow a background lookup to retire a newer key.
Display API exit_quantity separately from allocation/coverage/filled quantity in
linked-exit details, without client financial calculation or resizing intents.
Add scoped regressions for stale APPLIED/active-MANUAL and queued/partial/metadata
exit quantities; retain prior safety proof, no owner orders or new manual campaign.
