# Reference template dependency remediation — Validation

สถานะ: **Approved — plan/validation และ scope amendments NC-SEC-REF-01/02 อนุมัติ 2026-11-06**
วันที่: 2026-11-06
Requirements: [Approved](requirements.md) · [Plan](plan.md)

## เกณฑ์ตรวจรับ

| รหัส | เกณฑ์ / Requirements | วิธีตรวจและหลักฐานที่ต้องมี | ระยะรัน | ผลปัจจุบัน |
|---|---|---|---|---|
| RV-01 | Scoped lock update — RR-1/6 | Semantic diff ทุก package path เปลี่ยนเฉพาะ Vite 8.2.4, source-map-js 1.2.2, js-yaml 4.3.2, brace-expansion 5.0.11, zod 4.6.6 และ release metadata ที่จำเป็น; ทุก occurrence เป็น target; manifest/root constraints, application lockfiles/source, reference UI/config, workflows/pins คงเดิม; exception registry เพิ่มได้เฉพาะ NC-SEC-REF-02 identity ที่อนุมัติ | Feature | Passed local — ห้า target entries/verified metadata เท่านั้น; manifest/application source/locks/policy เดิม |
| RV-02 | Reproducible installation — RR-1/2 | Node 22 ตรง dependency engines; บันทึก npm/OS; `npm ci --include=dev --include=optional` ใน clean environment ผ่าน, `npm ls --all` ไม่มี invalid/missing; installed targets และ parent resolution ตรง; manifest/lock hashes ไม่เปลี่ยนจาก install/build | Feature | Passed local — clean npm ci + npm ls all; installed targets ตรง; engines 217/217; lock hash คงเดิม |
| RV-03 | Full template inventory — RR-3 | Staged lock hash ตรงต้นฉบับก่อน/หลัง scan; ledger ครบทุก package path (baseline 373 occurrences / 372 unique pairs); OSV all-packages set ตรง expected รวม nested/dev/transitive/optional; candidate counts/diff อธิบายครบ แยก backend supplemental scan ออก; temporary missing-row control ต้องถูกปฏิเสธ | Feature | Passed local — template 373 occurrences/372 unique + 54 backend; coverage 426/426; negative missing-row control ผ่าน |
| RV-04 | Vulnerability remediation — RR-4 | OSV v2.7.0 checksum pin/config เดิมและ severity evaluator เดิม; scan ไม่มี errors/incomplete inventory; 8 target advisories/aliases ไม่เหลือและ versions อยู่นอก affected ranges; unresolved High/Critical/unknown เป็น blocker; บันทึก Medium/Low; baseline feed detection/ช่องว่างระบุจริง ไม่มี suppress/dismiss/new exceptions | Feature | Passed local — five-package candidate High/Critical/unknown 0; known High 8 หาย; Medium 3 ตามจริง; รอบแรก Failed เก็บใน evidence |
| RV-05 | Toolchain build — RR-5 | Template `npm run build` ผ่าน TypeScript และ actual Vite/Tailwind/SVGR pipeline; generated assets โหลดได้; failure ต้องแยก baseline/candidate ไม่แก้ source/config นอกขอบเขต | Feature | Passed local — TypeScript + Vite build; 1,058 modules; 10.93 วินาที |
| RV-06 | Transitive caller compatibility — RR-5 | Temporary source-map round trip + valid indexed sections; js-yaml ผ่าน cosmiconfig resolution ตรวจ mapping/sequence/anchors/merge/omap/dump-load/invalid rejection และ temporary YAML config load; brace-expansion ผ่าน minimatch literal/escaped/nested cases และ zod ผ่าน eslint-plugin-react-hooks resolution รวม valid/invalid collection และ actual ESLint config/plugin/hook fixtures; ระบุ installed versions, fixtures/commands/digest/results; ไม่มี exploit/CPU exhaustion | Feature | Passed local — 10 caller/plugin probes; source-map initial assertion/baseline boundary comparison บันทึกใน evidence |
| RV-07 | Dev/preview + UI — RR-5/6 | ทั้ง dev และ preview บน loopback: HTML/module/JS/CSS/local assets โหลดได้; browser เปิด `/`, `/form-elements`, `/basic-tables`, `/buttons`, `/signin` desktop/mobile ตาม plan, content/interaction ตัวแทนทำงาน ไม่มี page errors/failed local modules; screenshots และผลจริง; ถ้าล้มเทียบ baseline และคง blocker เมื่อยังพิสูจน์ไม่ได้ | Feature | Passed local — dev/preview desktop/mobile 20/20; local assets/interactions/page errors ผ่าน; blocked external Google Fonts แยกตามจริง |
| RV-08 | Safety, architecture, identity — RR-6/7/8 | Diff ไม่มี app/session/DB/trading/financial changes หรือ runtime imports จาก references; ไม่มี Live credentials/orders/infrastructure ใหม่; บันทึก head/base/merge candidate, template/app lock fingerprints, policy/helper/tool/probe digests และ safe evidence; candidate เปลี่ยนตรวจใหม่เฉพาะที่กระทบ | Feature | Passed local — repository lock ตรง scanned/tested fingerprint; safety/app/policy/helper scope คงเดิม; final PR candidate ยังไม่มี |
| RV-09 | Review + required CI — RR-8 | Ready for Code Review แล้ว owner สั่ง review; findings แก้ครบ/ตรวจผลกระทบ; lockfile/docs-only ไม่ต้องถาม refactor; RV-01..08 ผ่านบน final candidate, original required CI และ Security checks ผ่านล่าสุดพร้อม run URLs/SHAs; owner สั่ง merge แยก | Feature | Partial — failed first run 8ccc9e7 เก็บตามจริง; NC-SEC-REF-02 Approved แล้ว; รอ policy/fresh Security และ original CI บน candidate ใหม่ |
| RV-10 | Post-merge closure — RR-8 | หลัง owner สั่ง merge ติดตาม required post-merge CI/Security บน merge SHAจนจบ; actual tree/lock fingerprints ตรง evidence หรือ rerun ส่วนที่เปลี่ยน; native alerts #15/#13/#9/#7/#6 ต้อง read back ว่า fixed/resolved จาก target versions โดยไม่ dismiss; หาก feed lag/new blocker ให้คง Partial และรายงานก่อน Completed | Release | Not Run — Pending Full Validation ที่ post-merge checkpoint; ยังไม่มี PR/merge |

