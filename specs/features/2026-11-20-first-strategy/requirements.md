# F-21 — rsi_step_grid + ระบบปรับพารามิเตอร์ — Requirements

สถานะ: **Approved — เจ้าของตอบ “approve” หลังยืนยันกลุ่มเดียว/TP ร่วมทุกไม้ วันที่ 2026-11-20**
วันที่: 2026-11-20 (Asia/Bangkok)
Branch: `feature/f-21-first-strategy`

## ทำไมต้องมี

เจ้าของระบุชื่อกลยุทธ์แรกเป็น `rsi_step_grid` วันที่ 2026-11-20
และสั่ง “ใช้กลยุทธ์นี้” โดยให้ `strategy.py` กับ `preset.py` ในวันเดียวกัน
ต่อมาเจ้าของให้อ่าน `https://github.com/yukasung/tiewtrade-desktop`
อ่าน source/spec ที่ commit `9fb12599bd3dad00b2c363c03a6ca1ed113e69e0` แล้ว
ดู [ผลตรวจต้นทางและข้อขัดแย้ง](source-review.md) พร้อม pinned source inventory
ผู้ใช้ต้องเลือกกลยุทธ์ที่เจ้าของระบบกำหนดและปรับพารามิเตอร์ได้ตาม mission C-6/R-06
F-20 วาง strategy contract, lifecycle และ execution linkage แล้ว แต่ไม่ได้กำหนด
สูตรเทรดหรือเผยแพร่กลยุทธ์จริง F-21 ต้องกำหนดกฎเหล่านี้ให้ตรวจสอบได้ก่อนเขียนโค้ด

ชื่อ `Grid Close System` และช่องงบในแผง Paper Spot เป็น UI จากงานก่อนหน้า
ไม่ใช่หลักฐานอนุมัติสูตร Grid การแบ่งไม้ หรือความหมายงบ
ดู [F-20 requirements](../2026-11-19-bot-lifecycle/requirements.md)
และ [Paper Spot Bot Panel requirements](../2026-11-13-paper-spot-bot-panel/requirements.md)

## ขอบเขต

### ทำใน F-21

- กลยุทธ์สำเร็จรูปตัวแรก `rsi_step_grid` ตามกฎที่เจ้าของตัดสินใน NC ด้านล่าง
- ข้อกำหนดพารามิเตอร์ ชนิด หน่วย ค่าเริ่มต้น ช่วงค่า และข้อจำกัดร่วมกัน
  รวมความหมายของงบและผลของการเปลี่ยนค่า
- การเลือกกลยุทธ์และปรับพารามิเตอร์ผ่าน UI/API เชื่อม F-20 โดยใช้ lifecycle
  และ order admission/execution เดิม
- หลักฐาน deterministic strategy, การคำนวณเงิน และ Paper flow ของกลยุทธ์จริง
  ตามเกณฑ์ที่จะจัดทำใน validation หลัง requirements ได้รับอนุมัติ

### ไม่ทำใน F-21

- กลยุทธ์ที่ผู้ใช้เขียนเอง AI ตัดสินใจเทรด backtesting หรือ Futures
- เปลี่ยน loss limit/formula, เพดานบอท, MANUAL/BOT, STOP/resume หรือสิทธิ์ Live
- สร้าง Live executor/reconciliation แทน F-22/F-23/F-24 หรือเปิด production
  admission เพียงเพราะเพิ่มกลยุทธ์แล้ว
- เลือกสูตรเทรด จำนวนเงิน ค่าเสี่ยง หรือ defaults แทนเจ้าของ

## ข้อกำหนดที่อ้างอิงจากระบบเดิม

รายการนี้เป็นร่างสำหรับตรวจรับ requirements; ใช้กฎจากไฟล์เจ้าของด้านล่าง
ส่วนที่ไฟล์ยังไม่ระบุบล็อกด้วย NC ไม่ถือว่าคำสั่งเลือกกลยุทธ์อนุมัติ requirements ทั้งฉบับ

