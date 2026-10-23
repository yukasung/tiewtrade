# F-01 follow-up — Self-hosted CI — Plan

สถานะ: **Retired (2026-10-24)** — ไม่ใช้แนวทาง self-hosted ต่อ; ดู [closure checkpoint](evidence/closure-checkpoint.md).
เนื้อหาและผลตรวจด้านล่างเป็นประวัติ ไม่ใช่คำสั่งให้ทำต่อหรือผล validation ผ่าน.

ประวัติการอนุมัติ: **Approved** — เจ้าของสั่ง `อนุมัติ plan/validation self-hosted CI รวม F-35 storage amendment`
วันที่ 2026-10-23; ห้ามลด isolation หรือเปลี่ยนแนวทางที่อนุมัติโดยไม่ขออนุมัติใหม่
วันที่: 2026-10-23
Requirements: [Approved](requirements.md)
Validation: [เกณฑ์ก่อนลงมือ](validation.md)
Branch: `docs/self-hosted-ci-spec`

## 1. แนวทางและขอบเขต

คง GitHub Actions และทั้ง 6 check names เดิม เปลี่ยนเฉพาะ runner, triggers,
การเก็บหลักฐาน และ lifecycle ของเครื่อง CI. ไม่สร้าง CI engine ใหม่หรือ autoscaling service.
ใช้ operator-supervised launcher บน Mac ที่ยืนยัน run/commit ก่อนเปิด runner;
หนึ่ง Linux VM และหนึ่ง ephemeral runner รับได้หนึ่ง job แล้วทำลาย VM ก่อน job ถัดไป.
งาน 6 jobs จึงรันตามคิว ไม่ได้ข้าม `needs` ของ GitHub หรือรวม jobs เป็น check เดียว.
ข้อแลกเปลี่ยน: รวมเวลาอาจนานกว่า hosted jobs ที่รันขนาน และเครื่องต้องเปิดพร้อม operator
เพื่อรับงาน; schedule เดิมยังสร้าง run ได้แต่เมื่อเครื่องปิดให้คง queued ไม่อ้างว่าได้ตรวจรายวันแล้ว.

ข้อเสนอสภาพแวดล้อม: Lima + Apple VZ, Ubuntu 24.04 ARM64, Docker Engine/Compose
ใน guest; ไม่ใช้ macOS runner สำหรับ service containers. VM เริ่มที่ 4 vCPU/4 GiB RAM/
60 GiB disk, active สูงสุดหนึ่ง VM/หนึ่ง job รวมทั้ง CI และ venue-contract.
ตัวเลขนี้เป็น resource budget ไม่ใช่ข้ออ้างว่าผ่าน capacity test แล้ว.

ก่อนติดตั้งต้องอ่าน CPU/RAM จริง (sandbox รอบแผนอ่าน sysctl ไม่ได้), ตรวจ host RAM
อย่างน้อย 8 GiB, เหลือให้ host อย่างน้อย 4 GiB และ disk ว่างอย่างน้อย 80 GiB.
พบ Mac arm64 และ disk ว่างประมาณ 159 GiB; ยังไม่ได้ตรวจ RAM หรือรับรองเครื่องพร้อม.
หาก preflight ไม่ผ่านให้หยุด ไม่เพิ่มทรัพยากร/ซื้อเครื่องหรือเปลี่ยน runtime เอง.
ไม่ขยายงานไป VPS/cloud, Kubernetes, runner scale sets หรือบริการเสียเงิน.

## 2. Isolation / trust boundary

- VM ไม่มี host home/repo mounts, SSH-agent forwarding, host Docker socket,
  cloud credentials หรือ production/development env files. ปิด default Lima mounts
  และ port forwards; SSH สำหรับควบคุม VM จำกัดบน host เท่านั้น.
- Docker daemon และทุก PG/Redis/Compose volume อยู่ใน guest ของ job นั้น;
  checkout ลง guest disk ไม่ใช้ worktree ของเจ้าของ. Docker group ถือว่ามี root-equivalent
  ภายใน VM จึงห้ามนำ VM นี้ไปร่วมใช้กับข้อมูลอื่น.
