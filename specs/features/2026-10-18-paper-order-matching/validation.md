# F-15 — จำลองการจับคู่ออเดอร์ Paper — Validation

สถานะ: **Approved** — เจ้าของอนุมัติพร้อม plan.md และ requirements amendment NC-F15-07 วันที่ 2026-10-18
วันที่: 2026-10-18
อ้างอิง [requirements](requirements.md), [plan](plan.md) และ testing standard §7
ฉบับแก้ไขนี้รวม NC-F15-07 ที่อนุมัติแล้ว; ตัวอย่าง liquidity เป็น independent oracle
สำหรับ implementation contract ตามคำอนุมัติ “approve” วันที่ 2026-10-18

## 1. “เสร็จ” หมายถึง

M1 core checkpoint มีผลตรวจแล้วตาม [หลักฐาน M1](evidence/m1-core.md);
M2 public input/storage/schema มีผลตาม [หลักฐาน M2](evidence/m2-input-storage.md)
V-1..V-9/V-16/V-17 เป็น **Partial** เพราะ production/financial integration ยังไม่ครบ
[M3 complete](evidence/m3-complete.md) ปิด order worker/financial/cancel/correction/recovery
ที่ development checkpoint แล้ว: V-10..V-13/V-15..V-17 เป็น **Partial** จน candidate/fault matrix ครบ;
[M4 complete](evidence/m4-complete.md) ปิด reset/readiness/API/UI integration ที่ development checkpoint แล้ว:
V-13..V-15/V-17 เป็น **Partial** จน candidate/race matrix ครบ; V-18 ยัง **Not Run**
และ [M5 candidate](evidence/m5-candidate.md) ปิด High finding, downstream conflict,
controlled admission/fill/GET races, source corruption/conflict และ cancellation/timeout แล้ว;
V-18 **Passed** หลัง required CI run #116 ผ่านครบ 6 jobs บน candidate commit ส่วน V-19 คง
**Pending Full Validation** สำหรับ release checkpoint

Post-M5 dispatch/worker/persistence ผ่าน affected safety 125 tests, follow-up 12 tests,
nominal/recovery smoke และ backend/full required CI บน candidate ล่าสุดตาม
[M5 candidate](evidence/m5-candidate.md); เกณฑ์ V-1..V-18 จึงปิดครบสำหรับ Development Complete
โดย V-19 ชุดยาวยังเลื่อนไป release checkpoint ตามคำสั่งเจ้าของ

