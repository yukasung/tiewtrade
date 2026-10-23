# F-01 follow-up — Self-hosted CI — Validation

สถานะ: **Retired (2026-10-24)** — ไม่ใช้แนวทาง self-hosted ต่อ; ดู [closure checkpoint](evidence/closure-checkpoint.md).
เนื้อหาและผลตรวจด้านล่างเป็นประวัติ ไม่ใช่คำสั่งให้ทำต่อหรือผล validation ผ่าน.

ประวัติการอนุมัติ: **Approved** — เจ้าของอนุมัติพร้อม plan และ F-35 storage amendment วันที่ 2026-10-23
วันที่: 2026-10-23
Requirements: [Approved CI-01..12](requirements.md)

## เสร็จหมายถึงอะไร

| # | เกณฑ์และวิธีพิสูจน์ | ระยะรัน | ผล |
|---|---|---|---|
| SC-01 | Policy matrix: feature push ไม่ auto-run; PR open/update/reopen/ready full 6 jobs, main push/manual full 6; job IDs/names/needs/commands/test selection เดิมครบ | development static/unit + pilot events | Not Run |
| SC-02 | PR revision supersession cancel เฉพาะ PR เดียว; main/manual/venue ไม่ถูก PR cancellation; SHA ที่ canceled/pending ไม่ถูกนับ Passed | unit + actual cancellation | Not Run |
| SC-03 | ทั้ง 7 jobs ในสอง workflows ใช้เฉพาะ self-hosted Linux labels; ไม่มี hosted fallback, remote caches หรือ artifact upload; GitHub logs/summary และ local reports ยังมี | static + pilot evidence | Not Run |
| SC-04 | Host/runtime preflight: ARM64/OS/tool checks, CPU/RAM/disk budget, checksum verification; insufficient resources/unknown VM paths ต้อง fail ก่อน register/side effect | unit + provision smoke | Partial — hardware/Lima 2.2.1/pinned image/VM create ผ่าน; boot smoke Failed จาก control SSH ถูก loopback policy บล็อก ยังไม่ยืนยัน guest Docker/capacity |
| SC-05 | Fresh VM ไม่มี host mounts/socket/SSH-agent/env; เข้า host/LAN/dev DB ไม่ได้ตาม policy, public package/GitHub endpoints ได้; service containers จริงทำงานบน guest daemon | provision smoke, host/guest evidence | Partial/Failed — effective config ผ่าน boundary checks แต่ control channel ใช้งานไม่ได้ภายใต้ policy; ยังไม่รัน guest canary/bypass/containers และ NC-52 ยังเปิด |
| SC-06 | Reject wrong repo/visibility/event/path/SHA/attempt/actor, fork/untrusted queued workflows และ offline/expired registration; ไม่มี long-lived credential ใน guest/log/git | unit + safe registration/security smoke | Not Run |
| SC-07 | One active VM/job: CI กับ venue แข่งกันแล้ว lock serialize; job ports และ Compose names ไม่ชน; launcherไม่รับ target/path จาก PR output, stale lock ไม่ทำให้ล้างงานอื่น | unit + controlled contention | Not Run |
| SC-08 | Success/failure/cancel/timeout/Ctrl-C/reboot reconciliation: runner removed/disabled, logs exported, VM resources ล้างเฉพาะ manifest; cleanup/export failure บล็อกงานใหม่ | fault injection + guest smoke | Not Run |
| SC-09 | Dirty workspace/file/container/volume canary ไม่อยู่ใน VM ของ job ถัดไป; canary บน host/development services ไม่ถูกแก้/ลบ; ไม่ใช้ global prune | two-job reuse regression | Not Run |
| SC-10 | Pilot GitHub run ของ candidate จริงครบ 6 jobs success รวม full backend/frontend, contracts, imports, actual-role DB migration และ browser E2E; บันทึก exact head/merge SHA และ runner versions | stable candidate ก่อน merge | Not Run |
| SC-11 | Controlled failing job ต้องเป็น Failed ไม่กลายเป็น green; cancellation ไม่ทิ้ง workers/services; runner offline คง queued ไม่ลด gates หรือ fallback | pilot failure/cancel/offline | Not Run |
| SC-12 | Venue workflow คง cron/manual, public-only requests และ verdict pass/unavailable-skip/contract-failure; routing/log/summary ทำงานและไม่เป็น merge gate | existing verdict unit + actual dispatch | Not Run |
| SC-13 | Logs/reports อยู่ local พร้อม run/attempt/job/SHA, permissions จำกัด, ไม่มี credential canary; capacity cap บล็อกงานใหม่; export failureไม่ลบ evidence; ไม่มี paid storage side effect | unit + pilot artifact inspection | Not Run |
| SC-14 | After owner-authorized merge, main merge SHA ผ่าน 6/6 จริงบน runner ใหม่; ไม่มี foreign resources/runner ค้าง; เก็บ Billing failures เก่าและไม่ certify Live/F-12/F-11 gates เพิ่ม | post-merge checkpoint | Not Run |

