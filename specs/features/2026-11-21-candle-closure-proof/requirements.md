# Shared Candle Closure Proof — Requirements

สถานะ: **Approved - owner replied approve2026-11-21; CP-01 through CP-16 approved**
วันที่: 2026-11-21 (Asia/Bangkok)
คำขอ: เริ่มตรวจหลักฐานและกำหนดเกณฑ์ CLOSED ของชั้นข้อมูลร่วมหลังพบปัญหาทั้งสองกลยุทธ์
Branch: `feature/candle-closure-proof`; worktree `../TiewTrade-candle-closure-proof`
ฐาน local F-21 snapshot e811800; Paper Test Entry ยังอยู่ branch แยกและต้องรวม candidate
ที่ผ่าน gates ตามลำดับ dependencies ก่อน publication/merge ไม่มีการย้าย WIP ของงานเดิม

## ทำไมต้องมี

แท่งสีเขียวจากตลาดจบช่วงและดึง REST หลังจบแล้ว แต่ระบบเก็บเป็น UNCONFIRMED
F-09/F-12 เดิมยังไม่ยอมรับหลักฐานปิดจาก stream ขณะที่ F-21/Paper Test Entry ต้องการ
CLOSED ก่อนประเมิน จึงไม่มีทางเกิด entry จาก source path ปัจจุบันด้วยการรอต่อเฉย ๆ

