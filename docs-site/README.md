# TiewTrade Documentation Site

เว็บไซต์เอกสารภายในสร้างด้วย Next.js และ Nextra เนื้อหาอยู่ใน `content/` และตรวจโครงสร้างก่อน production build

## Install

```bash
cd docs-site
npm install
```

## Local development

```bash
npm run dev
```

เปิด `http://localhost:3000` หลัง development server พร้อมใช้งาน

## Test

```bash
npm test
```

## Content check

```bash
npm run check:content
```

คำสั่งนี้ตรวจ routes, headings, Mermaid diagrams, prose ที่อธิบายแต่ละ diagram และข้อความภายในที่ไม่ควรปรากฏในหน้าเอกสาร

## Production build

```bash
npm run build
```

Production build จะรัน content check ก่อนสร้าง Next.js application
