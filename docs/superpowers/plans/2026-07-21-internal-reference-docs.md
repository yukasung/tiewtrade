> **สถานะ: Superseded** — เอกสารนี้ถูกแทนที่โดย `docs/superpowers/specs/2026-07-21-project-documentation-roadmap-design.md` และ `docs/superpowers/plans/2026-07-21-tiewtrade-system-documentation.md` เนื้อหาด้านล่างเก็บไว้เป็นประวัติเท่านั้น และห้ามใช้เป็นข้อกำหนด reader-facing metadata

# Internal Product & Engineering Reference Docs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** สร้าง Nextra reference site ภาษาไทยสำหรับ Product และ Engineering ของ TiewTrade V2 โดยใช้ Root Markdown/ADR เป็น Source of Truth และตรวจ production build ในเครื่องได้

**Architecture:** `docs-site/` เป็น Next.js/Nextra presentation application แยกจาก Python application และไม่มี runtime dependency ต่อกัน Curated MDX pages สรุป Source of Truth พร้อม source reference/date โดย Node validation script ตรวจว่า source paths มีอยู่จริงก่อน build

**Tech Stack:** Next.js, React, TypeScript, Nextra 4 App Router, `nextra-theme-docs`, npm, Node.js built-in test runner

## Global Constraints

- Root Markdown และ `docs/adr/` เป็น Source of Truth; Nextra เป็น curated presentation layer
- เนื้อหาเอกสารเป็นภาษาไทย แต่ filenames, module/class/function names และ Binance terms เป็นภาษาอังกฤษ
- ทุก reference page ต้องระบุ `Source file` และ `Last reviewed date` รูปแบบ `YYYY-MM-DD`
- ห้ามใช้ symlink และห้ามสร้าง automated Markdown-to-MDX generation
- ห้ามใส่ API credentials, account identifiers จริง หรือข้อมูลบัญชีจริง
- รอบนี้รองรับ local development และ `npm run build` เท่านั้น ไม่มี deployment หรือ CI
- ใช้ `nextra-theme-docs` และ App Router ตามเอกสารทางการของ Nextra 4
- ไม่เพิ่ม authentication, analytics, external search service หรือ custom component library
- ห้ามแก้หรือนำ `docs/superpowers/plans/tiewtrade.code-workspace` เข้า commit

## File Map

```text
.gitignore
CONTEXT.md
ARCHITECTURE.md
PROJECT_PLAN.md
docs/adr/0001-use-feature-first-modular-monolith.md
docs-site/
├── app/
│   ├── layout.tsx
│   └── [[...mdxPath]]/page.tsx
├── content/
│   ├── _meta.ts
│   ├── index.mdx
│   ├── product.mdx
│   ├── domain.mdx
│   ├── architecture.mdx
│   ├── strategy.mdx
│   ├── safety.mdx
│   ├── delivery.mdx
│   └── decisions.mdx
├── scripts/check-source-references.mjs
├── tests/source-references.test.mjs
├── mdx-components.tsx
├── next.config.mjs
├── next-env.d.ts
├── package.json
├── package-lock.json
├── tsconfig.json
└── README.md
```

---

### Task 1: Nextra foundation and Product Overview

**Files:**
- Create: `.gitignore`
- Create: `docs-site/package.json`
- Create: `docs-site/package-lock.json` through npm
- Create: `docs-site/tsconfig.json`
- Create: `docs-site/next.config.mjs`
- Create: `docs-site/next-env.d.ts`
- Create: `docs-site/mdx-components.tsx`
- Create: `docs-site/app/layout.tsx`
- Create: `docs-site/app/[[...mdxPath]]/page.tsx`
- Create: `docs-site/content/_meta.ts`
- Create: `docs-site/content/index.mdx`
- Create: `docs-site/content/product.mdx`
- Create: `docs-site/scripts/check-source-references.mjs`
- Create: `docs-site/tests/source-references.test.mjs`

**Interfaces:**
- Consumes: `PRODUCT.md`
- Produces: Nextra shell, `/` Overview, `/product`, `validateSourceReferences()` และ npm scripts ที่ทุก task ถัดไปใช้

