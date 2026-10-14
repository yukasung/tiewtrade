# Feature Specs

ทุกงานใหม่ได้โฟลเดอร์ของตัวเองหนึ่งอัน:

```
specs/features/YYYY-MM-DD-<ชื่อ-แบบ-kebab-case>/
├── requirements.md   ← ทำอะไร และทำไม
├── plan.md           ← ทำอย่างไร
└── validation.md     ← รู้ได้อย่างไรว่าเสร็จและปลอดภัย
```

วันที่คือวันที่เริ่มงาน หนึ่ง feature = หนึ่ง spec = หนึ่ง branch

---

## จุดหยุดสองจุด

```
requirements.md → [เจ้าของอนุมัติ] → plan.md + validation.md → [เจ้าของอนุมัติ] → เขียนโค้ด
```

**ห้ามเริ่มขั้นถัดไปก่อนได้รับอนุมัติ**

---

## requirements.md

```markdown
# <ชื่องาน> — Requirements

สถานะ: Proposed | Approved
วันที่:

## ทำไมต้องมี
ปัญหาอะไร ใครเดือดร้อน

## ขอบเขต
ทำอะไร / ไม่ทำอะไร

## ข้อกำหนด
| รหัส | ข้อกำหนด | ที่มา |
|---|---|---|
| RQ-1 | | mission.md / คำตอบเจ้าของ |

## กฎความปลอดภัยที่เกี่ยวข้อง
อ้างข้อจาก standards/trading-safety.md

## ยังไม่ชัด
สิ่งที่ยังไม่ได้ตัดสิน — ห้ามเดา ให้ถามเจ้าของ
```

## plan.md

```markdown
# <ชื่องาน> — Plan

สถานะ: Proposed | Approved

## แนวทาง
ทำอย่างไร และทำไมเลือกทางนี้

## ของเดิมที่จะใช้ซ้ำ
ฟังก์ชัน/component ที่มีอยู่แล้ว พร้อม path — ค้นก่อนเขียนใหม่เสมอ

## สิ่งที่จะแก้
| ไฟล์ | เปลี่ยนอะไร |

## ผลต่อฐานข้อมูล
migration ที่ต้องมี

## ความเสี่ยง
อะไรอาจพัง และจะรู้ได้อย่างไร
```

## validation.md

แยกเวลารันตาม `standards/testing.md` หัวข้อ 7: ระหว่างพัฒนา, candidate ก่อน merge,
และ release checkpoint ใช้ plan ที่อนุมัติแล้วต่อ ไม่ลดเกณฑ์ตรวจรับ
ชุดเต็ม performance/workload/stress/endurance/resource ระบุ `Pending Full Validation`
พร้อม checkpoint และหลักฐานเดิม; ส่วน correctness/trading safety ตรวจตามผลกระทบทันที

```markdown
# <ชื่องาน> — Validation

## "เสร็จ" หมายถึง
| # | เกณฑ์ | ตรวจอย่างไร | ระยะรัน | ผล / หลักฐาน |

## เทสต์ที่ต้องมี
- ตัวเลขจริง:
- คุณสมบัติ (hypothesis):
- ความปลอดภัยการเทรด:

## ตรวจด้วยมือ
ขั้นตอนที่คนต้องลองเอง

## ด่านที่ต้องเขียว
ระหว่างพัฒนา: targeted Tests และ checks ตามผลกระทบ
ก่อน merge: lint / types / imports / full regression / required CI ตามมาตรฐาน
ก่อน Completed/release: เกณฑ์ตรวจรับครบ รวม Pending Full Validation
```
