# F-19 — ปุ่มหยุดบอท (Kill Switch) — Plan

สถานะ: **Approved 2026-10-31** — รวม deep-review fixes R1–R7
วันที่: 2026-10-31

## 1. แนวทางและขอบเขต

สร้าง stop authority กลางที่บันทึกสาเหตุแยกกันและคำนวณผลรวมแบบ fail-closed
แล้วให้ F-18 loss stop, ปุ่มผู้ใช้, system stop และ platform stop ใช้ authority เดียวกัน
แต่ละ cause มี identity/revision/cutoff ของตัวเอง การเปิดกลับปิดได้เฉพาะ cause ที่ผู้ใช้
เห็นและยืนยัน จึงไม่ล้าง loss latch, platform stop หรือ stop ครั้งใหม่โดยบังเอิญ

API บันทึก immutable STOP intent และ audit ใน transaction เดียวก่อนตอบรับ STOP intent ที่ commit
เป็น authoritative fence ทันทีโดยทุก opening path อ่านจาก committed intent โดยตรง ส่วน engine
เป็นผู้เขียน applied result/projection, RESUME และ order effects; RESUME intent ยังไม่ปลด fence
จน engine ตรวจ proof/revision แล้ว commit applied result Platform stop ใช้ global lock/fence
ก่อนตอบรับ แล้ว engine ค่อยค้น owner/targets แบบ bounded; การค้นยังไม่ครบต้องแสดง STOPPING
และ opening ถูกบล็อกจาก committed fence อยู่แล้ว

Paper ทำ execution จริงใน F-19 ส่วน Live, bot lifecycle และช่องทางแจ้งเตือนภายนอกทำเป็น
typed integration contracts ที่ fail-closed ตาม NC-F19-03 ไม่มี Live order ในงานนี้

## 2. ของเดิมที่จะใช้ซ้ำ — สำรวจ source แล้ว

| ของเดิม | ใช้อย่างไร |
|---|---|
| `core/risk_limits.py::RiskStopProgress/RiskScope` | ย้าย progress enum เป็น shared contract พร้อม compatibility re-export และเชื่อม loss scope/cause โดยไม่เปลี่ยนสูตร/latch/reset |
| `infra/risk_limits/stops.py`, `stop_views.py` | แยกส่วน target enrollment/effect/retry/pagination ให้รับ stop policy กลาง; ใช้ตาราง target/effect เดิมสำหรับ Paper ไม่สร้าง consumer คู่ขนาน |
| migrations `0049`–`0051` | ใช้ risk stop jobs/effects, immutable cutoff และ DB-clock lifecycle เดิม; migration ใหม่เป็น additive และไม่ rewrite history |
| `infra/risk_limits/dispatch.py::lock_risk_owner` | ใช้ owner/mode writer ordering เดิมสำหรับ user stop, intake, cancel และ resume |
| `infra/paper_orders/{requests,dispatch}` | terminalize queued opening, submit cancel ด้วย idempotency เดิม และอ่านผลจริงเมื่อ cancel แข่ง fill |
| `services/engine/risk_limit.py::run_risk_stop_round` | ขยายเป็น shared Paper stop round พร้อม bounded owner fairness ไม่สร้าง worker loop ซ้ำ |
| `infra/platform/{records,storage}.py` | ใช้ `PlatformRole`, membership และ default-deny authorization ของ Platform Admin/Owner |
| `services/api/catalog_routes.py` | ใช้รูปแบบ server-side platform role check, safe errors และ audit actor เดิม |
| `RiskStopEffects.tsx`, `riskLimits.ts` | แยก shared stop effects view/client โดยคง wrapper ของ F-18 และ snapshot-bound pagination |
| `Button`, `Badge`, `Alert`, `Modal`, `Table`, `MarketTime` | ใช้ shared UI components เดิมทั้งหมด |
| `layout/AccountHeader.tsx`, `AccountLayout.tsx` | วางปุ่ม Paper/Live ที่เห็นทุกหน้าและ persistent platform/system banner |

### UI source mapping จาก admin template

| UI | Template source |
|---|---|
| header และ responsive action area | `references/admin-template/src/layout/AppHeader.tsx` |
| ปุ่ม stop/resume/admin action | `references/admin-template/src/components/ui/button/Button.tsx` |
| persistent warning/error | `references/admin-template/src/components/ui/alert/Alert.tsx` |
| restart summary | `references/admin-template/src/components/UiExample/ModalExample/DefaultModal.tsx` และ shared `frontend/src/components/ui/Modal.tsx` |
| status badge/effects table | `references/admin-template/src/components/ui/badge/Badge.tsx` และ shared Table เดิม |

Trading safety บังคับให้ปุ่ม Paper/Live สองปุ่มเห็นพร้อมกันและกดหยุดได้หนึ่งคลิก
บน desktop/mobile จึงไม่ซ่อนไว้ใน application menu แม้พื้นที่ header ต่างจาก template
ใช้ tokens, breakpoint และ shared components ของ template ส่วนข้อยกเว้นนี้มาจาก RQ-01/02
และ frontend standard §1/5

