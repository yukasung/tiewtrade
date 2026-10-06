# F-07 จัดการ API key ของผู้ใช้ — Plan

สถานะ: **Approved** — เจ้าของอนุมัติ 2026-10-04
วันที่: 2026-10-04
อ้างอิง: `requirements.md` ฉบับที่เจ้าของอนุมัติ 2026-10-04

---

## 1. แนวทาง

### 1.1 เส้นทางของ secret หนึ่งค่า ตั้งแต่ผู้ใช้กรอกจนใช้งานได้

```
ผู้ใช้กรอก key + secret
        │
        ▼
   api  ─ ยืนยัน TOTP ซ้ำ (ไม่รับรหัสสำรอง)
        ─ ปิดผนึกทันทีด้วยกุญแจของงานนี้
        ─ INSERT แถวสถานะ "กำลังตรวจ"      ← api เขียนได้ แต่ **อ่านคอลัมน์ที่ปิดผนึกไม่ได้**
        │
        ▼  (ไม่มี HTTP ระหว่าง service — คุยผ่าน PostgreSQL)
  engine worker
        ─ scan หาแถวที่ยังไม่ผ่าน (บทบาทข้าม RLS **แต่อ่าน secret ไม่ได้**)
        ─ สวมบทบาทผู้ใช้รายนั้น → เปิดผนึก → สร้าง "ตัวลงลายเซ็น"
        ─ อ่านกระเป๋าหนึ่งครั้งผ่าน venues
        ─ เขียนผลกลับ: ใช้งานได้ / ตรวจไม่ผ่าน / ตรวจไม่ได้ ลองใหม่ได้
        │
        ▼
   หน้าเว็บ poll สถานะ → ผู้ใช้เห็นผล
```

**ทำไมทางนี้** — `architecture.md` หัวข้อ 3 ให้ `engine` เท่านั้นที่ถอดรหัสได้ และหัวข้อ 1
ห้าม service เรียก HTTP หากัน ทางนี้จึงไม่ต้องยืดกฎข้อใด (Q-1 ช่อง ข.)
ราคาที่จ่ายคือ worker ตัวแรกของ `engine` ซึ่ง F-08 กับ F-22 ต้องมีอยู่แล้ว

### 1.2 สามอย่างที่ตัดสินรูปของงานนี้

1. **ตลาดไม่บอกสิทธิ์ของ key** (NC-16) → "ตรวจ key" ในงานนี้แปลว่า **พิสูจน์ว่าใช้ได้จริง**
   ไม่ใช่ "อ่านว่ามีสิทธิ์อะไร" · และ **ห้ามแตะ `canTrade`/`canWithdraw`/`canDeposit`**
2. **อาจมี key ที่ถอนเงินได้โดยผู้ใช้ปิดไม่ได้** (NC-16 ยังเปิด) → สิ่งที่กันความเสียหายจริง
   คือ **โค้ดต้องไปถึง endpoint ที่ย้ายเงินไม่ได้เลย** บังคับด้วยด่าน (RQ-16)
3. **`api` ถือค่าดิบได้ชั่วขณะเดียว** → ทุกอย่างหลังจากนั้นทำกับค่าที่ปิดผนึกแล้ว

---

## 2. ของเดิมที่จะใช้ซ้ำ

**ค้นแล้วก่อนเขียนใหม่** ตาม `AGENTS.md` หัวข้อ "ใช้ของเดิมซ้ำ"

| ของเดิม | path | ใช้ทำอะไร |
|---|---|---|
| `KeySource`, `KeyPurpose`, `seal`, `unseal` | `infra/crypto/` | ปิดผนึก/เปิดผนึก secret · **เพิ่มสมาชิกใหม่ใน `KeyPurpose` ไม่ใช่ใช้ของ TOTP ซ้ำ** (RQ-4) |
| `user_session`, `scan_session_bypassing_rls` | `infra/db/session.py` | สวมบทบาทผู้ใช้ และงานกวาดข้ามผู้ใช้ |
| `DatabaseRole` | `infra/db/engine.py` | เลือกบทบาทที่จุดเรียก |
| `record_own_action` | `infra/audit/writer.py` | audit log ของการกระทำที่ผู้ใช้ทำกับตัวเอง |
| `redaction` | `infra/audit/redaction.py` | กันค่าที่เป็นความลับหลุดเข้า log |
| `RouteRule`, `ROUTE_RULES` | `services/api/routing_policy.py` | ประกาศขอบเขตของเส้นทางใหม่ (RQ-8) |
| การยืนยันปัจจัยที่สองซ้ำ | `services/api/authentication.py` | `reverify=True` ของ F-06 |
| `Bucket`, ตัวคุมอัตรา | `infra/auth/throttle.py` | คุมอัตราเส้นทางที่เพิ่ม key (RQ-11) |
| `BinanceThTransport`, `RateLimitGuard`, `CallCost` | `venues/binance_th/transport.py`, `venues/limits.py` | เรียกตลาดผ่านทางเดียวที่จองโควตาก่อนเสมอ |
| `WalletSource`, `WalletHoldings`, `Holding` | `venues/wallets.py` | สัญญากระเป๋าของ F-33 — **ทำให้ครบ ไม่ใช่สร้างสัญญาใหม่** |
| ชนิดข้อผิดพลาดกลาง 6 ชนิด | `venues/errors.py` | แยก "ชั่วคราว" ออกจาก "ผิดจริง" ได้โดยไม่ต้องนิยามใหม่ |
| `FakeVenue` | `venues/fake.py` | เทสต์โดยไม่ยิงตลาด |
| `_WithoutQueryStrings` | `venues/binance_th/transport.py` | **สำคัญกับงานนี้มาก** — คำขอที่ลงลายเซ็นพาลายเซ็นไปใน query string |

**ที่ไม่ใช้ซ้ำโดยตั้งใจ:** กุญแจของ TOTP (RQ-4 ห้าม) · ตาราง `user_totp` (คนละเรื่อง)

---

## 3. สิ่งที่จะแก้

| ไฟล์ | เปลี่ยนอะไร |
|---|---|
| `migrations/versions/0009_api_keys.py` | **ใหม่** — ตาราง `user_api_keys`, RLS, สิทธิ์รายคอลัมน์, ชนิดเหตุการณ์ audit ใหม่ |
| `src/tiewtrade/infra/crypto/keys.py` | เพิ่มสมาชิก `VENUE_API_SECRET` ใน `KeyPurpose` |
| `src/tiewtrade/infra/api_keys/` | **ใหม่** — เก็บ/อ่าน/ลบแถว, การเปลี่ยนสถานะ, เพดานจำนวนและเวลา |
| `src/tiewtrade/venues/signing.py` | **ใหม่** — สัญญา `RequestSigner` (กลาง ไม่พูดคำของตลาด) |
| `src/tiewtrade/infra/api_keys/signing.py` | **ใหม่** — ตัวลงลายเซ็นที่ **ถือ secret** · อยู่ใน `infra` **ไม่ใช่ใน `venues`** (ดูข้อ 6.1) |
| `src/tiewtrade/venues/binance_th/transport.py` | รองรับคำขอที่ลงลายเซ็น |
| `src/tiewtrade/venues/binance_th/wallets.py` | **ใหม่** — ทำสัญญา `WalletSource` ให้ครบ (ส่วนที่ F-35 เลื่อนไว้) |
| `src/tiewtrade/venues/fake.py` | ให้ `FakeVenue` ตอบกระเป๋าได้ทุกกรณีรวมกรณีผิดพลาด |
| `src/tiewtrade/services/engine/main.py` | **worker ตัวแรก** — วนตรวจ key ที่ยังไม่ผ่าน |
| `src/tiewtrade/services/engine/verification.py` | **ใหม่** — ตรรกะของรอบตรวจหนึ่งรอบ (ทดสอบได้โดยไม่ต้องมี loop) |
| `src/tiewtrade/services/api/api_key_routes.py` | **ใหม่** — เพิ่ม/ดู/ลบ/กดลองใหม่ |
| `src/tiewtrade/services/api/routing_policy.py` | เพิ่มสี่แถวของเส้นทางใหม่ |
| `src/tiewtrade/services/api/app.py`, `resources.py` | lifespan อ่านกุญแจของงานนี้ และเปิดเส้นทางใหม่ |
| `src/tiewtrade/infra/audit/events.py` | ชนิดเหตุการณ์ใหม่ |
| `frontend/src/ApiKeyPanel.tsx` | **ใหม่** — ฟอร์มเพิ่ม key, รายการ, สถานะ, ปุ่มลองใหม่, ข้อความเตือน |
| `config/import-linter` และด่านของ CI | **ด่านใหม่: ห้ามโค้ดไปถึง endpoint ที่ย้ายเงิน** (RQ-16) |

---

## 4. ฐานข้อมูล — migration `0009`

### 4.1 ตารางเดียว ไม่ใช่สองตาราง

ต่างจาก F-06 ที่ต้องมี `user_totp` กับ `user_totp_pending` แยกกัน เพราะที่นั่น
"ของที่ยังไม่พิสูจน์" **ต้องไม่มีผลกับการยืนยันตัวตน** ส่วนที่นี่ key ที่ยังไม่ผ่าน
ไม่มีผลกับอะไรเลยอยู่แล้ว — มันแค่ใช้ไม่ได้ · สถานะจึงเป็นคอลัมน์ได้

```sql
CREATE TABLE user_api_keys (
    id              uuid PRIMARY KEY,
    user_id         uuid NOT NULL REFERENCES users (id),
    label           text NOT NULL,
    key_public      text NOT NULL,          -- ส่วนที่ไม่เป็นความลับ
    secret_sealed   bytea,                  -- NULL ได้ เพราะถูกลบทิ้งเมื่อจบรอบ
    key_version     text,
    status          text NOT NULL,
    failure_code    text,                   -- รหัสคงที่ ไม่ใช่ข้อความจากตลาด
    attempts        integer NOT NULL DEFAULT 0,
    retry_requested_at timestamptz,         -- ผู้ใช้กดลองใหม่ (api เขียนได้ช่องเดียวนี้)
    not_before      timestamptz,            -- ตลาดสั่งให้รอถึงเมื่อไร — ข้ามไม่ได้
    next_attempt_at timestamptz,            -- backoff ของเรา คำนวณไว้ตอนเขียนผล (ข้อ 7.5)
    claimed_by      text,                   -- worker ที่จองแถวนี้อยู่ (ข้อ 7.5)
    claim_id        uuid,                   -- รหัสของรอบตรวจที่จองไว้
    claim_expires_at timestamptz,           -- หมดอายุการจอง = ทางกู้เมื่อ worker ตาย
    created_at      timestamptz NOT NULL DEFAULT now(),
    verified_at     timestamptz,
    last_attempt_at timestamptz,
    CONSTRAINT user_api_keys_status CHECK (
        status IN ('PENDING', 'ACTIVE', 'REJECTED', 'UNVERIFIABLE')),
    -- **สถานะกับการมีอยู่ของ secret ต้องตรงกันเสมอ** บังคับที่ฐานข้อมูล
    CONSTRAINT user_api_keys_secret_shape CHECK (
        CASE status
            WHEN 'ACTIVE'       THEN secret_sealed IS NOT NULL AND key_version IS NOT NULL
            WHEN 'PENDING'      THEN secret_sealed IS NOT NULL AND key_version IS NOT NULL
            WHEN 'UNVERIFIABLE' THEN secret_sealed IS NOT NULL AND key_version IS NOT NULL
            WHEN 'REJECTED'     THEN secret_sealed IS NULL AND key_version IS NULL
        END),
    CONSTRAINT user_api_keys_label_shape CHECK (label <> ''),
    CONSTRAINT user_api_keys_public_shape CHECK (key_public <> ''),
    CONSTRAINT user_api_keys_attempts CHECK (attempts >= 0)
);
CREATE UNIQUE INDEX user_api_keys_one_label ON user_api_keys (user_id, label);
CREATE INDEX user_api_keys_unfinished ON user_api_keys (status)
    WHERE status IN ('PENDING', 'UNVERIFIABLE');
```

**`REJECTED` บังคับว่า secret ต้องหายไปแล้ว** (Q-7) — เขียนเป็น `CHECK` เพราะกฎที่อยู่
ในโค้ดอย่างเดียวคือกฎที่ลืมได้ในงานถัดไป

### 4.2 สิทธิ์รายคอลัมน์ — ข้อที่ทั้งงานนี้ตั้งอยู่บน

```sql
-- api: เพิ่มได้ ลบได้ อ่านได้ **ยกเว้นสองคอลัมน์**
GRANT INSERT (id, user_id, label, key_public, secret_sealed, key_version, status)
    ON user_api_keys TO tiewtrade_api;
GRANT SELECT (id, user_id, label, key_public, status, failure_code,
              attempts, created_at, verified_at, last_attempt_at,
              retry_requested_at, not_before, next_attempt_at)
    ON user_api_keys TO tiewtrade_api;
-- `not_before` กับ `retry_requested_at` อยู่ในรายการนี้เพราะ endpoint ของปุ่มลองใหม่
-- ต้องใช้ตัดสินและต้องส่งเวลาที่กดได้กลับไปหน้าจอ (แก้หลังรีวิว 2026-10-04)
GRANT DELETE ON user_api_keys TO tiewtrade_api;
-- **ปุ่ม "ลองใหม่" เขียนได้ช่องเดียว** (แก้หลังรีวิว 2026-10-04 — ร่างแรกให้ `api`
-- แก้ `status` กับ `attempts` ซึ่งทั้งขัดกับ "ผลการตรวจเป็นของ engine" และยัง
-- แก้ `last_attempt_at` ไม่ได้ตามที่ร่างแรกบอกให้ทำ)
GRANT UPDATE (retry_requested_at) ON user_api_keys TO tiewtrade_api;

-- engine: อ่าน secret ได้ เพราะต้องเปิดผนึก
GRANT SELECT ON user_api_keys TO tiewtrade_engine;
GRANT UPDATE (status, failure_code, attempts, verified_at, last_attempt_at,
              not_before, next_attempt_at, secret_sealed, key_version,
              claimed_by, claim_id, claim_expires_at) ON user_api_keys TO tiewtrade_engine;

-- engine_scan: หาแถวที่ต้องตรวจ **แต่ห้ามเห็น secret** (F-03 Q-3)
GRANT SELECT (id, user_id, status, attempts, created_at, last_attempt_at,
              retry_requested_at, not_before, next_attempt_at,
              claimed_by, claim_id, claim_expires_at)
    ON user_api_keys TO tiewtrade_engine_scan;
```

**`api` ไม่มี `SELECT` บน `secret_sealed`** — ฉะนั้น `SELECT *` ของ `api` จะ **ล้ม**
ไม่ใช่คืนค่ามาเงียบ ๆ นี่คือการบังคับ RQ-3 ที่ระดับฐานข้อมูลตาม `tech-stack.md` หัวข้อ 8

### 4.3 RLS

เหมือนแบบแผนของ `0007`/`0008`: `ENABLE` + `FORCE` · policy `FOR ALL` ของ `api`
และของ `engine` ผูกกับ `tiewtrade_current_user_id()` · `engine_scan` ข้าม RLS
อยู่แล้วตามบทบาท

### 4.4 ชนิดเหตุการณ์ audit ใหม่

**ทุกการกระทำต้องมีแถวในตารางนี้** (เติมให้ครบหลังรีวิว 2026-10-04 — ร่างแรกมีสี่ชนิด
แต่ไม่ครอบการกดลองใหม่ของผู้ใช้และผลตรวจแบบชั่วคราว ทั้งที่ V-35 บังคับให้ครบ):

| การกระทำ | ชนิดเหตุการณ์ | ผู้กระทำ | `outcome` | `failure_code` |
|---|---|---|---|---|
| ผู้ใช้เพิ่ม key | `API_KEY_ADDED` | `USER` | `SUCCEEDED` | — |
| ผู้ใช้กดลองใหม่ | `API_KEY_RETRY_REQUESTED` | `USER` | `SUCCEEDED` | — |
| ผู้ใช้ลบ key | `API_KEY_DELETED` | `USER` | `SUCCEEDED` | — |
| ตรวจผ่าน | `API_KEY_VERIFIED` | `SYSTEM` | `SUCCEEDED` | — |
| ตรวจไม่ผ่าน (key ผิดจริง) | `API_KEY_REJECTED` | `SYSTEM` | `REJECTED` | รหัสของสาเหตุ |
| หมดเวลา 24 ชม. | `API_KEY_REJECTED` | `SYSTEM` | `REJECTED` | `VERIFICATION_EXPIRED` |
| ตรวจไม่ได้ชั่วคราว | `API_KEY_VERIFICATION_DEFERRED` | `SYSTEM` | `FAILED` | รหัสของสาเหตุ |

**`AuditOutcome` และ `ActorKind` มีค่าที่ต้องใช้ครบแล้ว** (`SUCCEEDED`/`FAILED`/`REJECTED`
และ `SYSTEM`) จึงไม่ต้องเพิ่มชนิดใหม่ของ F-04 · `failure_code` เป็น **ช่องของมันเอง
ในตาราง audit อยู่แล้ว** ไม่ต้องยัดลง `details`

**`details` ต้องว่างหรือมีได้แค่ `key_id`** — ห้ามมี `key_public` และห้ามมี secret
(RQ-9.1) บังคับด้วย `CHECK` ตามแบบแผนของ F-04/F-06

**ลงบันทึกทุกครั้ง ไม่มีข้อยกเว้น** (แก้หลังรีวิว 2026-10-04) — ร่างก่อนเสนอให้เขียน
`API_KEY_VERIFICATION_DEFERRED` เฉพาะเมื่อรหัสสาเหตุเปลี่ยน ซึ่งเป็น **การสร้าง
ข้อยกเว้นให้ RQ-9 ในชั้น `plan.md`** — `plan.md` ลดข้อกำหนดที่อนุมัติแล้วไม่ได้
(`AGENTS.md` กฎข้อ 1 และ 3) ถ้าจะยกเว้นต้องแก้ `requirements.md` และขออนุมัติก่อน

**และข้อยกเว้นนั้นไม่จำเป็น เพราะจำนวนแถวมีเพดานอยู่แล้ว:**

| ที่มาของแถว | เพดาน |
|---|---|
| รอบตรวจอัตโนมัติ | backoff 1/5/15/60 นาที ภายในอายุ 24 ชม. → **ราว 30 แถวต่อ key** |
| ผู้ใช้กดลองใหม่ | ถัง `API_KEY_RETRY` ต่อบัญชี (ข้อ 7.4) |
| จำนวน key | 6 อันต่อผู้ใช้ (Q-3) |

ผู้โจมตีจึงทำให้ตารางโตตามใจไม่ได้ ซึ่งเป็นเหตุผลเดียวที่ F-05/F-06 ไม่ลงบันทึก
ทุกครั้งที่กรอกรหัสผิด — เหตุผลนั้นไม่มีที่นี่

---

## 5. กุญแจเข้ารหัส

```python
class KeyPurpose(Enum):
    TOTP_SECRET = "TOTP_SECRET"
    VENUE_API_SECRET = "VENUE_API_SECRET"   # ← งานนี้
```

- ตัวแปรสภาพแวดล้อม `TIEWTRADE_SEALING_KEY_VENUE_API_SECRET` (ได้จาก property เดิม)
- **`api` อ่านกุญแจนี้ตอนเปิดแอป** เพื่อปิดผนึก · **`engine` อ่านเพื่อเปิดผนึก**
- `seal()` ผูกค่ากับ `purpose` + `owner` อยู่แล้ว ฉะนั้นกุญแจที่ถูกตั้งสลับกับของ TOTP
  จะ **เปิดผนึกไม่ออก** ไม่ใช่เปิดออกเงียบ ๆ (F-06 V-9)
- **T-03 ฝั่งเครื่องจริงยังไม่ปิด** — เขียนกำกับใน docstring เหมือน F-06 (RQ-14)

**ข้อที่ต่างจาก TOTP และต้องเขียนไว้:** กุญแจหายของงานนี้ **กู้ได้** —
ผู้ใช้สร้าง key ใหม่ที่ตลาดแล้วกรอกใหม่ ต่างจาก TOTP ที่กุญแจหาย = ล็อกออกทั้งระบบ

---

## 6. `venues` — ตัวลงลายเซ็นและสัญญากระเป๋า

### 6.1 สัญญาที่กลาง ไม่พูดคำของตลาด

```python
# venues/signing.py
class RequestSigner(Protocol):
    """ลงลายเซ็นคำขอหนึ่งใบ — **ผู้ทำสัญญานี้ถือความลับไว้ข้างใน**"""
    @property
    def public_identifier(self) -> str: ...
    def sign(self, payload: str) -> str: ...
```

**ตัวที่ทำตามสัญญานี้ต้องอยู่นอก `venues`** (แก้หลังรีวิว 2026-10-04) — ร่างแรกวางมันไว้
ที่ `venues/binance_th/signing.py` ซึ่ง **ขัดกับคำตัดสิน Q-2 เอง**: ตัวที่ลงลายเซ็นได้
คือตัวที่ถือ secret ฉะนั้นถ้ามันอยู่ใน `venues` ก็เท่ากับ `venues` เห็นค่าดิบ
การที่ `engine` เป็นผู้สร้าง object ไม่ได้เปลี่ยนว่าโค้ดที่ถือความลับอยู่ที่ไหน

