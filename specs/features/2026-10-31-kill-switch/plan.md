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

### NC-F19-14 owner-isolated one-shot partial trade — Approved 2026-11-01

- แทน global ask-quantity window ด้วย dedicated BOT BUY limit ที่ราคาเฉพาะซึ่ง core workload ไม่ใช้
  (เสนอ 2 USDT): submit ให้ resting `ACCEPTED` ก่อน แล้ว publisher path เดิมส่ง one-shot authoritative
  BUY trade quantity0.5 ที่ราคาเดียวกัน; รอ `PARTIALLY_FILLED` แล้วเดิน stop/cancel/release/resumeเดิม
- one-shot control ต้อง acknowledge input identity และ consumeได้ครั้งเดียว; `finally` ต้อง clear pending
  injection. ห้ามเปลี่ยน global book liquidity, publication cadence หรือ pause core workload
- production/schema/order policy, owners, offered schedule, duration, SLA, RESET schedule และ NEW retry
  ไม่เปลี่ยน; test ต้องพิสูจน์ core MARKET BUY/SELL ยัง FILLED ระหว่าง injection, dedicated fill exactly0.5,
  remainder cancel/release, no duplicate execution และ failure cleanup
- หลัง targeted publisher/real-worker/static checks ให้รัน W1 fresh-schemaหนึ่งรอบ; failure หยุด W2/W3
- **Needs Clarification ปิดแล้ว 2026-11-01:** เจ้าของอนุมัติเปลี่ยนจาก global book window
  เป็น one-shot trade พร้อม Set-5 plan/NC-F19-15 ตาม §11; ข้อความเลื่อนก่อนหน้านี้เป็นประวัติ

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

## 11. Full Validation ท้ายชุดที่ 5 — Approved 2026-11-01

สถานะส่วนนี้: **Approved — เจ้าของสั่ง `approve Set-5 plan including NC-F19-14 and NC-F19-15`**
อนุมัติ implementation/targeted checks และลำดับ conditional W1→W2→W3→W4 ตามส่วนนี้
ไม่เปลี่ยนสถานะ Approved ของส่วนเดิมหรือเปลี่ยน Failed/Not Run เป็น Passed

### หลักฐานที่ใช้ต่อและ candidate

- ตั้งต้นจาก main หลัง F-19/workflow (`2322d86`); freeze candidate ใหม่หลังแก้ harness
  พร้อม source-tree/config/lockfile/schema/schedule hashes และ process inventory ครบ
  ไม่นำ local changes ที่ไม่เกี่ยวข้องมาปน candidate
- ใช้ V-01..19 และ CI ของ `de25852`/`ccc3ce1` ต่อเฉพาะ behavior ที่ harness diff ไม่กระทบ
  post-merge CI เป็น regression evidence ไม่ใช่ workload/restore acceptance
- F-18 R34 W1–W4 ใช้เป็นฐานเปรียบเทียบ ไม่แทน F-19 V-20 เพราะ shared stop authority,
  discovery/clock และ schema0061/0062 เปลี่ยนจาก F-18 schema0058
- NC13 W1 ยัง Failed: global ask0.5 window40.9s ทำ core BUY partial0.833/EXPIRED
  และ timeoutที่+159.73s; W2/W3 ยัง Not Run. เก็บ
  `validation-artifacts/f19-20261101/nc13-w1-r1/` และ checkpointเดิม ไม่ rerun NC13
- Map F-16 V-18 ด้วย production risk composition หลัง F-18 ไม่ใช้ allow-policy harness
  ปิดด่านนี้; F-16 V-20/F-15 ชุด4หรือreleaseไม่ปิดเหมารวมจาก profileV2
- V-21..24 รอ dependenciesเดิม ไม่เปิด production/Live และไม่ Completed

### NC-F19-14: รายละเอียด implementation ที่เสนอ

Reuse `backend/tests/infra/risk_limits/profile_workload.py`, `profile_stop_schedule.py`,
`profile_publisher.py`, `profile_publisher_process.py` และ tests เดิม ไม่แก้ production matching

1. Dedicated BOT BUY GTC quantity1 ที่ราคา2 USDT ต้องผ่าน metadata/min-notional และ
   proven book coverage จาก fixture bids99/1, queue ahead0 และ core intentsไม่ใช้ราคา2
   หากพิสูจน์ไม่ได้ให้ fail ก่อน injection ไม่เปลี่ยน depth/constraintsเพื่อให้ผ่าน
2. รอ durable ACCEPTED/resting ก่อน one-shot `MarketTrade` resting_side BUY,
   price2/quantity0.5/ordering_proven ผ่าน child publisherบน cadenceเดิม ผูก control sequence,
   generation/input/trade identities และ committed receipt; transport ACK ไม่ใช่หลักฐานว่า fillแล้ว
3. Reject unknown/duplicate/conflicting control; เมื่อ ACKหายใช้ identity lookup หรือ fail
   ไม่ replay injection/NEW. `finally` clear pending injection; committed factsห้ามลบ
4. ต้องได้ exactly one fill0.5 แล้ว stop/cancel/release/resumeตาม scheduleเดิม ไม่มี auto-fill
   หรือ auto-resume. RESET retryคง NC09; ไม่เพิ่ม retry NEW
5. Real-worker matrix ต้องมี core MARKET BUY/SELL overlapที่ FILLED, exact partial financial
   effects, reservation0หลังcancel และ request/audit identitiesตรง ใช้ Money/Quantity กับ
   hand oracle/fee policyเดิม ไม่ใช้ expectedราคา100ของNC13

### NC-F19-15: evaluator ไม่ตรง F-19 SLA — Approved 2026-11-01

`profile_workload.sla_summary` ใช้ per-owner quota995/1000ใน W1–W3 และ runnerให้
`missing_commit_allowance=1` ตาม F-18 R34 แต่ F-19 validation§5 ระบุราย owner99.9%≤3s
พร้อม source windowครบ จึงใช้ F-18 verdictโดยตรงปิด F-19 ไม่ได้

เสนอ **คงเกณฑ์ F-19 เดิม** ด้วย explicit F-19 acceptance selection ใน harness/manifest:
owner999/1000, run-wide999/1000, ทุก ready input≤5s และ source countsครบ nominal active
windowโดยไม่มี short-count allowance; fault exemptionsคง scheduleเดิม ไม่เพิ่ม padding
คง F-18 R34/owner99.5%/allowance1 สำหรับ F-18 ตามเดิม ไม่เปลี่ยน production/financial
คำนวณสอง verdictจาก raw receiptsชุดเดียวได้ แต่ F-18 Passedไม่แทน F-19 Failed
เพิ่ม boundary tests ที่ F-18ผ่านแต่ F-19ต้องล้ม รวม missing ack/clock/duplicate/drain exclusion

เจ้าของอนุมัติการแยก evaluator ตามข้อเสนอนี้แล้ว ไม่ลดเกณฑ์ F-19 ตาม R34
ข้อความ Needs Clarification/การเลื่อนก่อนหน้านี้เป็นประวัติก่อนอนุมัติส่วนนี้

### W4: ปิด coverage ของเกณฑ์เดิมก่อนเริ่มชุดยาว

Reuse `backend/tests/infra/risk_limits/profile_restore.py` และ
`backend/tests/infra/execution_market/profile_restore.py` สำหรับ guard, backup/restore,
roles/RLS/grants และ canonical/economic digests ไม่สร้างเครื่องมือ restoreใหม่
runnerเดิม stage LOSS stop และ `RISK_TABLES` ยังไม่มี shared F-19 tables จึงต้องขยาย:

- source fixtureมี active USER/SYSTEM/PLATFORM causes, discovery cursor/child targets,
  unfinished effects, idempotency receipts, audit และ reconciliation revision0062
- digestรวม `trading_stop_requests/results/events/causes/dispatch`,
  `platform_stop_progress/targets`, `trading_reconciliation_clock` กับ F-18/F-15 factsเดิม
- backup sourceที่ quiescedตาม procedureเดิมไป fresh targetคนละDB แล้วเทียบ
  canonical/schema/roles/grants/RLS ก่อน recovery
- หลัง recovery: pending effectsเดินต่อ, exact-key replayไม่สร้างผลซ้ำ, stale resumeถูกปฏิเสธ,
  economic/position/balance/reservationไม่เปลี่ยน แยก mutable progressที่คาดว่าจะเปลี่ยน
  จาก immutable/economic digest ไม่บังคับ progress digestคงเดิมหลัง recovery

### ลำดับเดียวหลังอนุมัติ

| ขั้น | งาน/เงื่อนไขผ่านก่อนเดินต่อ | เวลารวม setup/วิเคราะห์ |
|---|---|---|
| P0 | แก้ NC14/NC15/W4 coverage; review diff; targeted publisher/control/schedule/SLA/restore tests, real-DB overlap/idempotency/financial matrix และ Ruff/format/mypyที่กระทบ | 1.5–3 ชั่วโมงสำหรับ implementation/checks |
| P1 | Freeze candidate; ตรวจ disposable DB/Redis, VM/container/CPU/RAM/pools/workerinventoryเดิมจาก approved profile/NC13 runner, sleep prevention และ schedule digest | 5–10 นาที |
| P2 | W1 fresh DB/real workers/explicit child5Hz: dedicated LOSS→RESET→opening blocked และ baseline100×20ผ่านก่อน measured600s; stop schedule/counters/SLA/resource/financialครบ | 20–30 นาที |
| P3 | W1ผ่านจึง W2 fresh DB100commands/s300s; concurrent10 dedicated stops/duplicate/lost-ack/stale-resume/fairness/overflowเดิม | 15–22 นาที |
| P4 | W2ผ่านจึง W3 fresh DB10commands/s1800s; faults7ครั้งตาม JSONเดิม, platform windows/alertจริง≥60s/retry/recovery/RSSเดิม | 40–50 นาที |
| P5 | W3ผ่านจึง W4 source/targetDBใหม่ schemaเดียวกัน explicit childสำหรับbuild; stop/risk/economic/role oraclesครบ | 15–25 นาที |
| P6 | Reconcile affected regression/production-browser evidence ใช้ CIเดิมเฉพาะ source/configที่ยังตรง; สรุปทุก oracle/งานค้างใน checkpointเดิม | 10–15 นาที |

P1–P6 รวม **105–152 นาที**; รวม P0 ประมาณ **3.25–5.5 ชั่วโมง** หากผ่านครั้งแรก
ไม่รวมรออนุมัติ/แก้failure/remoteCI งบ1–2ชั่วโมงเดิมไม่รวม harnessที่ยังขาดและไม่ใช่เวลารับรอง
ไม่เพิ่ม short diagnosticอัตโนมัติเมื่อ targeted real-worker matrixพิสูจน์สิ่งเดียวกันแล้ว

ทุก attemptใช้ outputใหม่และเก็บ Failed/Partial/failure branchก่อนแก้ ไม่ overwrite หรือ
rerun inputเดิม. ห้ามลด owners/load/duration/threshold, pause coreเพื่อให้scenarioผ่าน,
เพิ่มทรัพยากร หรือเปลี่ยน production/source mechanismนอก amendmentโดยไม่อนุมัติ
พบ production bottleneck/ช่องว่างเงินหรือความเสี่ยงให้หยุดเสนอ amendmentก่อนแก้
ผ่านครบให้ส่ง checkpoint ไม่เปิดPRเอกสารวนบันทึกCI; Gitทำเมื่อเจ้าของสั่งตามเดิม

### ผลรอบ Set-5 แรก — 2026-11-01

