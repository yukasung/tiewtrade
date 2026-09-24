# TiewTrade — Calculation Spec

| Field | Value |
|---|---|
| Status | **v0.3** — C-07 ถึง C-11 Decided (2026-09-22); ข้อที่ระบุ **Verify** ต้องยืนยันด้วย golden test กับ Binance |
| Date | 2026-09-22 |
| Based on | [MVP Requirements v0.22](../requirements/mvp.md), [Architecture v0.2](../architecture/architecture.md) |
| Scope | สูตรที่ Trading Core (`tiewtrade_core`) ต้อง implement: Futures (USDⓈ-M, One-way, Single-Asset), Spot, Paper Fill Model, Funding Fee, Open Notional, Entitlement checks, golden test |
| Out of scope | Hedge Mode, Multi-Assets Mode, Portfolio Margin, Spot Margin (D-03, D-10) |

> **หลักการ**
> - ทุกสูตรเป็น deterministic code ใช้ `Decimal` ไม่ใช้ float (P-07, FR-MRG-08)
> - เมื่อข้อมูลเข้าเหมือนกัน ผลต้องเท่ากับ Binance ยกเว้นการปัดเศษ (FR-MRG-07)
> - **Live:** ค่าที่แสดงอ้างอิง Binance ค่าที่คำนวณเองใช้ทำ pre-trade estimate และ Risk check (FR-MRG-06) **Paper:** ค่าที่คำนวณเองคือค่าจริงของ Portfolio
> - **Verify** = สูตรที่อ่านจากเอกสาร Binance แต่ยังไม่ได้ยืนยันกับตัวเลขจริง ห้ามถือว่าถูกจนกว่า golden test ผ่าน

---

## 1. Notation

| สัญลักษณ์ | ความหมาย |
|---|---|
| `Q` | Position size แบบมีเครื่องหมาย: `+` Long, `−` Short (หน่วย Base Asset) |
| `|Q|` | ขนาด Position แบบไม่มีเครื่องหมาย |
| `side` | `+1` Long, `−1` Short (= sign ของ `Q`) |
| `EP` | Entry Price (ราคาเฉลี่ยของ Position) |
| `MP` | Mark Price |
| `LP` | Last Price |
| `L` | Leverage ของ Symbol |
| `MMR`, `cum` | Maintenance Margin Rate และ Maintenance Amount จาก Leverage Bracket |
| `WB` | Wallet Balance (cross: cross wallet balance, isolated: isolated wallet ของ Position) |
| `f_m`, `f_t` | Maker / Taker fee rate |
| `s` | Paper slippage rate (ค่าเริ่มต้น 0.02%, FR-ORD-07) |

---

## 2. USDⓈ-M Futures (One-way, Single-Asset USDT)

### 2.1 Notional และ Unrealized PnL
```
Notional        = |Q| × MP
Unrealized PnL  = Q × (MP − EP)            # Long: |Q|(MP−EP), Short: |Q|(EP−MP)
ROE             = Unrealized PnL / Position Initial Margin
```

### 2.2 Initial Margin
```
Position Initial Margin = |Q| × MP / L                                  # Verify: Binance แสดงด้วย MP
Order Initial Margin    = Assuming Price × Order Qty / L
Order Cost              = Order Initial Margin + Open Loss
Open Loss               = Order Qty × | min(0, dir × (MP − Order Price)) |   # dir = +1 buy, −1 sell
```

**Assuming Price** (จากเอกสาร Binance, **Verify** — ตัวเลข 0.15% ต่างจากที่เคยเห็นในเอกสารรุ่นเก่า):
| Order | Assuming Price |
|---|---|
| Limit Buy | Order Price |
| Limit Sell | `max(LP × (1 + 0.15%), MP, Order Price)` |
| Market (Buy / Sell) | `LP × (1 + 0.15%)` |

**Margin requirement รวม order ค้าง (One-way, Binance):**
```
Margin Requirement(symbol) = max(|PosNotional + BidOrderValue|, |PosNotional − AskOrderValue|) / L
PosNotional   = Q × MP     (มีเครื่องหมาย)
BidOrderValue = Σ (qty × limit price) ของ Buy order ค้าง
AskOrderValue = Σ (qty × limit price) ของ Sell order ค้าง
```

### 2.3 Maintenance Margin และ Leverage Bracket
```
Maintenance Margin(position) = Notional × MMR − cum
```
- `MMR`, `cum` และ max leverage เลือกจาก **Leverage Bracket ของ Symbol ตาม Notional** (ดึงจาก Binance ต่อ Symbol ต่อ Venue และเก็บเป็นข้อมูลอ้างอิงที่มีเวอร์ชัน)
- ตัวอย่างจากเอกสาร Binance: `3,500,032.458 × 2.50% − 16,300 = 71,200.81144`
- Leverage ที่ตั้งได้ต้องไม่เกิน max leverage ของ bracket และไม่เกินค่าของ Plan (FR-PLN-06)

