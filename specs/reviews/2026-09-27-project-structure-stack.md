# Review: โครงสร้างโปรเจกต์และความเหมาะสมกับ Tech Stack

วันที่: 2026-09-27  
สถานะ: ข้อเสนอจากการรีวิว — ยังไม่ได้แก้โครงสร้างหรืออนุมัติการเปลี่ยนสถาปัตยกรรม  
ขอบเขต: โครงสร้าง repo ปัจจุบัน, config เครื่องมือ, CI และ Docker เทียบกับ spec ของ F-01 และมาตรฐานโครงการ

## ข้อสรุป

โครงสร้างปัจจุบันเหมาะกับ Python/FastAPI + React/TypeScript/Vite และเหมาะกับการต่อยอดจาก F-01 ไม่จำเป็นต้องรื้อโครงหลัก อย่างไรก็ตาม สิ่งที่มีอยู่ยังเป็น skeleton ไม่ใช่ระบบเทรดที่พร้อม deploy ใช้งานจริง

งานที่ควรทำก่อนสุดคือทำให้เอกสารสถานะตรงกัน จากนั้นค่อยเพิ่มโครงย่อยตาม feature ที่ผ่านอนุมัติ การไม่มี PostgreSQL, Redis หรือ frontend libraries ครบทุกตัวในตอนนี้ ไม่ใช่หลักฐานว่างาน F-01 ทำตกหล่น

## สิ่งที่เหมาะแล้ว

| ส่วน | ผลประเมินและเหตุผล |
|---|---|
| `backend/` และ `frontend/` ใน repo เดียว | เหมาะกับสองภาษา แยก dependency และเครื่องมือ แต่เปลี่ยน API และผู้เรียกในงานเดียวกันได้ |
| `backend/src/` | แยก source ออกจาก tests และ config เหมาะกับการจัด package Python |
| `core/`, `strategies/`, `venues/`, `infra/` | รองรับการแยกตรรกะคำนวณ กลยุทธ์ การเชื่อมตลาด และโครงสร้างพื้นฐานตาม spec |
| `services/api`, `services/engine`, `services/market_data` | วางที่สำหรับ API และ process ที่รันยาวตามสถาปัตยกรรม โดย engine และ market_data ยังเป็น placeholder |
| OpenAPI → TypeScript | ลดการประกาศชนิดข้อมูลซ้ำข้ามภาษา และมี CI ตรวจไฟล์ที่สร้างแล้วกับสัญญาปัจจุบัน |
| import-linter และ tests ของด่านตรวจ | มี config บังคับทิศทาง dependency และกรณีทดสอบด่าน ไม่ได้อาศัยเพียงชื่อโฟลเดอร์หรือการรีวิว |
| Frontend ขนาดเล็ก | เหมาะกับขอบเขตหน้า health ของ F-01 ยังไม่มีเหตุให้สร้างโครงซับซ้อนล่วงหน้า |

อ้างอิง: [architecture](../standards/architecture.md), [tech stack](../tech-stack.md), [F-01 requirements](../features/2026-09-26-project-skeleton/requirements.md), [F-01 plan](../features/2026-09-26-project-skeleton/plan.md), [backend config](../../backend/pyproject.toml), [CI](../../.github/workflows/ci.yml)

## ข้อเสนอปรับปรุงตามลำดับความสำคัญ

### 1. ทำเอกสารสถานะให้ตรงกันก่อนเริ่มงานถัดไป

หลักฐาน:

- [AGENTS.md](../../AGENTS.md) ยังระบุว่าไม่มีโค้ดแอปพลิเคชันและไม่มีงานผ่านเงื่อนไขอนุมัติครบ
- [tech-stack.md](../tech-stack.md) ยังระบุว่า “ยังไม่มีโค้ดสักบรรทัด”
- [roadmap.md](../roadmap.md) ระบุ F-01 Completed แล้ว
- [plan.md](../features/2026-09-26-project-skeleton/plan.md) และ [validation.md](../features/2026-09-26-project-skeleton/validation.md) ของ F-01 ระบุ Approved
- ส่วนท้ายของ [requirements.md](../features/2026-09-26-project-skeleton/requirements.md) ยังบอกว่า plan และ validation รออนุมัติ

ผลกระทบ: ผู้พัฒนาและ agent อาจเข้าใจสถานะหรือจุดอนุมัติผิด และเลือกขั้นตอนการทำงานไม่ตรงกัน

ข้อเสนอ: ตรวจประวัติการอนุมัติแล้วปรับข้อความสถานะที่ล้าสมัยให้ตรงกัน โดยไม่ถือว่าการอนุมัติ F-01 เท่ากับอนุมัติ spec ทั้งโครงการ

**Needs Clarification:** เอกสารกำกับงานกับสถานะ F-01 ขัดกัน ต้องยืนยันข้อความสถานะที่ถูกต้องก่อนอาศัยเอกสารเหล่านี้เป็นฐานตัดสินสิทธิ์เริ่ม implementation งานถัดไป รายงานนี้ไม่เลือกแก้สถานะหรือประกาศอนุมัติแทนเจ้าของ

