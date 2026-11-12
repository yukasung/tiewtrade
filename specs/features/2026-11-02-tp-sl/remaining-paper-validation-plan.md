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
