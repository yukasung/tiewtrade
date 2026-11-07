# F-12 extension — กราฟ timeframe 3m — Plan

สถานะ: **Approved — เจ้าของตอบ approve วันที่ 2026-11-07**
วันที่: 2026-11-07
อ้างอิง: [requirements](requirements.md) Approved 2026-11-07; [validation](validation.md)
Branch: `feature/f-12-3m`; base `f15596d`

**Implementation checkpoint:** [NC-3M-01 A](source-maintenance-amendment.md) อนุมัติแล้ว
วันที่ 2026-11-07; ทำ P2 ด้วย maintenance เดิมตามข้อกำหนดที่แก้แล้ว
เจ้าของสั่ง review แล้ว; สอง Medium findings แก้และตรวจผลกระทบผ่าน
เจ้าของสั่ง refactor แล้ว; ลดความซ้ำใน fixture/browser tests โดยคง runtime behavior
ตรวจผลกระทบต่อเนื่องตาม validation; required CI และ local activation ยังไม่ผ่านด่านครบ

## แนวทางและของเดิมที่จะใช้ซ้ำ

เพิ่มสมาชิกใน shared Timeframe และขยายเส้นทางเดิมตั้งแต่ข้อมูลต้นทางถึงกราฟ
ไม่สร้าง aggregator, scheduler, storage หรือ component อีกชุด

| ส่วน | ของเดิมที่จะใช้ซ้ำ / จุดที่แก้ |
|---|---|
| เวลา | `backend/src/tiewtrade/core/timeframes.py`: เพิ่ม M3/180 วินาที; ใช้ align_floor/ceil, advance, slot_count, retention_cutoff และ chart_display_start เดิม |
| Native data | `backend/src/tiewtrade/venues/binance_th/candles.py`: เพิ่ม request bound 1000 slots เช่น 1m/5m ภายใต้ max_request_span เดิม; `candle_feed.py`/`candle_stream_mapping.py` ใช้ series/interval จาก enum เดิม ตรวจว่ารับและตรวจ native3m ได้ |
| Ingestion/preview | `services/market_data/{ingestion,candle_realtime}.py`, `infra/market_data/{candle_preview,claims,storage}.py`: ใช้ catalog + enum iteration, writer lease, bounded pages, finality และ upsert เดิม; แก้เฉพาะรายการ/ขอบเขตที่ตรึง TF |
| SQL | migration ใหม่หลัง0065: ใช้ pattern0026/0030/0040 ในการเปลี่ยน constraints และ function definitions แบบตรวจ signature/fragment ก่อนแก้; ไม่แก้ migration เก่า |
| API/contract | enum ที่ re-export ใน `core/market_data.py` และ API models เดิม; regenerate `backend/openapi.json` และ `frontend/src/api-types.ts` ด้วยเครื่องมือเดิม |
| UI | เพิ่ม option3m ใน `frontend/src/CandlestickChartPanel.tsx`; เพิ่ม180ใน `frontend/src/chart/candleTimeline.ts`; ใช้ shared `components/ui/Select.tsx` ที่ปรับจาก `references/admin-template/src/components/form/Select.tsx` ไม่แก้ style/layout |
| Chart lifecycle | `frontend/src/chart/{api,useChartData,candleTimeline}.ts*` และ controller เดิม: คง query identity, cancellation, stale-result protection, bounded history และ error policies |

## P1 — Shared schedule และต้นทาง

- เพิ่ม `3m` ใน enum และ fixed-span map; ขอบ UTC ทุก180วินาที รวมก่อน epoch/ข้ามวัน
- ระยะแสดงสามเดือนปฏิทินและ seed/retention ของ intraday ใช้ฟังก์ชันเดิม
- native REST requests และ stream subscription ใช้ `3m` ตรงตัว; ข้อมูล OHLCV ยังคง exact
- ใช้ tests เดิมและเพิ่ม cases เฉพาะขอบเขต3m/unknown interval/ผิด series/closure proof

## P2 — Migration และ scheduler/catalog ที่แชร์ enum

เลข migration เริ่มที่0066ถ้ายังว่างเมื่อ implement; ตรวจ head ใหม่ก่อนเลือกเลข
ทดสอบบนฐานแยก ห้ามทดลอง downgrade กับฐานที่เจ้าของกำลังใช้งาน