- แยก network ของ CI และปิดทางเข้าจาก guest สู่ host/LAN/development DB ด้วย
  host-enforced policy ที่จำกัดเฉพาะ VM นี้. ไม่แก้ firewall ทั้งเครื่องแบบกว้าง;
  ถ้า runtime บังคับ isolation นี้ไม่ได้ ให้หยุดเสนอทางเลือกก่อนเริ่ม workflow code.
  ออกอินเทอร์เน็ตได้เพื่อ GitHub/registries/package downloads; venue job ใช้ public endpoints เดิม.
- ไม่ติดตั้ง persistent runner service. Launcher ใช้เฉพาะ source ที่ review แล้วจาก
  trusted host checkout; ห้ามรัน launcher/provisioning code ที่ดึงจาก untrusted PR.
- ก่อนสร้าง VM ตรวจผ่าน GitHub API: repo ตรง `yukasung/tiewtrade`, private,
  workflow path ตรงสองไฟล์ที่กำหนด, run ID/attempt/SHA/event และผู้เริ่มงานตรง owner
  `yukasung`. PR ต้องมาจาก repo เดียวกันและ owner ตรวจ workflow diff แล้ว.
  Fork/bot/ผู้ใช้ใหม่ไม่อยู่ allowlist ต้องหยุดให้ owner review ไม่ใช่ auto-approve.
- ใช้ labels เฉพาะ repo และ `run ID + attempt`; labels เป็นการ route ไม่ใช่ security boundary.
  ก่อนเปิด runner ต้องไม่มี untrusted queued job ที่สามารถใช้ labels เดียวกัน;
  ตรวจสิทธิ์ผู้เขียน workflows และ fork approval settings. หากยืนยัน trust policy ไม่ได้
  ห้ามลงทะเบียน runner. VM isolation ยังจำเป็นแม้ repo เป็น Private.
- `permissions: contents: read`, checkout `persist-credentials: false`, ไม่ใช้
  `pull_request_target`. Long-lived GitHub credential คงใน host credential store;
  ส่งเพียง short-lived registration token เข้า guest โดยไม่ลง log/git หรือแสดงบน host argv.
  package runner/image และ checksum ถูกตรึงใน manifest หลังตรวจ official releases.

## 3. Lifecycle และชนกันของ resources

Launcher รับ run ID ที่ operator อนุมัติ ไม่ scan/execute ทุก queued workflow เอง.
ใช้ host lock เดียวครอบ lifecycle ของสอง workflows; lock มี owner identity ไม่ลบ
stale lock หรือฆ่า process ที่ไม่ใช่ของ run นี้โดยเดา.

ลำดับต่อ job: preflight/trust check → fresh VM จาก clean base ไม่มี credentials →
register `--ephemeral` → รับหนึ่ง job → export sanitized logs/results → ยืนยัน job
สิ้นสุด/runner ถูกถอดทะเบียน → ลบเฉพาะ VM/disk/credentials ของ job ที่ระบุแน่นอน.
จากนั้นจึงสร้าง VM ใหม่ให้ job ถัดไปจน run จบ. ไม่ reuse VM ที่เคยรัน workflow.
Clean base เก็บ tooling/image downloads ได้ แต่ห้าม snapshot หลัง registration/checkout.

ก่อนเริ่มมี manifest บันทึก run/attempt/job/VM name/runner ID และ resource paths;
host process ไม่รับ path สำหรับลบจาก output ของ PR. Cleanup failure ต้องบล็อกงานถัดไป.
Success/failure/cancel/timeout/Ctrl-C ใช้ cleanup เดียวกัน; host reboot/sleep ต้อง reconcile
จาก manifest และ GitHub state ก่อนรับงานใหม่ ไม่เดาว่างานที่หายคือผ่าน.
เฉพาะ resources ของ VM นี้ถูกลบ ไม่มี global `docker prune`, host Compose down หรือ
recursive delete ที่ home/workspace. หาก export logs ล้ม ให้หยุด runner/VM และ quarantine
disk โดยไม่รับงานใหม่จนกู้หลักฐาน/cleanup ได้.