- [ ] **Step 1: สร้าง package และติดตั้ง dependencies ตามคำสั่งที่อนุมัติ**

```bash
mkdir -p docs-site
cd docs-site
npm init -y
npm i next react react-dom nextra nextra-theme-docs
npm i -D typescript @types/node @types/react @types/react-dom @types/mdx
```

Expected: สร้าง `docs-site/package.json`, `docs-site/package-lock.json` และติดตั้ง dependencies สำเร็จ

- [ ] **Step 2: กำหนด scripts และ TypeScript configuration**

กำหนด package metadata/scripts โดยไม่เขียนทับ dependency versions ที่ npm บันทึกไว้:

```bash
cd docs-site
npm pkg set name=tiewtrade-docs
npm pkg set private=true --json
npm pkg set scripts.dev="next dev"
npm pkg set scripts.build="npm run check:references && next build"
npm pkg set scripts.start="next start"
npm pkg set scripts.test="node --test tests/*.test.mjs"
npm pkg set scripts.check:references="node scripts/check-source-references.mjs"
```

```json
// docs-site/tsconfig.json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": false,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }]
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

```typescript
// docs-site/next-env.d.ts
/// <reference types="next" />
/// <reference types="next/image-types/global" />
```

- [ ] **Step 3: เขียน failing source-reference test**

```javascript
// docs-site/tests/source-references.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { validateSourceReferences } from '../scripts/check-source-references.mjs'

test('all curated pages reference existing source files', async () => {
  const failures = await validateSourceReferences()
  assert.deepEqual(failures, [])
})
```

Run: `cd docs-site && npm test`

Expected: FAIL เพราะ `scripts/check-source-references.mjs` ยังไม่มี

- [ ] **Step 4: Implement source-reference validator สำหรับสองหน้าแรก**

```javascript
// docs-site/scripts/check-source-references.mjs
import { access, readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const docsRoot = path.dirname(fileURLToPath(import.meta.url))
const siteRoot = path.resolve(docsRoot, '..')
const repositoryRoot = path.resolve(siteRoot, '..')

export const references = {
  'content/index.mdx': ['PRODUCT.md'],
  'content/product.mdx': ['PRODUCT.md']
}

export async function validateSourceReferences() {
  const failures = []
  for (const [page, sources] of Object.entries(references)) {
    const content = await readFile(path.join(siteRoot, page), 'utf8')
    if (!/Last reviewed date: \d{4}-\d{2}-\d{2}/.test(content)) {
      failures.push(`${page}: missing Last reviewed date`)
    }
    for (const source of sources) {
      try {
        await access(path.join(repositoryRoot, source))
      } catch {
        failures.push(`${page}: missing source ${source}`)
      }
      if (!content.includes(`Source file: \`${source}\``)) {
        failures.push(`${page}: does not declare ${source}`)
      }
    }
  }
  return failures
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const failures = await validateSourceReferences()
  if (failures.length) {
    console.error(failures.join('\n'))
    process.exitCode = 1
  }
}
```

- [ ] **Step 5: สร้าง Nextra App Router shell**

```javascript
// docs-site/next.config.mjs
import nextra from 'nextra'

const withNextra = nextra()
export default withNextra({})
```

```tsx
// docs-site/mdx-components.tsx
import type { MDXComponents } from 'mdx/types'
import { useMDXComponents as getThemeComponents } from 'nextra-theme-docs'

const themeComponents = getThemeComponents()

export function useMDXComponents(components: MDXComponents): MDXComponents {
  return { ...themeComponents, ...components }
}
```

```tsx
// docs-site/app/layout.tsx
import type { Metadata } from 'next'
import { Head } from 'nextra/components'
import { getPageMap } from 'nextra/page-map'
import { Footer, Layout, Navbar } from 'nextra-theme-docs'
import 'nextra-theme-docs/style.css'

export const metadata: Metadata = {
  title: { default: 'TiewTrade Reference', template: '%s — TiewTrade Reference' },
  description: 'Internal product and engineering reference for TiewTrade V2'
}

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="th" dir="ltr" suppressHydrationWarning>
      <Head />
      <body>
        <Layout
          navbar={<Navbar logo={<strong>TiewTrade Reference</strong>} />}
          pageMap={await getPageMap()}
          docsRepositoryBase="https://github.com/yukasung/tiewtrade/tree/main/docs-site"
          footer={<Footer>TiewTrade Internal Alpha</Footer>}
        >
          {children}
        </Layout>
      </body>
    </html>
  )
}
```

```tsx
// docs-site/app/[[...mdxPath]]/page.tsx
import { generateStaticParamsFor, importPage } from 'nextra/pages'
import { useMDXComponents as getMDXComponents } from '../../mdx-components'

