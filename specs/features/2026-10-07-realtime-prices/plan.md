# F-10 — รับราคาเรียลไทม์และต่อกลับเมื่อหลุด — Plan

สถานะ: **Approved** — เจ้าของตอบ approve วันที่2026-10-07 หลังอนุมัติ NC-26/NC-27 และปรับแผนตามคำตัดสิน
วันที่: 2026-10-07
Branch: feature/f-10-realtime-prices

สำหรับผู้ลงมือ: ใช้ executing-plans ทำทีละขั้น พร้อมตรวจผลก่อนข้ามขั้น
ไม่ commit/push โดยอัตโนมัติ และไม่เริ่มโค้ดก่อนเอกสารทั้งสองฉบับอนุมัติ

## เป้าหมายและแนวทาง

รับ trade stream ร่วมกันสำหรับ 5 คู่ แล้วส่งราคาซื้อขายล่าสุดและสถานะถึงเว็บ
ผ่าน PostgreSQL → Redis notification → API WebSocket
PostgreSQL เป็นแหล่ง snapshot/revision ที่เชื่อถือได้; Redis ไม่เก็บ trade history
และไม่เป็นหลักฐานว่าราคาสด API ไม่เรียกตลาด และ market-data ไม่อ่าน session
ไม่เปลี่ยนแผน ingestion/retention/closure ของ F-09

ข้อเท็จจริงและ fixtures อยู่ใน
[public contract evidence](../../research/2026-10-07-f10-stream-contract.md)
พบข้อมูลจริงครบ 5 คู่ผ่าน endpoint TH และ explicit SUBSCRIBE
ไม่ต้องเปลี่ยนแหล่งข้อมูลหรือลดเกณฑ์อายุที่ requirements อนุมัติ

### ทางเลือกที่พิจารณา

1. **เลือก:** PostgreSQL latest snapshot + Redis notification + API WebSocket
   กู้คืนหลัง missed notification/restart ได้ และคงขอบเขต process เดิม
2. Redis เป็นแหล่งราคาหลัก: ลด DB writes แต่ต้องพิสูจน์ recovery/ordering ใหม่
   และข้อมูลสถานะที่ต้องคงอยู่ยังต้องบันทึกก่อนประกาศ
3. API polling อย่างเดียว: ง่ายกว่า แต่ไม่ครอบ lifecycle realtime ถึงเบราว์เซอร์
   ตามขอบเขต A; ไม่ใช้เป็นทางเลือกแทน stream โดยเงียบ ๆ

## ข้อจำกัดทุกขั้น

- Spot, source `primary_spot`, BTC/ETH/SOL/XRP/DOGE กับ USDT เท่านั้น
- อายุราคา `now - trade_time > 10s` คือเก่า; อายุเท่ากับ 10s ยังผ่าน
- ท่อตลาดหลุดที่ตรวจพบ → backendไม่พร้อมทันที; serverนับตลาดไม่พร้อมครบ60s
  → alert_dueในsnapshot; เว็บdeliveryfailureเตือนทันทีที่ตรวจพบตามNC-27
- handshake/ack/pong/REST receipt ไม่ทำให้ราคาเก่ากลายเป็นสด
- Money/Quantity เท่านั้น; ไม่มี financial float/Decimal เปล่า
- core ไม่อ่าน clock/network/random; randomness ของ backoff อยู่ใน adapter/service
- ไม่เพิ่ม account stream, execution, indicator, bid/ask, candle stream หรือ Live
- เวลาที่อยู่อนาคตเทียบ reference time ไม่ถือว่าราคาสด; fail closed พร้อม reason
- ถ้าหลักฐานตอนลงมือขัดกับแผน ให้หยุดขอเปลี่ยนแผนก่อนแก้ implementation

## ของเดิมที่จะใช้ซ้ำ

| Path | ใช้ทำอะไร |
|---|---|
| `backend/src/tiewtrade/venues/prices.py` | Price, PriceSource, age/is_stale; ไม่เพิ่ม field บังคับให้ผู้ใช้เดิม |
| `backend/src/tiewtrade/venues/{symbols,moments,errors,limits,fake}.py` | symbol/เวลา/errors/โควตา/FakeVenue |
| `backend/src/tiewtrade/venues/binance_th/{prices,mapping,transport,rate_limit,failures,endpoints}.py` | `/trades?limit=1`, exact parsing, HTTP transport และการพักตามตลาด |
| `backend/src/tiewtrade/core/{money,moments}/` | exact price/quantity และเวลา aware |
| `backend/src/tiewtrade/infra/market_data/storage.py` | SOURCE/PAIRS/database_now; ย้าย SOURCE/PAIRS ไป catalog.py ใน package เดิมแล้ว import กลับ ไม่ทำสองรายการ |
| `backend/src/tiewtrade/infra/db/{engine,session}.py` | actual-role assertions, MarketDataSession/UserSession |
| `backend/src/tiewtrade/infra/auth/sessions.py` | hash_token/owner_of_presented ภายใต้ RLS; ไม่เขียนกฎหมดอายุใหม่ |
| `backend/src/tiewtrade/infra/auth/{throttle,cleanup}.py`, `backend/src/tiewtrade/services/api/throttling.py` | TokenRule/claim/spend_token/cleanup เดิม สำหรับ handshake bucket ไม่คัดลอกสูตรเติม token |
| `backend/src/tiewtrade/services/api/{authentication,routing_policy,resources,safe_input_routes}.py` | จุดตรวจตัวตนและตาราง routes เดียว |
| `frontend/src/{AccountSession,AuthPanel}.tsx` | cache ต่อ identity, cleanup/expiry flow, ที่ติดตั้ง panel |
| `frontend/src/{accountPanels.css,styles/admin-theme.css,accountMessages.ts}` | TailAdmin tokens/i18next; ไม่เพิ่ม theme หรือ toolchain |
| `backend/tests/infra/market_data/`, `backend/tests/api/`, `frontend/e2e/helpers/` | disposable DB, actual roles, authenticated E2E |

## หน่วยงานและไฟล์

| สร้าง/แก้ | หน้าที่ |
|---|---|
| สร้าง `backend/src/tiewtrade/core/realtime_prices.py` | QuoteObservation, readiness/ordering แบบบริสุทธิ์ |
| สร้าง `backend/src/tiewtrade/venues/price_streams.py` | สัญญา stream/recovery กลาง |
| แก้ `venues/{__init__,fake}.py` | live_price_feed factory และ fake feed; factory ไม่เผย network vocabulary |
| สร้าง `venues/binance_th/{stream_mapping,stream_transport,price_feed}.py` | parsing, network/control frames, ประกอบ feed ตามลำดับ |
| แก้ `venues/binance_th/{mapping,__init__}.py` | ใช้ parser trade ร่วมกับ REST และประกาศ vocabulary |
| สร้าง `infra/market_data/{catalog,realtime_records,realtime_storage}.py` | catalog ร่วม, typed persistence, lease/revision/latest prices |
| สร้าง `backend/migrations/versions/0014_realtime_prices.py` | snapshot/writer lease + user connection slots/RLS + handshake bucket พร้อม grants |
| สร้าง `backend/src/tiewtrade/infra/realtime/{admission,connections}.py` | atomic pre-auth throttle และ user slot leases ผ่านUserSession |
| สร้าง `services/api/price_admission.py` | local socket/pending budgets, claim/renew/release lifecycle |
| แก้ `infra/auth/throttle.py`, `infra/auth/cleanup.py`, `infra/db/engine.py` | bucket/rule/cleanup และ bounded API-role pool สำหรับ realtime |
| สร้าง `backend/src/tiewtrade/infra/realtime/{__init__,notifications}.py` | Redis notification lifecycle ไม่มี venue import |
| สร้าง `services/market_data/realtime.py`; แก้ `main.py` | ingestion supervisor + F-09 runner พร้อม graceful shutdown |
| สร้าง `services/api/{price_models,price_routes,price_broadcast}.py` | snapshot models, GET/WS, shared broadcaster |
| แก้ `services/api/{authentication,routing_policy,app,resources,settings}.py` | WS auth ที่จุดกลาง, lifecycle/settings ไม่แตะ TOTP rules |
| สร้าง `frontend/src/{realtimePrices.ts,useRealtimePrices.ts,RealtimePricePanel.tsx,realtimePriceMessages.ts,RealtimePricePanel.css}` | decode/client/cache, lifecycle, UI/status/i18n |
| แก้ `frontend/src/{AuthPanel.tsx,api-types.ts}`, `frontend/vite.config.ts` | ติด panel หลัง login, generated schema, WS proxy |
| แก้ `backend/{pyproject.toml,uv.lock,openapi.json}`, `compose.yaml`, `.github/workflows/ci.yml` | dependencies, import gates, Redis/runtime/CI |
| แก้ `frontend/playwright.config.ts`, `frontend/e2e/helpers/environment.ts` | fake market-data process ใน test environment |