## เลือกตรวจตามผลกระทบ

- Diff เปลี่ยน execution environment/dispatch/isolation ไม่เปลี่ยน application behavior;
  unit tests เน้น policy/manifest/cleanup/trust เพราะ workflow green เพียงอย่างเดียวไม่พิสูจน์
  ว่า runner ปลอดภัย. ไม่เพิ่ม tests สูตรเงินซ้ำ แต่ full safety regressions เดิมต้องผ่านใน SC-10.
- ใช้ fake GitHub/VM subprocess responses สำหรับ wrong SHA, token/log redaction,
  unsafe paths, partial failures และ cancellation ใน host launcher; tests ไม่รัน sudo,
  ไม่ลงทะเบียนจริงและไม่ลบ VM/host directories.
- Parse YAML ด้วย parser ที่รองรับ GitHub Actions semantics; static assertions เทียบ
  baseline `51f0e27` ว่าด่าน/commands เดิมครบ ไม่ใช่แค่ค้นชื่อไฟล์. ตรวจ workflow syntax
  ด้วย actionlint รุ่นที่ตรวจสอบแล้วใน guest; ไม่เพิ่ม application runtime dependency.
- ก่อน pilot รัน focused gate tests, Ruff/format/mypy ที่ครอบ launcher/tests และ shell/config
  checks ที่เกี่ยวข้อง. Full backend/frontend/build/contracts/E2E รันเมื่อ candidate นิ่งใน SC-10;
  หลัง fix ให้รันซ้ำส่วนที่ผลได้รับผลกระทบตาม testing §7.
- Performance/workload V-17/F-11 ไม่รันใหม่สำหรับการย้าย runner โดยอัตโนมัติ และไม่ใช้
  เวลา CI บนเครื่องใหม่แทน accepted workload metrics. หากต้องเปลี่ยน harness/resource
  assumptions ให้ประเมินผลกระทบ/ขออนุมัติก่อน ไม่ลด threshold.

## Manual acceptance / evidence

1. Owner ตรวจ isolated VM/no shared host Docker/no production credentials และ resource budget.
   รับทราบ serial-job runtime/เครื่องต้องเปิด และอนุมัติ F-35 storage amendment ใน plan §5;
   เกณฑ์นี้ยังไม่ผ่านเพียงเพราะเอกสารมีไฟล์ครบ.
2. ตรวจ run ID/attempt/SHA/actor/workflow diff ก่อนเปิด supervised runner;
   บันทึก GitHub check URLs ทั้ง 6 กับ environment manifest โดยไม่บันทึก registration tokens.
3. ทดลองอย่างน้อยหนึ่ง full successful candidate run และ controlled failure/cancel/recovery,
   รวมรอบ job ใหม่ที่พิสูจน์ clean state; ไม่ถือ targeted tests แทน full six checks.
