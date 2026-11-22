# F-21 — Desktop strategy reference review

สถานะ: **Reference reviewed — owner decisions reconciled in requirements; ไม่ใช่การอนุมัติ requirements**
วันที่: 2026-11-20 (Asia/Bangkok)

เจ้าของให้ใช้ `rsi_step_grid` และให้อ่าน `yukasung/tiewtrade-desktop`
ตรวจเอกสาร สูตร implementation และ unit test source ที่เกี่ยวข้องบน main commit
`9fb12599bd3dad00b2c363c03a6ca1ed113e69e0` โดยไม่รันระบบ/เทสต์ต้นทาง
รายการไฟล์พร้อม pinned links/blob hashes อยู่ใน
[source inventory](references/desktop-source-inventory.md)
ไฟล์ strategy/preset ใน repo ตรงกับสองไฟล์ที่เจ้าของให้มาก่อนหน้า

## กฎที่พบเพิ่ม

อ้าง `docs/strategies/rsi-step-grid-v1.md`, `trading/basket.py`,
`application/paper_candle_transition.py` และ `application/paper_spot_session.py`
ใน inventory กฎนี้เป็นข้อเท็จจริงของต้นทาง รอรวมเป็น requirements ของ F-21:

- Preset ยังคง RSI14, reset <30, entry >50, ATR14 และ TP multiplier 3 แบบ
  canonical; LONG เท่านั้น ไม่มี strategy SL; entry signal ใช้ completed candle
- หากไม่มี pending และ RSI <30 ให้แทน reset close ด้วย close ล่าสุด แม้ gate
  ไม่เปิด; FIRE ต้องครบเงื่อนไขใน SR-04 และ gate อนุญาต; filled ล้าง reset,
  rejected คง reset; ไม่ใช่ grid ที่ซื้อทุกระยะราคาหรือทบเงินตามชื่อ
- มี Basket ครอบหลาย Entry Group: ไม้ใหม่ราคาต่ำกว่าราคาเฉลี่ยถ่วงจำนวนของ
  **กลุ่มที่เปิดล่าสุด** จะเข้ากลุ่มนั้น มิฉะนั้นสร้างกลุ่มใหม่ รวมกรณีราคาเท่ากัน
  group identity กำหนดเมื่อ fill และไม่ย้ายไม้ไปมา
- Long group average = sum(price × quantity) / sum(quantity) ของไม้ที่ยังเปิด
  TP ใหม่ = floor-to-tick(group average + 3 × ATR ของไม้ล่าสุดในกลุ่ม)
  และ TP ที่ถือจริง = min(TP ใหม่, TP เดิม) เมื่อมี TP เดิม
- ATR ของไม้ถูกส่งมากับ signal intent ไม่ใช่ ATR ปัจจุบันของตลาด;
  เมื่อไม้ล่าสุดออก ใช้ ATR ของไม้ที่ยังเปิดล่าสุดตาม (filled_at, entry_number)
  คำนวณ TP ใหม่ภายใต้กฎเลื่อนเข้าใกล้เท่านั้น กองว่างจึงลบ TP
- TP แยกแต่ละกลุ่ม ขายไม้ในกลุ่มที่ถึงเป้าพร้อมกัน ไม่ปิดกลุ่มอื่น;
  กลุ่มที่ใกล้ถึงเป้าก่อนถูกประมวลผลก่อน ค่า TP ระดับ Basket ใช้แสดงผล
- `max_entries` เป็นเพดานไม้ที่ **ยังเปิด** ไม่ใช่ lifetime fill count;
  ขายแล้วคืนช่อง แต่ entry number/group sequence เดินหน้าภายใน Basket
  การปิดไม้ไม่คืนเลขเดิม กำไรรายไม้คิดจาก fill จริงของไม้นั้น
- เมื่อทุกไม้ปิด Basket จบและ reset pair/cooldown; การปิดบางไม้ไม่ปิด Basket
  และไม่บันทึกกำไรสะสมซ้ำเป็น fill ใหม่เมื่อออกใบสรุป