path ในตารางที่ละ prefix อยู่ใต้ `backend/src/tiewtrade/`
เทสต์ใหม่แต่ละหน่วยอยู่ใน path คู่กันใต้ backend/tests และ frontend/tests

## 1. สัญญาและตรรกะกลาง

QuoteObservation เก็บ source/base/quote, amount: Money, trade_id: int,
trade_time/received_at: datetime, observation_kind: STREAM|SNAPSHOT;
ไม่ใช้ event time เป็นเวลาเกิดราคา และไม่ใช้trade_idเป็นsequence
จำกัด trade_id เป็น integer nonnegative และ reject bool; ราคาบวกหน่วย quote
อายุใช้ reference time UTC ที่ส่งเข้ามา

```python
class PriceFeed(Protocol):
    async def snapshot(self, symbol: Symbol) -> QuoteObservation: ...
    def events(self, symbols: tuple[Symbol, ...]) -> AsyncIterator[FeedEvent]: ...
```

FeedEvent เป็น union ของ FeedConnected(generation), FeedQuote(generation, quote),
FeedDisconnected(generation, failure_code); generation เป็นรอบ connection
snapshot ไม่ต้องเปลี่ยน PriceSource.latest_price signature; adapter สร้าง
QuoteObservation ด้วย trade parser ร่วมกันที่ยังคง trade ID ไว้

### ลำดับข้อมูลแบบไม่สมมติว่า ID เพิ่มตามเวลา — แก้ review issue3

หลักฐานที่ใช้: TH Trade Streamsกำหนด `T` เป็นtrade time และ `t` เป็นtrade ID;
REST General API Informationกำหนดarrayเป็นoldest-first/newest-last
เอกสารที่ตรวจยังไม่รับรองnumerical-ID ordering หรือsequenceร่วมREST/WS
จึงไม่ใช้IDที่มากกว่าเป็นตัวเลือกwinner ไม่ใช้E/received_at/arrival orderแทน
แหล่งอ้างอิงและขอบเขตที่พิสูจน์ได้อยู่ในresearch หัวข้อordering contract

ภายในsource/pairเดียวและgenerationปัจจุบัน เปรียบเทียบเป็นpartial order:
- trade_timeใหม่กว่า → candidateใหม่กว่า แม้trade_idตัวเลขน้อยกว่า
- trade_timeเก่ากว่า → ignore ไม่ย้อนราคา/อายุ/revision
- เวลาเท่ากันและamountเท่ากัน → ราคาเดียวกันในresolutionที่มี ไม่เลื่อนอายุ
  ไม่อ้างว่าtradeเป็นเหตุการณ์เดียวกันถ้าIDต่าง; metadatareceived_at/Eไม่ทำให้สด
- เวลาเท่ากันแต่amountต่าง → ORDER_UNCONFIRMED, ไม่เลือกจากID/arrival order
  เก็บราคาconfirmedก่อนหน้าเพื่อแสดงพร้อมRECOVERING; ถ้าไม่เคยมีแสดงmissing
  invalidationต้องflushทันทีและสร้างambiguity latchตามtimeนั้น
- duplicateของSTREAM IDเดิมในscope(source,pair,generation)ที่ยังเทียบอยู่
  ต้องมีเวลา/ราคาเดิม; เปลี่ยนเนื้อหา → VENUE_PROTOCOLและrecovery
- REST IDกับWS IDไม่มีการเปรียบเทียบเพื่อจัดลำดับหรือพิสูจน์identityข้ามท่อ
  trade_idใช้metadata/ตรวจduplicateภายในscopeเท่านั้น ไม่ใช่globalsequence
- ไม่กำหนดว่าIDต้องต่อเนื่อง ไม่สร้างtradeที่หายหรือเลือกผู้ชนะด้วยmin/max ID

ambiguity latchเป็น `order_ambiguous_at` ที่เก็บในPGและไม่หายเมื่อreconnect
timestampที่เท่ากันแต่ราคาต่างกันให้ผลไม่พร้อมไม่ว่าจะอ่านสองราคาลำดับใด
ความกำกวมของbucketเก่ากว่าconfirmedล่าสุดไม่ทำให้ราคาย้อนหรือแทนที่confirmed

### กู้จาก ordering ที่ยังยืนยันไม่ได้

หลังพบambiguity เริ่มrecoveryหนึ่งงานต่อคู่ รวมเหตุซ้ำระหว่างงานค้าง
RESTrequestต้องเริ่มหลังพบlatchและผูกgeneration/attemptปัจจุบัน
arrayล่าสุดเลือกสมาชิกท้ายตามสัญญาREST ไม่sortด้วยID
RESTempty/failure/responseเวลาเก่าหรือเท่ากับlatchยังไม่resolve แม้ราคาอายุไม่เกิน10s
ต้องได้RESTtrade_timeมากกว่าorder_ambiguous_at แล้วmergeกับstreamcandidate:
ถ้าtimestampต่างใช้เวลาที่ใหม่กว่า; ถ้าเท่ากันราคาต่างให้คง/ขยายlatch
ถ้าเท่ากันราคาเดียวกันยืนยันscalarpriceได้โดยไม่อ้างIDร่วมกัน
ล้างlatchและตั้งreconciledในtransactionเดียวเมื่อmergeไม่กำกวมและwinnerผ่านเกณฑ์สด
STREAMquoteใหม่เพียงอย่างเดียวไม่ล้างlatchหรือทำให้กลับREADYก่อนrecoveryผ่าน

คำตอบRESTจากattemptเก่าหรือrequestที่เริ่มก่อนพบlatchไม่มีสิทธิ์ล้างlatch
ถ้าตลาดไม่ให้tradeในbucketถัดไปคงRECOVERING/แจ้งเตือน60sตามเดิม
retryใช้boundedbackoff/rate-limitเดิม ไม่เปิดpollingทดแทนstream
การเลือกpartial orderนี้ให้ความพร้อมน้อยลงได้ แต่ไม่เปลี่ยน10s/60s
และไม่อนุมานorderingที่ตลาดไม่ได้รับรองเพื่อทำให้พร้อม

```python
def readiness(*, quote: QuoteObservation | None, connected: bool,
              reconciled: bool, producer_alive: bool, now: datetime) -> Readiness: ...
```

Readiness เป็น MISSING/RECOVERING/STALE/READY พร้อม reason;
connected/reconciled/producer_alive ต้องผ่านทั้งหมดจึงพิจารณา READY
ไม่มีราคาตั้งแต่ต้นเป็น MISSING; อายุเกิน 10s เป็น STALE;
อนาคต/clock reference ผิดหรือ conflict เป็น RECOVERING ไม่เลือกเวลาทดแทน

## 2. Adapter และ recovery

