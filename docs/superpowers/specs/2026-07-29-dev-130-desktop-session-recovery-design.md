# DEV-130 Desktop Session Recovery Design

## สถานะ

- วันที่: 2026-07-29
- สถานะ: อนุมัติสำหรับจัดทำ implementation plan
- Issue: DEV-130
- Parent: DEV-117
- Milestone: Paper Trading Complete

## เป้าหมาย

นำ Desktop Session Setup acceptance behavior จาก DEV-115 และ focused
`SessionWorkflow` refactor จาก DEV-116 กลับเข้าสู่ `main` ล่าสุด โดยรักษา hardening,
dependency rules และ deterministic behavior ที่เพิ่มหลัง branch ทั้งสองแยกออกไป

## สภาพปัจจุบัน

DEV-115 และ DEV-116 แยกจาก `main` ที่ commit `9a3ac7f` และถูกปิดเป็น Done ก่อน
commits ถูกนำเข้าสู่ `main` ปัจจุบัน branch สำรองยังอยู่ที่:

- `dev-115-desktop-session-acceptance` — head `3a31823`
- `dev-116-desktop-session-workflow` — head `4573387`

DEV-115 ไม่มี production-code delta สิ่งที่ยังขาดจาก `main` คือ acceptance tests ที่
พิสูจน์ Desktop vertical slice และสถานะการส่งมอบใน `PROJECT_PLAN.md`

DEV-116 มี production refactor ที่แยก Qt worker lifecycle ออกจาก `MainWindow` ไปยัง
focused `SessionWorkflow` พร้อม tests เฉพาะ แต่ branch เก่าไม่มี hardening รุ่นใหม่บน
`main` ทั้งหมด จึงห้าม merge หรือ cherry-pick ทั้ง branch โดยไม่คัดเลือก

## แนวทางที่เลือก

ใช้ Selective Recovery จาก recovery branch ที่สร้างจาก `main` ล่าสุด:

1. นำ acceptance contract ของ DEV-115 กลับมาก่อนและรันกับ source ปัจจุบัน
2. เพิ่ม tests ของ `SessionWorkflow` ก่อน production implementation
3. สร้าง focused workflow ด้วย behavior ที่พิสูจน์แล้วจาก DEV-116
4. ย้าย task lifecycle ออกจาก `MainWindow` โดยเก็บ presentation และ safety coverage
   ปัจจุบันทั้งหมด
5. บันทึกสถานะ recovery ใน `PROJECT_PLAN.md`

ไม่ใช้ merge หรือ cherry-pick branch เก่าทั้งก้อน และไม่ลบไฟล์หรือ behavior ใหม่จาก
`main`

## ทางเลือกที่ไม่เลือก

### Patch Replay

นำ patch ของ branch เก่ากลับมาตามลำดับ commit วิธีนี้เก็บประวัติเดิมได้มากกว่า แต่
เสี่ยงนำ test reductions และ assumptions จาก base เก่ามาทับ hardening ปัจจุบัน

### Acceptance Only

นำเฉพาะ DEV-115 acceptance tests กลับมา วิธีนี้ลด source change แต่ไม่ส่งมอบ
`SessionWorkflow` refactor และไม่ครบ Acceptance Criteria ของ DEV-130

## ขอบเขต

### ทำ

- เพิ่ม Desktop Session Setup acceptance tests สำหรับ Paper Spot และ Paper Futures
- เพิ่ม focused `SessionWorkflow` ใน `ui`
- ให้ Workflow ดูแล startup load, create request, busy state, duplicate suppression,
  sanitized error mapping, task references และ late-callback invalidation
- ให้ `MainWindow` ดูแล widgets, page transitions และ rendering เท่านั้น
- รักษา current MainWindow safety tests พร้อมเพิ่ม Workflow-level coverage
- บันทึกสถานะ DEV-115, DEV-116 และ DEV-130 ใน `PROJECT_PLAN.md`

### ไม่ทำ