- ต้นทางไม่สร้าง entry signal ในแท่งที่เพิ่งมี exit; backfill ต้องไม่เปิดไม้
  จากราคาในอดีต และต้องคืน pending เก่าแทนการเลื่อนไป fill ที่แท่งสดภายหลัง
  การ port ต้องพิสูจน์จาก F-20 input/feedback contracts ไม่สร้าง historical fill
- UI/Session config ปัจจุบันให้เลือกจำนวนไม้เลขคู่ 2–20 default10,
  timeframe default5m และ cooldown Off หรือ1–30วัน default30;
  capital per entry ไม่มี default เป็นจำนวนเงินที่ผู้ใช้ต้องกรอก
  หลังเริ่ม Session ค่าตั้งถูกตรึง การเปลี่ยน canonical preset ต้องใช้รุ่นใหม่

## ข้อขัดแย้งภายในต้นทาง — ไม่เลือกข้างแทนเจ้าของ

| รหัส | หลักฐานแต่ละฝั่ง | ผลต่อ F-21 |
|---|---|---|
| D-01 Capital | `trading/capital.py`, `session_config.py`, UI และ `test_capital.py`: ผู้ใช้กรอกเงินต่อไม้, entry notional เท่าจำนวนนั้น, total = เงินต่อไม้ × max_entries ไม่มี reserve; แต่ PRODUCT §7.1: เงินรวม ÷ max_entries; docs-site/capital-allocation: เงินรวม × trading ratio (default80%) ÷ max_entries | ต้องเลือกความหมายช่องงบ/Amount ก่อนทำสูตรเงินและ UI; ห้ามแปลงค่าหน้าจอเดิมเงียบ ๆ |
| D-02 Cooldown | `cooldown_policy.py`, `entry_pair.py`, UI, PRODUCT §6 และ unit tests: Off/1–30วัน default30 ปลดเองเมื่อครบเวลาจาก fill ที่ทำให้คู่ครบ; ยกเลิกได้เฉพาะคู่ปัจจุบัน และขายสมาชิกของคู่ล่าสุดแล้วปลดทันที แต่ strategy doc §8 บอกไม่หมดอายุเอง และ docs-site/entry-pair-cooldown ใช้เดือน UTC | ต้องเลือกกฎ timing/waiver และขอบเขต UI ก่อนอนุมัติ; ไม่ตีความ Cancel Cooldown ว่าข้าม F-18/F-19 gate |
| D-03 Warm-up | preset_rules กำหนด250แท่ง แต่ strategy doc §1.5 กล่าวว่า update() คืน None ก่อน250 ขณะที่ WilderIndicators.update ไม่มี250 gate และให้ค่าหลัง seed พร้อม; startup caller จึงเป็นอีก contract ที่ต้องพิสูจน์ | ไม่ใช้คำกล่าวในเอกสารเป็น proof ว่าทุก path บังคับ250; ต้องระบุ readiness gate ของ F-21 |
| D-04 Timeframe | market_data/config และ UI มี1m แต่ PRODUCT §4.1 list ไม่มี1m ขณะที่ PRODUCT §3 list มี1m | ต้องกำหนด subset ที่ต้องการใน F-21 และเทียบ catalog/timeframes ปัจจุบัน |

รายละเอียด D-02 จาก code: ทุกสอง lifetime fills ทำให้คู่ครบ ใช้ market time
ของ fill ที่ครบคู่เริ่มนับวัน; max_entries ตรวจจาก open count ก่อน gate อื่น
การขายสมาชิกของคู่ก่อนหน้าไม่ปลด cooldown ของคู่ล่าสุดที่ยังถือครบ
waiver ใช้ได้เฉพาะ completed pair ที่กำลังบล็อก ไม่ส่งผลถึงคู่ถัดไป
เป็นหลักฐาน code behavior ไม่ใช่คำตัดสินให้เลือก code เหนือ spec

