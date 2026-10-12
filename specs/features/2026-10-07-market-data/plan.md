# F-09 — Candle history Implementation Plan

สถานะ: **Approved** — เจ้าของตอบ approve วันที่2026-10-07 หลังแก้ไขและรีวิวแผนฉบับนี้; รวมNC-35 amendmentsที่เจ้าของอนุมัติเมื่อ2026-10-10
วันที่: 2026-10-07
Branch: feature/f-09-market-data

แผนdependencyของF-11 NC-35อยู่ใน [performance-plan-v2](../2026-10-10-backend-indicators/performance-plan-v2.md)
และ [ADR-002](../../decisions/002-prepared-indicators.md) — **Approved**
เจ้าของอนุมัติamendmentF-09เมื่อ2026-10-10 ตามคำสั่ง “approve”; พร้อมปรับphysicalcleanup/partition triggers/grantsตามแผน
แก้reviewรอบ2ข้อ1: รวมการปรับrun_round/write_candles/cleanupให้acquire sourcewrite
scopeก่อนlock_claim/candleprelocks และmaintenance relation-first ตามADR-002
ไม่ใช่การเปลี่ยนcleanupcutoffเพียงอย่างเดียว; amendmentนี้Approvedแล้ว
แก้reviewรอบ2ข้อ5: ต้องdrain/หยุดlegacyF-09รวมcleanupทุกreplicaก่อนติดstrict
sourceprooftrigger/เปิดbuilderตามS0..S5 และคงgraceระหว่างrollback supportwindow
ในแผนรอบ2; ห้ามoldimage restartกลับมาcleanup365วันระหว่างpreparedmode

ใช้ executing-plans ดำเนินงานตามลำดับหลังอนุมัติ รักษา working tree ไม่ commit/pushเอง

## เป้าหมายและข้อจำกัด

ให้ market-data ดึง/เก็บ/เติมประวัติแท่งเทียนใน PostgreSQL และ API อ่านข้อมูลพร้อมcoverage
6timeframes/5คู่ตามrequirements; ระยะเก็บ365วัน เริ่มไม่เกิน1,000แท่งล่าสุดต่อseries
ไม่ทำกราฟ/indicator/WebSocket/order/balance/Live ในงานนี้
ใช้ Python/PostgreSQL/React18/Vite6 และ dependencies เดิม
Money/Quantity และ DB domains เดิม ไม่มี float/financial Decimalเปล่า

## หลักฐานก่อนวางแผน

[Researchและ17publicfixtures](../../research/2026-10-07-f09-candle-history.md)
ตรวจ17GETแบบไม่ใช้key: ทุกtimeframeที่เลือกคืนshape12fields, ทั้งSITE/GLOBALดึงได้,
5คู่ตั้งต้นเป็นGLOBAL/TRADING; startTime/endTimeสังเกตว่าinclusiveตามopenTime
limit1000ได้1,000rows; limit1001และunknownsymbolคืน400พร้อมfixederrorcodes
UTC alignment/fixedspanสังเกตได้ครบ6intervals แต่ไม่ใช้สิ่งนี้รับรองประวัติทุกคู่

ข้อสำคัญที่แผนต้องคง:
- RESTไม่มีclosureflag ทุกRESTobservationเป็น **UNCONFIRMED** แม้closeTimeผ่านไปแล้ว
  ไม่ยืนยันจากเวลาที่ผ่านไป/แท่งถัดไป/อ่านสองครั้งเหมือนกัน
  โครงสร้างรองรับOPEN/CLOSEDสำหรับsourceที่มีหลักฐานจริงในงานถัดไป/FakeVenue
  coverageครบหมายถึงมีobservationsครบ ไม่ใช่finalityครบหรือพร้อมให้บอทเทรด
- เอกสารบอกweight1 แต่headersของ500/1000rowsเพิ่ม5 และinvalidlimitเพิ่ม10
  ไม่ได้พิสูจน์tariffจากIPที่แยกขาด แผนเสนอ **จองงบ10weightต่อklinesrequest**
  โดยส่ง `CallCost(weight=1, orders=0)` ตามเอกสารตลาด และใช้ local reservation floor
  ใน IpWeightLimiter ตามรายละเอียดด้านล่าง ไม่ส่ง CallCost(weight=10) แทนต้นทุน klines
  เป็นconservative local reservation ไม่กล่าวว่าตลาดคิด10; observe used-weight headers
  และ429/418ตามtransportเดิม ไม่มีHTTPretryในtransport
- IpWeightLimiterเดิมนับในprocessเดียวตามข้อยกเว้นF-35ที่อนุมัติแล้ว
  market-dataทั้งprocessใช้transport/guardชุดเดียว ไม่อ้างว่าquotaร่วมข้ามengineครบ
  shared-IP limiterก่อนปล่อยผู้ใช้จริงยังเป็นข้อจำกัดเดิมที่ต้องแก้ก่อนdeployment

## ของเดิมที่ใช้ซ้ำ

