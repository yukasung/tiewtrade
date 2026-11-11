# ลดเวลารอ CI — Plan

สถานะ: **Approved — เจ้าของอนุมัติ 2026-11-11**
วันที่: 2026-10-26
ปรับแผน: 2026-11-11 — ตามคำสั่งเจ้าของให้ลด CI ซ้ำโดยคงขั้นตอนพัฒนาและด่านก่อน–หลัง merge
Requirements: [Approved](requirements.md)

## แนวทางและขอบเขต

รอบนี้ลดงานซ้ำสี่จุด: ตัด feature-push CI ที่ซ้ำกับ PR, ยกเลิก PR candidate เก่า,
ให้เอกสารทั่วไปตรวจเฉพาะเอกสาร และรวมการแก้/เอกสาร/หลักฐานให้ครบก่อน push.
ใช้ GitHub-hosted runners เดิม ไม่เปลี่ยน branch protection หรือเพิ่มบริการภายนอก.
คง review, validation, required CI ก่อน merge และ CI หลัง merge บน main.
post-merge ยังคงทุกชุดของ workflow เดิม ไม่ลดเหลือ smoke checks.

Selector รอบแรกมีเพียง `docs-only` กับ `full`: PR ที่มี runtime/config/test หรือ path
ที่ระบุผลกระทบไม่ได้ยังเรียก backend/frontend/API-contract/E2E/container ครบตามเดิม.
เป็นการเลือกแบบ conservative ภายใต้ RQ-04; เลื่อนการข้ามชุด backend/frontend แยกกัน
และการวิเคราะห์ dependencies ราย test ออกไปก่อน หากจะทำภายหลังต้องเสนอแผนใหม่.
ไม่เปลี่ยน assertions, thresholds หรือจำนวนชุดตรวจของ runtime PR เพื่อให้เร็วขึ้น.

## จังหวะ PR และ CI ของงานนี้

- ระหว่างพัฒนาใช้ targeted tests/static checks ตาม testing §7; เมื่อครบ implementation
  ให้แจ้ง Ready for Code Review แล้วรอ `review code` ตาม AGENTS.md.
- หลัง review/แก้ findings และ refactor ตามคำตอบเจ้าของ ให้ทำ validation ระดับ Feature
  ที่ตรวจในเครื่องได้ แล้วรวมโค้ด เอกสาร และหลักฐานที่มีอยู่ให้ครบก่อนเสนอ commit/push/PR.
- เปิด PR หรือ manual dispatch เมื่อเจ้าของสั่งตามกฎ Git; หากต้อง pilot ก่อนพร้อมตรวจรับ
  ต้องระบุขอบเขต เหตุผล และเกณฑ์ที่ยัง Pending ให้ชัด ไม่ถือเป็นการอนุมัติ merge.
- หลังเปิด PR ให้รวมการแก้ที่เกี่ยวข้องและ targeted checks ก่อน push รอบถัดไป;
  candidate ใหม่ต้องผ่าน required CI ของตัวเอง ไม่ใช้ผลจาก SHA เก่าแทน.
- ใช้ผลตรวจเดิมที่ยัง valid และไม่ rerun บน candidate เดิมโดยไม่มี input เปลี่ยน,
  หลักฐานขาด หรือเหตุด้าน environment/tooling ที่ตรวจพบและบันทึกไว้.
- ติดตาม required CI จนจบบน candidate ล่าสุด; หลังเจ้าของสั่ง merge ให้ติดตาม
  post-merge CI บน merge SHA จนจบตาม AGENTS.md.
- รายงานผล CI พร้อม SHA/run URL โดยไม่สร้าง commit เอกสารวนเพียงเพื่อบันทึก CI;
  หากพบ blocker หรือสถานะเปลี่ยนจริงให้รวมบันทึกกับรอบแก้ที่เกี่ยวข้องตามกฎเดิม.

## ของเดิมที่จะใช้ซ้ำ

| Path | ใช้ซ้ำ |
|---|---|
| `.github/workflows/ci.yml` | คำสั่ง lint/types/imports/pytest/contracts/E2E/Compose, services, versions, caches และชื่อ required checks |
| `config/postgres.env` | PostgreSQL version source เดิม |
| `frontend/package.json` | คำสั่ง test และ E2E เดิม ไม่คัดลอกชุดทดสอบใหม่ |
| `frontend/playwright*.config.ts` และ `frontend/e2e/helpers/environment.ts` | isolation และ environment เดิม; คง workers: 1 สำหรับ shared-state suites |
| `specs/standards/testing.md` §7 | เลือกตรวจและใช้ผลเดิม พร้อมบันทึก checkpoint เดียว |

