import { access, readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const scriptsDirectory = path.dirname(fileURLToPath(import.meta.url))
const siteRoot = path.resolve(scriptsDirectory, '..')
const repositoryRoot = path.resolve(siteRoot, '..')

export const references = {
  'content/index.mdx': ['PRODUCT.md'],
  'content/product.mdx': ['PRODUCT.md'],
  'content/work-plan.mdx': [
    'docs/superpowers/specs/2026-07-21-internal-reference-docs-design.md',
    'docs/superpowers/plans/2026-07-21-internal-reference-docs.md'
  ]
}

export async function validateSourceReferences() {
  const failures = []

  for (const [page, sources] of Object.entries(references)) {
    const content = await readFile(path.join(siteRoot, page), 'utf8')

    if (!/Last reviewed date: \d{4}-\d{2}-\d{2}/.test(content)) {
      failures.push(`${page}: missing Last reviewed date`)
    }

    for (const source of sources) {
      try {
        await access(path.join(repositoryRoot, source))
      } catch {
        failures.push(`${page}: missing source ${source}`)
      }

      if (!content.includes(`Source file: \`${source}\``)) {
        failures.push(`${page}: does not declare ${source}`)
      }
    }
  }

  return failures
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const failures = await validateSourceReferences()
  if (failures.length) {
    console.error(failures.join('\n'))
    process.exitCode = 1
  }
}