| รหัส | ข้อกำหนด | ที่มา |
|---|---|---|
| RQ-01 | กลยุทธ์มาจากเจ้าของระบบ ผู้ใช้เลือกและปรับได้เฉพาะพารามิเตอร์ที่ระบุไว้ใน requirements ที่อนุมัติ; ไม่รับโค้ดกลยุทธ์จากผู้ใช้ | mission C-6/R-06 และ §7 |
| RQ-02 | ต้องระบุ identity/version คู่เทรด timeframe แหล่งข้อมูล trigger/warm-up และเงื่อนไขเข้า/ออกที่แน่นอนก่อน implement; ไม่อนุมานว่าซื้อขายเมื่อแท่งปิดหรือใช้ indicator ตัวใดจาก UI | F-20 RQ-02/03; NC-F21-01/02 |
| RQ-03 | ตรรกะกลยุทธ์พึ่ง core เท่านั้น รับ inputs/state แล้วคืน decision/state; ไม่อ่าน DB/เครือข่าย/นาฬิกา/credential หรือส่งออเดอร์เอง; input/config/state เดียวกันต้องให้ผลเหมือนกันใน Paper/Live | architecture §1–3; F-20 RQ-01/04/05; ADR-004 |
| RQ-04 | เงิน ราคาและปริมาณใช้ Money/Quantity และกฎ numeric/rounding เดิม; สูตรขนาดไม้ งบจอง/ใช้ไป การคืนงบ ค่าธรรมเนียม และการจัดการเศษต้องมีความหมายตามคำตัดสินเจ้าของ ไม่สร้างเพดาน/default ใหม่ | AGENTS.md กฎ 6; F-20; NC-F21-03 |
| RQ-05 | ต้องกำหนดชนิด หน่วย defaults ช่วงค่า และเงื่อนไขข้ามพารามิเตอร์ให้ครบ; server ตรวจค่าก่อนยอมรับ ไม่อาศัย UI validation อย่างเดียว | F-20 RQ-02/06/08; NC-F21-04 |
| RQ-06 | Run ผูก strategy/config version ที่กู้คืนได้และตรึงค่าตลอด run; เปลี่ยนค่าต้องเป็น run ใหม่เมื่อไม่มี position/order ที่ระบบดูแลตาม F-20 ไม่เปลี่ยน run เดิมเงียบ ๆ และไม่ปิดรายการเดิมเพื่อสร้าง run ใหม่เอง | F-20 RQ-06/14; NC-F20-03; NC-F21-05 |
| RQ-07 | Intent ผ่าน admission/risk/catalog/STOP/protection และ execution เดิม; ปรับ state จากผลจริงของคำสั่ง ไม่ถือว่า signal คือ fill; ข้อมูลไม่พร้อมต้องไม่สร้างสัญญาณจากศูนย์หรือข้อมูลเก่า | trading-safety §3–6/8–13; F-20 RQ-03/04/18/19 |
| RQ-08 | Config/state/progress ที่จำเป็นต่อ recovery ต้องอยู่ PostgreSQL; restart/redeploy/หลาย instances/Redis loss ต้องไม่ทำ state หายหรือเกิดออเดอร์ซ้ำ ใช้ transaction, single writer และ durable linkage เดิม; browser เก็บได้เพียง draft ไม่เป็น authority | AGENTS.md Stateless; F-20 RQ-15..19 |
| RQ-09 | UI ต่อยอดแผง/controls และ component กลางจาก admin template รองรับไทย/อังกฤษ light/dark keyboard และ responsive; แสดงโหมด ค่าที่ใช้จริง validation error และเหตุเริ่มไม่ได้ ไม่แสดงว่ารับคำขอเท่ากับกำลังเทรดหรือ fill แล้ว | F-20 RQ-09/13/25; frontend standard |
| RQ-10 | คง disabled/activation gates เดิมจนผ่าน dependencies และการอนุมัติเปิดใช้งานที่เกี่ยวข้อง; การอนุมัติหรือ merge F-21 ไม่เปิด Paper production/Live อัตโนมัติ ไม่ใช้ test strategy รับรองกลยุทธ์จริง | F-20 scope/RQ-08 และ validation V-20/21; trading-safety §1 |
| RQ-11 | แต่ละ Basket ของ run มีกลุ่มเดียว รวมทุกไม้ที่ยังเปิดและมี TP ร่วมกัน ไม่แยกกลุ่มตามราคาซื้อ; TP ใช้ต้นทุนเฉลี่ยถ่วงจำนวนเหรียญของไม้ที่ยังเปิดทั้งหมด +3×ATR ของไม้ล่าสุด และคงกฎเลื่อนเข้าใกล้เท่านั้นตามรายละเอียด Web ด้านล่าง | เจ้าของสั่ง “ให้มีกลุ่มเดียว” 2026-11-20; สูตรเดิม SR-10 |

## กฎจากไฟล์กลยุทธ์ที่เจ้าของเลือก — 2026-11-20

เก็บต้นฉบับโดยไม่แก้ที่ [strategy.py](references/strategy.py) และ
[preset.py](references/preset.py) จาก `/Users/chainarongjaykeaw/Downloads/`
ไฟล์เหล่านี้เป็นหลักฐานพฤติกรรม ไม่ใช่ runtime implementation ของ repo ปัจจุบัน
imports/types ของต้นฉบับต่างจาก F-20; การ port ต้องรักษากฎและใช้ contracts,
Money/Quantity และ durable state เดิมตาม RQ-03/04/08 ไม่คัดลอก process memory
หรือ Decimal เปล่าสำหรับราคาเข้าระบบ

### Preset ต้นทาง (หลักฐานอ้างอิงก่อนเงื่อนไขเพิ่มเติมของเจ้าของ)

| ค่า | canonical v1 |
|---|---|
| preset version | `rsi-step-grid-v1` |
| RSI period | 14 |
| RSI reset threshold | 30 |
| RSI entry threshold | 50 |
| ATR period | 14 |
| take-profit ATR multiplier | 3 |

`preset.py` ปฏิเสธ version อื่นและค่าที่ต่างจาก canonical v1 ทั้งหมด
จึงยังไม่ให้สิทธิ์ผู้ใช้แก้หกค่านี้ แม้ feature มีเป้าหมาย parameter editor
property `minimum_warm_up_candles` เรียก helper ที่ไม่ได้แนบมากับสองไฟล์แรก
ต่อมาอ่าน helper ใน Desktop repo พบ floor250แท่ง แต่สูตร seed ATR ต่างจาก F-11
และ indicator update ไม่ได้บังคับ250เอง ดู source-review D-03/W-02 และ NC-F21-02

### สัญญาณและสถานะที่อ่านได้จาก strategy.py