### 2.4 Margin Balance และ Margin Ratio
```
Cross:
  Margin Balance = cross WB + Σ Unrealized PnL (ทุก cross position)
  MM             = Σ Maintenance Margin (ทุก cross position)
Isolated (ต่อ Position):
  Margin Balance = isolated WB + Unrealized PnL
  MM             = Maintenance Margin ของ Position

เงื่อนไข Liquidation (authoritative):   MM > 0  และ  Margin Balance ≤ MM
```
- **ใช้เงื่อนไขนี้ตัดสิน Liquidation เท่านั้น** ไม่ใช้ Margin Ratio เพราะเมื่อ Margin Balance เป็น 0 หรือติดลบ อัตราส่วนหารด้วยศูนย์หรือติดลบ ทำให้บัญชีที่ล้มละลายแล้วหลุดจากเงื่อนไข
- ขอบเขต `≤` (เท่ากันก็ถูก Liquidate) ตาม "Margin Ratio ถึง 100%" ของ Binance (**Verify** กรณีเท่ากันพอดี)

**Margin Ratio สำหรับแสดงผลและแจ้งเตือนเท่านั้น:**
```
ถ้า Margin Balance > 0:  Margin Ratio = MM / Margin Balance
ถ้า Margin Balance ≤ 0 และ MM > 0:  แสดงเป็น "≥ 100%" (อยู่ในเงื่อนไข Liquidation แล้ว)
ถ้า MM = 0:  ไม่มี Position ไม่แสดง
```
- เตือนก่อนถูก Liquidate เมื่อ Margin Ratio ≥ 80% (ค่าเริ่มต้น FR-NTF-05)

### 2.5 Liquidation Price (One-way)
สูตรของ Binance ลดรูปสำหรับ One-way Mode (**Verify** — เอกสาร Binance แสดงสูตรเป็นรูปภาพ):
```
LP_liq = (WB − TMM₁ + UPNL₁ + cum − side × |Q| × EP) / (|Q| × MMR − side × |Q|)
```
| ตัวแปร | Cross | Isolated |
|---|---|---|
| `WB` | cross wallet balance | isolated wallet ของ Position |
| `TMM₁` | Maintenance Margin ของ Position อื่นทั้งหมด (ไม่รวม Symbol นี้) | 0 |
| `UPNL₁` | Unrealized PnL ของ Position อื่นทั้งหมด | 0 |
| `MMR`, `cum` | ของ bracket ที่ Notional ณ `LP_liq` ตกอยู่ | เหมือนกัน |

**การเลือก bracket (iterative):**
1. เริ่มด้วย bracket ของ Notional ปัจจุบัน
2. คำนวณ `LP_liq` แล้วหา bracket ของ `|Q| × LP_liq`
3. ถ้าไม่ตรงกับ bracket ที่ใช้ ให้คำนวณใหม่ด้วย bracket นั้น ทำซ้ำจนคงที่ (จำนวนรอบจำกัด; ถ้าวน ให้เลือกผลที่ปลอดภัยกว่า คือใกล้ราคาปัจจุบันกว่า)
4. ถ้า `LP_liq ≤ 0` (Long ที่ margin พอเสมอ) แสดงว่าไม่มี Liquidation Price

### 2.6 Entry Price เมื่อเพิ่ม / ลด / กลับทิศ Position
```
เพิ่มทิศเดิม:   EP_new = (|Q| × EP + q × fill) / (|Q| + q)
ลด Position:    EP ไม่เปลี่ยน; Realized PnL = q × (fill − EP) × side
ปิดทั้งหมด:     Q = 0, EP ไม่มีค่า
กลับทิศ:        ปิดส่วนเดิมทั้งหมดที่ fill ก่อน (Realized PnL) แล้วเปิดส่วนที่เหลือด้วย EP = fill
```
- Realized PnL ไม่รวม Fee และ Funding Fee ซึ่งบันทึกใน ledger แยกรายการ (Glossary)

### 2.7 Frozen Margin และ Available Balance (Cross)
ใช้ **Margin Requirement แบบรวมต่อ Symbol ของ §2.2** เป็นตัวเดียวที่กำหนดเงินที่ถูกกัน ไม่บวก Initial Margin ของ Position กับ Order Cost ทุกตัวแยกกัน (ไม่เช่นนั้น Order ที่ปิด Position จะถูกกันเงินซ้ำ)
```
MR(symbol)        = max(|Q×MP + BidValue|, |Q×MP − AskValue|) / L
                    BidValue / AskValue = Σ qty × Assuming Price ของ Order ค้างฝั่งนั้น (§2.2)
Frozen Margin     = Σ_symbol MR(symbol) + Σ Open Loss ของ Order ค้าง
Available Balance = max(0, cross WB + UPnL_usable − Frozen Margin)
```
**Margin ที่ Order ใหม่ต้องใช้ (incremental):**
```
Order Margin = MR_after(symbol) − MR_before(symbol) + Open Loss(order ใหม่)
ส่ง Order ได้เมื่อ Order Margin ≤ Available Balance
```
**ตัวอย่างตรวจสอบ:** Long 1 unit, MP = LP = 100, L = 10, WB = 20 และมี Sell 1 @ 100 ค้างเพื่อปิด → Assuming Price ของ Sell = `max(100 × 1.0015, 100, 100) = 100.15` → `MR = max(|100 + 0|, |100 − 100.15|) / 10 = 10`; MR ก่อนมี Order นี้ = `100 / 10 = 10` → Order Margin = `10 − 10 + 0 = 0` เงินถูกกันรวมแค่ 10 ไม่ใช่ 20