| # | Requirements | เกณฑ์และวิธีตรวจ | ระยะรัน | ผล/หลักฐาน |
|---|---|---|---|---|
| V-1 | RQ-1..5/17 | strict intent/type/size/TIF/unit/owner/mode/episode; MARKET BUY budget, SELL quantity, LIMIT GTC; unsupported options/ambiguous size reject; no silent resize; shared constraints contract | พัฒนา + candidate | **Passed 2026-10-20** — core, durable boundary และ final candidate gates ผ่าน |
| V-2 | RQ-3/4/9/10/25 | independent golden/Hypothesis เงิน/fee/step/reserve/budget, Money range/18 decimals, hostile ambient decimal context, no float/raw Decimal outside money; exact PostgreSQL round-trip | พัฒนา + candidate | **Passed 2026-10-20** — independent financial tests และ PostgreSQL integration ผ่าน |
| V-3 | RQ-6..8/12 | crossing เดินราคาตาม depth, price/limit/budget bounds, partial/EXPIRED/FILLED, no extrapolated depth; book freshness/latency boundaries และไม่ใช้ future input | พัฒนา + candidate | **Passed 2026-10-20** — verified source, worker integration และ boundary matrix ผ่าน |
| V-4 | RQ-6/7/14 | queue-ahead/FIFO/eligible trade side/price, depth cancellation ไม่ใช่ fill; NC-F15-07 A/C/V golden trace ทุก transition รวม zero/reappearance/gap, duplicate/out-of-order และ shared consumption; independent episodes ไม่แย่ง virtual liquidity | พัฒนา + candidate | **Passed 2026-10-20** — golden traces, durable checkpoint/rebase และ recovery ผ่าน |
| V-5 | RQ-3/6/7/13/20/21 | capture/replay serialized intent+market inputs+profile+เวลาแล้ว event/state/ledger digest ตรง; repeat/restart ไม่เพิ่ม fill; full evidence มีเนื้อหาไม่ใช่เพียง hash | พัฒนา + candidate | **Passed 2026-10-20** — serialized evidence/replay, restart และ restore checks ผ่าน |
| V-6 | RQ-1/11/18/26 | safety contract fail closed, missing risk capability ไม่รับ production order; MANUAL/BOT/owner boundary; risk-reduction/cancel ไม่ติด allowlist แต่ไม่ข้าม gates และไม่สร้าง fill เมื่อ feed ไม่พร้อม | พัฒนา + candidate | **Passed 2026-10-20** — production composition และ fail-closed/scope gates ผ่าน |
| V-7 | RQ-6..8/20 | snapshot/diff bridge IDs, absolute levels/zero removal, gap/disconnect/stale lease/late callback, duplicate trade, malformed/unknown required rule; overflow 4096 slots เป็น unavailable/rebase ไม่ drop เงียบ | พัฒนา + candidate | **Passed 2026-10-20** — source/PG/fake feed, overflow และ runtime recovery matrix ผ่าน |
| V-8 | RQ-6/8/10/26 | versioned pair capability/type/TIF/price tick/min/max/step/notional และ execution rules ใช้จริงตาม contract; unsupported required filter reject; withdrawn pair demand ยังทำงานโดย market-data ไม่อ่าน user table | พัฒนา + candidate | **Passed 2026-10-20** — capability parser, required-rule rejection และ withdrawn-pair lifecycle ผ่าน |
| V-9 | RQ-8/17/21/22 | real PG grants/RLS/FORCE RLS/composite FKs/owner/mode/episode, scanner metadata-only, market-data public-only, parent/child partition append-only, no runtime owner; upgrade populated 0032 และ safe downgrade refusal | พัฒนา + candidate | **Passed 2026-10-20** — schema/RLS/grants, migrations 0033–0038 และ writer fences ผ่าน |
| V-10 | RQ-10/13..17/21/25 | full PG financial transaction: input/order/fill/F-14/ledger/reservation/revision/audit ครบหรือ rollback ทั้งชุด; APPLIED/REPLAYED/CONFLICTED semantics, unique cash effect, fee profile pinning | พัฒนา + candidate | **Passed 2026-10-20** — persisted financial transaction, rollback/fault injection และ replay ผ่าน |
| V-11 | RQ-10/13/14/20/25 | real multiple connections/workers: two buys ใช้ quote ซ้ำไม่ได้, two sells ใช้ base ซ้ำไม่ได้, fill/cancel ordering ทั้งสองทาง, expired claim/duplicate scan ไม่ double-apply; no starvation ต่อ user อื่น | พัฒนา + candidate | **Passed 2026-10-20** — controlled races, per-owner claim, lease recovery และ fairness ผ่าน |
| V-12 | RQ-13/16/20/21/25 | F-14 RECORD/REPLACE/VOID ผ่าน caller จริง, exact compensating ledger effects/fee history; repeated correction ไม่มีผลเพิ่ม, downstream invalid chain conflict ไม่สร้าง negative position หรือ half-correction | พัฒนา + candidate | **Passed 2026-10-19** — RECORD/REPLACE/VOID/compensating cash/replay และ downstream-invalid caller ผ่าน; conflict fingerprint/audit คงอยู่โดยไม่มี partial fill/cash |
| V-13 | RQ-18..20/24 | episode เดิม/ใหม่/หลัง reset initialize sources พร้อม proof/baseline/profile; absent/corrupt/mismatched proof unknown; concurrent init, init/fill race, fault rollback/retry และ conflicted rebuild ไม่ auto-clear | พัฒนา + candidate | **Passed 2026-10-20** — source proof/conflict matrix, init/fill barrier, rollback/retry และ rebuild fail-closed ผ่าน |
| V-14 | RQ-15/17..20/24..26 | F-13 reset success ด้วย real position+order sources, pending commands/reservations block; coherent API reset readiness/owner-scoped grants, reset/reset/admission/fill/GET barriers; browser confirmation/pending/retry/conflict/refetch, history/PnL isolation และ terminal replay across episode | พัฒนา + candidate | **Passed 2026-10-20** — real-source reset/races/replay, browser regression และ candidate gates ผ่าน |
| V-15 | RQ-13..15/20/22 | failure injection ทุก write/audit/precommit, DB failure/commit outcome unknown, cancellation/timeout/kill ก่อนและหลัง commit, Redis loss/restart/generation change; recover durable result โดยไม่มีเงิน/order ซ้ำ | พัฒนา + candidate | **Passed 2026-10-20** — rollback/retry, lost acknowledgement, TCP disconnect, process kill และ recovery smoke ผ่านโดยไม่มีผลการเงินซ้ำ |
| V-16 | RQ-2/8/18/23 | Paper entrypoint/transitive imports ไม่มี venue/network/credential/key prerequisite; purity/import/endpoint gates และ negative fixtures; fake venue เดิน feed→DB→matching→ledger ได้ ไม่ส่ง Live order | พัฒนา + candidate | **Passed 2026-10-20** — persisted fake pipeline, isolation/import/network gates และ negative fixtures ผ่าน |
| V-17 | RQ-6/8/18/20/22/23 | bounded public shape check (read-only ไม่มี key), fixture provenance/diff, isolation/snapshot coherence, migration+old/new writer fence, no public order/correction route หรือ Live activation; manual checks §5 | ก่อนปิด integration + candidate | **Passed 2026-10-20** — public shape observation, provenance, migrations/writer fences, route/Live absence และ integration checks ผ่าน |
| V-18 | ทุกข้อ | final diff/dependency review Critical/High ปิดครบ; backend full regression/lint/format/mypy/imports, frontend lint/types/unit/build, OpenAPI drift, browser regression และ required CI บน final commit | candidate ก่อน merge | **Passed 2026-10-20** — latest review ไม่มี Critical/High ค้าง; affected safety 125 tests, follow-up 12 tests, static gates, backend full regression, frontend, OpenAPI, E2E และ required CI run #124 attempt 2 บน final candidate ผ่าน; post-merge run #125 ผ่านครบ 6 jobs |
| V-19 | RQ-6..8/10/13..15/18/20/22/23/25 | workload/stress/endurance/resource/restore ตาม §6 ทั้งหมด; correctness assertions ทำงานตลอดและเก็บผลเดิมหาก Failed/Partial | release checkpoint; development smoke ตามความเสี่ยง | Pending Full Validation — W4 restore ผ่าน 2026-10-20 ตาม `evidence/m6-w4-final-20261020/`; W1–W3 ยังไม่ผ่านครบ เก็บ failed attempts และ smoke แยก ไม่ใช้ smoke ปิดชุดเต็ม |