## 3. Domain และ policy

เพิ่ม pure immutable types ใน `core/trading_stops.py` โดยใช้ `core.orders.TradingMode` เดิม:

- `StopCause`, `StopActor`, `StopScope`, `StopSnapshot` และ shared `StopProgress` ที่
  `core.risk_limits.RiskStopProgress` re-export เพื่อไม่สร้าง enum สถานะสองชุด
- policy matrix แยก USER, SYSTEM/LOSS_LIMIT และ PLATFORM:
  - USER หยุด bot opening; MANUAL opening หลัง cutoff ผ่าน gates เดิมได้
  - SYSTEM/LOSS_LIMIT ห้าม opening ตาม proof/latch ของต้นเหตุ
  - PLATFORM ห้าม opening ทั้ง manual/bot ทุก owner/mode
  - reduction/cancel/protective TP/SL ไม่ถูกบล็อกด้วย stop policy
- resume decision รับ expected stop/revision, current causes, account use, reconciliation proof
  และ cause-specific recovery proof; mismatch/unknown/missing proof ปฏิเสธ
- aggregate status ไม่รายงาน STOPPED จน target discovery ครบ; target ที่รู้ผลแต่ cancel ไม่สำเร็จ
  เป็น PROBLEMS ไม่ใช่ความสำเร็จปลอม

core ไม่อ่าน DB/clock/network และไม่สร้าง UUID ผู้เรียกส่งค่าทั้งหมดเข้ามา
ไม่คำนวณเงินหรือ quantity ใหม่ใน F-19

## 4. Persistence, ordering และ audit

เพิ่ม migration ถัดจาก current head `0060` (คาดหมาย `0061_kill_switch.py`;
ถ้า head เปลี่ยนให้ใช้เลขถัดไปก่อนลงมือ):

1. `trading_stop_requests/results` เป็น immutable STOP/RESUME inbox และ engine result มี
   stop/cause identity, action, scope owner+mode หรือ PLATFORM, actor/role, reason code/text,
   expected revision, canonical fingerprint, durable cutoff และ recorded time;
   committed STOP request เป็น fence ทันที แต่ RESUME มีผลเฉพาะเมื่อ engine result เป็น APPLIED
2. `trading_stop_events` เป็น append-only applied facts และ `trading_stop_causes` เป็น current
   projection แยกต่อ scope/cause identity; repeated user STOP สร้าง generation/cutoff ใหม่
   และแทน active USER generation เดิมโดยเก็บ history/effects เดิม ส่วน resume ปิดเฉพาะ
   expected latest active cause และเก็บ monotonic revision
3. `platform_stop_state/progress` เก็บ global fence revision, owner-discovery watermark/cursor
   และ aggregate counts; fence commit ก่อน API ตอบ แม้ child jobs ยังสร้างไม่ครบ
4. ขยาย `risk_stop_requests` เป็น Paper effect job ของ shared authority:
   เพิ่ม authority stop/cause FK; backfill loss stops เดิมด้วย LOSS_LIMIT shadow facts โดยคง IDs,
   history และ effective admission เดิม สร้าง active cause เฉพาะ latch/stop ปัจจุบันที่ active อยู่แล้ว;
   `event_id/risk_revision` ใช้เฉพาะ loss source ตาม CHECK และ history เดิมยังอ่านได้
5. ใช้ `risk_stop_targets/effects/progress` เดิมสำหรับ queued request/command/order outcomes;
   เพิ่ม source/origin evidence ที่จำเป็นต่อ user/platform target policy โดยไม่แก้ facts เดิม
6. เพิ่ม indexes สำหรับ effective committed STOP intents, active causes, global fence,
   due child jobs และ owner/mode snapshot; RLS/column grants จำกัด API ให้ INSERT/SELECT
   inbox และ audit request ใน transaction เดียวเท่านั้น ไม่มี UPDATE projection/result/effect;
   engine เขียน result/events/projection/effects, scan role อ่านเฉพาะ due hints
   ไม่มี runtime role เป็น owner/BYPASSRLS
7. audit actions/details แบบ typed สำหรับ STOP_REQUESTED, STOP_UPDATED, RESUME_REQUESTED,
   RESUMED, RESUME_REJECTED และ PLATFORM_STOPPED; audit อ้าง stop/reason code โดยไม่คัดลอก
   free-text reason ไป general log ส่วน UI เตือนผู้มีสิทธิ์ห้ามกรอก secret

ทุก opening transaction ถือ shared PostgreSQL advisory transaction lock ของ global stop ก่อน
owner writer lock (`global shared → owner → pair`) ส่วน platform STOP ถือ exclusive global lock,
commit request/fence แล้วจึงตอบ ทำให้ in-flight opening จบก่อน cutoff หรือเห็น fence หลัง cutoff
โดยไม่มีช่องคาบเกี่ยว User stop ถือ global shared แล้ว owner lockเดียวกับ intake/dispatch

