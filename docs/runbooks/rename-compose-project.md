# Runbook: ย้าย local infrastructure หลังเปลี่ยนชื่อ Compose project เป็น `tiewtrade`

สถานะ: Active — ใช้กับเครื่อง developer เท่านั้น (`deploy/docker-compose.yml`, ADR-0008 §11.1)
ปิด finding: [REV-01](../reviews/backend-structure-review.md)

Runbook นี้ใช้เมื่อ **เคยรัน Compose project ชื่อ `fasttrade` บนเครื่องมาแล้ว** ถ้าเพิ่งเริ่มใหม่
ให้ข้ามไปที่ [§1 Fresh installation](#1-fresh-installation) แล้วจบ

> **ห้ามทำในทุกขั้นตอนของ runbook นี้**
> - ห้ามใช้ `docker compose down -v`, `docker volume rm` หรือ `docker volume prune`
>   จนกว่าจะ verify ข้อมูลใหม่ครบและตัดสินใจทิ้ง volume เดิมอย่างตั้งใจ
> - ห้าม overwrite `deploy/.env` ที่มีอยู่ — ให้อ่านค่าที่ใช้อยู่จริงก่อนเสมอ
> - `deploy/.env` ถูก git-ignore จึงไม่มีใน repository; ค่าที่ใช้อยู่มีเฉพาะบนเครื่องของคุณ

---

## 0. อะไรเปลี่ยนไปบ้าง

การเปลี่ยน `name:` ใน `deploy/docker-compose.yml` เปลี่ยน identity ของ Compose project
ซึ่งเป็น prefix ของ resource ที่ Compose สร้าง เพราะ `postgres-data` ไม่ได้ตั้ง `external`/`name`
ตายตัว ค่า default ของ `POSTGRES_DB` / `POSTGRES_USER` ก็เปลี่ยนไปพร้อมกัน

| สิ่งที่เปลี่ยน | ค่าเดิม | ค่าใหม่ | ผลเมื่อขึ้น project ใหม่ |
|---|---|---|---|
| Compose project name | `fasttrade` | `tiewtrade` | เป็นคนละ project; ของเดิมไม่ถูกแตะ |
| Postgres volume | `fasttrade_postgres-data` | `tiewtrade_postgres-data` | **volume ใหม่ว่างเปล่า** — Postgres จะ initdb ใหม่ |
| Docker network | `fasttrade_default` | `tiewtrade_default` | network ใหม่ |
| `POSTGRES_DB` default | `fasttrade` | `tiewtrade` | ใช้เฉพาะตอน initdb ครั้งแรก |
| `POSTGRES_USER` default | `fasttrade` | `tiewtrade` | ใช้เฉพาะตอน initdb ครั้งแรก |
| Redis | ไม่มี volume (`--appendonly no`) | เหมือนเดิม | **ไม่มีข้อมูลต้องย้าย** |

ประเด็นสำคัญ:

- **ข้อมูลเดิมไม่ได้หาย** ยังอยู่ใน volume `fasttrade_postgres-data` แต่ project ใหม่จะไม่เห็น
- ถ้า stack เดิมยังรันอยู่ stack ใหม่จะ **ชน published ports** (5432/6379) และขึ้นไม่ได้
- การแก้ `POSTGRES_DB` / `POSTGRES_USER` ใน `.env` **ไม่ได้ rename** database/role ที่ initdb ไปแล้ว
  ตัวแปรสองตัวนี้ถูกใช้ครั้งเดียวตอนสร้าง data directory เท่านั้น การ rename ต้องทำด้วย SQL (§3)

ตรวจค่าที่ resolve ได้จริงบนเครื่องคุณ โดยไม่ต้องแตะ container (อ่านอย่างเดียว):

```sh
cd deploy
docker compose config --format json \
  | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['name']);print({k:v.get('name') for k,v in d.get('volumes',{}).items()})"
```

---

## 1. Fresh installation

ยังไม่เคยรัน Compose project ของ repo นี้บนเครื่อง — ไม่ต้องย้ายอะไร

```sh
cd deploy
cp .env.example .env         # ตั้ง POSTGRES_PASSWORD; เปลี่ยน port ถ้า 5432/6379 ถูกใช้อยู่
docker compose up -d --wait
```

ยืนยันว่าขึ้นแล้ว:

```sh
docker compose ps
docker compose exec -T postgres psql -U tiewtrade -d tiewtrade -c 'select 1'
```

> `POSTGRES_USER` / `POSTGRES_DB` อยู่ใน `deploy/.env` ซึ่ง Compose อ่านเอง แต่ **ไม่ได้ export
> เข้า shell ของคุณ** จึงต้องพิมพ์ชื่อจริงในคำสั่ง `psql` (หรือ `set -a; . ./.env; set +a` ก่อน)
>
> อย่าใช้ `pg_isready` เป็นตัวยืนยันว่า database/user ถูกต้อง — มันตอบ `accepting connections`
> แม้ `-U`/`-d` จะเป็นชื่อที่ไม่มีอยู่จริง (ทดสอบแล้ว §4) ใช้ `psql` เป็นตัวตรวจจริง

จบที่นี่ ส่วนที่เหลือของ runbook ไม่เกี่ยวกับคุณ

---

## 2. Existing installation — เลือกแนวทาง

ตรวจก่อนว่าเข้าข่ายหรือไม่ (อ่านอย่างเดียว ไม่เปลี่ยน state):

```sh
docker compose ls -a                                  # มี project ชื่อ fasttrade อยู่ไหม
docker volume ls | grep -E 'fasttrade|tiewtrade'      # volume เดิม/ใหม่
cat deploy/.env                                        # ค่าที่ใช้อยู่จริง — อ่าน ห้ามเขียนทับ
```

ถ้าไม่เจอ project `fasttrade` และไม่เจอ volume `fasttrade_postgres-data` → คุณคือกรณี §1

| แนวทาง | เหมาะเมื่อ | ข้อมูล | ความเสี่ยง |
|---|---|---|---|
| **A — คง identity เดิม** (แนะนำ) | ยังอยู่ช่วงพัฒนา ไม่ซีเรียสเรื่องชื่อ local | ไม่ย้ายเลย | ต่ำสุด — ไม่มีการ copy ข้อมูล |
| **B — ย้ายไป project ใหม่** | อยากให้ชื่อ local ตรงกับ TiewTrade | dump → restore | ปานกลาง — ต้อง verify หลัง restore |
| **C — ทิ้งข้อมูลเดิม** | ข้อมูลเดิมเป็นของทิ้งได้ (ยังไม่มี schema/migrations) | เริ่มใหม่ว่าง | ต่ำ ถ้าแน่ใจว่าไม่มีอะไรต้องเก็บ |

Phase 1 ยังไม่มี migrations หรือ schema ที่ commit ไว้ (ดู [IMP-03](../reviews/backend-structure-review.md)) ถ้า
volume เดิมมีแค่ database ว่างจากการลองรัน แนวทาง C ก็เพียงพอ — ตรวจก่อนด้วย §2.1

### 2.1 ตรวจว่ามีอะไรอยู่ใน volume เดิมจริงหรือไม่

```sh
cd deploy
# ต้องให้ project เดิมรันอยู่ ถ้ายังไม่รัน: COMPOSE_PROJECT_NAME=fasttrade docker compose up -d --wait
COMPOSE_PROJECT_NAME=fasttrade docker compose exec -T postgres \
  psql -U fasttrade -d fasttrade -c '\dt'
```

ถ้าได้ `Did not find any relations.` แปลว่ายังไม่มีตาราง → เลือกแนวทาง C ได้เลย

---

## A. คง identity, volume และ credentials เดิม (แนะนำ)

ไม่ย้ายข้อมูล ไม่ dump ไม่ restore — แค่บอก Compose ให้ใช้ project name เดิมต่อ
`COMPOSE_PROJECT_NAME` มี precedence สูงกว่า `name:` ในไฟล์ จึงไม่ต้องแก้ไฟล์ที่ commit ไว้

เพิ่มบรรทัดนี้ใน `deploy/.env` ที่มีอยู่ (**append ห้าม overwrite**):

```sh
cd deploy
grep -q '^COMPOSE_PROJECT_NAME=' .env || echo 'COMPOSE_PROJECT_NAME=fasttrade' >> .env
```

`POSTGRES_DB` / `POSTGRES_USER` ใน `.env` เดิมของคุณยังเป็น `fasttrade` อยู่แล้ว — **ปล่อยไว้**
เพราะต้องตรงกับ database/role ที่ initdb สร้างไว้ใน volume

**Verification**

```sh
docker compose config --format json \
  | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['name'], {k:v.get('name') for k,v in d.get('volumes',{}).items()})"
# คาดหวัง: fasttrade {'postgres-data': 'fasttrade_postgres-data'}

docker compose up -d --wait
docker compose exec -T postgres psql -U fasttrade -d fasttrade -c '\dt'   # ข้อมูลเดิมครบ
```

**Rollback:** ลบบรรทัด `COMPOSE_PROJECT_NAME` ออกจาก `.env` แล้วกลับไปเป็น project `tiewtrade`
ไม่มีข้อมูลถูกแตะ

---

## B. ย้ายข้อมูลไป project ใหม่ `tiewtrade`

ทำตามลำดับ ห้ามข้ามขั้น backup

### B.1 Backup (ทำก่อนเสมอ)

```sh
cd deploy
mkdir -p ~/tiewtrade-backups
STAMP=$(date +%Y%m%d-%H%M%S)

COMPOSE_PROJECT_NAME=fasttrade docker compose up -d --wait postgres
COMPOSE_PROJECT_NAME=fasttrade docker compose exec -T postgres \
  pg_dump -U fasttrade -d fasttrade --format=custom --no-owner --no-acl \
  > ~/tiewtrade-backups/fasttrade-$STAMP.dump
```

ตรวจ backup ก่อนไปต่อ — ถ้าไฟล์ว่างหรือ list ไม่ออก **ให้หยุด**:

```sh
ls -lh ~/tiewtrade-backups/fasttrade-$STAMP.dump
docker run --rm -v ~/tiewtrade-backups:/backup:ro postgres:16-alpine \
  pg_restore --list /backup/fasttrade-$STAMP.dump | head
```

ต้องเห็น header `Format: CUSTOM` และรายการ TOC ถ้าขึ้น
`did not find magic string in file header` แปลว่า dump เสีย — **หยุด อย่าไปต่อ**

> ตรงนี้ใช้ container ชั่วคราวที่ mount directory ของ backup แบบ read-only ไม่ใช่
> `exec -T ... pg_restore --list /dev/stdin` เพราะ custom format ต้องการ input ที่ seek ได้
> การ pipe ผ่าน `exec` จะ fail เสมอ (ทดสอบแล้ว §4)

`pg_dump` คือ backup หลักของขั้นตอนนี้ และปลอดภัยขณะ PostgreSQL ทำงานอยู่ เพราะทำงาน
ใน transaction เดียวจึงได้ snapshot ที่ consistent

> **อย่า `tar` volume ขณะ PostgreSQL ยังรันอยู่** การ copy ระดับ filesystem ของ data
> directory ที่กำลังถูกเขียนอยู่จะได้ไฟล์ที่ไม่ consistent (torn pages, WAL ไม่ตรงกับ
> data file) ต่อให้ mount แบบ `:ro` ก็ไม่ช่วย เพราะ `:ro` แค่กัน **tar** ไม่ให้เขียน
> ไม่ได้หยุด **PostgreSQL** ไม่ให้เขียน ไฟล์ที่ได้อาจ restore ไม่ขึ้นโดยไม่มีอะไรเตือน
> ถ้าต้องการ copy ทั้ง volume ให้ทำหลังหยุด container แล้วใน §B.2

### B.2 หยุด project เดิมโดย **ไม่ลบ volume**

```sh
cd deploy
COMPOSE_PROJECT_NAME=fasttrade docker compose down      # ไม่มี -v โดยเจตนา
docker volume ls | grep fasttrade_postgres-data          # ต้องยังอยู่
```

ถ้าบรรทัดสุดท้ายไม่ขึ้น volume → **หยุดทันที** อย่าไปต่อ

ตอนนี้ container หยุดแล้ว จึง copy ทั้ง volume เป็น backup ชั้นที่สองได้อย่างปลอดภัย
(cold copy — ทำตรงนี้เท่านั้น ไม่ใช่ใน §B.1):

```sh
# ใช้ตัวแปรแยก: อย่าเขียนทับ $STAMP ของ §B.1 เพราะ §B.4 ยังต้องใช้ชื่อ dump เดิม
VOLSTAMP=$(date +%Y%m%d-%H%M%S)
docker run --rm -v fasttrade_postgres-data:/data:ro -v ~/tiewtrade-backups:/backup alpine \
  tar czf /backup/fasttrade-volume-$VOLSTAMP.tar.gz -C /data .
ls -lh ~/tiewtrade-backups/fasttrade-volume-$VOLSTAMP.tar.gz
```

> ถ้าเปิด shell ใหม่ระหว่างขั้นตอน `$STAMP` จะหาย ให้หาชื่อ dump จริงด้วย
> `ls -lt ~/tiewtrade-backups/*.dump | head -1` แล้วใช้ชื่อนั้นใน §B.4 แทน

### B.3 เริ่ม project ใหม่

ตรวจ `deploy/.env` ก่อนแก้ ค่าที่ต้องใช้กับ volume ใหม่คือ `POSTGRES_DB=tiewtrade`,
`POSTGRES_USER=tiewtrade` และต้องไม่มี `COMPOSE_PROJECT_NAME=fasttrade` ค้างอยู่
แก้ทีละบรรทัดด้วยมือ (ห้าม `cp .env.example .env` ทับ เพราะจะทับ `POSTGRES_PASSWORD` ของคุณ)

```sh
cd deploy
docker compose config --format json \
  | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['name'], d['services']['postgres']['environment'])"
# คาดหวัง: tiewtrade {'POSTGRES_DB': 'tiewtrade', 'POSTGRES_USER': 'tiewtrade', ...}

docker compose up -d --wait
```

### B.4 Restore

`--no-owner --no-acl` ตอน dump ทำให้ restore เข้า role ใหม่ `tiewtrade` ได้โดยไม่ติด ownership เดิม

```sh
cd deploy
docker compose exec -T postgres \
  pg_restore -U tiewtrade -d tiewtrade --no-owner --no-acl \
  < ~/tiewtrade-backups/fasttrade-$STAMP.dump
```

`pg_restore` อาจเตือนเรื่อง role/extension ที่ไม่มี — ตรวจว่าเป็น warning ไม่ใช่ error ที่ทำให้ตารางหาย
ด้วย §B.5 ก่อนสรุปว่าสำเร็จ

### B.5 Verification

```sh
cd deploy
docker compose ps                                                   # postgres + redis healthy
docker compose exec -T postgres psql -U tiewtrade -d tiewtrade -c '\dt'
```

> `docker compose ps` ขึ้น `healthy` **ไม่ได้แปลว่า restore สำเร็จ** healthcheck ใน compose file
> ใช้ `pg_isready` ซึ่งเช็กแค่ว่า server ตอบ ไม่ได้ตรวจว่า database/role ที่ระบุมีอยู่จริง
> (ทดสอบแล้ว §4) ตัวตัดสินคือผลของ `psql` ด้านบนและ row count ด้านล่าง

เทียบจำนวนตารางกับของเดิม (นับจาก backup โดยไม่ต้องเปิด project เดิม):

```sh
docker compose exec -T postgres psql -U tiewtrade -d tiewtrade -tAc \
  "select count(*) from information_schema.tables where table_schema='public'"
```

ถ้ามีตารางที่มีข้อมูล ให้เทียบ row count ของตารางสำคัญทีละตัวกับที่จดไว้ก่อน migrate
และตรวจว่า sequence เดินต่อถูก (insert ใหม่ต้องไม่ชน primary key เดิม)

### B.6 Rollback

volume เดิมยังอยู่ครบ กลับไปใช้ได้ทันที โดย**ไม่ลบ** `tiewtrade_postgres-data`:

```sh
cd deploy
docker compose down                                       # หยุด project ใหม่ ไม่มี -v
COMPOSE_PROJECT_NAME=fasttrade docker compose up -d --wait # กลับไป project เดิม
COMPOSE_PROJECT_NAME=fasttrade docker compose exec -T postgres \
  psql -U fasttrade -d fasttrade -c '\dt'
```

`POSTGRES_DB`/`POSTGRES_USER` ใน `.env` ที่แก้ไปตอน B.3 **ไม่ทำให้ rollback พัง** เพราะสองตัวนี้
ถูกใช้แค่ตอน initdb และ volume เดิม initialize ไปแล้ว — container ขึ้นปกติ แค่ต้องใช้ชื่อเดิม
(`fasttrade`) ในคำสั่ง `psql` ตามด้านบน (ทดสอบแล้ว §4) แต่แนะนำให้แก้ `.env` กลับเป็นค่าเดิม
ด้วย เพื่อไม่ให้สับสนภายหลัง

แล้วกลับไปใช้[แนวทาง A](#a-คง-identity-volume-และ-credentials-เดิม-แนะนำ) แทน

ถ้า volume ใหม่เสียหายและอยากเริ่ม restore ใหม่ ให้ลบเฉพาะ volume ใหม่อย่างตั้งใจ
(`docker volume rm tiewtrade_postgres-data` หลัง `docker compose down`) — **อย่าแตะ** volume เดิม

---

## C. เริ่มใหม่และเก็บ volume เดิมไว้เฉย ๆ

ใช้เมื่อยืนยันแล้วตาม §2.1 ว่าข้อมูลเดิมทิ้งได้

```sh
cd deploy
COMPOSE_PROJECT_NAME=fasttrade docker compose down   # ไม่มี -v — volume เดิมเก็บไว้เป็น safety net
# แก้ deploy/.env ด้วยมือ: POSTGRES_DB=tiewtrade, POSTGRES_USER=tiewtrade, ไม่มี COMPOSE_PROJECT_NAME
docker compose up -d --wait
docker compose exec -T postgres psql -U tiewtrade -d tiewtrade -c 'select 1'
```

volume เดิมยังอยู่ ลบทีหลังได้เมื่อมั่นใจแล้ว (คำสั่งลบไม่ได้ใส่ไว้ที่นี่โดยเจตนา)

**Rollback:** `docker compose down` แล้ว `COMPOSE_PROJECT_NAME=fasttrade docker compose up -d --wait`

---

## 3. Optional — rename database/role ภายใน volume เดิม

ถ้าเลือกแนวทาง A แต่ยังอยากให้ชื่อ database/role เป็น `tiewtrade` ทำแยกจากการเปลี่ยน project name
และต้องมี backup จาก §B.1 ก่อน `POSTGRES_DB`/`POSTGRES_USER` ใน `.env` ไม่ rename ให้ —
สองตัวนี้ถูกใช้แค่ตอน initdb ครั้งแรกเท่านั้น

> **ข้อควรระวังสำคัญ:** `ALTER ROLE ... RENAME` จะ fail ด้วย `ERROR: session user cannot be renamed`
> ถ้าคุณ login เป็น role ตัวนั้นเอง และ image `postgres` สร้าง superuser ไว้แค่ตัวเดียวคือ
> `POSTGRES_USER` จึงต้องสร้าง superuser ชั่วคราวมาทำการ rename ให้ (ทดสอบแล้ว §4)

### 3.1 rename database (ทำได้จาก role เดิม)

ต้องไม่มี session ใดเชื่อมกับ database ที่จะ rename อยู่ — ต่อเข้า `postgres` แทน
และหยุด service อื่นที่ใช้ database นี้ก่อน

```sh
cd deploy
COMPOSE_PROJECT_NAME=fasttrade docker compose exec -T postgres \
  psql -U fasttrade -d postgres -c 'ALTER DATABASE fasttrade RENAME TO tiewtrade;'
```

### 3.2 rename role (ต้องใช้ superuser ชั่วคราว)

```sh
cd deploy
# 1) สร้าง superuser ชั่วคราว (ตั้ง password ชั่วคราวเองแล้วลบทิ้งใน 3)
COMPOSE_PROJECT_NAME=fasttrade docker compose exec -T postgres \
  psql -U fasttrade -d postgres -c "CREATE ROLE tmp_rename SUPERUSER LOGIN PASSWORD 'tmp-only';"

# 2) rename จาก session ของ tmp_rename
COMPOSE_PROJECT_NAME=fasttrade docker compose exec -T postgres \
  psql -U tmp_rename -d postgres -c 'ALTER ROLE fasttrade RENAME TO tiewtrade;'

# 3) ลบ superuser ชั่วคราวทิ้งทันที
COMPOSE_PROJECT_NAME=fasttrade docker compose exec -T postgres \
  psql -U tiewtrade -d postgres -c 'DROP ROLE tmp_rename;'
```

### 3.3 หลัง rename

แก้ `deploy/.env` ด้วยมือให้เป็น `POSTGRES_DB=tiewtrade`, `POSTGRES_USER=tiewtrade`
(ค่าเหล่านี้ไม่มีผลกับ volume ที่ initdb แล้ว แต่ต้องตรงเพื่อไม่ให้สับสนและเพื่อให้คำสั่งในเอกสารนี้ใช้ได้)
แล้ว verify:

```sh
cd deploy
COMPOSE_PROJECT_NAME=fasttrade docker compose exec -T postgres \
  psql -U tiewtrade -d tiewtrade -c '\dt'
```

**เรื่อง password:** PostgreSQL 16 ใช้ `password_encryption = scram-sha-256` เป็นค่า default
ซึ่ง **password อยู่รอดหลัง rename** (ยืนยันแล้ว §4) ข้อจำกัดที่ password ถูกล้างหลัง
`ALTER ROLE ... RENAME` มีเฉพาะกรณีที่ใช้ `md5` ตรวจของคุณเองด้วย:

```sh
COMPOSE_PROJECT_NAME=fasttrade docker compose exec -T postgres \
  psql -U tiewtrade -d postgres -tAc "show password_encryption"
```

ถ้าได้ `md5` ให้ตั้ง password ใหม่: `ALTER ROLE tiewtrade WITH PASSWORD '<ค่าใน .env>';`

**Rollback:** rename กลับด้วยขั้นตอนเดียวกันแบบสลับชื่อ (role ก็ยังต้องใช้ superuser ชั่วคราว)
หรือ restore จาก backup §B.1

---

## 4. สถานะการทดสอบ runbook นี้

ทดสอบเมื่อ 2026-09-23 กับ Docker Engine 29.7.2 / `postgres:16-alpine` โดยใช้สำเนาของ
`deploy/docker-compose.yml` ใน Compose project ชั่วคราว (`ttmig-old` / `ttmig-new`) บน port
55432/56379 พร้อมข้อมูลตัวอย่าง 2 ตาราง (5 แถว รวมค่า `numeric(30,10)`)
ไม่ได้แตะ project, volume, ฐานข้อมูล หรือ `.env` จริงของเครื่องใด ๆ และลบ resource
ที่สร้างขึ้นทั้งหมดหลังทดสอบเสร็จ

### ทดสอบกับข้อมูลจริงแล้ว

| ขั้นตอน | ผล |
|---|---|
| Project/volume/network name resolution ทั้งชื่อเก่าและใหม่ | ✅ `fasttrade_postgres-data` vs `tiewtrade_postgres-data` |
| แนวทาง A — `COMPOSE_PROJECT_NAME` ใน `.env` override `name:` ในไฟล์ | ✅ ยืนยันตอน runtime: volume ที่ถูกสร้างจริงใช้ชื่อจาก `COMPOSE_PROJECT_NAME` |
| `-p` บน CLI มี precedence เหนือ `COMPOSE_PROJECT_NAME` | ✅ |
| project ใหม่ขึ้นมาพร้อม database ว่าง (ตามที่ §0 เตือน) | ✅ `Did not find any relations.` |
| §B.1 `pg_dump --format=custom --no-owner --no-acl` | ✅ |
| §B.1 ตรวจ dump ด้วย container ชั่วคราว | ✅ `Format: CUSTOM`, TOC 18 entries |
| §B.2 cold copy ทั้ง volume ด้วย `tar` หลังหยุด container | ⚠️ ทดสอบแค่ว่า**สร้างไฟล์ได้** ยังไม่ได้ทดสอบว่า restore กลับขึ้น |
| §B.2 `docker compose down` ไม่ลบ named volume | ✅ volume เดิมยังอยู่ |
| §B.4 `pg_restore` ผ่าน `exec -T` stdin | ✅ exit 0 |
| §B.5 ตาราง, row count และค่า `numeric` ตรงทุกหลัก | ✅ `1000.1234567890` ตรงเป๊ะ; owner ย้ายเป็น role ใหม่ |
| §B.5 sequence เดินต่อถูก ไม่ชน primary key | ✅ insert หลัง restore ได้ `id = 3` |
| §B.6 rollback กลับ project เดิม | ✅ ข้อมูลเดิมครบและ **ไม่มี** แถวที่เพิ่มใน project ใหม่ — volume เดิมไม่ถูกแตะ |
| §3.1 `ALTER DATABASE ... RENAME` | ✅ |
| §3.2 rename role ด้วย superuser ชั่วคราว | ✅ password (scram-sha-256) ใช้ได้ต่อหลัง rename |
| Redis ไม่มี volume ต้องย้าย | ✅ |

### ข้อผิดพลาดที่เจอจากการทดสอบและแก้ในเอกสารแล้ว

ร่างแรกของ runbook นี้มี 4 จุดที่ใช้งานจริงไม่ได้ ทั้งหมดแก้แล้ว:

1. **`pg_restore --list /dev/stdin` ผ่าน `exec -T` ใช้ไม่ได้** — custom format ต้องการ input
   ที่ seek ได้ ได้ `did not find magic string in file header` เสมอ → เปลี่ยนเป็น container
   ชั่วคราวที่ mount backup directory แบบ read-only (§B.1)
2. **`ALTER ROLE fasttrade RENAME TO tiewtrade` จาก session ของ `fasttrade` เอง fail** ด้วย
   `ERROR: session user cannot be renamed` → เพิ่มขั้นตอน superuser ชั่วคราว (§3.2)
3. **`pg_isready` ไม่ใช่ตัวยืนยัน database/user** — ตอบ `accepting connections` แม้ `-U`/`-d`
   จะเป็นชื่อที่ไม่มีอยู่จริง ทำให้ healthcheck เขียว ๆ หลอกได้ → ใช้ `psql` เป็นตัวตรวจแทน (§1, §B.5)
4. **`$POSTGRES_USER` ไม่มีค่าใน shell ของผู้ใช้** เพราะ `.env` ถูกอ่านโดย Compose ไม่ได้ export
   ออกมา → เปลี่ยนเป็นชื่อจริงในคำสั่ง (§1)
5. **`tar` volume ขณะ PostgreSQL ยังรันอยู่ไม่ใช่ backup ที่เชื่อถือได้** — `:ro` กันแค่ tar
   ไม่ได้หยุด PostgreSQL ที่กำลังเขียน ได้ไฟล์ที่ไม่ consistent และอาจ restore ไม่ขึ้น →
   ย้ายขั้นตอนนี้ไปหลัง `docker compose down` ใน §B.2 ให้เป็น cold copy
   (พบจาก re-review ของ Codex ไม่ใช่จากการทดสอบรอบแรก)

ข้อ 2 แก้ความเข้าใจเดิมด้วย: PostgreSQL 16 default เป็น `scram-sha-256` password จึง**ไม่ถูกล้าง**
หลัง rename ข้อจำกัดนั้นมีเฉพาะ `md5`

### ยังไม่ได้ทดสอบ

| รายการ | เหตุผล |
|---|---|
| ย้ายข้อมูลขนาดใหญ่ (หลาย GB) | ข้อมูลตัวอย่างมีขนาดเล็ก; เวลา dump/restore จริงจะนานกว่านี้มาก |
| Volume ที่มี extension, custom role หรือ schema หลายชั้น | ข้อมูลตัวอย่างใช้ `public` schema ล้วน ไม่มี extension |
| restore ข้ามเวอร์ชัน PostgreSQL | ทดสอบภายใน `postgres:16-alpine` เท่านั้น |

ก่อนใช้กับข้อมูลที่เสียไม่ได้ ให้ทำ `pg_dump` ใน §B.1 เสมอ และ cold copy ใน §B.2 เพิ่มอีกชั้น
