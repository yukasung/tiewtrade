import type { Metadata } from 'next'
import { Head } from 'nextra/components'
import { getPageMap } from 'nextra/page-map'
import { Footer, Layout, Navbar } from 'nextra-theme-docs'
import 'nextra-theme-docs/style.css'

export const metadata: Metadata = {
  title: {
    default: 'TiewTrade Reference',
    template: '%s — TiewTrade Reference'
  },
  description: 'Internal product and engineering reference for TiewTrade V2'
}

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="th" dir="ltr" suppressHydrationWarning>
      <Head>
        <meta name="application-name" content="TiewTrade Reference" />
      </Head>
      <body>
        <Layout
          navbar={<Navbar logo={<strong>TiewTrade Reference</strong>} />}
          pageMap={await getPageMap()}
          editLink={null}
          feedback={{ content: null, link: undefined }}
          footer={<Footer>TiewTrade Internal Alpha</Footer>}
        >
          {children}
        </Layout>
      </body>
    </html>
  )
}