**แบ่งหน้าที่แบบนี้แทน:**

| ใคร | รู้อะไร | ไม่รู้อะไร |
|---|---|---|
| `infra/api_keys/signing.py` | **secret** และวิธีคำนวณลายเซ็น (HMAC-SHA256) | ไม่รู้ว่าจะส่งไปที่ไหน ไม่รู้ชื่อ header ไม่รู้ว่าตลาดไหน |
| `venues/binance_th/transport.py` | **ข้อความที่ต้องลงลายเซ็น** (query string พร้อม `timestamp`) และ **ชื่อ header** ของตลาด | **ไม่เคยเห็น secret** — เรียก `signer.sign(payload)` แล้วได้สตริงกลับมา |

ได้ทั้งสองข้อพร้อมกัน: คำศัพท์ของตลาดไม่ออกนอก `venues` (F-33) และความลับ
ไม่เข้าไปใน `venues` (Q-2) · **ต้องมีเทสต์ที่พิสูจน์ว่า `venues` ไม่มีทางอ่าน secret
จากตัวลงลายเซ็นได้** — สัญญามีแค่ `public_identifier` กับ `sign()`

### 6.2 คำขอที่ลงลายเซ็นใน `binance_th`

- ต่อท้าย `timestamp` + `recvWindow` แล้วลงลายเซ็น query string ทั้งก้อน
- ส่ง `public_identifier` ทาง header ของตลาด
- **ผ่านทางเดียวเดิมที่จองโควตาก่อนเสมอ** ไม่เปิดทางลัดใหม่
- **ตัวกรอง log เดิมสำคัญขึ้นมาก** เพราะลายเซ็นเดินทางใน query string —
  ต้องมีเทสต์ที่พิสูจน์ว่าแม้เปิด log ระดับ INFO ของไลบรารี ลายเซ็นก็ไม่ลง log

### 6.3 `WalletSource` ของจริง

ทำตามสัญญาเดิมของ F-33 ครบทุกข้อ รวม **แปลงข้อผิดพลาดเข้าชนิดกลาง** เพื่อให้
`engine` แยก "ชั่วคราว" ออกจาก "ผิดจริง" ได้โดยไม่ต้องรู้จักรหัสของตลาด

### 6.4 ด่าน "ไปถึง endpoint ที่ย้ายเงินไม่ได้" (RQ-16)

**ด่านค้นสตริงอย่างเดียวพิสูจน์ข้อนี้ไม่ได้** (แก้หลังรีวิว 2026-10-04) — เส้นทางที่
ประกอบจากตัวแปรจะผ่านด่านไปได้ ฉะนั้น V-32 ที่เขียนไว้เดิมรับรองเกินกว่าที่ตรวจได้จริง

**บังคับสามชั้น ชั้นแรกคือของจริง:**

1. **ที่จุดส่งคำขอ — ชั้นที่บังคับจริงตอนรัน**
   `BinanceThTransport` **ไม่รับเส้นทางเป็นสตริงอีกต่อไป** แต่รับค่าจาก `Endpoint`
   ที่เป็นรายการปิด (`Enum`) ซึ่งมีเฉพาะเส้นทางที่งานนี้ต้องใช้ · **เส้นทางที่ไม่อยู่
   ในรายการ ส่งไม่ได้เลย ไม่ว่าจะประกอบสตริงเก่งแค่ไหน** เพราะไม่มีทางสร้างค่าของ
   `Endpoint` ที่ไม่ได้ประกาศไว้ · การเพิ่มสมาชิกใหม่เป็นการแก้โค้ดที่เห็นในรีวิวและ
   ต้องผ่านด่านข้อ 2
2. **ด่านกันทางลัด** — AST ที่แดงเมื่อโมดูลใดนอก `transport.py` import ไลบรารี
   เครือข่าย หรือประกอบ URL ของตลาดเอง · ตรวจทั่ว `backend/src`
   **NC-17 เจ้าของอนุมัติ 2026-10-06:** ยกเว้นเฉพาะ `httpx.AsyncClient` เพื่อสร้าง
   client ส่งเข้า venue และ `socket.gethostname()` ใน `services/engine/main.py`,
   กับ `urllib.parse.quote` ใน `infra/auth/totp.py` · ไม่ยกเว้นทั้งไฟล์
   · ต้องมีเทสต์จับการส่งคำขอเอง การใช้สมาชิกเครือข่ายอื่น และการประกอบ URL
   ในไฟล์ที่ยกเว้นด้วย · ชั้นที่ 1 ครอบคำขอตลาดทั้งหมด
3. **ด่านค้นสตริงต้องห้าม** (`/capital/withdraw`, โอนระหว่างบัญชี, จัดการบัญชีย่อย)
   — เป็นชั้นสุดท้ายที่จับกรณีเผลอ ไม่ใช่ชั้นที่เราพึ่ง

**เทสต์ต้องครอบเส้นทางที่ประกอบขึ้น ไม่ใช่เฉพาะสตริงที่เขียนตรง ๆ** (V-32)

---

## 7. worker ตัวแรกของ `engine`

### 7.1 แยกตรรกะออกจากการวน

`verification.py` มีฟังก์ชัน **"ตรวจหนึ่งแถว"** ที่รับเวลาและของที่ต้องใช้เข้ามา
ส่วน `main.py` มีแค่การวนกับการนอน — เทสต์จึงไม่ต้องรอเวลาจริง
(`architecture.md` หัวข้อ 2: เวลาเป็นค่าที่ผู้เรียกส่งเข้ามา)

### 7.2 หนึ่งรอบทำอะไร

```
1. scan (ข้าม RLS, ไม่เห็น secret) → รายการ (id, user_id) ของแถวที่ยังไม่ผ่าน
2. สำหรับแต่ละแถว:
   a. ถ้าอายุเกิน 24 ชม. นับจาก created_at → ลบ secret, สถานะ REJECTED,
      failure_code = VERIFICATION_EXPIRED   ← **ก่อนเรียกตลาด ไม่ใช่หลัง**
   b. user_session(ENGINE, user_id) → อ่านแถว → เปิดผนึก → สร้างตัวลงลายเซ็น
   c. อ่านกระเป๋าหนึ่งครั้ง
   d. เขียนผล (ดูตาราง 7.3) พร้อม audit log ใน transaction เดียวกับการเปลี่ยนสถานะ
```

**ข้อ 2a ไม่พอ** (แก้หลังรีวิว 2026-10-04) — ถ้าเริ่มตรวจตอน 23:59:59 แล้วตลาดตอบ
สำเร็จหลังครบ 24 ชั่วโมง สถานะยังเป็น `PENDING` อยู่ จึงผ่านการตรวจสถานะซ้ำได้
และ key ที่หมดอายุแล้วจะกลายเป็น `ACTIVE` ซึ่ง `requirements.md` ห้ามชัด

**ฉะนั้นก่อนเขียนผลทุกครั้ง ใต้ล็อกเดียวกัน ต้องตรวจสองอย่าง:**

```
2e. ใต้ล็อกของแถวนั้น:
    - สถานะยังเป็นค่าที่เราเริ่มตรวจไว้หรือไม่ (ผู้ใช้อาจลบหรือเพิ่มใหม่ไปแล้ว)
    - **เวลา ณ ตอนเขียน** ยังไม่เกิน created_at + 24 ชม. หรือไม่
      → เกินแล้ว: เขียน REJECTED + VERIFICATION_EXPIRED **ทิ้งผลที่เพิ่งได้มา**
      ไม่ว่าผลนั้นจะเป็นสำเร็จหรือไม่
```

**เวลาที่ใช้ตัดสินคือเวลาตอนเขียน ไม่ใช่เวลาตอนเริ่มรอบ** — เขียนเป็นเงื่อนไขใน
คำสั่ง `UPDATE` เองด้วย เพื่อให้ฐานข้อมูลเป็นผู้ชี้ขาด ไม่ใช่ลำดับคำสั่งในโค้ด:

```sql
UPDATE user_api_keys
   SET status = 'ACTIVE', verified_at = clock_timestamp(), ...
 WHERE id = :id
   AND status = :status_when_started
   AND clock_timestamp() < created_at + interval '24 hours'
```

**ต้องเป็น `clock_timestamp()` ไม่ใช่ `now()`** (แก้หลังรีวิว 2026-10-04) —
`now()` ของ PostgreSQL คือ **เวลาที่ transaction เริ่ม** ไม่ใช่เวลาที่คำสั่งทำงาน
ถ้า transaction เปิดคร่อมช่วงที่รอตลาดตอบ `now()` จะยังเป็นเวลาก่อนเส้นตาย
แล้วแถวที่หมดอายุระหว่างรอจะกลายเป็น `ACTIVE` ได้ — ซึ่งเป็นช่องเดียวกับที่
การตรวจก่อนเรียกตลาดเปิดไว้ แค่ย้ายที่

**และโดยหลักการ รอบตรวจต้องไม่เปิด transaction คร่อมการเรียกตลาดอยู่แล้ว**
(ถือล็อกข้ามการรอเครือข่ายคือการถือล็อกไว้ให้ตลาดกำหนดว่านานแค่ไหน)
แต่เงื่อนไขนี้ต้องถูกต้องแม้มีคนเผลอทำแบบนั้น จึงเลือกฟังก์ชันที่ถูกในทุกกรณี

### 7.3 ผลของแต่ละกรณี

| ตลาดตอบ | สถานะใหม่ | secret | ลองใหม่ |
|---|---|---|---|
| สำเร็จ | `ACTIVE` | เก็บไว้ | — |
| คำรับรองไม่ถูกต้องที่พิสูจน์แล้ว (`VenueCredentialRejectedError`) | `REJECTED` | **ลบทันที** | ไม่ |
| หมดเวลา, ตลาดล่ม, ถูกจำกัดอัตรา, เน็ตมีปัญหา | `UNVERIFIABLE` | เก็บไว้ | ใช่ |
| คำขอถูกปฏิเสธ แต่ยังไม่พิสูจน์ว่าคำรับรองผิด (`VenueRejectedError`) | `UNVERIFIABLE` | เก็บไว้ | **ด้วยมือเท่านั้น + แจ้งผู้ดูแล** (NC-20) |
| **ตอบไม่ตรงสัญญา** (`VenueProtocolError`) | `UNVERIFIABLE` | เก็บไว้ | ใช่ **+ แจ้งผู้ดูแล** |
| ครบ 24 ชม. ยังไม่ผ่าน | `REJECTED` | **ลบ** | ไม่ |

**การแจ้งผู้ดูแลของแถวที่ตอบไม่ตรงสัญญา** ยังไม่มีระบบแจ้งเตือนในโปรเจกต์ —
งานนี้ใช้ **log ระดับ ERROR ที่มีรหัสคงที่ของตัวเอง** และเขียนใน `README` ของ
การนำขึ้นเครื่องว่าต้องต่อเข้ากับช่องทางจริงใน **F-31** · เขียนไว้ให้ชัดว่านี่คือ
ช่องทางที่คนเห็นจริงวันนี้ ตามข้อที่เจ้าของระบุไว้ตอน F-35

### 7.5 การจองแถว — ต้องอยู่ข้าม transaction

**`FOR UPDATE SKIP LOCKED` ใช้ไม่ได้ที่นี่** (แก้หลังรีวิว 2026-10-04) — ล็อกของ
PostgreSQL หมดอายุเมื่อ transaction จบ แต่ข้อ 7.2 สั่งว่า **ห้ามเปิด transaction
คร่อมการเรียกตลาด** ฉะนั้นระหว่างที่ worker ตัวแรกกำลังรอตลาด แถวนั้นไม่มีล็อกอยู่เลย
· ยิ่งกว่านั้น ถ้าผู้ใช้กดลองใหม่ตอนนั้น `retry_requested_at > last_attempt_at`
จะเป็นจริงทันที แล้ว worker ตัวที่สองหยิบแถวเดียวกันได้ — และการตรวจสถานะก่อนเขียนผล
ไม่ช่วย เพราะทั้งสองรอบเริ่มจากสถานะเดียวกัน

**การจองที่อยู่ข้าม transaction:**

**คำสั่งจองต้องตรวจเงื่อนไข "ถึงคิว" ให้ครบในคำสั่งเดียวกัน** (แก้หลังรีวิว 2026-10-04)
— ร่างก่อนตรวจแค่สถานะกับการจองเดิม ซึ่งไม่พอ: ถ้า worker สองตัว scan เจอแถวเดียวกัน
แล้วตัวแรกตรวจเสร็จ ได้คำสั่งให้รอจากตลาด บันทึก `not_before` แล้วปลดการจอง
ตัวที่สองซึ่งถือผล scan เก่าอยู่จะจองต่อได้ทันที **แล้วเราก็ยิงตลาดทั้งที่เพิ่งถูกสั่งให้รอ**
· ผล scan เป็นเพียง **คำใบ้** เงื่อนไขจริงต้องถูกตรวจ ณ ตอนจอง

```sql
-- จอง (transaction สั้น ๆ ของตัวเอง ไม่คร่อมการเรียกตลาด)
UPDATE user_api_keys
   SET claimed_by = :worker, claim_id = :claim,
       claim_expires_at = clock_timestamp() + :lease,
       last_attempt_at = clock_timestamp(),      -- เขียนตอน "เริ่ม" ตามข้อ 7.4
       attempts = attempts + 1
 WHERE id = :id
   -- ยังเป็นแถวที่ต้องตรวจ
   AND status IN ('PENDING', 'UNVERIFIABLE')
   -- ยังไม่หมดอายุ (แถวที่หมดอายุมีคำสั่งของตัวเองในข้อ 7.2 ไม่ใช่มาจองที่นี่)
   AND clock_timestamp() < created_at + interval '24 hours'
   -- ไม่มีใครจองอยู่
   AND (claim_expires_at IS NULL OR claim_expires_at < clock_timestamp())
   -- **ตลาดสั่งให้รอ → ห้ามจอง ไม่ว่าใครกดอะไรมา**
   AND (not_before IS NULL OR not_before <= clock_timestamp())
   -- ถึงคิวตาม backoff **หรือ** มีคำขอลองใหม่ที่ยังไม่ถูกใช้
   AND (
         (next_attempt_at IS NULL AND last_attempt_at IS NULL)
      OR retry_requested_at > last_attempt_at
      OR next_attempt_at <= clock_timestamp()
      OR claim_expires_at < clock_timestamp() -- คืนงานที่เริ่มแล้ว แต่ worker ตาย
   )
   -- NC-20: rejection ที่เขียนเสร็จต้องมี manual request ใหม่
   AND (failure_code IS DISTINCT FROM 'VENUE_REJECTED'
        OR retry_requested_at > last_attempt_at
        OR claim_expires_at < clock_timestamp())
RETURNING id
```

- **คืนศูนย์แถว = ยังไม่ถึงคิว หรือมีคนอื่นจองอยู่** → ข้ามไป ไม่ใช่รอ
- **`not_before` อยู่เหนือทุกเงื่อนไข** — คำขอของผู้ใช้ข้ามมันไม่ได้ (ข้อ 7.4)
  และคำสั่งนี้คือที่ที่บังคับข้อนั้นจริง ไม่ใช่การตรวจใน endpoint ซึ่งเป็นแค่
  การบอกผู้ใช้ให้รู้ตัวเร็วขึ้น
- **`next_attempt_at` เป็นค่าที่เก็บไว้ ไม่ใช่ค่าที่คำนวณตอนจอง** (แก้หลังรีวิว 2026-10-04)
  — ร่างก่อนคำนวณ backoff จาก `attempts` ที่อ่านมาตอน scan แล้วส่งเข้ามาเป็นค่า
  ซึ่งผิดได้เมื่อ worker อีกตัวตรวจเสร็จและเพิ่ม `attempts` ไปแล้ว: ตัวที่ถือค่าเก่า
  จะใช้ช่วงรอ 1 นาทีแทน 5 นาที แล้วจองก่อนกำหนด
  **ผู้ที่คำนวณ backoff คือ worker ที่เพิ่งตรวจเสร็จ** ซึ่งรู้ `attempts` ที่แท้จริง
  และเขียน `next_attempt_at` ลงไปพร้อมผลในคำสั่งเดียวกัน · ตอนจองจึงเหลือแค่
  **เทียบเวลา ไม่มีการคำนวณ** — ไม่มีค่าที่เก่าได้อีกเลย
  · ทางเลือกที่ไม่เลือก: ใส่ `AND attempts = :attempts_observed` แล้วโหลดใหม่เมื่อไม่ตรง
  ซึ่งกันกรณีนี้ได้ แต่ยังปล่อยให้การคำนวณกระจายอยู่ที่จุดจอง และต้องมีวงจรลองใหม่
  ของตัวเองเพิ่มมาอีกชั้น
- **ตัวเลขของ backoff ยังอยู่ที่เดียว** ตามข้อ 7.4 — ย้ายแค่ *เวลาที่คำนวณ* ไม่ใช่ที่อยู่ของตัวเลข
- **เขียนผลได้เฉพาะเจ้าของการจองที่ยังไม่หมดอายุ** — ทุกคำสั่งเขียนผลมี
  `AND claimed_by = :worker AND claim_id = :claim AND clock_timestamp() < claim_expires_at`
  ฉะนั้น **ผลของรอบที่ช้าจะเขียนทับผลของรอบใหม่ไม่ได้** แม้ worker ตัวเก่าจะยังมีชีวิต
- **worker ตาย = การจองหมดอายุเอง** ไม่ต้องมีคนไปปลดล็อก · อายุการจองต้องยาวกว่า
  timeout ของการเรียกตลาดอย่างมีระยะเผื่อ และ **ตัวเลขอยู่ที่เดียว**
- เขียนผลเสร็จแล้วล้างสามคอลัมน์นี้ในคำสั่งเดียวกัน

**ผลกับการกดลองใหม่ระหว่างรอบที่กำลังทำงานอยู่** (ข้อ 7.4): คำขอนั้น **ไม่สร้างรอบซ้อน**
เพราะการจองยังไม่หมดอายุ — มันทำให้เกิดความพยายามเพิ่มอีกหนึ่งครั้ง **หลังรอบปัจจุบัน
จบและปลดการจองแล้ว** ซึ่งเป็นสิ่งที่ V-31.6 ต้องพิสูจน์

### 7.4 จังหวะการลองใหม่

ถอยเป็นช่วงกว้างขึ้น (เช่น 1, 5, 15, 60 นาที) โดย **ตัวเลขอยู่ในที่เดียว**
และเพดานคือ 24 ชม. ของข้อ 7.2 ไม่ใช่จำนวนครั้ง

**ปุ่ม "ลองใหม่" ของผู้ใช้** เขียน `retry_requested_at` ช่องเดียว (ข้อ 4.2)
· **ไม่ต้องยืนยัน TOTP** (เจ้าของตัดสิน)

**คำขอถูกใช้ไปเมื่อไร** (เติมหลังรีวิว 2026-10-04 — ร่างก่อนไม่ได้บอก แล้วคำขอเดิม
จะเร่งทุกรอบจนข้าม backoff ไปตลอด):

- **ถึงคิวก็ต่อเมื่อ `retry_requested_at > last_attempt_at`** — ไม่ต้องล้างค่า
  และ `engine` ไม่ต้องมีสิทธิ์เขียนคอลัมน์ของ `api`
- **`last_attempt_at` เขียนตอน *เริ่ม* ความพยายาม ไม่ใช่ตอนได้ผล** ฉะนั้นคำขอหนึ่งครั้ง
  ทำให้เกิดความพยายามหนึ่งครั้งพอดี · และถ้าผลออกมาเป็น `UNVERIFIABLE`
  รอบถัดไปกลับไปใช้ backoff ตามปกติ ไม่ใช่เร่งต่อเนื่อง
- **กดระหว่างที่รอบตรวจกำลังทำงานอยู่** → เวลาที่กดจะมากกว่า `last_attempt_at`
  ของรอบที่กำลังทำอยู่ จึงได้ความพยายามเพิ่ม **อีกหนึ่งครั้งเท่านั้น** ไม่ใช่สะสม
พร้อมสามข้อที่รีวิวชี้ (แก้ 2026-10-04):

1. **`not_before` ข้ามไม่ได้** — เมื่อตลาดบอกให้รอ (ถูกจำกัดอัตรา) worker บันทึก
   เวลานั้นไว้ และ **การกดของผู้ใช้เลื่อนคิวให้เร็วกว่า `not_before` ไม่ได้**
   มิฉะนั้นเราจะเอาผู้ใช้ไปชนโควตาของตลาดจนโดนลงโทษหนักกว่าเดิม
   หน้าเว็บแสดงเวลาที่กดได้ แทนที่จะให้กดแล้วเงียบ
2. **คุมอัตราของการกดเอง** — ถังใหม่ `API_KEY_RETRY` ต่อบัญชี แยกจาก `API_KEY_ADD`
   เพราะสองอย่างนี้มีต้นทุนต่างกันและต้องปรับแยกกันได้ · **นับต่อผู้ใช้ รวมทุก key**
   (RQ-11.1) และ **นับทุกครั้งที่กด ไม่ว่าผลจะเป็นอย่างไร** (RQ-11.2)
   · ค่าตั้งต้นอยู่ใน `infra/auth/throttle.py` ที่เดียว (RQ-11.5)
