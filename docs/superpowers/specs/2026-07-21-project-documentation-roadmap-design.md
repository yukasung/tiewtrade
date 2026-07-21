# TiewTrade System Documentation Design

## เป้าหมาย

สร้าง Project Documentation ที่อธิบายว่า TiewTrade V2 ทำงานอย่างไร ตั้งแต่ข้อมูลตลาดเข้าสู่ระบบ การสร้างสัญญาณ การเปิด Entry การดูแล Basket การทำ Take Profit ไปจนถึง shutdown และ recovery ผู้อ่านต้องเข้าใจกระบวนการหลักได้จากเว็บไซต์โดยไม่ต้องเปิดไฟล์อื่นประกอบ

เอกสารต้องไม่แสดงข้อมูลจาก Issue Tracker, issue identifier, status, `Source file` หรือ `Last reviewed date`

## กลุ่มผู้อ่าน

- Product owner ที่ต้องการตรวจว่าพฤติกรรมระบบตรงกับข้อตกลง
- ผู้ทดสอบ Internal Alpha ที่ต้องเข้าใจ expected behavior
- นักพัฒนาและ coding agent ที่ต้องเข้าใจ flow ก่อนแก้ระบบ

เนื้อหาอธิบายเป็นภาษาไทย โดยใช้ชื่อ module, class, function, parameter และคำศัพท์ Binance เป็นภาษาอังกฤษ

## หลักการนำเสนอ

- แต่ละหน้าตอบคำถามเดียวและอ่านจบได้ในตัวเอง
- เริ่มจากภาพรวม ก่อนลงรายละเอียด rules และ edge cases
- ใช้ Mermaid diagram เมื่อมีลำดับขั้น สถานะ หรือ dependency ตั้งแต่สามส่วนขึ้นไป
- ใช้ตารางสำหรับค่าตั้งต้น เงื่อนไข และการเปรียบเทียบ Spot/Futures หรือ Paper/Live
- ใช้ข้อความเตือนสำหรับ safety constraints ที่ห้ามละเมิด
- ไม่ใช้เอกสารเป็น changelog, backlog หรือ dashboard สถานะงาน

## Information Architecture

### Overview

อธิบายวัตถุประสงค์ของ Project Documentation และแผนที่การอ่านเอกสารทั้งหมด

Diagram: high-level system flow จาก completed candle ไปสู่ execution, persistence และ UI

### Product Overview

อธิบาย Product Vision, Internal Alpha scope, supported markets, Account Profile และ Paper-first delivery gates

Table: supported scope และสิ่งที่ยังไม่อยู่ใน Internal Alpha

### System Architecture

อธิบาย feature-first modular monolith, ขอบเขตความรับผิดชอบของ module, dependency direction และการแยก policy ออกจาก execution adapter

Diagrams:

- module dependency flowchart
- Paper/Live adapter boundary

### Trading Process

อธิบาย end-to-end process ตั้งแต่รับ completed candle 5 นาที จน Basket ปิดหรือรอ candle ถัดไป

Diagrams:

- trading pipeline flowchart
- entry-to-take-profit sequence diagram

### RSI Step Grid Strategy

อธิบาย RSI reset, entry conditions, ATR, completed-candle constraints, deduplication และการ consume reset signal หลัง Fill

Diagram: strategy signal state flow

### Basket Lifecycle

อธิบาย Basket creation, Entry Fill, weighted average entry price, Take Profit recalculation, Basket close และการเริ่ม Basket ใหม่

Diagram: Basket state diagram

### Entry Pair and Cooldown Month

อธิบายการจับคู่ Entries 1–2 ถึง 9–10, เงื่อนไขข้ามเดือน UTC, Cooldown Month และการเปิด Pair ถัดไป

Diagram: Entry Pair/Cooldown state diagram พร้อมตัวอย่าง timeline

### Capital Allocation

อธิบาย Available Capital, Trading Capital, Spot Reserve, Futures Collateral Buffer, leverage cap และขนาดของแต่ละ Entry

Diagrams and tables:

- เปรียบเทียบ Spot/Futures allocation
- capital flow diagram
- ตัวอย่างคำนวณจากเงินทุนสมมติ

### Paper Trading

อธิบาย conservative candle fill, fee, slippage, funding, replay determinism และเหตุผลที่ป้องกัน look-ahead bias

