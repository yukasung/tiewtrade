import test from 'node:test'
import assert from 'node:assert/strict'
import { validateSourceReferences } from '../scripts/check-source-references.mjs'

test('all curated pages reference existing source files', async () => {
  const failures = await validateSourceReferences()
  assert.deepEqual(failures, [])
})