| รหัส | พฤติกรรมต้นฉบับ |
|---|---|
| SR-01 | `entry_number` ต้องเป็นจำนวนบวก มิฉะนั้น error; ผู้เรียกเป็นผู้ส่งเลขไม้และ `can_enter` เข้ามา ไม่ได้กำหนดสูตรหรือเพดานในไฟล์นี้ |
| SR-02 | เมื่อมี pending intent ให้คืนไม่มี intent ทันที ไม่ปรับ reset close แม้ RSI ต่ำกว่า 30 |
| SR-03 | เมื่อไม่มี pending และ RSI < 30 ให้แทน reset close ด้วย close ของแท่งที่ประเมินนั้นแล้วคืนไม่มี intent; ต่ำกว่า 30 หลายแท่งใช้ close ของแท่งล่าสุด ไม่ใช่ค่าต่ำสุด |
| SR-04 | สร้าง LONG entry intent ก็ต่อเมื่อมี reset close, RSI > 50, close > open, close > reset close และ can_enter เป็นจริง ครบทุกเงื่อนไข; RSI = 30 ไม่ reset, RSI = 50 ไม่เข้า, doji หรือ close = reset close ไม่เข้า ไม่มีกฎต้อง cross จากแท่งก่อน |
| SR-05 | Intent บรรจุ session/preset version/เลขไม้/แท่งสัญญาณ/ATR จาก input และ LONG; ยังไม่มีราคา order จำนวน หรือ TP/SL order ในไฟล์นี้ แล้วเก็บ intent เป็น pending |
| SR-06 | Callback filled ที่ identity ตรง pending ล้างทั้ง pending และ reset close; ไม้ถัดไปต้องมี reset ใหม่ Callback rejected ที่ตรง pending ล้างเฉพาะ pending คง reset close; callback ไม่ตรงหรือไม่มี pending เป็น error ในต้นฉบับ |
| SR-07 | Intent identity เป็น SHA-256 ของ session UUID, preset version, symbol, timeframe, candle open_time.isoformat() และเลขไม้ เรียงตามนี้คั่นด้วย newline; การเชื่อม identity กับ F-20 ต้องบันทึกใน plan โดยรักษาการกันซ้ำและความคงที่ |

การ callback จากต้นฉบับไม่ระบุ partial fill/cancel/unknown หรือ dedup ของ feedback
จึงยังใช้แทน lifecycle ผลจริงของ F-20 ไม่ได้ ส่วน `take_profit_atr_multiplier = 3`
ยังไม่ได้ถูกใช้คำนวณใน strategy.py; ต่อมาอ่าน basket code ใน Desktop repo พบสูตร
TP รายกลุ่มตามส่วนถัดไป ไม่ใช่การใช้ fill price +3×ATR ให้ทุกไม้แยกกันเสมอ
ไม่มีเงื่อนไขระยะ grid ตามราคาหรือการทบขนาดไม้ในสองไฟล์นี้

### กฎเพิ่มเติมจาก Desktop repo — ร่างสำหรับอนุมัติ

แหล่งหลัก `trading/basket.py`, `entry_pair.py`, `cooldown_policy.py`, `capital.py`,
`session_config.py` และ UI ที่ pin ไว้ใน [inventory](references/desktop-source-inventory.md)
ใช้ [source-review](source-review.md) เป็นรายการหลักฐาน/ข้อขัดแย้ง ไม่เลือก code
หรือ doc ฝั่งใดเป็นข้อกำหนด F-21 โดยอัตโนมัติ

| รหัส | พฤติกรรมที่พบและขอบเขตที่เสนอ |
|---|---|
| SR-08 | ประเมิน entry บน completed candle ไม่เข้าใหม่จากแท่งที่เพิ่ง exit หรือ backfill; pending เก่าต้องไม่ไป fill จากสัญญาณเก่าที่แท่งสดภายหลัง; backend indicator/provenance และ entry timing ของ Web ต้องตัดสินใน NC-F21-02/06 |
| SR-09 | Long entry ราคาต่ำกว่า average ถ่วง quantity ของกลุ่มที่เปิดล่าสุดเข้ากลุ่มนั้น; ราคาเท่าหรือสูงกว่าสร้างกลุ่มใหม่ ไม่ย้าย group assignment ภายหลัง |
| SR-10 | TP กลุ่ม = floor-to-tick(weighted average ของไม้ที่ยังเปิด +3×ATR ของไม้ล่าสุดในกลุ่ม) และ min กับ TP เดิม; เมื่อไม้ล่าสุดออกใช้ ATR ของไม้ที่ยังเหลือล่าสุดตาม filled_at/entry_number กองว่างจึงลบ TP; TP เป็น durable history ไม่คำนวณคืนจาก inventory อย่างเดียว |
| SR-11 | ขายเฉพาะกลุ่มที่ถึงเป้า ไม่กวาดทุก Basket; ไม่มี strategy SL; เส้นทางปิด/ลดโดยผู้ใช้และ risk/STOP/protection safety ของ Web ยังคงเดิม; ไม่คัดลอก desktop fill/PnL ที่ไม่คิด fee มาแทน execution facts |
| SR-12 | max_entries จำกัดจำนวนไม้ที่ยังเปิด ขายแล้วคืนช่องแต่ไม่คืน entry_number; Basket จบเมื่อทุกไม้ปิด แล้ว reset pair/cooldown สำหรับ Basket ใหม่; ทุกรายการต้องสัมพันธ์กับ actual fill ของ Web |
| SR-13 | Canonical preset แก้ไม่ได้; UI ต้นทางให้ปรับ capital_per_entry ไม่มีเงิน default, max_entries เลขคู่2–20 default10, timeframe default5m และ cooldown Off/1–30วัน default30 ก่อนเริ่ม; config immutable ระหว่าง run; รอตัดสินความขัดแย้งเงิน/cooldown/คู่/timeframeก่อนยืนยันค่าตั้ง Web |