- ไม่เปลี่ยน application request/result หรือ SQLite schema
- ไม่เปลี่ยน UI fields, appearance, copy หรือ business rules
- ไม่เริ่ม Market Data, Strategy, Execution หรือ Live integration
- ไม่เชื่อม Binance network และไม่ใช้ credentials
- ไม่สร้าง generic task framework, ViewModel framework หรือ hypothetical interface
- ไม่ย้อน decimal-context, persistence, runtime หรือ trading hardening บน `main`

## Module และ Interface

### SessionWorkflow

`SessionWorkflow(QObject)` อยู่ใน `ui` เพราะเป็นเจ้าของ Qt task lifecycle ไม่ใช่
business Session orchestration โดยรับ dependencies ผ่าน constructor:

- `create_session: Callable[[PaperSessionSetupValues], PaperSessionCreateOutcome]`
- `load_active: Callable[[], ConfiguredPaperSession | None]`
- `thread_pool: QThreadPool | None`

คำสั่ง:

- `start()` — โหลด Active Session เมื่อเปิดหน้าต่างหรือ retry
- `create(values)` — ขอสร้าง Paper Session เมื่อไม่มี task ทำงาน
- `close()` — ปิดรับงานใหม่และ invalidate semantic callbacks ที่มาช้า

semantic signals:

- `setup_required`
- `session_ready`
- `validation_failed`
- `unavailable`
- `busy_changed`

Workflow ต้องไม่ import SQLite, Strategy, Execution, Market Data Runtime, Binance หรือ
credential integration และไม่แก้ durable state เอง

### MainWindow

`MainWindow` ประกอบ widgets และเชื่อม Workflow signals เข้ากับ focused rendering
methods หน้าต่างต้องไม่เก็บ active `SessionTask`, operation state หรือ callback
generation counter หลัง refactor

`MainWindow` ต้องเก็บ constructor contract เดิมเพื่อไม่เปลี่ยน composition root และ
ต้องคง tests ที่พิสูจน์ actual-window duplicate submit, sanitized error paths, retry และ
close safety

## Data Flow

### Startup Load

1. `MainWindow` เชื่อม signals แล้วเรียก `workflow.start()`
2. Workflow emit `busy_changed(True)` และเริ่ม `load_active` ผ่าน `SessionTask`
3. ไม่มี Active Session → emit `setup_required`
4. มี `ConfiguredPaperSession` → emit `session_ready(session)`
5. storage unavailable → emit `unavailable("Session storage is unavailable")`
6. result หรือ exception อื่น → emit sanitized load failure
7. task จบ → disconnect callbacks, clear task state แล้ว emit `busy_changed(False)`

### Create Session

1. Setup ส่ง `PaperSessionSetupValues` ให้ `workflow.create(values)`
2. หากมี load/create task ทำงานอยู่ Workflow เพิกเฉย request ใหม่
3. Workflow emit `busy_changed(True)` แล้วเริ่ม `create_session` ผ่าน `SessionTask`
4. outcome ที่มี durable `ConfiguredPaperSession` → emit `session_ready(session)`
5. validation error → emit `validation_failed(field, message)` แล้ว
   `setup_required`
6. storage unavailable → emit sanitized storage message
7. result หรือ exception อื่น → emit sanitized create failure
8. task จบ → disconnect callbacks, clear task state แล้ว emit `busy_changed(False)`

Semantic result ต้องเกิดก่อน idle signal เพื่อให้ presentation เปลี่ยนหน้าก่อนเปิด
controls อีกครั้ง

## Window Lifecycle Safety

`close()` ต้องปิดรับ task ใหม่และ invalidate semantic callbacks ของ task ที่ยังทำงาน
อยู่ โดยไม่พยายามยกเลิก SQLite operation กลาง transaction เมื่อ worker emit
`finished` Workflow ยังต้อง disconnect callbacks และ clear task reference แม้หน้าต่าง
ปิดแล้ว

