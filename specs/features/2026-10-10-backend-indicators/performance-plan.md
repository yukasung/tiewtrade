# F-11 — การเปลี่ยนแผนหลัง benchmark ไม่ผ่าน

สถานะ: **Approved** — เจ้าของอนุมัติเมื่อ 2026-10-10 ตามคำสั่ง “approve”; NC-34 ปิดแล้ว
วันที่: 2026-10-10
Branch: feature/f-11-backend-indicators

## ปัญหาและหลักฐาน

[Profile](profiling/report.md) พบ core14.21s/decode10.37s/DB2.16s/
เตรียมและhash1.97s ภายในคำขอ30sที่ยังอ่านได้ประมาณ97,000ช่อง
decodeบางbatchทำงานต่อเนื่องประมาณ150ms ส่วน API ปกติยังคืน504
จึงต้องลดต้นทุนต่อแท่งและช่วง CPU ที่ไม่ yield ก่อนพิสูจน์ชุด525,600ช่องอีกครั้ง
ตัวเลขนี้ไม่ได้รับรองว่าแนวทางด้านล่างจะผ่าน V-15

ข้อเสนอรอบนี้ให้ทดลอง **การอ่าน/ตรวจ/คำนวณแบบ bounded batches** โดยใช้
snapshot และ content digest เดิม; ยังสแกน input ทั้งชุดทุกหน้า
เป้าหมายคือลดการสร้าง objects/context/การตรวจข้อมูลเดียวกันซ้ำ และไม่สร้าง
ผลของแท่งนอก output page ไม่ได้อ้างว่าตัดการอ่านประวัติหรือ recursive work ออกแล้ว

## ทางเลือกที่พิจารณา

| ทางเลือก | ผลที่คาดจากหลักฐาน | ผลต่อสัญญา/ข้อจำกัด | ข้อเสนอรอบนี้ |
|---|---|---|---|
| ลดต้นทุน batch ภายใต้ full scan เดิม | แก้ core/decode ที่เป็นต้นทุนส่วนใหญ่ และจำกัด CPU slices | ต้องเพิ่ม batch API ภายใน core.money และพิสูจน์ parity; ยังไม่ทราบว่าจะถึง30sหรือไม่ | ทดลองก่อน พร้อมด่านหยุดเมื่อไม่ผ่าน |
| checkpoint ของ state ต่อชุดข้อมูล | ลด recursive work ของหน้าถัดไป | หน้าแรก/cold miss ยังต้องคำนวณเต็ม; ต้องผูก L/U/as_of/digest และ invalidation; token6hไม่ใช่อายุข้อมูล | ยังไม่รวมในการอนุมัติรอบนี้ |
| worker เตรียมผลใน DB | APIอ่านได้เร็วเมื่อผลพร้อม | ต้องอนุมัติ process/writer/migration และ readiness/cold miss; Lเลื่อนทุกนาทีทำให้seedของชุดหนาแน่นเปลี่ยน ไม่ใช่ต่อท้ายstateได้เสมอ | ต้องเสนอแผน/requirements แยกหากรอบนี้ไม่ผ่าน |

ไม่เสนอเพิ่ม deadline/เพดานmemory/concurrency หรือลดจำนวนinput/output
เพื่อให้ benchmark ผ่าน ไม่มีการเพิ่ม readiness/staleness policy ให้ผู้ใช้ในรอบนี้

## ขอบเขตที่อนุมัติ — NC-34 Closed

เจ้าของอนุมัติ batch API, การประกอบ reader/core และเกณฑ์ PV-1..10 ในเอกสารนี้
เมื่อ 2026-10-10; ใช้แทนรายละเอียด implementation ของ baseline plan เฉพาะส่วน
ที่ระบุด้านล่าง ส่วนสัญญาตัวเลข/ข้อมูล/ความปลอดภัยและ V-1..18 เดิมยังมีผล

อนุมัติการขยาย batch API ด้านล่างและวิธีประกอบ reader/core แทนการเรียก
scalar operations/สร้างผลทุกจุดจากเส้นทางปัจจุบัน โดยใช้สัญญาตัวเลข NC-33 เดิม
NC-30..33 ที่ปิดแล้วไม่เปลี่ยนสูตรหรือเปิดใหม่; เพิ่มเพียงข้อเสนอ implementation
นี้ซึ่งยังไม่ใช่ข้อยกเว้นให้ข้ามกฎของ Money/Quantity หรือเปลี่ยนกฎการเทรด

