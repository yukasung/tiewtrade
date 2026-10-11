# F-11 — D1 harness review

วันที่: 2026-10-11
ขอบเขต: approved first-release amendment ทั้ง 5 ข้อ, profile_first_release.py,
fixtures ใน profile_mixed_replicas.py, API default bounds, rollout orchestration,
first-release JUnit/JSON และ validation mapping ปัจจุบัน

## ผลแก้ไขและตรวจซ้ำ

Findings ทั้งสอง **Closed**. D1 first-release amendment ผ่านตามขอบเขตที่อนุมัติ:
[JUnit หลังแก้](first-release-fixed-tests.xml) **1 passed / 0 failures/errors/skips,
21.539s**; [evidence หลังแก้](first-release-fixed-evidence.json).

- result bounds อิง source ที่อ่านจริง เริ่มหลัง300แท่งเพื่อให้ warm-up ครบ;
  ทั้ง8แถวมี seed และทุก indicator มีค่า non-null/status READY ก่อนเทียบ
  full-scan values/status/seed/finality/digest/claims ข้าม A→B→A→Bหลังrestart
- เปลี่ยน numeric value ในสำเนา response แล้ว comparator เดิมต้อง reject;
  ป้องกันการผ่านด้วย GAP-only parity หรือการตรวจเฉพาะHTTP200
- บันทึก schema0023, before/after mode/proof/epoch, result bounds/digest,
  routing/HTTP/claim และnegative controls. Assert rejected capabilityไม่เปลี่ยนcontrol,
  หลังstageเป็นPREPARING/READYจริง, trigger integrityผ่าน และทั้งสองAPIคืน
  503 INDICATOR_DATA_NOT_READY โดยไม่บันทึกkeys/cookies/cursors
- Ruff check/formatผ่าน, mypy331filesผ่าน. หลังteardown testDBเป็นLEGACY/PENDING,
  slotIDLE/runtime sessions0. ไม่มีproductioncodechangeหรือการรันทดสอบยาว

รอบแรกของการแก้พบassertionเทียบUUIDจากDBกับstringจากorchestrate;
แก้การเปรียบเทียบเป็นstringก่อนรันผ่าน ไม่เปลี่ยนเกณฑ์epoch.
JUnit/evidence20.09sเดิมเก็บไว้ ไม่เปลี่ยนย้อนหลังเป็นnumeric parity.
D2..D7 และPartialอื่นยังใช้เกณฑ์เดิม; ผลนี้ไม่รับรองDevelopment Complete/activation.

## Findings เดิม — เก็บเป็นประวัติก่อนแก้

1. **Medium — Cross-replica parity ตรวจเฉพาะ GAP**
   - Location: `backend/tests/services/indicator_builder/profile_first_release.py`
     ใน legacy_write_cleanup และ first request/reference; QUERY มาจาก
     `profile_mixed_replicas.py:58` โดยไม่มี start/end
   - Problem: fixture มี 360 แท่งย้อนหลัง 60 วัน แต่ API เลือกหน้าแรกจาก
     upper−1000×4h (ประมาณ 166 วันก่อน). ทั้ง 8 slots ที่เทียบจึงอยู่ก่อนข้อมูล
     มากกว่า 100 วัน ไม่มี numeric indicator value ให้เปรียบเทียบ
   - Evidence: อ่าน default bounds จาก immutable image
     `sha256:b96ed3cf5c213a887bb5e631958498938f861384a620505425a7d747449d3302`
     ด้วย inspect.getsource ยืนยันสูตรเดียวกับ working tree. การตรวจเป็น read-only,
     network none; ไม่รัน acceptance ซ้ำหรือเปลี่ยนผล JUnit เดิม
   - Impact: 200/claims/digest และ GAP parity ผ่านได้แม้ numeric output ของ replica
     ผิด จึงยังไม่ครบ amendment ข้อ 2
   - Recommended fix: กำหนด result bounds ภายใน source fixture ให้มี warm history,
     assert non-null numeric values/READY status ที่คาดหมายก่อนเทียบแต่ละหน้า
     และทดสอบ negative control ที่ numeric value ต่างแล้ว parity ต้องล้ม;
     รัน lifecycle สั้นใหม่และเก็บหลักฐานเดิมแยกจากผลใหม่