1. ขยาย timeframe CHECK ของ market_candles, market_candle_demand,
   market_candle_preview, indicator_build_jobs, indicator_generations และ
   supported_symbol_timeframe_readiness รวม CHECK/function อื่นที่ inventory พบ
2. ขยาย SQL floor/advance/slots, candle/preview schedule constraints และ
   indicator_calculation_bounds ให้ตรง Python180วินาที ไม่ปล่อย3mตก ELSE86400
3. ขยาย seed_indicator_build_jobs และ claim_indicator_build_job mapping เป็น9TF
   ต่อคู่ตาม catalog เดิม รวม cursor arithmetic และ rollover; ไม่ตรึงคู่ไว้ที่BTC/ETH
   SQLปัจจุบันหลัง0040นับคู่ ACTIVE/PREPARING แบบ dynamic แต่คูณ8TF
   จึงเปลี่ยนเป็น9: baseline2คู่กลายเป็น18series ไม่ hard-code18ใน runtime
4. transition_indicator_rollout และ readiness publication/catalog activation
   ต้องตรวจครบ9TFต่อคู่; 8TFเดิมอย่างเดียวห้ามทำให้ถือว่าชุดใหม่พร้อม
   เพิ่ม3mใน record_supported_symbol_timeframe_readiness validation โดยไม่ปลอม ready
5. รักษา latest function owner, SECURITY DEFINER/search_path, REVOKE/GRANT,
   FORCE RLS, job identities/claims/lease/progress และ source/business facts เดิม
   หลังหยุด readers/writers และตรวจ build slot IDLE ให้เรียก maintenance เดิมใน transaction
   อนุญาตเฉพาะ source epoch/revision/journal_floor เปลี่ยน, eligible generations EXPIRED
   และลบ derived heads เพื่อ rebuild; คง generation/checkpoint/history และสูตรเดิม
   ทดสอบ expected derived changes, injected rollback และ writer drain/fencing กับ DB จริง
   ใช้ CREATE OR REPLACE/checked fragment pattern ของ migration เดิมกับนิยามล่าสุด
   ถ้านิยามไม่ตรงคาดให้ fail/rollback ไม่ replace แบบกว้าง
6. Downgrade ต้องหยุด writers และล็อกตารางที่เกี่ยวข้องใน transaction ก่อนตรวจ
   inventory ของ3mทุกตารางที่เกี่ยวข้องและ state/metadata ที่อ้างอิง3m; ถ้ายังมีให้ปฏิเสธก่อน maintenance/DDL
   ไม่ลบ jobs/history/readiness หรือแปลงTFเองเพื่อให้ผ่าน; เมื่อไม่มีข้อมูล3mจึงคืน
   definitions/constraints เดิมพร้อมสิทธิ์เดิมได้ ทดสอบ concurrent insert กับ guard

การเพิ่ม3mไม่เปลี่ยนสถานะคู่, rollout mode หรือ risk admission flags โดยอัตโนมัติ
ไม่ reset checkpoint/cursor เพื่อซ่อนปัญหา; ทดสอบการเดินต่อจาก cursor เดิมด้วย

## P3 — Contract และ UI

- regenerate contracts หลัง enum/DB พร้อม; เพิ่ม3m ระหว่าง1mและ5m ค่าเริ่มต้นยัง1h
- ใช้ timeline math เดิมสำหรับ180วินาที; ตรวจช่องว่าง/append/replace/preview-to-REST
- ใช้ component/controller tests เดิมสำหรับการสลับ TF/คู่และ request เก่าที่มาช้า
- ไม่แก้ clock-domain bug ที่พบใน local API ในงานนี้; local launcher ที่ตรวจใช้
  asyncio ตามข้อเท็จจริง runtime ปัจจุบันโดยไม่เพิ่ม deadline หรือเปลี่ยนเกณฑ์สด

## Checkpoints และผลกระทบ

- ระหว่างพัฒนา: targeted core/venue/DB/API/UI tests ตาม [validation](validation.md)
  รวม actual-role migration/scheduler/readiness/concurrency; static checks เฉพาะ diff
- เพิ่มเคสใน suites เดิมก่อนสร้าง harness ใหม่; test-state isolation ใช้ pattern เดิม
  ห้ามลด assertion/skip/xfail เพราะ enum มีสมาชิกเพิ่ม ให้ปรับ expected set ให้ตรง9TF
- ก่อนส่ง review: บันทึก requirement coverage, คำสั่ง, SHA/config/schema และผลจริง
  เมื่อ implementationครบ แจ้ง **Ready for Code Review** แล้วหยุดรอ `review code`