Task callbacks ต้องถูก disconnect หลัง completion เพื่อป้องกัน retained task ส่ง
semantic result ซ้ำและเพื่อไม่เก็บ Workflow หรือ Window เกิน lifecycle

## Error Mapping

| Operation | Condition | Semantic result |
| --- | --- | --- |
| Load | ไม่มี Active Session | `setup_required` |
| Load | Session ถูกต้อง | `session_ready(session)` |
| Load | storage unavailable | `unavailable("Session storage is unavailable")` |
| Load | invalid result/exception | `unavailable("Paper Session could not be loaded")` |
| Create | outcome และ nested Session ถูกต้อง | `session_ready(session)` |
| Create | validation error | `validation_failed(field, message)` แล้ว `setup_required` |
| Create | storage unavailable | `unavailable("Session storage is unavailable")` |
| Create | invalid result/exception | `unavailable("Paper Session could not be created")` |

ห้ามส่ง raw exception, filesystem path, SQLite detail หรือ secret ไปยัง UI

## Testing Strategy

### DEV-115 Acceptance

กู้ acceptance tests ที่พิสูจน์:

- Paper Spot และ Futures: form → durable create → Overview → restart → restore
- Session และ market-specific policies ตรงกับ SQLite
- create/restart ไม่สร้าง Basket หรือ Fill
- duplicate create คง Active Session เดิมเพียงหนึ่งรายการ
- validation และ commit failure ทำงานแบบ fail closed และคง form input
- source boundary ไม่มี runtime, Strategy, Execution, Binance private หรือ credential
  imports
- smoke flow ไม่พยายามเชื่อม network และใช้ Qt offscreen

### SessionWorkflow Unit Tests

ใช้ TDD ครอบคลุม:

- startup Setup และ durable Session
- create success และ reuse หลัง task จบ
- validation ordering และ sanitized failures
- invalid outer result และ invalid nested Session
- duplicate suppression ระหว่าง busy
- semantic result เกิดก่อน `busy_changed(False)`
- signal disconnect และ task cleanup หลัง finish
- close suppresses late result แต่ worker finish ยัง cleanup task

### MainWindow Tests

เพิ่ม architecture test ว่า `MainWindow` delegate lifecycle ไปยัง Workflow และคง
current presentation/safety tests ทั้งหมด เว้นแต่ assertion ใดตรวจ implementation
field ที่ถูกย้าย ซึ่งต้องย้าย assertion นั้นไปทดสอบ Workflow โดยไม่ลด behavior
coverage

### Quality Gates

- focused acceptance และ UI tests
- full Python unit, integration และ acceptance tests
- Ruff check และ format
- Mypy strict
- docs tests และ content check
- `git diff --check`

## ความเข้ากันได้และความเสี่ยง

ไม่มี serialized-data, schema หรือ application-contract change ความเสี่ยงหลักคือ Qt
signal ordering, duplicate callback, task retention และ late result หลังปิดหน้าต่าง จึง
ต้องตรึง behavior เหล่านี้ที่ Workflow seam และรัน DEV-115 acceptance หลัง rewire

Recovery ต้องเก็บ `configure_decimal_context()` และ hardening ทั้งหมดบน `main` โดย
ตรวจ diff สุดท้ายว่าไม่มีไฟล์ใหม่บน `main` ถูกลบหรือย้อนกลับ

## Acceptance Criteria

- DEV-115 Desktop Session Setup acceptance behavior ถูกกู้และผ่านบน `main` ล่าสุด
- DEV-116 `SessionWorkflow` refactor ทำงานผ่าน focused interface และไม่ย้อน hardening
- `MainWindow` ไม่มี Qt task/generation lifecycle implementation
- ไม่มีไฟล์หรือ behavior ใหม่บน `main` ถูกลบ
- dependency direction และ Trading Safety ตรงกับ `ARCHITECTURE.md` และ `AGENTS.md`
- unit, integration, acceptance, Ruff, format, Mypy และ docs checks ผ่าน
