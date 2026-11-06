# ข้อเสนอขยาย dependency remediation — NC-SEC-REF-01

สถานะ: **Approved — เจ้าของตอบ approve ให้ amendment requirements/plan/validation 2026-11-06**
วันที่: 2026-11-06

## เหตุผลและหลักฐาน

Full OSV v2.7.0 scan ของ template baseline พบ High 8 records ไม่ใช่เฉพาะ 5 native
alerts ที่ใช้กำหนดงานตอนแรก. Temporary candidate ที่อัปเดต 3 packages ตามอนุมัติ
แก้เป้าหมายทั้ง 5 แล้ว แต่ยังเหลือ High 3 records ในอีก 2 packages ดังตาราง.
ทั้ง 3 มีอยู่ใน baseline เดิมด้วย ไม่ใช่ช่องโหว่ที่ candidate เพิ่มเข้ามา.

| Package | Current → proposed target | Remaining High | Parent range เดิม |
|---|---|---|---|
| brace-expansion | 5.0.9 → 5.0.11 | GHSA-6j4f-fj2g-mc7p; GHSA-qhr7-859c-m2p7 | minimatch 10.2.6 → `^5.0.8` |
| zod | 4.5.4 → 4.6.6 | GHSA-mrhx-c7xc-m3w5 | eslint-plugin-react-hooks 7.1.1 → `^3.25.0 || ^4.0.0` |

Advisory ranges: brace-expansion สองรายการแก้ที่ 5.0.10 และ 5.0.11 ตามลำดับ
จึงเลือก 5.0.11; zod `<4.6.6` แก้ที่ 4.6.6. ตรวจ GitHub advisory API และ npm
exact-version registry แล้ววันที่ 2026-11-06: releases มีจริง ไม่ withdrawn และ
targets อยู่ใน parent ranges เดิม. brace-expansion 5.0.11 ยังใช้ balanced-match
`^4.0.2` ซึ่ง locked 4.0.4 เดิมรองรับ; zod 4.6.6 ไม่มี dependency ใหม่ใน metadata.
ยังไม่ได้เปลี่ยน/ติดตั้ง/ทดสอบ 2 targets นี้ จึงยังไม่รับรอง candidate ใหม่จะผ่าน.

หลักฐาน: [feature-candidate.md](feature-candidate.md),
[safe results + inventories](feature-candidate.json). Baseline 373 occurrences / 372
unique package pairs; scanner ตรง inventory ทั้งหมด และ missing-row control ถูกปฏิเสธ.

## ข้อเสนอที่แนะนำ: ขยายงานเดิมอย่างจำกัด

อนุมัติแก้เอกสารทั้งสามตามรายการนี้ก่อนดำเนิน implementation ต่อ:

1. **Requirements:** เพิ่ม 2 packages/3 scanner High ในตาราง target และขอบเขต/RR-1
   จากเดิม 3 packages/5 native High เป็น 5 packages/8 known High records.
   แยกที่มาของ native alerts เดิมกับ additional scanner findings ให้ชัด ไม่อ้างว่า
   GitHub native มี 8 alerts. คง targets เดิม, manifest ranges และ RR-2..8 รวม
   no High/Critical/unknown, stop-on-scope-expansion และห้าม exceptions ตามเดิม.
2. **Plan:** ขยาย allowlist lock entries เป็น 5 packages; ขั้น registry metadata,
   clean/frozen install, full inventory scan, build และ browser เดิมใช้ทั้งหมดต่อ.
   เพิ่ม temporary compatibility probes ของ brace-expansion ผ่าน minimatch caller
   (literal/escaped/nested brace cases ขนาดเล็ก) และ zod ผ่านการ resolve จาก
   eslint-plugin-react-hooks (valid/invalid constrained collections ขนาดเล็ก).
   ตรวจ actual ESLint config/plugin loading กับ temporary valid/invalid hook fixtures
   ใน isolated template copy; ต้องแยก expected rule rejection ออกจาก tool crash.
   ไม่ทำ resource exhaustion/exploit ไม่แก้ template source/config.
3. **Validation:** RV-01 ครอบคลุม 5 packages; RV-04 ครอบคลุม known High ทั้ง 8
   และ full candidate findings ตามจริง; RV-06 เพิ่ม caller/plugin probes ข้างต้น.
   RV-02/03/05/07/08/09/10 และระยะ Feature/Release เดิมคงไว้.
4. **Clarification/status:** ปิด NC-SEC-REF-01 ด้วยคำอนุมัติและปรับ roadmap;
   implementation ต่อได้หลังบันทึก amendment ที่อนุมัติแล้วเท่านั้น.

ผลกระทบ: zod เป็น minor update ภายใน major 4 เพิ่ม compatibility surface ของ
ESLint plugin; ต้องทดสอบ caller จริง. brace-expansion เป็น patch update อยู่ใน range
เดิม. ยังไม่ต้องเปลี่ยน manifest, package อื่น, UI/application source, database/trading,
scanner policy/pins/exceptions หรือ permanent CI scope. หากพบว่าต้องขยายอีกให้หยุดตามเดิม.

## ทางเลือกและข้อจำกัด

- **ขยาย scope ตามข้อเสนอ (แนะนำ):** แก้ known High ให้ครบโดยไม่ลด security gate;
  ต้องตรวจ candidate ใหม่และ compatibility เพิ่มตามรายการข้างต้น.
- **คง scope เดิม:** เก็บงานไว้ Blocked; 3 High ยังทำให้ RR-4/RV-04 ไม่ผ่านและ merge
  ไม่ได้. อาจแยกงาน remediation สำหรับ 2 packages แล้วกลับมาตรวจ candidate รวมภายหลัง.

ไม่เสนอ dismiss/ignore/ยกเว้น severity เพื่อให้ผ่าน. Original repository lockfile
ยังไม่ได้เปลี่ยน; candidate อยู่ใน temporary directory และยังไม่ install/build/browser.
ไม่มี commit/push/PR/merge ใน checkpoint นี้.

## แหล่งอ้างอิง

- [brace-expansion recursion advisory](https://github.com/juliangruber/brace-expansion/security/advisories/GHSA-6j4f-fj2g-mc7p)
- [brace-expansion nested-brace advisory](https://github.com/juliangruber/brace-expansion/security/advisories/GHSA-qhr7-859c-m2p7)
- [Zod fix](https://github.com/colinhacks/zod/pull/6652) และ [advisory](https://github.com/advisories/GHSA-mrhx-c7xc-m3w5)
- [brace-expansion 5.0.11 registry](https://registry.npmjs.org/brace-expansion/5.0.11)
- [zod 4.6.6 registry](https://registry.npmjs.org/zod/4.6.6)