export const generateStaticParams = generateStaticParamsFor('mdxPath')

export async function generateMetadata(props: { params: Promise<{ mdxPath?: string[] }> }) {
  const params = await props.params
  const { metadata } = await importPage(params.mdxPath)
  return metadata
}

const Wrapper = getMDXComponents().wrapper

export default async function Page(props: { params: Promise<{ mdxPath?: string[] }> }) {
  const params = await props.params
  const { default: MDXContent, toc, metadata, sourceCode } = await importPage(params.mdxPath)
  return (
    <Wrapper toc={toc} metadata={metadata} sourceCode={sourceCode}>
      <MDXContent {...props} params={params} />
    </Wrapper>
  )
}
```

- [ ] **Step 6: สร้าง navigation และ Product pages**

```typescript
// docs-site/content/_meta.ts
export default {
  index: 'Overview',
  product: 'Product'
}
```

```mdx
---
title: Overview
description: จุดเริ่มต้นสำหรับเอกสารอ้างอิง TiewTrade V2
---

# TiewTrade V2 Reference

เอกสารสำหรับ Product และ Engineering ของ Binance Trading Bot แบบ Paper-first ในช่วง Internal Alpha

> Source file: `PRODUCT.md`  
> Last reviewed date: 2026-07-21

## เริ่มอ่านจากที่ใด

- [Product](/product) — ขอบเขตและสิ่งที่ไม่ทำ
- [Domain](/domain) — คำศัพท์ที่ใช้ร่วมกัน
- [Architecture](/architecture) — module ownership และ dependency rules
- [Strategy](/strategy) — RSI Step Grid และ Basket lifecycle
- [Safety](/safety) — Paper/Live safety และ recovery
- [Delivery](/delivery) — milestones และ Linear frontier
```

```mdx
---
title: Product
description: ขอบเขต Internal Alpha ของ TiewTrade V2
---

# Product

> Source file: `PRODUCT.md`  
> Last reviewed date: 2026-07-21

TiewTrade V2 รองรับ BTCUSDT completed candle 5 นาที โดยส่งมอบตามลำดับ Paper Trading, Live Spot และ Live USDⓈ-M Futures

## Internal Alpha

- macOS เป็นแพลตฟอร์มแรก
- RSI Step Grid พร้อม Versioned Preset เพียงกลยุทธ์เดียว
- สูงสุด 5 Account Profiles และหนึ่ง Active Bot Session ต่อ Profile
- Local single-user ไม่มี Login, License หรือ Cloud Sync

## Delivery gates

Live Spot เริ่มได้หลัง Paper acceptance ผ่าน และ Live Futures เริ่มได้หลัง Live Spot acceptance ผ่านเท่านั้น
```

- [ ] **Step 7: Ignore build artifacts, run tests and build**

```gitignore
# .gitignore
docs-site/node_modules/
docs-site/.next/
docs-site/out/
```

Run: `cd docs-site && npm test`

Expected: `1 passed`

Run: `cd docs-site && npm run build`

Expected: Next.js production build สำเร็จและสร้าง routes `/` กับ `/product`

- [ ] **Step 8: Commit foundation**

```bash
git add .gitignore docs-site
git commit -m "docs: add Nextra reference foundation"
```

---

### Task 2: Domain Glossary and Domain Reference

**Files:**
- Create: `CONTEXT.md`
- Create: `docs-site/content/domain.mdx`
- Modify: `docs-site/content/_meta.ts`
- Modify: `docs-site/scripts/check-source-references.mjs`

**Interfaces:**
- Consumes: `PRODUCT.md`, Nextra shell และ validator จาก Task 1
- Produces: canonical domain vocabulary ที่ Task 3–5 ต้องใช้

- [ ] **Step 1: เพิ่ม failing reference mapping**

เพิ่ม entry นี้ใน `references`:

```javascript
'content/domain.mdx': ['CONTEXT.md']
```

Run: `cd docs-site && npm test`

Expected: FAIL เพราะ `CONTEXT.md` และ `content/domain.mdx` ยังไม่มี

- [ ] **Step 2: สร้าง canonical glossary**

```markdown
# TiewTrade Domain Context

