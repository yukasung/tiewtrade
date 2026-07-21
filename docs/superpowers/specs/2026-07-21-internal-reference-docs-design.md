> **สถานะ: Superseded** — เอกสารนี้ถูกแทนที่โดย `docs/superpowers/specs/2026-07-21-project-documentation-roadmap-design.md` และ `docs/superpowers/plans/2026-07-21-tiewtrade-system-documentation.md` เนื้อหาด้านล่างเก็บไว้เป็นประวัติเท่านั้น และห้ามใช้เป็นข้อกำหนด reader-facing metadata

# Internal Product & Engineering Reference Docs Design

## 1. เป้าหมาย

สร้าง Nextra documentation website สำหรับอ้างอิง Product และ Engineering ของ TiewTrade V2 ภายในทีม โดยทำหน้าที่เป็น presentation layer ที่อ่านและค้นหัวข้อได้ง่าย ขณะที่เอกสาร Markdown ใน repository root และ ADR ยังคงเป็น Source of Truth

รอบแรกส่งมอบเฉพาะ local development และ production build verification ไม่มี deployment หรือ CI

## 2. กลุ่มผู้อ่าน

- เจ้าของผลิตภัณฑ์
- ผู้ทดสอบ Internal Alpha
- นักพัฒนาและ coding agent ที่ต้องทำความเข้าใจ domain, architecture และลำดับงาน

เนื้อหาใช้ภาษาไทย โดยคงชื่อไฟล์, module, class, function, variable และคำศัพท์ Binance เป็นภาษาอังกฤษ

## 3. Source of Truth

ลำดับความเป็นเจ้าของข้อมูล:

1. `PRODUCT.md` — product scope, strategy rules, capital rules, safety และสิ่งที่ไม่ทำ
2. `CONTEXT.md` — domain glossary และความหมายของ state/lifecycle
3. `ARCHITECTURE.md` — module ownership, interfaces และ dependency rules
4. `docs/adr/` — เหตุผลและประวัติการตัดสินใจด้านสถาปัตยกรรม
5. `PROJECT_PLAN.md` — milestones, gates และลำดับการส่งมอบ

Nextra pages เป็น curated summaries ของเอกสารเหล่านี้ ไม่ใช่ Source of Truth แยกต่างหาก Linear ใช้ติดตามงานสร้างและปรับเอกสาร ไม่ใช้เป็นที่เก็บ business rules หลัก

## 4. Folder Ownership

```text
tiewtrade/
├── PRODUCT.md
├── CONTEXT.md
├── ARCHITECTURE.md
├── PROJECT_PLAN.md
├── docs/
│   ├── adr/
│   └── superpowers/
│       ├── plans/
│       └── specs/
└── docs-site/
    ├── app/
    │   ├── layout.tsx
    │   └── [[...mdxPath]]/
    │       └── page.tsx
    ├── content/
    │   ├── index.mdx
    │   ├── product.mdx
    │   ├── domain.mdx
    │   ├── architecture.mdx
    │   ├── strategy.mdx
    │   ├── safety.mdx
    │   ├── delivery.mdx
    │   └── decisions.mdx
    ├── public/
    ├── mdx-components.tsx
    ├── next.config.mjs
    ├── package.json
    └── tsconfig.json
```

Ownership rules:

- Root Markdown และ ADR เก็บรายละเอียดที่ coding agent ต้องอ่านก่อน implement
- `docs-site/` เก็บ Next.js/Nextra application และเนื้อหาที่จัดรูปแบบเพื่อคนอ่าน
- `docs/` ไม่เก็บ Node project, `node_modules`, `.next` หรือ build output
- Python application อยู่ภายใต้ `src/tiewtrade/` และไม่มี runtime dependency กับ `docs-site/`
- ไม่ใช้ symlink เพื่อคงความเข้ากันได้กับ Windows ในอนาคต

## 5. Technology

- Next.js
- React
- Nextra 4 App Router
- `nextra-theme-docs`
- TypeScript
- npm

