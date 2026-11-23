# Paper Test Entry — Plan

สถานะ: **Approved — เจ้าของเลือกเริ่ม implement ตาม plan/validation วันที่ 2026-11-21**
วันที่: 2026-11-21 (Asia/Bangkok)
ฐาน: requirements.md Approved; first-fill anchor ยืนยันแล้ว; ยังไม่แก้ runtime

## 1. แนวทาง

เพิ่ม strategy identity/version แยก `paper-green-atr-test` version1/configuration1/state1
ซื้อจากแท่ง CLOSED สีเขียวของ timeframe ที่เลือก ใช้ ATR14 ของแท่งเดียวกัน
ไม่มี RSI/EMA entry filters ไม่สร้าง exchange adapter หรือ execution/PnL ชุดใหม่

ใช้เงินต่อไม้ที่กรอกและถือเพียงหนึ่ง position พร้อม entry-in-flight guard
TP/SL คงที่จาก first actual fill ±3×signal ATR ตลอด entry นั้น แม้มี partial fills
เพิ่มเติมหรือ ATR/ราคาของแท่งถัดไปเปลี่ยน ตามคำตอบเจ้าของ NC-04

แสดงเฉพาะใน owned Paper acceptance environment: API/engine ต้อง opt-in ตรงกัน
production defaults ไม่ publish/execute กลยุทธ์นี้ และ Live ไม่รับ config/reference นี้
การเปิด flag ไม่แทน account/risk/catalog/source/protection readiness
ไม่มี production debug endpoint หรือ client-side flag ที่ใช้อนุญาตเทรดแทน server

## 2. ของเดิมที่จะใช้ซ้ำและข้อจำกัดที่พบ

| ของเดิม | ใช้ต่ออย่างไร |
|---|---|
| `core/strategies.py` StrategyDescriptor/StrategyInput/StrategyDecision/StrategyDocument | pure strategy/versioned config/state, durable input identity/feedback |
| `core/strategy_candles.py`, `infra/bots/candle_sources.py`, `inputs.py`, `indicator_tail.py` | CLOSED candle/source proof/ATR readiness ผ่าน integration เดิม; ไม่ลด warm-up ของ shared source |
| `infra/bots/configurations.py`, `start.py`, `decisions.py`, `services/engine/bot.py::StrategyRegistry` | persisted config resolution, start/replacement/idempotency, evaluate/commit/feedback |
| `infra/protections/worker.py::bot_bracket`, `record_fill`, `_record_fill` | durable protection/quantity tracking, trigger/late fill/cancel/failure behavior; bracket เดิมเป็น absolute prices จึงต้องเพิ่ม entry-fill anchor แบบ typed |
| `core/protections.py::ProtectionPrices`, `core/money/` | exact target validation, Money/Quantity/Scalar arithmetic และ tick policy เดิม |
| `infra/paper_orders/worker.py`, `core/positions.py` | actual fill/fee/base quantity ไม่คัดลอก sizing/PnL/fee formulas |
| `PaperBotPanel.tsx`, `BotRunStatus.tsx`, `strategyJournal.ts`, `auth.ts::send` | selector/config/start/stop/recovery และ initial-load gates เดิม |
| `components/ui/Select.tsx`, `Input.tsx`, `Button.tsx`, `references/admin-template/` | pattern/style เดิม ไม่มี layout ใหม่ |

F-21 หลายจุดระบุ RSI identity โดยตรง ห้ามใช้ชื่อ RSI กับ strategy ใหม่หรือส่ง
config ใหม่เข้า strict RSI decoder เพื่อหลบ contract ต้องเพิ่ม dispatch เฉพาะขอบเขต
config/input/registry โดยให้ RSI route/default/codec เดิมได้ผลเดิม

## 3. งานก่อน implementation และการแยกงาน

- สร้าง branch/worktree ของงานนี้จากฐาน F-21 ที่ใช้งานได้ โดยรักษา source WIP และ
  spec/evidence ของ F-21 ไม่ reset/ย้าย/ทับงานเดิม ไม่ merge หรือเผยแพร่อัตโนมัติ