P0 implementation/targeted checks ผ่าน; W1 fresh schema0062 บน frozen source
`8da984f63d73c70f9fafed2f6810ad4e640efdf11acc805a9163a618727c3633` **Failed**
ที่ measured+121.09s เพราะ core cycle1 ใช้60.009sและถูกยกเลิกขณะรอ API pool connection
ใน request-result polling. SELL commandของ cycleนั้น SUCCEEDED แต่ orderยัง ACCEPTED
เมื่อหยุด; API pool peak15/15 เป็น observed failure branch ไม่ใช่ข้อพิสูจน์ต้นเหตุทั้งหมด
ไม่มี committed one-shot trade จึงยังไม่ผ่าน NC14ภายใต้โหลด แม้ targeted matrixผ่าน
W2/W3/W4 และ final acceptance ไม่เริ่ม ตามเงื่อนไขหนึ่ง W1/หยุดเมื่อ failure
รายละเอียด/P0 failures/diagnosticsอยู่ใน checkpointและ `validation-artifacts/f19-set5-20261101/`

### NC-F19-16 bounded pool/transaction diagnostic — Approved 2026-11-01

ไม่ใช่การอนุมัติ rerun W1: เสนอใช้ failed DB/receipts/worker metricsเดิมก่อน แล้วเพิ่ม
instrumentationเฉพาะ harness เพื่อแยก connection queue, SQL/transaction time และ worker latency
ซึ่ง logsเดิมยังระบุไม่ได้ว่า pool starvationเกิดจาก phaseใดหรือเป็นผลของ downstreamที่ช้า

- Reuse `profile_resources.PoolEvidence`, `profile_dispatch_timing.py` และ
  `profile_timing.py`; จับ pool wait/checkout/checkin กับ owner/action/request/command identities
  แยก INTAKE, READY_HINT, REQUEST_VIEW และ worker transaction; ไม่ log SQL params/secrets
- Capture bounded DB wait/transaction metadata และ VM/container resource samples ให้สัมพันธ์
  timestampเดียวกัน ไม่เพิ่ม workers/pools/CPU/RAM หรือเปลี่ยน lock/policy/financial code
- หลัง targeted instrumentation tests: อนุญาต diagnosticหนึ่งรอบ fresh DB, core100×20,
  W1 command10/s, child5Hz, source/scenarios/stop scheduleเดิม; จำกัดช่วงสังเกต180s
  เพื่อครอบคลุม cycleที่ล้มราว+120s. ต้องประกาศ `acceptance_result=false` ตลอด
  และหยุดที่ failureแรก; 180sนี้ไม่แทน W1 600s หรือใช้รับรอง SLA/Full Validation
- ไม่เพิ่ม retry NEW/RESET, ไม่ปรับ polling/deadline/threshold และไม่เริ่ม W2/W3/W4จากผล diagnostic
  ใช้ผลแยก harness/product/environment; production fixหรือเปลี่ยน profileต้อง amendmentก่อนลงมือ
- ประเมิน instrumentation/checks20–40นาที และ diagnostic/setup/วิเคราะห์15–30นาที
  รวม35–70นาที ไม่รับรองว่าจะปิด root causeได้ครบหากหลักฐานยังขาด

เจ้าของตอบ “approve” ต่อ NC-F19-16 แล้ว อนุญาต instrumentation/targeted checks และ diagnostic
หนึ่งรอบตามส่วนนี้เท่านั้น; W1ยัง Failed/Pending Full Validation ไม่เรียก Completed/เปิด Live

### NC-F19-17 scheduled one-shot consumer barrier — Approved 2026-11-01

**สถานะ: Approved — เจ้าของตอบ `apprve` ต่อข้อเสนอ NC17; อนุญาต implementation/checks
และ W1หนึ่งรอบหลัง targetedผ่าน ตามขอบเขตด้านล่าง**

เหตุผลจาก NC16: target order ACCEPTED/resting/queue0 แล้ว แต่ trade1568ที่ commitครั้งเดียว
ถูกข้ามเมื่อ owner REBASE1566→1575. รอบ processถัดไปเริ่มหลัง oldest inputเกิน1s;
pool acquisitionของ processนั้น0.000659s. จึงต้องแก้การประสานเหตุการณ์ fixture
ไม่ใช่เพิ่ม pool หรือถือว่าพบ root causeของ API-pool timeoutใน W1รอบแรกแล้ว

แนวทางที่เสนอคือ **ส่ง one-shot เมื่อ target worker อยู่ที่ recovery-read boundaryจริง**
ภายใต้โหลดเดิม แทนการส่งทันทีที่ parentเห็น resting. ใช้ deterministic interleaving
เหมือน process-recovery testsเดิม โดย productionเลือก owner/claim/recoveryเองตามปกติ
ไม่มี fast lane, forced recovery หรือการเรียก matchingแทน worker

ของเดิมที่จะใช้ซ้ำ:

- `backend/tests/infra/execution_market/test_process_recovery.py`: child process barrier
  หลัง claim/ก่อน sourceใช้จริง; ใช้แนวทางนี้ ไม่ใช้ sleepเดาว่า workerพร้อม
- `backend/tests/infra/risk_limits/profile_publisher_process.py`:
  `encode`/`receive`, bounded async IPC/control serialization/child health;
  `profile_publisher.py:publish_one_shot`: one publicationและ committed receiptเดิม
- `profile_workload.py:Fixture.spawn`, `wait_one_shot_resting`,
  `scheduled_partial_trade`, `prepare_partial_bot` และ `profile_stop_runtime.py`:
  arm/cleanup/stop scheduleเดิม ไม่สร้าง order executorใหม่
- `backend/src/tiewtrade/infra/paper_orders/worker.py:_recovery_inputs`:
  ใช้เป็นตำแหน่ง observationใน test processเท่านั้น ไม่แก้ production file
- `test_set5_acceptance.py` และ publisher/control testsเดิม: real-worker overlap,
  financial oracle, fault/cleanupและ idempotency coverage

#### Implementation ที่ขออนุมัติ

1. เพิ่ม helperเฉพาะ harness `profile_partial_barrier.py` สำหรับ arm/READY/COMMITTED/CLOSED
   ใช้ async IPC framingเดิมและ endpointชั่วคราวใน runner. Parentเป็นผู้สั่ง publisherเพียงรายเดียว;
   ไม่เพิ่ม DB schema, Redis, pool, workers หรือ infrastructureสำหรับ application
2. Parent armหลังตรวจ durable target ACCEPTED/resting/queue0. Identityต้องมี run/key,
   owner/wallet/episode/order/pairและ generation. เป้าหมายคือ matching pairของ ownerนั้น:
   commandของ baselineใน pairเดียวกันอาจ drive targetได้ จึงไม่ผูกเฉพาะ NEW commandของ target
3. Opt-in wrapperใน **paper worker test process** เข้าเฉพาะ `_recovery_inputs` ของ state
   ที่มี target open/restingตรง identity. หลัง original `read_latest_book` คืน recordจริง
   แต่ก่อน original following `read_inputs(after=book.input_id,limit=19)` ให้ส่ง READY
   พร้อม claim/worker/backend/book identities แล้วรอ publisher receipt
4. Parentส่ง controlหนึ่งครั้งผ่าน PublisherLinkเดิม; child publish BOOK/PRICEตาม cadenceเดิม
   และ one-shot price2/quantity0.5/resting_side BUYบน tickปกติ. เมื่อ receiptยืนยันcommit
   ให้คืน COMMITTEDแก่ worker แล้ว original following readดำเนินต่อจาก bookที่อ่านจริง
   ไม่แทน return values, ไม่ inject decisions, ไม่กรอง inputs, ไม่บังคับ rebase และ
   ไม่แก้ received_at/verified_at/clock/freshness/risk context/claim lease
5. ผูก receiptกับ armed key/generationและตรวจว่า tradeอยู่ใน bounded following batch
   หลัง captured bookจริง. Normal BOOK/PRICEและ core workเดินต่อระหว่าง barrier;
   ไม่ pause publisherหรือทั้ง worker fleet และไม่เปลี่ยน owner scheduling/priority
6. Barrierเพิ่มเวลารอเฉพาะ target transactionและต้องถูกนับใน timing/resourceตามจริง.
   ใช้ deadlineที่ไม่เกิน freshness budget1sของ captured bookและเวลาที่เหลือก่อน scheduled
   partial-stopเดิม (+120sในW1); ห้ามยืด existing60s wait/cycleหรือเลื่อน +120/+150s.
   เกินงบ, ไม่พบ natural recovery boundaryทันเวลา หรือ freshness gateปฏิเสธ ให้ Failed
   พร้อม stage/identities ไม่ fallbackไปส่งอิสระหรือส่งซ้ำ; รอบที่ไม่มี recoveryไม่ถูกบังคับให้เกิด
7. Armต้องมีผู้ใช้สิทธิ์ได้ครั้งเดียวใน parent. ก่อนส่ง controlให้ mark delivery attempted;
   timeout/ACKสูญหาย/unknown commitต้องเก็บสถานะ unknown/failed ไม่ retry publication.
   Duplicate READYไม่สร้าง controlเพิ่ม; identityผิดหรือ receiptขัดกันต้อง fail closed
8. Cleanupทุก exit: release/cancel/join IPC handlers, restore monkeypatch/listeners,
   clear pending controlตามของเดิม และคืน pool. ห้ามลบ committed source/fill/audit facts;
   worker/parent/publisherตายต้องไม่ทิ้งการรอแบบไม่มีกำหนด
9. เปิดใช้เฉพาะ explicit F19_SET5 child scheduled partial scenario; F18 defaults,
   dedicated LOSS_LIMIT scenarioและ application runtimeไม่เปลี่ยน. Helperไม่ใช่ session
   หรือ persistent business store; authorization/financial factsยังอยู่ DBตามเดิม

#### การพิสูจน์และลำดับดำเนินการ

- เริ่ม targeted protocol/barrier tests: identity mismatch, duplicate READY, single publication,
  lost ACK/unknown commit, worker/parent disconnect, cancellation และ patch/IPC cleanup
- Real PostgreSQL + real paper workers + child publisher: ใช้ scenario/financial oracleเดิม
  พร้อม core BUY/SELL overlap. ตรวจ captured book→committed trade→persisted INPUT→exact
  one fill0.5/spent1→stop/cancel/release→resumeและ request/audit identitiesครบ
- Negative caseต้องพิสูจน์ว่า delayed/stale tradeยังถูก production fail-closed/rebaseตามเดิม
  และ harnessรายงาน Failed ไม่ refresh/replay source; ทดสอบ unarmed/other-owner/non-recovery
  pathsว่าไม่ถูก gateหรือเปลี่ยนผล และ no-recovery/dead workerจบภายใน bound
- Real-DB checkต้องยืนยันว่า following readเห็น committed tradeใน isolationปกติ และไม่มี
  publication-fence/DB lockที่ทำให้ child commitรอ workerที่กำลังรอ receiptเป็นวงจร;
  ถ้าพบให้หยุด ไม่แก้ isolation/lock orderingหรือ productionนอก amendment
- รันเฉพาะ affected regressionและ Ruff/format/mypy. Reuse P0/NC16หลักฐานที่ไม่กระทบ;
  production/DB concurrency safety testsเดิมที่ helperเกี่ยวข้องต้องยังผ่าน
- หาก targetedผ่าน ให้ freeze candidate/hashและตรวจ resource inventoryเดิม แล้วรัน **W1
  acceptanceหนึ่งรอบ** fresh DBตาม P2 (600s/core100×20/10commands/s/child5Hz)
  ไม่เพิ่ม180s diagnosticซ้ำ. รวบรวม source window/SLA/stop schedule/economic evidenceครบ
- W1ผ่านครบจึงเดิน P3–P6ตาม Set-5ที่อนุมัติไว้ ไม่ถามซ้ำงานย่อย; failureใดให้เก็บ Failed
  และวิเคราะห์ก่อนขั้นถัดไป ห้าม rerun unchanged. W1รอบเก่ากับ NC16ยังคง Failed