## เงื่อนไข BUY เพิ่มเติมจากเจ้าของ — 2026-11-20

เจ้าของสั่ง: “เพิ่มเงื่อนไข buy เมื่อ ema 20 > ema 50 และ rsi > 60 และแท่งเทียนสีเขียวปิดเหนือ ema >20 และ ema 50”
บันทึก `ema >20` ในบริบทประโยคเป็นชื่อ `EMA20` ตามการระบุ EMA20 ต้นประโยค

| รหัส | เงื่อนไขที่เจ้าของระบุ — ต้องจริงพร้อมกัน |
|---|---|
| BUY-01 | EMA20 > EMA50 |
| BUY-02 | RSI > 60 |
| BUY-03 | แท่งเทียนสีเขียว: close > open |
| BUY-04 | close > EMA20 และ close > EMA50 |

ใช้ strict `>` ตามคำสั่ง; ค่าเท่ากันไม่ผ่านและ doji ไม่ใช่แท่งเขียว
ไม่ตีความเป็น EMA crossover หรือ RSI crossing เพราะเจ้าของระบุความสัมพันธ์ค่า
ไม่ได้ระบุว่าต้องเพิ่งตัดกันบนแท่งนี้
ใช้ backend EMA20/EMA50/RSI14 จาก F-11 เป็นจุดอ้างอิงเดิม ไม่คำนวณ indicator
แยกในกลยุทธ์หรือ browser; สูตร/seed/readiness ที่ต่างจาก Desktop ยังอยู่ NC-F21-02

เจ้าของยืนยัน “เพิ่มเป็นตัวกรองโดยยังรอ RSI < 30 ตามกฎเดิม” วันที่ 2026-11-20
ปิด NC-F21-07: BUY-01..04 เป็นตัวกรอง AND ของ ARM/FIRE เดิม
เกณฑ์ RSI >60 ทำให้ >50 เดิมผ่านโดยปริยาย ไม่ใช่ทางเข้าอีกทางแบบ OR
เงื่อนไขเจ้าของมีลำดับเหนือ canonical preset ต้นทางในส่วนที่เปลี่ยน

สูตร BUY ที่รวมแล้ว ต้องจริงครบทุกข้อบนแท่งสัญญาณ:

```text
pending_intent ไม่มี
AND reset_close มีค่า (เคย RSI < 30 ตามกฎ ARM เดิม)
AND RSI14 > 60
AND EMA20 > EMA50
AND close > open
AND close > reset_close
AND close > EMA20
AND close > EMA50
AND can_enter
```

กฎ ARM/state เดิมยังใช้: เมื่อไม่มี pending และ RSI <30 ให้แทน reset_close
ด้วย close ของแท่งนั้นแล้วไม่ BUY; ระหว่าง pending ไม่ปรับ reset;
เมื่อ filled ล้าง pending และ reset_close จึงต้องรอ ARM ใหม่สำหรับไม้ถัดไป;
เมื่อ rejected ล้างเฉพาะ pending และคง reset_close
ตัวกรองไม่สร้างสัญญาณเองและไม่ข้าม admission/risk/STOP/protection เดิม
การเชื่อม partial fill/cancel/unknown ใช้ contracts เดิมของ Web ตามคำยืนยัน
NC-F21-01/06 และข้อสรุป Web ด้านล่าง ไม่ใช้ callback ต้นฉบับแทนผลจริง

พฤติกรรมที่เปลี่ยนต้องมี strategy/config identity แยกจาก Desktop canonical v1
เพื่อไม่เปลี่ยนความหมาย `rsi-step-grid-v1` หรือ run เดิมเงียบ ๆ ตาม F-20 RQ-06
ยังไม่กำหนดชื่อ version ใหม่หรือให้ผู้ใช้ปรับ60/20/50เองโดยไม่มี requirements

## ข้อสรุปสำหรับ Web หลังคำตอบเจ้าของ — 2026-11-20

ส่วนนี้ใช้ประกอบการอนุมัติ requirements ทั้งฉบับ มีลำดับเหนือข้อมูลต้นทาง
SR-01..13 ในส่วนที่ต่างกัน; คง source review เป็นหลักฐานประวัติ ไม่แก้ไฟล์ต้นฉบับ