- อ่าน shared standards/callers ตามผลกระทบก่อนแก้ และระบุ exact reuse functions
  จาก module ที่มีจริง ไม่สร้าง abstraction จากชื่อ module ที่คาดเดา
- ฟังก์ชันใหม่ใช้เฉพาะเมื่อของเดิมไม่รองรับ; refactor dispatch เท่าที่จำเป็น
  ไม่ย้าย implementation RSI ทั้งก้อน ไม่ทำ generic plugin framework

## 4. Pure strategy และ config/state

- Config: identity/version, pair, timeframe, capital_per_entry; ไม่มี max_entries field
  กลยุทธ์นี้ บังคับเลือก timeframe จาก shared contract ก่อนเริ่ม ไม่มีเงิน default
- Immutable pin ต่อ run; decoder ปฏิเสธ unknown fields/wrong version/invalid units
- State เก็บ last processed candle, pending entry identity และ lifecycle ที่จำเป็น
  ใน PostgreSQL checkpoint ผ่าน contract เดิม ไม่มี global business state
- BUY เฉพาะ CLOSED green candle ที่ ATR/source/clock/progress ผ่าน guards
  และไม่มี open position, pending/unresolved entry, outstanding exit หรือ exit-candle block
- หนึ่ง candle identity สร้างได้ไม่เกินหนึ่ง BUY; quote polls/replay/backfill ไม่สร้าง BUY เพิ่ม
- Feedback/no-fill reject/cancel ปิด pending ตามข้อเท็จจริง ไม่ตีความ signal ว่า filled
  จบ entry/exit ทั้งหมดแล้วจึงกลับมาประเมิน candle ใหม่ตาม freshness/exit guards เดิม

## 5. First-fill TP/SL และ transaction

- Persist ATR snapshot/entry target policy กับ immutable entry linkage ก่อนส่ง BUY
  ใช้ versioned typed payload แยกจาก absolute bracket เดิม; strict decoding
- ที่ first actual fill ใช้ราคาของ execution fact แรกคำนวณ TP/SL และบันทึก anchor
  พร้อม protection ใน transaction เดียวกับ fill/ledger เดิม ภายใต้ locks เดิม
- ใช้ Money/Quantity/Scalar และ tick rounding/price guards ของ F-17 เท่านั้น
  ห้ามนำ raw Decimal/float มาคำนวณใน strategy/infra
- ถ้า integration ต้องมีตารางเสริมให้จำกัดเฉพาะ durable entry-anchor metadata
  (entry order/protection linkage, ATR, first execution identity/price, resolved levels,
  schema version) ใช้ FORCE RLS/FK/unique checks และ narrow grants ตาม standards
  ตรวจ schema เดิมก่อนเลือก additive JSON metadata หรือตาราง; บันทึกทางเลือกก่อนแก้ migration
- Resolve once โดย unique entry identity + row lock/transaction guards; retries,
  worker takeover และ late/duplicate feedback ต้องใช้ anchor เดิม
- Subsequent fills เพิ่ม net protected quantity ตาม fee/base effect เดิม ไม่ retarget
  หาก protection trigger/exit ไปก่อน late fill ให้ใช้ late-fill/failure policy เดิม
- SL<=0, tick invalid, target crossed หรือ source/setup unavailable ใช้ failure policy
  เดิม ไม่สร้างระดับใหม่ ไม่ทิ้ง fill หรือ ledger เพื่อซ่อนปัญหา protection
- Manual reduction/cancel ใช้ F-17 เดิม ไม่เปิดบอทใหม่จาก partial reduction
  ไม่เพิ่มปุ่มแก้ราคาซึ่งเขียนทับ frozen strategy levels

## 6. API/UI และ activation

- เพิ่ม strategy identity ใน immutable config storage/resolver โดยมี typed discriminator
  ที่ไม่เปลี่ยนความหมายเอกสาร RSI เดิมหรือ reference เก่า และ fingerprint รวม identity
