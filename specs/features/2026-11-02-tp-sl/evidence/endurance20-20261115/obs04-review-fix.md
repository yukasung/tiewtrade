# OBS-04 review findings M1–M2 fixed

สถานะ: Targeted checks Passed — รอ owner refactor ก่อน campaign

M1: ครอบ capture ทั้ง fixture/session lifecycle ด้วย timeout ตามเวลาคงเหลือถึง
min(next slot,measurement end); collector1sเดิมไม่เปลี่ยน. คงpost-checkสำหรับ
operationที่คืนค่าหลังdeadline. TimeoutบันทึกIncompleteและส่งfailure signalเดิม.
Testsค้างจริงที่slot boundaryและfinal measurement boundaryยืนยันยกเลิก/join,
ไม่มีcaptureซ้ำ/slotถัดไป และfailure signalถึงparent.

M2: closeเก็บexceptionแรกและพยายามobserver.close/fixture.disposeครบ ก่อนraiseตัวเดิม;
ข้อผิดพลาดถัดไปแนบเฉพาะtypeเป็นnote. TestsตรวจRuntimeError/CancelledErrorแรก,
สองcleanupล้มพร้อมกัน และdisposeล้มเพียงจุดเดียว โดยไม่เผยprivateข้อความในnote.

165 targeted tests Passed รวมOBS02/OBS03/fail-fastและrealPGcapture/rollback/lock-release.
หลังปรับtest doublesให้ตรงmypy ตรวจ5affected casesอีกครั้งPassed; runtimeไม่เปลี่ยน.
Ruff/format/mypy2filesPassed; git diff --checkPassed.
Raw `validation-artifacts/f17-obs04-m1m2-tests-20261116/` (21.617s);
independent audit: DB absent,0connections/locks. ไม่มีcampaign/preflight/Git/CIใหม่.
คงผลFailed/Incompleteเดิมทั้งหมดและF17notCompleted.

ขั้นถัดไป owner refactor the code; หลังrefactor/affectedchecksจึงเดินหนึ่งcampaign
ตามOBS04ที่อนุมัติ ไม่เริ่ม4hหรือเปลี่ยนเกณฑ์.
