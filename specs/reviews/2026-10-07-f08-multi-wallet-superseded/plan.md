> Historical record: เจ้าของยกเลิกขอบเขตหลายกระเป๋า/sub-account 2026-10-07
> ไม่ใช่ spec ที่ใช้เริ่มงานต่อ; ผล tests เป็นของ implementation เดิม

# F-08 ทะเบียนกระเป๋าและผูก API key — Implementation Plan

> **For agentic workers:** ใช้ `executing-plans` ทำทีละ task หลังเจ้าของอนุมัติ plan.md และ validation.md; หากเจ้าของเลือกงานแบบ agent แยก ให้ใช้ `subagent-driven-development` แทน ทุกขั้นติดตามด้วย checkbox

สถานะ: **Superseded** — เจ้าของอนุมัติฉบับรวม TailAdmin และ shared QueryClient 2026-10-07
วันที่: 2026-10-07

**Goal:** ผู้ใช้สร้างทะเบียนกระเป๋าและผูก key ที่ตรวจผ่านแล้ว โดยยังไม่ยืนยันบัญชีจริงและยังใช้เทรดไม่ได้

**Architecture:** `infra/wallets` จัดเก็บทะเบียนภายใต้ UserSession/RLS; API ประกอบการยืนยันตัวตน การจัดเก็บ และ audit ใน transaction เดียวกัน ฐานข้อมูลตรวจ key เดิมซ้ำและเพดานด้วยล็อก/constraint จึงไม่พึ่งการตรวจหน้าเว็บ ไม่เพิ่มการเรียกตลาดหรือแก้ engine ของ F-07

**Tech Stack:** Python/FastAPI, SQLAlchemy async, Alembic, PostgreSQL รุ่นตาม `config/postgres.env` (ปัจจุบัน 16), React/TypeScript, TanStack Query, i18next, Tailwind CSS 4 (เสนอเพิ่มสำหรับ component จาก TailAdmin), Vitest, Playwright

## Global Constraints

- requirements Approved 2026-10-07; สูงสุด 6 กระเป๋าต่อผู้ใช้
- เลือกเทรดมือหรือบอท; หนึ่งกระเป๋ารันบอทได้สูงสุด 1 ตัวเมื่อมีงานบอท แต่ F-08 ไม่รันบอท
- ไม่แสดงยอด ไม่เปิด Live ไม่ส่งออเดอร์ ไม่ถอน/โอน/จัดการบัญชีย่อย
- การผูก key ต้อง TOTP ซ้ำทุกครั้ง ไม่รับ recovery grant และไม่มี grace period
- key ใหม่ไม่ผูกแทนในกระเป๋าเดิม; ลบ key แล้วคงทะเบียนและประวัติ
- บัญชีจริงยังไม่ยืนยัน; NC-21/NC-22 ยังเปิดก่อนใช้กระเป๋าเทรด
- ไม่ commit/push/merge จนเจ้าของสั่ง; ไม่แก้โค้ด F-07 ที่ไม่จำเป็นต่อการลบ key/audit

## 1. ของเดิมที่จะใช้ซ้ำ

| Path | ใช้ซ้ำอย่างไร |
|---|---|
| `infra/db/session.py` | `user_session`, `UserSession`, `require_user_session`; transaction และ RLS |
| `infra/db/engine.py` | `create_engine_for` ที่ปิด echo และซ่อน SQL parameters |
| `infra/db/errors.py` | แปล SQLSTATE โดยไม่คืนข้อความ/ค่าจาก driver |
| `infra/api_keys/storage.py` | ลบ key เดิมและรายการสรุป; อ่านเฉพาะคอลัมน์ที่ API มีสิทธิ์ |
| `infra/api_keys/records.py` | `ApiKeyStatus.ACTIVE`, `ApiKeySummary`; ไม่ใช้สถานะบัญชีแทนสิทธิ์ key |
| `infra/audit/events.py`, `writer.py`, `redaction.py` | `AuditEvent`, `record_event`, ป้องกันความลับในบันทึก |
| `services/api/authentication.py`, `routing_policy.py` | `Authenticated`, `current_user`, session/CSRF/TOTP และ anti-replay |
| `services/api/resources.py` | `engine_for` ไม่สร้าง connection engine ใหม่ต่อคำขอ |
| `services/api/api_key_routes.py` | แบบแผนการสร้าง/ลบที่มี audit และ validation ไม่สะท้อน input |
| `frontend/src/auth.ts` | `send`, `ApiRequestError`; cookie/CSRF/TOTP ไม่เขียนซ้ำ |
| `frontend/src/apiKeys.ts`, `ApiKeyPanel.tsx`, `apiKeyMessages.ts` | เลือก key จากข้อมูลสรุป รูปแบบ Query/mutation และ i18next |
| `backend/tests/conftest.py` | fixtures ของบทบาท DB และกุญแจทดสอบ |
| `frontend/e2e/helpers/totp.ts`, `frontend/e2e/api-keys.spec.ts` | เปิด TOTP และตรวจ key ผ่าน worker จริงกับ FakeVenue |

Paths ใต้ backend ในตารางนี้อยู่ภายใต้ `backend/src/tiewtrade/`

### ต้นฉบับ UI ที่จะใช้ซ้ำ

เจ้าของเลือกใช้ source ใน `references/admin-template/` (TailAdmin Pro React
package version 2.4.0) เพื่อสร้าง UI; เก็บต้นฉบับไว้สำหรับเทียบและตรวจ license
ไม่ import runtime จาก references และไม่คัดลอกทั้งแอป/dependency tree