request/command เก็บ admitted global revision และ owner-mode revision ทุกครั้ง Execution ตรวจทั้ง
current active causes และ STOP events ที่เกิดหลัง admitted revisions; intent ก่อน stop จึงไม่ฟื้น
แม้ resume commit ก่อน worker ทำงาน คำสั่ง queued-unsent ก่อน/เท่ากับ cutoff terminalize เท่านั้น
ส่วน sent/unknown/active/terminal ใช้ผลจริงตาม RQ-07..09

Platform scanner สร้าง per-owner Paper jobs แบบ bounded หลัง global fence commit; snapshot ของ owner
inventory ต้อง complete ก่อน aggregate STOPPED และ cursor/revision ต้องกู้ต่อหลัง restart ได้

same idempotency key + canonical payload คืน intent/result เดิม ต่าง payload/scope/action เป็น conflict
commit outcome ไม่ทราบให้ lookup intent เดิม ห้ามสร้าง stop/resume ใหม่เอง

Downgrade ปฏิเสธเมื่อมี stop/resume/effect history ที่รุ่นเดิมรับไม่ได้ ไม่ลบ audit/order facts

## 5. API และ engine composition

### User routes

| Method/path | Contract |
|---|---|
| GET `/{paper\|live}/kill-switch` | authoritative causes, aggregate status/counts, current stop/revision, platform banner, reconciliation/snapshot revision และ capabilities |
| POST `/{paper\|live}/kill-switch/stop` | ไม่มี confirmation/TOTP; Idempotency-Key UUID; server ผูก owner/mode และ commit immutable STOP intent+audit ก่อน 202; กดซ้ำด้วย key ใหม่สร้าง generation/cutoff ใหม่แม้ USER cause เดิมยัง active |
| GET `/{paper\|live}/kill-switch/requests/{id}` และ `/by-key/{key}` | recovery หลัง response/commit ไม่ทราบ โดย owner/mode scoped |
| GET `/{paper\|live}/kill-switch/stops/{id}/effects` | stable keyset page/filter/watermark แบบ F-18; cross-owner/mode/not-found คืน 404 เหมือนกัน |
| GET `/{paper\|live}/kill-switch/stops/{id}/resume-summary` | positions, canceled/failed/pending outcomes, target completeness, reconciliation/snapshot revision และ cause proof readiness |
| POST `/{paper\|live}/kill-switch/resume` | expected stop/cause/summary/reconciliation revisions + Idempotency-Key; ไม่ใช้ TOTP; stale/new cause/missing proof ปฏิเสธ |

Live routes บันทึก/อ่าน durable authority ได้ แต่ไม่มี executor/reconciliation จึงต้องคง
`target_set_complete=false`, `resume_ready=false` และ typed `LIVE_EXECUTION_UNAVAILABLE`;
การปิด capability อย่างเดียวไม่ใช่หลักฐานว่าไม่มี historical/unknown target ห้ามปิด discovery
ด้วยศูนย์รายการจน F-22/F-23 มี durable activation history และ complete reconciliation proof
ไม่สร้าง Paper mutation จาก Live route และคง Live validation Pending Dependency

### Platform routes

| Method/path | Contract |
|---|---|
| GET `/admin/kill-switch` | Admin/Owner อ่าน global state/progress/reason; user ทั่วไปได้ uniform denial |
| POST `/admin/kill-switch/stop` | Admin/Owner, ไม่ใช้ TOTPเพราะเป็นการลดความเสี่ยง; reason บังคับ 1–500 Unicode code points และแสดงตามที่กรอก; commit global fence/audit ก่อน 202 |
| POST `/admin/kill-switch/resume` | Platform Owner เท่านั้น; expected platform revision และ complete summary/reconciliation evidence; ไม่ใช้ TOTP ตาม security §1 และไม่ข้าม active causes อื่น |

เพิ่ม routes ใน app/routing policy/OpenAPI classification และใช้ safe typed error codes
ไม่คืน raw payload, SQL, secret หรือข้อมูล owner อื่น

Engine ใช้ shared stop round เดิม: effective STOP intents/global fence/owner causes → bounded target discovery →
terminalize queued opening → cancel eligible active remainder → poll actual outcome → retry with
backoff. User stop เลือก bot+manual; platform child jobsเลือก bot เท่านั้นและคง manual orders
ที่ส่งแล้ว TP/SL ไม่เข้า candidate ทุกกรณี Fill/partial fill เข้า recovery/protection path เดิม
แจ้งเมื่อครบหนึ่งนาทีแต่ worker ยัง retry จนรู้ผล

target eligibility อยู่ใน shared policy/query contract เดียวที่ `_CANDIDATES`,
`queued_opening_stopped()`, `cancel_stopped_remainders()`, request worker และ matching worker
ต้องเรียกใช้ ห้ามแต่ละ path join `risk_stop_requests` แล้วตีความ cause/origin เอง

## 6. UI และ interaction

- `KillSwitchControls` อยู่ใน `AccountHeader` ทุกหน้า มีปุ่ม “หยุดบอท Paper” และ
  “หยุดบอท Live” แยกชัด กดแล้วส่ง stop ทันทีหนึ่งคลิก ไม่มี confirmation modal
