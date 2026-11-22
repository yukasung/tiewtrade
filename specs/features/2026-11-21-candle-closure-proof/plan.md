# Shared Candle Closure Proof — Plan

สถานะ: **Approved - owner replied approve2026-11-21; implementation authorized within this plan**
วันที่: 2026-11-21 (Asia/Bangkok)
ฐาน: CP-01–CP-16 Approved; branch `feature/candle-closure-proof`

## 1. ผลลัพธ์และขอบเขต

รับ native close event ของ Binance TH ที่ x=true เป็น candidate ตรวจเทียบ canonical
REST รุ่นที่ request เริ่มหลัง end_at และ identity/OHLCV ตรงกัน จึงสร้าง durable proof
และประกาศ CLOSED ใน transaction เดียว ไม่มี inference จาก clock/REST/ATR อย่างเดียว

โค้ด REST adapter และ stream preview ยังคงให้ original finality/hint ตามเดิม
เพิ่ม verifier ระหว่าง public-source ingest กับ canonical publication ไม่ย้ายการยืนยัน
เข้า strategy/browser/indicator ไม่มีสูตร ATR, sizing, PnL, fees หรือ execution ใหม่
Paper Test Entry และ RSI ยังคง require CLOSED และผ่าน common guards เดิม

## 2. Dependency และ candidate

- Worktree ปัจจุบันมีฐาน local F-21 e811800; Paper Test Entry candidate อยู่ใน worktree
  แยกพร้อม migration0075 และ diagnostic/UI fixes ล่าสุด ยังไม่ถือว่า merged/ผ่าน required CI
- ก่อน source edits ให้ materialize/rebase local dependency candidate ที่รวม F-21/Paper
  ที่ได้รับอนุมัติไว้แล้วอย่าง reviewable บันทึก base SHA และ content fingerprint รักษา WIP/index
  เดิม ไม่ reset/copy ทับ source worktree และไม่ publish snapshot แทน final reviewed commit
- ตรวจ diff ของ dependency กับแผนนี้ก่อนแก้ ส่วนที่ไม่กระทบใช้หลักฐานเดิมต่อ ไม่รีวิวทั้ง repo ซ้ำ
- ใช้ migration0076 หลัง0075 เมื่อ dependency base พร้อม; หาก upstream ใช้เลขนี้แล้ว ให้เลือก
  revision ถัดไปและบันทึกก่อนสร้าง migration ไม่สร้าง conflicting Alembic heads เงียบ ๆ
- Required CI และ owner acceptance ต้องตรวจบน combined final candidate เดียวกันก่อน merge

## 3. ของเดิมที่ใช้ซ้ำ

| Path / function | ใช้อย่างไร |
|---|---|
| `core/candle_preview.py::CandleObservation, compare` | native typed observation และ partial-order/duplicate/conflict rules |
| `core/market_data.py`, `core/timeframes.py` | native identity, inclusive-end normalization, calendar alignment/retention |
| `core/money/::Money, Quantity` | exact OHLCV equality ไม่เพิ่ม tolerance/rounding หรือ raw float/Decimal |
| `venues/binance_th/candle_stream_mapping.py`, `candle_feed.py`, `stream_transport.py` | strict payload/subscription/connection generation; ไม่ต่อ stream ต่อ user |
| `services/market_data/candle_realtime.py::CandleSupervisor` | observe/flush/connection/catalog fencing; เพิ่ม candidate capture จาก native event |
| `infra/market_data/candle_preview.py::fence, enqueue_ended` | feed lease/epoch checks และ refresh coalescing |
| `infra/market_data/storage.py::coalesce_demand, refresh_due` | request-after-end semantics; ไม่สร้าง REST polling framework ใหม่ |
| `services/market_data/ingestion.py::_apply_page, run_round` | existing request/claim/backoff/rate-limit path; ไม่มี HTTP ใน DB transaction |
| `infra/market_data/claims.py::write_candles, lock_claim` | canonical row/claim locking และ correction inspection ก่อน skip/upsert เดิม |
| `infra/indicators/source.py::begin_source_write, PROOF_SQL` | source scope ก่อน row locks, revision journal และ consumer invalidation |
| `infra/bots/inputs.py::require_current_indicators, require_current_candle` | commit-time proof checks; version/fingerprint เป็น server-derived |
| `infra/bots/authority.py::_queued_signal_current` | queued BUY revalidation; lost proof/correction ห้ามผ่าน |
| `infra/indicators/rollout.py`, `infra/platform/storage.py` | inventory/explicit attestation และ heartbeat patterns สำหรับ compatible deployment |

## 4. โครงสร้างที่เพิ่มให้น้อยที่สุด

- `core/candle_closure.py`: immutable typed candidate/result และ pure exact-match decision
  ใช้ CandleObservation/Money/Quantity/native-time helpers ไม่มี network/SQL/persistent cache
- `infra/market_data/candle_closure.py`: persistence, protocol/fence checks และ verifier
  เรียกผ่าน MarketDataSession ตาม architecture ไม่ import venues/services/strategies
- migration: public source evidence, append-only resolution records, bounded mutable work/status
  projection และ singleton protocol control version1/default OFF ใน PostgreSQL เดิม
  ไม่มี Redis/service/storage ใหม่ และไม่สร้าง generic proof/worker plugin framework