คง fixed ports 5432/6379/8000/5173 ใน guest เดิมได้ เพราะไม่มี guest reuse และมีหนึ่ง
active VM. Compose project ใช้ run/attempt/job identity แทนชื่อ project จาก path ปริยาย;
ทุก up/logs/down ใช้ชื่อเดียวกัน. ยังรักษา service cleanup และ `if: always()` เดิม.

## 4. Trigger matrix / concurrency

| เหตุการณ์ | CI ที่ต้องเกิด |
|---|---|
| Push feature branch ยังไม่มี PR | ไม่ auto-run; local checks หรือ manual dispatch |
| PR เปิด, synchronize, reopen, ready for review | full 6 jobs หนึ่ง run ต่อ event ไม่เกิด push duplicate |
| PR revision ใหม่แทน revision เก่า | cancel เฉพาะเก่าของ PR เดียวกัน; cleanup ก่อน VM ถัดไป |
| Push main หลัง merge | full 6 jobs ของ merge SHA; ไม่ cancel main เพราะ PR ใหม่ |
| Manual dispatch | full 6 jobs บน ref ที่ operator ตรวจ SHA/trust แล้ว |
| Venue schedule/manual | workflow เดิม แยกจาก merge gates และใช้ host lock เดียวกัน |

ใช้ workflow-level concurrency แยก PR number / main / manual run identity;
cancel-in-progress เฉพาะ PR. ไม่ใช้ paths filters หรือ job skips เพื่อลดการตรวจ.
Main อาจแทนที่ pending run ตาม GitHub concurrency semantics; ถ้าเกิดต้อง dispatch SHA
ที่ขาดใหม่และเก็บสถานะ superseded ไม่ถือว่า SHA นั้นผ่าน. ไม่ใช้ green จาก SHA เก่า.
Offline ไม่มี matching runner ให้คง queued ไม่ fallback ubuntu-latest หรือ mark success.

## 5. Storage และหลักฐานไม่เสียค่า GitHub เพิ่ม

ปิด remote setup-uv/setup-node Actions caches และไม่เรียก upload-artifact ในสอง workflows.
คง test commands และ GitHub job logs/step summaries. Export Playwright report,
venue-contract outputs, runner diagnostic logs และ manifest ไป host evidence directory
เฉพาะงาน เช่น `.local-ci/evidence/<run>/<attempt>/<job>/` (gitignored, mode จำกัดเจ้าของ).
ไม่คัดลอก `.credentials`, runner registration files, raw env หรือ database dumps.
เก็บอย่างน้อย 7 วันและตรึง accepted checkpoint จน owner อนุญาตจัดเก็บ/ลบ;
soft cap 2 GiB สำหรับ unarchived evidence: เต็มให้หยุดก่อนงานใหม่ ไม่ลบหลักฐานเอง.
ไม่ใช้ paid external log/storage service. ค่าไฟ/เน็ต/disk ของ host ยังมีอยู่.
การลบ artifacts เก่าหรือเปลี่ยน account billing ไม่อยู่ในงานนี้.

**Storage amendment ที่เสนอพร้อมแผนนี้:** F-35 `plan.md` §6 ข้อแสดงผลลัพธ์ 3
กำหนดแนบไฟล์เป็น GitHub artifact. ข้อเสนอนี้แทนเฉพาะที่เก็บไฟล์ด้วย local evidence
ผูก run/attempt/job และบอกตำแหน่งรายงานใน summary; คง raw public-response evidence,
verdict และ summary เดิม. ต้องให้ owner อนุมัติ amendment นี้พร้อม plan/validation
ก่อนแก้ workflow และจึงเพิ่ม cross-reference ใน F-35 spec โดยไม่ลบประวัติเดิม.
ยังไม่ถือว่า local artifact ทำให้เข้าถึงรายงานจาก GitHub UI ได้เหมือนเดิม.

## 6. ของเดิมที่จะใช้ซ้ำ / ไฟล์ที่จะแก้

