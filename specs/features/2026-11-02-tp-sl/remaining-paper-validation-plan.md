# F-17 — แผนตรวจหลักฐาน Paper ที่ยังขาดหลัง PR63–65

สถานะ: **Approved A — เจ้าของตอบ approve วันที่ 2026-11-09; เตรียม runner/checks และ A1→A2→A3 อย่างละหนึ่งรอบเมื่อด่านก่อนผ่าน แล้วหยุดรายงาน; ไม่รวม B**
วันที่: 2026-11-09 (Asia/Bangkok)
ที่มา: เจ้าของสั่ง “เริ่มทำข้อ 3” เพื่อจัดแผน ไม่ใช่เริ่ม campaign
Candidate ตั้งต้น: `de3bdcb6b9d9187ee9a06b5f7dcb43387f5d8e98`.

## 1. เป้าหมายและขอบเขต

ตรวจเพิ่มเฉพาะหลักฐานที่โค้ด protection/worker/API และ schema0066 กระทบ
ใช้ผล Feature CI และหลักฐานที่ยังตรง source ต่อ ไม่รัน full suite ซ้ำเป็นพิธี
ไม่เปลี่ยนกฎเงิน ออเดอร์ PnL ปริมาณ การปัด ความเสี่ยง หรือเกณฑ์ที่อนุมัติ
เอกสารนี้เป็นข้อเสนอการจัดลำดับตรวจเพิ่มเติม ไม่แทน approved requirements,
plan, validation หรือ amendments เดิม ไม่มี campaign ใด Passed เพิ่มจากแผนนี้

อ้างอิงหลัก:
[requirements](requirements.md), [plan](plan.md), [validation](validation.md),
[internal amendments §14–23](internal-paper-acceptance-amendment.md),
[manual validation](manual-acceptance-fix-validation.md),
[MANUAL/BOT mapping Approved A](manual-profile-clarification.md),
[retained campaign receipt](evidence/recovery-20261106/internal-pilot-local-checkpoint-20261107.md).

### ความพร้อมของเอกสารและ source

Worktree เอกสารข้อ1–2 เดิมไม่พบเมื่อเริ่มงานวันนี้ และ Git แสดงเป็น prunable
จึงสร้าง worktree ใหม่บน branch เดิม `docs/f17-checkpoint-de3bdcb` โดยไม่ลบหรือ
prune metadata เดิม ไม่แก้งานค้างใน root worktree และไม่สร้าง commit
เอกสารข้อ1–2 ที่ยังไม่ commit **ยังไม่ได้กู้คืน**; ไม่สร้างไฟล์เก่าขึ้นแล้วอ้างว่า
เป็นต้นฉบับ แผนนี้อยู่ได้ด้วยหลักฐานใน Git และข้อสรุปในบทสนทนา

