# fasttrade — API Spec (REST + WebSocket)

| Field | Value |
|---|---|
| Status | **v0.3** — A-01 ถึง A-08 Decided (2026-09-22) |
| Date | 2026-09-22 |
| Based on | [MVP Requirements v0.23](../requirements/mvp.md), [Architecture v0.3](../architecture/architecture.md), [Data Model v0.3](data-model.md), [Calculation Spec v0.3](calculation.md) |
| Scope | สัญญาระหว่าง Frontend กับ `api`: conventions, authentication, command model, REST endpoints, WebSocket, error codes |
| Out of scope | Internal messages ระหว่าง engine / execution / notifier (อยู่ใน architecture §6), implementation |

> **หลักการ**
> - `api` **ไม่แก้ state การเทรดเอง** ทุกการเปลี่ยน state ของ Portfolio เป็น **command** ที่บันทึกลง Postgres แล้วให้ engine เจ้าของ Workspace ประมวลผล (ADR-0002, ADR-0009, ADR-0011)
> - OpenAPI generate จาก FastAPI และ Frontend generate type จาก OpenAPI (ADR-0006) — เอกสารนี้เป็นสัญญาระดับ design
> - Endpoint ที่ระบุ **[P2]** ใช้ใน Phase 2 (Live) เท่านั้น

---

## 1. Conventions

| เรื่อง | กติกา |
|---|---|
| Base path | `/api/v1` |
| Format | JSON, `snake_case` |
| เงิน / ราคา / จำนวน | **string** ของเลขทศนิยม (เช่น `"0.00125"`) ห้ามส่งเป็น JSON number เพื่อไม่ให้เสีย precision (FR-MRG-08) |
| เวลา | ISO-8601 UTC (`2026-09-22T10:00:00Z`) — Frontend แปลงตาม timezone ของ User (FR-I18N-06) |
| ID | UUID string; `symbol_id` เป็น integer |
| Enum | `UPPER_SNAKE_CASE` ตาม Glossary (เช่น `USDM_FUTURES`, `BUY`, `CROSS`) |
| Pagination | cursor: `?limit=50&cursor=<opaque>` → `{ "items": [...], "next_cursor": "..." \| null }`; `limit` สูงสุด 200 |
| Tenant | Workspace มาจาก session (MVP: 1 User = 1 Workspace, D-12) ไม่ส่งใน path; resource ของ Workspace อื่นตอบ `404` เสมอ (ไม่บอกว่ามีอยู่) |
| ภาษา | API ไม่ส่งข้อความสำหรับแสดงผล ส่ง `code` + `params` แล้ว Frontend แปลตาม locale (FR-I18N) |

---

## 2. Authentication & Security (ADR-0007, ADR-0013)

| เรื่อง | กติกา |
|---|---|
| Session | cookie `session` แบบ httpOnly / Secure / SameSite=Lax; ตรวจกับ Postgres ทุก request (ไม่ cache, fail-closed) |
| CSRF | **ก่อน login (bootstrap):** Frontend เรียก `GET /auth/csrf` ได้ cookie `csrf_pre` (random, SameSite=Strict, ไม่ httpOnly) + token ใน body; request ที่ไม่ใช่ `GET` ของ endpoint ก่อน login (register, login, mfa/verify, password-reset) ต้องส่ง `X-CSRF-Token` ที่ตรงกับ cookie นี้ (double-submit) **หลัง login:** session ใหม่ถูกสร้าง (rotate) พร้อม CSRF token ที่ผูกกับ session ส่งกลับใน response ของ login / mfa-verify และขอใหม่ได้ที่ `GET /auth/csrf`; ทุก request ที่ไม่ใช่ `GET` ตรวจทั้ง token และ header `Origin` ต้องเป็น origin ของระบบ |
| 2FA step-up | endpoint ที่ติดป้าย **[MFA]** ต้องมี session ที่ยืนยัน TOTP แล้วภายใน 15 นาที ไม่เช่นนั้นตอบ `403 MFA_REQUIRED` แล้วเรียก `POST /auth/mfa/step-up` |
| Live | ใช้ **Authorization Policy §2.1** กับทุก endpoint ที่อาจทำให้เกิดการส่ง Order หรือเปิดการเทรดอัตโนมัติใน Live (FR-TEN-04, FR-LIVE-08) |
| Admin | prefix `/api/v1/admin`, บัญชีแยก (`admin_users`), 2FA บังคับทุก session (FR-ADM-01) |
| Rate limit | ต่อ User / IP (20 req/s ทั่วไป, 5 req/s สำหรับส่ง Order) ตอบ `429 RATE_LIMITED` พร้อม `Retry-After` |