**`UPnL_usable`** (**Verify**): Unrealized PnL ที่เป็นกำไรใช้เป็น margin เปิด Position ใหม่ได้หรือไม่ ก่อนยืนยันกับ Binance ให้ใช้แบบระมัดระวัง `UPnL_usable = min(0, Σ Unrealized PnL)` (**Proposed**)

**Assuming Price ในสูตรรวม** (**Verify**): เอกสาร Binance เรื่อง margin requirement ใช้ limit price แต่เรื่องต้นทุนการเปิด Order ใช้ Assuming Price ของ §2.2 ให้ใช้ Assuming Price (ค่าที่ระมัดระวังกว่า) จนกว่า golden test จะยืนยัน

### 2.8 Fee
```
Fee = fill qty × fill price × (f_m หรือ f_t)          # หน่วย USDT, หักจาก WB
```
- Maker / Taker ตาม Paper Fill Model (§4) หรือตามที่ Binance รายงาน (Live)

### 2.9 Funding Fee
```
Funding Payment = Q × MP(ณ funding time) × Funding Rate
WB -= Funding Payment        # rate > 0: Long จ่าย Short รับ
```
- คิดเฉพาะ Position ที่เปิดอยู่ ณ เวลา funding (**Verify** รูปแบบเวลาและว่าใช้ Mark Price)
- **Paper แยกเป็น 2 ขั้น (idempotent ทั้งคู่, NFR-22):**
  1. **Funding job ส่วนกลาง:** บันทึก Funding Rate และ Mark Price ของรอบ 1 ครั้ง key = `(Venue, Symbol, funding time)`
  2. **การลงบัญชีต่อ Portfolio:** engine เจ้าของ Portfolio ลง ledger ของตัวเอง key = `(Portfolio, Venue, Symbol, funding time)` ถ้า key นี้มีอยู่แล้วให้ข้าม
- หลังลง Funding ต้องตรวจเงื่อนไข Liquidation ใหม่ทันที (§4.4)

---

## 3. Spot

### 3.1 Position ของ Spot
- Position ของ Spot คือ **Base Asset ที่ถือ** ใน Wallet ของ Portfolio (Long only, D-10)
- **ต้นทุนเฉลี่ยแบบถ่วงน้ำหนัก ไม่รวม Fee (fee-exclusive Weighted Average Cost)** (**Decided C-07**) เพื่อให้สอดคล้องกับ Glossary ที่ Realized PnL ไม่รวม Fee และไม่นับ Fee ซ้ำ:
```
ซื้อ q ที่ fill, fee rate f (หักเป็น Base Asset):
   q_net       = q × (1 − f)
   AvgCost_new = (H × AvgCost + q_net × fill) / (H + q_net)
   Fee (ledger) = q × f × fill                       # มูลค่า USDT ของ Base ที่ถูกหัก
ขาย q ที่ fill (หัก Fee เป็น USDT):
   Realized PnL = q × (fill − AvgCost)               # gross ไม่รวม Fee
   Fee (ledger) = q × fill × f
   AvgCost ไม่เปลี่ยน
Net PnL = Σ Realized PnL − Σ Fee
H = Base Asset ที่ถือก่อนหน้า
```
**ตัวอย่างตรวจสอบ:** ซื้อ 1 @ 100, f = 1% → ได้ 0.99, AvgCost = 100, Fee = 1; ขาย 0.99 @ 100 (f = 0 เพื่อให้เห็นชัด) → Realized PnL = 0, Net PnL = −1 ตรงกับเงินที่หายจริง ไม่มีการนับ Fee ซ้ำ

### 3.2 Fee ของ Spot (**Verify**)
- ไม่ใช้ BNB (D-05): Fee หักจาก **asset ที่ได้รับ**
  - ซื้อ: ได้ Base Asset = `q × (1 − f)`
  - ขาย: ได้ USDT = `q × fill × (1 − f)`

### 3.3 มูลค่าและ PnL
```
Holding Value   = H × LP
Unrealized PnL  = H × (LP − AvgCost)
Equity (Spot)   = USDT balance + Holding Value ของทุก Base Asset
```
- เงินที่ถูกจองใน Order ค้าง (locked) ใช้ซ้ำไม่ได้: Buy จอง USDT = `qty × limit price` (Market Buy ประมาณด้วย `qty × ask × (1 + s)`), Sell จอง Base Asset

---

## 4. Paper Fill Model (D-05)