ตรวจ hash ซ้ำแบบอ่านอย่างเดียว: final review-correction manifest6/6ตรง source;
W4 snapshot994รายการ:912ตรง/76เปลี่ยน/6ไม่อยู่ที่pathเดิม ไม่ใช่ full-tree equivalence
ผลโหลดเดิมยังคงตาม candidate/profile เดิม ไม่ถูกแปลงเป็นผลของ de3bdcb
[หลักฐาน refactor เดิม](evidence/manual-acceptance-fix/review-corrections/refactor-checkpoint.md)
ยังแยก synthetic API proof ออกจากเจ้าของใช้งานจริง
CI/Security ของ de3bdcb ที่ตรวจในข้อ1–2:
[CI42498430491](https://github.com/yukasung/tiewtrade/actions/runs/42498430491),
[Security42498430605](https://github.com/yukasung/tiewtrade/actions/runs/42498430605).
ยอด backend4,926/frontend664/browser42 มาจากการตรวจ log ในข้อ2 ไม่ใช่การรันใหม่วันนี้
ก่อน execution ยืนยัน candidate/หลักฐานอีกครั้งเฉพาะส่วนที่เปลี่ยน

## 2. ทางเลือกและเวลาที่เสนอ

**แนะนำ A — ชุดสั้นเพื่อปิดช่องว่างก่อนลงทุนกับโหลดชุดยาว**

| ลำดับ | สิ่งที่ทำและหลักฐานเพิ่ม | เวลาประมาณหลัง environment พร้อม |
|---|---|---|
| A1 | controlled20 บนฐานว่าง:20บัญชี/400baseline, input-ready→processing-start≤1sครบ20owner, exact exit/cash/position/audit/replay |3–8นาที รวม preflight |
| A2 | D20:20บัญชี/400baseline/600commands,300s measured, freshDB; บันทึก latency/inputs/final-tail/pool/resources |10–15นาที; งบเดิม20นาทีตั้งแต่ preflightรวมcleanup |
| A3 | W4:สร้าง source/target ใหม่, real pg_dump/restore, RLS/grants/canonical equality, pending F16/F17 request/retry/exit/recovery |5–10นาที รวม preflight; recovery boundเดิม60s |
| A4 | ตรวจ manifest/results/cleanup และสรุปเกณฑ์ที่ยังค้าง |5–10นาที |

เผื่อ fixture/การสลับphase: **ประมาณ30–50นาทีรวมชุด A หลัง environment พร้อม**
เป็นประมาณการ ไม่ใช่การขยาย timeout หรือรับประกันผลผ่าน
การเตรียม Python/dependencies/Docker/ฐานแยก/runner ที่ worktree เดิมหายไป
ประเมินเบื้องต้นเพิ่ม15–30นาทีถ้า dependencies มีพร้อม หากต้องกู้ runtime หรือ
บริการมีปัญหา ให้รายงานก่อนเริ่ม timing ไม่ซ่อนเวลาเตรียมไว้ในเวลาชุด A
วันนี้ยังไม่ได้ตรวจสุขภาพบริการหรือยืนยันว่า venv/container เดิมมีอยู่

ชุด A เป็น **affected-evidence checkpoint** เท่านั้น การเลือก W4 หลัง D20 เป็น
การตรวจ restore แยกเพิ่มเติม ไม่ใช่เปลี่ยนลำดับ acceptance เดิมเพื่อข้าม W1/W2/W3
หากผ่านจะยังไม่ปิด IP-V6, V-18 หรือเรียก Paper Internal Pilot Accepted/F17 Completed

**B — ต่อหลักฐานโหลดภายในที่ยังขาด หลัง A ผ่านและเจ้าของเลือกชุดนี้**

| ลำดับ | Approved profile ที่ใช้ | เวลารวมต่อphaseโดยประมาณ |
|---|---|---|
| B1 W1 |20owner/400baseline,3600commands,2/s,1800s measured ตาม§16 |35–40นาที |
| B2 W2 |PAPER_INTERNAL20_V2,12000commands,10/s,1200s target,1260s completion bound ตาม§20 |25–30นาที |
| B3 overflow |4097inputs พร้อม recovery/economic invariants เดิม |5–10นาที |
| B4 short W3 |PAPER_INTERNAL20_V3,3000commands,1800s measured,7faults,620snapshots/20final replays ตาม§21–22 |35–45นาที |

รวม B พร้อมสรุปประมาณ **1¾–2¼ชั่วโมง** เพิ่มจาก A ไม่ใช่4h endurance
แต่ละphaseต้อง preflight/freshDB/cleanup เดิม และผ่านก่อนเริ่มphaseถัดไป
W4ของ A ใช้ต่อได้หาก source/config/schema/restore dependencies ไม่เปลี่ยนระหว่าง B
ไม่รัน W4ซ้ำเพียงเพราะอยู่ท้ายรายการ ถ้ามีการแก้ที่กระทบ ให้ระบุ gap ก่อนเสนอรอบใหม่
Bไม่ได้รับอนุมัติจากการเลือก A และไม่เริ่มเองหลัง Aจบ

## 3. คงเกณฑ์ที่อนุมัติแล้ว

- ใช้ profile/threshold จาก `profile_internal.py` ปัจจุบัน: internal pilot processing
  p95≤500ms/p99≤2s ตาม§16; เป้าหมาย250ms/1sยังรายงาน warning เมื่อเกิน
  ไม่ย้อนใช้ D20 runnerเก่าก่อน§16 แล้วอ้างว่าข้อกำหนดเหมือนกัน การเลือก threshold
  นี้ใช้การแก้ที่อนุมัติแล้ว ไม่ใช่ผ่อนเกณฑ์ใหม่ในการรันทดสอบ
- D20คง300s/600commands/book inputs≥3000 และ20min total cap; W1/W2/W3คง
  counts/duration/input denominator ตามprofileเดิม ไม่มีลดowner/rate/commandแอบแฝง
- TP/SL input-ready→start≤1s, snapshot p95≤250ms/p99≤1s, rebuild≤60s/owner,
  cycle/recovery bounds และ exact money/quantity/PnL/order/position assertionsเดิม
- Duplicate economic effects=0; queued exit identity/quantityไม่เปลี่ยนเมื่อretry;
  ไม่มีขายเศษเพิ่มเอง ไม่re-arm FAILEDจากdeploy ไม่อ้างเต็มcoverageเมื่อมีresidual
- ใช้ complete owned-pool inventory/loan return/disposal/error rules ตาม§15–16/22,
  ไม่ใช้initial+2แทน ไม่ยกเว้น errorจากผู้สังเกตแบบไม่มีหลักฐาน
- Preflightใช้ **§14 revision2**:120s,7samplesที่0/20/40/60/80/100/120,
  CPU idleเฉลี่ย≥20%,memory Normal/Warningยอมรับได้และCriticalปฏิเสธ,
  disk≥2GiBทุกsample,PostgreSQL/Redisพร้อมก่อน–หลัง,ไม่มีrestartวน
  ค่าขาด/ผิดรูปเป็นIncomplete; load1/5/15ใช้ประกอบ ไม่ใช้ load≤CPUเกณฑ์เก่า
- ห้ามตัดsampleช้า เพิ่มretry เปลี่ยนfault schedule/timeout หรือใช้เครื่องว่าง
  เป็นเหตุยกเว้นperformance; preflightผ่านไม่รับประกันworkloadผ่าน

## 4. ของเดิมที่จะใช้ซ้ำและขอบเขตเตรียม runner หากอนุมัติ

| ของเดิม | การใช้ |
|---|---|
| `backend/tests/infra/execution_market/profile_internal.py` | profile validation, isolation guard, bounded preflight และ protocol fixture |
| `profile_protections.py` ใน directoryเดียวกัน | controlled20 ผ่าน real worker; quantity/exit/cash/audit/replay assertions |
| `profile_workload.py`, `profile_parent_poll.py`, `profile_owned_pools.py` | existing workload supervision/poll limit/resource evidence |
| `profile_internal_restore.py`, `profile_restore.py`, `profile_restore_fixture.py` | restored DB routing, canonical/security equality, pending request และ exact recovery |
| `evidence/recovery-20261106/nc12-section22-w3/campaign-runner.py` | latest common archived wrapper รองรับ controlled/SMOKE/W1/W2/W3/overflow |
| `evidence/recovery-20261106/nc12-section23-w4/campaign-runner.py` + `campaign-support.py` | pinned W4 wrapper/support pattern; actual workerต้องอ่านtargetDB |
| `backend/tests/infra/risk_limits/profile_resources.py` | ใช้ atomic evidence publication บนmainแล้ว ไม่ย้อนcopywriterเก่า |

Archived wrappersมี absolute recovery ROOT,container namesและ `nc12_campaign`
import ที่อาจไม่มีแล้ว จึง **ห้ามรันไฟล์หลักฐานโดยตรง** หรือแก้ทับหลักฐานเก่า
หลังอนุมัติ A อนุญาตเตรียม wrapper สำเนาใหม่ที่ผูก repository rootจริง/importจริง
และระบุ service targetsของ fixture; คงค่าทำงาน/สูตรตัดสินทุกอย่าง ใช้ role URL
ของฐานใหม่เท่านั้น ไม่ retarget บริการที่เปิดให้เจ้าของใช้งาน
ไม่แก้ production code/API/migrations/DB contracts

ก่อน timing ตรวจ targeted tests ที่ wiringกระทบ (root/import/DB routing,
preflight invocation/ไม่เริ่มfixtureเมื่อfail, output-folder guard/cleanup);
ใช้ existing `test_internal_profile.py`, `test_environment_preflight.py`,
`test_restore_routing.py`, `test_owned_pools.py` และ
`backend/tests/infra/risk_limits/test_profile_resources.py` เฉพาะที่diffกระทบ
ไม่กำหนดยอด testขึ้นเอง ไม่มี full suite/lint/buildซ้ำหากไม่กระทบ
ถ้าแก้ wrapperให้รัน Ruff/format/mypy เฉพาะไฟล์ที่ตรวจได้ตามpatternเดิม
ถ้าพบว่าต้องแก้ production หรือเปลี่ยนแผน/กฎ ให้หยุดเสนอ amendmentก่อน

## 5. Execution boundary และการเก็บหลักฐาน

1. ก่อนเริ่มหลังอนุมัติ ยืนยัน source HEAD/diff/config/schema/contract/harness;
   ถ้า candidateใหม่มีdiffที่เปลี่ยนความเสี่ยง ให้ปรับ mapping/เสนอขอบเขตก่อนรัน
   คำยืนยันว่าเครื่องพักงานวันที่8ไม่ใช่หลักฐานสภาพเครื่องวันที่9 ให้เจ้าของ
   จัดช่วงทดสอบอีกครั้งก่อน timing ไม่หยุด process/container โครงการอื่นเอง
2. สร้างเฉพาะฐาน fixture local `tiewtrade_internal20_*` ด้วย roleและbootstrapเดิม;
   ตรวจempty/role routingทุกตัวและfreshsource/targetก่อนW4 ไม่ใช้ owner DB,
   ไม่คัดลอก credentials/session/accountเงินจริง ไม่ใช้Live/API keyจริง
3. Pin source inventory รวมไฟล์เพิ่ม/ลบ, HEAD+diff digest,dependency locks,
   configที่ไม่ใช่secret,actual schema revision/hash,pool/runtime flags,runner/support
   สำเนา+hashก่อนpreflight;ห้ามเดาว่าschemaยัง0065ตามcampaignเก่า
4. ใช้outputrootใหม่ทุกphase;เก็บ `preflight.json` ที่rootแยกจาก `run/`,
   manifests/results/analysis/resource/pool/faulttimestamps/final-tail/cleanup
   ไม่บันทึก cookie,token,secret,connection URL หรือคำสั่งที่มี credentials
5. Failed/Incomplete/Cancelledให้เก็บข้อมูลจริงและcleanupเฉพาะfixtureของงาน;
   ตรวจ0connections/0advisory locksทุกฐานและคืนborrowedresourcesครบก่อนรายงาน
   ถ้าcleanupไม่ครบให้รายงานค้างพร้อมชื่อfixture ห้ามอ้างว่าล้างแล้ว
6. **หนึ่งรอบต่อphaseเท่านั้น**: preflightไม่ผ่านหยุดก่อนworkload;
   phaseไม่ผ่านหยุดphaseถัดไปและรายงาน ไม่auto-retry/auto-fix/ลดเกณฑ์
   อย่าเปลี่ยนFailedเป็นIncompleteเพียงเพราะมีharnesserrorร่วมด้วย
7. จบAให้รายงานครั้งเดียวพร้อมcandidate/profile/results/runlinksหรือartifactlinks,
   เวลาและงานค้าง;ไม่เริ่มB/การทำรายการในบัญชีเจ้าของ/Git/deploy/Liveเอง

## 6. การตรวจหน้าจอเจ้าของและด่านที่ยังไม่รวม

| งานค้าง | ขั้นถัดไป / ผลที่ปิดได้ |
|---|---|
| MF-13หน้าจอหลังแก้ | นัดเจ้าของยืนยัน warning/table/รายละเอียดquantityอ่านได้ โดยเริ่มจากread-only;ประมาณ5–10นาทีเมื่อappพร้อม ไม่จำเป็นส่งBUY/SELL/STOPหรือเปลี่ยนMANUAL→BOTเพื่อยืนยันหน้าจอ ห้ามนับแทนwholemanualacceptanceโดยอัตโนมัติ |
| IP-V3/IP-V9 opening | ตรวจactualAPI/worker/source/stopauthority/accessตามapprovedopeningprofileและคำสั่งเปิดจริง;ยังไม่รวมA/B ไม่เปิดsignupหรือเปลี่ยนaccess/gatesจากแผนนี้ |
| V-18 original100/4h | Pending Full Validation ตามapprovedReleaseprofile ไม่ใช้AหรือshortW3แทน4h;ไม่รวมเวลานี้ในA/B |
| V-19 bot/notifications | Pending Dependency F20/F21+channels;ยังไม่ประเมินเวลารวมก่อนdependencies/criteriaครบ |
| V-20 Live/reconciliation | Pending Dependency F22–24;ใช้fixtures/FakeVenueสำหรับautomatedvalidation ห้ามส่งLiveorder |

## 7. Checklist ผลตรวจและการอนุมัติ

| เกณฑ์ของแผนนี้ | ระยะ | สถานะเมื่อจัดแผน |
|---|---|---|
| A readiness/runner/isolation/static ก่อนtiming | Feature | Not Run — รออนุมัติและตรวจenvironment |
| A1 controlled20 lifecycle/ทุกowner≤1s | Feature ตามcontrolledprofile | Not Run on this campaign |
| A2 D20 count/financial/timing/resourceครบ | Batch | Not Run on this campaign |
| A3 W4 realrestore/sourceunchanged/RLS/exactretry/exit | Batch | Not Run on this campaign |
| A4 identity/result/cleanupพร้อมremaininggates | checkpoint | Not Run — มีเพียงแผน |
| B1–4 load/fault/snapshot/stability | Batch | Pending Full Validation; ไม่รวมA |
| MF-13 ownervisual confirmation | manual checkpoint | Partialเดิม;รอเจ้าของ |
| F17 V-18/19/20รวม | Batch/Release | Partial / Failed / Pending Dependency ตามหลักฐานเดิม |

**การตัดสินใจที่เสนอ:** อนุมัติ **A** (เตรียมwrapperจำเป็น+targetedchecks แล้ว
controlled20→D20→W4 อย่างละหนึ่งรอบเมื่อด่านก่อนผ่าน จากนั้นหยุดรายงาน)
คงBและReleaseไว้พิจารณาตามผล ไม่commit/push/PR/merge/deployเอง
หรือเลือกBรวมAหากต้องการช่วงเวลาต่อเนื่องที่ยาวขึ้น โดยยังหยุดเมื่อphaseใดล้ม

AGENTS.md “จุดที่มี [เจ้าของอนุมัติ] คือจุดหยุดจริง” และ approved NC12§5
กำหนดหยุดหลังphaseล้ม จึงต้องอนุมัติขอบเขตรอบใหม่ก่อนเตรียมwrapper/รันcampaign
วันนี้ทำเฉพาะแผน ตรวจลิงก์/ความสอดคล้อง/diff ไม่รันtestsหรือเปิดระบบ
ขั้นถัดไป:เจ้าของเลือกอนุมัติAหรือB;คำสั่งเริ่มข้อ3ยังไม่ใช่อนุมัติexecution

## Approval/execution record — 2026-11-09

Owner answered approve to recommended A. Preparing new runner copies under backend/tests/infra/execution_market, retaining archived evidence intact. New ROOT resolves this worktree; W4 imports its actual current support module. Effective environment and test/campaign outcomes remain unclaimed until observed. No B/Git/deploy/Live authorization.

## Execution outcome — 2026-11-09

[Approved A checkpoint](evidence/remaining-paper-20261109/checkpoint.md): controlled20 Passed (max0.255965s,20/20 owners); D20 workload600commands/financial/p95-p99 passed but campaign Incomplete due final1connection. Later post-exit cleanup0/0 and fixture removal recorded separately, not a passing replacement. W4/B Not Run. Stop rule applied; no timed rerun or runtime failure fix. Next requires owner decision on [cleanup diagnostic proposal](remaining-paper-cleanup-diagnostic-proposal.md).

## Superseding scoped replacement checkpoint — 2026-11-09

Owner separately approved D20 identity replacement and conditional W4. [Current receipt](evidence/remaining-paper-20261109/identity-replacement-checkpoint.md) records both Passed, completing this scoped A evidence refresh with retained controlled20 proof. Original first-A stop/Incomplete is historical and unchanged, not overwritten. B/full Release/manual/opening/dependency gates remain pending. No further timed work authorized in this completed scope.

## Continuous Paper completion execution — 2026-11-14

สถานะ: Owner requested completion of Paper verification without intermediate approval prompts.
This authorizes resuming existing Paper validation, retaining all criteria and
Live/owner-account restrictions. Engineering decisions use delegated authority in
AGENTS.md. This new execution instruction does not rewrite historical approvals.

Candidate main 98152fa; isolated validation/f17-paper-completion-20261114 worktree.
Map retained evidence against current source/config/schema, then run affected
isolation/preflight/cleanup tests. Prepare a private campaign-runner copy changing
only ROOT and disposable Redis-container binding. A dedicated Redis fixture is
required because the former fixture now serves the owner preview; W3 must not
pause it. Reuse the installed image on a localhost-only port, without a volume.
All economic mutations use generated tiewtrade_internal20_* DBs, never owner DBs.

Conditional sequence: controlled20/D20 refresh where source mapping shows an
impact, B1 W1, B2 V2 W2, overflow, B4 V3 short W3, affected W4. Preserve fixed
profile/thresholds/faults and seven-sample preflight, source binding and cleanup.
A failed phase stops later timed phases; bounded engineering diagnosis/fixes may
proceed under delegation, without blind retries. Unsafe financial results and
three unsuccessful same-criterion attempts retain mandatory stop rules.

Separately assess approved original100-account/4h composition and actual opening/
manual gates. Internal20 success cannot close those gates. Do not claim whole
Paper acceptance or manufacture owner acceptance from fixtures. Preserve all
prior Failed/Incomplete results; record measured durations, cleanup and blockers.

### Identified original-profile wiring gap and engineering approach

Evidence: profile_workload.py creates authenticated intake and PositionChecks only
when internal.validate returns a selected internal20 phase. The default100-owner
path lacks both and cannot establish the approved integrated100 acceptance.
Reusing default100 unchanged would produce the wrong evidence. D20 source remains
frozen; no implementation change will occur during that running campaign.

After D20, if its gate passes, reuse that same opt-in composition for an explicit
PAPER_RELEASE100_V1 harness selector, retaining existing internal20/default paths.
Use original approved counts: diagnostic100x6cycles/3000commands/10s^-1/300s;
W1 100x36/18000/10s^-1/1800s; W2 100x120/60000/100s^-1/600s;
W3 100x282/141000/10s^-1/14400s with unchanged seven-event original schedule.
Twenty workers/R8/coordination/heartbeat/poll4/final-tail are the already approved
integrated composition. No strategy, API or production defaults are changed.
Retain release processing250ms/1s, original resource contract (including initial+2
connections), snapshot250ms/1s, replay60s, exact economics and all cleanup rules.
Add strict profile/wiring/default-isolation tests and real-DB HTTP/snapshot tests
before timing. Reuse existing fault, pool and restoration proofs where unchanged.
This is the authorized consolidated plan's missing harness, not a relaxation or
an assertion that a new profile name itself closes acceptance. Internal20 and
original100 results remain distinct. Execution order may prioritize the100-owner
diagnostic after readiness to reveal release blockers before spending on B;
no later phase is started on a failed gate. No owner financial activation.

### Original100 diagnostic gate — Failed; bounded SQL diagnosis

First original100 diagnostic completed3000/3000 commands and all economic,
resource/owned-pool/cleanup assertions. Engine p95=285.665ms exceeded250ms;
p99=386.307ms passed. Failed retained; no W1 starts. Per-minute p95 rose from
275ms to311ms, with no recorded lock waits, but current evidence contains only
whole-transaction durations and cannot distinguish SQL, pool, commit or process
scheduling. Do not infer a specific root cause or change production/SLA from this.

Use existing profile_diagnostics/TransactionTrace once on the same original100
SMOKE fixture/configuration with diagnostics=True, fresh DB and new output root.
This is diagnostic-only (existing diagnostic-only.json acceptance_result=False),
not a replacement acceptance run. Preserve all timeouts/counts and the1200s cap,
existing bounded allowlisted SQL fingerprint/timing, runtime and pool observers.
Record instrumentation overhead; do not use its latency as uninstrumented
acceptance. Estimated10–20min includingpreflight/setup/cleanup. No source/money/
API/gate change. This is necessary engineering diagnosis under owner delegation
and current continuous-work instruction, not blind retry or relaxed acceptance.

### Scoped performance correction — accounting reads without reset presentation

Completed diagnostic-only observation758.091s;3000/3000 commands, all financial/
pool/cleanup assertions Passed; instrumented p95/p99=302.040/437.362ms. Retain
both Failed aggregates; no W1. SQL timing identifies4800full-wallet reads costing
59.38s, and repeated reset-readiness calls, while processing-pool p95 wait6.47ms.
The wallet query always evaluates paper_wallet_reset_readiness, computing UI-only
reset eligibility. Worker and risk _scope use only accounting/identity fields;
get_wallet separately validates active episode, complete capital ledger and typed
ledger balance. Reset readiness is not a financial admission predicate at either
caller; it only populates reset_available/reset_reason. Existing manual held/
reserved and position-readiness checks remain mandatory and unchanged.

Chosen minimal correction: add include_reset_readiness=False opt-in to get_wallet,
used only by order worker and risk _scope. DefaultTrue retains complete existing
API/reset behavior. Both paths query current active identity and the full ledger,
validate exactly one external-capital entry, currency/capital consistency and
compute balance through existing Money helpers. No snapshot caching/reuse across
calls, transaction/lock changes, new infra, schema or financial rule. Lightweight
result always reset_available=False/reset_reason=ACTIVITY_UNKNOWN, so absence of
presentation proof can never grant reset. All actual reset/wallet/public callers
keep defaultTrue. Do not skip held_and_reserved or position/risk/STOP guards.

Before another acceptance run: real-DB accounting parity/default reset/owner
isolation tests; missing-ledger rejection in both paths; relevant wallet, risk,
manual-admission, worker, concurrency/idempotency/STOP/protection safety tests and
scoped static checks. Review changed callers and financial guard equivalence.
Then one fresh original100 uninstrumented diagnostic with unchanged250ms/1s and
all earlier counts/timeouts/cleanup; source-freeze receipts required. If it passes,
continue conditional approved phases. This correction uses delegated engineering
authority/current owner continuous-work instruction and retains historical failures.
It is not a relaxation of safety, accounting checks or performance acceptance.

### Replacement result: cycle failure; classification and bounded follow-up

Accounting candidate uninstrumented acceptance attempt2 stopped at a real60s
cycle deadline:557offered/admitted,457completed,41/600cycles;no rejection/worker
exit. Full financial/final-tail verification NotRun. Raw aggregate Incomplete,
731.710s; source unchanged, cleanup0/0 and fixture removed. Retain raw result;
acceptance cycle criterion Failed. Host maxload16.25,RSS780MiB,lockwait samples0,
connections≤60; these observations do not establish an infrastructure root cause.
No performance improvement or causal regression is established. No W1 starts.

Accounting/reviewed-safety tests178passed remain correctness evidence; do not ship
or declare the performance change accepted from them. Two uninstrumented100
acceptance attempts have not passed; the intervening instrumented observation is
explicitly diagnostic-only, not an acceptance attempt. No blind acceptance rerun.

Necessary harness correction: distinguish proven cycle-budget expiry from nested
transport TimeoutError/cancellation, classifying the former Failed while keeping
60s and existing cleanup. Preserve old raw Incomplete as historical. Reuse existing
owner/order cycle timeline and post-stop queue snapshot for one diagnostic-only
observation on the accounting candidate. The earlier diagnostic observed only the
pre-change p95 failure; it cannot explain this new post-change deadline failure.
Keep100owners/2000baseline/3000commands/300s,20min cap, fixed source and all safety
assertions. Observer overhead is not acceptance. No new timeout/retry allowance,
production change or later phase. Add deterministic expiry/nested-timeout/cancel
regressions and existing observer/classification checks before this observation.
Only after a supported fix and safety checks may a third acceptance attempt be
considered under the current continuous-work instruction; a third unsuccessful
acceptance gate retains AGENTS mandatory stop/options rule. Do not conflate
profiling with acceptance to claim a pass or suppress any historical failure.

### Follow-up profiling outcome and final bounded correction

Post-change profiling completed3000/3000, all financial/pool/resource/cleanup
Passed; no cycle timeout reproduced. Instrumented p95/p99=285.513/424.358ms.
Retain Failed diagnostic; no acceptance pass and no timeout root-cause claim.
Parent pool-wait p95≈9–15ms for measured submit/poll paths; no pool expansion
justified. Remaining repeated full reset-readiness evaluation occurs in cash fill/
correction get_wallet calls (only balance consumed), and held_and_reserved (needs
only position readiness, not reset/order eligibility). Current100 throughput is
still unaccepted. Do not change rate/counts, pools, SLA, timers or strategy rules.

Final minimal extension under delegated engineering authority:
1. Cash linkage/correction uses existing accounting-only wallet option; full ledger,
   active episode, exact cash effect/negative balance, position/receipt/fence and
   audit checks remain identical. Reset fields are not consumed at those callers.
2. Worker supplies its already decoded, complete position snapshot to the existing
   manual-policy/held-reserved helper. API/default callers retain original full
   readiness function. Optimized path checks snapshot owner/episode/PAPER/READY/
   nonnull proof and rereads current activity availability/revision/sequence/proof
   in the SAME SQL snapshot as the existing actual held/reservation quantities;
   any mismatch is rejected. No numeric value is taken from a cached snapshot.
   Worker holds the existing owner wallet lock across snapshot/read/policy, with
   no intervening position mutation. Snapshot decoder already verifies record/max
   sequence, pair/projection counts and every projection revision/last sequence;
   these proofs are not omitted. No cross-request/process cache or new grants.
3. RealDB equivalence/current-source/stale/wrong-scope/unavailable tests, accounting,
   fill/correction/replay/atomicity/concurrency/manual/risk/STOP/protection tests and
   scoped static checks before the third uninstrumented acceptance attempt. Reuse
   unaffected existing proof; no further profiling campaign just for confidence.
If the third acceptance gate is unsuccessful, stop timed work and offer concrete
options per AGENTS; preserve both profiling runs and both earlier acceptance runs.
No W1/W2/W3/W4 before original100 diagnostic passes and no owner activation/Live.

Final extension implemented: fill/correction use accounting-only wallet reads;
manual worker passes its decoded snapshot into held/reserved with owner/episode/
mode/readiness/proof and current revision/sequence/proof recheck in the same SQL
as actual financial quantities. API/default path remains unchanged. Final safety
suite:190 Passed,1 new fixture failure (writer protocol marker omitted, TT015);
corrected fixture only, all9 holdings cases then Passed on a new isolated DB.
Ruff/format/mypy affected5files Passed. Other accounting178 and cycle109 tests
retained where unaffected. No financial/cache/pool/SLA/schema/grants change.
Third final uninstrumented original100 SMOKE starts only after these checks;
preserve both earlier acceptance attempts and both diagnostic-only observations.

### Final attempt3 receipt / mandatory timed-work stop

Original100 SMOKE Failed:CycleBudgetExceededError,2939offered/2937admitted/2880
completed,541cycles; full financial/snapshot oracleNotRun.748.252stotal,source
unchanged,cleanup0connections/0locks,DBremoved. Partialp95/p99=262.598/474.016ms
not acceptance. Interrupt while waiting parentpollpermit does not establish
root cause; individual measured gate waits≤2.443s.191unique final safety cases
Passed after correcting writer-markerfixture; scopedstatic checksPassed.
Three unsuccessful uninstrumented attempts reached AGENTS stop/options bound;
no further timedphase/automaticrerun/publication. See current checkpoint for
recommendation and alternatives. All historic failures/scopes remain retained.

### Failure-only timeline amendment — owner instruction 2026-11-14

Owner instructed "เริ่มทำ" after the three-attempt stop and proposed timeline
investigation. Implement a bounded diagnostic selector, reusing parent_observations
and scanner post-stop queue evidence, without full parent/worker transaction trace
or additional DB/resource samplers. Existing acceptance/default execution remains
unchanged. No production modification in this amendment, no new infrastructure.

Within each in-flight cycle retain the existing32phase limit and at most32query
fingerprint aggregates (counts/durations/type-only outcomes; no SQL text, parameters,
row contents, cookies or keys),16recentquery timings and total query count. Completed
cycle records are discarded; only real expired budgets persist. Keep60s, cancellation
and inner timeout semantics unchanged. Reuse existing per-owner poll JSONL and
worker latency files; at failure collect bounded tails after workers stop and the
existing read-only queue snapshot. Mark all observed results diagnostic-only, even
if the workload succeeds; never substitute these for a release acceptance pass.

Test deterministic success/expiry/inner timeout/sibling cancellation, late-cycle
retention, query/phase bounds, parameter/error redaction, restoration on failure,
post-stop reads and evidence errors preserving the original failure. Reuse realDB
scanner checks; scoped Ruff/format/mypy. Then permit one original100 SMOKE diagnostic
on a fresh local fixture with preflight/source pin/1200s total cap (about12–15min),
with this selector only. Preserve three acceptance failures; no fourth acceptance,
W1 or automatic retry from this permission. Stop/report after this observation;
any supported correction must be documented and safety-verified before acceptance.

Failure timeline pre-run checkpoint: initial isolated suite completed with six
legacy mocked-Namespace failures because the new CLI flag was absent. Corrected
optional flag reads to defaultFalse, preserving old programmatic runner inputs;
all33 failure-timeline/review regression cases thenPassed. Existing realDB scanner/
worker diagnostic cases and release composition passed in the isolated suite.
Scoped Ruff/format/mypy4filesPassed (mypy uses MYPYPATH=src for typed source).
Malformed worker timing is rejected type-only; evidence-write errors cannot mask
the primary cycle failure. No production changes this amendment. One bounded
failure-only diagnostic now starts, not a fourth acceptance attempt.

Failure-only observation completed671.267s,preflight7/7,sourceunchanged,cleanup0/0/
DBremoved. Reproduced60scycle failure with1061completed; complete boundedtimeline
and post-stop queue captured. Diagnostic-only, not a fourth acceptance attempt.
See failure-timeline-checkpoint.md under evidence/paper-completion-20261114 for
results, corrected metadata flag, limits and proposed next scope. Stop/report
reached; no automatic rerun or production scheduler/pool/timeout changes.

### Continuous completion / timing separation — owner instruction 2026-11-14

Owner requested continuous completion and adjustment of criteria if more than two
attempts remain unsuccessful. This supersedes the previous one-observation stop
for the following engineering scope; no routine approval stop between these steps.
Retain all old Failed/Incomplete and diagnostic-only results. It does not authorize
waiving economic/security correctness or creating unspecified bot/Live features.

First distinguish confirmed worker transaction completion from parent observation.
Reuse the existing test worker transaction wrapper and process_claimed_order alias;
add opt-in observer only in original100 SMOKE failure-timeline mode. After processing
read only command/order/status/result identities with the existing owner session;
record bounded type-only metadata after the existing transaction exits successfully.
An uncertain/failed commit must never be labeled confirmed. Log monotonic timestamps
from the same Python runtime, no credentials/SQL/payload/financial amounts. Parent
phase end identifies first successful receipt/status observation. Join exact scoped
identities/statuses offline; server row timestamps are NOT commit timestamps.
Observer adds one read per processing transaction: diagnostic-only, never acceptance.

Deterministic transaction success/rollback/uncertain commit and observer restoration,
redaction/bounds/CLI propagation tests plus realDB committed visibility/rollback tests
before one bounded original100 diagnostic (preflight,1200s cap,~12–15min). Then choose
only a supported engineering correction, document before source edit, safety/static
checks, and at most two checks of that correction before reevaluating timing criteria.
Owner permits evidence-based timing/profile amendments without another routine ask;
record exact revised thresholds and their rationale BEFORE applying, keep old grades
and parallel original-threshold measurements, negative boundary tests, no dropping
slow samples or subtracting overlapping waits. Do not loosen duplicate/money/quantity/
position/risk/precision/authorization/recovery correctness. If safe rationale cannot
be established, report the unresolved limitation rather than manufacture a pass.

After a valid diagnostic gate continue approved W1→W2/overflow→W3→W4 with individual
preflight/cleanup, original economic oracles and conditional progression. No production
activation, owner-account orders or Live; no Git publication without its review/CI gates.

Timing separation implementation checkpoint:147targeted casesPassed, including
realDB committed visibility/rollback, uncertain commit, bounded recorder, CLI
propagation/restoration and matching lower/upper confirmation bounds. Ruff/format/
mypy4affectedfilesPassed. Record only5000workerrows/process and10000firstobservations
perSMOKE; all persisted identities/statuses whitelist only. No production changes.
One fresh original100 diagnostic starts with the same60s/250ms/1s criteria recorded,
all results diagnostic-only. Server commit is bracketed between status read and
client confirmation; negative observation gaps and ambiguous deadlines preserved.

### Timing separation result and representative polling correction

Commit diagnostic FailedCycleBudgetExceededError;818.323stotal,sourceunchanged,
cleanup0/0/fixtureDBremoved.2464offered/admitted,2364completed,433cycles,fullfinal
financialoracleNotRun.17071confirmedworkerrows;2873matchedobservations,930missing.
Receipt1920matches: observationgapmedian166ms/p95404ms, workerconfirmation-minus-
receiptwait-startp9510.528s. This demonstrates admission/queue delay dominates
receipt observation, not a60sindividualpollwait. Fill930matches are missing because
one claimed command can advance other orders in the pair; current observer sees
claimed order only. Do not use missing fills to prove fill commit timing or accept
financial correctness. No repeated profiling merely to obtain complete fill timings.

Supported harness correction under continuous owner authority: foreground request
receipt uses1s in frontend/src/ManualRequestStatus.tsx:37 and useDurableAttempt.ts:42;
existing harness polls the same pending result and single-order status every250ms.
The measured expired cycle had149pollattempts/22.127s gatewait in previous trace,
so high-frequency status observation is an identified competing load. This does
not prove all page traffic is lower; other risk/protection/STOP reads remain separate.
Add explicit observation_poll_seconds=1.0 for original100 campaign, retaining250ms
as default/historical configuration. Reuse ParentPollGate, same4 permits and same
actual queries/RLS/60s positivecycle/recovery/250ms-1s/resource/economic assertions.
Delay is counted, never subtracted. No extra retry, suppressed samples or worker/API
change. Snapshot/recovery sampling cadence and financial oracle stay unchanged.

Test default/explicit polling cadence and invalid options, unchanged60s failure,
no sleeping with a connection/permit checked out; scopedstatic and existing poll/
workload regression. Then one original100 uninstrumented acceptance check on fresh
fixture/preflight/1200s cap; no commit observer/full traces. If still unsuccessful,
use owner's >2 unsuccessful-round authorization with retained three original
acceptance failures and current diagnostics to document the smallest timing
amendment BEFORE applying it; do not blindly repeat unchanged workloads.

Representative-poll pre-run check:103targeted poll/gate/default/final-tail/cycle/
release/reviewregressionsPassed, including realDB proof reused by release composition;
Ruff/format/mypy4filesPassed. Explicit1.0s observation cadence recorded in manifest
and gate receipt; historical/default250ms unchanged. No processing/cycle/recovery/
financial threshold changed. Next fresh original100 uninstrumented SMOKE has no
commit/timeline/SQL observer; previous diagnostic/acceptance failures retained.

### Polling correction Passed; transient maintenance cleanup evidence

Uninstrumented original100/poll1s workload Passed3000/3000,600cycles,1200fills,
600cancels/replays,enginep95/p99=170.827/236.244ms,323.881s measured,allfinancial/
resource/owned-pool assertionsPassed. Original250ms/1s/60s criteria unchanged.
Initial campaign rawIncomplete:cleanup snapshot saw PostgreSQL autovacuum worker
with roleNULL (no application connection/advisorylock); validator raisedValueError.
Follow-up strict identical query at1001.869s conservative total (<1200) found0/0;
fixtureDB dropped normally. Preserve initial rawIncomplete and append follow-up,
not rewrite it as Passed. Complete workload plus within-budget strict cleanup is
valid evidence for progressing; no repeated fullSMOKE for cleanup-only code.

Necessary harness correction before W1: recognize nullable role ONLY for explicitly
identified PostgreSQL autovacuum worker. Its nonzero connection count still fails
cleanup. If and only if every remaining backend is that maintenance type and locks0,
recheck read-only at1s up to10s, saving bounded separate observations. Any application
backend, malformed identity, advisorylock or persistent maintenance must remain
Incomplete immediately/atbound. Never terminate a backend, ignore it in finalcounts,
retry a financial command or relax exact0connections/0locks. All cleanup time stays
inside the phase envelope and SMOKE1200s cap. Deterministic transient/persistent/
client/malformed/cancel tests and existing realDB identity/primary-error preservation
checks before proceeding directly to W1; reuse unaffected workload proof above.

Cleanup correction45affected testsPassed, scopedRuff/format/mypyPassed; private
launcher also applies identical bounded autovacuum-only wait before normalDROP.
Initial test launcher retained its DB for transient maintenance (testcasesPassed);
independent0backend check and normaldrop thencompleted. No application leak hidden.
Uninstrumented100SMOKE workload+strict within-budget cleanup followup closes entry
gate; no financial/performance rerun for cleanup-only changes. Next W1 then conditional
W2/overflow/W3/W4 under original100 counts,250ms/1s,cycle/recovery60s and4hW3.
No timing threshold relaxation is currently needed or applied.

Approved TIMING_V2 implemented before next run;223targeted contract/profile/gate/
cycle/cleanup regressionsPassed (including actualDB release composition), scoped
Ruff/format/mypy5filesPassed. Default profiles and original threshold grades
retained; aggregate cycle report records completed/interrupted/max/over60s and
original/revised grades. Fresh revisedSMOKE→W1→W2/overflow→W3→W4 conditional chain
now begins, no further owner approval stop. No production code changed this amendment.

R2 consistency amendment recorded before grader change: final ordinary workflow
allowance60→90s for TIMING_V2 only; targetnominaldurations, recovery/tail60s unchanged.
22focused boundary/timeout cases and scopedstatic3filesPassed. Complete R1SMOKE
reused by separate r2-regrade.json: all15independent conditionsPassed, rawFailed
retained;369.355s fits390s newbound, original360s and250ms/60s stillNotMet. Source
inventory comparison shows ONLY3post-measurement grader/test paths changed; no
production/schema/dependency change. No new execution fabricated or failed file
rewritten. Before W1 rerun controlled20 once on current production accounting-read
candidate (initial controlled20 predated those source changes), preserving original
TP-SL trigger/safety criteria. Then conditional R2W1→W2/overflow→W3→W4; no extraasks.

### Complete HTTP observation cadence correction — 2026-11-14

During R2W1 read-only review found profile_http.HttpIntake.request still slept the
legacy250ms while waiting for durable transfer, despite gate.poll_seconds=1s for
command/status reads. Earlier polling correction missed this caller. HTTP request
frontend actually polls at1s, so this is incomplete implementation, not new business
or safety criteria. Own R2W1 was interrupted via exact-PID SIGINT; rawIncomplete/
CancelledError retained, no finalfinancialoracle claimed. Normalcleanup0/0 and DBdrop
confirmed; no other process/service stopped. No threshold change from this finding.

Before source edit: reuse a single poll_interval(gate,legacy_default) helper in
profile_parent_poll for command, status AND HTTP transfer waits, using existing
4permitgate and outside-session sleep. Default250ms preserved, explicit1s applies
consistently. No POST retry/key replacement, no API/worker/order changes, same60s
inner timeout and R2wholecycle90s. Extend existing HTTP no-retry/redaction/identity
fixture with pending-transfer and default/250ms/1s cases, assert GET permit use and
sleep outside permits. RealDB HTTP auth/CSRF/ownerisolation, relatedpoll/gate/cycle/
profile tests and scopedstatic; then fresh R2W1, conditionally laterphases. Retain
SMOKE/controlled20 proof because neither uses HTTP transfer polling; no needless rerun.

HTTP cadence completion checks: initial combined112cases had109Passed and3pending
mockcasesFailed because fake GET incorrectly returned202 instead of actual API200.
Corrected fixture status only; all15HTTPno-retry/redaction/pollcadence casesPassed,
then all21HTTPcasesPassed including realDB default and explicit1s auth/CSRF/owner
isolation. Other109proof retained;113unique affected casesnowPassed. ScopedRuff/
format/mypy4filesPassed. No productionchange or further criterion change. Reuse
controlled20 and R2SMOKE proof (HTTPtransfer absent there), start freshR3W1 on same
TIMING_V2/R2criteria, then conditional W2/overflow/W3/W4. No automaticretry of old
uncorrected workload, oldIncomplete/Failed results retained.


### R3 result / approved internal capacity continuation

R3W1 FailedCycle90 after12341/18000completed,2431cycles,1999.601s total;
HTTPpoll1s confirmed. FinalfinancialoraclesNotRun. No workercrash/rejection; strict
cleanup0/0 and normalDBdrop. [Disposition](paper-timing-acceptance-amendment-20261114.md)
records BEFORE next execution: finish existing NC12internal20SMOKE→W1→V2W2/
overflow→V3shortW3→W4, preserving all existing criteria, freshDB/preflight/hashes.
This is internal checkpoint only, not acceptance of failed100-account release or
F17Completed. Current controlled20 and unaffected safety proof retained. Original
20SMOKE predates affected production/HTTP paths; refresh before W1. No owner orders,
Live, source/runtime change or implicit publication authorized by this disposition.


### R4 bounded public-reader cancellation / local burst5

W1internalPassed3600 and all20oracles/cleanup. W2Failed with complete12000monetary
proof; elapsed1645.305>1260, p95508.348>500ms and4unproven public-reader cancellations.
RawFailed retained; cannot waive unknown resource errors. BEFORE source edits,
[R4 amendment](paper-timing-acceptance-amendment-20261114.md) records read-only pricepool,
actual expired-timer provenance, narrow expected-cancel classification with all return/
leak/error guards retained, and explicit6000commands/5s^-1/20min local profile (old
10s^-1 unchanged). Negative and real-DB tests/static first, fresh burst5 then conditional
overflow/shortW3/W4, no further routine approval stop under latest owner instruction.


R4 checks complete before timing:168Passed/2initialSkipped; followup86Passed/no skips,
including both dedicated-Redis guards, actual expected-deadline handling, unchanged
external-cancel/borrow-leak/unknown-engine rejection, same physical pool/read-only
facade with writable WS auth and all prior5WSregressions. Scoped7fileRuff/format/mypy
Passed. Two initial targeted source errors (wrong import; overly broad readonly
engine) were corrected; failed outcomes retained in amendment, their first raw test
logs were overwritten by the replacement test log (not reconstructed). All timed
Failed/Incomplete artifacts remain intact. Latest facade/followup logs retained.

Fresh burst5W2→overflow→V3shortW3→W4 now authorized under R4/latest owner instruction,
new per-phase source/runner hashes/fresh fixtures/preflight/cleanup. Cash/position/
policy production hashes unchanged; current controlled20/W1 monetary proof retained,
real HTTP/session/WS regression covers the narrower reader-only API change. Normal
500ms/2s,60s workflow/final-tail, pool return and money/source/STOP rules unchanged.
No code edits during timing. No100/4h/F17Completed or Git publication claim.


## Execution closed at local internal checkpoint — 2026-11-15

[Final evidence](evidence/paper-completion-20261114/final-checkpoint.md) records all
R4conditional phasesPassed, earlier controlled20/SMOKE/W1 retained with explicit
source-reuse mapping; zero task-owned DB sessions/locks, normalDBdrops and exact-label
Redis removed. Local conditional execution finished, not release/Completed. Original
100/4h and20W2 failures unchanged; review/required CI/opening/dependencies pending.
No further timed rerun justified without a named impact. No owner financial/Live/Git.


## R5 consolidated review corrections — 2026-11-15, before source edit

Owner instructed starting the proposed consolidated review. Engineering corrections
use existing delegation; no financial/rate/safety or production change in this step.

Medium: profile_commit_observation.begin reads connection.info in a finally block.
A reproducible no-DB fault (unreadable connection.info and primary ValueError) raises
secondaryRuntimeError instead of preserving the primary. Guard metadata retrieval,
retain primary exception/cancellation and annotate only exception type; never claim
confirmation if metadata cannot be retrieved. Keep diagnostic hooks restored. Also
preserve primary cancellation if observe_workload observer teardown fails (existing
branch exempts CancelledError and can mask it). Add deterministic error/cancel,
metadata-only failure, hook restoration and observer teardown regression cases.

Medium audit finding: remaining_paper_campaign manifest authorization describes
both revised100 and burst5 with old250ms/10s^-1 prose. Bind authorization to the actual
known profile and approved document, with effective parameters in existing structured
manifest/results; do not duplicate quantitative criteria in prose. Reject unsupported
phase/profile pairs (including W2-only burst5 used asCONTROLLED20) before output or
preflight. Existing valid commands/criteria unchanged. Test revised/original/legacy
metadata, unknown profile and early CLI rejection.

Run the smallest affected diagnostic/commit/campaign/profile unit/regression groups
and scopedRuff/format/mypy. Real monetary/readonly/WS and completed campaigns remain
valid: these are diagnostic-only failure paths and manifest/invalid-input changes;
prove current backend/src hashes unchanged and record harness-only source bridge.
Do not rewrite original manifests or grades; add correction notice for their stale
human authorization strings, retain structured parameters/actual results. No timed
rerun, owner/Live actions or Git publication in this correction. Refactor still
requires the separate owner instruction in AGENTS.md after review/fixes.

R5 execution: four findings corrected (threeMedium, oneLow),139targeted tests including
realPG commit/rollback Passed; six-file Ruff/format/mypy and whitespace checks Passed.
All backend/src hashes unchanged from R4. No workload repeated, historical grades or
artifacts rewritten. [Review/correction notice](evidence/paper-completion-20261114/review-r5.md)
and source bridge recorded. Next owner refactor instruction, then publication gates.

## R5 owner-authorized refactor — 2026-11-15

Owner explicitly instructed `refactor the code`. Keep behavior/contracts unchanged:
flatten the newly added campaign CONTROLLED20 guards; replace commit-observation's
nested deadline classification conditional expression with named local state and
ordinary branches; move the new teardown test's contextmanager import to module
imports. Reuse existing parametrized commit-boundary/rollback, cancellation and CLI
regressions; no new abstraction or financial-source change. Run the affected existing
test modules with scoped Ruff/format/mypy, verify backend/src inventory unchanged and
reuse completed acceptance evidence. No timed workload, publication or Live actions.

R5 authorized refactor executed: three-file control-flow/import simplification,
139targeted tests Passed in7.22s/no skips; Ruff/format/mypy and whitespace Passed.
Backend production hashes unchanged; no timed repeat needed. [Checkpoint](evidence/paper-completion-20261114/refactor-r5.md).
Next owner Git instruction; requiredCI/publication and existing Release gates pending.