Development Complete ต้อง V-1..18 ผ่านและไม่มี Critical/High ค้าง; required CI ต้องตรง
commit สุดท้าย ไม่ใช้ local แทน CI; V-19 คง pending จน release checkpoint
Completed ต้อง V-1..19 ผ่านครบและตรวจ readiness/dependencies ก่อน production activation
F-15 ไม่รับรองว่า F-16/F-18 หรือ Live execution พร้อมใช้งานตามไปด้วย

## 2. ตัวเลขอิสระและคุณสมบัติที่ต้องจริง

oracle ใช้คำตอบคำนวณอิสระหรือ exact integer/rational ใน tests ไม่เรียก production
matching/fee helper มาสร้าง expected values และไม่ใช้ float generator
golden fixtures ระบุ raw input, units, profile version, event order และเหตุผลคำตอบ:

1. **Fee และ cash conservation:** ทุน 2500 USDT ซื้อ gross 1 ETH ที่ 100 USDT,
   fee 0.001 ETH → ถือ 0.999 ETH, cost 100, cash 2400;
   ขาย 0.999 ETH ที่ 120 → gross 119.88, fee 0.11988 USDT, net 119.76012,
   cash 2519.76012, realized PnL 19.76012 และ position/cost ศูนย์
   ห้ามเพิ่ม PnL เข้ายอดเงินอีกครั้ง ทดสอบทั้ง single fill และหลาย fills ที่รวม economic inputs เท่ากัน
2. **Budget/depth:** MARKET BUY งบ 150, ask 100×1 และ 110×1, gross step 0.01
   → ซื้อ gross 1.45, ใช้ 149.5, fee 0.00145 base, net 1.44855,
   เงินที่ไม่ใช้ 0.5 คืนเมื่อ terminal commit; ไม่มี liquidity สมมติให้ใช้เงินจนพอดี 150
   คำตอบนี้ใช้ fixture constraints ที่อนุญาต ไม่อ้างว่าเป็น actual BTC/ETH filters
3. **Correction จากกรณี 1:** แก้ sell price เป็น 110 → gross 109.89,
   fee 0.10989, net 109.78011, cash 2509.78011,
   compensating cash = -9.98001 เทียบผลเดิม; replay correction ผลเพิ่มศูนย์
   แยกอีกกรณี VOID sell เดิม → compensating cash -119.76012,
   cash 2400 และกลับถือ 0.999 ETH/cost 100 โดยไม่มีการแก้ ledger เก่า
4. **Reserve:** cash 150 กับ LIMIT BUY gross 1 ที่ 100 สองใบแข่งกัน
   ต้องรับได้ไม่เกินหนึ่งใบ (reserved 100, available 50);
   ขายสองใบรวมเกิน held base ต้องไม่ผ่านทั้งคู่; buy/sell fee-in-received ไม่หักอีกสินทรัพย์ซ้ำ
5. **Queue:** visible ahead 2, Paper A quantity 1 แล้ว B quantity 1 ณราคาเดียวกัน;
   eligible opposing trade quantity 2.5 → A fill 0.5, B fill 0;
   duplicate trade ไม่เปลี่ยนผล; การถอน depth อย่างเดียวไม่ fill A หรือ B
6. **Latency/freshness:** t0 acceptance → eligible t0+100ms; book ก่อน eligible
   ใช้ไม่ได้ และต้องมี input received หลัง eligibility ตาม requirements;
   book verification อายุเท่ากับ 30s ยังผ่านอายุ มากกว่า 30s ไม่ผ่านตาม NC-F15-11
   แต่ disconnect/lease/sequence fail ทำให้ไม่พร้อมแม้อายุยังน้อย
   latest-trade boundary 10s ยังผ่านอายุ, >10s ไม่ผ่าน และยังใช้ provenance คนละชุดกับ book
   NC-F15-12 ต้องครอบคลุม trade ID ที่กระโดด/ย้อนลำดับ, bounded economic dedupe ซึ่ง
   event time ต่าง, conflicting duplicate, stale depth `u`, depth gap และ receive-order replay
7. **Limits:** partial ที่ราคาดีกว่า limit ได้ แต่ไม่ซื้อแพง/ขายต่ำกว่า limit;
   quantity step ที่ไม่ใช่กำลังสิบ, price ticks, minimum/maximum boundary,
   unknown required metadata, dust และ unsupported size/type ต้องได้ typed result
8. **Numeric boundary:** positive/zero/negative, Money max/min storage quantum,
   overflow ตอนคูณหรือ fold, unit mismatch, excess precision, bool/NaN/Infinity,
   hostile decimal context และ fee rounding ขอบ scale ต้องไม่ทำ negative funds/position
9. **Liquidity amendment NC-F15-07:** เริ่ม A/C/V=10/0/10, taker q=4 → 10/4/6,
   absolute 8 → 8/4/4, absolute 10 → 10/4/6, absolute 2 → 2/2/0,
   confirmed zero → 0/0/0, reappearance 10 → 10/0/10;
   duplicate ทุกขั้นให้ state เดิมและ stale IDs ไม่ย้อน state
   fork อีก trace หลัง taker เป็น gap → snapshot 10 ต้องยัง 10/4/6;
   snapshot ไม่ครอบคลุมระดับเดิมต้อง unknown ไม่ใช่ 0/0/0
   A/B ใช้ shared V=6: A ซื้อ 4 แล้ว B ซื้อได้ไม่เกิน 2 ไม่ใช่ 4;
   episode อีกคนเริ่ม V=10 ได้ตามโมเดลแยก episode
   maker trade ลด queue/fill แต่ A/C/V คงเดิมจนมี depth update จริง;
   replay ตรวจ state ทุก prefix รวม rebase โดย oracle ไม่เรียก production transition

