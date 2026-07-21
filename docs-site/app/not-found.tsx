import Link from 'next/link'

export default function NotFound() {
  return (
    <main className="x:mx-auto x:flex x:min-h-[60vh] x:max-w-2xl x:flex-col x:items-start x:justify-center x:gap-4 x:px-6">
      <p className="x:text-sm x:font-semibold x:text-blue-600">404</p>
      <h1 className="x:text-3xl x:font-bold">ไม่พบหน้าเอกสาร</h1>
      <p className="x:text-gray-600">เส้นทางนี้ไม่มีในเอกสาร TiewTrade V2</p>
      <Link className="x:font-medium x:text-blue-600 x:underline" href="/">
        กลับไปหน้า Overview
      </Link>
    </main>
  )
}
