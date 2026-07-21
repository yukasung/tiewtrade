import test from 'node:test'
import assert from 'node:assert/strict'
import { mkdtemp, mkdir, readFile, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { pages, validateDocumentation } from '../scripts/check-content.mjs'

const expectedPages = [
  'content/index.mdx',
  'content/product.mdx',
  'content/domain.mdx',
  'content/architecture.mdx',
  'content/trading-process.mdx',
  'content/strategy.mdx',
  'content/basket-lifecycle.mdx',
  'content/entry-pair-cooldown.mdx',
  'content/capital-allocation.mdx',
  'content/paper-trading.mdx',
  'content/live-safety.mdx',
  'content/recovery.mdx',
  'content/delivery.mdx',
  'content/decisions.mdx'
]

test('production documentation registers every page and satisfies its content contract', async () => {
  assert.deepEqual(Object.keys(pages), expectedPages)
  assert.deepEqual(await validateDocumentation(), [])
})

test('navigation lists all documentation routes in process order', async () => {
  const meta = await readFile(new URL('../content/_meta.ts', import.meta.url), 'utf8')
  const navigationKeys = [...meta.matchAll(/^  (?:'([^']+)'|([a-z-]+)):/gm)]
    .map((match) => match[1] ?? match[2])

  assert.deepEqual(navigationKeys, expectedPages.map((page) => path.basename(page, '.mdx')))
})

test('package commands use the content gate and README documents the local workflow', async () => {
  const packageJson = JSON.parse(await readFile(new URL('../package.json', import.meta.url), 'utf8'))
  assert.equal(packageJson.scripts.build, 'npm run check:content && next build')
  assert.equal(packageJson.scripts['check:references'], undefined)

  const layout = await readFile(new URL('../app/layout.tsx', import.meta.url), 'utf8')
  assert.doesNotMatch(layout, /docsRepositoryBase/)

  const readme = await readFile(new URL('../README.md', import.meta.url), 'utf8')
  for (const command of ['npm install', 'npm run dev', 'npm test', 'npm run check:content', 'npm run build']) {
    assert.match(readme, new RegExp(command.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')))
  }
})

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

for (const forbiddenContent of [
  'Source file: `PRODUCT.md`',
  'Last reviewed date: 2026-07-21',
  'Linear',
  'https://linear.app/example',
  'DEV-82',
  'Main Issue',
  'Sub-issue',
  'PRODUCT.md',
  'CONTEXT.md',
  'ARCHITECTURE.md',
  'PROJECT_PLAN.md',
  '.superpowers/example.md',
  'docs/superpowers/example.md',
  'docs/adr/0001-example.md'
]) {
  test(`documentation validator rejects forbidden reader-facing content: ${forbiddenContent}`, async () => {
    const root = await mkdtemp(path.join(tmpdir(), 'tiewtrade-docs-'))
    await mkdir(path.join(root, 'content'))
    await writeFile(path.join(root, 'content', 'guide.mdx'), `${forbiddenContent}\n`)
    const contract = { 'content/guide.mdx': { headings: [], diagrams: 0 } }
    assert.deepEqual(await validateDocumentation(root, contract), [
      'content/guide.mdx: contains forbidden tracker or source metadata'
    ])
  })
}

test('documentation validator allows ordinary prose using product and architecture terms', async () => {
  const root = await mkdtemp(path.join(tmpdir(), 'tiewtrade-docs-'))
  await mkdir(path.join(root, 'content'))
  await writeFile(path.join(root, 'content', 'guide.mdx'), 'Product context และ architecture decisions อธิบาย project plan สำหรับผู้อ่าน\n')
  const contract = { 'content/guide.mdx': { headings: [], diagrams: 0 } }
  assert.deepEqual(await validateDocumentation(root, contract), [])
})
