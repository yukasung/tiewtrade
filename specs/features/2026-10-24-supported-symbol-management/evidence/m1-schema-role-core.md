# F-37 M1 — Schema, role และ core contract

วันที่: 2026-10-24

สถานะ: **Passed**

## ขอบเขตที่ปิดแล้ว

- บันทึก ADR-005 เรื่อง PostgreSQL source of truth, pair fence/lock order, audit ownership,
  bootstrap role และ rolling protocol gate
- เพิ่ม migration `0039_supported_symbol_catalog.py` แบบ additive โดยเริ่มจาก BTC/USDT และ
  ETH/USDT, ปิด catalog mutation ไว้ และคง static compatibility snapshot
- เพิ่ม registry, global revision control, pair fence/projection, append-only events,
  idempotent command state, immutable constraints snapshots, readiness/effects และ protocol heartbeat
- เปลี่ยน pair constraints และ indicator stored functions ที่ runtime ใช้จาก hard-coded BTC/ETH
  เป็น registry/fence แบบ dynamic
- เพิ่ม deployment-only `tiewtrade_platform_bootstrap` ซึ่งไม่มี table privilege, ไม่เป็น
  superuser/owner/`BYPASSRLS` และเรียกได้เฉพาะ one-shot bootstrap function
- bootstrap ตรวจ user ที่มี active TOTP, serialize ด้วย advisory lock และเขียน membership กับ
  typed append-only audit ใน transaction เดียว
- เพิ่ม immutable `CatalogSnapshot` ใน pure core และคง `COMPATIBILITY_SNAPSHOT` revision 0
- เพิ่ม offline interactive CLI `platform-owner-bootstrap --user-id <uuid>` ที่ต้องพิมพ์ UUID ซ้ำ

## หลักฐาน

| การตรวจ | ผล |
|---|---|
| Alembic single head | `0039 (head)` |
| migration `0039 → 0038 → 0039` | ผ่าน |
| clean schema replay `base → head → base → head` | ผ่าน |
| F-37 catalog/privilege/bootstrap integration | 7 passed |
| M1 affected tests รวม migration replay/audit/core/CLI | 42 passed |
| Ruff check | ผ่านทั้ง backend |
| Ruff format check | ผ่าน 506 files |
| strict mypy | ผ่าน 462 source files |
| import-linter | 7 contracts kept, 0 broken |
| `git diff --check` | ผ่าน |

Dynamic third-pair regression เพิ่ม SOL/USDT ภายใน transaction, เขียน
`market_latest_prices`, บังคับ deferred constraints แล้วอ่าน revision 3 จาก active view ได้
ก่อน rollback fixture โดยไม่มี static pair constraint ขวาง และ `pg_get_functiondef` ของ
`seed_indicator_build_jobs`, `claim_indicator_build_job`, `transition_indicator_rollout`
ไม่มี BTC/ETH ฝังอยู่แล้ว

Privilege probe ยืนยัน `tiewtrade_platform_bootstrap` มี `rolsuper=false`,
`rolbypassrls=false`, ไม่มี `SELECT` บน registry และมีเพียง `EXECUTE` บน bootstrap function
ตามขอบเขตที่อนุมัติ

## ปัญหาที่พบและแก้ระหว่างพัฒนา

- แก้วงเล็บของ dynamic dispatch expression หลัง PostgreSQL ปฏิเสธ function definition
- แก้ลำดับ downgrade ให้ลบ trigger-owning tables ก่อน projection function
- เพิ่ม deferred global-revision invariant หลัง review พบว่า pair projection invariant อย่างเดียว
  ยังไม่บังคับ `catalog_control.current_revision = max(event.revision)`
- เพิ่ม RLS ให้ command table และจำกัด idempotency/reason codes ที่ฐานข้อมูล

ผลรอบสุดท้ายทั้งหมดข้างต้นผ่านบน schema/code ปัจจุบันแล้ว

## งานถัดไป

M2 ยังต้องทำ API mutation/readiness, venue validation, hot reload ของ market-data/indicator,
protocol heartbeat/enable gate และ OpenAPI/generated frontend contract งานทั้ง feature ยังไม่ถึง
สถานะ `Ready for Code Review`