| ค่า | ข้อกำหนด Web |
|---|---|
| คู่เทรด | เลือก BTC/USDT หรือ ETH/USDT ก่อนเริ่ม หนึ่งคู่ต่อ run; ยังต้องอยู่ใน supported-symbol catalog ที่ใช้งานได้ตาม F-37 ไม่เพิ่ม BNB จาก Desktop |
| Timeframe | เลือกจากชุด Web ที่รองรับ: 1m, 3m, 5m, 15m, 1h, 4h, 1d, 1w, 1M; 1M คือเดือนปฏิทิน และไม่มี30mจากDesktop; ใช้ shared timeframe contract ไม่สร้างรายการ runtime คู่ขนาน |
| Warm-up | ก่อนประเมินกลยุทธ์ต้องมี completed candles ต่อเนื่องอย่างน้อย250แท่งของคู่/timeframeที่เลือก พร้อม EMA20/EMA50/RSI14/ATR14 ที่ backend รับรองพร้อม; 250เป็นเกณฑ์ขั้นต่ำ ไม่เลื่อน central seed หรือคำนวณจากหน้าต่าง250ใหม่ |
| ข้อมูลไม่พอ | หากข้อมูลตาม retention/source/readiness เดิมไม่พอ เช่น timeframe ยาว ยังเริ่มประเมินไม่ได้และต้องแสดงเหตุผล; ไม่ลด250 ไม่สังเคราะห์แท่ง ไม่เปลี่ยน retention เพื่อให้ผ่าน |
| เงินต่อไม้ | ผู้ใช้กรอกจำนวนบวกใน quote asset USDT ไม่มีจำนวนเงิน default; ใช้เงินต่อไม้ตามที่กรอก ไม่หารจำนวนไม้ ไม่ทบเงินตามเลขไม้; actual reservation/fee/lot/minimum/available funds ใช้ policy Web เดิม |
| จำนวนไม้ | max_entries เป็นจำนวนเต็ม1–10 เพิ่ม/ลดทีละ1 เลือกได้ทั้งเลขคี่และเลขคู่ตามคำสั่งเจ้าของ; คงข้อเสนอdefault10 จำกัดไม้ที่ยังเปิด; pending intent ต้องไม่จองช่องซ้ำหรือทำให้เกินเพดาน ช่วงค่าเจ้าของยืนยันแล้ว ส่วนdefaultรวมให้ตรวจในการอนุมัติ requirements ทั้งฉบับ |
| ค่าเริ่มต้นหน้าจอ | เสนอ timeframe5m ตามต้นทาง; แสดงคู่ที่เลือกชัดเจน ไม่เริ่ม run จาก default อัตโนมัติ |
| Cooldown | ไม่มี cooldown จากจำนวนไม้หรือเวลา ไม่มี dropdown วัน/เดือนหรือปุ่มปลด; ไม้ถัดไปยังต้องผ่าน ARM/FIRE, pending/max_entries และ safety gates เดิม |
| กลุ่มไม้ | มีกลุ่มเดียวต่อ Basket ของ run รวมทุกไม้ที่ยังเปิดไม่ว่าราคาไม้ใหม่ต่ำกว่า เท่ากับ หรือสูงกว่าต้นทุนเฉลี่ย; ทุกไม้ใช้ TP ร่วม ไม่รวมข้าม owner/account/mode/run/pair |
| พารามิเตอร์กลยุทธ์ | EMA20/50, RSI14 reset30/entry60 และ ATR14 multiplier3 คงที่ในรุ่นใหม่; ผู้ใช้ปรับเฉพาะคู่/timeframe/เงินต่อไม้/max_entries ก่อนเริ่ม ไม่เปิดแก้สูตรหรือตัวเลขคงที่จาก browser |
| การเปลี่ยนค่า | Config ถูกตรึงตลอด run ตาม F-20; เปลี่ยนค่าด้วย run ใหม่ได้เมื่อไม่มี position/order ที่ระบบดูแล ไม่ขายรายการเดิมให้อัตโนมัติ |

เจ้าของเห็นด้วยให้นำเงื่อนไข BUY และสูตร TP มาใช้กับระบบซื้อขายเดิมของ Web
ใช้ F-11 central indicators/seed/precision และ F-15 matching/liquidity/fees
รวม F-17 TP trigger→MARKET; ไม่ใช้ Desktop next-candle-open/target fills
และไม่รับประกัน numerical replay parity กับ Desktop

- ประเมินสัญญาณจาก completed candle ที่พร้อมและสดตาม trigger/readiness contract
  ไม่ซื้อด้วย backfill หรือสัญญาณเก่าที่เลื่อนไปรอแท่งสด; ใช้ pending/dedup เดิม
- สัญญาณ BUY ผ่าน common admission แล้วจึงส่งตาม execution contract Web
  ราคา fill/quantity/fee และเงินจองมาจากผลจริง ไม่รับรองซื้อที่ open แท่งถัดไป
- Group/TP ใช้ RQ-11 แทนการจัดหลายกลุ่มตาม SR-09/11 ของ Desktop:
  ทุกไม้ใน Basket รวมกลุ่มเดียว โดยเชื่อม actual fill และ protection allocation ของ F-17
  จัดการเฉพาะปริมาณสุทธิที่ยืนยันแล้ว; partial fill ไม่ถือเป็นทั้งไม้
  ผล unknown ต้อง reconcile ก่อนออกคำสั่งซ้ำตาม F-20; reject/cancel ไม่ล้าง fill ที่เกิดแล้ว
- ต้นทุนเฉลี่ยรวม = sum(ราคาซื้อ × จำนวนเหรียญของไม้ที่ยังเปิด) / sum(จำนวนเหรียญที่ยังเปิด)
  TP ใหม่ = floor-to-tick(ต้นทุนเฉลี่ยรวม +3×ATR ของไม้ที่ยังเปิดล่าสุด)
  โดยใช้ ATR ที่ผูกกับแท่งสัญญาณของไม้นั้น; เมื่อมี TP เดิมให้ใช้ min(TP ใหม่, TP เดิม)
  คง numeric/rounding contracts ของ Web ไม่คำนวณด้วย Decimal เปล่าหรือ float
