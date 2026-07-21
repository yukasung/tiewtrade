import test from 'node:test'
import assert from 'node:assert/strict'
import { mkdtemp, mkdir, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { validateDocumentation } from '../scripts/check-content.mjs'

test('documentation validator accepts a complete reader-facing page', async () => {
  const root = await mkdtemp(path.join(tmpdir(), 'tiewtrade-docs-'))
  await mkdir(path.join(root, 'content'))
  await writeFile(path.join(root, 'content', 'guide.mdx'), '## Process\n\n```mermaid\nflowchart LR\nA --> B\n```\n\nแผนภาพนี้อธิบายลำดับจาก A ไป B\n')
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

for (const [name, block] of [
  ['horizontal rule', '---'],
  ['standalone image', '![Trading flow](flow.png)']
]) {
  test(`documentation validator rejects a ${name} after a Mermaid diagram`, async () => {
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
