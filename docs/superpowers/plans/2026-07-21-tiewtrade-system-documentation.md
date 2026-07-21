# TiewTrade System Documentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** สร้าง Project Documentation แบบ self-contained ที่อธิบายพฤติกรรมและ process ของ TiewTrade V2 ผ่าน 11 routes พร้อม Mermaid diagrams โดยไม่มี metadata หรือข้อมูลจาก Issue Tracker ใน reader-facing content

**Architecture:** `docs-site/content/` เก็บ MDX ที่แบ่งตาม mental model ของผู้อ่าน ส่วน `scripts/check-content.mjs` ตรวจ route contract, required headings, Mermaid diagrams, internal links และ forbidden tracker/source metadata ก่อน Nextra build ทุกครั้ง Nextra 4 compile Mermaid code fences เป็น diagram โดยไม่เพิ่ม diagram dependency ใหม่

**Tech Stack:** Next.js 16, React 19, Nextra 4 App Router, `nextra-theme-docs`, MDX, Mermaid, unified, remark-parse, remark-mdx, Node.js built-in test runner, npm

## Global Constraints

- Reader-facing content ใช้ภาษาไทย โดยคงชื่อ module, class, function, parameter และคำศัพท์ Binance เป็นภาษาอังกฤษ
- ห้ามแสดง Issue Tracker URL, issue identifier, status, `Source file` หรือ `Last reviewed date`
- ทุก process diagram ต้องมีคำอธิบายเป็นข้อความประกอบ
- ใช้ completed candle 5 นาทีและ UTC ตาม Product Definition
- ห้ามเปลี่ยน business rules ของ TiewTrade V2
- ห้ามใส่ API credentials, account identifiers จริง หรือข้อมูลบัญชีจริง
- ไม่มี deployment, CI, authentication, analytics หรือ external search service
- แต่ละ task ใช้ failing test → minimal content/configuration → passing test → commit

## File Map

```text
docs-site/
├── README.md
├── app/layout.tsx
├── content/
│   ├── _meta.ts
│   ├── index.mdx
│   ├── product.mdx
│   ├── architecture.mdx
│   ├── trading-process.mdx
│   ├── strategy.mdx
│   ├── basket-lifecycle.mdx
│   ├── entry-pair-cooldown.mdx
│   ├── capital-allocation.mdx
│   ├── paper-trading.mdx
│   ├── live-safety.mdx
│   └── recovery.mdx
├── package.json
├── scripts/check-content.mjs
├── scripts/check-source-references.mjs
├── tests/documentation.test.mjs
└── tests/source-references.test.mjs
```

Task 1 ยังเก็บ `content/work-plan.mdx`, `scripts/check-source-references.mjs` และ `tests/source-references.test.mjs` เพื่อให้ production build gate เดิมยังผ่าน จนกว่า Task 2 จะ rewrite Overview/Product, ลงทะเบียน production pages แรก และย้าย build gate ไปใช้ content contract ได้พร้อมกัน

---

### Task 1: Reader-facing documentation contract

**Files:**
- Create: `docs-site/tests/documentation.test.mjs`
- Create: `docs-site/scripts/check-content.mjs`
- Modify: `docs-site/package.json`
- Modify: `docs-site/package-lock.json`
- Retain: `docs-site/tests/source-references.test.mjs`
- Retain: `docs-site/scripts/check-source-references.mjs`

**Interfaces:**
- Produces: `validateDocumentation(): Promise<string[]>`
- Produces: npm scripts `test` และ `check:content`
- Retains: production `build` gate ผ่าน `check:references` จนถึง Task 2

- [ ] **Step 1: Write the failing documentation contract test**