Evidence เก็บ native series identity, OHLCV, actual closed_hint, progress IDs/count, event/receive
เวลา, writer lease/epoch, digest และข้อมูล normalized ที่ reconstruct ได้; ไม่เก็บ digest อย่างเดียว
Resolution ผูก observation กับ canonical fingerprint/request times/source fence/policyversion
พร้อม MATCHED/CONFLICT/INVALIDATED outcome แบบ append-only; projection เก็บ pending/due/state

ยึด unique logical candle/policy/observation fingerprint สำหรับ dedup ไม่ใช้ arrival timestamp
เป็น price authority. Public data ไม่มี user/session credential จึงใช้ public-market role grants
ไม่เพิ่ม owner RLS ปลอม; API/engine/indicator-builder อ่านได้เฉพาะคอลัมน์ที่จำเป็น เขียนไม่ได้
market-data เขียนเฉพาะ public-source/proof paths ไม่มีสิทธิ์ข้อมูลบัญชี/secret

Accepted proof เก็บ native/canonical snapshot ที่ตรวจย้อนหลังได้แม้ history partitionหมด retention
ไม่ใช้ FK ที่บังคับเก็บ market_candles partition ตลอดชีวิต ledger; ใช้ FK ภายใน evidence/resolution,
checks/unique และ transactional canonical validation. Proof ที่อ้าง candle ซึ่งไม่มีแล้วใช้เปิด tradeไม่ได้
ห้ามลบ evidence ที่ยังถูก pin ใน decision/audit; cleanup ใช้ retention policy เดิมและตรวจ reference

## 5. Flow และ transaction

### 5.1 Native event → durable candidate

- ตรวจ strict adapter/series/market identity และ existing compare ก่อนรับ ไม่เชื่อข้อมูลจาก client
- Capture เฉพาะ **native actual closed_hint=true** ก่อน sticky-preview hint transformation
  ห้ามใช้ hint ที่ carry จาก event เก่า หรือหมดเวลาแล้ว synthesize เป็น native proof
- FALSE→TRUE ที่ OHLCV/progress เท่าเดิมยังต้องบันทึก closure candidate แม้ compareเป็น DUPLICATE
  และต้องไม่ทำให้ duplicate price revisions เกิด BUY ซ้ำ; negative testsครอบคลุม E/arrival ordering
- Persist candidate ก่อน latest-series slot ถูกแท่ง B ทับ; ใช้ bounded pending buffer เป็น transient
  schedulingเท่านั้น ถ้า persist ไม่สำเร็จห้ามถือว่ารับ proofแล้ว; recoveryใช้DBไม่พึ่งself.rows
- ใน transaction ที่จะแตะ proof/canonical: begin_source_write ก่อน feed/candle/projection locks
  fence current lease/epoch/connection/subscription และ catalog ไม่มีการจับ source guardหลังrowlocks
- ถ้ามี canonical post-end observation ที่ตรงและยัง valid ใช้ verifier ได้ทันทีโดยไม่ยิง GETเพิ่ม
  มิฉะนั้น enqueue refresh ของแท่งนั้นผ่าน existing coalescing เดียวกับ F09/F11

### 5.2 REST → atomic verification/publication

- HTTP อยู่นอก transaction; ใช้ saved request-start timestamp ของ request ที่ให้ OHLC รุ่นนั้นจริง
- หลังตอบกลับ: source write scope → feed/source fence → claim → native candle row → evidence/state
  recheck epoch/claim/catalog/request bounds และ normalize exact numeric values ก่อนเขียน
- ตรวจ pending native proof กับ row/fingerprint ล่าสุด ไม่ใช้ REST จาก stale claim หรือ observationเก่า
- เมื่อ match: append accepted resolution และ promote canonical finality CLOSED พร้อม proof reference
  ใน transaction เดียว ให้ source triggers/journal invalidate indicator metadata ตามปกติ
- เมื่อ missing/mismatch: ไม่ promote; append durable resultเมื่อ evidence/stateเปลี่ยน และคง pending/
  conflict stateตามเหตุ ใช้ backoff/claim/availability deadline เดิม ไม่ retryทุกquoteหรือเพิ่ม grace window
- หาก transaction/ackล้ม: replay proofkey/claim/result เดิมได้ ไม่สร้าง closure opportunity/entryซ้ำ

### 5.3 Correction และ invalidation

`claims.write_candles` ปัจจุบันข้าม incoming UNCONFIRMED ถ้า canonicalเป็น CLOSED
ต้องตรวจ evidence contradiction **ก่อน** branchข้ามนั้น ไม่ทำให้ correctionหายไปเงียบ ๆ

- Conflicting closed event/REST ทำให้ append invalidation และ mark current proof non-tradable
  โดยใช้ source write lockก่อนทุกrowlock และเปลี่ยน revision/journalในtransactionเดียว
- เมื่อ proof ของ current CLOSED ถูกเพิกถอน: trusted verifier demote **finality** กลับ UNCONFIRMED
  อย่างมี invalidation evidence; ไม่เขียนเลือก OHLC ตัวที่ชอบ ไม่ลบ accepted history เดิม
  การ demote ใช้ dedicated verified path ไม่ให้ generic/old REST writer overwrite finalityเอง