## Time and Market Data

- **completed candle** — BTCUSDT 5-minute candle ที่ปิดแล้วและมี `open_time` แบบ UTC
- **data freshness** — สถานะว่าข้อมูลตลาดต่อเนื่องถึง completed candle ล่าสุดโดยไม่มี gap

## Account and Session

- **Account Profile** — การตั้งค่าบัญชี Binance/Sub-account หนึ่งรายการ; secret เก็บใน OS Keyring
- **Bot Session** — การทำงานของ Bot หนึ่งชุดที่ผูกกับ Account Profile, Mode และ Preset version
- **Versioned Preset** — immutable strategy parameters ที่ Session อ้างอิงด้วย version

## Strategy and Trading

- **Entry Intent** — การตัดสินใจขอเปิด Entry จาก completed candle; ยังไม่ใช่ Fill
- **Entry** — การซื้อที่ Fill แล้วและเป็นส่วนหนึ่งของ Basket
- **Entry Pair** — คู่ Entries 1–2, 3–4, 5–6, 7–8 หรือ 9–10
- **Basket** — กลุ่ม Entries ที่ปิดพร้อมกันด้วย Basket Take Profit
- **Basket Take Profit** — weighted average entry price บวก ATR(14) คูณ 3
- **Cooldown Month** — เดือน UTC ที่ห้ามเพิ่ม Entry หลัง Pair ก่อนหน้าครบสองไม้และค้างข้ามสิ้นเดือน

## Capital and Execution

- **Trading Capital** — เงินส่วนที่ใช้คำนวณ Entry sizes
- **Spot Reserve** — 20% ของ Spot Available Capital ที่ไม่ใช้สร้าง Entry
- **Collateral Buffer** — 50% ของ Futures Available Capital ที่ไม่ใช้สร้าง Entry แต่ยอมเสี่ยงเพื่อเลื่อน liquidation
- **Paper** — execution simulation ที่ไม่ส่ง order ไป Binance
- **Live Spot** — Spot execution ด้วย Binance account จริงหลังผ่าน Live Gate
- **Live Futures** — USDⓈ-M Futures execution ด้วย Cross Margin หลังผ่าน Live Gate

## Operations

- **Preflight** — การตรวจ account/exchange state ก่อนเริ่ม Live Session
- **Reconciliation** — การเปรียบเทียบ local state กับ exchange state
- **Recovery** — กระบวนการกู้ Session หลัง restart โดยบล็อก Entry ใหม่จน state ตรงกัน
```

- [ ] **Step 3: สร้าง Domain page**

```mdx
---
title: Domain
description: คำศัพท์หลักของ TiewTrade V2
---

# Domain

> Source file: `CONTEXT.md`  
> Last reviewed date: 2026-07-21

ใช้คำศัพท์ต่อไปนี้ให้มีความหมายเดียวกันในโค้ด เอกสาร และ Linear Issues

## Trading lifecycle

`completed candle` → `Entry Intent` → `Entry` → `Entry Pair` → `Basket` → `Basket Take Profit`

## Operational lifecycle

`Preflight` ใช้ก่อน Live Session ส่วน `Reconciliation` และ `Recovery` ใช้หลัง restart หรือเมื่อ state ไม่ตรงกัน

## Capital

