# F-03 โครงฐานข้อมูล + migration + แยกข้อมูลผู้ใช้ — Plan

สถานะ: **Approved** — เจ้าของอนุมัติ 2026-09-27 (ฉบับปรับตามข้อรีวิวทั้ง 6 ประเด็น)
วันที่: 2026-09-27
ข้อกำหนด: [requirements.md](requirements.md) (Approved 2026-09-27)

---

## แนวทาง

แยกงานเป็นห้าชั้น ชั้นล่างเสร็จก่อนชั้นบนใช้ได้ และแต่ละชั้นมีเทสต์ของตัวเอง

```
1. บทบาทฐานข้อมูล        ← สร้างด้วย bootstrap (ต้องใช้ superuser ครั้งเดียว)
2. migration + โครงสร้าง  ← รันด้วยบทบาท migrator
3. กลไก RLS + append-only ← สร้างใน migration เป็นของกลางที่ตารางอื่นเรียกใช้
4. ชั้นเชื่อมต่อใน infra   ← ทุก service ใช้ร่วมกัน บังคับการระบุผู้ใช้
5. ตาราง users            ← ผู้ใช้จริงรายแรกของกลไกทั้งหมด
```

**ทำไมแยกชั้น 1 ออกจาก migration:** `CREATE ROLE` เป็นคำสั่งระดับ cluster ไม่ใช่ระดับ
ฐานข้อมูล และต้องใช้สิทธิ์ที่สูงกว่าที่ migration ควรมี ถ้าเอาไปไว้ใน migration
แปลว่าบทบาทที่รัน migration ต้องสร้างบทบาทได้ ซึ่งขัดกับ RQ-5.1
bootstrap จึงเป็นสคริปต์ SQL แยกที่รันครั้งเดียวตอนตั้งเครื่อง (ใน compose และใน CI
รันโดยผู้ใช้ superuser ของ container เท่านั้น) ส่วนบนเครื่องจริงเป็นงาน F-31

### 1. บทบาทฐานข้อมูล

| บทบาท | อยู่ใต้ RLS | สิทธิ์ | มาจาก |
|---|---|---|---|
| `tiewtrade_migrator` | ใช่ (`FORCE`) | เจ้าของตารางทั้งหมด, DDL, ปิด trigger ได้ | Q-4, RQ-5.1 |
| `tiewtrade_api` | ใช่ | `SELECT`, `INSERT` ตามตารางที่ระบุ — **อ่านคอลัมน์ secret ไม่ได้ เขียนได้** | `database.md` หัวข้อ 5 |
| `tiewtrade_engine` | ใช่ | แก้สถานะการเทรด, อ่าน secret ได้ | Q-3 |
| `tiewtrade_engine_scan` | **ไม่** (`BYPASSRLS`) | **อ่านอย่างเดียว ห้ามอ่าน secret ห้ามเขียนข้อมูลผู้ใช้** | Q-3 เงื่อนไข ก, ข |
| `tiewtrade_market_data` | ใช่ | เขียนได้เฉพาะตารางราคาและแท่งเทียน (ยังไม่มีตารางในงานนี้) | `database.md` หัวข้อ 5 |

- ทุกบทบาท **ไม่เป็น superuser** และ **ไม่เป็นเจ้าของตาราง** ยกเว้น `tiewtrade_migrator`
- `tiewtrade_engine_scan` เป็นบทบาทเดียวที่มี `BYPASSRLS` และถูกจำกัดให้อ่านอย่างเดียว
  ถ้าบทบาทนี้เขียนได้ ข้อดีของการแยกบทบาทก็หายไปทั้งหมด
- **`REVOKE ALL ON SCHEMA public FROM PUBLIC`** และ `REVOKE` สิทธิ์ตั้งต้นของ `PUBLIC`
  แล้วค่อยให้สิทธิ์ทีละอย่าง — ค่าเริ่มต้นคือปฏิเสธ (RQ-5)

### 2. migration

