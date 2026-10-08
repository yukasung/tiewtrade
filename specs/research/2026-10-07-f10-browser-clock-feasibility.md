# F-10 — Browser clock feasibility

วันที่: 2026-10-07
ประเภท: หลักฐานประกอบแผน ไม่ใช่การรับรอง platform หรือการอนุมัติข้อกำหนด

## คำถามและผล

สามารถกำหนด `clock_eligible` จาก JavaScript บน browser ทั่วไปให้พิสูจน์ว่า
elapsed time รวม OS suspend และมี error bound รวมไม่เกิน 1ms ได้หรือไม่?

**ยังไม่มีหลักฐานเพียงพอให้กำหนดเป็น true บน platform ใดใน F-10**
Windows + Chromium เป็น candidate สำหรับการตรวจต่อ แต่ชื่อ OS/browser
หรือการพบ `performance.now()` ไม่ใช่ capability proof ของ instance ที่กำลังใช้
ไม่พบ standardized JavaScript API ใน High Resolution Time ที่คืนชนิด native clock,
ขอบเขต accuracy หรือคำรับรอง suspend ของ instance นั้น
นี่เป็นข้อสรุปจากขอบเขต API ที่ตรวจ ไม่ใช่การอ้างว่าทุก browser extension/native API ไม่มีความสามารถนี้
ดู [W3C High Resolution Time](https://www.w3.org/TR/hr-time-3/).

## หลักฐาน primary sources

| หลักฐาน | สิ่งที่พิสูจน์และขอบเขต |
|---|---|
| [Microsoft: Acquiring high-resolution time stamps](https://learn.microsoft.com/en-us/windows/win32/sysinfo/acquiring-high-resolution-time-stamps) | QPC เป็น monotonic และเป็นอิสระจากการปรับ system time; Microsoft ระบุว่ารวม standby, hibernate และ connected standby แต่ accuracy ขึ้นกับ hardware/oscillator จึงไม่ให้ absolute error bound 1ms สำหรับ browser ทุกเครื่อง |
| [Chromium Windows TimeTicks, revision `acca47dc0a9e6971232cf29c4482cc410740f278`](https://chromium.googlesource.com/chromium/src/+/acca47dc0a9e6971232cf29c4482cc410740f278/base/time/time_win.cc) | `QPCNowRaw()` เรียก QPC และ `QPCNow()` แปลงเป็น TimeTicks แต่ `InitializeNowFunctionPointer()` เลือก clock ตาม CPU/เงื่อนไข/experiment; มี fallback `RolloverProtectedNow()` และ `GetClock()` แยก WIN_QPC กับ WIN_ROLLOVER_PROTECTED_TIME_GET_TIME จึงห้ามอนุมานว่าทุก Windows Chromium ใช้ QPC |
| [Chromium Blink change `b220921f7dd2d7c767e044abe0eea072a0c9565c`](https://chromium.googlesource.com/chromium/src/+/b220921f7dd2d7c767e044abe0eea072a0c9565c%5E%21/) | change แสดง `Performance::now()` เปลี่ยนจาก tick clock เป็น `base::TimeTicks::Now()` ผ่าน `MonotonicTimeToDOMHighResTimeStamp`; ใช้ยืนยัน interface seam ไม่ใช่ยืนยันว่า binary ปัจจุบันตรง revision นี้ |
| [W3C: coarsen time](https://www.w3.org/TR/hr-time-3/#dfn-coarsen-time) | resolution เริ่ม 100µs หรือค่าที่สูงกว่าตาม implementation; cross-origin isolated เริ่ม 5µs หรือสูงกว่า และอนุญาต jitter จึงไม่มี maximum coarsening/error 1ms แบบ universal |

source revision ข้างต้นเป็นคนละ revision และไม่ได้ผูกกับ Chrome release ที่ติดตั้ง
จึงยังไม่ใช่ source-to-binary certification; ต้องตรวจทั้ง Blink และ base/time ใน
revision เดียวกับ binary เป้าหมายก่อนรับรอง การอ่าน source ไม่เท่ากับผล suspend จริง

## เหตุใด runtime sampling ยังไม่ปิดข้อค้าง

การเห็น delta ละเอียดในการเรียกหลายครั้งบอกพฤติกรรมที่สังเกตตอนนั้น
แต่ไม่พิสูจน์ขอบเขต error ทั้งหมดหรือการเดินข้าม suspend ในอนาคต
การเทียบ `Date.now()` ช่วยตรวจความผิดปกติ แต่ wall clock ปรับได้
จึงไม่ใช่ independent trusted elapsed-time reference ตาม
[W3C clock definitions](https://www.w3.org/TR/hr-time-3/#clocks).
การกำหนด allowlist จาก user agent จึงต้องแยกจากคำว่า runtime proof อย่างชัดเจน

## ทางตรวจต่อที่ review ได้

ก่อนรับรอง candidate ต้องระบุ browser version/build และ source revision, OS build,
hardware/VM, power mode, privacy/timer settings และ context isolation ของ deployment
พร้อมหลักฐาน error budget ซึ่งแยก native rate error, conversion และ browser coarsening
ออกจาก network RTT การนำ 1ms margin เดิมมาใช้ต้องมีหลักฐานรองรับผลรวม ไม่ใช่ใช้ resolution แทน accuracy

ทดสอบ suspend จริงบน candidate ด้วย reference elapsed time ที่อิสระจาก clock ที่ทดสอบ
เก็บก่อน/หลังจาก `performance.now()` และ reference พร้อมระยะเวลาที่คร่อม 10s,
response ที่ค้าง, proof ก่อนพัก, ไม่มี lifecycle event, hibernate/standby ที่ platform รองรับ
และ wall-clock adjustments ทดสอบ browser upgrade/privacy setting changes ด้วย
ผลทดลองผ่านเป็นหลักฐานเฉพาะ configuration ที่ทดสอบ ไม่ใช่ mathematical guarantee
สำหรับ hardware ทั้งหมดหรือ native clock selection ที่หน้าเว็บมองไม่เห็น

**สถานะการทดลอง: ไม่ได้ทำ OS suspend/hibernate และยังไม่มี candidate ที่รับรอง**
รอบนี้อ่านเอกสารและ source เท่านั้น ไม่ได้เปลี่ยนโค้ด F-10 หรือค่าตั้งระบบ
หากต้องรองรับ browser ทั่วไปโดยไม่จำกัด configuration ต้องตัดสินใจวิธี readiness
และสมมติฐาน clock ใหม่ก่อนอนุมัติ plan; การตั้ง `clock_eligible=false` ทุกเครื่อง
รักษาการปฏิเสธ READY แต่ยังไม่พิสูจน์เส้นทางใช้งาน READY ตาม feature


## Preflight รอบสอง — ผล feasibility วันที่2026-10-07

**ผล: วิธีในแผนยังไม่ feasible สำหรับการรับรอง browser ทั่วไปภายใต้
สมมติฐานปัจจุบัน** ไม่ใช่เพียงการขาด test case: JavaScript อาจไม่มีข้อมูล
เพียงพอแยก elapsed ที่ต่างกันจริง การตั้ง default false ช่วยป้องกัน false READY
แต่ไม่สร้างเส้นทาง READY หรือรับรอง local warning60s
ไม่สรุปว่า clock ทุกตัว/ทุก platform ทำไม่ได้; managed environment ที่มี
suspend-inclusive clock contract ยังเป็นทางตรวจต่อได้ แต่ยังไม่รับรอง target ใด

### การทดลอง browser จริงขณะเครื่องตื่น

ใช้ Playwright CLI session `f10-clock-feasibility` แยกจาก browser ของผู้ใช้
เปิด about:blank, evaluate performance.now100,000ครั้ง แล้วรอ timer2s
และอ่าน CDP Browser.getVersion; ปิด session หลังเก็บข้อมูล
ไม่มีการพักเครื่อง เปลี่ยน system clock หรือเปิด app/backend F-10

[ผลดิบ](2026-10-07-f10-clock-preflight/01-awake-observation.json):
macOS27.0 build26A428, Chrome154.0.8037.93 (headless), CDP revision
`f89f3a4363808e117c592adedcf9947882ac3b79`, crossOriginIsolated=false
พบ71 positive deltas มีstepประมาณ0.1ms; ช่วงรอได้ monotonic2001.200ms
กับ wall2001ms ทั้งสองค่ามีตัวอย่างและ sampling order ของตัวเอง
ไม่ถือ wall clock เป็น independent reference หรือใช้ส่วนต่างนี้สร้าง error bound
User-Agent แสดง MacOS10_15_7 แม้ sw_vers แสดง27.0 เป็นตัวอย่างชัดว่า
UA ไม่ได้ยืนยัน OS build สำหรับ evidence profile
ผล: **awake observation PASS; suspend/error-bound certification UNVERIFIED**

### Source contract ของ macOS

[Chromium time_apple.mm](https://chromium.googlesource.com/chromium/src/+/refs/heads/main/base/time/time_apple.mm)
ที่ตรวจ (blob `a2c17d14f95f3c783c705f8c2744925d05a09cae`) แยก
TimeTicks→ComputeCurrentTicks→mach_absolute_time ออกจาก
RealTicks→ComputeCurrentRealTicks→mach_continuous_time ที่บวก sleep offset
[Apple mach_time.h](https://github.com/apple/darwin-xnu/blob/main/osfmk/mach/mach_time.h)
ระบุ mach_continuous_time เป็นตัวที่เดินระหว่าง sleep เพิ่มจาก mach_absolute_time
จึงห้ามใช้คำว่า TimeTicks high-resolution เป็น proof ว่ารวม suspend
ตรวจ source ตรง CDP revision `f89f3a4363808e117c592adedcf9947882ac3b79`
สำเร็จด้วย read-only HTTP fetch หลัง web reader อ่าน URL นั้นไม่สำเร็จ:

- [performance.cc](https://chromium.googlesource.com/chromium/src/+/f89f3a4363808e117c592adedcf9947882ac3b79/third_party/blink/renderer/core/timing/performance.cc):
  now() เรียก MonotonicTimeToDOMHighResTimeStamp(base::TimeTicks::Now())
- [time.cc](https://chromium.googlesource.com/chromium/src/+/f89f3a4363808e117c592adedcf9947882ac3b79/base/time/time.cc):
  default TimeTicksNow function ใช้ TimeTicksNowIgnoringOverride
- [time_apple.mm](https://chromium.googlesource.com/chromium/src/+/f89f3a4363808e117c592adedcf9947882ac3b79/base/time/time_apple.mm):
  TimeTicksNowIgnoringOverride→ComputeCurrentTicks→mach_absolute_time
  default path นี้ไม่มี mach_continuous_time
- [time_clamper.h](https://chromium.googlesource.com/chromium/src/+/f89f3a4363808e117c592adedcf9947882ac3b79/third_party/blink/renderer/core/timing/time_clamper.h)
  และ [time_clamper.cc](https://chromium.googlesource.com/chromium/src/+/f89f3a4363808e117c592adedcf9947882ac3b79/third_party/blink/renderer/core/timing/time_clamper.cc):
  coarse100µs/fine5µs; clamping jitterอยู่ในbucketของtimestampนั้น
  errorจากclampingของผลต่างสองsamplesต่ำกว่า200µsในcoarsecontext
  จึงมีหลักฐานว่า1msครอบquantizationส่วนนี้ในbuildที่ตรวจ แต่ยังไม่ครอบ
  clock-rate/hardware errorทั้งระบบ และไม่ทำให้clockที่หยุดรวมsleepขึ้นมา

**ผล target นี้: FAIL suspend-inclusive source contract** สำหรับ default
clock path ไม่ต้องบังคับพักเครื่องเพื่ออนุมัติtargetที่sourceไม่ผ่านอยู่แล้ว
การทดลองพักเครื่องจริงยัง NOT RUN; ไม่อ้างว่าsourceเป็นผลการทดลองsleep
ใช้ CDP build revision เป็นหลักฐานของbuildที่อ่าน ไม่ใช่ใบรับรองhardware/configทุกเครื่อง

### Counterexample ที่ตรวจซ้ำได้

[synthetic price counterexample](2026-10-07-f10-clock-preflight/02-synthetic-counterexample.json)
เป็นแบบจำลอง ไม่ใช่ผลพักเครื่องจริง:

| World | เวลาจริง | monotonic delta | wall delta | ราคามีbudget1sยังผ่านหรือไม่ |
|---|---|---|---|---|
| เครื่องตื่น0.5s | 0.5s | 0.5s | 0.5s | ผ่าน |
| เครื่องพัก20s + ตื่น0.5s และ wallปรับกลับ20s | 20.5s | 0.5s | 0.5s | ไม่ผ่าน |

ภายใต้ stopping monotonic/adjustable wall และไม่มี lifecycle event
ทั้งสอง world ให้ค่า clock samples เหมือนกันทุกค่าที่หน้าเว็บอ่านก่อน/หลัง
สูตรปัจจุบันคืน elapsed501ms ในทั้งสอง world; delta check5msก็แยกไม่ได้
อัลกอริทึมที่ใช้เพียงข้อมูลชุดนี้จึงต้องคืนค่าเดียวกัน ทั้งที่คำตอบถูกต้องต่างกัน
นี่เป็นข้อพิสูจน์ข้อจำกัดของข้อมูลในสมมติฐานนี้ ไม่ใช่ proof ว่าทุก clock หยุด
correlated request ใหม่ก็ไม่ช่วยถ้าrequest/responseนั้นค้างคร่อมพักและ
หน้าเว็บไม่มี trusted elapsed ตรวจความหน่วงของคำขอใหม่เอง
server_time บอกเวลาสร้างresponse ไม่บอกเวลาปัจจุบันที่browserรับ response

[synthetic alert counterexample](2026-10-07-f10-clock-preflight/03-synthetic-alert-counterexample.json)
ใช้เวลาไม่พร้อม20sเทียบกับ20s+sleep60s+wallrollback60s: ทั้งคู่เห็นdelta20s
แต่กรณีแรกยังไม่ครบ60s ส่วนกรณีหลังครบแล้ว จึงรับรอง local alert threshold
พร้อมกันทั้งสองworldไม่ได้จาก clock samplesชุดนี้เช่นกัน

### Decision ที่จำเป็นก่อนเดินต่อ

1. **คงกฎพิสูจน์แบบเดิม:** ต้องกำหนด supported managed target พร้อม trusted
   suspend-inclusive elapsed/error contract และวิธีรับรองcontextที่ deployจริง
   อาจต้อง native clock provider/managed client ซึ่งอยู่นอก stackเว็บปัจจุบัน
   ต้องขออนุมัติขอบเขตก่อนเพิ่ม ไม่รับรองWindows/Chromiumจากชื่ออย่างเดียว
2. **คง browserทั่วไป:** ต้องกำหนดข้อสมมติ/ความหมาย readinessฝั่งเว็บใหม่
   เช่นแสดงสถานะตาม snapshotพร้อมเวลา แยกจากการรับรองราคาปัจจุบันเพื่อส่งคำสั่ง
   backendยังตรวจ10s/leaseก่อนอนุญาตexecutionในงานภายหลัง
   ทางนี้เป็นข้อเสนอให้เจ้าของตัดสิน ไม่ได้เปลี่ยนrequirementsที่อนุมัติแล้ว

แนะนำให้ทบทวน timing approach สำหรับ browserทั่วไปก่อนทำ production F-10
การทดสอบ suspendจริงเพิ่มอาจยืนยันหรือหักล้างหนึ่งtarget แต่ไม่แก้
indistinguishable-world limitation ของ browserที่ clockหยุด+wallปรับได้
NC-26 ยังเปิดอยู่จนเจ้าของเลือกสมมติฐาน/ขอบเขต และแผนผ่านเกณฑ์ของทางนั้น


## คำตัดสินหลัง research — NC-26 Closed

เจ้าของตอบ approve วันที่2026-10-07 ให้เปลี่ยนเว็บเป็นสถานะที่serverตรวจ
ณsnapshotพร้อมเวลา โดยbackendตรวจfreshnessใหม่ก่อนใช้จริง
จึงยกเลิกclock certificationเป็นprerequisiteของREADYในเว็บ; ไม่ใช่การรับรอง
platformที่researchพบว่าไม่ผ่าน ข้อความNC-26ยังเปิดในผลpreflightด้านบนเป็น
ประวัติก่อนคำตัดสินนี้ ส่วนlocal-onlyalert60sยังอยู่ในNC-27รอคำตอบแยก
source of truthปัจจุบันคือ requirements/plan/validation ของF-10


2026-10-07 — NC-27 Closed: เจ้าของอนุมัติservermarketoutage60s และ
browserdeliverywarningทันทีที่ตรวจพบ ไม่ใช้browserclockรับรอง60s
จึงยกเลิกalert-clockcertificationจากแผน; historicalpreflightไม่ใช่mergegate