- ใช้ F09 repair/source readiness เดิมจนมี accepted proof ชุดใหม่ครบ; RESTอย่างเดียวไม่ re-close
- Consumers จึงเห็น source revision/finalityใหม่ และต้องปฏิเสธ old prepared/queued BUY ตาม fences
  หาก fill commitก่อน invalidation ให้เก็บ ledgerจริง ไม่มีออเดอร์ย้อนหรือ TP/SL retargetของtest
- Invalidationหลังcommitต้องเห็นทุกinstance; transient buffers/Redis notification ไม่ใช่ authority

### 5.4 DB enforcement และ lock order

- Closure control read/fence และ `begin_source_write` ต้องมาก่อน feed/claim/canonical/state locks
  ยึด source/advisory ordering เดิมทั้ง ingest, proof verifier, correction และ cleanup
- ใช้ append-only guards, unique/FKs/checks และ runtime grants ตาม database standard
- canonical promotionต้องมี matching accepted proof reference/version ใน transactionเดียว;
  runtime direct UPDATE เป็น CLOSED โดยไม่มี proof ถูกปฏิเสธเมื่อ protocolเปิด
- invalidation/demotionต้องมี append-only invalidation reference; ทดสอบfaultทุกจุดสำคัญกับPGจริง
- ไม่มี REST await ภายใต้ source/row lock และไม่ขยาย DB deadlines เพียงเพราะ contention

## 6. Consumer และความสด

- Pure strategiesยัง reject non-CLOSED เหมือนเดิม ไม่มี UNCONFIRMED exception หรือสูตรใหม่
- Rebind F11 generation/source metadata ตาม journal: closure finalityเป็น source change ที่ต้อง
  พิสูจน์ prefix/checkpoint ใหม่ ใช้ bounded suffixที่เริ่มก่อนแท่งเปลี่ยน ไม่แค่แก้ finalityในcachedpoint
  ไม่เพิ่ม full-history scan ต่อ quote หรือขยาย preparation deadlineเดิมเพื่อกลบปัญหา
- ใส่ proof ID/policy version/canonical fingerprint ใน server-derived decision provenance
  และ recheckใน require_current_candle/_queued_signal_current ไม่เชื่อ booleanจากbrowser
- Preserve start/source-recovery cutoff และ exit-candle guards; same candleมีได้หนึ่งentry
  แม้ proof/revisionเปลี่ยน ถ้าสัญญาณ A ไม่ทันช่วง B/freshnessเดิมให้skip ไม่ backfill BUY
- Existing warm-upใช้ F11 NC31 ตามเดิม ส่วน signal candleต้องCLOSEDและ current proof valid
- API/graphอ่าน canonical finalityจริง ไม่ให้ preview overrideหลักฐาน และไม่คืนhidden UI copyที่เจ้าของลบ

## 7. Rollout/compatibility และการปิดกลับ

- Expand migrationโดย control OFF: old pathsยังทำงานเดิม ไม่มีpromoteย้อนหลัง ไม่มีauto-start
- Extend existing inventory/heartbeat **patterns** ด้วย closure-specific capability/version attestation
  เท่าที่จำเป็นในDBcontrol/activation tooling ไม่เปลี่ยน catalog protocol1เป็น2ทั้งระบบ
  ไม่สร้าง heartbeat infrastructureใหม่หรืออ้าง health endpointว่าเป็น compatibility proof
- ก่อนเปิด:หยุด/ยืนยันdrain old canonical writers และปิดrestartเก่า ตรวจprocess inventory,
  role/version/schema, source proof READY, source-trigger inventory และ consumer compatibility
  การเงียบskipของoldwriterตรวจจากrowtriggerไม่ได้ จึงไม่อนุญาตmixed legacywriterขณะเปิด
- Source-protocol guard/DBchecksปฏิเสธlegacy writesที่ไม่ประกาศ compatible source-write path
  consumerเก่าจะถือcompatibleได้เฉพาะมีtestsพิสูจน์ canonical/proof/invalidation invariantsครบ
  ไม่พบหลักฐานให้ปฏิเสธactivation แทนการสมมติว่าอ่าน CLOSEDได้จึงปลอดภัย
- Ownerอนุมัติแผนนี้อนุญาตสร้าง/เปิด **isolated owned Paper validation DB** หลัง pre-activation
  safety tests+source evidence+review ผ่าน เพื่อเก็บ Feature evidence ไม่มีcredentialเงินจริง
- Previewเจ้าของ15121ไม่ถูกเปลี่ยนขณะ research/implementation; หลังตรวจครบให้แจ้งcandidate/
  ผลกระทบและส่งowner acceptance checkpointก่อนเปลี่ยนactivationที่นั่น ไม่เริ่ม/หยุด/เปลี่ยนconfig
  ของเจ้าของแทนเอง การเปิด source อาจทำให้ runที่เคยStartไว้ซื้อเมื่อสัญญาณผ่าน ต้องแจ้งชัด
- ปิดกลับ:หยุดpublish CLOSEDใหม่/ปิดentry admissionตามexistingSTOP ก่อน drain incompatiblewriter
  เก็บaccepted history/evidence ห้าม downgradeทำลายข้อมูล; downgradeอนุญาตเฉพาะOFF+ไม่มีproofhistory
  ถ้ามีhistoryให้forward fix ไม่ DROP/แก้ledgerเพื่อทำให้rollbackผ่าน

## 8. ลำดับลงมือและขอบเขตตรวจ

