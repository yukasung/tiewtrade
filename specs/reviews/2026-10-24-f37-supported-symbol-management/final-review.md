# F-37 — Final code review

วันที่: 2026-10-25

ผล: **Critical/High findings ไม่มีค้าง**

## Findings และการแก้

### High — ADD replay ยังพึ่ง venue availability

- File/location: `backend/src/tiewtrade/services/api/catalog_routes.py` และ
  `backend/src/tiewtrade/infra/platform/storage.py`
- Problem: endpoint เรียก public venue capability ก่อนตรวจ durable idempotency command ทำให้ retry
  ของคำขอที่สำเร็จแล้วคืน 503 ได้เมื่อ venue ล่ม แทนที่จะคืนผลเดิมตาม V-11/RQ-12
- Impact: Admin เห็นผลไม่แน่นอนและอาจ retry ซ้ำโดยไม่ทราบว่า catalog command ถูกสร้างแล้ว
- Recommended fix: ตัดสิน exact replay/conflict จาก command ภายใต้ requester RLS ก่อนแตะ venue
- Resolution: **Fixed** — เพิ่ม `replay_command()`, column-level SELECT grant ภายใต้ FORCE RLS
  และ regression test ที่ทำให้ venue unavailable แต่ replay เดิมยังคืน 202

### High — V-12 ขาด negative protocol-gate matrix

- File/location: `backend/tests/infra/catalog/test_migration.py`
- Problem: มี happy-path heartbeat ใน lifecycle แต่ไม่มีหลักฐานตรงสำหรับ missing heartbeat,
  expired lease และ mixed deployment generation ตาม validation
- Impact: ยังกล่าวว่า rolling-deployment gate ผ่านไม่ได้ แม้ implementation จะ fail closed
- Recommended fix: เพิ่ม PostgreSQL integration ที่เรียก enable จริงและพิสูจน์ทั้งสาม rejection
  ก่อนยอมรับ heartbeat ที่ version/generation/lease ตรงครบ
- Resolution: **Fixed** — เพิ่ม negative matrix และผ่านบน fresh migration

### High — BUY ที่รับเข้าก่อน remove อาจกลับมาจับคู่หลัง re-add

- File/location: `backend/src/tiewtrade/infra/paper_orders/dispatch.py`,
  `backend/src/tiewtrade/infra/paper_orders/storage.py`,
  `backend/src/tiewtrade/infra/paper_orders/worker.py` และ migration `0040`
- Problem: worker ตรวจเฉพาะสถานะ ACTIVE ปัจจุบัน จึงแยกไม่ออกว่า command ถูก admit ก่อน removal
  ที่เกิดคั่นกลางแล้ว pair ถูก re-add
- Impact: queued/resting BUY เก่าอาจถูก execute หลังเจ้าของถอนคู่ไปแล้ว ทำให้เกิด unintended trade,
  balance และ position เปลี่ยนผิดนโยบาย
- Recommended fix: บันทึก catalog revision ตอน admit และเปรียบเทียบกับ removal revision ล่าสุดภายใต้
  pair fence เดียวกัน ทั้ง queued และ resting order
- Resolution: **Fixed** — durable payload เก็บ admitted revision โดยไม่เปลี่ยน idempotency fingerprint;
  worker reject/cancel command รุ่นเก่าแม้สถานะปัจจุบันกลับเป็น ACTIVE และ effect reconciliation แยก
  command รุ่นหลัง re-add ออกจาก removal เก่า

### High — indicator scheduler ยังเลือกงานของคู่ที่ถอนออก

- File/location: `backend/migrations/versions/0040_supported_symbol_catalog.py`
- Problem: claim/coalesce/rollout readiness ยังอิง job เดิมโดยไม่กรอง catalog และ dispatch modulus
  ยังอิงจำนวนคู่คงที่
- Impact: ใช้ทรัพยากรกับคู่ที่ถอน, readiness count ผิด และ scheduler อาจคำนวณ dispatch ผิดเมื่อ
  catalog เปลี่ยน
- Recommended fix: กรอง ACTIVE/PREPARING ในทุก eligibility path และคำนวณ dispatch domain จาก
  catalog ภายใต้ SQL function เดิม