เพิ่ม direct dependency `websockets>=17.1,<18` และ `redis>=5,<8`
ล็อก resolved versions ใน uv.lock; ใช้ Python3.12/React18/Vite6/Node22 เดิม
เพิ่ม import contracts ของโมดูลใหม่และขยาย network gate อย่างจำกัด:
`stream_transport.py` เป็นจุด WSS network เพียงจุดเดียวของ adapter,
transport.py ยังเป็นจุด HTTP เดิม; stream_mapping ต้องไม่รู้จักเครือข่าย
core/strategies ต้องไม่เข้าถึง websockets/redis

เปิด combined TH endpoint สำหรับ 5 stream แล้วส่ง SUBSCRIBE ด้วย id รอบใหม่
ควบคุม control frames ไม่เกิน 5/s รวม ping/pong; รอ ack ที่ id ตรงกัน
ก่อนเริ่ม recovery ไม่ใช้ LIST_SUBSCRIPTIONS เป็นเงื่อนไขพร้อม

กำหนด `subscription_ack_timeout=5s` แยกจาก WSS open timeout10s
เป็นค่าเทคนิคที่เสนอในแผน ไม่ใช่ SLA ของตลาด ใช้ monotonic deadline
เริ่มก่อนส่ง SUBSCRIBE (รวมเวลารอ control-frame limiter และ send)
ต้องรับและตรวจ success ack (`result: null`, id ตรง, generation ปัจจุบัน)
เสร็จก่อน deadline; ณ deadline หรือหลังจากนั้นถือว่า timeout
pong, trade frames, ack ผิด id หรือ ack ซ้ำต้องไม่เลื่อน deadline
ระหว่างรอ ack อ่าน frames ด้วย reader เดียวและจัดการ control frames ต่อเนื่อง;
trade ก่อน ack ยังไม่ใช้ประกาศพร้อม และไม่สะสมเป็นคิวไม่จำกัด

เมื่อหมดเวลาให้ invalidate attempt ก่อน await cleanup, ส่ง FeedDisconnected
พร้อม failure_code `SUBSCRIPTION_ACK_TIMEOUT` แล้วปิด connection/ยกเลิกงานรอ
ใช้ close timeout5s เพื่อไม่ให้ cleanup ขวาง reconnect ไม่จำกัด
จากนั้นเข้า reconnect full-jitter/backoff เดิม ไม่ส่ง SUBSCRIBE ซ้ำบน socket เดิม
ไม่เริ่ม REST recovery และไม่ reset retry attempt จาก handshake/pong
callback/ack ที่มาช้าของ attempt หรือ generation เก่าต้องไม่มีผลกับรอบใหม่
ack error หรือ malformed payload ใช้ protocol-error path เดิมพร้อมพัก30s;
การ timeout นี้ใช้ reconnect backoff ปกติ ไม่รอรอบหมุน23h50m
server ping ต้องตอบ pong; client probe ทุก10s, timeout5s; timeout/close
ส่ง disconnected ทันที ไม่มี data อย่างเดียวไม่พิสูจน์ว่าท่อหลุด
ขนาด frame สูงสุด64KiB, receive queue16; เกินขอบเขต → disconnect/recovery
หมุน connection ก่อน24h ที่23h50m โดยผ่าน recovery เหมือนการหลุด

หลัง ack ให้ reader เดิมอ่านต่อเนื่องและเริ่ม REST snapshot 5 คู่ผ่าน transport/guard เดิม
dirty mapมี5entries แต่แต่ละentryเก็บcandidateที่เวลาใหม่ที่สุดพร้อมambiguity latch
ตรวจequal-time/different-priceและduplicateconflictก่อนcoalesceทุกครั้ง
ห้ามทิ้งconflictแล้วเหลือquoteเดียวจนดูเหมือนยืนยันลำดับแล้ว
ไม่เก็บทุกtrade และcontrol/invalidationไม่ถูกquotebatchทับ
รอ snapshot ของคู่สำเร็จ → merge กับ stream ด้วยเกณฑ์ข้อ1
ready รายคู่ได้เมื่อ snapshot/recovery ผ่านใน generation ปัจจุบัน
ไม่มีordering latchที่ยังค้าง และwinnerสด; snapshotsuccessอย่างเดียวไม่พอ
snapshot เก่าต้องไม่เขียนทับ stream ใหม่; callback จาก generation เก่าถูกทิ้ง
snapshot failure คู่หนึ่งไม่ขวางคู่ที่ผ่าน; retry เฉพาะคู่ผิดพลาดตาม backoff
ไม่มีการ polling เป็นแหล่งราคาทดแทน stream; REST ใช้ recovery เท่านั้น

reconnect full jitter ในช่วง0..min(30s, 1s*2^attempt); retry attempt
reset หลัง connection เสถียร60s ไม่ reset จาก handshake อย่างเดียว
429/418 ใช้ Retry-After เป็นเวลารอขั้นต่ำ แม้ backoff สั้นกว่า
protocol error เปิด reason/พัก30s ก่อนลองใหม่ ไม่ log payload
HTTP timeout5s; WSS open timeout10s; tasks/clients ปิดใน finally
ใช้ limiter instance เดียวของ HTTP recovery และ F-09 ภายใน market-data
ไม่อ้างว่าแก้ข้อจำกัด shared-IP ระหว่าง process จาก F-35 แล้ว

## 3. PostgreSQL และ worker fencing

Migration0014 แบบเพิ่มของใหม่: ไม่แตะ candle schema/retention

- `market_price_feed`: source PK, generation BIGINT, owner UUID,
  lease_until TIMESTAMPTZ, connected BOOLEAN, last_failure_code TEXT
- `market_latest_prices`: PK(source,base,quote), amount ใช้ domain เงินเดิม,
  trade_id BIGINT, trade_at/received_at TIMESTAMPTZ nullable ก่อนมีราคา,
  reconciled_generation BIGINT, revision BIGINT, effective_readiness TEXT,
  reason TEXT, unavailable_since TIMESTAMPTZ, order_ambiguous_at TIMESTAMPTZ
- ทั้งสองตารางเป็นข้อมูลตลาดสาธารณะ ไม่มี user_id/secret จึงไม่มี RLS
  migrator เป็นเจ้าของ; market-data SELECT/INSERT/UPDATE; API/ENGINE SELECT เท่านั้น
  engine_scan/auth ไม่ได้ grants ใหม่ ไม่มี runtime DDL
- ใช้ MarketDataSession หรือ UserSession ที่ระบุ role ตามเดิม ไม่คืน connection ดิบ
- CHECK หน่วย/คู่/ราคา/field null coherence และ FK source; ไม่มี unbounded trade log
- downgrade ลบเฉพาะตารางใหม่ หลังหยุด F-10 runtime; ไม่ทำให้ F-09 สูญข้อมูล

worker ใช้ DB lease5s ต่ออายุทุก1s; takeover เพิ่ม generation ภายใต้ row lock
ทุก write ต้องตรวจ owner/generation/lease ด้วย DB clock ใน transaction เดียว
lease หาย → ปิด feed/หยุดเขียนทันที; worker อีกตัวไม่เปิด upstream จนได้ lease
ทุก reconnect เพิ่ม durable generation ภายใต้ owner/lease CAS ด้วย ไม่ใช้
connection epoch ที่เริ่มนับจากศูนย์หลัง restart; adapter callbacks ผูก generation นี้
startup/takeover/reset connection ทำ reconciled false ทั้ง5คู่ก่อนรับ snapshot
อ่านordering latchเดิมจากPGและห้ามresetเพียงเพราะได้generationใหม่
DB commit ไม่สำเร็จ → ไม่ publish และไม่ประกาศ ready