### 4.1 Market Order
```
Buy  fill = round_up_tick(BestAsk × (1 + s))
Sell fill = round_down_tick(BestBid × (1 − s))
Fee = Taker
```
- ปัดราคาไปทางที่เสียเปรียบผู้ใช้ เพื่อไม่ให้ผลดีเกินจริง (**Decided C-11**)

### 4.2 Limit Order
| สถานะ | กติกา |
|---|---|
| ตอนส่ง: Buy `limit ≥ BestAsk` หรือ Sell `limit ≤ BestBid` (marketable) | fill ทันทีแบบ Taker ที่ `min(limit, Buy fill ของ §4.1)` สำหรับ Buy / `max(limit, Sell fill)` สำหรับ Sell |
| ค้างอยู่: Buy | fill เมื่อ `LP < limit` (**ทะลุ** ไม่ใช่แตะ) ที่ราคา `limit`, Maker |
| ค้างอยู่: Sell | fill เมื่อ `LP > limit` ที่ราคา `limit`, Maker |
- fill เต็มจำนวนครั้งเดียว (FR-ORD-09)

### 4.3 TP / SL
| Position | SL ทำงานเมื่อ | TP ทำงานเมื่อ |
|---|---|---|
| Long | `LP ≤ SL` | `LP ≥ TP` |
| Short | `LP ≥ SL` | `LP ≤ TP` |
- ทำงานแล้ว fill แบบ Market Order (§4.1) ด้วย reduce-only และยกเลิกขาที่เหลือของ Bracket (R-16)

### 4.4 Liquidation (Paper แบบลดรูป, **Decided C-09**)
**เมื่อไรตรวจ:** หลัง**ทุก event ที่กระทบ margin** ไม่ใช่แค่ Mark Price: Mark Price อัปเดต, Fill, Fee, Funding, Transfer ออก, เปลี่ยน Leverage และทุก event ใน replay (§4.5) โดยใช้เงื่อนไข authoritative ของ §2.4 (`Margin Balance ≤ MM`) ไม่ใช้การเทียบกับ `LP_liq` เพราะ Liquidation อาจเกิดจาก Funding หรือ Fee โดยราคาไม่ขยับ (`LP_liq` ใช้แสดงผลและประมาณการเท่านั้น)

**เมื่อเงื่อนไขเป็นจริง:**
| ขั้น | Isolated (ต่อ Position) | Cross (ทั้งกลุ่ม cross ของ Portfolio) |
|---|---|---|
| 1. ยกเลิก Order ค้าง | Order ของ Symbol นั้น | ทุก Order ของ Portfolio (ตาม Binance) |
| 2. Position ที่ถูกปิด | Position นั้น | **ทุก cross position พร้อมกัน** |
| 3. ราคาปิด | Mark Price ณ event ที่ทำให้เงื่อนไขเป็นจริง | Mark Price ของแต่ละ Symbol ณ event เดียวกัน (snapshot เดียว) |
| 4. Clearance Fee | `Notional × clearance rate` | รวมของทุก Position ที่ปิด |
| 5. ผลต่อเงิน | isolated wallet ที่เหลือหลังปิดถูกริบทั้งหมด (**Verify**) | cross WB = `max(0, ผลลัพธ์)`; ส่วนที่ติดลบถือว่า Insurance Fund รับไป ไม่หักผู้ใช้ |

- **ผลไม่ขึ้นกับลำดับการประมวลผล** เพราะ cross ปิดทุก Position พร้อมกันด้วย snapshot ราคาเดียว และคำนวณ fee จาก snapshot เดียวกัน
- clearance rate ต่อ Symbol ต้อง **Verify** และเก็บเป็น config
- ไม่จำลอง Insurance Fund, ADL และ Smart Liquidation แบบทยอยปิด (FR-MRG-05) — ผลจึงแย่กว่า Binance ที่อาจปิดแค่บางส่วน ซึ่งสอดคล้องกับหลัก "ไม่ดูดีเกินจริง" (D-05)
- บันทึก ledger ประเภท Liquidation และแจ้งเตือน (FR-NTF-04)

### 4.5 จำลองย้อนหลังด้วย Candle (NFR-15)
**Order ที่มีสิทธิ์ fill ใน replay:** เฉพาะ Order ที่**ลดหรือปิด** Position (TP, SL, reduce-only Limit) และ Liquidation เท่านั้น
- Order ที่เปิดหรือเพิ่ม Position (entry Limit) **ไม่ fill ใน replay** และยังค้างอยู่หลัง replay เพื่อให้ตรงกับกติกา "ไม่เปิด Position ใหม่ย้อนหลัง"
- ไม่เรียก Strategy