- Resolution: **Fixed** — ปรับ claim/coalesce/rollout functions ทั้ง upgrade/downgrade และผ่าน
  indicator regression 124 tests; ระหว่างตรวจพบ ambiguous `USING(base, quote)` จากลำดับ join
  และแก้ให้ join heads ก่อน pair fence แล้ว

### High — candle preview metadata ของคู่ที่ถอนสะสมเกิน bound

- File/location: `backend/src/tiewtrade/infra/market_data/candle_preview.py`
- Problem: metadata key ของ retired pair ไม่ถูกลบ แต่ bound ลดลงตาม runtime catalog
- Impact: producer อาจหยุดด้วย `unbounded preview metadata` หลังถอนคู่ ทำให้ preview ของคู่ที่ยังรองรับ
  ไม่เดินต่อ
- Recommended fix: prune metadata ด้วย runtime pair set ก่อนตรวจ bound และเขียน state
- Resolution: **Fixed** — prune stale keys ใน transaction เดียวกันและมี regression test ตรง

### High — re-add ระยะ REQUESTED/FAILED ตัด maintenance feed ของ exposure เดิม

- File/location: `backend/migrations/versions/0040_supported_symbol_catalog.py`
- Problem: runtime view รวม maintenance เฉพาะ REMOVED; เมื่อเริ่ม re-add สถานะเปลี่ยนเป็น REQUESTED
  หรือ FAILED ทั้งที่ยังมี position/order เดิม คู่จะหายจาก runtime feed
- Impact: position เดิมขาดข้อมูลราคา/แท่งสำหรับ risk และ reduce-risk path
- Recommended fix: คง REQUESTED/FAILED ใน runtime catalog เมื่อ durable exposure proof ระบุว่ายังต้อง
  maintenance
- Resolution: **Fixed** — view ใช้ `supported_symbol_requires_maintenance()` กับทั้งสามสถานะ
  REMOVED/REQUESTED/FAILED และ migration test ตรวจ definition

### High — stale readiness race ทำให้ quote supervisor หยุดถาวร

- File/location: `backend/src/tiewtrade/services/market_data/realtime.py`
- Problem: activation อาจชนะ race ก่อน PREPARING producer บันทึก readiness ทำให้ DB คืน
  `CatalogStateError`; run loop เดิมจับเฉพาะ lease loss
- Impact: public quote producer process ออกจาก supervisor loop และราคาทุกคู่หยุดอัปเดตจน process
  ถูก restart ภายนอก
- Recommended fix: มอง stale catalog write เป็น generation/fence change, ยกเลิกงานรอบเก่าและ reload
  catalog ก่อนเริ่มรอบใหม่
- Resolution: **Fixed** — supervisor จับ `CatalogStateError` แบบเดียวกับ lease fencing และ cleanup
  task ก่อน reload

### Medium — Admin UI ไม่ติดตามสถานะ asynchronous หลังรับ command

- File/location: `frontend/src/SupportedSymbolPanel.tsx`
- Problem: query ถูก invalidate ครั้งเดียวหลัง mutation แต่ไม่มี polling สำหรับ REQUESTED/PREPARING หรือ
  cleanup PENDING
- Impact: ผู้ดูแลเห็นสถานะเก่าจน reload หน้าเอง จึงอาจเข้าใจผิดว่าคำสั่งค้างหรือ retry โดยไม่จำเป็น
- Recommended fix: เปิด bounded polling เร็วระหว่าง transitional state และช้าลงเมื่อ stable
- Resolution: **Fixed** — polling 1 วินาทีระหว่าง transitional/cleanup pending และ 5 วินาทีเมื่อ stable;
  component test พิสูจน์ REQUESTED→ACTIVE โดยไม่ reload

## Coverage หลังแก้

- Requirement/plan: RQ-1–RQ-18 และ M1–M5 ครบในขอบเขต candidate ที่อนุมัติ
- Validation: V-01–V-09, Paper/catalog subpart ของ V-10, V-11–V-17 และ V-20 ผ่าน
- Tests: backend full candidate 3205 ผ่าน; post-review affected 207 ผ่าน; frontend 262 ผ่าน;
  Chromium final 2/2; Ruff/format/mypy/import contracts และ frontend lint/type/build ผ่าน