- ปุ่มแต่ละโหมดแสดง STOPPING/STOPPED/PROBLEMS และจำนวนค้าง; loading/unknown ห้ามแสดง
  ว่าหยุดสำเร็จ ปุ่มหยุดยังสร้าง generation ใหม่ได้เสมอด้วย key ใหม่เพื่อจับ MANUAL orders
  ที่เกิดหลัง cutoff เดิม ส่วน “ดูรายละเอียด” เป็น control แยก; retry จาก response UNKNOWN
  ต้องใช้ key เดิมและห้ามถูกตีความเป็นการหยุดครั้งใหม่
- `StopSummaryModal` แสดง position ค้าง รายการ canceled/failed/pending และเวลาที่กระทบยอด
  ปุ่ม resume ใช้ snapshot ที่เห็น; stale response ปิดการ submit และบังคับ refresh
- platform/system/loss stop แสดง persistent `Alert` ทุกหน้าพร้อม source/reason; platform free text
  แสดงเป็น user content ไม่ผ่าน translation แต่ labels/status/error รองรับไทย/อังกฤษ
- เพิ่มหน้า admin “ความปลอดภัยระบบ” สำหรับ reason + global stop และ Owner resume;
  Admin เห็น resume disabled พร้อมคำอธิบายสิทธิ์ ไม่มีอำนาจแตะ position/order แทนผู้ใช้
- TanStack Query เป็น server state ใช้ shared query เดียวต่อ owner, query keys ผูก
  owner/mode/stop/revision, refetch ทุก 1 วินาทีเมื่อ signed-in app มองเห็นและ refetch เมื่อกลับมา
  focus; local durable journal เก็บเฉพาะ idempotency recovery intent แบบ F-18
- ใช้ focus trap/return focus/live region, keyboard, contrast, light/dark และ responsive states
  ของ shared components; ปุ่มทั้งสองยังเห็นและแตะได้บน viewport mobile

## 7. ไฟล์ที่จะเพิ่มหรือแก้

| ส่วน | ไฟล์หลัก |
|---|---|
| Core | `core/trading_stops.py`, adapter ใน `core/risk_limits.py` |
| Migration/infra | `migrations/versions/0061_kill_switch.py`, `infra/trading_stops/{records,storage,views}.py`, `infra/risk_limits/{stops,stop_views}.py`, `infra/paper_orders/{requests,dispatch,request_worker,worker}.py` และ shared eligibility contract |
| Engine | `services/engine/{kill_switch,risk_limit,main}.py` |
| API | `services/api/{kill_switch_models,kill_switch_routes,routing_policy,app}.py`, audit contracts และ platform role helper |
| Frontend | `killSwitch.ts`, `killSwitchMessages.ts`, `KillSwitchControls.tsx`, `StopSummaryModal.tsx`, `PlatformKillSwitchPanel.tsx`, shared stop effects, account layout/header/navigation/styles |
| Tests | core, real PostgreSQL migration/roles/concurrency, API routing/contracts, engine stop recovery, component/browser tests และ combined set-5 harness |

รายชื่อเป็นขอบเขตคาดหมาย หาก implementation ต้องเปลี่ยนกฎที่อนุมัติหรือข้าม layer ตามมาตรฐาน
ต้องหยุดเสนอ amendment; การแตกไฟล์ภายใน layer โดยไม่เปลี่ยน behavior ทำได้ตามความเหมาะสม

## 8. Milestones และ checkpoints

| Milestone | ขอบเขต | Validation |
|---|---|---|
| M1 | pure policy/cause precedence/resume CAS และ F-18 adapter | V-01..03 |
| M2 | migration/RLS/audit/idempotent API/platform authority | V-04..08 |
| M3 | Paper target selection/cutoff/concurrency/retry/recovery และ F-18 integration | V-09..14 |
| M4 | header controls, summary/admin UI, i18n/accessibility/browser composition | V-15..18 |
| M5 | affected regression/static/generated contracts; แจ้ง **Ready for Code Review** แล้วหยุดรอ `review code` | V-19 |
| หลัง review/refactor | แก้ findings ตามคำสั่ง, ถาม `refactor the code`; เมื่ออนุมัติและ refactor เสร็จจึง validation ต่อทันที | V-01..19 ที่ได้รับผล |
| ท้ายชุดที่ 5 | combined F-18/F-19 Paper risk/stop/recovery/full regression และ W1–W4 ที่เกี่ยวข้อง | V-20 |
| Dependency/release | real TP/SL, bot, Live และ notification integration กับชุดที่ 9 | V-21..24 |

แต่ละ milestone บันทึก evidence เดิมต่อเนื่องพร้อม diff, environment, commands/results และเวลาจริง
ไม่รัน workload/endurance/timed smoke อัตโนมัติระหว่าง milestone

### V-20 core-loss amendment — Approved 2026-10-31