| Source ใต้ references/admin-template/src/ | นำมาปรับใช้ |
|---|---|
| `layout/AppLayout.tsx`, `AppHeader.tsx`, `AppSidebar.tsx`, `context/SidebarContext.tsx` | shell ของหน้าจัดการบัญชีและ sidebar บนมือถือ; เปลี่ยน Outlet เป็น children และใช้เมนูเฉพาะความสามารถที่มีจริง |
| `components/ui/button/Button.tsx` | ปุ่มกลาง; รองรับ native button props รวม type, disabled และ aria attributes |
| `components/form/input/InputField.tsx`, `components/form/Label.tsx`, `components/form/Select.tsx` | ฟอร์ม key/use/TOTP; รักษา labels, controlled values, autocomplete และ error associations เดิม |
| `index.css` | คัดเฉพาะ theme tokens/utility styles ที่ component ใช้; ไม่ยก demo/plugin CSS และ remote font import ทั้งไฟล์ |

## 2. ส่วนต่อประสานและไฟล์

### Backend ใหม่

- `backend/src/tiewtrade/infra/wallets/records.py`: `WalletUse` (MANUAL/BOT), immutable `WalletSummary`, `WalletError`, `TooManyWalletsError`, `WalletKeyUnavailableError`, `WalletActivityUnknownError`; ไม่มี key เต็ม/secret/fingerprint ใน summary หรือ repr
- `backend/src/tiewtrade/infra/wallets/storage.py`: SQL และ transaction-safe operations
- `backend/src/tiewtrade/infra/wallets/__init__.py`: export เฉพาะ public interface
- `backend/src/tiewtrade/services/api/wallet_routes.py`: request/response schemas, routes และ wallet audit
- `backend/src/tiewtrade/services/api/safe_input_routes.py`: ย้าย validation handler เดิมของ F-07 มาเป็น helper ที่ตั้ง error code ได้ โดยคง status/response ของ F-07 เดิม
- `backend/migrations/versions/0012_wallet_registry.py`: ตาราง RLS triggers FK indexes และ audit shape

### Backend ที่แก้

- `services/api/app.py`: include wallet router
- `services/api/routing_policy.py`: ประกาศ routes ทุกเมธอด
- `services/api/api_key_routes.py`: ใช้ safe input helper และเพิ่ม audit ผลการลบ key ต่อ wallet ใน transaction เดิม
- `infra/audit/events.py`, `infra/audit/__init__.py`: WALLET subject/details/actions
- `backend/openapi.json`: สร้างใหม่จาก app

### Frontend ใหม่/ที่แก้

- ใหม่ `frontend/src/layout/AccountLayout.tsx`, `AccountHeader.tsx`, `AccountSidebar.tsx`: ปรับ source layout ของ TailAdmin ให้รับ children และใช้ auth/logout handlers เดิม
- ใหม่ `frontend/src/components/ui/Button.tsx`, `Input.tsx`, `Label.tsx`, `Select.tsx`: component ที่ปรับจากต้นฉบับ พร้อม native semantics
- ใหม่ `frontend/src/styles/admin-theme.css`: Tailwind/theme ที่เลือกใช้; อ้าง accountPanels.css สำหรับค่าร่วม ไม่ทำ token ซ้ำ
- แก้ `frontend/package.json`, `package-lock.json`, `vite.config.ts`: เพิ่มเฉพาะ tailwindcss/@tailwindcss/vite รุ่น 4 ที่พิสูจน์กับ toolchain เดิมได้
- แก้ `frontend/src/ApiKeyPanel.tsx` และ stylesheet: ใช้ component กลางจาก template โดยคง flow และข้อมูลเดิม

- ใหม่ `frontend/src/wallets.ts`, `WalletPanel.tsx`, `WalletPanel.css`, `walletMessages.ts`
- ใช้ซ้ำ `frontend/src/accountPanels.css`: ค่ากลาง spacing/ขนาด panel ที่แยกจาก ApiKeyPanel.css ในการซ่อม review F-07; WalletPanel อ้าง tokens เดิม ไม่สร้างชุดสี/font ใหม่
- ใหม่ `frontend/src/AccountSession.tsx`: QueryClientProvider ร่วมที่มี lifecycle ต่อผู้ใช้ ครอบ ApiKeyPanel และ WalletPanel
- แก้ `frontend/src/AuthPanel.tsx`: วางทั้งสอง panel ภายใน AccountSession ที่ key ด้วย identity.user_id; WalletPanel อยู่หลังส่วนจัดการ key
- แก้ `frontend/src/ApiKeyPanel.tsx`: ย้าย QueryClient/provider และ cleanup ของ KeySession ไป AccountSession; หลังลบ key ให้ invalidate wallet query ผ่าน client ร่วมของผู้ใช้เดียวกัน
- แก้ `frontend/src/ApiKeyPanel.css`: อ้างค่ากลางจาก accountPanels.css โดยหน้าตา F-07 เดิมต้องไม่เปลี่ยน
- แก้ `frontend/src/api-types.ts`: สร้างจาก OpenAPI เท่านั้น
- คง flow และกฎ auth/session/TOTP กับ polling ของ F-07; เปลี่ยน presentation เฉพาะหน้าจัดการบัญชี/key/wallet ไม่ redesign หน้า login/register/TOTP ในงานนี้

### สัญญาของ storage