| Path | ใช้ซ้ำ / เปลี่ยน |
|---|---|
| `.github/workflows/ci.yml` | คง job IDs/names, needs, lint/types/imports/pytest, schema generation, browser E2E, Compose smoke; แก้ labels/triggers/concurrency/permissions/storage เท่านั้น |
| `.github/workflows/venue-contract.yml` | คง schedule/manual/public-only verdict/summary; เปลี่ยน runner/storage และ serialization |
| `config/postgres.env`, `backend/db/bootstrap/`, `backend/uv.lock`, `frontend/package-lock.json`, `compose.yaml` | ใช้เวอร์ชัน/bootstrap/commands เดิม ไม่เปลี่ยน business config |
| `.ci/self-hosted/` (ใหม่) | VM template/tool manifest และ host launcher stdlib Python ขนาดเล็ก; ไม่มี application dependency ใหม่ |
| `backend/tests/gates/` | เพิ่ม focused launcher/policy tests ตามรูปแบบ gate tests เดิม; ใช้ fakes ไม่ต่อ GitHub จริงใน unit tests |
| `.gitignore`, `specs/standards/testing.md`, F-01/F-35 spec references | ignore local evidence; ระบุ approved trigger/storage amendments โดยไม่เปลี่ยนเกณฑ์ checks |
| โฟลเดอร์ spec นี้ / roadmap | runbook, acceptance evidence และสถานะตามผลจริง |

ไม่มี migration/application/API contract/financial calculation change.

## 7. Checkpoints / rollback

1. **หลัง plan/validation Approved:** implement policy/launcher/template + unit/static
   checks โดยยังไม่ลงทะเบียน runner. Review cancellation/trust/deletion targets ก่อนทดลองจริง.
2. **Provision smoke:** owner อนุมัติ OS permission เมื่อจำเป็น ติดตั้งเฉพาะ runtime
   ที่เสนอ, fresh guest, Docker/tool/ARM64 smoke และ isolation/failure cleanup.
   หยุดทันทีถ้าต้องเพิ่มงบ/เปิด host mounts/เปลี่ยน security boundary.
3. **Pilot:** owner สั่ง commit/push/เปิด PR ตามกฎ Git; ตรวจ workflow diff แล้วใช้
   operator-supervised runner บน candidate run. ผ่าน full 6 jobs และ failure/cancel/reuse checks.
   ทดสอบ GitHub dispatch จริงก่อนรับรองว่าแก้ Billing block ได้; ไม่ rerun ซ้ำถ้ายังถูกปฏิเสธ.
4. **Merge checkpoint:** owner สั่ง merge หลัง gates ครบ; ตรวจ main merge SHA ด้วย runner
   ใหม่ครบ 6 jobs จึงปิดงาน. Venue workflow ต้องพิสูจน์ routing/summary/verdict แยกต่างหาก.

Rollback: หยุดสร้าง VM ใหม่, cancel เฉพาะ run ที่เกี่ยวข้อง, เก็บหลักฐานและล้าง resources
ตาม manifest; revert workflow ด้วย PR/คำสั่ง Git เจ้าของ ไม่ enable paid runner เอง.
Workflow เก่าก่อน migration ยังคงอ้าง runner เดิม: main `51f0e27` run 39972554569
คง Failed จาก Billing. ห้ามเปลี่ยนประวัติเป็น Passed หรือใช้ผล revision ใหม่แทน SHA เก่า.

## แหล่งอ้างอิง (ตรวจ 2026-10-23)