ประมาณ implementation+targeted checks **45–90นาที**, W1/setup/วิเคราะห์ **20–30นาที**;
ถ้า W1ผ่าน งาน W2/W3/W4/reconcileยังใช้เวลาตาม P3–P6เดิม ไม่รวมใน65–120นาทีนี้
แจ้งเวลารวมก่อนเริ่มแต่ละชุดยาวตามกฎโครงการ. ไม่รับรองว่าจะผ่าน: barrierแก้ fixture
delivery raceเท่านั้น; API-pool/worker latencyหรือ SLAที่เหลือต้องพิสูจน์ด้วยผลจริง

#### จุดอนุมัติและทางเลือก

ข้อเสนอแนะนำ: อนุมัติ NC17ตามขอบเขตข้างบน โดยคง requirements/เกณฑ์เดิมทั้งหมด
หากไม่ต้องการ coordinationภายใน worker ให้คง Failedและแยกงานวิเคราะห์/ปรับ production
scheduling เป็น amendmentอื่นก่อน (ยังไม่มีหลักฐานให้เลือก production fixที่ถูกต้อง).
การขยาย freshness/ส่ง tradeซ้ำ/ลดโหลดไม่อยู่ในข้อเสนอนี้

จุดอนุมัติ NC17ปิดแล้วจากคำตอบ `apprve`; ไม่มี Needs Clarificationค้างสำหรับขอบเขตนี้
ยังต้องหยุดเมื่อพบ failure/production gapหรือจำเป็นต้องเปลี่ยนแผนตามกฎเดิม

#### ผล NC17 — 2026-11-01

Implement harness consumer barrierแล้ว; production/API/schemaไม่เปลี่ยน. Targeted regression100,
real-worker matrix3 และ frozen Linux16ผ่าน รวม stale/unarmed/other-owner/protocol faults,
financial overlapและ recovery safety; Ruff/format/mypyผ่าน. Preflightแรก Failedเพราะ restart
workerก่อน arm จึงไม่มี READY และทิ้ง active fixtureที่ทำให้ restore testถัดไป timeout;
เก็บ Failedแล้วแก้เฉพาะลำดับ preflight/cancel-join ก่อนตรวจใหม่บนfresh DB ไม่แก้ restore

W1หนึ่งรอบ source `dfd4cce5d4702afcb6dfee1e80347b6783bf035be0e1480201ede9ac1ec17a13`
รันครบ600s/elapsed610.629s: commands6000/cycles1200/fills2400/cancels1200/replays1200,
RESET100/100, stop/resume, source3000/channel, per-owner financial/global invariantsและ
resource/pool/connection cleanupผ่าน. Barrierส่ง trade1325ครั้งเดียวหลังbook1323 และ
original following readเห็น [1323,1324,1325]; scheduled partial/stop/resumeสำเร็จ

**W1 Failed — risk SLA**:918703/918703 samples acknowledged แต่1302เกิน3s
(service99.858278%, ต้อง99.9%); owner quotaไม่ผ่าน56/100. อีก3 samplesของownerเดียว
เกิน5s สูงสุด5.034698s. Hard missesเกิดก่อนbarrier activation จึงไม่ใช่เวลารอbarrierนั้น
Engine transaction p95/p99=0.218810/0.339924sผ่าน. สาเหตุ SQL/lock/queueของ risk tail
ยังไม่ยืนยัน ห้ามอนุมานจาก NC16คนละcandidateหรือปรับquota/freshness/resourceเพื่อผ่าน

เก็บfailed DB/hash/receipts/log/result/analysisใน `validation-artifacts/f19-set5-20261101/`;
หยุดก่อนP3–P6และไม่ rerunW1. ขั้นถัดไปคือเสนอแผนวิเคราะห์/แก้ risk service latency
จากfull-run evidenceนี้ ก่อนเปลี่ยน productionหรืออนุมัติ timed runใหม่. V-20คงFailed/
Pending Full Validation และV-21..24 Pending Dependency ไม่มีcommit/pushใน checkpointนี้

### NC-F19-18 risk-stage/commit diagnostic — Approved 2026-11-02

**สถานะ: Approved 2026-11-02 — เจ้าของสั่ง `approve NC-F19-18` แล้ว**

เจ้าของสั่งทำแผนวิเคราะห์หลักฐานเดิมและจัดทำข้อเสนอนี้เมื่อ attributionไม่พอ;
คำสั่งนั้นคงจุดอนุมัติแยกของ diagnosticไว้ ไม่ใช่การอนุมัติ300s runนี้ล่วงหน้า
ผลวิเคราะห์อยู่ที่ [risk-latency analysis](evidence/risk-latency-analysis-2026-11-02.md)

#### หลักฐานและเป้าหมาย

Independent reconstructionตรง original1302 late/918703 expected/3 hard samplesทุกidentity.
ไม่มี duplicate input/stream time regression;1239 late samplesปิดgapด้วยrisk worker,
63ด้วยpaper workers. PostgreSQL logsยืนยันconfigured owner-advisory-lock timeouts137ครั้ง
ในช่วงที่ตรวจ รวม11ครั้งที่+50..65s และ25ที่+240..270s แต่ไม่ผูก owner/round/backend
กับ acknowledgementเดิมได้. ยังไม่มีเหตุพอเลือกแก้ scheduling/SQL/locksหรือปรับevaluator

เป้าหมายคือแยก input-ready→selection→slot/pool/lock→snapshot/replay/persist→server commit
→client observation ไม่ใช้ observer timingหรือความใกล้ของthresholdเป็นเหตุลดเกณฑ์

#### ของเดิมและ instrumentation ที่ขออนุมัติ

- Reuse `profile_pool_timing.py`, `profile_dispatch_timing.py`, `profile_resources.py`,
  `profile_memory.py` และ workload `telemetry`/`diagnostic_window`; เพิ่ม helperเฉพาะharness
  `profile_risk_timing.py`. ไม่แก้ production fileหรือสร้างเครื่องมือworkloadใหม่
- ใช้ scoped wrappers/ContextVarใน risk test process: wrap monitor round/selection result,
  semaphoreและfunctionsจริง. Semaphore observerต้องแทน aliasเฉพาะrisk moduleในtest
  ไม่แก้global asyncio.Semaphore. เก็บ selected order/due_at/fairness cursor, round/attempt,
  owner, queued/slot-acquired timestamps โดยไม่เปลี่ยน rows, orderingหรือslot count
- ใช้ pool checkout hooks/PIDจากdriverเดิม; จับ outer/reentrant owner-lock callsแยก,
  snapshot, replay, persist, final-state verificationและtransaction exit. Query timings
  aggregateตามSQL hashภายในspan ไม่ serializeSQL/parameters/financial payloads/error text
- แยกstageและoutcomeของ timeout; เก็บเฉพาะ exception class/SQLSTATEจากdriver hookเมื่อมี
  ห้ามเดาlock/statement timeoutจาก DatabaseTimeoutErrorชื่อเดียว. Snapshot metadataมี
  captured watermark, cursor/boundary before/after, pendingและ replay budgetsเดิม
- เพิ่มcommit identityเฉพาะdiagnosticใน final-state verification SELECTเดิมของtelemetry
  ทุกwriter เพื่อให้เชื่อม63paper samplesได้ด้วย; phase tracingเต็มมีเฉพาะrisk worker.
  เก็บstate-row xminและcurrent transaction identityโดยไม่บังคับสร้างXIDในread-only transaction
- Collectorในparentใช้migrator poolเดิม lookup `pg_xact_commit_timestamp`แบบbatchหลังcommit.
  ยืนยันrow writer XIDกับtransactionก่อนใช้เวลานั้น; mismatch/NULL/lookupไม่สำเร็จเป็นUNKNOWN
  ห้ามแทนด้วยเวลาrestore/เวลาclientหรือแก้original acknowledgement. ไม่ให้collectorรอใน
  risk-owner critical section และไม่เพิ่มpool/grants/server settings
- DB wait samplesใช้existingmigrator poolทุก2s พร้อมpg_blocking_pids/PIDsและVM/container
  resourcesเดิม. NULL metadataถือว่าunknown. ไม่ถือว่าตรวจไม่พบwaitเท่ากับไม่มีwait;
  ถ้าไม่มีblocker attributionให้รายงานข้อจำกัด ไม่เดาpaper writerเป็นต้นเหตุ
- Timingใช้monotonicสำหรับdurationและUTCสำหรับjoin; เก็บobserver flush durationและ
  event-loop delayเพื่อเห็นoverhead. Buffer flushทุก1s; cap100000 owner spansและ100000
  commit-proof recordsต่อprocess/window, SQL hash buckets≤64/span. Truncated/write/collector
  failuresต้องทำให้diagnosticไม่สมบูรณ์ ห้ามทิ้งrecordsแล้วสรุปว่าpassed
- เก็บsetupเฉพาะaggregate; traceช่วงmeasured0..300sพร้อมtailของงานที่เริ่มในwindow.
  Restore patches/listenersและcancel/join collector/IPCทุกexit; ephemeral observer state
  ไม่ใช่application sessionหรือauthoritative business data

#### Diagnostic หนึ่งรอบและ controls

เพิ่มexplicit `--risk-diagnostic-seconds 300` ในworkload CLI; ใช้ได้เฉพาะF19_SET5/W1/child,
ห้ามใช้ร่วม CHECK/preflight/dedicated-lossหรือdiagnosticอื่น และrejectworker flagsบนparent
Parentส่งworker-only trace/proof flagsให้risk/otherwritersตามหน้าที่ข้างบน

หลังtargeted checksผ่าน ให้ freezeใหม่/manifest hashและตรวจ inventoryเดิม. รันfresh
disposable DBหนึ่งครั้ง: core100×20baseline,10commands/s,10paper workers/monitor concurrency4,
existing pools/CPU/RAM,child5Hz,NC17barrierและstop/RESET scheduleเดิม. W1 profileยัง600s
แต่ diagnosticยกเลิก/joinที่observation300sเพื่อครอบคลุม+54และ+240 windows

ประกาศ `acceptance_result=false` และdiagnostic-onlyตั้งแต่manifest. ครบwindowคือ
OBSERVATION_COMPLETE ไม่ใช่SLA/W1 Passed; การยกเลิกที่cutoffแยกจากfailureก่อนcutoff
งาน/resetที่ยังไม่ถึงจุดจบไม่ถูกนับเป็นsuccess. Failureก่อนcutoffหยุดและเก็บFailed.
ไม่rerunถ้าmissไม่เกิด ไม่เริ่มW2/W3/W4 และไม่ใช้shortened countersแทนacceptance

#### Checks / การตัดสินใจหลังได้ผล

1. Observer testsพิสูจน์originalrows/results/semanticsไม่เปลี่ยน, owner/round propagation,
   actualslot count, stageของtimeout, redaction/cap/cleanup/cancellationและdisabled defaults
2. Real-DB testsตรวจsuccessful commitกับrollback/savepoint rollback/current-XID mismatch,
   NULLcommit proofและcollector failure; ไม่ackuncommitted/pendingcursor. ใช้pg timestampจริง
   ไม่มีการบวก/ลบobserverdelayสมมติออกจากSLA
3. Affected scheduler fairness/slow-owner, snapshot/replay/transient breach/fence/idempotency
   testsเดิม พร้อม Ruff/format/mypyตามdiff. ไม่รันfull regressionหรือW1เพื่อทดสอบobserver
4. หลังone diagnostic สร้างต่อowner/input latency budgetพร้อมcoverage/residual time,
   timeout/deferral historyและ server-vs-observed delay. อธิบายว่าstageใดทำให้late/next-round
   ไม่ใช่แค่stageที่มีp95สูง; unlinked/unknown spansต้องแสดงชัด
