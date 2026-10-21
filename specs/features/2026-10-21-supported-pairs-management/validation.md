# F-37 — รายการเหรียญที่รองรับและการจัดการ — Validation

สถานะ: **Proposed — รอเจ้าของอนุมัติ**

อ้างอิง: [requirements.md](requirements.md) · [plan.md](plan.md)

## “เสร็จ” หมายถึง

| รหัส | เกณฑ์ | ตรวจอย่างไร | ช่วงรัน | ผล / หลักฐาน |
|---|---|---|---|---|
| V-01 | seed catalog มี BTC/USDT และ ETH/USDT เป็น ACTIVE โดยข้อมูลเดิมไม่เปลี่ยน | PostgreSQL migration fixture + count/digest | Candidate | Not Run |
| V-02 | pair canonical, Spot/USDT, lifecycle transition และ revision ถูกบังคับทั้ง core/DB | unit + constraint/negative integration | ระหว่างพัฒนา | Not Run |
| V-03 | core ไม่อ่าน DB/network/time และทุก financial caller รับ snapshot/revision ชัดเจน | unit + import-linter + caller review | ระหว่างพัฒนา | Not Run |
| V-04 | API role เขียนได้เฉพาะ command; lifecycle/readiness/audit/economic state เขียนตรงไม่ได้ | PostgreSQL grant/RLS negative tests | Candidate | Not Run |
| V-05 | เฉพาะ Platform Admin/Owner จัดการได้; role จาก client ปลอมไม่ได้และ default deny | authenticated API integration ทุก role | ระหว่างพัฒนา | Not Run |
| V-06 | add ต้อง fresh TOTP, recovery code ใช้ไม่ได้; remove ไม่ถูก TOTP ขวาง | route-policy/TOTP integration | ระหว่างพัฒนา | Not Run |
| V-07 | idempotency exact retry คืนผลเดิม, payload ต่าง conflict และ concurrent mutation มี transition เดียว | API+PostgreSQL concurrency tests | Candidate | Not Run |
| V-08 | add เปิดได้เมื่อ venue metadata และ readiness generation ปัจจุบันผ่านครบเท่านั้น | venue stub + market-data/engine integration | Candidate | Not Run |
| V-09 | venue invalid/failure, stale/missing proof หรือ restart ทำให้คู่ไม่ ACTIVE และ retry ต่อได้ | failure injection/restart integration | Candidate | Not Run |
| V-10 | re-add สร้าง generation ใหม่ ไม่ใช้ proof เก่า และไม่ลบ history | lifecycle integration + digest | Candidate | Not Run |
| V-11 | withdrawal commit ปิด opening admission/dispatch/matching ทุกทางตาม revision เดียว | deterministic race/integration tests | Candidate | Not Run |
| V-12 | ไม่มี fill ใหม่หลัง withdrawal revision commit แม้งานถูก enqueue/claim ก่อนหน้า | barrier-controlled worker race | Candidate | Not Run |
| V-13 | opening remainder ถูก cancel และ reservation คืนครั้งเดียวใน transaction เดียว | PostgreSQL order/wallet invariant tests | Candidate | Not Run |
| V-14 | partial fill ก่อน fence คง fill/position/history และ cancel เฉพาะ remainder | controlled fill-withdraw race + ledger digest | Candidate | Not Run |
| V-15 | retry/restart/worker ซ้อนระหว่าง withdrawal ไม่ cancel/release/event ซ้ำ | multi-worker crash/retry integration | Candidate | Not Run |
| V-16 | risk-reducing close หลังถอนยังผ่าน quantity/position/reduce-only gates และทำได้ | order/position integration | Candidate | Not Run |
| V-17 | ถอนคู่หนึ่งไม่เปลี่ยน balance/position/order ของคู่อื่นและไม่ block ทั้งระบบ | multi-pair/multi-owner concurrency test | Candidate | Not Run |
| V-18 | feed cleanup เกิดเมื่อ authoritative dependencies เป็นศูนย์; อ่านไม่ได้ให้คง feed/history | dependency claim/cleanup integration | Candidate | Not Run |
| V-19 | public/admin API แยกข้อมูลเหมาะสม, revision monotonic และไม่มี raw venue/secret | contract, auth, redaction tests | ระหว่างพัฒนา | Not Run |
| V-20 | audit/outbox append-only ครบ actor/action/old-new/revision/outcome/reason และ event ไม่ซ้ำ | PostgreSQL audit/event integration | Candidate | Not Run |
| V-21 | frontend ใช้ server catalog ไม่มี runtime enum/static fallback และทิ้ง stale identity/revision | frontend unit/component tests | ระหว่างพัฒนา | Not Run |
| V-22 | admin UI ครบ loading/error/disabled/confirm/progress, keyboard/focus/responsive และไทย/อังกฤษ | component + browser smoke + template diff review | Candidate | Not Run |
| V-23 | OpenAPI/generated types ตรงกันและ dynamic pair ไม่ต้อง rebuild frontend | drift check + contract fixture pair ที่สาม | Candidate | Not Run |
| V-24 | Paper/Live data/credentials/execution ยังแยก และ automated tests ไม่ส่ง Live order | isolation/negative integration + config review | Candidate | Not Run |
| V-25 | migration upgrade/downgrade guard, backfill, FK และ capability fence ปลอดภัย | PostgreSQL 0038→0039, guarded downgrade, old-binary tests | Candidate | Not Run |
| V-26 | dynamic subscriptions/reconnect ไม่มี duplicate และ resource/queue bounded ใน smoke workload | targeted runtime smoke + metrics | Candidate | Not Run |
| V-27 | pair ใหม่ผ่าน correctness/readiness และ workload/resource ชุดเต็มของ release จริง | production-like release validation | Release checkpoint | Pending Full Validation |
| V-28 | F-16 อ้าง catalog contract นี้ แต่ยังไม่เริ่มจน NC-08 และเอกสาร F-16 ผ่านอนุมัติ | spec/link/roadmap review | ก่อน merge | Not Run |
| V-29 | required backend/frontend/E2E/static/build/security gates ผ่านบน candidate สุดท้าย | required local/CI gates ตาม testing standard | ก่อน merge | Not Run |