Public inputs/state/results ที่มีหน่วยยังใช้ Money/Quantity; RSIใช้ Scalar
และ state/ผลทุกขั้นยัง scale18 ตามเดิม Batch operations อยู่ใน core.money
เท่านั้น รับ/คืนชนิดกลางที่ตรวจได้ ไม่รับ state จาก HTTP และไม่ส่ง state ในcursor
การอนุมัติรอบนี้ไม่ครอบคลุม persistent checkpoint, cache, worker, migration
หรือการผ่อนเกณฑ์ ถ้าแนวทางที่จำกัดไว้นี้ไม่ผ่านต้องหยุดและเสนอแผนถัดไป

## แนวทางและของเดิมที่ใช้ซ้ำ

### 1. Fetch กับ decode เป็นคนละช่วง

- `infra/market_data/indicator_reader.py` fetch RowMapping ไม่เกิน1,000ช่อง
  ใน snapshot เดิม เก็บ bufferหนึ่งbatch ไม่เรียก `storage.stored_rows()` ซึ่ง
  decodeทั้ง1,000แท่งแบบ synchronous ก่อนคืน control
- ใช้ `storage.parameters`, catalog SOURCE/PAIRS และ SQL selection/order เดิม
  แต่เพิ่ม queryเฉพาะF-11 ที่เลือก columnsที่ใช้จริง ไม่แก้ F-09 public reader
- readerส่งข้อมูลเป็น slicesไม่เกิน16ช่องให้ตัวตรวจ/คำนวณ แล้ว yield/check
  monotonic deadline และ disconnect หลังทุกslice รวมช่วงสร้าง input/hash
  ต้องวัด decodeและdriver result materialization แยก เพราะ driverอาจbuffer
  ทั้ง1,000แถว; การลด CPU sliceไม่ได้รับรองว่า query bufferingไม่ทำให้lagสูง
- ถ้า result materialization ยังเกิน100ms ให้ลด fetch batch size ภายในเพดาน
  1,000และวัด full-size ใหม่; ต้องไม่เพิ่มquery concurrencyหรือpool size
- ไม่ถือแถวที่มาจาก DB ว่าผ่าน domain invariant ทุกอย่างแล้วโดยปริยาย
  ใช้การตรวจเดิมของ money/market_data; malformed source ต้องยัง error
  ไม่ข้าม positivity, OHLC ordering, units, volume, timestamps หรือ fetch proof

### 2. ตรวจข้อมูลที่ไม่เปลี่ยนตามแท่งครั้งเดียวต่อ series

- เพิ่ม validated series descriptor ใน `core/indicators.py` สำหรับ source/pair/
  timeframe/quote/base และเวลาที่ backendส่งมา; ทุกrowยังต้องตรงdescriptor
- สร้าง Moneyศูนย์/Quantityศูนย์ของหน่วยนั้นครั้งเดียวแล้วใช้ซ้ำ แทนการสร้าง
  ที่ทุกแท่ง; ไม่ใช้ zero แทนค่าที่ไม่มีผล/gap
- แยก shared validation helpers ใน `core/market_data.py` เท่าที่จำเป็นให้
  Candleเดิมและ input batchของF-11เรียกตรวจเดียวกัน; Candle constructorเดิม
  ยังต้องตรวจเอง ไม่เปิด unchecked constructor/public bypass
- การตรวจ unitที่ immutable/ตรวจแล้วอาจใช้ผลdescriptorซ้ำ แต่ค่าการเงิน
  และ identity/time/finality ของแต่ละrowยังต้องตรวจตามเดิม

### 3. Batch operations ใน core.money

Public entry pointที่เสนอคือ
`advance_indicator_batch(state, inputs, *, output_indices, rounding)`:
inputsเป็นimmutable tupleของvalidated slot eventsไม่เกิน16ช่อง;
output_indicesเป็นtupleของindicesภายในbatchที่ไม่ซ้ำ/เรียงตามเวลา;
roundingต้องระบุและF-11ใช้TOWARD_NEGATIVEเท่านั้น
คืนimmutable batch resultซึ่งมีnext stateกับค่าของindicesที่เลือกเท่านั้น
stateรวมseries/formula identity, last slot, previous close, EMA/RSI/ATR/signal
averagesและbounded seed buffersที่ยังไม่ครบ; ค่าที่มีหน่วยทุกช่องใช้Money
controllerเก็บseed/finality/blocked/gap semanticsเดิมและส่งreset/accept/block
eventsที่ตรวจแล้วให้kernel ไม่ให้kernelเลือกข้ามข้อมูลที่ใช้ไม่ได้เอง
stateและeventsผิดseries/formula/order/typeต้องถูกปฏิเสธก่อนเริ่มคำนวณbatch
public financial typesไม่รับraw coefficientsหรือclient JSONแทนstateที่ตรวจแล้ว