| Path | การใช้ |
|---|---|
| `core/money/` | Money/Quantity.of, comparisons, canonical units และprecision; ไม่เขียนกฎปัดใหม่ |
| `venues/{symbols,moments,errors,limits}.py` | Symbol, aware-time validation, fixed venue errors, CallCost/RateLimitGuard |
| `venues/binance_th/{transport,mapping,failures,rate_limit}.py` | typedclosed endpoint gate, parsing helpers, SITE/GLOBAL discovery, weight headers/errors |
| `venues/fake.py` | ขยายFakeVenueด้วยcandle pages/duplicates/failures ไม่ทำfakevenueชุดที่สอง |
| `infra/db/{engine,session,errors}.py` | role-specific URL, transaction/errortranslation, runtime role assertion |
| `services/api/{authentication,routing_policy,safe_input_routes}.py` | auth/CSRF/nonrenew routes/safevalidation; ไม่ใช้UserSessionกับworker |
| `services/engine/main.py` | ใช้เป็นแบบสำหรับcomposition/clock/workername/loop; ไม่importserviceนี้ |
| `migrations/versions/{0001_foundation,0006_partition_event_trigger}.py` | financial/unitdomains และตรวจผลaudit partition triggerเดิม ไม่เปลี่ยนสิทธิ์audit |
| `tests/infra/db/test_migrations.py`, actual-role/FakeVenue/E2E patterns | isolation/disposableDB/migrationrollback/roleerrors/networkgates |

## โครงสร้างและ interfaces

Pathsทั้งหมดด้านล่างอยู่ใต้ `backend/src/tiewtrade/` ถ้าไม่ระบุprefix

- `core/moments.py`: ย้ายrequire_awareที่เป็นpurestdlibจากvenues/moments.pyมาใช้ร่วม
  venues/moments.py re-exportsignatureเดิม ไม่เปลี่ยนพฤติกรรมของprice/constraints
- `core/market_data.py`: shared pure `Timeframe` (6ค่า), `CandleFinality`
  (UNCONFIRMED/OPEN/CLOSED), `Candle`, `CandleWindow` และpure window/gap helpers
  Candleมีbase/quote, open_at/end_at(exclusive), OHLC:Money, volume:Quantity,
  finality, observed_at; ไม่มีvenue-specificsymbol/clock/DB/network
  canonicalหน่วยใช้Quantity/Moneyเดิม ไม่คัดลอกregexจากSymbol
- `venues/candles.py`: `CandleSource.fetch_candles(symbol:Symbol, timeframe:Timeframe,
  start:datetime,end:datetime,limit:int)->CandlePage`; half-open `[start,end)` ในสัญญากลาง
  CandlePageพาsourceobservations/requestedrange/received_at ไม่สัญญาว่าครบทุกslot
- `venues/binance_th/candles.py`: ตัวเชื่อม, shapeguard และ published CallCost(weight=1, orders=0)
  ใช้ `Endpoint.KLINES="/klines"`; `endTime=end_ms-1`, explicitstart/end/limitทุกครั้ง
  normalizepublishedinclusivecloseTimeเป็นend_at exclusiveโดยเพิ่ม1ms
  primitiveparsers/timeconversionใช้mappingเดิม; ไม่ย้ายnetworkออกจากtransport
- `venues/__init__.py`: exports + `live_candle_source(client,clock,timeout)` แบบfactoryเดิม
  lazyadapterimport, sharedIpWeightLimiterภายในพร้อม reservation_weight_floor=10
  สำหรับ candle-source factory นี้เท่านั้น; ไม่เพิ่มTIMEendpointที่ไม่มีruntimecaller
- `infra/market_data/{records,storage,claims,__init__}.py`: มีแต่core/dbdependencies
  reads/coverage/demandcoalescing/claim/fencedwrite/retention ไม่มีvenuesimport
- `services/market_data/{ingestion,main}.py`: ประกอบCandleSource+infra, HTTPนอกDBtransaction
  `run_round(engine,source,worker,as_of)->RoundSummary`; loop/clockอยู่mainเท่านั้น
- `services/api/candle_routes.py`: input/query/DTOพร้อมcoverageและdemandstatus
- `migrations/versions/0013_market_candles.py`: สองตาราง+partition+grantsตามด้านล่าง

## Published cost และ local reservation budget (RQ-15)

- คงสัญญา `venues/limits.py`: CallCost คือ cost ที่ adapter ประกาศจากเอกสารตลาด
  klines ส่ง weight=1/orders=0 ผ่าน transport ตามหลักฐาน research; ไม่สร้าง CallCost
  ที่มีค่า10เพื่อแทนงบเผื่อ และไม่แก้ RateLimitGuard.reserve(cost) หรือ transport signature
- ขยาย `venues/binance_th/rate_limit.py` ของเดิมด้วย keyword-only
  `reservation_weight_floor: int = 1` ใน IpWeightLimiter; รับเฉพาะจำนวนเต็มบวก ไม่รับ bool
  ก่อน HTTP คำนวณ `reserved_weight = max(cost.weight, reservation_weight_floor)`
  แล้วใช้ค่านี้ชุดเดียวในการตรวจทุก window, คำนวณเวลารอ และบันทึก _Spent หนึ่งครั้ง
  ไม่จอง published cost ก่อนแล้วจองส่วนเผื่อแยก ซึ่งอาจสำเร็จเพียงครึ่งเดียว
  ไม่สร้าง limiter/ledger ตัวที่สอง ไม่แปลง reserved_weight กลับเป็น CallCost
- candle-source factory ตั้ง floor=10 ให้ limiter ที่ transport ของ source ใช้ร่วมกัน
  รวมการอ่าน exchangeInfo ซึ่งมี published cost10 อยู่แล้วจึงยังจอง10 ไม่ใช่20
  floor เป็น policy ของ limiter instance นี้ ไม่ใช่ tariff/limit tier ตาม page size
  factory เดิมของราคา/บัญชีใช้ default1 จึงคง accounting เดิม และยังปฏิเสธ cost.orders>0