- Catalogue ส่ง strategy ทดสอบเฉพาะ server gate เปิด; configure/start ตรวจ gate,
  owner, mode, version และ risk/readiness จาก server แม้ยิง API โดยตรง
- Paper selector เลือก RSI เดิมหรือ “Paper Test Entry · ATR TP/SL” ได้เมื่อ server อนุญาต
  ใช้ form เดิม ซ่อนจำนวนไม้เฉพาะ test strategy ไม่ส่งค่า max_entries แฝง
- Pinned run แสดงค่าที่ใช้จริง เปลี่ยน strategy/config ต้องเป็น run ใหม่ตาม replacement
  proof เดิม ห้ามเปลี่ยน strategy ของ run ที่กำลังทำงานหรือมี exposure
- Start/Stop ใช้ action area เดิม ไม่มีข้อความสถานะเท็จระหว่าง reload และ journal
  กู้คำขอเดิมได้ ไม่ส่ง start ใหม่อัตโนมัติ
- อัปเดต OpenAPI/generated frontend types พร้อม targeted contract tests ถ้า contract เปลี่ยน

## 7. Validation และ checkpoint

ทำตาม validation.md: pure/numeric tests → real-PostgreSQL integration/races/faults →
actual-API Paper browser flow → static checks/review/fix/refactor → owner checkpoint

เมื่อ implementation ครบ แจ้ง Ready for Code Review พร้อมผล/ข้อค้าง แล้วรีวิวต่อทันที
owner visual acceptance และ required CI ยังเป็น gates ก่อน merge ไม่ใช้ local แทน CI
Batch/Release ที่ยังไม่ถึงกำหนดคง Pending Full Validation ไม่เปิด Live ในการทดสอบ

## 8. ความเสี่ยงและเงื่อนไขหยุด

- Anchor resolution กระทบ F-17 fill transaction ต้องมี actual-DB rollback/replay tests
  และ RSI/F-17 regressions ก่อนผ่าน Feature
- ถ้าพบว่าการคงระดับ/partial-fill policy หรือ tick rules ไม่สามารถทำตาม requirements
  ภายใต้ contract เดิม ให้บันทึกหลักฐานและถามเจ้าของก่อนเปลี่ยนกฎ
- หากจำเป็นต้องขยาย architecture/สิทธิ์/infra หรือผ่อนเกณฑ์ ต้องขออนุมัติตาม AGENTS.md
- งานที่ไม่ผ่านสามรอบหรือเกินขอบเขตทดลองที่อนุมัติต้องหยุดเสนอทางเลือก

## Engineering detail before implementation — 2026-11-21

Worktree `../TiewTrade-paper-test-entry`, branch `feature/paper-test-entry`, local F-21
baseline e811800. Original F-21 worktree/index/WIP preserved; nothing published.

Reuse F-21 candle/progress/source/exit guards via a closed two-strategy dispatch, and
its entry bookkeeping with internal occupancy1. Test strategy bypasses basket TP
retarget/trigger; its ordinary F-17 two-leg protection controls exits. Do not impersonate
RSI or add RSI/EMA filters. Reuse250-candle readiness without lowering its gates.

Use separate owner-scoped append-only config table for the distinct strict config
shape, plus entry-anchor metadata table bound to immutable bot order/run scope. Both
are in existing PostgreSQL with FORCE RLS/FKs/unique checks/narrow grants. Config create
uses the existing idempotency keys across both strategies, serialized by a narrow
transaction advisory key lock; fingerprint includes strategy identity. New typed
EntryAtrProtection declaration shares StrategyDecision.brackets with legacy absolute
ProtectionPrices. Persist its ATR before BUY admission; resolve/latch first actual fill
inside the existing financial writer transaction before quantity/protection processing.

F-17 executable_protection_quantity uses MARKET exits; its trigger levels do not
require LIMIT tick alignment. Reuse the existing RSI TP tick-floor helper for TP,
and keep exact Money(price−3×ATR) for SL, without introducing a new SL rounding rule.
Provisional levels exist only for WAITING_ENTRY admission; actual first-fill levels
replace them atomically before exposure is protected. If resolution is invalid, retain
actual fill and use existing BOT protection setup-failure close/stop policy. Subsequent
fills never recompute the latched levels. Mark resolution before handling late fills.

