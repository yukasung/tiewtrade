# TiewTrade — MVP Requirements

| Field | Value |
|---|---|
| Status | **Draft v0.23** — รอตัดสิน [Decisions Needed](#7-questions--decisions-needed) (ตัดสินแล้ว: D-01, D-02, D-03, D-04, D-05, D-06, D-07, D-08, D-09, D-10, D-11, D-12, D-13, D-14, D-15, D-16, D-17, D-18, D-19, D-20, D-22 — ครบทุกข้อที่ block architecture และ Phase 1; ที่เหลือ block Phase 2 — ดู [Decision Log](#71-decision-log)) |
| Date | 2026-09-22 |
| Scope | วิเคราะห์ requirement, ambiguity, technical risk, MVP scope, domain glossary |
| Out of scope | Architecture design, data model, database migration, API design, UI design, implementation |
| Architecture | [docs/architecture/architecture.md](../architecture/architecture.md) |

> **หลักการอ่านเอกสารนี้**
> - ข้อความที่ระบุ **"Proposed"** คือข้อเสนอที่ยังไม่ได้รับการยืนยัน
> - ข้อความที่ระบุ **"Pending D-xx"** คือเรื่องที่ต้องตัดสินใน [Section 7](#7-questions--decisions-needed) ก่อนนำไปออกแบบ
> - ข้อความที่ระบุ **"Decided D-xx"** คือเรื่องที่ตัดสินแล้ว บันทึกไว้ใน [Decision Log](#71-decision-log)
> - Domain term ใช้ภาษาอังกฤษตาม [Glossary (Section 6)](#6-domain-glossary-ubiquitous-language) เสมอ ทั้งในเอกสาร, code, API และ UI

---

## 1. Product Overview

### 1.1 Vision
Trading SaaS แบบ multi-user สำหรับเทรดบน **Binance Spot** และ **Binance USDⓈ-M Futures** ทั้งแบบ **Manual Trading** และ **Bot Trading** โดยมีหน้าจอลักษณะ Trading Terminal, Strategy Engine, Portfolio Risk Management และ Performance Analytics รองรับทั้ง **Paper Trading** และ **Live Trading** บน Trading Core ชุดเดียวกัน

**ตลาดเป้าหมาย: ผู้ใช้ในประเทศไทย** พัฒนาบน Binance.com ก่อน และรองรับ Binance TH ในอนาคตเมื่อเปิด feature ที่ต้องใช้ (D-17)

### 1.2 Goals
1. ผู้ใช้แยกเงินทุนและความเสี่ยงเป็นหลาย **Portfolio** (1 Portfolio ต่อ 1 Sub-account, 1 Market Type, Active Bot ได้ครั้งละ 1 ตัว) และเปรียบเทียบผลลัพธ์ระหว่าง Portfolio ได้
2. Paper Trading ต้องมีพฤติกรรมใกล้เคียง Live มากพอให้ใช้ทดสอบ Strategy ก่อนใช้เงินจริง
3. ทุก Order ทั้งจากคนและ Bot ต้องผ่านการควบคุมความเสี่ยงระดับ Portfolio
4. ความปลอดภัยของ API Credential ต้องออกแบบตั้งแต่วันแรก
5. เริ่มพัฒนา Paper Trading ก่อน แล้วจึงเปิด Live Trading

### 1.3 Technology Direction (กำหนดแล้ว)
| Layer | Technology |
|---|---|
| Frontend | React + TypeScript |
| Backend API | Python + FastAPI |
| Trading Core | Pure Python, **ไม่ผูกกับ FastAPI** |
| Database | PostgreSQL |
| Cache / Realtime | Redis |
| Infrastructure | Docker; ช่วงทดลองรันบน **VM เดียว**, production target **GCP: Cloud Run + Cloud SQL** (ส่วนที่ต้องทำงานตลอดเวลาจะใช้ Cloud Run แบบทำงานตลอด / worker pools / GKE / Compute Engine — ตัดสินตอน design) ออกแบบตามหลัก NFR-19 ถึง 25 |

### 1.4 Guiding Principles (Invariants)
ทุก design และ implementation ต้องไม่ละเมิดหลักต่อไปนี้ อ้างอิงด้วย ID

| ID | Principle |
|---|---|
| P-01 | **Strategy / Bot ห้ามเรียก Binance API โดยตรง** Strategy ส่งได้แค่ Signal / Order Intent |
| P-02 | **ทุก Order ต้องผ่าน Risk Engine และ Order Manager** ไม่มีทางลัด ทั้ง Manual, Bot และ Paper/Live |
| P-03 | **Paper และ Live ใช้ Trading Core ร่วมกัน** ต่างกันแค่ Execution Adapter และแหล่งที่มาของ account state |
| P-04 | **Paper Execution Adapter และ Binance Execution Adapter แยกจากกัน** และมี interface เดียวกัน |
| P-05 | **Margin / Liquidation คำนวณระดับ Portfolio (Sub-account)** ไม่ใช่ระดับ Bot หรือ Strategy |
| P-06 | **Timeframe ไม่ผูกกับ Sub-account โดยตรง** Timeframe เป็น property ของ Bot / Strategy / Chart |
| P-07 | **การคำนวณ PnL, Margin, Liquidation, Fee ต้องเป็น deterministic code** ห้ามใช้ AI |
| P-08 | **Binance เป็น Source of Truth สำหรับ Live** ถ้า state ภายในขัดกับ Binance ให้เชื่อ Binance |
| P-09 | **ต้องมี Reconciliation กับ Binance** เป็นกลไกหลัก ไม่ใช่งานเสริม |
| P-10 | **Security และ API Credential Isolation ออกแบบตั้งแต่ต้น** |

---

## 2. Requirement Analysis

Requirement ID: `FR-<area>-<nn>` (Functional), `NFR-<nn>` (Non-functional)

### 2.1 Tenancy & User
| ID | Requirement |
|---|---|
| FR-TEN-01 | รองรับหลาย User; ข้อมูลของแต่ละ Workspace (Exchange Account, Sub-account, Portfolio, Bot, Order, API Credential) ต้องแยกกันเด็ดขาด (**Decided D-12**) |
| FR-TEN-02 | User สมัครสมาชิก, login, logout, reset password ได้ |
| FR-TEN-03 | Workspace ผูกกับ Plan (Free / Pro / Advanced) หนึ่ง Plan ณ เวลาหนึ่ง และระบบบังคับใช้ Entitlement ตาม Plan (**Decided D-12**) |
| FR-TEN-04 | ต้องรองรับ 2FA และบังคับใช้กับ User ที่เปิด Live Trading (**Decided D-11**) |
| FR-TEN-05 | เมื่อ User สมัคร ระบบสร้าง Workspace ส่วนตัวให้อัตโนมัติ 1 อัน โดย User เป็นสมาชิกคนเดียว; ใน MVP หนึ่ง Workspace มีสมาชิกได้ 1 คน และหนึ่ง User มี Workspace ได้ 1 อัน (**Decided D-12**) |
| FR-TEN-06 | ข้อมูลทั้งหมดเป็นของ Workspace ไม่ใช่ของ User โดยตรง เพื่อให้เพิ่มสมาชิกหลายคนในอนาคตได้โดยไม่ต้องย้ายความเป็นเจ้าของของข้อมูล (**Decided D-12**) |
| FR-TEN-07 | ใน MVP ผู้ใช้ไม่เห็นคำว่า Workspace ในหน้าจอ ประสบการณ์ใช้งานเหมือนบัญชีส่วนตัว (**Decided D-12**) |
| FR-TEN-08 | การตรวจสิทธิ์ทุกครั้งผ่านจุดเดียว ในรูป "User นี้เป็นสมาชิกของ Workspace นี้และมีสิทธิ์ทำสิ่งนี้หรือไม่"; ใน MVP สมาชิกคนเดียวมีทุกสิทธิ์ ยังไม่มี Role (**Decided D-12**) |
| FR-TEN-09 | Audit log บันทึกทั้ง Workspace และ User ผู้กระทำ ตั้งแต่วันแรก (**Decided D-12**) |

### 2.2 Account Hierarchy
ระบบใช้ **model เดียวกัน** ทั้ง Paper และ Live (mirror structure) เพื่อให้ Trading Core ไม่ต้องรู้ว่าเป็น Paper หรือ Live (P-03)

```
Workspace (MVP: สมาชิก 1 คน = User ผู้สมัคร)
├── Exchange Account (LIVE)  = Binance Main Account        ← ใช้เป็น Live Portfolio ได้ 1 Portfolio (D-04)
│   ├── Sub-account           = Binance Sub-account ── Portfolio (USDM_FUTURES)
│   └── Sub-account           = Binance Sub-account ── Portfolio (SPOT)
└── Exchange Account (PAPER) = Paper Main Account          ← กองกลาง (MVP ไม่เทรด)
    ├── Sub-account           = Virtual Sub-account ── Portfolio (USDM_FUTURES)
    └── Sub-account           = Virtual Sub-account ── Portfolio (SPOT)
```

| ID | Requirement |
|---|---|
| FR-ACC-01 | User มี Paper Main Account ได้ และสร้าง Virtual Sub-account ภายใต้ได้ (จำนวนตาม Plan) |
| FR-ACC-02 | User เชื่อมบัญชี Binance (Sub-account หรือ Main Account) เข้าระบบ**ทีละบัญชีด้วย API Key ของบัญชีนั้นเอง** ระบบ**ไม่ขอและไม่เก็บ Key ของ Main Account เพื่อจัดการ Sub-account** และไม่สร้าง Sub-account ให้ (**Decided D-04**) |
| FR-ACC-03 | Main Account กับ Sub-account ใน Paper มีพฤติกรรมเลียนแบบ Binance: เงินเริ่มต้นอยู่ที่ Paper Main Account และ User Transfer ไป Virtual Sub-account เอง (**Decided D-19**) |
| FR-ACC-04 | Trading Mode (`PAPER` / `LIVE`) เป็น attribute ของ Exchange Account; Portfolio สืบทอด Trading Mode และห้ามเปลี่ยนภายหลัง |
| FR-ACC-05 | **Paper:** Paper Main Account เป็นกองกลาง ไม่มี Portfolio (**Decided D-01**). **Live:** Binance Main Account ใช้เป็น Live Portfolio ได้ 1 Portfolio ตามกติกา 1 บัญชี = 1 Portfolio = 1 Market Type เพื่อรองรับ User ที่เปิด Sub-account ไม่ได้; ระบบเตือน User ไม่ให้เทรดเองในบัญชีที่เชื่อมกับระบบ (**Decided D-04** — ทบทวน D-01 ข้อ 2 สำหรับ Live) |
| FR-ACC-06 | Account model ต้องออกแบบให้ทั้ง Main Account และ Sub-account เป็นบัญชีชนิดที่ผูก Portfolio ได้ เพื่อให้เปิดการเทรดบน Main Account ภายหลังได้โดยไม่ต้องรื้อ model (**Decided D-01**; การเปิดใช้บน Live ทบทวนพร้อม **D-04**) |
| FR-ACC-07 | Paper Main Account ของแต่ละ Workspace เริ่มต้นด้วย **10,000 USDT** (ค่านี้ Platform Admin ปรับได้) เท่ากันทุก Plan; Asset เป็น USDT อย่างเดียว (**Decided D-19**) |
| FR-ACC-08 | User **เติมเงินจำลอง** เข้า Paper Main Account ได้ ระบบบันทึกเป็นเงินทุนที่เข้ามา (Virtual Deposit) และ Analytics ต้องไม่นับเป็นกำไร (**Decided D-19**) |
| FR-ACC-09 | User **Reset Portfolio** ของ Virtual Sub-account ได้ ต้องไม่มี Active Bot: (1) ปิด Position และยกเลิก Order ตาม FR-ACC-10 (2) **โอนเงินที่เหลือทั้งหมดคืน Paper Main Account** บันทึกเป็น Transfer (เงินออก ไม่นับเป็นกำไร) (3) เก็บ Portfolio เดิมเป็นประวัติแบบอ่านอย่างเดียว (Archived; ยังแสดงใน Analytics และเปรียบเทียบได้) (4) สร้าง Portfolio ใหม่ใน Sub-account เดิมด้วย**ยอด 0** แล้ว User โอนเงินจาก Paper Main เอง (หน้าจอกรอกจำนวนเดิมไว้ให้); ถ้า Main ไม่พอใช้ Virtual Deposit (FR-ACC-08) (**Decided D-19**, ปรับตาม Review 2026-09-22) |
| FR-ACC-10 | Position และ Order ที่ค้างใน Portfolio ที่ถูก Reset ต้องปิด/ยกเลิกก่อนเก็บเป็นประวัติ ตามกติกา Paper Fill Model (**Decided D-19**; รายละเอียดกำหนดตอน design) |
| FR-ACC-11 | Analytics ต้องแยกเงินที่เข้า/ออก Portfolio (Transfer, Virtual Deposit) ออกจากกำไร/ขาดทุน (**Decided D-19**) |
| FR-ACC-12 | Portfolio ที่ Archived แล้ว **ไม่นับ**ใน limit จำนวน Portfolio ของ Plan และไม่นับในวงเงิน (Open Notional) (**Decided — Review 2026-09-22**) |

**ข้อสังเกตจาก Binance (ต้อง verify ตอน design):**
- บัญชี Binance ทั่วไปมีเงื่อนไขในการเปิดใช้ Sub-account (เช่น VIP level หรือ corporate account) ผู้ใช้บางคนอาจไม่มี Sub-account เลย
- การส่ง Order ใน Sub-account ต้องใช้ **API Key ของ Sub-account นั้น** ส่วน Master Key ใช้ได้แค่ endpoint จัดการ Sub-account เช่นโอนเงิน หรือดู balance
- Binance มี Broker program ที่สร้าง Sub-account ให้ลูกค้าได้ แต่มีเงื่อนไขทางธุรกิจและกฎหมาย — ไม่ใช้ใน MVP (**Decided D-04**)

### 2.3 Portfolio
**นิยาม (Decided D-01):** Portfolio คือหน่วยของเงินทุน ความเสี่ยง และผลลัพธ์ โดย **1 Sub-account = 1 Portfolio = 1 Market Type** Portfolio ใช้เฉพาะ Wallet ของ Market Type ที่เลือก จึงมีแหล่ง margin ก้อนเดียวเสมอ

```
Sub-account "Scalping"  ── Portfolio "Scalping"  (USDM_FUTURES → ใช้ USDⓈ-M Futures wallet)
Sub-account "Hold BTC"  ── Portfolio "Hold BTC"  (SPOT         → ใช้ Spot wallet)
```

| ID | Requirement |
|---|---|
| FR-PF-00a | Sub-account หนึ่งตัวมี Portfolio ที่ **ACTIVE** ได้ไม่เกิน 1 ตัว (Portfolio ที่ Archived หลัง Reset ไม่นับ, FR-ACC-09) |
| FR-PF-00b | ตอนสร้าง Portfolio ต้องเลือก Market Type (`SPOT` หรือ `USDM_FUTURES`) และห้ามเปลี่ยนภายหลัง |
| FR-PF-00c | Portfolio นับ Balance, Margin, PnL, Risk และ Liquidation จาก Wallet ของ Market Type ของตัวเองเท่านั้น |
| FR-PF-00d | Live: ยอดเงินใน Wallet อื่นของ Sub-account เดียวกัน (ที่ Portfolio ไม่ได้ใช้) ต้องแสดงแยกเป็นเงินนอก Portfolio และไม่นำไปคำนวณใดๆ |
| FR-PF-00e | Portfolio ต้องถูกระบุด้วยคู่ (Sub-account, Market Type) ตั้งแต่ต้น เพื่อให้ยกเลิกข้อจำกัด 1:1 ในอนาคตได้โดยไม่ต้องรื้อ model |
| FR-PF-01 | แต่ละ Portfolio มี Balance, Position, Margin, PnL, Risk และ Liquidation ของตัวเอง และไม่กระทบ Portfolio อื่น |
| FR-PF-02 | Portfolio ถือได้หลาย Symbol พร้อมกัน |
| FR-PF-03 | Portfolio ใช้ได้หลาย Bot / Strategy **ตลอดอายุของ Portfolio** แต่มี **Active Bot ได้ครั้งละ 1 ตัว** (**Decided D-02** — เปลี่ยนจาก requirement ต้นฉบับ "Portfolio รองรับหลาย Strategy, Bot") Bot ตัวเดียวเทรดได้หลาย Symbol และหลาย Timeframe (P-06) |
| FR-PF-04 | แสดง Wallet Balance, Available Balance, Margin Balance, Equity, Unrealized PnL, Realized PnL, Margin Ratio แบบ realtime |
| FR-PF-05 | แสดง Position ทั้งหมดพร้อม Entry Price, Mark Price, Liquidation Price, Leverage, Margin Mode |
| FR-PF-06 | บันทึกประวัติ Order, Fill, Fee, Funding Fee และ Transfer ของ Portfolio ครบถ้วน (audit trail) |
| FR-PF-07 | Portfolio อยู่ในสถานะใดสถานะหนึ่งเสมอ: **มี Active Bot** (ใช้กับ Bot นั้นเท่านั้น) หรือ **ไม่มี Active Bot** (ใช้ Manual Trading) (**Decided D-02**) |
| FR-PF-08 | เริ่ม Bot ได้เฉพาะเมื่อ Portfolio ไม่มี Position และ Order ค้าง ซึ่งรวมถึง Position/Order ที่เปิดจาก Manual (**Decided D-02**; นิยามของ Spot ดู A-24) |
| FR-PF-09 | เปลี่ยน Bot ใน Portfolio เดิมได้ (หยุด Bot A แล้วเริ่ม Bot B) เมื่อ Portfolio ไม่มี Position และ Order ค้าง (**Decided D-02**) |
| FR-PF-10 | ทุก Order และ Fill ต้องบันทึก **Order Owner** (Bot ID, `MANUAL` หรือ `EXTERNAL` ตาม D-14) = ผู้ส่ง Order; และทุก Fill, Fee, Funding และรายการ ledger ที่เกี่ยวกับ Position ต้องบันทึก **Position Episode** ที่เป็นเจ้าของผล (FR-PF-11) (**Decided D-02**, ปรับตาม Review 2026-09-22) |
| FR-PF-11 | **Position Episode:** Position ของ Symbol หนึ่งตั้งแต่เปิดจากศูนย์จนกลับเป็นศูนย์คือหนึ่ง Episode; **ผลทั้งหมดของ Episode** (Realized PnL ทุก Fill รวม Fill ที่ปิดโดย Manual, Liquidation หรือนอกระบบ, Fee และ Funding) **เป็นของผู้ที่เปิด Episode** (Bot, `MANUAL` หรือ `EXTERNAL`); Episode คร่อมสอง Bot ไม่ได้เพราะเปลี่ยน Bot ได้เฉพาะเมื่อไม่มี Position ค้าง (FR-PF-09); การกลับทิศใน One-way ปิด Episode เดิมและเปิด Episode ใหม่ (**Decided — Review 2026-09-22**) |

**ข้อสังเกต (เหตุผลของ D-02):** บน Binance USDⓈ-M แบบ One-way Mode, **หนึ่ง Symbol มี Position ได้แค่ตัวเดียวต่อ account** และ **Leverage / Margin Mode ตั้งค่าต่อ Symbol ต่อ account** ถ้ามีหลาย Bot ในบัญชีเดียว Position ของ Symbol เดียวกันจะถูกหักลบกันเป็น net position และ Bot ต้องใช้ Leverage ร่วมกัน ส่วนใน Cross Margin ความเสียหายของ Bot หนึ่งยังลามไป Liquidate Position ของ Bot อื่นได้ กติกา Active Bot ครั้งละ 1 ตัวป้องกันปัญหาเหล่านี้ทั้งหมด

### 2.4 Markets
| ID | Requirement |
|---|---|
| FR-MKT-01 | รองรับ Market Type `SPOT` และ `USDM_FUTURES` |
| FR-MKT-02 | **Spot:** ซื้อ/ขายด้วย balance จริงของ asset; ไม่มี Leverage, Margin Mode หรือ Liquidation; ทำได้แค่ Long (ถือ base asset) |
| FR-MKT-03 | **USDⓈ-M Futures:** Long / Short, Leverage, Cross / Isolated Margin, Funding Fee, Liquidation |
| FR-MKT-04 | ใช้ Symbol metadata และ Symbol Filters (tickSize, stepSize, minNotional, min/max qty) จาก Binance ทั้งใน Paper และ Live |
| FR-MKT-05 | USDⓈ-M Futures ใน MVP รองรับเฉพาะ **One-way Mode** ถือ Position ได้ทิศทางเดียวต่อ Symbol ส่วน Hedge Mode อยู่ใน Future (**Decided D-03**) |
| FR-MKT-06 | ใช้ **Single-Asset Mode** เท่านั้น ไม่รองรับ Multi-Assets Mode และ Portfolio Margin (**Decided D-03**; quote asset คือ USDT อย่างเดียวตาม **D-15**) |
| FR-MKT-07 | Cross / Isolated Margin ยังรองรับครบ และตั้งแยกต่อ Symbol ได้ (ไม่กระทบจาก D-03) |
| FR-MKT-08 | Virtual Sub-account ใช้ One-way และ Single-Asset ตายตัว เพื่อให้ตรงกับฝั่ง Live (P-03, **Decided D-03**) |
| FR-MKT-09 | Position ต้องระบุด้วย (Portfolio, Symbol, Position Side) ตั้งแต่ต้น แม้ One-way จะมีแค่แถวเดียวต่อ Symbol เพื่อให้เพิ่ม Hedge Mode ภายหลังได้โดยไม่ต้องรื้อ model (**Decided D-03**) |
| FR-MKT-10 | **ไม่รองรับ Spot Margin** (กู้เงิน/เหรียญมาเทรด Spot) ใน MVP; Spot เป็น Long อย่างเดียวและไม่มี Leverage ส่วน Short, Leverage และ Cross / Isolated Margin ใช้กับ USDⓈ-M Futures เท่านั้น (**Decided D-10**) |
| FR-MKT-11 | Market Type ต้องออกแบบให้เพิ่มค่าใหม่ได้ และการคำนวณ Margin / Liquidation แยกตาม Market Type ไม่เขียนเงื่อนไขเฉพาะ Market Type กระจายทั่ว code เพื่อให้เพิ่ม Spot Margin ภายหลังได้ (**Decided D-10**) |
| FR-MKT-12 | Quote Asset ที่รองรับคือ **USDT อย่างเดียว** ทั้ง Spot และ USDⓈ-M Futures (**Decided D-15**) |
| FR-MKT-13 | Symbol ที่เปิดให้เทรดมาจาก **Symbol Whitelist** ที่ Platform Admin จัดการ เริ่มประมาณ 30 ตัว ไม่เกิน 50 ตัว (เป้า NFR-16) (**Decided D-15**) |
| FR-MKT-14 | เกณฑ์คัดเลือก Symbol: มีทั้งใน Spot และ USDⓈ-M Futures และมีปริมาณซื้อขายสูง (**Decided D-15**) |
| FR-MKT-15 | การนำ Symbol ออกจาก Whitelist: ถ้ายังมี Position/Order ค้าง ให้ปิดการเปิด Position ใหม่ก่อน และนำออกได้เมื่อไม่มีใครถือแล้ว (**Decided D-15**) |
| FR-MKT-16 | เมื่อ Binance ประกาศ delist Symbol: ปิดการเปิด Position ใหม่ทันที และแจ้ง User ที่ถือ Position อยู่ (**Decided D-15**) |

**ข้อสังเกต:**
- "Short" ใน Spot ทำได้ผ่าน Spot Margin เท่านั้น — **ไม่รองรับ Spot Margin ใน MVP** (**Decided D-10**) ดังนั้น Long / Short, Leverage และ Cross / Isolated ใน requirement ต้นฉบับหมายถึง USDⓈ-M Futures เท่านั้น
- Spot wallet กับ USDⓈ-M Futures wallet ใน Binance account เดียวกันเป็น **คนละ wallet** — Portfolio ใช้ wallet เดียวตาม Market Type ที่เลือก (**Decided D-01**) ผู้ใช้ที่ต้องการเทรดทั้งสองตลาดต้องใช้ 2 Sub-account

### 2.5 Manual Trading
| ID | Requirement |
|---|---|
| FR-MAN-01 | ส่ง Order แบบ `MARKET` และ `LIMIT` ได้ |
| FR-MAN-02 | ตั้ง Entry, Take Profit (TP), Stop Loss (SL) พร้อมกันเป็น Bracket Order ได้ |
| FR-MAN-03 | แก้ไข / ยกเลิก TP/SL ของ Position ที่เปิดอยู่ได้ |
| FR-MAN-04 | เลือก Long / Short (Futures), ตั้ง Leverage และ Margin Mode ต่อ Symbol |
| FR-MAN-05 | ปิด Position บางส่วนหรือทั้งหมดได้ (reduce-only) |
| FR-MAN-06 | Order จาก Manual Trading ต้องผ่าน Risk Engine เหมือน Order จาก Bot (P-02) |
| FR-MAN-07 | ก่อนส่ง Order ต้องแสดงค่าประมาณ: required margin, estimated liquidation price, fee |
| FR-MAN-08 | ใน Portfolio ที่มี Active Bot: Manual **ลดหรือปิด Position และยกเลิก Order ได้** (ใช้กรณีฉุกเฉิน) และเมื่อทำแล้วระบบ **Pause Bot อัตโนมัติ**; Manual **เปิดหรือเพิ่ม Position ไม่ได้ทุก Symbol** รวมถึง Symbol ที่ Bot ไม่ได้เทรด (**Decided D-02**) |
| FR-MAN-09 | Kill Switch ข้ามกติกา FR-MAN-08 ได้เสมอ (**Decided D-02**) |

**ข้อสังเกต:**
- TP/SL บน Binance Futures ใช้ conditional order (STOP_MARKET / TAKE_PROFIT_MARKET ฯลฯ) และ Binance เคยเปลี่ยน endpoint ของ conditional order ไปใช้บริการแยก (Algo Order) — ต้อง verify API ปัจจุบันตอน design
- Spot ใช้ OCO / OTO แทน ทำให้พฤติกรรม Bracket ต่างกันระหว่าง Market Type
- Binance ไม่ได้ทำให้ TP/SL เป็น OCO ระหว่างกันเสมอไป Order Manager อาจต้องยกเลิกขาที่เหลือเองเมื่อขาหนึ่ง fill

### 2.6 Order Pipeline
Flow บังคับ (P-01, P-02, P-04):

```
Manual UI ─┐
           ├─► Order Intent ─► Risk Engine ─► Order Manager ─► Execution Adapter ─┬─► Paper Execution Adapter
Bot/Strategy┘                  (approve/reject)  (lifecycle,          (interface)   └─► Binance Execution Adapter
                                                  idempotency)
                         ◄──────────── Fill / Order Update Events ◄──────────────────┘
```

| ID | Requirement |
|---|---|
| FR-ORD-01 | Strategy / Bot / UI สร้างได้แค่ Order Intent ส่ง Order ถึง exchange เองไม่ได้ |
| FR-ORD-02 | Risk Engine ตรวจ Order Intent กับ Risk Rule ของ Portfolio แล้วคืน Risk Check Result (approve / reject + เหตุผล) |
| FR-ORD-03 | Order Manager ดูแล lifecycle ของ Order (new → partially filled → filled / canceled / rejected / expired), Bracket Order และ idempotency (Client Order ID) |
| FR-ORD-04 | Execution Adapter เป็น interface เดียว; Trading Core ไม่รู้ว่าเบื้องหลังเป็น Paper หรือ Binance |
| FR-ORD-05 | ทุก Order และการตัดสินของ Risk Engine ต้องบันทึกไว้ (audit log) |
| FR-ORD-06 | Paper Execution Adapter จำลองการ fill จาก market data จริงของ Binance ตาม Paper Fill Model (FR-ORD-07 ถึง 13) หลักการคือผล Paper ต้องไม่ดูดีเกินจริง (**Decided D-05**) |
| FR-ORD-07 | **Market Order (Paper):** fill ที่ best bid/ask (ซื้อที่ราคาเสนอขาย, ขายที่ราคาเสนอซื้อ) บวก slippage คงที่ ค่าเริ่มต้น **0.02%** ซึ่ง Platform Admin ปรับได้; ไม่จำลองความลึกของ order book (**Decided D-05**) |
| FR-ORD-08 | **Limit Order (Paper):** fill เมื่อราคาวิ่ง**ทะลุ** Limit ไม่ใช่แค่แตะ และคิด Maker fee; Limit ที่ fill ได้ทันทีตอนส่ง (marketable) นับเป็น Taker และ fill ทันทีด้วย**ราคาที่ไม่แย่กว่าราคา Limit เสมอ**: Buy = `min(limit, ask×(1+s))`, Sell = `max(limit, bid×(1−s))` (Calculation §4.2) (**Decided D-05**, ปรับตาม Review 2026-09-22) |
| FR-ORD-09 | **Partial fill (Paper):** ไม่จำลอง Order fill ครั้งเดียวเต็มจำนวน (**Decided D-05**) |
| FR-ORD-10 | **Fee (Paper):** ใช้อัตรามาตรฐานของ Binance ระดับเริ่มต้น (VIP 0) เป็นค่ากลางทั้งระบบ Platform Admin ปรับได้; ไม่คิดส่วนลด BNB (อัตราจริงต้อง verify ตอน design) (**Decided D-05**) |
| FR-ORD-11 | **Funding Fee (Paper):** จำลองด้วย Funding Rate และเวลาจริงจาก Binance (**Decided D-05**) |
| FR-ORD-12 | **TP / SL (Paper):** ตัดสินว่าแตะแล้วด้วย **Last Price**; เมื่อแตะแล้ว fill แบบ Market Order (bid/ask + slippage + Taker fee) (**Decided D-05**) |
| FR-ORD-13 | ข้อมูลตลาดที่ต้องรับสำหรับทุก Symbol ที่รองรับ: best bid/ask, Last Price, Mark Price และ Funding Rate (**Decided D-05**) |
| FR-ORD-14 | **Bracket — เริ่มป้องกัน:** TP/SL เริ่มทำงานตั้งแต่ Entry **fill ครั้งแรก** และครอบคลุม**จำนวนที่ fill แล้วเท่านั้น**; ทุกครั้งที่ Entry fill เพิ่ม ปรับขนาด TP/SL ตามจำนวนที่ fill สะสม (**Decided — Review 2026-09-22**) |
| FR-ORD-15 | **Bracket — จบ:** ขาใดขาหนึ่ง (TP หรือ SL) fill แล้วยกเลิกขาที่เหลือ; ถ้า Entry ถูกยกเลิกหรือหมดอายุหลัง fill บางส่วน TP/SL ยังคุมส่วนที่ fill แล้ว; ถ้า Position ถูกปิดด้วยวิธีอื่น (Manual, Liquidation, นอกระบบ) ยกเลิก TP/SL ที่เหลือ (R-16) (**Decided — Review 2026-09-22**) |
| FR-ORD-16 | **Bracket — วางป้องกันไม่สำเร็จ (Live):** ลองวาง SL ใหม่ได้จำนวนครั้งจำกัดภายในไม่กี่วินาที (ค่าตั้งของระบบ); ถ้ายังไม่สำเร็จ **fail-safe: ปิดส่วนที่ไม่มี SL ด้วย Market Order แบบ reduce-only**, Pause Bot (ถ้ามี) และแจ้งเตือนระดับวิกฤต; TP ที่วางไม่สำเร็จไม่ต้องปิด Position แต่แจ้งเตือน (**Decided — Review 2026-09-22**) |
| FR-ORD-17 | Paper จำลอง TP/SL ภายในระบบตามกติกา FR-ORD-14/15 (ไม่มีกรณีวางไม่สำเร็จ) (**Decided — Review 2026-09-22**) |

### 2.7 Margin, PnL & Liquidation
| ID | Requirement |
|---|---|
| FR-MRG-01 | คำนวณ Initial Margin, Maintenance Margin, Margin Ratio, Unrealized PnL, Realized PnL, Liquidation Price ด้วย deterministic code (P-07) |
| FR-MRG-02 | คำนวณระดับ Portfolio (P-05): Cross Margin ใช้ Margin Balance รวมของ Portfolio และคิด Unrealized PnL ของทุก Cross Position; Isolated คำนวณต่อ Position |
| FR-MRG-03 | ใช้ Leverage Bracket (Maintenance Margin Rate แบบขั้นบันไดตาม Notional) จาก Binance |
| FR-MRG-04 | ใช้ **Mark Price** เป็นเกณฑ์ Liquidation และ Unrealized PnL ตาม Binance |
| FR-MRG-05 | Paper: เมื่อ Mark Price แตะ Liquidation Price ต้องจำลอง Liquidation: ปิด Position และหักค่าธรรมเนียม Liquidation ตามกติกา Binance (ต้อง verify); **ไม่จำลอง** Insurance Fund และ ADL; รายละเอียดสูตรอยู่ใน calculation spec (**Decided D-05**) |
| FR-MRG-06 | Live: ค่าที่แสดงต้องอ้างอิง Binance เป็นหลัก (P-08); ค่าที่คำนวณเองใช้สำหรับ pre-trade estimate และ risk check |
| FR-MRG-07 | ต้องมีชุด golden test case จากข้อมูลบัญชี Binance จริง: **เมื่อข้อมูลเข้าเหมือนกัน ผลการคำนวณต้องเท่ากับ Binance** คลาดเคลื่อนได้เฉพาะการปัดเศษตาม tick size / precision; ความต่างที่ยอมรับได้มีแค่จากช่วงเวลาของราคาที่ใช้ (**Decided D-05**) |
| FR-MRG-08 | ตัวเลขเงินทั้งหมดใช้ Decimal precision ห้ามใช้ float |

**ข้อสังเกต:** "ใกล้เคียง Binance" นิยามใน FR-MRG-07 ส่วนสิ่งที่ Paper จำลอง (Funding Fee, liquidation fee) และไม่จำลอง (Insurance Fund, ADL) อยู่ใน FR-ORD-11 และ FR-MRG-05 (**Decided D-05**)

### 2.8 Market Data & Chart
| ID | Requirement |
|---|---|
| FR-CHT-01 | Candlestick chart ลักษณะ Trading Terminal (chart + order panel + positions/orders + portfolio summary) |
| FR-CHT-02 | Timeframe ที่รองรับทั้ง Chart และ Strategy: `1m, 5m, 15m, 30m, 1h, 4h, 1d` (7 ค่า) (**Decided D-08**) |
| FR-CHT-03 | Indicator บน Chart ใน MVP: Volume, SMA, EMA, Bollinger Bands, RSI, MACD, ATR (7 ตัว) User ปรับค่าได้ เช่น ระยะของ EMA (**Decided D-08**) |
| FR-CHT-04 | แสดง Entry / TP / SL / Liquidation Price และ Order ที่ค้างอยู่บน chart |
| FR-CHT-05 | Candle อัปเดต realtime จาก Binance market data stream |
| FR-CHT-06 | ค่า Indicator ที่ Strategy ใช้ต้องตรงกับที่แสดงบน Chart: Trading Core เป็นต้นแบบของสูตรทุก Indicator ถ้า Frontend คำนวณเองต้องผ่านชุดค่าทดสอบเดียวกับ Trading Core (**Decided D-08**) |
| FR-CHT-07 | ระบบดึง market data จาก Binance public endpoint/stream ครั้งเดียวแล้วแจกจ่ายให้ทุก User (ไม่ให้แต่ละ User เปิด stream เอง) (**Proposed**) |
| FR-CHT-08 | **ป้าย Buy / Sell บน Chart** แบบ Binance: แสดงจุดที่ Order ของ Portfolio ที่เลือก fill แล้ว ณ เวลาและราคาที่ fill แยกสีซื้อ/ขาย; เมื่อชี้ที่ป้ายแสดงรายละเอียด (ราคา, จำนวน, Fee, Order Owner ว่าเป็น Bot หรือ `MANUAL`); หลาย Fill ในแท่งเดียวกันรวมเป็นป้ายเดียว (**Decided D-08**) |
| FR-CHT-09 | Chart library: **TradingView Lightweight Charts** พร้อมแสดง attribution ตามเงื่อนไข license (เงื่อนไขปัจจุบันต้อง verify ตอน design) (**Decided D-09**) |
| FR-CHT-10 | เครื่องมือวาดเส้นบน Chart (trend line, แนวรับแนวต้าน) ไม่อยู่ใน MVP (**Decided D-09**) |

**ข้อสังเกต:** Lightweight Charts ไม่มี Indicator และเครื่องมือวาดเส้นในตัว Indicator 7 ตัวจึงต้องสร้างเอง ซึ่งช่วยให้ค่าตรงกับ Trading Core (FR-CHT-06) (**Decided D-09**)

### 2.9 Strategy Engine & Trading Bot
| ID | Requirement |
|---|---|
| FR-STR-01 | Strategy รับ input เป็น Candle / Indicator / Portfolio state แล้วส่ง Signal หรือ Order Intent เท่านั้น (P-01) |
| FR-STR-02 | Bot คือ Strategy ที่กำลังรันอยู่ ผูกกับ Portfolio, Symbol, Timeframe และ Strategy Parameters |
| FR-STR-03 | Timeframe เป็น property ของ Bot (P-06); Bot ตัวเดียวใช้หลาย Symbol และหลาย Timeframe ได้ |
| FR-STR-04 | สั่ง Start / Stop / Pause Bot ได้ และดูสถานะ, log, Order และ PnL ของ Bot ได้ |
| FR-STR-05 | Bot ชุดเดียวกันรันบน Paper หรือ Live ได้โดยไม่ต้องแก้ Strategy (P-03) |
| FR-STR-06 | Strategy Engine เป็นส่วนของ Trading Core และไม่ผูกกับ FastAPI |
| FR-STR-07 | Strategy ทั้งหมดเป็น **Built-in Strategy** ที่เจ้าของระบบเขียนเอง User เลือกใช้ได้แต่สร้างหรืออัปโหลด Strategy เองไม่ได้ (**Decided D-06**) |
| FR-STR-08 | **ไม่มี Backtesting ในระบบ** ทั้งใน MVP และในแผนปัจจุบัน; Strategy ทดสอบด้วย Paper Trading (**Decided D-07**) |
| FR-STR-09 | Portfolio มี Active Bot ได้ครั้งละ 1 ตัว; Start Bot ถูกปฏิเสธถ้า Portfolio มี Active Bot อื่น หรือมี Position/Order ค้าง (**Decided D-02**) |
| FR-STR-10 | เมื่อ Manual เข้าไปลด/ปิด Position หรือยกเลิก Order ใน Portfolio ของ Bot ระบบเปลี่ยน Bot Status เป็น `PAUSED` อัตโนมัติ และแจ้ง User; Bot กลับมาทำงานเมื่อ User สั่ง Resume เท่านั้น (**Decided D-02**) |
| FR-STR-11 | แต่ละ Built-in Strategy มี Strategy Parameter Schema ที่เจ้าของระบบกำหนด: Parameter ไหนให้ User ปรับได้ พร้อมชนิด ค่าต่ำสุด/สูงสุด และค่าเริ่มต้น; Parameter ที่ไม่เปิดให้ปรับถูกล็อกไว้ ระบบต้องปฏิเสธค่าที่อยู่นอก schema (**Decided D-06**) |
| FR-STR-12 | Built-in Strategy มีเวอร์ชัน (Strategy Version) และ Bot บันทึกเวอร์ชันที่ใช้ เพื่อให้ตรวจสอบผลย้อนหลังได้เมื่อ Strategy ถูกแก้ไข (**Decided D-06**) |
| FR-STR-13 | Strategy ต้องเขียนตาม Strategy interface เดียว: รับเฉพาะข้อมูลที่ระบบส่งให้ (Candle / ราคาล่าสุด / Indicator / Portfolio state), ไม่ทำ I/O เอง (network, database, Binance) และส่งออกเป็น Signal / Order Intent เท่านั้น เพื่อให้รันได้เหมือนกันทั้ง Paper และ Live และทดสอบซ้ำได้ผลเดิม (P-01, P-03, **Decided D-06**) |
| FR-STR-14 | ชุด Built-in Strategy และ Indicator ที่แต่ละตัวต้องใช้ เจ้าของระบบเป็นผู้กำหนด Indicator ของ Strategy ต้องอยู่ใน Trading Core; Timeframe ใช้ได้เฉพาะ 7 ค่าตาม FR-CHT-02 (**Decided D-08**) |
| FR-STR-15 | Timeframe เล็กสุดที่รองรับคือ `1m` (**Decided D-18**) |
| FR-STR-16 | Strategy interface รองรับ 2 จังหวะ: **เมื่อ Candle ปิด** และ **เมื่อราคาอัปเดตระหว่างแท่ง** Built-in Strategy แต่ละตัวเลือกใช้เฉพาะจังหวะที่ต้องการ (**Decided D-18**) |
| FR-STR-17 | ราคาระหว่างแท่งส่งให้ Strategy แบบรวบ: ราคาล่าสุดของแต่ละ Symbol **ไม่เกิน 1 ครั้งต่อวินาที** (ปรับค่าได้) และส่งเฉพาะ Symbol ที่ Bot ใช้ (**Decided D-18**) |
| FR-STR-18 | Strategy ใช้ Last Price ในการตัดสินใจ ส่วน Liquidation และ Unrealized PnL ของ Futures ใช้ Mark Price (FR-MRG-04) (**Decided D-18**) |

### 2.10 Portfolio Risk Management
| ID | Requirement |
|---|---|
| FR-RSK-01 | กำหนด Risk Rule ต่อ Portfolio ได้ |
| FR-RSK-02 | ตัวอย่าง Risk Rule (**Proposed**, ชุดสุดท้ายต้องยืนยัน): max leverage, max position notional ต่อ Symbol, max total exposure, max open positions, max daily loss, max drawdown, max order size, order rate limit, ต้องมี SL ทุก Order |
| FR-RSK-03 | Kill Switch ระดับ Portfolio (และระดับ User **Proposed**): หยุด Bot ทั้งหมด, ยกเลิก Order ค้าง และเลือกได้ว่าจะปิด Position ด้วยหรือไม่ |
| FR-RSK-04 | เมื่อผิด Risk Rule แบบต่อเนื่อง (เช่นขาดทุนเกิน daily loss) ระบบหยุด Bot อัตโนมัติ |
| FR-RSK-05 | Risk Engine ใช้กับทั้ง Manual และ Bot ทั้ง Paper และ Live (P-02, P-03) |
| FR-RSK-06 | Risk Engine ปฏิเสธ Order Intent ที่ผิดกติกา D-02 เช่น Manual เปิด Position ใน Portfolio ที่มี Active Bot หรือ Bot ที่ไม่ใช่ Active Bot ของ Portfolio ส่ง Order Intent |

### 2.11 Performance Analytics & Portfolio Comparison
| ID | Requirement |
|---|---|
| FR-ANL-01 | แสดง Equity Curve, Realized/Unrealized PnL, Fee, Funding Fee ตามช่วงเวลา |
| FR-ANL-02 | Metrics: Total Return, Max Drawdown, Win Rate, Profit Factor, Average Win/Loss, Sharpe Ratio (**Proposed**) |
| FR-ANL-03 | แยก Analytics ได้ระดับ Portfolio, Bot/Strategy และ Symbol; **ผลระดับ Bot คำนวณจาก Position Episode ที่ Bot นั้นเปิด** (FR-PF-11) ไม่ใช่จาก Order Owner ของแต่ละ Fill; Win Rate และสถิติรายเทรดนับต่อ Episode (**Decided D-02**, ปรับตาม Review 2026-09-22) |
| FR-ANL-04 | เปรียบเทียบหลาย Portfolio ได้ในหน้าเดียว (รวม Paper vs Live) |
| FR-ANL-05 | Metrics คำนวณด้วย deterministic code (P-07) และนิยามสูตรไว้ในเอกสาร |

### 2.12 Live Trading, Source of Truth & Reconciliation
| ID | Requirement |
|---|---|
| FR-LIVE-01 | Binance Execution Adapter รองรับ Spot และ USDⓈ-M Futures บน **Binance.com** (ตลาดที่ใช้พัฒนา) และออกแบบให้เพิ่ม **Binance TH** ได้ภายหลัง (FR-LGL-02) |
| FR-LIVE-02 | รับ Order Update / Account Update แบบ realtime จาก Binance User Data Stream |
| FR-LIVE-03 | Binance เป็น Source of Truth (P-08): Balance, Position, Order Status ที่ถูกต้องคือค่าบน Binance |
| FR-LIVE-04 | Reconciliation (P-09): เทียบ Balance, Position, Open Order, Fill ของระบบกับ Binance ทั้งแบบตามรอบเวลา, หลัง reconnect และหลัง restart |
| FR-LIVE-05 | เมื่อพบความต่าง ระบบต้องแก้ state ภายในให้ตรง Binance, บันทึก event และแจ้ง User |
| FR-LIVE-06 | **การเปลี่ยนแปลงนอกระบบ** (User เทรดหรือตั้งค่าเองใน Binance app) ตรวจพบผ่าน User Data Stream และ Reconciliation; Order ที่ไม่มี Client Order ID ในรูปแบบของระบบถือเป็นนอกระบบ (**Decided D-14**):<br>• **ทุกกรณี:** บันทึก Order/Fill เข้าระบบด้วย Order Owner = `EXTERNAL` ให้ยอดเงินและ PnL ตรงกับ Binance และแจ้ง User<br>• **Portfolio มี Active Bot:** Pause Bot และแจ้ง User<br>• **Portfolio ไม่มี Active Bot:** บันทึกและแจ้งเตือนเท่านั้น<br>• **เปลี่ยน Leverage หรือโหมดบัญชีนอกระบบ:** Pause Bot และแจ้ง User (Leverage เกิน Plan ใช้ FR-PLN-06, 11)<br>• **ฝาก / ถอน / โอนเงินบน Binance:** บันทึกเป็นเงินเข้า/ออก ไม่นับเป็นกำไรหรือขาดทุน (FR-ACC-11)<br>• **เกินวงเงินของ Plan:** ไม่ปิดให้ แต่ห้ามเปิด/เพิ่ม Position จนกว่าจะอยู่ในวงเงิน (FR-PLN-05) |
| FR-LIVE-07 | เมื่อสถานะ Order ไม่แน่นอน (timeout, network error) ห้าม retry แบบสุ่มสี่สุ่มห้า ต้อง query สถานะจริงด้วย Client Order ID ก่อน |
| FR-LIVE-08 | เปิด Live Trading ได้เฉพาะ Workspace ที่ Plan อนุญาต และ User ต้องเปิด 2FA และยอมรับการเปิดเผยความเสี่ยง (risk disclosure) ก่อน (**Decided D-11**) |
| FR-LIVE-09 | ตอนเชื่อม Binance Sub-account ต้องตรวจ Position Mode, Multi-Assets Mode และประเภทบัญชี (Portfolio Margin) ว่าตรงกับที่ระบบรองรับ (**Decided D-03**) |
| FR-LIVE-10 | ถ้าโหมดไม่ตรงและ**ไม่มี** Position/Order ค้าง: แสดงให้ User เห็นและเสนอเปลี่ยนโหมดผ่าน API **เมื่อ User กดยืนยันเท่านั้น** ห้ามเปลี่ยนเองโดยไม่บอก (**Decided D-03**) |
| FR-LIVE-11 | ถ้าโหมดไม่ตรงและ**มี** Position/Order ค้าง: ปฏิเสธการเชื่อม และบอกวิธีแก้ (**Decided D-03**) |
| FR-LIVE-12 | Reconciliation ตรวจโหมดของบัญชีซ้ำเป็นระยะ ถ้าพบว่าถูกเปลี่ยนเป็นโหมดที่ไม่รองรับ (Hedge, Multi-Assets, Portfolio Margin) ให้ Portfolio เข้าสถานะ **Trading Restriction** ตาม FR-LIVE-19, Pause Bot และแจ้ง User (**Decided D-03**, ปรับตาม Review 2026-09-22; การเปลี่ยนแปลงนอกระบบอื่นๆ ดู FR-LIVE-06) |
| FR-LIVE-13 | มี**หน้าแนะนำทีละขั้นตอน**: สร้าง Sub-account, สร้าง API Key, ตั้งสิทธิ์ และตั้ง IP whitelist (**Decided D-04**) |
| FR-LIVE-14 | ตอนเชื่อม Portfolio แบบ Futures ตรวจว่าบัญชีเปิดใช้ Futures แล้ว ถ้ายังไม่เปิดให้ปฏิเสธพร้อมบอกวิธีเปิด (**Decided D-04**) |
| FR-LIVE-15 | Live **ไม่มีการ Transfer ผ่านระบบ** User โอนเงินระหว่างบัญชีบน Binance เอง และระบบอ่านยอดจาก Binance (P-08) (**Decided D-04**) |
| FR-LIVE-16 | ใช้ **Binance Testnet ภายในทีมเท่านั้น** เพื่อทดสอบการส่ง Order, TP/SL, Reconciliation และการเชื่อมบัญชี; **ไม่เปิดให้ User** (User ใช้ Paper) (**Decided D-13**) |
| FR-LIVE-17 | ก่อนเปิด Live และทุกครั้งที่แก้โค้ดส่วนที่ติดต่อ Binance ต้องผ่านการทดสอบบน Testnet (**Decided D-13**) |
| FR-LIVE-18 | ก่อนเปิด Live ให้ User ต้องทดสอบด้วยเงินจริงจำนวนน้อยในบัญชีของเจ้าของระบบก่อน (**Decided D-13**) |
| FR-LIVE-19 | **Trading Restriction:** Portfolio ที่อยู่ในสถานะนี้**ห้ามส่ง Order ทุกชนิดผ่านระบบ** รวมถึง Manual และ reduce-only เพราะ Trading Core คำนวณและส่ง Order ในโหมดที่ไม่รองรับไม่ได้; ทำได้แค่**ยกเลิก Order ค้าง**; ระบบแจ้งให้ User จัดการ Position และเปลี่ยนโหมดกลับบน Binance; เมื่อ Reconciliation ยืนยันว่าโหมดกลับมาถูกต้องและ state ตรงกัน ระบบ**ปลดสถานะอัตโนมัติ** แต่ Bot ยังต้องรอ User สั่ง Resume (**Decided — Review 2026-09-22**) |

### 2.13 Security & API Credential Isolation
| ID | Requirement |
|---|---|
| FR-SEC-01 | API Key/Secret ของ Binance เข้ารหัสก่อนเก็บ (encryption at rest) ด้วย key ที่ไม่อยู่ใน database เดียวกัน (เช่น envelope encryption / KMS) |
| FR-SEC-02 | Secret ถอดรหัสได้เฉพาะ component ที่ส่ง Order จริง (Binance Execution Adapter / worker) API server และ Frontend ห้ามเห็น secret |
| FR-SEC-03 | หลังบันทึกแล้ว ห้ามแสดง Secret กลับไปให้ใครเห็นอีก (แสดงได้แค่ key แบบ masked) |
| FR-SEC-04 | ตรวจ permission ของ API Key ตอนเชื่อม: **ปฏิเสธ Key ที่เปิด Withdrawal**; ปฏิเสธถ้าไม่มีสิทธิ์อ่านข้อมูลหรือสิทธิ์เทรดตาม Market Type ของ Portfolio (Spot หรือ Futures) (**Decided D-04**) |
| FR-SEC-05 | **บังคับ IP whitelist:** API Key ต้องตั้ง IP whitelist เป็น IP ขาออกของระบบ ไม่เช่นนั้นปฏิเสธการเชื่อม; ระบบต้องมี static egress IP ที่แจ้ง User ได้ (NFR-25) (**Decided D-04**) |
| FR-SEC-06 | Credential ผูกกับ Sub-account เดียวและเป็นของ Workspace; การเข้าถึงต้องตรวจสิทธิ์ของ User ใน Workspace นั้นทุกครั้ง (FR-TEN-08) |
| FR-SEC-07 | Audit log สำหรับการเพิ่ม/ลบ/ใช้ Credential และการเปิด Live Trading |
| FR-SEC-08 | ห้าม secret หลุดเข้า log, error message, trace หรือ cache |
| FR-SEC-09 | User ลบ Credential ได้ทันที และระบบหยุดใช้ Credential นั้นทันที |
| FR-SEC-10 | ถ้า API Key เปิดสิทธิ์ Margin ไว้ ให้แจ้งเตือน User ว่าระบบไม่ได้ใช้สิทธิ์นี้และแนะนำให้ปิด แต่ไม่ปฏิเสธการเชื่อม (**Decided D-10**) |
| FR-SEC-11 | **หนึ่งบัญชี Binance เชื่อมได้ที่เดียวในระบบ:** ตรวจจากหมายเลขบัญชี Binance ถ้าบัญชีนี้ถูกเชื่อมกับ Portfolio หรือ Workspace อื่นอยู่แล้ว ปฏิเสธการเชื่อม (**Decided D-04**) |
| FR-SEC-12 | ถ้า API Key เปิดสิทธิ์โอนเงินระหว่างบัญชี (Internal / Universal Transfer) ให้แจ้งเตือนและแนะนำให้ปิด แต่ไม่ปฏิเสธ (**Decided D-04**) |

### 2.14 Pricing Plans
| ID | Requirement |
|---|---|
| FR-PLN-01 | มี Plan: Free / Pro / Advanced |
| FR-PLN-02 | ระบบมี Entitlement model ที่กำหนด limit ต่อ Plan ได้โดยไม่ต้องแก้ code และ Platform Admin ปรับค่าได้ผ่านหน้าจอ Admin (FR-ADM-11) |
| FR-PLN-03 | Entitlement ใน MVP และ**ค่าเริ่มต้น** (Admin ปรับได้ทุกค่า) (**Decided D-11**):<br>• **Leverage สูงสุด (Futures):** Free 5x / Pro 20x / Advanced 50x<br>• **วงเงิน Paper (มูลค่า Position รวม):** 10,000 / 50,000 / 250,000 USDT<br>• **วงเงิน Live (มูลค่า Position รวม):** — / 50,000 / 250,000 USDT<br>• **Live Trading:** ไม่ได้ / ได้ / ได้<br>• **จำนวน Paper Portfolio:** 2 / 5 / 10<br>• **จำนวน Live Portfolio:** — / 3 / 10<br>• **Built-in Strategy, Timeframe, Indicator:** ครบทุก Plan (ระบบรองรับการจำกัด Strategy ตาม Plan ไว้ใช้ภายหลัง) |
| FR-PLN-04 | **วงเงินการเทรด** วัดจาก**มูลค่า Position ที่เปิดอยู่รวมทุก Portfolio ใน Workspace** (Open Notional) แยก Paper และ Live: Futures = Quantity × Mark Price, Spot = มูลค่าเหรียญที่ถือ × Last Price หน่วย USDT (**Decided D-11**) |
| FR-PLN-05 | Risk Engine ปฏิเสธ Order ที่**เปิดหรือเพิ่ม** Position ถ้าทำให้มูลค่ารวมเกินวงเงิน โดย**นับ Order ค้างที่เปิด/เพิ่ม Position ทุกตัวของทุก Portfolio ใน Workspace (Trading Mode เดียวกัน) เป็นการจองวงเงิน** ตามสูตร Calculation §5.2 และตรวจแบบลำดับเดียวต่อ Workspace (ADR-0009); วงเงินคืนเมื่อ Order ถูกปฏิเสธ/ยกเลิก/หมดอายุ/fill; การลด/ปิด Position ทำได้เสมอ; ถ้าราคาขยับจนเกินวงเงิน ไม่บังคับปิดแต่ห้ามเปิด/เพิ่มจนกว่าจะต่ำกว่าวงเงิน (**Decided D-11**, ปรับตาม Review 2026-09-22) |
| FR-PLN-06 | **Leverage สูงสุดตาม Plan** (Futures เท่านั้น): Leverage ที่ใช้ได้ = ค่าต่ำกว่าระหว่างค่าของ Plan กับค่าที่ Binance อนุญาต (Leverage Bracket); ตรวจทั้งตอนตั้ง Leverage และตอนส่ง Order (กรณีตั้งค่านอกระบบ) (**Decided D-11**) |
| FR-PLN-07 | Strategy Parameter ที่เกี่ยวกับ Leverage ถูกจำกัดไม่ให้เกินค่าของ Plan อัตโนมัติ (**Decided D-11**) |
| FR-PLN-08 | วงเงินและ Leverage ตาม Plan ใช้กับ**ทั้ง Paper และ Live** เพื่อให้ทดสอบภายใต้เงื่อนไขเดียวกัน (P-03) (**Decided D-11**) |
| FR-PLN-09 | Entitlement ของ Plan เป็นกฎที่ User ข้ามไม่ได้; Risk Rule ของ Portfolio ตั้งให้เข้มกว่าได้แต่หละหลวมกว่าไม่ได้ (**Decided D-11**) |
| FR-PLN-10 | แสดงการใช้ Entitlement ให้ User เห็นตลอด เช่น "ใช้วงเงินไป 32,000 / 50,000 USDT", Leverage สูงสุดที่ใช้ได้ (**Decided D-11**) |
| FR-PLN-11 | **เมื่อ Workspace เกิน Entitlement** (ลด Plan หรือ Admin ลดค่า): ไม่ลบข้อมูล, ไม่ปิด Position และไม่เปลี่ยน Leverage ให้; Portfolio ส่วนเกินยังดูได้แต่เริ่ม Bot ไม่ได้; Bot ส่วนเกินถูก Pause และแจ้ง User ให้เลือกตัวที่จะเก็บ; ห้ามเปิด/เพิ่ม Position ที่เกินเกณฑ์ (รวม Symbol ที่ Leverage เกิน) จนกว่าจะอยู่ในเกณฑ์; เสียสิทธิ์ Live แล้วยังลด/ปิด Position ได้ (**Decided D-11**) |
| FR-PLN-12 | การเพิ่มค่า Entitlement มีผลทันที; การลดค่าต้องแจ้ง User ล่วงหน้า และทุกการปรับค่าบันทึกใน Audit log (**Decided D-11**) |
| FR-PLN-13 | **Phase 1 ไม่เก็บเงินจริง** Platform Admin กำหนด Plan ให้ Workspace เอง; ไม่มี trial แยกเพราะมี Free; ราคา, ผู้ให้บริการรับชำระเงิน และเวลาเริ่มเก็บเงิน ตัดสินใน **D-21** (**Decided D-11**) |
| FR-PLN-14 | **Order ค้างเมื่อ Entitlement ลดลง** (ลด Plan, Admin ลดค่า): ยกเลิก Order ค้างที่เปิด/เพิ่ม Position ซึ่งทำให้เกินเกณฑ์ใหม่ (วงเงิน, Leverage ของ Symbol, จำนวน Portfolio ที่มี Bot); **เสียสิทธิ์ Live** = ยกเลิก Order ค้างที่เปิด/เพิ่ม Position ทุกตัวใน Live; ทุกกรณี**คง TP/SL และ Order ที่ลด Position ไว้** (**Decided — Review 2026-09-22**) |

### 2.15 Deployment & Non-functional Requirements
| ID | Requirement |
|---|---|
| NFR-01 | ทุก service รันด้วย Docker; ช่วงทดลองรันทั้งระบบบน VM เดียว (เช่น docker compose) ในงบประหยัด |
| NFR-02 | ย้ายไป GCP (Cloud Run + Cloud SQL) ได้โดยไม่ต้องเขียนใหม่ (config ผ่าน environment, stateless API, ไม่ผูกกับ filesystem ของ VM) ตามหลัก NFR-19 ถึง 25 |
| NFR-03 | Trading Core เป็น Python package อิสระ ทดสอบได้โดยไม่ต้องมี FastAPI, database หรือ Binance |
| NFR-04 | การคำนวณเงินใช้ Decimal; ปัดเศษตาม Symbol Filters ของ Binance |
| NFR-05 | Idempotency: Order ทุกตัวมี Client Order ID ที่ไม่ซ้ำ และ retry ต้องไม่ทำให้เกิด Order ซ้ำ |
| NFR-06 | Time sync: เวลาของ server ต้องตรงกับ Binance (Binance ปฏิเสธ request ที่ timestamp ห่างเกิน recvWindow) |
| NFR-07 | Respect Binance rate limits (request weight, order count) ในระดับระบบรวมทุก User |
| NFR-08 | WebSocket ต้อง reconnect อัตโนมัติ และ recover state ได้ (Binance ตัด connection เป็นระยะ) |
| NFR-09 | Audit log แบบ append-only สำหรับ Order, Risk decision, Credential และ Kill Switch |
| NFR-10 | Observability: log, metric และ health check ของ Bot, market data stream และ reconciliation |
| NFR-11 | Backup PostgreSQL ได้ แม้ในโหมด VM เดียว |
| NFR-12 | **Latency:** ส่ง Order Intent ภายใน 1 วินาทีหลังข้อมูลที่ทำให้เกิดสัญญาณเข้ามา (ราคาอัปเดตหรือ Candle ปิด) ใน 95% ของครั้ง และวัดเป็น metric (**Decided D-18**) |
| NFR-13 | **Availability ช่วงทดลอง (VM เดียว):** 99% ต่อเดือน; แจ้ง User ล่วงหน้าเมื่อปิดปรับปรุง (**Decided D-18**) |
| NFR-14 | **Live เมื่อระบบกลับมาทำงาน:** Bot คง**สถานะและเหตุผลการ Pause เดิม**เสมอ; ทำ Reconciliation ก่อน ถ้าตรงกัน **เฉพาะ Bot ที่เป็น `RUNNING` ก่อนระบบหยุด**ทำงานต่อ ถ้าไม่ตรงให้ Pause ด้วยเหตุผล `RECONCILIATION_MISMATCH` และแจ้ง User; Reconciliation ที่ผ่านไม่ใช่เหตุให้ Bot ที่ Pause อยู่กลับมาทำงาน (ต้องให้ User สั่ง Resume ตาม FR-STR-10) (**Decided D-18**, ปรับตาม Review 2026-09-22) |
| NFR-15 | **Paper เมื่อระบบกลับมาทำงาน:** จำลองย้อนหลังด้วย Candle 1m ของช่วงที่ระบบหยุด เพื่อตรวจว่า TP / SL / Liquidation ถูกแตะหรือไม่; **ไม่เปิด Position ใหม่ย้อนหลัง**; ถ้า Candle เดียวแตะทั้ง TP และ SL ให้ถือว่าโดน SL ก่อน (**Decided D-18**) |
| NFR-16 | **เป้าขนาดระบบช่วงทดลอง:** User ใช้งานพร้อมกัน 20, Bot รันพร้อมกัน 100, Symbol 50, VM 4 vCPU / RAM 16 GB — ต้องยืนยันด้วยการทดสอบโหลดจริงก่อนใช้งาน (**Decided D-18**) |
| NFR-17 | **เกณฑ์ย้ายไป GCP:** เมื่อข้อใดข้อหนึ่งเกิดขึ้น: CPU หรือ RAM เกิน 70% ต่อเนื่อง, ต้องการ availability เกิน 99%, หรือก่อนเปิด Live ให้ User ภายนอกจำนวนมาก (**Decided D-18**) |
| NFR-18 | **Data retention:** Candle Timeframe ต่ำกว่า 1h (1m, 5m, 15m, 30m) เก็บ 2 ปี; Candle Timeframe ≥ 1h เก็บตลอดไป (ปรับตาม D-08); Order / Fill / Transfer / Audit log เก็บตลอดอายุ Workspace (หลังลบบัญชีตาม D-17); log ระบบ 30 วัน; log ของ Bot 90 วัน; API Credential ลบทันทีเมื่อ User ลบหรือปิดบัญชี (**Decided D-18**) |
| NFR-19 | **แยก process ตามหน้าที่** แม้รันบน VM เดียว: API, ตัวรับ market data, ตัวรัน Bot, Execution และงานตามรอบ เพื่อย้ายแต่ละส่วนไปรันบนบริการที่เหมาะสมของ GCP ได้ (Cloud portability) |
| NFR-20 | process **สื่อสารกันผ่าน Redis หรือ PostgreSQL** ไม่เรียกกันตรงในหน่วยความจำ; Redis ห้ามเป็นที่เก็บข้อมูลหลัก (Cloud portability) |
| NFR-21 | **ผู้ประมวลผลที่เดียว:** แต่ละ Bot และแต่ละ Portfolio (ฝั่งส่ง Order) มีผู้ประมวลผลได้ที่เดียว ณ เวลาหนึ่ง ด้วยกลไกจองสิทธิ์ (lease) ที่ทำงานได้ทั้งเครื่องเดียวและหลายเครื่อง; ตัวรับ market data จาก Binance มีตัวเดียวต่อ stream (Cloud portability) |
| NFR-22 | **ทุกงานรันซ้ำได้โดยผลไม่ผิด** (idempotent) ทั้ง Order (NFR-05), Reconciliation, Funding Fee, การจำลองย้อนหลัง และงานลบข้อมูลตามระยะเวลา; งานตามรอบเขียนเป็น job ที่สั่งจากภายนอกได้ ไม่ผูกกับ cron ใน process (Cloud portability) |
| NFR-23 | **ไม่เก็บ state ใน disk ของเครื่องหรือในหน่วยความจำ**โดยไม่มีสำเนาภายนอก process ถูกปิดแล้วเริ่มใหม่ได้ทุกเมื่อ; การเชื่อมต่อ WebSocket (ทั้งกับ Binance และกับหน้าจอ User) ต้อง reconnect เองได้ (Cloud portability) |
| NFR-24 | **ใช้เฉพาะ feature ของ PostgreSQL ที่ Cloud SQL รองรับ** (เช่น ไม่ใช้ TimescaleDB; ใช้ partitioning ปกติ) และรองรับ connection pooling (Cloud portability) |
| NFR-25 | **ผู้ให้บริการ key สำหรับเข้ารหัส API Credential** (key ในเครื่อง → Cloud KMS) และ **IP ขาออกคงที่** (VM → Cloud NAT static IP) เปลี่ยนได้ด้วย config; region ต้องเลือกโดยคำนึงถึงการปิดกั้นประเทศของ Binance และ latency (verify ตอน design) (Cloud portability) |

### 2.16 Platform Admin
| ID | Requirement |
|---|---|
| FR-ADM-01 | บัญชี Platform Admin **แยกจากบัญชี User ทั่วไป** และ**บังคับ 2FA**; MVP มี Admin คนเดียว (**Decided D-20**) |
| FR-ADM-02 | จัดการ Built-in Strategy: เปิด/ปิดให้ User เห็น (ตัว Strategy เพิ่มผ่านการเขียนโค้ดและ deploy) (**Decided D-20**) |
| FR-ADM-03 | จัดการ Symbol Whitelist: เพิ่ม, ปิดการเปิด Position ใหม่, นำออก (FR-MKT-13 ถึง 15) (**Decided D-20**) |
| FR-ADM-04 | ปรับค่าระบบ: slippage และ fee rate ของ Paper, เงินเริ่มต้นของ Paper Main Account, ความถี่ในการส่งราคาให้ Strategy (**Decided D-20**) |
| FR-ADM-05 | จัดการ User: ดูรายชื่อ User และสรุปของ Workspace (Plan, จำนวน Portfolio/Bot, สถานะ Bot), เปลี่ยน Plan ของ Workspace, ระงับบัญชี (**Decided D-20**) |
| FR-ADM-06 | **Global Kill Switch:** Pause Bot ทุกตัว; **ยกเลิก Order ค้างที่เปิดหรือเพิ่ม Position** ทุกตัว; **คง TP/SL และ Order ที่ลด Position ไว้**; Risk Engine ปฏิเสธ Order เปิด/เพิ่ม Position ใหม่ทั้งหมด แต่ User ยัง**ลดหรือปิด Position (reduce-only) และแก้ TP/SL ให้เสี่ยงน้อยลง**ได้; **ไม่ปิด Position ของ User** (**Decided D-20**, ปรับตาม Review 2026-09-22) |
| FR-ADM-07 | ดูสถานะของระบบ: market data stream, Reconciliation, latency และภาระของ VM (NFR-10, NFR-16) (**Decided D-20**) |
| FR-ADM-08 | ดูข้อมูลการเทรดของ User ได้แบบ**อ่านอย่างเดียวเพื่อช่วยแก้ปัญหา** และทุกครั้งที่เปิดดูต้องบันทึกใน Audit log; ต้องระบุในนโยบายความเป็นส่วนตัว (เกี่ยวกับ D-17) (**Decided D-20**) |
| FR-ADM-09 | **Admin ห้าม:** เห็น API Secret ของ User, ส่ง Order หรือเทรดแทน User, ปิด Position ของ User, แก้ประวัติ Order / Fill / Audit log; ทุกการกระทำของ Admin บันทึกใน Audit log แบบแก้ไขไม่ได้ (NFR-09) (**Decided D-20**) |
| FR-ADM-10 | มี**หน้าจอ Admin แบบเรียบง่าย**ในระบบ ครอบคลุม FR-ADM-02 ถึง 08 (**Decided D-20**) |
| FR-ADM-11 | ปรับค่า Entitlement ของแต่ละ Plan ผ่านหน้าจอ Admin (Leverage สูงสุด, วงเงิน Paper/Live, จำนวน Portfolio, สิทธิ์ Live) ตามกติกา FR-PLN-11 และ FR-PLN-12 (**Decided D-11**) |

### 2.17 Notification
| ID | Requirement |
|---|---|
| FR-NTF-01 | ช่องทางแจ้งเตือน: **In-app และ Email** ตั้งแต่ Phase 1; **Telegram** ใน Phase 2 ก่อนเปิด Live; LINE อยู่ใน Future (**Decided D-16**) |
| FR-NTF-02 | เรื่องที่ต้องแจ้งอย่างน้อย: Bot ถูก Pause (ทุกสาเหตุ), Order/การเปลี่ยนแปลงนอกระบบ, TP/SL ทำงาน, ใกล้ถูก Liquidate, ถูก Liquidate แล้ว, API Key ใช้ไม่ได้หรือไม่ผ่านการตรวจ, Reconciliation พบความต่าง, Symbol ถูกปิด/delist, การลดค่า Entitlement ล่วงหน้า, Global Kill Switch, การปิดปรับปรุงระบบ (**Decided D-16**) |
| FR-NTF-03 | User เลือกได้ว่าเรื่องไหนแจ้งทางช่องทางไหน (**Decided D-16**) |
| FR-NTF-04 | **เรื่องวิกฤตปิดการแจ้งไม่ได้:** ใกล้ถูก Liquidate, ถูก Liquidate แล้ว, Bot ถูก Pause, API Key ใช้ไม่ได้, Global Kill Switch (**Decided D-16**) |
| FR-NTF-05 | **เตือนก่อนถูก Liquidate** เมื่อ Margin Ratio ถึงเกณฑ์ ค่าเริ่มต้น **80%** User ปรับได้ (**Decided D-16**) |
| FR-NTF-06 | Email ใช้กับเรื่องบัญชี, การเปลี่ยน Plan / Entitlement และการปิดปรับปรุงระบบเสมอ (**Decided D-16**) |

### 2.18 Legal & Target Market
| ID | Requirement |
|---|---|
| FR-LGL-01 | **ตลาดเป้าหมาย: ผู้ใช้ในประเทศไทย** (**Decided D-17**) |
| FR-LGL-02 | **พัฒนาบน Binance.com** เพราะ Binance TH ยังไม่เปิด feature ที่ต้องใช้; ระบบต้องออกแบบให้เพิ่ม **Binance TH** เป็น Exchange Venue ได้ภายหลังโดยไม่ต้องแก้ Trading Core (**Decided D-17**) |
| FR-LGL-03 | Exchange Venue เป็น attribute ของ Exchange Account; Symbol Whitelist, market data, fee rate และ feature ที่เปิดใช้ (เช่น USDⓈ-M Futures) แยกตาม Venue; ตลาดที่ Venue ไม่รองรับต้องปิดใน UI และ Risk Engine (**Decided D-17**) |
| FR-LGL-04 | **ต้องผ่าน legal review** (นักกฎหมาย) **ก่อนเปิด Live** และ**ก่อนเริ่มเก็บเงิน** (D-21) โดยครอบคลุม: ใบอนุญาตภายใต้การกำกับของ ก.ล.ต., การให้บริการผู้ใช้ในไทยบน Binance.com, เงื่อนไข API ของ Binance สำหรับบริการบุคคลที่สาม, PDPA และภาษี; Phase 1 (Paper) ต้องมีเอกสารใน FR-LGL-05 (**Decided D-17**) |
| FR-LGL-05 | เอกสารที่ต้องมี: Terms of Service, Privacy Policy (รวมการที่ Admin ดูข้อมูลได้ตาม FR-ADM-08) และ Risk Disclosure (FR-LIVE-08) (**Decided D-17**) |
| FR-LGL-06 | **ข้อมูลหลังลบบัญชี (ข้อเสนอเริ่มต้น รอนักกฎหมายยืนยัน):** ลบข้อมูลส่วนตัวและ API Credential ทันที; ประวัติการเทรดเก็บแบบไม่ระบุตัวตน (**Decided D-17**) |
| FR-LGL-07 | จำกัดประเทศที่ใช้บริการได้ตามผล legal review และตามประเทศที่ Binance ไม่ให้บริการ (**Decided D-17**) |

### 2.19 Language
| ID | Requirement |
|---|---|
| FR-I18N-01 | UI รองรับ **ภาษาไทยและภาษาอังกฤษ** User สลับภาษาได้และระบบจำค่าที่เลือก (**Decided D-22**) |
| FR-I18N-02 | Email และ Notification ส่งในภาษาที่ User เลือก (**Decided D-22**) |
| FR-I18N-03 | ข้อความทั้งหมดแยกจาก code (ไม่ hard-code) เพื่อเพิ่มหรือแก้คำแปลได้โดยไม่แก้ logic (**Decided D-22**) |
| FR-I18N-04 | ภาษาเริ่มต้นสำหรับ User ใหม่เป็น **ภาษาไทย** เพราะตลาดเป้าหมายคือไทย (**Decided D-22**) |
| FR-I18N-05 | ศัพท์เทรดที่เทรดเดอร์ไทยใช้ทับศัพท์ (เช่น Long, Short, Stop Loss, Take Profit, Leverage, Margin) คงเป็นภาษาอังกฤษใน UI ภาษาไทย ให้ตรงกับ Glossary และ Binance (**Decided D-22**) |
| FR-I18N-06 | เวลาเก็บเป็น UTC และแสดงตามเขตเวลาของ User ค่าเริ่มต้น Asia/Bangkok (**Decided D-22**) |
| FR-I18N-07 | เอกสาร Terms of Service, Privacy Policy และ Risk Disclosure มีทั้งภาษาไทยและอังกฤษ (ฉบับที่มีผลทางกฎหมายตามคำแนะนำของนักกฎหมาย) (**Decided D-22**) |

---

## 3. Ambiguities / Missing Requirements

| ID | ประเด็น | ผลกระทบ | Decision |
|---|---|---|---|
| A-01 | ~~Portfolio กับ Sub-account เป็น 1:1 หรือไม่ และ Portfolio ครอบทั้ง Spot wallet และ Futures wallet หรือแยก~~ **Resolved:** 1 Sub-account = 1 Portfolio = 1 Market Type | กำหนด boundary ของ Margin/Risk/Analytics และ data model ทั้งหมด | D-01 ✅ |
| A-02 | ~~Main Account ใช้เทรดได้หรือเป็นแค่กองกลาง~~ **Resolved:** MVP เป็นกองกลาง, model รองรับการเปิดเทรดภายหลัง | Account hierarchy, Portfolio ของ Main | D-01 ✅ (ทบทวนฝั่ง Live กับ D-04) |
| A-03 | ~~หลาย Bot เทรด Symbol เดียวกันใน Portfolio เดียวได้หรือไม่~~ **Resolved:** Portfolio มี Active Bot ได้ครั้งละ 1 ตัว | Order Manager, Position attribution, Bot analytics | D-02 ✅ |
| A-04 | ~~Position Mode: One-way / Hedge; Multi-Assets Mode, Portfolio Margin~~ **Resolved:** One-way + Single-Asset เท่านั้น | สูตร Liquidation, Order model | D-03 ✅ |
| A-05 | ~~วิธีได้ Binance Sub-account~~ **Resolved:** User เชื่อม API Key ทีละบัญชี; Main Account ใช้เป็น Live Portfolio ได้ 1 Portfolio | Onboarding, Credential model, ความเป็นไปได้ทางธุรกิจ | D-04 ✅ |
| A-06 | ~~ความสมจริงของ Paper fill~~ **Resolved:** Paper Fill Model ใน FR-ORD-06 ถึง 13 | Paper Execution Adapter, ความน่าเชื่อถือของผล Paper | D-05 ✅ |
| A-07 | ~~วิธีสร้าง Strategy: built-in template / config (no-code) / User เขียน Python~~ **Resolved:** Built-in Strategy ที่เจ้าของระบบเขียน, User ปรับ Parameter ได้ในขอบเขต | Security (sandbox), Strategy Engine design, UI | D-06 ✅ |
| A-08 | ~~Backtesting ไม่ได้ระบุ แต่ Strategy Engine มักต้องใช้~~ **Resolved:** ไม่มี Backtesting ในระบบ | Scope, historical data storage | D-07 ✅ |
| A-09 | ~~ชุด Indicator และ Timeframe ใน MVP~~ **Resolved:** FR-CHT-02, FR-CHT-03 | Market data storage, Chart, Strategy | D-08 ✅ |
| A-10 | ~~Chart library และ license~~ **Resolved:** Lightweight Charts | Frontend, ต้นทุน, ระยะเวลาขออนุญาต | D-09 ✅ |
| A-11 | ~~"Long/Short" รวม Spot Margin ด้วยหรือไม่~~ **Resolved:** ไม่รวม Long/Short และ Leverage ใช้กับ Futures เท่านั้น | เพิ่ม Market Type และสูตร margin อีกชุด | D-10 ✅ |
| A-12 | ~~Limit ของแต่ละ Plan, trial, และจะเก็บเงินใน MVP หรือไม่~~ **Resolved:** FR-PLN-03 ถึง 13; ที่ยังเปิด: ราคาและ billing provider | Entitlement, payment integration | D-11 ✅, D-21 |
| A-13 | ~~Tenant = User เดียว หรือ Team/Organization~~ **Resolved:** Workspace เป็น Tenant; MVP มีสมาชิก 1 คนต่อ Workspace | Authorization model | D-12 ✅ |
| A-14 | ~~ใช้ Binance Testnet เป็นขั้นระหว่าง Paper → Live หรือไม่~~ **Resolved:** ใช้ภายในทีมเท่านั้น (FR-LIVE-16 ถึง 18) | Adapter config, test strategy | D-13 ✅ |
| A-15 | ~~Order / Position ที่เกิดนอกระบบ~~ **Resolved:** FR-LIVE-06 | Reconciliation policy, Risk Engine | D-14 ✅ |
| A-16 | ~~Symbol universe และ quote asset~~ **Resolved:** USDT อย่างเดียว, Whitelist (FR-MKT-12 ถึง 16) | Market data load, Risk | D-15 ✅ |
| A-17 | ~~Notification~~ **Resolved:** หัวข้อ 2.17 (FR-NTF-01 ถึง 06) | Integration scope | D-16 ✅ |
| A-18 | ~~ประเทศเป้าหมายของผู้ใช้ และข้อกฎหมาย~~ **Resolved:** ไทย, พัฒนาบน Binance.com, legal review ก่อน Live และก่อนเก็บเงิน (หัวข้อ 2.18) | ความเป็นไปได้ของ Live Trading | D-17 ✅ |
| A-19 | ~~เป้า latency ของ Bot, availability และขนาดระบบบน VM เดียว~~ **Resolved:** ดู NFR-12 ถึง 17 | Infra, process model | D-18 ✅ |
| A-20 | ~~Paper Main Account: เงินเริ่มต้น, asset, reset, เติมเงิน~~ **Resolved:** FR-ACC-07 ถึง 11 | Paper account model | D-19 ✅ |
| A-21 | ~~นิยามเชิงตัวเลขของ "Liquidation ใกล้เคียง Binance"~~ **Resolved:** ข้อมูลเข้าเหมือนกันต้องได้ผลเท่ากัน ยกเว้นการปัดเศษ (FR-MRG-07) | Acceptance criteria ของ FR-MRG | D-05 ✅ |
| A-22 | Data retention — **ระยะเวลาเก็บ Resolved (NFR-18)**; ข้อมูลหลังลบบัญชีมีข้อเสนอเริ่มต้นใน FR-LGL-06 (รอนักกฎหมายยืนยัน); ที่ยังเปิด: สิทธิ์ export ข้อมูลของ User (ให้ legal review กำหนด) | Storage cost, privacy | D-18 ✅, D-17 ✅ |
| A-23 | AI Chart Analysis (Future): ใช้ข้อมูลอะไร ส่งข้อมูล User ไป third-party หรือไม่ | ไม่ block MVP แต่ต้องไม่ละเมิด P-07 | — (Future) |
| A-24 | นิยาม "ไม่มี Position ค้าง" ของ Spot Portfolio (FR-PF-08, FR-PF-09): ถ้า Portfolio ยังถือ Base Asset อยู่ เช่น BTC ที่ซื้อจาก Manual หรือจาก Bot ตัวก่อน นับเป็น Position ที่ต้องปิดก่อนเริ่ม/เปลี่ยน Bot หรือไม่ | Start/Change Bot ของ Spot Portfolio, Attribution | D-02 follow-up (กำหนดตอน design) |
| A-25 | ~~สิทธิ์และขอบเขตของ Platform Admin~~ **Resolved:** หัวข้อ 2.16 (FR-ADM-01 ถึง 10) | Authorization, Security, Admin tooling | D-20 ✅ |
| A-26 | ~~ภาษาของหน้าจอ~~ **Resolved:** ไทยและอังกฤษ (หัวข้อ 2.19) | Frontend, Notification, เอกสารกฎหมาย | D-22 ✅ |

---

## 4. Technical Risks

| ID | Risk | Severity | แนวทางลด (ระดับ requirement) |
|---|---|---|---|
| R-01 | Liquidation / Margin คำนวณไม่ตรง Binance (Leverage Bracket แบบขั้นบันได, Cross ใช้ uPnL ของทุก Position, fee และ funding) | High | ทำ calculation spec แยก, golden test case จากบัญชีจริง, กำหนด tolerance (FR-MRG-07) |
| R-02 | Binance API เปลี่ยน (เช่น endpoint ของ conditional/algo order, rate limit, stream format) | High | เก็บทุก Binance-specific logic ไว้ใน adapter; verify API docs ตอน design; contract test |
| R-03 | Rate limit / IP ban เพราะทุก User ใช้ egress IP เดียวกัน | High | ใช้ market data stream ชุดเดียวแจกทุก User (FR-CHT-07), global rate limiter (NFR-07) |
| R-04 | API Credential รั่ว | Critical | FR-SEC-01..09; ไม่รับ Key ที่เปิด withdrawal; แยก process ที่ถอดรหัสได้ |
| R-05 | State drift ระหว่างระบบกับ Binance (missed event, disconnect, restart) | High | Reconciliation (FR-LIVE-04), Binance เป็น Source of Truth |
| R-06 | Duplicate order จาก retry / timeout | High | Client Order ID + query-before-retry (NFR-05, FR-LIVE-07) |
| R-07 | Precision error จาก float และการปัดเศษผิด Symbol Filters | Medium | Decimal ทั้งระบบ (NFR-04) |
| R-08 | ~~Multi-bot ใน Portfolio เดียวชนกันบน net position / leverage~~ | ~~High~~ → Low | ลดแล้วด้วย D-02 (Active Bot ครั้งละ 1 ตัว) และบังคับที่ Risk Engine (FR-RSK-06) |
| R-17 | ฝั่ง Live ต้องใช้ Binance Sub-account มากขึ้น (1 Bot ที่รันพร้อมกัน = 1 Sub-account) ติดเพดานจำนวน Sub-account และต้องสร้าง API Key ทีละ Sub-account | Medium | พิจารณาใน D-04 และ D-11; UI ช่วยแนะนำขั้นตอนเชื่อม Sub-account |
| R-18 | ย้ายไป Cloud Run + Cloud SQL แล้วติดปัญหา: process ที่ต้องทำงานตลอด (market data, Bot, User Data Stream) ถูกปิด/ขยาย instance เอง, Bot ถูกรันซ้ำ, connection ของ database เต็ม, IP ขาออกเปลี่ยน, ใช้ extension ที่ Cloud SQL ไม่รองรับ | Medium | ออกแบบตาม NFR-19 ถึง 25 ตั้งแต่ช่วง VM และเลือกบริการสำหรับส่วนที่ทำงานตลอดตอน design |
| R-09 | Paper กับ Live พฤติกรรมต่างกันมาก ทำให้ผล Paper หลอกตา | Medium | Trading Core ร่วมกัน (P-03), Paper Fill Model แบบไม่ดูดีเกินจริง (D-05 ✅), ทดสอบ Binance Execution Adapter บน Testnet ก่อน Live (D-13 ✅); ส่วนที่ยังต่างจากจริง: Order ขนาดใหญ่ได้ราคาดีเกินจริง, ไม่มี partial fill / ADL, Fee ไม่ตรงกับ VIP สูงหรือส่วนลด BNB |
| R-10 | VM เดียว: resource contention (market data + bot + API + DB) และ single point of failure; ภาระสูงขึ้นเพราะ Strategy ดูราคาระหว่างแท่ง (D-18) | Medium | แยก process ตามหน้าที่, backup, health check, ส่งราคาแบบรวบ (FR-STR-17), ทดสอบโหลดตาม NFR-16 และย้ายตามเกณฑ์ NFR-17 |
| R-11 | ปริมาณ market data (หลาย Symbol × หลาย Timeframe) โตเร็ว | Medium | Whitelist ไม่เกิน 50 Symbol (D-15 ✅), retention policy (NFR-18) |
| R-12 | ~~User-code Strategy รันโค้ดไม่ปลอดภัยบน server~~ | ~~Critical~~ → ไม่มีใน MVP | ตัดออกด้วย D-06 (มีเฉพาะ Built-in Strategy); ถ้าอนาคตเปิดให้ User เขียนโค้ด ต้องประเมินใหม่และมี sandbox แยก |
| R-13 | ข้อกฎหมาย / ToS สำหรับการให้บริการ trading bot และจัดการ API Key ของผู้อื่น รวมถึงการให้บริการผู้ใช้ในไทยบน Binance.com | High | Legal review ก่อนเปิด Live และก่อนเก็บเงิน (D-17 ✅); รองรับ Binance TH (FR-LGL-02) |
| R-19 | Binance TH มี API, Symbol, feature (เช่น Futures) หรือกติกาต่างจาก Binance.com ทำให้ย้ายหรือรองรับเพิ่มได้ยาก | Medium | แยก Exchange Venue ตั้งแต่ต้น (FR-LGL-02, 03); verify API ของ Binance TH เมื่อเปิด feature |
| R-14 | Bot ทำงานผิดพลาดใน Live แล้วเสียเงินจริง | High | Risk Engine บังคับ (P-02), Kill Switch, เปิด Live แบบ gated (FR-LIVE-08) |
| R-15 | Clock drift ทำให้ Binance ปฏิเสธ request | Low | Time sync (NFR-06) |
| R-16 | TP/SL ไม่ผูกกันเป็น OCO ใน Futures ทำให้เหลือ Order ค้างหลังปิด Position | Medium | Order Manager จัดการ Bracket lifecycle (FR-ORD-03) |

---

## 5. Scope: MVP vs Future

> ทั้ง Section นี้เป็น **Proposed** — ขึ้นกับ Decisions ที่อ้างถึง

### 5.1 MVP Phase 1 — Paper Trading
| Area | In scope |
|---|---|
| Tenancy | Multi-user, auth, Workspace ส่วนตัว 1 คนต่อ Workspace (D-12 ✅), Plan + Entitlement ผูกกับ Workspace บังคับวงเงิน/Leverage/จำนวน Portfolio/สิทธิ์ Live โดยยังไม่เก็บเงิน (D-11 ✅), หน้าจอ Platform Admin และ Global Kill Switch (D-20 ✅) |
| Account | Paper Main Account (กองกลาง, เริ่ม 10,000 USDT), Virtual Sub-account, Transfer, เติมเงิน, Reset Portfolio (D-19 ✅) |
| Portfolio | 1 Virtual Sub-account = 1 Portfolio = 1 Market Type (D-01 ✅); Balance, Position, Margin, PnL, Risk, Liquidation แยกต่อ Portfolio; หลาย Symbol / Timeframe; Active Bot ครั้งละ 1 ตัว (D-02 ✅) |
| Markets | Spot + USDⓈ-M Futures (One-way Mode, Single-Asset Mode — D-03 ✅); USDT เท่านั้น, Symbol Whitelist ~30 ตัว (D-15 ✅) |
| Manual Trading | Market / Limit, Entry / TP / SL, Long / Short, Leverage, Cross / Isolated |
| Calculation | Deterministic Margin / PnL / Liquidation / Fee / Funding Fee พร้อม golden tests; Paper Fill Model ตาม D-05 ✅ |
| Order Pipeline | Order Intent → Risk Engine → Order Manager → Paper Execution Adapter; interface ของ Execution Adapter ออกแบบให้รองรับ Binance ตั้งแต่ต้น |
| Market Data | Binance public market data (ไม่ต้องใช้ API Key), realtime + history |
| Chart | Trading Terminal ด้วย Lightweight Charts, Timeframe 7 ค่า, Indicator 7 ตัว, ป้าย Buy/Sell, เส้น Entry/TP/SL/Liquidation (D-08 ✅, D-09 ✅) |
| Strategy / Bot | Strategy Engine + Built-in Strategy ที่เจ้าของระบบเขียน, User ปรับ Parameter ได้ในขอบเขต (D-06 ✅), start/stop/pause/resume Bot, กติกา Active Bot และ Manual ตาม D-02 |
| Risk | Portfolio Risk Rule ชุดพื้นฐาน + Kill Switch |
| Analytics | Metric พื้นฐาน + เปรียบเทียบ Portfolio |
| Notification | แจ้งเตือนในระบบ (In-app) และ Email, ตั้งค่าการแจ้งเตือนรายเรื่อง, เตือนก่อนถูก Liquidate (D-16 ✅) |
| Language | UI, Email และ Notification รองรับภาษาไทยและอังกฤษ (D-22 ✅) |
| Security | Auth, tenant isolation, audit log; **ออกแบบ Credential Vault ไว้แล้วแม้ยังไม่ใช้** (P-10) |
| Infra | Docker, VM เดียว |

### 5.2 MVP Phase 2 — Live Trading
| Area | In scope |
|---|---|
| Credential | Credential Vault, เชื่อมบัญชี Binance ทีละบัญชีด้วย API Key ของบัญชีนั้น, หน้าแนะนำขั้นตอน, ตรวจ Key (FR-SEC-04, 05, 11, 12; FR-LIVE-13 ถึง 15) (D-04 ✅) |
| Account | Binance Main Account ใช้เป็น Live Portfolio ได้ 1 Portfolio (D-04 ✅); ไม่มี Transfer ผ่านระบบใน Live |
| Execution | Binance Execution Adapter (Spot + USDⓈ-M), User Data Stream |
| Consistency | Reconciliation, Source of Truth handling, การจัดการ Order และการเปลี่ยนแปลงนอกระบบ (D-14 ✅) |
| Safety | Live gating (2FA, disclosure), แจ้งเตือนผ่าน Telegram (D-16 ✅) |
| Pre-Live | ทดสอบบน Binance Testnet ภายในทีม แล้วทดสอบด้วยเงินจริงจำนวนน้อยในบัญชีของเจ้าของระบบ (D-13 ✅), legal review ก่อนเปิด Live (D-17 ✅) |

### 5.3 Future Scope
- AI Chart Analysis (ต้องไม่ใช้ AI คำนวณตัวเลขทางการเงิน ตาม P-07)
- Billing / payment และการเก็บเงินจริง (D-11, รายละเอียดตาม D-21)
- วิธีให้ User สร้าง Strategy เอง (ไม่อยู่ใน MVP ตาม D-06 และยังไม่ได้ตัดสินว่าจะทำหรือไม่): รับสัญญาณผ่าน Webhook เช่น TradingView Alert, No-code Rule Builder, User เขียน Python (ต้องมี sandbox)
- Portfolio ที่รวม Spot + Futures ใน Sub-account เดียว (เช่น hedge, cash-and-carry) และ Sub-account ที่มีหลาย Portfolio (D-01)
- Paper Main Account ที่มี Portfolio และเทรดได้ (D-01; ฝั่ง Live เปิดแล้วใน D-04)
- สร้าง Sub-account ให้ User อัตโนมัติ (ผ่าน Master Key หรือ Binance Broker program) และ Transfer ผ่านระบบใน Live (D-04 — ต้องประเมินความปลอดภัยและกฎหมายใหม่)
- หลาย Active Bot ใน Portfolio เดียว (เช่น กติกาเจ้าของ Symbol หนึ่งรายต่อ Portfolio) และการกำหนดงบเงินทุนต่อ Bot (D-02)
- Hedge Mode, Multi-Assets Mode, Portfolio Margin (D-03 — ไม่อยู่ใน MVP; Portfolio Margin ต้องทบทวน D-01 ก่อนเพราะขัดกัน)
- Spot Margin — ความสำคัญต่ำ ทบทวนหลัง Live Trading เสถียรและมีผู้ใช้ต้องการ (D-10); COIN-M Futures, Options
- Quote Asset อื่นนอกจาก USDT เช่น USDC (D-15)
- แจ้งเตือนผ่าน LINE (LINE Messaging API) (D-16)
- รองรับ **Binance TH** เป็น Exchange Venue เมื่อเปิด feature ที่ต้องใช้ (D-17)
- Exchange อื่นนอกจาก Binance
- Workspace ที่มีหลายสมาชิก (ระบบทีม): การเชิญ/ออกจาก Workspace และ Role เช่น Owner / Trader / Viewer (D-12 — ยังไม่ได้กำหนด Role; ต้องผ่าน legal review ตาม FR-LGL-04)
- Copy trading / social / marketplace ของ Strategy
- เครื่องมือวาดเส้นบน Chart (trend line, แนวรับแนวต้าน) — อาจพิจารณา TradingView Advanced Charts (D-09)
- เพิ่ม / ลด margin ของ isolated Position (Calculation spec C-10)
- Mobile app
- ย้ายไป GCP: Cloud Run + Cloud SQL, Memorystore, Cloud KMS, Cloud NAT (static egress IP), Cloud Scheduler + Cloud Run Jobs และ scale-out

---

## 6. Domain Glossary (Ubiquitous Language)

> กติกา: ใช้ **Term** ตามตารางนี้ใน code (class, field, enum), API, database, UI และเอกสาร ห้ามใช้ synonym ใน column "ห้ามใช้"
> ค่า enum เขียนเป็น `UPPER_SNAKE_CASE`

### 6.1 Tenancy
| Term | นิยาม | ห้ามใช้ / หมายเหตุ |
|---|---|---|
| User | บุคคลที่มีบัญชีเข้าระบบ TiewTrade | "Customer" |
| Workspace | ขอบเขตการแยกข้อมูล (Tenant) เป็นเจ้าของข้อมูลทั้งหมดและ Plan; MVP มีสมาชิก 1 คน (D-12) | "Tenant" (ใช้ได้เฉพาะเป็นคำอธิบายเชิง architecture), "Organization", "Team", "Account" |
| Workspace Member | User ที่เป็นสมาชิกของ Workspace; MVP มีได้ 1 คนต่อ Workspace | "Member" ลอยๆ |
| Platform Admin | เจ้าของ/ผู้ดูแลระบบ TiewTrade อยู่นอกทุก Workspace ใช้บัญชีแยกและบังคับ 2FA; สิทธิ์ตาม FR-ADM (D-20) | "Admin" ลอยๆ, "Superuser" |
| Plan | ระดับบริการ `FREE` / `PRO` / `ADVANCED` ผูกกับ Workspace | "Tier", "Package" |
| Entitlement | สิทธิ์/limit ที่ได้จาก Plan เช่น Leverage สูงสุด, วงเงินการเทรด, จำนวน Portfolio สูงสุด (D-11) | "Quota" (ใช้ได้เฉพาะในบริบท rate limit) |
| Open Notional | มูลค่า Position ที่เปิดอยู่รวมทุก Portfolio ใน Workspace ใช้วัดวงเงินการเทรดตาม Plan (D-11) | "Exposure" (ใช้ได้เป็นคำอธิบาย), "Volume" (Volume คือปริมาณซื้อขาย) |

### 6.2 Account
| Term | นิยาม | ห้ามใช้ / หมายเหตุ |
|---|---|---|
| Trading Mode | `PAPER` หรือ `LIVE` | "Demo", "Simulation", "Real" |
| Exchange Account | บัญชีระดับบนสุดของ User ในแต่ละ Trading Mode (Binance Main Account หรือ Paper Main Account) | |
| Exchange Venue | ตลาดของ Binance ที่ระบบเชื่อมต่อ: `BINANCE_COM` (ใช้พัฒนา) หรือ `BINANCE_TH` (อนาคต) แต่ละ Venue มี API, Symbol และ feature ของตัวเอง (D-17) | "Exchange" ลอยๆ เมื่อหมายถึง Binance.com หรือ Binance TH |
| Main Account | Exchange Account ระดับบนสุดที่มี Sub-account อยู่ภายใต้; Paper: กองกลาง ไม่มี Portfolio (D-01); Live: ใช้เป็น Portfolio ได้ 1 Portfolio (D-04) | "Master Account" (ใช้ได้เฉพาะตอนอ้างถึงเอกสาร Binance) |
| Sub-account | บัญชีย่อยภายใต้ Main Account; เป็นขอบเขตของ wallet, margin และ liquidation | "Subaccount", "Child account" |
| Binance Main Account | Main Account จริงบน Binance (`LIVE`) | |
| Binance Sub-account | Sub-account จริงบน Binance (`LIVE`) | |
| Paper Main Account | Main Account จำลองในระบบ (`PAPER`) | "Demo account" |
| Virtual Sub-account | Sub-account จำลองในระบบ (`PAPER`) | "Paper sub", "Fake account" |
| Virtual Deposit | การเติมเงินจำลองเข้า Paper Main Account; นับเป็นเงินทุนที่เข้ามา ไม่ใช่กำไร (D-19) | "Top-up" |
| Portfolio Reset | การเก็บ Portfolio (Paper) เดิมเป็นประวัติอ่านอย่างเดียว แล้วเริ่ม Portfolio ใหม่ด้วยเงินตั้งต้น (D-19) | "Restart", "Clear" |
| Wallet | ยอดเงินของ Sub-account แยกตาม Market Type (Spot wallet, USDⓈ-M Futures wallet) | |
| Transfer | การย้าย asset ระหว่าง Main Account ↔ Sub-account หรือระหว่าง Wallet; Live ทำบน Binance เอง ไม่ผ่านระบบ (D-04) | "Deposit"/"Withdraw" (หมายถึงเงินเข้า/ออก exchange เท่านั้น) |
| API Credential | API Key + Secret ของ Binance ที่ผูกกับ Sub-account หรือ Main Account หนึ่งตัว | "Token", "Keys" |
| Credential Vault | ส่วนที่เก็บและถอดรหัส API Credential | |

### 6.3 Market
| Term | นิยาม | ห้ามใช้ / หมายเหตุ |
|---|---|---|
| Market Type | `SPOT` หรือ `USDM_FUTURES` | "Product", "Exchange type" |
| Symbol | คู่เทรดตามชื่อ Binance เช่น `BTCUSDT` ต้องระบุคู่กับ Market Type เสมอ | "Pair", "Ticker", "Instrument" |
| Symbol Whitelist | รายการ Symbol ที่ Platform Admin เปิดให้เทรดในระบบ (D-15) | "Market list" |
| Base Asset / Quote Asset | เช่น `BTC` / `USDT` ใน `BTCUSDT` | |
| Symbol Filters | กติกา tickSize, stepSize, minNotional, min/max qty ของ Symbol | |
| Last Price | ราคาซื้อขายล่าสุด | |
| Best Bid / Best Ask | ราคาเสนอซื้อสูงสุด / ราคาเสนอขายต่ำสุด ณ ขณะนั้น; ใช้เป็นราคา fill ของ Market Order ใน Paper (D-05) | "Bid/Ask" ลอยๆ ในความหมายอื่น |
| Slippage | ส่วนต่างระหว่างราคาที่คาดกับราคาที่ fill จริง; ใน Paper เป็นค่าคงที่ที่ Platform Admin ตั้ง (D-05) | |
| Mark Price | ราคาอ้างอิงที่ Binance ใช้คำนวณ Unrealized PnL และ Liquidation (Futures) | |
| Index Price | ราคาดัชนีจากหลาย exchange ที่ใช้คำนวณ Mark Price | |
| Funding Rate | อัตรา funding ของ Futures ในแต่ละรอบ | |
| Market Data Feed | แหล่งข้อมูลราคาและ Candle ที่แจกจ่ายภายในระบบ | |

### 6.4 Portfolio & Margin
| Term | นิยาม | ห้ามใช้ / หมายเหตุ |
|---|---|---|
| Portfolio | หน่วยของเงินทุน ความเสี่ยง และผลลัพธ์; 1 Sub-account = 1 Portfolio = 1 Market Type ใช้เฉพาะ Wallet ของ Market Type นั้น (D-01) | "Account" (ห้ามใช้แทน Portfolio), "Fund" |
| Wallet Balance | ยอดเงินใน wallet ไม่รวม Unrealized PnL | |
| Unrealized PnL | กำไร/ขาดทุนของ Position ที่ยังเปิดอยู่ คิดจาก Mark Price (Futures) | "Floating PnL", "uPnL" (ใช้ได้แค่ในสูตร) |
| Realized PnL | กำไร/ขาดทุนที่เกิดจากการปิด Position ไม่รวม Fee และ Funding Fee (แสดงแยก) | |
| Margin Balance | Wallet Balance + Unrealized PnL | |
| Available Balance | ยอดที่ใช้เปิด Order/Position ใหม่ได้ | "Free balance" |
| Equity | มูลค่ารวมของ Portfolio ที่ใช้ทำ Equity Curve (นิยามละเอียดต่อ Market Type ใน calculation spec) | "NAV" |
| Position | ปริมาณที่ถืออยู่ของ Symbol หนึ่งใน Portfolio (Futures) | "Trade" (Trade ≠ Position) |
| Position Side | `LONG` หรือ `SHORT` | "Buy position", "Sell position" |
| Position Mode | `ONE_WAY` หรือ `HEDGE`; MVP รองรับเฉพาะ `ONE_WAY` (D-03) | |
| Margin Asset Mode | `SINGLE_ASSET` หรือ `MULTI_ASSETS`; MVP รองรับเฉพาะ `SINGLE_ASSET` (D-03) | "Multi-collateral" |
| Margin Mode | `CROSS` หรือ `ISOLATED` ของ USDⓈ-M Futures เท่านั้น (ใน MVP ไม่มี Spot Margin ตาม D-10 จึงไม่มีความหมายอื่น) | "Margin type" (ยกเว้นใน adapter ที่ map กับ Binance) |
| Leverage | ตัวคูณที่ตั้งต่อ Symbol ต่อ Sub-account | |
| Notional | Quantity × Price ของ Position/Order | "Size" (Size หมายถึง Quantity เท่านั้น) |
| Quantity | จำนวนหน่วยของ Base Asset | |
| Initial Margin | margin ที่ต้องใช้เปิด Position = Notional / Leverage | |
| Maintenance Margin | margin ขั้นต่ำที่ต้องรักษาไว้ ก่อนถูก Liquidation | |
| Maintenance Margin Rate | อัตราที่ใช้คำนวณ Maintenance Margin ตาม Leverage Bracket | "MMR" (ใช้ได้แค่ในสูตร) |
| Leverage Bracket | ตารางขั้นบันไดของ Binance ที่กำหนด max leverage และ Maintenance Margin Rate ตาม Notional | "Tier" |
| Margin Ratio | Maintenance Margin / Margin Balance (นิยามตาม Binance) | |
| Liquidation Price | Mark Price ที่ทำให้ Position ถูก Liquidation | "Liq price" ใน code |
| Liquidation | เหตุการณ์ที่ Position ถูกปิดบังคับเพราะ margin ไม่พอ | |
| Fee | ค่าธรรมเนียมการเทรด (maker/taker) | "Commission" (ยกเว้นใน adapter) |
| Funding Fee | เงินที่จ่าย/รับจาก Funding Rate ของ Position ที่ถืออยู่ | |

### 6.5 Order
| Term | นิยาม | ห้ามใช้ / หมายเหตุ |
|---|---|---|
| Order Intent | คำขอเปิด/ปิด/แก้ Order จาก UI หรือ Strategy **ก่อน** ผ่าน Risk Engine | "Signal" (Signal ≠ Order Intent) |
| Order | คำสั่งที่ผ่าน Risk Engine แล้วและ Order Manager เป็นผู้ดูแล | |
| Order Side | `BUY` หรือ `SELL` | ห้ามใช้แทน Position Side |
| Order Type | `MARKET`, `LIMIT`, `STOP_MARKET`, `TAKE_PROFIT_MARKET` ฯลฯ (ชุดสุดท้ายกำหนดตอน design) | |
| Order Status | `NEW`, `PARTIALLY_FILLED`, `FILLED`, `CANCELED`, `REJECTED`, `EXPIRED` | |
| Time in Force | `GTC`, `IOC`, `FOK` (ชุดที่รองรับกำหนดตอน design) | |
| Reduce-only | Order ที่ลด Position ได้อย่างเดียว | |
| Bracket Order | กลุ่มของ Entry Order + Take Profit + Stop Loss ที่ผูกกัน | "OCO" (OCO คือ Order Type ของ Spot เท่านั้น) |
| Entry | Order ที่เปิดหรือเพิ่ม Position | |
| Take Profit (TP) | Order ปิด Position เมื่อได้กำไรถึงระดับที่ตั้ง | |
| Stop Loss (SL) | Order ปิด Position เมื่อขาดทุนถึงระดับที่ตั้ง | |
| Fill | การจับคู่สำเร็จ (บางส่วนหรือทั้งหมด) ของ Order หนึ่งครั้ง | "Execution", "Trade" (ใช้ได้แค่ใน adapter) |
| Client Order ID | ID ที่ระบบสร้างเองให้ Order เพื่อ idempotency และ reconciliation | |
| Exchange Order ID | ID ที่ Binance หรือ Paper Execution Adapter ออกให้ | |

### 6.6 System Components
| Term | นิยาม | ห้ามใช้ / หมายเหตุ |
|---|---|---|
| Trading Core | Python package อิสระ ที่รวม domain logic: Portfolio, Margin, Risk Engine, Order Manager, Strategy Engine | "Engine" ลอยๆ |
| Risk Engine | ตรวจ Order Intent กับ Risk Rule แล้วคืน Risk Check Result | "Risk Manager" |
| Risk Rule | กฎความเสี่ยงหนึ่งข้อของ Portfolio | "Risk limit" (ใช้ได้เฉพาะในความหมายค่าตัวเลขของ Risk Rule) |
| Risk Check Result | ผลตรวจ: `APPROVED` / `REJECTED` + เหตุผล | |
| Order Manager | ดูแล lifecycle ของ Order และ Bracket Order, idempotency | "Order Router", "OMS" (ใช้ได้เฉพาะเป็นคำอธิบาย) |
| Execution Adapter | interface ที่ส่ง Order ไปยังที่ fill จริง | "Broker", "Connector" |
| Paper Execution Adapter | Execution Adapter ที่จำลอง fill ในระบบ | "Simulator" |
| Binance Execution Adapter | Execution Adapter ที่ส่ง Order ไป Binance | "Binance client" (หมายถึงแค่ HTTP client ระดับล่าง) |
| Reconciliation | กระบวนการเทียบและแก้ state ภายในให้ตรง Source of Truth | "Sync" |
| Source of Truth | แหล่งข้อมูลที่ถือว่าถูกต้องเมื่อขัดแย้ง; Live = Binance, Paper = Trading Core | |
| Kill Switch | คำสั่งหยุดฉุกเฉินระดับ Portfolio: หยุด Bot, ยกเลิก Order และเลือกปิด Position ได้ | "Panic button" |
| Global Kill Switch | คำสั่งฉุกเฉินของ Platform Admin: Pause Bot ทุกตัวและหยุดรับ Order ใหม่ทั้งระบบ **ไม่ปิด Position** (D-20) | "Kill Switch" ลอยๆ เมื่อหมายถึงทั้งระบบ |

### 6.7 Strategy & Chart
| Term | นิยาม | ห้ามใช้ / หมายเหตุ |
|---|---|---|
| Candle | แท่งราคา OHLCV ของ Symbol ใน Timeframe หนึ่ง | "Kline", "Bar" (Kline ใช้ได้ใน Binance adapter เท่านั้น) |
| Timeframe | ช่วงเวลาของ Candle; รองรับ `1m`, `5m`, `15m`, `30m`, `1h`, `4h`, `1d` (D-08) | "Interval", "Resolution" (ยกเว้นใน adapter/chart library) |
| Indicator | ค่าที่คำนวณจาก Candle เช่น EMA, RSI; สูตรต้นแบบอยู่ใน Trading Core (D-08) | |
| Trade Marker | ป้าย Buy / Sell บน Chart ที่แสดงจุด Fill ของ Portfolio (D-08) | "Arrow", "Signal marker" |
| Strategy | logic ที่รับ market/portfolio data แล้วส่ง Signal / Order Intent (เป็น definition ยังไม่รัน) | "Algo", "Bot" (Strategy ≠ Bot) |
| Built-in Strategy | Strategy ที่เจ้าของระบบเขียนและเปิดให้ User เลือกใช้; ใน MVP มีเฉพาะแบบนี้ (D-06) | "Template" (ใช้เป็นคำอธิบายได้ แต่ไม่ใช้ใน code) |
| Strategy Parameters | ค่าของ Strategy เช่น ระยะ EMA, % SL/TP | "Settings" |
| Strategy Parameter Schema | นิยามของ Parameter แต่ละตัว: ชนิด, ค่าต่ำสุด/สูงสุด, ค่าเริ่มต้น และ User ปรับได้หรือถูกล็อก (D-06) | |
| Strategy Version | เวอร์ชันของ Built-in Strategy ที่ Bot บันทึกไว้ (D-06) | |
| Bot | instance ที่รัน Strategy ผูกกับ Portfolio + Symbol(s) + Timeframe(s) + Strategy Parameters | "Robot", "Agent" |
| Active Bot | Bot ที่ครอบครอง Portfolio อยู่ ณ ขณะนั้น (Status ไม่ใช่ `STOPPED`) Portfolio หนึ่งมีได้ไม่เกิน 1 ตัว (D-02) | |
| Bot Status | `RUNNING`, `PAUSED`, `STOPPED`, `ERROR` (ชุดสุดท้ายกำหนดตอน design); `PAUSED` ใช้รวมถึงกรณีที่ Manual เข้าแทรก (FR-STR-10) | |
| Signal | ผลการตัดสินของ Strategy (เช่น enter long) ก่อนแปลงเป็น Order Intent | |
| Order Owner | ผู้สร้าง Order: Bot ID, `MANUAL` หรือ `EXTERNAL` (Order ที่เกิดนอกระบบ) บันทึกในทุก Order และ Fill (D-02, D-14) | "Source", "Creator" |
| Attribution | การระบุว่าผล (PnL, Fee, Funding) เป็นของ Bot ไหน คำนวณจาก **Position Episode** ไม่ใช่ Order Owner (FR-PF-11) | |
| Position Episode | ช่วงชีวิตของ Position ของ Symbol หนึ่งตั้งแต่เปิดจากศูนย์จนกลับเป็นศูนย์ ผลทั้งหมดเป็นของผู้ที่เปิด (FR-PF-11) | "Trade" (ใช้ได้ใน UI เป็นคำอธิบาย) |
| Trading Restriction | สถานะของ Portfolio ที่ห้ามส่ง Order ผ่านระบบเพราะบัญชีอยู่ในโหมดที่ไม่รองรับ (FR-LIVE-19) | "Locked", "Frozen" |
| Chart Workspace | layout ของหน้า Trading Terminal ที่ User บันทึกได้ (**Proposed**) | |

### 6.8 Analytics
| Term | นิยาม | ห้ามใช้ / หมายเหตุ |
|---|---|---|
| Equity Curve | อนุกรมเวลาของ Equity | |
| Drawdown / Max Drawdown | การลดลงจากจุดสูงสุดของ Equity / ค่าสูงสุดของการลดลงนั้น | |
| Win Rate | สัดส่วน closed trade ที่กำไร (นิยาม "closed trade" ต้องกำหนดใน analytics spec) | |
| Profit Factor | กำไรรวม / ขาดทุนรวม | |
| Sharpe Ratio | ผลตอบแทนต่อความผันผวน (กำหนด risk-free rate และความถี่ใน spec) | |
| Performance Snapshot | ค่า metric ของ Portfolio / Bot ณ เวลาหนึ่ง ที่เก็บไว้ใช้เปรียบเทียบ | |

---

## 7. Questions / Decisions Needed

**Blocking** = ต้องตัดสินก่อนเริ่ม design ระยะนั้น

| ID | Question | Options (ตัวอย่าง) | ผลกระทบ | Blocking |
|---|---|---|---|---|
| D-01 | ✅ **Decided** — ดู [Decision Log](#71-decision-log) | — | Boundary ของ Margin, Risk, Analytics, data model | ~~Architecture~~ |
| D-02 | ✅ **Decided** — ดู [Decision Log](#71-decision-log) | — | Order Manager, Position model, Bot analytics | ~~Architecture~~ |
| D-03 | ✅ **Decided** — ดู [Decision Log](#71-decision-log) | — | สูตร Liquidation, Order model | ~~Architecture~~ |
| D-04 | ✅ **Decided** — ดู [Decision Log](#71-decision-log) | — | Credential model, onboarding | ~~Phase 2~~ |
| D-05 | ✅ **Decided** — ดู [Decision Log](#71-decision-log) | — | Paper Execution Adapter, market data ที่ต้องใช้ | ~~Phase 1~~ |
| D-06 | ✅ **Decided** — ดู [Decision Log](#71-decision-log) | — | Strategy Engine, security, UI | ~~Architecture~~ |
| D-07 | ✅ **Decided** — ดู [Decision Log](#71-decision-log) | — | Historical data, Strategy testing | ~~Phase 1~~ |
| D-08 | ✅ **Decided** — ดู [Decision Log](#71-decision-log) | — | Market data storage, Strategy, Chart | ~~Phase 1~~ |
| D-09 | ✅ **Decided** — ดู [Decision Log](#71-decision-log) | — | Frontend, license, feature ของ drawing tools | ~~Phase 1~~ |
| D-10 | ✅ **Decided** — ดู [Decision Log](#71-decision-log) | — | Market Type เพิ่ม, สูตร margin อีกชุด | ~~Architecture~~ |
| D-11 | ✅ **Decided** — ดู [Decision Log](#71-decision-log) | — | Entitlement, Risk Engine | ~~Phase 1~~ |
| D-12 | ✅ **Decided** — ดู [Decision Log](#71-decision-log) | — | Authorization, data isolation | ~~Architecture~~ |
| D-13 | ✅ **Decided** — ดู [Decision Log](#71-decision-log) | — | Adapter configuration, test plan | ~~Phase 2~~ |
| D-14 | ✅ **Decided** — ดู [Decision Log](#71-decision-log) | — | Reconciliation, Risk Engine | ~~Phase 2~~ |
| D-15 | ✅ **Decided** — ดู [Decision Log](#71-decision-log) | — | Market data load, risk | ~~Phase 1~~ |
| D-16 | ✅ **Decided** — ดู [Decision Log](#71-decision-log) | — | Integration | ~~Phase 1, Phase 2~~ |
| D-17 | ✅ **Decided** — ดู [Decision Log](#71-decision-log) | — | ความเป็นไปได้ของ Live, ToS, privacy | ~~Phase 2~~ |
| D-18 | ✅ **Decided** — ดู [Decision Log](#71-decision-log) | — | Process model, infra sizing | ~~Architecture~~ |
| D-19 | ✅ **Decided** — ดู [Decision Log](#71-decision-log) | — | Paper account model, analytics | ~~Phase 1~~ |
| D-20 | ✅ **Decided** — ดู [Decision Log](#71-decision-log) | — | Authorization, security, admin tooling | ~~Phase 1~~ |
| D-21 | ราคาของแต่ละ Plan, ผู้ให้บริการรับชำระเงิน, เวลาเริ่มเก็บเงิน และลูกค้าที่จ่ายแล้วได้เงื่อนไขเดิมต่อเมื่อปรับ Entitlement หรือไม่ (grandfathering) | ราคา: กำหนดภายหลัง; billing: Stripe / ผู้ให้บริการในประเทศ / อื่นๆ; grandfathering: ใช่ / ไม่ | Billing integration, ความเชื่อมั่นของลูกค้า | ก่อนเริ่มเก็บเงินจริง |
| D-22 | ✅ **Decided** — ดู [Decision Log](#71-decision-log) | — | Frontend, Notification | ~~Phase 1~~ |

**ลำดับที่แนะนำในการตัดสิน:** ~~D-01~~ ✅, ~~D-02~~ ✅, ~~D-03~~ ✅, ~~D-06~~ ✅, ~~D-10~~ ✅, ~~D-12~~ ✅, ~~D-18~~ ✅ (block architecture — **ครบแล้ว**) → ~~D-05~~ ✅, ~~D-07~~ ✅, ~~D-08~~ ✅, ~~D-09~~ ✅, ~~D-11~~ ✅, ~~D-15~~ ✅, ~~D-19~~ ✅, ~~D-20~~ ✅ (block Phase 1 — **ครบแล้ว**) → ~~D-04~~ ✅, ~~D-13~~ ✅, ~~D-14~~ ✅, ~~D-16~~ ✅, ~~D-17~~ ✅, D-21 (block Phase 2 / ก่อนเก็บเงิน)

### 7.1 Decision Log

#### D-01 — Portfolio ↔ Sub-account mapping ✅ Decided (2026-09-22)

| ข้อ | Decision |
|---|---|
| 1. Portfolio ครอบอะไร | **1 Sub-account = 1 Portfolio = 1 Market Type** เลือก `SPOT` หรือ `USDM_FUTURES` ตอนสร้าง Portfolio และห้ามเปลี่ยน Portfolio ใช้เฉพาะ Wallet ของ Market Type นั้น |
| 2. Main Account | **MVP: เป็นกองกลาง** ใช้เก็บเงินและ Transfer เท่านั้น ไม่มี Portfolio แต่ model ต้องออกแบบให้ Main Account ผูก Portfolio ได้ในอนาคต ส่วนฝั่ง Live ให้ทบทวนพร้อม D-04 |
| 3. Paper vs Live | **ใช้กติกาเดียวกัน** ทั้งข้อ 1 และข้อ 2 |

**เหตุผล**
- ตรงกับ requirement "แยก Portfolio ตาม Sub-account" แบบ 1:1
- Portfolio หนึ่งตัวมีแหล่ง margin ก้อนเดียว ทำให้ Balance, Margin, Liquidation และ Risk มีความหมายชัดเจน (P-05)
- Risk Rule ใช้ได้ครบทุกข้อ และเปรียบเทียบ Portfolio ได้ยุติธรรม
- ลดความซับซ้อนของสูตรคำนวณ, Paper Execution Adapter และ Reconciliation ใน MVP
- Paper กับ Live ใช้กติกาเดียวกันตาม P-03 เพื่อให้ผล Paper นำไปคาดการณ์ Live ได้

**ผลที่ต้องยอมรับ**
- ผู้ใช้ที่ต้องการเทรดทั้ง Spot และ Futures ต้องใช้ 2 Sub-account (ฝั่ง Binance มีเพดานจำนวน Sub-account)
- กลยุทธ์ที่ถือ Spot คู่กับ Futures ในที่เดียวกัน (hedge, cash-and-carry) ย้ายไป Future Scope
- Live: เงินใน Wallet ที่ Portfolio ไม่ได้ใช้ ต้องแสดงเป็นเงินนอก Portfolio

**สิ่งที่ต้องทำใน design**
- ระบุ Portfolio ด้วยคู่ (Sub-account, Market Type) และบังคับ 1:1 ด้วยกฎแยก เพื่อให้ยกเลิกกฎนี้ในอนาคตได้โดยไม่ต้องรื้อ model
- Main Account และ Sub-account เป็นบัญชีชนิดเดียวกันที่ผูก Portfolio ได้ แต่ใน MVP เปิดใช้เฉพาะ Sub-account

**ผลต่อ Decision อื่น**
- D-02: ปัญหา net position และ Leverage/Margin Mode ร่วมกัน เหลือเฉพาะ Portfolio แบบ `USDM_FUTURES`
- D-04: ต้องตัดสินด้วยว่าจะเปิดให้ Binance Main Account มี Portfolio สำหรับผู้ใช้ที่ไม่มี Sub-account หรือไม่

#### D-02 — Bot ต่อ Portfolio ✅ Decided (2026-09-22)

| ข้อ | Decision |
|---|---|
| 1. จำนวน Bot | **1 Portfolio มี Active Bot ได้ครั้งละ 1 ตัว** Bot ตัวนั้นเทรดได้หลาย Symbol และหลาย Timeframe |
| 2. Manual บน Symbol ที่ Bot ถืออยู่ | **ลดหรือปิด Position และยกเลิก Order ได้** (ใช้กรณีฉุกเฉิน) แล้วระบบ Pause Bot อัตโนมัติ; **เปิดหรือเพิ่ม Position ไม่ได้**; Kill Switch ข้ามกติกาได้เสมอ |
| 3. Manual บน Symbol อื่นใน Portfolio ที่มี Active Bot | **ไม่ได้** Portfolio ที่มี Active Bot ใช้กับ Bot นั้นเท่านั้น ถ้าจะเทรด Manual ให้ใช้ Portfolio ที่ไม่มี Active Bot |
| 4. เปลี่ยน Bot | **ได้** เมื่อ Portfolio ไม่มี Position และ Order ค้าง; ทุก Order/Fill บันทึก Order Owner เพื่อแยกผลย้อนหลัง |

> ตัวเลือกนี้ **เปลี่ยน requirement ต้นฉบับ** "Portfolio รองรับหลาย Strategy, Bot" เป็น "ใช้หลาย Bot/Strategy ได้ตลอดอายุ แต่ active ได้ครั้งละ 1 ตัว"
> ตัวเลือกที่พิจารณาแล้วไม่เลือก: กติกาเจ้าของ Symbol หนึ่งรายต่อ Portfolio (หลาย Bot คนละ Symbol), แบบ Hybrid ที่ตั้งจำนวน Bot สูงสุดต่อ Portfolio ได้, Virtual Position ต่อ Bot

**เหตุผล**
- ง่ายที่สุด: ผลของ Portfolio คือผลของ Bot ทำให้ Analytics และการเปรียบเทียบ Strategy ชัดเจน
- ความเสียหายไม่ลามข้าม Bot ผ่าน Cross Margin เพราะแต่ละ Bot มีเงินค้ำประกันของตัวเอง
- ไม่มีปัญหา net position หักลบกัน หรือ Leverage / Margin Mode ชนกันระหว่าง Bot
- วาง TP/SL บน Binance ได้ตรงๆ ทำให้ Position มีตัวป้องกันบน exchange แม้ระบบล่ม
- Risk Rule ของ Portfolio เท่ากับ Risk Rule ของ Bot

**ผลที่ต้องยอมรับ**
- ฝั่ง Live ต้องใช้ Binance Sub-account เท่ากับจำนวน Bot ที่รันพร้อมกัน (R-17)
- เงินทุนแยกเป็นหลายก้อน และ Bot ที่ไม่มี Position ปล่อยเงินว่างไว้
- User ที่ต้องการทั้ง Bot และ Manual ต้องใช้คนละ Portfolio

**สิ่งที่ต้องทำใน design**
- บันทึก Order Owner ในทุก Order และ Fill ตั้งแต่วันแรก
- บังคับกติกา D-02 ที่ Risk Engine (FR-RSK-06) ไม่ใช่แค่ที่ UI
- ออกแบบให้ขยายเป็นหลาย Active Bot ต่อ Portfolio ได้ในอนาคต (เช่น กติกาเจ้าของ Symbol) โดยไม่ต้องรื้อ model
- กำหนดนิยาม "ไม่มี Position ค้าง" ของ Spot Portfolio (A-24)

**ผลต่อ Decision อื่น**
- D-04: จำนวน Sub-account ที่ต้องใช้เพิ่มขึ้น ความง่ายในการเชื่อม Sub-account สำคัญขึ้น
- D-11: limit จำนวน Portfolio ต่อ Plan เท่ากับ limit จำนวน Bot ที่รันพร้อมกัน
- D-14: Order ที่เกิดนอกระบบใน Portfolio ที่มี Active Bot ต้องมีนโยบายสอดคล้องกับกติกานี้ (เช่น Pause Bot)

#### D-03 — Position Mode และ Margin feature ✅ Decided (2026-09-22)

| ข้อ | Decision |
|---|---|
| 1. Position Mode | **One-way อย่างเดียว** ส่วน Hedge Mode อยู่ใน Future; model ระบุ Position ด้วย (Portfolio, Symbol, Position Side) ไว้รองรับอนาคต |
| 2. Multi-Assets Mode | **ไม่รองรับ** ใช้ Single-Asset Mode (quote asset ตัดสินใน D-15) |
| 3. Portfolio Margin | **ไม่รองรับ** |
| 4. Sub-account ตั้งโหมดไม่ตรง (Live) | ตรวจตอนเชื่อม; ไม่มี Position/Order ค้าง → เสนอเปลี่ยนเมื่อ User ยืนยัน; มีค้าง → ปฏิเสธการเชื่อม; Reconciliation ตรวจซ้ำ ถ้าโหมดเปลี่ยน → Pause Bot และแจ้ง User |

Paper (Virtual Sub-account) ใช้ One-way + Single-Asset ตายตัว และ Cross / Isolated Margin ยังรองรับครบตาม requirement

**เหตุผล**
- หลัง D-02 (Active Bot ครั้งละ 1 ตัว) แทบไม่มีกรณีที่ต้องถือ Long และ Short พร้อมกัน
- Order model ง่ายกว่า (คิดแค่ Buy/Sell) ลดโอกาสส่งคำสั่งผิดฝั่ง
- สูตร Liquidation มีชุดเดียว ลดความเสี่ยง R-01 และงาน golden test
- Multi-Assets Mode ทำให้เงินค้ำขึ้นลงตามราคาเหรียญ คำนวณยาก และ Binance จำกัดให้ใช้ได้เฉพาะ Cross Margin (ต้อง verify)
- Portfolio Margin ขัดกับ D-01 และต้องใช้ API และสูตรคนละชุด
- การเปลี่ยนค่าตั้งบัญชีจริงของ User ต้องได้รับการยืนยันก่อน และการตรวจซ้ำสอดคล้องกับ P-08 และ P-09

**ผลที่ต้องยอมรับ**
- Strategy ที่ต้องถือ Long และ Short พร้อมกัน (เช่น Grid บางแบบ) ทำไม่ได้ใน MVP
- User ที่ใช้ Hedge Mode, Multi-Assets Mode หรือ Portfolio Margin อยู่บน Binance ต้องใช้ Sub-account อื่นหรือยอมเปลี่ยนโหมด

**สิ่งที่ต้องทำใน design**
- Position model มี Position Side ตั้งแต่ต้น
- ตรวจสอบกติกาปัจจุบันของ Binance: การเปลี่ยนโหมดเมื่อมี Position/Order ค้าง, ข้อจำกัดของ Multi-Assets Mode และเงื่อนไขของ Portfolio Margin

**ผลต่อ Decision อื่น**
- D-14: การที่ User เปลี่ยนโหมดเองนอกระบบเป็นกรณีหนึ่งของการเปลี่ยนแปลงนอกระบบ
- D-15: ถ้ารองรับหลาย quote asset จะมีเงินค้ำแยกกองละเหรียญภายใต้ Single-Asset Mode

#### D-06 — วิธีสร้าง Strategy ✅ Decided (2026-09-22)

| ข้อ | Decision |
|---|---|
| 1. ใครสร้าง Strategy | **เจ้าของระบบเขียน Built-in Strategy เอง** แล้วเปิดให้ User เลือกใช้ User สร้างหรืออัปโหลด Strategy เองไม่ได้ |
| 2. User ปรับ Parameter ได้ไหม | **ได้ในขอบเขต** เจ้าของระบบกำหนดใน Strategy Parameter Schema ว่า Parameter ไหนปรับได้ พร้อมค่าต่ำสุด/สูงสุดและค่าเริ่มต้น ส่วนที่เหลือล็อกไว้ |
| 3. แบ่ง Strategy ตาม Plan | **ย้ายไปตัดสินใน D-11** ระบบต้องรองรับการเปิด Strategy ตาม Plan ผ่าน Entitlement (FR-PLN-02) |
| 4. ชุด Strategy เริ่มต้น | **เจ้าของระบบเป็นผู้กำหนด** ไม่ได้กำหนดในเอกสารนี้ |

**เหตุผล**
- ไม่มีโค้ดจากภายนอกรันบน server จึงตัดความเสี่ยง R-12 ออกจาก MVP
- เจ้าของระบบควบคุมคุณภาพและทดสอบ Strategy ได้ครบก่อนเปิดให้ใช้
- สร้างได้เร็วที่สุด และ Backtest, Paper, Live ใช้โค้ดชุดเดียวกัน
- การเปิดให้ปรับ Parameter ในขอบเขต ทำให้ User ปรับให้เข้ากับสไตล์ตัวเองได้โดยไม่ใส่ค่าที่อันตราย

**ผลที่ต้องยอมรับ**
- User ใช้ได้เฉพาะ Strategy ที่เจ้าของระบบเตรียมไว้ ถ้าต้องการแบบใหม่ต้องรอเจ้าของระบบเพิ่ม
- User ที่มี Strategy ของตัวเอง (เช่น ใน TradingView) ยังนำมาใช้ไม่ได้

**สิ่งที่ต้องทำใน design**
- Strategy interface เดียวที่ไม่ทำ I/O (FR-STR-13) เพื่อให้เพิ่มวิธีสร้าง Strategy แบบอื่นในอนาคตได้โดยไม่ต้องรื้อ
- Strategy Parameter Schema และการตรวจค่าที่ User ใส่ (FR-STR-11)
- Strategy Version ที่ Bot บันทึกไว้ (FR-STR-12)
- วิธีเผยแพร่ Strategy ใหม่: เขียนเป็นโค้ดใน Trading Core แล้ว deploy; การเปิด/ปิด Strategy ให้ User เห็น (**Proposed**) กำหนดตอน design

**ผลต่อ Decision อื่น**
- D-07: Backtest ใช้ Built-in Strategy ชุดเดียวกับ Live ได้โดยตรง
- D-08: Indicator ที่ต้องรองรับ ขึ้นกับ Built-in Strategy ที่เจ้าของระบบจะเขียน
- D-11: ต้องตัดสินว่าจะจำกัด Built-in Strategy ตาม Plan หรือไม่

#### D-10 — Spot Margin ✅ Decided (2026-09-22)

| ข้อ | Decision |
|---|---|
| 1. Spot Margin ใน MVP | **ไม่รองรับ** Spot เป็น Long อย่างเดียวและไม่มี Leverage ส่วน Short, Leverage และ Cross / Isolated Margin ใช้กับ USDⓈ-M Futures เท่านั้น |
| 2. Cross / Isolated ของ Spot Margin | ไม่เกี่ยว (ไม่รองรับ Spot Margin) |
| 3. อนาคต | **เก็บใน Future Scope โดยให้ความสำคัญต่ำ** ทบทวนหลัง Live Trading เสถียรและมีผู้ใช้ต้องการ |
| 4. API Key ที่เปิดสิทธิ์ Margin | **แจ้งเตือนแต่ไม่ปฏิเสธ** การเชื่อม (ต่างจากสิทธิ์ Withdrawal ที่ปฏิเสธเสมอ) |

**เหตุผล**
- Long / Short, Leverage และ Cross / Isolated ใน requirement ต้นฉบับทำได้ครบผ่าน Futures
- Spot Margin ต้องสร้างระบบกู้/คืน, ดอกเบี้ยรายชั่วโมง, สูตร Liquidation อีกชุด, การจำลองใน Paper และ Adapter อีกชุด ซึ่งเท่ากับเพิ่มตลาดที่สามเข้ามาใน MVP
- ลดความเสี่ยง R-01 เพราะไม่มีสูตร Liquidation เพิ่ม
- ไม่ต้องขอสิทธิ์ Margin ใน API Key ของ User (P-10)
- "Cross / Isolated" ในระบบมีความหมายเดียว ลดความสับสน
- บางประเทศจำกัดการใช้ Margin (เกี่ยวกับ D-17)

**ผลที่ต้องยอมรับ**
- เหรียญที่มีใน Spot แต่ไม่มีใน Futures จะ Short หรือใช้ Leverage ไม่ได้
- User ที่ต้องการถือเหรียญจริงแบบมี Leverage ต้องใช้ Futures แทน

**สิ่งที่ต้องทำใน design**
- Market Type เพิ่มค่าใหม่ได้ และการคำนวณ Margin / Liquidation แยกตาม Market Type (FR-MKT-11)
- ตรวจสิทธิ์ Margin ของ API Key ตอนเชื่อมและแจ้งเตือน (FR-SEC-10)

**ผลต่อ Decision อื่น**
- D-01: ถ้าเพิ่ม Spot Margin ในอนาคต จะเป็น Portfolio ประเภทใหม่ตามหลัก 1 Portfolio = 1 Market Type ไม่กระทบ Portfolio เดิม

#### D-12 — Tenant model ✅ Decided (2026-09-22)

| ข้อ | Decision |
|---|---|
| 1. Tenant model | **Workspace เป็น Tenant** ข้อมูลทั้งหมดและ Plan เป็นของ Workspace; ใน MVP ทุก User ได้ Workspace ส่วนตัว 1 อันอัตโนมัติ และ Workspace มีสมาชิกได้ 1 คน (ผลที่ผู้ใช้เห็น = 1 คนต่อ 1 Tenant) และผู้ใช้ไม่เห็นคำว่า Workspace |
| 2. Role | **ยังไม่กำหนดใน MVP** แต่การตรวจสิทธิ์ต้องผ่านจุดเดียวเพื่อเพิ่ม Role ภายหลังได้ |
| 3. Platform Admin | **เพิ่มเป็น Decision ใหม่ D-20** |
| 4. คำศัพท์ | ใช้ **Workspace** ใน code และเอกสาร; "Tenant" ใช้เป็นคำอธิบายเชิง architecture เท่านั้น |

**เหตุผล**
- ถ้าผูกข้อมูลกับ User โดยตรงแล้วภายหลังต้องการระบบทีม ต้องย้ายความเป็นเจ้าของของข้อมูลทุกชนิด ซึ่งเป็นงานใหญ่และเสี่ยงข้อมูลรั่วข้าม Tenant
- ต้นทุนตอนนี้ต่ำ: เพิ่มแค่ชั้น Workspace ใน model ไม่ต้องสร้างระบบเชิญ, Role หรือหน้าจอทีม
- ระบบทีมอาจเป็นจุดขายของ Plan ระดับสูงในอนาคต
- ไม่เปิดระบบทีมใน MVP เพราะเพิ่ม scope, ความซับซ้อนด้านความปลอดภัย (ใครสั่ง Live, ใครเห็น API Key) และอาจมีประเด็นกฎหมาย (D-17)

**ผลที่ต้องยอมรับ**
- งานออกแบบตอนต้นเพิ่มขึ้นเล็กน้อยจากการมีชั้น Workspace
- MVP ใช้งานร่วมกันหลายคนไม่ได้

**สิ่งที่ต้องทำใน design**
- ทุกข้อมูลที่เป็นของผู้ใช้ระบุ Workspace เจ้าของ และทุก query ต้องกรองตาม Workspace
- Plan และ Entitlement ผูกกับ Workspace
- Audit log เก็บทั้ง Workspace และ User ผู้กระทำ
- จุดตรวจสิทธิ์จุดเดียว (FR-TEN-08)

**ผลต่อ Decision อื่น**
- D-11: Plan และ limit คิดต่อ Workspace
- D-20: ต้องกำหนดสิทธิ์ของ Platform Admin ซึ่งอยู่นอกทุก Workspace

#### D-18 — Latency, Availability, ขนาดระบบ และ Data Retention ✅ Decided (2026-09-22)

| ข้อ | Decision |
|---|---|
| 1. Timeframe และจังหวะของ Strategy | Timeframe เล็กสุด `1m`; Strategy ดูได้ทั้ง**ตอน Candle ปิด**และ**ราคาระหว่างแท่ง** โดยราคาระหว่างแท่งส่งแบบรวบไม่เกิน 1 ครั้งต่อวินาทีต่อ Symbol เฉพาะ Symbol ที่ Bot ใช้ |
| 2. ราคาที่ใช้ | Strategy ใช้ Last Price; Liquidation และ Unrealized PnL ของ Futures ใช้ Mark Price |
| 3. Latency | ส่ง Order Intent ภายใน 1 วินาทีหลังข้อมูลที่ทำให้เกิดสัญญาณ (95% ของครั้ง) |
| 4. Availability | ช่วงทดลอง 99%; Live ทำ Reconciliation ก่อน Bot ทำงานต่อ; Paper จำลองย้อนหลังด้วย Candle 1m (ตรวจ TP/SL/Liquidation, ไม่เปิด Position ใหม่, แตะทั้งคู่ให้ถือว่าโดน SL ก่อน) |
| 5. ขนาดระบบ | User พร้อมกัน 20, Bot พร้อมกัน 100, Symbol 50, VM 4 vCPU / 16 GB — ยืนยันด้วยการทดสอบโหลด |
| 6. เกณฑ์ย้ายไป GCP | CPU/RAM เกิน 70% ต่อเนื่อง, ต้องการ availability เกิน 99%, หรือก่อนเปิด Live ให้ User ภายนอกจำนวนมาก |
| 7. Data retention | Candle 1m 2 ปี; Candle ≥ 1h ตลอดไป; Order/Fill/Transfer/Audit log ตลอดอายุ Workspace; log ระบบ 30 วัน; log Bot 90 วัน; API Credential ลบทันทีเมื่อลบ/ปิดบัญชี |

**เหตุผล**
- Timeframe 1m ไม่ต้องการความเร็วต่ำกว่าวินาที และฝั่ง Live มี TP/SL วางบน Binance อยู่แล้ว (D-02)
- การส่งราคาแบบรวบลดภาระลงมากแต่ยังเร็วพอสำหรับ Strategy บน Timeframe 1m
- VM เดียวทำ availability เกิน 99% ไม่ได้จริง จึงตั้งเป้าให้ตรงกับความสามารถ
- การจำลองย้อนหลังของ Paper ทำให้ผล Paper ไม่เพี้ยนจาก Live มากเกินไป และการถือว่าโดน SL ก่อนทำให้ผลไม่ดูดีเกินจริง
- ตัวเลขขนาดระบบใช้เป็นเป้าออกแบบและทดสอบโหลด; การย้ายไป GCP เกิดจากตัวชี้วัด
- Candle 1m 2 ปีพอสำหรับ Backtest พื้นฐานโดยไม่ทำให้ database ใหญ่เกิน VM

**ผลที่ต้องยอมรับ**
- ภาระของระบบสูงกว่าแบบดูเฉพาะตอน Candle ปิด และ Bot ต้องทำงานแบบรับ event ตลอดเวลา
- Strategy ที่ต้องการราคาทุกการเปลี่ยนแปลง (ถี่กว่า 1 ครั้งต่อวินาที) ทำไม่ได้
- ระบบหยุดทำงานได้ประมาณ 7 ชั่วโมงต่อเดือนในช่วงทดลอง

**สิ่งที่ต้องทำใน design**
- Strategy interface มี 2 จังหวะ (Candle ปิด / ราคาอัปเดต) และ Strategy ที่ไม่ใช้ราคาระหว่างแท่งต้องไม่เพิ่มภาระ
- ตัวรวบราคาต่อ Symbol ที่ปรับความถี่ได้
- Metric วัด latency และแผนทดสอบโหลดตาม NFR-16
- กลไกจำลองย้อนหลังของ Paper หลังระบบกลับมา
- Job ลบข้อมูลตามระยะเวลาเก็บ

**ผลต่อ Decision อื่น**
- D-05: กติกา "แตะทั้ง TP และ SL ใน Candle เดียวให้ถือว่าโดน SL ก่อน" ต้องสอดคล้องกับ Paper fill model
- D-07: Candle 1m ไม่พอให้ Backtest Strategy ที่ดูราคาระหว่างแท่งได้แม่นยำ ต้องตัดสินว่ายอมใช้การประมาณหรือเก็บข้อมูลละเอียดกว่า
- D-15: จำนวน Symbol ที่รองรับต้องสอดคล้องกับเป้า 50 Symbol
- D-17: การเก็บข้อมูลการเทรดหลังลบบัญชีขึ้นกับข้อกฎหมาย

#### D-05 — Paper Fill Model ✅ Decided (2026-09-22)

หลักการ: **ผล Paper ต้องไม่ดูดีเกินจริง**

| # | เรื่อง | Decision |
|---|---|---|
| 1 | ราคา Market Order | Best bid/ask (ซื้อที่ราคาเสนอขาย, ขายที่ราคาเสนอซื้อ) |
| 2 | Slippage | คงที่ ค่าเริ่มต้น 0.02% Platform Admin ปรับได้; ไม่จำลองความลึกของ order book |
| 3 | Limit Order | fill เมื่อราคาวิ่งทะลุ Limit (ไม่ใช่แค่แตะ) คิด Maker fee; Limit ที่ fill ทันทีนับเป็น Taker |
| 4 | Partial fill | ไม่จำลอง |
| 5 | Fee | อัตรามาตรฐาน Binance ระดับ VIP 0 เป็นค่ากลาง Platform Admin ปรับได้; ไม่คิดส่วนลด BNB |
| 6 | Funding Fee | จำลองด้วย Funding Rate และเวลาจริงจาก Binance |
| 7 | TP / SL | ตัดสินด้วย Last Price; แตะแล้ว fill แบบ Market Order (bid/ask + slippage + Taker fee) |
| 8 | Liquidation | ตัดสินด้วย Mark Price; ปิด Position และหักค่าธรรมเนียม Liquidation ตามกติกา Binance; ไม่จำลอง Insurance Fund และ ADL |
| 9 | ความแม่นยำเทียบ Binance | ข้อมูลเข้าเหมือนกันต้องได้ผลเท่ากับ Binance ยกเว้นการปัดเศษตาม tick size / precision; ตรวจด้วย golden test จากบัญชีจริง |

**เหตุผล**
- ใช้ bid/ask, slippage, Limit ที่ต้องทะลุ และ TP/SL ที่ fill แบบ Taker ทำให้ต้นทุนการเทรดใน Paper ใกล้เคียงหรือแย่กว่าจริงเล็กน้อย ไม่ดูดีเกินจริง
- Funding Fee มีผลต่อกำไรมากเมื่อถือ Position นาน จึงต้องจำลอง
- การไม่จำลอง partial fill, order book depth, Insurance Fund และ ADL ลดความซับซ้อนได้มาก โดยกระทบผลน้อยสำหรับ Order ขนาดเล็กช่วงทดลอง
- สูตรเป็น deterministic จึงตั้งเกณฑ์ "ได้ผลเท่ากัน" ได้ แทนการกำหนด % คลาดเคลื่อน

**ผลที่ต้องยอมรับ**
- Order ขนาดใหญ่ได้ราคาดีกว่าความจริง
- ไม่มี partial fill และไม่มีการถูก ADL
- Fee ไม่ตรงกับ User ที่มี VIP level สูงกว่าหรือใช้ส่วนลด BNB

**สิ่งที่ต้องทำใน design**
- รับ best bid/ask, Mark Price และ Funding Rate ของทุก Symbol ที่รองรับ
- ค่า slippage และ fee rate เป็น config ที่ Platform Admin ปรับได้ (เกี่ยวกับ D-20)
- ตรวจอัตรา Fee ปัจจุบันและกติกาค่าธรรมเนียม Liquidation ของ Binance
- กติกา "แตะทั้ง TP และ SL ใน Candle เดียวให้ถือว่าโดน SL ก่อน" (NFR-15) ใช้ร่วมกับ Paper Fill Model นี้

**ผลต่อ Decision อื่น**
- D-07: ถ้ามี Backtest ควรใช้ Paper Fill Model ชุดเดียวกัน
- D-20: Platform Admin ต้องมีวิธีปรับค่า slippage และ fee rate

#### D-07 — Backtesting ✅ Decided (2026-09-22)

| ข้อ | Decision |
|---|---|
| 1. Backtesting ในระบบ | **ไม่มี** ทั้งใน MVP และในแผนปัจจุบัน (ไม่อยู่ใน Future Scope) |
| 2. การทดสอบ Strategy | เจ้าของระบบและ User ทดสอบ Strategy ด้วย **Paper Trading** |

**ผลที่ต้องยอมรับ**
- ต้องรอผลจาก Paper Trading แบบ realtime ก่อนรู้ว่า Strategy หรือ Parameter ใช้ได้หรือไม่ ใช้เวลานานกว่าการ Backtest
- User เปรียบเทียบผลของ Parameter หลายชุดได้โดยรัน Paper Portfolio หลายตัวพร้อมกัน (ตาม D-02 ใช้ Portfolio ละ Bot)
- เจ้าของระบบอาจต้องใช้เครื่องมือนอกระบบในการพัฒนา Strategy

**ผลต่อการออกแบบ**
- ไม่ต้องเก็บประวัติ Funding Rate และไม่ต้องมีงานเบื้องหลังสำหรับ Backtest
- Strategy ยังต้องเป็นโค้ดที่ไม่ทำ I/O และให้ผลเดิมเมื่อข้อมูลเหมือนเดิม (FR-STR-13) เพื่อใช้กับ Paper, Live, การจำลองย้อนหลังหลังระบบล่ม (NFR-15) และการทดสอบอัตโนมัติ
- เหตุผลข้อหนึ่งของการเก็บ Candle 1m 2 ปีใน D-18 คือ Backtest ซึ่งไม่ใช้แล้ว ระยะเวลาเก็บยังคงตาม NFR-18 จนกว่าจะทบทวน

**หมายเหตุ:** ข้อความใน Decision Log ของ D-05, D-06 และ D-18 ที่กล่าวถึง Backtest เป็นบันทึกก่อนการตัดสินข้อนี้

#### D-08 — Timeframe และ Indicator ✅ Decided (2026-09-22)

| ข้อ | Decision |
|---|---|
| 1. Timeframe | `1m, 5m, 15m, 30m, 1h, 4h, 1d` (7 ค่า) ใช้ทั้ง Chart และ Strategy |
| 2. Indicator บน Chart | Volume, SMA, EMA, Bollinger Bands, RSI, MACD, ATR (7 ตัว) User ปรับค่าได้ |
| 3. Indicator ของ Strategy | เจ้าของระบบกำหนดตาม Built-in Strategy และต้องอยู่ใน Trading Core |
| 4. ความสอดคล้องของค่า | Trading Core เป็นต้นแบบสูตร Frontend ต้องผ่านชุดค่าทดสอบเดียวกัน (FR-CHT-06 เปลี่ยนจาก Proposed เป็นข้อบังคับ) |
| 5. ป้าย Buy / Sell | แสดงจุด Fill ของ Portfolio บน Chart แบบ Binance พร้อมรายละเอียดเมื่อชี้ (**เพิ่มโดยเจ้าของระบบ**) |
| 6. Data retention | Candle ต่ำกว่า 1h เก็บ 2 ปี, 1h ขึ้นไปเก็บตลอดไป (ปรับ NFR-18) |

**เหตุผล**
- 7 Timeframe ครอบคลุมตั้งแต่เทรดสั้นถึงรายวัน โดยไม่ต้องเก็บข้อมูลเกินจำเป็น
- Indicator 7 ตัวเป็นชุดที่ใช้บ่อยและสร้างเองได้บน Lightweight Charts
- ค่าที่ Bot ใช้กับที่ User เห็นบน Chart ต้องตรงกัน ไม่เช่นนั้น User จะสับสนว่า Bot ตัดสินใจจากอะไร
- ป้าย Buy / Sell ช่วยให้ User เห็นว่า Bot หรือตัวเองเข้าและออกที่จุดไหน ตรวจสอบพฤติกรรมของ Bot ได้ง่าย

**สิ่งที่ต้องทำใน design**
- Indicator library ใน Trading Core พร้อมชุดค่าทดสอบ (test vectors) ที่ Frontend ใช้ร่วม
- API สำหรับดึง Fill ของ Portfolio ตามช่วงเวลาของ Chart เพื่อแสดงป้าย (ใช้ข้อมูล Order Owner ตาม FR-PF-10)

#### D-09 — Chart library ✅ Decided (2026-09-22)

| ข้อ | Decision |
|---|---|
| 1. Chart library | **TradingView Lightweight Charts** |
| 2. เครื่องมือวาดเส้น | ไม่อยู่ใน MVP ย้ายไป Future (อาจพิจารณา Advanced Charts) |

**เหตุผล**
- ใช้ได้ทันทีโดยไม่ต้องรอการอนุมัติ license
- Indicator คำนวณด้วยสูตรของเราเอง ค่าบน Chart จึงตรงกับที่ Bot ใช้
- รองรับการแสดงเส้นราคา (Entry/TP/SL/Liquidation) และป้ายบนแท่งเทียน (ป้าย Buy / Sell)

**ผลที่ต้องยอมรับ**
- ต้องสร้าง Indicator ทั้ง 7 ตัวเอง
- ไม่มีเครื่องมือวาดเส้นใน MVP
- ต้องแสดง attribution ตามเงื่อนไข license (verify ตอน design)

#### D-15 — Symbol และ Quote Asset ✅ Decided (2026-09-22)

| ข้อ | Decision |
|---|---|
| 1. Quote Asset | **USDT อย่างเดียว**; USDC และอื่นๆ ย้ายไป Future |
| 2. ชุด Symbol | **Symbol Whitelist** ที่ Platform Admin คัดเลือก เริ่มประมาณ 30 ตัว ไม่เกิน 50 ตัว |
| 3. เกณฑ์คัดเลือก | มีทั้งใน Spot และ USDⓈ-M Futures และมีปริมาณซื้อขายสูง |
| 4. นำ Symbol ออก | ถ้ามี Position/Order ค้าง ปิดการเปิด Position ใหม่ก่อน นำออกเมื่อไม่มีใครถือ |
| 5. Binance delist | ปิดการเปิด Position ใหม่ทันที และแจ้ง User ที่ถือ Position |

**เหตุผล**
- USDT มีสภาพคล่องสูงสุด Futures ใช้เงินค้ำกองเดียว (D-03) และทุก Portfolio ใช้หน่วยเดียวกัน เปรียบเทียบได้ตรง
- Whitelist ควบคุมภาระของ VM (NFR-16) และตัดเหรียญสภาพคล่องต่ำที่ทำให้ Paper ไม่สมจริง (D-05)
- Symbol ที่มีทั้งสองตลาดทำให้ User ใช้เหรียญเดียวกันได้ทุก Portfolio

**สิ่งที่ต้องทำใน design**
- Platform Admin จัดการ Symbol Whitelist ได้ (เกี่ยวกับ D-20)
- สถานะของ Symbol อย่างน้อย: เปิดเทรด / ปิดการเปิด Position ใหม่ / นำออกแล้ว
- ตรวจจับประกาศ delist หรือการเปลี่ยนสถานะ Symbol จาก Binance

#### D-19 — เงินของ Paper Main Account ✅ Decided (2026-09-22)

| ข้อ | Decision |
|---|---|
| 1. เงินเริ่มต้น | **10,000 USDT** ต่อ Workspace, Platform Admin ปรับค่าได้ |
| 2. Asset | USDT อย่างเดียว |
| 3. การแบ่งเงิน | User Transfer จาก Paper Main Account ไป Virtual Sub-account เอง |
| 4. เติมเงิน | **ได้** บันทึกเป็น Virtual Deposit ไม่นับเป็นกำไร |
| 5. Reset | **ได้ต่อ Portfolio** ต้องไม่มี Active Bot; Portfolio เดิมเก็บเป็นประวัติอ่านอย่างเดียว แล้วเริ่ม Portfolio ใหม่ |
| 6. ต่อ Plan | เงินเริ่มต้นเท่ากันทุก Plan |

**เหตุผล**
- 10,000 USDT ใกล้กับขนาดเงินของผู้ใช้รายย่อย
- Analytics ต้องแยกเงินเข้า/ออกจากกำไรอยู่แล้วเพราะมี Transfer การเติมเงินจึงเพิ่มงานไม่มาก และผู้ใช้ที่ขาดทุนหมดยังทดลองต่อได้
- Reset แบบเก็บประวัติทำให้ผลเก่าไม่หายและไม่ปนกับผลใหม่
- เงินเท่ากันทุก Plan ทำให้ผล Paper เปรียบเทียบกันได้

**สิ่งที่ต้องทำใน design**
- Portfolio มีสถานะ Active / Archived (หลัง Reset)
- Analytics คำนวณผลตอบแทนโดยแยกเงินทุนที่เข้า/ออก (FR-ACC-11)
- กติกาปิด Position / ยกเลิก Order ตอน Reset (FR-ACC-10)

#### D-20 — Platform Admin ✅ Decided (2026-09-22)

| ข้อ | Decision |
|---|---|
| 1. บัญชี Admin | แยกจากบัญชี User, บังคับ 2FA, MVP มี Admin คนเดียว |
| 2. สิ่งที่ทำได้ | จัดการ Built-in Strategy, Symbol Whitelist, ค่าระบบ, User และ Plan; Global Kill Switch; ดูสถานะระบบ |
| 3. สิ่งที่ห้ามทำ | เห็น API Secret, เทรดแทน User, ปิด Position ของ User, แก้ประวัติ Order / Fill / Audit log |
| 4. ดูข้อมูลของ User | อ่านอย่างเดียวเพื่อช่วยแก้ปัญหา และบันทึก Audit log ทุกครั้ง |
| 5. หน้าจอ Admin | มีแบบเรียบง่ายในระบบ |
| 6. Audit log | ทุกการกระทำของ Admin บันทึกแบบแก้ไขไม่ได้ |

**เหตุผล**
- สิทธิ์ของ Admin อันตรายที่สุดในระบบ บัญชีแยกและ 2FA ลดความเสี่ยงเมื่อบัญชีถูกเจาะ
- Global Kill Switch ใช้หยุดทุก Bot ทันทีเมื่อพบ bug หรือ Binance มีปัญหา โดยไม่ตัดสินใจปิด Position เงินจริงแทน User (Live มี TP/SL บน Binance ป้องกันอยู่แล้ว)
- Admin ต้องช่วยแก้ปัญหาของ User ได้ แต่ต้องตรวจสอบย้อนหลังได้ทุกครั้งที่เข้าดู
- หน้าจอ Admin จำเป็นเพราะงานเหล่านี้ทำบ่อยหรือต้องทำเร็ว การแก้ database หรือ deploy ทุกครั้งช้าและเสี่ยง

**สิ่งที่ต้องทำใน design**
- Role ของ Platform Admin แยกจากการตรวจสิทธิ์ของ Workspace (FR-TEN-08)
- Global Kill Switch ต้องถูกตรวจที่ Risk Engine / Order Manager ไม่ใช่แค่ที่ UI
- การเปิดดูข้อมูล User ต้องสร้าง Audit log อัตโนมัติ

#### D-11 — Plan และ Entitlement ✅ Decided (2026-09-22)

| ข้อ | Decision |
|---|---|
| 1. เก็บเงินใน Phase 1 | **ไม่เก็บ** Admin กำหนด Plan ให้เอง; ไม่มี trial แยก; ราคาและ billing ไปตัดสินใน **D-21** |
| 2. สิ่งที่แบ่ง Plan | **Leverage สูงสุด, วงเงินการเทรด, สิทธิ์ Live, จำนวน Portfolio**; Strategy / Timeframe / Indicator ครบทุก Plan |
| 3. วิธีวัดวงเงิน | **มูลค่า Position ที่เปิดอยู่รวม (Open Notional)** ต่อ Workspace แยก Paper / Live |
| 4. ค่าเริ่มต้น | ตาม FR-PLN-03 — **ทุกค่า Platform Admin ปรับได้ภายหลัง** |
| 5. ขอบเขต | ใช้กับทั้ง Paper และ Live; เป็นกฎที่ User ข้ามไม่ได้ |
| 6. เกิน Entitlement | ไม่ลบข้อมูล, ไม่ปิด Position, ไม่เปลี่ยน Leverage ให้; ห้ามเปิด/เพิ่มส่วนที่เกิน; Bot ส่วนเกินถูก Pause |
| 7. ปรับค่า | เพิ่มมีผลทันที; ลดต้องแจ้งล่วงหน้า; บันทึก Audit log ทุกครั้ง |
| 8. เงื่อนไขก่อนเปิด Live | Plan อนุญาต + 2FA + ยอมรับ risk disclosure |

| Entitlement (ค่าเริ่มต้น) | Free | Pro | Advanced |
|---|---|---|---|
| Leverage สูงสุด (Futures) | 5x | 20x | 50x |
| วงเงิน Paper | 10,000 USDT | 50,000 USDT | 250,000 USDT |
| วงเงิน Live | — | 50,000 USDT | 250,000 USDT |
| Live Trading | ❌ | ✅ | ✅ |
| Paper Portfolio | 2 | 5 | 10 |
| Live Portfolio | — | 3 | 10 |

**เหตุผล**
- วัดวงเงินจากมูลค่า Position รวม: Risk Engine บังคับได้ทุก Order (P-02), ไม่ขึ้นกับยอดเงินใน Binance (P-08), ไม่ลงโทษผู้ที่ทำกำไร และสะท้อนความเสี่ยงรวม Leverage
- Leverage ตาม Plan ลดความเสี่ยงของมือใหม่ และจำกัดสูงสุดที่ 50x เพื่อลดโอกาส Liquidation จากราคาขยับเล็กน้อย
- ใช้กับ Paper ด้วยเพื่อให้ผลทดสอบตรงกับเงื่อนไขจริงของ Plan
- Free ใช้ Paper ได้เต็มรูปแบบแทน trial
- ค่าทั้งหมดปรับได้เพราะเป็นการตัดสินทางธุรกิจที่ต้องเปลี่ยนตามตลาด

**สิ่งที่ต้องทำใน design**
- Entitlement เป็น config ของ Plan ไม่ใช่ค่าใน code; Risk Engine อ่านค่าปัจจุบันทุกครั้งที่ตรวจ Order
- คำนวณ Open Notional ของ Workspace แบบ realtime
- กลไกแจ้ง User เมื่อจะลดค่า และ Pause Bot ส่วนเกิน

**ผลต่อ Decision อื่น**
- D-06: ไม่จำกัด Built-in Strategy ตาม Plan ใน MVP
- D-21: ราคา, billing และ grandfathering

#### D-04 — การเชื่อมบัญชี Binance ✅ Decided (2026-09-22)

| ข้อ | Decision |
|---|---|
| 1. วิธีเชื่อม | **User ให้ API Key ทีละบัญชี** (Sub-account หรือ Main Account) ระบบไม่ขอ Key ของ Main Account เพื่อจัดการ Sub-account, ไม่สร้าง Sub-account ให้ และไม่ใช้ Broker program |
| 2. Main Account ใน Live | **ใช้เป็น Live Portfolio ได้ 1 Portfolio** สำหรับ User ที่เปิด Sub-account ไม่ได้ (ทบทวน D-01 ข้อ 2 เฉพาะฝั่ง Live; Paper Main Account ยังเป็นกองกลาง) |
| 3. ตรวจ Key ตอนเชื่อม | ปฏิเสธ: เปิด Withdrawal, ไม่มีสิทธิ์ที่จำเป็น, ไม่ตั้ง IP whitelist, บัญชีถูกเชื่อมที่อื่นแล้ว, Futures ยังไม่เปิด; แจ้งเตือน: เปิดสิทธิ์ Transfer หรือ Margin |
| 4. Transfer ใน Live | ไม่ผ่านระบบ User โอนบน Binance เอง |

**เหตุผล**
- Key แต่ละตัวเทรดได้บัญชีเดียวและถอนเงินไม่ได้ ถ้าหลุดเสียหายแค่บัญชีเดียว; ไม่มี Key สิทธิ์สูงอยู่ในระบบเลย (P-10)
- ผู้ใช้บางคนเปิด Sub-account ไม่ได้ ถ้าไม่ให้ใช้ Main Account จะใช้ Live ไม่ได้เลย
- บังคับ IP whitelist ทำให้ Key ที่ถูกขโมยใช้จากที่อื่นไม่ได้
- ห้ามเชื่อมบัญชีเดียวซ้ำ ป้องกัน Position ชนกันแบบเดียวกับที่ D-02 ป้องกัน

**ผลที่ต้องยอมรับ**
- User ต้องสร้าง Sub-account และ Key เองหลายขั้นตอน (ช่วยด้วยหน้าแนะนำ)
- User ที่ใช้ Main Account ที่ตัวเองเทรดอยู่ด้วย จะเกิด Order นอกระบบบ่อย (เกี่ยวกับ D-14)
- ระบบต้องมี IP ขาออกคงที่ตลอดเวลา ถ้าเปลี่ยน IP ผู้ใช้ทุกคนต้องแก้ whitelist

**สิ่งที่ต้องทำใน design**
- ตรวจสอบกับ Binance API ฉบับปัจจุบัน: วิธีอ่าน permission และ IP whitelist ของ Key, หมายเลขบัญชีที่ใช้ตรวจซ้ำ, เงื่อนไขการเปิด Sub-account
- ขั้นตอนเชื่อมบัญชีที่ตรวจทุกข้อก่อนบันทึก Key ลง Credential Vault

#### D-13 — Binance Testnet ✅ Decided (2026-09-22)

| ข้อ | Decision |
|---|---|
| 1. ใช้ Testnet ไหม | **ใช้ ภายในทีมเท่านั้น** ไม่เปิดให้ User |
| 2. ใช้ทดสอบอะไร | การส่ง Order, TP/SL, Reconciliation และการเชื่อมบัญชี (ไม่ใช้ดูผลกำไร/ขาดทุน) |
| 3. เมื่อไร | ก่อนเปิด Live และทุกครั้งที่แก้โค้ดส่วนที่ติดต่อ Binance |
| 4. ขั้นถัดไป | ทดสอบด้วยเงินจริงจำนวนน้อยในบัญชีของเจ้าของระบบ ก่อนเปิดให้ User |

**เหตุผล**
- Paper ใช้ตัวจำลองของระบบเอง จึงไม่ได้ทดสอบโค้ดที่ส่ง Order ไป Binance จริง
- Testnet มีราคาและสภาพคล่องไม่เหมือนจริง ผลกำไร/ขาดทุนหลอกตา จึงไม่เปิดให้ User

**สิ่งที่ต้องทำใน design**
- Binance Execution Adapter เปลี่ยนปลายทางระหว่าง Testnet และของจริงได้ด้วย config
- ตรวจสอบว่า Testnet ของ Spot และ USDⓈ-M Futures รองรับ feature ที่ต้องทดสอบครบหรือไม่

#### D-14 — Order และการเปลี่ยนแปลงนอกระบบ ✅ Decided (2026-09-22)

| สถานการณ์ | Decision |
|---|---|
| ทุกกรณี | บันทึกเข้าระบบด้วย Order Owner = `EXTERNAL` และแจ้ง User |
| Portfolio มี Active Bot | Pause Bot และแจ้ง User |
| Portfolio ไม่มี Active Bot | บันทึกและแจ้งเตือนเท่านั้น |
| เปลี่ยน Leverage / โหมดบัญชีนอกระบบ | Pause Bot และแจ้ง User |
| ฝาก / ถอน / โอนเงินบน Binance | บันทึกเป็นเงินเข้า/ออก ไม่นับเป็นกำไร/ขาดทุน |
| เกินวงเงินของ Plan | ไม่ปิดให้ แต่ห้ามเปิด/เพิ่ม Position |

**เหตุผล**
- Binance เป็น Source of Truth (P-08) ระบบต้องรับรู้ทุกการเปลี่ยนแปลงให้ยอดเงินและ PnL ถูกต้อง
- Bot ที่ทำงานต่อหลังมีการแทรกจากภายนอกอาจตัดสินใจบนข้อมูลที่ผิด จึงต้อง Pause เหมือนกรณี Manual แทรก (D-02)
- เงินเข้า/ออกต้องแยกจากกำไร ไม่เช่นนั้น Analytics เพี้ยน

**สิ่งที่ต้องทำใน design**
- รูปแบบ Client Order ID ของระบบที่แยกจาก Order นอกระบบได้แน่นอน
- ตรวจจับเงินเข้า/ออกและการเปลี่ยนค่าตั้งของบัญชีจาก User Data Stream และ Reconciliation

#### D-16 — ช่องทางแจ้งเตือน ✅ Decided (2026-09-22)

| ข้อ | Decision |
|---|---|
| 1. ช่องทาง | Phase 1: In-app + Email; Phase 2 (ก่อน Live): Telegram; Future: LINE |
| 2. การตั้งค่า | User เลือกเรื่องและช่องทางเองได้ แต่เรื่องวิกฤตปิดไม่ได้ |
| 3. เตือนก่อน Liquidate | Margin Ratio ถึง 80% (ค่าเริ่มต้น User ปรับได้) |

**เหตุผล**
- In-app และ Email ไม่มีต้นทุนเพิ่มและพอสำหรับ Paper
- Live ใช้เงินจริง ต้องรู้ทันทีบนมือถือ Telegram ถึงเร็วและไม่มีค่าใช้จ่าย
- LINE Notify ปิดบริการแล้ว LINE Messaging API มีค่าใช้จ่ายต่อข้อความ (ต้อง verify) จึงเก็บไว้ใน Future

**สิ่งที่ต้องทำใน design**
- ระบบแจ้งเตือนกลางที่เพิ่มช่องทางใหม่ได้โดยไม่แก้ส่วนที่สร้างเหตุการณ์
- การส่งซ้ำไม่ทำให้ผู้ใช้ได้รับข้อความซ้ำ (NFR-22)

#### D-17 — กฎหมายและตลาดเป้าหมาย ✅ Decided (2026-09-22)

| ข้อ | Decision |
|---|---|
| 1. ตลาดเป้าหมาย | **ผู้ใช้ในประเทศไทย** |
| 2. Exchange ที่ใช้ | **พัฒนาบน Binance.com** เพราะ Binance TH ยังไม่เปิด feature ที่ต้องใช้; รองรับ **Binance TH** ในอนาคต |
| 3. Legal review | ต้องผ่าน**ก่อนเปิด Live** และ**ก่อนเก็บเงิน** |
| 4. เอกสาร | Terms of Service, Privacy Policy, Risk Disclosure |
| 5. จำกัดประเทศ | ตามผล legal review และประเทศที่ Binance ไม่ให้บริการ |
| 6. ข้อมูลหลังลบบัญชี | ลบข้อมูลส่วนตัวและ Credential ทันที เก็บประวัติการเทรดแบบไม่ระบุตัวตน (รอนักกฎหมายยืนยัน) |

**เหตุผล**
- Binance.com มี feature ครบ (โดยเฉพาะ USDⓈ-M Futures) จึงพัฒนาและทดสอบได้ครบตาม requirement
- การให้บริการผู้ใช้ในไทยบน Binance.com และบริการ Bot อาจมีประเด็นใบอนุญาต จึงต้องให้นักกฎหมายตรวจก่อนใช้เงินจริงหรือเก็บเงิน
- แยก Exchange Venue ตั้งแต่ต้น ทำให้เพิ่ม Binance TH ได้โดยไม่รื้อระบบ

**ผลที่ต้องยอมรับ**
- ผล legal review อาจทำให้ต้องเปลี่ยนแผน Live เช่น ใช้ได้เฉพาะ Binance TH หรือจำกัด feature
- Binance TH อาจไม่มี USDⓈ-M Futures ทำให้ผู้ใช้บน Venue นั้นใช้ได้แค่ Spot

**สิ่งที่ต้องทำใน design**
- Exchange Venue เป็นส่วนหนึ่งของ Exchange Account และ Binance Execution Adapter / Market Data แยกตาม Venue
- ติดตามและตรวจสอบ API ของ Binance TH เมื่อเปิด feature

#### Review 2026-09-22 — แก้ช่องว่างใน requirement ✅ Decided

| # | ประเด็น | Decision | Requirement |
|---|---|---|---|
| 1 | Global Kill Switch ขัดกับสิทธิ์ปิด Position | ยกเลิก Order เปิด/เพิ่ม Position, คง TP/SL, User ลด/ปิด Position ได้ | FR-ADM-06 |
| 2 | Restart ทำให้ Bot ที่ Pause กลับมาทำงาน | คงสถานะเดิม; เฉพาะ Bot ที่ RUNNING ทำงานต่อหลัง Reconciliation ผ่าน | NFR-14 |
| 3 | โหมดบัญชีที่ไม่รองรับ | Trading Restriction ระดับ Portfolio, ห้ามส่ง Order ทุกชนิด, ปลดอัตโนมัติเมื่อโหมดกลับมา | FR-LIVE-12, FR-LIVE-19 |
| 4 | Bracket ไม่มีกติกา partial fill / วางไม่สำเร็จ | ป้องกันตามจำนวนที่ fill; SL วางไม่สำเร็จ → ปิดส่วนที่ไม่มี SL (fail-safe) | FR-ORD-14..17 |
| 5 | Order ค้างกับวงเงิน | Order ค้างจองวงเงินข้าม Portfolio; Entitlement ลดลง → ยกเลิก Order เปิด/เพิ่มที่เกิน | FR-PLN-05, FR-PLN-14 |
| 6 | Attribution ผลของ Bot | ใช้ Position Episode แทน Order Owner | FR-PF-10/11, FR-ANL-03 |
| 7 | Reset ไม่มีกติกาเงิน / การนับ | เงินคืน Paper Main, Portfolio ใหม่เริ่ม 0; Archived ไม่นับ limit | FR-ACC-09, FR-ACC-12, FR-PF-00a |
| 8 | Marketable Limit ของ Paper เกินราคา Limit | fill ไม่แย่กว่าราคา Limit | FR-ORD-08 |

**ผลต่อ Decision เดิม:** ข้อ 7 เปลี่ยนความหมายของ D-19 ข้อ 5 ("เริ่ม Portfolio ใหม่ด้วยเงินตั้งต้น") เป็นเงินจาก Paper Main Account; ข้อ 1 ขยาย D-20

#### D-22 — ภาษาของระบบ ✅ Decided (2026-09-22)

| ข้อ | Decision |
|---|---|
| 1. ภาษา | **ไทยและอังกฤษ** ทั้ง UI, Email, Notification และเอกสารกฎหมาย |
| 2. การเลือก | User สลับภาษาได้และระบบจำค่า |
| 3. ค่าเริ่มต้นและรูปแบบ | ภาษาเริ่มต้นเป็นไทย; ศัพท์เทรดคงเป็นภาษาอังกฤษใน UI ภาษาไทย; เก็บเวลาเป็น UTC และแสดงตามเขตเวลาของ User (เริ่มต้น Asia/Bangkok) |

**สิ่งที่ต้องทำใน design**
- ระบบแปลภาษา (i18n) ใน Frontend และ template ของ Email / Notification แยกตามภาษา
- ข้อความ error จาก Backend ส่งเป็นรหัส แล้ว Frontend แปลเป็นภาษาที่เลือก

---

## Appendix A — Traceability: Original Requirement → Section

| Original requirement | Covered in |
|---|---|
| SaaS รองรับหลาย User | 2.1, 2.16, D-12 ✅, D-20 ✅ |
| Binance Spot | 2.4 |
| Binance USDⓈ-M Futures | 2.4, 2.7 |
| Paper Trading และ Live Trading | 2.2, 2.6, 2.12, 5 |
| Binance Main Account และ Sub-account | 2.2, D-04 ✅ |
| Paper Main Account และ Virtual Sub-account | 2.2, D-19 ✅ |
| แยก Portfolio ตาม Sub-account | 2.3, D-01 ✅ |
| Balance/Position/Margin/PnL/Risk/Liquidation แยกต่อ Portfolio | 2.3, 2.7, 2.10 |
| หลาย Symbol, Strategy, Bot, Timeframe ต่อ Portfolio | 2.3, 2.9, D-02 ✅ (**เปลี่ยน requirement:** Active Bot ครั้งละ 1 ตัว) |
| Manual Trading, Entry/TP/SL, Market/Limit, Long/Short | 2.5 |
| Leverage, Cross/Isolated | 2.5, 2.7 |
| Liquidation ใกล้เคียง Binance | 2.7, R-01, D-05 ✅ |
| Candlestick Chart แบบ Trading Terminal, หลาย Timeframe, Indicators | 2.8, D-08 ✅, D-09 ✅ |
| Strategy Engine, Trading Bot | 2.9, D-06 ✅, D-07 ✅ (ไม่มี Backtesting) |
| Portfolio Risk Management | 2.10 |
| Performance Analytics และเปรียบเทียบ Portfolio | 2.11 |
| AI Chart Analysis (Future) | 5.3, A-23 |
| Pricing Plan Free/Pro/Advanced | 2.14, D-11 ✅, D-21 |
| Paper ก่อน Live | 5.1, 5.2 |
| GCP + VM เดียว | 2.15, D-18 ✅ |
| Principles 1–10 | 1.4 (P-01..P-10) |