Hypothesis: deterministic replay, consumed quantity ไม่เกิน proven liquidity, budget ไม่เกิน,
reserved/available ไม่ติดลบ, total cash ไม่เปลี่ยนจาก reserve/release, holdings ตรง effective
F-14 stream, money invariant ทุก prefix, terminal order ไม่กลับมาจับคู่จาก input เดิม,
sequence correction ไม่เพิ่ม source completeness และ owner/episode isolation
properties ที่ต้องการ identical results ต้องถือ inputs/ลำดับ/rounding boundaries เหมือนกัน
ไม่สมมติว่าแบ่ง fill ต่างกันแล้ว rounding จะให้ยอดเหมือนกันทุกกรณี

## 3. Transactions, races และ recovery

ใช้ PostgreSQL จริงพร้อม runtime roles และอย่างน้อยสอง connections/workers
barriers คุม interleaving ไม่ใช้ sleep เพื่อหวังให้ race เกิด:

- same command/key/payload admission, payload conflict, same fill/event และ correction replay
  ต้องได้ durable result เดียวและ audit/economic effect ไม่ซ้ำ
- fill ก่อน cancel และ cancel ก่อน fill; cancel partial คืนเฉพาะ reservation ที่เหลือ
- pending command ก่อน order projection ต้องบล็อก reset; stale claim ที่ได้สิทธิ์หลัง reset
  ห้ามเขียนเข้า episode เดิม หรือย้าย intent ไป episode ใหม่โดยไม่ขอใหม่
- reset/reset จาก expected episode เดียวกันสำเร็จไม่เกินหนึ่ง; reset/fill/init/admission
  ต้องมี linearized winner, source read ไม่ครึ่ง revision และไม่มี orphan ledger/closure
- injection หลังทุก write, หลัง F-14 คืน effects, หลัง reservation update, หลัง audit,
  ก่อน commit และหลัง commit แต่ก่อน response; ตรวจ row counts/digests ภายหลัง restart
- transient failure, lease expiry และ concurrent scan ต้องไม่ทำให้ user อื่นอดประมวลผล
- F-14 conflict ต้องคง durable conflict fingerprint/audit ตาม contract ขณะที่ failed
  infrastructure transaction rollback ทั้งชุด ไม่กลืน conflict เป็น empty source
- Redis ล่ม/ข้อมูลหาย → PostgreSQL facts ยัง recover ได้; network ไม่พร้อม → ไม่มี fill ใหม่
- source ring overflow, engine ขาดช่วง หรือ feed generation เปลี่ยน → unavailable/rebase fact;
  rebuild ใช้ evidence ของ committed decisions ได้แม้ public cache ถูก overwrite แล้ว
- old/new worker และ schema rollout ต้องพิสูจน์ DB capability fence ปฏิเสธ old financial
  writes ต่อ managed episode; deployment rollback ไม่เปิด reset หรือ trade ผ่าน old path

## 4. การปิดงาน F-13/F-14 ที่เกี่ยวข้อง

V-13/V-14/V-15 ของ F-15 ต้องอ้างกลับ [validation F-13](../2026-10-15-paper-wallet/validation.md)
V-4/V-6..V-10/V-13 โดยรักษาผล Partial/Not Run เดิมจนมีหลักฐานสำหรับ production integration:

- browser สอง user ใช้ API session/CSRF จริง ไม่มี API key/TOTP เป็น prerequisite ของ Paper
  สร้าง wallet, init sources, reset ว่างสำเร็จ, reload เห็นรอบใหม่และ history เดิมคงอยู่
- seed activity ผ่าน actual internal order/F-14 writers ไม่ใส่ fake idle flag หรือแก้ DB ยอดเอง
  เมื่อมี position/open order/pending intent/reservation reset ต้อง fail closed
- ปิดกิจกรรมผ่าน actual execution/cancel workflow แล้ว reset ได้เมื่อหลักฐานครบ;
  ห้ามใช้ production risk bypass เพื่อทำ E2E ให้ผ่าน ถ้า dependency ยังไม่พร้อม
  integration subset ใช้ test composition ของ policy contract พร้อมบันทึกขอบเขตชัด
- source unknown/error/conflicted และ cancellation/timeout/commit-failure injection ต้องมี
  หลักฐานใหม่; เปิด wallet source อย่างเดียวไม่ทำให้ reset success Passed
- API snapshot ต้องให้ reset_available=true/reason=null เมื่อ sources ครบและว่างจริง;
  missing/unknown/conflict/activity ต้อง false พร้อม typed reason และ owner อื่นอ่านไม่ได้
  GET ที่แข่ง admission/reset ต้องไม่ผสม readiness จาก revision หนึ่งกับ balance อีก revision
- component/browser ต้องพิสูจน์ปุ่ม enabled จาก readiness, reason แปลถูกทั้งสองภาษา,
  confirmation แสดงทุน/episode ที่จะ reset, cancel confirmation ไม่ส่งคำขอ,
  pending กัน double submit, timeout retry ใช้ key/payload/expected episode เดิม,
  stale episode ไม่ auto-resubmit; success refetch เห็นรอบใหม่ ส่วน failure คงรอบเดิม
  ตรวจ focus/keyboard/error/loading/responsive และ template styles ของ modal/controls