1. P0 dependency/candidate inventory, schema/grants/source-lock analysis ยืนยันก่อน source changes
2. P1 pure verifier/codec และ migration OFF + real PG DB/security/rollback tests
3. P2 native capture/REST integration, correction/dedup/lease/recovery และ source guard regressions
4. P3 consumers/indicator tail/queued authority, default-off compatibility และ existing Paper/RSI regression
5. P4 actual source→proof→Paper campaignตาม validation.md ที่จำกัดไว้; no fake CLOSED promotion
6. P5 แจ้ง Ready for Code Review → reviewdiff/callers/security/stateless/financial → แก้/refactorเฉพาะที่จำเป็น
   → affected checks → ส่งcheckpointเดียว พร้อมowner/CI/Batch/Releaseค้างตามจริง
7. P6 owner acceptanceตามขอบเขตและrequired CIบนfinalcandidateก่อนpublication/mergeตามAGENTS

Localใช้targetedchecksก่อน ไม่รันfull suiteซ้ำทุกpatch ส่วนกลางนี้กระทบหลายระบบจึงต้องมี
full backend correctness/security/financial regressionบนcandidateที่นิ่งก่อนmerge ใช้requiredCI
ชุดเต็มตามconfigurationจริงเป็นหลักฐาน ไม่เลื่อนsafetyไปBatch. Scope/เวลาชุดยาวแจ้งก่อนรัน

## 9. จุดหยุด

- plan+validationต้องApprovedก่อนP0 materialization/source implementation
- หาก proof/source permissions, conflict repairหรือactivationต้องเปลี่ยนCPที่อนุมัติ ให้amendก่อนโค้ด
  เรื่องเงิน/Live/ผ่อนsafetyต้องให้เจ้าของตัดสินใจ ไม่ใช้engineeringdelegationข้าม
- เงื่อนไขเดิมแก้แล้วยังไม่ผ่าน3รอบหรือownerแจ้งใช้เวลามากไป ให้หยุดเสนอทางเลือก
- public campaignมีหนึ่งattemptตามvalidation;หากไม่ครบผลให้Partial/NotRun ไม่วนรอแท่งดีไม่จำกัด
- ไม่มีpublication/mergeจนowner Feature gates และrequiredCIครบ; Batch/Release pendingตามจริง

P0 dependency materialized locally: 46841d394f4fe23f94626114619ef0c4c66438d1 from approved Paper candidate working tree, original index/WIP/preview preserved. No publication. Planning stash 2033af9595fde1809d03e827e075b9d10af3a82c retained as backup.

## P1 engineering detail before persistence implementation

Use normalized immutable observations/results plus mutable per-candle state. Resolution
records form an append-only predecessor chain, so invalidate -> independently rematch
can create a new acceptance receipt without overwriting the old one; exact repeated
state/fingerprint/outcome is a no-op. Bind state/result to the same observation with
composite FKs. Include activation epoch in candidate dedup, not just feed epoch.
Reuse storage._stored for canonical decoding rather than copying Candle construction.
When active, preview bootstrap/connection/flush and canonical ingest must acquire source
write scope before their row locks; no added HTTP under a source/row lock. Feature env
opt-in plus DB default-off control both required for compatible writers. Activation is
migrator-only with strict existing-style explicit inventory attestations; missing/null
fields must reject. Consumer proof checks preserve existing source/recovery fences.

P1 PG role test exposed missing source-fence read privileges for receipt creation.
Grant market-data SELECT(epoch,revision) only on the public indicator_source_guard;
no table-wide SELECT/UPDATE, account, secret or trading permission. Revoke these two
column grants on empty downgrade. This is the smallest public-metadata privilege needed
for the approved durable source-fence receipt and is covered by role regression tests.
Await both concurrent test workers even on failure before closing pools/scratch DB.

P1 permission follow-up: the singleton source-fence query must read only its granted
epoch/revision columns (no WHERE id dependency). Engine closure readiness additionally
needs SELECT(source,connected,bootstrapped,failure_code,lease_until) on the public candle
feed state; no owner/epoch/write privilege. Add and revoke these narrow column grants
with0076, retain table-wide/secret denials. The first two PG runs failed on this missing
column privilege; do not report them as passed or relax role/atomicity assertions.

P2 binding detail before integration: save venue/market and per-symbol/catalog revision
with native evidence, validate known PUBLIC/PREPARING runtime pair before capture and
check symbol revision on consumption. Keep source identity primary_spot/Binance TH spot;
no Global adapter substitution. Strict CLOSED matching alone does not replace catalog fences.
For repair, extend existing StoredCandle refresh metadata/coalesced demand only while
closure protocol is active, and use the existing claim attempt/deadline/backoff limits;
matched post-end history must not suppress a bounded REST refresh for a closure conflict.

P3 bounded-tail implementation detail (engineering delegation, before changes): source
promotion can change a candle already inside the current F11 head. Existing tail fallback
only handles candles after head_end and would reject an otherwise fresh prefix until the
builder republishes. Reuse the latest published generation, find the earliest journal change
and the nearest checkpoint before it, prove the unchanged prefix at the original fence,
then replay fewer than1000 candles from that checkpoint under a new scoped source fence.
Keep codec/age/rollout/numeric-failure/head-authority gates and validate both prefix and
new suffix again before commit/queued admission. Record checkpoint boundary in provenance;
never relabel cached finality. Original full-generation proof remains the default everywhere.

