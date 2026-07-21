import test from 'node:test'
import assert from 'node:assert/strict'
import { mkdtemp, mkdir, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { validateDocumentation } from '../scripts/check-content.mjs'

test('documentation validator accepts a complete reader-facing page', async () => {
  const root = await mkdtemp(path.join(tmpdir(), 'tiewtrade-docs-'))
  await mkdir(path.join(root, 'content'))
  await writeFile(path.join(root, 'content', 'guide.mdx'), '## Process\n\n```mermaid\nflowchart LR\nA --> B\n```\n')
  const contract = { 'content/guide.mdx': { headings: ['Process'], diagrams: 1 } }
  assert.deepEqual(await validateDocumentation(root, contract), [])
})

test('documentation validator rejects tracker and source metadata', async () => {
  const root = await mkdtemp(path.join(tmpdir(), 'tiewtrade-docs-'))
  await mkdir(path.join(root, 'content'))
  await writeFile(path.join(root, 'content', 'guide.mdx'), 'Source file: `PRODUCT.md`\n')
  const contract = { 'content/guide.mdx': { headings: [], diagrams: 0 } }
  assert.deepEqual(await validateDocumentation(root, contract), [
    'content/guide.mdx: contains forbidden tracker or source metadata'
  ])
})