- ใช้เพดานตลาดเดิม; reservation ที่เกินเพดานหน้าต่างใดต้องถูกปฏิเสธก่อน HTTP
  ไม่มี partial reservation เมื่อหน้าต่างหนึ่งผ่านแต่อีกหน้าต่างไม่ผ่าน
  UsedWeightObserver ใช้ ledger เดิมและเติมเฉพาะส่วนที่ตลาดรายงานสูงกว่า budget ที่นับไว้
  ยอด header ที่ต่ำกว่าไม่คืนงบเผื่อ; งบหมดอายุตาม window เดิม แม้ HTTP ล้มเหลว
- tests ต้องแยก published cost, reserved budget และ observed usage อย่างชัดเจน
  ค่าจอง10เป็นนโยบายเผื่อที่เสนอ ไม่ใช่หลักฐานว่าต้นทุนจริงสูงสุด10
  429/418/backoff และข้อจำกัด shared-IP ข้ามprocessยังใช้กฎเดิม

## PostgreSQL และ transaction

### `market_candles`

Partition RANGE(open_at) รายเดือนUTC; ไม่มีDEFAULTpartition
PK(source,base,quote,timeframe,open_at) รวมpartitionkey กันซ้ำที่parentและchild
base/quoteใช้tiewtrade_unit_code; prices/volumeใช้tiewtrade_money_amountเดิม
sourceเป็นnamespaceกลาง `primary_spot` ไม่ใช้ชื่อvendorนอกvenues
close/exclusiveend/observed_atใช้TIMESTAMPTZ, finalityTEXTCHECK3ค่า
บันทึกingestion_generationและlast_checked_atเพื่อfenceและบอกเวลาของข้อมูล
เก็บ fetch_started_at เป็น TIMESTAMPTZ จาก DB ก่อน HTTP สำหรับ partial-observation refresh
CHECKช่วงเวลาตามinterval/หน่วยถูกต้องและOHLCสอดคล้อง ไม่สร้างfinancialrounding/rangeใหม่
INDEXตามPKรองรับseries/range; ไม่เพิ่มindexทุกcolumnหรือarchiveสำเนาแต่ละpoll

Migrationสร้างเดือนย้อนหลังครอบ365วันและล่วงหน้า12เดือนจากmigrationtimeUTC
runtimeไม่มีCREATE/ALTER/DROPหรือSECURITY DEFINER DDL
ถ้าpartitionที่ต้องใช้ไม่มี: failfixedcodePARTITION_UNAVAILABLE ไม่ตกDEFAULT/เขียนตารางอื่น
การสร้างเพิ่ม/ลบemptypartitionsผ่านmigratorในschema maintenance/migrationเท่านั้น
scheduledpartitionmaintenanceก่อนdeployเป็นF-31แบบเดียวกับaudit; ไม่ยกสิทธิ์DDLให้worker
Downgradeปฏิเสธเมื่อมีcandle/demandrowsเพื่อไม่ลบข้อมูลเงียบ ๆ; ทดสอบrollback/emptydowngrade

### `market_candle_demand`

หนึ่งแถวต่อsource/base/quote/timeframe (PK): desiredwindow, leasedwindow,
status(PENDING/RUNNING/COMPLETE/UNAVAILABLE/FAILED), cursor, generationBIGINT,
worker/token/lease_until, fetch_unit_id, attemptcount, next_attempt_at, checked_at, fixedfailurecode
เพิ่ม phase(FORWARD/REPAIR/REFRESH), repair_pass(0..2), repair_cursor และ active_fetch_window
เป็น metadata ของ worker; API ไม่มีสิทธิ์แก้ fields เหล่านี้
เก็บ refresh_requested_at ใน request columns เป็นเวลาสูงสุดของคำขอ refresh ที่รับไว้
และ refresh_as_of/refresh_cursor ใน worker columns เป็น snapshot ของรอบที่กำลังทำ
เพิ่ม refresh_served_at ใน worker columns เป็น watermark ของคำขอที่ตรวจและตอบสนองแล้ว
ทั้งสามเวลาใช้ DB time; API ใช้ greatest กับ refresh_requested_at ไม่เขียนเวลาย้อนกลับ
เพื่อ freeze ขอบเขตแต่ละรอบ ขณะยังเก็บคำขอใหม่ไว้ทำต่อหลัง restart
ไม่มีuser_id/email/key/secret เพราะเป็นงานข้อมูลตลาดร่วมที่ไม่มีข้อมูลผู้ใช้

APIขอwindowแล้วcoalesceunionเฉพาะภายใน365วัน; ไม่สร้างแถว/jobทุกrequest
ถ้าRUNNING: เปลี่ยนdesiredwindowได้แต่ไม่เปลี่ยนleasedwindow/tokenหรือขโมยงาน
งานเดิมcommitleasedwindowก่อนแล้วตรวจdesiredwindowที่ขยายเพื่อทำต่อ

market-data claimด้วยFOR UPDATE SKIP LOCKED แล้วcommitก่อนHTTP
claimเพิ่มgenerationและให้lease120s; หลังtimeout/crash workerใหม่claimexpiredleaseได้
fencedwriteล็อกdemandrow ตรวจtoken/generation/leaseยังไม่หมดด้วยDBtime แล้ว
upsertpage + cursor/checkedstateในtransactionเดียว มิฉะนั้นrollbackทั้งpage
ผลของworkerเก่าที่กลับมาช้าเขียนข้อมูล/coverageไม่ได้ ไม่downgradeCLOSEDเป็นUNCONFIRMED
rowfinalityต่างกันต้องทดสอบprecedence; conflictingsameversionต้องfailไม่เลือกตามluck