Spot แยก `Trading Capital` และ `Spot Reserve`; Futures แยก `Trading Capital` และ `Collateral Buffer`
```

อัปเดต navigation:

```typescript
// docs-site/content/_meta.ts
export default {
  index: 'Overview',
  product: 'Product',
  domain: 'Domain'
}
```

- [ ] **Step 4: Verify and commit**

Run: `cd docs-site && npm test && npm run build`

Expected: reference test และ production build ผ่าน พร้อม route `/domain`

```bash
git add CONTEXT.md docs-site/content/domain.mdx docs-site/content/_meta.ts docs-site/scripts/check-source-references.mjs
git commit -m "docs: define TiewTrade domain vocabulary"
```

---

### Task 3: Modular Monolith Architecture Reference

**Files:**
- Create: `ARCHITECTURE.md`
- Create: `docs/adr/0001-use-feature-first-modular-monolith.md`
- Create: `docs-site/content/architecture.mdx`
- Modify: `docs-site/content/_meta.ts`
- Modify: `docs-site/scripts/check-source-references.mjs`

**Interfaces:**
- Consumes: domain vocabulary จาก Task 2
- Produces: module ownership/dependency rules สำหรับ code plans และ Decisions page

- [ ] **Step 1: เพิ่ม failing mappings**

```javascript
'content/architecture.mdx': [
  'ARCHITECTURE.md',
  'docs/adr/0001-use-feature-first-modular-monolith.md'
]
```

Run: `cd docs-site && npm test`

Expected: FAIL เพราะ architecture sources/page ยังไม่มี

- [ ] **Step 2: สร้าง Architecture Source of Truth**

```markdown
# TiewTrade Architecture

## Style

TiewTrade V2 เป็น feature-first modular monolith: deploy เป็น Desktop application เดียว แต่แยก modules ตาม business capability

## Modules

- `market_data` — completed candles, continuity และ symbol facts
- `strategies/rsi_step_grid` — Preset, indicators และ Entry Intent
- `trading` — Basket, Entry Pair, capital และ shared policies
- `paper` — deterministic Paper execution
- `live` — Live preflight, reconciliation และ recovery orchestration
- `integrations/binance` — Binance REST/WebSocket และ Spot/Futures adapters
- `integrations/sqlite` — durable state และ audit persistence
- `ui` — PySide6 views/controllers; ไม่มี trading rules
- `runtime` — startup, workers และ shutdown ordering
- `observability` — logs, notifications และ operational events

## Dependency Rules

1. Strategy และ trading policies ไม่ import Qt, SQLite หรือ Binance SDK
2. UI เรียก application/runtime services และไม่คำนวณ business rules
3. Interfaces อยู่ใน consumer module; integration เป็นผู้ implement
4. Paper/Live ใช้ policies ร่วมกัน แต่ execution adapters แยกกัน
5. ห้ามสร้าง generic base/registry/factory ก่อนมี consumers จริงอย่างน้อยสองราย
6. ห้ามสร้าง catch-all `utils.py`, `interfaces.py`, `models.py` หรือ `repository.py`

## Data Flow

Market adapter → completed candle boundary → RSI Step Grid → Entry Intent → lifecycle/capital policy → Paper/Live executor → persistence/audit → UI projection
```

- [ ] **Step 3: บันทึก architecture decision**

```markdown
# ADR 0001: Use a Feature-First Modular Monolith

- Status: Accepted
- Date: 2026-07-21

## Context

TiewTrade ต้องรองรับ Paper, Live Spot, Live Futures, recovery และ Desktop UI โดยยังเป็น Internal Alpha ที่พัฒนาโดยทีมเล็ก

## Decision

ใช้ feature-first modular monolith แยก business capabilities ภายใน application เดียว Interfaces เป็น consumer-owned และสร้าง abstraction เมื่อมี consumer จริงอย่างน้อยสองราย

## Consequences

- Business rules ทดสอบได้โดยไม่เปิด Qt หรือเชื่อม Binance
- Paper และ Live แชร์ policies แต่เปลี่ยน execution adapter ได้
- การ deploy และ local development เรียบง่ายกว่า distributed services
- ต้องบังคับ dependency rules ใน review เพื่อไม่ให้ modules เชื่อมกันโดยตรงแบบไร้ขอบเขต
```

- [ ] **Step 4: สร้าง Architecture page**

```mdx
---
title: Architecture
description: Module ownership และ dependency rules
---