ก่อนเริ่ม measured load ให้สร้าง dedicated MANUAL loss owner แยกจาก core และ scheduled-stop owners:
สร้าง partial exposure จริง, ลดราคาให้เกิด LOSS_LIMIT stop, รอ effects/reconciliation complete, คืนราคา,
ส่ง risk reset แล้ว probe opening ซึ่งต้องยัง fail closed จาก durable stop บันทึก request/stop/generation,
status, financial markers และ digest ลง evidence โดยไม่รวมคำสั่งของ owner นี้ใน core counters
ส่วน selected core owner ยังคง partial-fill และ exact-correction scenarios เดิม แต่ไม่ทำ loss reseed

### NC-F19-05 reconciliation clock correction — Approved 2026-10-31

- แก้ migration `0061` ให้ reconciliation trigger ตรวจ active `PLATFORM` cause ผ่าน indexed key
  แล้ว increment singleton clock เฉพาะเมื่อ cause ยัง active; normal trading ทำเพียง bounded lookup
  และไม่ UPDATE global row
- เพิ่ม FORCE RLS policies แบบ role-scoped ให้ function owner อ่าน PLATFORM cause และ UPDATE clock;
  ไม่ grant UPDATE แก่ API/engine และคง transaction boundary ของ position write เดิม
- เพิ่ม real-PostgreSQL regression สำหรับ inactive no-write, active transactional increment,
  rollback no-change และ stale platform resume rejection ก่อนกลับไปรัน W1 ด้วย explicit child publisher

### NC-F19-06 stop-worker idle backoff — Approved 2026-10-31

- แยก stop-loop scheduler เล็ก ๆ ใน `services/engine/risk_limit_main.py` โดย reuse rounds/pools เดิม;
  aggregate activity จาก stop request, platform discovery และ risk-stop result แล้วใช้ pure bounded
  delay helper 20→40→80→160→250ms เฉพาะเมื่อทั้งสามว่าง
- ขยาย `StopRound` ด้วย active-platform hint จาก query เดิมเพื่อให้ restart/ongoing discovery คง 20ms
  โดยไม่เพิ่ม scan; processed/deferred/discovered/pending ใด ๆ reset delay เป็น 20ms
- เพิ่ม unit scheduler tests สำหรับ cap/reset/deferred/active-platform/restart และ rerun affected
  PostgreSQL stop tests/static checks จากนั้นใช้ diagnostic สั้นเทียบ rollback/lock pressure ก่อน W1

### NC-F19-08 R6-compatible workload readiness hint — Approved 2026-10-31

- แก้เฉพาะ read-only refusal backpressure query ใน
  `tests/infra/risk_limits/profile_workload.py`; production API/engine/schema/pools และ monitor
  scheduling ไม่เปลี่ยน
- hint ต้องเห็น evaluation/owner state ของ owner+wallet+episode เดิม, setting revision ตรง,
  ไม่ latched, evaluation และ owner ไม่ `replay_pending`, `evaluation.price_watermark = owner.cursor`
  และ current publication lag อยู่ในช่วง 0..100 frames ตามขอบเขต API R6
- hint ไม่ decode frame, ไม่ประเมิน risk และไม่ authorize คำสั่ง; เมื่อ hint เป็นจริง loop ต้องกลับไป
  เรียก `manual_policy_for` และ `checked.check` เต็มเสมอก่อน `admit_new_request` ดังนั้น transient
  breach, corrupt/missing frame, stale financial evidence หรือ tail ที่เกิน budget ยังคง fail closed
- ยกเลิกเฉพาะเงื่อนไข scheduling hint เดิมที่บังคับให้ owner/evaluation cursor เท่ากับ current
  publication watermark ทุกขณะ เพราะเข้มกว่า R6 และทำให้ workload รอ exact instant ที่ไม่ใช่
  production authorization contract
- คง setup/measured poll cadence, 60s command bound, 100×20 workload, source rates, SLA,
  resources และ stop schedule เดิมทั้งหมด; short diagnostic หนึ่งรอบหลัง targeted checks เท่านั้น
  ถ้ายังล้มหรือเกิด request ก่อน full policy pass ให้หยุด ไม่ขยาย timeoutและไม่รัน W1

### NC-F19-09 bounded dedicated RESET retry — Approved 2026-10-31

- คง production RESET fail-closed/lifecycle เดิม; เปลี่ยนเฉพาะ dedicated LOSS_LIMIT validation
  scenario เมื่อ durable result เป็น `REJECTED/RISK_SOURCE_UNAVAILABLE`
- ส่ง RESET request ใหม่ด้วย idempotency key/request identity ใหม่ได้รวมไม่เกิน 3 attempts,
  เว้น 250ms ระหว่าง attempts และทุก attempt รวมอยู่ภายใน deadline 60s เดิม
- บันทึก attempt number, request id, state และ failure code ทุกครั้ง; failure code อื่นต้องล้มทันที,
  attempt ที่สามยัง unavailable ต้องล้มและเก็บ evidence ห้ามถือเป็น retry success
- successful RESET ยังต้องผ่าน production worker/full authoritative replay จริง แล้ว opening probe
  ต้องถูก durable LOSS_LIMIT stop บล็อกเหมือนเดิม; ไม่เปลี่ยน source/SLA/pools/rates หรือ W1 gates