- เมื่อมี fill เพิ่มหรือปิดบางไม้ ให้คำนวณจากไม้ที่ยังเปิดในกลุ่มเดียวใหม่;
  ถ้าไม้ล่าสุดออกให้ใช้ ATR ของไม้ที่ยังเปิดล่าสุดตาม filled_at/entry_number
  คง TP ที่ถือไว้เป็น durable state ไม่รีเซ็ตเพราะเพิ่มไม้หรือ restart
- TP ที่ถึงเงื่อนไขส่ง MARKET exit ผ่านเส้นทาง F-17 ตาม allocation ของกลุ่มนั้น
  ครอบคลุมปริมาณที่ยังเปิดของทุกไม้ใน Basket นี้ เนื่องจากมีกลุ่มเดียว
  ราคา/ปริมาณขายจริงอาจต่างจาก target และอาจ fill บางส่วน; คงสถานะส่วนที่เหลือจริง
  ไม่บันทึกว่าปิดทุกไม้สำเร็จเพียงเพราะแตะเป้า
- เมื่อทุกไม้ปิดจริง Basket จบ; Basket ใหม่เริ่มกลุ่มเดียวใหม่และไม่มี TP เดิมให้เทียบ
  ไม่ยกเป้าของ Basket ที่ปิดแล้วมาครอบ Basket ใหม่
- คงเงื่อนไขตั้ง/แก้ protection และ target-already-crossed/failure policy เดิมของ F-17
  ไม่ขยับ target หนีหรือ bypass gates เพื่อบังคับตั้งสำเร็จ หากติด contract ต้องรายงาน
  และบันทึก amendment ก่อนลงมือ ไม่เปลี่ยน business rule ด้วย implementation
- ไม่มี SL ที่กลยุทธ์สร้างเพิ่มเอง; loss limits, STOP, protection-failure policy,
  manual reduction และการแยก Paper/Live ยังคงตาม Web เดิม

รายละเอียด feedback/group/protection persistence และ validation cases ต้องระบุใน
plan/validation หลัง requirements ได้รับอนุมัติ โดยรักษากฎข้างต้น หากพบข้อกำหนด
ธุรกิจที่ยังตัดสินไม่ได้ต้องเปิด Needs Clarification ก่อน implement

## ของเดิมที่เกี่ยวข้อง

รายการนี้เป็นจุดอ้างอิงสำหรับ plan หลังอนุมัติ ไม่กำหนด schema/API ล่วงหน้า:

- `backend/src/tiewtrade/core/strategies.py` — descriptor, configuration/state document,
  inputs, decisions และ execution feedback ของ F-20
- `backend/src/tiewtrade/strategies/` — package boundary ของกลยุทธ์
- `backend/src/tiewtrade/core/money/` — เงิน/ปริมาณและ arithmetic ที่กำหนดไว้แล้ว
- `backend/src/tiewtrade/services/engine/bot.py`, `backend/src/tiewtrade/infra/bots/`
  — orchestration, persistence, admission และ recovery ของ F-20
- `backend/src/tiewtrade/services/api/bot_routes.py` — lifecycle API เดิม
- `backend/src/tiewtrade/core/indicators.py`, `backend/src/tiewtrade/infra/market_data/indicator_reader.py`
  — indicator contract และ backend source หากกลยุทธ์ที่อนุมัติต้องใช้
- `frontend/src/PaperBotPanel.tsx`, `frontend/src/BotRunStatus.tsx`,
  `frontend/src/components/ui/` และ `references/admin-template/` — UI เดิม

## กฎความปลอดภัยที่เกี่ยวข้อง

ใช้ trading-safety §1–6 และ §8–13, architecture, Stateless Application & Session
Management ใน AGENTS.md และ ADR-004 ต่อ ไม่เปลี่ยนสูตรเงิน risk หรือกฎ protection
ของ F-17/F-18/F-19/F-37; การเพิ่มเงื่อนไขเฉพาะกลยุทธ์ต้องได้รับอนุมัติก่อน
Automated validation ต้องไม่ส่งออเดอร์ Live

## ยังไม่ชัด — Needs Clarification

### คำตอบเจ้าของเพิ่มเติม — 2026-11-20

- **ให้มีกลุ่มเดียว:** ทุกไม้ที่ยังเปิดของ Basket เดียวกันใช้ต้นทุนเฉลี่ยรวมและ TP ร่วม
  ไม่แยกกลุ่มเมื่อซื้อแพงขึ้น คำสั่งนี้แทนพฤติกรรมหลายกลุ่ม SR-09/11 ของ Desktop
  โดยคง ATR multiplier3 และกฎ TP เลื่อนเข้าใกล้อย่างเดียวใน SR-10
  รายละเอียดข้อกำหนดที่ใช้จริงอยู่ RQ-11 และข้อสรุป Web; เก็บ source เดิมไว้เป็นหลักฐาน