### 2.1 Authorization Policy สำหรับ Live

หลัก: **การกระทำที่อาจเพิ่มความเสี่ยง ลดการป้องกัน หรือเปิดการเทรดอัตโนมัติ ต้อง [MFA]; การกระทำที่ลดความเสี่ยงอย่างเดียวไม่ต้อง** เพื่อไม่ให้ขั้นตอน 2FA ขวางการหยุดความเสียหายในยามฉุกเฉิน ใช้กับ Portfolio ที่ `trading_mode = LIVE` เท่านั้น (Paper ต้องมีแค่ session)

| กลุ่ม | Endpoint | Live |
|---|---|---|
| เพิ่มความเสี่ยง | ส่ง Order ที่ไม่ใช่ reduce-only (`POST .../orders`), เปลี่ยน Leverage / Margin Mode (`PUT .../symbols/{id}/settings`) | **[MFA]** |
| ลด / ถอดการป้องกัน | ตั้ง / แก้ / ลบ TP / SL (`PUT .../positions/{symbol_id}/protection`), แก้ Risk Rule (`PUT .../risk-rules`) | **[MFA]** |
| เปิดการเทรดอัตโนมัติ | สร้าง / แก้ / **start / resume** Bot | **[MFA]** |
| Credential / บัญชี | เชื่อม, ตรวจใหม่, ลบ Credential, เปลี่ยนโหมดบัญชี | **[MFA]** |
| ลดความเสี่ยงเท่านั้น | ส่ง Order แบบ `reduce_only: true`, ปิด Position (`.../close`), ยกเลิก Order, **pause / stop** Bot, Kill Switch ของ Portfolio | session เท่านั้น |

---

## 3. Command Model (ADR-0011)

Endpoint ที่เปลี่ยน state การเทรด (ติดป้าย **[CMD]**) ทำงานแบบ command:

1. Client ส่ง header **`Idempotency-Key: <UUID>`** (บังคับ) ระบบสร้าง `command_id` เอง (ไม่ใช้ key ของ client เป็น ID เพื่อไม่ให้ key ของผู้ใช้หนึ่งชนหรือเปิดเผยการมีอยู่ของ command ของผู้ใช้อื่น)
2. api ตรวจ auth / input / ownership แล้วคำนวณ **request fingerprint** = hash ของ `(principal, workspace, HTTP method, route template, path parameters, body ที่ normalize แล้ว)` แล้ว INSERT แถว `commands` (`PENDING`) พร้อม key และ fingerprint โดย key ไม่ซ้ำภายใน `(principal, workspace)` แล้วปลุก engine
3. api **รอผลสูงสุด 2 วินาที**:
   - ประมวลผลทันเวลา → `200` พร้อม `command` ที่มี `status: "PROCESSED"` และ `result`
   - ยังไม่เสร็จ → `202` พร้อม `command` ที่มี `status: "PENDING"`; ผลตามมาทาง WebSocket channel `commands` หรือ `GET /commands/{command_id}`
4. key เดิม + fingerprint เดิม → ได้ command และผลเดิม; key เดิม + fingerprint ต่าง (รวมถึง operation, Portfolio หรือ resource เป้าหมายต่างกันแม้ body ว่างเหมือนกัน) → `409 IDEMPOTENCY_CONFLICT`
5. key ใช้ได้อย่างน้อย 24 ชั่วโมง (ตามอายุการเก็บ `commands`, M-04) หลังจากนั้นถือเป็น key ใหม่
6. **Command ที่อ้าง Position** ต้องระบุ `expected_episode_id` (§4.6) engine ตรวจตอนประมวลผล ถ้า Position ของ Symbol นั้นไม่อยู่ใน Episode ที่ระบุแล้ว (ปิดไปหรือเปิดรอบใหม่) ปฏิเสธด้วย `EPISODE_MISMATCH` ไม่ทำกับ Position รอบใหม่

```json
{
  "command": {
    "command_id": "7f1c...",
    "command_type": "PLACE_ORDER",
    "status": "PROCESSED",
    "result": { "outcome": "ACCEPTED", "order_id": "c2a9..." }
  }
}
```
- `result.outcome`: `ACCEPTED` | `REJECTED` (พร้อม `error` ตาม §7 เช่น Risk Engine ปฏิเสธ)
- **ผลของ Live Order** ที่ส่งไป Binance แล้ว (fill, reject จาก Binance) มาทาง WebSocket channel ของ Portfolio เสมอ ไม่รอใน response

```
GET /commands/{command_id}        → { "command": {...} }
```

---