3. **กดซ้ำระหว่างรอบที่กำลังทำงานอยู่ ไม่สร้างงานใหม่** — `retry_requested_at`
   เป็นเวลาเดียวไม่ใช่คิว ฉะนั้นกดสิบครั้งได้งานเดียว

---

## 8. เส้นทางของ `api`

| เส้นทาง | RouteRule | หมายเหตุ |
|---|---|---|
| `POST /api-keys` | `renews=True, reverify=True` | **ไม่รับรหัสสำรอง** (`accepts_recovery_grant` ปล่อยเป็นค่าปริยาย) |
| `GET /api-keys` | `RouteRule()` | ไม่ต่ออายุ เพราะหน้าเว็บ poll สถานะเป็นรอบ ๆ |
| `DELETE /api-keys/{id}` | `renews=True` | ลบไม่ใช่การเพิ่มความเสี่ยง |
| `POST /api-keys/{id}/retry` | `renews=True` | ไม่ต้องยืนยันซ้ำ (เจ้าของตัดสิน) · เขียน `retry_requested_at` ช่องเดียว · **ปฏิเสธเมื่อยังไม่ถึง `not_before`** และคุมด้วยถัง `API_KEY_RETRY` |

- **`GET` คืนเฉพาะ**: `id`, `label`, 4 หลักท้ายของ `key_public`, สถานะ, `failure_code`, เวลา
  — ไม่มีคอลัมน์ความลับให้คืนอยู่แล้วเพราะ `api` อ่านไม่ได้
- **เพดาน 6 อัน** ตรวจใต้ล็อกเหมือนที่ F-06 ทำกับการเปิด TOTP ซ้อนกัน
- **คุมอัตรา** ถังใหม่ `API_KEY_ADD` และ `API_KEY_RETRY` ต่อบัญชี (RQ-11)
  — ตัวเลขอยู่ที่เดียวกับถังอื่น · **คำตอบตอนถูกจำกัดบอกเวลาที่ลองได้อีกครั้ง**
  (RQ-11.3) ซึ่งต่างจากข้อความของ F-06 ที่ตั้งใจไม่บอก: ที่นั่นการบอกเวลาช่วยคน
  ที่กำลังเดารหัสให้จับจังหวะ ส่วนที่นี่ของลับอยู่ในมือผู้ใช้อยู่แล้ว และการไม่บอกเวลา
  ทำให้คนที่ใส่ key ถูกต้องไม่รู้ว่าต้องรอเท่าไร
- ขอ key ของผู้ใช้อื่น → RLS ทำให้ได้ "ไม่พบ" โดยไม่ต้องเขียนเงื่อนไขเอง (RQ-10)

---

## 9. หน้าเว็บ

- ฟอร์มเพิ่ม key: ช่อง key, ช่อง secret, ชื่อที่ผู้ใช้ตั้ง, ช่องรหัส TOTP
- **ข้อความถาวรสองข้อ** (RQ-6.3, RQ-17): ต้องติ๊ก `Enable Spot Trading` ที่ Binance ·
  แนะนำให้เปิด whitelist ที่อยู่ถอนเงิน
- รายการ key พร้อม **สี่สถานะที่เขียนต่างกันชัด** โดยเฉพาะ "ตรวจไม่ผ่าน" กับ
  "ตรวจไม่ได้ ลองใหม่ได้" ซึ่งคนใช้ต้องทำคนละอย่าง
- ปุ่มลองใหม่โผล่เฉพาะสถานะ `UNVERIFIABLE`
- **ช่อง secret ต้องไม่ถูกเติมกลับ ไม่ถูกเก็บใน state ที่ค้าง และไม่เข้า localStorage**

---

## 10. ความเสี่ยง

| ความเสี่ยง | จะรู้ได้อย่างไร / กันอย่างไร |
|---|---|
| **ลายเซ็นหลุดเข้า log** เพราะมันเดินทางใน query string | เทสต์ที่เปิด log ระดับ INFO ของไลบรารีแล้วพิสูจน์ว่าไม่มีลายเซ็นในบันทึก |
| **`api` อ่าน secret ได้โดยไม่ตั้งใจ** | เทสต์ที่ `SELECT` คอลัมน์นั้นด้วยบทบาท `api` แล้วต้องถูกฐานข้อมูลปฏิเสธ |
| **ผลตรวจที่มาช้าปลุก key ที่หมดอายุ** | ลำดับในข้อ 7.2a + เทสต์ที่จำลองผลมาถึงหลังเพดาน |
| **key ที่ผู้ใช้ลบแล้วถูกตรวจต่อ** | ตรวจสถานะซ้ำใต้ล็อกก่อนเขียนผล + เทสต์ |
| **worker ตัวแรกทำงานพร้อมกันสองตัว** | การจองแบบมีอายุของข้อ 7.5 — **ไม่ใช่ `FOR UPDATE SKIP LOCKED`** ซึ่งปล่อยล็อกทันทีที่ transaction จบ (`architecture.md` หัวข้อ 4) |
| **NC-16 ยังเปิด — key อาจถอนเงินได้** | ด่านของข้อ 6.4 ทำให้โค้ดไปถึง endpoint นั้นไม่ได้เลย · ไม่ใช่การปิดความเสี่ยง แต่เป็นการจำกัดความเสียหาย |
| **`FakeVenue` ไม่ครอบกรณีผิดพลาดจริง** | ให้มันตอบได้ทุกชนิดข้อผิดพลาดของ `venues/errors.py` และมีเทสต์ที่เดินครบทุกชนิด |

---

## 11. ลำดับการทำงาน

1. migration `0009` + สิทธิ์ + เทสต์ของสิทธิ์ (ล้มก่อน แล้วค่อยเขียว)
2. `KeyPurpose` ใหม่ + การปิดผนึกของงานนี้
3. ชั้น `infra/api_keys` + เทสต์
4. `venues`: สัญญาตัวลงลายเซ็น → คำขอที่ลงลายเซ็น → `WalletSource` → `FakeVenue`
5. ด่าน RQ-16 (**ทำก่อนเขียนตัวเชื่อม** เพื่อให้มันแดงถ้าเผลอเพิ่มเส้นทางที่ย้ายเงิน)
6. worker ของ `engine` + เทสต์ของรอบตรวจ
7. เส้นทางของ `api` + แถวใน `ROUTE_RULES`
8. หน้าเว็บ
9. ตรวจด้วยมือกับ key จริงของเจ้าของ

### ความคืบหน้า 2026-10-05 — ข้อ 4: บังคับรายการ endpoint ตอนรัน

**เสร็จเฉพาะส่วนนี้** — ตามข้อ 6.4 และ V-32 โดยไม่เปลี่ยนแนวทางที่อนุมัติไว้:

- `backend/src/tiewtrade/venues/binance_th/transport.py` ตรวจว่าเป็นสมาชิกของ
  `Endpoint` จริงที่ต้นทางของทั้ง `get()` และ `signed_get()` ก่อนจองโควตาหรือ
  ใช้คำรับรอง · object ที่เลียนแบบและ enum คนละชนิดผ่านไม่ได้
- ใช้ตัวตรวจเดียวกันทั้งสองทาง ไม่สร้างรายการเส้นทางที่อนุญาตชุดที่สอง
- `backend/tests/venues/binance_th/test_endpoint_boundary.py` เพิ่มเทสต์ 6 กรณี:
  สตริงที่ประกอบจากตัวแปร, object เลียนแบบ, enum คนละชนิด × สองทางเรียก
  · ทุกกรณีแดงก่อนแก้และเขียวหลังแก้ · ต้องไม่มีคำขอออกไปและไม่ใช้โควตา
- ตรวจเทสต์ของ `venues`, ตัวลงลายเซ็น, ด่านเส้นทางย้ายเงิน, ขอบเขต venue และ
  ความบริสุทธิ์ของ core: **222 ข้อผ่าน** · lint, format, mypy และ import-linter ผ่าน
- ตรวจ backend ทั้งชุดกับ PostgreSQL 16 ใน Docker โดยสร้างฐานข้อมูลทดสอบแยก
  และใช้บทบาทจริงทั้ง 6 บทบาท พร้อม bootstrap และ migration: **1,034 ข้อผ่าน**
  · ไม่รันเทสต์ตลาดจริง 1 ข้อ · มี deprecation warnings เดิม 3 รายการ
  · เทสต์ migration รื้อเฉพาะฐานข้อมูลทดสอบ ไม่กระทบฐานข้อมูลเดิม

**F-07 ยังไม่เสร็จ** — บันทึกนี้ไม่รับรองส่วนอื่นของข้อ 4 หรือด่านอื่นของ validation
· การตรวจไม่เรียกตลาดจริง · งานถัดไปคือข้อ 5 (ด่านความปลอดภัย)

---

### ความคืบหน้า 2026-10-05 — ข้อ 5: ด่านความปลอดภัย

**บันทึกเดิม: ทำบางส่วน** · NC-17 ได้รับอนุมัติ 2026-10-06
· การปิดด่านดูบันทึกวันที่ 2026-10-06 ด้านล่าง

- เพิ่มด่าน V-33 จับ `canTrade`, `canWithdraw`, `canDeposit` ทั้งในและนอก
  `venues` รวมการอ่าน attribute และ import alias · ไม่จับ docstring
- เพิ่มด่าน V-32.1 ภายใน adapter: import เครือข่าย, URL ตรง/ประกอบ,
  การอ่าน `BASE_URL` รวม alias · ยกเว้นเฉพาะ `transport.py` ที่ราก adapter
  ไม่ยกเว้นไฟล์ชื่อเดียวกันในโฟลเดอร์ย่อย · re-export ยังทำได้
- ใช้ของเดิมซ้ำ: `backend/tests/venue_isolation.py` (`check_network_only_in`,
  `check_vocabulary`, ตัวอ่าน AST `code_nodes`) และ `Violation` จาก
  `backend/tests/purity.py` · ด่านเส้นทางย้ายเงินเดิมยังทำงาน
- เพิ่มไฟล์ตัวอย่างผิดและถูกใน `backend/tests/gates/fixtures/api_key_safety/`
  และเทสต์ `backend/tests/test_api_key_safety.py` · ตัวอย่างผิด 11 กรณีแดง
  ก่อนเพิ่มด่าน · ทดสอบแยกทั้งสาม flag และกรณี docstring/re-export
- เทสต์ที่เกี่ยวข้อง **283 ข้อผ่าน** · backend ทั้งชุดบนฐานข้อมูล Docker
  ที่สร้างแยก **1,055 ข้อผ่าน, 1 ข้อไม่รัน (ตลาดจริง), warnings เดิม 3 รายการ**
  · Ruff lint/format, mypy และ import-linter ผ่าน · ลบฐานข้อมูลชั่วคราวแล้ว
- รีวิวพบช่องว่าง: ไฟล์ใน `services` ยัง import `httpx` และประกอบ URL ส่งเอง
  โดยผ่านด่านนี้ได้ จึง **ยังไม่ผ่าน V-32.1 ตามขอบเขตที่อนุมัติ**

**NC-17 — ขอบเขตด่านนอก adapter และข้อยกเว้นของ composition**

ข้อ 6.4/V-32.1 ห้าม import เครือข่ายทุกโมดูลนอก `transport.py` แต่โค้ดเดิม
`backend/src/tiewtrade/services/engine/main.py` import `httpx` เพื่อสร้าง
`AsyncClient` ส่งเข้า venue และ `socket` เพื่อเรียก `gethostname()` ตั้งชื่อ worker
ส่วน `backend/src/tiewtrade/infra/auth/totp.py` import `urllib.parse.quote`
เพื่อเข้ารหัสข้อความ ไม่ส่งเครือข่าย · ห้ามเพิ่มข้อยกเว้นโดยเดาเอง

**ข้อเสนอที่เจ้าของอนุมัติ 2026-10-06:** ตรวจทางลัดทั่ว `backend/src` โดยอนุญาตเฉพาะ
การใช้เดิมสามรายการข้างต้นในไฟล์ที่ระบุ พร้อมด่านพิสูจน์ว่าไม่ส่งคำขอเอง
และห้ามประกอบ URL ตลาดนอก transport · ไม่ยกเว้นทั้งไฟล์หรือทั้ง services
ปรับข้อ 6.4 และ V-32.1 ตามอนุมัติแล้วก่อนลงมือส่วนที่เหลือ

เดิมบล็อกการปิดข้อ 5 และการรับรอง RQ-16 · ผลตรวจล่าสุดอยู่ในบันทึก 2026-10-06

### ความคืบหน้า 2026-10-05 — ข้อ 6: รอบตรวจของ worker

**เสร็จส่วนซ่อมผลที่มาช้าและ audit ตามคำสั่งเจ้าของให้เริ่มข้อ 3** — ตามข้อ 7.2,
RQ-9 และ V-17/V-19/V-35 โดยไม่เปลี่ยนกฎที่อนุมัติ

ใช้ `expire_if_overdue` และ `EXPIRED_CODE` จาก
`backend/src/tiewtrade/infra/api_keys/claims.py` ซ้ำสำหรับผลที่มาถึงหลังเส้นตาย
ใช้ `_record`, `RoundSummary` และ transaction เดิมใน
`backend/src/tiewtrade/services/engine/verification.py` · ไม่เขียนกฎอายุใหม่
และไม่เปิด transaction คร่อมการเรียกตลาด

- ผลตลาดที่เขียนไม่ได้เพราะเลยอายุ 24 ชม. ต้องปิดแถวเป็น `REJECTED` +
  `VERIFICATION_EXPIRED`, ลบ secret/รุ่นกุญแจ/การจอง และลง audit ทันที
  ไม่ทิ้งแถวไว้รอ scan รอบหน้า · ทิ้งผลสำเร็จและผลล้มเหลวเหมือนกัน
- การหมดอายุก่อนเรียกตลาดลง audit ด้วยชนิดและรหัสเดียวกัน · ทั้งสองทางเขียน
  audit ใน transaction เดียวกับสถานะ · ถ้า audit ล้มเหลวต้อง rollback
- สรุปรอบตรวจนับการหมดอายุจริง และไม่นับผลที่เขียนไม่ได้เป็นตรวจผ่าน/เลื่อนไปก่อน
- เพิ่ม/ปรับเทสต์ใน `backend/tests/services/engine/test_verification.py`:
  ผลหลังเส้นตายสี่แบบ, audit และการไม่บันทึกซ้ำ, rollback ก่อน/หลังเรียกตลาด,
  ผล worker เก่าไม่เขียนทับ `ACTIVE` ของ worker ใหม่ทั้งก่อน/หลังเส้นตาย (V-22.2)
  · เทสต์ยืนยันปัญหา **7 กรณีแดงก่อนแก้**
- เทสต์ worker/ที่เก็บ key หลังแก้ **71 ข้อผ่าน** ก่อนเพิ่มสองกรณี worker เก่า
  · backend ทั้งชุดสุดท้าย **1,062 ข้อผ่าน, 1 ข้อไม่รัน (ตลาดจริง), warnings เดิม 3 รายการ**
  · ใช้ฐานข้อมูล PostgreSQL 16 ใน Docker ที่สร้างแยกพร้อมบทบาทจริงทั้ง 6
  · Ruff lint/format, mypy, import-linter และ `git diff --check` ผ่าน
- รีวิวแบบอ่านอย่างเดียวไม่พบข้อที่ต้องแก้เพิ่ม · ไม่ commit/push

บันทึกนี้รับรองเฉพาะส่วนซ่อมและเกณฑ์ที่ตรวจข้างต้น ไม่รับรอง validation ของ F-07
ทั้งฉบับ · ยังมีงาน API/หน้าเว็บ/ตรวจด้วยมือที่ต้องทำต่อ

NC-17 เดิมบล็อกการปิดด่านข้อ 5 / RQ-16 · ความคืบหน้าล่าสุดดูบันทึก 2026-10-06

### ความคืบหน้า 2026-10-05 — ข้อ 7: ข้อผิดพลาดของ API

**เสร็จส่วนซ่อมคำตอบ validation ตามคำสั่งเจ้าของข้อ 4** — ซ่อมคำตอบที่สะท้อน
ค่าดิบตาม RQ-5/RQ-9.2 และ V-4/V-7 โดยไม่เปลี่ยน schema ของข้อมูลเข้า

ใช้รหัส `ApiKeyError.code` จาก `backend/src/tiewtrade/infra/api_keys/records.py`
และ `APIRouter` เดิมใน `backend/src/tiewtrade/services/api/api_key_routes.py` ซ้ำ
จัดการ `RequestValidationError` ที่ขอบเขต router ของงานนี้ด้วย `APIRoute`
ของ FastAPI · คืน 422 พร้อมรหัสคงที่ ไม่คืน `input`, `msg`, `ctx` หรือ body
จาก exception · schema ของคำตอบ 422 ต้องตรงกับคำตอบจริง

เทสต์ใช้ `client`, `register`, `csrf_headers`, `enable_totp`, `code_now` เดิม
เพื่อเดิน HTTP, middleware, CSRF และการยืนยัน TOTP จริงก่อนถึง validation

- `backend/tests/api/test_api_key_routes.py` เพิ่ม 8 กรณี: key/secret ยาวเกิน,
  ชนิดข้อมูลผิดทั้งค่าตรงและค่าซ้อน, label ผิดชนิด, ขาด label, body ไม่ใช่ object,
  JSON ผิดรูป · ตรวจทั้งคำตอบ, log ระดับ DEBUG และไม่มี key ถูกบันทึก
  · ก่อนแก้เทสต์แดงทั้ง 8 กรณี (7 กรณีพบค่าดิบในคำตอบ อีกกรณีตรวจรูปคำตอบคงที่)
- หลังแก้เทสต์ API key/นโยบายเส้นทาง/ความลับ **29 ข้อผ่าน**
  · ตรวจ OpenAPI ที่สร้างจากแอปจริง: 422 ทั้งสี่เส้นทางมีเฉพาะ `detail: string`
- Backend ทั้งชุด **1,070 ข้อผ่าน, 1 ข้อไม่รัน (ตลาดจริง), warnings เดิม 3 รายการ**
  · PostgreSQL 16 ใน Docker ใช้ฐานข้อมูลทดสอบสร้างแยกพร้อมบทบาทจริงทั้ง 6
  · Ruff lint/format, mypy, import-linter และ `git diff --check` ผ่าน
- รีวิวแบบอ่านอย่างเดียวไม่พบข้อที่ต้องแก้เพิ่ม · ไม่ commit/push

งานนี้ไม่ปิด F-07 ทั้ง feature · การ sync OpenAPI snapshot/ชนิดหน้าบ้านและการตั้งค่า
สภาพแวดล้อมเป็นงานถัดไปในวันนั้น · ผลล่าสุดอยู่ในบันทึกด้านล่าง

### ความคืบหน้า 2026-10-05 — สัญญาและสภาพแวดล้อม (คำสั่งเจ้าของข้อ 5)

**เสร็จ · ตรวจหลังแก้ 2026-10-06** — ใช้ `backend/src/tiewtrade/services/api/openapi_export.py`
สร้าง `backend/openapi.json` และ `npm run gen:api` จาก `frontend/package.json`
สร้าง `frontend/src/api-types.ts` · ไม่แก้ไฟล์ที่สร้างด้วยมือ

เพิ่ม `TIEWTRADE_SEALING_KEY_VENUE_API_SECRET` ใน `compose.yaml` และ env ของ
job `backend`/`e2e` ใน `.github/workflows/ci.yml` ตามข้อ 5 ของแผน
ใช้รูปแบบและ `KeySource` เดิมจาก `backend/src/tiewtrade/infra/crypto/keys.py`
· ตัวอย่างกุญแจต้องยาว 32 ไบต์และต่างจาก TOTP · ใช้เฉพาะพัฒนา/CI

อัปเดต `README.md` ให้ตั้งกุญแจทั้งสองงานก่อนเปิด API และบอกวิธีรัน worker เดิม
`backend/src/tiewtrade/services/engine/main.py` ด้วยมือ · แหล่งกุญแจและตัวตั้งเวลา
บนเครื่องจริงยังเป็นงาน F-31 ไม่เพิ่ม service ใหม่ใน Compose

- สร้าง OpenAPI และชนิดหน้าบ้านซ้ำแล้วได้ไฟล์เดิมทุกไบต์ · มีเส้นทาง API key
  ครบทั้งสี่เมธอด พร้อม schema คำตอบ 422 ที่ปลอดภัย
- Frontend lint/typecheck ผ่าน · เทสต์ **14 ข้อผ่าน** รวมด่านสัญญาที่ต้องแดง
  เมื่อช่องที่หน้าบ้านใช้อยู่ถูกเปลี่ยนชื่อ
- ตรวจ YAML ของ Compose/CI, ความยาวกุญแจ 32 ไบต์และความต่างจาก TOTP
  และเปิด/ปิด lifespan ของ API ด้วย env ทั้งสามชุดจริงผ่าน · ไม่เรียกฐานข้อมูล
- `docker compose ... config --quiet` ผ่าน · backend Ruff lint/format,
  mypy, import-linter และเทสต์ crypto **20 ข้อผ่าน**
- รีวิวแบบอ่านอย่างเดียวไม่พบข้อที่ต้องแก้เพิ่ม · `git diff --check` ผ่าน
  · ไม่รัน backend ทั้งชุดหรือ e2e ซ้ำในงานนี้ เพราะไม่เปลี่ยน runtime Python/UI
  · ผล backend ทั้งชุดก่อนหน้านี้ 1,070 ข้อผ่านอยู่ในบันทึกข้อ 4

