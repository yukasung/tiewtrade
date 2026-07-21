import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { validateSourceReferences } from '../scripts/check-source-references.mjs'

test('all curated pages reference existing source files', async () => {
  const failures = await validateSourceReferences()
  assert.deepEqual(failures, [])
})

test('documentation work plan includes the main issue and every sub-issue', async () => {
  const content = await readFile(new URL('../content/work-plan.mdx', import.meta.url), 'utf8')

  for (const issueId of ['DEV-81', 'DEV-82', 'DEV-83', 'DEV-84', 'DEV-85', 'DEV-86', 'DEV-87']) {
    assert.match(content, new RegExp(`https://linear\\.app/chainarong/issue/${issueId}/`, 'i'))
  }

  assert.match(content, /## Dependency order/)
  assert.match(content, /ไม่ใช่การ sync สถานะแบบ real-time/)
})