- หลัง review/fix ให้ถาม `refactor the code` ตาม AGENTS; หลัง authorized refactor
  ทำ validation ที่ถึงกำหนดต่อโดยใช้หลักฐานเดิมที่ยัง valid
- ก่อน merge: Feature gates และ required CI บน final candidate ผ่าน; คำสั่ง Git แยก
- Shared enum/SQL กระทบหลาย feature จึงต้องมี full regression ใน required CI ก่อน merge
  ไม่รันซ้ำ local ทั้งชุดโดยไม่มีช่องว่าง; CI ไม่เปลี่ยน configuration เพื่อข้ามชุดเดิม
- Release/ชุดที่9: ใช้ [V3-10A/B](validation.md) ที่ผูกprofile/thresholdกับF-12 V-17
  และF-11 R2-C1..C6/R2-7 ผ่านF-38 RC-03..09/combined-phase amendmentโดยตรง
  แยกruntime readiness BTC+ETH18seriesจากworkload BTC9series; ไม่ใช้ผล16/8series
  รับรอง18/9series ไม่เปลี่ยนSLAหรือสร้างcampaignใหม่ในรอบพัฒนา
- F-09 correctness/concurrency/retry/finality/permissions ยังคงFeatureตามV3-02/03/04/06
  ไม่ใช่Release gateที่เลื่อนได้; ไม่มีtimedF-09campaignใหม่จากงานนี้

## นำขึ้น local หลังผ่านด่าน

การอนุมัติแผนนี้อนุญาตพัฒนาและทดสอบบนฐานแยกก่อน ยังไม่อัปเกรดฐาน local
`tiewtrade_local_f17_clean_20261107` ที่เจ้าของกำลังใช้ในช่วง implement
หลัง review/authorized refactor/Feature validationผ่าน ให้จัดทำขั้นตอน local ที่ตรวจรับได้:
สำรองฐานและตรวจคืนได้, หยุดเฉพาะ reader/market-data/builder ของงาน, migrate forward,
เริ่ม writer ที่เข้ากัน แล้วตรวจ3mด้วยบัญชีของเจ้าของก่อนรายงานใช้ได้
ดำเนินขั้น local ต่อในขอบเขตคำสั่งเพิ่ม3mเมื่อผ่านด่านข้างต้น โดยแจ้งขอบเขต/เวลา
ก่อนตรวจและหยุดหากพบเงื่อนไขเดิมที่ต้องถามเจ้าของ ไม่เพิ่มจุดอนุมัติย่อยใหม่
ไม่ปิด/เปิด signup หรือ risk/Live flags จากงาน3mโดยอ้อม และไม่ลบข้อมูลเพื่อ downgrade

## ความเสี่ยงและจุดหยุด

- SQL/enum คนละชุดทำให้ fail หรือจัด3mเป็นรายวัน → Python/SQL parity และ DB negatives
- readiness/fairness ข้าม3mหรือแย่งคิวเดิม → exact set, stale readiness และ multi-worker tests
- จำนวนseriesเพิ่มทำให้โหลดเปลี่ยน → คง bounds เดิมและเก็บข้อจำกัด Batch/Release ตามจริง
- downgrade ตรวจไม่ครบ/แข่ง writer → lock + actual-DB atomic guard/data digest tests
- ถ้า approved spec กับ implementation ขัดกัน, ต้องเปลี่ยนสถาปัตยกรรม/เกณฑ์ หรือไม่ผ่าน
  ครบ3รอบ ให้หยุดเสนอทางเลือกตาม AGENTS; ไม่วนเปลี่ยนเกณฑ์เอง

## Refactor ที่เจ้าของอนุมัติ — 2026-11-07

ใช้ CandlePage/ChartLive types จาก frontend/src/chart/api.ts แทน shape ที่เขียนซ้ำ
browser response waits เดิมยืนยัน requests ได้อยู่แล้ว จึงตัด request log/assertions ที่ซ้ำ
คง series identity,180s, exact values, stale-value และ no-order assertions เดิม
fixture ราคาเปลี่ยนจาก nested ternary เป็น explicit series data พร้อม named OHLC values
cursor test ใช้ query เดิมซ้ำผ่านตัวแปรและ map index โดยคง expected18-series/fairness
ไม่มี runtime/migration/business behavior change; ไม่เพิ่ม infrastructure หรือ abstraction