## Invariants ที่ต้องพิสูจน์

1. `opening_allowed(pair, revision)` เป็นจริงเฉพาะ lifecycle `ACTIVE` ของ revision authoritative
2. หลัง transaction `ACTIVE -> WITHDRAWING` commit ไม่มี economic write ที่เพิ่ม fill/open exposure
   ของ pair นั้น แม้ worker ถือ message หรือ snapshot เก่า
3. ต่อ order: `filled_quantity + canceled_remainder = admitted_quantity` ตาม lifecycle ที่อนุมัติ
   และ reservation release ไม่เกินยอดที่ยัง reserve อยู่
4. withdrawal/retry ไม่แก้ fill, position, ledger หรือ history ที่ commit แล้ว
5. risk-reducing order ไม่อาศัย active membership แต่ยังต้องไม่เพิ่ม position และไม่เกิน position
6. catalog revision เพิ่มทางเดียว; activation generation ใหม่ไม่ reuse readiness proof รุ่นเก่า
7. command, audit และ semantic event หนึ่งผลลัพธ์ต่อ idempotency identity
8. Redis/cache/UI ไม่สามารถอนุญาต opening แทน PostgreSQL authoritative state
9. คู่หนึ่งล้มเหลวหรือถูกถอนต้องไม่หยุด progress ของคู่/เจ้าของอื่นโดยไม่มี lock dependency

## Test matrix ระหว่างพัฒนา

เลือกชุดเล็กที่สุดตาม diff และผลกระทบ ไม่รัน full suite ซ้ำหลังทุก patch:

