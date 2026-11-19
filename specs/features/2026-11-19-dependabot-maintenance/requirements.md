# Dependabot maintenance — Requirements

สถานะ: **Approved — เจ้าของอนุมัติ 2026-11-19**
วันที่: 2026-11-19
Branch: `spec/dependabot-maintenance`
Baseline: `abd3fe15bc96488897c3fe5e4d813d575dfb4f4c`

## ทำไมต้องมี

หลังล้าง remote branches ที่ปิดงานแล้ว ยังมี Dependabot PR #50/#55/#56/#57 เปิดอยู่
เจ้าของสั่งเริ่มจัดทำ spec สำหรับ updates ชุดนี้. รุ่นเหล่านี้ยังไม่อยู่ใน main;
requirements เดิมอนุมัติ exact targets คนละชุด จึงไม่ใช้การอนุมัติเก่ารับรองงานใหม่นี้.

ทั้งสี่ PR ตามหลัง main. #50/#55/#57 มี checks เดิมผ่าน; #56 มี E2E ล้มที่
`frontend/e2e/trading-account.spec.ts:90:48` (ข้อความใน DOM ไม่ตรง). ยังไม่มีหลักฐาน
ว่า Vite เป็นสาเหตุ และผลเดิมไม่ใช่ acceptance ของ candidate ใหม่บน latest main.
[PR baseline และ diff ที่ตรวจ](evidence/pr-baseline.json).

## ขอบเขตและรุ่นเป้าหมาย

รวมเป็นงาน maintenance เดียว/หนึ่ง spec/หนึ่ง branch บน latest main เพื่อให้ dependency
ที่เกี่ยวข้อง resolve ร่วมกันและมี final candidate เดียว. งานนี้เป็นการอัปเดต toolchain;
ไม่อ้างว่ารุ่นใหม่ปิด advisory ใดเพียงจากเลขรุ่นหรือป้าย dev dependency.