## 4. REST Endpoints

### 4.1 Auth & Me
| Method | Path | ใช้ทำ | หมายเหตุ |
|---|---|---|---|
| POST | `/auth/register` | สมัคร (email, password, locale) | สร้าง User + Workspace (FREE) + Paper Main Account 10,000 USDT (FR-TEN-05, FR-ACC-07) |
| GET | `/auth/csrf` | ขอ CSRF token (ก่อน login: double-submit cookie; หลัง login: token ของ session) | §2 |
| POST | `/auth/login` | เข้าสู่ระบบ | ถ้าไม่เปิด 2FA: สร้าง session ทันที; ถ้าเปิด 2FA: **ไม่สร้าง session** ตอบ `{ mfa_required: true, challenge_id, expires_at }` (challenge อายุ 5 นาที, ใช้ครั้งเดียว, ผิดได้ไม่เกิน 5 ครั้ง) |
| POST | `/auth/logout` | ออก | เพิกถอน session (ADR-0013) |
| POST | `/auth/password-reset/request`, `/auth/password-reset/confirm` | รีเซ็ตรหัสผ่าน | เพิกถอนทุก session เมื่อสำเร็จ |
| POST | `/auth/mfa/totp/setup` | ขอ secret / QR | |
| POST | `/auth/mfa/totp/enable` | ยืนยันด้วยรหัส 6 หลัก | |
| POST | `/auth/mfa/verify` | ยืนยัน login ด้วย `challenge_id` + รหัส TOTP → สร้าง session (`mfa_verified`) | **challenge ไม่ใช่ session:** ใช้ได้กับ endpoint นี้เท่านั้น เรียก REST อื่นหรือเปิด WebSocket ไม่ได้ |
| POST | `/auth/mfa/step-up` | ยืนยัน TOTP ซ้ำสำหรับ **[MFA]** (ต้องมี session อยู่แล้ว) | |
| GET | `/me` | ข้อมูล User, locale, timezone, `liq_warning_ratio`, สถานะ 2FA, consent ที่ยอมรับแล้ว | |
| PATCH | `/me` | แก้ locale, timezone, `liq_warning_ratio` | FR-I18N, FR-NTF-05 |
| POST | `/me/consents` | ยอมรับเอกสาร (`TERMS`, `PRIVACY`, `RISK_DISCLOSURE`) + version | FR-LGL-05 |
| DELETE | `/me` **[MFA]** | ลบบัญชี | FR-LGL-06 |

### 4.2 Workspace & Plan
| Method | Path | Response หลัก |
|---|---|---|
| GET | `/workspace` | `plan_code`, `entitlements` (ค่าปัจจุบันของ Plan), `usage`: `paper_open_notional`, `live_open_notional`, จำนวน Paper / Live Portfolio ที่ ACTIVE, `global_kill_switch` (FR-PLN-10) |

### 4.3 Market Data
| Method | Path | Query / หมายเหตุ |
|---|---|---|
| GET | `/market/symbols` | `venue`, `market_type`, `status` — Symbol Whitelist + filters (FR-MKT-04/13) |
| GET | `/market/symbols/{symbol_id}` | รายละเอียด + filters + `whitelist_status` |
| GET | `/market/symbols/{symbol_id}/leverage-brackets` | bracket ปัจจุบัน (Futures) |
| GET | `/market/candles` | `symbol_id`, `timeframe` (7 ค่าตาม FR-CHT-02), `from`, `to`, `limit` ≤ 1000 |
| GET | `/market/ticker` | `symbol_ids` — ราคาล่าสุด, best bid/ask, mark price (สำหรับโหลดครั้งแรก; อัปเดตต่อทาง WebSocket) |

