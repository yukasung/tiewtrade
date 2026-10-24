# F-11 — คำนวณ indicator ที่ backend — Plan

## Development smoke — Approved 2026-10-24

**คำสั่งล่าสุด — Deferred, Approved 2026-10-24:** เจ้าของอนุมัติหยุดการรัน
smoke แบบจับเวลาในรอบพัฒนานี้และเลื่อนไปตรวจรับรวมชุดที่ 9 ตาม testing หัวข้อ 7.
ข้อความอนุมัติด้านล่างเก็บเป็นประวัติ/ขอบเขต harness ไม่ใช่คำสั่งให้รันต่อทันที
หรือรันซ้ำท้ายทุกงาน. steady ถูกหยุดตามคำสั่ง (exit130; progress ล่าสุด180s,
BTC8/8) ไม่ใช่ Passed; dirty/rejected-load ยังไม่รัน. หลักฐานอยู่ใน
`profiling/release-20261024/README.md`. คง C5/C4/C6 ส่วนโหลดเต็มและ ETH เป็น
Pending Full Validation พร้อมผล Failed/Partial เดิม; correctness/safety และ
candidate gates ที่ไม่เลื่อนยังบังคับ. ไม่เปลี่ยนข้อกำหนดผลิตภัณฑ์หรือ production.

เจ้าของอนุมัติ smoke BTCUSDT ครบ 8 timeframe: steady 300s และ dirty พร้อม
rejected load 300s; ใช้ harness `profile_capacity_steady.py` เดิม เพิ่มโหมด
`--smoke` ที่แยกชื่อผล SMOKE ออกจาก R2-C*. Default full run ยังคง3600s.
ตรวจ readiness เฉพาะ BTC ใน smoke แต่ไม่แก้ catalog/production และไม่ลบ ETH
จาก isolated fixture; background worker/source ของ fixture เดิมยังทำงานตามจริง.
คง cadence observer10s/probe60s, parity/resource/error assertions เดิม;
รายงาน30observations/5probe rounds ต่อseries และ200rejectionsในdirty phase.
สัดส่วน availability เดิมใช้กับจำนวนรอบ smoke ไม่ใช่หลักฐาน full acceptance.
ตรวจ duration/counts/gate separation และ prerequisite ไม่ให้ smoke ปิด full gate;
รัน lint/types และ tests ที่กระทบก่อนใช้จริง. คง C5/C4/C6 และ ETH Pending
Full Validation; ผล smoke ไม่แทนการวัด60+60นาทีในชุดที่9หรือเปิด production.

## เลื่อน full validation เพื่อพัฒนาต่อ — Approved 2026-10-24

เจ้าของอนุมัติด้วย “approve” ให้เลื่อน C5, C4/C6 ส่วนที่พึ่ง full workload และ
การตรวจรับครบทุก timeframe ไปชุดที่ 9 หลังพัฒนาชุดที่ 8 เสร็จ ตามลำดับเดิม.
คงขอบเขต 8 timeframe ไม่ลดเหลือ 1m; BTC-only amendment ด้านล่างยังเป็น
ขอบเขตของ checkpoint ที่เลื่อน ไม่ใช่การรับรอง ETH หรือเปลี่ยน production/F-38.
ยังไม่ปรับ harness scope หรือเริ่มโหลดเพื่อ checkpoint นี้ในรอบพัฒนาปัจจุบัน.
คง Pending Full Validation และผล Failed/Partial เดิมจนมีหลักฐานครบ;
ผล C1/C2/C3 ที่ผ่านเก็บตาม scope/รุ่นที่วัดจริงและตรวจความใช้ได้ก่อนนำกลับมาใช้.
ระหว่างพัฒนาต้องตรวจ correctness, safety และ regression ตามผลกระทบ;
ก่อน merge ต้องผ่าน candidate gates ที่ไม่เลื่อนทั้งหมด รวม review และ required CI.
F-11 คง Development Complete ไม่ใช่ Completed; ต้องตรวจรับครบก่อนใช้เงินจริง
หรือเปิดให้คนนอก และไม่อนุมัติ production PREPARED, commit/push/merge
หรือข้ามจุดอนุมัติ spec ของ feature ถัดไป.


## BTC-only checkpoint amendment — Approved 2026-10-24

เจ้าของยืนยันขอบเขตพร้อม requirements/validation: F-11 checkpoint ปัจจุบัน
ตรวจ workload และ readiness เฉพาะ BTCUSDT ครบ 8 timeframe.
ใช้ `backend/tests/services/indicator_builder/profile_capacity.py` และ
`profile_capacity_steady.py` เดิม โดยเพิ่มการเลือก scope เฉพาะการรัน checkpoint;
ค่า default ของ harness ยังตรวจ runtime ทุกคู่ตาม catalog เดิม และไม่แก้ production.
รายงานต้องระบุ scope ที่เลือกและ ETH Pending แยกจาก runtime readiness ทั้งระบบ;
ไม่เรียก BTC 8/8 ว่า BTC+ETH 16/16. ตรวจ selector/observer/report และ callers
ที่ได้รับผลกระทบก่อนใช้จริง โดยไม่ตัด safety regression หรือเปลี่ยน threshold.
ผล C1/C2/C3 เดิมที่ตรวจขอบเขตกว้างกว่ายังคงใช้เป็นหลักฐานเดิมได้เมื่อ dependencies
ไม่เปลี่ยน; ห้ามแก้ artifact ย้อนหลังหรือปิดผล Failed/Pending โดยไม่มีหลักฐาน.
การอนุมัตินี้ไม่ใช่คำสั่งเริ่มโหลดทันทีหรือ commit/push/merge.

## Publication checkpoint-boundary optimization — Approved (2026-10-24)

เจ้าของสั่ง “เริ่มทำต่อ” หลังเสนอขออนุมัติ amendment นี้และ validation คู่กัน.

ขอบเขตที่เสนอหลัง bounded diagnosis: เพิ่ม migration ใหม่ถัดจาก head ปัจจุบัน
เพื่อปรับเฉพาะ checkpoint completeness predicate ใน `publish_indicator_generation`.
ใช้ `market_timeframe_advance` เดิมและสูตร expected_count/bounds เดิม; materialize
expected boundaries ครั้งเดียวก่อน anti-join ป้องกัน planner เรียกฟังก์ชันซ้ำต่อคู่.
ไม่แก้ migration เดิม, timeout500ms, retry30/60s/budget3, attempt120s,
freshness600s, locks/fences/publication atomicity หรือกฎ trading/เงิน.
ตรวจ migration head อีกครั้งก่อนกำหนดเลข; downgrade คืน predicate เดิมอย่างแม่นยำ.
ใช้ pattern การแทน function definition จาก `backend/migrations/versions/0026_week_month_timeframes.py`
และ actual-role publication tests เดิมใน `backend/tests/infra/indicators/` ก่อนเพิ่มของใหม่.
เริ่ม implementation ตามขอบเขตที่อนุมัติข้างต้น; ไม่ขยายไปเปลี่ยน threshold.

## Exact fixture lifecycle clock amendment — Approved 2026-10-24

เจ้าของสั่งเริ่มทำหลังเสนอ NC-F11-CLOCK: แยก calculation snapshot/bounds ของ
525,600-slot fixture ออกจาก wall clock ของ retry/lease/deadline เฉพาะ harness.
ใช้ `tests/services/indicator_builder/profile_capacity.py` และ
`capacity_instrumentation/sitecustomize.py` เดิม; ไม่แก้ production/migration/threshold.
เปลี่ยนเฉพาะ SQL calculation-bounds function ในฐาน isolated และ calculation window
ของ captured snapshot; เก็บ snapshot as_of จริงเพื่อคง attempt/query deadline เดิม.
คืน definition/marker ใน cleanup; ห้าม replace clock_timestamp ทั้งกลุ่มอีก.
Harness รอ nonterminal transient ตาม retry/backoff เดิมภายใน deadline600s;
terminal failure ต้องหยุด. ตรวจ exact bounds, lifecycle time และ cleanup ก่อน reproduction.

สถานะ: **Approved** — เจ้าของอนุมัติทั้งฉบับเมื่อ 2026-10-10 ตามคำสั่ง “approve”; requirements อนุมัติและ NC-30..33 ปิดแล้ว; รวมNC-35 amendmentsที่อนุมัติเมื่อ2026-10-10
การลบ MACD ด้านล่าง: **Approved** — เจ้าของอนุมัติ amendment เมื่อ 2026-10-13
วันที่: 2026-10-10
Branch: feature/f-11-backend-indicators

## Amendment — ลบ MACD ทั้งระบบ (Approved 2026-10-13)

ขอบเขต: แทนเฉพาะชุดผล indicator และ state/rollout ที่พึ่ง MACD ในแผนเดิม;
สูตร EMA20/50/200, RSI14, ATR14 และสัญญาความปลอดภัยอื่นคงเดิม.

1. ใช้ `core/money/indicator_batch.py` และ `core/indicators.py` เดิมต่อ:
   ตัด EMA12/26, MACD signal state และผล MACD ทั้งสามออกจาก kernel, NAMES,
   output tuple และ guard ของ state. ปรับ index/seed/RESET/HOLD อย่างเป็นระบบ;
   ไม่เปลี่ยนสูตร/การปัดของ EMA20/50/200, RSI14, ATR14. เพิ่ม parity oracle
   ของชุดที่เหลือและกรณี gap, overflow, warm-up, checkpoint restore.
2. กำหนด `FORMULA_VERSION = indicators-v2` และ `CODEC_VERSION = 2` เพราะ state
   และผลลัพธ์เปลี่ยนรูป. ปรับ `infra/indicators/codec.py`, capabilities, claims,
   reader/builder/cursor ให้รับเฉพาะ schema และรุ่นที่ตรงกัน; ไม่ decode checkpoint
   v1 เป็น v2. ไม่ให้ cache หรือ ready head v1 ปรากฏใน API v2.
3. เพิ่ม migration ใหม่ (ไม่แก้ migration เดิม) เพื่อเปลี่ยน SQL functions/job
   และ rollout gates ที่ฝัง `indicators-v1`/codec 1 ให้รองรับรุ่นใหม่.
   ก่อนเปลี่ยน control ต้อง PAUSED, drain writer/API/worker เก่า และตรวจ inventory
   replica; ใช้ rollout epoch ใหม่. เก็บผล/ checkpoint v1 แยกด้วย version เดิม
   ตาม retention/rollback policy เดิม ไม่ลบหรือแปลงเป็น v2. สร้างงาน v2 ใหม่;
   ให้ LEGACY v2 กลับมาอ่านได้ก่อนพิจารณา PREPARED v2 ตาม gate เดิม.