### NC-F19-10 dedicated-loss fixture ordering and diagnostic — Approved 2026-10-31

- r7 ยืนยัน request `b11b6fde-4424-4b44-8050-c09b083b4414` ถูก transfer เป็น command
  `ff812dea-4c32-4925-b3b2-84884b5e5739` สำเร็จ แต่ paper worker ตรวจ risk ซ้ำหลัง transfer
  ประมาณ 2.91s แล้วปฏิเสธ `RISK_SOURCE_UNAVAILABLE`; financial boundary/source proof ตรงกัน
  แต่ owner replay เปลี่ยนจาก cursor6461/non-pending เป็น cursor6615/pending ระหว่าง continuous source
- เพิ่ม validation-only `--dedicated-loss-diagnostic` ซึ่งใช้ fresh schema0061, child publisher,
  real risk/paper workers และ `dedicated_loss_reset` เดิมกับ dedicated MANUAL ownerหนึ่งราย;
  ไม่สร้าง core measured commands และไม่เป็น acceptance result
- diagnostic บันทึก request→command→result timestamps/identities, owner/evaluation cursor+pending,
  current watermark/lag, financial boundary/source revision+proof และ balances/positions/reservations
  ก่อน partial, หลัง partial, หลัง stop และหลัง RESET; terminal failure ต้องเก็บ snapshot แล้วหยุด
- ใน integrated profile ย้าย dedicated scenario ไปหลัง risk settings และ paper workers พร้อม แต่ก่อน
  core `seed_baseline`; publisher/owners/source rates/pools คงทำงานจริง แล้วจึง seed core 100×20,
  scheduled-stop fixtures และเริ่ม measured loadตามเดิม การย้ายลำดับไม่เปลี่ยน denominator/SLA
- คง NC-F19-09 RESET retry และ production fail-closed เดิม ห้าม retry/resubmit NEW, ขยาย replay budget,
  เพิ่ม worker concurrency/pool หรือเปลี่ยน production request/command lifecycleใน amendment นี้
- ถ้า isolated diagnostic ผ่านแต่ integrated short diagnostic ยังล้มที่ NEW recheck ให้หยุดเสนอ
  production capacity/lifecycle amendment พร้อม evidence ใหม่; ห้าม rerun W1 หรือวนรอบเดิม

### NC-F19-11 setup-only stop-owner readiness gate — Approved 2026-11-01

- W1 r1 ผ่าน dedicated scenario และ core baseline 100×20 แล้ว แต่ setup-only BOT order ของ
  stop-owner slot 1 ถูกสร้างโดย `original_submit` ซึ่งข้าม read-only readiness backpressure ที่
  public request fixture ใช้; command ถูกส่งตอน owner replay ตาม source ไม่ทันและ terminal reject
  `RISK_SOURCE_UNAVAILABLE` ที่ cursor4314/watermark4427/lag113
- เสนอแก้เฉพาะ validation harness: ก่อนส่ง setup-only MANUAL/BOT NEW ของ dedicated stop owners
  ให้รอ `risk_retry_ready` เดิมแบบ bounded ภายใน setup deadline 60s แล้วเรียก `original_submit`
  เพียงครั้งเดียว; ระหว่างรอห้ามสร้าง request/command/order และ terminal reject หลัง submit ต้องล้มทันที
  ห้าม retry/resubmit NEW
- gate นี้ไม่ใช้กับ core 100×20 หรือ measured commands, ไม่เปลี่ยน production API/engine/monitor,
  replay budget, fail-closed, owners, source/load rates, duration, SLA, pools หรือ stop schedule;
  เป็นการทำให้ fixture precondition ตรงกับ authoritative state ก่อนสร้าง state สำหรับ stop oracle
- บันทึก owner/evaluation cursor+pending, publication watermark/lag และเวลา WAIT_START/READY/TIMEOUT;
  ถ้า timeout ให้เก็บ Failed และถือว่า production catch-up capacity ยังบล็อก โดยต้องเสนอ production
  optimization amendment แยกต่างหาก ห้ามขยาย timeoutหรือลด source/load
- เจ้าของอนุมัติ 2026-11-01; หลัง targeted control-flow/R6/static checks ให้รัน W1 บน fresh
  schemaเพียงหนึ่งรอบ แล้วเดิน W2/W3 ต่อเฉพาะเมื่อ W1 acceptance ผ่าน

ผล W1 2026-11-01: Failed ก่อน measured window เพราะ MANUAL stop-owner ไม่มี risk setting/state/evaluation
ให้ gate สังเกต จึง timeout โดยไม่ submit ตาม safety contract; หยุดก่อน W2/W3 และห้าม rerun NC-F19-11

### NC-F19-12 initialize MANUAL stop-owner risk state — Approved 2026-11-01

- ก่อน readiness gate ให้ MANUAL stop-owner ใช้ setup mutation `SET 1000` เดิมแบบเดียวกับ BOT
  stop-owner เพื่อสร้าง durable setting/owner/evaluation state แล้วจึงรอ `risk_retry_ready` และ submit
  setup NEW เพียงครั้งเดียว; ไม่เพิ่ม NEW retry และ timeout 60s เดิม