### Sessions/grants

เพิ่ม `MarketDataSession`/`market_data_session` ในinfra/db/session.py โดยreuse_begin/_assert_role
ตรวจexactMARKET_DATA/non-superuser/non-bypassก่อนใช้; แยกชนิดจากUser/ScanSession
APIใช้UserSessionเดิมสำหรับauthenticatedread/enqueue

API: SELECTcandles; SELECTdemandและINSERT/UPDATEเฉพาะdesiredwindow/requestcolumns
ไม่มีสิทธิ์claim/failure/generation/writeOHLC/deletecandles
market-data: SELECT/INSERT/UPDATE/DELETEcandles และควบคุมdemandเฉพาะข้อมูลตลาด
rolesอื่นไม่เพิ่มสิทธิ์credentials/users/audit/orders; ไม่เปลี่ยนRLSของผู้ใช้
ไม่มีRLSบนสองตารางpublicmarketdataนี้; GRANTsแยกparent/childอย่างเจาะจง
metadataตารางdemandเป็นส่วนควบคุมingestionตามRQ12/16 ไม่ให้งานAPIเขียนราคาเอง

## API และขอบเขตงาน

- GET `/market-data/candles`: base/quote,timeframe,start/endคู่กัน(optional),limit1..1000
  defaultเป็นinitialwindow=min(1000intervals,365วัน)ถึงas_ofUTC
  readwindowต้องไม่เกิน1000intervalsและไม่ออกนอกretention; otherwisefixed422
  ตอบrowsเรียงopen_atascending, requested/observedrange, observed_at,
  coverage(PRESENT/INCOMPLETE/UNAVAILABLE), gaps, finalityของแต่ละแท่ง
  และ last_checked_at/refresh_pending เพื่อแสดง observation เดิมระหว่างรอ refresh
  PRESENTยืนยันpresenceเฉพาะreadwindow ไม่ยืนยันCLOSEDหรือsourcecoverageนอกwindow
  GETไม่มีsideeffect/enqueue; emptyไม่แปลว่าpre-listingหรือไม่มีการเทรดโดยอัตโนมัติ
- POST `/market-data/candles/requests`: `{base,quote,timeframe,start,end}`;
  ไม่มีrange=initialwindow; rangeสูงสุด365วัน; inputextra forbid
  enqueue/coalesceจากข้อมูลที่ขาดหรือแท่งที่เข้าเกณฑ์ refresh ด้านล่าง:202accepted/existingrequest
  คืน200เมื่อมีข้อมูลครบwindowและไม่มี refresh ที่ถึงกำหนดหรือค้างอยู่ในช่วงที่ขอเท่านั้น
  coverage PRESENT ยังเป็นจริงได้ระหว่าง refresh_pending โดยไม่สื่อว่าได้ observation ใหม่แล้ว
  failed/unavailableretryทำได้หลังnext_attempt_at ไม่resetbackoffจากrequestซ้ำ
  ไม่รับworker/token/source arbitraryจากผู้ใช้
- สองroutesauthenticated/nonrenew/nonreverify; POSTผ่านCSRFตามmiddlewareเดิม
  ไม่มีfreshTOTPหรือrecoverygate เพราะไม่แตะเงิน/credential
- fixederrors: INPUT_REJECTED, UNSUPPORTED_SERIES, RANGE_OUTSIDE_RETENTION,
  WINDOW_TOO_LARGE, HISTORY_UNAVAILABLE, PARTITION_UNAVAILABLE, SOURCE_FAILURE
  ไม่คืนrawresponse/SQL/DSN; OpenAPI/generatedfrontendtypesสร้างอัตโนมัติ

## Ingestion/retry/retention

Startupworkerseedinitialdemandของ5x6seriesแบบidempotent ไม่โหลด365วันทั้งหมด
หนึ่งprocessใช้source/guard/clientร่วม; mainวนทุก30s timeout10sต่อHTTP
run_roundสูงสุด4pages/roundโดยเลือกseriesอย่างfair; limit1000/pageและexplicittimebounds
lease120sมากกว่าHTTPbudget40s; ไม่holdtransactionขณะรอHTTP/sleep

Paginationเดินจากrequestedstart/lastreturnedopen+interval ใช้half-openmappingข้างต้น
ตรวจno-progress/out-of-window/duplicate/out-of-orderก่อนcommit; ไม่loopจนจบ365วันในroundเดียว
missingภายในpageคงเป็นgap ไม่fill0; empty/shortresponseไม่ยืนยันwholewindowครบ
เก็บcursor/coverageที่ตรวจแล้วสำหรับrestart; ก่อนสรุปว่า gap ซ่อมไม่ได้ต้องผ่านขั้นตอนด้านล่าง
ทุกrequestอยู่ในretentioncutoffของDBtime; jobที่ค้างจนข้อมูลหมดอายุไม่ดึงนอกcutoff

### Refresh แท่งที่เคยอ่านก่อนสิ้น interval (RQ-6/7/15/16)

- ใช้ last_checked_at เป็นเวลา DB ที่บันทึกเมื่อรับ observation สำเร็จ โดยเก็บ
  fetch_started_at จาก DB ก่อน HTTP ด้วย เพื่อแยกคำขอที่เริ่มก่อน end_at
  แม้ response จะมาถึงหลัง end_at; เก็บ fetch_started_at คู่กับ observation ใน transaction เดียวกัน
  เวลาเหล่านี้บอกความใหม่ของการอ่าน ไม่ใช่หลักฐาน CLOSED