- ตรวจ F-14 sequence/replay/correction/source initialization tests ที่ได้รับผลกระทบอีกครั้ง
  และคง F-14 release workload ที่เลื่อนไว้ ไม่ใช้ F-15 smoke ปิดของเดิม

## 5. ตรวจด้วยมือและ contract integration

ใช้ internal harness/FakeVenue ใน automated flow ไม่มี Live order หรือ credential:

1. เริ่ม Paper worker โดยไม่ตั้ง credential/sealing key และสกัด network clients ทั้งหมด
   admission เมื่อ safety capability ไม่พร้อมต้อง reject ขณะที่ wallet/reset flow ยังทำงานตามหลักฐาน
2. เริ่ม market-data กับ public read-only adapter ตรวจ shape/metadata/depth bridging
   แบบจำกัดคำขอ BTCUSDT/ETHUSDT; บันทึก endpoint/เวลา/digest/rate-limit behavior
   ไม่เก็บ account data และไม่เรียก signed fee/account/order endpoint
3. ตรวจ received/source/verification time, generation, revision และ availability ใน internal
   snapshots; reconnect/clock skew/stale input ไม่คืน READY หรือแสดง fill ปลอม
4. ต่อ browser F-13 reset ตาม §4; UI states/i18n/exact amounts เดิมไม่ regression
   ไม่มี order form/Live toggle ใหม่ใน F-15
5. ถอนคู่ผ่าน test catalog/demand fixture หลังมีภาระจริง → opening ถูกปฏิเสธ,
   feed demand ยังอยู่, reduce/cancel ผ่าน gates เดิม; ไม่มีการบังคับปิด position

public venue mismatch ที่กระทบ contract เป็นเหตุให้หยุดและขอคำตัดสิน ไม่บันทึก Passed
จาก fixture อย่างเดียว; negative gate fixtures ต้องพิสูจน์ว่าทางลัดถูกจับ ไม่เพียง grep ข้อความ

## 6. Workload/resource/endurance/restore — Pending Full Validation

เกณฑ์ตัวเลขส่วนนี้เสนอเพื่ออนุมัติพร้อมแผน ไม่ใช่ business limits:
อ้างอิงเครื่องอย่างน้อย 4 logical CPU/8 GiB RAM, local PostgreSQL/Redis, runtime/lockfiles
ตาม repo และประกาศ CPU/RAM/container limits, DB settings, dataset/digest ใน evidence
เครื่องอื่นต้องระบุความแตกต่างและยังใช้ thresholds เดิม ไม่ปรับลดเพื่อให้ผ่าน

- **W1 workload:** 100 Paper episodes, แต่ละ episode 20 active LIMIT orders บน BTCUSDT,
  book inputs 10Hz พร้อม recorded/fake deterministic trade events;
  commands 10/s รวมทุก owner (new/cancel/replay แบบคงที่ใน fixture) 30 นาที
- **W2 burst/overload:** dataset เดิม commands 100/s 10 นาที; แยกกรณีจงใจ overflow
  book buffer/slow consumer เพื่อพิสูจน์ fail-closed/rebase โดยไม่มี false fill/money duplication
- **W3 endurance:** W1 4 ชั่วโมงพร้อม connection churn, worker restart และ Redis outage
  ที่ schedule ใน fixture; non-fault phases ใช้ latency/readiness thresholds เดียวกัน
- **W4 restore:** backup PostgreSQL ที่มีทุน/fills/partial/cancel/correction/reset/evidence จริง
  ใน harness แล้ว restore ลง DB แยก; replay ตรวจ canonical digest, cash/position/history,
  identity/claim recovery, profile/version และ RLS/grants ไม่ใช้ backup ไฟล์เปล่าปิดด่าน

### Positive matching oracle สำหรับ W1–W3

ใช้ synthetic BTCUSDT capability fixture ที่ pin version/digest และ constraints อนุญาต
ตัวเลขด้านล่าง ไม่อ้างว่าเป็น actual venue filters; public contract ตรวจแยกใน V-17
แต่ละ episode เริ่ม 10000 USDT และ seed 20 resting LIMIT BUY ราคา 1, quantity 1
ให้ reserved=20 โดยไม่มี trade ที่ราคา 1; setup ไม่นับเป็น measured command throughput
book ที่พร้อมมี bid=99/ask=100, quantity ฝั่งละ 1000000 และ boundary levels
bid=1/ask=120 อย่างละ 1000000 เพื่อพิสูจน์ coverage ของ baseline/resting prices;
revision 10Hz ไม่ reset C
และไม่ส่ง trade ที่ 110 ระหว่าง cycle ปริมาณนี้รองรับทุก cycle โดยไม่ต้องเติม liquidity ปลอม

หนึ่ง cycle ต่อ owner ต้องจบก่อน cycle ถัดไปของ owner นั้น มี measured commands 5 รายการ:

1. MARKET BUY budget 100 → gross 1, fee 0.001 base, net holding 0.999, cash -100
2. LIMIT SELL 0.999 ที่ 110 → resting และ reserve 0.999; ยังไม่มี fill
3. replay ข้อ 2 ด้วย key/payload เดิม → order/economic effect เพิ่มศูนย์
4. CANCEL LIMIT ข้อ 2 → CANCELED, release 0.999 โดยไม่เพิ่ม cash
5. MARKET SELL 0.999 ที่ bid 99 → gross 98.901, fee 0.098901,
   net cash +98.802099, holdings/cost กลับศูนย์