- เปลี่ยนเฉพาะ validation harness และ setup state ของ dedicated stop-owner; production source/schema,
  core100×20, measured load/duration/SLA/resources/stop schedule และ fail-closed policyไม่เปลี่ยน
- ต้องเพิ่ม test ว่า mutation สำเร็จก่อน WAIT_START, readiness มี durable rows, timeout ยัง no-submit และ
  W1 fresh-schemaรันได้เพียงหนึ่งรอบหลัง targeted checks; ผ่านแล้วจึงไป W2/W3
- เจ้าของอนุมัติ 2026-11-01; ปลดบล็อก implementation, targeted/static checks และ W1
  fresh-schemaหนึ่งรอบ โดย W2/W3 ยังขึ้นกับผล W1

ผล W1 2026-11-01: readiness ของ MANUAL/BOT ผ่านและ core baseline 100×20 ผ่าน แต่ Failed ที่
stop-owner partial oracle ถูก fill เต็มเพราะ global source liquidity ถูก core oracle เปลี่ยนก่อน event;
หยุดก่อน W2/W3 และห้าม rerun NC-F19-12

### NC-F19-13 isolate scheduled partial-fill source window — Approved 2026-11-01

- ใน `prepare_partial_bot` ให้ติดตั้ง source fixture ask@100 quantity 0.5 แบบ explicit ทันทีก่อนส่ง
  BOT limit quantity 1 แล้วคงไว้จน durable stop effects cancel/release remainder เสร็จ จากนั้น restore
  regular ask quantity เดิมทันที; ใช้ publisher/source-control path เดิมและไม่เปลี่ยน publication rate
- ต้องผูก restore กับ `finally`/terminal outcome เพื่อไม่ให้ core workload ใช้ partial liquidity ต่อเมื่อ
  scenario ล้มหรือหยุด และบันทึก install/restore timestamps กับ source input identities
- production source/schema/order policy, owners, offered load, duration, SLA, RESET schedule และ NEW
  retryไม่เปลี่ยน; เป็น harness isolation ให้ event ที่ spec ระบุ `PARTIALLY_FILLED` deterministic ภายใต้ load
- targeted test ต้องพิสูจน์ install → fill 0.5 → stop cancel/release → restore, failure cleanup restore,
  no duplicate execution และ core countersไม่ถูกตัด; ผ่านแล้วรัน W1 fresh-schemaได้หนึ่งรอบ
- เจ้าของอนุมัติ 2026-11-01; ปลดบล็อก harness implementation, targeted/static checks และ W1
  fresh-schemaหนึ่งรอบ โดย W2/W3 ยังขึ้นกับผล W1

ผล W1 2026-11-01: scheduled partial/stop/restore ผ่าน แต่ global quantity0.5 window กระทบ core
MARKET BUY ให้ EXPIRED/partial แทน FILLED และ cycle timeout; หยุดก่อน W2/W3 และห้าม rerun NC-F19-13

### NC-F19-14 owner-isolated one-shot partial trade — Proposed / Needs Clarification

- แทน global ask-quantity window ด้วย dedicated BOT BUY limit ที่ราคาเฉพาะซึ่ง core workload ไม่ใช้
  (เสนอ 2 USDT): submit ให้ resting `ACCEPTED` ก่อน แล้ว publisher path เดิมส่ง one-shot authoritative
  BUY trade quantity0.5 ที่ราคาเดียวกัน; รอ `PARTIALLY_FILLED` แล้วเดิน stop/cancel/release/resumeเดิม
- one-shot control ต้อง acknowledge input identity และ consumeได้ครั้งเดียว; `finally` ต้อง clear pending
  injection. ห้ามเปลี่ยน global book liquidity, publication cadence หรือ pause core workload
- production/schema/order policy, owners, offered schedule, duration, SLA, RESET schedule และ NEW retry
  ไม่เปลี่ยน; test ต้องพิสูจน์ core MARKET BUY/SELL ยัง FILLED ระหว่าง injection, dedicated fill exactly0.5,
  remainder cancel/release, no duplicate execution และ failure cleanup
- หลัง targeted publisher/real-worker/static checks ให้รัน W1 fresh-schemaหนึ่งรอบ; failure หยุด W2/W3
- **Needs Clarification:** เปลี่ยนจาก approved global book window เป็น one-shot trade คนละ source mechanism
  จึงบล็อก implementation และ W1 รอบถัดไปจนเจ้าของอนุมัติ NC-F19-14

เจ้าของตัดสินใจ 2026-11-01 ให้หยุดแก้และหยุดรัน workload เพิ่มใน feature checkpoint นี้;
เลื่อน NC-F19-14 พร้อม W1–W3 ไปทำครั้งเดียวที่ Full Validation ท้ายชุดที่ 5 โดยคงข้อเสนอเป็น
Needs Clarification และคงเกณฑ์/load/SLA เดิมทั้งหมด ผล Failed ก่อนหน้านี้ยังเป็นหลักฐานตามจริง