- pure core: canonical pair, allowed transitions, opening/reducing policy, revision/generation
- repository/migration slice บน PostgreSQL จริง: seed, uniqueness, transition, grants, audit/outbox
- API slice: auth/role/CSRF/TOTP/idempotency/schema/safe errors
- market-data slice: explicit symbols, venue validation, generation proof, subscribe/reconnect dedupe
- paper-order slice เมื่อแตะ admission/dispatch/matching/cancel: financial lock, revision fence,
  reservation/balance/position/ledger invariants
- frontend slice: dynamic catalog store, stale response, selectors และ admin state machine
- Ruff/format/Mypy/import-linter หรือ frontend lint/type/build เฉพาะเมื่อ code ฝั่งนั้นเปลี่ยน

ผลตรวจเดิมใช้ต่อได้เฉพาะเมื่อ source, contract, migration, dependency, config และ harness ที่ผลนั้น
พึ่งพาไม่เปลี่ยน ทุก test run ต้องระบุ V-code ที่พิสูจน์และสาเหตุที่หลักฐานเดิมไม่พอ

## Candidate ก่อน merge

### Migration และ rollout

1. clone production-like schema ที่ revision `0038` พร้อม users, market data, paper orders,
   positions, reservations, audit และ terminal history ของสองคู่
2. บันทึก deterministic count/digest ของ economic/history tables
3. upgrade `0038 -> 0039`; ตรวจ seed, backfill, validated FK, grants/RLS และ digest เดิม
4. ทดสอบ failure injection ระหว่าง migration ต้อง rollback ทั้งก้อน
5. จำลอง old binary/write path หลัง capability fence ต้อง fail closed ไม่เขียน pair ใหม่
6. downgrade ขณะมีเพียง seed dataต้องผ่าน; เมื่อมี dynamic pair/history ต้องถูก guard ปฏิเสธ
7. upgrade ใหม่และยืนยันผล deterministic โดยไม่สร้าง seed/event/member ซ้ำ

### Add/re-add และ failure recovery

- valid Binance TH Spot/USDT pair: `PREPARING`, metadata, bootstrap/proof, atomic `ACTIVE`
- invalid symbol, non-USDT, non-Spot, venue timeout/malformed response: `FAILED`/retryable reason ที่ปลอดภัย
- proof หาย/หมดอายุ/คนละ generation ห้าม activate
- API, market-data หรือ engine crash ทุก boundary แล้ว restart ต้องเดินต่อจาก durable state
- duplicate Redis wake-up และ worker หลายตัวต้องได้ transition/subscription/event เดียว
- retire แล้ว re-add ต้อง validate/bootstrap ใหม่และ history digest เท่าเดิม

### Withdrawal race matrix

ใช้ explicit barriers แทน timing/sleep เพื่อให้ผล deterministic:

| ลำดับ | ผลที่ต้องได้ |
|---|---|
| admission commit ก่อน withdrawal | order อาจมีอยู่ แต่หลัง fence ห้าม fill และ remainder ต้องถูก cancel |
| withdrawal commit ก่อน admission | admission ถูกปฏิเสธ ไม่มี order/reservation/economic side effect |
| partial fill commit ก่อน withdrawal | fill/position คงเดิม; cancel/release เฉพาะ remainder |
| matching เริ่มก่อนแต่ economic commit หลัง withdrawal | recheck พบ revision ใหม่และไม่เขียน fill |
| user cancel แข่งกับ withdrawal cancel | terminal transition และ release เกิดครั้งเดียว |
| worker crash หลัง state ก่อน/หลัง release/event | retry converge โดยไม่มี double release/audit semantic duplicate |
| ถอนหลาย owner และมี traffic อีก pair | per-owner invariant ผ่านและ pair อื่นยัง progress |

หลังแต่ละกรณีตรวจ order quantities, reservation, available/total balance, fills, positions, ledger,
catalog revision, command outcome และ audit/event ด้วย exact values ไม่ใช้ float comparison

### Frontend/browser