**ลำดับภายในแท่ง (SL มาก่อนเสมอ):** ไม่ใช้เส้นทางราคาแบบ Open → Low → High → Close เพื่อตัดสินลำดับ แต่ใช้กติกาต่อ Position ดังนี้
1. หา event ฝั่ง**ขาดทุน**ที่ถูกแตะภายในช่วง `[Low, High]` ของแท่ง: SL, reduce-only Limit ฝั่งขาดทุน, Liquidation (ประมาณด้วย Low สำหรับ Long / High สำหรับ Short แทน Mark Price เพราะไม่มี Mark Price ใน Candle — **Decided C-09**)
2. ถ้ามี ให้ทำ event ฝั่งขาดทุน**ที่ราคาใกล้ Open ที่สุดก่อน** (Long: ราคาสูงสุดก่อน, Short: ราคาต่ำสุดก่อน) แล้วตรวจ Liquidation ใหม่
3. event ฝั่ง**กำไร** (TP, reduce-only Limit ฝั่งกำไร) ทำได้**เฉพาะเมื่อแท่งนั้นไม่มี event ฝั่งขาดทุนถูกแตะ** — แท่งที่แตะทั้ง TP และ SL จึงเป็น SL เสมอ

**ราคา fill ใน replay** (ไม่มี bid/ask ย้อนหลัง จึงแทน §4.1 ด้วยราคา trigger + slippage ไปทางเสียเปรียบ):
| Event | Long | Short |
|---|---|---|
| SL / Liquidation (ขาดทุน) | `min(trigger, Open) × (1 − s)` — ถ้าเปิดแท่งทะลุไปแล้ว (gap) ใช้ Open | `max(trigger, Open) × (1 + s)` |
| TP (Market เมื่อแตะ) | `TP × (1 − s)` — ไม่ให้ประโยชน์จาก gap | `TP × (1 + s)` |
| reduce-only Limit | ราคา Limit, Maker (ต้องทะลุตาม §4.2) | ราคา Limit, Maker |
- ปัดราคาตาม tickSize ไปทางเสียเปรียบผู้ใช้; Liquidation ใช้กติกา §4.4 กับราคาข้างบน
- **Funding ระหว่างช่วงที่ล่ม:** ลงตามรอบ funding ที่อยู่ในช่วง ด้วย Funding Rate ย้อนหลังจาก Binance (public) ตามลำดับเวลาเทียบกับ Candle และตรวจ Liquidation หลังทุกรอบ

---

## 5. Open Notional และ Entitlement Checks (D-11)

### 5.1 Open Notional ของ Workspace (FR-PLN-04)
```
Open Notional(mode) = Σ_futures |Q| × MP  +  Σ_spot H × LP        # ทุก Portfolio ใน Workspace ของ Trading Mode นั้น
```

### 5.2 ตรวจ Order ที่เปิด / เพิ่ม Position (FR-PLN-05, **Decided C-08**)
นับ Order ค้างด้วยเพื่อกันการวาง Limit จำนวนมากเกินวงเงิน:
```
Futures (ต่อ Symbol):  Projected = max(|Q×MP + Bid|, |Q×MP − Ask|)   # หลังรวม Order ใหม่ (สูตรเดียวกับ §2.2)
Spot:                  Projected = H × LP + Σ Buy order ค้าง × limit
Workspace Projected    = Σ Projected ทุก Symbol ทุก Portfolio
ปฏิเสธถ้า Workspace Projected > วงเงิน และ Order นี้ทำให้ Projected เพิ่มขึ้น
```
- Order ที่ลดหรือปิด Position ผ่านเสมอ

### 5.3 Leverage (FR-PLN-06)
```
Effective Max Leverage = min(Plan Max Leverage, Bracket Max Leverage ของ Notional ที่จะเกิด)
```
ตรวจตอนตั้ง Leverage และตอนส่ง Order ที่เปิด / เพิ่ม Position

---

## 6. Rounding & Precision

| ค่า | กติกา |
|---|---|
| การคำนวณภายใน | `Decimal` ความละเอียดเต็ม ไม่ปัดระหว่างทาง |
| Order quantity | ปัดลงตาม `stepSize`; ปฏิเสธถ้าต่ำกว่า `minQty` หรือ Notional ต่ำกว่า `minNotional` |
| Order price | ปัดตาม `tickSize` (Paper fill ปัดไปทางเสียเปรียบผู้ใช้ §4.1) |
| Fee / PnL / Balance | เก็บด้วยความละเอียดของ asset (**Verify** จำนวนทศนิยมของ USDT ที่ Binance ใช้) |
| การแสดงผล | ปัดเฉพาะตอนแสดง ไม่กระทบค่าที่เก็บ |

---

## 7. Golden Tests (FR-MRG-07)

### 7.1 แหล่งข้อมูล
บันทึก snapshot จากบัญชี Binance (Testnet และบัญชีจริงจำนวนน้อยของเจ้าของระบบ, FR-LIVE-16..18):
- Leverage Bracket ของ Symbol
- Account / balance: wallet balance, margin balance, maintenance margin รวม
- Position risk: size, entry price, mark price, unrealized PnL, notional, isolated wallet, leverage, **liquidation price**
- Fills พร้อม fee และ funding history

### 7.2 รูปแบบ test case
แต่ละ case เป็นไฟล์ JSON: `inputs` (balances, positions, brackets, prices) → `expected` (ค่าที่ Binance รายงาน) + `tolerance` (ปัดเศษตาม tick / precision เท่านั้น)