ต่อ cycle ต้องมี 3 new orders, 2 fills, 1 successful cancel, 1 replay,
terminal orders เป็น FILLED 2/CANCELED 1; cash และ realized PnL เปลี่ยน -1.197901 USDT
reserved quote ของ baseline ยัง 20 และไม่มี reserved base หลัง cycle
expected values มาจาก independent exact arithmetic ไม่ใช้ production matching เป็น oracle

- W1: 10 commands/s × 1800s = 18000 commands, 3600 completed cycles,
  7200 fills/3600 cancels/3600 replays; กระจาย round-robin 100 owners คนละ 36 cycles
  cash ต่อ episode ต้องเป็น 9956.875564, position ศูนย์และ baseline orders คงอยู่ 20
- W2 non-fault burst: 100 commands/s × 600s = 60000 commands, 12000 cycles,
  24000 fills/12000 cancels/12000 replays; คนละ 120 cycles, cash 9856.25188
  overflow/slow-consumer เป็น fault phase แยก ห้ามรวม unavailable มาลด expected ของช่วงนี้
- W3: schedule fault intervals และจำนวน N cycles ต่อ owner ใน fixture พร้อม digest
  manifest ก่อนรัน หยุดสร้าง cycles ใหม่ตาม schedule ระหว่าง fault แล้ว resume;
  cycle ที่ค้างต้อง recover จน terminal โดยไม่ซ้ำ คำสั่งวัดช่วง non-fault ยังเป้าหมาย 10/s
  final fills=2N/cancels=N/replays=N และ cash=10000-(1.197901×N) ต่อ owner;
  N ต้องกำหนดจาก schedule ไม่คำนวณย้อนจากผลสำเร็จจริงหรือแก้หลังเห็นผล
  negative fault cases ที่คาดว่าจะ reject ต้องแยกจาก positive cycle counters

ใช้ fake feed และ test-only policy composition ผ่าน actual engine/storage/F-14/ledger
ใน isolated harness ตาม §4; production missing-gate rejection เป็น negative test แยก
ไม่เปิด bypass ใน production เพื่อให้ workload ผ่าน
วัด offered/admitted/completed/rejected/fill/cancel/replay counts แยก และตรวจว่าป้อน load
ถึงอัตราที่กำหนด ถ้าป้อนไม่ถึงหรือ positive cycle ไม่จบให้ Failed/Partial ไม่ตัดออกจาก sample
ทุก positive cycle ต้องจบภายใน 60s ในช่วง non-fault ที่ fixture รับรอง liquidity;
หลัง recovery ต้อง drain positive cycles ค้างภายใน 60s เกณฑ์นี้เป็น harness progress bound
ไม่ใช่ production order timeout และไม่แทน p95/p99 processing criteria ด้านล่าง

ทุก phase assertions: duplicate economic effects = 0, cash/quantity/reservation invariant
violations = 0, false READY/false safe reset = 0 และข้าม owner/mode/episode = 0
warm non-fault phases ต้อง p95 engine processing ≤250ms, p99 ≤1s
วัดแยกจาก simulated latency 100ms และจากเวลาที่ต้องรอสภาพคล่อง/คิวจริงในโมเดล
ไม่เพิ่ม business fill timeout เพื่อให้ metric ผ่าน; backlog ต้องไม่โตต่อเนื่องหลัง burst จบ
และต้องกลับเข้า baseline ภายใน 60s หลัง dependencies กลับมาพร้อม

บันทึก peak RSS/CPU/DB growth/connection count/lock waits และ buffer occupancy
worker RSS ไม่เกิน 1GiB ต่อ process, ไม่มี connection/claim/lock leak;
ใน W3 RSS หลัง warm-up ไม่โตเกิน 20% ระหว่างชั่วโมงแรกที่นิ่งกับชั่วโมงสุดท้าย
ยกเว้น financial evidence ที่ตั้งใจเพิ่มต้องแยกออกเป็น DB storage growth ไม่ใช่อ้างเป็น RAM leak
ตรวจ scale edge ด้วย Money/Quantity maximum inputs และ depth/order count boundary fixtures
แยกจากจำนวนผู้ใช้ใน workload; ขนาด harness ไม่กลายเป็น runtime order cap

ชุดยาวใช้ BTCUSDT เท่านั้นตาม F-38; runtime readiness และ correctness/safety ของ
ETHUSDT ยังต้องผ่าน V-1..17 ครบ ไม่ถือว่า BTC-only workload รับรอง ETH capacity
หากต้องรับรอง workload ของ ETH ต้องขออนุมัติเพิ่มและเก็บ Pending Full Validation แยก

**Workflow amendment — Approved 2026-10-24:** ไม่รัน W1 smoke อัตโนมัติท้ายงาน
หรือเมื่อกลับมาพัฒนาต่อ; ใช้หลักฐานเดิมที่ยัง valid ตาม testing หัวข้อ 7.
smoke W1 60s/10 episodes เป็นขอบเขตสำหรับกรณีมีความเสี่ยงของ harness/resource
ที่ tests เล็กกว่าหรือหลักฐานเดิมพิสูจน์ไม่ได้เท่านั้น ต้องแจ้งเหตุผลก่อนรัน.
W1–W4 ชุดเต็มคงตรวจที่ release checkpoint/ชุดที่ 9 ตามเกณฑ์เดิม
แต่ไม่ปิด W1..W4 หรือแทน safety/concurrency tests ถ้า smoke ไม่พอพิสูจน์ความปลอดภัย
ต้องรันส่วนที่จำเป็นทันที ไม่รอ release และคงผล Failed/Partial พร้อมสาเหตุของรอบเก่า