- เพิ่ม `core/money/indicator_batch.py` รับ validated inputsไม่เกิน16ช่อง,
  stateที่ผูกseries/formula และ output selection; คืน stateและผลเฉพาะที่ขอ
  `core.indicators` ยังคุม gap/finality/warm-up และลำดับ slot
- Batch financial calculation ครอบด้วย context guardของ money ไม่ใช้ float
  หรือ financial Decimalนอกโมดูลmoney ใช้ limits/validation/roundingเดิม
  ไม่คัดลอก scale/range/rounding definitionsไปอยู่ในreaderหรือindicators
- อนุญาต private scratch coefficients ภายใน operationเช่น primitive exact ratio
  เดิม เพื่อลด temporary Money/Scalar objects; ไม่ persistหรือเปิดเผย coefficient
  เป็นstateAPI ค่า stateที่operationคืนยังเป็นMoney/Scalarที่ตรวจครบ
- scratchของแต่ละrecursive stepต้องปัด/ตรวจช่วงในจุดเดียวกับ scalar contract
  ห้ามรวมหลายแท่งแล้วปัดทีเดียว ห้ามเก็บ precisionลับสูงกว่าscale18
  exact overflowของ delta/TR/MACD/histogram ต้อง errorที่stepเดิมแม้แท่งนั้น
  อยู่นอก output page; ไม่เลือกข้าม errorเพื่อให้ requestสำเร็จ
- ต้องใช้ primitivesร่วมของ `indicator_arithmetic.py`/`rounding.py` และตัวตรวจ
  กลางของmoneyสำหรับ scratch-to-state ไม่สร้าง validation rulesชุดที่สอง
  internal transient numeratorที่เกินช่วงอนุญาตเฉพาะ mean/ratioตาม NC-33 เดิม
- ไม่เรียก `Money.__new__`, ไม่ใช้object field writesเพื่อข้ามconstructor,
  ไม่เปลี่ยน public Money/Quantity operations และไม่ปิด trapsสำหรับข้อมูลที่ผิด
- Pure single-step entry point และ batch entry pointใช้ transition implementation
  ร่วมกัน; ไม่คัดลอกสูตรชุดที่สองเพื่อให้ batchเร็วกว่า
  ใช้ independent exact oracleและ fixturesตรวจ ไม่ใช้ scalar wrapperที่เรียก
  kernelเดียวกันเป็นหลักฐานเดียวว่า kernelถูกต้อง
- ก่อนลง kernelกำหนด input/state/result records และ bounded operation signatures
  ใน test fixtures; ถ้าทำตามขอบข้างต้นไม่ได้ ต้องหยุดเสนอแผนใหม่ ไม่ข้าม invariant

### 4. Hash กับผลที่ส่งออก

- digest ยัง SHA-256 canonical header/records เดิมทุกbyte ทุกslotใน [L,U)
  ใช้inputที่ตรวจแล้วชุดเดียวกับคำนวณและsnapshotเดียวกัน
- เพิ่มการ serialize inputเป็นcanonical stringsที่ money boundary ครั้งเดียว
  ต่อrow แล้ว readerใช้stringsนั้นสำหรับrecord ไม่เรียก as_partsซ้ำเมื่อไม่จำเป็น
  ไม่ใช้ raw SQL text/Decimal reprแทน canonical serializationโดยไม่ตรวจ
- คงการตรวจข้อมูลทั้งชุดและstateที่ต้องใช้ แต่ materialize IndicatorPoint/
  IndicatorValue สำหรับ output pageเท่านั้น; state/seed/finality/refresh dependencies
  นอกpageยังเดินครบ ไม่มีการข้าม future recordในdigest
- continuationยังต้องคำนวณrevisionใหม่ครบก่อนcommit/response;
  การใช้batchไม่ให้เชื่อdigestหรือstateจากcache/clientแทนต้นทาง

