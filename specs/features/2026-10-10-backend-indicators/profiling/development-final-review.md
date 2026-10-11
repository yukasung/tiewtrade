# F-11 — Review ด่านก่อน merge หลังเลื่อนการตรวจรับระยะยาว

วันที่: 2026-10-11
ผล: **CHANGES REQUIRED**

ขอบเขต: ตรวจเส้นทาง prepared API/cursor, admission, attempt/pinned session,
source scan, supervisor/recovery, rollout/evidence และ Compose ที่เกี่ยวข้อง
เทียบ requirements/plan/validation/performance-plan-v2 และ amendments ชุดที่9
ตรวจ git diff และไฟล์ F-11 ใหม่ที่ยัง untracked ด้วย
รายงานนี้ใช้ประกอบรีวิวปิดงาน ไม่อ้างว่าได้ตรวจทุกบรรทัดของ migrations/core ทั้งหมดซ้ำ
หรือพิสูจน์ production readiness ด้วย full regression เพียงอย่างเดียว

## Findings

### 1. Medium — Serialization อาจคืน HTTP200 หลัง deadline

- Location: `backend/src/tiewtrade/services/api/indicator_routes.py:314` ถึงขั้น return Response
- Problem: หลัง await `_read` แล้ว `model_dump_json().encode()` ทำงาน synchronous
  และไม่มีการตรวจ monotonic deadline ก่อนคืน200. `asyncio.timeout_at` ต้องอาศัย
  event loop dispatch cancellation; synchronous work ที่ไม่ yield ทำให้ callback
  ไม่ทันทำงานก่อนออกจาก timeout context
- Evidence: in-memory control เรียก route จริงโดยตั้ง deadline10ms, mock `_read`
  ให้คืนผลหลัง yield และ serialization ใช้50ms; route คืน200หลังประมาณ63ms.
  เป็นหลักฐานเส้นทางผิด ไม่ใช่ benchmark ว่า response จริงใช้เวลา30s
- Impact: คำขอที่ใช้ budget เกือบหมดก่อนสร้าง JSON อาจคืน successful response
  หลังเพดาน30s. แยกจาก API lag109.465ms ที่ยังต้องพิสูจน์ในชุดที่9
- Recommended fix: ตรวจ deadline หลังสร้าง/encode body และก่อนคืน200 ให้เข้า
  error path504เดิม; เพิ่ม regression control ที่ตรวจ synchronous overrun.
  ไม่ผ่อน deadline และไม่เสนอเปลี่ยน architecture โดยไม่มี approval

### 2. High — R2-D1 ยังไม่มี legacy F-11 artifact จึงรับรอง mixed-version gate ไม่ได้

- Location: `performance-plan-v2.md` หัวข้อ R2-D1 และ `profiling/mixed-version-report.md` Coverage
- Problem: gate ต้องรัน legacy API ที่ออก/อ่านv1เดิมร่วมกับ compatibility replica
  ในLEGACYก่อน strict source proof. Imagesที่ตรวจแล้วไม่มี legacy F-11 full-scan binary;
  current binary ในLEGACY ไม่พิสูจน์ decoder behavior ของ old binary
- Impact: ยังไม่ผ่านด่านก่อน merge ที่ไม่ได้เลื่อน การผ่าน current/current HTTP
  testsหรือ full backend ไม่ปิด backward compatibility ตามแผน
- Recommended fix: ใช้ preserved source archive/image พร้อม identity ที่ตรวจสอบได้.
  ถ้าไม่มี ต้องขออนุมัติ amendment ที่ระบุ first-release baseline และการตรวจแทน
  อย่างชัดเจนก่อนเปลี่ยนเกณฑ์ ห้ามสร้าง stub แล้วรายงาน D1ผ่าน

### 3. Medium — ยังไม่มี mapping ด่านก่อน merge ปัจจุบันครบทุกเกณฑ์

- Location: `validation.md` หัวข้อ R2-L/F/N/S/G/D และทะเบียนชุดที่9ใน roadmap
- Problem: มีหลักฐาน implementation หลายช่วงและผล full suite ล่าสุด แต่ baseline
  หลายหัวข้อยังระบุ Approved/ยังไม่ได้รัน. ยังไม่มีตารางปัจจุบันที่เชื่อมแต่ละเกณฑ์
  ที่ไม่เลื่อนกับ test/artifact และแยก deferred component ของ composite gate ชัดเจน
- Impact: อาจปิด Development Complete/merge ด้วยยอด tests โดยยังขาดบาง workload,
  fault matrix หรือ real replica requirement. ไม่ถือว่าจำนวน2324ทำให้ทุก gate ผ่าน
- Recommended fix: รวบรวม mapping รายเกณฑ์เป็น Passed/Partial/Blocked/Deferred
  พร้อม test location และ artifact; รันเฉพาะช่องว่างที่ไม่เลื่อน และคง phase ระยะยาว
  ไว้ชุดที่9. รายการ D2..D6 ใน mixed-version report ที่ยังขาดต้องนำเข้า mapping ด้วย

## Coverage และหลักฐาน

| ส่วน | ผลที่รับรองได้ / ข้อจำกัด |
|---|---|
| Requirements correctness | core/codec/parity/source/roles/worker/API มี regression หลักฐานเดิมและรอบล่าสุด; ยังไม่รับรอง coverage รายข้อทั้งหมดเพราะ finding3 |
| Plan | prepared read ไม่มี GET enqueue, cursorผูก session/format/epoch, writerใช้ pinned physical session และ source RO snapshot, ambiguous cleanup รักษา orphan และ operator-only recovery; D1ยัง blocked |
| Validation ก่อน merge | backend Linux2324passed/1skip และ Compose caseผ่านแยกhost; frontend158/16suites, E2E10, lint/type/build/generated contractผ่าน; ยังต้องปิด findings และ mapping |
| Security | cursorตรวจ HMAC/domain/session/canonical identity, runtime rolesไม่รับ migrator credentials; npm auditหลังอัปเดตเป็น0 ณรอบนั้น; ไม่ใช่การรับรองระบบปลอดช่องโหว่ทั้งหมด |
| Error/deadline | typed error/retry/no-auto-reapมีtests; serialization deadlineมีช่องตามfinding1 |
| Financial precision | indicatorใช้ Money/Quantity/Scalar และ checkpoint restoreผ่าน independent-oracle parity; featureนี้ไม่มีการส่งออเดอร์/PnL/margin/liquidation |
| Concurrency/idempotency | claims/fences/global slot/manual retry/rollout CAS มีtestsและbarriersเดิม; full30seriesfairness/pressure/2replica capacityยังอยู่ชุดที่9 |
| Database/transaction | migration verified-drainถูกปฏิเสธเมื่อfixtureค้างconnectionและผ่านหลังdispose; ไม่แก้productionguard. หลังทดสอบslotIDLE/runtime sessions0 |
| Deferred | โหลด/ระยะยาว C2/C3/C5 และส่วน C4/C6/G7/D7 ที่พึ่งcapacity; R2-7exact525600ยังPartial, APIlagเดิมFailed. คงผลเดิมจนวัดใหม่ |

หลักฐานอ้างอิง:
`resume-linux-final-tests.xml`, `resume-compose-test.xml`, `frontend-security-tests.xml`,
`frontend-security-audit.json`, `frontend-e2e-tests.xml`, `capacity-report.md`,
`mixed-version-report.md` และรายละเอียดใน validation.md.

ไม่มีการแก้ production code ในรอบรีวิวนี้ ไม่รันโหลด/soak ไม่ commit/merge
และยังไม่รับรอง Development Complete หรือ production activation.