- Alembic หนึ่งสาย หนึ่ง head ไฟล์ตั้งชื่อ `0001_...`, `0002_...` เรียงหมายเลข (RQ-1)
- **เขียน SQL ด้วยมือทั้งหมด ไม่ใช้ autogenerate** เพราะ autogenerate ไม่รู้จัก RLS
  policy, `GRANT`, trigger และ domain — ของที่กลไกทั้งงานนี้ยืนอยู่บน
  ถ้าใช้ autogenerate จะได้ migration ที่ "ดูเหมือนครบ" แต่ทิ้งกลไกหายไปเงียบ ๆ
- ทุก migration มี `downgrade()` ที่ทำงานจริง (RQ-2) และมีเทสต์ที่ขึ้น-ลง-ขึ้นแล้วได้ผลเหมือนกัน
- รันด้วย `tiewtrade_migrator` ผ่านตัวแปรสภาพแวดล้อมแยกจากของ service (RQ-5.1)

ลำดับ migration ที่วางไว้:

| ไฟล์ | ทำอะไร |
|---|---|
| `0001_foundation` | domain ของเงิน, ฟังก์ชันกลางของ RLS, ฟังก์ชันและ trigger กลางของ append-only, view รายชื่อตาราง append-only |
| `0002_users` | ตาราง `users`, เปิด RLS + policy, สิทธิ์ของแต่ละบทบาท |

### 3. กลไก RLS

- ผู้ใช้ปัจจุบันเก็บใน **ตัวแปร session ระดับ transaction** ชื่อ `tiewtrade.current_user_id`
  ตั้งด้วย `SET LOCAL` เท่านั้น (Q-2 เงื่อนไข ก) — `SET LOCAL` หมดอายุเมื่อ transaction จบ
  จึงไม่ค้างไปถึงผู้ใช้คนถัดไปที่ได้ connection เดิมจาก pool (เงื่อนไข ข)
- ฟังก์ชันกลาง `tiewtrade_current_user_id()` อ่านค่านั้น และ **คืนค่าว่างเมื่อยังไม่ถูกตั้ง**
  ไม่ใช่โยนข้อผิดพลาด เพราะ policy ต้องใช้ค่านี้เทียบได้
- policy ของทุกตารางใช้ทั้ง `USING` (กันอ่าน) **และ `WITH CHECK`** (กันเขียนให้คนอื่น)
  เมื่อยังไม่ตั้งผู้ใช้ ผลของเงื่อนไขไม่เป็นจริง → อ่านได้ศูนย์แถว และการเขียนถูกปฏิเสธ
  (Q-2 เงื่อนไข ค)
- ทุกตารางเปิด `ENABLE ROW LEVEL SECURITY` **และ `FORCE ROW LEVEL SECURITY`**
  ข้อหลังทำให้เจ้าของตาราง (`tiewtrade_migrator`) อยู่ใต้ policy ด้วย — ไม่ใช่ข้อยกเว้นเงียบ ๆ

### 4. กลไก append-only

- ฟังก์ชัน `tiewtrade_reject_mutation()` หนึ่งตัว ใช้ร่วมกันทุกตาราง โยนข้อผิดพลาด
  พร้อมรหัสที่ระบุได้ (RQ-14)
- ฟังก์ชัน `tiewtrade_make_append_only(regclass)` เป็นตัว **เปิดกลไกทีละตาราง**
  ตามขอบเขตที่เจ้าของระบุ (RQ-7) — ตารางทั่วไปไม่ถูกแตะ ทำสองอย่างในตัวเดียว:
  1. `REVOKE UPDATE, DELETE, TRUNCATE` จากทุกบทบาทที่ใช้ตอนทำงานปกติ
  2. ผูก trigger `BEFORE UPDATE OR DELETE ... FOR EACH ROW` และ
     `BEFORE TRUNCATE ... FOR EACH STATEMENT`
- **view `tiewtrade_append_only_tables`** บอกว่าเปิดกลไกกับตารางไหนไว้ โดย
  **อ่านจาก `pg_trigger` จริง ไม่ใช่ตารางทะเบียนที่เขียนเอง** — ทะเบียนที่เขียนเองจะ
  ไม่ตรงกับความจริงเมื่อมีคนลืมอัปเดต
- งานนี้ **ยังไม่เปิดกลไกนี้กับตารางจริง** — `users` แก้ได้ตามปกติ (F-05 ต้องแก้)
  ผู้ใช้จริงรายแรกคือ audit log ใน F-04 (Q-1) เทสต์ของงานนี้สร้างตารางของตัวเอง
  ด้วยบทบาท `tiewtrade_migrator` แล้วเปิดกลไกกับตารางนั้น

