# Security dependency remediation — Validation

สถานะ: **Approved — เจ้าของตอบ approve ให้ plan/validation ทั้งสองฉบับ 2026-11-05**
วันที่: 2026-11-05
Requirements: [Approved](requirements.md); implementation: [plan.md](plan.md)

Local checks DV-01..07 ผ่านตาม [หลักฐาน](evidence/feature-candidate.md).
Local evidence เป็น snapshot ก่อน commit; final candidate/review/CI และ post-merge gates
ผ่านแล้วตาม [post-merge checkpoint](evidence/post-merge.md).
ก่อน merge ทุก Feature gate ต้องผ่านบน final candidate พร้อม review และ required CI;
Release checkpoint ตรวจ post-merge ของ dependency change ไม่ใช่การประกาศ application Live ready.

| รหัส | เกณฑ์ / Requirement | วิธีและผลที่ต้องได้ | ระยะ | ผล |
|---|---|---|---|---|
| DV-01 | Scope/version — DR-1/2 | semantic lock diff แสดง certifi 2026.10.18 และทุก Vite 6.4.3 occurrence เป็น 6.4.4; manifests/ranges เดิม; ไม่มี package อื่นเปลี่ยนโดยไม่ได้รับอนุมัติ | Feature | Passed local — semantic diff เฉพาะสอง targets; manifests เดิม |
| DV-02 | Reproducibility — DR-2 | backend frozen sync/check และ frontend clean npm ci สำเร็จด้วย Python 3.12/Node 22; installed target versions ถูกต้อง; lockfiles ไม่เปลี่ยนหลังติดตั้ง; integrity/registry metadata ถูกต้อง | Feature | Passed local — frozen backend/npm ci และ installed versions ผ่าน; final hashes ตรวจแล้ว |
| DV-03 | Full dependency scan — DR-3/4 | OSV pinned version ตรวจทั้งสอง lockfilesครบ inventory; advisory เป้าหมายและ alias หาย; ไม่มี unresolved High/Critical/unknown; report/error/inventory mismatch ต้องเป็น blocker | Feature | Passed local — OSV 464 entries; 0 High/Critical/Unknown; target IDs/aliases หาย; Medium 4 records |
| DV-04 | TLS verification — DR-5/6 | installed certifi bundle โหลดได้; SSL context เปิด hostname check/CERT_REQUIRED; real loopback self-signed handshake ถูก HTTPX ปฏิเสธ; ไม่แก้ trust store/ไม่ใช้ Live endpoint | Feature | Passed local — real certifi context และ self-signed loopback rejection |
| DV-05 | HTTP callers/security — DR-5/6 | venue test_failures/test_error_changes/test_wallets และ API-key/Paper-isolation safety tests ผ่าน; mocks ไม่แทน DV-04; ไม่มี credential ใน output | Feature | Passed local — 156 targeted tests |
| DV-06 | Frontend build/toolchain — DR-5 | npm build ผ่าน; Vite dev module transform และ preview HTML/assets บน loopback ใช้ target patch ได้; selected Vitest tests ตาม plan ผ่าน; ไม่เรียก editor/exploit shell | Feature | Passed local — build, 10 Vitest tests, dev/preview/assets ผ่าน |
| DV-07 | Trading/stateless scope — DR-6 | diff ไม่มี app/session/DB/migrations/order/balance/risk/financial changes และไม่มี Live orders; ไม่เพิ่ม Redis/in-memory business state; ถ้า diff ขยายให้หยุดประเมิน scope | Feature | Passed local — scope จำกัดสอง lockfiles และ feature docs |
| DV-08 | Candidate integrity — DR-3/7 | บันทึก head/base หรือ merge SHA, lock hashes ก่อน/หลัง scan, tools/config digest; เปลี่ยน candidate/dependencies/harness แล้ว rerun เฉพาะหลักฐานที่กระทบ; ผล local ไม่แทน CI | Feature | Passed — PR #47 head/base/synthetic merge และ actual merge tree/fingerprints ตรง |
| DV-09 | Review/required CI — DR-7 | Ready for Code Review → review/fixes → refactor decision ตาม AGENTS; required CI เดิมผ่าน final candidate; DV-01..08 ผ่าน; owner สั่ง merge จึง merge | Feature | Passed — review APPROVED; PR/push CI 6/6 success บน final head |
| DV-10 | Post-merge checkpoint — DR-7 | หลัง owner สั่ง merge ติดตาม CI บน merge SHA; ยืนยัน target lockfiles/fingerprints และ scanner evidence ยังตรง merge tree; บันทึก dependency-ready handoff ให้ Security CI โดยไม่อ้างว่า Security CI activation เสร็จ | Release | Passed — merge a3a8652; post-merge CI 42050896249 ผ่าน 6/6; handoff บันทึกแล้ว |

## ขอบเขต tests และหลักฐาน

- เริ่มจาก tests เดิมใน plan; ไม่รันทั้ง application suite local ซ้ำโดยไม่มีผลกระทบ.
- ไม่มี transaction/locking/concurrency behavior change จึงไม่สร้าง DB workload เพิ่ม;
  required CI เดิมยังต้องผ่านตามจริง. หากพบผลกระทบกว้างขึ้นให้ประเมิน targeted coverage ใหม่.
- TLS ใช้เฉพาะ loopback และ temporary self-signed material; ไม่แสดง private key/certificate
  payload ในหลักฐาน. Credentials จริง/บัญชีจริง/exchange network ห้ามใช้.
- Artifact: `evidence/feature-candidate.md` เก็บ commands/versions, safe counts, fingerprints,
  changed dependency inventory, results และ CI URLs/SHAs. Raw secrets ไม่ถูกเก็บ.
- Blocked/Failed/Partial/Not Run คงตามจริง. New advisory ไม่ถูกกลบเพราะ target advisory หายแล้ว.
- Windows exploit ไม่ได้ reproduce ใน local smoke; ใช้ patched version/vendor advisory
  และ full scanner เป็น acceptance ของ vulnerability remediation ไม่อ้างผล platform ที่ไม่ได้รัน.
- ไม่มี Batch/workload ใหม่. DV-10 ยังไม่ถึงกำหนดก่อน merge ให้ Pending Full Validation;
  ไม่ใช้การปิดงานนี้แทน validation/activation ของ Security CI หรือ features เทรดอื่น.

## จุดหยุด

ก่อน implementation: requirements และ plan/validation ต้อง Approved ครบ.
หลัง implementation: Ready for Code Review แล้วรอ owner review.
Git mutations: commit/push/PR/merge ต้องมีคำสั่งแยก; หลังเปิด PR/merge ติดตาม CI ต่อจนจบ.

Code review: [APPROVED และขอบเขตหลักฐาน](evidence/code-review.md).
