# Security CI — Plan

สถานะ: **Approved — เจ้าของสั่ง “แก้ไข” implementation blocker ตามแผนนี้ 2026-11-05**
วันที่: 2026-11-05
Requirements: [Approved 2026-11-05](requirements.md)
Branch: `feature/security-ci-hardening`; ฐาน `c8d8ca78971fce3d98f624e0c35128195168d831`

## 1. แนวทางและขอบเขต

เพิ่ม `.github/workflows/security.yml` แยกจาก CI เดิม ใช้ standard Ubuntu GitHub-hosted
runners; เปิด native secret scanning/push protection และ Dependabot alerts/security updates.
ใช้ CodeQL แบบ **advanced setup** เท่านั้น ไม่เปิด default setup ซ้ำ.
การบังคับ merge ใช้ผล scanner ของ candidate ผ่าน required job `Security / gate`;
ไม่ใช้จำนวน open alerts บน main หรือผลเฉพาะ dependency diff เป็นตัวตัดสิน.

เลือกเครื่องมือดังนี้:

| งาน | เครื่องมือ / ขอบเขต | ผลที่ gate อ่าน |
|---|---|---|
| Secrets | Gitleaks CLI v8.30.1, default rules รวม generic API key/private key; เพิ่ม contextual rule สำหรับค่า sealing key และ venue credentials ของโปรเจกต์ตามชื่อ config จริง | JSON ที่ redact แล้ว + occurrence identity; ไม่ใช้ค่า secret เป็น exception key |
| Dependencies | OSV-Scanner v2.7.0 อ่าน `backend/uv.lock` และ `frontend/package-lock.json` ทั้งชุด รวม dev/transitive/optional entries ที่ lockfiles ระบุ | JSON แบบ all-packages, advisory IDs และ `groups[].max_severity` |
| SAST | CodeQL Action v4 ที่ตรึง commit SHA และ CLI bundle v2.27.4; matrix `python`, `javascript-typescript`, `actions`, build-mode none และ security-extended query suite ที่อยู่ใน bundle | SARIF ของ candidate ก่อนแปลงเป็นผลที่ปลอดภัยต่อการเผยแพร่ |
| Policy / aggregation | Python 3.12 standard library ใน `tools/security/` | manifest ที่ผูก SHA, tool/config versions, coverage และผล policy ทุก component |

เครื่องมือใหม่เป็นเครื่องมือ CI ไม่ใช่ dependencies ของ application.
Gitleaks ยังมี security maintenance แต่ upstream หยุดรับ features ใหม่; pin รุ่นและติดตาม
security updates ใน maintenance ของงานนี้ ไม่เปลี่ยน scanner อัตโนมัติ.
บันทึก full SHA ของ Actions และ release checksums ของ CLI/bundle ใน tool manifest;
ตรวจ artifact/checksum ก่อนรัน ไม่มี `latest` หรือ mutable major tag ใน workflow ที่เพิ่ม.
การเปลี่ยนรุ่นหลังอนุมัติ plan ต้องตรวจ compatibility/schema และบันทึกเหตุผลก่อนใช้.

## 2. ของเดิมที่จะใช้ซ้ำ

| ของเดิม | การใช้ซ้ำ |
|---|---|
| `.github/workflows/ci.yml` | คง 6 checks, PostgreSQL integration, browser และ container evidence เดิม; อ่านชื่อจริงจาก check runs ก่อนแก้ required settings |
| `.github/workflows/venue-contract.yml` | คงงานสาธารณะของ venue แยกจาก merge gate ตามขอบเขตเดิม |
| `backend/uv.lock`, `frontend/package-lock.json` | เป็น inventory ของ dependencies; ไม่ติดตั้ง application เพื่อสแกน |
| `backend/tests/gates/test_gates.py`, `backend/tests/venue_contract/test_workflow.py` | ใช้แนวทางทดสอบ input ที่ควรผ่าน/ควรถูกปฏิเสธและตรวจ workflow contract; ไม่คัดลอก business logic |
| `backend/tests/api/test_no_secrets.py`, `backend/tests/api/test_auth_flow.py` | หลักฐานเดิมเรื่อง log/response, auth และ CSRF; rerun เมื่อ diff กระทบ harness/config เท่านั้น |
| `backend/tests/infra/auth/test_session_rules.py`, `backend/tests/infra/db/test_user_isolation.py` | หลักฐาน PostgreSQL session/RLS; ไม่เปลี่ยน persistence หรือเพิ่ม cache/session service |
| `backend/tests/gates/test_paper_isolation.py`, `backend/tests/test_api_key_safety.py` | คง safety gates เดิมและผล required CI บน candidate จริง |

