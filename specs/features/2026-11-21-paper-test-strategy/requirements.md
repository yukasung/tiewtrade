# Paper Test Entry — Requirements

สถานะ: **Approved — เจ้าของตอบ “approve” วันที่ 2026-11-21; ยืนยัน first-fill anchor เพิ่มเติมในวันเดียวกัน**
วันที่: 2026-11-21 (Asia/Bangkok)

## เป้าหมาย

เพิ่มกลยุทธ์สำหรับตรวจรับ Paper ที่เข้าเงื่อนไขได้เร็วกว่า RSI Step Grid
ของ F-21 โดยไม่แก้กฎ RSI Step Grid เดิม ผลทดสอบกลยุทธ์นี้ใช้ตรวจ lifecycle,
order execution และ protection แต่ไม่แทนหลักฐานสัญญาณ RSI/EMA ของ F-21

## กฎที่เจ้าของตัดสิน

| รหัส | ข้อกำหนด | ที่มา |
|---|---|---|
| RQ-01 | BUY เมื่อแท่งเทียนที่เลือกปิดสีเขียว (close > open) แท่งแดง/doji/แท่งยังไม่ปิดไม่เข้า ไม่มีตัวกรอง RSI/EMA | เจ้าของตอบ 2026-11-21 และบริบทคำถามเลือก trigger |
| RQ-02 | เลือกคู่เทรดและ timeframe จาก shared contracts/catalog ของ Web ก่อนเริ่ม ใช้ timeframe ของบอทประเมินสัญญาณ ไม่อิง timeframe ที่ผู้ใช้กำลังดูบนกราฟ | เจ้าของให้เลือก timeframe ได้เอง และ patterns F-20/F-21 |
| RQ-03 | ใช้ ATR14 และ source/seed/readiness ของ indicator pipeline เดิมตาม RSI Step Grid ไม่เขียนสูตร ATR คู่ขนาน ไม่ลด warm-up/source safety เพื่อเร่งเข้า | เจ้าของให้ ATR เหมือน RSI Step Grid; F-11/F-21 |
| RQ-04 | TP = ราคาซื้อจริง + 3×ATR ของแท่งสัญญาณ; SL = ราคาซื้อจริง − 3×ATR ของแท่งสัญญาณ คำว่า SL เท่า TP หมายถึงระยะห่างสมมาตรรอบราคาซื้อ ไม่ใช่ราคา trigger เดียวกัน | เจ้าของให้ TP เหมือน RSI Step Grid และตอบ “sl เท่า tp” |
| RQ-05 | ตรึง TP/SL จากราคาที่ fill ครั้งแรก + ATR ของแท่งสัญญาณ ไม่ขยับเมื่อ fill เพิ่มหรือมีแท่งถัดไป; partial fills เพิ่มเฉพาะปริมาณที่ protection ดูแล ใช้ actual execution facts และ failure/trigger policy เดิม ไม่ใช้ราคาสัญญาณแทนราคาซื้อจริง | เจ้าของเลือก first-fill anchor วันที่ 2026-11-21; F-17 execution/protection contracts |
| RQ-06 | ถือได้ครั้งละหนึ่ง position ไม่เพิ่มไม้ขณะ position เดิมยังไม่ปิด ไม่มี grid/max_entries1–10 ให้ปรับในกลยุทธ์นี้ | เจ้าของระบุไม่เปิดไม้ใหม่จน position เดิมปิด |
| RQ-07 | ใช้เงินต่อไม้ที่ผู้ใช้กรอก ไม่ตั้งจำนวนเงินแทนเจ้าของ ใช้ sizing/fees/reservation/lot/minimum เดิม | บริบทคำถามที่เจ้าของตอบ และ trading safety |
| RQ-08 | คำสั่งเข้าที่ยัง pending/ไม่ทราบผลต้องกันการเปิดซ้ำ แม้ยังไม่มี fill; ไม่เริ่มซื้อใหม่ขณะคำสั่งเข้า/ออกเดิมยังไม่คลี่คลาย ใช้ duplicate/replay/exit-candle guards เดิม | trading safety และ F-20/F-21 |
| RQ-09 | กลยุทธ์แยกสำหรับสภาพแวดล้อมตรวจรับ Paper เท่านั้น ไม่เปิด production/Live และไม่แก้สิทธิ์หรือ activation gates เดิม | เป้าหมายตรวจรับ Paper และข้อเสนอแยกกลยุทธ์ |
| RQ-10 | Intent ผ่าน admission, balance, risk, STOP, catalog, execution และ protection เดิม สัญญาณซื้อไม่ถือว่าเกิด fill แล้ว ข้อมูลไม่พร้อมไม่เดาค่า | F-20/F-17 และ trading safety |
| RQ-11 | เงิน/ราคา/ปริมาณใช้ Money/Quantity และ rounding เดิม หาก target ไม่ถูกต้องตามข้อจำกัดเดิมให้ใช้ failure policy เดิม ไม่เดาราคา SL/TP ทดแทน | AGENTS.md และ F-17 |
| RQ-12 | Config ตรึงตลอด run; state/intent/protection ที่ต้องกู้คืนเก็บ PostgreSQL ใช้ isolation/idempotency เดิม รองรับ restart/หลาย instances ไม่ใช้ browser/process memory เป็น authority | AGENTS.md Stateless และ F-20 |
| RQ-13 | ใช้ lifecycle และ component กลางจาก admin template เดิม ต้องแยกชื่อกลยุทธ์ทดสอบให้เห็นชัด และแสดงเหตุเริ่มไม่ได้ตามสถานะที่ยืนยันแล้ว | frontend standard และ owner reload-state fixes |