- trader เห็นเฉพาะ opening-active pairs และยังเข้าทาง close ของ withdrawn position ได้
- admin/owner เพิ่มและถอนพร้อม confirmation/progress; regular user เข้า route/action ไม่ได้
- refresh/reconnect/session change/revision out-of-order ไม่คืน pair ที่ถอนมาใน selector
- error ไม่เผย internal/venue raw payload; duplicate click ไม่สร้าง command ใหม่
- ตรวจ keyboard, focus return, screen sizes หลัก และข้อความไทย/อังกฤษเทียบ admin template

### Required gates

- backend targeted safety tests แล้ว full regression ครั้งเดียวเมื่อ candidate นิ่ง
- frontend unit/component, lint, type check และ production build
- Playwright/browser flows ที่ได้รับผลกระทบ
- migration verifier, OpenAPI drift, generated frontend types, import-linter, Ruff/format/Mypy
- dependency/security scan และ secret/redaction checks ตาม CI ปัจจุบัน
- deep review diff + affected dependencies โดยไม่มี Critical/High ค้าง

หลังแก้ finding ให้รันเฉพาะ gate ที่ source/input ถูกกระทบ; รัน full ใหม่เมื่อ candidate หรือ shared
contract/migration/safety behavior เปลี่ยนจนหลักฐานเดิมใช้ไม่ได้

## Release checkpoint / Pending Full Validation

V-27 รันเมื่อมีรายการคู่ release จริงและ candidate คงที่ เพราะผล BTC/ETH เดิมรับรองคู่ใหม่ไม่ได้:

1. activation readiness ครบทุก dependency ของแต่ละ pair และ generation
2. workload/resource/stress/endurance ใช้ threshold และ duration ของ F-09–F-12/F-38 ที่ยังมีผล
   โดยไม่ลด threshold เพื่อให้ pair ใหม่ผ่าน
3. เก็บ latency, freshness, reconnect/recovery, event-loop lag, RSS, queue depth, database growth,
   worker fairness และ subscription count พร้อม pair/generation/revision metadata
4. ทดสอบ withdrawal ภายใต้ workload ว่า fence latency และ cancellation backlog bounded โดย
   opening ไม่หลุดหลัง commit และ risk-reducing path ยังทำงาน
5. คู่ที่ยังไม่รันชุดเต็มคง `Pending Full Validation`; smoke/correctness ไม่เปลี่ยนเป็น Passed แทน

## Requirements coverage

| Requirements | Validation |
|---|---|
| RQ-1–RQ-4 | V-01–V-03, V-08–V-10, V-19, V-23 |
| RQ-5–RQ-6 | V-08–V-10, V-26–V-27 |
| RQ-7–RQ-11, NC-F37-01/03/04 | V-11–V-18 |
| RQ-12, NC-F37-02 | V-11, V-15, V-18, V-20 |
| RQ-13–RQ-16 | V-05–V-07, V-19–V-22 |
| RQ-17–RQ-18 | V-02–V-04, V-09, V-11–V-12, V-25 |
| RQ-19–RQ-21 | V-21–V-24 |
| RQ-22 | V-08, V-26–V-27 |
| RQ-23–RQ-24 | V-03, V-13–V-14, V-23 |
| RQ-25 | V-28 |

## หลักฐานและสถานะ

- เก็บคำสั่ง, revision/commit, environment, diff state, duration และ V-code ใน checkpoint ledger
  เดียวของ F-37 ไม่สร้างรายงานใหม่หลังทุก patch
- ผลเริ่มต้นทุกข้อเป็น `Not Run`; V-27 เป็น `Pending Full Validation` จนรัน release workload ครบ
- `Development Complete` ต้องมี candidate gates ที่บังคับผ่านและไม่มี Critical/High ค้าง
- `Completed` ต้องผ่าน V-01–V-29 รวม V-27 และ owner acceptance ตามหลักฐานของโค้ดสุดท้าย
