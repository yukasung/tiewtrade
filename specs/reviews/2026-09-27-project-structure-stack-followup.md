# Review: โครงสร้างหลังย้ายเข้า tiewtrade — รอบติดตาม

วันที่: 2026-09-27  
ฉบับที่ตรวจ: `2f7891558ec6feb286e291412f2488d05da00a9f`  
อ้างอิง: [รีวิวรอบก่อน](2026-09-27-project-structure-stack.md)

## ผลประเมิน

ไม่พบข้อบกพร่องที่ต้องแก้จากการย้าย namespace ในขอบเขตที่ตรวจ โครงสร้างปัจจุบันเหมาะกับ stack และการต่อยอดจาก F-01 โดยยังไม่ใช่การรับรองความพร้อมสำหรับ production หรืออนุมัติ merge

Backend อยู่ใต้ `backend/src/tiewtrade/` โดยคงการแบ่ง core, strategies, venues, infra และ services ตามเดิม Frontend คง `frontend/src/` ได้ ไม่จำเป็นต้องเพิ่ม namespace แบบ Python

## ผลติดตามข้อเสนอเดิม

| ข้อ | สถานะ | หลักฐาน |
|---|---|---|
| 1. เอกสารสถานะล้าสมัย | แก้ประเด็นหลักแล้ว | AGENTS.md ระบุ F-01 เสร็จและงานใหม่ต้องผ่านอนุมัติของตัวเอง; tech-stack ระบุ stack ที่ใช้จริง; requirements ไม่ระบุว่า plan/validation รออนุมัติแล้ว |
| 2. Production deployment | บันทึกเป็นงานถัดไปแล้ว | roadmap F-31 ระบุการเพิ่ม build ใน CI และแยก development/deployment; Docker หน้าบ้านยังใช้ dev server ตามเดิม |
| 3. โครง frontend เมื่อมีหน้าจอจริง | ยังเป็นข้อเสนอสำหรับงานหน้าจอจริง | หน้าปัจจุบันยังเป็น health skeleton จึงยังไม่จำเป็นต้องเพิ่มโฟลเดอร์หรือ library ล่วงหน้า |
| 4. Python namespace | ย้ายครบในจุดที่ตรวจ | packaging, imports, mypy, import-linter, fixtures, purity test, Docker, Playwright, OpenAPI export, README และ spec อ้างชื่อใหม่ |

รีวิวรอบแรกเป็นบันทึกสภาพก่อนแก้ ให้ใช้รายงานนี้ประกอบเมื่อพิจารณาสถานะข้อเสนอเดิม

## รายละเอียดการตรวจโครงสร้าง

- Hatch package target เป็น `src/tiewtrade` และมี `__init__.py` ของ package หลัก
- mypy override ชี้ `tiewtrade.core.*`
- import-linter ใช้ root `tiewtrade` และยังบังคับสี่กฎเดิม
- fixtures ของ import-linter ย้ายตาม namespace และ tests ที่ใช้ config จริงผ่าน
- purity test ชี้ `src/tiewtrade/core` ไม่ได้ตรวจโฟลเดอร์เก่าที่ว่าง
- entry point ของ Uvicorn ใน README, Dockerfile และ Playwright ใช้ `tiewtrade.services.api.app:app`
- OpenAPI exporter ใช้ import ใหม่และปรับ default output path ให้ยังชี้ `backend/openapi.json` ถูกต้อง
- architecture และแผน F-01 บันทึก namespace ใหม่แล้ว โดยไม่เปลี่ยนทิศทาง dependency

## ผลตรวจที่รันในรอบนี้

| การตรวจ | ผล |
|---|---|
| Backend ruff check | ผ่าน |
| Backend ruff format --check | ผ่าน 20 ไฟล์ |
| Backend mypy | ผ่าน 20 source files |
| import-linter | ผ่าน 4 contracts |
| pytest | ผ่าน 24 tests มี deprecation warning ของ Starlette/httpx 1 รายการ |
| Frontend eslint | ผ่าน |
| Frontend TypeScript | ผ่าน |
| Vitest | ผ่าน 4 tests รวม API contract gate |
| Frontend production build | ผ่าน |
| OpenAPI schema และ default export path | ตรงกับไฟล์ที่เก็บใน repo และตำแหน่ง backend/openapi.json |

ใช้เครื่องมือที่ติดตั้งอยู่ใน backend venv และ frontend node_modules ของ workspace นี้ ไม่ได้ติดตั้ง dependency ใหม่

## ข้อจำกัดและงานที่ยังเหลือ

- ไม่ได้รัน E2E, Docker build/runtime หรือยืนยัน remote CI ในรอบนี้ จึงยังไม่รับรองเส้นทางเหล่านั้นหลังการย้าย
- การ build frontend ผ่านในเครื่องไม่ได้ทำให้ข้อเสนอเพิ่ม build ใน CI และ production serving ของ F-31 เสร็จแล้ว
- ยังไม่มีตรรกะเทรดจริงให้ตรวจ การผ่านด่านปัจจุบันไม่พิสูจน์ความถูกต้องของการคำนวณเงินหรือการส่งออเดอร์ในอนาคต
- ถ้อยคำใน AGENTS.md ที่ว่าเอกสารใน specs เป็น Proposed “ทั้งหมด” ยังอาจทำให้สับสน เพราะย่อหน้าเดียวกันระบุข้อยกเว้น F-01 แล้ว ควรใช้ “เอกสารระดับโครงการยังเป็น Proposed; เอกสาร F-01 ได้รับอนุมัติแล้ว” เมื่อปรับเอกสารครั้งถัดไป เป็นข้อเสนอด้านความชัดเจน ไม่ใช่ตัวบล็อกโครงสร้าง
- รอบนี้เพิ่มเฉพาะรายงานรีวิว ไม่ได้แก้ source/config หรือเปลี่ยนสถานะอนุมัติ