ระดับราคา TP/SL ที่ส่งจริงอยู่ภายใต้ tick/rounding และ trigger/execution rules ของ
protection เดิม ไม่รับรองว่าจะ fill ที่ราคา trigger พอดี และไม่เพิ่มโมเดล PnL/fees ใหม่

## ของเดิมที่จะอ้างอิงในแผน

- `backend/src/tiewtrade/core/strategies.py` — strategy contract/registry
- `backend/src/tiewtrade/strategies/rsi_step_grid/` — ATR snapshot/config/closed-candle integration ที่เกี่ยวข้อง
- `backend/src/tiewtrade/infra/bots/` — lifecycle, decisions และ execution linkage
- `backend/src/tiewtrade/infra/protections/` — TP/SL, partial fills และ actual execution facts
- `frontend/src/PaperBotPanel.tsx` — แผงเริ่ม/หยุดและค่าตั้ง
- `frontend/src/components/ui/` และ `references/admin-template/` — component/pattern เดิม

รายการนี้เป็นจุดเริ่มตรวจ reuse; plan ต้องระบุ functions/contracts ที่ใช้จริงก่อนแก้ runtime

## คำถามที่ปิดแล้ว

| รหัส | คำตัดสิน |
|---|---|
| NC-01 — Closed | เจ้าของให้เลือก timeframe ได้เอง และใช้ ATR เหมือน RSI Step Grid (ATR14) |
| NC-02 — Closed | TP=3×ATR ตาม RSI Step Grid; SL มีระยะเท่ากับ TP จึงเป็น3×ATR ด้านล่างราคาซื้อ |
| NC-03 — Closed | เจ้าของยืนยันอิงราคาซื้อจริงและ ATR ของแท่งสัญญาณ คงระดับหลังเข้า |
| NC-04 — Closed | เจ้าของเลือกตรึงจาก fill แรก ไม่ขยับเมื่อ fill เพิ่ม แทนการปรับราคาตามต้นทุนเฉลี่ย |

ไม่มี Needs Clarification ด้านกฎการเทรดค้างในฉบับนี้ หากพบช่องว่างด้านเงินจริง/
ความเสี่ยงหรือ conflict กับ protection contract ระหว่างวางแผน ต้องบันทึกและถามก่อนแก้

## ขั้นตอนและการตรวจรับถัดไป

1. เจ้าของอนุมัติ requirements ฉบับนี้แล้ว
2. จัดทำ plan.md และ validation.md ระดับ Feature/Batch/Release ให้ตรวจอนุมัติ
3. ใช้ branch แยกจาก F-21 ก่อน implementation โดยรักษา WIP/หลักฐาน F-21 เดิม
4. Implement → targeted tests → review/fix/refactor → ตรวจส่วนที่กระทบ
5. Owner acceptance และ required CI บน final candidate ก่อน merge

ขณะนี้เพิ่มเฉพาะ requirements ไม่มี runtime changes หรือการเปิดบอท/ส่งออเดอร์

## Amendment สำหรับ NC-05 — Proposed, ยังไม่อนุมัติ (2026-11-21)