```javascript
import test from 'node:test'
import assert from 'node:assert/strict'
import { mkdtemp, mkdir, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { validateDocumentation } from '../scripts/check-content.mjs'

test('documentation validator accepts a complete reader-facing page', async () => {
  const root = await mkdtemp(path.join(tmpdir(), 'tiewtrade-docs-'))
  await mkdir(path.join(root, 'content'))
  await writeFile(path.join(root, 'content', 'guide.mdx'), '## Process\n\n```mermaid\nflowchart LR\nA --> B\n```\n\nแผนภาพนี้อธิบาย **ลำดับ** จาก [A ไป B](/process)\n')
  const contract = { 'content/guide.mdx': { headings: ['Process'], diagrams: 1 } }
  assert.deepEqual(await validateDocumentation(root, contract), [])
})

test('documentation validator rejects a Mermaid diagram without a following prose paragraph', async () => {
  const root = await mkdtemp(path.join(tmpdir(), 'tiewtrade-docs-'))
  await mkdir(path.join(root, 'content'))
  await writeFile(path.join(root, 'content', 'guide.mdx'), '## Process\n\n```mermaid\nflowchart LR\nA --> B\n```\n\n## Next Step\n')
  const contract = { 'content/guide.mdx': { headings: ['Process'], diagrams: 1 } }
  assert.deepEqual(await validateDocumentation(root, contract), [
    'content/guide.mdx: Mermaid diagram 1 must be followed by an explanatory prose paragraph'
  ])
})

for (const [description, block] of [
  ['a horizontal rule', '---'],
  ['a standalone image', '![Trading flow](flow.png)'],
  ['indented code', '    const explanation = true'],
  ['a reference image', '![Trading flow][flow]\n\n[flow]: flow.png'],
  ['an MDX expression', '{diagramExplanation}'],
  ['MDX ESM', 'export const diagramExplanation = "Trading flow"'],
  ['a shortcut reference image', '![Trading flow]\n\n[Trading flow]: flow.png']
]) {
  test(`documentation validator rejects ${description} after a Mermaid diagram`, async () => {
    const root = await mkdtemp(path.join(tmpdir(), 'tiewtrade-docs-'))
    await mkdir(path.join(root, 'content'))
    await writeFile(path.join(root, 'content', 'guide.mdx'), `## Process\n\n\`\`\`mermaid\nflowchart LR\nA --> B\n\`\`\`\n\n${block}\n`)
    const contract = { 'content/guide.mdx': { headings: ['Process'], diagrams: 1 } }
    assert.deepEqual(await validateDocumentation(root, contract), [
      'content/guide.mdx: Mermaid diagram 1 must be followed by an explanatory prose paragraph'
    ])
  })
}

