# Project Documentation Roadmap Design

## เป้าหมาย

ปรับเว็บไซต์ Nextra ให้เป็น Project Documentation สำหรับ TiewTrade V2 โดยอธิบายขอบเขตผลิตภัณฑ์ หัวข้อเอกสาร ลำดับการจัดทำ และเกณฑ์คุณภาพจากไฟล์ใน repository เท่านั้น เว็บไซต์ต้องไม่แสดงข้อมูลจาก Issue Tracker เช่น URL, issue identifier, status หรือโครงสร้าง Main/Sub-issue

## แนวทางที่เลือก

- เปลี่ยน route จาก `/work-plan` เป็น `/roadmap`
- เปลี่ยนชื่อหน้าเป็น `Project Roadmap`
- ใช้ `PRODUCT.md` และ design/implementation documents ที่มีอยู่เป็น source metadata ของหน้า
- อธิบายหัวข้อเอกสารที่วางแผนไว้โดยไม่อ้างว่าหัวข้อที่ยังไม่มี source file เสร็จสมบูรณ์แล้ว
- ให้ repository documents เป็น Source of Truth และให้ Nextra เป็น presentation layer เท่านั้น

การคงชื่อ `Documentation Roadmap` หรือ route `/work-plan` ไม่ถูกเลือก เพราะทำให้หน้าดูเป็นรายการงานมากกว่าเอกสารภาพรวมของโครงการ

## Information Architecture

หน้า `Project Roadmap` ประกอบด้วยสี่ส่วน:

1. `Goals and Scope` — วัตถุประสงค์ กลุ่มผู้อ่าน ขอบเขต local documentation site และสิ่งที่ไม่รวม
2. `Documentation Areas` — Product, Domain, Architecture, Strategy and Trading Safety และ Delivery and Decisions
3. `Delivery Order` — ลำดับการสร้างเอกสารจาก foundation ไปสู่ final verification โดยไม่ผูกกับรหัสงาน
4. `Quality Gates` — source metadata, automated reference checks, tests, production build, responsive verification และการตรวจ secrets

หน้า Overview และ navigation ต้องเรียกหัวข้อนี้ว่า `Project Roadmap` และลิงก์ไป `/roadmap`

## Source Ownership

- `PRODUCT.md` เป็นแหล่งข้อมูลผลิตภัณฑ์ที่มีอยู่ในปัจจุบัน
- `CONTEXT.md`, `ARCHITECTURE.md`, `PROJECT_PLAN.md` และ `docs/adr/` จะเป็น Source of Truth ของหัวข้อที่เกี่ยวข้องเมื่อไฟล์เหล่านั้นถูกจัดทำ
- design และ implementation documents อธิบายขอบเขตและลำดับการสร้าง documentation site
- MDX pages ต้องเป็น curated summary และต้องไม่กลายเป็น Source of Truth ชุดที่สอง

## Validation

Automated test ต้องตรวจว่า:

- ไฟล์ `content/roadmap.mdx` มีหัวข้อหลักครบ
- เนื้อหาไม่มี Issue Tracker URL, ชื่อระบบติดตามงาน, issue identifier หรือถ้อยคำแบบ Main/Sub-issue
- source metadata อ้างถึงไฟล์ที่มีอยู่จริง
- Overview และ navigation ใช้ route `/roadmap`

หลังแก้ไขต้องรัน `npm test`, `npm run build`, `git diff --check` และตรวจหน้า `/roadmap` ใน browser

## Non-goals

- ไม่เพิ่ม deployment หรือ CI
- ไม่สร้าง content generation pipeline
- ไม่สร้าง source files ของ Domain, Architecture หรือ Project Plan ล่วงหน้าในงานนี้
- ไม่เปลี่ยน business rules ใน `PRODUCT.md`