ข้อกำหนดเดิมด้านบนยังเป็น Approved baseline; ข้อความเก่าที่ว่าไม่มีคำถามค้าง
เป็นสถานะก่อนพบปัญหา finality ของตลาดจริง ขณะนี้ NC-05 ยังเปิดและบล็อกการเข้า
ด้วย UNCONFIRMED; เจ้าของสั่งให้จัดทำข้อเสนอก่อนแก้ ไม่ได้อนุมัติให้เทรดจากข้อมูลนั้น
อ่าน [ข้อเสนอ RM-01–RM-13](real-market-candle-policy.md) และผลกระทบก่อนตัดสินใจ
หากอนุมัติ จะเป็นข้อยกเว้น RQ-01/03 สำหรับ Paper Test Entry รุ่นใหม่เท่านั้น
ตาม version/policy pin, audit และข้อจำกัด RQ-09/12/13 ที่เสนอ ไม่เขียนทับประวัติอนุมัติเดิม
ขั้นถัดไป: อนุมัติ requirements amendment → จัดทำ/อนุมัติ plan+validation เพิ่มเติม → runtime

## คำตัดสินเรื่องจังหวะเข้า — 2026-11-21

เจ้าของระบุ: “เมื่อแท่งเทียน closed ให้ซื้อแท่งเทียนเปิดถัดไป”
สำหรับ Paper Test Entry ให้ใช้แท่งสัญญาณสีเขียวที่จบแล้ว และเข้าในแท่งถัดไป
ไม่ใช้แท่งที่ยังเปิดเป็นสัญญาณ เงื่อนไข close>open, ATR14, หนึ่ง position และ
TP/SL จาก actual first fill คงเดิม ไม่มีการรับรอง fill ที่ราคา open ของแท่งถัดไป
คำสั่ง Market ต้องผ่านข้อมูล/ความสด/admission/STOP เดิม ไม่จำลอง fill ย้อนหลังที่ open
คำสั่งนี้กำหนดจังหวะซื้อ แต่ยังไม่ระบุอนุญาต UNCONFIRMED; NC-05 ยังต้องตัดสินใจ
ก่อนแก้ runtime หากข้อมูลไม่พร้อมในจังหวะเข้า ให้ไม่ส่งคำสั่งขณะนั้น ไม่ข้าม safety gate

## Latest decision NC-05 - Closed: same rules as RSI Step Grid (2026-11-21)

Owner selected the same rules as RSI Step Grid in the context of candle finality and
entry timing. Retain CandleFinality.CLOSED, source/indicator/warm-up/freshness/recovery
guards and common admission. F-21's approved Web execution contract evaluates fresh
completed candles and submits MARKET; it does not guarantee the next candle open price
or introduce an exact-open scheduler. Next-candle entry means acting after the signal
candle completes when these gates permit, without backdating a fill or replaying history.

Paper Test Entry keeps its own green-only signal (no RSI/EMA filters), one position,
and first-fill fixed TP/SL +/-3 ATR14. This decision does not import RSI ARM/FIRE logic.
The earlier UNCONFIRMED exception proposal is Superseded, not approved. Earlier text
awaiting that decision is historical. Both strategies already enforce the same CLOSED
gate, so no runtime change or additional implementation approval is needed for that rule.

Accepted consequence: when the source supplies only UNCONFIRMED candles, both strategies
must wait even if ATR is READY. NC-05 policy decision is closed; real-source entry
validation remains Blocked until actual CLOSED evidence is available. Do not relabel
finality or weaken a guard to generate an acceptance trade. Existing owner/CI and
Batch/Release gates remain pending.

### Explicit owner approval - 2026-11-21

Owner replied "approve" immediately after the CLOSED-only/same-RSI-rule confirmation.
NC-05 decision above is Approved. This approves retaining the existing rule, not the
superseded UNCONFIRMED exception, changing RSI filters, Live activation or owner visual
acceptance/CI completion. No runtime patch is needed because both strategies match.

## Owner UI decision - Approved, 2026-11-21

Owner explicitly requests no Paper PAUSED label and no candle-confirmation waiting
sentence. Hide these presentation elements while preserving real API/audit status,
Stop action, immutable run/config locking and CLOSED/source/trading guards. This
supersedes earlier UI disclosure wording for this waiting state; no financial change.

Owner UI follow-up2026-11-21: do not display indicator waiting text either. Remove
indicator readiness copy from compact/full status, retain API/audit reasons and all
admission/STOP/selector-lock behavior. This is a presentation instruction only.