| ที่ใช้ | Package/family | Main | Target | PR |
|---|---|---|---|---|
| Application frontend | `vite` | 6.4.4 | **6.4.6** | [#56](https://github.com/yukasung/tiewtrade/pull/56) |
| Application frontend | `vitest` และ installed `@vitest/*` family ที่เกี่ยวข้อง | 4.1.11 | **4.1.12** | [#55](https://github.com/yukasung/tiewtrade/pull/55) |
| Admin reference | `brace-expansion` | 5.0.11 | **5.0.13** | [#50](https://github.com/yukasung/tiewtrade/pull/50) |
| Admin reference | `@humanfs/node` | 0.16.6 | **0.16.8** | [#57](https://github.com/yukasung/tiewtrade/pull/57) |

Application family ที่พบใน lock: `vitest`, `@vitest/expect`, `@vitest/mocker`,
`@vitest/pretty-format`, `@vitest/runner`, `@vitest/snapshot`, `@vitest/spy`,
`@vitest/utils`; ต้องใช้ target 4.1.12 ให้สัมพันธ์กันตาม published dependencies.
ไม่เพิ่ม optional peer packages ที่ยังไม่ได้ใช้เพียงเพราะมี peer entry.

Published `@humanfs/node@0.16.8` ต้องใช้ `@humanfs/core ^0.19.2` และ
`@humanfs/types ^0.15.0`; อนุมัติ scope ที่ขอจึงรวม core **0.19.1→0.19.2** และ
เพิ่ม types **0.15.0**. `@humanwhocodes/retry` ที่ satisfy range เดิมไม่ต้องอัปเดตตาม.

PR #50/#57 ยังเพิ่ม nested entries ใต้ `@tailwindcss/oxide-wasm32-wasi`:
`@emnapi/core@1.11.1`, `@emnapi/runtime@1.11.1`, `@emnapi/wasi-threads@1.2.2`,
`@napi-rs/wasm-runtime@1.1.4`, `@tybys/wasm-util@0.10.2`, `tslib@2.8.1`.
Registry ของ parent 4.3.3 ประกาศ dependency edges เหล่านี้จริง แต่ไม่ได้พิสูจน์ว่าต้อง
เพิ่ม nested copies ทั้งหกใน candidate. ขอ scope แบบมีเงื่อนไข: เพิ่มได้เฉพาะรายการที่
พิสูจน์ด้วย graph/resolution ว่าจำเป็นต่อ frozen/portable lock ที่ถูกต้อง ภายใน edges/versions
ข้างต้น; คง optional/platform semantics และไม่เพิ่ม parent version. ห้ามคัดลอก extras
จาก PR โดยถือว่าผ่านจากชื่อ PR. หากไม่จำเป็นให้คง graph เดิม; หากต้องเปลี่ยน package
นอกขอบเขตที่อธิบายนี้ ให้บันทึกเหตุผล/ผลกระทบและขอ scope amendment ก่อนแก้ส่วนนั้น.

ยืนยัน published metadata ของ targets/family/closure จาก npm registry วันที่ 2026-11-19:
[metadata, engines, source URLs, integrity และ baseline hashes](evidence/registry-metadata.json).
Targets หลักรองรับ Node 22; ข้อมูล registry นี้ไม่ใช่หลักฐานว่าดาวน์โหลด/ติดตั้ง tarballs
หรือพิสูจน์ compatibility/absence of vulnerabilities แล้ว.

## ข้อกำหนด

| รหัส | ข้อกำหนด | ที่มา |
|---|---|---|
| DM-01 | ใช้ exact targets/necessary closure ตามข้างต้น ไม่ข้าม major ของ React/Vite/Vitest/Node/npm ไม่ใช้ broad update/audit-fix และไม่ย้าย dependencies ของ reference เข้า application | ขอบเขตที่เจ้าของให้จัดทำ; tech-stack |
| DM-02 | คง manifest ranges ปัจจุบันเมื่อรองรับ targets แล้ว: application `vite ^6.0.3`, `vitest ^4.1.11` รองรับรุ่นเป้าหมาย จึงไม่ยก range ตาม PR โดยไม่มีเหตุจำเป็น. Lock root/manifest ต้องตรงกัน; package ที่ไม่เกี่ยวข้องคง version/integrity/source เดิม และตัด funding-only churn ที่ไม่จำเป็น | reuse/minimal diff; approved dependency-remediation patterns |
| DM-03 | Install แบบ clean/frozen บน Node 22/npm ที่ pin ใน plan ได้; lock graph, artifact integrity และ every occurrence ต้องสอดคล้อง. อธิบายทุก semantic package/edge delta รวม dev/transitive/optional/nested ไม่ใช้แค่ชื่อ packages ที่ bump | testing; database-free toolchain reproducibility |
| DM-04 | คง application LP04 source: `picomatch file:./vendor/picomatch-4.0.7-lp04.tgz`, override `$picomatch`, archive/parser/provenance hashes, upstream name/version/license และ trusted-source manifest ตาม main. ไม่ fallback upstream parser/registry bytes หรือเปลี่ยน policy/exception ให้ update ผ่าน | LP04 approved source policy; PR #77/#79 |
| DM-05 | Reassess actual Vite/Vitest/tinyglobby/fdir caller graph/options และ LP04 matching restrictions เมื่อ callers เปลี่ยน. Verify installed bytes ทุก occurrence และ actual caller/toolchain behavior บน candidate ใหม่; reuse parser-byte proofs ที่ไม่เปลี่ยนได้ แต่ไม่ใช้ old-caller result แทน new-caller proof. Unsafe/unknown opt-out or compatibility ที่พิสูจน์ไม่ได้เป็น blocker ไม่ถือว่า advisory withdrawal ยกเลิก technical risk | existing LP04 retirement/reassessment conditions |
| DM-06 | App ต้องผ่าน scoped frontend lint/types/tests, API contract, build/dev/preview asset behavior และ relevant trading UI regressions บน actual candidate. Template install/build/dev/preview/caller behavior ตามผลกระทบต้องพิสูจน์แยก โดยไม่แก้ template UI/source หรือ styles เพื่อกลบ dependency incompatibility | frontend/admin template; testing |
| DM-07 | ใช้ scanner pins/policy เดิมกับ application lockfiles จริงครบทั้ง backend+frontend พร้อม LP04 identity และ complete template lock inventory แยกตามวิธีที่ plan อนุมัติ. ห้าม fake registry lock, skip dev/optional/nested, ขยาย permanent CI inventory หรือลด coverage. High/Critical/Unknown ที่ unresolved บล็อก publication; Medium/Low รายงานตามจริง. ไม่มี exception ใหม่ใน scope นี้ | security requirements and existing reference sidecar pattern |
| DM-08 | คงเงิน/quantity/order/balance/position/risk/idempotency/concurrency, DB schema/RLS, PostgreSQL sessions/stateless deployment, authorization deadline 500ms และ protection SLA 1s เดิม. Validation ใช้ owned fixtures/FakeVenue/Paper เท่านั้น ไม่ใช้ owner data/credentials หรือส่ง Live orders | AGENTS; architecture/security/trading-safety |
| DM-09 | ไม่แก้ assertions, timeout, CI selection/required checks หรือ source app ที่ไม่เกี่ยวข้องเพื่อให้ packages ผ่าน. หากพบ harness วัดผิด แก้ได้ตาม engineering delegation หลังบันทึกหลักฐานก่อนแก้ โดยคง criterion/risk proof และ failure history; หากเป็น product/security/semantic gap ให้หยุดขอคำตัดสิน | continuous workflow and delegated engineering authority |
| DM-10 | ก่อน merge ต้องผ่าน review, applicable Feature validation และ required CI บน final candidate ล่าสุด; ตามด้วย postmerge CI/Security และ exact SHA evidence. Old PR green/failed states ไม่แทน final proof. ตรวจ final expected head/base และรักษาผล Failed/Partial/Not Run เดิม | testing; AGENTS Git |
| DM-11 | จัดการ PR เดิมเป็น superseded/merged หลังตรวจว่าครบทุก intended update และ candidate ผ่านแล้ว; ไม่ทิ้ง active work หรือปลอม merge history เพื่อให้ลบ branches ได้. การลบ local/remote refs ยังใช้กฎ merged/pushed/CI-green และสำรองประวัติเดิม | branch cleanup and repository Git rules |
| DM-12 | ไม่มี workload/endurance/capacity/Live campaign ใหม่จาก dependency maintenance นี้. Reuse financial/Paper evidence ที่ source/contracts/harness ไม่เปลี่ยน; F-17 และ feature อื่นคง Pending Full Validation ตามจริง ไม่รับรอง release/opening จาก task นี้ | testing Feature/Batch/Release separation |

## กฎความปลอดภัยและขอบเขตสถาปัตยกรรม

ยึด [architecture](../../standards/architecture.md), [frontend](../../standards/frontend.md),
[security](../../standards/security.md), [trading safety](../../standards/trading-safety.md)
และ [testing](../../standards/testing.md). ไม่เพิ่ม session/cache infrastructure,
บริการเสียเงิน, scanner ใหม่, deployments หรือ product/business rules.
Application React 18/Vite 6 และ reference React 19/Vite 8 ยังคงแยกกัน.

เกณฑ์ของ maintenance ที่ต้องพิสูจน์ก่อน publication/merge จัดเป็น **Feature** ในขั้น
validation; postmerge เป็น checkpoint ปิด publication ตาม workflow เดิม. ไม่สร้าง
Batch/Release workload ใหม่หรือย้าย correctness/security ไปตรวจภายหลัง.

## สิ่งเดิมที่ plan ต้องพิจารณาใช้ซ้ำ

- `frontend/package.json`, `frontend/package-lock.json`, `vite.config.ts`, `vitest.config.ts`
  และ existing frontend tests/E2E/contract/build commands.
- `references/admin-template/package-lock.json` และ existing scripts/reference remediation
  ใน `../2026-11-06-security-reference-dependency-remediation/`.
- `frontend/vendor/`, `tools/security/trusted_sources.py`, `withdrawal.py`, `scan.py`,
  existing source/policy negative tests และ complete-inventory scanner behavior.
- Existing LP04 finite caller/artifact verification receipts และ retained harness archive:
  plan ต้องระบุ input/source paths ที่ใช้จริงและทำ acceptance evidence ให้ตรวจซ้ำได้
  โดยไม่พึ่ง private absolute paths หรือ raw dumps ใน CI.
- `.github/workflows/ci.yml`, `.github/workflows/security.yml` คง required checks/pins;
  ไม่มี source refactor หรือ test/helper implementation ในขั้น requirements.

## ยังไม่ชัด / จุดหยุด / ขั้นตอนถัดไป

- ไม่มี business/trading decision ใหม่หรือ relevant Needs Clarification ที่ต้องเดา.
  การมี package metadata/old green CI ไม่เท่ากับ compatibility/security acceptance.
- การอนุมัติที่ขอคือ targets, bounded transitive scope และ invariants ในเอกสารฉบับนี้.
  หาก exact package target ใช้กับ stack เดิมไม่ได้ ให้เสนอ scope amendment ไม่เปลี่ยน
  target/major/LP04 bytes/threshold เอง.
- **ขั้นถัดไปหลังเจ้าของอนุมัติ requirements เท่านั้น:** จัดทำ `plan.md` และ `validation.md`
  เพื่อขออนุมัติรอบที่สอง แล้วจึงเริ่ม resolve/install/edit code/lockfiles.
  ยังไม่ถือว่าคำสั่งเริ่มจัดทำ spec อนุมัติเนื้อหาฉบับนี้หรือ implementation แล้ว.

## บันทึกอนุมัติ

2026-11-19 เจ้าของตอบ “เริ่มทำ” ต่อคำขออนุมัติ requirements ฉบับนี้.
บันทึกเป็นการอนุมัติ scope/targets/invariants ข้างต้น เพื่อจัดทำ plan และ validation;
ยังต้องอนุมัติเอกสารทั้งสองก่อน implementation ตาม workflow.
