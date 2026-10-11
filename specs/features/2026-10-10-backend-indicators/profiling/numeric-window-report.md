# R2-N1–N3 — Numeric window validation

วันที่: 2026-10-11
ผล: **Passed** สำหรับ N1–N3; ไม่ครอบคลุม N4/concurrency/capacity gates อื่น

[JUnit](numeric-window-tests.xml): **52 passed, 0 failures/errors/skips, 38.353s**
บน isolated PostgreSQL16/Redis, Python3.12 Windows.
แบ่งเป็น API numeric-window8, worker numeric-window11 และ scheduler regression33.
Ruff check/formatสองไฟล์ผ่าน; mypy src/tests332filesผ่าน; git diff --checkผ่าน.

## Mapping และหลักฐาน

| Gate | Assertions / tests |
|---|---|
| N1 | `services/indicator_builder/test_numeric_windows.py::test_numeric_key_before_at_after_db_alignment_boundary` ครบ6TFก่อน/ตรง/หลังboundary; `api/test_numeric_windows.py::test_same_numeric_key_survives_restart_fence_metadata_and_gc` ครบ6TF: as_ofเปลี่ยนแต่boundsเดิม, metadata-only sourcewrite, actual ETH claimเพิ่มglobalfence, dispose/reconnectพร้อมownerใหม่, poll และmanifestGC ไม่เพิ่มgeneration/compute; GETซ้ำ422ไม่มีRetry-After และเมื่อmanifestหาย503 |
| N2 | `test_numeric_window_http_recovery_matches_independent_oracle[False]` ใช้ shared `recover_numeric_window`: readerเกิดMoney OutOfRangeจริง→FAILED_NUMERIC/HTTP422; Lเลื่อนพ้นแถวเสียโดยไม่แก้OHLC/formula/key→coalesce/QUEUED/HTTP503→actual attempt/READY/HTTP200. Failed manifestทั้งแถวไม่เปลี่ยนและแถวsourceที่เสียยังอยู่; deadlineเดิมไม่reset |
| N3 | recovery `[True]` มีvalid seedก่อนแถวเสีย; Lเลื่อนตัดseedแต่แถวเสียยังอยู่→new failed candidate/HTTP422ตรงactual full-scan error; Lเลื่อนอีกจนพ้นแถวเสีย→READY/200ตรงoracle. `test_append_outside_failed_window_waits_for_db_clock_to_expand_u` ยืนยันappendนอกUไม่ปลุกkeyเดิม, Uขยายแล้วkeyใหม่/errorตรงfull-scan; `test_missing_proof_does_not_reset_numeric_input` ทั้งfloor/epoch ไม่ปลุกfailed key |

ชื่อ tests ที่ไม่ระบุ path อยู่ใน `backend/tests/services/indicator_builder/test_numeric_windows.py`;
HTTP tests อยู่ใน `backend/tests/api/test_numeric_windows.py`.

Oracle สำเร็จใช้ independent rounded-Fraction reference เดิมจาก
`tests/infra/indicators/parity_reference.py`, เทียบ full-scan ทุกpoint,
DB canonical digest, restoreทุกcheckpoint/suffix/state และHTTP numeric READY
สองแถวที่มีwarm-upครบ (values/status/seed/finality/revision/generation).
กรณีerrorตรวจactual full-scan readerด้วยAPI role: errorอยู่นอกoutputpageยังต้องล้ม.
HTTPทุกstageไม่เปลี่ยนjobmetadata จึงไม่retryหรือbuildจากGET.

## ขอบเขต fault injection และ cleanup

ใช้ fixture เดิมที่ได้รับการบันทึกใน validation: ขยายชนิดhighชั่วคราวในฐานทดสอบ
เพื่อใส่ค่าเกินMoney rangeแล้วให้reader/core validationโยนOutOfRangeErrorจริง.
นี่คือ damaged-source range failure ไม่ใช่การรับรองว่าราคาถูกต้องตามdomainจะทำให้
สูตรoverflowได้; production domainยังปฏิเสธค่านั้นตั้งแต่เขียน.
ไม่mock numeric error/publisher/failed key หรือผลAPI.

นาฬิกาเปลี่ยนเฉพาะclock callsในtest DB function bodies/source/API read sessions;
ระบบauth/Redisยังใช้นาฬิกาจริง. RestartในN1คือปิดpoolแล้วเปิดphysicalconnection
และworker ownerใหม่เพื่อพิสูจน์durable suppressionของstateless attempt;
ไม่อ้างเป็นprocess crash/DB restart acceptanceของN4/G4.

หลังชุดทดสอบตรวจจริง: clock tableไม่มี, functionที่อ้างtest clockเป็น0,
highคืนชนิด `tiewtrade_money_amount`, control LEGACY/PENDING,
slot IDLE, runtime DB sessions0. ไม่มีruntimecode/migrationหรือฐานแอปเปลี่ยน.
มีTestClient dependency deprecation warningเดิมหนึ่งรายการ ไม่มีtest skip.

ไม่รันทดสอบโหลด/ระยะยาวของชุดที่9 และไม่รับรอง Development Complete/merge
จนPartialที่ไม่เลื่อนกลุ่มอื่นผ่านครบ.
