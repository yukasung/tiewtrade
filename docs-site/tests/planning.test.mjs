import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const projectPlanUrl = new URL('../../PROJECT_PLAN.md', import.meta.url)
const tracerPlanUrl = new URL(
  '../../docs/superpowers/plans/2026-07-20-paper-spot-core-tracer-bullet.md',
  import.meta.url
)
const deliveryUrl = new URL('../content/delivery.mdx', import.meta.url)

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
  assert.match(
    plan,
    /Account Profile isolation[\s\S]+SQLite[\s\S]+Public Binance market-data[\s\S]+Paper Futures[\s\S]+Desktop UI[\s\S]+Recovery/
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
    /Account Profile[\s\S]+SQLite[\s\S]+public market-data runtime[\s\S]+Paper Futures[\s\S]+desktop UI[\s\S]+Recovery/
  )
})