- **จำนวนไม้ไม่ต้องเป็นเลขคู่:** เจ้าของยกเลิกข้อจำกัด parity ของ Desktop;
  max_entries รับเลขคี่และเลขคู่ได้ ไม่ใช้ Entry Pair เป็นเงื่อนไขจำนวนไม้หรือการเริ่มไม้ใหม่
  ต่อมาเจ้าของสั่ง “ให้เริ่มที่ 1 ถึง 10” จึงใช้ช่วง1–10แทน2–20 เพิ่มทีละ1
  คงข้อเสนอdefault10 โดยยังรออนุมัติ requirements ทั้งฉบับ
  เก็บ SR-13 เป็นหลักฐานต้นทาง ไม่ใช้ข้อจำกัดเลขคู่หรือช่วง2–20ของDesktopในWeb
- **เงินกรอกต่อไม้:** `capital_per_entry` เป็นเงินสำหรับไม้หนึ่ง ไม่ใช่เงินรวม
  ที่นำไปหารจำนวนไม้ จึงปิดข้อขัดแย้งความหมายเงินใน D-01/NC-F21-03
  การจองเงิน/fee/partial fill ยังต้องเชื่อม policy ของ Web ที่รออธิบายและยืนยัน
  ใน NC-F21-01/06 ไม่ถือว่าคำตอบนี้อนุมัติเปลี่ยนกฎ fee หรือเพิ่มเงินอัตโนมัติ
- **ไม่มี cooldown:** ไม่ตั้งเวลาพักหลังครบคู่ ไม่มี cooldown dropdown/waiver
  หรือปุ่ม Cancel Cooldown ใน F-21 และไม่ใช้เดือน UTC; ไม่ต้องรอเพราะครบสองไม้
  แต่ทุกไม้ยังต้อง ARM ใหม่ตามกฎ reset และผ่าน max_entries/pending/risk/STOP
  และ admission เดิม กฎ grouping/TP ไม่เปลี่ยนเพราะยกเลิก cooldown
  คำตัดสินนี้แทนเฉพาะ cooldown ของ SR-13/ต้นทาง ไม่ได้ให้ปรับ preset/session
  ค่าอื่นระหว่าง run หรือยกเลิกกฎพักจากข้อมูลไม่พร้อมของ F-20
- **การเชื่อม Web:** หลังอธิบาย Desktop candle fills/ไม่มีfee เทียบกับ Web matching,
  fee และ TP→MARKET เจ้าของตอบ “3. เห็นด้วย” ยืนยันใช้ระบบ Web เดิมตามข้อสรุปด้านบน
  ปิด NC-F21-06; คำตอบก่อนหน้า “ข้อนี้ไม่เข้าใจ” ถูกชี้แจงแล้ว
- **คู่/timeframe/warm-up:** หลังเสนอ BTC/USDT หรือ ETH/USDT, timeframe ที่ Web
  รองรับ และข้อมูลอย่างน้อย250แท่ง เจ้าของตอบ “4. ใช่” ปิด NC-F21-02

อ่าน Desktop source เพิ่มแล้ว ได้กฎ SR-08..13 แต่พบข้อขัดแย้งต้นทางและความต่าง
กับ contracts ของ Web ตาม source-review; คำถามเดิมเรื่องไม่มีต้นฉบับถูกแทนด้วย
ประเด็นที่เจาะจงด้านล่าง ไม่ขอให้เจ้าของเขียนกลยุทธ์ใหม่ตั้งแต่ต้น

| รหัส | เจ้าของต้องกำหนด | บล็อกอะไร |
|---|---|---|
| NC-F21-01 — Closed: scope (2026-11-20) | ใช้ signal/group/TP จากกลยุทธ์และ F-17 จริงตามคำยืนยันใช้ระบบ Web ใน NC-F21-06; partial fill/unknown/target crossed คง policy เดิมตามข้อสรุป Web ไม่คัดลอก candle fills | ปิดคำถามขอบเขต; รายละเอียด implementation/proof อยู่ plan/validation ไม่อนุมัติเปลี่ยน protection contract |
| NC-F21-02 — Closed (2026-11-20) | เจ้าของตอบ “4. ใช่” ต่อข้อเสนอ BTC/USDT หรือ ETH/USDT, timeframeที่Webรองรับ และอย่างน้อย250แท่ง; ใช้ F-11 indicators ตาม NC-F21-06 | ปิดการเลือกตลาด/ข้อมูล/warm-up; ข้อมูลไม่พร้อมยังห้ามประเมิน |
| NC-F21-03 — Closed (2026-11-20) | เจ้าของเลือก “เงินกรอกต่อไม้”; ไม่หารจำนวนไม้หรือหัก trading ratio ตามเอกสารต้นทางฝั่งอื่น | ปิด D-01 เรื่องความหมายเงิน; รายละเอียด fee/reservation/execution ยังอยู่ NC-F21-01/06 |
| NC-F21-04 — Closed: cooldown (2026-11-20) | เจ้าของเลือก “ไม่มี cooldown”; ครบคู่ไม่ทำให้ต้องรอ ไม่มีตัวเลือกวัน/เดือนหรือ waiver UI; ยังคง reset/pending/max_entries/risk/STOP gates | ปิด D-02 และนโยบาย cooldown; ค่า session อื่นของ SR-13 ยังเป็นร่างสำหรับ requirements |
| NC-F21-05 — Resolved in draft | คง run/config pin ของ F-20 และเสนอค่าตั้งที่ตรึงตลอด run ตามต้นทาง; ไม่เพิ่มการแก้ระหว่าง run หรือปิด inventory อัตโนมัติ รวมไว้ในฉบับนี้เพื่ออนุมัติพร้อมกัน | รออนุมัติ requirements ทั้งฉบับ |
| NC-F21-06 — Closed (2026-11-20) | เจ้าของตอบ “3. เห็นด้วย” หลังอธิบายการใช้ BUY/TP กับ indicator/matching/fee/protection เดิมของ Web และผลตัวเลขที่อาจต่างจากDesktop | ปิดขอบเขต port; ไม่รับรอง numerical parity หรือเปิดproduction/Live |
| NC-F21-07 — Closed (2026-11-20) | เจ้าของยืนยัน BUY-01..04 เป็นตัวกรอง AND เพิ่มบน ARM/FIRE เดิม ต้องเคย RSI <30 และ close > reset_close; สูตรรวมและ state ตามส่วนเงื่อนไข BUY | ปิดความไม่ชัดเรื่องการรวมเงื่อนไข; ไม่ปิดข้อค้างอื่นหรืออนุมัติ requirements ทั้งฉบับ |