- POST ตรวจแท่งที่มีอยู่ใน requestedwindow และ finality ไม่ใช่ CLOSED:
  ถ้า observation ล่าสุดเริ่ม fetch ก่อน end_at ให้ refresh เมื่อ request time >= end_at
  หรือเมื่อยังอยู่ใน interval แต่ last_checked_at ผ่านมาอย่างน้อย30s
  ใช้ DB time และ source/job next_attempt_at เดิม; คำขอก่อน30sคืน observation เดิมพร้อมเวลา
  ไม่มีการ polling อัตโนมัติทุกแท่งเพียงเพราะเป็น UNCONFIRMED
- freeze refresh_as_of จากเวลา POST ที่ claim แล้ว; เลือกเฉพาะแท่งที่เข้าเกณฑ์ ณ เวลานั้น
  และยังไม่ได้รับ observation ที่เริ่ม fetch หลัง refresh_as_of
  สแกนไม่เกิน1,000 slots ต่อหน้าและ fetch เฉพาะ contiguous eligible ranges
  หลัง FORWARD/REPAIR ให้ทำ REFRESH สำหรับข้อมูลที่มีอยู่ แม้บาง gap จะซ่อมไม่สำเร็จ
  ทำหนึ่ง sweep ต่อคำขอที่ coalesce แล้ว ไม่เริ่ม sweep ใหม่ตามเวลาที่ผ่านระหว่างทำงาน
- POST ระหว่าง PENDING/RUNNING ไม่เลื่อน refresh_as_of หรือ reset cursor/attempt/backoff
  แต่ถ้าคำขอใหม่เข้าเกณฑ์ refresh ที่ observation ปัจจุบันยังตอบสนองไม่ได้ ให้บันทึก
  refresh_requested_at=max(ค่าเดิม, เวลา POST จาก DB) ใน demand แถวเดิมและคืน202
  รวมคำขอซ้ำด้วย watermark ไม่สร้างงานหนึ่งแถวต่อ POST; window ที่ขยายเก็บเป็น desired work ถัดไป
  การมองว่าเป็นช่วงเดียวกันอย่างเดียวห้ามทำให้ทิ้งคำขอที่เกิดหลัง end_at หรือหลังเกณฑ์30s
- เมื่อจบ active sweep ให้ตรวจ observation ที่ commit แล้วกับ refresh_as_of ของรอบนั้น
  และบันทึก refresh_served_at เฉพาะ watermark ที่ตอบสนองสำเร็จจริง
  หาก refresh_requested_at ใหม่กว่า ให้เก็บงาน follow-up ในแถวเดิม ไม่ประกาศ COMPLETE
  รอบถัดไป freeze refresh_as_of จาก watermark ล่าสุด แล้วตรวจ eligibility อีกครั้ง:
  ถ้า observation ที่มีอยู่ตอบสนองคำขอนั้นแล้วให้ advance served watermark โดยไม่ HTTP;
  ถ้ายังไม่ตอบสนองให้ fetch เฉพาะแท่งที่ต้อง refresh ด้วย bounded sweep เดิม
  ไม่เริ่ม follow-up เพราะนาฬิกาเดินเอง และไม่ reset งบ gap repair ที่ทำไปแล้ว
- POST และการจบรอบต้อง serialize ด้วย demand row lock เดียวกัน:
  การบันทึก served watermark/status ต้องตรวจ requested watermark และ desiredwindow ล่าสุด
  ใน transaction เดียวกัน ห้ามเขียนทับ requested watermark ด้วย snapshot เก่า
  ถ้า POST commit ก่อน completion ต้องเหลือ follow-up; ถ้า completion commit ก่อน
  POST ต้องเห็นสถานะล่าสุดและ enqueue คำขอที่ยังไม่ถูกตอบสนองได้
- refresh_requested_at/served_at/as_of/cursor/active_fetch_window ต้อง durable
  และใช้ lease/token/generation fence เดิม; reclaim/restart ไม่ทิ้ง pending watermark
  failed refresh ไม่ advance served watermark และคำขอใหม่ห้ามลด retry/backoff/eligibility120s
  งาน follow-up ใช้งบรวม4pages/roundและ fair selection เดิม ไม่วนทำทุก sweep ใน round เดียว
- observation ใหม่ที่ผ่านการตรวจแทน OHLCV เดิมแบบ atomic พร้อม timestamps/progress
  ยังคง UNCONFIRMED สำหรับ REST และไม่ downgrade CLOSED; worker เก่าเขียนทับไม่ได้
  valid response ที่ขาดแท่งเป้าหมายต้องไม่ลบแถวเดิมหรืออัปเดต last_checked_at ให้ดูใหม่
  retry active fetch unit เดิมตามงบ3attempts/30s/60s ด้านล่าง แล้ว FAILED+120s
  partial response บันทึกแท่งที่ได้รับได้ แต่ไม่เลื่อน refresh_cursor หรือสร้าง unit ใหม่
  จนเป้าหมายของ unit ครบ; retry ช่วงเดิมและ upsert อย่าง idempotent
  permanent/protocol failure หยุดตาม policy เดิม; GET คืนแถวเดิมพร้อมสถานะ refresh ล้มเหลว