เอกสารทางการ [Binance TH — Kline/Candlestick Streams](https://www.binance.th/api-docs/en/#klinecandlestick-streams)
อธิบายฟิลด์ `x` ว่าแท่งปิดหรือไม่ งานนี้เสนอให้รับเป็นส่วนหนึ่งของหลักฐานร่วมกับ
REST หลังปิดและ source/ordering checks ไม่เปลี่ยน UNCONFIRMED เป็น CLOSED จากเวลา
เอกสารเป็นหลักฐาน semantics; ตัวอย่างสังเกตจริงมีขอบเขตใน research.md ไม่รับรองทุกกรณี

## ขอบเขต

- เพิ่มสัญญายืนยันปิดแท่งใน public market-data pipeline เดิม ให้ F-11/กราฟ/กลยุทธ์
  อ่าน canonical finality และ revision ชุดเดียวกัน พร้อม provenance ที่ตรวจย้อนหลังได้
- ปลายทางเทรดช่วงแรกเฉพาะ owned Paper acceptance ของ RSI Step Grid และ Paper Test Entry
  คง CLOSED-only rule ไม่อนุญาตให้เทรดจาก UNCONFIRMED และไม่เปลี่ยนกลยุทธ์/เงิน/TP/SL
- ไม่เปิด Live/production/สิทธิ์ใหม่ ไม่ส่งคำสั่งซื้อขายหรือ Start/resume ระหว่าง research
  ไม่เพิ่ม source จาก Binance Global แทน Binance TH และไม่สร้าง infrastructure ใหม่
- คงข้อมูลประวัติที่ไม่มี proof เป็น UNCONFIRMED; ไม่ตีตราว่า250แท่งย้อนหลังเป็น CLOSED
  F-11 warm-up ใช้ประวัติที่ผ่าน NC-31 เดิม ส่วนแท่งสัญญาณต้องผ่าน closure proof นี้

## กฎที่เสนอให้อนุมัติ

| รหัส | ข้อกำหนด | ที่มา |
|---|---|---|
| CP-01 | CLOSED ใหม่เกิดได้จาก verifier ของ public market-data เท่านั้น ไม่เกิดจาก browser, strategy, engine หรือ indicator การพ้น end_at/ขึ้นแท่งถัดไป/ATR READY/REST อย่างเดียวไม่พอ | F-09 RQ6; F-11 NC31; owner CLOSED-only |
| CP-02 | ต้องได้รับ native kline event ที่ `x` เป็น boolean true จาก endpoint Binance TH ที่กำหนด ผ่าน TLS/connection/subscription/lease epoch และ strict adapter validation; event เก่าจาก connection ที่เสียสิทธิ์ไม่ใช้เป็น proof | official TH stream semantics; F-12 partial-order/lease contracts |
| CP-03 | source, market identity, base/quote, timeframe, open_at/end_at ต้องตรง canonical native series; normalize inclusive T ตาม convention เดิมและตรวจ native calendar alignment ไม่คำนวณ1w/1M ด้วยนาทีคงที่; ไม่ปน market/interval/แหล่งข้อมูล | F-09 native series, F-12 parser |
| CP-04 | ต้องดึง REST ของแท่งเดียวกันจาก Binance TH โดย request เริ่มตั้งแต่ end_at เป็นต้นไป และ commit ผลสำเร็จ; ตรวจ identity และ OHLCV เท่ากับ closed event ด้วย Money/Quantity เดิม ข้อมูลเท่ากันเชิงตัวเลขรับได้แม้รูปแบบทศนิยมต่างกัน; ดึงก่อนจบแต่ตอบหลังจบไม่พอ | ข้อเสนอ proof แบบ WS+post-end REST; F-11 NC31 |
| CP-05 | จน CP02–04 และ source/ordering/numeric checks ผ่านครบ ให้คง UNCONFIRMED และยังไม่ปล่อยสัญญาณ CLOSED; ถ้าไม่มี closed event, REST ไม่พร้อม/ไม่ตรง/ถูก rate limit, proof ขาดหรือช่องทางหลุด ให้ fail closed ใช้ repair/backoff เดิม ไม่เดาสถานะจากเวลา | trading safety; ไม่ใช้แค่เวลาเป็น proof |
| CP-06 | ใช้ cumulative/partial-order invariants เดิมสำหรับ duplicate/out-of-order/closure event; ไม่เลือก OHLC ที่ขัดกันด้วย E, received_at หรือ arrival order เพียงอย่างเดียว; event/REST ที่ขัดกันต้องบล็อกการเข้าใหม่และเข้าสู่ reconciliation เดิม ก่อนปล่อย proof ใหม่ที่ตรวจได้ | F-12 approved ordering; database/source safety |
| CP-07 | บันทึก native identity, raw/normalized close event ที่จำเป็นหรือ digest พร้อมข้อมูลที่ reconstruct ได้, event/receive time, connection generation/lease identity, request-start/response times, canonical revision, proof policy/version และผลตรวจใน PostgreSQL อย่าง durable ไม่มี process-memory authority; การเลื่อน canonical finality/revision และ proof ต้อง atomic | AGENTS stateless; F-09/F-11 source fencing |
| CP-08 | การประเมินกลยุทธ์และ queued BUY ต้องอ้าง revision/proof ที่ยัง valid และตรวจซ้ำตาม fences เดิม การ correction/invalidation ต้องเปลี่ยน source revision และทำให้ indicator/intent เก่าหมดอำนาจ ห้ามเก็บ CLOSED ที่รู้ว่าขัดแย้งไว้เป็นสัญญาณที่ยัง tradable | F-21 authority, F-11 proof |
| CP-09 | duplicate proof/event, REST retry, crashก่อน/หลังcommit, lost acknowledgement, worker takeover และหลาย instances ต้อง idempotent; ไม่เขียน proof/emit trading opportunity ซ้ำจนซื้อซ้ำแท่งเดิม แม้ revision เปลี่ยน | trading safety/idempotency |
| CP-10 | หลัง disconnect/recovery ห้ามสร้าง CLOSED ย้อนหลังจาก REST อย่างเดียว ถ้าไม่มี closure evidence ที่ตรวจได้ให้คง UNCONFIRMED; proof ของอดีตใช้ซ่อมข้อมูลได้ตามสัญญา แต่ต้องไม่ replay entry เก่าหลัง Start/recovery | F-21 freshness/cutoff; F-09 evidence gap |
| CP-11 | สัญญาณใช้แท่ง A สีเขียวที่ proof พร้อมแล้ว ประเมินและส่ง Market ในแท่ง B ถัดไปตาม freshness/admission เดิม ไม่รอ B ปิด ไม่ backdate หรือรับรอง fill ที่ราคา open; หากพ้นช่วง B/ความสดที่อนุญาต ไม่ยกสัญญาณเก่ามาซื้อภายหลัง | owner next-candle instruction; Web execution contract |
| CP-12 | RQ strategy guards เดิมทั้งหมดคงอยู่: RSI ARM/FIRE สำหรับ RSI; green-only/หนึ่งposition สำหรับ test;250 contiguous warm-up/ATR14/source readiness, pending orders/STOP/risk/catalog/balance/protection/fees/PnL และ first-fill TP/SL ไม่เปลี่ยน; closure proof ไม่ได้แปลว่ามี fill | approved F-17/F-20/F-21/Paper Test Entry |
| CP-13 | ถ้า canonical data ถูกแก้หลังมี execution ให้เก็บ execution/ledger ตามจริง ไม่ลบ/ชดเชย trade อัตโนมัติ ไม่เปลี่ยน frozen first-fill ATR/TP/SL ของ test strategy ใช้ reconciliation/STOP policy เดิมเมื่อกระทบ authority | existing financial invariants |
| CP-14 | reuse REST coalescing, public rate-limit guard, websocket limits และ lease/process separation เดิม; รวม refresh ของแท่งเดียวกัน ไม่สร้าง connection ต่อuser หรือ polling ไม่จำกัด ถ้าพิสูจน์ readiness ภายใน freshness เดิมไม่ได้ให้ข้าม entry ไม่ขยายเวลา/ลด safety เอง | architecture/trading safety; public API limits |
| CP-15 | schema/proof version และ activation ต้องรองรับ old/new compatible processes, default disabled จนผ่าน Feature/source evidence/owner gates; ไม่ promote history อัตโนมัติหรือปล่อย old writer ลบ proof/เขียนทับ CLOSED แบบไม่ตรวจ correction; canonical shared readers ต้องเห็นความหมายเดียวกัน | database migration/rollout standards |
| CP-16 | API/audit/debug ที่มีอยู่ต้องแยก missing/awaiting proof, conflict, stale/repair และ accepted proof ได้ตามจริง โดยไม่บังคับนำข้อความที่เจ้าของสั่งซ่อนกลับมาใน UI และไม่เปิดเผย credentials | owner UI decisions; auditability/security |

CP-04 เป็นข้อเสนอแบบอนุรักษ์นิยม: ตรวจทั้งสัญญาณปิดจาก stream และข้อมูลหลังปิดจาก REST
ไม่รับประกันว่าหลักฐานทั้งสองจะพร้อมตรงวินาทีเปิดแท่ง B จึงไม่รับประกันการเข้าในทุกแท่ง
ที่เห็นเป็นสีเขียว การซื้อยังต้องผ่านเงื่อนไขอื่นทั้งหมด

## ผลกระทบต่อข้อกำหนดเดิม

- เปลี่ยนข้อจำกัด F-09 และ F-12 ที่เคยถือ x=true เป็น hint เท่านั้น โดยอนุญาตการเลื่อน
  finality จาก verifier เมื่อมี proof ครบตามงานนี้ ไม่แก้ parser REST ให้เดา CLOSED
- F-11 คง NC-31 และนิยาม finality; การเปลี่ยน canonical revision ต้อง invalidate/rebuild
  เฉพาะข้อมูลที่กระทบ ไม่คัดลอกสูตรหรือทำ indicator pipeline ใหม่
- กลยุทธ์ยัง require CLOSED เหมือนเดิม แต่อาจเริ่มประเมิน/ส่ง Paper BUY ได้เมื่อ pipeline
  เปิดใช้งานและข้อมูลผ่านจริง ต้องรักษา Start/recovery cutoff และ explicit activation
- shared market finality อาจเปลี่ยนข้อมูลที่กราฟ/API อ่าน แต่ไม่อนุญาต Live execution ใหม่
  การเปิด production/Live ยังต้องผ่านขอบเขตและ gates ของงานเหล่านั้นแยกต่างหาก

## สิ่งที่ต้องพิสูจน์ก่อน implementation/merge

หลัง requirements Approved จึงจัดทำแผนและ validation เพื่ออนุมัติขั้นถัดไป โดยอย่างน้อย:

- native payload semantics และกรณี closure-before/after reconnect, mismatched identity/OHLCV,
  invalid x/type/time/calendar, duplicate/reordering/conflict และ absent-proof boundaries
- real PostgreSQL: proof+canonical atomicity/FKs/grants, concurrent publishers, rollback,
  correction invalidation ระหว่าง evaluate/commit/queued matching และ restart/lease takeover
- actual public-source payload → durable proof → ATR/source admission → guarded Paper entry
  ทั้ง RSI/test ตามเงื่อนไขเฉพาะของแต่ละตัว; fixtures ไม่แทน proof ของ source path จริง
- warm-up250, current/future/history cutoff, same-candle re-entry และ first-fill protection regressions
- rollout compatibility/default-off, targeted static/contract checks, review/owner acceptance/required CI
- จัดเกณฑ์เป็น Feature/Batch/Release ตาม testing standard; ยังไม่เพิ่ม timed endurance campaign

## จุดอนุมัติและข้อค้าง

ข้อเสนอ CP-01–CP-16 รวมการขยายความหมาย canonical CLOSED ต้องได้รับอนุมัติจากเจ้าของ
ก่อนจัดทำ plan/validation รายละเอียด และต้องอนุมัติสองเอกสารนั้นก่อนแก้ application code
การสั่ง “เริ่มทำ” รอบนี้อนุญาตเริ่ม research/ข้อเสนอที่แจ้งไว้ ไม่ใช่การข้ามจุดอนุมัติ

สถานะคำถาม: เจ้าของอนุมัติข้อเสนอ WS x=true + REST post-end ที่ตรงกัน และ Paper-only
activation ตาม CP-01–CP-16 แล้ว; รอ plan/validation gate ถัดไป ไม่มีการอนุมัติ inference
CLOSED จาก clock หรือใช้ UNCONFIRMED เทรดแฝง
โค้ดเดิม/preview/บอทที่เปิดอยู่ไม่ได้ถูกแก้หรือเปิดสิทธิ์เพิ่มโดยงานเอกสารนี้

## Research checkpoint before approval

Single public probe observed x=true for both BTC/ETH1m. BTC identity/OHLCV matched REST;
ETH identity/OHLC matched but volume differed (WS611.04950000 vs REST610.94450000).
See research.md and raw evidence. This does not block drafting a fail-closed contract,
but ETH's sample does NOT pass CP04 and must not be declared CLOSED/tradable by this proposal.
No tolerance/volume omission added. Other intervals/recovery/correction cases remain unproven
and must be explicit Feature checks in the subsequent approved plan/validation.

Owner approval record2026-11-21: requirements only. Prepare plan/validation for the next approval gate; no runtime activation or application implementation inferred. Earlier proposed wording is preserved as drafting history.
