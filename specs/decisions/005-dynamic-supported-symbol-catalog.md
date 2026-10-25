# ADR-005 — Dynamic supported-symbol catalog

สถานะ: **Approved** — เจ้าของอนุมัติพร้อมแผน F-37 วันที่ 2026-10-24
วันที่: 2026-10-24

## เหตุผล

ระบบเดิมใช้ allowlist BTC/USDT และ ETH/USDT ซ้ำใน Python, TypeScript และ SQL
จึงไม่มีแหล่งความจริงที่เปลี่ยนได้อย่างปลอดภัย การเพิ่มหรือถอนคู่กระทบทั้ง
การรับออเดอร์, Paper matching, market data, indicator, หน้าเว็บ และประวัติที่ห้ามลบ
จึงต้องมีการจัดลำดับ, audit และ rolling-deployment gate ที่บังคับจริงที่ฐานข้อมูล

## คำตัดสิน

### 1. Source of truth

PostgreSQL เป็น source of truth เดียว โดยมี:

- immutable symbol registry เก็บ identity ของคู่ที่เคยรองรับ ห้ามลบเมื่อถอนคู่
- current pair fence/projection หนึ่งแถวต่อคู่ เปลี่ยนได้เฉพาะ stored function
- append-only catalog events ที่มี global revision เพิ่มขึ้นเท่านั้น
- durable outbox/effects, readiness proofs, constraints snapshots และ protocol heartbeats

projection และ event ล่าสุดต้องตรงกันด้วย database constraint/trigger และเปลี่ยนใน
transaction เดียว Redis ใช้ได้เฉพาะเป็น invalidation signal; process ต้องกู้ state จาก
PostgreSQL ได้เสมอ

`core` ไม่อ่านฐานข้อมูล ผู้เรียกส่ง immutable `CatalogSnapshot(revision, active_pairs)` เข้าตรรกะโดเมน
และ engine ตรวจ authoritative snapshot ซ้ำใน transaction ก่อน admission/dispatch/match

### 2. Shared pair fence และ lock order

- catalog mutation: global catalog-revision advisory lock → pair fence `FOR UPDATE` → event,
  projection, outbox และ audit → commit
- authoritative Paper path: wallet advisory lock เดิม → pair fence `FOR KEY SHARE` และถือจน
  commit ทั้ง admission และการ match active LIMIT ทุกรอบ
- removal ไม่จับ wallet/user lock; effect consumer ไม่ถือ pair fence ขณะจับ wallet lock
- ห้ามจับ pair fence สองคู่พร้อมกัน; multi-pair mutation จัดลำดับด้วย global revision lock

ลำดับนี้ทำให้ Paper opening admission/fill ที่ commit หลัง `REMOVED` commit เกิดไม่ได้
และไม่สร้างวงจร pair→wallet สวนกับ wallet→pair ส่วน Live order ที่ venue รับแล้ว
อาจ fill ระหว่าง cancel ได้และต้อง reconcile ตามความจริงจากตลาด

### 3. Platform audit ownership

- human catalog command: `owner_user_id=actor_id` ของ Admin/Owner ผู้ขอ และ
  `actor_kind=PLATFORM`
- automatic transition: audit ยัง owned โดย requester เดิม, `actor_kind=SYSTEM`,
  `actor_id=NULL`
- first-owner bootstrap: audit owned โดย owner ใหม่, `actor_kind=SYSTEM`

ทุกกรณีเก็บเฉพาะ typed reason/detail จาก allowlist ไม่รับ free text เข้า immutable audit
catalog coordinator อยู่ใน engine; market-data และ indicator-builder เขียนได้เฉพาะ public readiness proof
และไม่ได้สิทธิ์ audit

### 4. Bootstrap role

`tiewtrade_platform_bootstrap` เป็น deployment-only login role ที่ไม่เป็น superuser,
table owner หรือ `BYPASSRLS` และไม่มี table privilege โดยตรง credential แบบ offline
ใช้เฉพาะตอน deploy เพือเรียก `SECURITY DEFINER` bootstrap function
เพียงฟังก์ชันเดียว ฟังก์ชันตรวจ user UUID, TOTP-enabled state และว่ายังไม่มี
Platform Owner ก่อนเขียน membership และ audit ใน transaction เดียว เมื่อมี owner แล้วจะเรียกซ้ำไม่ได้
และ credential นี้ห้าม mount เข้า API/engine/worker

### 5. Rolling protocol gate

migration เริ่มด้วย mutation disabled และ seed BTC/ETH สำหรับ compatibility reader
process รุ่นใหม่ทุกชนิดเขียน heartbeat ที่มี protocol version, deployment generation และ lease
เจ้าของเปิด mutation ได้เมื่อ API, engine, market-data และ indicator-builder มี heartbeat
รุ่น/generation ที่กำหนดครบและ lease รุ่นเก่าหมดแล้ว stored mutation function ตรวจ gate ซ้ำทุกครั้ง

ก่อน enable ยัง rollback ไปใช้ static compatibility reader ได้ หลัง enable ห้าม deploy binary
ที่ไม่รองรับ protocol; ต้อง roll forward หรือ disable mutation และ drain effects ก่อน

## ผลตามมา

- Python/TypeScript constants ไม่เป็น authority หลัง protocol gate เปิด
- pair removal ปิดการเปิดความเสี่ยงใหม่ก่อ แต่เก็บ maintenance data จนไม่มี order/exposure
- historical market/trading data ยังอ้าง symbol registry ได้และไม่ถูกลบตอน removal
- การเพิ่ม service role หรือเส้นทางที่ข้าม dependency boundary ต้องผ่าน import/privilege gates เดิม

## ขอบเขตการนำไปใช้

รายละเอียด state machine, API, UI, cleanup effects และหลักฐานตรวจรับยึดตาม
F-37 requirements/plan/validation ที่อนุมัติ 2026-10-24 ADR นี้ไม่ขยายไปถึงการเพิ่ม
Admin/Owner รายถัดไป, Live execution หรือการลบประวัติ