## ผลต่อ snapshot, seed และ pagination

| เรื่อง | สัญญาหลังเปลี่ยนที่ต้องพิสูจน์ |
|---|---|
| Seed | L/U/as_ofเดิม; seedกลางต่อsegment ไม่ขึ้นกับpage sizeหรือbatch size |
| Snapshot | REPEATABLE READ, READ ONLY; SQLตั้งisolationก่อนSELECTแรก; ทุกrow/metadataในconnectionเดียว |
| Revision | canonical bytesและdataset_revisionเดิมเมื่อbounds/recordsเดิม; missing/finality/fetch proofยังรวมครบ |
| Retention | continuationยึดsigned boundsเดิม; timeเลื่อนอย่างเดียวไม่409; cleanupเปลี่ยนrecordจริงยัง409 |
| Cursor | format/HMAC/keyring/session/6h expiryเดิม; ไม่มีcheckpoint/stateในpayload |
| Writer race | readerก่อนcommitเห็นชุดเก่าครบ; continuationหลังcommitปฏิเสธเมื่อdigestเปลี่ยน |
| Failure | numeric422, dataset409, infra503, deadline504เดิม; ไม่มีpartial responseหรือfallback |
| Refresh | GETไม่enqueue; target/queue metadataและF-09POST/poll/commit flowเดิม |

## ผลต่อฐานข้อมูลและสิทธิ์

- ไม่มี migration/ตาราง/index/revision counter/new writer หรือ cacheในรอบนี้
  F-11ยังอ่าน market_candles/demand ผ่าน API roleเดิม; F-09เขียน/cleanupตามเดิม
- ไม่เพิ่มสิทธิ์APIหรือmarket-data ไม่มีการอ่านkey/secretsหรือข้อมูลการเทรด
- dedicated pool1/overflow0/pool timeout250ms และ statement/lock budgetsเดิม
- rollbackด้านDBไม่มี schema/grantsให้ย้อน; rollbackโค้ดกลับ reader/kernelเดิมได้
  แต่แบบเดิมยังไม่ผ่านV-15 จึงไม่ทำให้ rollbackแล้วสามารถmerge/Completedได้
- ถ้าพบว่าต้องใช้ migration/cache/checkpoint/worker ไม่อยู่ในขอบอนุมัตินี้
  ต้องเสนอผลต่อgrants, retention, readiness, cold miss และ rollbackใหม่ก่อนลงมือ

## ไฟล์ที่เสนอให้แก้

| Path | งาน |
|---|---|
| `backend/src/tiewtrade/core/money/indicator_batch.py` | operationแบบboundedและscratchภายในmoney |
| `backend/src/tiewtrade/core/money/{indicator_arithmetic,rounding,__init__}.py` | ใช้primitivesร่วมและexport batch API; คงoperationsเดิม |
| `backend/src/tiewtrade/core/{indicators,market_data}.py` | validated descriptor, shared validation, state/ผลตามช่วงที่เลือก |
| `backend/src/tiewtrade/infra/market_data/indicator_reader.py` | แยกfetch/decode/hash/core slicesและจำกัดbuffer |
| `backend/tests/core/{test_indicator_arithmetic,test_indicators}.py` | independent oracle, random/chunk parity, numeric/error/ambient context |
| `backend/tests/infra/market_data/{test_indicator_reader,test_indicator_snapshot}.py` | rows/rawbuffer/race/digest/retention/permissions |
| `backend/tests/api/{test_indicator_routes,test_indicator_budgets,test_indicator_refresh_flow}.py` | resource/cancel/refresh/full flow |
| `backend/tests/api/profile_indicators.py` | จับเวลาของbatch entry pointใหม่และfetch/decodeให้ตรง; เก็บbaselineเดิม |

API schemaไม่จำเป็นต้องเปลี่ยน ถ้าsignatureภายในต่างจากข้างต้นให้บันทึกก่อนทำ
OpenAPI/typesต้องยังผ่านgenerated checks ไม่แก้frontendสูตรหรือเพิ่มUIในงานนี้

## ลำดับงานหลังอนุมัติและด่านหยุด

1. เจ้าของอนุมัติ NC-34 และเอกสารนี้ รวมextensionของ NC-33/plan/validation
   ที่ระบุในขอบเขตข้างต้น จึงเริ่มเปลี่ยน implementation