5. ถ้าพิสูจน์evaluatorผิด เสนอharness-only fixและnew assessmentแยกจากoriginalFailed;
   ถ้าพิสูจน์productionจุดใดเป็นต้นเหตุ เสนอamendmentระบุจุดแก้/invariants/targeted repro/
   rollbackก่อนลงมือ. ถ้ายังunknown ให้ส่งcheckpointข้อมูลที่ขาด ไม่เพิ่มrunอัตโนมัติ

Production amendmentใดต้องคง chronological replay/ทุกtransient breach, owner/publication
fences/lock order, atomic latch/stop/audit, pending-source fail-closed, RESET/idempotency,
Money/Quantityและdatabase/RLSauthority. ห้ามแก้ด้วยเพิ่มconcurrency/pool/resources,
ขยายtimeout/freshness,ข้ามinput,ลดquotaหรือเพิ่มNEWretry. Public API/schemaไม่เปลี่ยน
ถ้าจำเป็นต้องเปลี่ยนให้เสนอแผนใหม่. ไม่มีproduction fixหรือ600sW1rerunอยู่ในNC18นี้

ประมาณ instrumentation/checks/setup/300s run/analysisรวม **60–90นาที** หลังอนุมัติ;
แจ้งประมาณเวลาก่อนเริ่มrunจริงอีกครั้ง ไม่รวมproduction implementation/W1ใหม่.
ผลเดิมNC17/V-20ยังFailed/Pending Full Validation; ไม่เรียกCompletedหรือเปิดLive

จุดอนุมัติ NC18ปิดแล้ว อนุญาตinstrumentation/checksและ300sdiagnosticหนึ่งรอบตามส่วนนี้
ไม่มีproduction fixหรือW1acceptanceใหม่ในขอบเขต และยังคงจุดหยุดเมื่อหลักฐานไม่พอ

#### ผล NC18 — 2026-11-02

Targeted116/Linux38/Ruff/format/mypyผ่าน. Diagnosticหนึ่งรอบครบ300.392s,
`acceptance_result=false`, ไม่มีfailureก่อนcutoff. Stage/commit streams13ชุดปิดครบไม่truncated;
24920proofs:23648VERIFIED/1272UNKNOWN. มี933observed late samples/155ackgroups;
0hard5s misses แต่552inputsยังไม่ackตอนplanned shutdown จึงไม่ใช่W1/SLA acceptance

ยืนยันqueue causeในprobe: owner attempt10129/round106รอsemaphore3.161157sเอง
ก่อนpool0.013317s/owner-lock0.000890s/snapshot0.012062s/replay0.010731s;
server latency3.411689s.8linked groupsมีslot wait≥3s. ก่อนselection+slotwaitกิน97.48%
ของoldest-input budgetsของ150linked groups (ไม่ใช่CPUseconds; preselectionรวมfailedattempts).
170server locktimeouts,168ผูกPID/timeกับrecordedtransactionได้. การรอfull100-owner
page/4slotsและรอทั้งroundก่อนscanใหม่ทำให้actual3s violationsเกิดขึ้นจริงในprofileนี้

148/152verified late groupsยังเกิน3sที่server commit;4groups/12samplesข้ามthresholdเฉพาะ
client observation. ไม่ปรับverdictNC17ย้อนหลัง;1272mismatch proofsคงUNKNOWNและไม่มี
หลักฐานparent/sub-XIDmappingให้เดา. Observerflush11.519sและloop-delaymax0.094352s
เป็นaggregateตลอดsetup+measurement ไม่ใช่controlledoverhead comparison.
Hard5sของNC17ไม่เกิดซ้ำ จึงไม่อ้างว่าพบต้นเหตุของทุกoldmiss

ReportmetadataเดิมบอกRESETไม่exercisedไม่ตรงกับjournal100APPLIED; แก้futuremetadata
ให้แสดงprogressจริงและคงoriginalartifactโดยไม่rerun. No production edit/W1rerun;
รายละเอียดใน [risk-stage diagnostic](evidence/risk-stage-diagnostic-2026-11-02.md)

### NC-F19-19 bounded rolling monitor admission — Approved 2026-11-02

**สถานะ: Approved 2026-11-02 — เจ้าของอนุมัติ `approve NC-F19-19`**

ข้อเสนอแก้queueที่พิสูจน์ในNC18 ไม่ใช่เพิ่มกำลังเครื่องหรือผ่อนSLA. ต้องยืนยันด้วย
targetedcounterexampleและW1จริง ไม่รับรองว่ากรณีhard5sเดิมหรือallrisklatencyจะหายทั้งหมด

#### จุดแก้และการใช้ของเดิม

1. ใน `services/engine/risk_limit.py` แยกclosureประเมินownerจาก
   `run_risk_monitor_round` เป็นinternalasync helper `_evaluate_monitor_owner(engine, owner_id)`.
   ย้ายtransaction/ownerlock100ms/statement700ms/snapshot/initialize-or-replay/
   acknowledgeและexception→processed/deferred/skippedเดิมโดยไม่เปลี่ยนเนื้อหา
2. ย้ายcandidate SELECTเดิมเป็นinternalscan helperที่ใช้ร่วมกัน. คงPAPEReligibility,
   hints/UUIDcursorและboundedlimit1..100. เพิ่มexcludeรายการUUIDของlocalactiveowners
   ในSQL **ก่อนLIMIT** ด้วยboundparameters; emptyexcludeคงquerysemanticsเดิม.
   คืนrowsจริงที่มีuser_id/mode/due_at ไม่สร้างsnapshotcacheหรือauthoritative hintsใหม่
3. `run_risk_monitor_round` ยังคงsignature/resulttype/defaults/pagecursorเดิม และเรียก
   helpersข้างบนภายใต้semaphore/gatherเดิม เพื่อรักษาexistingcallers/tests. Emptyexclude
   ต้องให้selection/order/resultเทียบเท่าเดิม
4. เปลี่ยนเฉพาะmonitor loopใน `services/engine/risk_limit_main.py` เป็นrollingadmission:
   localmap owner→taskไม่เกินMONITOR_CONCURRENCY=4, เก็บcursorแบบเดิม. เก็บผลtaskที่จบ
   แล้ว scanได้ไม่เกินจำนวนslotว่างและexcludeactiveowners. Advancecursorเป็นUUIDแถวท้าย
   ของผลscanก่อนจัดdue_atpriorityภายในselectedbatch แล้วเริ่มหนึ่งtaskต่อownerทันที
5. เมื่อ4slotsเต็ม ให้awaitFIRST_COMPLETED แล้วเก็บผล/refill ไม่รอ100-ownerpageจบ.
   เมื่อไม่มีeligiblecandidate ให้poll20msตามเดิม ไม่busyloop; activeownerที่ยังทำงาน
   ไม่ถูกเลือกซ้ำในinstanceเดียว. ไม่มีคิวownerที่เลือกไว้ล่วงหน้าเกินslotว่าง
6. ต่อinstanceมีowner-evaluationtasks≤4; enginepool4/requestpool1/stoppool2/scanpool3,
   workerprocesses/CPU/RAM/load/freshness/deadlinesยังเท่าเดิม. Scanfrequencyเปลี่ยนตาม
   slotcompletionเป็นส่วนที่ตั้งใจแก้ ไม่อ้างว่าเป็นเพียงrefactor; บันทึกactualscan/slotinventory
7. Localactive map/cursorเป็นephemeralschedulerstateเท่านั้น. PostgreSQLยังเป็นauthority,
   ownerlocksเดิมคุมcross-instanceและriskstate/latch/stop/audit. Restartเริ่มscanใหม่ได้;
   ไม่มีpersistentjob/sessionที่สูญหายหรือsticky-session/newRedis requirement

#### Failure modes และ invariants

- เฉพาะPaper monitor; request/stop loopsและLivecontractsไม่เปลี่ยน. ไม่มีNEWretryหรือ
  per-ownerretryloopขณะถือslot: deferredattemptคืนslotและให้futurefairscanเลือกตามปกติ
- Scan failure/uncaughttaskfailureต้องpropagateผ่านserve TaskGroupตามเดิม ไม่ซ่อนerror
  แล้วปล่อยriskserviceดูhealthy. Shutdownต้องcancel/joinactive4ก่อนdisposepools
- คงowner/publicationfencesและlockorder, boundedchronologicalreplay/ทุกtransientbreach,
  atomiclatch+stop+audit, pending-sourcefail-closed, RESET/idempotency และRLSscopeเดิม
- ห้ามย้ายauthoritativechecksออกจากtransactionหรือเพิ่มglobal/in-memoryriskcache.
  Money/Quantity, fee/PnL/position/balance/orderlogicไม่เปลี่ยน
- Boundsและcandidateeligibilityเดิมยังคุมfairness. ห้ามpriorityhotownerซ้ำจนownerอื่น
  starve; exclactiveใช้แค่localinflight ไม่ใช่ปิดownerที่ต้องรับผิดชอบ
- ปรับharnessmanifest/observerให้ระบุrollingturn/free-slotspansแทน100-pagequeueอย่างชัดเจน;
  observerที่จับlinkageไม่ได้ต้องรายงานincomplete ไม่สร้างemptytraceแล้วเรียกผ่าน
- PublicAPI,DBschema/migrationและdurablestateไม่เปลี่ยน; internalhelperinterfacesเท่านั้น

#### Tests / acceptance และ rollback

1. Deterministiccounterexample: readyownerใหม่ถูกเลือกได้ขณะunrelatedslowtaskยังไม่จบ,
   maxinflight4, selected≤free slots, ไม่มีduplicateownerในlocalactive. ใช้barrierassert
   ลำดับเหตุการณ์ ไม่ใช้mockwallclockตัวเลขเพื่ออ้างว่าSLAผ่าน
2. Fairness: >100owners/wraparound, locked/failedowner, continuouslyeligibleowner,
   newlyeligibleownerระหว่างactivework และsettingsหาย/disabled; ทุกeligibleownerมีโอกาส
   ถูกscanโดยไม่ต้องรอทั้งpage, activeexclusionไม่ซ่อนhealthyownerหลังLIMIT
3. RealPostgreSQL: ownerlocktimeout/final-state/rollback/cancellation;2instancesแข่งownerเดียว
   แล้วไม่เกิดduplicatebreach/stop/audit/cursorcorruption. ใช้oldrisktransactionhelperจริง
4. ExistingroundAPIequivalence, monitor/snapshot/replay/fence/transientbreach,
   intake/source-pending/RESET,financial/idempotency safetytestsที่เกี่ยวข้อง และRuff/format/
   mypy/importboundaries. ตรวจscheduler/harnesschangesเฉพาะdiff ไม่fullsuiteเป็นพิธี
5. เมื่อtargetedผ่าน ให้freezecandidateและตรวจprofileinventory แล้วรัน **W1หนึ่งรอบ**
   freshDB600s/100×20/10commands/s/child5Hz/NC17barrierตามเกณฑ์F19เดิมครบทั้งหมด:
   ทั้งowner/run99.9%≤3s,ทุกinput≤5s พร้อมsource/counters/resource/financialoracles
6. W1ผ่านครบจึงP3–P6ตามSet-5ที่อนุมัติไว้. ถ้าtargetedไม่พิสูจน์ประโยชน์หรือW1ล้ม
   ให้เก็บFailed/diagnoseและหยุด ไม่ลองbatchsizeอื่น/เพิ่มconcurrencyหรือrerununchanged

Rollback: คืนmonitor loopให้เรียกlegacy `run_risk_monitor_round(limit=100,concurrency=4)`
และ20mssleepตามเดิม; ไม่มีmigration/ลบfacts/ปลดstopหรือauto-resume. Keepfailedartifacts
และบันทึกruntimehash ไม่อนุญาตdeployment/productionactivationหรือGitจากamendmentนี้

