# CI feedback time — Implementation checkpoint

วันที่: 2026-11-11
สถานะ: Review/R1/refactor/local validation ผ่าน — เจ้าของสั่ง Git/pilot แล้ว; กำลังตรวจ GitHub candidate และยังไม่ Completed

## Scope และ baseline

- เจ้าของอนุมัติ requirements เดิม 2026-10-26 และ plan/validation ฉบับปรับ 2026-11-11.
- Branch `feat/ci-feedback-time`, worktree `../TiewTrade-ci-feedback-time`.
- Committed baseline: `52a00feda66c6248b10fe72cf12a076047f0e3ed` จาก working tree เดิม.
- Working tree เดิมอยู่บน `feature/f-17-tp-sl`; workflow ไม่มี uncommitted hunks ก่อนแยก.
  ไม่ย้าย/stash/reset/commit งานอื่น. ตรวจ hash ของ tracked pending files เดิม 6 ไฟล์
  หลังบันทึก approval แล้วเทียบหลัง implementation ตรงกันทั้งหมด.
- Governance instructions ของเจ้าของใน session และ AGENTS/testing ฉบับ working tree เดิม
  ยังคงใช้; ไม่คัดลอก governance changes ที่ค้างอยู่เข้า branch นี้.
- [Baseline inventory](baseline-inventory.json) เก็บ SHA/hash และ required check names.

## สิ่งที่เปลี่ยน

- `.github/workflows/ci.yml`: PR opened/reopened/synchronize, push เฉพาะ main,
  manual full/affected; PR-only cancellation และ main/manual ใช้ run identity แยก.
- Config job ใช้ standard-library policy tests และ selector; docs-only ตรวจ whitespace
  ของ committed candidate diff โดยไม่ provision application services.
- `.github/scripts/ci_selection.py`: whitelist AGENTS.md/README.md/specs Markdown;
  เอกสาร runtime inputs มี override ก่อน whitelist. Non-docs/mixed/unknown/empty diff
  หรือ resolve base/fetch/diff ไม่ได้ → full. Selector error/whitespace failure → job fail.
- ใช้ argv subprocess และ NUL-delimited diff แบบ no-renames; ไม่แทรก PR payload/path
  ลง shell. PR เปรียบเทียบ base กับ checked-out merge candidate; manual affected
  fetch main แล้วใช้ merge-base. Main/manual full ข้ามการลดชุดตรวจเสมอ.
- `.github/scripts/ci_verdict.py`: required names เดิมทั้งหกยังอยู่;
  selected worker ต้อง success, docs-only worker ต้อง skipped และ config ต้อง success.
  Output ขาด/ผิดรูปแบบ หรือ failed/cancelled/missing worker ไม่ถูกแปลงเป็น success.
- `.github/tests/test_ci_selection.py`, `test_ci_verdict.py`: path policy, real disposable
  git repositories, CLI failure/output propagation, workflow wiring และ negative verdict matrix.

## Implementation verification (ไม่ใช่ Code Review)

| ตรวจ | ผล / ขอบเขต |
|---|---|
| `python3 -m unittest discover -s .github/tests -v` | Passed: 26 tests, 3.959s; รวม verdict matrix 7 selector results × 6 outputs × 7 worker results = 294 combinations |
| `/tmp/tiewtrade-ci-tools/actionlint -shellcheck='' .github/workflows/ci.yml` | Passed: actionlint v1.7.12 จาก official rhysd/actionlint release; ตรวจ SHA-256 archive เทียบ release checksums ก่อนใช้. ไม่ได้รัน ShellCheck เพราะเครื่องไม่มี tool นี้ |
| `ruff check --config backend/pyproject.toml .github/scripts .github/tests` | Passed โดยใช้ Ruff จาก backend environment เดิม |
| `ruff format --check --config backend/pyproject.toml .github/scripts .github/tests` | Passed: 4 files |
| `MYPYPATH=.github/scripts mypy --strict --follow-imports=normal .github/scripts .github/tests` | Passed: 4 source files โดยใช้ mypy จาก backend environment เดิม |
| Baseline execution-block comparison | Passed: ทั้งห้า worker หลัง normalize เฉพาะ job ID/name/selector condition/needs ตรงกับ original block ทุกตัวอักษร (ไม่นับ trailing whitespace); steps/services/env/defaults/assertions เดิมไม่เปลี่ยน |
| Required names / venue workflow / pending work | Local Passed: required names เดิมหกชื่อ, venue-contract.yml byte-identical, pending tracked files เดิมไม่เปลี่ยน; remote protection ยัง Pending |
| Runtime documentation-input scan (รอบ implementation เดิม) | ค้นเฉพาะ backend/src, backend/scripts, frontend/src, .github และ config จึงพลาด consumers ใน tests; พบและแก้ใน review R1 ด้านล่าง ไม่ใช้ข้อสรุปเดิมว่า RUNTIME_DOC_INPUTS ว่างต่อ |
| `git diff --check` | Passed สำหรับ tracked diff; ตรวจ whitespace/local Markdown links ของไฟล์ใหม่ก่อนส่ง checkpoint เพิ่มต่างหาก |