### 4.4 Exchange Accounts, Wallets, Transfers
| Method | Path | ใช้ทำ | หมายเหตุ |
|---|---|---|---|
| GET | `/accounts` | รายการ Exchange Account (Paper / Live) พร้อม Wallet และยอด | |
| POST | `/accounts/paper-sub` | สร้าง Virtual Sub-account (`label`) | จำนวนตาม Plan |
| POST | `/transfers` **[CMD]** | โอน USDT ระหว่าง Paper Main ↔ Virtual Sub-account | FR-ACC-03; Live ไม่มี (FR-LIVE-15) |
| POST | `/accounts/{account_id}/virtual-deposits` **[CMD]** | เติมเงินจำลองเข้า Paper Main | FR-ACC-08 |
| GET | `/credentials/public-key` **[P2]** | public key ของ execution: `{ key_id, format_version: 1, alg: "RSA-OAEP-4096-SHA256", public_key_spki }` | ADR-0012 |
| POST | `/accounts/live` **[P2] [MFA]** | เชื่อมบัญชี Binance: `venue`, `account_role`, `label`, **`market_type`** (ตลาดของ Portfolio ที่จะใช้บัญชีนี้: `SPOT` \| `USDM_FUTURES`), `api_key`, `secret_ciphertext`, `format_version`, `encryption_key_id` | Browser เข้ารหัส Secret เอง api ไม่เห็น plaintext; execution ตรวจสิทธิ์**ตาม `market_type`** และ (Futures) ตรวจโหมดบัญชี; **[CMD]**; ผล `result.link_status`: `ACTIVE` \| `PENDING_MODE_CHANGE` (พร้อม `mode_check`) \| `REJECTED` |
| POST | `/accounts/{account_id}/mode-change` **[P2] [MFA] [CMD]** | **ผู้ใช้ยืนยันการเปลี่ยนโหมดบัญชี** `{ "confirm": true, "target": { "position_mode": "ONE_WAY", "multi_assets_mode": false } }` ใช้ได้เฉพาะบัญชีที่ `PENDING_MODE_CHANGE` | execution เปลี่ยนโหมดผ่าน Binance API แล้วตรวจซ้ำ สำเร็จเป็น `ACTIVE`; ถ้ามี Position / Order ค้างปฏิเสธด้วย `UNSUPPORTED_ACCOUNT_MODE` พร้อมคำแนะนำ (FR-LIVE-10/11) |
| POST | `/accounts/{account_id}/credential/revalidate` **[P2] [MFA]** | ตรวจ Key ใหม่ (ตาม `market_type` ของบัญชี) | |

**`mode_check`** (Futures): `{ "position_mode": "HEDGE", "multi_assets_mode": false, "portfolio_margin": false, "supported": false, "can_change": true, "blocking_reason": null }` — `can_change: false` เมื่อมี Position / Order ค้างหรือเป็น Portfolio Margin; ระบบ**ไม่เปลี่ยนโหมดเองโดยไม่ได้รับการยืนยัน** (FR-LIVE-10)
| DELETE | `/accounts/{account_id}/credential` **[P2] [MFA]** | ลบ Credential ทันที | FR-SEC-09 |

### 4.5 Portfolios
| Method | Path | ใช้ทำ | หมายเหตุ |
|---|---|---|---|
| GET | `/portfolios` | `?status=ACTIVE\|ARCHIVED&trading_mode=` | |
| POST | `/portfolios` **[CMD]** | สร้าง: `account_id`, `market_type`, `name` | D-01, FR-PF-00a/b, limit ตาม Plan |
| GET | `/portfolios/{id}` | สรุป: balances, Margin Balance, Available Balance, Margin Ratio (display, Calculation §2.4), Equity, Unrealized / Realized PnL, `trading_restriction`, Active Bot | FR-PF-04 |
| GET | `/portfolios/{id}/positions` | Position + Entry, Mark, Liquidation Price, Leverage, Margin Mode, TP/SL, `episode_id` | FR-PF-05 |
| GET | `/portfolios/{id}/orders` | `?status=OPEN\|CLOSED&symbol_id=` | |
| GET | `/portfolios/{id}/fills` | `?symbol_id=&from=&to=` — ใช้ทำ Trade Marker (FR-CHT-08) | |
| GET | `/portfolios/{id}/episodes` | Position Episode และผล (FR-PF-11) | |
| GET | `/portfolios/{id}/ledger` | รายการเงิน + `is_capital_flow` | FR-PF-06 |
| PUT | `/portfolios/{id}/symbols/{symbol_id}/settings` **[CMD]** (Live: **[MFA]**) | `leverage`, `margin_mode` | FR-MAN-04, FR-PLN-06 |
| GET / PUT | `/portfolios/{id}/risk-rules` | Risk Rule ของ Portfolio (PUT เป็น **[CMD]**, Live: **[MFA]**) | FR-RSK-01/02 |
| POST | `/portfolios/{id}/kill-switch` **[CMD]** | `{ "close_positions": true\|false }` | FR-RSK-03 |
| POST | `/portfolios/{id}/reset` **[CMD]** | Reset Paper Portfolio | FR-ACC-09; ตอบ `new_portfolio_id` |