F-07 ยังไม่เสร็จ: หน้าจัดการ API key, การตรวจ validation ทั้งฉบับและ
ตรวจด้วย key ทดสอบจริงยังเหลือ · NC-17 ดูบันทึกถัดไป · ยังไม่ commit/push

### ความคืบหน้า 2026-10-06 — ปิดด่านข้อ 5 ตามคำตัดสิน NC-17

**เสร็จ · NC-17 ปิดทั้งคำตัดสินและการตรวจด่าน** — เจ้าของอนุมัติขอบเขตในบทสนทนา 2026-10-06
และปรับข้อ 6.4/V-32.1 ก่อนแก้ด่าน · ไม่เปลี่ยน runtime ของ production

- `backend/tests/money_movement.py` ตรวจ import และ URL ทั่ว `backend/src`
  ยกเว้น gateway ที่ราก adapter เท่านั้น · ข้อยกเว้น composition ตรวจทั้ง path,
  สมาชิกที่ import และการใช้งาน ไม่ยกเว้นทั้งไฟล์
- ใช้ `NETWORK_LIBRARIES` และตัวอ่าน `network_imports` จาก
  `backend/tests/venue_isolation.py` ร่วมกับด่านเดิม · ไม่สร้างรายการเครือข่ายชุดที่สอง
- client ต้องประกอบแล้วส่งเข้า venue ผ่าน helper ในโมดูลเดิม · ห้ามเรียกสมาชิก
  ของ client เอง, ส่งต่อออกผ่าน container/attribute/helper ภายนอก หรือคืน client
  · alias, type annotation และการส่งผ่าน helper รองรับในตัวตรวจ
- ไม่สับสน domain ของ blocklist, ชื่อไฟล์ หรือ `middleware("http")` กับ URL ตลาด
  · ตัวอย่าง URL ตรง/ประกอบ/BASE_URL นอก adapter และในไฟล์ที่ยกเว้นต้องแดง
- เพิ่มเทสต์ 26 กรณีใน `backend/tests/test_api_key_safety.py`
  (25 ตัวอย่างผิดแดงก่อนแก้ และตัวอย่าง composition ที่ถูกหนึ่งกรณี)
  · รีวิวพบสองช่อง: constructor เก็บใน attribute และ positional-only parameter
  · แก้แล้วพร้อมเทสต์ที่แดงก่อนแก้ · ตรวจซ้ำไม่พบข้อที่ต้องแก้เพิ่ม
- ด่านที่เกี่ยวข้อง **103 ข้อผ่าน** · Ruff lint/format, mypy และ import-linter ผ่าน
  · backend ทั้งชุด **1,096 ข้อผ่าน, 1 ข้อไม่รัน (ตลาดจริง), warnings เดิม 3 รายการ**
  บน PostgreSQL 16 ใน Docker พร้อมบทบาทจริงทั้ง 6 โดยสร้างฐานข้อมูลแยก
  และลบฐานข้อมูลทดสอบหลังตรวจเสร็จ · `git diff --check` ผ่าน

ผ่านส่วนด่าน V-32/V-32.1/V-32.2/V-33 ที่เกี่ยวข้องแล้ว · ไม่ปิด NC-16 และไม่เปิด Live
· F-07 ใน roadmap เป็น `In Progress` · งานถัดไปคือหน้าจัดการ API key,
ตรวจ validation ทั้งฉบับและตรวจด้วย key ทดสอบจริง · ยังไม่ commit/push

### ความคืบหน้า 2026-10-06 — ข้อ 8: หน้าจัดการ API key

**เสร็จส่วนหน้าจัดการ API key · 2026-10-06** — ใช้แบบข้อ 9 ที่อนุมัติแล้ว ไม่เพิ่มกฎการเทรด

- วาง `frontend/src/ApiKeyPanel.tsx` ในส่วนที่เข้าสู่ระบบของ `AuthPanel.tsx`
  โดยแยก cache ตามผู้ใช้และล้างเมื่อออกจากระบบ · ไม่เปลี่ยนหน้าจอ TOTP เดิม
- ใช้ชนิด `AddKeyRequest`, `KeyView`, `AddedKey`, `RetryAccepted` จาก
  `frontend/src/api-types.ts` และตัวส่งคำขอ/CSRF/TOTP เดิมใน `frontend/src/auth.ts`
  ซ้ำ · เพิ่ม GET/DELETE, การตอบ 204 และข้อมูล `Retry-After` ให้ตัวส่งเดิม
- `frontend/src/apiKeys.ts` เป็น adapter ของเส้นทางทั้งสี่ · ข้อมูล server อยู่ใน
  TanStack Query ตาม `tech-stack.md` และ `standards/frontend.md` ไม่เก็บซ้ำใน state
  · poll ทุก 5 วินาทีขณะหน้าจอเปิด ไม่ส่งซ้ำ mutation อัตโนมัติ
- secret/key/TOTP เป็นช่องกรอกที่ไม่ใส่ React state หรือ mutation variables
  · อ่านเฉพาะตอนส่ง และล้างทันทีทั้งกรณีสำเร็จ/ปฏิเสธ/เน็ตมีปัญหา
  · ไม่ใช้ localStorage/sessionStorage/cookie เพื่อเก็บค่าที่กรอก
- แสดงสี่สถานะ, 4 หลักท้าย, เวลารอจาก server และปุ่มลองใหม่เฉพาะ UNVERIFIABLE
  · ใช้ `may_retry` ของ server ห้ามข้ามเวลาที่ตลาดสั่งให้รอ · ลบหลังผู้ใช้ยืนยัน
- ใช้ i18next ตาม tech stack สำหรับข้อความใหม่ และ Intl สำหรับเวลา
  · ไม่มี TOTP ให้บอกทางไปเปิดที่ panel เดิม · คำเตือน RQ-6.3/RQ-17 แสดงถาวร
- ตรวจ unit/component tests ของ HTTP/header, ข้อผิดพลาด, polling, ความลับไม่ค้าง
  และ cache ไม่ข้ามผู้ใช้ · ตรวจ browser/e2e กับฐานข้อมูลทดสอบแยกและตลาดปลอม
  ไม่ยิงตลาดจริง · ไม่ commit/push

**ผลตรวจตาม requirements/validation ที่เกี่ยวข้อง:**

- `frontend/tests/ApiKeyPanel.test.tsx` **17 ข้อผ่าน** · 11 กรณีแรกแดงก่อนสร้าง
  หน้าจอ และเพิ่ม regression ของ stale confirmation/Retry-After ผิดรูปที่แดงก่อนแก้
  · ครอบ V-8, V-25, V-30.4, RQ-6.3/RQ-7.2/RQ-11.4/RQ-17
- Frontend ทั้งชุด **31 ข้อผ่าน** · lint, typecheck และ production build ผ่าน
  · ด่านสัญญาเดิมยังจับการเปลี่ยนช่องของ API ได้จริง
- Browser/e2e ทั้งชุด **7 ข้อผ่าน** รวมสองกรณีใหม่ใน
  `frontend/e2e/api-keys.spec.ts`: API/TOTP/CSRF จริง → worker เดิมกับ `FakeVenue`
  → UNVERIFIABLE → retry ไม่ส่ง TOTP → ACTIVE → delete → logout
  · อีกกรณีตรวจบัญชีไม่มี TOTP และทางไปเปิดบนมือถือ
- ใช้ helper TOTP เดิมจาก `frontend/e2e/totp.spec.ts` ย้ายไป
  `frontend/e2e/helpers/totp.ts` เพื่อใช้ร่วมกันโดยไม่คัดลอกสูตร
- ตรวจภาพ desktop และมือถือทั้งฟอร์ม/รายการ/บัญชีไม่มี TOTP · ไม่มี overflow
  · ภาพอยู่ใน `testInfo.outputPath()` ของ Playwright ใช้ได้ทั้งเครื่องและ Ubuntu CI
- CI e2e เพิ่ม URL ของ `engine`/`engine_scan` สำหรับ worker จริงคู่กับตลาดปลอม
  · ตรวจ YAML และ env ที่จำเป็นครบ · README บอกทางเข้าหน้าจอและการรัน worker
- รีวิวไม่พบ credential leak/auth regression · แก้ stale confirmation และ
  screenshot path ที่ผูกกับ macOS ตามผลรีวิวแล้ว พร้อมเทสต์ตรวจซ้ำ
- PostgreSQL 16 ใช้ฐานข้อมูลทดสอบแยก พร้อมบทบาทจริง · ล้างตัวนับเฉพาะฐานข้อมูล
  ทดสอบเมื่อรันซ้ำ ไม่ปิดกฎการคุมอัตรา · ลบฐานข้อมูลชั่วคราวหลังตรวจเสร็จ
  · `git diff --check` ผ่าน · ไม่แก้ runtime Python ในงานหน้าบ้านนี้

**ยังไม่ปิด F-07 ทั้ง feature** — ต้องตรวจ validation ทั้งฉบับและลอง key ทดสอบจริง
ของเจ้าของตามรายการตรวจด้วยมือ · ไม่มีการยิงตลาดจริงในงานนี้ · ยังไม่ commit/push

### ความคืบหน้า 2026-10-06 — ตรวจ validation ทั้งฉบับก่อน key จริง

**ยังไม่ผ่านครบ · หยุดก่อนแก้ code/spec ที่ขัดกันตาม AGENTS.md**

รายงาน: `specs/reviews/2026-10-06-api-keys-validation-audit.md`
· ทดสอบใหม่ backend **1,096 ข้อผ่าน**, frontend **31 ข้อผ่าน**, e2e **7 ข้อผ่าน**
· lint/format/type/import/build ผ่าน · ใช้ PostgreSQL 16 ฐานข้อมูลแยกพร้อมบทบาทจริง

ยืนยันโดยไม่เปลี่ยนโค้ดว่า scan อาจเลือกแต่แถวเก่าที่รอ backoff จนแถวใหม่ไม่ได้ตรวจ
และ `may_retry=True` แม้มี `not_before` ในอนาคต · กรณี market-wait 429 ไม่มี
Retry-After ใน source · พบ coverage gaps ของ startup/race/audit/property tests
ตามรายการในรายงาน ไม่ถือว่าผ่านเพราะเทสต์เดิมเขียว

**รอเจ้าของอนุมัติรายการซ่อมตาม spec และคำตัดสิน NC-18/NC-19**
ไม่เปลี่ยนโควตา RQ-11.5 ไม่เดาความหมายสิทธิ์ตลาด ไม่เก็บข้อมูลเงินจริงลง fixture
· ยังไม่ใช้ key จริง และไม่ได้อ่าน/ขอ key หรือ secret ผ่านแชต
· ลบฐานข้อมูล audit ชั่วคราวหลังตรวจ · ยังไม่ commit/push · F-07 ยัง In Progress

---

## 12. สิ่งที่งานนี้ไม่ทำ

ผูก key เข้ากระเป๋า (F-08) · ส่งออเดอร์ (F-16) · เปิด Live (F-24) ·
ตั้งเวลาเรียก worker บนเครื่องจริงและที่มาของกุญแจบนเครื่องจริง (F-31) ·
"key ถูกปฏิเสธ → หยุดบอท" (F-19/F-22) · ปิด NC-16

---

## 12.1 การเปลี่ยนแปลงที่ขออนุมัติแล้ว — ที่เก็บของถังคุมอัตรา

**เจ้าของอนุมัติ 2026-10-04** หลังพบตอนลงมือว่าแผนเดิมทำตามไม่ได้

ข้อ 7.4 และ 8 เขียนว่าถัง `API_KEY_ADD`/`API_KEY_RETRY` อยู่ "ที่เดียวกับถังอื่น"
ซึ่งหมายถึงตาราง `auth_throttle` ของ F-05 — **แต่ตารางนั้นให้สิทธิ์เฉพาะบทบาท
`tiewtrade_auth`** ส่วนเส้นทางของงานนี้รันบน `tiewtrade_api` จึงเขียนลงไปไม่ได้

| ทางเลือก | ผล |
|---|---|
| ก. เปิดให้ `tiewtrade_api` ใช้ `auth_throttle` ด้วย | ตรงตามถ้อยคำเดิมที่สุด **แลกกับ** บทบาทที่รับคำขอจากอินเทอร์เน็ตแตะตารางที่คุมการเดารหัสผ่านได้ — บั๊กฝั่ง `api` จะล้างโควตาการ login ได้ ซึ่งลบการคุมอัตราของ F-05 ทิ้งเงียบ ๆ |
| **ข. ตารางใหม่ `api_throttle` ของบทบาท `api` เท่านั้น** | **เลือกทางนี้** — `auth` ยังเป็นบทบาทเดียวที่แตะข้อมูลเข้าสู่ระบบตามที่ F-05 วางไว้ |

**ตรรกะ token bucket ไม่ถูกคัดลอก** — โค้ดเดิมของ `infra/auth/throttle.py` รับชื่อตาราง
เข้ามาเป็นพารามิเตอร์ แล้วทั้งสองที่เรียกตัวเดียวกัน (`AGENTS.md` หัวข้อ "ใช้ของเดิมซ้ำ")
· ที่แยกคือ **ที่เก็บกับสิทธิ์** ไม่ใช่ตรรกะ

---

## 12.2 การเปลี่ยนแปลงที่ขออนุมัติแล้ว — กุญแจของตารางกฎเส้นทาง

**เจ้าของอนุมัติ 2026-10-04** หลังพบตอนลงมือว่าแผนทำตามไม่ได้

ข้อ 8 วางเส้นทางไว้สี่เส้น โดยสองเส้นใช้ path เดียวกันคนละเมธอด (`POST /api-keys`
ต้องยืนยันซ้ำ · `GET /api-keys` เป็นการอ่านที่หน้าเว็บเรียกเป็นรอบ ๆ) **แต่ `ROUTE_RULES`
ของ F-06 ใช้ path เป็นกุญแจ** กฎที่เข้มกว่าจึงเหมารวมทั้งคู่ แล้วหน้าเว็บจะดูสถานะ
ไม่ได้ถ้าไม่กรอกรหัสทุกรอบ

**เลือก: เปลี่ยนกุญแจเป็น `(เมธอด, path)`** — ตรงกับความจริงว่าสิทธิ์ขึ้นกับเมธอดด้วย
และไม่แตะกลไกความปลอดภัยที่ F-05/F-06 วางไว้ (ค่าเริ่มต้นคือปฏิเสธ, เส้นทางที่ไม่มีแถว
ถูกปฏิเสธตอนรัน, รายการที่คำนวณจากตารางเดียว)

**ผลที่ตามมาซึ่งต้องทำไปด้วย:**

1. **ต้องหาแม่แบบของ path** เพราะ `/api-keys/{key_id}` มาถึงเป็นค่าจริงเสมอ
2. **เทียบแม่แบบเอง ไม่ถาม framework** — FastAPI รุ่นนี้ห่อ router ที่ `include_router`
   เข้ามาไว้ในตัวที่ไม่เปิดเผยแม่แบบข้างใน (ลองแล้วได้ `None`) การพึ่งโครงสร้างภายใน
   ของมันคือการพึ่งสิ่งที่เปลี่ยนได้ทุกรุ่นโดยไม่มีสัญญา · แม่แบบถูกคอมไพล์จาก
   **ตารางเดียวกัน** ไม่ใช่รายการที่สอง และเทสต์ที่เดินทุกเส้นทางของแอปยังตรวจอีกทิศ

---

## 13. การเปลี่ยนแปลงหลังอนุมัติ

ถ้าลงมือแล้วพบว่าทางที่วางไว้ผิด **ให้หยุดและขออนุมัติการเปลี่ยนก่อนแก้โค้ด**
ไม่ใช่เขียนโค้ดให้ต่างจากแผนแล้วค่อยบอก (บทเรียนจาก F-02)

### ความคืบหน้า 2026-10-06 — ซ่อม review ข้อ 1: credential ผิดรูปทำให้ worker ล้ม

เจ้าของสั่งแก้ข้อ 1 ในบทสนทนา · ขอบเขต RQ-13/V-7 ไม่เปลี่ยนกฎการเทรด
หรือโควตา · NC-18/NC-19 เกี่ยวกับงานอื่นและยังไม่ปิด

- ใช้ตัวตรวจ public identifier ร่วมกันใน `infra/api_keys/records.py` สำหรับ
  schema ของ `services/api/api_key_routes.py`, `infra/api_keys/storage.py` และ
  `services/engine/verification.py` · ตรวจความเข้ากันได้กับ HTTP header
  (ASCII ที่พิมพ์ได้) ไม่กำหนด alphabet หรือความยาว key ของตลาดขึ้นใหม่
  · คงการ trim และเพดานเดิม · ไม่จำกัด charset ของ secret ที่ใช้ HMAC
- ข้อมูลผิดรูปที่เก็บมาก่อน validation ใช้เส้นทาง VENUE_PROTOCOL/UNVERIFIABLE
  และ audit เดิม เก็บ secret จนถึงเพดาน 24 ชม. ไม่เรียกตลาดด้วยแถวนั้น
  และตรวจแถวถัดไปต่อได้ · ไม่จับ Exception กว้างเพื่อซ่อนบั๊กอื่น
- เพิ่ม regression ที่ HTTP ปฏิเสธโดยไม่สะท้อน credential และทดสอบ worker
  บนฐานข้อมูลแยกด้วยข้อมูลเก่าผิดรูปคู่กับ key ปกติของอีกผู้ใช้

สถานะ: **ซ่อม review ข้อ 1 เสร็จ** · F-07 ยัง In Progress · ไม่ commit/push

ผลตรวจ:
- regression ของ schema/worker แดงก่อนแก้ · หลังแก้ API/storage/worker
  ชุดที่เกี่ยวข้องผ่าน 101 ข้อ แล้วเพิ่มการตรวจ storage ก่อนเข้าฐานข้อมูล 4 ข้อ
- backend ทั้งชุด **1,107 passed, 1 deselected (ตลาดจริง), warnings เดิม 3 รายการ**
  · ใช้ PostgreSQL 16 ฐานข้อมูลทดสอบแยกพร้อมบทบาทจริงทั้ง 6
- Ruff lint/format, mypy (src/tests) และ import-linter ผ่าน
  · OpenAPI เปรียบเทียบกับ schema ปัจจุบันตรงทุกไบต์ ไม่ต้องเปลี่ยนชนิดหน้าบ้าน
- รีวิวอิสระแบบอ่านอย่างเดียวไม่พบปัญหาใหม่ที่บล็อกข้อ 1
  · ยืนยัน RQ-13/V-7 เฉพาะ malformed public identifier; ไม่ปิด validation ทั้ง F-07
- ลบฐานข้อมูลทดสอบแยกหลังตรวจ · ไม่ยิงตลาดจริง ไม่แตะฐานข้อมูลเดิม
  · review ข้อ 2–9 และ NC-18/NC-19 ยังเหลือ

### ความคืบหน้า 2026-10-06 — ซ่อม review ข้อ 2: การปฏิเสธที่ยังไม่ทราบสาเหตุ

เจ้าของสั่งแก้ข้อ 2 · ตรวจยืนยันว่า `_PERMANENT` ใน
`services/engine/verification.py` รวม `VenueRejectedError` ซึ่งครอบ WAF,
timestamp และรหัสที่ไม่รู้จัก แล้วลบ secret ทั้งที่ไม่ใช่การพิสูจน์ว่าคำรับรองผิด

**หยุดก่อนแก้ runtime — NC-20:** F-35 plan §1.1 และ `venues/errors.py`
กำหนดว่า `UNEXPLAINED` ห้ามส่งซ้ำอัตโนมัติ แต่เส้นทาง `mark_deferred` ของ F-07
ตั้ง backoff และ retry อัตโนมัติ · การเอาชนิดนี้ออกจาก `_PERMANENT` อย่างเดียว
จะเปลี่ยนนโยบาย retry ที่อนุมัติไว้โดยเงียบ ๆ

ผลที่ต้องได้ทั้งสองทาง: UNVERIFIABLE + secret ยังอยู่ตามอายุเดิม 24 ชม.
+ audit ใน transaction เดียว + ERROR แจ้งผู้ดูแลโดยใช้ id/รหัสคงที่
· ใช้ `infra/api_keys/claims.py`, `infra/audit` และตัวแปลชนิด venue เดิมซ้ำ
· credential rejection ที่พิสูจน์แล้วต้องยัง REJECTED และลบ secret

ทางเลือกที่ต้องตัดสินก่อนแก้:
- คงกฎเดิม: ไม่ retry อัตโนมัติเมื่อถูกปฏิเสธโดยไม่ทราบสาเหตุ
  แต่ให้ผู้ใช้กดลองใหม่ภายใต้โควตา/market wait เดิม และยังเก็บกวาดเมื่อหมดอายุ
- อนุมัติข้อยกเว้นเฉพาะการอ่านตรวจ key: ใช้ backoff/เพดานเดิมอัตโนมัติ
  ตามแนวทางการตรวจ protocol ของ F-07 · ไม่ขยายไปถึงส่ง/ยกเลิกออเดอร์

ยังไม่แก้ code/test · F-07 ยัง In Progress · ไม่ commit/push