คำตอบบางส่วนยังไม่ใช่การอนุมัติ requirements ทั้งฉบับ ต้องรวมคำตัดสินไว้ที่นี่
และขออนุมัติก่อนทำ plan/validation

## สถานะและจุดหยุดถัดไป

### Amendment NC-F21-08 — Approved FIFO, 2026-11-20

หลังพบว่าmanualSELLเลือกหลายentryแต่partialfillไม่มีattributionในF-17เดิม
เจ้าของยืนยัน “ใช้ FIFO ตามที่แนะนำ” ให้ตัดquantityที่ขายจริงจากentry_numberเก่า
ไปใหม่ เฉพาะไม้และไม่เกินquantityที่ผู้ใช้เลือกขายในคำขอนั้น ไม่แตะไม้ที่ไม่ได้เลือก
filled quantityเท่านั้นที่ตัดออกจากbasket; admission/manualreleaseไม่ใช่confirmeddisposal
partialfillถัดไปต่อจากยอดที่ตัดไปแล้วอย่างidempotent ไม่เริ่มโควตาใหม่หรือกระจายเศษ
เมื่อทราบremainingentriesแล้วคำนวณTPด้วยสูตรsinglebasket/heldminเดิม
คำตัดสินนี้ปิดNC-F21-08และอนุญาตimplementation/validationตามamendment

เริ่มขั้น requirements แล้ว ยังไม่แก้ runtime หรือรันทดสอบระบบ
F-20 ยังมี final-SHA CI/ด่านก่อน merge ค้างตาม roadmap ไม่ถือว่าการเริ่ม F-21 ปิดด่านนั้น
เจ้าของตอบ “approve” อนุมัติ requirements ทั้งฉบับหลังคำสั่งให้มีกลุ่มเดียว
วันที่ 2026-11-20 รวมช่วงจำนวนไม้1–10/default10, timeframe default5m และ config policy
ที่แสดงในข้อสรุป Web; ถ้อยคำ “เสนอ/รออนุมัติ” ในบันทึกก่อนหน้านี้คงไว้เป็นประวัติ
ไม่มี Needs Clarification ของ requirements ที่ยังค้าง ณ การอนุมัติฉบับนี้
ขั้นถัดไป: จัดทำ plan/validation เพื่ออนุมัติ → จึง implement ตาม AGENTS.md
ยังไม่เขียน runtime หรือ commit/push/merge ใน checkpoint เอกสารนี้

### Amendment NC-F21-09 — Owner approved 2026-11-20

เจ้าของเลือก “ห้ามแก้ TP/SL รายไม้ของ F-21 ใช้สูตร TP ร่วมเท่านั้น (แนะนำ)”
F-21-linked allocations ปฏิเสธ manual REPLACE ทั้งราคา/quantity/SL เพื่อไม่ให้แยก
protection ออกจาก basket authority; UI ไม่แสดงปุ่มแก้ไขรายไม้และแสดงว่าใช้สูตรร่วม
บังคับที่ admission และ engine อีกครั้งเพื่อครอบคลุมคำขอค้าง/old clients
manual SELL/FIFO และ explicit CANCEL ใช้กฎ F-17 เดิม ไม่ restore protection อัตโนมัติ
manual/F-20 allocations ที่ไม่ใช่ F-21 ยังคง REPLACE เดิม

### Owner UI amendment — 2026-11-21

Owner requested that accepting a bot start keep the main Paper Spot screen with a stop-bot button, replacing the expanded run detail and disabled configuration form. Preserve a truthful pending/running/paused/stopped status, safety errors and the existing stop request/retry behavior. Configuration remains available before start and when a replacement run is eligible. This presentation change was directly requested by the owner.

### Owner amendment — remove replacement checkbox, 2026-11-21

Owner requested removal of the replacement confirmation checkbox. Pressing Start explicitly requests the new run using the current server-provided replacement proof. Server flatness, order reconciliation, stop authorization and stale-proof rejection remain required.

### Owner UI removal — 2026-11-21

Approved by owner's explicit request to remove the screenshot's “กราฟแท่งเทียน”
menu and its code. Retire the standalone chart page and dedicated placeholders,
retaining the shared chart in Paper/Live trading. Authenticated default/retired chart
URLs resolve to Paper trade; keep authentication, admin authorization and trading rules.