### 4.6 Orders (Manual Trading)
| Method | Path | ใช้ทำ |
|---|---|---|
| POST | `/portfolios/{id}/orders/estimate` | ประมาณการก่อนส่ง: Order Margin, Estimated Liquidation Price, Fee, ผลต่อวงเงิน (FR-MAN-07) — **read-only** คำนวณด้วย core จาก state ล่าสุด ไม่รับประกันว่า Risk Engine จะอนุมัติ |
| POST | `/portfolios/{id}/orders` **[CMD]** (Live: **[MFA]** ยกเว้น `reduce_only: true`) | ส่ง Order (+ Bracket); Order แบบ reduce-only ที่ลด Position ต้องมี `expected_episode_id` |
| DELETE | `/portfolios/{id}/orders/{order_id}` **[CMD]** | ยกเลิก Order |
| PUT | `/portfolios/{id}/positions/{symbol_id}/protection` **[CMD]** (Live: **[MFA]**) | ตั้ง / แก้ / ลบ TP / SL ของ Position `{ "expected_episode_id": "...", "take_profit": {...} \| null, "stop_loss": {...} \| null }` (FR-MAN-03) |
| POST | `/portfolios/{id}/positions/{symbol_id}/close` **[CMD]** (session เท่านั้น) | ปิด Position ทั้งหมดหรือบางส่วน `{ "expected_episode_id": "...", "quantity": "..." \| null }` (reduce-only, FR-MAN-05) |

**Request: ส่ง Order**
```json
{
  "symbol_id": 123,
  "side": "BUY",
  "order_type": "LIMIT",
  "quantity": "0.010",
  "price": "60000.0",
  "time_in_force": "GTC",
  "reduce_only": false,
  "take_profit": { "trigger_price": "63000.0" },
  "stop_loss":   { "trigger_price": "58500.0" }
}
```
- `take_profit` / `stop_loss` สร้าง Bracket ตาม FR-ORD-14..17
- ตรวจ Symbol Filters (tickSize / stepSize / minNotional) ที่ api ก่อนสร้าง command (ตอบ `422 FILTER_VIOLATION`) แล้ว Risk Engine ตรวจซ้ำใน engine

### 4.7 Strategies & Bots
| Method | Path | ใช้ทำ | หมายเหตุ |
|---|---|---|---|
| GET | `/strategies` | Built-in Strategy ที่เปิดอยู่ + `parameter_schema` + `version` | D-06, FR-STR-11 |
| POST | `/portfolios/{id}/bots` **[CMD]** (Live: **[MFA]**) | สร้าง Bot: `strategy_code`, `strategy_version`, `parameters`, `symbol_ids` | ตรวจ schema, clamp Leverage ตาม Plan (FR-PLN-07) |
| GET | `/bots/{bot_id}` | สถานะ, `pause_reason`, parameters | |
| POST | `/bots/{bot_id}/start`, `/resume` **[CMD]** (Live: **[MFA]**) | เริ่ม | Portfolio ต้องไม่มี Position/Order ค้างและไม่มี Active Bot อื่น (FR-PF-08, FR-STR-09) |
| POST | `/bots/{bot_id}/pause`, `/stop` **[CMD]** (session เท่านั้น) | หยุดชั่วคราว / หยุด | Resume (แถวบน) ทำได้เฉพาะเมื่อไม่มี Trading Restriction (FR-LIVE-19) |
| PATCH | `/bots/{bot_id}` **[CMD]** (Live: **[MFA]**) | แก้ parameters (เฉพาะตอน `STOPPED`) | |
| GET | `/bots/{bot_id}/logs` | log ของ Bot (90 วัน, NFR-18) | |

### 4.8 Analytics
| Method | Path | Query |
|---|---|---|
| GET | `/portfolios/{id}/performance` | `from`, `to`, `interval` (`1h`, `1d`) — Equity Curve จาก `performance_snapshots` |
| GET | `/portfolios/{id}/metrics` | `from`, `to` — Total Return, Max Drawdown, Win Rate (ต่อ Episode), Profit Factor, Avg Win/Loss, Sharpe (FR-ANL-02) |
| GET | `/bots/{bot_id}/metrics` | ผลจาก Episode ที่ Bot เปิด (FR-ANL-03) |
| GET | `/analytics/compare` | `portfolio_ids` (สูงสุด 10), `from`, `to` — รวม Archived และ Paper vs Live (FR-ANL-04) |

### 4.9 Notifications
| Method | Path | ใช้ทำ |
|---|---|---|
| GET | `/notifications` | `?unread=true` |
| POST | `/notifications/{id}/read`, `/notifications/read-all` | |
| GET / PUT | `/notification-preferences` | เรื่องวิกฤตแก้ไม่ได้ (FR-NTF-04) — ส่งมาจะถูกปฏิเสธด้วย `422 CRITICAL_NOTIFICATION_REQUIRED` |
| POST | `/telegram/link-token` **[P2]** | ได้ token สำหรับเชื่อม Telegram Bot |
| DELETE | `/telegram/link` **[P2]** | ยกเลิกการเชื่อม |