4. ปรับ API/generated contract เฉพาะรายการผลที่ส่ง: ไม่มี MACD ในผลใหม่;
   error, auth, pagination, exact-value, proof และ retry contract เดิมคงอยู่.
   ข้อมูลหรือ cursor v1 ที่ส่งเข้าระบบ v2 ต้องถูกปฏิเสธอย่างมีขอบเขต
   ไม่ตอบข้อมูลผสมหรือ fallback เป็น v1.
5. ตรวจ diff/dependencies ก่อนทดสอบ. รัน core arithmetic/parity/codec,
   actual-role PostgreSQL migration/rollout/readers, API contract และ
   concurrency/retry regression ที่กระทบ; ไม่ส่งออเดอร์ Live.
   บันทึก full workload ที่เลื่อนเป็น Pending Full Validation ตามกฎเดิม.

หยุด implementation หาก inventory/drain หรือ migration รองรับการแยกรุ่นอย่าง
ปลอดภัยไม่ได้; เสนอ amendment เพิ่มก่อนเปลี่ยนสัญญา rollout ที่อนุมัติไว้.

## R2-D1 first-release amendment — Approved 2026-10-11

เจ้าของยืนยันว่าไม่เคยdeploy F-11 full-scan เดิม และอนุมัติ
[D1 first-release amendment](d1-amendment-proposal.md) ด้วยคำสั่ง “approve”.
ใช้เกณฑ์ทั้ง5ข้อใน amendment แทน R2-D1 legacy-F-11-binary เดิมเฉพาะส่วนนี้:
ทดสอบ pre-F-11 API/F-09จริงก่อนstrictproof และ compatibleF-11สองreplicas
ในLEGACYด้วยv1cross-replica/restart/fullscanparity พร้อมstagegate/drain/inventory
negativecontrols. ห้ามstubและไม่ผ่อนD2..D7/capacity/productionactivation.
D1เป็นPendingจนหลักฐานครบ ไม่ถือว่าการอนุมัติคือPassed


## เปลี่ยนลำดับการตรวจรับ — Approved 2026-10-11