ไม่พบ adapter สำหรับผล Gitleaks/OSV/SARIF หรือ workflow security gate ใน repo เดิม.
เขียนเฉพาะ adapter/policy ที่ขาด ไม่สร้าง vulnerability database หรือคำนวณ CVSS vector เอง.

## 3. Workflow และสิทธิ์

- Trigger: `pull_request` ไป `main` (รวม synchronize/reopened), `push` บน `main`,
  `schedule` รายวัน `17 3 * * *` UTC (10:17 น. ไทย), และ `workflow_dispatch`.
  ไม่ใช้ paths filter ที่ทำให้ required check หาย และไม่ใช้ `pull_request_target`/`workflow_run`.
- PR ตรวจ synthetic merge commit; บันทึก head SHA, base SHA และ merge SHA.
  ตรวจ checkout/metadata ที่ต้นและท้าย run; ผลต้องตรง candidate ล่าสุดที่ GitHub API รายงาน.
  ใช้ strict/up-to-date protection เดิมป้องกัน base เคลื่อนหลัง scan.
  push/schedule ตรวจ SHA ของ main ที่ checkout; manual run บันทึก ref/SHA ตามจริง.
- Jobs: `policy-tests`, `secrets`, `dependencies`, `codeql` (3 languages), และ `gate`.
  ตั้ง `gate` เป็น `if: always()` และตรวจว่า jobs ทุกตัว success พร้อมผลครบตรง SHA;
  skipped/cancelled/timed out/missing/malformed report ต้องไม่ให้ gate success.
  แต่ละ component ทำ policy decision ของตนเองด้วย ไม่รอ aggregate แก้ผล scanner ล้ม.
- `permissions: contents: read` เป็นค่าเริ่มต้น; เพิ่ม `pull-requests: read` เฉพาะ job
  ที่ยืนยัน candidate. ไม่มี repository secrets, PAT, exchange credential หรือ write token
  ใน jobs ของ PR; checkout ใช้ `persist-credentials: false`.
- CodeQL ใช้ `analyze` แบบ `upload: never`, `upload-database: false`;
  ไม่ upload raw SARIF/CodeQL database เพราะอาจมี source snippets หรือค่า secret.
  ผล SAST แสดงใน checks/summary แบบปิดค่า ไม่เปิด Code scanning dashboard upload ในขอบเขตนี้.
  การใช้ CodeQL advanced workflow ยังตรวจโค้ดตาม RQ-5 ครบ; gate ไม่พึ่ง dashboard.
- ไม่รัน package lifecycle/build scripts จาก candidate: OSV อ่าน lockfiles เท่านั้น;
  CodeQL ใช้ no-build extraction; ไม่ทำ `npm install`, `pip install` หรือ imports ของ app.
  helper/tests ของงานนี้รันด้วย read token และไม่มี secrets; ไม่ execute เนื้อหาจาก report.
- แยก tool/policy directory กับ candidate scan directory; scan config ระบุ explicit path.
  ไม่ใช้ suppression/config ที่ scanner ค้นพบจาก candidate โดยปริยาย;
  การแก้ gate/config/exception registry ต้องมี owner review ผูกกับ diff/SHA ก่อน merge
  ตาม workflow เดิม ไม่เพิ่มจำนวนผู้ reviewer หรือเปลี่ยน branch review settings.