### 4.10 Admin (`/api/v1/admin`, FR-ADM)
| Method | Path | ใช้ทำ | หมายเหตุ |
|---|---|---|---|
| POST | `/admin/auth/login`, `/admin/auth/mfa/verify`, `/admin/auth/logout` | | 2FA บังคับ: login ได้แค่ challenge เสมอ (กติกาเดียวกับ §4.1) |
| GET | `/admin/users` | ค้นหา User | |
| GET | `/admin/workspaces/{id}` | ดูข้อมูลการเทรดแบบอ่านอย่างเดียว | **สร้าง audit_log ทุกครั้ง** (FR-ADM-08) |
| PUT | `/admin/workspaces/{id}/plan` | เปลี่ยน Plan | FR-PLN-11/14 ทำงานผ่าน command ไปยัง engine |
| POST | `/admin/workspaces/{id}/suspend`, `/unsuspend` | ระงับ / คืนบัญชี | เพิกถอน session (ADR-0013) |
| GET / PUT | `/admin/plans/{plan_code}/entitlements` | ปรับ Entitlement | ลดค่าต้องระบุ `effective_at` เพื่อแจ้งล่วงหน้า (FR-PLN-12) |
| GET / PATCH | `/admin/symbols`, `/admin/symbols/{symbol_id}` | `whitelist_status`, `liquidation_clearance_rate` | FR-MKT-13..16 |
| GET / PATCH | `/admin/strategies/{code}/{version}` | `enabled` | FR-ADM-02 |
| GET / PUT | `/admin/settings/{key}` | ค่าระบบ (slippage, fee rate, เงินเริ่มต้น, price throttle) | FR-ADM-04 |
| POST | `/admin/kill-switch` | `{ "active": true\|false, "reason": "..." }` | FR-ADM-06 |
| GET | `/admin/system/health` | สถานะ market-data, engine lag, Reconciliation, latency, ภาระ VM | FR-ADM-07 |

ห้ามมี endpoint ของ Admin ที่ส่ง Order, ปิด Position, อ่าน Secret หรือแก้ ledger / audit (FR-ADM-09)

---

## 5. WebSocket

### 5.1 Connection
- URL: `wss://<host>/ws` — ใช้ cookie session เดียวกับ REST; ตรวจ session ตอนเปิดและทุก 60 วินาที (ADR-0013)
- Server ส่ง `ping` ทุก 20 วินาที; client ตอบ `pong`; ไม่มีการตอบภายใน 60 วินาทีถือว่าหลุด
- **ใช้ส่งข้อมูลออกเท่านั้น:** การกระทำทั้งหมด (ส่ง Order ฯลฯ) ผ่าน REST
- Close codes: `4001 SESSION_REVOKED`, `4003 FORBIDDEN`, `4008 TOO_MANY_SUBSCRIPTIONS`, `4009 SLOW_CONSUMER`

### 5.2 Messages
Client → Server:
```json
{ "op": "subscribe",   "channels": ["market.BINANCE_COM.USDM_FUTURES.123.price", "portfolio.<id>"] }
{ "op": "unsubscribe", "channels": ["..."] }
```
Server → Client:
```json
{ "channel": "portfolio.<id>", "type": "snapshot", "epoch": 17, "as_of_seq": 1041, "data": { ... } }
{ "channel": "portfolio.<id>", "type": "position.updated", "epoch": 17, "seq": 1042, "data": { ... } }
```
- **ขอบเขตของ `seq`:** ต่อ channel ภายใน `epoch` เดียว — `epoch` เปลี่ยนเมื่อผู้ผลิตข้อมูลของ channel เปลี่ยน (Portfolio / Workspace / Bot: fencing token ของ engine เจ้าของ Workspace; Market: fencing token ของ market-data leader) event ทุกตัวมี `epoch` และ `seq`
- **Portfolio `seq` = `state_version`** ของ Portfolio ที่ engine เพิ่มทีละ 1 ในทุก transaction ที่เปลี่ยน state และบันทึกใน Postgres; REST ของ Portfolio (`GET /portfolios/{id}`, `/positions`, `/orders`) ส่ง `state_version` และ `epoch` เดียวกัน จึงใช้ resync ได้ตรงจุด
- **Handoff snapshot → stream (ไม่ให้ event หลุด):**
  1. api เริ่มรับ event ของ channel จาก Redis และ**เก็บไว้ใน buffer ก่อน**
  2. api สร้าง snapshot จาก Postgres / ค่าล่าสุด พร้อม **watermark** = `seq` ของ state ใน snapshot (`as_of_seq`)
  3. ส่ง `{ "type": "snapshot", "epoch": E, "as_of_seq": W, "data": ... }`
  4. ปล่อย event ใน buffer ที่ `seq > W` ตามลำดับ ทิ้งที่ `seq ≤ W` แล้วส่งสดต่อ
  5. ถ้า buffer เกินขนาดที่กำหนด (1,000 event) ปิดด้วย `4009 SLOW_CONSUMER`