- [Lima VZ](https://lima-vm.io/docs/config/vmtype/vz/) และ [mounts](https://lima-vm.io/docs/config/mount/).
- [GitHub ephemeral runners](https://docs.github.com/en/actions/reference/runners/self-hosted-runners):
  one job/deregistration และต้อง export diagnostic logs ก่อนล้าง environment.
- [Workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax):
  trigger/concurrency/permissions semantics. ราคาหรือ dispatch eligibility ไม่ถือเป็นค่าคงที่;
  ตรวจจริงตาม requirements ก่อน activation.

## Implementation preflight — 2026-10-23 / NC-52 Needs Clarification

- ตรวจแบบ read-only: macOS 15.6.1/arm64, RAM 8 GiB, CPU 8 logical cores;
  disk ว่างที่ตรวจในขั้นแผนประมาณ 159 GiB. Hardware ผ่านค่าขั้นต่ำที่กำหนด
  แต่ยังไม่มี provision/capacity/isolation smoke. มี Homebrew; ยังไม่ได้ติดตั้ง Lima.
- `brew info --json=v2 lima` ให้ stable **2.2.1**. Template ของรุ่นนี้ไม่มี
  `networkOpts.hostLoopback`; upstream อธิบาย default guest→host loopback access
  ใน [issue #5574](https://github.com/lima-vm/lima/issues/5574).
- [Upstream template](https://github.com/lima-vm/lima/blob/master/templates/default.yaml)
  เพิ่ม hostLoopback สำหรับ v2.3 แต่ระบุว่าไม่ได้บล็อก host LAN IP.
  [user-v2 egress policy #4326](https://github.com/lima-vm/lima/pull/4326) ยังเป็น draft
  ณการตรวจ. จึงยังไม่มี verified recipe ของ stable runtime ที่ทำ host-enforced
  isolation ครบตาม §2. ไม่ได้พิสูจน์ว่า host-side filtering ทุกแบบทำไม่ได้;
  แต่ห้ามอ้างว่าปลอดภัยเพียงปิด mounts/port forwarding หรือใช้ guest firewall
  ที่ job ซึ่งมี Docker/root สามารถแก้ได้.
- **NC-52 บล็อก:** การเลือกและติดตั้ง network boundary, workflow/runner activation
  และ SC-05/06/10..14. หยุดก่อนสร้าง workflow/launcher ที่สมมติว่า isolation ผ่าน
  ตามเงื่อนไข §2. ไม่ติดตั้ง package, สร้าง VM, ลงทะเบียน runner หรือแก้ Billing.
- ขอ owner เลือกแนวทางถัดไป: อนุมัติ design amendment สำหรับ host-enforced network
  sandbox ที่ scope เฉพาะ CI (รวมพิจารณา dedicated macOS identity หากจำเป็น)
  โดยยังไม่เปลี่ยน account/firewall จน recipe และ validation ได้รับอนุมัติ;
  หรือใช้ Linux host ที่แยกจาก development อยู่แล้วและออกแบบ network boundary ของ host นั้น.
  ไม่ซื้อบริการ ไม่ใช้ unreleased fork และไม่ยกเลิกข้อห้าม guest→host/LAN เอง.

### NC-52 design follow-up

เจ้าของอนุมัติให้ออกแบบ sandbox เพิ่มด้วยคำสั่ง `approve` หลัง preflight;
จัดทำ [network isolation amendment](network-isolation-amendment.md) เป็น **Proposed**.
เสนอ dedicated non-admin identity + scoped PF proof และเกณฑ์ NI-01..07;
ยังไม่อนุมัติ account/firewall mutations หรือรับรองว่า PF UID filtering ครอบทุก path.
NC-52 จึงยังบล็อก activation ตามเดิม. ไม่มี VM/package/runner/workflow changes ในรอบนี้.
ต่อมา owner อนุมัติ bounded proof; เพิ่ม helper/tests และผ่าน synthetic host TCP identity
probe พร้อมคืน active PF/root rules เดิม ตาม [checkpoint](network-isolation-amendment.md#host-identity-probe-checkpoint--partial-ไม่ใช่-guest-isolation-ผ่าน).
ยังไม่ครบ guest/proxy/protocol/LAN/lifecycle scope และยังไม่ปิด NC-52.

Bounded VM follow-up: Lima 2.2.1/pinned image/VM create เสร็จแล้ว; effective isolation
config ตรวจผ่าน แต่ boot smoke ภายใต้ PF **Failed** ที่ control loopback SSH.
หยุด VM/reconcile owned policy แล้ว ไม่เพิ่ม broad exception และไม่ลงทะเบียน runner.
ใช้ [checkpoint/งานค้างเดิม](evidence/vm-policy-diagnostic.md) ทำ control-channel proof ต่อ;
ไม่เริ่ม requirements/plan ใหม่หรือรัน application full workload ที่ inputs ไม่เปลี่ยน.