- Concurrency แยก PR/ref; cancel run เก่าได้ แต่ candidate ใหม่ต้องได้ผลครบของตนเอง.
  Timeout เป็น failure ไม่ใช่ข้อยกเว้น; plan เริ่ม 15 นาทีสำหรับ secret/dependency,
  30 นาทีต่อ CodeQL language, 5 นาทีสำหรับ gate; ทบทวนเมื่อมีหลักฐานจริงว่าไม่พอ.

### 3.1 วิธีตรวจ PR permissions ทดแทน fork run สำหรับรอบนี้

สถานะ: **Approved — เจ้าของอนุมัติข้อเสนอและให้ปรับเอกสาร 2026-11-05**
อ้างอิง [RQ-9 amendment](requirements.md) และ
[ข้อเสนอที่อนุมัติ/ข้อจำกัด](evidence/fork-validation-amendment-proposal.md).

1. ตรวจ workflow ทุก job และ reusable/action call ที่เกี่ยวข้อง: ใช้ pull_request,
   ไม่มี privileged event, secrets reference/inherit, environment secrets, write permission,
   persisted checkout credential หรือ self-hosted runner; actions ใช้ full SHA
   และตรวจ repository workflow permissions จาก API อีกครั้ง
2. ใช้ PR #48 ตรวจ effective GITHUB_TOKEN permissions ของทุก job จาก job setup logs;
   เก็บเฉพาะชื่อ permission/ระดับและ job/run/SHA ไม่เก็บ token ทุก scope ต้อง read/none
   ตาม job ไม่มี write หากพิสูจน์ไม่ได้ให้คง Partial
3. ใน disposable validation PR ตาม V-16 ใช้ Python/JS entrypoint และ npm lifecycle script
   ที่จะสร้าง marker เมื่อรัน ตรวจใน harness รอบ scanners ว่า marker ไม่เกิดทั้งก่อน/หลัง
   ไม่ใช้ credential จริง ไม่อ้างว่า CodeQL ไม่ประมวลผล source หรือไม่มี candidate code รัน:
   policy tests และ helpers ยังรันด้วย read token ตาม workflow ปกติ
4. คง pins, ephemeral hosted runners, read-only PR token, ไม่มี repository secrets,
   ไม่มี cache/raw report/database upload; ไม่เพิ่ม repository secret-sentinel
   หรือทดสอบ token ด้วยคำขอเขียน การเพิ่ม harness/fixtures ต้องผ่าน targeted checks/review
5. ใช้ GitHub platform contract ตามลิงก์ในข้อเสนอประกอบหลักฐาน พร้อมบันทึกว่า
   fork execution/approval และ cross-repository API/ref/artifact behavior ยัง Not Run
   same-repo run และ marker probes ไม่เทียบเท่า fork test
6. ก่อนรับ merge ของ PR จาก fork ครั้งแรก ต้องตรวจ fork run จริงบน head/base นั้น
   รวม approval policy, candidate API/ref resolution, artifacts, ทุก scanner และ gate
   ถ้าไม่ได้รัน/ล้ม ให้คง PR นั้นไม่พร้อม merge ไม่ใช้ผล same-repo ปิดรายการนี้
   เมื่อ events/permissions/secrets/runner หรือ platform policy เปลี่ยนต้องประเมินใหม่

## 4. Secrets และการปิด finding

1. ครั้งแรกสแกน Git history ของ refs ที่ fetch ได้จาก origin ทั้งหมด พร้อมรายการ refs/SHAs;
   shallow/incomplete history ต้องไม่ผ่านเกณฑ์ first scan. ไม่อ้างว่าครอบคลุม deleted refs,
   fork ที่ไม่ได้ fetch หรือ unreachable objects.
2. ทุก PR สแกนประวัติที่ reachable จาก candidate รวม commit ที่เพิ่มแล้วลบ secret ใน PR
   และสแกน tracked tree ปัจจุบันด้วย; push/schedule ตรวจ main แบบเดียวกัน.
   ไม่สแกน `.git`, tool downloads หรือรายงานที่ตัว scanner สร้างเป็น working-tree input.