- หลัง fetch ที่เริ่มเมื่อหรือหลัง end_at สำเร็จ แท่งนั้นไม่เข้าเกณฑ์ partial-observation refresh อีก
  แต่ยัง UNCONFIRMED; ไม่รับรองว่า upstream จะไม่แก้ย้อนหลังในอนาคต
  หากไม่มี POST ใหม่จะไม่มีคำรับรอง freshness หรือการอ่านซ้ำอัตโนมัติใน F-09
  การรับข้อมูลต่อเนื่องเป็น F-10; policy นี้แก้การอ่านประวัติซ้ำแล้วติดค่า partial เดิม
- COMPLETE ของ demand ต้องผ่านทั้ง coverage และ refresh ที่ถึงกำหนดในรอบนั้น
  รวมถึงไม่มี requested watermark ใหม่ที่ยังไม่ได้ตรวจตอบสนอง
  ถ้า refresh ล้มเป็น FAILED; ถ้า refresh สำเร็จแต่ gap ยังเหลือเป็น UNAVAILABLE;
  PRESENT ของ coverage ไม่เปลี่ยนตาม refresh failure และไม่เท่ากับ finality/freshness
  ตัดข้อมูลที่หมด retention ก่อนเลือกงานและก่อน commit ตามกฎเดิม

### การซ่อม gap หลัง forward pass (RQ-10/16)

- เมื่อ forward pass ถึงปลาย leasedwindow ให้ตรวจ expected open-time slots เทียบกับ
  แถวที่ commit แล้วใน window นั้น หากยังขาดให้เข้าสู่ REPAIR อัตโนมัติ
  ไม่ต้องรอ POST ใหม่ และไม่ประกาศ COMPLETE เพียงเพราะ cursor ถึงปลายช่วง
- ตรวจช่วงทีละไม่เกิน1,000 slots ตามลำดับเวลา; เลือก contiguous missing subrange
  แรกจาก repair_cursor เป็น active_fetch_window และ fetch เฉพาะช่วงที่ขาด
  ไม่เก็บรายการ gap ของ365วันทั้งหมดในแถว demand หรือโหลดทั้งหมดเข้าหน่วยความจำ
  gap ที่อยู่ก่อน forward cursor จึงถูกตรวจซ้ำได้ รวมทั้ง leading/interior/trailing gap
- ทำ repair sweep สูงสุด2รอบหลัง forward pass: รอบแรกเริ่มหลัง30s และรอบสอง
  หลังจบรอบแรก60s ใช้ next_attempt_at และ source backoff เดิม โดยเลือกเวลาที่ช้ากว่า
  ทุก fetch รวมอยู่ในงบ4pages/round และ fair selection เดิม ไม่เพิ่ม loop นอกงบ
- แต่ละคำตอบที่ valid ให้ upsert + เลื่อน repair_cursor ไปปลาย active_fetch_window
  + บันทึก phase/pass ใน fenced transaction เดียวกัน แม้ valid response ยังว่าง/ขาด
  เพื่อให้รอบนั้นเดินไปตรวจ gap อื่นได้; เมื่อจบ sweep ให้ตรวจ coverage จาก DB อีกครั้ง
  ถ้ายังขาดและเหลือรอบ ให้เริ่ม repair_cursor ใหม่ที่ต้น leasedwindow ที่ยังไม่หมด retention
  ข้อมูลที่มีครบแล้วต้องไม่ถูก fetch ซ้ำเพื่อการซ่อม gap
- HTTP transient ใช้ retry policy ด้านล่างกับ active_fetch_window เดิม;
  failure ไม่เลื่อน cursor และไม่ถือเป็น successful repair observation
  หมด HTTP attempts เป็น FAILED; malformed/permanent failure ไม่วน repair ต่ออัตโนมัติ
  valid response ที่ยังมี gap จบ fetch unit นี้และเลื่อน repair_cursor ตามกฎข้างต้น
  การกลับมาตรวจ gap เดิมต้องอยู่ใน repair sweep ถัดไปเท่านั้น ไม่เปิด unit ใหม่ซ้ำทันที
- phase, repair_pass, repair_cursor, active_fetch_window, attemptcount และ next_attempt_at
  ต้อง durable และไม่ reset เมื่อ lease ถูก reclaim/restart หรือมี POST ซ้ำ
  worker ใหม่รับช่วงเดิมด้วย token/generation ใหม่; worker เก่าแก้ progress ไม่ได้
  การขยาย desiredwindow ระหว่างทำงานไม่เปลี่ยน leasedwindow หรือเริ่ม repair budget ใหม่
  ส่วนที่ขยายทำต่อหลัง window เดิมจบตามขั้นตอน coalescing เดิม
- COMPLETE ใช้ได้เมื่อทุก expected slot ของ window ที่ยังอยู่ใน retention มีแถวที่ commit แล้ว
  ครบและ refresh ที่ถึงกำหนดสำเร็จเท่านั้น; ถ้าจบ2 repair sweeps แล้วยังขาด ให้บันทึกผล gap เป็น UNAVAILABLE พร้อม checked_at,
  gap ที่ยังขาด และเหตุผล GAP_REPAIR_EXHAUSTED โดยไม่อ้างว่าไม่มีข้อมูลถาวรหรือเป็นก่อน listing
  คำขอใหม่หลัง eligibility120s จึงเริ่ม repair cycle ใหม่จาก gap ที่ยังเหลือได้
  POST ซ้ำก่อนเวลานั้น/startup/restart ต้องไม่ลดเวลารอหรือ reset budget
  coverage ของช่วงย่อยที่มีครบยังเป็น PRESENT ได้; finality ไม่เปลี่ยนจากการซ่อมสำเร็จ