### 2. กำหนดทาง deploy production แยกจาก skeleton ปัจจุบัน

หลักฐาน: [frontend/Dockerfile](../../frontend/Dockerfile) เรียก `npm run dev` และ [CI](../../.github/workflows/ci.yml) ยังไม่มีขั้น `npm run build` สำหรับ frontend

ผลกระทบ: การรัน container ปัจจุบันพิสูจน์เส้นทาง development ได้ แต่ยังไม่พิสูจน์ว่า production bundle สร้างและเสิร์ฟได้ การผ่าน typecheck และ unit tests ไม่ทดแทนการ build

ข้อเสนอเมื่อทำงาน deployment:

- เพิ่มการตรวจ production build ใน CI
- กำหนดขั้น build frontend และวิธีเสิร์ฟไฟล์ที่ build แล้ว
- ระบุให้ชัดว่า Compose ชุดใดใช้พัฒนาและชุดใดใช้ deploy

ข้อนี้เป็นงานเตรียมก่อน deploy จริง ไม่ใช่ข้อสรุปว่า F-01 ผิดขอบเขตที่อนุมัติ อ้างอิงแนวทาง [Vite: Building for Production](https://vite.dev/guide/build)

### 3. กำหนดโครง frontend เมื่อเริ่มหน้าจอจริง

หลักฐาน: [frontend/package.json](../../frontend/package.json) ยังไม่มี TanStack Query, Zustand และ i18next ส่วน [App.tsx](../../frontend/src/App.tsx) เป็นหน้า health ขนาดเล็ก ใช้ state และข้อความในไฟล์โดยตรง

F-01 กำหนดให้เป็นหน้าพิสูจน์การเชื่อมต่อและยังไม่ทำระบบแปลหรือ component กลาง จึงไม่ควรนำหน้าตัวอย่างนี้ไปเป็นรูปแบบสำหรับหน้าจอผลิตภัณฑ์โดยอัตโนมัติ

ข้อเสนอ: ก่อนเพิ่มหลายหน้า ให้ระบุตำแหน่งของ feature, API client/generated types, component กลาง และคำแปลในแผนของงานหน้าจอจริง พร้อมใช้เครื่องมือจัดการข้อมูลตาม [frontend standard](../standards/frontend.md) ไม่จำเป็นต้องติดตั้งทุก library หรือสร้างทุกโฟลเดอร์ล่วงหน้า

### 4. พิจารณา namespace ของ Python package ก่อนโค้ดโต

หลักฐาน: [backend/pyproject.toml](../../backend/pyproject.toml) ประกาศ package ระดับบนหลายชื่อ เช่น `core`, `infra` และ `services`

โครงนี้ใช้งานได้ แต่ชื่อทั่วไปอาจชนกับ package อื่นและไม่ได้บอกเจ้าของชัดเจน

ข้อเสนอทางเลือก: พิจารณารวมใต้ `backend/src/tiewtrade/` เพื่อให้ import เป็น `tiewtrade.core` และ `tiewtrade.services` โดยยังคง `src/` layout

นี่เป็นทางเลือกปรับปรุง ไม่ใช่ข้อผิดพลาดหรือเงื่อนไขที่ต้องทำก่อนต่อยอด หากเลือกเปลี่ยน ต้องปรับ spec, imports, packaging, entry points, tests และกฎ import-linter ให้ตรงกันตามขั้นตอนอนุมัติของ repo

อ้างอิงเรื่อง `src/` layout: [Python Packaging User Guide](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/) ส่วนการใช้ namespace `tiewtrade` เป็นข้อเสนอจากการรีวิวนี้

## สิ่งที่ยังไม่จำเป็นต้องเพิ่ม

- การแยก repo หรือเพิ่ม microservices มากกว่าสาม process ที่ spec กำหนด
- เครื่องมือ monorepo เพิ่มเติมเพียงเพราะมี backend และ frontend
- โฟลเดอร์เปล่าจำนวนมากสำหรับ feature ที่ยังไม่มีแผนอนุมัติ
- PostgreSQL และ Redis ใน F-01 ซึ่งถูกเลื่อนออกจากขอบเขตโดยเจตนาแล้ว

## ขอบเขตการตรวจและข้อจำกัด

- ตรวจ source, โครงไฟล์, dependency/config, CI, Docker และเอกสารที่เกี่ยวข้องแบบอ่านอย่างเดียว
- ใช้หลักการจาก skill `codebase-design` ประเมินการแยกหน้าที่และความสามารถในการทดสอบ
- ไม่ได้รัน tests, build, E2E หรือ Docker ในรอบนี้ จึงไม่รับรองว่าด่านปัจจุบันผ่านจากการตรวจครั้งนี้
- สถานะ Completed และผล CI ในอดีตเป็นข้อมูลที่บันทึกไว้ใน repo ไม่ได้ตรวจยืนยันกับ remote CI
- ยังประเมินพฤติกรรมระบบเทรดจริงไม่ได้ เพราะ core, strategies, venues และ infra ยังเป็นโครงเปล่า
- ไม่ได้แก้โค้ด เปลี่ยน stack หรือเปลี่ยนสถานะอนุมัติของ spec