```python
async def create_wallet(
    session: UserSession, *, key_id: UUID, use: WalletUse
) -> WalletSummary: ...
async def wallets_for(session: UserSession) -> tuple[WalletSummary, ...]: ...
async def wallet_for(session: UserSession, wallet_id: UUID) -> WalletSummary | None: ...
async def lock_wallets_for_key_deletion(
    session: UserSession, key_id: UUID
) -> tuple[UUID, ...]: ...
async def request_use_change(
    session: UserSession, wallet_id: UUID, use: WalletUse
) -> None: ...
```

`...` ในบล็อกนี้เป็น type signatures ไม่ใช่ implementation ที่ให้เขียนเป็น stub
ผู้ใช้มาจาก `session.user_id` ไม่รับ owner จาก payload

WalletSummary fields: `id`, `use`, `created_at`, `key_id: UUID | None`,
`key_label: str | None`, `key_public_tail: str | None`, `key_status: ApiKeyStatus | None`,
`connection_status: LINKED_UNVERIFIED | DISCONNECTED`, `account_verified=False`,
`may_trade=False`, `may_change_use=False` การเชื่อมเป็นเพียงทะเบียน ไม่เก็บโหมดเทรดที่ยังไม่มี
เมื่อมี Paper/Live ภายหลัง งานนั้นต้องกำหนด mode ตามกฎ immutable เดิม

`request_use_change` ตรวจ ownership ก่อน แล้วปฏิเสธด้วย WALLET_ACTIVITY_UNKNOWN ใน F-08
เพราะยังไม่มีแหล่งสถานะ bot/order/position ที่พิสูจน์ครบ ห้ามสร้างข้อมูล idle ปลอม
หรือทดสอบด้วยการใส่ true ใน production; งานที่มีหลักฐานจริงจึงค่อยเปิดทางเปลี่ยนประเภท

## 3. ฐานข้อมูลและการแข่งขันของคำขอ

### ตารางเดียว: wallet_registry

```sql
ALTER TABLE public.user_api_keys
    ADD CONSTRAINT user_api_keys_id_owner UNIQUE (id, user_id);

CREATE TABLE public.wallet_registry (
    id uuid PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES public.users(id),
    use text NOT NULL CHECK (use IN ('MANUAL', 'BOT')),
    key_id uuid,
    key_fingerprint bytea,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT wallet_key_owner FOREIGN KEY (key_id, user_id)
        REFERENCES public.user_api_keys(id, user_id)
        ON DELETE SET NULL (key_id),
    CONSTRAINT wallet_key_shape CHECK (
        (key_id IS NULL AND key_fingerprint IS NULL)
        OR (key_id IS NOT NULL AND key_fingerprint IS NOT NULL
            AND octet_length(key_fingerprint) = 32)
    )
);
CREATE INDEX wallet_registry_owner ON public.wallet_registry(user_id, created_at, id);
CREATE INDEX wallet_registry_key_id ON public.wallet_registry(key_id)
    WHERE key_id IS NOT NULL;
CREATE UNIQUE INDEX wallet_registry_one_key
    ON public.wallet_registry(key_fingerprint) WHERE key_id IS NOT NULL;
ALTER TABLE public.wallet_registry ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.wallet_registry FORCE ROW LEVEL SECURITY;
CREATE POLICY wallet_registry_api_self ON public.wallet_registry
    FOR ALL TO tiewtrade_api
    USING (user_id = public.tiewtrade_current_user_id())
    WITH CHECK (user_id = public.tiewtrade_current_user_id());
GRANT SELECT (id, user_id, use, key_id, created_at)
    ON public.wallet_registry TO tiewtrade_api;
GRANT INSERT (id, user_id, use, key_id)
    ON public.wallet_registry TO tiewtrade_api;
GRANT UPDATE (use) ON public.wallet_registry TO tiewtrade_api;
```

ไม่ให้ API อ่าน/เขียน fingerprint โดยตรง ไม่ให้ engine/engine_scan/auth/market-data
เข้าตารางใหม่นี้ เพราะยังไม่มีงานที่ต้องใช้ ไม่เพิ่มสิทธิ์อ่าน secret ของบทบาทใด

### BEFORE INSERT/UPDATE trigger — SECURITY INVOKER

- functions ระบุ `SET search_path = pg_catalog, public` และ schema qualify objects; ไม่ใช้ SECURITY DEFINER/BYPASSRLS
- INSERT ตรวจ NEW.user_id เท่ากับ current user ก่อนทำอะไร จากนั้นใช้
  `pg_advisory_xact_lock(7008, hashtext(NEW.user_id::text))`; namespace 7007 เป็นของ F-07
- ภายใต้ล็อก ตรวจ count กระเป๋าทั้งหมดของผู้ใช้ `< 6` รวมกระเป๋าที่ลบ key แล้ว
- อ่าน key ด้วย `SELECT key_public, status FROM public.user_api_keys WHERE id=NEW.key_id AND user_id=NEW.user_id FOR UPDATE`
  หากไม่พบหรือไม่ ACTIVE ปฏิเสธด้วย SQLSTATE 23514 โดยข้อความคงที่ที่ไม่มีค่าจาก key
- ใช้ `pg_catalog.sha256(pg_catalog.textsend(key_public))` ตั้ง fingerprint จาก key ที่ DB อ่านเอง
  ไม่รับ digest จาก HTTP/API; ข้อมูล key ที่ F-07 ยอมรับเป็น printable ASCII และไม่ case-fold
- UPDATE ห้ามเปลี่ยน id/user_id/created_at และห้ามเปลี่ยน key_id เป็นค่าที่ไม่เป็น NULL
  การลบ parent ผ่าน FK ตั้ง key_id=NULL แล้ว trigger ต้องตั้ง fingerprint=NULL ด้วย
