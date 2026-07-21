import { access, readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const siteRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

export const pages = {}

const forbidden = /linear\.app|\bDEV-\d+\b|Source file:|Last reviewed date:|Main Issue|Sub-issues/i
const nonProseBlock = /^(?:#{1,6}(?:\s|$)|```|~~~|>|[-+*]\s|\d+[.)]\s|\||<)/
const horizontalRule = /^(?:(?:\*[ \t]*){3,}|(?:-[ \t]*){3,}|(?:_[ \t]*){3,})$/
const standaloneImage = /^!\[[^\]\r\n]*\]\([^\r\n]*\)$/

function hasFollowingProseParagraph(content, diagram) {
  const diagramBody = content.slice(diagram.index + diagram[0].length)
  const closingFence = diagramBody.match(/^```[ \t]*$/m)
  if (!closingFence) return false

  const followingContent = diagramBody.slice(closingFence.index + closingFence[0].length)
  const firstBlock = followingContent.trimStart().split(/\r?\n[ \t]*\r?\n/, 1)[0].trim()
  return firstBlock.length > 0 &&
    !nonProseBlock.test(firstBlock) &&
    !horizontalRule.test(firstBlock) &&
    !standaloneImage.test(firstBlock)
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
