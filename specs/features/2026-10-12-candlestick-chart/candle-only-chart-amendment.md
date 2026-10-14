# Candle-only chart reads

สถานะ: **Approved** — 2026-10-14

## สาเหตุที่ยืนยันจากโค้ด

`CandlestickChartPanel.tsx` ส่งชุด indicator ว่างให้ renderer แต่ยังเรียก
`useChartData` ซึ่งเริ่ม `readEpisode` → `/market-data/chart/history` และเรียก
`/market-data/chart/verify` เป็นระยะ. History ใช้ indicator reader/admission
จึงยังคืน `INDICATOR_RATE_LIMITED` ได้แม้ UI ไม่แสดง indicator.
การเปลี่ยนข้อความ error ไม่ได้แก้ dependency นี้.

## Requirements amendment

- หน้ากราฟที่ไม่มี indicator ต้องไม่เรียก indicator-backed history หรือ proof API.
- ใช้ candle history/pagination และ live candle APIs เดิม พร้อม exact OHLCV,
  finality, gaps และขอบประวัติที่อนุมัติไว้. ไม่อ้าง indicator proof ให้ candle-only data.
- รักษา authentication, cancellation, request budgets และ Retry-After ของ candle/live.
- ไม่ลบ backend indicator API หรือ builder ที่ระบบส่วนอื่นยังใช้ และไม่เพิ่ม rate limit.

## Plan amendment

แทนที่ข้อกำหนดที่ให้หน้ากราฟคง history/proof เดิมใน amendment ลบ Indicator จาก UI.

1. ใช้ `chart/useChartPages.ts` เป็นแหล่ง history เดียวของหน้ากราฟ และใช้ `chart/api.ts`
   สำหรับ live โดยแยก lifecycle ที่ไม่เริ่ม `readEpisode`/`verify`.
2. ปรับ `CandlestickChartPanel.tsx` ให้รวม history/live ตาม open time โดยหน้าประวัติ
   ไม่ทับ current candle; แสดง gap จาก candle contract โดยไม่อาศัย indicator points.
3. รักษาการเปลี่ยน TF, viewport/reset, paging, visibility/offline, auth และ cooldown.
   อัปเดต history ล่าสุดเมื่อ live ข้ามแท่งด้วยคำขอแบบจำกัด ไม่ poll ทุกหน้า.
4. ลบ dependency ที่ไม่ใช้งานจากหน้ากราฟเท่านั้น; ไม่เปลี่ยน service ของ F-11.
5. ตรวจเฉพาะผลกระทบ แล้ว build/restart frontend และตรวจ network ในเบราว์เซอร์.

## Validation amendment

- Initial load, TF switch, retry, reset และ visibility resume ไม่ส่ง history/verify/
  indicator requests แม้จำลอง endpoint เหล่านี้ให้คืน 429.
- History และ live แสดงได้; ข้ามแท่งแล้ว history อัปเดตโดยไม่ซ้ำ/หาย/กลับเป็นค่าเก่า.
- Pagination, sparse/gap/empty data และ viewport anchor คงทำงาน.
- 401/cancellation/late response/429 Retry-After ของ candle/live ยังคงถูกต้อง.
- Targeted hook/component tests, ESLint, type-check และ browser network smoke.
- ไม่ส่งออเดอร์และไม่รัน full suite เพื่อการเปลี่ยนนี้โดยไม่มีเหตุเพิ่ม.

## ผลตรวจ — 2026-10-14

- `useChartData` เปลี่ยนเป็น candle-only lifecycle: ใช้ `useChartPages` และ live API
  ไม่มี import/call ไปยัง `readEpisode`, indicator history หรือ verify.
- ใช้ native candle slots จาก requested bounds สำหรับ gap timeline สูงสุด 1,000 slots.
  รวม OHLCV ตามเวลาโดยไม่ให้ preview เก่าทับ history ใหม่ หรือ downgrade CLOSED.
- โหลด latest page หนึ่งครั้งต่อขอบแท่งใหม่; page ที่ผู้ใช้เลื่อนดูยังอยู่ตำแหน่งเดิม.
- Targeted tests ผ่าน 39 ข้อรวม hook, page cache, component, renderer และ UTC timeline.
  ครอบคลุม StrictMode, TF/retry/resume ไม่เรียก indicator/proof, 401 cancellation,
  stale response, 429 cooldown ข้าม TF, native month/week, gap และ exact OHLCV.
- TypeScript และ scoped ESLint ผ่าน. ไม่รัน full suite หรือ benchmark.
- Browser smoke บน localhost หลัง build/restart frontend: เปิด 1h, เปลี่ยน 4h และ 1m,
  กด reset; network มี candle pages 3 คำขอและ live 6 คำขอ ไม่มี indicator/history/verify
  และไม่มี JavaScript page errors. ตั้ง intercept ให้ history/verify คืน 429 ไว้ด้วย
  แต่ไม่มีคำขอเข้า endpoint เหล่านั้น. ใช้ข้อมูล candle จริง ไม่เขียน fixture ลง DB.
- ภาพ: [candle-only chart](evidence/2026-10-14-candle-only.png).
- การแก้ท้ายสุดเลือกแท่งจริงล่าสุดเป็นค่า default ของ header แทนช่องว่างท้าย timeline;
  component tests และ type/lint ตรวจซ้ำผ่าน แล้ว build/restart frontend อีกครั้ง.
- การตรวจนี้ไม่ยืนยัน backfill ครบสามเดือน และไม่ปิด Pending Full Validation เดิม.