## การเลือกตรวจตามผลกระทบ

- เปลี่ยนเฉพาะ reference dev/toolchain lockfile: clean install + graph verification
  พิสูจน์ metadata/reproducibility; full template scan พิสูจน์ known vulnerability coverage;
  actual build/dev/preview/browser และ small caller probes พิสูจน์ compatibility.
- ไม่ใช้ scanner absence เดี่ยว ๆ แทน patched-version/range proof และไม่ใช้ CI
  application dependency gate แทน full template scan ที่ไม่มีอยู่ใน gate เดิม.
- OSV ใช้ unique package set; occurrence ledger ต้องยืนยัน duplicated/nested paths แยก
  จึงไม่คาดว่า scanner coverage count เท่ากับจำนวน lock entries เสมอ.
- ใช้ existing pinned OSV/install/inventory/evaluator/config ตาม plan โดยไม่แก้ helpers;
  temporary staging/harness ต้องผูกกับ candidate fingerprints และบันทึกวิธีทำซ้ำ.
  ผลจาก PR #48 ยืนยัน gate เดิมได้ แต่ไม่แทน candidate scan/compatibility ของงานนี้.
- ไม่มี production code, transaction, concurrency, idempotency, session หรือเงินเปลี่ยน
  จึงไม่เพิ่ม DB workload/order tests/full application regression local โดยไม่มีผลกระทบ.
  Required CI เดิมยังต้องผ่านบน final candidate; หาก scope ขยายต้องขออนุมัติก่อน
  และประเมิน targeted safety coverage ใหม่ตาม testing §7.
- Build มี type-check อยู่แล้ว; source/UI/lint config ไม่เปลี่ยน. ไม่เพิ่ม test ที่เพียง
  assert versions ซ้ำ lockfile และไม่แก้ lint/type/security exceptions เพื่อให้ผ่าน.
- Browser probes เป็น targeted checks ไม่มี duration/workload threshold ใหม่.
  หากต้องรัน full regression/cross-feature E2E/diagnostic แบบจับเวลา ให้แจ้ง scope,
  สิ่งที่พิสูจน์ และเวลาประมาณก่อนตาม AGENTS/testing §7.

## หลักฐานและผลที่ยอมรับ

ใช้ `evidence/feature-candidate.md` เป็น ledger หลัก เก็บ environment/commands,
package path diff/counts, manifest/lock hashes ก่อนหลัง, tool/config/helper versions/digests,
baseline/candidate findings และ probe/browser results พร้อม screenshots ที่ปลอดภัย
เมื่อจำเป็น. Raw scanner reports, npm credentials, real secrets และ signed URLs
ไม่ commit/upload. บันทึกเวลาที่วัดได้และช่วงประมาณแยกตามมาตรฐาน.