ประมาณimplementation+targeted **60–120นาที**, W1/setup/analysis **20–30นาที**;
ไม่รวมW2/W3/W4/requiredCI. Approvalที่ขอรวมproductionchangeตามscopeนี้+targeted+
W1หนึ่งรอบเมื่อchecksผ่าน เพื่อไม่หยุดขอซ้ำระหว่างงานย่อย. Commit/pushยังต้องสั่งต่างหาก

อนุมัติ production scheduler implementation, targeted checks และ W1 หนึ่งรอบเมื่อ checks ผ่าน
ตาม scope ข้างบน; V-20 ยังคง Failed/Pending Full Validation จนมีผลใหม่ครบเกณฑ์

### NC-F19-19 execution checkpoint — 2026-11-02

Rolling four-slot admission/shared scan/owner transaction and observer inventory implemented.
The authoritative transaction/exception body is AST-identical to the old evaluator.
Targeted35 passed; regression95 passed/1 fixture failure from a global STOP backlog beyond
the bounded20 scan. Fresh-DB concurrency/pending/financial26 passed with unchanged assertions.
Linux43 passed; default markers initially excluded four fresh-global tests. The first W1
setup was aborted before load, then explicit fresh-global4 passed. Final targeted9 passed;
Ruff/format/mypy seven files and seven import contracts passed.

`nc19-w1-r2`: **Failed / environment invalid**, before load. Baseline100x20 and dedicated
LOSS_LIMIT partial/stop/RESET/opening-blocked completed; subsequent BOT resting NEW rejected
SOURCE_UNAVAILABLE. The launcher created a new DB but all nine role URLs still pointed at
the preflight DB due mutable temporary env/string replacement. This cannot establish
scheduler/SLA acceptance or a production root cause. Keep Failed artifacts, both actual
and empty intended DB dumps, and the pending-replay window with its missing TX linkage.

Prepared a parsed-URL/role-inventory guard, verifying all nine actual database identities
and empty public schema before migration; self-test and real read-only verification passed.
No further production change. Owner approved `approve W1 fresh DB rerun` on 2026-11-02:
one replacement W1 on a verified fresh DB using the reviewed guard. This resolves the
rerun approval blocker. Keep the approved failure stop rule and original criteria;
V-20 stays Failed / Pending Full Validation until valid acceptance evidence passes.
Details: [NC19 report](evidence/rolling-monitor-2026-11-02.md).

### Authorized replacement W1 result — 2026-11-02

Owner's `approve W1 fresh DB rerun` executed as `nc19-w1-r3`. All nine actual role
connections, pre-migration empty public schema and post-migration empty fixture were
verified; schema0062 and the same tested source hash. Baseline100x20/dedicated LOSS_LIMIT
partial/stop/RESET/opening-blocked and manual/BOT resting setup completed.

**Failed** after recorded37.594s of load: child BOOK publisher SourceUnavailableError.
No completed600s/SLA verdict. Source journal has one confirmed wall-time reversal:
line3606->3607 wall -16.857ms while monotonic +18.732ms, adjacent to publisher failure.
The exact failing guard's SQL clock/book timestamps were not captured; clock causality
is still a hypothesis. No production fix, tolerance or resource increase follows from it.
Partial safety/cleanup passed as scoped in [report](evidence/w1-fresh-rerun-2026-11-02.md).
Keep Failed/dumps/raw72files. Stop before another timed run/W2/W3/W4.

### NC-F19-20 BOOK freshness/clock diagnostic — Approved 2026-11-02

**Status: Approved 2026-11-02 — owner authorized `approve NC-F19-20`.**

Goal: distinguish the exact BOOK freshness failure condition from a generic source error,
using the r3 clock anomaly as evidence to select the observation point. This amendment
does not select a production/environment fix or relax the original acceptance criteria.

Reuse `profile_publisher.py`, `profile_publisher_process.py`, the existing bounded
`diagnostic_window` in `profile_workload.py`, source receipt journal and the reviewed
`runner_database_guard.py`; no new publication mechanism or SQL observer process.

1. Add an opt-in scoped observer in the child test publisher around the existing
   `BookState.require_ready`. Call the original unchanged; only on its existing exception
   record input/generation/process identities, ready flag, received/verified/source times,
   and the exact `now` argument supplied by `publish_input`. Record which existing
   comparison is false, plus paired wall/monotonic times. Re-raise the original error;
   do not retry, replace timestamps or alter query results/authorization/scheduling.
2. No prices, quantities, SQL parameters, secrets or arbitrary exception messages in trace.
   Bound failure records (32); cap/write failures mark diagnostic evidence incomplete,
   never authorize a trade. Restore patches on every exit. Capture during setup too,
   so an early failure is not hidden behind load activation. No authoritative memory cache.
3. Reuse existing publisher category/stage reporting and receipt clocks. Do not enable
   the heavier SQL/backend SourceTimeline observer or add connections/pools/processes.
   Report observer call count/timing and its measurement limits; no claimed zero overhead
   or subtraction of guessed overhead from acceptance latency.
4. Add an explicit test-only W1/F19_SET5/child diagnostic option for60s observation,
   exclusive with other diagnostics and worker flags. Use the existing diagnostic cutoff;
   acceptance_result=false always. Add one explicitly allowed NC20 disposable DB name to
   the launcher guard, with same structured URL/all-nine actual connection/empty schema
   checks. Fresh DB/output/env; inventory must pass before seed.
5. Before running: controlled ready/future-received/future-verified/stale/not-ready/source-time
   cases must preserve the original return/exception, with exact reason flags; check scope
   restoration, cap/redaction, CLI exclusivity and resource inventory. Reuse relevant
   publisher tests, run affected Ruff/format/mypy. No full suite or production changes.
6. Run **one non-acceptance60s diagnostic** with100core owners x baseline20,10commands/s,
   ten Paper workers, monitor4/request1/stop2/scan3, child5Hz, same CPU/RAM and NC17 barrier.
   Do not pad source windows, force fill/READY, increase timeouts, add NEW retry or change
   financial logic. Scheduled work beyond60s is Not Exercised, not Passed.
7. On failure keep Failed and diagnose exact recorded branch; on no reproduction report
   Not Reproduced and stop. Never repeat automatically. No replacement W1 or W2/W3/W4
   authorized by this diagnostic. Propose any production/environment fix separately
   from the captured evidence, preserving original fail-closed and timing criteria.

Estimated instrumentation/targeted checks20–40min, setup/60s run/analysis10–20min
(latest fresh setup211s), total30–60min. Approval would cover this scoped harness change,
targeted checks and one diagnostic without intermediate reapproval; excludes Git/deploy
and further acceptance workloads. V-20 remains Failed/Pending Full Validation.

Options before another experiment: (A) read-only host/VM clock configuration and log review,
about10–20min, may identify an environment cause but cannot recover missing guard arguments;
(B) approve the scoped diagnostic above,30–60min including implementation/setup/analysis,
to capture the exact guard if it reproduces. No automatic environment edits or timed rerun.

### NC-F19-20 execution checkpoint — 2026-11-02 / Not Reproduced

Owner approved NC20; child-only observer/explicit60s mode/complete-evidence checks implemented.
94Linux tests passed/zero skips/10.044s; Ruff/format/mypy six files pass. Frozen tested source
`aa3fcb7009f53678ebe8b9b8765966a49b302ed29740f7df7270ffe094650cc8` unchanged during run;
no production edits. All-nine-role/fresh-schema/empty-fixture guards passed before seed.

One `nc20-r1` setup181.451s, baseline100x20/dedicated LOSS_LIMIT/RESET/manual-BOT setup
completed; observation60.600486s, OBSERVATION_COMPLETE/non-acceptance.1203guard calls,
zero failures, trace closed/complete. **Not Reproduced**; no exact failed guard arguments
from r3 recovered. No observed clock reversal among3599receipts, not a global stability proof.
Partial financial/cleanup checks and cancellation warnings retained; no full SLA/oracle pass.

Stop under item7: no rerun or additional workload. Recommended next scope is read-only
host/VM clock configuration/existing-log review, about10–20min, awaiting owner direction.
No production/environment fix selected from a non-reproduction. V-20 remains Failed /
Pending Full Validation. [NC20 evidence](evidence/book-clock-diagnostic-2026-11-02.md).

### Clock environment review — 2026-11-02

Owner requested read-only review. Host timed logs confirm NTP receipt/apply activity
before and after r3, but no time-aligned apply event at09:41:25. No recorded sleep/wake
or VM restart near failure; caffeinate assertions span the run. Resources match profile.
Retained VM logs do not identify a clock setter. Current UI switch unreadable: admin-only
systemsetup and Computer Use denied twice, including owner-requested retry. No settings,
services, production code or workload changed. No specific fix is proved. See
[clock environment review](evidence/clock-environment-review-2026-11-02.md).

### NC-F19-21 clock-only host/VM comparison — Approved 2026-11-02

**Status: Approved 2026-11-02 — owner instructed `เริ่มทำ` after the NC21 proposal.**

Purpose: localize a clock discontinuity to host, guest, or an uncertain interval before
choosing an environment remedy. This is not a trading/load reproduction or acceptance run.

1. Reuse saved r3/NC20 clock journals and current environment inventory. Prepare one
   bounded20min passive trace,10samples/s, on the current host and one disposable guest
   observer using the already-loaded runner image. No PostgreSQL/Redis/Paper workers,
   CPU stress, Live/API calls, network access or secrets in the probe.
2. VM CPUs/RAM/settings unchanged. Guest observer unprivileged, read-only root filesystem,
   network none, no added capabilities/host mounts; explicit maximum0.1CPU/64MiB. Only
   timestamp evidence on stdout; host saves it to a new artifact directory. Do not stop
   unrelated containers, restart Docker or alter clock synchronization.
3. Each sample brackets a wall-time read with monotonic-before/after in its own clock
   domain. Keep source sequence/PID and read-duration bounds. Do not subtract host and
   guest absolute monotonic values. Host request/receive timing bounds transport delay;
   intervals with clock changes or wide/overlapping uncertainty remain Unknown.
4. Compare wall-minus-monotonic offset intervals within each domain to detect a step
   even if adjacent wall timestamps still increase. Preserve all raw samples and
   uncertainty; do not turn an arbitrary detection threshold into a trading allowance.
   Cap30000records and bounded buffers; gaps/truncation/write failure mean incomplete.
5. Collect existing timed and Docker lifecycle logs for the same window without changing
   logging levels or privileges. Host step and guest step alignment supports an origin
   hypothesis; it does not identify an unlogged setter or prove the r3 guard condition.
6. Before sampling: controlled clock-step/no-step/slow-read/transport-uncertainty/gap/cap/
   cancellation tests, resource/privilege inventory and relevant static checks. The
   observer must never call clock_settime/adjtime/settimeofday or application/DB code.
7. Run exactly once. No anomaly -> Not Reproduced and stop; anomaly -> localize only as
   evidence permits and propose a fix separately. Never auto-extend, rerun W1, relax
   freshness/SLA or treat a clock-only result as trading/acceptance evidence.

Estimated implementation/checks15–25min plus setup/20min observation/analysis25–35min,
total40–60min. Approval would cover this probe/checks/one trace only, excludes system
settings changes, production/environment fixes, Git/deployment and trading workloads.
Alternative: environment administrator investigates retained evidence; no further run
until a justified remedy/proposal. V-20 stays Failed/Pending Full Validation.


### NC-F19-21 execution checkpoint — 2026-11-02