2. **Medium — Evidence bundle ยังไม่ครบ amendment ข้อ 5**
   - Location: `profile_first_release.py` ส่วน evidence writer และ
     `profiling/first-release-evidence.json`
   - Problem: JSON มี image IDs, จำนวนหน้า, stage result/epoch และ production flag
     แต่ไม่มี schema revision, before/after mode/proof, routing/HTTP/claim trace
     หรือผล negative controls. JUnit เป็นเพียง lifecycle case เดียว ไม่มีข้อมูลเหล่านี้
   - Impact: audit ผลแต่ละ stage จาก artifact ไม่ได้ครบ และแยก intended 503
     จาก unrelated unavailable error ไม่ได้ด้วย status assertion อย่างเดียว
   - Recommended fix: assert actual control mode/proof/epoch และ expected error code
     หลัง stage, บันทึก schema revision และ sanitized per-step observations
     รวม seed/claim และ negative controls โดยไม่เก็บ cookie/key/cursor/secret

## Validation disposition

| รายการ | ผลรีวิว |
|---|---|
| D1 amendment ข้อ 1 | ปิด coverage ส่วนนี้: old image health/auth/OpenAPI absence, actual F-09 write/read 360 rows/cleanup มี assertions และ JUnit ผ่าน |
| D1 amendment ข้อ 2 | Partial — findings 1; token identity/restart/GAP parity มีหลักฐาน แต่ numeric parity ยังไม่มี |
| D1 amendment ข้อ 3 | ปิด coverage ส่วนนี้: v1 claims, seed=0/claim=None, missing offline inventory, restart policy และ incompatible capability rejection มีหลักฐาน |
| D1 amendment ข้อ 4 | มี stop/dispose/orchestrate และ old writer TT011/compatible cleanup; ยังต้องเพิ่ม exact post-stage observations ตาม finding 2; D2..D7 ไม่ได้รับการยกเว้น |
| D1 amendment ข้อ 5 | Partial — finding 2 |
| Development review finding 1: serialization deadline | Closed: ตรวจ monotonic หลัง encode, >= deadline ให้ 504 เดิม; before/exact/after tests ตรวจ slot release ด้วย; serialization-prepared-regression.xml ผ่าน 32 cases |
| Development review finding 2: missing old F-11 artifact | Superseded โดย owner-approved first-release amendment; ไม่ใช่เหตุให้ D1 Passed |
| Development review finding 3: validation mapping | mapping มีแล้ว แต่ coverage gaps ยังไม่ครบ จึงไม่ปิด finding ทั้งข้อ |

R2-10 ยัง Partial แม้ปิด serialization finding แล้ว. ไม่มี R2 gate ที่เป็น Partial
ทั้งข้อและมีหลักฐานครบเพิ่มจากการรีวิวนี้ จึงไม่เปลี่ยนเป็น Passed ด้วยยอด tests รวม.
N1..N3 ยังขาด controlled-clock/actual-overflow/full-scan scenarios;
L/G/S ยังขาด barrier/fault/interval matrix; D2..D7 ยังมี release rehearsal gaps
ตาม merge-validation-mapping.md. การทดสอบโหลด/ระยะยาวที่เลื่อนไปชุดที่ 9
คง Deferred และเก็บผล Failed/Partial เดิม ไม่รันในรอบนี้

ไม่มี production/test code change; แก้เฉพาะรายงานและสถานะ coverage.
ไม่รับรอง Development Complete/merge หรือ production activation.

CHANGES REQUIRED
