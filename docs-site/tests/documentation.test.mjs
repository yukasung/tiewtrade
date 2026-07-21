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

test('documentation validator detects 1-3-space-indented Mermaid fences', async () => {
  const root = await mkdtemp(path.join(tmpdir(), 'tiewtrade-docs-'))
  await mkdir(path.join(root, 'content'))
  const contract = {}
  for (const spaces of [1, 2, 3]) {
    const page = `content/guide-${spaces}.mdx`
    const indentation = ' '.repeat(spaces)
    await writeFile(path.join(root, page), `${indentation}\`\`\`mermaid\nflowchart LR\nA --> B\n${indentation}\`\`\`\n\nแผนภาพลำดับการทำงาน\n`)
    contract[page] = { headings: [], diagrams: 1 }
  }
  assert.deepEqual(await validateDocumentation(root, contract), [])
})

test('documentation validator detects a tilde Mermaid fence', async () => {
  const root = await mkdtemp(path.join(tmpdir(), 'tiewtrade-docs-'))
  await mkdir(path.join(root, 'content'))
  await writeFile(path.join(root, 'content', 'guide.mdx'), '~~~mermaid\nflowchart LR\nA --> B\n~~~\n\nแผนภาพลำดับการทำงาน\n')
  const contract = { 'content/guide.mdx': { headings: [], diagrams: 1 } }
  assert.deepEqual(await validateDocumentation(root, contract), [])
})

test('documentation validator detects a longer-backtick Mermaid fence', async () => {
  const root = await mkdtemp(path.join(tmpdir(), 'tiewtrade-docs-'))
  await mkdir(path.join(root, 'content'))
  await writeFile(path.join(root, 'content', 'guide.mdx'), '````mermaid\nflowchart LR\nA --> B\n````\n\nแผนภาพลำดับการทำงาน\n')
  const contract = { 'content/guide.mdx': { headings: [], diagrams: 1 } }
  assert.deepEqual(await validateDocumentation(root, contract), [])
})

test('documentation validator does not count mermaidx as Mermaid', async () => {
  const root = await mkdtemp(path.join(tmpdir(), 'tiewtrade-docs-'))
  await mkdir(path.join(root, 'content'))
  await writeFile(path.join(root, 'content', 'guide.mdx'), '```mermaidx\nflowchart LR\nA --> B\n```\n\n## Next Step\n')
  const contract = { 'content/guide.mdx': { headings: [], diagrams: 0 } }
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