Dependencies ของ documentation website ติดตั้งภายใน `docs-site/` ด้วยคำสั่ง:

```bash
npm i next react react-dom nextra nextra-theme-docs
```

รอบนี้ไม่เพิ่ม external search service, analytics, authentication หรือ content generation pipeline

## 6. Information Architecture

### 6.1 Overview

อธิบายวัตถุประสงค์ของ TiewTrade V2, Internal Alpha, Paper-first delivery และวิธีใช้ reference site โดยลิงก์ไปยังหัวข้อหลัก

### 6.2 Product

สรุปจาก `PRODUCT.md`:

- Internal Alpha scope
- BTCUSDT completed candle 5 นาที
- Paper → Live Spot → Live Futures delivery gates
- Account Profile และ Session constraints
- สิ่งที่ไม่ทำ

### 6.3 Domain

สรุปจาก `CONTEXT.md`:

- Account Profile
- Bot Session
- Versioned Preset
- completed candle
- Entry Intent, Entry และ Entry Pair
- Basket และ Basket Take Profit
- Cooldown Month
- Trading Capital, Spot Reserve และ Collateral Buffer
- Paper, Live Spot และ Live Futures
- Recovery และ Reconciliation

### 6.4 Architecture

สรุปจาก `ARCHITECTURE.md` และ ADR:

- feature-first modular monolith
- module ownership
- consumer-owned interfaces
- dependency rules
- Paper/Live policy sharing และ execution adapter separation
- persistence, runtime, UI และ integrations boundaries

### 6.5 Strategy

สรุป RSI Step Grid:

- RSI reset และ entry conditions
- ATR และ Basket Take Profit formula
- Entry Pair/Cooldown Month lifecycle
- Spot/Futures capital allocation
- conservative Paper fill

### 6.6 Safety

สรุป:

- Trading Safety ระหว่าง development
- Live Preflight และ explicit confirmation
- stale market-data fail closed
- idempotency
- shutdown/recovery/reconciliation
- risk limits ที่ยังไม่บังคับใน Internal Alpha

### 6.7 Delivery

สรุปจาก `PROJECT_PLAN.md` และเชื่อมไปยัง Linear Main/Sub-issues:

- Paper Trading Complete
- Live Spot
- Live Futures
- current frontier และ blockers
- DEV-74 ถึง DEV-80 สำหรับ Paper Spot Core Tracer Bullet

Linear status ไม่ถูกคัดลอกมาเป็น business truth และไม่ต้อง sync อัตโนมัติ

### 6.8 Decisions

แสดง ADR index พร้อมสถานะ, decision summary, superseded relationships และลิงก์ไปยัง ADR source

## 7. Curated Summary Contract

ทุก reference page ต้องมี:

- ชื่อหัวข้อและวัตถุประสงค์
- concise summary ที่ไม่เปลี่ยนความหมายของ Source of Truth
- `Source file`
- `Last reviewed date` รูปแบบ `YYYY-MM-DD`
- ลิงก์ไปยังหัวข้อที่เกี่ยวข้อง

เมื่อ business rule เปลี่ยน:

1. แก้ Source of Truth ก่อน
2. ปรับ Nextra summary ใน commit เดียวกัน
3. อัปเดต `Last reviewed date`
4. ตรวจ internal links และ production build

ไม่สร้าง automated content generation ใน Internal Alpha รอบนี้ หาก curated summaries กลายเป็นภาระซ้ำซ้อนจึงค่อยพิจารณา generation ใน ADR ใหม่

## 8. Visual Direction

- ใช้ `nextra-theme-docs` เป็นฐาน
- light-first neutral/blue appearance
- typography และ contrast ต้องอ่านง่าย
- navigation แสดง Product, Domain, Architecture, Strategy, Safety, Delivery และ Decisions อย่างชัดเจน
- ไม่สร้าง custom design system หรือ component library ในรอบนี้
- รองรับ viewport ขนาด desktop และ mobile ตามความสามารถของ theme