# Architecture

> Source file: `ARCHITECTURE.md`  
> Source file: `docs/adr/0001-use-feature-first-modular-monolith.md`  
> Last reviewed date: 2026-07-21

TiewTrade ใช้ feature-first modular monolith เพื่อเก็บ business rules ให้เป็นอิสระจาก Qt, SQLite และ Binance transports

## Data flow

Market data → Strategy → Entry Intent → Trading policies → Execution → Persistence/Audit → UI

## Boundary rule

Interfaces อยู่ฝั่ง consumer และ integrations เป็นผู้ implement ห้ามสร้าง generic abstraction ก่อนมี consumer ตัวที่สอง
```

```typescript
// docs-site/content/_meta.ts
export default {
  index: 'Overview',
  product: 'Product',
  domain: 'Domain',
  architecture: 'Architecture'
}
```

- [ ] **Step 5: Verify and commit**

Run: `cd docs-site && npm test && npm run build`

Expected: ผ่านและมี route `/architecture`

```bash
git add ARCHITECTURE.md docs/adr docs-site/content/architecture.mdx docs-site/content/_meta.ts docs-site/scripts/check-source-references.mjs
git commit -m "docs: define modular monolith architecture"
```

---

### Task 4: Strategy and Trading Safety Reference

**Files:**
- Create: `docs-site/content/strategy.mdx`
- Create: `docs-site/content/safety.mdx`
- Modify: `docs-site/content/_meta.ts`
- Modify: `docs-site/scripts/check-source-references.mjs`

**Interfaces:**
- Consumes: `PRODUCT.md`, `CONTEXT.md`, `ARCHITECTURE.md`
- Produces: human-readable strategy/safety reference โดยไม่สร้าง Source of Truth ใหม่

- [ ] **Step 1: เพิ่ม failing mappings**

```javascript
'content/strategy.mdx': ['PRODUCT.md', 'CONTEXT.md'],
'content/safety.mdx': ['PRODUCT.md', 'ARCHITECTURE.md']
```

Run: `cd docs-site && npm test`

Expected: FAIL เพราะ Strategy/Safety pages ยังไม่มี

- [ ] **Step 2: สร้าง Strategy page**

```mdx
---
title: Strategy
description: RSI Step Grid และ Basket lifecycle
---

# RSI Step Grid

> Source file: `PRODUCT.md`  
> Source file: `CONTEXT.md`  
> Last reviewed date: 2026-07-21

## Entry

ใช้ completed candle 5 นาทีแบบ Long-only: RSI(14) reset ต่ำกว่า 30 จากนั้น Entry เมื่อ RSI สูงกว่า 50, `close > open` และ `close > reset close`

## Basket Take Profit

`weighted average entry price + ATR(14) × 3` ปัดลงตาม Binance tick size และคำนวณใหม่หลังแต่ละ Entry Fill

## Entry Pair

Entries แบ่งเป็นคู่ 1–2 ถึง 9–10 เมื่อ Pair ครบและค้างข้ามสิ้นเดือน เดือน UTC ถัดไปเป็น Cooldown Month

## Capital

- Spot: Trading Capital 80%, Spot Reserve 20%
- Futures: Trading Capital 50%, Collateral Buffer 50%, Cross Margin, leverage ไม่เกิน 5x
```

- [ ] **Step 3: สร้าง Safety page**

```mdx
---
title: Safety
description: Paper, Live gates และ recovery safety
---

# Trading Safety

> Source file: `PRODUCT.md`  
> Source file: `ARCHITECTURE.md`  
> Last reviewed date: 2026-07-21

## Development

ใช้ Paper และ fake adapters เท่านั้น ห้ามส่ง Live order หรือเก็บ secrets ใน source, fixtures, logs หรือ SQLite

## Live gate

ทุก Live Session ต้องผ่าน Preflight และ explicit confirmation ห้ามเปลี่ยนจาก Paper เป็น Live อัตโนมัติ

## Fail closed

เมื่อ market data ไม่สดให้หยุด Entry ใหม่ คง Take Profit และ backfill/deduplicate ก่อน Resume