ผลระหว่างพัฒนาที่แก้แล้ว: รอบแรก unittest 20/21 ผ่าน โดย fixture ที่ใช้ shallow clone
คาด docs-only แต่ merge-base ไม่มีจึงได้ full ตาม fallback ที่ปลอดภัย. แยกเป็น shallow
fallback test และ missing-base fetch test ที่มี graph ครบ แล้วชุดสุดท้ายผ่าน 26/26.
Ruff รอบแรกพบ formatting/line length/capture_output; แก้แล้ว lint/format ผ่าน.
ไม่รัน application full regression, E2E, Docker หรือ Live orders ในเครื่องเพื่อพิสูจน์
เฉพาะการจัดคิว. คำสั่ง runtime/safety เดิมยังต้องผ่านบน GitHub candidate จริง.

## Risks และ Pending

- ความเสี่ยงหลัก: docs whitelist ข้าม runtime input และ required checks เขียวเท็จจาก
  skipped dependency. Review selector, override policy และ needs/always()/verdict wiring แล้ว;
  แก้ R1 ด้านล่าง และยังต้องพิสูจน์ behavior จริงบน GitHub.
- Verdict jobs เพิ่ม runner startup และ config checkout fetch-depth 0 มีต้นทุน;
  ยังไม่มี GitHub wall-time/queue-time จึงไม่อ้างลดเวลาเป็นตัวเลข.
- Required protection/readback และ PR merge candidate กับ main ล่าสุดต้องตรวจจริง
  ก่อน pilot/merge. ผล static/local ไม่แทน GitHub scheduler หรือ required CI.
- V-01/V-02/V-08/V-11/V-12: รอ remote trigger/cancellation/docs-only/full pilot/check results.
  ใช้ PR งานนี้เป็น full pilot และรวม docs-only/cancellation evidence เมื่อทำได้.
- V-13: main post-merge ครบทุกชุดเดิม และ manual full เมื่อ default branch พร้อม;
  manual dispatch/commit/push/PR/merge ยังต้องรอคำสั่งเจ้าของแยกตามกฎ Git.
- เจ้าของสั่ง `review code` แล้ว และตอบ “แก้ไข” ต่อคำถาม refactor; ทำ refactor
  เฉพาะ CI selector และ local validation ต่อแล้วตามรายละเอียดด้านล่าง.
  ขั้นถัดไป: รอคำสั่ง commit/push/PR เพื่อ GitHub pilot; ยังไม่ทำ remote mutation.

## Semantics references

- [GitHub workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)
- [GitHub concurrency](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency)

อ่าน official docs วันที่ 2026-11-11; main/manual ใช้ group แยกต่อ run เพราะ
cancel-in-progress=false เพียงอย่างเดียวไม่ป้องกัน pending run ใน group ร่วมถูกแทนที่.

## Code Review — 2026-11-11

เจ้าของสั่ง `review code` หลัง Ready for Code Review. ตรวจ diff ของ workflow,
selector/verdict, tests และ callers/consumers ที่เกี่ยวข้อง เทียบแผนที่อนุมัติแล้ว.

### R1 — High — เอกสารที่เป็น operational/contract input ถูกเลือกเป็น docs-only (Fixed)

- ตำแหน่ง: `.github/scripts/ci_selection.py`, `RUNTIME_DOC_INPUTS` เดิมว่าง.
- Trigger: PR เปลี่ยนเฉพาะ `README.md` เช่นลบ `--no-proxy-headers` จากคำสั่งเปิด API.
  ก่อนแก้ selector ให้ docs-only จึงข้าม `backend/tests/test_price_proxy_headers.py`
  ซึ่งอ่านคำสั่งนี้แล้วพิสูจน์ว่า client spoof admission peer ผ่าน forwarded headers ไม่ได้.