เจ้าของยืนยันให้เลื่อนการทดสอบโหลดและความเสถียรระยะยาวไปตรวจรับระบบรวม
**ชุดที่ 9 — ตรวจรับระบบก่อนใช้งานจริง หลังพัฒนาชุดที่ 8 เสร็จ** ตาม [roadmap](../../roadmap.md#ชุดที่-9--ตรวจรับระบบก่อนใช้งานจริง)
ข้อความนี้แทนลำดับเดิมที่ให้รันทดสอบยาวทันทีท้าย implementation ของ F-11;
ไม่เปลี่ยนสูตร งบ ระยะเวลาวัด workload หรือเกณฑ์ผ่านของการตรวจรับ

ระหว่างพัฒนายังคงทดสอบความถูกต้อง ความปลอดภัย การคำนวณเงิน และ regression
ที่เกี่ยวข้อง ผล Failed/Partial เดิมและ API lag ที่พบยังเป็นงานค้าง ไม่ถือว่าผ่าน
R2-C2/C3/C5 รอบเต็มและการตรวจรับ capacity/ความเสถียรที่ต้องใช้ผลเหล่านั้น
ให้รวมในชุดที่ 9; การ profile สั้นและการแก้ปัญหาที่ทราบทำได้ระหว่างพัฒนา

เมื่อ implementation/review และด่านที่ไม่เลื่อนผ่านครบ จึงใช้สถานะ
Development Complete (พัฒนาเสร็จ รอตรวจรับระบบ) ตาม roadmap ได้ ไม่ใช่ Completed
เจ้าของอนุมัติ 2026-10-11 ให้ merge เพื่อพัฒนาต่อได้เมื่อ implementation/review และด่านที่ไม่เลื่อนผ่านครบ ตาม [testing standard](../../standards/testing.md#1-ต้องเขียวก่อน-merge);
ข้อความนี้แทนเงื่อนไขก่อน merge ใน baseline ด้านล่างเฉพาะการตรวจรับโหลด/ระยะยาวและผลรวมที่พึ่งรอบนั้น; รายการอยู่ใน [ทะเบียนชุดที่ 9](../../roadmap.md#ทะเบียนงานค้างสำหรับชุดที่-9) ไม่ยกเว้นด่านอื่นหรือผล regression ที่ล้ม และไม่ใช่คำสั่งให้ commit/push/merge ตอนนี้ เงื่อนไข Completed และ production prepared activation เดิมยังมีผล
ต้องผ่านชุดที่ 9 ก่อน F-25 ใช้เงินจริงหรือเปิดให้คนนอก ระหว่างนี้ทดลองภายในด้วย Paper
ก่อนเริ่มทดสอบยาวให้ตกลงเวลากับเจ้าของอีกครั้ง


การเปลี่ยนแผนหลัง benchmark ไม่ผ่าน: [performance-plan.md](performance-plan.md)
เป็น **Approved / NC-34 Closed** ตามคำสั่ง “approve” เมื่อ 2026-10-10
ใช้แผน performance แทนรายละเอียดเส้นทาง batch ที่ระบุใน baseline ด้านล่าง
ส่วนสัญญาตัวเลข/ข้อมูล/ความปลอดภัยและเกณฑ์งบเดิมยังมีผล; พร้อมเปลี่ยนimplementation

NC-34ลงมือแล้วแต่coldยังไม่ผ่าน ดู[หลักฐานbatch](profiling/batch/report.md)
ข้อเสนอ architecture รอบ2อยู่ใน [performance-plan-v2.md](performance-plan-v2.md)
และ [ADR-002](../../decisions/002-prepared-indicators.md) — **Approved / NC-35 Closed**
เจ้าของอนุมัติrequirements/plan/validation amendmentsเมื่อ2026-10-10 ด้วยคำสั่ง “approve”; ใช้แทนbaselineเฉพาะส่วนที่ระบุเปลี่ยน
แก้reviewรอบ2ข้อ3: Error/retry contractในแผนรอบ2และADR-002เสนอfailureview
เพื่อคงnumeric422/noautomaticretryตามNC-33 พร้อมboundedtransientretryและ
operatorCLI recovery; เกณฑ์R2-F1..F6Approved/ยังไม่ได้รัน พร้อมเริ่มimplementationตามแผนรอบ2ที่อนุมัติ
แก้reviewซ้ำข้อ1: Numeric recoveryในแผนรอบ2แยกfailedkey/inputversionเดิมจาก
alignedbounds/seedwindowใหม่ พร้อมdurablesuppression/coalesce/budgetsและ
R2-N1..N4; Approvedแล้ว ไม่reusefailedstateหรือทำGETenqueue
แก้reviewซ้ำข้อ2: แผนรอบ2กำหนดsharedtransient/SUPERSEDEDbudget3attempts,
FAILED_SUPERSEDED/backoff/cooldownและDBfairroundที่ไม่resetด้วยcoalesce
พร้อมR2-S1..S5; Approvedแล้ว เก็บepisode deadlineเดิมเพื่อรายงานcapacity
แก้reviewรอบ2ข้อ4: แผนรอบ2/ADR-002ระบุsingletonglobalbuildslotร่วมกับ
session advisory lockบนpinnedwriter, safehandoffและR2-G1..G7; Approvedแล้ว
แก้reviewรอบ2ข้อ5: แผนรอบ2 S0..S5/ADR-002กำหนดcompatibility/drain/central
activation/rollback supportwindowสำหรับAPIและF-09ต่างเวอร์ชัน; Approvedแล้ว

เอกสารนี้เป็นแผนที่อนุมัติแล้วและพร้อมใช้เริ่ม implementation
ตัวเลข สูตร finality seed และ error semantics ต้องยึด requirements ฉบับที่เจ้าของ
อนุมัติจริง หากคำตัดสิน NC-30..33 ต่างจากข้อเสนอด้านล่างให้ปรับแผนและ validation
ก่อนขออนุมัติรอบนี้ ห้ามเขียนโค้ดให้ต่างจากแผนที่อนุมัติแล้ว

## แนวทาง

Capacity harness R2-C1 ใช้ catalog เดิม (`infra/market_data/catalog.py`),
`Timeframe`/alignment จาก core, launcher/supervisor/scheduler จริงจาก
`services/indicator_builder/`, `proof_valid` จาก `infra/indicators/prepared.py`
สำหรับ API-role observer และ `read_indicators` full-scan สำหรับตรวจผล probe
หลัง measured phase. แยก PostgreSQL/Redis/container ของ capacity จาก application
และ integration tests; ใช้ authenticated HTTP เหมือน mixed-version harness.
เริ่มจาก derived tables ว่าง; C2/C3/C5 และ C6 ถูกบล็อกเมื่อ C1 ไม่ผ่านตามแผนรอบ2.
ไม่เปลี่ยนงบ/threshold หรือใช้ synthetic READY เพื่อทำให้ benchmark ผ่าน.
`tests/services/indicator_builder/profile_capacity_steady.py` ใช้ fixture/observer/
HTTP probe/full-scan audit ของ `profile_capacity.py` ซ้ำสำหรับ C2/C3/C5: 60 นาทีจริงต่อphase,
360 observer rounds/60 HTTP rounds, login จริงด้วยผู้ใช้ fixture เดิม และเก็บ
parity oracle ระหว่าง phase. หากพบ availability gap ให้รายงาน Failed พร้อม
ระยะที่วัดจริง ไม่อ้างว่า early failure เป็นการวัดผ่านครบ60นาที.
Instrumentation เฉพาะ container ทดสอบใช้ `profile_capacity_app.py` เก็บ API
lag/RSS/query count และ `capacity_instrumentation/sitecustomize.py` เก็บข้อมูล
จาก claim descriptor/attempt result จริงโดยไม่เพิ่ม database query หรือสิทธิ์ให้ worker.
รายละเอียด job/deadline มาจาก observer ภายนอก; C5 barrier อยู่หลัง admission จริง
เพื่อไม่ให้ rejected load แย่ง quota ของ accepted probes.

ใช้แท่งเทียนสาธารณะที่ F-09 เก็บไว้ใน PostgreSQL เป็น input เดียว
API ตรวจตัวตนและอ่านต้นทางภายใต้สิทธิ์เดิม แล้วส่งลำดับแท่ง/ช่วงขาด/หลักฐานเวลา
ให้ core คำนวณสูตรและสถานะของผล ไม่ให้ core อ่านฐานข้อมูลหรือนาฬิกา
API ส่งค่ากับสถานะเป็นข้อความเพื่อให้กราฟ F-12 และผู้ใช้ผลใน backend
ใช้ผลจากสัญญาเดียวกัน โดยไม่สร้าง signal หรือกฎส่งออเดอร์

หนึ่ง request อ่านหนึ่ง source/pair/timeframe กับ indicator ชุดเริ่มต้นทั้งหมด
backend เลือก seed กลาง ผู้เรียกเลือกได้เฉพาะช่วงผล ไม่เลือกจุดเริ่ม seed
ผลลัพธ์แต่ละแท่งมีเวลา UTC, source/pair/timeframe, รุ่นสูตร, รุ่นข้อมูล,
จุดเริ่ม seed, สถานะ และค่าที่พร้อมพร้อมหน่วยที่เหมาะสม
การคำนวณจาก input/รุ่นเดียวกันให้ผลเหมือนกันทั้งช่วงผลและ pagination

### ลำดับการทำหลังได้รับอนุมัติครบ

1. ปิด NC-30..33 ใน requirements และ mission ให้สูตร สัญญาตัวเลข finality
   วิธีระบุชุดข้อมูล/เพดานงานไม่เหลือคำถามที่บล็อก implementation;
   แก้แผนกับ validation ให้ตรง แล้วรับอนุมัติทั้งสองฉบับ
2. ทำตัวเลขอ้างอิงแยกจาก implementation และ test core ก่อนลงสูตรจริง
3. เพิ่มตัวอ่านแท่งต้นทางเป็นช่วงย่อยและตัวตรวจความคงเดิมของชุดข้อมูล
   ผ่าน session read-only เดิม; ทดสอบกับ PostgreSQL/บทบาทจริง
4. เพิ่ม API อ่านผลและ routing policy, สร้าง OpenAPI กับ frontend types
5. รันด่าน validation ทั้งหมด รีวิวขอบเขต/ประสิทธิภาพ/การรั่วข้อมูล
   แก้เฉพาะ F-11 แล้วตรวจครั้งสุดท้ายก่อนส่งให้เจ้าของ

## ของเดิมที่จะใช้ซ้ำ

| Path | ใช้ทำอะไร |
|---|---|
| `backend/src/tiewtrade/core/market_data.py` | `Candle`, `CandleFinality`, `Timeframe`, การจัดช่องเวลา UTC และช่องที่ขาด |
| `backend/src/tiewtrade/core/money/` | `Money`, `Quantity`, การตรวจหน่วย/ช่วง, context และกฎการปัดที่ได้รับอนุมัติแล้ว |
| `backend/src/tiewtrade/infra/market_data/{catalog,records,storage}.py` | source/pairs กลาง, `StoredCandle` ที่มี `fetch_started_at`, กฎ retention/การอ่าน/refresh เดิม |
| `backend/src/tiewtrade/infra/db/{engine,session}.py` | API role, `UserSession`, ขอบเขต transaction และสิทธิ์อ่านเดิม |
| `backend/src/tiewtrade/services/api/{candle_routes,authentication,routing_policy,safe_input_routes}.py` | รูปแบบช่วงอ่าน, middleware ตัวตน, กฎไม่ต่ออายุ session และ error ที่เป็นรหัส |
| `backend/src/tiewtrade/services/api/{app,openapi_export}.py` | ติดตั้ง route และสร้าง OpenAPI ตาม CI |
| `backend/tests/{core,infra/market_data,api}/` | patterns ของ pure tests, PostgreSQL roles และ route tests |
| `backend/src/tiewtrade/infra/indicators/{claims,pinned,scan,staging}.py` | worker orchestration ใช้ claim/physical writer, bounded scan และ terminal publication ที่ implement ตามแผนรอบ2แล้ว; ไม่สร้าง ownership/retry/codec protocol ซ้ำ |
| `backend/migrations/versions/0016_indicator_build_claims.py`, `0017_indicator_staging.py`, `0018_indicator_publication.py` | scheduler/coalesce ใช้ catalog seed, numeric suppression, durable fair round และ terminal transitions เดิม; migration0019เพิ่ม failure source boundary และรวม SQL bounds ที่ใช้ใน seed/staging/coalesceไว้ที่เดียว |
| `backend/src/tiewtrade/services/indicator_builder/attempt.py`, `backend/src/tiewtrade/infra/indicators/{pinned,scheduling}.py` | scheduler dispatch ผ่าน single-attempt เดิม; poll ระหว่าง scan ใช้ transaction สั้นบน physical writer เดิมโดยไม่เพิ่ม connection หรือ takeover orphan |
| `backend/src/tiewtrade/services/indicator_builder/{scheduler,attempt}.py`, `backend/src/tiewtrade/infra/db/{engine,session}.py`, `backend/migrations/versions/0016_indicator_build_claims.py` | launcherใช้ scheduler/pool2 เดิม, สร้าง ownerต่อbootและsupervise childครั้งเดียว; operator recoveryตรวจ stopped container แล้วใช้ migrator role/helper reapเดิมแบบ compareidentity ไม่ให้ runtime credentialเรียก reap |

Manual retry/GC ใช้ `backend/src/tiewtrade/infra/indicators/session.py`
และ `backend/src/tiewtrade/infra/db/session.py` สำหรับ actual-role transaction/budgets,
`backend/src/tiewtrade/services/indicator_builder/main.py` สำหรับ fixed CLI output,
และ job suppression/fair round/episode fields จาก migrations0015..0019 เดิม;
migration0020 เพิ่ม restricted retry/GC functions กับ journal retention timestamp
(timestamp ใช้เพื่อ retention เท่านั้น ไม่ใช้แทน commit-ordered source proof).
GC ไม่ลบ retry request records เพราะผล idempotency ต้องคงเดิมข้าม cycle.
Migration0021 ใช้ definitionจาก0020ซ้ำและแก้ pressure predicate ให้แยก
live-tuple storage chargesพร้อมheap/index/TOAST reservesจากallocated files;
threshold3GiB/bounded batchesเดิม ไม่เพิ่มVACUUMหรือเปลี่ยนsource/ownership protocol.
Prepared API ใช้ `infra/market_data/indicator_reader.py` สำหรับ fetch/decode/core slices,
query budgets และrefresh observationsเดิม โดยเพิ่ม restored-stream suffix mode;
ใช้ `infra/indicators/codec.py` เพื่อstrict restore, `infra/crypto/indicator_cursor.py`
เพื่อcanonical/HMAC/session bindingเดิม และ`infra/db/session.py` เพื่อAPI-role RO snapshot.
Migration0022เพิ่มcandidate orderingในREADY viewและmanifest_availableในsanitized
numeric failure view เพื่อไม่fallbackoldheadหลังmanifestGC ไม่มีAPI base-table grantsเพิ่ม.
Rollout orchestration ใช้ `infra/indicators/recovery.py` สำหรับ bounded Docker runner
และ verified stop/reap เดิม, `infra/db/session.py` สำหรับ migrator role/budgets,
`activate_indicator_source_proof()` จากmigration0015 สำหรับ relation→guard maintenance,
และ READY/source journal จากmigrations0015..0022; migration0023เพิ่มเฉพาะtyped
CAS/replay/fresh-head gate และCLIเดิมใน`services/indicator_builder/main.py`.
Compose stop/drain/start และ external inventory/keyring/gate attestationsอยู่ใน
[rollout runbook](rollout-runbook.md); ไม่สร้างdeploymentplatformหรือautomaticactivationใหม่.

Mixed-version acceptance ใช้ `tests/services/indicator_builder/profile_container_recovery.py`
สำหรับ bounded Docker commands, `tests/infra/indicators/test_rollout.py` สำหรับ
actual-role CAS/replay/drain predicates, `infra/indicators/pinned.py` และ
`services/indicator_builder/attempt.py` เพื่อสร้าง READY/checkpoints จริง;
ใช้ `tests/api/conftest.py` เป็นแบบของ HTTP authentication และ
`infra/market_data/indicator_reader.py` เป็น full-scan parity reference.
Harness รัน immutable compatibility/prepared images เป็น API คนละ process บน
isolated PG/Redis; ไม่แทน legacy decoder ด้วย stub. R2-D1 ต้องมี preserved
legacy F-11 full-scan artifact และ R2-D7 ยังขึ้นกับ capacity/regression release gates.

ค้นแล้วไม่พบสูตร EMA/RSI/MACD/ATR ใน backend ปัจจุบัน จึงเพิ่มสูตรใน core
ที่เดียว ไม่คัดลอกไว้ใน API หรือ frontend

## ส่วนที่จะสร้าง/แก้

| ไฟล์หรือพื้นที่ | งานที่เสนอ |
|---|---|
| สร้าง `backend/src/tiewtrade/core/indicators.py` | ชนิดผล/status และ state machine ของ EMA20/50/200, RSI14, MACD12/26/9, ATR14; รับลำดับ input และ `as_of` จากผู้เรียก |
| สร้าง `backend/src/tiewtrade/core/money/indicator_arithmetic.py`; แก้ `core/money/{rounding,__init__}.py` | เพิ่ม Scalar และ divide_money/weighted_mean_money/percentage_share ตาม NC-33; เพิ่ม primitive ปัดผลหาร exact ใน rounding กลางและ export API โดยคง operation เดิม |
| สร้าง `backend/tests/core/test_indicator_arithmetic.py` | golden values/rounding/sign/units/overflow และความคงเดิมของ Money/Quantity เดิม |
| สร้าง `backend/src/tiewtrade/infra/market_data/indicator_reader.py` | อ่านต้นทางเป็นช่วงไม่เกิน 1,000 ช่องตามลำดับ ภายใต้ภาพข้อมูลเดียวกัน; ตรวจ retention/เพดานรวม seed; ตรวจตัวตนชุดข้อมูลเมื่ออ่านต่อ |
| แก้ `backend/src/tiewtrade/infra/db/{session,__init__}.py` | เพิ่ม `indicator_read_session` ที่ตั้ง REPEATABLE READ/READ ONLY ก่อน query แรก แล้วตรวจ role/RLS ด้วยกลไกเดิม; ไม่เปลี่ยน transaction ของผู้เรียกเดิม |
| สร้าง `backend/src/tiewtrade/services/api/{indicator_admission,indicator_settings}.py`; แก้ `app.py` | จำกัดงาน F-11 ต่อ process, deadline/cancellation, dedicated API-role pool และค่าตั้งงบที่ตรวจได้ |
| แก้ `backend/src/tiewtrade/infra/realtime/admission.py`, `config/redis.acl` | ใช้ fixed-window admission เดิมซ้ำโดยเพิ่ม namespace/subject parameters ที่คง defaults F-10; เพิ่มสิทธิ์เฉพาะ key prefix F-11 |
| เพิ่ม `backend/tests/api/test_indicator_budgets.py` และ integration admission tests | deadline, concurrent admission, Redis failure, disconnect/cancel และ regression ของ F-10 |
| สร้าง `backend/src/tiewtrade/infra/crypto/indicator_cursor.py`; แก้ `infra/crypto/{keys,__init__}.py` | HMAC cursor codec และ KeyPurpose.INDICATOR_CURSOR ใช้ KeySource เดิม; validation แยกสำหรับ keyring F-11 โดยไม่เปลี่ยนผู้ใช้ crypto เดิม |
| แก้ API `app.py`/configuration documentation และ test setup | โหลด cursor keyring ตอน startup ทุก replica; เพิ่มค่าทดสอบเฉพาะ dev/CI และคำแนะนำ rotation โดยไม่ commit กุญแจใช้งานจริง |
| เพิ่ม `backend/tests/infra/crypto/test_indicator_cursor.py` และ API cursor tests | expiry, tamper, session binding, key rotation และ log redaction |
| สร้าง `backend/tests/infra/market_data/test_indicator_snapshot.py` | actual PostgreSQL isolation/read-only, concurrent writer, pagination digest และ pool cleanup |
| สร้าง `backend/src/tiewtrade/services/api/indicator_routes.py` | schema request/response, auth, ปฏิเสธ input/error ตามรหัส, ประกอบ reader กับ core โดยไม่มี venue call |
| แก้ `backend/src/tiewtrade/services/api/{app,routing_policy}.py` | เพิ่ม route ที่คุ้มครองและไม่ต่ออายุ session |
| สร้าง `backend/tests/core/test_indicators.py` | ตัวเลขอ้างอิง/คุณสมบัติ/gap/finality/seed ที่ตรวจซ้ำได้ |
| สร้าง `backend/tests/infra/market_data/test_indicator_reader.py` | อ่านหลายช่วง, snapshot/revision, actual role, ขอบ input/retention, race ของ backfill/refresh |
| สร้าง `backend/tests/api/test_indicator_routes.py` | auth, contract, pagination, 409/422 และไม่มีค่าที่พึ่งข้อมูลไม่พร้อม |
| สร้าง `backend/tests/api/test_indicator_refresh_flow.py` | ผู้ใช้ผลจำลองเรียก GET indicator → POST request เดิม → GET candles → GET indicator ใหม่ ครบ auth/CSRF/commit/failure และ duplicate requests |
| สร้างหรือแก้ API contract artifact: `backend/openapi.json`, `frontend/src/api-types.ts` | regenerate ให้ตรงกับ endpoint ใหม่; frontend ไม่คำนวณ indicator ใน F-11 |

ชื่อโมดูลและเส้นทางข้างต้นเป็นข้อเสนอสำหรับรีวิว หากเปลี่ยนหลังอนุมัติแผน
ต้องบันทึกและขออนุมัติการเปลี่ยนก่อนทำตามกฎ AGENTS.md

## อ่านต้นทางและรุ่นข้อมูล

ข้อเสนอหลังแก้ deep review ข้อ2: ใช้ **REPEATABLE READ, READ ONLY ต่อหน้า**
และ SHA-256 ของ input ทั้งชุดเป็น content revision ไม่เพิ่มตาราง revision
หรือ cache ในแนวทางนี้ การอ่านทุกหน้าสแกนชุดที่ตรึงไว้ทั้งหมดทีละช่วงย่อย
เพื่อพิสูจน์ว่าไม่มีข้อมูลเปลี่ยน; เจ้าของอนุมัติแนวทางและเกณฑ์งบทรัพยากรก่อน
implementation แล้วพิสูจน์ต้นทุนด้วย benchmark ของ implementation จริง
ผลผ่านเป็นเงื่อนไขก่อน merge หรือเปลี่ยนสถานะเป็น Completed ไม่ใช่ก่อนอนุมัติแผน

### Transaction lifecycle

1. middleware ตรวจ auth ตามเดิมก่อนเริ่มงาน แล้วใช้ connection ของ API role
   ผ่าน helper ใหม่ `indicator_read_session` ภายใน `infra/db/session.py`
2. เริ่ม transaction และให้คำสั่งแรกของ transaction เป็น
   `SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY`
   **ก่อน** `_assert_role`, `SELECT set_config`, การอ่านเวลา หรือ query ข้อมูลใด ๆ
   ห้ามเปิด `user_session()` เดิมแล้วค่อยตั้ง isolation เพราะ helper เดิม query แล้ว
3. ใช้ `_assert_role` และ transaction-local user setting เดิม แล้วคืน `UserSession`
   ให้ reader; ไม่คืน raw connection ให้ service และไม่เพิ่มสิทธิ์ฐานข้อมูล
   reader อ่านเวลา reference หนึ่งครั้งจาก DB; ภาพข้อมูลยึด snapshot ของ transaction
   เวลา reference เป็นเกณฑ์รับแท่ง ไม่ใช่หลักฐานว่าเห็น commit ทุกอันก่อนเวลานั้น
4. อ่าน bounds, candles, gaps, finality และ metadata คิว F-09 ด้วย session เดียวกัน
   ภายในภาพข้อมูลนั้น; ไม่เปิด transaction ใหม่ต่อช่วง ไม่เรียก refresh/enqueue
   หรือใช้ SELECT FOR UPDATE ระหว่างอ่าน และไม่ใช้ connection ที่สองตรวจรุ่น
5. สแกนจนจบขอบเขตชุดข้อมูลและตรวจ digest ก่อนส่ง HTTP body ใด ๆ
   เก็บเฉพาะ state/ผลหน้าปัจจุบันและ buffer ไม่เกิน 1,000 ช่อง
   commit สำเร็จจึงคืนหน้า; exception/cancel ต้อง rollback และคืน connection
   ถ้า commit/DB ล้มเหลวให้ error ของ infra เดิม ไม่แปลงเป็น 409 โดยไม่มีหลักฐาน
6. ห้ามถือ transaction ข้าม HTTP requests หรือ export snapshot ค้างเพื่อ pagination
   helper ใช้ SET TRANSACTION เฉพาะ transaction นี้ ไม่เปลี่ยน default isolation
   ของ pool; ทดสอบ connection reuse ว่า read-only/RLS ไม่ค้างไปคำขอถัดไป

อ้างอิง PostgreSQL16: [Repeatable Read](https://www.postgresql.org/docs/16/transaction-iso.html#XACT-REPEATABLE-READ)
และ [SET TRANSACTION](https://www.postgresql.org/docs/16/sql-set-transaction.html)
ภาพข้อมูลคงที่ใน transaction ไม่ได้หมายความว่าข้อมูลยังล่าสุดตอนส่ง HTTP
writer อาจ commit หลัง snapshot; หน้าปัจจุบันคืนรุ่นเก่าอย่างสอดคล้องได้
หน้าถัดไปที่เริ่มหลัง commit จึงตรวจพบการเปลี่ยนและคืน 409

### ขอบเขตชุดกลางและการสะสม seed

หน้าแรกตรึง `as_of` จาก DB และช่วงกลาง `[L,U)` ของ series:
`L = align_ceil(retention_cutoff(as_of), timeframe)` และ
`U = align_floor(as_of, timeframe)` เพื่อรวมเฉพาะช่องที่หมดเวลาแล้ว
ขอบกลางนี้ไม่ขึ้นกับ start/end/page size ของช่วงผลที่ผู้เรียกขอ
ช่วงผลต้องอยู่ภายในขอบกลางและตรงขอบแท่ง; input ผิดให้ error เดิม ไม่ clamp

เดินทุกช่องตั้งแต่ L ตามลำดับ รวมช่องว่างก่อนแท่งแรกด้วย; เมื่อพบ gap จริง
เริ่ม segment ใหม่ และใช้แท่งที่เข้าเกณฑ์ใน segment สะสม seed ตาม NC-30/31
ถ้าพบแท่งต้อง refresh ก่อน seed ครบต้องค้าง segment นั้น ไม่ข้ามไปเริ่ม seed
จากแท่งที่พร้อมถัดไป เก็บ seed-open ของแต่ละ segment ที่ผลหน้าปัจจุบันอ้างถึง
การเติมแท่งก่อน seed เดิมภายใน [L,U) จึงเปลี่ยน digest และคำนวณ seed ใหม่

หน้าถัดไปใช้ L/U/as_of เดิมจากตัวอ้างอิงที่ตรวจความถูกต้องแล้ว
การตรวจ retention สำหรับชุดเดิมยึด as_of ที่ลงนามไว้ ไม่ตรวจ L กับ cutoff
ของเวลาคำขอถัดไป; เวลาปัจจุบันใช้ตรวจ session/token expiry ตามเดิม
reader อ่านแถวที่ยังมีอยู่จริงครบ [L,U) ใน snapshot แล้วเทียบ content digest
กับชุดเดิม แม้บางแถวพ้น cutoff ปัจจุบันแต่ cleanup ยังไม่ลบก็ยังตรวจซ้ำได้
ถ้า cleanup ลบแถวที่เคยอยู่ในชุด digest ต้องเปลี่ยนและคืน409 ไม่มีผลบางส่วน
ห้ามแทนแถวที่หายด้วย state เก่า ห้ามเลื่อน L หรือเลือก seed ใหม่ใต้ token เดิม
ถ้าเวลาเพียงเลื่อนผ่าน leading MISSING slots โดยไม่มี record เปลี่ยน
digest ยังเดิมและอ่านต่อได้; ตรวจ token/MAC/auth ก่อนใช้ขอบเวลานี้เสมอ

นี่เป็นข้อเสนอเฉพาะ continuation ของ F-11 ภายใต้ NC-32: หน้าแรกยังใช้
retention ปัจจุบันตาม F-09; ไม่เปลี่ยน F-09 public GET/POST, cleanup หรือเวลาเก็บ
indicator_reader ต้องแยกการตรวจช่วงหน้าแรกกับ signed continuation และอ่าน
ผ่าน UserSession เดิม ไม่เรียกตัวตรวจ public window ของ F-09 ด้วยเวลาปัจจุบัน
สำหรับ continuation; ไม่เปิดทางให้ raw start/end ขอข้อมูลย้อนหลังนอก retention
ไม่เพิ่ม persistent snapshot/cache/migration หรือรับรองอายุข้อมูลขั้นต่ำ6h
เมื่อ cleanup เปลี่ยน record จริงยังต้องเริ่มใหม่ตาม restart budget เดิม
แท่งที่เพิ่มหลัง U ไม่อยู่ใน digest และไม่ทำให้ชุดเดิมเริ่มใหม่

### Content revision และลำดับอ่าน

- ใช้ SHA-256 แบบ incremental ใน infra ไม่ใช้ Python `hash()`
  header ระบุ format-version, source/base/quote/timeframe, formula-version, L/U
  ตามด้วย record เรียง open_at ครบทุกช่อง ไม่มีการเรียงตามเวลาที่ดึงมา
- รูปแบบ bytes เป็น UTF-8 canonical JSON ของ array ต่อ record ตามด้วย newline
  (ไม่มี whitespace พิเศษ); ใช้ timestamp UTC รูปแบบเดียวความละเอียด microsecond
  และตัวเลข Money/Quantity canonical strings เดิม ห้าม stringify float
- ช่องว่างมี record `[open_at,"MISSING"]`; ช่องที่มีแท่งมี open/end time,
  OHLCV, finality, observed_at, fetch_started_at ตามลำดับตายตัว
  หลักฐาน fetch หายใช้ explicit null ไม่แปลงเป็นเวลาปัจจุบัน
  รวม seed/gap ก่อนช่วงแสดงผลและ input หลังหน้าปัจจุบันจนถึง U ทุกครั้ง
- ไม่รวม cursor/page size/ช่วงผล/user_id หรือ exact wall-clock as_of ใน digest
  เพื่อให้ผู้ใช้ผลที่อ้าง bounds/input เดียวกันมีรุ่นเดียวกัน; as_of ยังอยู่ใน
  ตัวอ้างอิง pagination ที่ตรวจความถูกต้อง และสูตรใช้ค่าเดิมตลอดการอ่านชุดนั้น
- สถานะคิว/last_checked_at ที่เปลี่ยนโดย OHLCV/finality/หลักฐานรับแท่งไม่เปลี่ยน
  เป็นข้อมูลประกอบพร้อมเวลาอ่าน แยกจากรุ่นของค่าคำนวณ ไม่ถือว่ายืนยัน finality
  และไม่ใช้เป็นเหตุให้คืน indicator จากต่างรุ่น
- อ่านช่วงเวลาต่อเนื่องครั้งละไม่เกิน1,000ช่อง; digest กับ core ใช้ rows
  ชุดเดียวกันที่อ่านใน transaction นี้ ห้าม digest จาก cache อีกภาพหนึ่ง
  เก็บผลเฉพาะ output page แต่ยังสแกน/hash ทั้งชุดจนจบก่อนคืนผล
- หน้าแรกคืน digest เป็น dataset revision; หน้าถัดไปคำนวณใหม่แล้วเทียบ
  ไม่ตรงให้ `409 INDICATOR_DATASET_CHANGED` ไม่มีแถวผลหรือตัวอ้างอิงชุดใหม่
  เท่ากันคืนหน้าของรุ่นเดิม แม้เกิด commit ใหม่ที่ reader มองไม่เห็นใน snapshot นี้

Content revision ระบุเนื้อหาที่ใช้จริง ไม่ใช่ประวัติทุก write: การเปลี่ยนแล้วคืน
ค่าเดิมครบทุก field ก่อน snapshot ถัดไปให้ revision เดิมได้ เพราะ input เดิม
ถ้าต้องการตรวจทุกเหตุการณ์ write แม้ผลสุดท้ายเหมือนเดิม ต้องเปลี่ยน requirements
และเสนอ migration เพิ่ม; ห้ามอ้างว่า digest ให้คุณสมบัตินั้น

ตัวอ้างอิงอ่านต่อใช้สัญญาอายุ/ลงนามด้านล่าง ไม่ใช้ raw client input เป็นหลักฐาน
snapshot; งบของ review ข้อ3 อนุมัติแล้ว แต่ยังรอพิสูจน์ด้วย benchmark หากสแกน
เต็มชุดไม่ผ่านงบ ต้องเสนอแผนใหม่พร้อม migration/grants/rollback ก่อนเปลี่ยนแนวทาง

### Token lifecycle — Approved (2026-10-10)

**อายุและการผูกตัวตน**

- อายุสูงสุดของ logical paginated read คือ6ชั่วโมง (21,600s) นับจาก DB time
  ตอนหน้าแรกเริ่มอ่าน; `expires_at = min(issued_at + 6h, session.absolute_expires_at)`
  ทุก next token คง issued_at/expires_at เดิม ไม่ต่ออายุเมื่อเปลี่ยนหน้า/re-sign
  เลือก6hเพื่อไม่ให้TTLสั้นกว่าการอ่าน525,600ช่องที่แบ่ง526หน้าภายใต้งบ30s/หน้า
  แต่ไม่รับรองว่าจะอ่านครบก่อนข้อมูลเปลี่ยนหรือcleanupลบrecordในชุด; idle expiryของsession
  ยังมีผลตามเดิมและ GET ไม่ต่ออายุ session
- ใช้ `Authenticated.user_id` และ `Authenticated.token_hash` จาก middleware
  ผูก MAC ของ token กับsessionที่ออกให้ โดยไม่ใส่ raw cookie/session token
  หรือ token_hash ใน payload; token ไม่ใช้แทนauthentication/authorization
  loginใหม่แม้userเดิมต้องเริ่มอ่านใหม่ Session revoked/หมดอายุได้401จากmiddleware
- ใส่ token ผ่าน query parameter `cursor` ของ GET เดิม; max4,096 ASCII bytes
  ห้ามส่งพร้อม query ที่พยายาม override ขอบ/คู่/timeframe/page_size ใน token
  ทุกหน้าต้องผ่านauthและadmissionก่อนเริ่มงานเหมือนหน้าแรก

**รูปแบบและการลงนาม**

- รูปแบบสามส่วน `kid.payload.mac`: kidคือkey version; payloadเป็นbase64url
  ไม่มีpaddingของUTF-8 canonical JSON; macเป็นbase64urlของHMAC-SHA256เต็ม32bytes
  ไม่รับ algorithm จากclient และไม่ใช้ hash ธรรมดาแทนHMAC
- canonical payload เป็นobjectเรียงkeys/ไม่มีwhitespace, ห้ามduplicateหรือunknown
  fields; fieldsคือ `format_version=1`, `formula_version`, `dataset_revision`,
  `source`, `base`, `quote`, `timeframe`, `calculation_start`, `calculation_end`,
  `as_of`, `result_start`, `result_end`, `next_open_at`, `page_size`,
  `issued_at`, `expires_at`; timestampใช้UTCรูปแบบmicrosecondเดียวกับdataset
  ไม่มีOHLC, indicator state, รายการseedทุกsegment หรือข้อมูลส่วนบุคคลในpayload
  seedคำนวณใหม่จากinputที่digestรับรอง ไม่เชื่อstateที่clientส่งมา
- ข้อความMACคือ domain `tiewtrade.indicator.cursor.v1` ตามด้วย NUL,
  `kid.payload`, NUL, canonical UUIDของuser, NUL, token_hashจากmiddleware
  kidต้องเป็นASCII `[A-Za-z0-9_-]{1,32}`; payload/base64urlไม่รับอักขระนอกชุด
  ตัวคั่นจึงไม่กำกวมและkidถูกคุ้มครองด้วยMACด้วย
- ใช้ stdlib `hmac.digest(..., 'sha256')` และ `hmac.compare_digest`;
  ตรวจsignatureก่อนใช้claimsเพื่อเลือกSQL/seed/cursor ต้องตรวจschema/boundsด้วย
  แม้signatureถูก: `L < U`, ช่วงผลอยู่ภายใน, cursorตรงขอบและอยู่ในช่วงผล,
  page_size1..1000, อายุไม่เกิน6h, issued_atไม่เกินเวลาDBปัจจุบัน, expiry>issued_at
  และformula/format versionที่รองรับ ห้ามใช้boolแทนint
- Crypto codec อยู่ในinfra รับidentityและเวลาเป็นarguments; ไม่อ่านDB/นาฬิกาเอง
  ไม่ต่อURL/keyserverจากkid ไม่ลองทุกkey และไม่fallbackเป็นunsigned cursor
  อ้างอิง [Python hmac](https://docs.python.org/3/library/hmac.html)

**กุญแจและการหมุน**

- เพิ่ม `KeyPurpose.INDICATOR_CURSOR` ใช้ `KeySource.current()/for_version()` เดิม
  แยกกุญแจ32bytesจากTOTPและvenue secret; environmentของdev/CIตามconventionเดิม
  คือ `TIEWTRADE_SEALING_KEY_INDICATOR_CURSOR` แม้ใช้สำหรับMACไม่ใช่AES sealing
  ค่าเป็น `version:base64key,...` รุ่นแรกเป็นcurrentสำหรับออกtokenใหม่
  รุ่นที่เหลือตรวจtokenเก่าได้เท่านั้น ไม่ให้requestเลือกkeyสำหรับออกtoken
- กุญแจสร้างด้วยCSPRNGโดยผู้ตั้งระบบ ไม่deriveจากcookie/password/TOTP/venue key
  ไม่สร้างใหม่อัตโนมัติทุกstartup; APIทุกreplicaต้องรับkeyringเดียวกันผ่านsecret
  configuration runtime ใช้KeySource abstractionเดิม; production providerยังเป็น
  T-03/F-31ตามขอบเขตเดิม ไม่ฝังกุญแจproductionในCompose/repo/CI logs
- Startupต้องปฏิเสธกุญแจหาย/รูปแบบผิด/รุ่นซ้ำ/ความยาวผิด/เกิน3รุ่น
  และห้ามใช้bytesซ้ำกับkeyring TOTPหรือvenueที่APIโหลดอยู่หรือระหว่างcursorรุ่นต่างกัน
  ตรวจkeyringหลังparseด้วยwrapperเฉพาะF-11; errorบอกเฉพาะชื่อตัวแปร/รหัส
  ไม่มีkey/token/rawค่าจากenvironment ไม่เปลี่ยนparser behaviorของF-06/F-07
- Rotationใช้deploymentสามขั้น: (1) กระจายkeyใหม่เป็นverification keyโดยcurrent
  ยังเป็นตัวเก่าทุกreplica (2) เมื่อทุกreplicaอ่านรุ่นใหม่ได้แล้วจึงสลับcurrent
  เป็นรุ่นใหม่ (3) หลังไม่มีreplicaออกtokenเก่าแล้วรออย่างน้อย6hจึงถอดkeyเก่า
  ไม่reuseชื่อversionกับbytesใหม่; immutable keyringต่อprocess อัปเดตด้วยrestart
  tokenหน้าถัดไปอาจลงนามด้วยcurrentใหม่ แต่คงexpiryเดิม
- หากสงสัยkeyรั่ว สามารถถอดkeyนั้นทันทีทุกreplicaโดยยอมให้tokenเก่าอ่านต่อไม่ได้
  แล้วเริ่มหน้าแรกใหม่ ไม่ลดการตรวจรุ่นข้อมูลหรือauthเพื่อให้tokenเก่าผ่าน
  การถอดkeyต้องทำครบทุกreplica; ไม่อ้างว่าถอดจากเครื่องเดียวแล้วrevokeทั้งระบบ

**Expiry, error และการใช้ซ้ำ**

- ตรวจขนาด/รูปแบบ/MACก่อนquerycandles; ใช้DB timeตรวจexpiryก่อนสแกน และตรวจ
  อีกครั้งก่อนออกresponseเมื่อสแกนเสร็จ หาก `now >= expires_at` ให้409
  `INDICATOR_DATASET_CHANGED` ไม่มีแถวผล/next token ไม่ต่ออายุtokenเดิม
- kidที่ถูกต้องตามรูปแบบแต่ไม่อยู่ในkeyring (เช่นถอดkeyแล้ว) ได้409รหัสเดียวกัน
  เพื่อให้เริ่มใหม่; ไม่อ่านclaimsเป็นtrustedหรืออ่านcandlesในกรณีนี้
  tamper/MACผิด/oversize/schemaผิด/sessionbindingไม่ตรงให้422 `INPUT_REJECTED`
  ไม่บอกว่าfieldใดผิดหรือคืนtokenในerror; missingauthยังเป็น401ตามmiddleware
  format_versionที่ไม่รองรับถือเป็นinputผิด422; tokenที่ตรวจMACผ่านแต่
  formula_versionถูกเลิกใช้ให้409ตามการเปลี่ยนชุดคำนวณ
- กุญแจstartupใช้ได้แต่cryptoล้มระหว่างruntimeให้503 `INDICATOR_DATA_UNAVAILABLE`
  ไม่fallbackkeyอื่นและไม่โยนconfigexceptionที่มีข้อความภายในออกAPI
- Replay tokenเดิมโดยsessionเดิมอนุญาตให้อ่านหน้าเดิมได้ตราบที่input/expiry
  ยังผ่าน เพื่อให้GET retryมีความหมาย; ไม่มีsingle-use state/tableและไม่มีside effect
  replayทุกครั้งยังผ่านrate/concurrencyเดิม ไม่ทำให้ได้next pageโดยข้ามการตรวจ
- เมื่อหมดอายุ/ถอดkey/รุ่นข้อมูลเปลี่ยน ให้ผู้ใช้ผลทิ้งหน้าสะสมและเริ่มหน้าแรก
  automatic restartสูงสุด1ครั้งตามงบเดิม ไม่เพิ่มretryแยกตามสาเหตุของ409
- Responseมี `Cache-Control: private, no-store`; tokenไม่บันทึกในlogs/analytics
  ตรวจ query redaction เดิมในsafe_logging และไม่echo rawcursorในvalidation errors
  payloadเป็นข้อมูลที่อ่านได้ ไม่อ้างว่าการลงนามเข้ารหัสเนื้อหา

## Core และ numeric contract

core รับ `Candle`/หลักฐานของ F-09 ตามลำดับ เปิดเผยผลแยกสำหรับทุก indicator
พร้อม `WARM_UP`, `GAP`, `REFRESH_REQUIRED` หรือค่าพร้อมและสถานะ finality
แท่ง `OPEN`, ยังไม่ถึง `end_at`, หรือ UNCONFIRMED ที่ดึงก่อน `end_at`
ไม่สะสม state; REFRESH_REQUIRED ค้างผลที่ต้องพึ่งแท่งนั้นจน refresh สำเร็จ
gap จริงเริ่มช่วงต่อเนื่องใหม่ตาม NC-31; ห้ามถือ refresh-required เป็น gap
ผลที่สะสม input UNCONFIRMED ใดยังคงแสดงว่า finality ไม่ยืนยัน

สูตร/seed/กรณีหารศูนย์ยึด NC-30 ที่ได้รับอนุมัติจริง การหารและค่าที่ไร้หน่วย
ต้องใช้ numeric contract ที่ปิด NC-33 แล้วเท่านั้น ใช้ `Money`/`Quantity`
สำหรับราคา/ปริมาณ ห้ามลดกฎ F-02 หรือแปลงเป็น float/Decimal เปล่า
ไม่มีสูตรตัวเลขในแผนนี้ที่ถือว่าอนุมัติแทน requirements

ข้อเสนอ implementation ของ numeric contract หลังแก้ review ข้อ1:

- Scalar เป็น immutable value object อยู่ใน money ใช้ `normalise_amount`,
  `ensure_valid_amount`, `guarded` และการ serialize ตัวเลขกลางเดิม;
  การดึง serializer ภายในมาใช้ร่วมต้องรักษา output Money/Quantity เดิมทุกค่า
  ห้าม copy validation/scale/range ไปสร้างใหม่ใน indicators
- Operations ใหม่รับ Money และน้ำหนัก/ตัวหาร int ตาม bounds ใน NC-33;
  ตรวจหน่วย/ชนิดก่อนคำนวณ คืน Money/Scalar ที่ผ่าน invariant กลาง
  ทุก entry point อยู่ใต้ context guard เดิม ไม่มี default rounding
- เพิ่ม primitive ผลหารใน `money/rounding.py` จุดเดียว ใช้ coefficient ที่ scale
  กลางเดิมและ integer quotient/remainder ของ numerator/denominator ที่ exact
  เพื่อเลือกทิศทางตาม RoundingDirection; ไม่ปัดที่ 80 หลักก่อนแล้วปัดซ้ำที่ 18
  รองรับทิศทางเดิมทั้งสี่สำหรับ primitive แต่ F-11 ระบุ TOWARD_NEGATIVE เท่านั้น
  การแปลง coefficient/ผลกลับเป็น Decimal อยู่ใน money และผ่าน validation เดิม
- weighted mean รวม numerator ภายในก่อนหารและตรวจขอบผล exact ก่อนปัด;
  ไม่สร้าง Money ของผลรวมชั่วคราว และไม่ปัด alpha ก่อนคูณ
  percentage_share ใช้ numerator/denominator exact เพื่อปัด RSI ครั้งเดียว
  bounds ของ operations ทำให้ numerator ที่จำเป็นอยู่ภายในความละเอียด 80 หลัก
- core.indicators ใช้ operation ที่กำหนดในตาราง NC-33 ทุกขั้น;
  state เก็บ scale 18 เช่นเดียวกับ output ไม่มีการเก็บเลขละเอียดพิเศษแยก
  ใช้ Money ลบ/เทียบสำหรับ delta/TR/MACD; ถ้าสูตรกลางล้มให้ยุติผลทั้งหน้า
- API แปลง MoneyError จากขั้นคำนวณเป็น `422 / INDICATOR_NUMERIC_ERROR`
  โดยไม่ใส่ input หรือข้อความ exception; input schema ผิดใช้รหัส input เดิม
  ไม่มี retry numeric failures และไม่ส่ง partial page

การเพิ่ม operations เป็นส่วนขยายที่เสนอใน NC-33 ไม่ใช่การแก้ behavior
ของ existing operations; ต้องให้ owner อนุมัติ contract นี้ก่อน implement

## API และเพดานงาน

### Flow refresh — ข้อเสนอหลังแก้ deep review ข้อ5

ผู้รับผิดชอบขอ refresh คือ **ผู้เรียกที่แสดง/ใช้ indicator** ผ่าน endpoint เดิม
`POST /market-data/candles/requests`; สำหรับเว็บคือ data controller ของ F-12
ส่วน F-11 พิสูจน์ flow นี้ด้วย API integration consumer ในเทสต์
โดยไม่เพิ่ม UI หรือ HTTP call ระหว่าง services บอทในอนาคตต้องใช้ทางประกอบ
ภายใน backend ที่งานบอทอนุมัติ ไม่ให้ engine เรียก API service ผ่าน HTTP
GET indicator ยังคงอ่านอย่างเดียว ไม่ enqueue และไม่เปิด transaction เขียนแทรก

**สัญญาผลตอบกลับ GET indicator:** นอกจากค่ากับสถานะต่อจุด เพิ่ม metadata
`refresh` ที่ไม่มีสิทธิ์สั่งงานในตัวเอง:

| Field | ความหมาย |
|---|---|
| `required` | มี input ที่ต้อง refresh และเป็น dependency ของผลหน้าปัจจุบัน ไม่ใช่บอกว่ามีงานในคิว |
| `target` | `{base,quote,timeframe,start,end}` ของช่วงที่แนะนำให้ขอผ่าน F-09; null เมื่อไม่มีช่วงที่ขอได้ |
| `more_required` | มี dependency ที่ต้อง refresh นอก target ด้วย; ไม่ใช่คำสั่งให้ยิงหลายคำขอทันที |
| `queue_status`, `failure_code` | ค่า status/failure_code จาก demand ของ F-09 หรือ null เมื่อไม่มีแถว; เป็นสถานะระดับ series ไม่ใช่ job ของผู้ใช้คนนี้ |
| `observed_at` | เวลาที่อ่าน metadata ใน snapshot ของหน้านี้ ไม่ใช่เวลาที่ตลาดรับรองแท่ง |

เลือก target จาก input ตัวแรกที่ต้อง refresh ในเส้นทาง seed/state ของผลหน้า
ที่ขอ โดยต้องรวม dependency ก่อนช่วงแสดงผลด้วย; target เป็นช่วง half-open
เริ่มที่ open_at ของแท่งนั้น ยาวไม่เกิน1,000ช่องและไม่เกิน U/retention
หากเหลือช่องที่ต้องแก้นอกช่วงนี้ตั้ง more_required=true
ไม่คืนรายการเป้าหมายขนาดเท่าประวัติทั้งหมด และไม่ใช้ gap จริงเป็น REFRESH_REQUIRED
กรณี gap ใช้ coverage/gap ที่มีอยู่เพื่อให้ผู้เรียกขอ backfill ทาง F-09 ตามเดิม

**ลำดับของผู้ใช้ผลหนึ่งรอบ:**

1. อ่าน GET indicator และแสดง REFRESH_REQUIRED พร้อม metadata ตามจริง
   ถ้าผู้ใช้เลือก “ขอข้อมูลใหม่” หรือ caller มีนโยบายขอ refresh ที่งานนั้นอนุมัติ
   ให้ POST target ไป F-09 หนึ่งครั้ง ด้วย session และ CSRF headers เดิม
   การเข้า GET อย่างเดียวหรือการมี required=true ไม่ทำให้ POST เอง
2. `202 {accepted:true}` หมายถึงรับ/coalesce demand แล้ว ไม่รับรองว่ามี job ใหม่
   ไม่รับรองว่าเริ่ม fetch หรือได้แท่งใหม่; `200 {accepted:false}` หมายถึง F-09
   ไม่พบงานที่ต้องเพิ่ม ณ เวลาตรวจ ไม่ใช้เป็นหลักฐาน finality หรือพร้อมคำนวณ
3. หลัง202 ผู้เรียกตรวจ GET `/market-data/candles` ของ target เดิมได้
   ทุก10s สูงสุด6ครั้ง/60s ต่อรอบ; targetไม่เกิน1,000ช่องจึงอยู่ในขอบ endpoint เดิม
   ใช้ `refresh_pending`, status, failure_code และ observed_at ตามความหมาย F-09
   COMPLETE/PRESENT/refresh_pending=false ไม่ใช่ข้อยืนยันว่าทุกแท่งใช้กับ F-11 ได้
4. เมื่อ F-09 ดูเหมือนตอบรอบ refresh แล้ว หรือ POST คืน200 ให้ทิ้ง pagination
   indicator ที่สะสมไว้และเรียก GET indicator จากหน้าแรกหนึ่งครั้ง
   GET นี้ตรวจ `fetch_started_at`/finality และสร้าง digest ใหม่จากข้อมูล committed
   ถ้ายัง REFRESH_REQUIRED ให้คงสถานะ ไม่มี POST ซ้ำอัตโนมัติเพื่อบังคับให้ผ่าน
5. ถ้า F-09 รายงาน FAILED/UNAVAILABLE, POST/poll error, เกิน60s หรือพบ401
   ให้หยุดรอบนั้น; แสดง failure/ยังรอข้อมูล/session expired ตามจริง
   ไม่ล้างสถานะไม่พร้อม ไม่นำค่าที่คำนวณก่อน refresh มาแสดงเป็นค่าล่าสุด
   ผู้ใช้เริ่มรอบใหม่เองได้ภายใต้ auth/CSRF และ backoff/eligibility F-09 เดิม
6. more_required ไม่ทำให้ loop ส่ง POST ทุกช่วง ผู้เรียกอาจขอรอบถัดไปตามการกระทำ
   ของผู้ใช้; ไม่มีคำรับรองว่าหนึ่ง target หรือหนึ่งรอบจะซ่อมครบทั้ง365วัน

**Concurrency/idempotency:** หลายหน้าจอ/ผู้ใช้ขอ series/ช่วงเดียวกันให้ใช้
`enqueue()` เดิมใน `infra/market_data/storage.py` ที่ coalesce ภายใต้ row lock
และ worker lease/generation เดิมของ F-09 ไม่เพิ่ม demand ต่อผู้ใช้หรือ idempotency
table ของ F-11; duplicate POST อาจอัปเดต requested_at/refresh watermark
ตามกฎเดิม จึงไม่อ้างว่าเป็น no-op แต่ต้องไม่สร้าง independent worker/job ซ้ำ
หรือ reset active cursor/attempt/backoff การ timeout ของ POST ไม่ทำให้ส่งซ้ำทันที
ให้ตรวจ GET candles ตามรอบจำกัดก่อนหรือหยุดให้ผู้ใช้เริ่มใหม่

**Failure/commit boundary:** เกณฑ์พร้อมใช้มาจาก GET indicator หลัง transaction
ที่เขียนแท่ง commit แล้วเท่านั้น; Redis notification/202/COMPLETE ไม่แทนหลักฐานนี้
writer rollback/failure ต้องยังไม่มีค่า dependent ส่วน refresh สำเร็จที่ยัง
UNCONFIRMED ต้องคง finality ตาม NC-31; continuation เก่าตรวจ revision ตาม RQ-14
เมื่อ retention เลื่อนจน target ใช้ไม่ได้ให้แสดงรหัสช่วงข้อมูลของ F-09 ตามจริง
และเริ่มอ่าน indicator ใหม่เมื่อผู้ใช้ร้องขอ ไม่ clamp target หรือเลื่อน seed เอง

ไม่มี schema/permission/behavior change ของ F-09 endpoints ใน flow นี้
fields ที่เพิ่มเป็น metadata ของ response F-11 และ generated API types เท่านั้น

เส้นทาง GET ใต้ `/market-data/indicators` ใช้ตัวตนจาก middleware
และ `RouteRule()` แบบไม่ต่ออายุ session ใช้ API role อ่านข้อมูลสาธารณะเท่านั้น
schema ต้องรับคู่/timeframe/ช่วงผล/ขนาดหน้าและตัวอ้างอิงอ่านต่ออย่างเข้มงวด
ไม่รับ seed จากผู้เรียก; ใช้ `SafeInputRoute` และ error code คงที่
ตัวเลขผลส่งเป็นข้อความพร้อมหน่วย; ค่าไม่มีผลเป็น `null` พร้อมเหตุผลชัด
ไม่ส่งข้อมูลลับหรือคำของตลาดที่ API ไม่ควรรู้

ตรวจช่วงต้นทางจาก seed ถึงขอบผลก่อนโหลด: สูงสุด 365 วันตาม timeframe
(1m 525,600; 5m 105,120; 15m 35,040; 1h 8,760; 4h 2,190; 1d 365)
output 1–1,000 ช่อง/หน้า รวม warm-up/gap; อ่านครั้งละไม่เกิน 1,000 ช่อง
เกินช่วงเก็บใช้ `RANGE_OUTSIDE_RETENTION`; เกินเพดานงานใช้
422 `INDICATOR_WINDOW_TOO_LARGE`; ข้อมูลขาดในขอบรายงานสถานะ ไม่ตัด seed
core/reader เก็บเพียง state ที่ต้องใช้ ผลหน้าปัจจุบัน และช่วงย่อยที่อ่าน
ไม่โหลด 525,600 แท่งพร้อมกันหรือสร้างผลทุกหน้าค้างในหน่วยความจำ

### งบทรัพยากร — Approved (2026-10-10)

เจ้าของอนุมัติตัวเลขต่อไปนี้และแนวทาง benchmark ตาม V-15 เป็นเกณฑ์ผ่าน
ตามคำสั่ง “ทำข้อ 1”; ขอบเขตการอนุมัติบันทึกใน requirements ส่วน NC-32
ยังไม่มีผล benchmark จึงไม่อ้างว่าแนวทางสแกนทั้งชุดทำได้ตามงบแล้ว

| ทรัพยากร | งบที่เสนอ |
|---|---|
| งาน F-11 พร้อมกัน | 1 งานต่อ API process รวมช่วง admission/อ่าน/คำนวณ/cleanup; ไม่มีคิวรอ |
| Rate ต่อผู้ใช้ | 6 attempts ต่อ fixed window 60 วินาที ใช้ authenticated user ID ที่ hash แล้ว |
| Rate รวมทุก API process | 30 attempts ต่อ fixed window 60 วินาที ใช้ Redis TIME และ atomic script |
| Admission Redis | ไม่เกิน 500ms; ล้ม/timeout ให้ fail closed |
| เวลาคำขอ | 30s เริ่มหลัง auth สำเร็จ ก่อน validation/admission; รวมทุกช่วงอ่าน/hash/คำนวณ/สร้าง response |
| Dedicated DB pool | API role เดิม, pool_size=1, max_overflow=0, pool_timeout=250ms ต่อ API process |
| Query/lock | statement_timeout=500ms, lock_timeout=200ms; ก่อนทุก query ใช้ค่าที่น้อยกว่าระหว่างเพดานนี้กับเวลาที่เหลือ |
| Cleanup หลัง cancel/timeout | 2s สำหรับ rollback/close; เกินแล้ว invalidate connection และคง slot จนยืนยันว่าปิดจริง |
| CPU slice | ไม่เกิน16ช่องต่อ slice; yield และตรวจ deadline/disconnect ทุก slice; measured event-loop lag สูงสุด100ms |
| Buffer/output | bufferต้นทางไม่เกิน1,000ช่อง, outputไม่เกิน1,000ช่อง; serialized responseไม่เกิน2MiB |
| หน่วยความจำเพิ่มต่อ process | peak RSS เพิ่มไม่เกิน128MiB จาก idle baseline ใน benchmark ของงาน F-11 |

ค่าจำนวน process เป็นขอบ deployment: ถ้ามี N API processes งานพร้อมกันสูงสุด N
และ pool เพิ่ม N connections; ไม่อ้างว่า semaphore ภายใน process จำกัดทั้งระบบ
rate counters ใช้ Redis ร่วมกันทุก process แต่ไม่ได้รับประกัน global concurrency=1
หาก deployment ต้องการเพดาน global ที่ต่ำกว่า N ต้องเสนอแผน admission ใหม่
fixed window ยอมรับ burst สองฝั่งขอบนาทีได้สูงสุด12/user และ60รวมตามสองหน้าต่าง
ห้ามอธิบายเป็นเพดาน rolling60s หรือเปลี่ยน semantics เป็น token bucket เงียบ ๆ

### Admission และการใช้ของเดิม

หลัง auth/schema ตรวจผ่าน จอง local slot แบบไม่รอ แล้วเรียก admission เดิม
ใน `infra/realtime/admission.py` ซึ่งมี Lua atomic global+subject counter อยู่แล้ว
เพิ่ม parameters สำหรับ namespace/subject โดยคง API/defaults ของผู้เรียก F-10
ใช้ prefix `market.indicator.admission:global` และ `market.indicator.admission:user:`
ไม่ใช้ WS/IP buckets ร่วมกัน; เพิ่ม ACL เฉพาะ prefix นี้ให้ Redis API principal
ใช้ expiry120sตาม script เดิมและไม่ refund attempt หลังเริ่มหรือคำนวณล้มเหลว
Redis หลาย process ต้องใช้ชุดเดียวกัน; Redis ล่มไม่ fallback เป็นตัวนับ local

local slot ไม่ว่างให้ `503 / INDICATOR_BUSY` ทันทีพร้อม Retry-After:1
Redis ปฏิเสธ rate ให้ `429 / INDICATOR_RATE_LIMITED` พร้อม Retry-After:60
Redis error/timeout ให้ `503 / INDICATOR_ADMISSION_UNAVAILABLE`
adapter admission ต้องแยก denied/unavailable แบบ typed outcome แทน bool
สำหรับ F-11 โดย wrapper เดิมของ F-10 คง behavior fail-closed และ tests เดิม
ทุกการปฏิเสธก่อนรับงานต้องไม่เริ่ม query candles; local rejection ก่อน Redis
ไม่นับ rate เพราะไม่เกิดการอ่าน/คำนวณหรือใช้ Redis

### Deadline, cancellation และข้อผิดพลาด

API ใช้ monotonic deadline ครอบงานหลัง auth จนได้ response ครบ; core ยังบริสุทธิ์
service/reader เป็นผู้ตรวจเวลาและ yield ระหว่าง slices ทั้งการ decode Money,
canonical hash และการ feed core ไม่ทำลูป synchronous 525,600 แท่งบน event loop
ไม่ใช้ thread task ที่ยังคำนวณต่อหลัง HTTP timeout; synchronous primitive
หนึ่งครั้งมีขอบ input/ขนาดจำนวนจำกัดตาม NC-33 และต้องผ่าน event-loop lag test

watchdog deadline และ disconnect watcher ยกเลิก reader task ร่วมกัน
เมื่อ timeout คืน `504 / INDICATOR_DEADLINE_EXCEEDED`; เมื่อ disconnect หยุดงาน
และไม่สร้าง response ต่อ Cancellation ต้องไม่ถูก broad exception แปลงเป็น success
cleanup อยู่ใน finally และต้อง shield เฉพาะช่วง rollback/close ที่จำกัด2s
ไม่ release local slot จน query/task/connection หยุดจริง จึงไม่ให้ timeout
เปิดทางรับงานใหม่ซ้อนกับงานเก่าที่ยังใช้ทรัพยากร

DB pool/query timeout และ infrastructure failure ใช้
`503 / INDICATOR_DATA_UNAVAILABLE` ถ้า deadline ยังไม่หมด;
ถ้า deadline หมดให้ใช้504 ไม่ปลอมเป็น409 DATASET_CHANGED
responseเกิน2MiBให้ `503 / INDICATOR_RESOURCE_LIMIT` ไม่มีแถวบางส่วน
ทุก error ไม่มี body ของข้อมูล input, credentials หรือ stack trace
คำขอที่สำเร็จส่ง body หลังปิด read transaction แล้วเท่านั้น
ตัวคุมเวลาถือครอง snapshot ทั้งหมดต้องรวม DB waits และ CPU slices ไม่รีเซ็ตต่อหน้าอ่านย่อย

server ไม่มี automatic retry ของ DB/Redis/numeric/409 ภายในคำขอ
ผู้ใช้ผล retry409ได้อัตโนมัติสูงสุด1ครั้งต่อ logical paginated read โดยทิ้ง
หน้าที่สะสมทั้งหมดก่อนเริ่มใหม่; 429/503/504 ไม่ retry อัตโนมัติใน F-11
ผู้ใช้เริ่มคำขอใหม่เองได้แต่ต้องผ่าน admission เดิม; ไม่มี fallback ลดประวัติ/เลื่อน seed

### เกณฑ์รับผล benchmark

อนุมัติ requirements และปิด NC-30..33 แล้วอนุมัติ plan/validation รวมเกณฑ์นี้
ก่อนเริ่มเขียนโค้ด จากนั้นรัน benchmark เมื่อมี implementation ที่ทดสอบครบทางได้
บันทึกผลวัดเป็นหลักฐานตาม V-15; ต้องผ่านก่อน merge หรือเปลี่ยนสถานะเป็น Completed
การอนุมัติแผนไม่ใช่การรับรองผล benchmark และไม่อนุญาตให้ข้ามด่านนี้

รันบน Linux container ที่จำกัด2 vCPU/1GiB สำหรับ API, หนึ่ง API process,
PostgreSQL16/Redis7 แยก container บน host เดียว พร้อมบันทึก CPU/host/versions
ใช้ fixture 1m จำนวน525,600ช่องและครบทุก indicator; บันทึกทั้ง cold run1ครั้ง
และ warm run5ครั้ง โดยไม่มีการส่งออเดอร์หรือเรียกตลาดจริง
ทุก valid request ต้องสำเร็จภายใน30sพร้อม output/digestถูกต้อง ไม่ถือว่า
คืน504ภายใน30sแล้วผ่านเกณฑ์รองรับชุดสูงสุด; RSS delta<=128MiB,
event-loop lag<=100ms และ cleanup<=2s ตามตัวชี้วัดข้างต้น
รันทดสอบภายใต้ writer refresh/backfill และโหลดปฏิเสธพร้อมกันด้วย
ถ้าไม่ผ่าน ต้องกลับมาแก้แผนการเก็บ revision/state พร้อมผล benchmark และ
ขออนุมัติก่อนเปลี่ยน implementation; ห้ามขยาย timeout/ลด input เงียบ ๆ

## ผลต่อฐานข้อมูล

แนวทาง REPEATABLE READ + content revision ไม่เพิ่มตารางหรือ migration:
อ่าน `market_candles` และ metadata F-09 ภายใต้สิทธิ์ API เดิม
เพิ่มเฉพาะ session helper สำหรับ F-11 และไม่เปลี่ยน F-09 writer/upsert/cleanup
ไม่มีการเขียนผล indicator ลงฐานข้อมูล
แก้ deep review ข้อ4: READ ONLY เป็นคุณสมบัติ transaction ของ F-11 เท่านั้น
API role ยังคงสิทธิ์ INSERT ค่าลับที่เข้ารหัสแล้วของ F-07 และ INSERT preference
ของ F-08 ภายใต้ RLS เดิม; ห้ามถอนสิทธิ์เหล่านี้เพื่อทำให้ API ทั้ง role เป็น read-only
สิทธิ์อ่าน secret ที่เก็บไว้และเขียน candles ยังคงถูกปฏิเสธตาม grants เดิม
validation ต้องตรวจทั้งข้อห้ามของ F-11 และ positive regression ของฟีเจอร์เดิม
ข้อเสนอนี้ขึ้นกับการพิสูจน์ว่าอ่าน/ตรวจรุ่นภายในงบและกัน race ได้จริง
หากพิสูจน์ไม่ได้ ต้องแก้แผนระบุ migration, grants, retention, rollback
และขออนุมัติใหม่ก่อนลงมือ ไม่แทรก schema change ระหว่าง implementation

## ความเสี่ยงและวิธีตรวจ

| ความเสี่ยง | การตรวจ/เงื่อนไขผ่าน |
|---|---|
| สูตรหรือการปัดผิด ทำให้กราฟกับบอทตัดสินต่างกัน | ตัวเลขอ้างอิงอิสระ, property tests, ทดสอบ context/หน่วย/overflow หลังปิด NC-30/33 |
| seed เลื่อนตามหน้าหรือช่วงที่ขอ | เทียบแท่งทับซ้อนของคำขอ 200/1,000 จุดและหลายหน้า กับรุ่นข้อมูลเดียว |
| แท่งก่อนจบช่วงถูกนำไปคำนวณ | ใช้ `fetch_started_at` ของ OHLC รุ่นนั้น เทสต์ก่อน/ตรง/หลัง `end_at` และ refresh ล้มเหลว |
| backfill เปลี่ยน input ระหว่างอ่าน | PostgreSQL race test ให้หน้าใหม่เป็นรุ่นเดียวทั้งหน้า หรือ 409 ไม่มีผล |
| 1,000 ผลต้องใช้ input มากกว่า 1,000 | EMA200 1,199 แท่ง, ข้ามช่วงย่อยโดย state ไม่ reset |
| ช่วงเก็บ 365 วันทำให้ API ช้า/กินหน่วยความจำ | หลัง implementation ทดสอบช่วงสูงสุดและ concurrency ตามเกณฑ์ที่อนุมัติ; ต้องผ่านก่อน merge/Completed หากต้องเปลี่ยนแนวทางหรือผ่อนเกณฑ์ให้ขออนุมัติแผนใหม่ก่อนเปลี่ยน implementation |
| การเพิ่ม endpoint เปิดทางข้าม auth/venue | routing inventory, actual-role DB test, import/network gates, ไม่ต่ออายุ session |

## ก่อนขออนุมัติแผน

เงื่อนไขการอนุมัติด้านล่างครบแล้วเมื่อ 2026-10-10: เจ้าของอนุมัติ requirements
ปิด NC-30..33 และอนุมัติ plan/validation ทั้งฉบับตามคำสั่ง “approve”
ยังไม่มี implementation หรือผล benchmark; ผลผ่านยังเป็นเงื่อนไขก่อน merge/Completed

- requirements F-11 ต้องเป็น Approved และ NC-30..33 ปิดครบ
- ตรวจอนุมัติ numeric contract, ตัวตนชุดข้อมูล/seed, งบทรัพยากรและ token lifecycle
  ที่เสนอ; เติมแนวทาง migration หากต้องเปลี่ยนจากแผนอ่านอย่างเดียว
- เจ้าของอนุมัติ plan.md และ validation.md แยกจาก requirements
- จึงเริ่ม implementation ตามแผนที่อนุมัติ; ยังไม่ commit/push จนเจ้าของสั่ง


### NC-36 implementation correction — 2026-10-12

เจ้าของสั่งแก้ D6 grants ให้ตรง R2-D6 เดิม ไม่มีการเปลี่ยนเกณฑ์หรือสถาปัตยกรรม.
ใช้ runtime function signatures จาก migrations 0016/0017/0018 ซ้ำใน 0023
เพื่อสร้าง privilege predicate; ใช้ test_rollout synthetic_heads เฉพาะ predicate tests.
D5/D7 ใช้ published/Replicas/authenticate จาก profile_mixed_replicas.py, actual
rollout inventory/retirement checks และ migrations เดิมบน isolated test DB.
การแก้ 0023 เป็น feature ที่ยังไม่ release; ฐานทดสอบต้อง downgrade 0022/upgrade head
ก่อนตรวจผล ไม่อ้างว่า upgrade head จะเปลี่ยน revision ที่ติดตั้งไปแล้ว.

### NC-37 correction / F1–F6 validation — 2026-10-12

เจ้าของสั่งแก้ numeric pre-STAGING commit ตาม R2-F1 เดิม. ใช้ captured snapshot,
`staging.initialize` และ numeric publication proof เดิมซ้ำหลัง source/heartbeat ปิด;
ไม่ recapture source หรือ retry การคำนวณ. เพิ่ม boundary tests และใช้ db_clock
จาก tests/services/indicator_builder/test_numeric_windows.py สำหรับ backoff/cooldown,
fixtures/API จาก test_prepared_indicators.py และ publication/maintenance tests เดิม.

### N4 validation implementation — 2026-10-12

ตามคำสั่งเริ่ม N4 ใช้ `tests/services/indicator_builder/profile_global_handoff.py`
(`Probes`, actual containers/verified reap), `global_slot_probe.py` (barriers/trace),
`test_numeric_windows.py` (`db_clock`, damaged-source fixture) และ
`tests/api/test_numeric_windows.py` (`http_clock`) ซ้ำ. เพิ่ม clock option และ numeric
publication barriers เฉพาะ test probe เพื่อทดสอบหลาย window ระหว่าง RUNNING/outage,
crash ก่อน/หลัง publication, GC และสอง replicas โดยไม่รอ wall-clock ระยะยาว.
เกณฑ์เดิม R2-N4 ไม่เปลี่ยน; full-load budgets ยังคงชุดที่ 9.

N4 review correction (2026-10-12): ใช้ numeric barrier/clock เดิมซ้ำ แยก
119/120/121s publication จาก GC โดยตรวจ lease/manifest/source proof ยัง valid;
เพิ่ม M1 ข้ามสอง boundary ภายใน 61s เพื่อพิสูจน์ live pending-window publication.
เป็นการตรวจเกณฑ์ R2-N4 เดิม ไม่เปลี่ยน production หรือข้อกำหนด.

### NC-38 implementation clarification — approved 2026-10-12

Owner approved restoring the existing disconnect contract while completing A–D.
Reuse `services/api/indicator_routes.py` for ASGI receive observation,
`IndicatorBudget.reserve` for admission lifetime, and
`infra/db/session.py::indicator_read_session` for transaction cleanup.
Join reader and watcher before leaving admission; repeated caller cancellation
must not cancel transaction cleanup a second time. No acceptance threshold changes.

Owner requested both A–D review corrections on 2026-10-12. Reuse the saved
asyncpg driver / synchronous terminate approach from
`infra/indicators/session.py::indicator_source_session` in the bounded
`infra/db/session.py::_begin` cleanup path. Reserve part of the existing 2s
budget for abort/cancellation; detach the physical connection from its pool
before abort so stalled invalidation cannot make it reusable. Preserve the
original cancellation/error, and bound successful transaction exit as well.
The test-only refresh consumer uses an injected monotonic clock, one 60s
deadline including HTTP time, remaining-time request timeouts and late-response
rejection. Reuse its existing HTTP scenarios and actual F-09/scheduler integration;
add stalled cleanup/transport reuse and slow HTTP boundary cases. No threshold,
trading rule, production activation or phase-9 deferral changes.