### 7.3 ชุด case ขั้นต่ำ
| กลุ่ม | Case |
|---|---|
| Isolated | Long / Short, leverage ต่ำ / สูง, bracket แรก / bracket สูง |
| Cross | 1 Position; หลาย Position ที่มีกำไรและขาดทุนปนกัน; Position ที่ Notional ข้าม bracket |
| Entry price | เพิ่ม, ลด, กลับทิศ |
| Fee / Funding | Maker, Taker, funding rate บวก / ลบ |
| Spot | ซื้อหลายครั้งแล้วขายบางส่วน (Average Cost, fee ใน asset ที่ได้รับ) |
| Available Balance | Order ปิด Position ไม่ถูกกันเงินซ้ำ (ตัวอย่าง §2.7), Order เพิ่ม Position ใช้ margin ส่วนเพิ่ม |
| Liquidation | Margin Balance = 0 และติดลบ, Liquidation จาก Funding / Fee โดยราคาไม่ขยับ, cross หลาย Position |
| Paper | Market / Limit / TP / SL / Liquidation / replay: แท่งเขียวและแดงที่แตะทั้ง TP และ SL (ต้องเป็น SL), gap เปิดแท่งทะลุ SL, entry Limit ไม่ fill ใน replay, Funding ระหว่างช่วงที่ล่ม |
| Funding | สอง Portfolio ถือ Symbol เดียวกัน ได้ Funding คนละรายการ; รัน job ซ้ำไม่ลงซ้ำ |
| Spot | ซื้อที่มี Fee เป็น Base แล้วขายทั้งหมด: Net PnL = −Fee (ตัวอย่าง §3.1) |
| Entitlement | เกินวงเงิน, Order ค้างทำให้เกินวงเงิน, ลด Position ขณะเกินวงเงิน, Leverage เกิน Plan |

### 7.4 Property-based tests
- ปิด Position ทั้งหมดแล้ว Unrealized PnL = 0 และ `WB_end − WB_start = ΣRealized PnL − ΣFee − ΣFunding + Σเงินเข้า − Σเงินออก` (FR-ACC-11)
- Ledger รวมแล้วเท่ากับ state เสมอ (ADR-0003)
- เพิ่มแล้วลด Position ขนาดเท่ากันที่ราคาเดิม: Realized PnL = 0 ก่อนหัก Fee
- **Liquidation Price สอดคล้องกับเงื่อนไข:** เมื่อแทนราคา `LP_liq` เข้าไป (Position อื่นคงที่) ต้องได้ `Margin Balance = MM` ภายในความคลาดเคลื่อนจากการปัดเศษ และ bracket ของ `|Q| × LP_liq` ต้องเป็น bracket เดียวกับที่ใช้คำนวณ
- **Isolated เท่านั้น** (Leverage > 1): Liquidation Price ของ Long ต่ำกว่า Entry Price และของ Short สูงกว่า Entry Price — ไม่ใช้กับ cross เพราะขาดทุนของ Position อื่นอาจดัน Liquidation Price ของ Long ขึ้นเหนือ Entry Price ได้ ทั้งที่ยังไม่ถูก Liquidate
- **Liquidation ไม่หลุดเงื่อนไข:** บัญชีที่ `Margin Balance ≤ 0` และมี Position ต้องถูก Liquidate เสมอ
- **ลำดับไม่มีผล:** ประมวลผล cross liquidation ด้วยลำดับ Symbol ต่างกันต้องได้ผลเท่ากัน

---