## Recovery

หลัง restart ต้อง Reconcile local/exchange state หากไม่ตรงกันให้บล็อก Entry ใหม่และรอผู้ใช้แก้ไข
```

```typescript
// docs-site/content/_meta.ts
export default {
  index: 'Overview',
  product: 'Product',
  domain: 'Domain',
  architecture: 'Architecture',
  strategy: 'Strategy',
  safety: 'Safety'
}
```

- [ ] **Step 4: Verify and commit**

Run: `cd docs-site && npm test && npm run build`

Expected: ผ่านและมี routes `/strategy` กับ `/safety`

```bash
git add docs-site/content/strategy.mdx docs-site/content/safety.mdx docs-site/content/_meta.ts docs-site/scripts/check-source-references.mjs
git commit -m "docs: add strategy and safety references"
```

---

### Task 5: Delivery Roadmap and Decisions Reference

**Files:**
- Create: `PROJECT_PLAN.md`
- Create: `docs-site/content/delivery.mdx`
- Create: `docs-site/content/decisions.mdx`
- Modify: `docs-site/content/_meta.ts`
- Modify: `docs-site/scripts/check-source-references.mjs`

**Interfaces:**
- Consumes: `PRODUCT.md`, `ARCHITECTURE.md`, ADR 0001 และ Linear DEV-74–DEV-80
- Produces: canonical milestone order และ reference pages สำหรับ delivery/decisions

- [ ] **Step 1: เพิ่ม failing mappings**

```javascript
'content/delivery.mdx': ['PROJECT_PLAN.md'],
'content/decisions.mdx': ['docs/adr/0001-use-feature-first-modular-monolith.md']
```

Run: `cd docs-site && npm test`

Expected: FAIL เพราะ roadmap/pages ยังไม่มี

- [ ] **Step 2: สร้าง canonical project plan**

```markdown
# TiewTrade V2 Project Plan

## Milestone 1: Paper Trading Complete

1. Paper Spot Core Tracer Bullet — DEV-74 ถึง DEV-80
2. SQLite durability, audit trail และ restart recovery
3. Paper Futures, funding และ collateral accounting
4. Binance public market-data runtime พร้อม reconnect/backfill
5. PySide6 Operational UI และ Paper acceptance

## Milestone 2: Live Spot

เริ่มหลัง Paper acceptance ผ่าน เพิ่ม Live Preflight, Spot execution adapter, idempotency และ reconciliation ผ่าน fake contract tests ก่อนขออนุญาตทดสอบบัญชีจริง

## Milestone 3: Live USDⓈ-M Futures

เริ่มหลัง Live Spot acceptance ผ่าน เพิ่ม Cross Margin, leverage cap, Collateral Buffer, funding และ liquidation-related account facts

## Delivery Rules

- ทำ vertical slice ทีละ Sub-issue
- ย้ายเฉพาะ Issue ที่กำลังทำเป็น In Progress
- ใช้หนึ่ง Issue branch ต่อหนึ่ง Sub-issue
- ปิด Main Issue เมื่อ Sub-issues และ acceptance ทั้งหมดผ่าน
```

- [ ] **Step 3: สร้าง Delivery และ Decisions pages**

```mdx
---
title: Delivery
description: Milestones, gates และ current work frontier
---

# Delivery

> Source file: `PROJECT_PLAN.md`  
> Last reviewed date: 2026-07-21

ลำดับส่งมอบคือ Paper Trading Complete → Live Spot → Live USDⓈ-M Futures

## Current frontier