## Trigger และ cancellation

- `pull_request`: รันเมื่อเปิด PR, เปิดใหม่ หรือ synchronize; รักษา candidate merge-ref
  ที่ checkout action เลือกตาม PR ไม่เปลี่ยนไปตรวจเฉพาะ head โดยไม่ตั้งใจ.
- `push`: เฉพาะ `main`; ไม่รันซ้ำบน feature-branch push ที่มี PR.
- `workflow_dispatch`: input `mode` เป็น `full` (default) หรือ `affected`.
  full เรียกทุกชุดของ CI นี้; affected เปรียบเทียบกับ merge-base ของ main.
- Concurrency group ของ PR ใช้ PR number และ `cancel-in-progress: true` เฉพาะ PR.
  main/manual ใช้ run identity แยก จึงไม่ถูก run ใหม่แทนที่หรือยกเลิก pending run
  จาก concurrency group ร่วมกัน; จำกัดด้วย runner capacity ตามเดิม.
- ไม่มี workflow-level paths filter. คง permission เท่าที่จำเป็น เช่น `contents: read`;
  ไม่ใช้ `pull_request_target`, ไม่ให้ workflow code สิทธิ์เขียน repository.

## Selector และตารางผลกระทบ

เพิ่ม selector Python standard-library ใน `.github/scripts/ci_selection.py` และ tests
ที่ `.github/tests/test_ci_selection.py` รันได้โดยไม่ติดตั้ง application dependencies.
ใช้ git diff แบบ NUL-delimited; พิจารณาทั้งชื่อเก่าและใหม่ของ rename/copy
หรือใช้ no-renames ให้เห็น deletion/addition ทั้งสองด้าน ไม่แยก path ด้วยช่องว่าง/newline.
PR ใช้ base SHA ที่ตรวจรูปแบบแล้วกับ candidate ที่ checkout อยู่และ merge-base;
ไม่แทรกชื่อ branch/path จาก PR ลง shell code. ตรวจ fetch/diff return codes.

| การเปลี่ยนแปลง | ชุดที่เลือก |
|---|---|
| เฉพาะ `AGENTS.md`, root `README.md` และ `specs/**/*.md` ที่ไม่ใช่ input สร้างโค้ด | ตรวจเอกสาร/whitespace และ selector checks; ไม่เริ่ม application services |
| frontend/backend source, tests, styles/assets, migrations/bootstrap หรือ API schema/generated API types | ทุกชุดตาม workflow เดิม |
| lockfiles/manifests, tooling config, Compose/Docker, `.github/`, `config/`, shared files หรือเอกสารที่ tooling ใช้สร้างโค้ด/กระทบ runtime | ทุกชุด |
| executable artifacts ใน specs, path อื่นที่ไม่รู้จัก, diff ว่างหรือหา base/diff ไม่ได้ | ทุกชุด พร้อมสรุปเหตุผล; ถ้า selector เอง error ต้องไม่รายงาน success |
| main push หรือ manual full | ทุกชุดโดยไม่ใช้ diff ตัดออก |

Selector ให้ `docs-only` เฉพาะเมื่อทุก path เข้า docs whitelist และไม่มี runtime input;
หากมี path เดียวที่ไม่เข้าเงื่อนไขให้ `full`. ไม่เลือกข้ามชุดตรวจแยก backend/frontend.
Mapping ข้อยกเว้นที่ตรวจพบระหว่าง review 2026-11-11 ตาม RQ-03/RQ-04
(ใช้เงื่อนไข runtime/contract input ที่อนุมัติไว้ ไม่เปลี่ยนขอบเขต selector):

| เอกสารที่ต้องเลือก full | Consumer เดิมที่จะใช้ตรวจต่อ |
|---|---|
| `README.md` | `backend/tests/test_price_proxy_headers.py` อ่านคำสั่งเปิดเซิร์ฟเวอร์และพิสูจน์ว่า spoof admission peer ผ่าน proxy headers ไม่ได้ |
| `specs/roadmap.md` | `backend/tests/infra/audit/test_documented_exception.py` ตรวจ release gate ของ audit retention |
| `specs/features/2026-09-28-venue-layer/validation.md` และ `specs/features/2026-10-01-binance-th-adapter/plan.md` | `backend/tests/venues/binance_th/test_error_changes.py` ตรวจเอกสารเทียบสัญญา error ของ venue |