22 probe regressions passed, zero skips; Ruff/format/mypy two files passed. One20min10Hz
trace completed:12000 contiguous exchanges, no gaps, guest exit0/noOOM, source verified.
40 guest offset movements recur at median29.999772s, including24 decreases(max2.994309ms).
Host has no offset decrease;504 increase intervals align with logged positive NTP adjtime,
not504 discrete steps.11930 conditional transport bounds/70 retained Unknowns; selected
sequence400 supports guest-relative backward offset movement beyond uncertainty.
Exact setter and original r3 guard cause remain unproved; no trading failure reproduced.
No setting/production/criteria changes or W1 rerun. Diagnostic complete/non-acceptance;
V-20 Failed/Pending Full Validation, dependencies unchanged. Next: separate environment
remediation proposal/approval; no automatic further diagnostic. See
[NC21 evidence](evidence/clock-comparison-2026-11-02.md).


### NC-F19-22 — Linux validation proposal / Superseded by same-machine audit

สถานะ: **Superseded 2026-11-02 — เจ้าของไม่ต้องการใช้เครื่องอื่น; เก็บข้อเสนอเดิมเป็นประวัติเท่านั้น**
ไม่มีการจัดหาเครื่องหรือpreflight/W1ตามข้อเสนอเดิม ให้ใช้แผนsame-machine auditด้านล่างแทน
เจ้าของสั่ง `เริ่มทำ` เพื่อจัดทำแผนต่อจาก NC21; คำสั่งนี้อนุญาตการจัดทำข้อเสนอเท่านั้น

#### เหตุผลและทางเลือก

NC21 ยืนยัน guest-relative offset decrease ใน Docker Desktop โดยไม่มี trading load;
ยังไม่รู้ setter และยังไม่พิสูจน์สาเหตุ r3 ส่วน NC17 risk-latency failure ยังไม่ปิด
จึงไม่เลือกลด freshness/SLA หรือแก้ production จากหลักฐานนี้

| ทางเลือก | ผลกระทบ / ข้อจำกัด |
|---|---|
| **แนะนำ: Linux environment แยกสำหรับ validation** | แยกออกจาก Docker Desktop บน Mac ที่พบอาการ ใช้ Docker/runner เดิมเท่าที่รองรับ; ต้องยืนยันเครื่องและ resource profile ก่อน อาจมีค่าใช้จ่ายและผล CPU/I/O ต่างจากเดิม ไม่ถือว่าเร็วขึ้นเพราะโค้ดแก้แล้ว |
| ให้ผู้ดูแลแก้ guest timekeeping บนเครื่องเดิม | รักษา topology เดิม แต่ตอนนี้ยังไม่มี setting/patch ที่พิสูจน์ว่าแก้ได้ ต้องมีข้อเสนอเฉพาะจากผู้ดูแลก่อนเปลี่ยน ไม่สลับ virtualization backend/update/restart/ปิด sync เพื่อทดลองเอง |
| พัก workload และคง blocker | ไม่มีค่าใช้จ่ายหรือการเปลี่ยนระบบเพิ่ม; F-19 ยัง Pending Full Validation |

ข้อเสนอนี้เลือกทางแรกแบบมีเงื่อนไข ไม่รับรองว่า Linux จะไม่มี clock movement หรือทำให้
W1 ผ่าน เป็นการแยก environment ที่มีหลักฐานผิดปกติออกจาก acceptance candidate
ไม่จำเป็นต้องรู้ชื่อ setter เดิมก่อนย้าย แต่ห้ามประกาศว่าแก้ root cause เดิมแล้ว

#### Needs Clarification — บล็อก execution แต่ไม่บล็อกการจัดทำแผน

- เจ้าของระบุ Linux host ที่อนุญาตให้ใช้ พร้อมช่องทางเชื่อมต่อและยืนยันเป็น disposable
  validation environment; ห้ามส่ง password/API secret ลง spec/chat ใช้ช่องทาง credential เดิม
- ยืนยันสิทธิ์สร้าง/ลบเฉพาะ test DB, Redis namespace และ containers ของงานนี้
  หากต้องซื้อ/เช่า/เพิ่ม infrastructure ต้องระบุวงเงินและขออนุมัติก่อน ไม่มีสิทธิ์จัดซื้อโดยปริยาย
- ยืนยัน target inventory เทียบ approved profile: CPU architecture/model, effective CPU/RAM
  limits, kernel/clocksource, Docker, storage, image/dependencies, clock synchronization
  และโหลดร่วม ถ้าไม่ตรงให้แสดง diff และหยุดก่อน timed run ไม่ถือว่าจำนวน vCPU เท่ากันแล้วเทียบเท่า

#### ลำดับทำงานที่เสนอ — อนุมัติรวมได้หลังยืนยัน target

1. **ตรึง candidate และ manifest**: ใช้ working-tree content hashes รวม uncommitted NC19–21
   ไม่ใช้ HEAD เพียงอย่างเดียว; runner image เดิม, lockfiles, schema0062 และ source/config
   ของแต่ละ role ต้องตรง ทิ้ง runtime secrets ออกจาก artifacts ใช้ read-only inventory ก่อน
   ARM64 target เป็นตัวเลือกแรกเพื่อ reuse image เดิม หาก image/architecture ไม่ตรง หยุดเสนอ
   compatibility amendment ไม่ rebuild ข้าม architecture แล้วถือว่าหลักฐานเดิมใช้ได้ทั้งหมด
2. **เตรียม isolated environment**: ใช้ bootstrap/migrate/fixture/config guards เดิมใน
   `backend/tests/infra/risk_limits/` และ `profile_workload.py`, `profile_memory.py`,
   `profile_restore.py`; ไม่สร้าง runner/financial oracle ซ้ำ ใช้ fresh disposable DB และ
   Redis แยก ตรวจ actual DB ทั้ง9roles/empty fixture/schema ก่อน seed เช่น NC19-r3
   จำกัด CPU/RAM ตาม approved manifest (เดิม VM8CPU/3,043,373,056bytes รวมขอบเขตบริการ)
   พร้อม limits ของแต่ละ container เดิม ห้ามจัด limit เท่านี้ให้ทุก container แยกแล้วรวมเกิน
   ระบุ host OS/service overhead และ enforcement boundary ให้ตรวจได้; หาก enforce/เทียบ
   budget ไม่ได้ให้หยุด ห้ามเพิ่ม pools/concurrency/resources/deadlines ให้ผ่าน
3. **Targeted portability/safety checks**: reuse scheduler/concurrency/fresh-global guards,
   publisher/BookState และ relevant DB safety tests ที่ได้รับผลจาก environment/dependency
   เท่านั้น ใช้ commands/versions จากหลักฐานเดิม บันทึก selection และผล ไม่รัน full suite
   ซ้ำหากไม่มีผลกระทบ หากต้องแก้ harness/code ให้หยุดระบุ diff และตรวจ scope ก่อน
4. **Environment preflight หนึ่งรอบ300s**: reuse NC21 `profile_clock_probe.py` และ analysis
   เดิม 10Hz bounded trace พร้อม existing clock/lifecycle logs บน target ตรวจ guest wall/
   monotonic และ bound uncertainty ภายในเครื่องนั้น (อย่าสมมติว่ามี Mac host domain)
   ช่วงนี้เป็น diagnostic/non-acceptance, acceptance_result=false เสมอ ไม่สร้าง tolerance
   ใหม่ หากพบ backward offset movement ที่ bound exclude0, sampling incomplete หรือ
   แยกเวลา/transport ไม่ได้ ให้ถือว่า readiness ยังไม่พิสูจน์และหยุด ไม่สุ่มเปลี่ยน setting
   หรือรันซ้ำ การไม่พบใน300sไม่ใช่หลักฐานรับรอง clock ตลอด W1
5. **W1 หนึ่งรอบเมื่อ1–4ผ่านและเจ้าของอนุมัติขอบเขตนี้**: fresh DB ใหม่จาก preflight/tests;
   F19_SET5 100owners×baseline20, dedicated LOSS_LIMIT→stop effects→RESET→opening blocked,
   600s/10commands/s, child publisher5Hz,10Paper workers, monitor4/request1/stop2/scan3,
   NC17 barrier/stop schedule และ RESET retryNC09เดิม คง owner/run99.9%≤3s และทุก ready
   input≤5s พร้อม source/financial/resource/counter oraclesครบ ไม่เพิ่มretryNEWหรือผ่อนfail-closed
   ใช้ clock evidence เดิมของ acceptance harness จับต่อทั้ง setup/load/drain ไม่เพิ่ม observer
   ลง W1 โดยไม่ประเมิน overhead การล้มทุกแบบเก็บFailed/DB/logs/hashes แล้วหยุดวิเคราะห์
6. **ปิด checkpoint**: รายงาน source/environment/manifest hashes, setup/measurement/drain
   จริง, completeness, uncertainty, SLAและsafety verdictแยกกัน W1ผ่านจึงพร้อมเดินW2/W3/W4
   ตามvalidationเดิม ไม่เริ่มในNC22นี้ ไม่ regrade NC17/r3 หรือแทน required CI ด้วยlocalผลใหม่

#### สิ่งที่ไม่เปลี่ยน / rollback

Public API/schema/domain/authorization/financial arithmetic ไม่เปลี่ยน ไม่เปิดLive ไม่ปิด
clock synchronization หรือเปลี่ยนmacOS/Docker Desktopบนเครื่องเดิม ไม่เพิ่มclock tolerance
และไม่แตะ user containers ค่าresource/load/SLAเดิมเป็นเงื่อนไขตรวจ ไม่ใช่ตัวเลือกให้ผ่อน

Rollback: หยุดเฉพาะ processes/containers ของNC22 เก็บlogs/dump/manifestก่อน cleanup;
ลบเฉพาะ disposable targets ที่ inventory ยืนยันและเจ้าของอนุญาต ไม่ restore หลักฐานFailed
ทับ ไม่เปลี่ยน default connection ให้ชี้กลับผิดเครื่อง เก็บ target config แยกจากlocalเดิม

ประมาณเวลาเมื่อhost/accessพร้อม: inventory/setup/targeted checks20–40นาที,
clock preflightพร้อมวิเคราะห์10–15นาที, W1setup/load/drain/analysis20–35นาที,
รวม50–90นาที ไม่รวมจัดหาเครื่อง/แก้portabilityหรือfailure ใช้ผลจริงแทนการรับประกันผ่าน
แจ้งประมาณการใหม่ก่อนเริ่ม timed batch หาก inventory ทำให้ขอบเขตเปลี่ยน

จุดอนุมัติ: เจ้าของเลือก target และอนุมัติNC22พร้อม environment manifest ก่อนเปลี่ยนระบบ
สามารถอนุมัติรวมข้อ1–6รวมconditional W1เพื่อไม่หยุดขอซ้ำระหว่างทาง แต่หากข้อมูลtargetยังขาด
หรือprofileไม่ตรง การอนุมัติทั่วไปไม่ใช่สิทธิ์เดาenvironment/เพิ่มงบ/เปลี่ยนcriteria
ตอนนี้ **ยังไม่รันหรือเปลี่ยน environment**; V-20 Failed/Pending Full Validationตามเดิม


### NC22 local preparation — owner instructed เริ่มทำ (2026-11-02)

เริ่ม preparation ตามคำสั่งเจ้าของ: ตรวจ connection inventory แบบread-only พบเฉพาะ
local Docker contexts `default`/`desktop-linux` (active) และไม่มี `~/.ssh/config`;
ไม่พบ target ที่ยืนยันสิทธิ์ใช้เป็นdisposable Linux validation environment จากข้อมูลที่ตรวจ
นี่ไม่ใช่ข้อพิสูจน์ว่าเจ้าของไม่มีเครื่องอื่น จึงขอชื่อhost/SSH aliasและสิทธิ์ใช้งานไว้แล้ว

