import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const projectPlanUrl = new URL('../../PROJECT_PLAN.md', import.meta.url)
const tracerPlanUrl = new URL(
  '../../docs/superpowers/plans/2026-07-20-paper-spot-core-tracer-bullet.md',
  import.meta.url
)
const deliveryUrl = new URL('../content/delivery.mdx', import.meta.url)
const singleAccountDocuments = [
  '../../PRODUCT.md',
  '../../CONTEXT.md',
  '../../ARCHITECTURE.md',
  '../../PROJECT_PLAN.md',
  '../content/index.mdx',
  '../content/product.mdx',
  '../content/domain.mdx',
  '../content/architecture.mdx',
  '../content/trading-process.mdx',
  '../content/paper-trading.mdx',
  '../content/live-safety.mdx',
  '../content/recovery.mdx',
  '../content/delivery.mdx',
  '../content/decisions.mdx'
].map((path) => new URL(path, import.meta.url))

test('product documentation defines one account and one active session', async () => {
  for (const documentUrl of singleAccountDocuments) {
    const content = await readFile(documentUrl, 'utf8')
    assert.doesNotMatch(
      content,
      /Account Profile|account_profile_id/i
    )
  }

  const product = await readFile(new URL('../../PRODUCT.md', import.meta.url), 'utf8')
  assert.match(product, /หนึ่ง Binance Account ต่อ installation/)
  assert.match(product, /Active Bot Session ได้สูงสุดหนึ่ง Session/)
  assert.match(product, /Multi-account และ Binance sub-account/)
})

test('project plan defines delivery order, ownership, and quality gates', async () => {
  const plan = await readFile(projectPlanUrl, 'utf8')

  for (const heading of [
    'Shared Core Foundation',
    'Paper Spot Tracer Bullet',
    'Paper Trading Complete',
    'Live Spot',
    'Live USDⓈ-M Futures',
    'Module Ownership',
    'Quality Gates'
  ]) {
    assert.match(plan, new RegExp(heading))
  }

  assert.match(plan, /DEV-78[\s\S]+DEV-79[\s\S]+DEV-80/)
  assert.match(plan, /Paper-first ไม่ใช่ Paper-only business logic/)
  assert.match(plan, /80% และ 10 Entries เป็นค่าเริ่มต้นของ form เท่านั้น/)
  assert.doesNotMatch(plan, /funding replay/)
  assert.match(plan, /Paper Futures[\s\S]+Funding Fee[\s\S]+0\.00/)
  assert.match(
    plan,
    /Active Bot Session[\s\S]+SQLite[\s\S]+Public Binance market-data[\s\S]+Paper Futures[\s\S]+Desktop UI[\s\S]+Recovery/
  )
})

test('paper tracer plan uses shared policies and a concrete paper executor', async () => {
  const plan = await readFile(tracerPlanUrl, 'utf8')

  for (const expected of [
    'shared immutable `SessionConfig`',
    '`EntryPolicy`',
    '`SpotTradingPolicy`',
    'concrete Paper executor',
    'DEV-78',
    'DEV-79',
    'DEV-80'
  ]) {
    assert.match(plan, new RegExp(expected.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')))
  }

  for (const obsolete of [
    /PaperSpotSessionConfig/,
    /src\/tiewtrade\/paper\//,
    /tests\/unit\/paper\//,
    /Decimal\("0\.80"\)/,
    /Decimal\("10"\)/,
    /preset\.max_entries/
  ]) {
    assert.doesNotMatch(plan, obsolete)
  }
})

test('delivery documentation follows the project dependency order', async () => {
  const delivery = await readFile(deliveryUrl, 'utf8')

  assert.match(
    delivery,
    /Active Bot Session[\s\S]+SQLite[\s\S]+public market-data runtime[\s\S]+Paper Futures[\s\S]+desktop UI[\s\S]+Recovery/
  )
})
