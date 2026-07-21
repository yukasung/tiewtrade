import { access, readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import GithubSlugger from 'github-slugger'
import { unified } from 'unified'
import remarkParse from 'remark-parse'
import remarkMdx from 'remark-mdx'

const siteRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const markdownParser = unified().use(remarkParse).use(remarkMdx)

export const pages = {
  'content/index.mdx': {
    headings: ['ภาพรวมระบบ', 'เส้นทางการอ่าน', 'หลักความปลอดภัย'],
    diagrams: 1
  },
  'content/product.mdx': {
    headings: ['ขอบเขต Internal Alpha', 'Delivery Gates', 'Risk Policy', 'สิ่งที่ไม่อยู่ในขอบเขต'],
    diagrams: 1
  },
  'content/domain.mdx': {
    headings: ['Identity และ Configuration', 'Market และ Decision', 'Basket และ Lifecycle', 'Capital และ Execution', 'Recovery และ Reconciliation'],
    diagrams: 0
  },
  'content/architecture.mdx': {
    headings: ['Module Ownership', 'Dependency Direction', 'Paper และ Live Boundaries', 'Persistence และ UI'],
    diagrams: 3
  },
  'content/trading-process.mdx': {
    headings: ['จาก Candle ถึง Entry Intent', 'จาก Fill ถึง Basket Take Profit', 'Persistence และ Audit Trail', 'Fail-closed Paths'],
    diagrams: 2
  },
  'content/strategy.mdx': {
    headings: ['Versioned Preset', 'Signal Lifecycle', 'Deterministic Entry Intent', 'Completed Candle Contract'],
    diagrams: 1
  },
  'content/basket-lifecycle.mdx': {
    headings: ['Weighted Average', 'Take Profit', 'State Transitions', 'หลัง Basket ปิด'],
    diagrams: 1
  },
  'content/entry-pair-cooldown.mdx': {
    headings: ['Pair Sequence', 'UTC Month Boundary', 'ระหว่าง Cooldown Month', 'การประเมินสิทธิ์ Entry'],
    diagrams: 3
  },
  'content/capital-allocation.mdx': {
    headings: ['Spot 80/20', 'Futures 50/50', 'ตัวอย่าง 200,000 USDT', 'Policy Checks'],
    diagrams: 1
  },
  'content/paper-trading.mdx': {
    headings: ['Candle Timing', 'Execution Costs', 'Deterministic Replay', 'Boundaries'],
    diagrams: 1
  },
  'content/live-safety.mdx': {
    headings: ['Live Activation', 'Execution Boundaries', 'Stale Data Fail Closed', 'Operational Guardrails'],
    diagrams: 2
  },
  'content/recovery.mdx': {
    headings: ['Stop Session', 'Startup Recovery', 'Mismatch Handling', 'Resume Conditions'],
    diagrams: 2
  },
  'content/delivery.mdx': {
    headings: ['Delivery Order', 'Paper Trading Complete', 'Live Spot', 'Live Futures', 'Vertical-slice Quality Gates'],
    diagrams: 1
  },
  'content/decisions.mdx': {
    headings: ['Paper-first Desktop Product', 'Feature-first Modular Monolith', 'Consumer-owned Interfaces', 'Shared Policies, Separate Execution', 'Completed Candle และ UTC', 'Conservative Paper Fill', 'Durable State และ Secret Boundary', 'Fail Closed on Uncertainty'],
    diagrams: 0
  }
}

const forbidden = /\bLinear\b|linear\.app|\bDEV-\d+\b|Source file|Last reviewed date|Main Issue|Sub-?issues?|\b(?:PRODUCT|CONTEXT|ARCHITECTURE|PROJECT_PLAN)\.md\b|\.superpowers\/|docs\/superpowers\/|docs\/adr\//i
const unicodeLetterOrNumber = /[\p{L}\p{N}]/u
const statusLabels = new Set(['Status', 'สถานะ'])
const workflowValues = new Set([
  'todo',
  'in progress',
  'done',
  'canceled',
  'cancelled',
  'สิ่งที่ต้องทำ',
  'กำลังดำเนินการ',
  'เสร็จแล้ว',
  'ยกเลิก'
])

function routeForPage(page) {
  const name = page.replace(/^content\//, '').replace(/\.mdx$/, '')
  if (name === 'index') return '/'
  return `/${name.replace(/\/index$/, '')}`
}

function findLinks(node, links = []) {
  if (node?.type === 'link') links.push(node.url)
  if (Array.isArray(node?.children)) {
    for (const child of node.children) findLinks(child, links)
  }
  return links
}

function nodeText(node) {
  if (node?.type === 'text' || node?.type === 'inlineCode') return node.value
  if (!Array.isArray(node?.children)) return ''
  return node.children.map(nodeText).join('')
}

function headingIds(document) {
  const slugger = new GithubSlugger()
  return new Set(document.children
    .filter((node) => node.type === 'heading')
    .map((node) => slugger.slug(nodeText(node))))
}

function normalizedText(value) {
  return value.trim().replace(/\s+/g, ' ')
}

function isWorkflowValue(value) {
  return workflowValues.has(normalizedText(value).toLocaleLowerCase('en'))
}

function hasWorkflowStatusHeading(document) {
  return document.children.some((node, index) => {
    if (node.type !== 'heading' || !statusLabels.has(normalizedText(nodeText(node)))) return false
    const followingBlock = document.children[index + 1]
    return followingBlock?.type === 'paragraph' && isWorkflowValue(nodeText(followingBlock))
  })
}

function splitTableRow(line) {
  const trimmed = line.trim()
  if (!trimmed.includes('|')) return null
  const cells = trimmed.split(/(?<!\\)\|/)
  if (trimmed.startsWith('|')) cells.shift()
  if (trimmed.endsWith('|')) cells.pop()
  return cells.map((cell) => cell.trim().replaceAll('\\|', '|'))
}

function cellText(cell) {
  return normalizedText(nodeText(markdownParser.parse(cell)))
}

function isTableDelimiter(cells) {
  return cells.length > 0 && cells.every((cell) => /^:?-{3,}:?$/.test(cell.trim()))
}

function hasWorkflowStatusTable(content, document) {
  const codeLines = document.children
    .filter((node) => node.type === 'code')
    .map((node) => [node.position?.start.line, node.position?.end.line])
  const isCodeLine = (lineNumber) => codeLines.some(([start, end]) => start <= lineNumber && lineNumber <= end)
  const lines = content.split(/\r?\n/)

  for (let index = 0; index < lines.length - 2; index += 1) {
    if (isCodeLine(index + 1) || isCodeLine(index + 2)) continue
    const headers = splitTableRow(lines[index])
    const delimiter = splitTableRow(lines[index + 1])
    if (!headers || !delimiter || headers.length !== delimiter.length || !isTableDelimiter(delimiter)) continue
    const statusColumn = headers.findIndex((cell) => statusLabels.has(cellText(cell)))
    if (statusColumn < 0) continue

    for (let rowIndex = index + 2; rowIndex < lines.length; rowIndex += 1) {
      if (isCodeLine(rowIndex + 1) || !lines[rowIndex].trim()) break
      const row = splitTableRow(lines[rowIndex])
      if (!row || row.length !== headers.length) break
      if (isWorkflowValue(cellText(row[statusColumn]))) return true
    }
  }
  return false
}

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

function isExplanatoryParagraph(content, node) {
  return node?.type === 'paragraph' &&
    !hasCodeIndentation(content, node) &&
    hasMeaningfulText(node)
}

export async function validateDocumentation(root = siteRoot, contracts = pages) {
  const failures = []
  const pagesByRoute = new Map(Object.keys(contracts).map((page) => [routeForPage(page), page]))
  const documents = new Map()

  for (const [page, contract] of Object.entries(contracts)) {
    const absolutePath = path.join(root, page)
    try {
      await access(absolutePath)
    } catch {
      failures.push(`${page}: missing page`)
      continue
    }
    const content = await readFile(absolutePath, 'utf8')
    const document = markdownParser.parse(content)
    documents.set(page, { content, document })
  }

  for (const [page, contract] of Object.entries(contracts)) {
    const parsed = documents.get(page)
    if (!parsed) continue
    const { content, document } = parsed
    if (forbidden.test(content) || hasWorkflowStatusHeading(document) || hasWorkflowStatusTable(content, document)) {
      failures.push(`${page}: contains forbidden tracker or source metadata`)
    }
    for (const url of findLinks(document)) {
      if ((!url.startsWith('/') && !url.startsWith('#')) || url.startsWith('//')) continue
      const hashIndex = url.indexOf('#')
      const pathOnly = url.startsWith('#') ? routeForPage(page) : url.split(/[?#]/, 1)[0]
      const route = pathOnly.length > 1 ? pathOnly.replace(/\/$/, '') : pathOnly
      const targetPage = pagesByRoute.get(route)
      if (!targetPage) {
        failures.push(`${page}: link points to missing route ${route}`)
        continue
      }
      if (hashIndex < 0 || hashIndex === url.length - 1) continue
      const rawFragment = url.slice(hashIndex + 1)
      let fragment = rawFragment
      try {
        fragment = decodeURIComponent(rawFragment)
      } catch {
        // Keep malformed fragments literal so validation reports the missing heading.
      }
      const targetDocument = documents.get(targetPage)?.document
      if (targetDocument && !headingIds(targetDocument).has(fragment)) {
        failures.push(`${page}: link points to missing heading #${rawFragment} in ${route}`)
      }
    }
    for (const heading of contract.headings) {
      if (!content.includes(`## ${heading}`)) failures.push(`${page}: missing heading ${heading}`)
    }
    const diagrams = document.children
      .map((node, siblingIndex) => ({ node, siblingIndex }))
      .filter(({ node }) => node.type === 'code' && node.lang === 'mermaid')
    if (diagrams.length < contract.diagrams) failures.push(`${page}: expected ${contract.diagrams} Mermaid diagrams, found ${diagrams.length}`)
    for (const [index, diagram] of diagrams.entries()) {
      const followingBlock = document.children[diagram.siblingIndex + 1]
      if (!isExplanatoryParagraph(content, followingBlock)) {
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
