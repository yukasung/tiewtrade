# CI feedback time — Implementation checkpoint

วันที่: 2026-11-11
สถานะ: Bounded network diagnostics review/refactor passed; preparing new GitHub candidate; local 58 tests/static checks Passed; PR #67 remains 754edcc (6/7 required checks Passed, E2E Failed); real diagnostic evidence Pending

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

## Remote checkpoint — PR #67 / runner DNS blocker — 2026-11-11

- เจ้าของสั่ง commit/push/เปิด PR แล้ว; feature commit เดียว
  `d5e733ecdd6934179ed4c1944bf9bcd69c5bddc4`, PR
  [#67](https://github.com/yukasung/tiewtrade/pull/67), merge candidate
  `9ea0a06efed0a06b58207538a2a0256ce097d486` บน main `de3bdcb`.
- Required checks ผ่าน **6/7**: config/backend/frontend/API/container และ Security.
  [Security 43048918175](https://github.com/yukasung/tiewtrade/actions/runs/43048918175) Passed.
- [Main CI attempt 1](https://github.com/yukasung/tiewtrade/actions/runs/43048918284/attempts/1)
  และ [attempt 2](https://github.com/yukasung/tiewtrade/actions/runs/43048918284/attempts/2)
  **Failed** จาก E2E Playwright dependencies installation: Azure Ubuntu mirror DNS
  resolution failure, exit 100 ก่อนเริ่ม browser/application tests. ตรวจ log ทั้งสองรอบแล้ว.
  Attempt 2 เป็น targeted E2E retry หลัง attempt 1 จบ; ชุดที่ผ่านแล้วใช้ผลเดิมต่อ.
  Required E2E verdict เป็น failure ตามจริงทั้งสองรอบ ไม่มี false green.
- Full pilot เลือกทุก worker ถูกต้อง; config บน GitHub รัน 28 policy tests ผ่าน.
  API แสดงเฉพาะ pull_request events ของ CI/Security บน head นี้ ไม่มี feature-push CI ซ้ำ.
- [Docs-only run 43049130357](https://github.com/yukasung/tiewtrade/actions/runs/43049130357)
  บน `0975c3f8efa46d58ae2e6cd9827c95583953c410` **Passed**: six stable checks success,
  five application workers skipped; log ยืนยัน docs-only และ 28 policy tests Passed.
  เวลา run_started_at ถึง updated_at 78s เป็นผลรอบนี้ ไม่ใช่คำรับรองเวลาที่ลดได้ทุก PR.
- [Superseded run 43049060969](https://github.com/yukasung/tiewtrade/actions/runs/43049060969)
  บน `6201df0e26cde759c43be4f35ef3168508b54d71` in_progress ก่อน synchronize และ
  cancelled หลัง update; พิสูจน์ cancellation จริง. Pilot
  [PR #68](https://github.com/yukasung/tiewtrade/pull/68) ปิดโดยไม่ merge;
  branch คงไว้ตามข้อห้ามลบ branch ที่ยังไม่ merged.
- Structured metadata/results อยู่ใน [github-pilot.json](github-pilot.json).
  บันทึก CI results ใน PR description ด้วย; รอบ evidence นี้ยังไม่ commit/push
  เพื่อไม่สร้าง CI วนจากเอกสารรายงานผล.
- [Runner DNS amendment](../runner-dns-amendment.md) เป็น Proposed เพื่อ owner review;
  ยังไม่แก้ workflow/bootstrap นอกแผนที่อนุมัติ และไม่ rerun รอบสามด้วยวิธีเดิมโดยไม่มีข้อมูลใหม่.
  ขั้นถัดไปคือขออนุมัติ amendment หรือรอ environment ฟื้นก่อน targeted E2E retry.
  Required E2E ยัง Failed; post-merge/main/manual ยัง Pending และยังไม่พร้อม merge/Completed.

## Approved DNS amendment — implementation checkpoint — 2026-11-11

เจ้าของตอบ `approve` ให้ runner-dns-amendment.md แล้ว; บันทึก Approved และเพิ่ม
scope/validation ใน plan.md + validation.md ก่อนแก้ source code.

- เพิ่ม `.github/scripts/prepare_e2e_apt.py` และ step เฉพาะ e2e-run ก่อน Playwright install.
  แก้เฉพาะ active Azure Ubuntu base URI ใน known APT files เป็น HTTPS Ubuntu archive;
  รักษา bytes อื่น, security pocket, signing-key fields, permissions และ ownership เดิม.
- ตรวจ known config ทั้งหมดก่อนเริ่มเขียน; unsupported Azure URI, missing layout,
  symlink/parent escape และ read/write failure ทำให้ operational failure.
  stdout รายงานเฉพาะ updated_files count และ stderr ไม่พิมพ์ raw config/error contents.
- เพิ่ม `.github/tests/test_e2e_apt.py`: 11 fixture/CLI tests; เพิ่ม workflow-order test อีก 1
  ใน test_ci_selection.py. Existing 28 policy/verdict tests คงไว้ รวมเป็น **40 tests**.
- Development test รอบแรกพบ matcher ของ unknown host กว้างเกินไป จนปฏิเสธ third-party
  hostname ที่เพียงมี Azure hostname เป็น prefix; เพิ่ม exact-host boundary แล้ว fixture ผ่าน.
  Ruff รอบแรกพบ long fixture literals; แบ่ง literals โดยไม่เปลี่ยน bytes แล้วผ่าน.
- `python3 -m unittest discover -s .github/tests -v`: **Passed 40 tests, 4.467s**.
- Actionlint v1.7.12 (ShellCheck unavailable), Ruff lint/format และ strict mypy: **Passed**
  สำหรับ workflow และ CI helpers/tests ทั้งหกไฟล์.
- Implementation inventory: ถอดเฉพาะ approved bootstrap step ออกจาก workflow แล้ว
  byte-identical กับ d5e733e; selectors/verdict helper ไม่เปลี่ยน และ original pending
  tracked files ทั้งหกยังตรงกับ snapshot เดิม. ไม่รัน application full regression ในเครื่อง.
- นี่เป็น implementation verification ไม่ใช่ focused Code Review ของ helper เพิ่มใหม่.
  งาน CI ตามขอบเขตแผน amended เขียนครบแล้ว; ส่ง Ready for Code Review พร้อมผลนี้
  และหยุดรอคำสั่ง `review code` ตาม AGENTS.md ก่อน review/ขั้นถัดไป.
- ขณะนี้ยังไม่ commit/push amendment source code; PR #67 ยังอยู่บน d5e733e และ required
  E2E เป็น Failed จาก runner DNS ทั้ง attempts 1/2. Local fixture proof ไม่แทน Linux/browser.
  หลัง review/checkpoints ที่กำหนดจึงอัปเดต PR candidate ตามคำสั่ง Git ที่ได้รับแล้ว
  และติดตาม required CI 7/7/E2E จริงบน SHA ใหม่; docs-only/cancellation ใช้ผลเดิมที่ยัง valid.
- ไม่มี application, session/persistent business data, database transaction หรือ trading
  logic เปลี่ยน; sudo ใช้เฉพาะ config บน disposable E2E runner ตาม amendment ที่อนุมัติ.

## DNS amendment focused Code Review — 2026-11-11

Owner requested `review code`. No actionable findings in the approved amendment scope.
Reviewed known-file writes, URI boundaries, symlink/root containment, preflight validation,
error propagation, sanitized output, and preservation of signing keys and repository fields.
Removing the sole new E2E bootstrap step leaves the workflow byte-identical to d5e733e;
selector/verdict helpers and required checks are unchanged. No application session,
persistent storage, transaction or trading behavior changes.

No source changes resulted from review. Reused the valid 40-test/actionlint/Ruff/strict-mypy
evidence; no redundant application regression or CI run. Fixture tests do not establish
actual Linux runner/network/browser success: V-21 remains Pending and prior E2E failures
remain recorded. No commit/push/merge performed during this review.

Next checkpoint: await owner's `refactor the code` decision under AGENTS.md before
continuing candidate preparation and the previously authorized PR update/required CI.
Not ready for merge or Completed. This review supersedes the review-pending status above.

## Authorized DNS helper refactor and final local validation — 2026-11-11

Owner requested `refactor the code`. Extracted `_prepare_config` as a pure byte transformation;
`prepare_apt` retains filesystem validation, collecting all changes before writes. Behavior,
URI matching, exception propagation and output remain unchanged. Focused diff inspection
confirmed the original loop was moved without changing its rules. No new test-only abstraction
or application changes were introduced.

- Post-refactor: 40 existing fixture/policy tests Passed (4.164s); Ruff lint/format, strict
  mypy and actionlint Passed. No full local application regression repeated.
- Workflow remains byte-identical to d5e733e after removing the approved three-line step;
  original pending tracked files in the owner's worktree remain unchanged.
- Review/refactor stop gates satisfied. Combine all available source/spec/evidence in one
  commit and update PR #67 under the prior owner Git authorization, then monitor required
  CI on the new SHA. Full runtime CI estimate 20–30 minutes was communicated before push.
- V-21 remains Pending until the new actual Linux/browser run passes. Failed attempts 1/2
  and valid docs-only/cancellation proof are retained; merge still requires owner instruction.

## Refactored amendment GitHub candidate — 2026-11-11

Committed/pushed 754edcce82636046e992b65e0abadfcac616de19 under prior Git authorization;
PR #67 synthetic merge candidate 9c41779924b770794e0b9f6de47762cad041a388.
CI run: https://github.com/yukasung/tiewtrade/actions/runs/43057440639.
Security: https://github.com/yukasung/tiewtrade/actions/runs/43057440674 — Passed.

Config log proves full selection and all 40 policy/fixture tests Passed on Linux.
APT preparation succeeded at 16:22:51 UTC with updated_files=1. Playwright installation
then failed at 16:36:38 UTC: archive.ubuntu.com DNS resolution failure, APT exit 100.
E2E job 130650830410 did not reach browser/application tests; required E2E verdict
130659764506 correctly Failed. Switching the mirror did not recover the environment.
This establishes failure across both the original Azure mirror and Ubuntu archive,
not the root cause of DNS failure or general network unavailability.

Backend is still being monitored to completion; no unchanged retry started. Preserve
the failed gate. After three unsuccessful E2E setup attempts across the original and
amended methods, stop further experiments and present options under AGENTS.md.
Remote result updates are uncommitted to avoid another documentation-only CI cycle.

### Final candidate checkpoint

CI run 43057440639 finished at 16:45:12 UTC. Backend and every isolated/migration/fresh-state
step Passed; all four other non-E2E CI gates and the Security gate Passed. Compared all seven
strict required contexts against the latest PR status rollup: **6/7 Passed**, E2E Failed.
Head remains 754edcc; base remains de3bdcb; no conflicts and no merge performed.

Refactor is complete. V-21 remains Failed, V-12 Partial and post-merge/main/manual Pending.
Next options before another experiment: (1) wait for evidence of environment/DNS recovery
then retry only E2E on this SHA; (2) approve a bounded DNS/network diagnostic amendment
to identify why both Ubuntu endpoints fail on the runner. Recommend option 2 before
another long installation attempt. Changing resolver/network policy or adopting a prebuilt
Playwright image is outside the currently approved bootstrap amendment. Await owner choice
under AGENTS.md's stop-after-three-rounds rule; no automatic fourth attempt.

## Approved bounded network diagnostics — implementation checkpoint — 2026-11-11

Owner explicitly requested implementation of the proposed diagnostic plan. Added the
approved network-diagnostics-amendment.md and plan/validation extension before source edits.
No unresolved clarification blocks this diagnostic scope.

- Added `.github/scripts/diagnose_e2e_network.py`: user/sudo DNS probes for four fixed
  domains, HTTPS probes for Ubuntu archive and Microsoft packages, sanitized nameserver/
  proxy-presence/runner-image metadata. No resolver, proxy or repository configuration writes.
- JSON stdout omits raw command output, errors, proxy values, headers and response bodies.
  Privileged metadata must match the safe schema. curlrc disabled, TLS verification retained,
  HTTPS-only redirects and zero retries. Root subprocesses have nested coreutils timeouts.
- Parent monotonic budget 100s; step timeout 2 minutes. Missing tools/invalid evidence/budget
  exhaustion fail closed. DNS and HTTPS results are separate; DNS failure alone cannot
  override successful HTTPS via proxy. Sudo Ubuntu archive HTTPS must succeed to continue.
- All 12 probes are collected despite individual network failures; no privileged/live-network
  diagnostic was executed on the developer machine. Tests use injected command responses,
  temporary fixtures and one short real Python child timeout (no network/sudo/APT invocation).
- Added 17 diagnostic behavior tests and one workflow wiring test to the prior 40 tests.
  **58 tests Passed in 3.949s**, Ruff lint/format, strict mypy on eight files and actionlint
  Passed (ShellCheck unavailable). Initial static formatting/import/type issues fixed;
  no failing behavior tests. No application full regression repeated.
- Removing the four-line diagnostic step restores workflow bytes exactly to HEAD 754edcc.
  Selector/verdict/mirror helper, Security/venue workflows and original six tracked pending
  files in the owner's worktree are unchanged. New inventory records the approved exception.
- Implementation complete for amended scope. This is development verification, not focused
  Code Review: send **Ready for Code Review** and wait for `review code` under AGENTS.md.
  Reviewer should focus on privileged metadata/log redaction, subprocess/global time limits,
  and fail-closed gate without treating DNS/proxy observations as actual browser success.
- No commit/push/new CI in this checkpoint. PR #67 remains 754edcc; prior failures remain.
  V-24 (real runner report, E2E, latest required 7/7) and post-merge/main/manual are Pending.
  After review/refactor checkpoints, combine source/spec/evidence in one PR update under
  prior Git authorization and monitor CI to completion (estimate 20–30 minutes).
  Further recovery methods require a new evidence-based amendment; merge needs owner command.

## Bounded diagnostics focused Code Review — 2026-11-12

Owner issued `review code`. Reviewed the new helper, workflow wiring, fixture tests and
approved diagnostic amendment. **No actionable findings** in the reviewed scope.

- Examined user/sudo command construction, noninteractive privilege use, DNS/HTTPS
  separation, privileged metadata schema, sanitization and fail-closed installation gate.
- Checked per-command limits, nested timeout placement, global budget and workflow step cap;
  original Playwright/test commands and required verdict wiring remain intact.
- Reused valid 58-test/Ruff/strict-mypy/actionlint evidence because source was unchanged.
  Added a one-off independent CLI subprocess check using executable fixtures in a temporary
  directory (fake sudo/timeout/getent/curl/apt-config, with real Python metadata re-exec).
  Both success and sudo-only archive DNS failure scenarios Passed: correct JSON/exit status,
  user/sudo proxy-presence differences retained, sensitive fixture values absent from logs.
  This exercised process boundaries but did not use actual privilege escalation or network
  probes; it does not replace Linux runner evidence or validate actual DNS recovery.
- No application/session/shared-storage/transaction/trading logic changes in this scope.
  No source changes resulted from review; only validation/checkpoint status updated.
- Next: await owner's `refactor the code` decision under AGENTS.md. After that checkpoint,
  prepare one authorized PR update and monitor required CI on the new SHA. PR #67 remains
  754edcc with E2E Failed; real diagnostic evidence and post-merge/main/manual stay Pending.
  No commit/push/CI rerun/merge performed during this review.

## Authorized diagnostic refactor — 2026-11-12

Owner requested `refactor the code`. Extracted `_context_metadata` from `diagnose` to
separate context-specific collection/schema validation from probe orchestration and gating.
No probe targets, permissions, budgets, sanitization or gate policy changed.

- Post-refactor 58 tests Passed (4.019s), Ruff lint/format, strict mypy on eight files and
  actionlint Passed (ShellCheck unavailable). No full local application regression repeated.
- Independent CLI subprocess fixtures compared the pre/post-refactor scripts: identical
  JSON, stderr and exit status for success, sudo-only archive DNS failure and sudo APT
  metadata failure. All three scenarios Passed with no sensitive fixture values in output.
  Fake command executables were used; no real sudo/network/APT operations occurred locally.
- Workflow preservation and original pending-file inventory verified. Review/refactor gates
  satisfied; combine source/spec/evidence in one commit/push under the existing owner Git
  authorization. Follow latest PR candidate's required CI to completion; full-run estimate
  20–30 minutes communicated before push. Two-minute limit applies to diagnostic step only.
- Real runner diagnostic evidence and required 7/7 remain Pending. Preserve all earlier
  E2E setup failures. Any new resolver/proxy/image recovery requires a separate approved
  amendment based on the actual report; merge still requires owner instruction.