Docs whitelist ต้องไม่มี wildcard `.md` ทั้ง repo; หากพบเอกสารที่ tooling ใช้สร้างโค้ด
ให้จัดเป็น full และบันทึก path ใน mapping. Diff failure ที่จัด full ไม่ได้หรือไม่สามารถ
ออก outputs ที่สมบูรณ์ถือเป็น selection failure. Selector ต้องรายงาน chosen sets/reasons
ใน job summary เพื่อให้ reviewer เห็นว่าข้ามเพราะอะไร โดยไม่พิมพ์ secrets.

## รักษา required checks และ failure propagation

- คงชื่อ checks ทั้งหกเดิมตาม workflow. `config` ยังอ่านเวอร์ชัน PostgreSQL
  และทำ selection/selector tests ที่จำเป็น ไม่ bootstrap application DB.
- ย้ายคำสั่งงานหนักไป internal jobs เช่น `backend-run`, `frontend-run`,
  `api-contract-run`, `e2e-run`, `docker-run`; ใช้ job-level condition ตาม selector
  เพื่อไม่ provision services ของชุดที่ไม่เลือก.
- Jobs ชื่อ required checks เดิมเป็น verdict jobs ขนาดเล็ก ใช้ `always()` และ `needs`
  selector กับ worker ที่เกี่ยวข้อง. แต่ละ verdict ต้องตรวจ selector success,
  output เป็น boolean ที่ถูกต้อง และผล worker ตรงกับการเลือกจริง.
- ถ้าเลือก worker ต้องได้ `success` เท่านั้น. ถ้าไม่เลือก worker ต้องเป็น `skipped`
  และ selection สมบูรณ์ จึง success พร้อมเหตุผล not applicable. Failure/cancelled/
  missing/unknown outputs ต้อง fail ไม่ใช้ default success หรือ `continue-on-error`.
- Verdict logic ใช้ helper เดียว `.github/scripts/ci_verdict.py` พร้อม negative tests
  ไม่คัดลอกเงื่อนไข success ที่ต่างกันห้าชุด. ไม่ใช้ผล local แทน required CI.
- Required names ตรวจทั้ง static workflow comparison กับ baseline และ remote readback
  ก่อน pilot เมื่อได้รับคำสั่ง Git. ไม่เปลี่ยน protection โดยอัตโนมัติ.
- ก่อน merge ใช้ PR merge candidate กับ main ล่าสุดตาม required protection จริง;
  หาก base เปลี่ยนจน candidate ไม่เป็นปัจจุบัน ต้องอัปเดตและผ่าน required CI ใหม่.
  ไม่อ้างผลบน head เก่าแทน candidate ที่จะ merge.

## E2E และ environment

**Amendment Approved 2026-11-11:** ใช้ [runner DNS recovery amendment](runner-dns-amendment.md)
เพิ่ม known-config Ubuntu mirror preparation เฉพาะ e2e-run ก่อน Playwright install.
นี่เป็นข้อยกเว้นจากการคง execution block ทุกตัวอักษรเฉพาะ bootstrap ใหม่นี้;
คำสั่ง test/browser, services, env, assertions และ workers อื่นคง baseline เดิม.
ใช้ `.github/scripts/prepare_e2e_apt.py` กับ fixture tests ใน
`.github/tests/test_e2e_apt.py`; คง layout ที่รองรับตาม amendment และ fail closed
เมื่อ layout/permissions ไม่พร้อม. ไม่มี infrastructure ถาวรหรือ application state เปลี่ยน.

รอบแรกคง E2E แบบเรียงชุดใน worker เดียวและ services เดิม. ยังไม่แยก E2E ขนาน
เพราะ fixtures ปัจจุบันมี shared mutable state และยังไม่มีหลักฐาน isolation ระหว่างชุด.
นี่เป็น fallback ตาม RQ-08; ไม่เพิ่ม workers หรือคัดลอกระบบ bootstrap เพื่อเร่งโดยพลการ.
ไม่แชร์ DB/Redis ของ CI กับ development environment. หากต้องแยกขนานภายหลัง
ต้องเสนอ amendment พร้อมหลักฐาน isolation ก่อนเปลี่ยนแผนนี้.

## ไฟล์ที่จะเปลี่ยน

- `.github/workflows/ci.yml`: triggers/concurrency/selection/workers/verdicts/manual mode.
- `.github/scripts/ci_selection.py`, `.github/scripts/ci_verdict.py`: policy helpers.
- `.github/tests/test_ci_selection.py`, `.github/tests/test_ci_verdict.py`:
  test matrix สำหรับการเลือกและการป้องกัน false success.