4. ตรวจ venue route/summary โดยเฉพาะ public endpoints ที่อนุมัติเดิม ไม่มี API key/Live order.
   หากต้นทาง unavailable ให้เก็บ verdict จริง ไม่อ้าง contract ผ่านจาก skip.
5. หลัง merge ตรวจ exact main merge SHA และ cleanup อีกครั้ง. GitHub billing ปฏิเสธ
   dispatch หรือเครื่องไม่พร้อมให้คง Failed/Pending ไม่ forge status หรือซื้อ quota.

ผลทุกข้อเริ่ม **Not Run**; รอบนี้เป็นเอกสารเท่านั้น ยังไม่ติดตั้ง/ลงทะเบียน runner,
แก้ workflows, commit/push หรือเปลี่ยน Billing. Required gates/owner Git commands ยังบังคับเดิม.

Checkpoint หลังอนุมัติ: SC-04 เปลี่ยนเป็น Partial จาก read-only preflight เท่านั้น;
NC-52 บล็อก network recipe/activation ตาม plan. ไม่มี application/workflow code เปลี่ยน
จึงตรวจ approval/status/evidence consistency และ `git diff --check` ไม่รัน application
tests/lint/types ที่ inputs ไม่เปลี่ยน. ไม่มีข้อใดได้รับ Passed จากการอนุมัติเอกสารเพียงอย่างเดียว.

Network design follow-up: เจ้าของอนุมัติการออกแบบเพิ่มเติมแล้ว; เกณฑ์ NI-01..07 ใน
[amendment ที่เสนอ](network-isolation-amendment.md) เป็น **Not Run** ทั้งหมด.
SC-05 และ NC-52 ยังไม่ผ่านจาก static documentation research; ไม่ได้แก้ OS หรือติดตั้ง runtime.

Bounded-proof checkpoint หลัง owner อนุมัติ: host-only PF identity probe รันจริงแล้ว
ตาม [amendment checkpoint/raw evidence](network-isolation-amendment.md#host-identity-probe-checkpoint--partial-ไม่ใช่-guest-isolation-ผ่าน).
NI-01/02/05/07 มีหลักฐาน **Partial เฉพาะ synthetic host TCP probe**;
NI-03/04/06 และ guest/proxy/LAN scope ยัง Not Run. Focused safety tests 18 ผ่าน,
Ruff/format และ mypy 2 files ผ่าน. คืน active PF/root rules เดิมแล้ว แต่ kernel เก็บชื่อ
owned empty anchor ไว้โดยไม่มี rules/root hook; ไม่ใช้ global flush เพื่อลบชื่อ.
SC-05 และ NC-52 ยังไม่ผ่าน; ไม่มี VM/runner/workflow activation และไม่รัน application suite
ซ้ำสำหรับ helper ที่ไม่ได้เปลี่ยน application inputs.

Checkpoint ต่อมา: สร้าง VM และทดลอง boot ภายใต้ policy แล้ว **Failed** ที่ control channel;
Lima ยังต่อ `127.0.0.1:53071` แม้ตั้ง SSH over vsock. NI-04 **Failed**, NI-01/07
มีหลักฐานเพิ่มแบบ **Partial**; NI-02/03/05/06 ยังไม่ครบตาม scope. ไม่เพิ่ม broad loopback
exception. ยืนยัน VM Stopped ก่อน recovery; คืน root filter/NAT/Apple references เดิม,
release own PF reference แล้ว PF Disabled/states=0. Original failed journal ไม่ถูกเขียนทับ;
[diagnostic/recovery](evidence/vm-policy-diagnostic.md) เก็บแยก. Focused tests **36 passed**,
Ruff/format/mypy 4 files และ `git diff --check` ผ่าน. เก็บบัญชี/VM แบบ stopped เพื่อทำ
bounded proof ต่อ; ยังไม่ครบ rollback account/home ทั้งชุด ไม่ปิด NI-07 หรือ NC-52.
