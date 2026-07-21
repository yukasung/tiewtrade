import nextra from 'nextra'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const withNextra = nextra({})
const siteRoot = path.dirname(fileURLToPath(import.meta.url))

export default withNextra({
  turbopack: {
    root: siteRoot
  }
})