2. ทำ batch input/validation และdecode/yieldก่อน ตรวจ fixture parity, lag และRLS
3. ทำ money batch transitionร่วมกับsingle-step; เพิ่ม independent oracleและ
   ตรวจ rounded-state/overflowทุกขั้น ก่อนต่อreaderเข้าทางใหม่นี้
4. Profile1,000/10,000ช่องเพื่อดู phase/call volumeและlag; ขนาดsampleไม่ใช่
   เกณฑ์ผ่านและห้ามปรับ30s deadlineของHTTPเพื่อให้ผ่าน
5. รัน full-size cold1/warm5 กับ APIจริงบน2vCPU/1GiBตามV-15
   ถ้า coldคืน504หรือผล/lag/memoryผิด ให้หยุดก่อนwarmต่อและบันทึกfailure
   การแก้bugภายในขอบนี้ทำได้ แต่การเปลี่ยนarchitecture/สูตร/เกณฑ์ต้องอนุมัติใหม่
6. เมื่อfull-sizeผ่าน จึงรัน writer/rejected-load, concurrency, disconnect/cleanup,
   refresh flow และregressionที่ค้างครบ ไม่ถือว่าperformanceผ่านแล้วจบF-11

## เกณฑ์ validation ที่เพิ่ม — Approved; ยังไม่ได้รัน

| ID | เกณฑ์ |
|---|---|
| PV-1 | แบ่งbatch1/2/16 และ fetch16/64/1,000 ให้ผล/status/seedทุกจุดและdigestตรง independent expected; สุ่มราคา/gaps/finality/refresh และเปลี่ยนambient context |
| PV-2 | ขอบseed20/50/200,15,26/34, fractional rounding, tiny gains/losses, unit/type/nonfinite และexact overflowต้องเหมือนNC-33ทุกstep แม้ไม่มีoutputของstepนั้น |
| PV-3 | byte fixtures/digestของinputเดิมตรงbaseline; backfill/finality/observed_at/fetch proof/deleteทุกfieldยังinvalidate และqueue/last_checked/outsideUไม่invalidate |
| PV-4 | มีyield/checkdeadlineทุกCPU slice<=16ช่อง ทั้งdecode/hash/core; วัดquery bufferingแยก; ไม่โหลดinputทั้งชุดหรือผลทุกหน้าค้างไว้ |
| PV-5 | เตรียมfixtureในprocessแยกจากAPIที่วัด; วัดidle RSSหลังstartupก่อนrequest และpeak RSSของprocessเดียวกันระหว่างrequest ไม่ลบhigh-water markที่เกิดตอนเตรียมfixture |
| PV-6 | full-size525,600ช่อง cold1/warm5 ต้อง200พร้อมค่าที่ตรวจแล้ว/digest/output1,000ช่องภายใน30s; RSS delta<=128MiB, lag<=100ms, response<=2MiB |
| PV-7 | ใช้fixtureราคาคงที่และราคาที่เปลี่ยนทิศ/มีเศษละเอียด เพื่อให้RSI percentage_shareทำงานจริง; ไม่มีการเปิดตลาดหรือส่งออเดอร์ |
| PV-8 | active reader/writer race, pooledconnectionหลังcancel, slotไม่releaseก่อนquery/connectionหยุดจริง, cleanup<=2s และadmissionหลายprocessผ่านV-15เดิม |
| PV-9 | มีleading gaps/full warm-up/refresh-blocked segments/cross-retentionตามV-4..14/V-17..18เดิม; no partial responseและrestartbudgetเดิม |
| PV-10 | ด่านbackend/frontend/generated/API-secret canaryทั้งหมดผ่าน; จัดการWindows symlink gateด้วยการรันLinuxตามCI และfull regressionจบจริง |

## บันทึกการอนุมัติ

เจ้าของอนุมัติให้ทำการปรับbatchภายในขอบนี้ พร้อม validation PV-1..10 และ V-1..18เดิม
โดยยังคง full-scan revision, สูตร/rounding, Money/Quantity invariants และเกณฑ์
30s/100ms/128MiB; ไม่มีการอนุมัติแนวทาง checkpoint/workerหรือผ่อนเกณฑ์ล่วงหน้า
หากยังไม่ผ่านจะใช้หลักฐานใหม่เสนอแผนต่อไปก่อนเปลี่ยนimplementationนอกขอบนี้