flush dirty quotes สูงสุดทุก100ms (latest-price feed ไม่ใช่ every-trade archive)
control/disconnect flush ทันทีตามคิว priority ไม่รอ quote batch
revision ของคู่เพิ่มใน SQL ภายใต้ lock เมื่อ effective quote/state เปลี่ยน
lease refresh ไม่ทำให้ trade ใหม่หรือรีเซ็ต unavailable_since
consumer ตรวจ lease_until และอายุเองด้วย DB reference time;
หาก producer crash ที่ไม่มี close event จะไม่พร้อมเมื่อ lease หมด ไม่ค้าง READY

unavailable_since คงอยู่ข้าม restart/reconnect; reset เฉพาะเมื่อพร้อมจริง
กรณีอายุเกิน10s ใช้ trade_at+10s เป็นจุดเริ่ม; crash ใช้ lease deadline;
known disconnect ใช้เวลาที่ตรวจพบ เลือกจุดเริ่มที่มาก่อนเมื่อมีหลายสาเหตุ
ถ้าพร้อมช่วงสั้นระหว่างสอง read ต้องมี durable transition เพื่อไม่รวมสองช่วง
ดังนั้น worker ticker1s บันทึก age/lease transitions และ flush พร้อม quote
API ประเมินเวลาที่ผ่านไปเองด้วย เพื่อไม่ต้องรอ ticker ตอนอ่านราคา

## 4. Redis และ API

ใช้ Redis7 ใน compose ไม่ expose public port; API subscriber อ่าน notification และใช้pre-auth admissionkeysตามหัวข้อconnectionbudgets
market-data publisher เขียน channel `market.prices.changed` เท่านั้น
แยก Redis ACL/env ตาม process; ไม่มี default allow-all credentials ใน runtime
publish ส่ง source/revision notification หลัง PG commit ไม่ส่ง session/user data
Pub/Sub หายได้: broadcaster subscribe ก่อนอ่าน snapshot PG และตรวจ revision
ซ้ำทุก1s; รวม notification bursts ให้ read PG สูงสุด10ครั้ง/s ต่อ API process
Redis disconnect → downstream RECOVERING ทันที; resubscribe+อ่าน PG
ก่อนกลับพร้อม; ไม่ให้ notification เก่าทำ revision ย้อน
Redis downtime ไม่ขวาง upstream ingestion/PG commit ไม่สะสม retry queue

เพิ่ม authenticated GET `/market-data/prices` คืนทั้ง5คู่ ไม่รับ arbitrary symbols
และ WS `/market-data/prices/stream` ส่ง full PricesView ตามแบบเดียวกับ GET
ตัวเลขราคาเป็น string; revision/generation เป็น decimal strings เพื่อไม่ล้น JS
PricesView มี schema_version=1, server_time (DB reference time หลังอ่านข้อมูล),
delivery status และ rows:
source/base/quote/amount/trade_at/received_at/revision/generation,
readiness/reason/valid_until/unavailable_since/alert_due
valid_until เป็น deadline ที่ server ใช้ประเมิน ณ server_time ไม่ใช่ browser timer
amount nullable เมื่อยังไม่มีราคา; failure_code เป็นรายการกลาง ไม่ส่ง exception text
GET ไม่รับ arbitrary symbols หรือ request_id; Cache-Control:no-store
GET ต้องอ่าน current snapshot และประเมิน readiness ด้วย DB reference timeใหม่
ไม่ส่ง cached READY โดยเปลี่ยนเฉพาะ server_time; client ตรวจ schema ก่อน cache

WS ไม่อยู่ใน OpenAPI จึงใช้ price_models.py เป็นสัญญา shared กับ GET
contract test deserialize ทุก frame เทียบ PricesView; generated type จากGET
ไม่เพิ่ม PriceReadRequest หรือ client-side proof protocol
client ส่ง application commands ไม่ได้; application frameใด ๆ ปิด1008
ตั้ง inbound max256bytes เพื่อจำกัด malformed frames; native ping/pong จัดการตามtransport
ส่ง full view เมื่อ quote/state เปลี่ยนและ heartbeat full view ทุก1s
ทุก view ประเมิน backend readiness ใหม่ตาม DB reference time
clientช้าใช้ latest push slot1, send deadline5s แล้วปิด1013 ไม่สะสมราคา
หลังaccept/reconnectรับ full viewใหม่ก่อนแสดงสถานะ snapshot ของconnectionนั้น

### ตัวตนของ WS

HTTP middleware เดิมไม่ครอบ WebSocket จึงเพิ่ม ASGI scope guard ที่จุดกลาง
ใช้ authentication.py helper สำหรับ presented token → owner_of_presented
ใน transaction สั้นภายใต้ API/RLS; HTTP identify ใช้ helper นี้ซ้ำ โดยกฎ renew
ของ HTTP เดิมไม่เปลี่ยน WS ไม่ renew และไม่รับ token ใน URL/message
RouteRule เพิ่ม `('WEBSOCKET','/market-data/prices/stream')` และ GET Rule()
route coverage gate ต้องเดิน WebSocket routes และ unknown scopes ปฏิเสธ

ก่อน accept ต้อง session ใช้ได้และ Origin ตรง configured allowlist
ไม่ยอม wildcard/missing Origin สำหรับ browser route; Vite proxy เปิด ws:true
เพิ่ม public origin configuration สำหรับ dev/compose โดยไม่เชื่อ Host ที่ผู้เรียกส่ง
ระหว่างต่ออยู่ revalidate อย่างน้อยทุก1s ก่อนส่ง view ใหม่;
หมดอายุ/เพิกถอน → ปิด4401, frontend ส่ง ApiRequestError(401) เข้า expiry flow
DB/auth error → ปิด1011 และแสดง offline ไม่ปล่อย feed ผ่าน
ไม่ถือ transaction/DB connection ตลอด socket และไม่ log cookie/token/hash
ไม่เปลี่ยน csrf/TOTP/recovery grant ของ HTTP endpoints


### Connection budgets และ handshake admission — แก้ review issue4

ค่าที่เสนอสำหรับF-10 เป็นresource limits ไม่ใช่กฎการเทรดหรือSLA
เพดานต่อผู้ใช้เป็นค่าคงที่ **3 slots** ของสัญญา schema สำหรับ F-10
ไม่เปิดเป็น environment/settings override ส่วน limits อื่นในตารางประกาศ
ใน settings ที่เดียว มี validation และ documented defaults ตามขอบเขตเดิม
runtime ประกาศ `USER_CONNECTION_SLOTS = (1, 2, 3)` ที่
`infra/realtime/connections.py` จุดเดียว; claim ใช้ tuple นี้และ service เรียกผ่าน
connection repository ไม่ประกาศจำนวนช่องซ้ำใน settings
migration0014 เก็บ CHECK1..3 แบบ literal เพื่อให้ migration ย้อนรันได้คงเดิม
ไม่ import runtime constant เข้า migration; ใช้ actual-DB contract test
ตรวจว่า constraint กับ runtime slots สอดคล้องกัน
การเปลี่ยนเพดานต่อผู้ใช้ภายหลังต้องแก้แผนที่อนุมัติและทำ migration คู่กับ runtime
ไม่เปลี่ยนด้วย configuration อย่างเดียว:

| ขอบเขต | ค่าเสนอ | การบังคับ |
|---|---|---|
| ผู้ใช้เดียวทุกsession/device/APIprocessรวมกัน | คงที่ 3 unexpired connection slots; ไม่มี settings override | PGunique(user_id,slot), slot1..3 ภายใต้RLS |
| APIprocessเดียว pending+acceptedรวม | 100 | localnon-waiting reservationก่อนเข้าDB; connectionหมดอายุยังนับจนtransportปิด |
| pendinghandshakeต่อprocess | 16 | localnon-waiting semaphore; ไม่มีwaitingqueue |
| handshakeทั้งระบบ | 200 attempts/60s fixedwindow | sharedRedisatomiccounterก่อนsessionlookup |
| handshakeต่อIP | 30 attempts/60s fixedwindow | sharedRedisatomiccounterก่อนsessionlookup |
| authenticatedhandshakeต่อผู้ใช้ | burst6, เติม1tokenทุก10s | api_throttle tokenbucketเดิมนับทุกattemptที่ตรวจตัวตนผ่าน |
| connection slot lease | 5s, renewทุก1s | DBclockและCASconnection_id; renewหลังตรวจsessionผ่าน |