- `specs/features/2026-10-26-ci-feedback-time/evidence/checkpoint.md`:
  บันทึก diff/checks/ผลจริงและ pending pilot; อัปเดต roadmap เฉพาะสถานะงานนี้.
- ไม่เปลี่ยน venue-contract workflow, application tests/assertions หรือ trading code.
- ไม่มี migration, application session storage หรือ persistent business data เปลี่ยนแปลง;
  ไม่เพิ่ม Redis/infrastructure และไม่ใช้ cache เป็นหลักฐานแทน required checks.

## Branch และงานที่ค้างอยู่

ก่อน implementation สร้าง branch/worktree แยก `feat/ci-feedback-time` จาก committed
baseline ที่บันทึก SHA ไว้; ตรวจสถานะจริงใหม่ ไม่ยึดว่ารายการค้างเมื่อ 2026-10-26
ยังเหมือนเดิม. ไม่ stash/reset/commit หรือคัดลอกงานอื่นใน working tree โดยพลการ.
เก็บ inventory ของ jobs/commands/services และ diff ของ workflow ที่มีอยู่ก่อนแก้
รวม F-17/F-18/F-19 และ isolated migration/global-state guards ที่อยู่ใน baseline จริง.
หากมี workflow hunks ของงานอื่นที่ยังไม่ committed ให้บันทึก integration dependency;
ตรวจ selector/verdict wiring และรักษาคำสั่งเดิมบน final combined candidate เมื่อพร้อม.
ส่วนที่ยังไม่รวมต้องคง Pending ไม่อ้างว่าตรวจแล้ว และไม่ merge/cherry-pick งานอื่นเอง.

## ความเสี่ยงและการตรวจ

ความเสี่ยงหลักคือข้าม tests ที่จำเป็นหรือ required check เขียวเท็จจาก skipped dependency.
พิสูจน์ด้วย selection matrix, mixed/renamed/deleted paths และ verdict failure matrix.
ไม่ทดสอบด้วยการส่ง Live orders หรือรัน workload หลายชั่วโมง.
การเพิ่ม verdict jobs มี runner startup overhead; ยังไม่อ้างว่าลด wall time เท่าไร
จนมีผล pilot. ถ้าประโยชน์ไม่คุ้ม ต้องรายงานก่อนขยาย scope.

## Checkpoints

1. หลังอนุมัติ plan/validation: branch/worktree แยก, implementation และ targeted helper tests.
2. แจ้ง **Ready for Code Review** พร้อม tests/pending/risks ทันทีเมื่อครบ implementation;
   หยุดรอ `review code` ก่อนเริ่มรีวิว ไม่ถือว่าการแจ้งเป็นคำสั่ง review/แก้/refactor.
3. เมื่อได้รับคำสั่ง review ให้รีวิวและแก้ findings แล้วตรวจ affected cases;
   ใช้จุดถาม refactor ตาม AGENTS.md และรอคำตอบก่อนขั้นนั้น.
4. ตรวจ workflow ด้วย actionlint และ helper tests, diff/static safety inventory และ
   validation ระดับ Feature ที่ทำในเครื่องได้; ไม่รัน application full regression
   เพียงเพื่อพิสูจน์การจัดคิว. รวมเอกสาร/หลักฐานก่อนเสนอ commit/push/PR/dispatch.
5. เมื่อเจ้าของสั่ง Git ให้ทำ pilot และติดตาม required CI ของ SHA ล่าสุดจนจบ;
   ก่อน merge ต้องผ่าน Feature gates ที่ถึงกำหนดและ required CI แล้วรอคำสั่ง merge.
   หลัง merge ตรวจ main ครบชุดเดิมและติดตามจนจบ; manual full ที่เรียกได้หลัง workflow
   อยู่บน default branch และเกณฑ์ที่ยัง Pending ต้องผ่านก่อนเรียกงาน Completed.
6. Release ใช้ manual full mode เมื่อได้รับคำสั่ง และเกณฑ์ release เดิม;
   งานนี้ไม่เพิ่ม workload/endurance อัตโนมัติหรือแทนเกณฑ์ feature อื่น.

## สถานะการปรับเอกสาร

เจ้าของอนุมัติ plan/validation ฉบับปรับ 2026-11-11 แล้ว ให้เริ่ม implementation
บน branch/worktree แยกตามแผนนี้ได้. Requirements ที่ Approved เดิมคงไว้; การอนุมัติ
แผนไม่ใช่คำสั่ง commit, push, เปิด PR, dispatch หรือ merge.

## อ้างอิง semantics

- [GitHub workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)
- [Required status checks troubleshooting](https://github.com/github/docs/blob/main/content/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks.md)