ผลที่ยังไม่มีให้ Not Run; Failed/Partial ต้องคงตามจริง ไม่อ้าง platform ที่ไม่ได้ทดสอบ.
ถ้า OSV baseline feed ไม่ครอบคลุม 8 advisories ต้องระบุช่องว่างและคงเกณฑ์ที่ยังพิสูจน์
ไม่ได้ ไม่ลด coverage/severity policy. หาก native alerts ยังไม่ refresh หลัง merge
ให้คง RV-10 Partial/รอตรวจซ้ำ ไม่เปลี่ยนเป็น Passed เพราะ CI เขียวอย่างเดียว.

หลักฐานเดิมใช้ต่อเมื่อ source/dependency/config/environment/harness ที่พิสูจน์ไม่เปลี่ยน.
Final head/base เปลี่ยนให้เทียบ merge tree และ fingerprints; รันซ้ำเฉพาะส่วนกระทบ
เว้นแต่ required CI ต้องรันใหม่ตามระบบ. Git mutations ต้องมีคำสั่งเจ้าของ;
หลังเปิด PR/merge แล้วติดตาม CI ต่อทันทีจนจบ.

## Checkpoints / จุดหยุด

1. Requirements และ plan/validation Approved ครบแล้ว 2026-11-06; เริ่ม implementation ได้.
2. Implementation ครบให้แจ้ง Ready for Code Review แล้วรอ `review code`;
   ไม่เริ่ม review เอง. Lockfile/docs-only หลัง review/fixes ทำ validation ต่อได้โดยไม่ถาม refactor.
3. ก่อน merge RV-01..09 ต้อง Passed ทั้งหมด; RV-10 เป็น Release/post-merge checkpoint
   คง Pending Full Validation จนถึงกำหนด. ไม่มี Batch/workload ใหม่สำหรับขอบเขตนี้;
   เกณฑ์ชุดรวมของ feature อื่นคงตาม roadmap เดิม.
4. Completed ได้เมื่อ RV-10 ผ่านด้วยและไม่มี blocker; ไม่อ้างว่าการปิดงานนี้รับรอง
   app release, Live Trading หรือการตรวจ fork จริงก่อน fork PR แรก.
5. เจอ scope/spec conflict หรือเกณฑ์เดิมล้ม 3 รอบ ให้หยุดเสนอทางเลือกตาม AGENTS
   ไม่แก้ source/dependency อื่นหรือผ่อนเกณฑ์เอง.

## ผล execution 2026-11-06

[หลักฐาน checkpoint](evidence/feature-candidate.md) และ [safe results](evidence/feature-candidate.json).
รอบแรก NC-SEC-REF-01 บล็อก RV-04; เจ้าของอนุมัติ [scope amendment](evidence/scope-amendment-proposal.md)
แล้วและ candidate ห้า packages ผ่าน RV-01..08 local; [code review APPROVED](evidence/code-review.md).
เจ้าของสั่ง publication แล้ว; required CI ยัง pending จน final SHA/PR checks ผ่าน.
ผล RV-03 เป็น local temporary candidate เท่านั้น ไม่แทน required CI/final merge candidate.

## Scope amendment อนุมัติ 2026-11-06

เจ้าของตอบ approve ให้ขยาย requirements/plan/validation ตาม [ข้อเสนอ](evidence/scope-amendment-proposal.md);
NC-SEC-REF-01 Closed. สถานะใน execution รอบแรกเก็บตามจริงจนมีผลใหม่มาทดแทน
พร้อม fingerprints; RV-04 ต้องผ่านบน 5-package candidate ก่อน install/build.

## CI checkpoint — NC-SEC-REF-02

[ข้อเสนอ exact checksum exception](evidence/checksum-exception-proposal.md) และ
[safe failure record](evidence/ci-checkpoint.json). ยังไม่เปลี่ยน exception registry;
RV-09 Failed บน head 8ccc9e7; push/PR original CI ติดตามต่อจนจบ.

## Approved exception amendment — NC-SEC-REF-02

Owner อนุมัติ exact identity และ requirements/plan/validation amendment แล้ว.
RV-01/08: registry เปลี่ยนได้ 1 entry นี้เท่านั้น (92 → 93), scanner rules/pins/workflow
และ dependency policy เดิม. RV-04 ต้องมี full-template evidence ผูก policy digest ใหม่;
RV-09 ต้องผ่าน existing policy contracts และ fresh secrets/aggregate/required CI บน
final head/base. Reuse install/build/caller/browser เมื่อ lock/source/harness ไม่เปลี่ยน.
First failed run คงเป็น Failed ใน history; ไม่ถือว่าอนุมัติ exception แล้ว CI ผ่านเอง.