## 8. Open Items
| # | เรื่อง | สถานะ |
|---|---|---|
| C-01 | Assuming Price ของ Market Order (0.15%) และ Open Loss | Verify |
| C-02 | สูตร Liquidation Price ลดรูป One-way | Verify ด้วย golden test |
| C-03 | `UPnL_usable`: Unrealized PnL ที่เป็นกำไรใช้เปิด Position ใหม่ได้หรือไม่ (§2.7) | Verify; ก่อนยืนยันใช้ `min(0, ΣUPnL)` |
| C-04 | Funding: ใช้ Mark Price หรือไม่ และเวลาตัดรอบ | Verify |
| C-05 | Liquidation Clearance Fee rate ต่อ Symbol | Verify, เก็บเป็น config |
| C-06 | Spot fee หักจาก asset ที่ได้รับ และความละเอียดของ USDT | Verify |
| C-07 | Spot ใช้ Weighted Average Cost แบบไม่รวม Fee (§3.1) | ✅ Decided |
| C-08 | Open Notional นับ Order ค้างด้วยสูตรเดียวกับ margin requirement (§5.2) | ✅ Decided |
| C-09 | Paper Liquidation แบบลดรูป (cross ปิดทุก Position พร้อมกัน, ปิดที่ Mark Price ณ event, WB ไม่ติดลบ) และ replay ใช้ Low / High แทน Mark Price (§4.4, §4.5) | ✅ Decided |
| C-10 | การเพิ่ม / ลด margin ของ isolated Position | ✅ Decided: **ไม่อยู่ใน MVP** (Future) |
| C-11 | Paper fill ปัดราคาไปทางเสียเปรียบผู้ใช้ และราคา fill ใน replay (§4.5) | ✅ Decided |
| C-12 | Assuming Price ใช้ในสูตร Margin Requirement แบบรวม (§2.7) | Verify |
| C-13 | ขอบเขต Liquidation `Margin Balance ≤ MM` กรณีเท่ากันพอดี (§2.4) | Verify |
| C-14 | isolated wallet ที่เหลือหลัง Liquidation ถูกริบทั้งหมด (§4.4) | Verify |
| C-15 | ขอบเขต Paper slippage rate `s`: บังคับ `0 ≤ s < 1` (`s < 0` จะ fill ดีกว่าราคาตลาด ขัด D-05; `s ≥ 1` ทำให้ราคาขาย ≤ 0; `s = 0` อนุญาตตาม FR-ORD-07 ที่ระบุแค่ค่า default) | ✅ Decided |
| C-16 | Book ที่ `bid ≥ ask` (crossed หรือ locked): Trading Core รับไว้และคำนวณตามข้อมูลที่ได้ ไม่ตัดสินว่าข้อมูลดีหรือเสีย และเปิด predicate ให้ Paper adapter กรอง snapshot เอง | ✅ Decided |
| C-17 | เมื่อเงื่อนไข TP และ SL เป็นจริงพร้อมกันใน tick เดียว (bracket ตั้งผิดหรือราคา gap) ให้ **SL ชนะ** สอดคล้องกับ §4.5 และ D-05 (§4.3) | ✅ Decided |
| C-18 | Paper fill ปัด tick แล้วจึง cap ตามราคา Limit (ไม่ปัดซ้ำหลัง cap) และตรวจว่าราคาเป็นบวกเฉพาะราคาสุดท้าย ไม่ใช่ค่ากลางทางของ §4.2 | ✅ Decided |
| C-19 | **`ExecutionReport`**: รูปแบบผลลัพธ์ที่ venue คืนกลับมาต่อ 1 Order ใช้ร่วมกันทั้ง Paper และ Live (P-03/P-04) ฟิลด์: `client_order_id`, `kind` (`ACCEPTED`/`REJECTED`/`FILLED`/`CANCELED`/`EXPIRED`), และเมื่อ `FILLED` ต้องมี `quantity`, `price`, `liquidity` ครบ · **ไม่มี timestamp** เพราะเวลามากับ event ที่ทำให้เกิด report และ core ไม่อ่านนาฬิกา (ADR-0001) | ✅ Decided |
| C-20 | **`PaperExecutionAdapter` ไม่เก็บ Order เอง**: engine เป็นเจ้าของ Order ที่ยังเปิดอยู่ (ตาราง `orders`, data-model §6.5) และส่งกลับเข้ามาเมื่อราคาขยับ การเก็บสำเนาใน adapter จะเป็นแหล่งความจริงที่สอง และหายเมื่อ restart ซึ่ง paper replay (§7.5) กู้คืนไม่ได้ · market data เข้ามาทาง `update_market` ไม่ใช่พารามิเตอร์ของ port เพราะ Live ไม่ต้องใช้ | ✅ Decided |
| C-21 | ~~`submit` กัน retry ด้วยสถานะของ Order เอง~~ — **แทนที่ด้วย C-22** เหตุผล: กฎนี้ถูกต้องเฉพาะ Paper ที่ record คือ venue · Live อนุมานแบบเดียวกันไม่ได้ (`PENDING_NEW` หลัง timeout คือสถานะไม่แน่นอนที่ FR-LIVE-07 บอกว่าต้อง query ก่อน retry) การเขียนเป็นสัญญาของ port จึงทำให้ Live ทำตามไม่ได้ และเปิดทาง R-06 | ⚠️ Superseded |
| C-22 | **ขอบเขตของ Execution Adapter port** (FR-ORD-03, FR-ORD-04): <br>• **Idempotency เป็นของ Order Manager** ตาม FR-ORD-03 ที่ระบุไว้ตรงตัว รวมถึง query-before-retry ของ FR-LIVE-07 · adapter รับประกันแค่ว่าได้ Order ที่เป็น `PENDING_NEW` มา ถ้าไม่ใช่ให้โยน `ValueError` เป็น precondition ไม่ใช่ policy<br>• **`submit` คืน report เสมอ 1 ใบ** ไม่มีเส้นทางที่เงียบ ดังนั้น "ไม่มี report" แปลว่า bug อย่างเดียว<br>• **การขับ Order ที่ค้างด้วยราคาไม่ใช่งานของ adapter** เพราะ Binance ขับ order ของตัวเอง ถ้า engine เรียกผ่าน adapter จะรู้ว่าอยู่ฝั่ง Paper ซึ่งขัด FR-ORD-04 · แยกเป็น pure function `resting_fill_report(order, last_price)` ที่ engine เรียกเฉพาะเส้นทาง Paper<br>• TP/SL ที่ยิงแล้วต้อง fill แบบ Market และต้องใช้ position จึงเป็นงานของ Order Manager (§4.3) ไม่ใช่ของฟังก์ชันนี้ | ✅ Decided |
| C-23 | **ขอบเขตของ Bracket ใน core** (FR-ORD-14, FR-ORD-15, R-16): <br>• **คืนแผน ไม่สั่งงานเอง** — ทุกเหตุการณ์คืน `BracketPlan` (`protect` / `cancel`) แล้ว Order Manager เป็นคนลงมือ · เหตุผลเดียวกับ C-22 คือ core ต้องไม่รู้ว่า venue เป็น Paper หรือ Binance (FR-ORD-04)<br>• **ป้องกันเท่าที่ fill แล้วเท่านั้น** — ขนาดของ TP/SL = `entry.filled_quantity` ไม่ใช่ `quantity` ที่สั่ง · Entry ที่ยังไม่ fill เรียก `on_entry_fill` แล้วโยน `ValueError` เพราะขา 0 หน่วยไม่มีความหมาย<br>• **resize เป็น action เดียว** — `ProtectLeg.replaces` ถือ Client Order ID ของขาเดิม ไม่แยกเป็น cancel + place เพราะจะอธิบายช่วงเวลาที่จำนวนที่ fill แล้วไม่มีการป้องกัน ซึ่ง FR-ORD-14 ไม่อนุญาต · วิธีทำจริง (amend หรือ cancel/replace) ต่างกันตาม venue จึงเป็นการตัดสินของ Order Manager<br>• **Bracket ไม่ใช่ entity แยก** — ตรงกับ data-model §6.5 ที่เก็บเป็น `bracket_id` + `bracket_role` บนแถว `orders` · core ไม่ถือ state ใด ๆ (C-20)<br>• **FR-ORD-16 (retry + fail-safe ตอนวาง SL ไม่สำเร็จ) ไม่อยู่ใน core** — ต้องนับเวลาและนับครั้ง ซึ่ง core อ่านนาฬิกาไม่ได้ (ADR-0001) · Paper ไม่มีกรณีนี้อยู่แล้วตาม FR-ORD-17 | ✅ Decided |
| C-24 | **Bracket ที่จบแล้วต้องไม่เหลือ order ใดค้าง รวมถึง Entry** (FR-ORD-15, ขยายจากที่ spec เขียนไว้): FR-ORD-15 ระบุแค่ให้ยกเลิก*ขาป้องกัน*ที่เหลือ ไม่ได้พูดถึง Entry · ใช้กับทั้ง 2 เหตุการณ์ที่จบ Bracket คือ **ขาป้องกัน fill** และ **Position ถูกปิดด้วยวิธีอื่น** (Manual, Liquidation, นอกระบบ) · เหตุผล: หลัง SL ยิง Entry ฝั่ง Buy จะค้างอยู่**เหนือ**ราคาตลาดที่เพิ่งร่วงทะลุมา ซึ่ง fill ทันที แล้วเปิด Position เดิมกลับขึ้นมาโดย**ไม่มีการป้องกัน** เพราะขาที่จะคุ้มครองถูกใช้หรือถูกยกเลิกไปแล้ว · FR-ORD-14 วางการป้องกันที่ Entry fill **ครั้งแรก** แล้วปรับขนาดต่อไป ไม่มีการวางชุดที่สอง (`on_entry_fill` จึงปฏิเสธการ resize ขาที่ terminal ไปแล้ว) · สถานะปลายทาง (Entry ถูกยกเลิกหลัง fill บางส่วน) เป็นสถานะที่ FR-ORD-15 อธิบายไว้อยู่แล้ว · ความเสียหายสองทางไม่เท่ากัน: ยกเลิกผิดแค่เสียโอกาสและเข้าใหม่ได้ แต่ Position ที่ไม่มี SL ขาดทุนได้ไม่จำกัด | ✅ Decided |

---

## Sources
- [How to Calculate Liquidation Price of USDⓈ-M Futures Contracts](https://www.binance.com/en/support/faq/how-to-calculate-liquidation-price-of-usd%E2%93%A2-m-futures-contracts-b3c689c1f50a44cabb3a84e663b81d93)
- [How to Calculate the Cost Required to Open a Position in Perpetual Futures Contracts](https://www.binance.com/en/support/faq/how-to-calculate-the-cost-required-to-open-a-position-in-perpetual-futures-contracts-87fa7ee33b574f7084d42bd2ce2e463b)
- [How to Calculate the Margin Requirement on Binance Futures Trading](https://www.binance.com/en/support/faq/how-to-calculate-the-margin-requirement-on-binance-futures-trading-4f83b65d83654b5e933f85ef12bf769d)
- [Binance Futures Liquidation Protocols](https://www.binance.com/en/support/faq/binance-futures-liquidation-protocols-360033525271)
- [Leverage and Margin of USDⓈ-M Futures](https://www.binance.com/en/support/faq/leverage-and-margin-of-usd%E2%93%A2-m-futures-360033162192)