global/IPcounterต้องตรวจและนับแบบatomicในLua scriptสั้นที่มีจำนวนคำสั่งคงที่
ใช้RedisTIMEเป็นwindowreference; ตรวจglobalbudgetก่อนสร้างIPkeyใหม่
เมื่อglobalbudgetหมดต้องไม่สร้างkeyจากIPอื่นเพิ่ม; keysมีTTL120s
Redisเก็บhashIP ไม่เก็บcookie/token/secret; scriptsใช้KEYS/ARGVไม่ประกอบsourceใหม่
unknownpeerใช้sharedunknownbucket ไม่เชื่อX-Forwarded-Forจากผู้เรียก
หากใช้reverseproxyต้องตั้งtrustedproxyexplicitlyก่อนอ่านforwardedIP
Redisล่ม/timeout≤500ms → failclosedเฉพาะnewWS admission ไม่มีunlimitedfallback
Redisrestartรีเซ็ตattemptcountersได้ แต่ไม่รีเซ็ตPGactive-user-slots
APIACLเพิ่มเฉพาะcommandsของadmissionscriptและkeyprefix`market.ws.admission:*`
market-dataไม่มีสิทธิ์prefixนี้; APIไม่มีสิทธิ์publishราคาหรืออ่านkeyอื่น
หลักฐานatomicityอยู่ใน [Redis Lua docs](https://redis.io/docs/latest/develop/programmability/eval-intro/)

ขั้นตอนก่อนaccept:
1. จัดประเภทpath/scope; จองprocessbudget+pendingslotแบบไม่รอ หากเต็มปิดก่อนDB
2. หักglobal/IPattempt แม้ภายหลังOrigin/sessionไม่ผ่าน; ตรวจOriginallowlist
3. lookupsessionภายใต้RLS; เมื่อผ่านใช้spend_tokenกับBucket.PRICE_STREAM_HANDSHAKE
   capacity6/refill10s บันทึกในtransactionของตัวเอง ไม่rollbackเมื่อslotclaim/acceptล้มเหลว
4. claimuserconnection slotในtransactionสั้น แล้วจึงaccept/sockettasks
   acceptfailure/cancellationทุกจุดต้องปล่อยlocalreservationsและreleasePGslotที่จองสำเร็จ

ก่อนaccept ถ้าถูกจำกัดใช้ASGIclose1008 (handshakeไม่สำเร็จ)
ไม่คาดว่าbrowserจะได้รับclosecode/reasonที่กำหนดก่อนaccept;
frontendต้องแสดงไม่พร้อมและใช้backoffเดิม ไม่มีimmediateretryเมื่อเปิดsocketไม่สำเร็จ
ถ้ามีHTTP denial extension ใช้429/Retry-Afterแต่ไม่พึ่งextensionเพื่อบังคับโควตา
process/DBbudgetหมดระหว่างเปิดอยู่ → ปิด1013 และคืนslotตามfinally
ไม่ปิดconnectionเดิมเพื่อให้handshakeใหม่แย่งช่อง

#### ตารางuserconnection slotsในmigration0014

`market_price_connections`: user_id UUID NOT NULL FKusers ONDELETECASCADE,
slot SMALLINT CHECK1..3, connection_id UUID UNIQUE NOT NULL,
lease_until TIMESTAMPTZ NOT NULL; PK(user_id,slot)
เป็นconnectionmetadataของผู้ใช้ ไม่ใช่ตารางราคาสาธารณะ
เปิดFORCERLS/policiesตามcurrent_user_idสำหรับSELECT/INSERT/UPDATE/DELETE
APIได้สิทธิ์ทั้งสี่ผ่านUserSession; migratorเป็นเจ้าของ;
market-data/engine/engine_scan/authไม่ได้grantsตารางนี้
ไม่เก็บrawsessiontokenหรือtokenhashในตาราง connection_idเป็นservergeneratedopaqueID

claimใช้INSERTONCONFLICT(user_id,slot)DOUPDATEเฉพาะlease_untilหมดแล้ว
พร้อมRETURNINGconnection_id; ลอง USER_CONNECTION_SLOTS (1, 2, 3) ตามลำดับเดียวกันในtransactionเดียว
DBuniqueและrowlockingทำให้claimพร้อมกันจากสองprocessไม่เกิน3leases
ห้ามCOUNTก่อนINSERTโดยไม่มีconstraint/atomicclaim
ใช้DBclockหลังได้rowlockตรวจexpiry และตั้งleaseใหม่ ไม่ใช่เวลาrequestเริ่มก่อนรอlock
เวลาล็อก/statement/connectionpoolมีtimeout≤500ms ไม่มีunboundedwait
หลักฐานrowlockingอยู่ใน [PostgreSQL docs](https://www.postgresql.org/docs/16/explicit-locking.html)

renewและreleaseใช้(user_id,slot,connection_id)CASภายใต้RLS
renewได้เฉพาะleaseเดิมยังไม่หมดและsessionยังใช้ได้;
expiredownerห้ามต่ออายุleaseเก่าหรือclaimใหม่จากsocketเดิม
close/revoke/idleexpiry/sendtimeout/protocolerror/logout/cancel → releaseในfinally
releaseซ้ำเป็นno-op; oldsocketfinallyห้ามลบleaseของsocketใหม่
processcrashไม่มีfinally → ช่องreuseได้เมื่อlease5sหมดด้วยatomicclaim
expiredsocketที่ยังไม่เห็นtakeoverต้องหยุดส่งก่อนrenew/authorizationรอบถัดไป
เพดาน3หมายถึงunexpiredauthorizedslots ไม่อ้างว่าzombieTCPหายทันทีเมื่อleaseหมด
zombieTCPยังถูกจำกัดด้วยphysicalprocessbudget100และsendtimeout

ขยายapi_throttle_kind CHECKเพื่อเพิ่มPRICE_STREAM_HANDSHAKE;
Bucket.table/RULES/cleanupใช้patternเดิม เฉพาะbucketใหม่ ไม่แตะlogin/TOTP/APIkeylimits
connectionrowsสูงสุด3ต่อuser ไม่สะสมrowต่อhandshake; releaseลบเฉพาะslotตนเอง
crashrows reuseแบบlazyclaim; ไม่ต้องให้backgroundjobใหม่มีสิทธิ์ข้ามRLS
migrationdowngradeลบconnectiontableและbucketrowsใหม่ก่อนคืนCHECKเดิม
ไม่ลบหรือเปลี่ยนtokenbalancesของbucketเดิม

#### จำกัดDBงานrealtime

WSใช้API-role engineแยกpoolจากinteractiveHTTP: pool_size3/max_overflow0,
pool_timeout≤500ms; credentials/role/RLSเดิม ไม่มีURLของroleที่แรงกว่า
ขยายcreate_engine_forด้วยboundedpooloptionsสำหรับcallerนี้ defaultsเดิมไม่เปลี่ยน
ไม่เปิดtransactionตลอดsocketและไม่สร้างtaskตรวจsessionใหม่ต่อทุกpush
socketมีcoordinatorเดียวรวมrenew/sessioncheck/clocksampleในtransactionเดียวทุก500ms
มีauthorizationdeadlineจากเวลาเริ่มsuccessfulcheck+1s ไม่ต่อเวลาเพราะqueryช้า; ต้องเริ่มตรวจให้ทันdeadline
เวลารอqueryจำกัดmin(500ms, remainingauthorizationbudget)
ถ้าตรวจไม่ทันdeadline watchdogหยุดส่ง/ปิดsocket ไม่รอDBต่อจนเกิน1s
ไม่มี client snapshot command หรือ auth queryต่อpush; coordinator≤2DBtransactions/s/socket
การส่งpushใช้ผลตรวจsessionอายุไม่เกิน1s มิฉะนั้นรอตรวจหรือปิดsocket
ยังต้องปิดrevoked/expiredsessionภายในรอบ1sตามV-17
N≤100ทำให้coordinator WStransactions≤200/s/processตามdesignbudgetก่อนhandshake
บวก shared snapshot reads≤10/s/processตามbroadcaster (ไม่นับhandshake/cleanup)
นี่คือupperboundจากlimits ไม่ใช่ผลbenchmarkหรือรับรองDBthroughputจริง
pool/statementtimeoutทำให้failclosed ไม่กินpoolของinteractiveHTTP

browserconnectionใช้หนึ่งตัวต่อAccountSession; unmount/identitychangeหยุดreconnecttimer
cleanupคืนquotaทุกexitpath; ห้ามใช้ราคาสำรองหรือเปิดupstreamเพิ่มเพื่อหลบcap
pendingcap/throttleไม่กระทบคำสั่งลดความเสี่ยงหรือHTTPauthเดิม

## 5. UI ขั้นต่ำ

วาง RealtimePricePanel หลัง TradingAccountPanel ใน AccountSession เดิม
ตาราง5แถว desktop และรายการอ่านง่ายที่360px มีคู่/ราคา USDT/เวลาซื้อขาย/สถานะ
ไม่มีกราฟ/ปุ่มซื้อขาย/selector เพิ่มคู่; missing แสดงไม่มีข้อมูล ไม่แสดงศูนย์
ใช้ tokens และ layout ของ TailAdmin เดิม ข้อความไทย/อังกฤษผ่าน i18next
ใช้ formatter กลางสำหรับ decimal string และวันเวลา ไม่แปลงเงินเป็น Number
หาก formatter เดิมไม่มี สร้าง `frontend/src/components/MarketValue.tsx`
สำหรับ string formatting ล้วน ไม่คำนวณเงิน ใช้ร่วมทุกแถว

TanStack Query key `['market-data','prices']` ใน cache ต่อ identity
GET initial snapshot และ WS ใช้ full view ชุดเดียว; compare generation/revision
รายคู่ก่อน setQueryData โดย state guard ใช้ server_time ของ delivery view ด้วย
generation/revision/server_time เป็น ordering metadata ไม่ใช่ browser freshness proof
HTTP snapshot ที่ช้ากว่า WS ต้องไม่ย้อน quote/connectivity; connection epoch
กัน callback socketเก่า และ identity guards กันข้อมูลข้ามผู้ใช้
cleanup close/abort/timers เมื่อ logout/unmount/identity change

### สถานะตาม snapshot — NC-26 อนุมัติ2026-10-07

เว็บแสดง reported readiness ของ snapshot พร้อมข้อความเช่น
“พร้อม ณ เวลาที่ตรวจ” / “Ready at last check”, server_time และ trade_at
ไม่แสดง READY เดี่ยว ๆ ที่อ้างราคาปัจจุบัน และไม่คืน boolean trusted/current-ready
ให้ execution consumer จาก cacheเว็บ
ราคาและreported status เก็บในTanStack Queryต่อidentity; delivery status เป็น
local metadata เช่น CONNECTING/CONNECTED/DISCONNECTED/AWAITING_SNAPSHOT
CONNECTED แปลเพียงสถานะ transport ที่สังเกตได้ ไม่รับรองราคา/account

ยกเลิก clock_eligible/clock_epoch, budgets1ms, correlated request/time proof
ไม่รับรอง browser clockข้ามsleep และไม่ใช้ Date.now/performance.now
เปลี่ยน server readiness หรือยืด trade_at/valid_until
browser heartbeat/watchdog3s เป็น detection timer เมื่อ callbackทำงาน:
close/offline/missedheartbeatที่ตรวจพบ → แสดง delivery failureทันทีพร้อมข้อมูลค้าง
hidden/freeze/pageshow/resume ที่ตรวจพบ → รอ full snapshotใหม่และ reconnect
ตาม backoffเดิม; ถ้าOSsleepไม่มีeventและclockหยุด ป้ายยังหมายถึงsnapshotเดิม
พร้อมเวลาที่ตรวจ จึงไม่อ้างว่า fresh ณ เวลาตื่นหรือว่า detect sleepได้ครบ

ข้อความ HTTP/WS ที่หน่วง500ms ตอนราคาอายุ9.9s ยังคงแสดงเฉพาะ
“พร้อม ณ server_time” พร้อมเวลา ห้ามทำเป็น READY ปัจจุบันหรือเปลี่ยนเวลาเป็นreceipt
เกณฑ์backend10s/leaseยังตรวจด้วย DB reference time ณ การสร้าง snapshot
backend consumer (futureexecution) ต้องอ่านข้อมูลและประเมิน readiness ใหม่ก่อนใช้
F-10 ไม่มี order endpoint/action หรือ front-end money calculations

schema invalid → offline/refetch; connection epoch guardและbackoffยังทำงาน
ไม่สร้าง upstreamเพิ่มหรือข้าม admission; timer failure ไม่บล็อกการรับราคา
UI status มีreason ข้อความไม่พึ่งสีและaria-liveเฉพาะtransition ไม่อ่านทุกtick

### Alert60s และ delivery warning — NC-27 อนุมัติ2026-10-07

serverนับmarket-unavailable interval จากDB reference timeกับdurable
unavailable_sinceตามข้อ3; ครบ60sตั้งalert_due ไม่ใช้browserelapsed
ช่วงไม่พร้อมคงอยู่ข้ามrestart/reconnect/lease refresh และhandshake
resetเมื่อbackend readinessผ่านจริงเท่านั้น ไม่รวมสองช่วงที่มีREADYคั่น

เว็บแสดงmarket warningจากsnapshotที่ผ่านordering/schema/identity guards
พร้อมserver_time การเตือนหมายถึงผลที่serverตรวจ ณsnapshotเช่นเดียวกับstatus
snapshotหลังAPI/Redisrecoveryประเมินalert_dueใหม่ ไม่ถือcachedfalseว่ายังสด
marketwarningเก่าบนหน้าที่หลุดคงแสดงเป็นข้อมูลตามsnapshotพร้อมเวลา
ไม่ลบwarningจากhandshake; หลังได้snapshotใหม่ใช้alert_dueของsnapshotนั้น

browserclose/offline/missedheartbeatที่ตรวจพบ → แสดงdeliverywarningทันที
เช่น “การเชื่อมต่อขาด ข้อมูลอาจไม่เป็นปัจจุบัน” พร้อมเวลาsnapshotล่าสุด
ไม่มีlocal60s countdown/alert-clock eligibility หรือการนำwallclockมาอ้างelapsed
callbackถูกพักตอนOSsleepอาจตรวจพบช้ากว่าเวลาจริง: เตือนทันทีเมื่อมีหลักฐาน
ไม่รับรองzero-latencyหรือdetectsleepครบ; snapshotcopyยังอ้างเฉพาะเวลาที่ตรวจ

reconnectทำdeliverystatusเป็นAWAITING_SNAPSHOT และยังแสดงข้อความว่ารอสถานะใหม่
ไม่เคลียร์เพียงเพราะtransportเปิดได้; fullviewใหม่ที่ผ่านguardsจึงเคลียร์ข้อความ
delivery failure ขณะmarketwarningยังมีอยู่ต้องสื่อทั้งสองเหตุ ไม่ใช้แทนกัน
ไม่ประกาศซ้ำทุกtick; aria-liveใช้เฉพาะtransitionและข้อความไทย/อังกฤษ

NC-26/NC-27ปิดแล้ว requirements/plan/validationได้รับอนุมัติครบ
เจ้าของอนุมัติแผนทั้งฉบับแยกจากคำตัดสินNC-26/NC-27 วันที่2026-10-07

## 6. ลำดับลงมือหลังอนุมัติ

แต่ละขั้นเริ่มด้วยเทสต์เฉพาะพฤติกรรมที่คาดหวัง ให้เห็นแดงก่อนเขียนส่วนใหม่
แล้วตรวจเขียวรวม boundary tests ก่อนข้ามขั้น; ไม่จำเป็นต้อง commit ระหว่างขั้น

1. [x] core/contracts: QuoteObservation/readiness/ordering, fake feed, reuse catalog
   tests `backend/tests/core/test_realtime_prices.py`, `backend/tests/venues/test_price_streams.py`
   ตัวอย่าง: อายุ10s READY/10s+1µs STALE; duplicate Eใหม่ไม่เลื่อนอายุ;
   same T/different price → ORDER_UNCONFIRMED ไม่เลือกhigherID;
   timestampใหม่กว่าแต่IDน้อยกว่าต้องไม่ถูกมองว่าเก่า; scopedduplicateconflict → RECOVERING
2. [x] adapter: parser/transport/feed + public fixtures และ gates
   tests `backend/tests/venues/binance_th/test_price_feed.py`
   ทดสอบ explicit ack, malformed payload, old generation, stream ahead of snapshot,
   retry-after, ping timeout, 24h rotation ด้วย fake transport/time ไม่ยิงตลาด
   same-timeREST/WSdifferentprice, pre-latchRESTattempt, persistedlatchและ
   next-bucketRESTresolutionต้องพิสูจน์ตามV-8
3. [x] migration/storage: actual grants/lease/revisions/concurrent writer fencing
   และuserconnectionRLS/atomicclaim/APIhandshakebucketตามV-29/V-30
   tests `backend/tests/infra/realtime/test_connections.py`,
   `backend/tests/infra/realtime/test_admission.py`
   tests `backend/tests/infra/market_data/test_realtime_storage.py`
   migrator upgrade/downgrade; API write denied; stale owner CAS rejected
4. [x] supervisor/Redis: PG commitก่อนpublish, crash, reconnect, durable alert interval
   tests `backend/tests/services/market_data/test_realtime.py`,
   `backend/tests/infra/realtime/test_notifications.py` ใช้ Redisจริงในชุด integration
   ประกอบ F-09 loop ร่วม client/limiter; shutdown ปิด tasks/clients ไม่มีงานค้าง
5. [x] API: snapshot/broadcaster/ASGI auth/WS + schema generation
   tests `backend/tests/api/test_realtime_prices.py`
   expired/revoked sessions, Origin, unknown route, slow clients, missed Pub/Sub
   admission/processcaps/pre-authglobal-IPthrottle/PGslotcleanupต้องผ่านV-29..32;
   tests `backend/tests/api/test_price_admission.py`;
   snapshotต้องประเมินreadinessด้วยDBreferenceใหม่; appcommandsปิด1008;
   frame limits/pushslot1 และ schema contract ต้องผ่าน
6. [x] frontend: cache/proxy/panel/i18n และ E2E fake producer ผ่าน services จริง
   tests `frontend/tests/realtimePrices.test.ts`,
   `frontend/tests/RealtimePricePanel.test.tsx`, `frontend/e2e/realtime-prices.spec.ts`
   delayedHTTP/WS9.9s+500msต้องแสดงstatus ณserver_time ไม่อ้างcurrentREADY;
   ทดสอบ ordering, clockchange/sleepไม่เปลี่ยนเวลาที่ตรวจ, reconnect/resume
   ห้ามสร้าง production endpoint สำหรับฉีด fake quotes; test-only subprocess
   `backend/tests/e2e_realtime_runner.py` ใช้ FakeVenue และ role market-data จริง
7. [x] ตรวจครบ validation + scope review + final check; update roadmap เมื่อเสร็จจริง
   ก่อน merge ทุกด่าน testing.md ต้องเขียว; commit/push/PR ตามคำสั่งเจ้าของเท่านั้น

## ความเสี่ยงและข้อจำกัด

- มี batching100ms/lease5s/heartbeat detection3s จึงไม่รับรอง zero-latency
  known disconnect ต้อง invalidateทันที; unknown producer crash ตรวจจาก lease
- หลักฐานจริงพบ duplicate และ initial query-only silence; ไม่ประกาศพร้อมจาก ack
- ไม่รับรอง shared-IP quota ทุก process; ข้อจำกัด F-35 ก่อนปล่อยผู้ใช้จริงยังคงอยู่
- ราคาร่วมไม่ได้พิสูจน์ความพร้อมบัญชี และไม่ได้ทำให้ Live เปิดได้
- Redis ACL/ASGI scope guard เป็นส่วนของแผนนี้ ต้อง actual integration test
- NC-26/NC-27 Closed: ownerอนุมัติsnapshotและalertsemantics; แผน/validationได้รับอนุมัติแล้ว
- socket/handshakecapsเป็นค่าที่เสนอในแผน; ยังไม่ได้benchmarkและต้องอนุมัติก่อนโค้ด

## บันทึกการแก้หลัง review

รายการก่อน NC-26 approval เป็นประวัติการออกแบบ; ส่วนหลักด้านบนเป็นแผนปัจจุบัน
วิธี correlated freshness proof/clock certification ในประวัติถูก superseded แล้ว

2026-10-07 — issue2: เปลี่ยนจาก receipt-anchored countdown เป็น
correlated request + conservative remaining budgets โดยรวมเวลาทั้งรอบ
เพิ่ม inbound WS schema และกรณีทดสอบ V-19/V-20/V-23
requirements10s/60sคงเดิม; planยังProposed ไม่ใช่การอนุมัติ implementation
ขณะแก้issue2นั้นissue3/4ยังไม่ได้แก้; การแก้issue3บันทึกด้านล่าง

2026-10-07 — issue3: ตัดnumerictrade-IDtie-breakerออก ใช้partialorder
ตามtrade_time; equal-time/different-priceไม่พร้อมและเก็บdurableambiguitylatch
กู้ด้วยRESTattemptที่เริ่มหลังพบปัญหาและtimestampที่ข้ามlatchแล้ว
เพิ่มV-8 casesและแก้researchไม่ให้สื่อว่าหลักฐานสั้นรับรองIDmonotonicity
ไม่เปลี่ยนrequirements ไม่อนุมัติแผนแทนเจ้าของ; reviewissue4ยังไม่ได้แก้

2026-10-07 — issue4: เพิ่มper-userPGslotleases/RLS, per-processphysicalcap
และpendingcap พร้อมpre-authglobal/IPthrottleและauthenticateduserbucket
เพิ่มCAScleanup/crashrecovery/separateboundedAPI-rolepool และV-29..32
ค่าจำกัดทั้งหมดเป็นProposed; ไม่เปลี่ยนrequirementsการเทรดและไม่เริ่มโค้ด


2026-10-07 — review รอบสอง issue1: เพิ่ม subscription-ack deadline5s
นับก่อน send รวม limiter/send; pong หรือ ack ผิด id ไม่ต่อเวลา
timeout invalidate attempt/แจ้ง failure/ปิดแบบมี deadline แล้วเข้า backoff เดิม
เพิ่ม V-10 สำหรับ missing/mismatched/late ack และ deadline races
plan/validation ยัง Proposed; ยังไม่มีผลทดสอบ runtime


2026-10-07 — review รอบสอง issue2: เพิ่ม clock guard/clock_epoch ก่อน consume
ตรวจ discontinuity โดยไม่พึ่ง lifecycle events และ invalidate pending responses
แยก dual-clock heuristic ออกจากหลักฐาน clock ที่เดินข้าม suspend;
platform ที่พิสูจน์ไม่ได้ไม่ READY เพิ่ม V-23 no-event sleep/clock-adjustment cases
ยังไม่ได้รับรอง platform หรือผล runtime; plan/validation คง Proposed


2026-10-07 — review รอบสอง issue3: ระบุ user connection cap เป็นค่าคงที่3
ไม่มี settings override; runtime ใช้ slots tuple จุดเดียว ส่วน migration
เก็บ CHECK1..3 โดยไม่ import runtime เพิ่ม V-29 ตรวจ contract กับฐานข้อมูลจริง
limits อื่นคงเดิม; plan/validation ยัง Proposed และยังไม่ได้ทดสอบ runtime


2026-10-07 — review รอบสาม issue1: ตรวจ primary sources ของ clock และบันทึก
feasibility research; เพิ่ม preflight ก่อนอนุมัติและ NC-26 แทนการอ้างว่าไม่มีข้อค้าง
ยังไม่ certify platform/เปิด clock_eligible และยังไม่ได้ทดสอบ OS suspend จริง


2026-10-07 — review รอบสาม issue2: แยก transport/data lifecycle จาก clock proof
GET/WS รับราคาต่อได้เมื่อ ineligible; invalidate เฉพาะ proof/clock epoch
ไม่สร้าง reconnect storm หรือ outstanding requests ซ้อน เพิ่ม V-23 cold-start/
recovery/old-proof tests; NC-26 ยังไม่ปิดและยังไม่พิสูจน์ runtime


2026-10-07 — review รอบสาม issue3: แยก backend interval/local outage record
ใช้ suspend-inclusive alert-clock contract และรักษา record/latch ข้าม sleep
เพิ่ม V-24 no-event sleep/reconcile/local-only cases; ไม่ใช้ stopped monotonic
เป็นหลักฐาน60sอีก ยังไม่รับรอง target/ปิด NC-26 หรือผล runtime


2026-10-07 — owner approve NC-26: เปลี่ยนเว็บเป็นserver-observed snapshot status
พร้อมเวลา แยกtransport; backend freshness10s คงเดิมและประเมินใหม่ก่อนใช้จริง
ลบ clock certification/proof request protocol จากแผนปัจจุบัน
NC-27 alert local-onlyรอคำตอบ ไม่อนุมัติplan/validationหรือเริ่มโค้ดโดยปริยาย


2026-10-07 — owner approve NC-27: serverนับmarketoutage60s ส่วนbrowser
เตือนdeliveryfailureทันทีที่ตรวจพบ ไม่ใช้localelapsedclock; requirementsRQ-15แก้แล้ว
NC-26/NC-27ปิด; plan/validationยังProposedรออนุมัติทั้งฉบับก่อนโค้ด


2026-10-07 — เจ้าของตอบ approve ให้plan.mdและvalidation.mdทั้งฉบับ
requirementsอนุมัติแล้วและNC-24..27ปิด ครบgateก่อนimplementation
การเปลี่ยนแนวทางหลังจุดนี้ต้องขออนุมัติก่อนโค้ดตามAGENTS.md
ไม่ใช่คำสั่งcommit/push; implementationและผลทดสอบยังไม่เกิดขึ้น


## การเปลี่ยนแปลงหลังอนุมัติ — NC-28 Approved

พบขณะimplementation: รอบcoordinator1sและเพดาน1transaction/sไม่ให้เวลาพอ
ทำqueryถัดไปก่อนauthorizationdeadline1sที่ต้องนับจากcheck-start
ข้อเสนอที่ขออนุมัติ2026-10-07: ทุก500ms เพดาน2transactions/s/socket
รวม≤200/sที่100sockets บวกsharedread≤10/s; คงpool3/overflow0,
querytimeout≤500ms และstrictwatchdogปิดเมื่อauthorizationdeadlineหมด
watchdogต้องยกเลิกsend/queryที่ค้าง ไม่รอqueryเกินdeadline

เจ้าของตอบ approve วันที่2026-10-07 ก่อนเปลี่ยนโค้ด ปรับแผนด้านบนเป็น500ms/2transactionsแล้ว
NC-28ปิด; strictwatchdogและV-17/V-32ต้องทดสอบตามแผนฉบับแก้ก่อนรับรอง


2026-10-07 — implementationและlocalvalidationครบตามขั้น1..7
ผลและข้อจำกัดอยู่ใน specs/reviews/2026-10-07-f10-realtime-prices/final-validation.md
ยังไม่มีcommit/push/mergeหรือผลexternalCI; CIต้องเขียวก่อนmergeตามtesting.md


## การเปลี่ยนแปลงหลังอนุมัติ — NC-29 Approved (2026-10-08)

**Approved — เจ้าของเลือกอนุมัติข้อยกเว้น decoder ตาม NC-29 วันที่2026-10-08 ก่อนเปลี่ยนด่าน**

Review issue7: native decoder ปิด oversized messages ด้วย1009ก่อนถึง ASGI แต่
แผนข้อ API กำหนด1008สำหรับ application messages ทุกชนิด และ inbound256bytes.
Draft ที่เตรียมเพื่อทบทวนอยู่ที่
`backend/src/tiewtrade/services/api/price_protocol.py`: สืบทอด Uvicorn Sans-I/O
protocol และ websockets ServerProtocol เพื่อเปลี่ยนเฉพาะ size-failure1009เป็น1008.
คง bounded decoder256bytes รวม UTF-8 bytes/fragmented/compressed messages,
ASGI/auth/flow-control/keepalive ใช้ของ Uvicorn เดิม ไม่มี outbound connection.

Draft ผ่าน wire tests และ Docker build แต่ด่าน NC-17 เดิมไม่อนุญาต import
websockets นอก gateway จึงยังรับรองหรือปรับด่านให้ผ่านไม่ได้. NC-17 ใน F-07
plan ระบุว่า "ห้ามเพิ่มข้อยกเว้นโดยเดาเอง".

**คำตัดสินที่อนุมัติ:** เพิ่มข้อยกเว้นเฉพาะไฟล์ price_protocol.py และเฉพาะ
`websockets.server.ServerProtocol` (ใช้เป็น base class ของ decoder เท่านั้น) กับ
`websockets.frames.CloseCode` (type annotation/enum constants เท่านั้น).
ไม่ยกเว้นทั้งไฟล์หรือ module; ไม่อนุญาต connect/HTTP/socket/asyncio network calls,
client protocols, re-export หรือประกอบ market URL. Uvicorn จำกัด>=0.54,<0.55
เพราะ adapter อาศัย Sans-I/O implementation ที่ตรวจแล้ว; lockfileไม่เปลี่ยน
เวอร์ชัน package ที่ติดตั้ง. Docker/Compose/README/Playwright ใช้ --ws entry point
เดียวกัน; decoder กำหนด256bytesภายใน adapter.

หลังอนุมัติจึงปรับ network boundary checker และเพิ่ม negative fixtures ยืนยัน
ว่า member อื่น, ไฟล์อื่น, outbound client, re-export และ asyncio network calls
ยังถูกปฏิเสธ แล้วรันด่านและ backend regression อีกครั้ง. ข้อกำหนดราคา/การเทรด
และ close code1008เดิมไม่เปลี่ยน.

NC-29 ปิดด้านคำตัดสิน; ต้องตรวจด่านและ regression ตามขอบเขตข้างต้นก่อนปิด issue7.

2026-10-08 — NC-29 implemented after explicit owner approval. Narrow decoder
import/use exception and positive/negative fixtures pass. Backend1851/frontend158/
Playwright10 and static/Docker/lock checks pass; final results recorded in validation.md.
The previous draft gate failure is resolved. Final deep review and externalCI remain.