3. ใช้ `--redact=100`, ปิด inline `gitleaks:allow`, ระบุ ignore file ว่างและไม่ใช้ baseline.
   rule set และ contextual rules มี synthetic positive/negative cases; ไม่มีคำรับรองว่า
   regex ตรวจ secret ทุกแบบได้ โดยเฉพาะค่าที่ถูกเข้ารหัส/แยกชิ้น/ไม่มีบริบท.
4. stdout/stderr/raw reports อยู่ใน runner temp แบบจำกัดสิทธิ์ ไม่ echo หรือ upload;
   ขั้นเผยแพร่สร้างข้อมูลจาก allowlist fields เท่านั้น: rule ID, commit, relative path,
   line, occurrence identity และผล triage. ทดสอบ sentinel ว่าไม่หลุดแม้ tool ล้มเหลว.
5. `exceptions.json` บันทึกเฉพาะรายการที่เจ้าของอนุมัติ: kind, scanner/rule,
   exact occurrence (commit/path/line/finding identity), resolution, เหตุผล และหลักฐานปิดค่า.
   `remediated/revoked` ต้องมีหลักฐานว่า credential เดิมใช้ไม่ได้และคำรับรองเจ้าของ.
   ไม่ยกเว้นด้วยค่า secret, directory, regex กว้าง หรือ fingerprint แบบไม่ผูก commit.
6. Tree finding จะพ้น blocker ได้ก็ต่อเมื่อพิสูจน์ mapping ไปยัง occurrence เดิมที่อนุมัติ;
   mapping ไม่ได้ให้ Needs Triage. การเพิ่ม occurrence ใน commit ใหม่ต้องบล็อกใหม่.
   fixture/false-positive registry ก็ต้องตรวจการเปลี่ยนเนื้อหาเพื่อไม่ให้ exception เดิม
   กลบ credential ใหม่ที่มาแทนบรรทัดเดิม.
7. พบ secret ที่อาจเป็นของจริง: หยุดเฉพาะส่วนที่ต้องตัดสิน remediation, รายงานปิดค่า;
   ไม่ทดสอบ credential/rotate/revoke/rewrite history หรือปิด alert แทนเจ้าของเอง.

## 5. Dependency coverage และ severity

- ส่ง lockfiles สองไฟล์ให้ OSV โดย explicit path; ใช้ all-packages JSON,
  config ที่ไม่มี ignore/PackageOverrides และปิด call analysis/reachability filtering.
  ไม่ติดตั้ง/resolve dependencies ใหม่ และไม่ใช้ lockfile ของ `references/admin-template`
  ซึ่งเป็นแหล่งอ้างอิง UI ไม่ใช่ application ที่ build.
- เทียบรายการ package/name/version/ecosystem ที่ scanner ตรวจ กับ inventory ใน lockfiles
  รวม dev/transitive/optional ทุก platform; local project entry แยกอย่างชัดเจน.
  lockfile หาย/parse ไม่ได้, inventory หายบางส่วน, package source ไม่รองรับ,
  API timeout หรือ advisory response ไม่ครบ → ไม่ผ่าน ไม่ตีความว่า zero vulnerabilities.
- ใช้ `results[].packages[].groups[].max_severity` ของ OSV รุ่นที่ pin เป็นคะแนน
  ที่ scanner คำนวณจาก advisory vectors; เก็บ IDs/aliases และ metadata ต้นทางใน temp
  เพื่อเชื่อม package-version กับกลุ่ม advisory. ไม่คำนวณ vector ใหม่ใน helper.
- Mapping: `9.0 ≤ score ≤ 10` Critical; `7.0 ≤ score < 9` High;
  `4.0 ≤ score < 7` Medium; `0 < score < 4` Low; score 0 ที่มี metadata ถูกต้องเป็น None.
  Missing/non-numeric/out-of-range หรือ advisory/group identity ขัดกันจนจัดกลุ่มไม่ได้
  → Needs Triage. หลายคะแนนที่ถูกต้องในกลุ่มใช้ค่าสูงสุดตาม OSV; ไม่เลือกค่าต่ำเพื่อผ่าน.