Test activation stays deployment-owned and false by default in API and registry.
Catalogue publishes the test choice only when enabled; direct configure/start and
Live references cannot bypass gates. Preserve legacy RSI config/request payloads and
references; add a strict test input union and additive catalogue choices. No new service
or generic plugin framework.

## Implementation / review checkpoint — 2026-11-21

ทำตามแนวทางที่อนุมัติด้านบน ไม่มีการเปลี่ยนกฎซื้อ/เงิน/TP/SL/STOP/Live
ใช้ first-fill row lock ร่วมกับ financial writer locks เดิม; metadata/levels/ledger rollback
ด้วย transaction เดียวกัน ตรวจ fault หลัง registration และหลัง anchor/protection write,
concurrent replay และ separate-interpreter recovery กับ PostgreSQL จริง

Review refactor: ลด nested ternary ใน bracket serialization, ลบ duplicate configuration
read และ join ที่ไม่จำเป็น, ใช้ shared candle fixtures แทนคัดลอก fixture จาก RSI test
ไม่มี plugin framework, infrastructure หรือ production activation เพิ่ม

Environment isolation: แยก virtualenv ของ worktree ใหม่ และคืน editable package pointer
ของ virtualenv เดิมให้ repo F-21; ตรวจ source paths ทั้งสองฝั่งและคง preview15121/API18021
เดิม ไม่ย้ายข้อมูลหรือเปิด bot/Live ของเจ้าของ

เพิ่ม CI E2E step ใช้ owned database/ports แยกจาก F-21. รายละเอียดผล/ข้อค้างอยู่ใน
[checkpoint](evidence/checkpoint.md); owner acceptance / final required CI ยังเป็นจุดหยุดก่อน merge

## Preview correction before activation — 2026-11-21

Owner reports new strategy cannot be selected. Evidence:15121/API18021 and both bot
workers still import original F-21 worktree; UI there has disabled single RSI option.
Owned preview DB is0074, existing RSI runs STOPPED/RETIRED, zero nonzero positions.
The new feature exists only in its isolated worktree, so code tests did not update the
owner-facing preview. Alternative separate URL would preserve an obsolete review link;
update the existing local acceptance URL to this worktree instead, preserve accounts/history,
apply additive0075, and opt in both API and worker only in the /tmp acceptance composition.
Stop old API/bot workers before starting the compatible composition, keeping public market
source and risk/protection/STOP rules. No new run, BUY, balance change, resume, Live or
production activation. Authority: approved engineering/diagnostic scope and requested
Paper owner acceptance. Verify catalogue→UI selection/reload, worker gate and DB migration;
retain owner acceptance/CI gates. No application behavior/risk change required.

## Start/readiness follow-up before correction — 2026-11-21

Latest owner Start created paper-green-atr-test run correctly but paused at
SOURCE_NOT_READY/INDICATOR_NOT_READY. Data demand is COMPLETE; six indicator jobs QUEUED
and no indicator builder process is running. Compact BotRunStatus shows PAUSED and Stop
but omits the existing readiness explanation rendered by the full view. Reuse existing
indicatorNotReady/awaitingData text below Stop only for confirmed PAUSED readiness, without
new alerts during loading or changing start/stop semantics. Add regression for paused
indicator/candle vs RUNNING/loading. Restore existing production indicator-builder service
with its narrow DB role in owned preview, preserve all source/warm-up/STOP guards; no
manual status/indicator/price rewrite, no new start. This supports the already user-started
Paper run; no Live activation. Approved engineering/diagnostic authority applies.

### NC-05 — Needs Clarification: live-source candle finality

