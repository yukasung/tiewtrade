import { access, readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import { unified } from 'unified'
import remarkParse from 'remark-parse'
import remarkMdx from 'remark-mdx'

const siteRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const markdownParser = unified().use(remarkParse).use(remarkMdx)

export const pages = {}

const forbidden = /linear\.app|\bDEV-\d+\b|Source file:|Last reviewed date:|Main Issue|Sub-issues/i
const unicodeLetterOrNumber = /[\p{L}\p{N}]/u

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

function hasFollowingProseParagraph(content, diagram) {
  const diagramBody = content.slice(diagram.index + diagram[0].length)
  const closingFence = diagramBody.match(/^```[ \t]*$/m)
  if (!closingFence) return false

  const followingContent = diagramBody.slice(closingFence.index + closingFence[0].length)
  const firstBlock = markdownParser.parse(followingContent).children[0]
  return firstBlock?.type === 'paragraph' &&
    !hasCodeIndentation(followingContent, firstBlock) &&
    hasMeaningfulText(firstBlock)
}

export async function validateDocumentation(root = siteRoot, contracts = pages) {
  const failures = []
  for (const [page, contract] of Object.entries(contracts)) {
    const absolutePath = path.join(root, page)
    try {
      await access(absolutePath)
    } catch {
      failures.push(`${page}: missing page`)
      continue
    }
    const content = await readFile(absolutePath, 'utf8')
    if (forbidden.test(content)) failures.push(`${page}: contains forbidden tracker or source metadata`)
    for (const heading of contract.headings) {
      if (!content.includes(`## ${heading}`)) failures.push(`${page}: missing heading ${heading}`)
    }
    const diagrams = [...content.matchAll(/^```mermaid[^\r\n]*\r?$/gm)]
    if (diagrams.length < contract.diagrams) failures.push(`${page}: expected ${contract.diagrams} Mermaid diagrams, found ${diagrams.length}`)
    for (const [index, diagram] of diagrams.entries()) {
      if (!hasFollowingProseParagraph(content, diagram)) {
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