- ทุก advisory ต้องอยู่ในกลุ่มที่ประเมินครบ; ห้ามข้าม advisory ที่ severity ขาดเพราะ
  อีก advisory ในกลุ่มให้คะแนนได้. ระดับ High/Critical ไม่มี patched version ก็ยังบล็อก.
  รายการถอน advisory ต้องยืนยันจาก response ปัจจุบัน ไม่เดาเป็น false positive.
- Known Low/Medium รายงานตามจริง; Unknown/Needs Triage ไม่ผ่าน.
  Exception ระบุ ecosystem/package/version/advisory และ approval evidence;
  เปลี่ยน version/advisory ไม่ขยาย exception เอง. ไม่ใช้ auto-fix/auto-merge.

## 6. CodeQL coverage และ policy

- สแกน source ใน repo ของทั้ง 3 languages รวม runtime, migrations, tooling/tests
  และ `.github/workflows`; exclude เฉพาะ `references/admin-template` กับ generated/vendor
  output เช่น `.venv`, `node_modules`, `dist`, test reports. บันทึก config/exclusions
  และจำนวน files ที่ extract ได้ต่อภาษา; language ที่คาดว่ามีโค้ดแต่ไม่ extract ให้ไม่ผ่าน.
- `analyze` ต้องสร้าง full current-candidate SARIF; ประเมิน results ทั้งหมด
  ไม่กรองเฉพาะ new alerts, diff lines หรือ GitHub baseline state.
- Resolve rule descriptor ตาม SARIF schema ทั้ง driver/extensions และอ่าน
  `properties.security-severity` เป็นคะแนน 0–10 ตาม mapping ในหัวข้อ 5.
  ใช้ tags/metadata ระบุ security rule; security finding ที่ metadata หาย/ขัดกัน
  เป็น Needs Triage. Non-security error/warning ไม่แปลงเป็น High โดยอัตโนมัติ.
- ตรวจ report/run/ภาษา/กฎและ invocation/extraction errors; ไฟล์ว่าง, JSON ผิดรูป,
  ขาดภาษา, analyze ข้าม queries หรือ extraction failure ไม่เท่ากับไม่มี findings.
- ไม่ยอมรับ SARIF suppression จาก candidate เป็น owner approval อัตโนมัติ;
  exception ต้องระบุ rule/location/content identity และ approval เช่นเดียวกับ gate อื่น.
- summary เผยเฉพาะ language, rule ID, path/line, severity และจำนวน findings;
  ไม่เผย message/snippet/code flow/raw SARIF. หลักฐานภายในสำหรับ triage ต้องปิดค่าก่อนนำออก.

## 7. ผลรวมและค่าใช้จ่าย

- แต่ละ component ส่ง manifest ขนาดเล็กเฉพาะ safe fields: schema version, run/attempt,
  candidate identity, tool/config versions, source coverage, scan status และ policy verdict.
  aggregate ตรวจรูปแบบ/identity และ job conclusion ครบก่อนให้ success;
  ใช้ artifact เฉพาะ manifests ที่ไม่มี raw data, retention 1 วัน และเพดานขนาดต่อไฟล์.
- ใช้ summary รายงาน Low/Medium/Needs Triage/Blocked แยกกัน; ไม่ใช้ `continue-on-error`
  หรือ `|| true` ทำให้ scan error ผ่าน. ถ้าต้องจับ exit code เพื่ออ่านผลพบช่องโหว่
  ต้องแยก documented findings exit กับ execution error และส่ง verdict ต่ออย่างครบถ้วน.
