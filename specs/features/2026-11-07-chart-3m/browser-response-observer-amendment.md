# 3m CI checkpoint — browser response observation

สถานะ: **Approved A — เจ้าของอนุมัติ browser observer, targeted tests และ CI หนึ่งรอบ; ผ่านแล้วนำขึ้น local ตามแผน**
วันที่: 2026-11-07
อ้างอิง: RQ-3M-06, V3-08/V3-09, review M1

## หลักฐาน

-15de827: backend1failed/4790passed จาก harness schema0065 pin; แก้ตรง0066และ24targeted testsผ่าน
-f4464c0: browser1failed/18passed; async response predicate อ่าน CDP body ไม่ได้ตอน navigation
-a9faaf7: browser1failed/18passed อีกครั้ง แม้อ่าน bodyนอกpredicateแล้ว;
  failure อยู่ที่ live response.json(), Network.getResponseBody unavailable
  https://github.com/yukasung/tiewtrade/actions/runs/42388030151
- Local native3m และไฟล์กราฟทั้งหมด8testsผ่าน; ยังไม่พิสูจน์สาเหตุที่ต่างใน CI
- Backendของ candidateล่าสุดยังรันอยู่ ณ จุดเสนอ; ต้องติดตามให้จบ ไม่ตีความว่าผ่าน
- Owner runtime/database0065ไม่ถูกหยุดหรืออัปเกรด; migration/backupที่เตรียมไว้ยังไม่เริ่ม

## A — Observe actual browser fetch inside the test (แนะนำ)

1. เปลี่ยนเฉพาะ native3m browser test; reuse page.addInitScript pattern จาก
   frontend/e2e/manual-orders.spec.ts. เก็บผลของ native fetch จริงในหน้า test
   โดย clone response ของเฉพาะ candle pages/live3m แล้วคืน responseเดิมให้แอป
   ไม่ mock GET, ไม่ส่ง probe/retryเพิ่ม, ไม่อ่านผ่าน Playwright CDP response.json
2. จำกัด observer เป็นข้อมูล public fixture ที่จำเป็น: base/TF/status/open/end/OHLC
   จำนวน records/rowsมีขอบเขต; ไม่เก็บ headers/cookies/tokens/login payload
   แยก completed/aborted/errorตามจริง ห้ามให้ข้อผิดพลาดเงียบแล้วถือว่าผ่าน
3. คง real API/PostgreSQL/worker, READY, exact values,180s, distinct rendered BTC/ETH,
   stale-value rejection และ no-order/mode-mutation assertions. ไม่ลดเกณฑ์หรือเพิ่มtimeout
4. ตรวจ scoped ESLint/types และ browser file8testsหนึ่งรอบ จากนั้น commit/pushในPR60
   และติดตาม required CIบน SHAใหม่หนึ่งรอบ หากผ่านจึงทำ local activationตามแผนเดิม
   คาดประมาณ25–30นาทีรวม CIหลังพัฒนา; ไม่ทดลองซ้ำอัตโนมัติหากด่านยังล้ม
5. ไม่แก้ runtime/migration/financial/security/business rules หรือ release workload profiles

ผลกระทบ: ลดการพึ่ง body retrieval ของ DevTools แต่เพิ่ม observerเฉพาะtest ต้องตรวจว่า
แอปยังเป็นผู้ส่ง requestsจริงและแสดง seriesจริง; ไม่ใช้ observerแทน UI assertions
ไม่ถือว่าวิธีนี้พิสูจน์ root cause ของ Chromium แล้ว จนมีหลักฐานจากการตรวจ

## B — Stop at this checkpoint

เก็บผล Failed/Passedตามcandidate รอ backendที่เริ่มแล้วให้จบ และรายงานหลักฐาน
ไม่แก้ test เพิ่ม ไม่เริ่ม CI/local migrationรอบใหม่; localยังไม่มี3m

## เหตุผลที่ต้องรอคำตัดสิน

AGENTS.md หัวข้อการทำงานให้เร็ว:
“เมื่อแก้และตรวจเกณฑ์เดิมแล้วยังไม่ผ่าน 3 รอบ … ให้หยุดและเสนอทางเลือก … ก่อนทดลองรอบถัดไป”
ไม่มีคำอนุมัติให้ข้าม correctness/safety หรือเปิด localก่อน Feature gates ผ่าน

## ผลเพิ่มจาก candidate ก่อนหน้า ระหว่างรอคำตัดสิน

Backend f4464c0 จบ Failed1/4793passed/31deselected ใน949.79s:
test_deadline_or_cancellation_closes_scan_before_release[False] รอ started event2s
ไม่สำเร็จ โดย test จำลอง ATTEMPT_SECONDS=0.3. ยังไม่ยืนยันความเกี่ยวข้องกับ3m;
ไม่แก้ test นี้หรือขยายเวลาในทางเลือก A. รอผล backend a9faaf7 เพื่อรายงานแยก
หากยังเป็น blocker ต้องวิเคราะห์และกำหนดขอบเขตก่อนแก้ ไม่ถือว่า A อนุมัติแก้ทุกtest

## Latest backend outcome

Backend a9faaf7 จบ Passed:4794tests และทุก isolated/migration gateผ่าน
รวมfrontend/API contract/container/Securityผ่าน; เหลือเฉพาะbrowser1failed/18passed
ที่อ่านlive response bodyไม่ได้. Deadline0.3s testผ่านบนcandidateนี้โดยไม่แก้
คงผลFailedเดิมของf4464c0ไว้ และไม่ขยายขอบเขต A ไปแก้testนั้น
ทุกjobที่เริ่มแล้วจบครบ ไม่มีjobที่ยังต้องติดตามก่อนรอคำตัดสิน

## คำตัดสิน

เจ้าของตอบ A ผ่านคำถาม checkpoint; เริ่มเฉพาะขอบเขต A ได้ต่อเนื่อง
คงผลเดิมทั้งหมด และไม่อนุมัติการทดลองซ้ำหากรอบที่อนุมัตินี้ยังล้ม