test('documentation validator rejects tracker and source metadata', async () => {
  const root = await mkdtemp(path.join(tmpdir(), 'tiewtrade-docs-'))
  await mkdir(path.join(root, 'content'))
  await writeFile(path.join(root, 'content', 'guide.mdx'), 'Source file: `PRODUCT.md`\n')
  const contract = { 'content/guide.mdx': { headings: [], diagrams: 0 } }
  assert.deepEqual(await validateDocumentation(root, contract), [
    'content/guide.mdx: contains forbidden tracker or source metadata'
  ])
})
```

- [ ] **Step 2: Run the test and verify RED**

Run: `cd docs-site && npm test`

Expected: FAIL with `ERR_MODULE_NOT_FOUND` for `scripts/check-content.mjs`

- [ ] **Step 3: Implement the content validator**

```javascript
import { access, readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import { unified } from 'unified'
import remarkParse from 'remark-parse'
import remarkMdx from 'remark-mdx'

const siteRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const markdownParser = unified().use(remarkParse).use(remarkMdx)

export const pages = {}

const forbidden = /linear\.app|\bDEV-\d+\b|Source file:|Last reviewed date:|Main Issue|Sub-issues/i
const unicodeLetterOrNumber = /[\p{L}\p{N}]/u

function hasMeaningfulText(node) {
  if ((node.type === 'text' || node.type === 'inlineCode') && unicodeLetterOrNumber.test(node.value)) return true
  return Array.isArray(node.children) && node.children.some(hasMeaningfulText)
}

function hasCodeIndentation(content, node) {
  const offset = node.position?.start.offset
  if (typeof offset !== 'number') return false

  const lineStart = content.lastIndexOf('\n', offset - 1) + 1
  const indentation = content.slice(lineStart, offset)
  return indentation.includes('\t') || indentation.length >= 4
}

function hasFollowingProseParagraph(content, diagram) {
  const diagramBody = content.slice(diagram.index + diagram[0].length)
  const closingFence = diagramBody.match(/^```[ \t]*$/m)
  if (!closingFence) return false

  const followingContent = diagramBody.slice(closingFence.index + closingFence[0].length)
  const firstBlock = markdownParser.parse(followingContent).children[0]
  return firstBlock?.type === 'paragraph' &&
    !hasCodeIndentation(followingContent, firstBlock) &&
    hasMeaningfulText(firstBlock)
}

export async function validateDocumentation(root = siteRoot, contracts = pages) {
  const failures = []
  for (const [page, contract] of Object.entries(contracts)) {
    const absolutePath = path.join(root, page)
    try {
      await access(absolutePath)
    } catch {
      failures.push(`${page}: missing page`)
      continue
    }
    const content = await readFile(absolutePath, 'utf8')
    if (forbidden.test(content)) failures.push(`${page}: contains forbidden tracker or source metadata`)
    for (const heading of contract.headings) {
      if (!content.includes(`## ${heading}`)) failures.push(`${page}: missing heading ${heading}`)
    }
    const diagrams = [...content.matchAll(/^```mermaid[^\r\n]*\r?$/gm)]
    if (diagrams.length < contract.diagrams) failures.push(`${page}: expected ${contract.diagrams} Mermaid diagrams, found ${diagrams.length}`)
    for (const [index, diagram] of diagrams.entries()) {
      if (!hasFollowingProseParagraph(content, diagram)) {
        failures.push(`${page}: Mermaid diagram ${index + 1} must be followed by an explanatory prose paragraph`)
      }
    }
  }
  return failures
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const failures = await validateDocumentation()
  if (failures.length) {
    console.error(failures.join('\n'))
    process.exitCode = 1
  }
}
```

- [ ] **Step 4: Add direct parser dependencies and update npm scripts**

เพิ่ม direct devDependencies ด้วย `npm install --save-dev unified@11.0.5 remark-parse@11.0.0 remark-mdx@3.1.1` เพื่อให้ imports ของ content validator ไม่พึ่ง transitive dependencies เพิ่ม `check:content` เป็น `node scripts/check-content.mjs` และคง `test` เป็น `node --test tests/*.test.mjs` โดยยังคง `check:references` และ `build` เป็น `npm run check:references && next build` จนถึง Task 2

- [ ] **Step 5: Run the tests and verify GREEN**

Run: `cd docs-site && npm test`

Expected: documentation validator tests สิบรายการและ source-reference tests เดิมสองรายการ PASS; AST contract ยอมรับ paragraph ที่มี Unicode text/inlineCode descendant รวม inline emphasis/link และปฏิเสธ non-paragraph blocks, image-only paragraphs, MDX expressions, MDX ESM, full/shortcut reference images และ indented code; production page registry remains empty until Task 2 adds the first complete pages

- [ ] **Step 6: Commit the contract**

```bash
git add docs-site/package.json docs-site/scripts docs-site/tests
git commit -m "test: define project documentation contract"
```

---

### Task 2: Overview, Product Overview, and navigation

**Files:**
- Modify: `docs-site/content/_meta.ts`
- Modify: `docs-site/content/index.mdx`
- Modify: `docs-site/content/product.mdx`
- Modify: `docs-site/app/layout.tsx`
- Modify: `docs-site/package.json`
- Delete: `docs-site/content/work-plan.mdx`
- Delete: `docs-site/tests/source-references.test.mjs`
- Delete: `docs-site/scripts/check-source-references.mjs`

**Interfaces:**
- Consumes: route contract from Task 1
- Produces: navigation order and entry points used by all later pages

- [ ] **Step 1: Add navigation assertions to the test**

Read `_meta.ts` and assert that it contains these keys in order: `index`, `product`, `architecture`, `trading-process`, `strategy`, `basket-lifecycle`, `entry-pair-cooldown`, `capital-allocation`, `paper-trading`, `live-safety`, `recovery`. Assert it does not contain `work-plan`.

- [ ] **Step 2: Run the test and verify RED**

Run: `cd docs-site && npm test`

Expected: FAIL because navigation still contains `work-plan`

- [ ] **Step 3: Replace navigation**

```typescript
export default {
  index: 'Overview',
  product: 'Product Overview',
  architecture: 'System Architecture',
  'trading-process': 'Trading Process',
  strategy: 'RSI Step Grid Strategy',
  'basket-lifecycle': 'Basket Lifecycle',
  'entry-pair-cooldown': 'Entry Pair & Cooldown',
  'capital-allocation': 'Capital Allocation',
  'paper-trading': 'Paper Trading',
  'live-safety': 'Live Trading Safety',
  recovery: 'Recovery & Reconciliation'
}
```

- [ ] **Step 4: Rewrite Overview as the reading map**

Use `# TiewTrade System Guide`, explain the Paper-first Internal Alpha purpose, add `## How the System Works` with a Mermaid `flowchart LR` connecting `Completed Candle → Strategy → Entry Intent → Execution → Basket → Take Profit`, and add `## Recommended Reading` with paths for Product owner, Tester, and Developer.

- [ ] **Step 5: Rewrite Product Overview**

Use `# Product Overview`, `## Internal Alpha Scope`, and `## Delivery Gates`. Include a scope table for BTCUSDT, completed candle 5m, UTC, RSI Step Grid, maximum five Account Profiles, one Active Bot Session per profile, Paper Spot/Futures, and sequential gates `Paper → Live Spot → Live Futures`. Include an explicit non-goals list for Login, License, Cloud Sync, Stop Loss, Maximum Drawdown hard limit, Max Daily Loss, and automatic Paper-to-Live switching.

- [ ] **Step 6: Remove repository edit metadata from layout**

Remove `docsRepositoryBase` from `<Layout>` so the reader interface does not present source-file navigation.

- [ ] **Step 7: Register the first two production pages**

Set `pages` in `scripts/check-content.mjs` to:

```javascript
export const pages = {
  'content/index.mdx': { headings: ['How the System Works', 'Recommended Reading'], diagrams: 1 },
  'content/product.mdx': { headings: ['Internal Alpha Scope', 'Delivery Gates'], diagrams: 0 }
}
```

- [ ] **Step 8: Switch the production build gate**

Set `build` to `npm run check:content && next build`, keep `check:content`, remove `check:references`, and delete `scripts/check-source-references.mjs` กับ `tests/source-references.test.mjs` หลัง Overview/Product ไม่มี source metadata และถูกลงทะเบียนใน `pages` แล้ว

- [ ] **Step 9: Run tests**

Run: `cd docs-site && npm test`

Expected: all tests PASS with Overview and Product Overview registered

- [ ] **Step 10: Commit foundation content**

```bash
git add docs-site/app/layout.tsx docs-site/content docs-site/package.json docs-site/scripts docs-site/tests
git commit -m "docs: add system guide foundation"
```

---

### Task 3: Architecture and end-to-end Trading Process

**Files:**
- Create: `docs-site/content/architecture.mdx`
- Create: `docs-site/content/trading-process.mdx`

**Interfaces:**
- Produces: shared system terminology and pipeline referenced by strategy, execution, and recovery pages

- [ ] **Step 1: Register both pages in the production contract**

Add `architecture.mdx` and `trading-process.mdx` with their required headings and two diagrams each to the exported `pages` object.

- [ ] **Step 2: Run the contract test and capture RED for both pages**

Run: `cd docs-site && npm test`

Expected: FAIL with missing `architecture.mdx` and `trading-process.mdx`

- [ ] **Step 3: Create System Architecture**

Document `## Module Boundaries` with responsibilities for accounts, market data, strategy, trading, paper, live, integrations, UI, runtime, and observability. Add a `flowchart LR` showing UI/runtime depending on feature modules and integrations implementing consumer-owned boundaries. Document `## Dependency Direction` and add a second diagram comparing shared business policies with separate Paper, Live Spot, and Live Futures adapters.

- [ ] **Step 4: Create Trading Process**

Document `## Trading Pipeline` with a flowchart covering completed-candle validation, deduplication, strategy evaluation, lifecycle/risk checks, Entry Intent, execution, Fill, Basket update, Take Profit recalculation, and persistence/UI notification. Document `## Entry to Take Profit` with a sequence diagram between Market Data, Strategy, Trading Engine, Executor, Basket, Persistence, and UI.

- [ ] **Step 5: Run tests and build these MDX diagrams**

Run: `cd docs-site && npm test && npm run build`

Expected: all tests PASS and build compiles Mermaid code fences

- [ ] **Step 6: Commit**

```bash
git add docs-site/content/architecture.mdx docs-site/content/trading-process.mdx
git commit -m "docs: explain architecture and trading process"
```

---

### Task 4: Strategy, Basket lifecycle, Entry Pair, and Capital Allocation

**Files:**
- Create: `docs-site/content/strategy.mdx`
- Create: `docs-site/content/basket-lifecycle.mdx`
- Create: `docs-site/content/entry-pair-cooldown.mdx`
- Create: `docs-site/content/capital-allocation.mdx`

**Interfaces:**
- Consumes: Trading Process terminology from Task 3
- Produces: complete business-rule reference used by Paper and Live pages

- [ ] **Step 1: Register all four pages in the production contract**

Add `strategy.mdx`, `basket-lifecycle.mdx`, `entry-pair-cooldown.mdx`, and `capital-allocation.mdx` with the headings and diagram counts defined in the design.

- [ ] **Step 2: Run the contract test and capture RED for four pages**

Run: `cd docs-site && npm test`

Expected: FAIL listing the four missing pages

- [ ] **Step 3: Create RSI Step Grid Strategy**

Document `## Entry Signal` with RSI(14) reset below 30, entry above 50, bullish candle, close above reset close, maximum 10 Entries, completed candle 5m only, and reset consumption after Fill. Add `## Strategy State` with a state diagram `Waiting for Reset → Armed → Entry Intent → Filled → Waiting for Reset`. Explain ATR(14) and `weighted_average_entry_price + ATR × 3` without treating an incomplete candle as input.

- [ ] **Step 4: Create Basket Lifecycle**

Document `## Basket Take Profit` with recalculation after every Fill, Binance tick-size rounding, bot-owned position coverage, fees in realized PnL, and immediate new Basket eligibility after close. Add `## Basket States` with `Empty → Open → TP Active → Closed`, plus transitions for additional Entry Fill and recovery mismatch.

- [ ] **Step 5: Create Entry Pair and Cooldown Month**

Document `## Entry Pairs` as pairs 1–2 through 9–10 and add a state diagram for first Entry, completed Pair, month boundary, cooldown, and next Pair. Document `## Cooldown Month` with a Mermaid timeline showing that a lone first Entry may receive its second Entry next month, while a completed Pair held across month end forces the following month to cooldown.

- [ ] **Step 6: Create Capital Allocation**

Document `## Spot Allocation` as 80% Trading Capital and 20% Spot Reserve, divided equally across 10 Entries. Document `## Futures Allocation` as 50% Trading Capital and 50% Collateral Buffer, Cross Margin, leverage cap 5x, and 10 equal initial-margin budgets. Add a flowchart and a table using a clearly fictional 200,000 USDT example without implying guaranteed liquidation protection.

- [ ] **Step 7: Run tests and build**

Run: `cd docs-site && npm test && npm run build`

Expected: all tests and the build PASS

- [ ] **Step 8: Commit**

```bash
git add docs-site/content/strategy.mdx docs-site/content/basket-lifecycle.mdx docs-site/content/entry-pair-cooldown.mdx docs-site/content/capital-allocation.mdx
git commit -m "docs: document strategy and lifecycle rules"
```

---

### Task 5: Paper Trading, Live Safety, and Recovery

**Files:**
- Create: `docs-site/content/paper-trading.mdx`
- Create: `docs-site/content/live-safety.mdx`
- Create: `docs-site/content/recovery.mdx`

**Interfaces:**
- Consumes: shared pipeline and business rules from Tasks 3–4
- Produces: complete execution and operational safety documentation

- [ ] **Step 1: Register all three pages in the production contract**

Add `paper-trading.mdx`, `live-safety.mdx`, and `recovery.mdx` with the required headings and diagram counts.

- [ ] **Step 2: Run the contract test and capture RED for three pages**

Run: `cd docs-site && npm test`

Expected: FAIL listing the three missing pages

- [ ] **Step 3: Create Paper Trading**

Document `## Conservative Fill Model` with a sequence diagram: signal on completed candle N, Entry Fill at candle N+1 open, Take Profit eligible from the candle after Fill, plus fee/slippage/funding capture. Document `## Replay Determinism` and explain identical market data, Preset version, fee, slippage, and funding configuration producing the same replay result.

- [ ] **Step 4: Create Live Trading Safety**

Document `## Preflight` with a flowchart for credentials in OS Keyring, permissions, selected Account Profile, symbol rules, balance, open orders/positions, margin mode, leverage, reconciliation, and explicit confirmation. Document `## Stale Market Data` with a fail-closed decision diagram: block new Entries, preserve exchange-hosted Take Profit, alert, bounded retry, backfill, deduplicate, validate continuity, then resume.

- [ ] **Step 5: Create Recovery and Reconciliation**

Document `## Stop Session` as stopping new Entries while preserving state and Take Profit. Document `## Startup Recovery` with a state diagram and sequence diagram covering load local state, fetch exchange state for Live, compare, resume only on match, and block Entries/report mismatch without automatic cancellation or state mutation.

- [ ] **Step 6: Run tests and build**

Run: `cd docs-site && npm test && npm run build`

Expected: PASS with all 11 pages satisfying headings, diagrams, and forbidden-content checks

- [ ] **Step 7: Commit**

```bash
git add docs-site/content/paper-trading.mdx docs-site/content/live-safety.mdx docs-site/content/recovery.mdx
git commit -m "docs: explain execution safety and recovery"
```

---

### Task 6: Local usage, links, responsive rendering, and final verification

**Files:**
- Create: `docs-site/README.md`
- Modify: `docs-site/tests/documentation.test.mjs`
- Modify: `docs-site/scripts/check-content.mjs`

**Interfaces:**
- Consumes: all routes produced by Tasks 2–5
- Produces: verified local Project Documentation package

- [ ] **Step 1: Add a failing internal-link validator test**

Create a temporary `content/index.mdx` fixture containing `[Missing](/missing)` and assert that validation returns `content/index.mdx: missing internal route /missing`. Keep the link check unimplemented so this test proves RED. The production rule must extract Markdown links beginning with `/`, map `/` to `content/index.mdx` and other routes to `content/<route>.mdx`, and report missing targets. Every non-home page must also be linked from `content/index.mdx` or `_meta.ts`.

- [ ] **Step 2: Run test and verify RED if any link is missing**

Run: `cd docs-site && npm test`

Expected: FAIL because the validator does not report the fixture's missing route yet

- [ ] **Step 3: Implement internal-link validation and create local usage README**

Implement the route extraction and missing-target report, then ensure all production links resolve. Create the README with the following commands.

Document Node/npm prerequisites and exact commands:

```bash
cd docs-site
npm install
npm run dev
npm test
npm run check:content
npm run build
```

Explain that the site opens at `http://localhost:3000` unless Next selects another port.

- [ ] **Step 4: Run full automated verification**

Run: `cd docs-site && npm test && npm run check:content && npm run build`

Expected: all commands exit 0

- [ ] **Step 5: Verify browser rendering**

Start `npm run dev`, open every route, confirm Mermaid diagrams render rather than appearing as raw code, and inspect `/`, `/trading-process`, `/entry-pair-cooldown`, `/live-safety`, and `/recovery` at 1440×900 and 390×844. Confirm navigation, tables, diagrams, and Thai copy do not overflow.

- [ ] **Step 6: Scan forbidden content and secrets**

Run:

```bash
rg -n -i 'linear\.app|\bDEV-[0-9]+\b|Source file:|Last reviewed date:|api[_ -]?key|secret' docs-site/content
```

Expected: no matches

- [ ] **Step 7: Check repository diff**

Run: `git diff --check && git status --short`

Expected: no whitespace errors; only intended documentation changes

- [ ] **Step 8: Commit final verification support**

```bash
git add docs-site/README.md docs-site/scripts/check-content.mjs docs-site/tests/documentation.test.mjs
git commit -m "docs: verify project documentation site"
```