- ปิด cache/DB upload ใหม่ที่ไม่จำเป็น; ตรวจ billing/storage เดิมก่อนเพิ่ม artifacts.
  หากโควตาไม่พอ ให้ใช้ job outputs ขนาดจำกัดแทน manifests artifacts โดยต้องคง identity/
  verdict ครบ หรือหยุดเสนอปรับแผน ไม่เปิด paid storage/larger runners.
- GitHub Dependabot security updates เปิดเฉพาะการสร้าง remediation PRs ตาม feature;
  ไม่มี auto-merge. ไม่เปิด version-update PRs จำนวนมากหรือสร้าง external notifications เพิ่ม.

## 8. GitHub settings, rollout และการกู้คืน

การเปลี่ยน settings ทำหลัง code review/validation ที่เกี่ยวข้องและได้รับคำสั่ง Git ตามเดิม.

1. Read-only snapshot: visibility, default branch SHA, workflow token/fork permissions,
   secret-scanning settings, dependency graph/alerts/security updates, CodeQL default setup,
   protection/rulesets ทั้งหมด และ required check names/app IDs. ไม่อ่านค่า secrets.
2. พัฒนา local → tests → **Ready for Code Review** พร้อมผล/งานค้าง/ความเสี่ยง;
   หยุดรอ `review code`. หลัง review/fixes ให้ถาม refactor ตาม AGENTS.md;
   หลัง refactor ที่อนุญาตทำ validation ต่อทันที.
3. เมื่อเจ้าของสั่ง commit/push/PR: รัน security workflow บน candidate และติดตาม required CI
   จนจบ. ยืนยันชื่อ `Security / gate` และ source app จาก check runs จริง รวมผลครบทุกภาษา.
   Findings ที่ต้องแก้ application คง blocker; ไม่ขยาย scope เอง.
4. เปิด dependency graph ถ้ายังปิด, Dependabot alerts/security updates,
   repository secret scanning/push protection. อ่านกลับยืนยันสถานะทุกตัว;
   คง CodeQL default setup ปิดเพื่อใช้ advanced workflow เพียงชุดเดียว.
   native partner monitoring/validity checking มีพฤติกรรมของ provider เอง;
   agent ไม่เปิด on-demand validity checks หรือใช้ credential ติดต่อ provider.
5. Activate merge enforcement แบบมีช่วงเปลี่ยนที่ป้องกัน merge: snapshot/re-read
   แล้ว lock main ชั่วคราว, เพิ่ม required `Security / gate` โดยรักษา 6 checks เดิม,
   strict/enforce-admins/no-force-push/no-delete; ตรวจค่าที่อ่านกลับและผล candidate ล่าสุด.
   ปลด lock คืนสถานะเดิมเฉพาะเมื่อ settings และ candidate ตรงกันครบ.
   ก่อน activation ยังรายงานว่า Pending activation ไม่อ้างว่ามี security gate บน main แล้ว.
6. หาก settings ถูกเปลี่ยนโดยคนอื่น/เขียนได้บางส่วน/ผลไม่ตรง หยุดและรายงานสถานะจริง;
   ไม่ overwrite snapshot เก่าทับคนอื่น. ถ้า lock แล้วไม่ปลอดภัยต่อการปลด ให้คง lock
   และรายงานทันทีพร้อมทางกู้คืน ไม่ปลดโดยข้าม gate ใหม่.
7. การกู้คืนใช้ read-before-write เฉพาะ fields ที่งานนี้เปลี่ยน; การลด/ถอน security gate
   หรือปิด protection หลังเปิดต้องให้เจ้าของตัดสินก่อน. ห้ามลบ required CI เดิม,
   ลบหลักฐาน findings หรือใช้ admin bypass เพื่อ merge.
8. Merge เฉพาะเจ้าของสั่ง; ตรวจ final head/base และทุก gate อีกครั้ง ติดตาม post-merge CI
   บน merge SHA. งานสำเร็จเมื่อ Feature validation ครบและ Release checkpoint V-19 ผ่าน
   รวม post-merge settings readback และ manual dispatch บน main;
   scheduled path ตรวจ config/dispatch โดยไม่ต้องรอวันถัดไปเป็นพิธี.