- ผลกระทบ: required checks อาจเขียวก่อน merge ทั้งที่ security regression เดิมควรตรวจจับ;
  post-merge full CI จะพบช้าไป. อีกสาม contract inputs ถูกข้ามด้วย ได้แก่
  `specs/roadmap.md`, F-33 validation และ F-35 plan.
- หลักฐาน: เพิ่ม regression case ก่อนแก้และรันพบ 4 failing subcases (ทั้งสี่ paths
  ถูกจัด docs-only). ไม่แก้ README จริงหรือเรียก Live Trading เพื่อทำ reproduction.
- แก้: เติมสี่ paths ใน exception set ก่อน whitelist ตาม RQ-03/RQ-04 และบันทึก
  mapping/consumer ใน plan ตามกลไก exception ที่อนุมัติไว้; ไม่เปลี่ยนข้อกำหนดผลิตภัณฑ์.
- Tests: เพิ่ม regression ของสี่ operational/contract inputs และ real-git/CLI case
  เปลี่ยนคำสั่ง README ซึ่งต้องออก `run_checks=true`, `selection=full`.
  ใช้ AGENTS.md เป็น ordinary-doc fixture แทน README เพื่อรักษาการตรวจ docs-only จริง.

### ผลตรวจหลังแก้

- `python3 -m unittest discover -s .github/tests -v`: **Passed 28 tests, 4.046s**;
  รวม verdict 294 combinations, git/CLI paths และ workflow wiring.
- Ruff lint/format และ strict mypy ของ CI helpers/tests ทั้งสี่ไฟล์: **Passed**.
- Worker-block comparison กับ baseline: **Passed** ทั้งห้า worker; required names หกชื่อคงเดิม.
  Workflow ไม่มีการแก้เพิ่มจาก candidate ที่ actionlint v1.7.12 ผ่าน จึงใช้ผลเดิมต่อ.
- Pending tracked files เดิมทั้งหกยัง hash ตรงกับก่อนเริ่มงาน; แก้เฉพาะ worktree ของ CI.
- ตรวจ security: PR/base/path ไม่ถูกแทรกลง shell, Git ใช้ argv และ validate SHA,
  logs ไม่พิมพ์ raw payload/secrets, permissions เป็น contents:read.
- ตรวจ stateless/session rules: ไม่มี application/session/persistent business data เปลี่ยน;
  constant mapping และ Selection เป็นข้อมูลชั่วคราวต่อ CI run ไม่ใช่ persistent state.
- ตรวจ diff fallback, main/manual full, PR-only cancellation และ skipped/failed/cancelled
  verdict paths แล้ว ไม่พบ finding เพิ่มในขอบเขต review นี้หลังแก้ R1.

GitHub scheduler/cancellation/branch protection, docs/full pilot และ post-merge/manual
ยัง Pending ตาม V-01/V-02/V-08/V-11/V-12/V-13; local review ไม่แทนหลักฐานเหล่านั้น.
ณ checkpoint หลัง review ยังไม่รับรองพร้อม merge หรือ Completed และรอคำตอบ refactor;
ผลขั้นถัดไปอยู่ในหัวข้อ refactor/local validation ด้านล่าง.

## Refactor และ local validation — 2026-11-11

หลังคำถาม refactor เจ้าของตอบ “แก้ไข”; ดำเนินการต่อในขอบเขต CI ของงานนี้.

- แยก `_resolve_comparison_base` ออกจาก `select_for_event` เพื่อให้ส่วน fetch/validate SHA/
  merge-base อยู่ด้วยกัน และอ่านนโยบายเลือก full/docs-only ได้ตรงขึ้น.
- คง fallback, argv handling, whitespace checks และ exception mapping ของ R1 เดิม.
  เทียบ diff หลัง refactor แล้วเป็นการย้าย logic เดิมเข้า helper โดยไม่เปลี่ยนสัญญา.
- จาก fingerprint ก่อน refactor มีเพียง `.github/scripts/ci_selection.py` เปลี่ยน;
  workflow, verdict helper และ tests เดิมไม่เปลี่ยน. ใช้ actionlint และ baseline worker
  inventory ที่ยัง valid ต่อ ไม่รัน E2E/application full regression ซ้ำเพื่อยืนยันการย้ายฟังก์ชัน.