P2/P3 safety-check findings before fixes: disconnected recovery requires the market-data
role to advance only control.recovery_at; grant UPDATE(recovery_at), retain migrator-only
activation/inventory/version fields and add a denial test. OFF-mode accounting fixtures
intentionally inject decision signals without canonical candles; keep original authority
path OFF, enforce proof rebinding when ON or provenance names a proof. Canonical batch
publication adds two constant schema/control reads, so update the query budget from6to8,
retaining one batch insert/partition lookup and no per-candle read while OFF.

P2 review identified a retry hazard before the repair fix: periodic enqueue_ended could
advance requested_at for the same unresolved close after the existing three-attempt budget
failed. Bind closure-only refresh requests to the immutable candidate.created_at, while
ordinary missing/pre-end requests retain their existing timestamps. Repeated heartbeats
then cannot revive FAILED for the same native evidence; a new candidate may request new
bounded work. Add a real-PG failed-demand replay test. Mutable closure state follows the
existing candle cleanup cutoffs; immutable receipts remain available for execution audit.

P3 deterministic composition exposed a distinct finality contract issue before the fix:
F11 IndicatorStream intentionally accumulates UNCONFIRMED provenance across eligible
NC31 warm-up history. read_bot_indicators treated that aggregate as the signal candle's
own finality, rejecting even a canonical CLOSED signal with a current closure receipt.
Keep F11 point metadata untouched. For the approved candle strategies under the enabled
protocol, permit READY indicator values with inherited UNCONFIRMED provenance only after
_candle_context verifies the actual signal is CLOSED with a current receipt. Other
strategies and protocol-OFF retain the original aggregate guard. Add real-PG composition
using250 eligible UNCONFIRMED history bars and one verified green signal, plus commit/
queued invalidation. This implements CP08/12's explicit history/signal separation without
relaxing source/age/codec/cutoff/numeric or pure strategy CLOSED gates.

P3 review before guard hardening: changing only closure_proof_id is outside F11's original
row-field journal comparison. The new closure guard will journal that native scope using
the existing statement revision (ON CONFLICT coalesces normal finality changes), so proof
rebinding also invalidates prepared/queued authority. Add a closure-trigger inventory
function following F11's catalog-only recursive partition check; activation, compatible
writers and current-proof readers reject missing/disabled closure guards. No relation-lock
inventory scan or new infrastructure. Keep downgrade refusal once evidence exists.

Review finding CP06/08 (before correction): invalidating A demotes its finality, but F11
NC31 may still accept its post-end REST values as historical UNCONFIRMED input when B
later closes. A current B receipt alone must not release a series with a known unresolved
contradiction. Reuse per-series source readiness/recovery semantics: closure state keeps
recovery_at; CONFLICT/INVALIDATED blocks that pair/timeframe, and repair advances its
cutoff before new entries. Ordinary missing/stale close evidence does not become a new
risk trigger and remains subject to the existing signal/warm-up guards.
A REST-conflict receipt can reconcile only against a newer independently fetched post-end
REST snapshot matching the native evidence, with current lease/catalog/protocol guards;
native contradictions still require new native evidence. Keep contradiction state across
candidate replacement until matching succeeds. No price winner or history/ledger rewrite.
Add real-PG blocked-next-entry/readiness and fresh repair regressions. Default OFF unchanged.
The one public campaign already ended Partial during F11 preparation (READY/SUPERSEDED),
zero orders/positions and protocol never enabled. Do not retry that campaign automatically;
its report is retained and cannot validate this later runtime correction.

Final migration regression adjustment before edit: the existing F21/Paper downgrade
refusal tests hard-code their former head0074/0075. With0076 installed, transactional
refusal must preserve the current head, not assert an older one. Capture revision before
the attempted downgrade and assert it remains unchanged afterwards; retain history/RLS/
privilege assertions. This changes the migration harness expectation only.

Correction to the preceding migration-harness assumption: real tests showed Alembic
commits each revision separately. Empty0076/0075 downgrades correctly succeed before
an earlier history-bearing migration refuses. Therefore the original assertions of
0075/0074 were correct. Restored both existing tests exactly; no migration semantics or
assertions weakened. The attempted expectation change failed2/4 tests and is retained
in the run history; rerun the restored tests only. No production change resulted.


Final review checkpoint: see review.md and validation.md for Passed/Partial/Failed/Not Run
results. Engine public-feed grants additionally include source writer owner/epoch to bind
current receipts to the native lease; the earlier P1 note omitting those columns is historical.
These are generated public writer IDs, not user ownership/credentials; no account privilege
was added. Narrow recovery_at update remains distinct from migrator-only activation.
No further public campaign, owner-preview activation or publication follows this checkpoint
without the outstanding gates/authorization described in validation.md.

## Owner continuation —2026-11-21

Owner replied “เริ่มทำ” after the checkpoint explicitly listing CI type blockers and a
new bounded public attempt as next steps. Continue the same approved feature: include
only the ten F21 dependency test files named by the full-mypy evidence for annotation,
optional/union narrowing, correctly typed interception callbacks and SQL Row conversion.
No runtime trading behavior, test assertions, mypy configuration or safety gates will be
weakened. Use direct imports rather than accidental module re-exports. This is necessary
combined-candidate CI cleanup under the engineering delegation and this continuation.
Retain the prior90-errors failure and Partial public attempt as history.

