# Code cleanup — Implementation checkpoint

วันที่: 2026-11-06

## Candidate และ preflight

- Branch: `feature/code-cleanup`; base/HEAD ยังเป็น `eeb304e71b95b7e68aeb215e4448e01a6f46215e` พร้อม uncommitted cleanup diff.
- Worktree: `/Users/chainarongjaykeaw/Projects/TiewTrade/Projects/TiewTrade-code-cleanup`.
- [F-17 PR #46](https://github.com/yukasung/tiewtrade/pull/46) ยืนยัน merged ผ่าน GitHub metadata;
  merge SHA `98ff2f840fe08dc46ab5eb9976f17bdf32b062b1` เป็น ancestor ของ base main.
  PR เดิมรายงาน [post-merge CI](https://github.com/yukasung/tiewtrade/actions/runs/42063166018)
  success; ผลนั้นไม่ใช่ CI ของ cleanup candidate.
- Requirements, plan และ validation Approved 2026-11-06 ตามคำสั่งเจ้าของใน conversation.
- Fetch main แล้วตรวจ diff จาก audit `52a00fe`: backend/src, frontend/src, frontend/tests,
  backend/tests/core และ package/lockfiles ของแอปไม่เปลี่ยน; error/journal baseline ใช้ได้.
- Reference scan ครอบ source/tests/scripts/migrations/configuration และ specs:
  เจ็ดรายการไม่พบ caller; `read_monitor_owner` มี historical evidence และ R16 amendment
  อ้างถึง decoder เดิม ซึ่งยังคงไว้เป็น `decode_monitor_owner`.
- Working tree เดิมยังอยู่บน F-17; รักษา AGENTS.md, testing.md, CI-feedback specs และ
  validation-artifacts ที่ค้างอยู่ ไม่มี source changes ของ cleanup ใน worktree เดิม.
  คัดลอกเฉพาะ cleanup specs และเพิ่ม cleanup entry ลง roadmap ของ main โดยไม่ทับ roadmap ทั้งไฟล์.
- ใช้ Node 22.23.4 / npm 10.9.9 และ Python 3.12.15; `npm ci --no-audit --no-fund`
  กับ `uv sync --frozen` สำเร็จใน worktree นี้ ไม่มี lockfile changes.
  ใช้ workflow เจ้าของที่ให้ไว้ใน conversation และ approved cleanup spec;
  ไม่คัดลอก local AGENTS/testing edits ไปทับไฟล์บน main.

## สิ่งที่เปลี่ยน

- ลบเจ็ด declarations ตาม RQ-01; คง Health, backend CatalogPair, API endpoints,
  decode_monitor_owner และ runtime snapshot reader.
- `apiRequest.ts` รวม error mechanics; wrappers ทั้งเจ็ดใช้ local policy เดิม
  และ `send()`/ApiRequestError เดิม; `auth.ts` ไม่มี diff.
- `isRecord.ts` แทน local guard ของสาม journals; valid/storage/identity rules อื่นคงเดิม.
- เพิ่ม public API characterization, risk journal recovery และ object guard boundary tests;
  เปลี่ยน unused callback parameter เป็น `_url` สามจุด.
- ไม่มีการเปลี่ยน SQL ที่มีผู้เรียกใช้งาน; ลบเฉพาะ query ภายใน read_monitor_owner ที่ไม่มี caller.
  ไม่มี migrations, OpenAPI/generated types, dependencies, UI appearance,
  session storage หรือ trading rule changes; ไม่รัน Live/network trading validation.

## ผล local ที่รันจริง

| ชุดตรวจ | ผล | รายละเอียด |
|---|---|---|
| Baseline ก่อน extraction | Passed — 303 tests / 4 files | API policies + manual/protection/risk journals; Vitest 1.09s |
| Baseline test lint และ TypeScript | Passed | ESLint สองไฟล์ใหม่ และ `tsc --noEmit` |
| หลัง extraction + callers | Passed — 409 tests / 13 files | ชุด baseline เดิม + isRecord + 8 component suites; Vitest 4.27s |
| Frontend affected-file ESLint | Passed | 19 affected/new TS/TSX files |
| Frontend unused/type check | Passed | `tsc --noEmit --noUnusedLocals --noUnusedParameters` |
| Backend risk regression | Passed — 73 tests | test_risk_limits.py + test_risk_matching.py; pytest 1.57s |
| Backend affected-file Ruff lint | Passed | สี่ source files ที่ลบ definitions |
| Backend affected-file format | Initial Failed → Passed | records.py ขาด blank line หลังลบ property; format เฉพาะไฟล์แล้วตรวจซ้ำผ่าน อีกสามไฟล์ผ่านรอบแรก |
| Backend targeted mypy | Passed | สี่ source files; no issues |
| Reference/structure check | Passed | ไม่เหลือเจ็ด declarations; backend CatalogPair ยังคงอยู่; helper imports ครบ 7/3 modules |
| Diff whitespace / contract files | Passed | `git diff --check`; OpenAPI/generated types/lockfiles ไม่มี cleanup diff |

Command groups ที่ใช้ (จาก frontend/ หรือ backend/ ตามชื่อ):

```sh
npm run test -- tests/apiRequestPolicies.test.ts tests/manualOrderJournal.test.ts tests/protectionJournal.test.ts tests/riskLimitJournal.test.ts
npm run test -- tests/apiRequestPolicies.test.ts tests/manualOrderJournal.test.ts tests/protectionJournal.test.ts tests/riskLimitJournal.test.ts tests/isRecord.test.ts tests/ApiKeyPanel.test.tsx tests/TradingAccountPanel.test.tsx tests/PaperWalletPanel.test.tsx tests/ManualOrderForm.test.tsx tests/ManualOrderSession.test.tsx tests/PaperOrderList.test.tsx tests/RiskLimitPanel.test.tsx tests/KillSwitchControls.test.tsx
./node_modules/.bin/tsc --noEmit --noUnusedLocals --noUnusedParameters
uv run pytest tests/core/test_risk_limits.py tests/core/test_risk_matching.py
uv run mypy src/tiewtrade/infra/risk_limits/storage.py src/tiewtrade/infra/auth/sessions.py src/tiewtrade/infra/api_keys/records.py src/tiewtrade/core/risk_limits.py
```

ESLint ตรวจ apiRequest/isRecord, เจ็ด API modules, สาม journal modules, api.ts,
marketCatalog.ts, สาม test files ใหม่ และ ApiKeyPanel/RiskLimitPanel tests.
Ruff check/format ใช้สี่ backend paths เดียวกับ targeted mypy.
ไม่รัน runtime tests ซ้ำหลังแก้ blank line อย่างเดียว เพราะ behavior ไม่เปลี่ยน.

Characterization tests สองไฟล์นี้ไม่ได้แก้ expected results ระหว่าง baseline กับหลัง extraction:

- `frontend/tests/apiRequestPolicies.test.ts`: `67b4abc1144dd5bf27a35012e07a834f4e987956fb86588d405b8dd04aa41595`
- `frontend/tests/riskLimitJournal.test.ts`: `9386c37b4ec6b0f60fbe85cedefded2726039183b741b988522a105225fa9ae6`

## Checkpoint และรายการค้าง

แจ้ง **Ready for Code Review** แล้ว; เจ้าของสั่ง “เริ่มทำ” ในขั้นถัดไป จึงดำเนิน code review
วันที่ 2026-11-06 บน uncommitted candidate เดิม. ผล: ไม่พบ actionable findings ในขอบเขต diff.

- เทียบ error wrappers ทั้งเจ็ดกับ base: allowlists/fallbacks, 403/429 precedence,
  DOMException identity และ Retry-After deadline คงเดิม; sender/signatures/envelopes ไม่เปลี่ยน.
- Journal diff เปลี่ยนเฉพาะ object guard; validators, owner/mode/key isolation,
  storage prefix และ fail-closed/readback/conditional-clear mechanics คงเดิม.
- Backend diff เป็น approved deletions เท่านั้น; decoder/runtime snapshot reader และ
  PostgreSQL session implementation ยังคงอยู่. ไม่เพิ่ม process-local session/business state;
  module-local policy ไม่มีข้อมูลผู้ใช้ และ journal ยังคงเป็น client recovery intent.
- ตรวจ characterization/recovery tests: expected policies เป็น fixtures อิสระ,
  เรียก public APIs ผ่าน send จริงโดย stub fetch; ครอบคลุม secret sanitization,
  request count, abort, deadlines และ recovery identity โดยไม่มี Live request จริง.
- ไม่แก้ source/tests ในรอบ review จึงใช้ผล 409 frontend / 73 backend และ static checks เดิมต่อ;
  แก้เฉพาะสถานะหลักฐานและอธิบายการลบ unused SQL ให้แม่นยำ.

## Post-review refactor และ final local validation — 2026-11-06

เจ้าของสั่ง `refactor the code` แล้ว. ปรับเฉพาะการเลือก error code ใน `apiRequest.ts`:
เริ่มด้วย fallback แล้วเข้า allowlist/status mapping เฉพาะเมื่อเป็น ApiRequestError;
ลดการผสม `&&` กับ `??` และ conditional expression โดยคงลำดับ/ผลลัพธ์เดิม.
ไม่เพิ่ม helper, policy, request, state หรือ validation rule. ตรวจส่วนที่ปรับเทียบ approved
algorithm แล้วไม่พบ finding ใหม่; ส่วนอื่นไม่จำเป็นต้อง refactor เพิ่มในขอบเขตนี้.

ก่อนรันชุดเต็มแจ้งขอบเขตและประมาณ 5–15 นาทีแล้ว. ผลจริงบน candidate หลัง refactor:

| ชุดตรวจ | ผล |
|---|---|
| `npm run test` | Passed — 662 tests / 39 files; Vitest 41.81s รวม API-contract positive/negative cases และทุก characterization/journal/component test |
| `npm run lint` | Passed — full frontend ESLint |
| `./node_modules/.bin/tsc --noEmit --noUnusedLocals --noUnusedParameters` | Passed — full TypeScript check พร้อม unused checks; ครอบคลุม `npm run typecheck` ซึ่งคือ `tsc --noEmit` จึงไม่รันคำสั่งย่อยซ้ำ |
| `npm run build` | Passed — 221 modules; Vite 1.29s; มี warning JS chunk 631.14 kB เกิน 500 kB (gzip 195.78 kB); ไม่เปลี่ยน bundling configuration นอกขอบเขต cleanup |
| `uv run ruff check .` | Passed — full backend |
| `uv run ruff format --check .` | Passed — 712 files already formatted |
| `uv run mypy` | Passed — 643 source files |
| `uv run lint-imports` | Passed — 7 contracts kept / 0 broken; analyzed 297 files, 2140 dependencies |
| Backend risk regression | Reused Passed — 73 tests; backend/tests/dependencies/environment ไม่เปลี่ยนจากรอบ implementation |
| Final diff/reference checks | Passed — `git diff --check`; removed declarations ไม่พบใน source/tests; contract/generated types/lockfiles ไม่มี diff |

ยังไม่มี commit: base/HEAD คง `eeb304e71b95b7e68aeb215e4448e01a6f46215e`.
Fingerprint ของ source/test candidate ทั้ง 23 changed/untracked files (เรียง path แล้ว hash
`path + NUL + content + NUL` ด้วย SHA-256):
`b416ebb752dde7fecb19fd764991a139dbe61fca791d769ae64ee09e96fa943e`.
SHA-256 ของ `frontend/src/apiRequest.ts` หลัง refactor:
`901ed9c981dd98a6d705e1380c02046ccc3d39e664bdac2915dc64f9b0e7695a`.

Local validation ผ่านครบ; required CI ต้องตรวจบน cleanup SHA เมื่อมี PR.
ไม่ได้รัน Playwright/DB integration ซ้ำใน local รอบนี้ตาม approved validation §4;
ยังต้องผ่าน required CI ของงานเหล่านั้นก่อน merge. ไม่ส่ง Live orders.

## สถานะหลัง final local validation

- V-01..V-09: มีหลักฐาน local ตามตารางและ reference checks.
- V-10: Passed — full frontend/backend static checks และ production build ตามตาราง.
- V-11: Passed — full frontend regression รวม API-contract gate; contracts ไม่มี diff.
- V-12: Passed — owner-directed review และตรวจผลกระทบของ authorized refactor ไม่พบ actionable findings.
- V-13/V-14: Not Run — ไม่มี commit/push/PR/merge ของ cleanup และยังไม่มี required CI บน cleanup SHA.
- F-17/F-18/F-19 Batch/Release/dependency gates ไม่ถูกเปลี่ยนโดย checkpoint นี้.

ขั้นถัดไป: รอเจ้าของสั่ง commit/push/เปิด PR ตามกฎ Git; เมื่อเปิด PR แล้วติดตาม
required CI บน SHA ล่าสุดต่อทันที. Merge ต้องมีคำสั่งแยกและผ่านทุก Feature gate.
ยังไม่เรียกงาน Completed หรือพร้อม merge จากผล local อย่างเดียว.

## Authorized Git checkpoint

Owner approved commit, push and PR creation after the final local checkpoint.
Pre-commit fetch confirms origin/main remains eeb304e71b95b7e68aeb215e4448e01a6f46215e;
there are no base changes invalidating local evidence. The results above are the
pre-commit snapshot. Track CI and Security on the latest PR candidate and report
its SHA and run URLs in the conversation, without a documentation-only CI loop.
Merge remains unauthorized; V-13/V-14 remain Not Run until actual results exist.