- ตรวจผลกระทบและทำ local validation ตามแผนต่อทันที:
  `python3 -m unittest discover -s .github/tests -v` **Passed 28 tests, 4.003s**
  รวม R1 operational/contract paths, real Git/CLI, main/manual/full fallback และ
  verdict 294 combinations. Ruff lint/format และ strict mypy **Passed** ทั้งสี่ไฟล์.
- ตรวจ whitespace/local document references ผ่าน และยืนยัน pending tracked files
  ใน working tree ต้นทางทั้งหกยังมี hash ตรงกับ snapshot เดิม.
- Stateless/session/persistent business data ไม่มีผลกระทบจากการย้าย helper ใน CI.

ผลปัจจุบัน: local gates ที่ถึงกำหนดผ่านแล้ว; GitHub trigger/cancellation/protection,
docs/full pilot/required CI และ post-merge/manual ยังคง Partial/Pending ตาม validation.
ไม่แทนผล GitHub ด้วย local tests และไม่อ้างลดเวลาเป็นตัวเลขหรือพร้อม merge/Completed.
ขั้นถัดไป: รอเจ้าของสั่ง commit/push/เปิด PR/dispatch ตามกฎ Git เพื่อทำ pilot จริง.

## Git authorization และ integration candidate — 2026-11-11

เจ้าของตอบ “เริ่มทำ” หลังระบุขั้นถัดไป commit/push/เปิด PR เพื่อทดสอบ GitHub CI;
ถือเป็นคำสั่ง Git สำหรับงานนี้และ pilot ตาม validation ไม่ใช่คำสั่ง merge.

- Fetch main และ rebase เฉพาะ feature commit ไปบน
  `de3bdcb6b9d9187ee9a06b5f7dcb43387f5d8e98` สำเร็จโดยไม่เกิด conflict.
- Main มี 44 commits เพิ่มจาก baseline เริ่มต้น; CI baseline เพิ่ม
  `TIEWTRADE_DATABASE_URL_PLATFORM_BOOTSTRAP` ใน backend env ซึ่งรักษาไว้ครบ.
  ตรวจ execution blocks หลังรวมอีกครั้ง ตรงกับ latest main ทั้งห้า worker.
- Native protection readback: strict/up-to-date + enforce admins และ required contexts
  **7 รายการ** ได้แก่ main CI เดิมหกชื่อ (GitHub ตัดชื่อที่แสดงบางรายการด้วย `...`)
  และ `Security / gate`. ไม่เปลี่ยน protection/settings.
- `.github/workflows/security.yml` และ venue-contract.yml ตรงกับ latest main ทุก byte;
  Security gate เป็น required workflow แยกจาก selector ของงานนี้และยังต้องผ่านตามเดิม.
  รายละเอียด readback/integration hashes อยู่ใน baseline-inventory.json.
- Local validation บน combined candidate: 28 tests **Passed, 3.876s**,
  actionlint, Ruff lint/format และ strict mypy **Passed**.
  ไม่รัน application full regression ในเครื่องซ้ำ; ชุดนั้นตรวจจริงใน PR CI.
- รวม spec/implementation/review/refactor/integration evidence ก่อน push ใน feature commit
  เดียว. ผล GitHub ที่เกิดภายหลังจะรายงานพร้อม SHA/run URLs โดยไม่สร้าง commit วน.
- Main PR เข้า main เป็น full pilot. ใช้ temporary `validation/ci-docs-only` และ draft PR
  เข้า feature branch เป็น Git fixture ของงานเดียวกัน เพื่อให้ diff เป็น ordinary Markdown
  โดยไม่ต้อง merge workflow ก่อน. Synchronize pilot หนึ่งครั้งระหว่าง run เก่ายังทำงาน
  เพื่อพิสูจน์ cancellation และใช้ candidate สุดท้ายพิสูจน์ docs-only/verdict checks.
  Pilot ไม่ merge และไม่แก้ application/security policy; ปิด draft PR เมื่อเก็บผลครบ.
- Manual full/default-branch และ post-merge main ยัง Pending จนมีคำสั่งและเงื่อนไขพร้อม;
  การเปิด/ติดตาม PR ไม่ถือเป็นคำสั่ง merge.