Interpret this continuation as authorizing one additional campaign with the same approved
BTC/ETH1m/Paper funds/6-minute capture limits after readiness; no repeated attempts or
owner-preview activation. Before consuming it, review the previous harness failure:
SUPERSEDED is an existing safe builder outcome, not failed numeric evidence. Preparation
must use existing bounded source-recovery scheduling and verify actual quote/book/source
readiness; no forced READY, synthetic prices/closed bars, cutoffs, ARM or fills. Record any
harness correction and bounded preparation budget before edits/run. No scope to relax
venue ordering/financial/entry rules is inferred.

Continuation harness review before correction: previous capture required READY from exactly
two run_attempt calls; F11 can safely supersede a scan when a current candle settles while
that scan is running. Preserve the real600-second failed-cycle cooldown and existing DB
attempt limits; do not reset jobs, counters or source fences. Use coalesce_jobs plus fresh
published-head authority checks within one300-second total preparation budget. Capture
remains at most360seconds after readiness; preparation timeout yields Partial and consumes
this authorized attempt without retries. Preflight must additionally pass existing quote
readiness and read_latest_book/BookState.require_ready for both pairs before activation.
Read-only inspection of the earlier owned DB showed real verified books had been published
(ETH2455/BTC2280 retained input IDs), so intermittent producer warnings alone do not prove
a permanently broken venue contract. No execution-book business rule change is justified.

Continuation environment finding: the temporary owned test launcher originally read all
job environments from ci.yml, unintentionally enabling E2E's chart flag for backend tests.
The secret-canary test correctly rejected HTTP200 instead of the default-off HTTP404;
focused reproduction confirmed it. Stop that invalid-environment full run, retain its
failure/interruption, restrict the launcher to backend-run's env, and verify the exact
failed case before restarting the full run on a fresh owned DB. No canary assertion,
security expectation or production flag default is changed. The public campaign alone
receives the required CI test sealing keys and explicit stop-authority activation.

Correct backend environment then exposed a genuine F21 test-inventory gap: the all-route
secret canary lacks a value/expected404 for /paper/bots/configurations/{identity}. Extend
only this canary's explicit placeholder and BOT_CONFIGURATION_NOT_FOUND assertion; keep
its no-unfilled-template assertion, default-off chart assertion and all forbidden-secret
checks. This is coverage for the approved F21 endpoint, not a security-policy relaxation.

Full backend continuation findings (before test fixes): the renewing-route inventory lacks
F21's existing POST /paper/bots/configurations, while the protected production policy already
classifies that explicit user mutation as renewing. Add the exact route to the test inventory,
retaining equality/public-route/polling exclusions. F21 API status tests depend on shared
market/indicator state: inventory=True fails without the F11 authority required by its
injected accounting BUY, and a shared-suite flat case differs from a fresh DB. Reuse the
existing isolated PostgreSQL fixture and a module-local client depending on it; seed actual
F11 codec/head authority only for the injected accounting entry, using existing seed_prepared.
Keep actual matcher/ledger/flat replacement/read-only TP assertions. No start-readiness,
financial, session or protection behavior in production is changed.

Additional full-suite coverage findings before fixes: Paper isolation's explicit internal
module inventory predates F21/Paper/Candle Closure dependencies. All current violations
are 'unexpected internal dependency', not forbidden network/venue/credential edges.
Inventory the exact approved domain/SQL-only modules (basket_disposals, strategy_candles,
strategy_config, bot baskets/candle_sources/configurations/indicator_tail, indicator codec/
source, public candle_closure/storage/indicator_reader, entry_anchor and the two pure
strategies); retain recursive traversal, all forbidden imports/markers and alias/transitive
negative fixtures. No wildcard or network/secret allowance is added.
The readiness-reason unit mock assumes aggregate UNCONFIRMED always exits before reading
values. CP08/12 now requires distinguishing eligible history from the actual signal/proof.
Supply complete READY indicator/page metadata and a classification-only candle-context
mock with no proof; preserve exact BOT_CANDLE_UNCONFIRMED rejection and verify context is
consulted only for inherited UNCONFIRMED, while OPEN rejects immediately. Real PG proof/
financial safety tests remain authoritative and are not replaced with this unit mock.


Continuation validation-environment finding: Redis Pub/Sub is shared across logical
Redis databases. The owner-preview Redis instance therefore cannot isolate the actual
notification-idle test by selecting DB10; the full run observed a completed public event
before its controlled publish. A dedicated disposable Redis instance on localhost56394
passed all3 notification checks without source/assertion changes. Use that instance for
the final focused failures and the authorized campaign; do not stop/reconfigure the owner
Redis. Two protection timing cases failed while full regression was active (one5s timeout,
one1.44309s versus required1s). Preserve these failures and rerun only those cases when
heavy regression is quiescent, with unchanged deadlines/SLA. This is diagnostic environment
isolation under the engineering delegation, not production infrastructure or a relaxed gate.
The full backend run completed6012passed/7failed/32deselected in2157.74s; six failures are
covered by the documented test-inventory/fixture fixes, and the seventh is notification
isolation. Keep its raw result and use affected reruns; do not claim it was a green full run.