- ทุก sweep ตัดช่วงที่หมด retention ด้วย DB time เดิม; ไม่ดึงข้อมูลที่หมดอายุ
  หรือรายงาน expired slots เป็น gap ที่ต้องซ่อม

### หน่วยนับ retry และการ reset (RQ-15/16)

- `fetch unit` คือหนึ่งหน้า/ช่วงย่อยที่ worker เลือกดึงผ่าน CandleSource
  ระบุด้วย fetch_unit_id, phase และ active_fetch_window ที่ freeze ไว้ พร้อม limit<=1000
  attemptcount นับการเริ่มเรียก source ของ unit นี้ รวมครั้งแรก สูงสุด3ครั้ง
  ไม่ได้นับรวมทั้ง leasedwindow, จำนวนหน้าทั้ง job, จำนวน lease หรือจำนวน repair sweeps
- ก่อนแต่ละ call ให้ตรวจ token/lease/next_attempt_at แล้วเพิ่ม attemptcount และ commit
  ใน transaction สั้นก่อน HTTP; ไม่ hold transaction ระหว่าง network
  หาก crash หลังจอง attempt แต่ไม่ทราบว่าเรียกสำเร็จหรือยัง ให้ถือว่า attempt นั้นใช้ไปแล้ว
  reclaim/restart ใช้ unit และ count เดิม; ถ้าครบ3และไม่มีผลสำเร็จที่ commit ให้ FAILED
  ไม่ชดเชย attempt จากการเดาว่า HTTP อาจยังไม่ได้ส่ง
- หลัง attempt1 ล้มแบบ transient รอ30s; หลัง attempt2 รอ60s;
  attempt3 ยังไม่สำเร็จเป็น FAILED และ eligible อีกครั้งหลัง120s
  transient/timeout และ refresh response ที่ยังขาดเป้าหมายใช้ count เดียวกัน
  malformed/permanent failure หยุดทันที ไม่มี automatic retry
- เมื่อ unit สำเร็จ ให้ commit rows/progress และปิด unit แบบ atomic
  เมื่อเลือกหน้าหรือช่วงย่อยถัดไปจึงสร้าง fetch_unit_id ใหม่และเริ่ม count0
  ดังนั้น job ที่มีมากกว่า3หน้าสำเร็จได้ และความล้มเหลวในหน้าหลังมีงบของหน้านั้น
  ผลสำเร็จของ FORWARD/REPAIR หมายถึง valid response ที่ประมวลผลและเลื่อน cursor
  ตามกฎ phase แล้ว ไม่ใช่การยืนยันว่า coverage ครบ; REFRESH ต้องได้เป้าหมายของ unit ครบ
- valid empty/partial ใน REPAIR เดิน cursor ต่อและคง gap ไว้ตามกฎ2sweepsเดิม
  sweep ถัดไปสร้าง unit ใหม่เมื่อถึง gap นั้นได้ แต่ห้าม reset repair_pass
  ส่วน partial REFRESH คง unit/count เดิมจนได้เป้าหมายครบหรือหมด attempts
  ไม่สร้าง unit ใหม่จาก retry, lease renewal/reclaim, POST ซ้ำ, desiredwindow ขยาย
  หรือการเลื่อน retention cutoff; การตัด expired slots คง count ของ unit ที่เหลือ
- explicit request หลัง FAILED และผ่าน eligibility เริ่ม retry cycle ใหม่ของงานค้างได้
  โดยตั้ง count0 ภายใต้ row lock แต่คง cursor/repair_pass/refresh progress ที่ commit แล้ว
  generation ที่เพิ่มเพื่อ reclaim เป็นเพียง fence ไม่ใช่สิทธิ์ reset budget
  การเริ่ม gap cycle ใหม่หลัง UNAVAILABLE ใช้กฎ exhaustion120s ในหัวข้อ gap repair
- ทุก attempt รวมในงบ4pages/roundเดิม; การเปลี่ยน unit/phase ไม่ลด source backoff
  429/418 หยุด round ทันทีและ persist next_attempt_at ทุก series ใน source เดียวกัน
  ด้วย greatest(next_attempt_at, blocked_until); API/startup/reclaim ห้ามลดเวลานี้
  รอ max(backoff,Retry-After); ถ้าไม่มี Retry-After ใช้ unknown-retry metadata และ120s
  การจอง attempt ที่เจอ local rate-limit ก่อน HTTP ก็นับอย่าง conservative ตามกฎก่อน call
  ไม่มี sleep/HTTP retry ใน transport และไม่อ้างว่า retry สำเร็จพิสูจน์ history/finality/tariff

Cleanupแต่ละroundลบexpiredcandlesแบบbounded10,000rowsด้วยmarket-dataDMLเท่านั้น
APIread/POSTwindowclampปฏิเสธข้อมูลเกิน365วันแม้cleanupยังทำไม่ทัน
ไม่droppartition/runtimeDDL ไม่ล้างcredentials/throttles/audit/user tables
scheduler/deploymentserviceของworkerเป็นF-31; F-09รันด้วยมือแบบengineและมี--onceสำหรับทดสอบ

## Tasks (TDD / หยุดก่อนcodeจนกว่าplan+validationApproved)

### 1. Puretypesและvenuecontract (RQ1–6/15/18)
- [x] เพิ่มtests `tests/core/test_market_data.py`, `tests/venues/test_candles.py`
  สำหรับunits/timeframe/half-open/unknownfinality/decimal/gaps; รันให้แดง