Diagram: candle N signal ไปยัง candle N+1 fill และ Take Profit eligibility

### Live Trading Safety

อธิบาย explicit confirmation, Preflight, idempotency, stale-data fail-closed, account isolation, OS Keyring และข้อห้ามระหว่างการพัฒนา

Diagrams:

- Live Session startup gate
- stale market-data decision flow

### Recovery and Reconciliation

อธิบาย Stop Session, startup recovery, local/exchange state comparison, mismatch handling และเงื่อนไข resume

Diagram: recovery state machine และ reconciliation sequence

## Navigation and Reading Order

Navigation เรียงตาม mental model ของผู้อ่าน:

1. Overview
2. Product Overview
3. System Architecture
4. Trading Process
5. RSI Step Grid Strategy
6. Basket Lifecycle
7. Entry Pair and Cooldown Month
8. Capital Allocation
9. Paper Trading
10. Live Trading Safety
11. Recovery and Reconciliation

Overview แสดง recommended reading paths สำหรับ Product, Tester และ Developer โดยทุกหน้ามีลิงก์ไปหัวข้อก่อนหน้าและหัวข้อถัดไปตามความเกี่ยวข้อง

## Diagram Implementation

ใช้ Mermaid ใน MDX เพื่อให้ source ของ diagram แก้ไขและ review ได้พร้อมเนื้อหา หลีกเลี่ยงภาพ bitmap สำหรับ process diagrams เพราะค้นข้อความไม่ได้และแก้ไขยาก

Diagram ต้อง:

- มีชื่อและคำอธิบายสั้นก่อน diagram
- ใช้คำศัพท์ชุดเดียวกับเนื้อหา
- อ่านได้ทั้ง desktop และ mobile โดยไม่บังคับให้ข้อความเล็กเกินไป
- มีข้อความอธิบายกระบวนการหลัง diagram เพื่อไม่พึ่งภาพเพียงอย่างเดียว
- ไม่ใส่ข้อมูลบัญชี, credentials หรือค่าจริงของผู้ใช้

หาก Mermaid renderer ทำให้ Nextra build ไม่เสถียร ให้ใช้ MDX component ที่ render SVG จากข้อมูลคงที่แทน โดยยังเก็บ diagram definition เป็น text ที่ review ได้

## Content Ownership

Reader-facing pages ต้อง self-contained และไม่แสดง path ของเอกสารภายใน อย่างไรก็ตาม business rules ต้องสอดคล้องกับเอกสารโครงการที่ได้รับอนุมัติ การเปลี่ยนกฎต้องแก้เอกสารที่เกี่ยวข้องและ Project Documentation ใน change เดียวกันเพื่อป้องกันข้อมูลไม่ตรงกัน

Project Documentation ไม่บันทึกสถานะงาน ไม่แสดง backlog และไม่ทำงานแทน Issue Tracker

## Validation

Automated verification ต้องตรวจว่า:

- ทุก route ใน navigation เปิดได้
- ไม่มี Issue Tracker URL, issue identifier, `Source file` หรือ `Last reviewed date` ใน reader-facing content
- แต่ละหน้ามีหัวข้อและ diagram ตาม design
- internal links ไม่เสีย
- Mermaid/MDX compile ผ่าน
- production build ผ่าน
- layout ใช้งานได้ที่ desktop 1440×900 และ mobile 390×844
- ไม่มี credentials, secrets หรือข้อมูลบัญชีจริง

## Error Handling

- หากเนื้อหาสองหน้าขัดแย้งกัน ต้องหยุดและแก้กฎให้เหลือความหมายเดียวก่อนเผยแพร่
- หาก diagram กับคำอธิบายไม่ตรงกัน ให้ถือว่า verification ไม่ผ่าน
- หาก diagram render ไม่ได้ หน้าไม่ควรล้มทั้งหมด แต่ต้องแสดงคำอธิบายกระบวนการที่อ่านได้
- หาก build หรือ internal-link verification ล้มเหลว ห้ามรายงานว่า documentation เสร็จ

## Non-goals

- Deployment และ CI
- Authentication, analytics หรือ external search service
- Automated status synchronization
- Generated documentation จาก source code
- คู่มือ Binance หรือคำแนะนำการลงทุนทั่วไป
- การเปลี่ยน business rules ของ TiewTrade V2
