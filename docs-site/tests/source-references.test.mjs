import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { validateSourceReferences } from '../scripts/check-source-references.mjs'

test('all curated pages reference existing source files', async () => {
  const failures = await validateSourceReferences()
  assert.deepEqual(failures, [])
})

test('documentation roadmap organizes every Linear reference by topic', async () => {
  const content = await readFile(new URL('../content/work-plan.mdx', import.meta.url), 'utf8')

  for (const issueId of ['DEV-81', 'DEV-82', 'DEV-83', 'DEV-84', 'DEV-85', 'DEV-86', 'DEV-87']) {
    assert.match(content, new RegExp(`https://linear\\.app/chainarong/issue/${issueId}/`, 'i'))
  }

  for (const heading of [
    'Goals and Scope',
    'Foundation and Product Overview',
    'Domain Reference',
    'Architecture Reference',
    'Strategy and Trading Safety',
    'Delivery and Decisions',
    'Final Verification',
    'Delivery Order'
  ]) {
    assert.match(content, new RegExp(`## ${heading}`))
  }

  assert.doesNotMatch(content, /## Main Issue|## Sub-issues/)
  assert.match(content, /ไม่ใช่การ sync สถานะแบบ real-time/)
})