## 9. Main Issue และ Sub-issues

### Main Issue — Internal Product & Engineering Reference Docs

ส่งมอบ Nextra reference site ที่อ้างอิงเอกสารหลักของ TiewTrade V2 และ build ในเครื่องได้

### Sub-issue 1 — สร้าง Nextra foundation และ Product Overview

**Blocked by:** ไม่มี

ส่งมอบ `docs-site/`, Nextra App Router, Docs Theme, navigation เริ่มต้น และ Product page ที่อ้างอิง `PRODUCT.md`

### Sub-issue 2 — กำหนด Domain Glossary และ Domain Reference

**Blocked by:** Sub-issue 1

ส่งมอบ `CONTEXT.md` และ Domain page ที่กำหนดคำศัพท์หลักเพียงความหมายเดียว

### Sub-issue 3 — กำหนด Modular Monolith Architecture

**Blocked by:** Sub-issue 2

ส่งมอบ `ARCHITECTURE.md`, ADR สำหรับ feature-first modular monolith และ Architecture page

### Sub-issue 4 — จัดทำ Strategy และ Trading Safety Reference

**Blocked by:** Sub-issues 2 และ 3

ส่งมอบ Strategy และ Safety pages ที่อ้างอิงกฎใน `PRODUCT.md`, `CONTEXT.md` และ `ARCHITECTURE.md`

### Sub-issue 5 — จัดทำ Delivery Roadmap และ Decisions Reference

**Blocked by:** Sub-issue 3

ส่งมอบ `PROJECT_PLAN.md`, Delivery page, Decisions page และลิงก์ DEV-74 ถึง DEV-80

### Sub-issue 6 — ตรวจความสอดคล้องและ Production Build

**Blocked by:** Sub-issues 4 และ 5

ตรวจ source references, navigation, internal links, responsive layout, accessibility เบื้องต้น และ production build

Main Issue เป็น tracking issue ส่วน Sub-issues อยู่ใน `Todo`, Project `Tiewtrade`, Milestone `Phase 1 — Internal Alpha` และติด labels `Feature` กับ `ready-for-agent`

## 10. Error Handling และ Validation

- หาก Source of Truth ที่ page อ้างถึงไม่มีอยู่ ให้ verification ล้มเหลว
- หาก internal route/link ไม่ถูกต้อง ต้องแก้ก่อนปิด Sub-issue
- หาก `npm run build` ล้มเหลว ห้ามรายงานว่า documentation site เสร็จ
- หาก Source of Truth และ summary ขัดแย้ง ให้ Source of Truth มีผลและแก้ summary ก่อน merge
- ห้ามแสดง secret, API credentials, account identifiers จริง หรือข้อมูลบัญชีจริง

## 11. Acceptance Criteria

- `docs-site/` มี dependencies และ scripts แยกจาก Python application
- ใช้ Nextra 4 App Router และ `nextra-theme-docs`
- เปิดหน้า Overview, Product, Domain, Architecture, Strategy, Safety, Delivery และ Decisions ได้
- Root Markdown และ ADR เป็น Source of Truth
- ทุก page ระบุ Source file และ Last reviewed date
- Navigation และ internal links ถูกต้อง
- Source references ชี้ไปยังไฟล์ที่มีอยู่จริง
- ไม่มี secret หรือข้อมูลบัญชีจริง
- responsive layout ใช้งานได้ใน viewport desktop และ mobile
- README อธิบายการติดตั้ง, `npm run dev` และ `npm run build`
- `npm run build` ผ่าน
- ไม่มี deployment และ CI ในรอบนี้

## 12. Non-goals

- คู่มือผู้ใช้ Desktop application ฉบับสมบูรณ์
- Deployment ไป GitHub Pages หรือ Vercel
- CI workflow
- Authentication และ private portal
- Analytics
- External search service
- Automated Linear status synchronization
- Automated Root Markdown-to-MDX generation
- Custom component library