Authorized second public attempt reached both actual F11 heads READY, source preflight
and owned closure activation, then stopped during OWNED_API_SETUP before any user/wallet/
order was created. Its result records RuntimeError only, which is insufficient to identify
the rejected setup step. Offline API-only signup in another fresh DB succeeded; this does
not establish the campaign's original failure cause and is not a third public campaign.
Before any future attempt, improve harness-only diagnostics: a typed API rejection with
controlled path/HTTP status, and traceback file/function/line without exception text,
request/response bodies, locals, cookies or secrets. Preserve the second Partial report and
its candidate manifest exactly. Test diagnostic sanitization offline, do not retry source/
trading campaign or modify production admission to make it pass. This is observability
work under engineering delegation; another public attempt still needs owner authorization.


## Owner completion continuation —2026-11-21

Owner explicitly approved proceeding to finish and report Ready for Code Review after the
previous checkpoint. Authorize one new actual-source attempt with the same300s preparation/
360s capture budgets, owned DB/Redis and existing funds/pairs/guards. Use corrected safe
API diagnostics, preserve earlier Partial reports and manifests. Continue engineering fixes,
affected tests and review within the delegated scope. This is not owner UI acceptance,
Live permission, relaxation of entry/proof/financial criteria or unlimited public reruns.
P5 remains the requested code-review checkpoint; report external owner/CI gates truthfully.


Attempt3 finding before harness edits: both actual F11 heads became READY and owned
activation succeeded, but /paper/bots/configurations rejected HTTP422. The RSI configuration
model forbids strategy_name, while the harness sends it to both strategy variants. Build
request payloads with existing StrategyConfigurationInput/PaperTestConfigurationInput,
not a parallel handwritten API contract. Add a real API test for both payloads.
The migrator is subject to FORCE RLS: earlier generic count/financial evidence queries
could hide existing users/wallets. Their empty results must not be used as proof of absence.
Use the already required test-admin URL only after strict owned-database/local guards,
with a read-only evidence/inventory engine (hide_parameters=True); keep runtime writers
on their existing narrow roles. Reuse this collector to append independently read corrected
historical evidence without overwriting old reports. Add actual-PG proof that a real wallet
ledger hidden from migrator is present in read-only evidence; no RLS/security policy change.
This is a diagnostic harness correction under engineering delegation. Attempt3 is Partial,
not retried, and the three-attempt stop rule remains in force before any further public run.


## Owner authorized attempt4 —2026-11-21

Owner explicitly selected “อนุมัติเพิ่ม 1 รอบเพื่อยืนยันการซื้อจริง” after the three-attempt
stop. Run exactly one additional public-source Paper attempt on the reviewed completion
candidate, using a new owned DB and separate disposable Redis; preparation300s and capture
360s, same BTC/ETH1m, existing funds/guards. Payload/RLS harness fixes are already tested.
No fifth attempt, time extension, synthetic readiness/fill or owner-preview activation is
inferred. Preserve original reports; inspect actual proof/decision/order/ledger/anchor chain
and report Partial honestly if the attempt does not demonstrate real entry.

## Review corrections —2026-11-22 (before implementation)

Owner requested fixes after the read-only review of candidate51f65193. Apply the
2026-11-14 engineering delegation to restore CP06/08/11 without new strategy/risk rules.
Evidence: queued authority accepts a healthy but expired B; accepted command processing
skips queued checks; native capture commits before observe detects an open→close conflict.

- Reuse native advance() and database clock: initial queued admission requires
  end(A) <= now < end(B), including exact boundaries. Keep fill timestamps factual.
- Extract the existing closure-reference check for reuse by queued and accepted BUYs.
  Before matching nonterminal candle-strategy BUYs, acquire existing financial/source
  fences in their established order and revalidate closure authority, including shared
  matchers driven by SELL. Do not reuse queued run-revision equality for accepted orders:
  ordinary feedback legitimately changes revisions. Preserve executions, balances and
  protection facts already committed; invalidated signals may not acquire new fills.
- Check native progression against the existing slot before publishing. For conflicting
  actual close events, persist candidate plus invalidation in the same source transaction,
  without an intermediate CLOSED publication. Reuse record_candidate/invalidate rather
  than introducing a second evidence writer. Existing closed→newer contradiction handling
  and sticky-hint separation remain intact.
- Add targeted real-PG regressions: expired/boundary queued admission, accepted BUY
  invalidation before first fill (including SELL-driven matching), and conflicting open→
  close with a competing reader. Keep deterministic fixture labels and all safety assertions.

Alternative of waiting for the bot to pause leaves a multi-instance race; accepting then
revoking a contradictory proof exposes an intermediate tradable state. Reject both.
Scope: authority, closure capture, affected matcher callers/tests only. No Live, owner
preview activation, extra public attempt, commit/push/merge or strategy/financial formula
change. Existing partial public evidence and required CI/owner gates remain open.

Affected-test evidence before fixture edits: legacy accounting queue_entry uses the
currently OPEN slot as signal, and one feedback fixture pins old calendar dates. The new
CP11 guard correctly rejects these before matching. Update those synthetic accounting
fixtures to the last CLOSED slot (two consecutive closed slots for ARM/FIRE), not the guard
or financial/race assertions. The SELL-driven regression needs free manual inventory after
its pending test BUY exists; prepare account-use metadata only with the isolated fixture's
test-admin connection (normal API correctly denies UPDATE), restore BOT before the actual
SELL-driven assertion, and create all inventory/execution facts through the real matcher.
No production account-use capability or RLS policy changes.