### 5. ความละเอียดของเงิน

- domain ชื่อ `tiewtrade_money_amount` ตั้งบน **`NUMERIC` ที่ไม่บังคับ scale**
  พร้อม `CHECK` สามข้อ: ต้องไม่ใช่ `NaN`/อนันต์, ทศนิยมจริงไม่เกิน `STORED_SCALE` (ไม่นับศูนย์ท้าย),
  ค่าสัมบูรณ์น้อยกว่า `MAX_ABS`
- **เหตุผลที่ไม่ใช้ `NUMERIC(38,18)` ตรง ๆ:** `NUMERIC(p,s)` **ปัดค่าที่ทศนิยมเกินให้เอง
  เงียบ ๆ** ค่า `0.0000000000000000001` จะกลายเป็น `0` ก่อนที่ `CHECK` จะได้เห็นค่าจริง
  ซึ่งเป็นการฝากการปัดให้ฐานข้อมูล — F-02 RQ-9 ห้ามไว้ การใช้ `NUMERIC` เปล่า
  ทำให้ค่าดิบถึง `CHECK` ครบ แล้ว **ฐานข้อมูลปฏิเสธเองได้แม้โค้ดพลาด** (RQ-9.1)
- **ค่ากลางยังมาจาก `tiewtrade.core.money.limits` ที่เดียว** แต่ใช้ตอนจัดทำ revision:
  อ่าน `STORED_SCALE` และ `MAX_ABS` เพื่อสร้าง SQL แล้วเก็บ SQL ผลลัพธ์ไว้ใน
  `0001_foundation.py` เป็น snapshot ของ schema รุ่นนั้น **ไม่ import โค้ด runtime ตอนรัน migration**
  snapshot เป็นประวัติโครงสร้าง ไม่ใช่แหล่งกำหนดกฎเงินอีกแห่ง และห้ามแก้ย้อนหลัง
  เมื่อค่ากลางเปลี่ยน ต้องมี migration ใหม่; เทสต์ตรวจ domain ที่ head กับ `Money`
  ทั้งสองทิศ และตรวจว่า replay revision เก่าไม่เปลี่ยนเมื่อค่าคงที่ runtime เปลี่ยน
  ใช้ `min_scale()` ตรวจทศนิยมจริงให้ตรงกับ `real_decimal_places()` ของ F-02
  เช่น `1.0000000000000000000` ต้องผ่าน แต่ `0.0000000000000000001` ต้องไม่ผ่าน
- **ไม่สร้างกฎการปัดใหม่** (RQ-9.1) ชั้น `infra` ไม่ปัดอะไรเลย — ค่าที่ปัดไม่ได้ต้องถูกปฏิเสธ
  การปัดเป็นการตัดสินใจของผู้เรียกผ่าน `RoundingDirection` ของ F-02 ก่อนส่งมาถึงที่นี่
- **หน่วยเก็บคู่กับจำนวนเสมอ** domain `tiewtrade_unit_code` เป็น `TEXT` ที่ห้ามว่าง
  โดยไม่เพิ่มเพดานความยาว — **ไม่เขียนกฎรูปแบบหน่วยซ้ำใน SQL** เพราะกฎจริงอยู่ที่
  `normalise_unit` ของ F-02 ที่เดียว
- การเขียนลงแล้วอ่านกลับรักษา **ค่าตัวเลขและหน่วยมาตรฐาน** ไม่รักษารูปแบบข้อความเดิม
  ใช้ `as_parts` / `from_parts` ตาม F-02 ซึ่งตัดศูนย์ท้าย: `1.2300` กับ `1.23` เป็นค่าเดียวกัน

### 6. ตาราง `users`