## 9. ไฟล์ที่จะเปลี่ยน

| ไฟล์ / ส่วน | การเปลี่ยน |
|---|---|
| `.github/workflows/security.yml` | เพิ่ม isolated security workflow และ aggregate required check |
| `.github/security/tools.json`, `gitleaks.toml`, `osv-scanner.toml`, `codeql-config.yml`, `exceptions.json` | pins/checksums, explicit rules/config และ scoped exceptions (เริ่มว่างจนมี owner approval) |
| `tools/security/` | scanner adapters, inventory/candidate checks, safe report/aggregate และ wrapper ดาวน์โหลดเครื่องมือที่ตรวจ checksum |
| `tools/security/tests/` | stdlib unittest สำหรับ policy/error/redaction และ integration fixtures ที่สร้างใน temp |
| `specs/features/2026-11-05-security-ci/` | evidence/checkpoints และผล validation |
| `specs/roadmap.md` | สถานะจริงของงาน; ไม่เปลี่ยนสถานะ features อื่น |
| GitHub repository settings | เฉพาะรายการในหัวข้อ 8 และไม่สร้าง infra ใหม่ |

ไม่มี migration, API contract, application/session/persistent storage หรือ trading logic changes.
ไม่แก้ workflow CI เดิมถ้าไม่จำเป็น; หาก implementation ต้องเปลี่ยนขอบเขตจากตารางนี้
ให้หยุดเสนอ amendment ก่อนแก้ส่วนที่ต่าง.

## 10. Checkpoints และความเสี่ยง

- M1: adapter/policy + explicit config, unit tests และ no-secret-output checks.
- M2: workflow + real scanner probes บน disposable synthetic fixtures/candidate,
  inventory completeness, three-language coverage และ static checks.
- M3: เมื่อโค้ดครบทุกขอบเขตแจ้ง Ready for Code Review; remote activation เป็น deployment
  validation ที่ยังค้าง ไม่แอบเปิด settings ก่อนผ่านขั้น review.
- M4: หลัง review/refactor และคำสั่ง Git ตรวจ remote CI, rejection cases และ settings activation;
  V-01..18 เป็น Feature ต้องผ่านก่อน merge. Merge เมื่อสั่ง แล้วตรวจ V-19 เป็น Release
  checkpoint ของ security CI ก่อน Completed; ไม่ใช่การตรวจรับ release ของ application
  และไม่เพิ่ม workload/Batch ของระบบเทรด.
- ความเสี่ยงหลัก: scanners พบปัญหาเดิมจริงจน merge ไม่ได้, source/report schema เปลี่ยน,
  suppression/exception กว้างเกินไป, raw output รั่ว, fork permissions และชื่อ required check ผิด.
  ใช้ [validation.md](validation.md) ปิดความเสี่ยงเหล่านี้; ไม่ลดเกณฑ์เพื่อให้ onboarding ผ่าน.
- Full regression ของ app ใช้ required CI เดิม ไม่สั่งซ้ำ local ทั้งระบบโดยไม่มีผลกระทบใหม่;
  ก่อนชุดยาว/remote scanner probes ให้แจ้งขอบเขตและเวลาประมาณตาม testing.md.

## แหล่งอ้างอิง

- [OSV supported lockfiles](https://github.com/google/osv-scanner/blob/v2.7.0/docs/supported_languages_and_lockfiles.md)
- [OSV JSON model / max_severity](https://github.com/google/osv-scanner/blob/v2.7.0/pkg/models/results.go)
- [Gitleaks flags และ occurrence fingerprint](https://github.com/gitleaks/gitleaks/blob/v8.30.1/README.md)
- [CodeQL analyze inputs](https://github.com/github/codeql-action/blob/main/analyze/action.yml)
- [CodeQL security severity](https://github.blog/changelog/2021-07-19-codeql-code-scanning-new-severity-levels-for-security-alerts/)
- [GitHub Actions secure use](https://docs.github.com/en/actions/reference/security/secure-use)
