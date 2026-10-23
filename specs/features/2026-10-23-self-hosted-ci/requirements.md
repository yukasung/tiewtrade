# F-01 follow-up — Self-hosted CI และลดงานซ้ำ — Requirements

สถานะ: **Retired (2026-10-24)** — ไม่ใช้แนวทาง self-hosted ต่อ; ดู [closure checkpoint](evidence/closure-checkpoint.md).
เนื้อหาและผลตรวจด้านล่างเป็นประวัติ ไม่ใช่คำสั่งให้ทำต่อหรือผล validation ผ่าน.

ประวัติการอนุมัติ: **Approved** — เจ้าของสั่ง `อนุมัติ requirements self-hosted CI` วันที่ 2026-10-23;
รวม CI-05 amendment เรื่อง triggers. ยังต้องอนุมัติ plan/validation ก่อน implementation
วันที่: 2026-10-23
Branch: `docs/self-hosted-ci-spec`

## ทำไมต้องมี

Repository เป็น Private และ post-merge CI ของ PR #25 ถูก GitHub ปฏิเสธก่อนเริ่ม jobs.
[Run 39972554569](https://github.com/yukasung/tiewtrade/actions/runs/39972554569)
attempts 1/2 แจ้ง failed payments หรือ spending limit; ข้อความนี้ยังไม่พิสูจน์ว่า
โควตาหมดหรือเป็นปัญหาชำระเงิน. เจ้าของไม่ต้องการจ่ายเพิ่มหรือเปิด repository เป็น Public.
CI เดิมรันทั้ง branch push และ pull_request ทำให้ commit เดียวถูกตรวจซ้ำ.

## ขอบเขต

- เตรียม CI บน Linux runner ที่เจ้าของควบคุม โดยรักษา GitHub Actions checks และ
  commands/coverage เดิม; ไม่ถือ local validation เป็นผลผ่านของ GitHub.
- ลด run ซ้ำโดยไม่ลด quality/security/trading safety gates.
- ไม่แก้ application, migration, trading logic, production deployment หรือเปิด Live.
- ไม่เพิ่มวงเงิน/วิธีชำระเงิน/บริการ cloud แบบมีค่าใช้จ่าย ไม่เปลี่ยน visibility.
- ไม่ติดตั้ง VM/runner, ลงทะเบียน runner หรือแก้ workflow ในขั้น requirements.

## ข้อกำหนดที่เสนอ

| รหัส | ข้อกำหนด | ที่มา |
|---|---|---|
| CI-01 | คง repository เป็น Private และไม่เปิด paid fallback โดยอัตโนมัติ; runner offline ให้แสดง queued/failed ไม่รายงานผ่าน | คำสั่งเจ้าของไม่จ่ายเพิ่ม; testing §1 |
| CI-02 | ใช้ Linux runner พร้อม Docker สำหรับ service containers; แยกจาก development/production data, credentials และ Docker daemon ของเครื่องพัฒนา | workflow services เดิม; security; GitHub service-container contract |
| CI-03 | คงครบ 6 jobs: PostgreSQL config, backend lint/types/imports/tests, frontend lint/types/tests, API contract, container smoke และ browser E2E. คงชื่อ checks และ assertions เดิม | F-01 RQ-6/8/9/16; testing §1 |
| CI-04 | คำสั่ง/versions/lockfiles/bootstrap/migrations ใช้ของเดิม; ไม่ลด test selection หรือ performance thresholds เพื่อให้ runner ผ่าน | F-01 RQ-9; testing §7 |
| CI-05 | เสนอแทน trigger ทุก branch push: รัน full CI สำหรับทุก PR ที่เปิด/อัปเดต, ทุก push เข้า main และ manual dispatch. Branch ที่ยังไม่มี PR ใช้ local checks หรือ manual dispatch ไม่อ้างว่าได้รับ GitHub CI อัตโนมัติ | คำสั่งลด CI ซ้ำ; amendment ต่อ F-01 ซึ่งต้องอนุมัติใหม่ |
| CI-06 | PR ใหม่ต้องมีผล CI ของ head/merge candidate ปัจจุบันก่อน merge; main ต้องมีผลของ merge commit จริง. ยกเลิกเฉพาะ PR revision ที่ถูกแทน ไม่ยกเลิก main gate เพียงเพราะมี PR ใหม่ | testing §1; ไม่ใช้ SHA เก่าแทนใหม่ |
| CI-07 | จำกัด runner เฉพาะ repo นี้และ trusted source; ไม่รัน fork/untrusted PR บนเครื่องเจ้าของโดยอัตโนมัติ, ไม่ใช้ pull_request_target checkout untrusted code และให้ token สิทธิ์น้อยสุด | security; GitHub self-hosted security guidance |
| CI-08 | ไม่ใช้ Live API keys/production secrets; registration token ห้ามลง git/log. แผนต้องกำหนด workspace/service/volume cleanup หลัง success/failure/cancel และการสร้างสภาพแวดล้อมสะอาดก่อนงานถัดไป | AGENTS.md; security; trading safety |
| CI-09 | ต้องควบคุม concurrent jobs/runs ไม่ให้ fixed ports 5432/6379/8000/5173 และ Compose project/volumes ชนกัน; cleanup ต้องไม่แตะ resources ของงานอื่น | backend/E2E services และ container job เดิม |
| CI-10 | ครอบคลุม venue-contract workflow เพื่อไม่เหลือ scheduled paid runner โดยไม่ตั้งใจ; คง schedule/manual และสถานะแยกจาก merge gates ตาม F-35 ไม่เพิ่ม Live requests | `.github/workflows/venue-contract.yml`; F-35 scope |
| CI-11 | เก็บ logs/evidence พร้อม SHA/runner versions และผล checks; กำหนด artifact/cache policy ไม่ให้ใช้ paid storage โดยไม่อนุมัติ. ค่าทรัพยากร/ไฟ/เน็ตเครื่องเจ้าของยังมี ไม่รับรองต้นทุนรวมเป็นศูนย์ | คำสั่งไม่จ่ายเพิ่ม; testing §7 |
| CI-12 | เก็บ failure ของ main `51f0e27` ไว้; ผลบน workflow revision ใหม่ไม่เปลี่ยนประวัติ SHA เก่าเป็น Passed. Rollout ต้องมี PR และ post-merge CI บน runner ใหม่ผ่านจริงก่อนปิด checkpoint | F-12 evidence; testing §7 |

## จุดอนุมัติและข้อมูลสำหรับขั้นแผน

CI-05 เปลี่ยนข้อกำหนด F-01 เรื่องทุก push และเจ้าของอนุมัติ amendment นี้แล้ว
2026-10-23. สถานะ Completed ของ F-01 เดิมไม่อนุมัติ implementation follow-up นี้โดยปริยาย.

หลังอนุมัติ requirements จึงจัดทำ plan/validation ระบุ Linux VM/runtime บน Mac arm64
หรือ Linux host ที่เจ้าของมีอยู่, resource budget, isolation/cleanup, runner lifecycle,
trigger matrix, storage policy, rollback และ acceptance tests. ยังไม่เลือก/ติดตั้ง
VM product หรือถือว่า account billing block จะหายด้วย self-hosted; ต้องพิสูจน์ dispatch จริง.

## ของเดิมที่ตรวจพบสำหรับขั้นแผน

- `.github/workflows/ci.yml`: 6 jobs, Python 3.12, Node 22, actual PostgreSQL/Redis,
  role bootstrap, generated OpenAPI/TypeScript และ container cleanup.
- `.github/workflows/venue-contract.yml`: public-endpoint checks แยก schedule/manual;
  ไม่อยู่ใน merge gate.
- `config/postgres.env`, `backend/db/bootstrap/`, `backend/uv.lock`,
  `frontend/package-lock.json`, `compose.yaml` และ scripts/tests เดิมใน repo.
- `specs/standards/testing.md` §1/7 และ F-01 requirements RQ-6/8/9/16.

## แหล่งอ้างอิงภายนอก — ตรวจ 2026-10-23

- [GitHub Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions):
  self-hosted runner usage ไม่คิดค่า runner ของ GitHub ตามเงื่อนไขปัจจุบัน;
  ไม่ได้ยืนยันว่าบัญชีนี้จะ dispatch ได้หรือไม่มีค่า storage.
- [Service containers](https://docs.github.com/en/actions/tutorials/use-containerized-services/use-docker-service-containers):
  self-hosted service containers ต้องใช้ Linux พร้อม Docker.
- [Self-hosted runner security](https://docs.github.com/en/actions/reference/security/secure-use):
  private repository ก็ยังเสี่ยงจาก untrusted workflow code; ต้องแยกและจำกัดสิทธิ์.