### คำตัดสิน NC-20 — เจ้าของอนุมัติ 2026-10-06 ก่อนแก้ code

เลือกข้อ 1: คงกฎไม่ส่งซ้ำอัตโนมัติสำหรับการปฏิเสธที่ไม่พิสูจน์ว่า key ผิด
· เส้นทางตรวจ key รับ `VenueRejectedError` เป็น UNVERIFIABLE/VENUE_REJECTED
และ ERROR แจ้งผู้ดูแล เก็บ secret ตามอายุเดิม 24 ชม.

ใช้ `infra/api_keys/claims.py` และ `services/engine/verification.py` เดิมซ้ำ:
`mark_deferred` รับการเลือก automatic retry จาก worker · กรณี manual-only
ไม่ตั้ง next_attempt_at และคำสั่ง claim ต้องบังคับให้มี retry_requested_at
ที่ใหม่กว่า last_attempt_at (NULL ของ next_attempt_at ไม่ใช่สิทธิ์ยิงอัตโนมัติ)
· expiry ยังตรวจได้ตามเดิม ไม่เพิ่มคอลัมน์/สิทธิ์ · ไม่เพิ่ม quota
· `frontend/src/ApiKeyPanel.tsx`/`apiKeyMessages.ts` แสดงว่าต้องกดลองใหม่เอง

validation ที่ต้องพิสูจน์ก่อนปิดข้อ 2: WAF/timestamp/รหัสไม่รู้จักผ่าน transport
จริงคู่กับ MockTransport → secret ยังอยู่ + audit/error ปลอดภัย
→ รอบอัตโนมัติไม่เรียกตลาด แม้ next_attempt_at เก่า → manual retry เรียกได้
→ สำเร็จ ACTIVE · กรณีไม่กดจนหมด 24 ชม. ต้องลบ secret
· credential rejection ที่พิสูจน์แล้วต้องยังลบทันที

สถานะ: **ซ่อม review ข้อ 2 เสร็จ** · F-07 ยัง In Progress

เพิ่มเติมก่อนแก้ schema: เทสต์จริงพบ CHECK audit ใน 0009 ผูก VENUE_REJECTED
กับเหตุการณ์ REJECTED เท่านั้น · เพิ่ม `migrations/versions/0011_deferred_rejection.py`
เพื่อรับคู่ API_KEY_VERIFICATION_DEFERRED/FAILED/VENUE_REJECTED
โดยใช้ snapshot รูป audit เดิมและขยายเฉพาะรหัสนี้ · คงคู่ REJECTED เดิม
สำหรับประวัติที่แก้ย้อนหลังไม่ได้ · downgrade ใช้ NOT VALID ตามแบบ 0009
ไม่แก้ migration เดิม ไม่เพิ่มคอลัมน์หรือสิทธิ์

รีวิวพบ edge case ที่ต้องรักษา V-22.3: เมื่อ manual request เริ่มแล้ว worker
ตายก่อนเขียนผล การคืนงานหลัง lease หมดอายุคือการคืนงานที่ได้รับอนุญาตแล้ว
ไม่ใช่การสร้าง retry ใหม่ · เงื่อนไข claim จึงรับ pending manual request
หรือ lease เดิมที่หมดอายุ · ผล rejection ที่เขียนเสร็จปลด lease เป็น NULL
จึงยังไม่เรียกเอง · เพิ่ม regression ของการคืนงานนี้ก่อนแก้เงื่อนไข

ผลตรวจ review ข้อ 2 (2026-10-06):
- Backend **1,112 passed, 1 deselected (ตลาดจริง), warnings เดิม 3 รายการ**
  · regression WAF/timestamp/unknown/expiry แดงก่อนแก้ และ regression
  การคืนงาน manual หลัง worker ตายแดงก่อนแก้ตามผลรีวิว
- Frontend **32 passed** · regression ข้อความ manual-only แดงก่อนแก้
  · lint/typecheck/build ผ่าน · e2e ทั้งชุด **7 passed**
- Ruff lint/format รวม migration, mypy src/tests และ import-linter ผ่าน
  · OpenAPI ตรงทุกไบต์ ไม่ต้องเปลี่ยนชนิด API
- downgrade 0011 → 0010 → upgrade head หลังมี audit แบบใหม่ผ่าน
  · ใช้ NOT VALID เพื่อเก็บประวัติเดิม ไม่แก้/ลบ audit
- รีวิวอิสระพบกรณี worker ตายและแก้แล้ว ตรวจซ้ำไม่มีข้อที่บล็อกข้อ 2
- ตรวจ RQ-7.3/V-15.1/V-14/V-17/V-22.3 และ transaction/audit ที่เกี่ยวข้อง
  · PostgreSQL 16 ฐานข้อมูลแยกพร้อมบทบาทจริง · ไม่ยิงตลาดจริง
  · ลบฐานข้อมูลทดสอบเมื่อจบ · ไม่รัน migration บนฐานข้อมูลใช้งานเดิม
- NC-20 ปิดแล้ว · review ข้อ 3–9 และ NC-18/NC-19 ยังเหลือ
  · F-07 ยัง In Progress · ไม่ commit/push

### ความคืบหน้า 2026-10-06 — ซ่อม review ข้อ 3: แถวรอบัง batch

เจ้าของสั่งแก้ข้อ 3 · ใช้ SQL eligibility ของ `infra/api_keys/claims.py`
ร่วมกันสำหรับ scan/claim · scan ยังเป็น hint และ atomic UPDATE ต้องตรวจซ้ำ
· แถวหมดอายุถูกเลือกได้โดยไม่ติด backoff/market wait/live lease/manual-only
· ใช้คอลัมน์เดิมที่ engine_scan อ่านได้ ไม่เพิ่มสิทธิ์หรืออ่าน failure_code/secret

สถานะ schedule เดิมที่ใช้ซ้ำ: next_attempt_at เป็นรอบอัตโนมัติที่บันทึกไว้
· แถวที่ยังไม่เคยเริ่ม (last_attempt_at NULL) ตรวจครั้งแรกได้
· next_attempt_at NULL หลังเริ่มแล้วหมายถึงไม่มีรอบอัตโนมัติ (NC-20)
· retry_requested_at ใหม่หรือ lease เดิมหมดอายุเปิดทางให้ manual/คืนงานเดิม
· claim คง guard VENUE_REJECTED เป็นด่านสุดท้ายอีกชั้น

เพิ่มเทสต์ batch เต็มด้วย backoff/market wait/live lease/manual-only
คู่กับ PENDING ใหม่และแถวหมดอายุ รวมทดสอบ default batch 100 แถว
· ยืนยันใหม่ถูกตรวจและ expired ถูกลบ secret โดยไม่เรียกตลาดด้วยแถวรอ
· ไม่เปลี่ยน backoff/โควตา/เพดาน 24 ชม. · ไม่แก้ review ข้อ 4–9

สถานะ: **ซ่อม review ข้อ 3 เสร็จ** · F-07 ยัง In Progress · ไม่ commit/push

ผลตรวจ review ข้อ 3 (2026-10-06):
- เทสต์ batch ที่รอทั้งสี่ชนิดและ default 100 แถว **5 กรณีแดงก่อนแก้**
  · หลังแก้ใหม่ถูกตรวจ expired ลบ secret/audit โดยไม่เรียกตลาดด้วยแถวรอ
- เพิ่ม stale-hint regression ทั้งสี่ชนิด ยืนยัน atomic claim ไม่ข้ามเงื่อนไข
  · ปรับ assertion เดิมของ live lease จาก skipped=1 เป็นไม่ถูก scan (skipped=0)
  และยืนยันไม่มี market call เพิ่ม · ไม่เปลี่ยนพฤติกรรมการคืน lease หมดอายุ
- worker/storage ชุดที่เกี่ยวข้อง **94 passed**
  · backend ทั้งชุด **1,121 passed, 1 deselected (ตลาดจริง), warnings เดิม 3 รายการ**
- Ruff lint/format รวม migration, mypy src/tests และ import-linter ผ่าน
  · รีวิวอิสระไม่พบข้อที่บล็อก · git diff --check ผ่าน
- ตรวจ V-22.7/เงื่อนไข claim, V-17/expiry, NC-20/manual-only และคืนงานเดิม
  · PostgreSQL 16 ฐานข้อมูลแยกพร้อมบทบาทจริงทั้ง 6 · ลบฐานข้อมูลทดสอบเมื่อจบ
  · ไม่เพิ่ม privilege หรือ migration ไม่แตะฐานข้อมูลใช้งาน ไม่ยิงตลาดจริง
- ไม่รัน frontend/e2e ซ้ำ: งานนี้เปลี่ยนเฉพาะ scan/claim กับ backend tests
  · ไม่เปลี่ยน API schema หรือ UI · ผล frontend/e2e ล่าสุดอยู่ในบันทึกข้อ 2
- review ข้อ 4–9 และ NC-18/NC-19 ยังเหลือ · F-07 ยัง In Progress
  · ไม่ commit/push

### ความคืบหน้า 2026-10-06 — ซ่อม review ข้อ 4: อายุของตัวนับโควตา IP

เจ้าของสั่งแก้ข้อ 4 · ใช้ `venues/binance_th/rate_limit.py::IpWeightLimiter`,
`transport.py::BinanceThTransport` และ `wallets.py::BinanceThWallet` เดิมซ้ำ
· ไม่เปลี่ยนต้นทุน endpoint/เพดานตลาด ไม่เพิ่มตัวนับอีกชุด

เปลี่ยน composition ของ `venues/__init__.py` เป็น `live_wallet_factory`
ที่สร้าง transport/limiter ครั้งเดียวแล้วรับ signer เพื่อสร้าง wallet แต่ละใบ
· `services/engine/main.py` สร้าง factory ก่อน while และใช้ตัวเดิมทุก key/ทุกรอบ
· signer ยังแยกใบ ไม่มี secret ใน factory/limiter
· factory ใช้ clock/timeout ที่ระบุชนิดได้ ไม่ให้ engine รู้จักชื่อตลาด
· ปรับด่าน composition `tests/money_movement.py` และ positive fixture
ให้รู้จักชื่อ factory ใหม่ โดยยังส่ง client ได้เฉพาะเข้าชั้น venues ตาม NC-17
ไม่เพิ่มข้อยกเว้นเครือข่ายหรือทางเรียกออกใหม่

เพิ่ม regression ผ่าน MockTransport: ใช้โควตาสะสมข้าม key, header ยอดเต็ม
กั้น key ใบถัดไป, ครบหน้าต่างเวลาแล้วเรียกได้ และยอดอยู่ข้าม serve loop rounds
· เทสต์อัตโนมัติไม่ยิงตลาด · ขอบเขตตัวนับยังหนึ่ง process ตาม F-35
การรวมโควตาข้าม process ยังเป็นงานก่อนปล่อยผู้ใช้จริง ไม่สร้าง Redis ในงานนี้

สถานะ: **ซ่อม review ข้อ 4 เสร็จ** · F-07 ยัง In Progress · ไม่ commit/push

ผลตรวจ review ข้อ 4 (2026-10-06):
- regression **3 กรณีแดงก่อนแก้**: header เต็มกั้น key ใบถัดไป,
  น้ำหนักสะสมเมื่อไม่มี header และ actual serve loop ไม่ล้างยอดข้ามรอบ
  · หลังแก้ผ่าน พร้อมคืนโควตาที่ครบหนึ่งนาที และ header ตรง signer แต่ละใบ
- venue/gates ชุดที่เกี่ยวข้อง **244 passed**
  · backend ทั้งชุด **1,124 passed, 1 deselected (ตลาดจริง), warnings เดิม 3 รายการ**
- Ruff lint/format รวม migration, mypy src/tests (**181 files**)
  และ import-linter ผ่าน · WalletFactory รับ signer แบบ positional ตามจุดเรียก
  เพื่อให้เข้ากับ Callable โดยไม่ใช้ type-ignore ของ factory เดิม
- รีวิวอิสระไม่พบข้อที่บล็อก · factory ไม่ถือ/เก็บ signer ของผู้ใช้
  · guard reserve ไม่มี suspension point ระหว่างตรวจและจองโควตา
  · ด่าน composition คงขอบเขตเดิม เปลี่ยนชื่อ factory ที่รับ client เท่านั้น
- ตรวจ V-38.1, RQ-16/ขอบเขตเครือข่าย, RQ-2/RQ-5/คำรับรองแยกใบ
  · PostgreSQL 16 ฐานข้อมูลแยกพร้อมบทบาทจริงทั้ง 6 · ลบฐานข้อมูลทดสอบเมื่อจบ
  · ไม่ยิงตลาดจริง ไม่แตะฐานข้อมูลใช้งาน ไม่มี migration ใหม่ในงานนี้
- ไม่รัน frontend/e2e ซ้ำ: ไม่เปลี่ยน UI/API schema และ lifecycle/transport
  ที่ FakeVenue ของ e2e ไม่ตรวจ ถูกทดสอบตรงผ่าน MockTransport/actual serve loop
- review ข้อ 5–9 และ NC-18/NC-19 ยังเหลือ · F-07 ยัง In Progress
  · ข้อจำกัดตัวนับข้าม process ของ F-35 ยังเหมือนเดิม · ไม่ commit/push

### ความคืบหน้า 2026-10-06 — ซ่อม review ข้อ 5: may_retry กับ market wait

เจ้าของสั่งแก้ข้อ 5 · ใช้เงื่อนไข status/not_before/clock_timestamp เดิม
ของ `_REQUEST_RETRY` ใน `infra/api_keys/storage.py` ร่วมกับ query summaries
· `infra/api_keys/records.py::ApiKeySummary` รับ may_retry ที่ฐานข้อมูลคำนวณ
ไม่อ่านนาฬิกา process/browser · default False เพื่อไม่เปิดสิทธิ์จาก DTO ที่ไม่ผ่าน query
· ใช้ `services/api/api_key_routes.py::_view` และ UI disabled guard เดิม
· ไม่เปลี่ยนโควตา, อายุ key, backoff หรือข้อความ/header ของ issue 6

เพิ่ม HTTP tests ด้วยบทบาทจริง: UNVERIFIABLE ที่ not_before เป็น NULL/อนาคต/
เวลาปัจจุบัน/อดีต, สถานะอื่นต้อง False และนาฬิกา process เร็ว/ช้าไม่เปลี่ยนผล
· ไม่รอเวลาจริง ใช้เวลา database ใน test setup · ไม่เพิ่มคอลัมน์หรือสิทธิ์

สถานะ: **ซ่อม review ข้อ 5 เสร็จ** · F-07 ยัง In Progress · ไม่ commit/push

ผลตรวจ review ข้อ 5 (2026-10-06):
- HTTP regression อนาคต **2 กรณีแดงก่อนแก้** (process clock เร็ว/ช้า 20 ปี)
  · หลังแก้ทั้ง 11 กรณีของ flag ผ่าน: NULL/now/past/future และสถานะอื่น
  · API/storage ชุดที่เกี่ยวข้อง **90 passed**
- backend ทั้งชุด **1,135 passed, 1 deselected (ตลาดจริง), warnings เดิม 3 รายการ**
  · frontend **32 passed** รวมปุ่ม retry ที่ disabled ตาม server flag
  · e2e เดิมทั้งชุด **7 passed** ตรวจความเข้ากันได้ของ UI/API/worker
- Ruff lint/format รวม migration, mypy src/tests, import-linter ผ่าน
  · frontend lint/typecheck ผ่าน · OpenAPI ตรงทุกไบต์ ไม่เปลี่ยน API schema
- รีวิวอิสระไม่พบข้อที่บล็อก · SQL ให้ boolean ชัดเจนแม้ not_before เป็น NULL
  · query/UPDATE ใช้ predicate เดียวกันและเวลา DB · endpoint ยังบังคับซ้ำ
- ตรวจ RQ-11.4/V-30.5.1 ด้วยบทบาทจริง PostgreSQL 16 ฐานข้อมูลแยก
  · ไม่เพิ่ม privilege/migration ไม่แตะฐานข้อมูลใช้งาน ไม่ยิงตลาดจริง
  · ลบฐานข้อมูลทดสอบเมื่อจบ · git diff --check ผ่าน
- review ข้อ 6–9 และ NC-18/NC-19 ยังเหลือ · F-07 ยัง In Progress
  · ไม่ commit/push

### ความคืบหน้า 2026-10-06 — ซ่อม review ข้อ 6: market-wait Retry-After

เจ้าของสั่งแก้ข้อ 6 · ใช้ `request_retry`/not_before จาก DB, `_as_text`
และตัวอ่าน Retry-After ของ `frontend/src/auth.ts` เดิมซ้ำ
· ส่ง header เป็น HTTP-date UTC จาก not_before ไม่ใช่คำนวณระยะรอด้วยนาฬิกา process
· HTTP-date มีความละเอียดหนึ่งวินาที จึงปัดขึ้นเมื่อมี microsecond
เพื่อไม่บอกให้ลองก่อนเส้นตาย · ไม่เดาเวลาเมื่อ race ทำให้ไม่มี not_before
กรณีข้อมูลรอไม่ครบตอบ conflict 409 ให้ดึงสถานะใหม่ ตามเส้นทาง conflict เดิม

ใช้ `_set_retry_view_state` ใน `tests/api/test_api_key_routes.py` ซ้ำ
ทดสอบ endpoint ด้วย API role จริงและโควตาที่ยังเหลือ: header parse ได้
ไม่เร็วกว่า not_before, process clock เร็ว/ช้าไม่เปลี่ยนผล
และ retry_requested_at/attempts ไม่เปลี่ยนเมื่อถูกปฏิเสธ
· คงโควตาและ worker guard เดิม · ไม่มีงานส่งถึงตลาดจากคำขอที่ถูกปฏิเสธ

สถานะ: **ซ่อม review ข้อ 6 เสร็จ** · F-07 ยัง In Progress · ไม่ commit/push

รีวิวข้อ 6 พบ race ที่เกี่ยวกับ header โดยตรง: worker เปลี่ยน not_before หลัง
SELECT แรก ก่อน UPDATE ที่ถูกปฏิเสธ · ต้องอ่าน target ปัจจุบันอีกครั้งเมื่อ UPDATE
ไม่สำเร็จ และใช้ `_RETRY_ELIGIBILITY` เดิมให้ DB ตัดสินเวลาของ snapshot ล่าสุด
· key ถูกลบตอบ 404, สถานะเปลี่ยนหรือกลับมาถึงเวลาแล้วตอบ conflict 409
· กรณีตลาดยังสั่งรอตอบ 429 ด้วย deadline ล่าสุด · ไม่ลอง UPDATE ซ้ำเอง
เพิ่ม regression ที่เปลี่ยนแถวด้วยบทบาทจริงระหว่าง SELECT/UPDATE ก่อนแก้

ผลตรวจ review ข้อ 6 (2026-10-06):
- HTTP regression **3 กรณีแดงก่อนแก้**: ไม่มี header ทั้ง clock เร็ว/ช้า
  และข้อมูลรอที่ไม่มีเวลาต้องไม่เดา delay
- รีวิวพบ stale deadline ระหว่าง SELECT/UPDATE · เพิ่ม regression ด้วย
  การเปลี่ยนข้อมูลจากบทบาทจริง **3 กรณีแดงก่อนแก้** (market wait ใหม่/ACTIVE/ลบ)
  · แก้ให้ re-read ก่อนเลือก HTTP status/deadline และไม่ลอง mutation ซ้ำ
- API/storage ชุดที่เกี่ยวข้อง **96 passed**
  · backend ทั้งชุด **1,141 passed, 1 deselected (ตลาดจริง), warnings เดิม 3 รายการ**
- frontend **33 passed** รวม HTTP-date → UTC ISO ผ่าน adapter และตัด raw error
  · lint/typecheck ผ่าน · e2e เดิมทั้งชุด **7 passed**
- Ruff lint/format รวม migration, mypy src/tests และ import-linter ผ่าน
  · OpenAPI ตรงทุกไบต์ ไม่เปลี่ยนชนิด API
- รีวิวซ้ำไม่พบข้อที่บล็อก · ตรวจ V-30.4/V-30.4.1/V-31.3 และ no enqueue
  · HTTP-date GMT ปัดขึ้นไม่เกินหนึ่งวินาทีจาก deadline ปัจจุบันของ DB
- PostgreSQL 16 ฐานข้อมูลแยกพร้อมบทบาทจริง · ลบฐานข้อมูลทดสอบเมื่อจบ
  · ไม่เพิ่ม privilege/migration ไม่แตะฐานข้อมูลใช้งาน ไม่ยิงตลาดจริง
  · git diff --check ผ่าน · ไม่ commit/push
- review ข้อ 7–9 และ NC-18/NC-19 ยังเหลือ · F-07 ยัง In Progress

### ความคืบหน้า 2026-10-06 — ซ่อม review ข้อ 7: ชื่อ key ซ้ำต้องเป็น 409

เจ้าของสั่งแก้ข้อ 7 · ใช้ `infra/db/errors.py::DuplicateValueError` และรหัส
`DUPLICATE_VALUE` เดิมซ้ำ ตามรูปแบบการจับ unique violation ของ auth_routes
· `services/api/api_key_routes.py::add_key` จับเฉพาะชนิดนี้จาก store_key
แล้วตอบ 409 รหัสคงที่ ไม่ส่งข้อความ SQL/constraint/ค่าที่กรอก
· ไม่ pre-check ชื่อก่อน INSERT ไม่เปลี่ยน unique index/user scope
· transaction ของ key rollback แต่ถัง quota ที่ commit แยกยังนับครั้งที่กด

