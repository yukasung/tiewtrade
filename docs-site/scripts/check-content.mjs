import { access, readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const siteRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

export const pages = {}

const forbidden = /linear\.app|\bDEV-\d+\b|Source file:|Last reviewed date:|Main Issue|Sub-issues/i
const horizontalRule = /^(?:(?:\*[ \t]*){3,}|(?:-[ \t]*){3,}|(?:_[ \t]*){3,})$/
const standaloneInlineImage = /^!\[[^\]\r\n]*\]\([^\r\n]*\)$/
const standaloneReferenceImage = /^!\[[^\]\r\n]*\]\[[^\]\r\n]*\]$/
const referenceDefinition = /^\[[^\]\r\n]+\]:[ \t]+\S/
const unicodeLetterOrNumber = /[\p{L}\p{N}]/u

function firstNonblankBlock(content) {
  const lines = content.replace(/\r\n?/g, '\n').split('\n')
  const start = lines.findIndex(line => line.trim().length > 0)
  if (start === -1) return ''

  let end = start
  while (end < lines.length && lines[end].trim().length > 0) end += 1
  return lines.slice(start, end).join('\n')
}

function isTableDelimiter(line) {
  const trimmed = line.trim()
  if (!trimmed.includes('|')) return false

  const cells = trimmed.replace(/^\|/, '').replace(/\|$/, '').split('|')
  return cells.length > 0 && cells.every(cell => /^:?-{3,}:?$/.test(cell.trim()))
}

function isPlainProseParagraph(block) {
  if (!block) return false

  const lines = block.split('\n')
  if (/^(?: {4}| {0,3}\t)/.test(lines[0])) return false

  const candidate = block.replace(/^ {0,3}/, '').trimEnd()
  const firstLine = candidate.split('\n', 1)[0]
  if (/^(?:#{1,6}(?:[ \t]+|$)|`{3,}|~{3,}|>|[-+*][ \t]+|\d{1,9}[.)][ \t]+|\||<|\{)/.test(firstLine)) return false
  if (horizontalRule.test(candidate)) return false
  if (standaloneInlineImage.test(candidate) || standaloneReferenceImage.test(candidate)) return false
  if (referenceDefinition.test(candidate)) return false
  if (lines.length > 1 && /^(?:=+|-+)[ \t]*$/.test(lines[1].trim())) return false
  if (lines.length > 1 && firstLine.includes('|') && isTableDelimiter(lines[1])) return false

  return unicodeLetterOrNumber.test(candidate)
}

function hasFollowingProseParagraph(content, diagram) {
  const diagramBody = content.slice(diagram.index + diagram[0].length)
  const closingFence = diagramBody.match(/^```[ \t]*$/m)
  if (!closingFence) return false

  const followingContent = diagramBody.slice(closingFence.index + closingFence[0].length)
  return isPlainProseParagraph(firstNonblankBlock(followingContent))
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