- **Client:** หลัง snapshot ใช้เฉพาะ event ที่ `seq = ล่าสุด + 1` ของ `epoch` เดียวกัน; ถ้า `seq` กระโดด, `epoch` เปลี่ยน หรือ reconnect → subscribe ใหม่ (ได้ snapshot ใหม่) หรือโหลด REST แล้วใช้ event ที่ `seq > state_version` ของ REST
- **ถ้า `seq` กระโดด หรือ reconnect** → client ขอ snapshot ใหม่ (subscribe ซ้ำ) หรือโหลดผ่าน REST — WebSocket ไม่รับประกันการส่งครบ (ADR-0011 ข้อ 7, NFR-23)

### 5.3 Channels
| Channel | Event | แหล่ง |
|---|---|---|
| `market.{venue}.{market}.{symbol_id}.price` | `price` (last, best bid/ask, mark) ≤ 1 ครั้ง/วินาที | market-data (FR-STR-17) |
| `market.{venue}.{market}.{symbol_id}.candle.{timeframe}` | `candle.updated`, `candle.closed` | market-data |
| `portfolio.{id}` | `balance.updated`, `margin.updated`, `position.updated`, `order.updated`, `fill.created`, `episode.closed`, `restriction.changed`, `liquidation` | engine (outbox) |
| `bot.{bot_id}` | `status.changed` (+ `pause_reason`), `log` | engine |
| `commands` | `command.processed` (ผลของ command ที่ตอบ `202`) | engine |
| `notifications` | `notification.created` | notifier |
| `workspace` | `usage.updated` (Open Notional, จำนวน Portfolio), `kill_switch.changed` | engine / api |

- จำกัดจำนวน channel ต่อการเชื่อมต่อ (100) ส่วนเกินตอบ close `4008`
- Subscribe `portfolio.*` / `bot.*` ได้เฉพาะของ Workspace ตัวเอง

---

## 6. Status Codes

| HTTP | ใช้เมื่อ |
|---|---|
| 200 | สำเร็จ / command ประมวลผลแล้ว (ดู `result.outcome`) |
| 201 | สร้าง resource ที่ไม่ใช่ command (เช่น register) |
| 202 | command รับแล้ว ยังไม่เสร็จ |
| 400 | request ผิดรูปแบบ |
| 401 | ไม่มี session / session หมดอายุหรือถูกเพิกถอน |
| 403 | ไม่มีสิทธิ์ / ต้องใช้ 2FA |
| 404 | ไม่พบ หรือเป็นของ Workspace อื่น |
| 409 | Idempotency conflict / state ไม่อนุญาต (เช่น Portfolio ไม่ว่าง) |
| 422 | validation / กติกาธุรกิจที่ api ตรวจได้เอง |
| 429 | rate limit |
| 503 | Postgres หรือ engine ใช้ไม่ได้ (fail-closed) |

---

## 7. Error Format & Codes

```json
{
  "error": {
    "code": "ENTITLEMENT_NOTIONAL_EXCEEDED",
    "params": { "limit": "50000", "projected": "53210.5", "trading_mode": "LIVE" },
    "request_id": "01J9..."
  }
}
```
- Frontend แปล `code` + `params` เป็นข้อความไทย / อังกฤษ (FR-I18N)
- ผลปฏิเสธจาก Risk Engine อยู่ใน `command.result.error` รูปแบบเดียวกัน