- Security/transactions: TOTP + DB authorization, FORCE RLS, append-only history/audit,
  global revision + pair fence, wallet→pair lock order และ fail-closed protocol/readiness ตรวจแล้ว

## Remaining risks ที่อนุมัติให้ติดตาม

- Live cancellation/fill/partial/unknown reconciliation ของ V-10 รอ F-22/F-23
- V-18 bot stop/in-app notification รอ F-20/F-26
- V-19 workload/stress/resource profile รอ numeric plan ที่เจ้าของอนุมัติ
- candidate CI และ PR #29 merge ผ่านแล้ว ตาม merge checkpoint ใน M5 evidence;
  post-merge CI: [40160909137](https://github.com/yukasung/tiewtrade/actions/runs/40160909137)

ไม่มีการส่ง Live order ระหว่าง validation

## Follow-up deep review — 2026-10-25

เจ้าของสั่งแก้ findings เพิ่มเติม 4 ข้อบน `deb2a06`; แจ้ง `Ready for Code Review` ก่อนตรวจ
corrections และตรวจ diff/dependencies ที่ได้รับผลกระทบซ้ำแล้ว:

| ระดับ / Finding | Resolution |
|---|---|
| High — claim ของคำสั่งใหม่ยัง match BUY เก่าหลัง remove/re-add ได้ | **Fixed** — `infra/paper_orders/worker.py` ตรวจ admitted revision ของ BUY ทุกใบใน checkpoint ภายใต้ wallet lock/pair fence แล้ว cancel/persist ก่อน advance state ใช้ cancellation/audit/reservation pattern เดิม; PostgreSQL regression ให้คำสั่งใหม่ consume trade ที่อาจ fill ออเดอร์เก่า และยืนยันว่าเฉพาะคำสั่งใหม่ fill ในภายหลัง |
| High — preview bootstrap สร้าง candle readiness ก่อน backfill เสร็จ | **Fixed** — เอาการเขียน proof ออกจาก `services/market_data/candle_realtime.py`; ใช้ ingestion completion เดิมเท่านั้น lifecycle test เรียก bootstrap จริงและพิสูจน์ว่า pending demand ไม่สร้าง candle proof และ activation ยังถูกปฏิเสธแม้ indicator/price พร้อม |
| Medium — delayed venue result เปลี่ยนคำขอใหม่ของ pair/requester เดิม | **Fixed** — `services/engine/catalog.py` ตรวจ pair revision และเก็บ expected global revision ก่อน venue call แล้วใช้ค่าเดิมทั้ง activate/fail; ไม่มีการอ่าน revision ใหม่เพื่อรับรองผลเก่า tests ครอบคลุม replacement ก่อนตรวจและระหว่าง venue I/O ทั้ง success/failure |
| Medium — UI retry ใช้ key เดิมกับ revision/payload ใหม่ | **Fixed** — `SupportedSymbolPanel.tsx` ตรึง payload เมื่อ submit และคง key เดิมขณะ retry; ADD base ถูกล็อกหลัง submit แต่ TOTP เปลี่ยนได้ tests จำลอง lost response แล้ว refresh catalog revision ทั้ง ADD/REMOVE และตรวจ body/key เดิม |

หลักฐาน correction ชุดสุดท้าย: **225 backend tests passed**, frontend affected **6 passed**,
Ruff/format/mypy/import checks และ frontend ESLint/TypeScript/build ผ่าน รายละเอียดการเลือกตรวจ,
exploratory failures และ runtime patch digest อยู่ใน [M5 evidence](../../features/2026-10-24-supported-symbol-management/evidence/m5-local-candidate.md#follow-up-review-corrections--2026-10-25)

ผล: **ไม่มี Critical/High ค้างใน corrections ที่รีวิว**; full candidate/required CI บน
`cf2efd9` ผ่าน 12/12 checks และ PR #29 merge เป็น `033671f` แล้ว
Backend 3258 tests, frontend 265 tests และ Chromium 18+2 tests ผ่าน รายละเอียดและ post-merge
run อยู่ใน [M5 evidence](../../features/2026-10-24-supported-symbol-management/evidence/m5-local-candidate.md#candidate-ci-และ-merge-checkpoint--2026-10-25)
Milestone **Catalog/Order Safety Ready** ไม่ใช่ Completed; V-10 Live, V-18/V-19 ยัง Pending ตามเดิม
