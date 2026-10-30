# F-18 M1 — shared risk domain — 2026-10-26

สถานะ: M1 implementation/targeted checks ผ่าน; feature ยัง In Progress

## ขอบเขตและผล

- เพิ่ม `backend/src/tiewtrade/core/risk_limits.py`: immutable scope/setting/price/
  baseline/evaluation/stop contracts, loss evaluation, reset allowance, allocation
  หลัง partial sell/buy เพิ่ม, correction replay และ shared AdmissionPolicy
- ใช้ F-14 apply_execution/unrealized_pnl/rebuild_position และ Money/Quantity/
  allocate_money เดิม ไม่มี float/Decimal เปล่าคำนวณ ไม่มี domain access DB/network
- เพิ่ม `backend/tests/core/test_risk_limits.py` 46 cases รวม hand oracles, hypothesis,
  Paper/Live parity, duplicate/source-order rejection, reset/recovery/latch และ policy
  ที่ไม่บล็อก bounded reduction เมื่อ loss valuation unavailable

## เหตุผลเลือกตรวจ

เปลี่ยนเฉพาะ pure risk domain ที่เรียก F-14 และ order contracts จึงตรวจ risk tests
ร่วมกับ position/manual/parity/purity tests และ static checks; ยังไม่เปลี่ยน runtime
composition/schema/API จึงยังไม่รัน DB/full regression/workload ใน M1

คำสั่งจาก `backend/`:

```text
uv run ruff check src/tiewtrade/core/risk_limits.py tests/core/test_risk_limits.py
uv run ruff format --check src/tiewtrade/core/risk_limits.py tests/core/test_risk_limits.py
uv run mypy src/tiewtrade/core/risk_limits.py tests/core/test_risk_limits.py
uv run pytest tests/core/test_risk_limits.py tests/core/test_positions.py tests/core/test_manual_trading.py tests/core/test_position_parity.py tests/test_core_purity.py -o addopts= -q
uv run lint-imports
```

ผล final M1: lint/format ผ่าน; mypy 2 source files ผ่าน; pytest **76 passed in 0.74s**;
import-linter **7 kept / 0 broken** (260 files / 1740 dependencies)
รอบพัฒนาพบ lint และ strict-mypy errors จาก generated comparison operators/typing
แก้โดยใช้ comparisons ที่ชนิด Money/Quantity ประกาศไว้และ typed sort key แล้ว
ตรวจใหม่ผ่าน ไม่ข้ามกฎหรือใช้ ignore เพื่อปิด error

## Validation และงานถัดไป

M1 เป็นหลักฐานส่วน domain ของ V-01..06 เท่านั้น ไม่ปิด DB/API/monitor/rolling/
episode lifecycle ที่อยู่ในเกณฑ์เดียวกันก่อนมี integration evidence
V-07..23 ยัง Not Run/Pending ตาม validation โดยเฉพาะ V-21 workload และ V-22/23
dependencies ไม่ผ่านจาก tests นี้ Production NEW admission ยัง policy=None
และไม่เปิด Live ไม่มี commit/push; ต่อ M2 ตาม plan ที่ Approved แล้ว ไม่ต้องอนุมัติซ้ำ

Branch: `feat/f18-wallet-risk-limits`; evidence อ้าง uncommitted source ข้างต้น
เวลาตรวจ pytest วัดได้ 0.74s; static tool commands <1s ต่อคำสั่งตามผลเครื่องมือ
เวลาอ่าน/เขียน/รีวิวไม่ได้จับเวลา จึงไม่อ้างเป็นเวลาที่วัดได้


### Dependency follow-up — 2026-10-26

อ่าน F-14 integration ระหว่าง M2 พบ source sequence เป็น global ต่อ episode ไม่ใช่
per-pair จึงแก้ RiskBook ให้ทุก pair ใช้ cursor เดียวกัน และ advance cursor ของคู่ที่
ไม่มี execution โดยไม่เปลี่ยน cost/quantity/PnL ตาม F-14 VOID/other-pair slots เดิม
เพิ่ม alternating BTC/ETH regression และ reject mixed-cursor snapshot; ไม่มี spec change
ตรวจ affected risk/positions/parity/manual/purity ใหม่ **77 passed in0.78s** และ
core lint/strict mypy ผ่าน ผล76เดิมเก็บเป็นประวัติ ใช้ผล77นี้แทนสำหรับ domainฉบับล่าสุด