ใช้ `_seed_keys`, `enable_totp`, `csrf_headers` และการอ่านผ่าน UserSession เดิมซ้ำ
HTTP regression ชื่อซ้ำและชื่อที่ trim แล้วซ้ำด้วย TOTP จริง → 409
· รายการเดิมไม่เปลี่ยน ไม่มี key เพิ่ม/ไม่มี audit เพิ่มสำเร็จ และ quota ลดหนึ่ง
· ข้อผิดพลาด/log ไม่พา key/secret/label ที่กรอก · UI ใช้ conflict branch เดิม

สถานะ: **ซ่อม review ข้อ 7 เสร็จ** · F-07 ยัง In Progress · ไม่ commit/push

ผลตรวจ review ข้อ 7 (2026-10-06):
- HTTP regression ชื่อซ้ำตรง/trim **2 กรณีแดงก่อนแก้** ด้วย unique violation
  จริง · หลังแก้ตอบ 409/DUPLICATE_VALUE, รายการเดิมเหมือนเดิม
  · ไม่มี audit API_KEY_ADDED/SUCCEEDED เพิ่ม · quota ลดหนึ่งตาม RQ-11.2
  · response/log ระดับ DEBUG ไม่มี key/secret/label ที่กรอก
- API/storage ชุดที่เกี่ยวข้อง **98 passed**
  · backend ทั้งชุด **1,143 passed, 1 deselected (ตลาดจริง), warnings เดิม 3 รายการ**
- frontend **34 passed** รวม conflict 409 ล้าง credential/ไม่แสดง error ดิบ
  · frontend lint/typecheck ผ่าน · e2e เดิมทั้งชุด **7 passed**
- Ruff lint/format รวม migration, mypy src/tests และ import-linter ผ่าน
  · OpenAPI ตรงทุกไบต์ ไม่เปลี่ยนชนิด API · git diff --check ผ่าน
- รีวิวอิสระไม่พบข้อที่บล็อก · catch อยู่เฉพาะ store_key ไม่เหมารวม audit error
  · key transaction rollback ส่วน quota commit แยกตามแบบเดิม
- ตรวจ V-7/V-31/V-31.0.1 และ RQ-11.2 · PostgreSQL 16 ฐานข้อมูลแยก
  · ไม่เพิ่ม privilege/migration ไม่แตะฐานข้อมูลใช้งาน ไม่ยิงตลาดจริง
  · ลบฐานข้อมูลทดสอบเมื่อจบ · ไม่ commit/push
- review ข้อ 8–9 และ NC-18/NC-19 ยังเหลือ · F-07 ยัง In Progress

### ความคืบหน้า 2026-10-06 — ซ่อม review ข้อ 8: asyncio network gate

เจ้าของสั่งแก้ข้อ 8 · ใช้ `tests/venue_isolation.py::code_nodes`, Violation
และ boundary walkers เดิมซ้ำ · เพิ่มตัวตรวจสมาชิก asyncio ที่แตะเครือข่าย
ใน utility เดียวให้ `check_network_only_in` และ `money_movement.check_network_boundary`
ใช้ร่วมกัน · ไม่ใส่ asyncio ใน denylist import ทั้งโมดูล

ครอบ direct/alias/from-import/submodule, connection/server/Unix socket,
loop TCP/UDP/DNS/TLS/socket I/O, loop getters/annotations/aliases/local helpers
และ Runner/policy.get_loop/get_event_loop · ด่านจับ references ด้วย ไม่ใช่เฉพาะ calls
· wildcard import ไม่เปิดสมาชิกเครือข่ายโดยไม่ตรวจ
· run/sleep/gather/create_task/call_soon และสมาชิกของ object อื่นยังใช้ได้
· transport gateway ที่ราก adapter ยังเป็นข้อยกเว้นเดิม ไม่ยกเว้น nested transport

เพิ่ม negative/positive AST fixtures แบบไม่ execute ทั้ง global/adapter boundaries
ก่อนแก้ · ไม่แก้ production/network endpoints · คง NC-17/RQ-16/V-32.1

สถานะ: **ซ่อม review ข้อ 8 เสร็จ** · F-07 ยัง In Progress · ไม่ commit/push

ผลตรวจ review ข้อ 8 (2026-10-06):
- negative fixtures **54 กรณีแดงก่อนแก้** (18 รูป × 3 boundary paths)
  · รีวิว/ตรวจเพิ่มพบ bound getter และ alias ของ local helper
  · เพิ่ม **9 กรณีแดงก่อนแก้** พร้อม scheduling-only positive counterpart
- ใหม่ทั้งหมด **64 passed** รวม positive ที่ scheduling/unrelated objects
  และ gateway ยังใช้ได้ · ชุดด่านที่เกี่ยวข้อง **167 passed**
- backend ทั้งชุด **1,207 passed, 1 deselected (ตลาดจริง), warnings เดิม 3 รายการ**
  · PostgreSQL 16 ฐานข้อมูลแยกพร้อมบทบาทจริงทั้ง 6
- Ruff lint/format รวม migration, mypy src/tests (**182 files**) และ import-linter ผ่าน
  · binding maps เพิ่มได้จำกัดตาม source จึงจบแน่นอน
  · helper return ไม่รวม return ของ nested functions/classes เพื่อกัน false positives
- รีวิวซ้ำไม่พบข้อที่บล็อก · ตัวตรวจ asyncio อยู่ที่เดียวใช้ร่วมสองด่าน
  · ไม่เพิ่ม asyncio ใน NETWORK_LIBRARIES ที่ห้าม import ทั้งโมดูล
- ตรวจ RQ-16/V-32.1/V-32.1.1 และ NC-17 · ไม่ execute source/network fixtures
  · ไม่แก้ production ไม่แตะฐานข้อมูลใช้งาน ไม่ยิงตลาดจริง
  · ลบฐานข้อมูลทดสอบเมื่อจบ · git diff --check ผ่าน · ไม่ commit/push
- ไม่รัน frontend/e2e ซ้ำเพราะเปลี่ยนเฉพาะ backend gates/tests
  · review ข้อ 9 และ NC-18/NC-19 ยังเหลือ · F-07 ยัง In Progress

### ความคืบหน้า 2026-10-06 — ซ่อม review ข้อ 9: เทสต์ที่ไม่พิสูจน์เกณฑ์

เจ้าของสั่งแก้ข้อ 9 ตามสี่รายการที่พบ · ไม่เปลี่ยนกฎ runtime/โควตา/อายุ key
· requirements/plan/validation Approved และ NC-18/NC-19 ไม่บล็อกการเติม
หลักฐานสี่ส่วนนี้ แต่ยังบล็อกการรับรองเพดาน ~30/RQ-6/V-39 ของ F-07

ใช้ `_seed_keys`, `_set_retry_view_state`, UserSession, ScriptedWallet, claim,
`verification._write`, `as_structure_owner` และ audit helpers เดิมซ้ำ:
- V-30.2: seed UNVERIFIABLE ที่ถึงเวลา ให้ HTTP retry **202** จนครบ quota
  แล้ว 429 ไม่ใช้ PENDING/409 เป็นหลักฐานของ successful request
- V-16: เทสต์ log รอบ unavailable ต้องทำให้ถึงคิวด้วย request_retry
  และ assert market.calls เพิ่ม/ผล deferred ไม่ตรวจ empty log จาก skipped round
- V-19.2: claim ก่อน แล้วเปิด completion transaction · อ่าน transaction_timestamp
  ตั้ง created_at ให้ deadline อยู่หลัง transaction start 1 microsecond
  และพิสูจน์ว่า clock_timestamp ผ่าน deadline ก่อน `_write` ใน transaction เดิม
  · inject เฉพาะ context ของเทสต์ ไม่คร่อม network ใน runtime
  · mutant `_MARK_ACTIVE` ใช้ now() ต้องถูก regression จับ โดยไม่แก้ไฟล์ production
- V-35: user add/retry/delete ผ่าน HTTPจริง และ system outcome matrix
  ครบ verified/credential rejection/expiry/temporary outcomes
  · รวม repeated identical failures ต้องได้ audit ทุกรอบ
  · ใช้ shared test audit query/expected shape ไม่คัดลอกโค้ด producer

ขอบเขต review ข้อ 9 ไม่ใช่การปิด validation ทั้ง feature:
NC-18 (~30 automatic/manual), NC-19 (permissions/fixture) และตรวจ key จริง
ยังต้องปิดแยก · ไม่เดาเพดาน/เปลี่ยน quota เพื่อทำให้เทสต์ผ่าน

สถานะ: **ซ่อม review ข้อ 9 ทั้งสี่ส่วนเสร็จ** · F-07 ยัง In Progress · ไม่ commit/push

ผลตรวจ review ข้อ 9 (2026-10-06):
- assertion ที่เพิ่มให้ quota/log เทสต์เดิม **2 กรณีแดงก่อนซ่อม setup**
  · quota เดิมได้ 409 ทุกครั้ง และ log เดิมเรียกตลาดเพียงครั้งเดียว
  · หลังซ่อม 202 × 6 → 429 และ market.calls=2/deferred จริง
- V-19.2 base transaction-crossing regression ผ่าน และ regression เดียวกัน
  จับ now() mutant ได้ด้วย assertion เฉพาะ · เปลี่ยน SQL constant ใน memory
  เท่านั้น และ monkeypatch คืนค่า · ไม่แก้ไฟล์ production/ไม่รอจริง
- audit matrix ครบ user add/retry/delete + system verified/credential rejection/
  expired และทุก temporary type รวม repeated identical failures 4 รอบ
  · expected shape มาจาก plan 4.4 ไม่ใช้ producer สร้าง expected
  · query/expected helper ร่วมใน `tests/api_key_audit.py` รวม expiry helper เดิม
- ตรวจกลุ่มใหม่ 14 ข้อผ่าน · API/worker/storage/audit ทั้งชุด **230 passed**
  · ระหว่างเติมเทสต์พบ decorator ของ late-outcome test ย้ายผิดตำแหน่ง
  · คืนให้ถูกต้องและตรวจ collect เดิมครบ 4 parameters แล้วรันใหม่
- backend ทั้งชุดสุดท้าย **1,218 passed, 1 deselected (ตลาดจริง), warnings เดิม 3 รายการ**
- Ruff lint/format รวม migration, mypy src/tests (**183 files**) และ import-linter ผ่าน
  · รีวิวอิสระไม่พบข้อที่บล็อก · git diff --check ผ่าน
- PostgreSQL 16 ฐานข้อมูลแยกพร้อมบทบาทจริง · ลบฐานข้อมูลทดสอบเมื่อจบ
  · ไม่แก้ runtime ไม่แตะฐานข้อมูลใช้งาน ไม่ยิงตลาดจริง · ไม่ commit/push
- ไม่รัน frontend/e2e ซ้ำเพราะเปลี่ยนเฉพาะ backend tests/fixtures
  · review 1–9 ซ่อมตามขอบเขตแล้ว แต่ **F-07 ยัง In Progress**
  · ต้องปิด NC-18/NC-19 และ validation ทั้งฉบับ/manual real-key checks แยก

### ความคืบหน้า 2026-10-06 — refactor เฉพาะงาน review ข้อ 9 ล่าสุด

เจ้าของสั่ง review/refactor โดยไม่เปลี่ยนพฤติกรรม · ขอบเขตมีเฉพาะ
`tests/api_key_audit.py`, ส่วน quota/user-audit ที่แก้ใน `tests/api/test_api_key_routes.py`
และ log/deadline/audit matrix ที่แก้ใน `tests/services/engine/test_verification.py`
· ไม่แตะ runtime หรือเทสต์ของ review 1–8

- ใช้ shared audit helper เดิมซ้ำ เปลี่ยนชื่อเป็น read_key_audit_events/
  expected_key_audit_event ให้ชัดว่าตัวไหนอ่านและตัวไหนสร้าง expected
- helper ใช้ dict[str, object] แทน Any และ Literal ของ actor kind
  · expected action/actor/outcome/failure_code เป็น keyword-only ตามชื่อคอลัมน์
- ลด parentheses ของ query ด้วย result ตัวเดียว อ่าน mappings ภายใน session
- outcome matrix ใช้ pytest.param พร้อม id และ expired boolean
  ไม่เอาชื่อกรณีมาเป็นเงื่อนไข fixture · secret deletion เทียบ expected outcome
  ตามตารางเดิม · ยังคงครบ 8 กรณี
- deadline helper ใช้ชื่อ _assert_late_completion_is_rejected และระบุ owner/key_id
  ตรง ๆ แทน tuple unpack ปน positional argument · mutant/base ใช้ helperเดียวกัน

สถานะ: **refactor งานข้อ 9 ล่าสุดเสร็จ** · F-07 ยัง In Progress · ไม่ commit/push

ผลตรวจ refactor งานล่าสุด (2026-10-06):
- API/worker/storage/audit ที่เกี่ยวข้อง **230 passed** รวม mutation proof
  · จำนวนกรณีเดิมคงครบ ไม่เปลี่ยน audit expectations หรือกฎ runtime
- Ruff lint/format รวม migration, mypy src/tests (**183 files**) และ import-linter ผ่าน
  · รีวิวอิสระไม่พบข้อที่บล็อก · git diff --check ผ่าน
- PostgreSQL 16 ฐานข้อมูลแยกพร้อมบทบาทจริง · ลบฐานข้อมูลทดสอบเมื่อจบ
  · ไม่แก้ runtime ไม่แตะฐานข้อมูลใช้งาน ไม่ยิงตลาดจริง · ไม่ commit/push
- ไม่รันทั้ง backend/frontend/e2e ซ้ำเพิ่มเติม เพราะเป็น refactor เทสต์ล้วน
  และชุดที่ครอบทุกจุดเรียก helper/ทุกกรณีที่แก้ผ่านแล้ว
  · ผล backend ทั้งชุดก่อน refactor **1,218 passed** อยู่ในบันทึกข้อ 9
- NC-18/NC-19 และ validation/manual real-key checks ยังเหลือ · F-07 ยัง In Progress

### ความคืบหน้า 2026-10-06 — ซ่อมผลรีวิวรอบรวม ข้อ 1: response headers

เจ้าของสั่งแก้ header ผิดรูปที่ทำให้ verification worker หยุด · ใช้
`venues/binance_th/transport.py::_retry_after/used_weight_of`, IpWeightLimiter
และ `VenueProtocolError` เดิมซ้ำ · ไม่เพิ่ม catch-all ใน worker

- numeric Retry-After ที่ timedelta เก็บไม่ได้ หรือบวกเวลารับ response แล้ว
  เกินขอบเขต datetime → VENUE_PROTOCOL
- reported weight ติดลบ และ numeric window span ที่เก็บไม่ได้ → VENUE_PROTOCOL
- โยน error นอก except block ไม่เก็บ exception chain/raw header
- คงการอ่าน header ปกติ/ต้นทุนตลาด/limit/backoff/อายุ key เดิม
  · คงพฤติกรรม header ไม่รู้จัก/ค่าที่ไม่ใช่ integer/HTTP-date ที่ reader ยังไม่รองรับ
  ตามสัญญา F-35 เดิม ไม่เดาเวลาตลาดหรือเพิ่มกฎใหม่

ใช้ transport_for/replying/FakeClock/signing/live_wallet_factory/_state/
read_key_audit_events และ UserSession เดิมซ้ำ: adapter public+signed regressions
และ actual worker Round ที่มี key ผิด header กับ key ปกติของอีกผู้ใช้
→ UNVERIFIABLE/secret retained/audit+ERROR และตัวถัดไป ACTIVE ในรอบเดียว

สถานะ: **ซ่อม response headers เสร็จ** · F-07 ยัง In Progress · ไม่ commit/push

ผลตรวจ (2026-10-06):
- regression ใหม่ 12 กรณี: header ผิดรูป 4 แบบ × adapter public/signed และ worker
  · 9 กรณีแรกแดงด้วย ValueError/OverflowError ก่อนแก้
  · deadline boundary adapter 2 กรณีแดงก่อนเพิ่มการตรวจ datetime
- ชุด backend สุดท้าย **1,231 passed**, warnings เดิม 3 รายการ
  · ชุดปกติ 1,230 และ public venue-contract 1 รายการ
  · รอบสุดท้ายใช้ marker `not live` ผิดจาก `not venue_contract` จึงรวมเทสต์ตลาด
    สาธารณะโดยไม่ตั้งใจ · ไม่มี credential หรือคำสั่งซื้อขาย
- Ruff lint/format, mypy src/tests 183 files และ import-linter 6 contracts ผ่าน
  · รีวิวอิสระไม่พบ blocker หลังแก้ deadline boundary · git diff --check ผ่าน
- PostgreSQL 16 ฐานข้อมูลทดสอบแยกพร้อมบทบาทจริง ลบแล้วเมื่อจบ
  · ไม่แตะฐานข้อมูลใช้งาน ไม่ทดสอบด้วย key จริง · ไม่ commit/push
- ไม่รัน frontend/e2e ซ้ำ เพราะไม่มี UI/API schema เปลี่ยนในงานนี้
- ตรวจตามเส้นทาง VENUE_PROTOCOL ที่ requirements/validation กำหนด:
  secret คงอยู่, claim ถูกปล่อย, audit+ERROR และ key ของอีกผู้ใช้ตรวจต่อได้
  · ไม่เปลี่ยนต้นทุน/limit/backoff/อายุ key หรือ policy การซื้อขาย
- ข้อรีวิวรอบรวม 2–4, NC-18/NC-19 และ validation/manual real-key checks ยังเหลือ


### ความคืบหน้า 2026-10-06 — ซ่อมผลรีวิวรอบรวม ข้อ 2: label มี NUL

เจ้าของสั่งแก้ NUL ใน label ที่ผ่าน validation แล้วเป็น 500 · ตาม RQ-13
ต้องปฏิเสธก่อนฐานข้อมูล และใช้ safe 422 ของ API เดิม
- ใช้ records.py เป็นที่เดียวของตัวตรวจ NUL ร่วม schema และ storage
- ใช้ _accepted_label/ApiKeyError, AddKeyRequest, safe validation handler เดิมซ้ำ
- คง trim/ความยาว/Unicode/ชื่อซ้ำ/โควตา/การซื้อขายเดิม
- เพิ่มกรณี NUL ต้น/กลาง/ท้ายใน HTTP privacy regression และ storage input regression
  · ต้องไม่มีแถว key ถูกเพิ่ม ไม่มี key/secret/label ใน response/log

สถานะ: **ซ่อม label NUL เสร็จ** · F-07 ยัง In Progress · ไม่ commit/push

ผลตรวจ (2026-10-06):
- NUL ต้น/กลาง/ท้าย × API/storage **6 กรณีแดงก่อนแก้** ด้วย SQLSTATE 22021
- API-key API/storage/worker regressions **159 passed**, warning เดิม 1 รายการ
  · HTTP ตอบ 422 API_KEY_REJECTED_INPUT ไม่มี label/key/secret ใน response/log
  · ไม่เพิ่มแถว key และ storage ปฏิเสธด้วย ApiKeyError ก่อนฐานข้อมูล
- safety/AST gates **157 passed**
- Ruff lint/format, mypy src/tests 183 files และ import-linter 6 contracts ผ่าน
  · รีวิวอิสระไม่พบ blocker · git diff --check ผ่าน
- PostgreSQL 16 ฐานข้อมูลทดสอบแยกพร้อมบทบาทจริง ลบแล้วเมื่อจบ
  · ไม่แตะฐานข้อมูลใช้งาน ไม่เรียกตลาดจริง ไม่ commit/push
- ไม่รันทั้ง backend/frontend/e2e ซ้ำ เพราะเปลี่ยนเฉพาะ label validation
  และชุดที่ครอบ schema/storage/HTTP/privacy/worker ผ่านแล้ว
- ตรวจ RQ-13 และ V-4/V-7: validation ก่อนฐานข้อมูลและไม่สะท้อน input
  · กฎ label อื่น/โควตา/การซื้อขายคงเดิม
- F-07 ยัง In Progress · ข้อรีวิวรอบรวม 3–4 และงาน validation ที่ค้างยังเหลือ


### ความคืบหน้า 2026-10-06 — ซ่อมผลรีวิวรอบรวม ข้อ 3: asyncio conditional fallback

เจ้าของสั่งแก้ด่าน asyncio ที่พลาด loop ผ่าน BoolOp/IfExp ตาม V-32.1/NC-17
ใช้ check_asyncio_network ใน tests/venue_isolation.py ร่วม global/adapter gate เดิม
และ UNSAFE/SAFE matrix ใน tests/test_asyncio_network_gate.py เดิมซ้ำ
- ตรวจทางเลือกผลลัพธ์ของ `or`/`and`/conditional expression โดยไม่ execute source
- ครอบ loop ในแต่ละฝั่ง/nested fallback/direct receiver/alias/local return
- คง asyncio scheduling และ gateway เดิมที่ได้รับอนุญาต
- ไม่แตะ runtime หรือ scope binding ของข้อรีวิว 4 ในงานนี้