- การเปลี่ยน use ปฏิเสธใน F-08 เช่นเดียวกับ API เพราะไม่มีหลักฐาน RQ-14;
  UPDATE ที่ FK เปลี่ยนเฉพาะ key_id เป็น NULL ต้องผ่าน เพื่อไม่ขวางการลบ key
- key ซ้ำคนละแถวหรือคนละผู้ใช้ชน UNIQUE เดียวกัน; ข้อผิดพลาด API ใช้ WALLET_KEY_UNAVAILABLE
  ไม่แสดงเจ้าของ wallet id digest constraint name หรือ driver detail

storage ทำ count/ACTIVE precheck ภายใต้ล็อกชุดเดียวกันเพื่อคืน error code ที่เข้าใจได้
แต่ trigger/unique/FK ยังคงเป็นด่านเมื่อข้าม helper การชน hash ทำให้ปฏิเสธการผูก
ไม่อนุญาตให้ข้าม uniqueness; fingerprint ไม่ใช่หลักฐานรหัสบัญชีจริง

### ลำดับ transaction

**สร้าง:** user advisory lock → count → key row FOR UPDATE → INSERT wallet
→ audit WALLET_CREATED และ WALLET_KEY_BOUND → commit คืน WalletView หลัง commit
หาก insert/audit ล้มเหลว rollback ทั้งทะเบียนและการผูก ไม่มี wallet ครึ่งทาง

**ลบ key:** `lock_wallets_for_key_deletion` lock key row ก่อนอ่าน wallet IDs ภายใต้ RLS
→ เรียก `delete_key` ของเดิม → FK/trigger ตัด key_id และล้าง fingerprint
→ audit API_KEY_DELETED และ WALLET_KEY_DISCONNECTED สำหรับ IDs ที่อ่านไว้ → commit
ใช้ UserSession เดียวและไม่เพิ่มการยืนยัน TOTP ในเส้นทางลบ key
ถ้า key ถูกลบระหว่างรอสร้าง จะไม่สร้าง wallet; ถ้าสร้างสำเร็จก่อนลบ ต้องเก็บ audit wallet ที่ถูกตัดครบ

ไม่เก็บ fingerprint หรือ 4 หลักท้ายไว้หลังลบ key ไม่เก็บ credential สำเนาใน wallet
ทะเบียนที่คงอยู่ยังนับในเพดาน 6 และยังไม่มี endpoint ลบทะเบียนในขอบเขตที่อนุมัติ

### Audit และ migration downgrade

เพิ่ม `SubjectKind.WALLET`, `WalletDetails` และ actions `WALLET_CREATED`,
`WALLET_KEY_BOUND`, `WALLET_KEY_DISCONNECTED` ใน enum และ frozen SQL audit shape
ของ migration 0012 พร้อมกัน อ้าง subject_id เป็น UUID ของ wallet
CREATED ใช้ details `{}`; BOUND/DISCONNECTED ใช้ `{'key_id': '<UUID ของแถว>'}` เท่านั้น
actor USER=owner, outcome SUCCEEDED, mode NOT_APPLICABLE และ failure_code NULL
ไม่เพิ่ม successful USE_CHANGED เพราะ F-08 ปฏิเสธการเปลี่ยนประเภท

upgrade เป็น additive ต่อ F-07 ไม่แก้ migration 0009/0011 เดิม
ก่อน downgrade หากมี wallet_registry rows ให้ปฏิเสธด้วยข้อความคงที่และไม่ลบข้อมูล
ถ้าไม่มี rows จึงถอด trigger/table/composite constraint; เก็บ audit ใหม่ที่เกิดแล้ว
และคืน audit shape ก่อน F-08 แบบ NOT VALID ตาม pattern 0011 ห้าม rewrite audit

