# F18 M4 — UI and production composition checkpoint

วันที่ 2026-10-26; branch `feat/f18-wallet-risk-limits`, base40851ee + uncommitted changes.
สถานะ: In Progress. ไม่ใช่ Completed/merge/production activation evidence.

## Implementation

- Shared RiskLimitPanel ใน Paper/Live; server values เท่านั้น ไม่มี optimistic money/latch.
- แยก SET/DECREASE/INCREASE/RESET; increase ใช้ transient TOTP header ไม่เก็บ code
  ใน journal, mutation variables หรือ query keys; reset อธิบาย allowance/ยังถือไม้/งาน stop เดิม.
- ใช้ attemptJournal/useDurableAttempt ร่วมกับ manual orders ไม่เพิ่ม recovery ชุดที่สาม;
  UNKNOWN/lookup404 คง identity, AUTHORIZATION_ONLY retry intent/key เดิมโดยไม่ขอรหัสใหม่.
- Owner/mode scoped queries/journal; request payload คง expected episode/revision เดิม.
  Session cache ถูกยกเลิก/ล้างตาม AccountSession เดิม; unresolved risk journal เก็บต่อ
  ภายใต้ owner/mode เพื่อไม่สูญเสีย authorization-only identity เมื่อ logout/login.
- Effects แยก bounded endpoint, snapshot/watermark key; ไม่ผสม counts กับ pages
  คนละ revision และไม่แปล empty/incomplete เป็น STOPPED.
- Shared Alert มาจาก `references/admin-template/src/components/ui/alert/Alert.tsx`;
  Input/Label/Button/Modal/Badge/Card/Table ใช้ shared template controls เดิม.
- API/Paper main ประกอบ TransactionalRiskPolicy จริงแล้ว แต่ DB admission flags
  ค่าเริ่มต้นยัง false. Compose เพิ่ม isolated risk/order worker และ schema health dependency.
- Test-only browser app มี local database guard, recorded public feed และ production
  API/engine/monitor/stop loops; ไม่มี AllowPolicy หรือ Live executor.

## หลักฐาน

| Check | Result |
|---|---|
| Manual recovery/form/session/journal affected regression | 23 passed,1.88s |
| New risk UI component scenarios | 6 passed,0.989s |
| Full frontend tests | 296 passed,11.75s |
| Frontend types/lint/build | passed; build203modules,0.989s |
| Risk Chromium actual composition | 3 passed,31.4s — unset/set/BUY/breach/active cancel/bounded SELL/reset/resume; lost response/reload; real AUTH commit + API connection termination + same-key no-new-TOTP recovery |
| Effects105targets + actual execution + API actual risk | 10 passed,9.82s |
| M3 replay optimization affected monitor/execution/scheduler | 13 passed,8.98s — transient breach/latch preserved; intermediate projection rewrites removed, final projection and new breaches still durable |
| Backend full mypy after UI composition | 532files passed; extended workload source later533files passed |
| Import contracts | 7 kept,0 broken;279files/1952dependencies |

Browser screenshots อยู่ `ui/`: ไทย light/dark desktop/mobile/tablet และ risk panel อังกฤษ
light desktop/dark tablet. ตรวจภาพแล้วพบ UUID ใน effects ยุบคอลัมน์บน mobile จึงใช้
whitespace-nowrap/scroll pattern เดียวกับ PaperOrderList; screenshot รอบหลังแก้ผ่าน
browser3flowsด้านบน. Financial oracle assertions ที่เพิ่มต่อมารอ affected rerun.
React checklist: ไม่มี inline component definitions, secret persistence, floating-point
money computation หรือ duplicated server state; stable modal close/focus return และ
scope keys; query reads abort on unmount; translated TH/EN messages; no Live orders.

## Failed/partial runs ที่คงไว้

- Browser first attempts: legitimate risk-evidence refresh503 (same-key recovery added
  to test); strict locator matched both alert heading/status; resume budget below
  fixture market notional filter. ไม่เปลี่ยน filters/financial rulesเพื่อให้ผ่าน.
- Backend first full regression interrupted: historical0014 producer test เรียก current
  F18 functionก่อนschemaพร้อม และ secret-canary route inventoryขาด risk404/placeholders.
  ปรับเฉพาะ test harness ให้ current producerรอheadและcanaryตรวจresponsesใหม่ครบ.
- Full regression stalled while the previously reused F16 Redis was paused by another
  worktree's validation. F18 now has its own Redis; no external job/container was stopped.
  First full run is **Failed/Partial**, not Passed. Replacement full run remains pending.

## Remaining

- Focused regression for the two full-run failures; full backend regression on a fresh DB.
- Final generated-contract/static/Compose/Chromium gates and final review checkpoint.
- Integrated workload harness/check/final W1–W4, run one at a time; actual PG commit
  timestamps and successful authoritative cursor commits, no historical evaluated_at shortcut.
- V22/23 bot/Live/notification dependencies remain pending. No Git commit/push/merge.

Times above are tool-measured elapsed times, not an invented total development duration.