สร้าง local content-hash inventory ของsource/tests/schema/lock/config ที่เกี่ยวข้องใน
`validation-artifacts/f19-set5-20261101/nc22-preparation/`; ยังไม่ใช่final candidate freeze
ต้องตรวจซ้ำก่อนexecution ระบุreuse runner/DB guard/clock probeเดิม ไม่มีremote connection,
service/config/code changesหรือtest/workloadเพิ่ม การเริ่มทำไม่ยกเลิกtarget/manifest gates
ของNC22; ยังไม่ถือว่าอนุมัติเครื่อง/งบ/profileที่ไม่ระบุ และไม่ต้องขอเริ่มpreparationซ้ำ
ขั้นถัดไปที่บล็อก: รอเจ้าของระบุtarget/accessและยืนยันdisposable scope แล้วตรวจinventory
เพื่อเสนอmanifestจริงก่อนเปลี่ยนenvironmentหรือtimed run ผลFailed/Pendingเดิมไม่เปลี่ยน


### NC-F19-22 replacement — same-machine measurement audit / Approved and executed 2026-11-02

สถานะ: **Approved — owner explicitly instructed PLEASE IMPLEMENT THIS PLAN**
ใช้เครื่องปัจจุบันเท่านั้น ยกเลิกLinux target/access/budgetเป็นprerequisiteของงานนี้
ไม่เปลี่ยนsettings/production ไม่รันworkloadหรือclock diagnosticใหม่ ไม่ลดSLA/resources/load

ขอบเขตที่อนุมัติ: ใช้รายงานNC17/18/19-r3/20/21เดิม ตรวจhash/source snapshotและช่องว่าง
commit/clock ทำตารางclock domains/identities/precision ตรวจearliest valid acknowledgement
ทุกworker, rollback/pending guards, denominator/setup/load/drain แยกserver commitจากclient
observation และประเมินuncertaintyเฉพาะหลักฐานที่ครอบคลุม ห้ามใช้เวลาหลังrestoreแทนต้นทาง
ห้ามนำNC21~3msไปชดเชยรอบอื่น ลบsampleหรือเปลี่ยนเป็นmonotonicโดยไม่มีidentityเชื่อม
ใช้existing non-DB regressions;เก็บผลใหม่แยก ไม่overwriteFailedเดิม คาด20–30นาที

ผล:261rawhash entriesตรงทั้งหมด,9sourcefilesตรงhash; originalNC17/18workloadและNC18
observer sourceไม่สามารถกู้จากsnapshotที่มีได้ บันทึกgapไม่อ้างsourceใหม่แทนNC17/18
18non-DB regressionsผ่าน/zero skips และ5controlled cases NC17reconstructตรงเดิม
918703samples/1302>3s/3>5s/56ownersไม่ผ่านquota NC18มี23648verified sourcecommit proofs
และmonotonic semaphorewait3.161s;ความช้าไม่อธิบายได้ด้วยclient observationอย่างเดียว
Clock continuity/oldnormal-telemetry transaction identityยังไม่พอrecertifyphysicalelapsed

พบMedium guard defect: sla_summaryใช้heapq.mergeแต่ไม่ตรวจper-stream timestamp ordering
controlledย้อนหลัง00.500→00.400ให้passed=true/clock_errors0 ขณะที่4run×11ackstreamsจริง
ไม่มีtimestampregression จึงไม่ใช่คำอธิบายผลFailedเดิม หยุดตามแผนก่อนแก้harness

**Proposed narrow fix, awaiting approval:** validateorderingทุกstreamก่อนpending/ownerfilter;
retainfile/line/time metadata, rejectmeasurement evidenceเมื่อregression; equaltimeยังvalid
ไม่sort/drop/clamp/shiftเพื่อให้ผ่าน Additivestream-order error metadataแยกจากnegative-latency
counterเดิม Tests:regressedwould-pass/would-miss/equal/interleavedworkers/pending/foreignowner
พร้อมboundary/quota/missingacksเดิม ไม่เปลี่ยนproduction/settings/schemaหรือเพิ่มtimedrun

[Measurement audit](evidence/measurement-audit-2026-11-02.md) แยกพิสูจน์ได้/defect/หลักฐานไม่พอ
ครบ งานauditเสร็จ;ขั้นต่อไปรออนุมัติguardpatchเท่านั้น ไม่เริ่มW1หรือdiagnosticต่อเอง
V-20Failed/Pending Full Validationและdependenciesคงเดิม ไม่มีcommit/push


### NC22 stream-order guard — Approved 2026-11-02

Owner instructed `approve` for the narrow patch proposed in the measurement audit.
Validate every consumed worker acknowledgement stream before pending/owner filtering;
retain bounded file/line/timestamp diagnostics and the total regression count, permit
identical timestamps, and reject the overall measurement verdict on any regression.
Use parsed timestamp keys consistently in the existing streaming merge; preserve every
row and all existing thresholds/denominators. Reuse the evaluator and its existing tests,
with cases for would-be pass/miss, ordered interleaving/equality and filtered rows.
No production/settings/schema/resource/financial change or timed run. After targeted
non-DB tests and changed-file static checks, report the checkpoint; no automatic W1.


### NC22 stream-order guard checkpoint — 2026-11-02

Owner approved the narrow guard fix. Implemented in `profile_workload.py::sla_summary`
and covered in `test_workload_sla.py`. Each stream is validated before pending/owner
filtering, including trailing rows after all inputs have acknowledgements. Parsed datetime
keys keep validation and merge ordering consistent. Equal timestamps remain valid; every
row is preserved, with no sorting/dropping/clamping/clock correction. All regressions are
counted; only the first20 file/line/timestamp diagnostics are retained. Additive fields
`stream_order_errors` and `first_stream_order_errors` are separate from `clock_errors`.
Any ordering error forces overall passed=false; existing numerical SLA counters remain.

27 non-DB regressions passed, zero skips (18 existing +9 cases): would-be pass/miss under
F18/F19, filtered pending/foreign-owner rows, equality, earliest interleaved worker results,
and bounded diagnostics with full error count. Ruff/check, format/check and mypy two files
passed. Initial mypy invocation could not resolve local src and reported235 import/type
errors; corrected invocation `MYPYPATH=src` passes without source/config suppression.
DB rollback/savepoint tests reused; no services/workload/settings/production changes.

Artifacts: `validation-artifacts/f19-set5-20261101/nc22-stream-order-guard/` contains test
XML, static log/summary, exact evaluator patch and candidate hashes. Original audit/run
artifacts remain unchanged. Historical audit.py expects the prepatch evaluator (matched
NC20 snapshot retained in audit snapshots); its counterexample assertions must not be
rerun against the patched evaluator as though they were new acceptance criteria.

Guard defect fixed, not an environment/latency fix. Existing44 real acknowledgement files
were ordered, so this does not explain or regrade original failures. V-20 remains Failed /
Pending Full Validation; W2/W3/W4 and dependencies unchanged. Next recommendation: review
this narrow patch before deciding the next clock/acceptance amendment; no automatic timed
run or new diagnostic. No commit/push. This subtask does not trigger full-feature Ready
for Code Review or authorize refactor/full validation.


### NC22 guard refactor — owner authorized 2026-11-02

Owner instructed `refactor the code` after the narrow guard review passed. Reuse existing
`inputs`, `risk_acknowledgement` and evaluator tests. No existing shared JSONL writer was
found; the existing F15 `save` writes whole JSON, not JSONL. Consolidate repeated writes
only in newly added guard tests into a local `write_risk_stream` helper. Replace positional
previous-row state in the guard with named previous-time fields and derive adjacent line
number from enumeration. Preserve error counts/cap/metadata, merge keys, input bytes and
all verdicts. No unrelated refactor. Run27 non-DB regressions and two-file static checks;
reuse unaffected DB/safety evidence. Existing stop forbids a new W1/diagnostic.


### NC22 guard refactor checkpoint — 2026-11-02

Owner-authorized refactor complete, limited to the guard and its new tests. Named previous
observed/raw timestamp fields replace tuple indexes; adjacent line identity comes from
enumeration and filename is computed once per stream. Local `write_risk_stream` removes
repeated JSONL serialization in the new tests; existing fixtures/ack builders remain in
use. Preservation test compares original bytes. Verdicts, counters, cap20, diagnostics,
merge/filter order and all SLA/financial behavior unchanged; no new infrastructure.

27 non-DB tests passed, zero skips; two-file Ruff/check, format/check and mypy passed
(`MYPYPATH=src`). Validation after refactor covers only the affected Feature/evaluator
criteria; DB/safety evidence remains valid. Approved stop on timed runs still applies:
no W1, other workload, new diagnostic or settings change. No production change.

Artifacts in `validation-artifacts/f19-set5-20261101/nc22-stream-order-refactor/` retain
before-source copies, exact refactor diff, test XML, final hashes and check summary.
This finishes the authorized guard/refactor checkpoint. Next: owner may instruct commit/
push of this checkpoint under Git rules; no Git action occurred. V-20 Failed/Pending Full
Validation and clock/old-latency/source-evidence limitations remain; do not infer a W1pass.


### NC-F19-23 clock-setter identification — Approved 2026-11-02

Owner approved one bounded clock-only diagnostic on the current Mac/Docker runtime.
Keep the existing 8 CPU / 3,043,373,056-byte VM, pinned Set-5 runner image, load,
pools and original SLA. Do not switch VMMs, change NTP/settings, production/schema/
financial code, start trading workers or databases, or run W1.

Gate implementation with a read-only capability preflight. It must find usable tracefs,
private instances, `mono` trace clock and syscall entry/exit events for `clock_settime`,
`settimeofday`, `adjtimex` and `clock_adjtime`. The observer is root in the VM host PID
namespace with only `CAP_SYS_ADMIN`: privileged=false, no SYS_TIME/SYS_PTRACE, network
none, read-only root,0.1 CPU/64MiB, no Docker socket, and only tracefs plus frozen source
mounted. Do not relax seccomp/AppArmor or install/restart anything. A failed capability
gate stops this amendment before full instrumentation; no alternate tracing method.

If and only if the gate passes, reuse NC21's pure bracketed clock helpers in a separate
private-ftrace observer. Capture one maximum90s run at10Hz with64KiB perCPU buffers
(512KiB total), retain only bounded/redacted syscall identities and timings, cap output
at16MiB/10000records, and mark gaps/write failures/drops/overruns Incomplete. A parent
watchdog must disable/remove only this run's instance on every exit; cleanup-only retry
uses the same privileges and may not touch other instances. Diagnostic result is always
`acceptance_result=false` and is never repeated just because no event reproduces.

Classify evidence as Confirmed/Candidate/Unknown/Not Reproduced/Incomplete under the
approved interpretation: a paired successful realtime `clock_settime`/`settimeofday`
identifies a caller but not r3 causality; successful adjtimex variants remain candidates
without mode/payload. Correlate only within this run's uncertainty. Separately verify the
existing NC19 rolling-scheduler source/hashes still preserve its authoritative transaction,
lock order, concurrency4, fairness and cleanup; do not change or rerun it without a
specific evidence gap. Preserve all prior Failed evidence and V-20 Failed/Pending Full
Validation. Environment/production repair and another W1 require separate approval.


### NC-F19-23 execution checkpoint — Incomplete 2026-11-02

The approved read-only capability gate ran against the unchanged VM and pinned image.
Its container profile matched the requested root/host-PID/CAP_SYS_ADMIN-only bounds, but
the read-only `/sys/kernel/tracing` bind did not contain `trace_clock`. The gate therefore
could not prove tracefs/private-instance/`mono`/required-event availability and stopped
after0.565s, exit1/noOOM. No private instance or event was created, so no tracing cleanup
was needed. Full instrumentation/tests, the90s observation and all trading/DB/W1 work were
not started. No fallback, install, restart, confinement relaxation or setting change.