## ข้อแตกต่างกับ TiewTrade Web ที่ต้องอนุมัติขอบเขต port

| รหัส | ต้นทาง | Contract ปัจจุบัน / จุดที่ต้องตัดสิน |
|---|---|---|
| W-01 Execution | Entry fill ที่ open ของแท่งถัดไป ปัดราคาเข้าขึ้น/ปริมาณลง; TP fill ที่เป้าจากช่วง high/low ไม่คิด fee/slippage ไม่มี partial fill model | F-15 ใช้ matching/liquidity/fee จริงตามโมเดลที่อนุมัติ; F-17 TP trigger สร้าง MARKET exit ไม่รับประกัน fill ที่ราคา TP ห้ามคัดลอก desktop fills หรือยกเว้น fee เพื่อให้ replay เท่ากัน |
| W-02 Indicators | Desktop ATR seed รวม high−low ของแท่งแรกแล้วครบ14TR; ใช้ Decimal context และ250 warm-up floor | F-11 ATR เริ่มแท่งที่สองครบ14TRที่แท่ง15 พร้อม central seed/provenance และ Money/Scalar arithmetic; สูตรที่ seed/precision ต่างกันทำให้สัญญาณ/TP ต่างกันได้แม้ใช้ period14เหมือนกัน ห้ามสร้าง indicator คู่ขนานเอง |
| W-03 Inventory/protection | Desktop มี Entry Group และ TP ที่ถ่วงจากหลายไม้ พร้อม target ที่เลื่อนเข้าใกล้อย่างเดียว; เก็บ tick จาก fill แรก และไม่มี strategy SL | ต้องกำหนดการเชื่อมกลุ่มกับ F-17 protection allocations/partial fills และเงื่อนไขตั้ง TP เหนือราคาปัจจุบัน; เมื่อ target ถูกข้ามหรือไม่พร้อมยังใช้ safety policy เดิม ไม่เลื่อนเป้าหรือข้าม gate เอง |
| W-04 Config/lifecycle | Desktop เปลี่ยน Session อาจยืนยันปิด inventory เดิมแล้วเริ่มใหม่; symbols BTC/ETH/BNB และมี Futures | F-20 run ใหม่ต้องไม่มี position/order ที่ระบบดูแล; F-21 ไม่ปิด inventory เพื่อเปลี่ยน config และไม่เพิ่ม BNB/Futures/Live โดยอ้างต้นทาง ต้องใช้ catalog และ scope ของ Web ที่อนุมัติ |

ข้อเสนอสำหรับเจ้าของพิจารณา: นำ signal/reset, grouping/TP และ session parameters
ของกลยุทธ์มาใช้ โดยคง Money/Quantity, F-11 backend indicators, F-15 matching/fees,
F-17 protections และ F-20 lifecycle ของ Web; ไม่รับรอง numerical replay parity
กับ Desktop และไม่ยกเลิกด่าน safety/production activation ใด
รายละเอียด partial fill/group protection ต้องชัดใน requirements ก่อน plan

## จุดหยุด

การอ่าน source อ้างอิงทำแล้ว ไม่ได้ implement หรือรันทดสอบระบบ
เจ้าของตัดสินต่อมาในวันเดียวกัน: เงินต่อไม้, ไม่มี cooldown, ใช้ indicator/matching/
fee/protection เดิมของ Web, BTC/ETH และ timeframe Web พร้อม warm-upอย่างน้อย250แท่ง
รวมกับตัวกรอง EMA/RSI แบบ AND ที่ยังรอ reset RSI<30 ลง requirements แล้ว
รายการข้อขัดแย้งด้านบนคงเป็นผลอ่านต้นทาง ไม่ใช่ blocker ที่ให้ถามคำตอบเดิมซ้ำ
รออนุมัติ requirements ทั้งฉบับ ก่อนจัดทำ plan/validation ตาม AGENTS.md
