# F-18 M2 — persistence/API checkpoint — 2026-10-26

สถานะ: In Progress — ยังไม่ปิด M2/M3 และยังไม่ Ready for Code Review ของ feature

## ทำแล้ว

- migrations 0043/0044: scoped setting/authorization/inbox/result/dispatch/events/
  baseline/pair/evaluation tables, RLS/roles/append-only, restricted intake function,
  typed audit shape/failure allowlist และ token bucket ของ risk แยกจาก order/cancel
- durable requests/authorization-only/by-key lookup และ owner-fair fenced claims
- amount-setting worker ใช้ expected revision ตรวจทั้ง intake/execution, เก็บ result/
  applied event/audit/terminal atomic และไม่ล้าง latch จากการเปลี่ยน limit
- HTTP settings/increase/reset/lookup + route classifications; TOTP consume กับ
  authorization receipt อยู่ AUTH transaction เดียวกัน; exact replay ต้อง current
  session/CSRF และ matching identity/payload ไม่เป็นสิทธิ์ทำ action ใหม่
- API และ engine production order policy ยัง None ไม่เปิด Paper NEW หรือ Live

## Environment และหลักฐาน

สร้าง PostgreSQL16 container `tiewtrade-f18-postgres` แยกจาก F-16/F-38 databases
พอร์ต localhost55458, bootstrap เดิมของ repo, runtime roles จริง ไม่ใช้ superuser
สำหรับ application tests; dev DB container 2CPU/2GiB เป็น correctness environment
ไม่อ้างเป็น release workload environment ของ V-21
temporary wrapper `/tmp/tiewtrade-f18-run.py` ตั้ง role URLs ไป DB นี้สำหรับแต่ละคำสั่ง
ไม่มี network order/venue credential path และยังไม่รัน workload/diagnostic ซ้อน

ผลตรวจ:

| ตรวจ | ผล |
|---|---|
| Alembic fresh upgrade ถึง0042 แล้ว0043; downgrade0042→upgrade0043 ก่อนใส่ risk history | Passed |
| 0044 additive upgrade บน DB ที่มี risk history แล้ว | Passed |
| `tests/infra/risk_limits/test_requests.py` | **11 passed in2.77s** — concurrency/replay/rollback/RLS/auth-only/forgery/permission/scope |
| `tests/api/test_risk_limit_routes.py` | **9 passed in4.93s** — HTTP strict input, session/CSRF, TOTP exemption, AUTH→inbox crash recovery, payload conflict, concurrent authentication |
| `tests/infra/risk_limits/test_worker.py` | **5 passed in1.46s** — atomic apply/audit rollback, claim takeover, stale revision, latch preservation/unavailable reset |
| affected audit regression: event_shape/manual_order_events/transaction/isolation | **74 passed in3.33s** |
| targeted lint/format/mypy | ผ่านสำหรับไฟล์ที่ตรวจตามผลเครื่องมือ; ต้องตรวจ affected changes หลัง checkpoint นี้และ candidate gates อีกครั้ง |

คำสั่ง tests ใช้ `python3 /tmp/tiewtrade-f18-run.py uv run pytest <paths> -o addopts= -q`
จาก backend; static checks ใช้ `uv run ruff`/`uv run mypy` พร้อม source paths ที่เกี่ยวข้อง

Development failures ที่แก้แล้ว: migration parameterชื่อauthorizationชน SQL keyword
เปลี่ยนเป็นrequest_authorization; strict UUID ของ domain ต้อง normalize asyncpg UUID
ที่ boundary ของ fixture เช่นเดียวกับ route/DB decoders; mypy invocation ที่ชี้ tests
อย่างเดียวเห็น editable package เป็น untyped จึงระบุ affected source paths ด้วย
ไม่มีการ ignore/skip หรือลด assertions เพื่อให้ผ่าน

## งานที่ยังค้าง

- M3 publication journal/fence/financial boundaries/monitor และ authoritative reset
  ยังไม่ implement ส่วน reset worker จึง reject RISK_SOURCE_UNAVAILABLE และ setting
  evaluations เป็น unavailable/replay_pending ไม่ให้ความหมาย READY โดยไม่มี proof
- ยังต้องเชื่อม evaluation เมื่อเปลี่ยนเพดาน/หลัง fill/correction และ stop consumer,
  effects pagination และ source/price freshness ใน read/order gates
- F-06 regression หลังเพิ่ม middleware branch, full candidate gates/generated contracts,
  M4 UI/browser และ M5 review ยังไม่ผ่านจาก checkpointนี้
- V-21 Pending Full Validation; V-22/23 Pending Dependency ตาม scope เดิม
  ไม่เปิด production จาก targeted tests และไม่เรียก feature Completed
- ไม่มี commit/push; เวลาข้างต้นเฉพาะ test elapsed ที่วัดได้ ไม่มีเวลารวมอ่าน/เขียน/รีวิวที่จับจริง


### Follow-up — F-06 and sequence integration

F-06 + route policy/classification combined run มี44 testsผ่าน ก่อน inventory ล้มเพราะ
ยังไม่ใส่6 risk mutation routes; เพิ่มรายการ explicit user-action renewal และ2 increase
reverification routes ใน tests โดยคง GETpoll non-renewing และ resetไม่เป็นrisk-reducing
รันซ้ำเฉพาะ route-policy/classification ที่ได้รับผลกระทบ ผลอยู่ checkpoint ถัดไป
M1 follow-up เปลี่ยนเฉพาะ financial source cursor; [หลักฐาน](m1-core.md)77testsผ่านแล้ว