## 9. Rollout และความเสี่ยง

1. deploy schema/read paths ก่อน writer/worker; global/user fence default fail-closed เมื่อ revision
   อ่านไม่ได้ ไม่มี migration ที่สร้าง stop/resume ให้ผู้ใช้โดยปริยาย
2. mixed-version writer ที่ไม่ตรวจ stop revision ต้องถูก writer-version gate ปฏิเสธก่อนเปิด authority
   ใหม่; rollback ใช้ปิด opening และ compatible cancel/read path ไม่ใช้ worker เก่าข้าม fence
3. production NEW admission และ Live execution คงปิดจน activation gates ของ feature ที่เกี่ยวข้องผ่าน
4. ความเสี่ยงหลักคือ submit-vs-stop, stop-vs-resume, platform owner discovery, cancel-vs-fill,
   stale summary, mixed causes, retry duplication, owner starvation และ UI แสดง success เร็วเกินจริง
5. F-17/F-20/F-22/F-26/F-36/F-27 เป็น Pending Dependency ตาม validation; ไม่เรียก F-19 Completed
   จาก Paper targeted checks หรือ contracts อย่างเดียว

แผนนี้ไม่เปลี่ยนกฎเงิน กฎ order matching หรือ loss formula หาก reuse ของ F-18 ต้องเปลี่ยน
ผลที่อนุมัติไว้ให้หยุดและแก้ spec ก่อน implementation

## 10. Deep-review corrections — Approved 2026-10-31

| Finding | การแก้ในแผน |
|---|---|
| R1 writer authority | committed STOP inbox เป็น fence; APIเขียนเฉพาะ inbox/audit, engineเขียน result/projection/effects; RESUME ไม่มีผลก่อน engine APPLIED |
| R2 global race | global shared/exclusive advisory lock order + admitted global/owner revisions + historical execution check |
| R3 duplicate enforcement | shared eligibility ใช้ร่วม target discovery, request worker และ matching worker แยก user/platform/origin |
| R4 repeated stop | STOP keyใหม่สร้าง generation/cutoffใหม่เสมอ; details control แยก; UNKNOWN retryใช้ keyเดิม |
| R5 lifecycle semantics | requirements RQ-07 แยก unsent, sent/unknown, active remainder และ terminal |
| R6 Live false completeness | คง Live discovery/resume incomplete จนมี activation history+reconciliation จาก F-22/F-23 |
| R7 protective dependency | targeted stage ตรวจ contract เท่านั้น; real TP/SL integration เป็น V-21 รอ F-17 |

### Review remediation — เจ้าของสั่งแก้ 2026-11-01

แก้ findings จาก review บน candidate `5620843` ให้ตรง RQ-12/15 และ V-03/11/14 เดิม:

- เพิ่ม additive migration `0062_stop_snapshot_revision.py`: progress เก็บ nullable
  `reconciliation_revision`; ค่าเดิมเป็น NULL จึงไม่ใช้ resume จน discovery ตรวจใหม่
  counts/completeness/clock มาจาก SQL snapshot เดียวกัน และ publish ด้วย progress-revision CAS
  พร้อมตรวจ clock ปัจจุบัน; clock เปลี่ยนต้อง refresh snapshot ไม่ใช้ clock ใหม่คู่ progress เก่า
- resume ถือ global exclusive ตามเดิม แล้วเรียก narrow SECURITY DEFINER function เพื่อล็อก
  reconciliation-clock row จน commit; ใช้สิทธิ์ migrator/RLS policy เดิม API/engine ยัง UPDATE
  clock โดยตรงไม่ได้ และ function ให้ EXECUTE เฉพาะ engine; downgrade ปฏิเสธเมื่อมี snapshot history
- discovery ใช้ timeout 100ms/700ms ตาม risk-worker pattern เดิม, page แบบ bounded และ rotate
  ผ่าน owners ที่ยังไม่มี durable target; lock/failure ไม่ทำ owners ถัดไปอด และ owner ที่พลาดยังถูก retry
  completion ต้องไม่มี missing owner พร้อม child/reconciliation complete; concurrent publishers ใช้ CAS
- status หา latest STOP แยก cause แล้วกรอง resumed ก่อนเลือก primary summary;
  additive `active_causes` ให้ banner แสดง LOSS_LIMIT/SYSTEM ต่อแม้ latch reset แล้ว
  resume USER ไม่ซ่อน unresolved cause อื่น; scope, cause-specific proof และ account-use gates เดิมคงอยู่
- reuse `lock_risk_owner`, global locks, clock trigger, target uniqueness, `serialize` real-DB barrier
  และ shared wallet fixture factory; ไม่เพิ่ม infrastructure, order retry หรือสูตรการเงิน
- ตรวจ targeted regression, migration/roles/locking, generated contracts, frontend แล้ว backend
  สี่ phase ตาม CI พร้อม F-19 browser E2E; ไม่รัน W1–W3 ที่เลื่อนไป Full Validation