After builder restoration, read_bot_indicator_page returns ATR READY but candle finality
UNCONFIRMED; actual latest BTC1m market_candles are also UNCONFIRMED. RQ01 and shared
read_bot_indicators require CLOSED. F-09 RQ6 / F-11 RQ9+NC31 explicitly preserve
UNCONFIRMED after post-end REST fetch; calculable ATR is not closure/trading proof.
Therefore the real-market Paper run remains PAUSED despite ready ATR. No permissible
engineering-only conversion exists: do not rewrite finality or weaken this guard.
Blocks real-source entry acceptance, not start request/Stop button correctness. Owner must
choose existing controlled CLOSED acceptance fixtures or approve a separately documented
trading-finality policy change for real data before implementation. No change made to
financial/source admission rules; retain pending owner/CI status.

## NC-05 proposal prepared — 2026-11-21

Owner selected drafting real-market rules before changing code. Prepared
[requirements amendment RM-01–RM-13](real-market-candle-policy.md), status Proposed.
Do not implement UNCONFIRMED trading, reclassify canonical finality, migrate a paused run
or auto-start on this drafting instruction. After requirements approval, prepare concrete
plan/validation amendment for the second approval gate. Existing approved baseline retained.

## NC-05 latest decision - Closed, 2026-11-21

Owner selected the same candle-finality/readiness and MARKET execution rules as RSI
Step Grid. Compared both pure strategies and shared read_bot_indicators: both reject
non-CLOSED candles, unready warm-up and stale/backfill inputs. No runtime change needed.
Paper Test Entry retains green-only entry/one-position/first-fill ATR TP/SL rules.
UNCONFIRMED proposal is Superseded, not approved; earlier pending-decision notes are
historical. No new tests needed for this documentation change; source/spec consistency
and git diff --check reviewed. Real-source entry remains Blocked until CLOSED evidence
is available. Owner acceptance/CI and pending full validation remain unchanged.

## Finality readiness diagnostic correction before code - 2026-11-21

Owner requested proceeding after approving the existing CLOSED-only rule. Remaining
real-source acceptance blocker is unchanged, but reporting INDICATOR_NOT_READY when
ATR is READY and the point is UNCONFIRMED is misleading. Split that existing rejection
into BOT_CANDLE_UNCONFIRMED, keep the exact same rejection/no-trade behavior, and map
it to a short confirmed status message in compact/full status. Reuse existing readiness
prefix/API status field, UI text dictionaries and TailAdmin status text pattern. Do not
modify finality, strategy triggers, amounts, source policy, active run pin or STOP.
Targeted tests: both real strategy descriptors reject an UNCONFIRMED indicator point;
UI reports the precise reason only for confirmed paused state with no loading flash.
This is engineering/diagnostic scope under delegated authority, not a new strategy rule.

## Owner display override before code - 2026-11-21

Owner explicitly requests removing the Paper "Paused" label and the confirmed-candle
waiting sentence. Hide only Paper PAUSED badge (keep Live behavior, pending/running/STOP
and control availability), remove the now-unused candle-wait translations, and suppress
that specific readiness message without falling through to misleading warm-up text.
Keep precise API/audit readiness and all CLOSED/trading/locking guards. Reuse existing
BotRunStatus rendering and targeted panel tests; no new layout or hidden CSS text.
This display choice supersedes the earlier requested finality explanation on the UI.

## Owner indicator-copy removal before code - 2026-11-21

Owner requests removing indicator waiting text. Remove indicator readiness rendering
in compact/full BotRunStatus and delete its unused translation keys. Simplify remaining
candle-warm-up mapping; preserve data gates, durable status/reason, Stop and run/config
locking. Reuse existing panel tests for hidden indicator/candle copy and loading states.
No backend, money, trading or source-finality change. Explicit owner UI instruction
supersedes previous display-only indicator explanation; no new approval gate needed.

Targeted panel run exposed an existing test synchronization race: refetching flat
replacement proof updates query cache before its scheduled observer notification reaches
React, while waiting for an already-enabled Start button returns immediately. Flush that
scheduled notification within act before clicking; retain exact latest revision6 assertion.
No application replacement/permission/business logic change or weakened assertion.