[DEV-74](https://linear.app/chainarong/issue/DEV-74) เป็น Main Issue ของ Paper Spot Core โดยเริ่มจาก DEV-75 และเดินตาม blocking relations ถึง DEV-80
```

```mdx
---
title: Decisions
description: Architecture Decision Records
---

# Decisions

> Source file: `docs/adr/0001-use-feature-first-modular-monolith.md`  
> Last reviewed date: 2026-07-21

| ADR | Status | Decision |
| --- | --- | --- |
| 0001 | Accepted | ใช้ feature-first modular monolith |

เมื่อ decision เปลี่ยน ให้สร้าง ADR ใหม่และระบุว่า ADR เดิมถูกแทนที่ ห้ามแก้ประวัติ decision เดิมโดยเงียบ ๆ
```

```typescript
// docs-site/content/_meta.ts
export default {
  index: 'Overview',
  product: 'Product',
  domain: 'Domain',
  architecture: 'Architecture',
  strategy: 'Strategy',
  safety: 'Safety',
  delivery: 'Delivery',
  decisions: 'Decisions'
}
```

- [ ] **Step 4: Verify and commit**

Run: `cd docs-site && npm test && npm run build`

Expected: ผ่านและมี routes `/delivery` กับ `/decisions`

```bash
git add PROJECT_PLAN.md docs-site/content/delivery.mdx docs-site/content/decisions.mdx docs-site/content/_meta.ts docs-site/scripts/check-source-references.mjs
git commit -m "docs: add delivery and decision references"
```

---

### Task 6: Consistency, Responsive Review and Production Build

**Files:**
- Create: `docs-site/README.md`
- Modify: `docs-site/tests/source-references.test.mjs`
- Modify: `docs-site/content/*.mdx` only when verification finds a concrete defect

**Interfaces:**
- Consumes: ทุก Source of Truth/page จาก Tasks 1–5
- Produces: verified local documentation site และ reproducible runbook

- [ ] **Step 1: เพิ่ม coverage test สำหรับ expected pages**

```javascript
// append to docs-site/tests/source-references.test.mjs
test('the complete reference navigation is covered by source validation', async () => {
  const { references } = await import('../scripts/check-source-references.mjs')
  assert.deepEqual(Object.keys(references).sort(), [
    'content/architecture.mdx',
    'content/decisions.mdx',
    'content/delivery.mdx',
    'content/domain.mdx',
    'content/index.mdx',
    'content/product.mdx',
    'content/safety.mdx',
    'content/strategy.mdx'
  ])
})
```

Run: `cd docs-site && npm test`

Expected: `2 passed`

- [ ] **Step 2: สร้าง documentation runbook**

````markdown
# TiewTrade Reference Site

Nextra presentation layer สำหรับเอกสาร Product และ Engineering ภายในทีม Root Markdown และ `docs/adr/` ที่ repository root เป็น Source of Truth

## Install

```bash
npm install
```

## Run locally

```bash
npm run dev
```

เปิด `http://localhost:3000`

## Verify

```bash
npm test
npm run check:references
npm run build
```

รอบนี้ไม่มี deployment และ CI
````

- [ ] **Step 3: Run complete automated verification**

Run: `cd docs-site && npm test`

Expected: `2 passed`

Run: `cd docs-site && npm run check:references`

Expected: exit code 0 และไม่มี output

Run: `cd docs-site && npm run build`

Expected: production build สำเร็จและมี routes ทั้ง 8 หน้า

Run: `git diff --check`

Expected: ไม่มี output

- [ ] **Step 4: Run local responsive smoke review**

Run: `cd docs-site && npm run dev`

Expected: server พร้อมที่ `http://localhost:3000`

ตรวจ viewport `1440×900` และ `390×844` สำหรับ `/`, `/architecture`, `/strategy` และ `/delivery`:

- sidebar/navigation เปิดใช้งานได้
- ไม่มี horizontal overflow
- heading, tables และ code blocks อ่านได้
- internal links เปิด route ถูกต้อง
- light theme มี contrast ชัดเจน

หยุด dev server หลังตรวจเสร็จ

- [ ] **Step 5: Commit final verification changes**

```bash
git add docs-site/README.md docs-site/tests docs-site/content
git commit -m "docs: verify internal reference site"
```

## Completion Evidence

ก่อนปิด Main Issue ต้องรายงาน:

- commit hashes ของ Sub-issues 1–6
- output ของ `npm test`, `npm run check:references`, `npm run build` และ `git diff --check`
- routes ทั้ง 8 หน้า
- viewport ที่ตรวจและ defect ที่แก้
- ยืนยันว่าไม่มี deployment, CI, secret หรือข้อมูลบัญชีจริง