| คอลัมน์ | ชนิด | กฎ |
|---|---|---|
| `id` | `UUID` | primary key, **เป็นคอลัมน์เจ้าของของตัวเอง** (Q-1.1) |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT now()` |

- รหัสสร้างที่ชั้น `infra` ด้วย `uuid4` **ไม่ใช่ที่ `core`** เพราะ `core` ห้ามใช้ค่าสุ่ม
- **เวลาสร้างแก้ไม่ได้ (RQ-10.1)** บังคับด้วยสิทธิ์ระดับคอลัมน์:
  บทบาทที่ใช้ตอนทำงานปกติได้ `INSERT (id)` เท่านั้น ไม่ได้สิทธิ์ `INSERT` คอลัมน์
  `created_at` และไม่ได้สิทธิ์ `UPDATE` คอลัมน์นั้น **ส่งค่าเวลามาเองจึงถูกปฏิเสธ
  ไม่ใช่ถูกเมิน** — ค่าปริยายอย่างเดียวกันแค่กรณีไม่ส่งค่ามา
- ใช้ `now()` (เวลาเริ่ม transaction) เพื่อให้แถวที่เกิดใน transaction เดียวกันมีเวลาเดียวกัน
  และลำดับเหตุการณ์เทียบกันได้ข้าม process
- ยังไม่มีอีเมล รหัสผ่าน TOTP — เป็นงาน F-05 ซึ่งเพิ่มคอลัมน์ตาม RQ-19

### 7. ชั้นเชื่อมต่อใน `tiewtrade.infra`

- SQLAlchemy 2 async + asyncpg สร้าง engine จาก URL ใน environment variable
  **หนึ่ง URL ต่อหนึ่งบทบาท** ไม่ใช่ URL เดียวแล้วสลับบทบาททีหลัง
- **ทางเข้าเดียวสำหรับงานของผู้ใช้:** ตัวช่วยแบบ context manager ที่เปิด transaction
  ตั้ง `SET LOCAL` ให้ผู้ใช้ที่ระบุ แล้วคืน `UserSession` ให้ใช้
  **ไม่มี API ที่ให้ connection ของผู้ใช้โดยไม่ระบุตัวผู้ใช้** — ลืมระบุไม่ได้เพราะไม่มีทางลืม
- งานกวาดข้ามผู้ใช้ใช้ทางเข้าแยกที่ผูกกับ `tiewtrade_engine_scan` และ **ชื่อฟังก์ชัน
  บอกชัดว่าข้าม RLS** เพื่อให้เห็นตอนรีวิวว่าโค้ดตรงไหนใช้ทางนั้น (Q-3 เงื่อนไข ค)
- `session.py` คืน `UserSession` สำหรับงานรายผู้ใช้ และ `ScanSession` สำหรับงานกวาด
  เป็นคนละชนิด ไม่สืบทอดกัน และไม่เปิด raw connection เป็น public API
  ก่อนคืน `UserSession` ตรวจ `current_user` ของ connection จริงว่าตรงกับบทบาท
  `tiewtrade_api` หรือ `tiewtrade_engine` ที่ร้องขอ และไม่เป็น superuser/ไม่มี `BYPASSRLS`
  หากตั้ง URL ผิดจนต่อด้วย scan ต้องโยน `DatabaseRoleError` ก่อนอ่านข้อมูลผู้ใช้
  จุดเข้า repository รายผู้ใช้รับเฉพาะ `UserSession` และใช้ตัวตรวจ runtime กลาง
  ปฏิเสธ `ScanSession`/raw connection ก่อน query ทั้งเส้นทางอ่านและเขียน
  เทสต์ใช้ตารางเงินจำลองกับตัวตรวจเดียวกัน ไม่สร้างกระเป๋าหรือกลยุทธ์จริงใน F-03
  `ScanSession` ให้สิทธิ์เฉพาะข้อมูลจัดคิวที่จำเป็น; ไม่มีสิทธิ์อ่านจำนวนเงินหรือ secret
- **นโยบาย log ของ PostgreSQL ตั้งที่ระดับฐานข้อมูลใน bootstrap** (เพิ่มหลังรีวิว 2026-09-27)
  `hide_parameters` ของ SQLAlchemy กันได้แค่ฝั่งแอป ฝั่ง server มี log ของตัวเองที่เขียน
  คำสั่งและรายการค่าที่ bind ลงไปได้ — พิสูจน์แล้วว่าค่าจำลองโผล่ใน log จริงเมื่อไม่ตั้งนโยบาย
  จึงตั้ง `log_statement=none`, `log_min_duration_statement=-1`, `log_parameter_max_length=0`,
  `log_parameter_max_length_on_error=0`, `log_error_verbosity=terse`
  ตั้งที่ระดับฐานข้อมูลเพราะ service container ของ CI ส่ง command ให้ PostgreSQL ไม่ได้
  **ข้อจำกัดที่ยังเหลือ:** ข้อความข้อผิดพลาดของ PostgreSQL เองอ้างค่าที่ผิดได้
  ฉะนั้นค่าที่ผิดต้องถูกปฏิเสธก่อนส่งไปฐานข้อมูล ซึ่งเป็นกฎเดียวกับ RQ-9.1
- **ข้อผิดพลาดตอนขอ connection ก็ต้องแปลง** รวม `OSError` เช่น `ConnectionRefusedError`
  ที่ driver โยนตรง ๆ (เพิ่มหลังรีวิว 2026-09-27) ไม่เช่นนั้นผู้เรียกที่เตรียมรับ
  "ฐานข้อมูลล่ม" รับไม่ได้ ส่วนข้อผิดพลาดในตัวงานของผู้เรียกไม่ถูกแปลง
- ข้อผิดพลาดที่คาดไว้ได้แปลงเป็นชนิดข้อมูลของเรา ไม่ปล่อยข้อความดิบของฐานข้อมูลออกไป
  และ **ห้ามมี URL, รหัสผ่าน หรือค่าใน log** (RQ-14, RQ-15)
  ปิด SQL echo และ parameter logging; ใช้รหัสข้อผิดพลาดที่เลือกไว้แทนข้อความ/DETAIL
  ของ driver และไม่ส่งต่อ exception chain ที่มีข้อมูลดิบ ตรวจด้วย secret จำลองทั้ง
  connection failure และ query/constraint failure รวมข้อความ traceback และ log
- `core` ไม่ถูกแตะเลย ด่านความบริสุทธิ์ยังเขียว (RQ-11)

### 8. เวอร์ชัน PostgreSQL ร่วมกันระหว่าง CI และ Compose

- เก็บ image tag ที่เลือกสำหรับ PostgreSQL 16+ ไว้ที่ `config/postgres.env` เพียงแห่งเดียว
  เริ่มด้วย `POSTGRES_VERSION=16` (ตรึง major version ตามขอบเขต PostgreSQL 16+; ไฟล์นี้ไม่มี secret)
- `compose.yaml` ใช้ `postgres:${POSTGRES_VERSION:?load config/postgres.env}`
  เรียกจาก root ด้วย `env -u POSTGRES_VERSION docker compose --env-file config/postgres.env ...`
  การลบค่าจาก shell ก่อนอ่านไฟล์กันค่าภายนอกทับเวอร์ชันกลางโดยไม่ตั้งใจ
- CI เพิ่ม job `config`: checkout แล้วอ่านบรรทัด `POSTGRES_VERSION` เป็น step output
  และ job output ชื่อ `postgres_version`; job `backend` ประกาศ `needs: config` แล้วใช้
  `image: postgres:${{ needs.config.outputs.postgres_version }}` ใน service PostgreSQL
  ไม่ใช้ workflow `env` อ้าง service image ส่วน job `docker` ใช้คำสั่ง Compose เดียวกับในเครื่อง
- V-41 ตรวจทั้ง image ที่ Compose resolve จริงและการต่อ job output ของ CI
  รวมกรณี shell ตั้งเวอร์ชันผิดและไฟล์กลางหาย เพื่อไม่ให้ใช้ fallback เงียบ ๆ

อ้างอิง: [GitHub job outputs](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/pass-job-outputs),
[Compose interpolation](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/)

---

## ของเดิมที่จะใช้ซ้ำ

ค้นแล้วก่อนเขียนใหม่ (`AGENTS.md` หัวข้อ "ใช้ของเดิมซ้ำ")

| ของเดิม | path | ใช้ทำอะไร |
|---|---|---|
| `Money`, `Quantity` | `backend/src/tiewtrade/core/money/types.py` | ชนิดข้อมูลที่เข้าออกฐานข้อมูล — ไม่สร้างชนิดใหม่ |
| `STORED_SCALE`, `MAX_ABS`, `STORED_PRECISION` | `backend/src/tiewtrade/core/money/limits.py` | แหล่งค่าตอนสร้าง SQL snapshot ของ revision; ตรวจ domain ล่าสุดตรงกับค่ากลาง |
| `as_parts` / `from_parts` | `backend/src/tiewtrade/core/money/types.py` | แปลงค่าเข้าออกโดยไม่ผ่าน `float` |
| `MoneyError` และลูกหลาน | `backend/src/tiewtrade/core/money/errors.py` | ชนิดข้อผิดพลาดของค่าเงิน — ชั้น `infra` ไม่สร้างชุดใหม่ |
| แบบแผนด่านที่พิสูจน์ตัวเองได้ | `backend/tests/gates/test_gates.py` | เพิ่มกรณี "ต้องแดง" ของงานนี้ตามแบบเดิม |
| ตัวตรวจความบริสุทธิ์ | `backend/tests/purity.py`, `backend/tests/test_core_purity.py` | ยืนยันว่า `core` ยังไม่แตะฐานข้อมูล |
| แนวทางตรึงเวอร์ชันของ F-01 | `.github/workflows/ci.yml` | คงแนวทางแหล่งค่าเดียว; PostgreSQL ใช้ `config/postgres.env` และ job output ตามข้อ 8 |
| กฎ import-linter | `backend/pyproject.toml` | เพิ่ม `sqlalchemy`, `asyncpg`, `alembic` เข้ารายการที่ `core` ห้ามพึ่ง |

---

## สิ่งที่จะแก้

| ไฟล์ | เปลี่ยนอะไร |
|---|---|
| `backend/pyproject.toml` | เพิ่ม `sqlalchemy[asyncio]`, `asyncpg`, `alembic`; dev เพิ่ม `pytest-asyncio`; เพิ่มไลบรารีใหม่เข้ารายการที่ `core` ห้ามพึ่ง |
| `backend/alembic.ini` (ใหม่) | ตั้งค่า Alembic ให้อ่าน URL จาก environment ของ `migrator` |
| `backend/migrations/env.py` (ใหม่) | เชื่อม Alembic กับ engine, ไม่ใช้ autogenerate |
| `backend/migrations/versions/0001_foundation.py` (ใหม่) | domain เงินและหน่วย, ฟังก์ชัน RLS, กลไก append-only, view รายชื่อตาราง |
| `backend/migrations/versions/0002_users.py` (ใหม่) | ตาราง `users`, RLS + policy, สิทธิ์รายคอลัมน์ |
| `backend/db/bootstrap/00-roles.sql` (ใหม่) | สร้าง 5 บทบาท, `REVOKE` สิทธิ์ตั้งต้นของ `PUBLIC` |
| `backend/src/tiewtrade/infra/db/__init__.py` (ใหม่) | ของสาธารณะของชั้นนี้ |
| `backend/src/tiewtrade/infra/db/engine.py` (ใหม่) | สร้าง engine ต่อบทบาท อ่าน URL จาก environment |
| `backend/src/tiewtrade/infra/db/session.py` (ใหม่) | `UserSession`, `ScanSession`, ตัวตรวจ session กลาง และตรวจบทบาทจริงก่อน `SET LOCAL` |
| `backend/src/tiewtrade/infra/db/money.py` (ใหม่) | แปลง `Money`/`Quantity` เข้าออกคอลัมน์ ไม่ปัด ไม่ใช้ `float` |
| `backend/src/tiewtrade/infra/db/errors.py` (ใหม่) | ชนิดข้อผิดพลาดของชั้นนี้ |
| `backend/src/tiewtrade/infra/users.py` (ใหม่) | เพิ่มและอ่านแถวผู้ใช้ — ผู้ใช้จริงรายแรกของกลไก |
| `backend/tests/infra/db/*` (ใหม่) | เทสต์ทั้งหมดของงานนี้ ตาม `validation.md` |
| `backend/tests/gates/test_gates.py` | เพิ่มกรณีที่ต้องแดง: ลืมระบุผู้ใช้, ใช้บทบาทข้าม RLS ในเส้นทางที่แตะข้อมูลผู้ใช้ |
| `compose.yaml` | เพิ่มบริการ `postgres` (ตรึงเวอร์ชัน) + `migrate` แบบรันครั้งเดียว, `api` รอทั้งสองตัว |
| `config/postgres.env` (ใหม่) | แหล่ง image tag PostgreSQL เดียวสำหรับ CI และ Compose ไม่มี secret |
| `.github/workflows/ci.yml` | เพิ่ม job `config` ส่งเวอร์ชันผ่าน output ให้ service `postgres` ในงานหลังบ้าน; bootstrap + migrate ก่อน `pytest`; job `docker` โหลดไฟล์กลาง |
| `README.md` | วิธีตั้งฐานข้อมูลบนเครื่องนักพัฒนา |

**ไม่แตะ** `backend/src/tiewtrade/core/**` และโค้ดของ `services/**` ที่ไม่เกี่ยวกับงานนี้
(`AGENTS.md` กฎข้อ 10)

---

## ผลต่อฐานข้อมูล

- migration `0001` และ `0002` ตามตารางข้างบน ทั้งสองไฟล์ย้อนกลับได้
- ยังไม่มีข้อมูลจริงในระบบ จึงไม่มีขั้นย้ายข้อมูล (RQ-19 ไม่มีผลกับงานนี้
  แต่มีผลกับ F-05 ที่จะเพิ่มคอลัมน์ให้ `users`)
- ไม่มีตารางที่โตเร็วในงานนี้ จึงยังไม่มีการแบ่งพาร์ทิชันและยังไม่ต้องกำหนดอายุข้อมูล
- **เอกสาร `specs/standards/database.md` แก้แล้ว 2026-09-27** ตามคำตัดสิน Q-1.1, Q-3, Q-4

---

## ความเสี่ยง

| อะไรอาจพัง | จะรู้ได้อย่างไร |
|---|---|
| ลืม `SET LOCAL` ในเส้นทางใหม่ที่เขียนภายหลัง | ไม่มี API ที่ให้ connection ของผู้ใช้โดยไม่ระบุตัวผู้ใช้ + เทสต์ที่พิสูจน์ว่าไม่ระบุแล้วอ่านศูนย์แถวและเขียนไม่ได้ |
| ใช้ `SET` แทน `SET LOCAL` แล้วค่าค้างข้ามผู้ใช้ผ่าน pool | เทสต์ที่ใช้ connection เดิมต่อเนื่องสองผู้ใช้ และตรวจว่าคนที่สองไม่เห็นข้อมูลคนแรก |
| มีคนเผลอใช้บทบาทข้าม RLS ในเส้นทางที่แตะเงิน | ตรวจบทบาทจริง + แยกชนิด session + ตัวตรวจ runtime; เทสต์ใช้ scan เข้าเส้นทางอ่าน/เขียนเงินแล้วถูกปฏิเสธก่อน query |
| `GRANT` ผิดในอนาคตทำให้แก้ของเก่าได้ | trigger เป็นชั้นที่สอง และเทสต์ตรวจสองชั้น × สามคำสั่งแยกกัน |
| ฐานข้อมูลปัดเศษเงินเงียบ ๆ | `NUMERIC` ไม่บังคับ scale + `CHECK` และเทสต์เทียบขอบเขตกับ `Money` ทั้งสองทิศ |
| เวอร์ชัน PostgreSQL ใน CI ต่างจากเครื่องนักพัฒนา | ไฟล์ `config/postgres.env` เดียว; CI ใช้ job output และ Compose ใช้ `--env-file` ตามข้อ 8 |
| migration ย้อนกลับไม่ได้จริงแต่ไม่มีใครรู้ | เทสต์ที่รัน upgrade → downgrade → upgrade แล้วเทียบผล |
| bootstrap ต้องใช้ superuser ทำให้คนเอาไปใช้บนเครื่องจริงผิด ๆ | สคริปต์แยกโฟลเดอร์ เขียนกำกับว่าใช้ตอนตั้งเครื่องเท่านั้น และเรื่องเครื่องจริงเป็น F-31 |

---

## การเปลี่ยนแปลงหลังอนุมัติ

ถ้าลงมือแล้วพบว่าทางที่อนุมัติไว้ผิด **ให้หยุดและขออนุมัติการเปลี่ยนก่อนแก้โค้ด**
ห้ามเขียนโค้ดให้ต่างจาก plan นี้แล้วมาแก้ plan ตามหลัง (บทเรียนจาก F-02)