## 7. ด่าน candidate และรูปแบบหลักฐาน

เมื่อ candidate นิ่ง รันคำสั่งตาม CI/environment จริง:

```text
backend: uv run ruff check .
backend: uv run ruff format --check .
backend: uv run mypy
backend: uv run lint-imports
backend: uv run pytest
frontend: npm run lint
frontend: npm run typecheck
frontend: npm run test
frontend: npm run build
frontend: npm run gen:api พร้อมตรวจ generated diff ตาม CI
frontend: npm run test:e2e พร้อม real migrated PostgreSQL และ workers
```

ใช้ bootstrap/migration/contract export ขั้นตอนเดียวกับ `.github/workflows/ci.yml`
รวม required security/architecture/jobs ทั้งหมด ไม่เลือกเฉพาะคำสั่งในตัวอย่างนี้
ไม่รันซ้ำเต็มหลังทุก patch; การแก้ findings ตรวจ targeted/regression ที่ได้รับผลกระทบก่อน
และใช้ผลเดิมต่อเมื่อ dependencies/config/source/environment ที่พึ่งพาไม่เปลี่ยน

เก็บใน `evidence/` เมื่อเริ่ม implementation: command, runtime/tool versions, commit/diff
fingerprint, fixture/profile/input digest, result/count/time, criterion IDs, failure trace
ที่ไม่มี secret และงานค้าง บันทึกเวลาอ่าน/วางแผน/เขียน/ตรวจ/รีวิว/รออนุมัติแยกตามวัดจริง
ไม่มีหลักฐานหมายถึงยังไม่ผ่าน และไม่มีการเปลี่ยนผล F-13/F-14 เดิมโดยไม่มีผลทดสอบใหม่

## NC-F15-10 — Approved (2026-10-20)

เจ้าของอนุมัติให้คง revision ของ terminal history เดิม และอัปเดตเฉพาะ active orders/รายการที่เพิ่งจบใน transaction ปัจจุบัน พร้อม reservation ที่ปล่อยเป็นศูนย์อย่าง atomic. Terminal revision ต้องไม่เกิน activity revision; projection/reservation ของรายการเดียวกันต้องสอดคล้องกัน. ใช้ additive migration ปรับ F-13 reset coherence โดยรักษา source proof, event linkage, owner isolation และการปฏิเสธข้อมูลผิด/ไม่ครบ; ไม่แก้ migration 0037. Downgrade ต้องปฏิเสธเมื่อมีข้อมูลที่ contract เดิมรับไม่ได้ ไม่ rewrite ประวัติ.

ใช้ `matching_storage.persist_checkpoint` และ `paper_wallet_reset_readiness` เดิม; เพิ่ม real PostgreSQL safety tests สำหรับ active/current-terminal revision, old terminal rows ไม่ถูกเขียนซ้ำ, corruption, reset, correction, rollback/retry และ migration. กฎเงิน/การจับคู่และเกณฑ์ W1–W4 คงเดิม; ผลที่ได้รับผลกระทบต้องตรวจใหม่ก่อน Completed.

### NC-F15-13 — Binance TH execution filters

ก่อน manual acceptance ต้องผ่าน parser/codec/history pagination และ gap tests,
weighted-average/percent/min-notional exact boundaries, max-open concurrent/idempotent
admission, restart/recovery และ affected API/worker/matching tests ตาม
[amendment](binance-th-execution-filters-amendment.md). Unknown/incomplete evidence ต้องยัง
ได้ typed unavailable/unsupported; localhost result ไม่แทน full validation.

Checkpoint 2026-10-30: Binance TH `BTC/USDT` และ `ETH/USDT` จริงถูก decode เป็น
capability ที่ `unsupported_rules=[]` สำหรับ MARKET/LIMIT; `PERCENT_PRICE`,
`MIN_NOTIONAL.applyToMarket` และ `MAX_NUM_ORDERS` ถูกเก็บพร้อม weighted public-trade
reference 5 นาที. ชุด affected venue/core/service ผ่าน รวม 67 tests ในชุดยืนยันย่อย
และชุดขยายที่เกี่ยวข้องทั้งหมดไม่มี failure; ruff, mypy 236 source files และ
`git diff --check` ผ่าน. API read-only ด้วย owner ปัจจุบันให้ `admission_ready=true`
และ `admission_reasons=[]` เมื่อ BTC price/book/risk พร้อม. ระหว่างตรวจพบ price feed
recovery ชั่วคราวทำให้ `ORDER_PRICE_UNAVAILABLE` ตาม fail-closed contract แล้วฟื้นเอง;
ไม่มี Live order หรือ manual submit โดย agent. Full F-15 validation ยังคงสถานะเดิม.