| กลุ่ม | Code | Requirement |
|---|---|---|
| Auth | `AUTH_REQUIRED`, `SESSION_REVOKED`, `MFA_REQUIRED`, `MFA_CHALLENGE_INVALID` (หมดอายุ / ใช้แล้ว / ผิดเกินกำหนด), `CSRF_INVALID`, `ORIGIN_INVALID`, `FORBIDDEN`, `ACCOUNT_SUSPENDED` | ADR-0007/0013 |
| Request | `VALIDATION_FAILED`, `NOT_FOUND`, `IDEMPOTENCY_CONFLICT`, `IDEMPOTENCY_KEY_REQUIRED`, `RATE_LIMITED`, `SERVICE_UNAVAILABLE` | |
| Market | `SYMBOL_NOT_TRADABLE` (DISABLED / CLOSE_ONLY), `FILTER_VIOLATION` (`filter`: tick / step / min_qty / min_notional) | FR-MKT |
| Entitlement | `ENTITLEMENT_NOTIONAL_EXCEEDED`, `ENTITLEMENT_LEVERAGE_EXCEEDED`, `LIVE_NOT_ENTITLED`, `PORTFOLIO_LIMIT_REACHED` | FR-PLN |
| Risk | `INSUFFICIENT_MARGIN`, `RISK_RULE_VIOLATION` (`rule_code`), `KILL_SWITCH_ACTIVE`, `GLOBAL_KILL_SWITCH_ACTIVE`, `TRADING_RESTRICTED` | FR-RSK, FR-ADM-06, FR-LIVE-19 |
| Position | `EPISODE_MISMATCH` (Position ไม่อยู่ใน Episode ที่ระบุแล้ว) | FR-PF-11 |
| Bot / Ownership | `ACTIVE_BOT_OWNS_PORTFOLIO` (Manual เปิด/เพิ่ม Position ใน Portfolio ที่มี Bot), `PORTFOLIO_NOT_FLAT`, `ACTIVE_BOT_EXISTS`, `BOT_NOT_RESUMABLE`, `STRATEGY_DISABLED`, `PARAMETER_OUT_OF_RANGE` | D-02, FR-STR |
| Paper | `INSUFFICIENT_BALANCE` (Transfer), `PORTFOLIO_HAS_ACTIVE_BOT` (Reset) | FR-ACC |
| Credential [P2] | `WITHDRAWAL_PERMISSION_ENABLED`, `MISSING_PERMISSION`, `IP_NOT_RESTRICTED`, `ACCOUNT_ALREADY_LINKED`, `FUTURES_NOT_ENABLED`, `UNSUPPORTED_ACCOUNT_MODE`, `MODE_CHANGE_NOT_PENDING`, `INVALID_API_KEY`, `CIPHERTEXT_INVALID` | D-04, FR-SEC |
| Exchange [P2] | `EXCHANGE_REJECTED` (`exchange_code`), `EXCHANGE_UNAVAILABLE` | FR-LIVE |
| Notification | `CRITICAL_NOTIFICATION_REQUIRED` | FR-NTF-04 |

Warning (ไม่ใช่ error) ตอนเชื่อม Key: `TRANSFER_PERMISSION_ENABLED`, `MARGIN_PERMISSION_ENABLED` (FR-SEC-10/12)

---

## 8. Traceability (หลัก)

| Requirement / ADR | ที่รองรับ |
|---|---|
| P-02, ADR-0002/0009 ทุก Order ผ่าน engine | §3 command model, §4.6 |
| ADR-0011 Durable commands | §3 `Idempotency-Key` = `command_id` |
| ADR-0012 Credential | §4.4 `/credentials/public-key`, `/accounts/live` |
| ADR-0013 Session | §2, §5.1 |
| FR-MAN-07 Pre-trade estimate | §4.6 `/orders/estimate` |
| FR-CHT-08 Trade Marker | §4.5 `/fills` |
| FR-PF-11, FR-ANL-03 Episode | §4.5 `/episodes`, §4.8 `/bots/{id}/metrics` |
| FR-PLN-10 แสดงการใช้ Entitlement | §4.2 `/workspace`, channel `workspace` |
| FR-ADM | §4.10 |
| FR-I18N | §1, §7 code + params |

## 9. Open Items
| # | เรื่อง | สถานะ |
|---|---|---|
| A-01 | api รอผล command สูงสุด 2 วินาทีก่อนตอบ `202` | ✅ Decided |
| A-02 | 2FA step-up มีอายุ 15 นาที | ✅ Decided |
| A-03 | Rate limit 20 req/s ทั่วไป, 5 req/s สำหรับ Order | ✅ Decided |
| A-04 | จำกัด 100 channel ต่อ WebSocket | ✅ Decided |
| A-05 | แก้ parameters ของ Bot ได้เฉพาะตอน `STOPPED` | ✅ Decided |
| A-06 | MFA challenge อายุ 5 นาที, ใช้ครั้งเดียว, ผิดได้ไม่เกิน 5 ครั้ง | ✅ Decided |
| A-07 | Buffer ของ WebSocket ระหว่าง snapshot handoff 1,000 event | ✅ Decided |
| A-08 | Idempotency-Key ใช้ได้อย่างน้อย 24 ชั่วโมง | ✅ Decided |
