# F-11 — Compose rollout / rollback runbook

สถานะ: **Implementation review APPROVED (2026-10-11)**; ใช้สัญญา S0..S5 / R2-D1..D7 จาก
[แผนที่อนุมัติ](performance-plan-v2.md#migrationgrantsrollback) และ ADR-002
วันที่: 2026-10-11

CLI ทำ verification และ atomic DB transition; operator ทำ stop/drain/start และ
ควบคุม routing/restart ของ deployment จริง ไม่มี load balancer หรือ platform ใหม่.
คำสั่งด้านล่างเป็น runbook สำหรับ operator ไม่ใช่คำสั่งที่ agent รันกับแอประหว่าง implementation.

## ก่อนเริ่ม

1. เก็บ inventory ทุก API, market-data, cleanup/startup/cron/operator writer และ builder;
   รวม container ที่หยุดอยู่แต่ restart ได้. บันทึก immutable image **config ID**
   `sha256:...` กับ release digest และ capability ของแต่ละ image. CLI ใช้ config ID
   ที่ Docker inspect `.Image` คืน ไม่ใช้ tag ที่เปลี่ยนปลายทางได้.
2. ตรวจ keyring จริงของ API ทุก replica ว่ามี current/verification keys เหมือนกัน;
   บันทึก non-secret deployment configuration ID. ไม่ใส่ keys, MAC หรือ cursor ลงไฟล์/log.
   ไม่ rotate key ระหว่าง cutover. Capability probe ไม่ตรวจ environment keys แทน operator.
3. ปิดทางเข้า indicator ที่ routing และ direct access; Compose ที่ไม่มี routing controller
   ให้หยุด API ทั้ง process. หยุด legacy image ในทุก restart/autoscale/cron path.
   รอ request drain 30s+cleanup2s; ถ้าไม่จบให้ stop และยืนยัน process/snapshot ปิด.
4. หยุด builder ทุกตัวด้วย verified stop/join เดิม (Compose grace130s).
   หยุด F-09 ทุกตัว รวม cleanup/startup/cron/operator paths และ DB transactions.
   ตั้ง restart policy ของ container ใน inventory เป็น `no` ก่อนตรวจ.
   ห้ามให้ orchestrator อื่น/manual start เปิด process กลับระหว่าง verification กับ transition.
5. Slot ที่ยัง RUNNING ต้องใช้ verified stop/reap CLI เดิมพร้อม owner/slot epoch/fence.
   Lease หมดหรือ container PID0 อย่างเดียวไม่ให้สิทธิ์ clear slot. Rollout CLI ไม่ reap/reset
   attempt counters, retry budget, fairness หรือ episode deadlines.

ตรวจ container แบบไม่อ่าน environment secrets:

```powershell
docker ps --all --no-trunc --filter label=com.docker.compose.project=<project>
docker inspect --format '{{.Id}} {{.Image}} {{.State.Status}} {{.HostConfig.RestartPolicy.Name}}' <container-id>
```

## Inventory

ไฟล์ JSON ใช้ `version:1`, `project`, `containers` (อย่างน้อยหนึ่งตัวต่อ service
`api`, `market-data`, `indicator-builder`) และ operator attestations:

```json
{
  "version": 1,
  "project": "tiewtrade",
  "containers": [
    {"container_id": "<64 lowercase hex>", "image_id": "sha256:<64 lowercase hex>", "service": "api"},
    {"container_id": "<64 lowercase hex>", "image_id": "sha256:<64 lowercase hex>", "service": "market-data"},
    {"container_id": "<64 lowercase hex>", "image_id": "sha256:<64 lowercase hex>", "service": "indicator-builder"}
  ],
  "external_paths_drained": true,
  "legacy_restart_disabled": true,
  "verification_keyring_verified": true,
  "keyring_config_id": "<non-secret deployment config ID>"
}
```

Placeholder ด้านบนตั้งใจไม่ผ่าน schema; เติมค่าจริงและตรวจ attestations ก่อนใช้.
ต้องสร้าง container ของ compatible replacement image ไว้ในสถานะ created/exited;
ห้ามมี legacy API/F-09 อยู่ใน project แล้วละออกจาก inventory.
Archive release/inventory ของ legacy หลังถอน container และปิด restart source ทั้งหมด.
หากมี process บน host อื่นหรือ cleanup service ชื่ออื่น ต้องทำ external inventory/drain
ตามข้อก่อนเริ่ม; CLI ค้นได้เฉพาะสาม Compose service names บน Docker context ปัจจุบัน.
ไม่ถือว่า Docker inventory หรือ pg_stat_activity พิสูจน์ offline host restart policy ได้.

CLI ตรวจ inventory เทียบ `docker ps -a` ทั้ง project, exact image/service/project,
สถานะ stopped/created, PID0/restart no, timestamps และตรวจซ้ำหลัง capability probes.
Probe ใช้ immutable image แบบ network none/read-only/no credentials ไม่เปิด app.
DB ต้องไม่มี connection ของ API/market-data/builder รวม idle pool และ slot/advisory lock ว่าง.

## S0..S3: Expand, compatibility, drain และ Prepare

- S0: `alembic upgrade head` เพิ่ม schema/functions/grants; ไม่ติด strict proof
  และไม่เปิด PREPARED. ทดสอบ legacy binary กับ expanded schema ก่อน compatibility rollout.
- S1: upgrade image ทุก API ให้ decode v1/v2 และทุก F-09 ให้ scope/physical grace.
  LEGACY ยังออก v1. Builder ยังไม่ claim ใน LEGACY.
- S2: ทำรายการ stop/drain ด้านบนจริงก่อน source proof activation.
- S3: ใช้ migrator credential เฉพาะ operator process. อ่าน mode/epoch จาก DB:

```powershell
python -m tiewtrade.services.indicator_builder.main rollout-status
python -m tiewtrade.services.indicator_builder.main rollout --inventory inventory.json --expected-mode LEGACY --expected-epoch <DB-epoch> --target PREPARING
```

Initial prepare ใช้ `activate_indicator_source_proof()` เดิมภายใน transaction เดียวกับ
transition: relation locks → source guard → control → slot. ถ้า transition ไม่สำเร็จ
การติดตั้ง/reset proof ในคำสั่งนั้น rollback ด้วย. คำสั่ง stale/replay ไม่ reset proof.
CLI ไม่ retry query/ambiguous commit และไม่เปิด process ให้อัตโนมัติ.
หลัง PREPARING ให้เริ่ม compatible F-09/builder ตาม image allowlist เพื่อเตรียม 30 series;
API หน้าแรก503/valid cursor409. ไม่มี public cursor issuance ก่อน activation.

## S4: Activate

ก่อน activation ต้องมี owner-reviewed gate bundle ครบ R2-L/F/G, C1..C6, D1..D7,
REGRESSION และ READY-API ของ release images/keyring config ที่จะใช้จริง.
Gate bundle JSON มี `version:1`, `image_ids` (exact set จาก inventory),
`keyring_config_id`, `approved_gate_mapping:true`, และ `gates`:

```json
{"name":"R2-C1","artifact":"reports/capacity.xml","sha256":"<artifact SHA256>","status":"PASSED"}
```

แต่ละ gate อ้าง JUnit XML ใต้ directory ของ bundle, <=4MiB, hashตรง, tests>0,
failures/errors/skipped เป็น0 และไม่มี failure/error/skipped nodes.
ใช้ report เดียวหลาย gate ได้เมื่อ owner ตรวจว่า report นั้นครอบคลุม gate เหล่านั้นจริง.
นี่เป็น operator-approved mapping ไม่ใช่การเดาว่า XML เขียวใด ๆ พิสูจน์ capacity.
รายงาน synthetic metadata/CLI tests ของ phase นี้ใช้แทน C/D/READY-API ไม่ได้.
Capacity และ full mixed-version acceptance ยังไม่ครบ จึงยังไม่มี production activation bundle.

หยุด/drain API, builder และ F-09 อีกครั้ง และสร้าง inventory ของ image ที่จะ resume:

```powershell
python -m tiewtrade.services.indicator_builder.main rollout --inventory inventory.json --expected-mode PREPARING --expected-epoch <DB-epoch> --target PREPARED --evidence evidence.json
```

DB ตรวจ fresh valid heads ครบ30, proof/codec/expiry/checkpoint retention และ slot ว่าง
ก่อนเปลี่ยน epoch/format2. ไม่แก้ READY metadata หรือขยาย expiry; old build epoch เป็นประวัติ.
ผล APPLIED/ALREADY_APPLIED exit0; STALE/REJECTED/NOT_DRAINED/POLICY_UNSUPPORTED/
HEADS_NOT_READY exit12. Inventory/evidence/operational failure exit13 เป็น fixed category.
เมื่อผลกำกวมอ่าน `rollout-status` และตรวจสภาพจริงก่อนส่ง exact CAS command เดิม;
ไม่มี automatic retry. Replay ของ transition ล่าสุดไม่เปลี่ยน epoch/cutoff ซ้ำ.
หลังผ่านให้ resume เฉพาะ compatible allowlisted images แล้วเปิด traffic.
S5 rolling updates ใช้ protocol/codec เดียวกัน; version ที่อ่านร่วมกันไม่ได้ต้องกลับเข้า drain.

## Rollback หลังออก v2

1. ปิด traffic/direct access และ verified stop/drain ทุก process ตามข้อก่อนเริ่ม.
2. ใช้ expected mode/epoch ปัจจุบันเปลี่ยนเป็น PAUSED:

```powershell
python -m tiewtrade.services.indicator_builder.main rollout --inventory inventory.json --expected-mode PREPARED --expected-epoch <DB-epoch> --target PAUSED
```

PAUSED ยังทำได้เมื่อ source proof/protocol เสีย; ไม่ clear orphan slot เพื่อให้ผ่าน.
DB เพิ่ม epoch และบันทึก `last_v2_issue_cutoff` จาก DB clock หลัง drain;
replay ไม่เลื่อน cutoff. PREPARING→PAUSED ก่อนเคยออกv2ไม่เพิ่ม support window ใหม่.
API compatible หน้าแรก503/valid v1/v2→409; ไม่มี legacy fallback.

3. หากต้องให้ API ตอบ error ระหว่างรอ ให้ resume เฉพาะ compatibility image;
   คง keyring/control/views/source scope/physical grace. ห้าม legacy F-09 cleanup365วัน.
4. รอ DB cutoff+6h; หยุด/drain ทุก reader/writer อีกครั้ง และตรวจ:

```powershell
python -m tiewtrade.services.indicator_builder.main rollout-retire-check --inventory inventory.json
```

RETIREMENT_READY หมายถึงตรวจ support window, connection/slot/advisory drain แล้ว;
ไม่ได้ทำ DDL และไม่อนุญาตเริ่ม process กลับระหว่าง check กับ Alembic.
เมื่อทุก process ที่อ่าน control หยุดแล้วจึง `alembic downgrade 0014`
ซึ่งใช้ existing maintenance protocol เพื่อถอน strict triggers/derived schema.
คง F-09 candles/jobs; grants/bootstrap rollback ทำท้ายสุดโดย cluster operator.
Downgrade ของ0023และ0015บล็อก premature cutoff/active slot;
0023ตรวจruntimeconnection/advisory drainก่อนถอนCASด้วย. ทำใน maintenance window
ด้วย bounded lock/query settings และไม่ retry transaction ที่ abort.
Rollback ก่อนเคยออกv2ไม่ต้องรอ6h แต่ยังต้อง drain source writers ก่อน DDL.

## Re-enable

PAUSED→PREPARED และ PREPARED→LEGACY ถูกปฏิเสธ.
กลับเปิดต้อง PAUSED→PREPARING, ผ่าน gates/ready heads ใหม่ แล้ว PREPARING→PREPARED;
ใช้ stop/drain/inventory ขั้นเดิมทั้งสองครั้ง. Epochใหม่ทำให้ old valid v2 ยัง409.
ห้าม resume STAGING/claim เดิมหรือ reset retry/episode เพื่อให้ activation ผ่าน.
การกลับ full-scan LEGACY หลังถอน schemaไม่ได้รับรอง V-15 หรือ F-11 Completed.

## R2-D1 first-release amendment — Approved 2026-10-11

เจ้าของยืนยันว่าไม่เคยdeploy F-11 full-scan เดิม และอนุมัติ
[D1 first-release amendment](d1-amendment-proposal.md) ด้วยคำสั่ง “approve”.
ใช้เกณฑ์ทั้ง5ข้อใน amendment แทน R2-D1 legacy-F-11-binary เดิมเฉพาะส่วนนี้:
ทดสอบ pre-F-11 API/F-09จริงก่อนstrictproof และ compatibleF-11สองreplicas
ในLEGACYด้วยv1cross-replica/restart/fullscanparity พร้อมstagegate/drain/inventory
negativecontrols. ห้ามstubและไม่ผ่อนD2..D7/capacity/productionactivation.
D1เป็นPendingจนหลักฐานครบ ไม่ถือว่าการอนุมัติคือPassed