The current NC19 risk-limit source and scheduler test hashes exactly match the measured
NC19 candidate manifest, so prior evidence for authoritative transaction/lock order,
concurrency4, UUID fairness and cancellation/engine cleanup remains applicable. No
scheduler source/test changed or reran. Setter remains Unknown; classification Incomplete,
not Not Reproduced. See [NC23 preflight evidence](evidence/clock-setter-preflight-2026-11-02.md).
V-20 stays Failed/Pending Full Validation; a new environment/diagnostic amendment and
owner approval are required before any tracing enablement, alternative or W1.


### NC-F19-24 ephemeral in-namespace tracefs mount — Approved 2026-11-02

NC23 established that Docker Desktop's LinuxKit host path exists but is not a mounted
tracefs. Kernel documentation requires mounting `tracefs` before `trace_clock`, events
and private instances exist. Docker documents `SYS_ADMIN` as the mount capability and
states that its default seccomp profile adjusts to selected capabilities; do not disable
seccomp or AppArmor. Sources:
[kernel ftrace](https://www.kernel.org/doc/html/latest/trace/ftrace.html),
[Docker run capabilities](https://docs.docker.com/engine/containers/run/), and
[Docker seccomp](https://docs.docker.com/engine/security/seccomp/).

**Owner approved `approve NC-F19-24`:** retain the same Mac, Docker runtime,
8CPU/3,043,373,056-byte VM and pinned runner. Replace the failed host-path bind only with
an ephemeral tracefs mount inside one observer container's private mount namespace. The
container remains privileged=false, host-PID, network none, read-only root,0.1CPU/64MiB,
cap-drop ALL plus SYS_ADMIN only, no SYS_TIME/SYS_PTRACE and `no-new-privileges`; use the
default seccomp/AppArmor profiles without overrides. A bounded tmpfs under `/run/nc24`
provides the mount point. No Docker socket, host filesystem, application secrets,
PostgreSQL, Redis, trading workers, settings change, Docker restart or package install.

Phase A performs one conditional mount preflight: verify exact inventory and proc
capability/seccomp/LSM state, confirm `tracefs` in `/proc/filesystems`, mount it only in
the observer namespace, then require private instances, `mono` and all eight syscall
entry/exit events. If default confinement denies mount or any capability is absent, unmount
if needed, stop **Incomplete** and do not change seccomp/AppArmor or use privileged mode.

Only when Phase A passes in that same execution may Phase B run the already approved
maximum90s/10Hz observation. Create one UUID-scoped private instance, select `mono`, set
64KiB perCPU buffers, enable only the four approved syscall entry/exit pairs and retain
at most10000records/16MiB. Parse in memory and persist only sequence, PID/TID, bounded
process name, syscall, entry/exit, return code, timing and `clock_settime` clock ID; discard
pointer values and raw lines. Missing pairs/identities, drops/overruns, output failures or
caps classify Incomplete. All results remain `acceptance_result=false`.

Cleanup disables this instance, clears only its events/buffer, removes its directory and
unmounts the container-private tracefs on every exit. The Mac parent verifies container
exit and may start one cleanup-only helper with the identical profile and exact UUID if
the observer dies; it must not enumerate/remove other instances. Failure to verify cleanup
is reported and stops. Retain mount/trace/cleanup timings and observer resource overhead.

Before execution, implement controlled tests for mount gate/failure, exact inventory,
event parsing/pairing/redaction/caps, uncertainty, cancellation/death and own-instance-only
cleanup, plus relevant Ruff/format/mypy. Recheck NC19 hashes only; its prior safety tests
remain valid unless source differs. No production/API/schema/financial/scheduler change,
SLA adjustment, W1 or repeated trace. Classification and causal limits remain NC23's.

Rollback is container exit plus verified private-instance removal and namespace unmount;
there is no persistent Docker/NTP setting to restore. If kernel state cannot be verified
clean afterward, report the exact residue and stop. This approval covers implementation,
controlled tests and one conditional execution only; it does not cover a repeat, W1,
settings/environment remediation or production changes.


### NC-F19-24 execution checkpoint — Incomplete 2026-11-02

Implementation and controlled checks completed:45 tests passed with Ruff check/format
and mypy. The one authorized container matched the approved profile and ran5.772s,
exit2/noOOM, but its sanitized result existed only on container tmpfs and was lost at exit.
Therefore exact mount/trace/outcome/cleanup evidence is unavailable and the run is
Incomplete; it was not repeated.

The single cleanup-only helper verified CAP_SYS_ADMIN-only, NoNewPrivs1 and Seccomp2,
then failed before mount because `/proc/self/attr/current` was unavailable. Its no-op
cleanup fields cannot prove the exact instance was absent, so cleanup remains unverified.
The executed observer reads the same LSM path before mount under the same profile, strongly
supporting the same pre-mount branch but not replacing the missing original result.

Post-run harness-only fixes emit bounded results to stdout, classify the LSM gap explicitly
and refuse cleanup success before mount; final tests/static checks pass. The corrected
observer was not executed. No fallback/helper2/trace repeat, setting, production/DB/trading
or W1 action occurred. See [NC24 evidence](evidence/clock-setter-nc24-2026-11-02.md).
Setter remains Unknown; V-20 remains Failed/Pending Full Validation. Any further cleanup
inspection, environment/diagnostic change or W1 requires a new approved amendment.


### NC-F19-25 final same-machine cleanup and conditional trace — Stopped 2026-11-02

Read-only Docker inventory after NC24 reports daemon security options
`name=seccomp,profile=builtin` and `name=cgroupns`, with no advertised AppArmor or SELinux;
both NC24 containers report empty `AppArmorProfile`, privileged=false, cap-drop ALL plus
CAP_SYS_ADMIN and engine-added `label=disable`. Thus absence of
`/proc/self/attr/current` is consistent with this runtime and is not by itself proof that
the documented Docker confinement changed. NC25 proposes replacing only that invalid
guest-LSM-file gate with a fail-closed host/guest evidence combination.

**Option A (recommended proposal):** one final combined same-machine execution. Before
start, require unchanged8CPU/3,043,373,056-byte VM/base digest; daemon built-in seccomp
and no advertised LSM; container AppArmorProfile empty; privileged=false, host PID,
network none, read-only root,0.1CPU/64MiB/32PIDs, cap-drop ALL plus SYS_ADMIN only,
no-new-privileges, exact bounded tmpfs, no bind mounts/socket/application env. Inside,
require CapEff SYS_ADMIN-only, NoNewPrivs1 and Seccomp2. Any inventory drift stops before
mount. Missing guest LSM file is recorded as expected only while every host criterion
above matches; if daemon advertises an LSM or a container profile appears, missing guest
evidence fails closed.

Use one unbuffered stdout lifecycle stream retained by Docker logs. Emit bounded stage
records before/after mount, exact old-instance check, preflight, trace, instance cleanup
and unmount; emit final result to stdout before exit and keep tmpfs only as a secondary
copy. Short writes, missing stage sequence or missing final result classify Incomplete.

After the namespace-local tracefs mount, inspect only the literal prior instance path
`f19_nc24_202611020756abcd`; never list/remove other instances. Record absent/present.
If present, disable its tracing/events, clear its buffer and remove that exact directory;
failure stops before new tracing. Once exact absence is verified, require private instances,
`mono` and all eight syscall events, then create a distinct exact NC25 UUID instance and
run the existing maximum90s/10Hz bounded observation. Preserve all NC23/24 redaction,
pairing,64KiB-perCPU,10,000-record/16MiB, drop/overrun, classification and causal limits.

Cleanup disables/removes only the NC25 instance and unmounts tracefs. A Mac watchdog
captures Docker logs and validates stage/final sequences. Only if the process dies before
final cleanup may it start one cleanup-only helper for the two literal NC24/NC25 paths;
that helper may not trace or enumerate. No repeat of the observation under any result.

Before execution, add targeted regression for authoritative inventory combinations,
missing/present LSM evidence, old-residue exact cleanup, no enumeration, stdout sequence/
short-write/final-result loss, mount/event failures, observer death and two-name cleanup;
rerun existing NC21/24 tests plus Ruff/format/mypy. Recheck NC19 hashes only. No public
API/schema/production/scheduler/financial/settings/resource/SLA change, DB/trading service,
Docker restart/install or W1.

**Option B:** stop clock-setter investigation now. This avoids another CAP_SYS_ADMIN mount
and preserves the current Unknown/Incomplete evidence, but cannot verify old residue or
identify a setter; V-20 remains Failed/Pending until a separate evidence-backed latency
decision. Choosing B needs no environment action.

Historical proposal only; the owner selected Option B with the SLA amendment and stopped
NC25 before implementation/tests/execution. No NC25 mount/helper/trace is authorized.

Had Option A been selected, NC25 would have been the terminal same-machine ftrace attempt:
if inventory/mount/events/output/cleanup
fail or setter is not reproduced, preserve the result and stop ftrace work—do not create
NC26 or rerun automatically. Any production/environment remedy or W1 remains a later
separate amendment. This text is retained as superseded planning evidence only.


### F-19 SLA and all-or-nothing activation amendment — Approved 2026-11-02

Owner approved RQ-22: per owner and run-wide99.5%≤3s,99.9%≤5s and every ready input≤6s,
with complete acknowledgements and zero clock/measurement errors. Owner also requires
Paper and Live production activation together only after the complete integrated candidate
passes all release/dependency gates. Correctness, stop, idempotency, fail-closed, financial,
source, load, duration and resource criteria remain unchanged. NC25 and further clock
diagnostics stop now.

**Approved implementation plan:**

1. Change only explicit `F19_SET5` acceptance limits/evaluator output in
   `backend/tests/infra/risk_limits/profile_workload.py`; reuse `acceptance_limits()` and
   `sla_summary()`. Keep F-18 R34/default profiles byte-for-behavior unchanged. Represent
   the3s service target,5s tail target and6s absolute ceiling separately; evaluate each
   both per owner and run-wide. Preserve every input, earliest eligible acknowledgement,
   stream-order guard, denominators and setup/load/drain boundaries.
2. Extend the existing `test_workload_sla.py` boundary matrix at exact3.000/3.001,
   5.000/5.001 and6.000/6.001 seconds. Cover aggregate pass/owner fail and inverse,
   missing/pending acknowledgement, clock/stream-order errors, multi-input acknowledgement,
   and unchanged F-18 criteria. No new abstraction outside existing helpers.
3. Re-evaluate frozen NC17 raw evidence offline with the updated evaluator and exact
   candidate/source hashes. Write a separate derived result; never overwrite/relabel the
   original Failed artifact. Confirm expected run-wide and worst-owner fractions at3s/5s,
   max6s, complete acknowledgements, stream order and all non-SLA gates.
4. Remove/exclude NC23/24 observer implementation from the release candidate after
   preserving evidence; no further mount/helper/trace. This diagnostic test code is not
   production behavior and is no longer needed for acceptance. Preserve historical
   artifacts/spec reports; do not delete unrelated user work.
5. Run only affected non-DB evaluator regression plus Ruff/format/mypy. Reuse existing
   production, DB/concurrency/idempotency/financial/review/CI evidence because no runtime
   code changes. Do not rerun W1 now.
6. Mark F-19 Development Complete when its feature gates remain satisfied, while System
   Ready stays blocked by V-20..24 and other Paper/Live dependencies. Run the approved
   workload once on the final integrated release candidate after those dependencies are
   complete; Paper and Live activation remains off until that candidate passes every gate.

Expected implementation/static/offline-evaluation time:15–30minutes. Public API, schema,
production code, resource/load/duration/source rates and trading logic do not change.
Rollback is restoring the evaluator/test/spec diff; historical raw evidence is immutable.
Owner approved this amended plan and validation on 2026-11-02. Implementation completed
without a workload rerun; execution evidence and remaining Batch/System Ready dependency
are recorded in `validation.md` and the revised-SLA evidence report.