- [x] ทำcore/market_data.py และvenues/candles.pyตามinterfacesด้านบน
- [x] ขยายFakeVenueสำหรับcandlepages/recordedcalls/errors; ไม่มีnetworkในfake
- [x] รัน `.venv/bin/pytest tests/core/test_market_data.py tests/venues/test_candles.py`

### 2. ตัวเชื่อมสาธารณะ (RQ1–6/9/15/18)
- [x] fixtures17ชุดคัดเฉพาะที่testsใช้ไป `tests/venues/binance_th/fixtures/`
  เขียนtests `test_candles.py` shape/6intervals/SITEGLOBAL/bounds/costheaders/errorsก่อนadapter
- [x] เพิ่มKLINESในEndpoint และcandlesadapter/factoryผ่านtransportเดิม
  ไม่มีAPIkey/TIMEที่ไม่ได้ใช้ ไม่มีtransportHTTPretry
- [x] เพิ่ม tests ใน `tests/venues/binance_th/test_rate_limit.py` สำหรับ reservation floor
  และ factory wiring; ใช้ accounting helpers เดิม ไม่เปลี่ยน CallCost contract
- [x] ปรับendpoint-boundary gateยกเว้นเฉพาะcompositionHTTPclientของmarket_datamain
  ตามengine pattern ไม่เปิดnetworkimportsทั่วservices; ใส่negativefixtureพิสูจน์gate
- [x] รัน `.venv/bin/pytest tests/venues tests/gates` รวมregressionadapterเดิม

### 3. Storage/migration/claims (RQ5/7–14/16/17)
- [x] tests `tests/infra/market_data/{test_storage,test_claims,test_permissions,test_retention}.py`
  actualrolegrants/childpartitions/fence/coalescing/expiry/cutoff/rollback ให้แดงก่อนschema
- [x] เพิ่มmigration0013, MarketDataSession, infrarecords/storage/claims
  ไม่แก้auditprotectionหรือเพิ่มruntimeDDLprivileges
- [x] migrationtests emptyupgrade/downgrade, populatedrefusal, partitionmissing,
  distinctUTCmonthsและinvaliddirectDBwritesตามconstraints
- [x] รัน `.venv/bin/pytest tests/infra/market_data tests/infra/db`
  ใช้disposableDBที่bootstraproles/eventtrigger ไม่ใช้DBเดิมหรือDBpreview

### 4. WorkerและAPI (RQ7–18)
- [x] `tests/services/market_data/test_ingestion.py` FakeVenue+actualDB:
  request→claim→page→commit→read,4pagebudget,partialfailure/restart/oldworkerlatereply
  และ forward ข้าม gap → repair เติมจริง/หมดงบ → restart/coalescing ไม่ reset progress
  รวม POST ประวัติแท่ง partial เดิม → REFRESH → OHLCV ใหม่ commit โดยยัง UNCONFIRMED
- [x] `tests/api/test_candle_routes.py` auth/CSRF/nonrenew/inputbounds,
  emptycoverage/coalesced202/complete200/noTOTP/crossuserpublicdataไม่รั่วprivateidentity
- [x] ทำingestion/main/candle_routes/router/routing rulesตามแผน
  CLIประกอบruntimeไม่รู้ชื่อvendor และFakeVenue injectionในtests
- [x] readonlyGET+explicitPOSTผ่านAPIจริงในdisposablebrowserE2E
  `frontend/e2e/market-data.spec.ts`; เรียกworkerจริงกับFakeVenueแบบF-07 ไม่สร้างUIใหม่
- [x] regenerate `.venv/bin/python -m tiewtrade.services.api.openapi_export`
  และ `npm run gen:api` แล้วตรวจbyteidenticalรอบสอง

### 5. ตรวจสุดท้าย/เอกสาร (ทุกRQ)
- [x] backend `.venv/bin/ruff check .`, `ruff format --check .`, `mypy`, `lint-imports`, `pytest`
- [x] frontend `npm run lint`, `npm run typecheck`, `npm test`, `npm run build`, `npm run test:e2e`
- [x] DockerLinux/APIhealth/UIproxyhealth และCLI--once smokeกับFakeVenue/disposableDB
  ไม่เรียกproductionmarket/ใช้keyจริงเป็นส่วนmergegate
- [x] รีวิวrequirement/validationmapping, schema/grants, concurrency และretry/finalitylimitations
- [x] บันทึกผลในvalidation/reviewaudit/README และอัปเดตroadmapตามจริง
  ไม่commit/push/mergeเอง ไม่เพิ่มdeployautomationหรือF-10/F-11/F-12ในงานนี้

## การตัดสินทางเทคนิคที่ขออนุมัติพร้อมแผน

1. RESTทั้งหมดUNCONFIRMED จนsourceมีclosureproof; coverageไม่เท่ากับfinality
2. คง published CallCost ของ klines=1 และใช้ IpWeightLimiter reservation floor10
   เฉพาะ candle-source factory พร้อมheaderobserver/backoff; defaultของfactoryเดิมคงเดิม
   ไม่แก้tariffตลาดหรืออ้างว่านับquotaข้ามprocessครบแล้ว
3. APIrequestmetadataผ่านPG, generation/leasefence, boundedworker/retryconstantsข้างต้น
4. partitionสร้างด้วยmigration ไม่ให้runtimeDDL; cleanup365วันเป็นboundedDML

ทั้งสี่ข้อไม่มีการimplementก่อนอนุมัติ และไม่เปลี่ยนข้อกำหนดการเทรด/precisionเดิม