สถานะ: **ซ่อม asyncio conditional fallback เสร็จ** · F-07 ยัง In Progress · ไม่ commit/push

ผลตรวจ (2026-10-06):
- UNSAFE ใหม่ 9 snippets × global 2 ชั้นและ adapter = **27 กรณีแดงก่อนแก้**
  · หลังแก้ตรวจพบ network-outside-gateway ครบทุกกรณี
- safety/AST gates **184 passed** และ venue isolation/endpoint boundary **16 passed**
  · scheduling/unknown receiver และ transport gateway ยังผ่านตามเดิม
- Ruff lint/format, mypy src/tests 183 files และ import-linter 6 contracts ผ่าน
  · รีวิวอิสระไม่พบ blocker ในขอบเขต conditional fallback · git diff --check ผ่าน
- ตรวจ V-32.1/NC-17: shared checker ครอบ conditional loop fallback ทั้ง global/adapter
- ไม่รัน DB/backend ทั้งชุด/frontend/e2e ซ้ำ เพราะเปลี่ยนเฉพาะ AST test checker
  และเทสต์ที่เรียก checker/ตรวจ architecture ผ่านครบ · ไม่แตะ runtime/DB/ตลาดจริง
- ไม่ commit/push · ข้อรีวิวรอบรวม 4 และงาน validation ที่ค้างยังเหลือ


### ความคืบหน้า 2026-10-06 — ซ่อมผลรีวิวรอบรวม ข้อ 4: asyncio bindings ข้ามฟังก์ชัน

เจ้าของสั่งแยก binding ของด่านตาม lexical scope ตาม V-32.1/NC-17
ใช้ check_asyncio_network/qualified/kind/call_result/annotation_kind เดิมซ้ำ
และ SAFE/UNSAFE matrix ใน tests/test_asyncio_network_gate.py เดิมซ้ำ
- ผูก symbol/object/function/return/argument binding กับ scope ของชื่อ
- ชื่อ local ของอีกฟังก์ชันต้องไม่ปะปน; closure/module lookup ยังตรวจ loop ได้
- ทดสอบชื่อซ้ำใน assignment/parameter/import/local helper และ nested closure
- ไม่เปลี่ยน runtime/กฎซื้อขาย/gateway

สถานะ: **ซ่อม asyncio scope binding เสร็จ** · F-07 ยัง In Progress · ไม่ commit/push

ผลตรวจ (2026-10-06):
- SAFE ชื่อซ้ำ 7 กรณีแดงก่อนแก้ด้วย false-positive
- เพิ่ม regressions สำหรับ closure/local helper/global/nonlocal/instance fields/
  annotation ที่ parameter บังชื่อ module และแยก field ของคนละ class
  · global/nonlocal 6 checks, field 3 checks และ annotation 3 checks
    แดงระหว่างซ่อม ก่อนแก้การ resolve ให้รักษาการตรวจพบเดิม
- scopes เก็บชื่อ local แม้ไม่รู้ชนิดเพื่อบัง outer names; argument propagation
  เขียนเฉพาะ scope ของ callee; annotations/defaults lookup ใน enclosing scope
- self/cls attributes ใช้ identity ของ class ร่วมระหว่าง methods
  แยก instance/class receiver และไม่ใช้กับ staticmethod
- safety/AST/venue-isolation/endpoint-boundary **226 passed**
  · รวม asyncio matrix **117 passed** และ scheduling/gateway เดิม
- Ruff lint/format, mypy src/tests 183 files และ import-linter 6 contracts ผ่าน
  · รีวิวอิสระยืนยันแก้ cross-method regression แล้ว ไม่พบ blocker เพิ่ม
  · git diff --check ผ่าน
- ตรวจ V-32.1/NC-17: ลด false-positive จาก sibling bindings
  พร้อมรักษาการตรวจ network ใน outer scope และ attributes ของ class เดียวกัน
- ไม่รัน DB/backend ทั้งชุด/frontend/e2e ซ้ำ เพราะเปลี่ยนเฉพาะ AST test checker
  และเทสต์ที่เรียก checker/ตรวจ architecture ผ่านครบ · ไม่แตะ runtime/DB/ตลาดจริง
- ไม่ commit/push · F-07 ยัง In Progress · งาน validation/NC-18/NC-19 และ
  manual real-key checks ที่ค้างยังเหลือ


### ความคืบหน้า 2026-10-07 — ซ่อม final review ข้อ 1: comprehension scope

เจ้าของสั่งแก้ comprehension target ที่บัง enclosing loop ผิด ตาม V-32.1/NC-17
ใช้ index_scope/binding และ SAFE/UNSAFE matrix เดิมซ้ำ
- แยก scope ของ list/set/dict comprehension และ generator expression
- iterable แรกอ่าน enclosing scope; target/filters/iterables ถัดไป/ผลลัพธ์อยู่ใน scope ใหม่
- ทดสอบ outer loop หลัง comprehension, first iterable, nested comprehension
  และ target ที่ไม่ใช่ loop ต้องไม่ถูกตีความตาม outer loop
- ไม่แก้ inherited fields ของ final review ข้อ 2 ในงานนี้ ไม่แตะ runtime

สถานะ: **ซ่อม comprehension scope เสร็จ** · F-07 ยัง In Progress · ไม่ commit/push

ผลตรวจ (2026-10-07):
- regressions ใหม่ 9 UNSAFE snippets × global 2 ชั้น + adapter และ 4 SAFE snippets
  · **28 checks แดงก่อนแก้** (24 false-negative และ 4 false-positive)
  · ทั้ง matrix หลังแก้ **148 passed**
- safety/AST/venue-isolation/endpoint-boundary รวม **257 passed**
- Ruff lint/format, mypy src/tests 183 files และ import-linter 6 contracts ผ่าน
  · รีวิวอิสระไม่พบ blocker ในขอบเขต comprehension
  และยืนยัน filters/subsequent iterables/class-scope free variables
  · git diff --check ผ่าน
- ตรวจ V-32.1/NC-17: global และ adapter ใช้ scope index เดียวกัน
  ตรวจ outer loop ต่อได้ และไม่เหมารวม target ของ comprehension เป็น outer loop
- ไม่รัน DB/backend ทั้งชุด/frontend/e2e ซ้ำ เพราะเปลี่ยนเฉพาะ AST test checker
  และเทสต์ที่เรียก checker/ตรวจ architecture ผ่านครบ · ไม่แตะ runtime/DB/ตลาดจริง
- final review ข้อ 2 inherited fields, validation gaps และ NC-18/NC-19/manual checks
  ยังเหลือ · ไม่ commit/push


### ความคืบหน้า 2026-10-07 — ซ่อม final review ข้อ 2: inherited loop fields

เจ้าของสั่งแก้ loop field จากคลาสแม่ที่ด่านตรวจไม่พบ ตาม V-32.1/NC-17
ใช้ binding/qualified/kind/call_result และ SAFE/UNSAFE matrix เดิมซ้ำ
- resolve field จากคลาสแม่ที่ประกาศในไฟล์เดียวกันตาม lexical binding
- ครอบหลายชั้นและหลาย base, แยกคลาสไม่เกี่ยวข้อง และ field override
- คง receiver identity ของ instance/class และ shared checker global/adapter
- ไม่แตะ runtime/DB/ตลาดจริง และไม่เพิ่ม dynamic execution ในด่าน

สถานะ: **ซ่อม inherited fields เสร็จ** · F-07 ยัง In Progress · ไม่ commit/push

ผลตรวจ (2026-10-07):
- inheritance/หลายชั้น/หลาย base/classmethod **12 checks แดงก่อนแก้**
- เพิ่ม diamond inheritance เพื่อพิสูจน์ C3 ordering ทั้ง network/override
  · ใช้ลำดับคลาสแม่ที่ประกาศในไฟล์ ไม่ execute/import source
- regression annotation-only `self.loop: Any` **3 checks แดงระหว่างรีวิวก่อนแก้**
  · annotation อย่างเดียวไม่บัง field คลาสแม่; explicit loop annotation ยังเป็น
    หลักฐานตรวจ network ตามด่านเดิม · assignment จริงแยกจาก annotation
- ใหม่รวม 7 UNSAFE snippets × global 2 ชั้น + adapter และ 3 SAFE snippets
  · ทั้ง asyncio matrix **172 passed**
- safety/AST/venue-isolation/endpoint-boundary รวม **281 passed**
- Ruff lint/format, mypy src/tests 183 files และ import-linter 6 contracts ผ่าน
  · รีวิวอิสระยืนยัน annotation regression แก้แล้ว ไม่พบ blocker เพิ่มในงานนี้
  · git diff --check ผ่าน
- ตรวจ V-32.1/NC-17: shared global/adapter checker ตรวจ inherited fields ได้
  โดยไม่ปะปนคลาสที่ไม่เกี่ยวข้อง และรักษา field override/typed evidence
- ไม่รัน DB/backend ทั้งชุด/frontend/e2e ซ้ำ เพราะเปลี่ยนเฉพาะ AST test checker
  และเทสต์ที่เรียก checker/ตรวจ architecture ผ่านครบ · ไม่แตะ runtime/DB/ตลาดจริง
- validation gaps สามข้อจาก final review และ NC-18/NC-19/manual checks
  ยังเหลือ · ไม่ commit/push


### ความคืบหน้า 2026-10-07 — เติม final review validation gaps

เจ้าของสั่งเริ่มขั้น 3: เติมเทสต์สามข้อทีละข้อ โดยไม่เปลี่ยน runtime
1. V-22.1/V-31.6: request_retry ระหว่าง actual worker claim/market wait หลายครั้ง
   ใช้ ScriptedWallet/_round/_state/user_session/request_retry เดิมซ้ำ
   พิสูจน์ worker สองไม่ยิงตลาด และหลังจบรอบมีเพิ่มเพียงหนึ่งรอบ
2. V-11: ใช้ startup test ของ API เดิมและ engine.main.serve ตรวจขาด VENUE key
3. V-6: ใช้ raw audit INSERT/UserSession/ValueRejectedError เดิม
   ตรวจ details ต้องห้ามครบ API-key actions ด้วย API/ENGINE roles จริง

สถานะ: **เติมสาม validation gaps เสร็จ** · F-07 ยัง In Progress · ไม่ commit/push

- ข้อ 1 retry ระหว่าง claim: เทสต์ DB จริง 1 passed · Ruff/mypy ผ่าน
  worker สองไม่เรียกตลาด, manual 3 คำขอรวมเป็นหนึ่งรอบเพิ่ม, attempts=3 รวม seed

- ข้อ 2 startup: API ที่ขาด VENUE/TOTP และ engine ที่ขาด VENUE
  ตรวจ failure ก่อนเปิด resources · ชุด startup/route policy 18 passed

- ข้อ 3 audit: 6 actions × 3 forbidden details **18 passed** ด้วย API/ENGINE roles
  · valid empty-details control เขียนและ commit ได้ก่อนทดสอบ invalid shape
- ผล regression รวม worker/API key/route policy/audit/startup/safety gates
  **501 passed**, warning เดิม 1 รายการ
- Ruff lint/format, mypy src/tests 183 files และ import-linter 6 contracts ผ่าน
  · รีวิวอิสระไม่พบ blocker ในสามช่องว่างนี้ · git diff --check ผ่าน
- PostgreSQL 16 ฐานข้อมูลแยกพร้อมบทบาทจริง ลบแล้วเมื่อจบ
  · ไม่แก้ runtime ไม่แตะ DB ใช้งาน ไม่เรียกตลาดจริง ไม่ commit/push
- ไม่รันทั้ง backend/frontend/e2e ซ้ำในงานเทสต์นี้ เพราะชุดที่เกี่ยวข้องผ่านครบ
- การเพิ่มเทสต์ validation-only ไม่มี production bug ที่ต้องแก้ให้เทสต์ผ่าน
- ยังไม่รับรอง F-07 ทั้งฉบับ: NC-18/NC-19, generated mixed-outcome sequences,
  exact deadline boundary, stale 1→5-minute backoff และ manual key checks ยังเหลือ


### ความคืบหน้า 2026-10-07 — รีวิวและรันทุกด่านซ้ำ

รีวิว read-only เทียบ base 510111070d59a22b6f7ef697265d4dbed3b06d65
รวม working tree/untracked ของ F-07 · ไม่แก้ runtime ระหว่างรีวิว
- Backend **1,365 passed, 1 venue_contract deselected, 3 warnings เดิม**
  · PostgreSQL 16 ฐานข้อมูลแยกพร้อมทั้ง 6 roles · ลบแล้วเมื่อจบ
- Frontend **34 passed**, ESLint/typecheck/build ผ่าน
- E2E **7 passed** · API/worker จริงกับ FakeVenue · ฐานข้อมูลแยกอีกชุด ลบแล้ว
- Ruff lint/format, mypy src/tests 183 files และ import-linter 6 contracts ผ่าน
- OpenAPI ที่สร้างใหม่ใน /private/tmp ตรงกับ backend/openapi.json
  และ TypeScript ที่สร้างจาก schema ตรงกับ frontend/src/api-types.ts
  · เทียบไฟล์ปัจจุบัน ไม่เทียบ working tree ที่ยังไม่ commit กับ HEAD
- git diff --check ผ่าน · ไม่ยิงตลาดจริง ไม่ใช้ key จริง ไม่ commit/push

ผลรีวิว: **CHANGES REQUIRED**
- Medium ใหม่: declared_fields/field_binding ใน tests/venue_isolation.py
  มอง assignment ใน optional setter ของ subclass เป็น guaranteed override
  จึงบัง loop ที่ inherited __init__ ยังสร้างให้ · Base.__init__ กำหนด self.loop
  เป็น asyncio loop, Client.set_loop อาจเขียน replacement แต่ Client.send
  ก่อนเรียก setter ยังใช้ inherited loopจริง · global/adapter คืน [] ทั้งคู่
  จาก pure AST probes ของ root และ reviewer
  · ต้องเก็บ possible inherited-loop evidence เมื่อ optional method เขียนค่าที่
    ยังไม่รู้ชนิด พร้อม regression และรักษา legitimate constructor overrides
- ไม่พบ actionable runtime Standard finding เพิ่ม
- validation ที่ยังขาด: V-22.5/V-22.6 stale 1→5 นาทีที่นาทีสอง,
  exact deadline equality และ generated mixed-outcome state/secret invariants
- NC-18/NC-19 และ manual real-key checks ยังเหลือ · F-07 ยัง In Progress

Docker gate: **ผ่าน build/migrate/startup/HTTP smoke tests**
- build images ใหม่, API /health และ frontend / รวม proxy /api/health ผ่าน
- temp project/ports/database แยก · config ที่สร้างจาก compose มี network name เดิม
  จึงแก้ชื่อเฉพาะ config ใน /private/tmp และรัน startup/smoke ซ้ำบน network ใหม่
- ตรวจ DB ทดสอบ head 0011 และ DB เดิมคง 0010 · cleanup containers/network แล้ว
  · ไม่เปลี่ยน compose.yaml
- npm audit ที่ Docker build รายงาน ตรวจเพิ่มพบ 4 advisories:
  2 critical (vitest/tinypool), 1 high (source-map-js), 1 moderate (@vitest/mocker)
  · versions เดียวกับ HEAD lockfile ก่อน task ไม่ใช่ dependency ที่เพิ่มโดย F-07
  · เป็น tooling advisories ยังไม่ประเมิน exploitability ของ deployment
  · บันทึกแยกจาก F-07 finding ไม่อัปเดต dependency นอกขอบเขต

สถานะ: รันด่านอัตโนมัติครบและผ่าน แต่ review **CHANGES REQUIRED**
· ไม่มี code fix ระหว่าง review · อัปเดตหลักฐานใน plan เท่านั้น


### ความคืบหน้า 2026-10-07 — ซ่อม optional setter ของ AST gate

เจ้าของสั่งแก้ optional setter ที่บัง inherited loop ตาม V-32.1/NC-17
ใช้ declared_fields/field_binding/class_order/kind เดิมและ SAFE/UNSAFE matrix ซ้ำ
- assignment ใน optional method ไม่เป็น guaranteed constructor override
- เก็บ possible inherited-loop evidence; คง direct constructor overrides และ
  C3 lookup, class isolation และ annotation evidence เดิม
- ทดสอบ setter unknown/known non-loop และ conditional constructor assignment
  · ไม่แตะ runtime/DB/ตลาดจริง

สถานะ: **ซ่อม optional setter เสร็จ** · F-07 ยัง In Progress · ไม่ commit/push

ผลตรวจ (2026-10-07):
- unknown setter / Runner-valued setter / conditional constructor
  3 UNSAFE snippets × global 2 ชั้น + adapter = **9 checks แดงก่อนแก้**
- เปลี่ยน declared_fields เป็น constructor_fields: เฉพาะ assignment จริง
  ที่อยู่ตรงใน __init__ เท่านั้น · optional/conditional assignment ไม่บัง ancestor
- field_binding รักษา possible loop จาก C3 ancestors ก่อนใช้ non-loop candidate
  · ยังรักษา direct constructor overrides, class isolation และ annotation evidence
- asyncio matrix **181 passed** · safety/AST/venue-isolation/endpoint-boundary
  รวม **290 passed**
- Ruff lint/format, mypy src/tests 183 files และ import-linter 6 contracts ผ่าน
  · รีวิวอิสระยืนยัน optional setter แก้แล้ว ไม่มี blocker เพิ่มในขอบเขตนี้
  · git diff --check ผ่าน
- ตรวจ V-32.1/NC-17: shared global/adapter checker จับ inherited loop ก่อนเรียกsetter
- ไม่รัน backend/frontend/E2E/Docker ซ้ำทั้งหมดหลัง test-checker change นี้
  เพราะด่านที่ใช้ checker ผ่านครบและไม่มี runtime/frontend/container เปลี่ยน
  · ผลทุกด่านก่อนแก้บันทึกไว้ในหัวข้อก่อนหน้า
- ไม่แตะ runtime/DB/ตลาดจริง ไม่ commit/push · validation backoff/deadline/property,
  NC-18/NC-19 และ manual key checks ยังเหลือ


### ความคืบหน้า 2026-10-07 — รันทุกด่านหลังซ่อม optional setter

เจ้าของสั่งขั้น 1 รันทุกด่าน · ไม่มีการแก้ runtime ในรอบนี้
สถานะ: **ขั้น 1 รันด่านอัตโนมัติครบและผ่าน** · F-07 ยัง In Progress

- Backend **1,374 passed, 1 venue_contract deselected, 3 warnings เดิม**
  · strict markers/config · รวม AST optional-setter regressions ล่าสุด
- Frontend **34 passed** · ESLint/typecheck/build ผ่าน
- E2E **7 passed** · real API/worker + FakeVenue ไม่ยิงตลาดจริง
- Ruff lint/format src/tests/migrations ผ่าน; mypy src/tests **183 files** ผ่าน
  และ import-linter **6 contracts** ผ่าน
- OpenAPI สร้างใน /private/tmp ตรง backend/openapi.json
  และ generated TS ตรง frontend/src/api-types.ts · ไม่แก้ generated files
- Docker Compose isolated project/network/ports/DB:
  build/migrate/startup ผ่าน, API /health, frontend / และ proxy /api/health ผ่าน
  · test DB head 0011; DB ใช้งานเดิมคง 0010
- PostgreSQL16 test DB backend/E2E แยกกัน, real rolesทั้ง6
  · ลบฐานข้อมูลทั้งสองและ Docker project/network/volumes เมื่อจบ
- git diff --check ผ่าน · ไม่ commit/push ไม่ใช้ key จริง
- ขั้น 1 เสร็จ ไม่ใช่การรับรอง validation ทั้งฉบับ:
  backoff/deadline/property gaps, NC-18/NC-19 และ manual real-key checks ยังเหลือ
- tooling advisories เดิมจาก npm audit รอบก่อนยังไม่ได้แก้ในงานนี้


### ความคืบหน้า 2026-10-07 — ปิด validation และ NC-18/NC-19

เจ้าของยืนยัน NC-18: ~30 เฉพาะ automatic ภายใน 24h; manual quota เดิม ไม่มีcapรวม
เจ้าของยืนยันนโยบาย NC-19: unknown permission report → VENUE_PROTOCOL/secret retained/
ERROR, fixtures รูปร่างจริงแต่ค่าทดแทน · actual response provenance ตรวจใน UI ขั้นถัดไป
รอคำตอบขอบเขต unknown top-level fields ก่อนแก้ adapter ไม่เดาชื่อ permission fields

ทำทีละงานโดยใช้ของเดิม:
1. V-22.5/6 ใช้ claims.claim/due_hints/_round/_state/as_structure_owner
   stale hint หลัง backoff 1→5 นาที และ mutant claim recomputes backoff
2. exact equality ใช้ claims SQL constants เดิมและ DB จริงกับ fixed test timestamp
3. generated mixed outcomes ใช้ ScriptedWallet, _round และ state/audit helpers + hypothesis
4. NC-19 ใช้ holdings_from_account/_mapping และ shapes fixture เดิม

สถานะ: กำลังเติม validation · F-07 ยัง In Progress · ไม่ commit/push

- งาน 1 stale 1→5-minute backoff ที่นาทีสอง **1 passed** พร้อม mutation proof
  mutant recompute 1-minute ถูกจับ และ rollback ไม่เพิ่ม attempts · Ruff/mypy ผ่าน