Follow-up runtime checkpoint 2026-10-30: NC-F15-11 implementation ยังมี hard-coded
1-second pre-publication check แม้ `BookState` ใช้ approved 30-second boundary แล้ว;
แก้ให้ใช้ `MAX_BOOK_AGE` จุดเดียวและเพิ่ม exact boundary test. NC-F15-14 เพิ่ม public
execution source-clock tolerance 100ms ตามอนุมัติ พร้อม depth/trade 100ms และ
100ms+1us cases. Bootstrap เดิมจับ depth snapshot ก่อน paginate weighted trade history
จน snapshot อายุเกินระหว่าง catch-up; แก้ตาม NC-F15-13 ให้เรียง capability → history →
current snapshot → buffered stream. Targeted core/adapter/matching tests ผ่าน 111/111,
real-role pipeline ผ่าน 3/3, F-10 real-role integration ผ่าน 10/10, ruff/format,
mypy 236 source files และ diff check ผ่าน. หลัง rebuild BTC/ETH book และ price เป็น READY
พร้อมกัน 12/12 samples ต่อเนื่อง 30 วินาที; owner read-only API คืน
`admission_ready=true`, reasons ว่าง, MANUAL และมีกระเป๋า Paper. Agent ไม่ส่งออเดอร์.

NC-F15-10 checkpoint: migration up/down/up และ affected order/wallet/position safety ผ่าน; readiness smoke 100 owners บน 0038 Failed ที่ positive-cycle timeout โดย cancel ยังรอ dispatch. คง W1–W3/V-19 Pending Full Validation; W4 เดิมเป็นหลักฐาน schema 0037 ต้องตรวจ final candidate ใหม่. ดู M5 evidence สำหรับคำสั่ง/ฐานข้อมูล/ผลตรวจ.

Dispatch checkpoint 2026-10-20: affected safety 118 tests ผ่าน; smoke หนึ่งรอบครบ 500 commands/100 cycles และ post-stop economics ผ่านทุก owner แต่ไม่ถือเป็น acceptance เพราะ drain Failed. รอบยืนยันถัดไปยัง Failed (publisher/progress); เก็บทั้งสองผลตาม M5 evidence และคง Pending Full Validation.

Publisher/worker checkpoint 2026-10-20: supervision และ atomic per-owner claim แก้ครบ; affected safety 125 tests และ follow-up dispatch/supervision 12 tests ผ่าน. `evidence/m6-supervised-smoke-20261020/` ผ่าน 500 commands/100 cycles พร้อม financial oracle; `evidence/m6-supervised-recovery-20261020/` ผ่าน restart/churn/Redis recovery smoke. เก็บผล Failed เดิมและคง W1–W3/V-19, W4 บน final schema และ final candidate gates เป็น Pending Full Validation; smoke ไม่แทน acceptance ชุดเต็ม.


## Deep-review remediation candidate — 2026-10-25

Owner requested remediation of two High findings (correction rebase cursor and
execution-time type-specific/cumulative maximum constraints) and one Medium finding
(immutable MARKET expiry outcome). The uncommitted candidate is on
`fix/f15-review-findings`; scope, regression mapping, retained failed harness attempts
and final evidence are recorded in [M5 checkpoint](evidence/m5-candidate.md#deep-review-remediation--2026-10-25).
V-3/V-4/V-5/V-8/V-10/V-12/V-15 are affected and receive new targeted evidence.
Historical V-18/CI results above apply to the earlier merged candidate; this remediation
still requires full candidate/required CI gates before merge. V-19 remains
`Pending Full Validation`; this checkpoint does not declare Completed or activation.

Final local serial confirmation: **302 tests passed** in 90.517s,
including the new real-role PostgreSQL regressions, affected order/wallet/position safety,
core/Hypothesis, market input/adapter and gate tests. Ruff/format, mypy (477 files), seven
import contracts and final diff review passed. These results close the scoped local
remediation; final-commit full candidate/required CI and V-19 remain pending as above.


## Local full backend candidate — 2026-10-25

Full backend confirmation on the final remediation source passed **3267 tests**,
with **2 venue-contract tests deselected**, in **795.874s**. Real-role PostgreSQL/Redis,
migration cycles, API, domain/property, financial transaction/race/recovery, security,
import/purity and F-15 regression tests all completed in one serial pytest invocation.
Full attempt 1 exposed a process-kill test's dependence on global scan duration; the
owner-scoped real-claim/barrier correction passed targeted tests and the full run.
Full attempt 2 had an unrelated intermittent prepared-indicator failure; its unchanged
standalone recheck and the final full run passed. Earlier failed results are retained
with diagnosis/limitations in [M5 checkpoint](evidence/m5-candidate.md#full-backend-candidate-continuation--2026-10-25).

V-18 local backend regression is **Passed**; required CI on a final commit remains
pending. Runtime/static/import evidence remains valid; full mypy after the final test
change passed 477 files. No commit/push/merge is included. V-19 stays
`Pending Full Validation`; this does not declare Completed or activation.


## Required CI checkpoint — 2026-10-25

Remediation commit `f2240a4` passed all six jobs in push CI
[40169303759](https://github.com/yukasung/tiewtrade/actions/runs/40169303759)
and PR CI [40169323746](https://github.com/yukasung/tiewtrade/actions/runs/40169323746).
Backend totals are 3267 and 3270 respectively (2 venue-contract tests deselected);
PR CI includes main's F-13 remediation. Config, API contract, frontend, containers,
browser E2E, backend static/import checks and full regression all passed without reruns.

The branch is synchronized with main to satisfy the up-to-date branch requirement.
Its pre-documentation tree exactly matches the PR merge tree verified by that CI;
there are no further runtime/test changes. The latest-head required CI is tracked in
[PR #33](https://github.com/yukasung/tiewtrade/pull/33). This closes the runtime candidate
CI evidence; merging the PR still requires the synchronized head's checks. V-19 remains
`Pending Full Validation` at the approved release checkpoint; F-15 is not Completed.