The corrected CLOSED-slot fixture exposes a related real race: an exit in B advances
progress.guard_revision, but queued authority never compares it with the decision's pinned
guard_revision; the old same-candle check compared the exit B to signal A and missed it.
Keep the existing rejection assertion. Reuse the already recorded guard_revision in queued
and accepted-opening invalidation queries under the owner lock. This restores the existing
exit guard (CP12), adds no cooldown/new trigger, and preserves existing positions/protections.

Broader affected basket/recovery tests retain four same-candle rejection failures after
fixing fixture timestamps: registration/context check exit(A), whereas orders enter in B.
Existing SR08/Paper RQ08 and these assertions require no re-entry in the current exit slot.
Before edits: extend the existing exit lookup to both signal A and its immediate entry slot
B, using native advance() (including month/week); retain the guard-revision race check.
Reuse the lookup through current context and register_entry, with a shared infra helper
in baskets.py to avoid three copies. No extra cooldown or TP/SL/financial formula change.


## Scoped review-fix refactor —2026-11-22 (before edits)

Owner requested review/refactor of the latest correction only. Reuse native advance() in
authority.py and compare()/existing prior observation in candle_realtime.py. Name signal
and entry boundaries once; flatten closure capture with an early generation/lease return
and resolve the previous observation once instead of repeating tuple access/None checks.
Keep every progression condition, branch priority, fence, transaction, error and time
check unchanged. Existing signal_exit_guarded and _closure_signal_current already remove
the relevant duplication; do not add abstractions or touch financial/domain formulas.
Alternative: retain nested code; selected cleanup improves readability with a two-file diff.
Engineering delegation applies. No strategy/session/persistent-state/Live/activation change.
Run existing closure PostgreSQL boundary/conflict/accepted-matcher regressions, realtime
unit tests and scoped Ruff/mypy/import checks. Existing Partial gates and campaign limit
remain unchanged; no public run, publication or merge is part of this refactor.


## Local Feature-gate continuation —2026-11-22 (before tests)

Owner requested continuation after refactor. Publication exception is awaiting an explicit
answer; do not commit/push/merge or run public campaign5. Close concrete V08 durable
recovery gaps first under engineering delegation using existing ready(), market_data_session,
PreviewLease acquire/connection and claim_next/write_candles test patterns in
tests/infra/execution_market/test_candle_closure_proof.py. Add real-PG tests for a committed
WAITING_REST observation surviving pool disposal and completing through actual claimed
REST persistence, and expired-writer takeover refusing both old lease submissions and
old-epoch pending reconciliation until a fresh current-writer close arrives. Keep exact
proof/row/result counts and lease checks; no runtime/business behavior change or mock
for durable/transaction correctness. Full multi-process deployment/public matrices remain
Partial unless separately evidenced. Inspect existing attempt4 dispatch evidence offline;
do not infer missing historical claim timing from terminal metadata.


## Owner draft-publication continuation —2026-11-22

Owner replied “เริ่มทำ” after the explicit next-step request for commit/push and a draft PR
solely to run required CI, without merge or another public campaign. This authorizes that
publication exception to P6; it does not approve owner acceptance, activation, merge, Live
or campaign5. Preserve remaining Partial gates. Integrate origin/main005ec483 (merged F17
refactor8e5bab69) before publication, preserving its existing trigger/manual-sale behavior
and the approved first-fill ATR extension. Run affected protection tests/static checks,
commit the combined reviewed source/docs/evidence once and open one draft PR. Follow required
CI on the final SHA, fix in-scope failures and report run links/status. Do not create a
document-only commit/PR loop merely to record the subsequent CI result. Prior source
manifests remain historical; final Git SHA binds the integrated candidate.


Pre-publication security-tool diagnostic: the unpublished integration commit is a merge
with newly added evidence. Existing tree occurrence mapping finds introduction commits
using git log --diff-filter=A without merge expansion, so merge-only additions have no
resolvable introduction and the scan fails INVALID_STRING. Do not weaken the scanner.
Preserve the unpublished integration as a local backup ref and create one linear final
reviewed commit with exactly the same tree on main005ec483, as permitted by the dependency
materialization plan. This also avoids publishing intermediary local dependency snapshots.
Source/evidence bytes and historical manifests remain intact; only unpublished topology
changes. Run the unchanged scanner on that final candidate before pushing.


## Owner-approved exact evidence exception —2026-11-22 (before registry edit)

Owner explicitly replied “อนุมัติข้อยกเว้นเฉพาะ 2 จุดนี้” for generic-api-key at lines12/17
of evidence/public-paper-campaign-4-diagnostics.json introduced by
c864411eb730d200cbb8dad3410a356e20579e88. Both values exactly equal the actual disposable
Paper order_id and intent.order_id, not authentication credentials. Add one immutable
binding to .github/security/evidence-exceptions.json using existing schema/resolver:
blobefa230cc4f1a248517af06f124cde0083936cb9b, deduplicatedcount2, occurrence-setdigest
39300c3e82add96b48536196bda5185f27485de40840e12f45b5a0622e43f892.
Preserve every previous approval; no new regex/path-wide suppression, identity/coverage
change or secret-scanner code change. Existing Security RQ7/approved immutable-evidence
contract applies. Run evidence resolver tests and full pinned history/tree scan on the
new commit before push, then required CI on that SHA. Other gates remain unchanged.