- งาน 2 exact equality **3 passed** ก่อน/ตรง/หลังเส้นตาย ±1µs ด้วย SQL test clock เดียว
  ไม่มีการรอ wall time · status/secret/audit/market-call ตรงเกณฑ์
- งาน 3 generated outcomes + NC-18 schedule **2 passed**
  hypothesis 30 histories และ explicit mixed histories 2 ชุด
  · ทุก example user/key ใหม่และ cleanup; ตรวจ state/secret/version/claim/audit ทุกstep
  · independently enumerated automatic scheduleได้27 attempts ภายใน24h
  · Ruff/mypy ผ่าน ไม่เพิ่ม runtime cap รวม manual

- ตรวจ matrix ทั้งฉบับเพิ่ม: เติมหลักฐาน all-routes canary/ciphertext,
  actual signed INFO logging, VENUE crypto properties/rotation/cross-purpose,
  wrong TOTP/recovery grant ผ่าน API-key route, HTTP ADD quota + denied work,
  stable signing text/ครบ fixture balances และ engine_scan SELECT *
  · ใช้ route_keys, helpers/role sessions, transport_for และ seal/unseal เดิม


ผลตรวจรอบปิด automated evidence (2026-10-07):
- Backend รอบสุดท้าย **1,386 passed, 1 venue_contract deselected, 3 warnings เดิม**
- Ruff lint/format, mypy src/tests 183 files, import-linter 6 contracts ผ่าน
- all-route canary แยก session-ending group, restore auth เมื่อจำเป็น,
  assert /auth/me200 ทุก route, GET200/DELETE204/retry409 และ ciphertext representations
  · รีวิวพบ logout-all vacuity แล้วซ่อมเทสต์ก่อน full run สุดท้าย
- quota worker isolation ใช้ test-only SQL owner filter ก่อน LIMIT
- signed_get INFO/httpx logging, both-purpose generated crypto/rotation/owner binding,
  scan SELECT *, wrong TOTP/recovery grant, full wallet quantities/signing text ผ่าน
- reviewer ไม่พบ critical automated-evidence gap เพิ่มในชุดที่เติม
  · DB test แยก PostgreSQL16 ทั้ง6roles ลบแล้ว · git diff --check ผ่าน
- ไม่มี runtime change ระหว่างเติมหลักฐาน ไม่ยิงตลาดจริง ไม่ commit/push

สถานะปัจจุบัน: **NC-18 ปิดแล้ว; automated evidence ที่ตรวจพบเติมแล้ว**
· **NC-19 ยังไม่ปิด**: นโยบาย fail closed/sanitized fixture เจ้าของยืนยันแล้ว
  แต่ pending question เรื่อง unknown top-level fields ทุกชนิดยังไม่มีคำตอบ
  จึงไม่แก้ adapter หรือเดารายชื่อ fields · AGENTS.md ห้ามคิดข้อกำหนดเอง
· การยืนยัน fixture provenance/manual UI key จริงอยู่ขั้น 3
· ไม่มีการรับรอง F-07 เสร็จหรืออัปเดต roadmap เป็น Completed


### ความคืบหน้า 2026-10-07 — NC-19 / RQ-6.4 approved strict account shape

เจ้าของ approve unknown top-level fields ทุกชนิด → VENUE_PROTOCOL
ใช้ holdings_from_account/_mapping และ account_shape fixture เดิมซ้ำ
- allowlist top-level fields เดิมทั้ง9ตาม fixture ที่มาจากรูปจริง:
  makerCommission/takerCommission/buyerCommission/sellerCommission/
  canTrade/canWithdraw/canDeposit/updateTime/balances
- ไม่อ่านหรือใช้ค่า account flags ตัดสินสิทธิ์ของ key; known optional fields คงเดิม
- unknown name/value ทุกแบบปฏิเสธด้วย error กลางไม่เก็บ raw fields/values
- ใช้ actual adapter + worker protocol flow เดิมพิสูจน์ retained secret/audit/ERROR
- ไม่เพิ่ม endpoint หรือการเทรด · manual UI รอ runtime guard ผ่านก่อนเริ่ม

สถานะ: กำลัง implement NC-19 · F-07 ยัง In Progress · ไม่ commit/push

- Full suite พบ false-positive account-flag literals ใน approved _ACCOUNT_FIELDS
  จึงปรับด่านเฉพาะ positions ของ literal names ใน root immutable schema declaration
  ที่ตรง known-nine-fields ทุกตัวและอยู่ mapping.py นี้เท่านั้น
  · ไม่ยกเว้นทั้งไฟล์/ทั้งบรรทัด; getters/attributes/strings นอก declaration ยังห้าม
  · ไม่อ่าน flag values และไม่ encode ชื่อเพื่อหลบ gate


ผล NC-19 (2026-10-07):
- 3 unknown-account-field regressions แดงก่อนแก้; adapter+worker guard ผ่าน
  · retained secret/version, UNVERIFIABLE/VENUE_PROTOCOL, audit+ERROR และ healthy owner ACTIVE
- narrow schema-literal exception มี11positive/negative/inline checks
  · flag value accessยังห้าม · ไม่มี file/line blanket exemption
- Backend final **1,402 passed, 1 venue_contract deselected, 3 warningsเดิม**
- Ruff lint/format, mypy183files, import-linter6contracts ผ่าน
  · independent reviews ไม่พบblocker guard/gate refinement · git diff --check ผ่าน
- NC-18/NC-19 ปิดแล้ว · runtime guardเป็นapproved change · regressionDBแยกลบแล้ว

Manual UI readiness (ยังไม่ใช่ผลทดสอบ key จริง):
- local API127.0.0.1:8000, UI127.0.0.1:5173 และ real read-only verification worker เปิดแล้ว
- dedicated DB tiewtrade_codex_manual_20261007_29, migrationshead0011
  ไม่แตะ DBเดิม · private randomsealingkeysแยกpurposeใน0600/tmpenvironment
- runner /private/tmp/tiewtrade-manual-runner-20261007.py
  logs /private/tmp/tiewtrade-manual-{api,ui,engine}-20261007.log permissions0600
- APIsession77915/UI75846 · workerดู readinessจาก log โดยไม่แสดงเนื้อหา
- Browser automation unavailable: Computer Use permissions are not granted
  · ผู้ใช้ต้องสมัคร/เปิดTOTP/กรอก fresh non-trading testkey ในUIเอง ไม่ส่งค่าในแชต
- ยังไม่มีkeyในmanualDB ณ readinesscheck จึงยังไม่มี signed requestถึงตลาด
- สถานะ: **รอ credential entry ในUI** · manual1–7ยังไม่รับรอง · F-07 In Progress
  ไม่commit/push · รักษาmanualDB/environmentจนทดสอบ/ถอนkey/cleanupเสร็จ


### Manual real-key validation — 2026-10-07 ผลข้อ1

เจ้าของแจ้งเพิ่ม key ผ่าน UIแล้ว · ตรวจเฉพาะ metadata ไม่เลือกค่าคำรับรอง/ยอดบัญชี
- manualDB มี1key: ACTIVE, attempts1, verified_atมีค่า, claimไม่ค้าง
- secret_sealed/key_versionยังมีค่า (ตรวจbooleanเท่านั้น)
- audit API_KEY_ADDED(USER/SUCCEEDED) และ API_KEY_VERIFIED(SYSTEM/SUCCEEDED)
  failure_codeว่าง/detailsว่างทั้งคู่
- API/engine logs: ERROR0/Traceback0; ไม่พบ signature=/timestamp=/X-MBX-APIKEY
  ไม่แสดงlogดิบหรือcredentials · engineไม่มี venueerrorcode
- readonly live verification สำเร็จ ไม่มีคำสั่งซื้อขาย
- Backendผลตรวจยืนยันข้อ1; การเห็นสถานะในUIให้เจ้าของยืนยันเพราะbrowsercontrolไม่มีสิทธิ์
- ข้อ2wrongsecret, ข้อ3network/retry, ข้อ4delete/readd, ข้อ5noTOTP UI,
  ข้อ6manuallogreviewครบและข้อ7revokeยังไม่รับรอง
- F-07ยัง In Progress · manualDB/keyenvironment/3processesรักษาไว้จนทดสอบเสร็จ


### Manual real-key validation — 2026-10-07 ข้อ2ยัง inconclusive

เจ้าของเพิ่ม secretผิดผ่านUIแล้ว · metadata-only inspection:
- keyเดิม ACTIVE/attempts1 ไม่เปลี่ยน
- keyทดสอบใหม่ UNVERIFIABLE/VENUE_REJECTED/attempts1,
  secret/versionยังมีและclaimปล่อยแล้ว
- ตลาดตอบ HTTP400/market_code -1021 ไม่ใช่ credential rejection
  · official Binance TH docs ระบุ timestamp outside recvWindow
  · จึงยังไม่พิสูจน์wrong-secret rejection/deletion; ไม่เดาสาเหตุว่าลายเซ็นผิด
- auditADDEDและVERIFICATION_DEFERRED/SYSTEM/FAILED/VENUE_REJECTED detailsว่าง
- ห้ามแก้สถานะเป็นREJECTEDหรือลบsecretเอง; NC-20 manual-only flowคงเดิม
- ตรวจclockแบบread-only; ต้องretryผ่านUIเพื่อได้ผลsecretvalidationที่ชัด
  · ไม่เพิ่ม endpoint/time offset/recvWindow หรือเปลี่ยนruntimeโดยไม่ผ่านspec


### Manual real-key validation — 2026-10-07 ข้อ2ผ่านหลังmanualretry

เจ้าของกดลองใหม่ผ่านUI · ไม่มีการเปลี่ยนสถานะเอง:
- keyเดิม ACTIVE/attempts1 ยังมีsecret/version
- secretผิด REJECTED/VENUE_CREDENTIAL_REJECTED/attempts2
  secret_sealed/key_versionไม่มีค่า, verified_atไม่มี, claimปล่อยแล้ว
- ตลาด HTTP400/-1022 รอบใหม่; รอบแรก-1021จึงเป็นinconclusiveก่อนหน้านี้
- audit RETRY_REQUESTED(USER/SUCCEEDED) + REJECTED(SYSTEM/REJECTED)
  codeVENUE_CREDENTIAL_REJECTED/detailsว่าง
- logไม่มีTraceback/query-signature markers · ไม่เลือกหรือแสดงcredentials
- ข้อ3เตรียมแล้ว: หยุดเฉพาะidentifiedmanualworker แล้วเปิดด้วยclosedlocalproxy
  จำกัดเฉพาะworker ไม่แก้clock/recvWindow/OSnetwork/API/UI/TLS
  · offlineworkerlog /private/tmp/tiewtrade-manual-engine-offline-20261007.log
  · รอเจ้าของเพิ่มvalidtestkeyอีกlabelในUIเพื่อพิสูจน์UNVERIFIABLE/retainedsecret


### Manual real-key validation — 2026-10-07 ข้อ3 network-failure halfผ่าน

เจ้าของเพิ่มvalidkeyอีกlabelผ่านUIระหว่างworker-only network restriction:
- third key UNVERIFIABLE/VENUE_UNAVAILABLE/attempts1
  sealed secret/versionยังมี, ไม่มีclaimค้าง · ไม่เป็นREJECTED
- audit ADDED USER/SUCCEEDED + DEFERRED SYSTEM/FAILED/VENUE_UNAVAILABLE detailsว่าง
- keyเดิมACTIVEและsecretผิดREJECTEDยังไม่เปลี่ยน
- offlineengine Traceback0/query-signature markers0
- หยุดidentifiedofflineworkerแล้ว (proxyoverrideมีแค่processนั้น ไม่ใช่OSnetwork)
  · API/UIยังเปิด · รอเจ้าของกดretryก่อนstartnormalworker
  เพื่อไม่ให้automatictimerชิงรันจนปุ่มretryหายก่อนทดสอบmanualrequest
- ยังไม่รับรองnetwork recovery half/ข้อ4–7 และ UIdisplay/provenance confirmation


### Manual real-key validation — 2026-10-07 ข้อ3 recoveryผ่าน

เจ้าของกดretryในUIระหว่างworkerหยุด:
- ก่อนstartnormalworker: thirdkey UNVERIFIABLE/VENUE_UNAVAILABLE/attempts1
  retry_requested_at>last_attempt_atจริง
- normalworkerไม่มีproxyoverride → thirdkey ACTIVE/attempts2,
  secret/versionยังมี, verified_atมีค่า, ไม่มีclaimค้าง/failure_code
- audit RETRY_REQUESTED(USER/SUCCEEDED) + VERIFIED(SYSTEM/SUCCEEDED) detailsว่าง
- firstkeyACTIVE/attempts1และwrongsecretREJECTED/attempts2ไม่เปลี่ยน
- normalengine Traceback0/query/credential markers0
- network-failure/recoveryข้อ3ผ่านbackend evidence; รอเจ้าของยืนยันผลUI
- normalworkersession86121กำลังรัน · ข้อ4delete/readd, ข้อ5noTOTP UI,
  ข้อ6logreviewครบ, ข้อ7revoke/provenanceยังไม่รับรอง


### Manual real-key validation — 2026-10-07 ข้อ4 deleteผ่าน/readdรอโควตา

เจ้าของลบnetwork keyผ่านUIแล้วพยายามเพิ่มชื่อเดิม:
- auditAPI_KEY_DELETED/SUCCEEDED; เหลือACTIVEเดิมและREJECTEDsecretผิดเท่านั้น
- ยังไม่มี ADDED ใหม่: HTTP429เพราะAPI_KEY_ADD tokens0
- approvedquota capacity3/refill1ต่อ20นาที · refilled_at00:54:55.266289 ICT
  nexttoken01:14:55.266289 ICT วันที่7ต.ค.2026
- TOTP_ACCOUNT/TOTP_IP tokens4: ไม่ใช่second-factor bucket refusal
- deletionไม่คืนADDquota · ไม่ล้างถัง/แก้เวลาหรือยกเว้นquotaเพียงเพื่อผ่านmanualtest
- ให้เจ้าของลองหลัง01:15 ICTด้วยTOTPชุดใหม่; readdขั้นนี้ยังไม่รับรอง


### Manual real-key validation — 2026-10-07 ข้อ4 readdผ่าน

เจ้าของรายงานเพิ่มใหม่ด้วยชื่อเดิมหลังquotaคืน:
- ADDEDใหม่เกิดหลังDELETED; firstpollPENDING/attempts0 จากนั้น normalworkerACTIVE/attempts1
- sealedsecret/versionมี, verified_atมี, ไม่มีfailure/claimค้าง
- auditADDED USER/SUCCEEDED + VERIFIED SYSTEM/SUCCEEDED detailsว่าง
- firstkeyACTIVEและwrongsecretREJECTEDไม่เปลี่ยน
- workerยังรัน ไม่มีTraceback/querymarkers · ข้อ4backendผ่าน
- ชื่อเดิม/ผลหายจากUIเป็นคำรายงานของเจ้าของ ไม่พยายามคืนข้อมูลแถวที่ลบแล้วจากaudit
- ถัดไปข้อ5บัญชีไม่เปิดTOTPในUI, ข้อ6logreview และข้อ7ถอนtestkeyที่BinanceTH


### Manual real-key validation — 2026-10-07 ข้อ5ผ่านจากภาพเจ้าของ

ภาพUIบัญชีทดสอบที่ไม่เปิดTOTPยืนยัน:
- แสดงบัญชียังไม่เปิดTOTPจึงเพิ่มkeyไม่ได้ พร้อมลิงก์เปิดการยืนยันสองชั้น
- ไม่มีฟอร์มเพิ่ม API key · รายการว่าง · ไม่แสดงcredentials
- ข้อ5ผ่าน · ไม่บันทึกภาพที่มีตัวตนหรือรายละเอียดบัญชีลงrepo
- ตรวจlogAPI/normalengine/offlineengineแบบไม่แสดงเนื้อหา: ค้นcredential/query markers
  และtraceback · ยังไม่เรียกผลนี้ว่าexact-secret-comparison (ไม่ได้เปิดผนึกเพื่อค้นlog)
- ข้อ7ถอนtestkeyที่BinanceTHและcleanupยังต้องเจ้าของดำเนินการ/ยืนยัน


### Manual real-key validation — 2026-10-07 ข้อ6/provenanceผ่าน

- logAPIทั้งหมดที่ตรวจประกอบด้วย lifecycle/access metadata + knowndeprecated422warning
  และliteral source-code warning line; ไม่มีrequestbodyหรือcredentials
- normalengine16lines: lifecycle/round counters8, HTTPmetadataที่queryตัดออก5,
  structuredvenuewarnings2, rowUUID/errorcode1
- offlineengine4lines: lifecycle/counters3 + structuredConnectErrorwarning1
- rawlog/credentialsไม่ถูกแสดง; signature=/timestamp=/APIheader markers0, Traceback0
  · ไม่เปิดผนึกเพื่อไล่ค้นlog และไม่เก็บscreenshotส่วนตัวในrepo
- provenanceone-off engine-role diagnostic ใช้ signer/crypto/wallet factory เดิม
  readonlyACCOUNTเท่านั้น, เปิดผนึกเฉพาะenginecontext; ไม่เลือกbalancesออกจากprocess
  · top-level fieldsetจริงตรงsanitizedfixtureทั้ง9=true
  · balance-entryfieldsตรงasset/free/locked=true
  · stdoutมีแค่booleans; ไม่เก็บrawresponse/ยอดเงินจริง/credentials
- ข้อ6ผ่านและV39provenanceยืนยันแล้ว
- เหลือข้อ7เจ้าของถอนเฉพาะtestkeyที่สร้างสำหรับงานนี้ที่BinanceTH
  และยืนยันผลUIข้อ1–4; F-07ยัง In Progress จนacceptance/cleanupครบ


### Final acceptance/cleanup — 2026-10-07

- เจ้าของยืนยันถอนเฉพาะtestkeysทั้งหมดที่BinanceTHแล้ว: manualข้อ7ผ่านจากownerreport
  ไม่อ้างว่าagentกดถอนหรือเห็นหน้าตลาดเอง
- หยุดmanualAPI/worker/UI, dropเฉพาะmanualDB29, ลบprivate master-key environment
  · ตรวจDB29ไม่อยู่แล้วและDBเดิมmigration0010ไม่เปลี่ยน
- final latest-code Frontend34tests/lint/type/buildผ่าน, E2E7ผ่านด้วยFakeVenue
  · OpenAPIและgeneratedTSเทียบตรง, Ruff/mypy183files/import-linter6contractsผ่าน
- latestDockerbuild/migrate/startup/HTTPsmoke/proxyผ่านบนisolatednetwork+ports
  · cleanupcontainers/network/volumesและsyntheticE2EDB30แล้ว
- Backend1402passedจากfinalNC19guardrun (หลังจากนั้นไม่มีsourceเปลี่ยน)
- tooling advisoriesเดิม4รายการยังเป็นงานแยก ไม่อัปเดตdependencyนอกF07
- ยังรอownerconfirmationว่าผลUIข้อ1–4ตรงbackendevidenceตามpendingquestion
  จึงยังไม่เปลี่ยนroadmapเป็นCompleted · ไม่มีcommit/push/merge


### Final sign-off — 2026-10-07

เจ้าของตอบ “ตรงครบ” ยืนยันผลUI manualข้อ1–4ตรงหลักฐานbackend
รวม screenshotข้อ5/logreviewข้อ6/ownerrevokeข้อ7: manualvalidationผ่านครบ
NC-18/NC-19ปิดแล้ว; automatedvalidationผ่านและcleanupเสร็จ

สถานะสุดท้าย: **implementation/validation/review F-07 เสร็จ**
- roadmap F-07 → Completed ตามนิยามcodeทำงานจริง+tests+validationผ่านครบ
- Backend1402passed/1real-marketcontractdeselected, Frontend34, E2E7
  lint/format/type/architecture/APIcontract/Dockerผ่าน
- ไม่มีcredentials/rawbalances/private screenshotในrepo; manualDB/masterkeys/processesล้างแล้ว
- ไม่commit/push/merge; changesยังอยู่workingtreeของfeature/f-07-api-keys
- ไม่ได้รับรองLive Trading/สิทธิ์ถอนเงิน/สิทธิ์เทรดของkey;
  NC-16/F-24 และ production key management F-31 เป็นงานต่อไปตามroadmap

## ซ่อม review — ค่ากลาง CSS (2026-10-07)

เจ้าของสั่งแก้ issue 2: ย้ายค่าระยะจาก ApiKeyPanel.css ไปค่ากลางตาม
standards/frontend.md หัวข้อ 2 โดยไม่เปลี่ยนหน้าตาหรือพฤติกรรม
ค้น frontend/src แล้วไม่มี stylesheet/token กลางเดิม จึงเพิ่ม
`frontend/src/accountPanels.css` และ import จาก ApiKeyPanel.css;
ใช้ CSS custom properties สำหรับ spacing, panel/control dimensions, typography,
border/focus และสีเดิม คง breakpoint 40rem เพราะ CSS variables ใช้ใน media query ไม่ได้
ตรวจว่าแทนค่า token แล้ว declarations ตรงกับ CSS เดิม พร้อม frontend lint/typecheck/build
เป็นการซ่อม F-07 ที่เจ้าของสั่ง ไม่เริ่ม implementation ของ F-08