อ้างอิงกลไก PostgreSQL: [RLS](https://www.postgresql.org/docs/16/ddl-rowsecurity.html),
[Constraints](https://www.postgresql.org/docs/16/ddl-constraints.html),
[Binary functions](https://www.postgresql.org/docs/16/functions-binarystring.html)

## 4. API และ UX

| เมธอด/path (app มี /api ผ่าน proxy) | Request | Result | ROUTE_RULES |
|---|---|---|---|
| GET /wallets | ไม่มี | WalletView[] เรียง created_at/id | RouteRule() ไม่ต่ออายุ session |
| POST /wallets | `{key_id: UUID, use: MANUAL/BOT}` | 201 WalletView หลัง commit | renews=True, reverify=True, ไม่รับ recovery grant |
| POST /wallets/{wallet_id}/use | `{use: MANUAL/BOT}` | 404 เมื่อไม่มี/ของผู้อื่น; 409 WALLET_ACTIVITY_UNKNOWN เมื่อเป็นของตน | renews=True, ไม่ reverify เพราะไม่ผูก key |

ไม่มี API รับ key เต็ม/secret/owner/fingerprint/balance/mode ใน wallet request
Pydantic `ConfigDict(extra='forbid')`; validation handler คืน WALLET_INPUT_REJECTED
โดยไม่สะท้อน input เส้นทางเปลี่ยน use ไม่มี successful response ในขอบเขตนี้
error ที่กำหนด: WALLET_NOT_FOUND (404), WALLET_LIMIT_REACHED (409),
WALLET_KEY_UNAVAILABLE (409), WALLET_ACTIVITY_UNKNOWN (409), WALLET_INPUT_REJECTED (422)
กรณี key ไม่พบ/ของผู้อื่นต้อง 404 ข้อความแบบเดียวกัน ไม่บอกผู้ใช้เจ้าของ key

### QueryClient ร่วมและ lifecycle ของบัญชี

`frontend/src/AccountSession.tsx` เป็นขอบเขต cache ของส่วนจัดการบัญชีใน AuthPanel:

```text
AuthPanel (authenticated)
└── AccountSession key={identity.user_id}
    └── QueryClientProvider (client หนึ่งตัวต่อ session ที่ mount)
        ├── ApiKeyPanel identity={identity}
        └── WalletPanel identity={identity}
```

ย้ายการสร้าง QueryClient แบบ `useState` และ cleanup จาก
`frontend/src/ApiKeyPanel.tsx` KeySession มาไว้ใน AccountSession; ApiKeyPanel
และ WalletPanel ใช้ `useQueryClient()` จาก provider นี้ ห้ามมี provider ซ้อนที่สร้าง
client แยกใน panel หรือใช้ module-global client ใช้ options เดิมของ F-07:
queries `{retry: false, gcTime: 0}` และ mutations
`{retry: false, gcTime: 0, networkMode: 'always'}`; คง polling 5 วินาทีของ key เดิม

ทั้งสอง panel ใช้ query key เดียวกันสำหรับสรุป key คือ
`['api-keys', identity.user_id]` และ queryFn `fetchApiKeys` เดิม; WalletPanel
ไม่สร้างสำเนารายการ key ใน local state ส่วนรายการกระเป๋าใช้
`['wallets', identity.user_id]` หลัง DELETE key สำเร็จ ให้ invalidate ทั้งสอง
query key แบบ `exact: true` ผ่าน client ร่วม และรอการ refetch ของ active queries
ทั้งสองรายการ; สถานะกระเป๋ามาจาก server ไม่แก้เป็น DISCONNECTED เอง
หาก refetch ล้มเหลว ให้แสดง error/สถานะกำลังปรับปรุงข้อมูลตาม query state
ไม่แสดงข้อมูลเก่าว่าเป็นผลที่ยืนยันล่าสุด และให้ refresh/focus ลองอ่านใหม่ได้

เมื่อ logout/session หมดอายุ AuthPanel ต้อง unmount AccountSession; เมื่อเปลี่ยน
identity.user_id ต้อง remount ด้วย React key จึงได้ client ใหม่ เริ่มจาก cache ว่าง
cleanup ต้อง cancel queries ที่ค้างและ clear query/mutation cache ของ client เก่า;
queryFn ส่ง AbortSignal ต่อให้ fetch ทั้ง key และ wallet เพื่อหยุดคำขออ่านที่ค้าง
ผลคำขอเก่าต้องไม่ไปเขียน client ของผู้ใช้ใหม่ ไม่ retry mutation หรือเรียก mutation
ซ้ำจาก cleanup และไม่ persist cache/credentials/TOTP ไป storage

WalletPanel ใช้ TanStack Query key `['wallets', identity.user_id]`; เลือก key จาก
query สรุป F-07 และ submit ได้เฉพาะ ACTIVE พร้อม select ประเภทและช่อง TOTP
server เป็นผู้ตรวจซ้ำเสมอ ไม่แสดงช่อง API key/secret ใหม่
หัวข้อ “กระเป๋า” และคำอธิบาย “ทะเบียนนี้ยังใช้เทรดไม่ได้” อยู่เหนือรายการ
แต่ละรายการแสดงประเภท เวลา และสถานะ; เมื่อมี key แสดงชื่อ key และ 4 หลักท้าย
พร้อม “ยังไม่ยืนยันบัญชีจริง”; เมื่อไม่มี key แสดง “ยังไม่เชื่อมต่อ”
ไม่มีปุ่มเริ่มบอท/เทรด/เปลี่ยน key/ลบทะเบียน และการเปลี่ยนประเภทถูกปิดพร้อมเหตุผล
ไม่มีวงรอบอัปเดตยอดหรือ WebSocket

### การนำ TailAdmin มาใช้

เลือกปรับ source/component แทนการแทนที่ frontend ทั้งแอป โดยคง React 18,
Vite 6 และ Node 22 ของโปรเจกต์ ไม่คัดลอก package.json/lockfile ของ template
ซึ่งระบุ React 19/Vite 8 และไม่เพิ่ม react-router/chart/map/calendar libraries
เพียงเพื่อทำ shell; component ที่พึ่ง alias @/ หรือ utils ของ template ต้องปรับ
imports และย้ายเฉพาะ helper ที่จำเป็นเข้ามาใน frontend พร้อมระบุที่มาใน comment

เพิ่ม Tailwind 4 เป็นข้อเสนอของแผนนี้: ก่อนย้าย UI ให้ build component ตัวอย่าง
ด้วย toolchain เดิมและรัน lint/typecheck/build; บันทึก exact versions ใน lockfile
หากใช้ร่วมกันไม่ได้ ให้หยุดเสนอการเปลี่ยนแผน ไม่อัปเกรด React/Vite เอง
จำกัด utility generation ให้ source ของ frontend ไม่ scan references/demo;
นำเข้า theme/utilities โดยไม่เปิด global Preflight ที่เปลี่ยน native styles ของ
หน้า auth/TOTP เดิม และ scope base/theme overrides ใต้ AccountLayout
ไม่เพิ่ม CSS reset ทั่วแอป; อ้าง tokens กลาง accountPanels.css โดยไม่ประกาศซ้ำ

AccountLayout ครอบเฉพาะส่วน signed-in จัดการบัญชี/key/wallet ภายใน AuthPanel;
AccountSession/provider ร่วมยังเป็นขอบเขต cache ของทั้งสอง panelตามหัวข้อก่อนหน้า
เมนูมีเฉพาะบัญชี/API key/กระเป๋าที่ใช้งานได้จริง ไม่ใส่ demo links, mock metrics,
balance, trading หรือ bot actions ปุ่ม logout ใช้ handler เดิม ไม่มี auth จำลอง
sidebar มือถือเปิด/ปิดด้วยปุ่มที่มี aria-expanded; Escape/Backdrop ปิดได้และคืน focus
ไม่บังคับเพิ่ม theme switch หรือหน้า demo จากต้นฉบับ

ใช้ tokens สี/spacing จาก template เฉพาะส่วนที่ต้องใช้; typography มี fallback
สำหรับภาษาไทย และไม่โหลด remote fonts จาก Google โดยอัตโนมัติ ปุ่มกลางต้อง
กำหนด type ชัดเจน ไม่ให้ปุ่มลบ/ยกเลิกเผลอ submit ฟอร์ม; input/label/select
ต้องส่งต่อ id/name/aria-invalid/aria-describedby และ attributes ที่ flow เดิมใช้
ข้อความทั้งหมดผ่าน i18next ของโปรเจกต์ ไม่ใช้ demo text/auth/data จาก template

รักษา semantic labels และ keyboard navigation,

aria-live สำหรับผลการส่ง และข้อความผิดพลาดผูกกับ field ที่เหมาะสม
ทุกข้อความผ่าน walletMessages.ts ของ i18next แบบ F-07; ภาษาไทยเป็นค่าเดิม
ไม่ขยายเป็นระบบสลับภาษาทั้งแอป (F-30)

หลังส่งคำขอ clear TOTP ทั้งสำเร็จและล้มเหลว; ไม่เก็บ code ใน Query key/error/log และ
reset mutation variables หลังจบคำขอ เมื่อสร้างสำเร็จ invalidate wallets query; หลังลบ key invalidate
ทั้ง api-keys และ wallets ของผู้ใช้เดียวกัน; focus/reload ดึงสถานะใหม่จาก server
หากคำขอสร้าง timeout ไม่ retry mutation อัตโนมัติและไม่แสดงว่าสำเร็จ ให้ผู้ใช้ตรวจรายการ
session หมดอายุ/logout ต้องไม่แสดง cache ของผู้ใช้ก่อนหน้า
wallets.ts ส่ง error เฉพาะ allowlist ของรหัส wallet/auth ที่กำหนด; response ที่ไม่รู้จัก
ใช้ WALLET_REQUEST_FAILED ไม่เก็บข้อความดิบจาก server/proxy ใน mutation cache

## 5. Tasks และรอบทดสอบ

### Task 1 — Schema, RLS และการกัน key ซ้ำ

**Files:** migration 0012; ใหม่ `backend/tests/infra/wallets/test_constraints.py`,
`test_permissions.py`, `test_concurrency.py`; แก้ `backend/tests/infra/db/test_migrations.py`

**Consumes:** users, user_api_keys, current-user RLS function และ role fixtures ของ F-03/F-07
**Produces:** wallet_registry ที่ API สร้างได้ด้วย id/user/use/key_id และ DB คำนวณ fingerprint เอง

- [x] เขียนเทสต์ migration/constraints ตาม SQL ในหัวข้อ 3 ก่อน migration:
  same key in two rows → second insertion rejected; two different keys with same tail → both accepted;
  RLS cross-user inserts/reads denied; count 5 + two concurrent inserts → exactly one succeeds
- [x] Run `cd backend && uv run pytest tests/infra/wallets/test_constraints.py tests/infra/wallets/test_permissions.py tests/infra/wallets/test_concurrency.py -q`; ก่อน migration ต้องแดงเพราะไม่มี table
- [x] สร้าง migration 0012 ตาม DDL และ trigger rules หัวข้อ 3; ไม่เปลี่ยน config รุ่น DB
- [x] Run migration บนฐานข้อมูลทดสอบ `cd backend && uv run alembic upgrade head`
- [x] รัน tests เดิมและ migration cycle; ต้องไม่มี skip ของ DB tests และ downgrade ที่มีทะเบียนต้องไม่ลบข้อมูล

ตัวอย่าง assertion ของกรณี FK ที่ต้องตรวจด้วย actual role:

```python
assert wallet_before.key_id == key_id
assert wallet_after.key_id is None
assert wallet_after.connection_status == 'DISCONNECTED'
assert wallet_after.id == wallet_before.id
```

### Task 2 — Storage, audit และการลบ key เดิม

**Files:** infra/wallets สามไฟล์; audit/events.py และ __init__.py;
ใหม่ `backend/tests/infra/wallets/test_storage.py`, `test_audit.py`;
แก้ `backend/tests/infra/audit/test_event_shape.py`

**Consumes:** schema Task 1, UserSession, SQLSTATE translation, ApiKeyStatus, record_event
**Produces:** storage interfaces หัวข้อ 2 และ WalletDetails/actions ที่ตรง DB shape

- [x] เขียนเทสต์ create/list/ownership/quota/ACTIVE และตรวจ summary ไม่มี credential/digest
- [x] Run `cd backend && uv run pytest tests/infra/wallets/test_storage.py tests/infra/wallets/test_audit.py -q`; ก่อน module ต้องแดงจาก missing import
- [x] ทำ immutable records และ storage ตามลำดับ transaction หัวข้อ 3; ห้ามผ่าน ScanSession
- [x] เพิ่ม WalletDetails validation: details ของ CREATED ว่าง; BOUND/DISCONNECTED มีเฉพาะ key_id UUID
- [x] ทดสอบ injected audit failure ย้อน wallet creation และ key deletion ทั้งชุด
- [x] ทดสอบ concurrent bind/delete ผ่านสอง actual sessions พร้อม barriers ไม่ใช้ sleep เพื่อสร้าง race
- [x] รัน storage/audit/key tests ทั้งชุด; key_delete semantics และ worker verification ของ F-07 ต้องยังผ่าน

### Task 3 — API, TOTP และ OpenAPI

**Files:** wallet_routes.py, safe_input_routes.py, app.py, routing_policy.py,
api_key_routes.py, backend/openapi.json; ใหม่ `backend/tests/api/test_wallet_routes.py`;
แก้ `test_api_key_routes.py`, `test_route_classification.py`

**Consumes:** Task 2 interfaces, current_user/engine_for และ authentication middleware เดิม
**Produces:** routes/schemas ในหัวข้อ 4 โดยไม่เพิ่มเส้นทางเปลี่ยน key

- [x] เขียน API tests สำหรับ session/CSRF/TOTP; replay ของรหัสที่ใช้เพิ่ม key ต้องผูก wallet ไม่ได้
- [x] Run `cd backend && uv run pytest tests/api/test_wallet_routes.py -q`; ก่อน router ต้องแดงเพราะ 404 ของ route ที่ยังไม่มี
- [x] ย้าย safe validation handler ของ F-07 ไป helper โดย tests เดิมคง expected responses
- [x] เพิ่ม router และ ROUTE_RULES ตามตาราง; actor มาจาก Authenticated และ owner มาจาก session
- [x] ปรับ remove_key ให้ lock key/gather wallet IDs ก่อน delete และบันทึก disconnected หลัง delete ใน UserSession เดิม
- [x] ทดสอบเส้นทาง type-change ปฏิเสธและไม่มี successful audit/data mutation; ไม่มี binding replacement route
- [x] Run API tests และ `uv run python -m tiewtrade.services.api.openapi_export`

ตัวอย่าง HTTP contract assertion:

```python
assert response.status_code == 201
view = response.json()
assert view['connection_status'] == 'LINKED_UNVERIFIED'
assert view['account_verified'] is False
assert view['may_trade'] is False
assert view['may_change_use'] is False
assert 'key_fingerprint' not in view
```

### Task 4 — UI และเส้นทางผู้ใช้จริงผ่าน FakeVenue

**Files:** frontend files หัวข้อ 2; ใหม่ `frontend/tests/WalletPanel.test.tsx`,
`frontend/tests/AccountSession.test.tsx`, `frontend/tests/AccountLayout.test.tsx`, `frontend/e2e/wallets.spec.ts`; แก้ F-07 deletion tests โดยไม่เปลี่ยน expected auth behavior

**Consumes:** generated WalletView/CreateWalletRequest, Identity, send, F-07 key summary queries
**Produces:** WalletPanel ที่สร้างทะเบียนได้และแสดงสถานะตาม server

- [x] ตรวจ component paths/imports/license ของ source ที่เลือก; ไม่เปลี่ยนต้นฉบับใน references
- [x] เพิ่มเฉพาะ Tailwind 4 ที่จำเป็นและทดสอบกับ React 18/Vite 6; เก็บ exact lockfile และผ่าน lint/typecheck/build ก่อนย้าย UI
- [x] สร้าง AccountLayout/component กลางจาก source ที่ระบุ; เพิ่ม layout tests สำหรับ keyboard/mobile/sidebar และ native form semantics
- [x] ตรวจหน้า login/register/TOTP เดิมว่าไม่มี CSS reset/theme leakage
- [x] สร้าง types ด้วย `cd frontend && npm run gen:api`
- [x] เขียน Vitest tests ของ empty/loading/error/ACTIVE-only/TOTP/uncertain mutation/result และ cache isolation
- [x] Run `cd frontend && npm run test -- tests/WalletPanel.test.tsx`; ก่อน panel ต้องแดงจาก missing module
- [x] ทำ wallets.ts, walletMessages.ts, WalletPanel และ CSS ตาม UX หัวข้อ 4; server state อยู่ใน Query เท่านั้น
- [x] ย้าย QueryClient/provider/cleanup จาก KeySession ไป AccountSession ตามหัวข้อ 4; ปรับ F-07 panel tests ให้ใช้ provider ร่วม
- [x] เพิ่มทั้งสอง panel ใน AccountSession ของ AuthPanel และ invalidation แบบ exact หลัง F-07 ลบ key; ไม่แก้ธุรกิจของ key worker
- [x] ทดสอบ AccountSession โดย render ทั้งสอง panel จริง: ลบ key แล้วรายการ key และ wallet refetch โดยไม่ reload/focus; refetch failure ต้องไม่อ้างข้อมูลเก่าว่าเป็นผลล่าสุด
- [x] ทดสอบ logout/session expired/เปลี่ยนผู้ใช้ขณะ GET ค้าง: cancel+clear cache เก่า; response ที่มาช้าไม่ปรากฏในบัญชีใหม่; ไม่มี mutation retry
- [x] E2E สมัคร/เปิด TOTP/เพิ่ม fake key/worker ตรวจผ่าน/สร้าง wallet ด้วยรหัสใหม่/refresh/ลบ key
  แล้วต้องเห็นทะเบียนเดิมเป็นยังไม่เชื่อมต่อ และไม่มี pageerror
- [x] Run `npm run test`, `npm run lint`, `npm run typecheck`, `npm run test:e2e -- e2e/wallets.spec.ts`

ตัวอย่าง UI assertions ที่ใช้ user-visible labels:

```typescript
await expect(panel.getByText('ยังไม่ยืนยันบัญชีจริง', { exact: true })).toBeVisible();
await expect(panel.getByText('ทะเบียนนี้ยังใช้เทรดไม่ได้', { exact: true })).toBeVisible();
await expect(panel.getByRole('button', { name: 'เริ่มบอท' })).toHaveCount(0);
```

### Task 5 — ตรวจครบ เรื่องเอกสาร และส่งให้เจ้าของรีวิว

**Files:** validation.md, roadmap.md และ README.md เฉพาะวิธีใช้ทะเบียน F-08

- [x] รันทุก command ใน validation.md ด้วย actual database roles; รายงาน failures/skips ตามจริง
- [x] ตรวจ requirement-to-validation mapping และ output/log hygiene ด้วย synthetic credential markers
- [x] ตรวจ UI ด้วย browser และ screenshot desktop/mobile ตาม validation ก่อนอ้างว่าพร้อมใช้
- [x] รีวิว diff กับ requirements/standards และแก้ข้อพบในขอบเขตที่อนุมัติ
- [x] บันทึกหลักฐานใน validation; roadmap Completed ได้เมื่อทุกเกณฑ์ผ่านเท่านั้น
- [x] ยังไม่ commit/push/merge; รอเจ้าของสั่ง และคง NC-21/NC-22 สำหรับงานใช้เทรด

## 6. ความเสี่ยงและเงื่อนไขเริ่ม implementation

| เรื่อง | วิธีป้องกัน/ตรวจ |
|---|---|
| F-07 ยังไม่ commit และ checkout ปัจจุบันมี diff ใหญ่ | ห้าม reset/stash/ย้ายงานเดิมหรือเริ่ม F-08 บน branch F-07; ก่อนโค้ดต้องมี branch/worktree ของ F-08 ที่มี baseline F-07 ครบ ใช้ using-git-worktrees และขอการจัดเก็บ F-07 เมื่อจำเป็น; ไม่ commit เอง |
| ห้ามแก้ approved plan ต่างไปก่อน | หาก DDL/trigger/locking ที่อนุมัติใช้ไม่ได้จริง ให้หยุดพร้อมหลักฐานและขอแก้ plan ก่อนแก้แนวทาง |
| digest เป็นข้อมูลเชื่อมโยง credential | ไม่ส่งออก ไม่ log ไม่ให้ API อ่าน และล้างพร้อม key_id เมื่อ key ถูกลบ |
| global unique มีผลข้าม RLS | ทำ error แบบคงที่ไม่คืนเจ้าของ/ID/constraint/ค่าที่ชน; ทดสอบสองผู้ใช้ด้วย key เดียวกัน |
| fingerprint กัน key เดิม ไม่กันบัญชีจริง | UI/account_verified/may_trade แสดงข้อจำกัดและไม่เปิด trading capability |
| type-change ยังไม่มีหลักฐานกิจกรรม | API และ DB ปฏิเสธ ไม่ใช้ default idle; เปิดได้หลังงานถัดไปมี spec และหลักฐานครบ |
| audit migration ถอยแล้วสูญเสียข้อมูล | ห้าม downgrade เมื่อมีทะเบียน และไม่แก้ audit เดิม; ทดสอบข้อปฏิเสธและรอบ schema เปล่า |
| quota หลังลบ key | wallet ยังอยู่และยังนับใน 6; ไม่เพิ่มลบทะเบียนหรือรีไซเคิลประวัติโดยไม่มี requirements ใหม่ |

## 7. Self-review ก่อนส่งอนุมัติ

- requirements RQ-1–RQ-22 ครอบใน validation.md; RQ-11/RQ-12 ถอนและไม่เพิ่มงานให้มัน
- ไม่ตั้ง requirement ใหม่เรื่องสิทธิ์ตลาด ไม่เพิ่ม secret storage/cryptographic key/venue endpoint
- interfaces storage, routes และ generated frontend types ใช้ชื่อเดียวกันตามหัวข้อ 2/4
- การสร้างผูก key พร้อมกันไม่ทำให้มี wallet ที่รับ replacement ภายหลัง
- คำสั่งใน tasks เป็นคำสั่งที่จะรันหลังอนุมัติ ไม่ใช่ผลทดสอบที่เกิดแล้ว
- ขั้นถัดไปให้เจ้าของอนุมัติ plan.md และ validation.md ก่อน implementation


## 8. บันทึกการทำตามแผน — 2026-10-07

Tasks 1–5 ทำและตรวจแล้ว ดูผลจริงใน validation.md หัวข้อ 7
แยก baseline F-07/branch F-08 แล้วก่อนเริ่มโค้ด; ข้อเสี่ยง checkout ในหัวข้อ 6 ได้รับการแก้
การเปลี่ยน presentation F-07 เป็น component จาก TailAdmin เป็นขอบเขต UI ที่เจ้าของ
อนุมัติในหัวข้อ 2/4; ไม่เปลี่ยนธุรกิจ verification/retry/secret ของ F-07
ไม่มีการเปลี่ยนข้อกำหนดการเทรดหรือแก้ต้นฉบับ references/admin-template
ยังไม่ commit/push/merge F-08; review implementation/quality PASS; dev dependency
security backlog เดิมบันทึกแยกใน validation และ review record
