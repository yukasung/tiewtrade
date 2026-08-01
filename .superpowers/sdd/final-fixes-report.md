# รายงานการแก้ไข final review ของ DEV-120

## การเปลี่ยนแปลง

- เพิ่ม regression coverage ให้ `SymbolRules` ยืนยันว่ารับ symbol ที่มีช่องว่างได้เมื่อไม่ว่าง และเก็บค่าเดิมโดยไม่ normalize
- ปรับ mismatch tests ทั้ง 5 จุดของ Paper Spot/Futures ให้ตรวจ exact identity สำหรับ `"btcusdt"`, `" BTCUSDT "` และ `"ETHUSDT"` พร้อมตรวจข้อความ `ValueError` ทั้งบรรทัด รวมค่า Candle และ `SymbolRules` จริง
- แปลคำอธิบาย คำสั่ง และผลที่คาดหวังใน implementation plan เป็นภาษาไทย โดยคง template headings, identifiers, code, commands และ error strings

## หลักฐาน RED/GREEN

- RED: ไม่มี RED ที่ถูกต้องตามหลัก TDD สำหรับ regression นี้ เพราะ guard production ที่มีอยู่ตรวจ exact equality และ `SymbolRules` เก็บค่า padded โดยไม่ normalize อยู่ก่อนแล้ว การแก้ production ที่ถูกต้องชั่วคราวเพื่อบังคับให้ test ล้มเหลวจะเป็น RED เทียมและอยู่นอกขอบเขตงาน
- GREEN ก่อนจัดรูปแบบ: `PYTHONPATH=src ../../.venv/bin/python -m pytest -q tests/unit/trading/test_capital.py tests/unit/execution/test_paper_spot.py tests/unit/execution/test_paper_futures.py` — `51 passed in 0.06s`
- GREEN หลังจัดรูปแบบ: คำสั่งเดิม — `51 passed in 0.05s`

## การตรวจสอบ

- `../../.venv/bin/python -m ruff check tests/unit/trading/test_capital.py tests/unit/execution/test_paper_spot.py tests/unit/execution/test_paper_futures.py` — ผ่าน
- `../../.venv/bin/python -m ruff format --check tests/unit/trading/test_capital.py tests/unit/execution/test_paper_spot.py tests/unit/execution/test_paper_futures.py` — ผ่าน
- ชุด SymbolRules/Paper Spot/Paper Futures ที่ครอบคลุม — `78 passed in 0.72s`
- `npm --prefix ../../docs-site test` — `50` tests ผ่าน
- `npm --prefix ../../docs-site run check:content` — ผ่าน
- `git diff --check` — ผ่าน

---

# รายงานการแก้ไข final review ของ DEV-134

## สิ่งที่แก้ไข

- ผูก `BotControlSnapshot` กับ `ConfiguredPaperSession` แบบ fail-closed โดยตรวจ exact `symbol`, `timeframe`, `trade_mode`, `market_type` และ `preset_version`
- บังคับ `transition_bot_control()` ให้คง `read_state`, `orders`, `basket` และ `data_as_of_utc`; lifecycle เปลี่ยนได้เฉพาะ `runtime_state` และ `data_freshness` ตาม contract
- ให้ invalid cross-session/cross-market result รวมถึง result ที่ลบ Basket หรือเปลี่ยน Orders/เวลา/read state ถูก `BotLifecycleWorkflow` map เป็น exact safe Blocked reason พร้อมคง Workspace facts เดิม
- เพิ่ม `Blocked → Blocked` ใน application transition graph และนำ special-case ที่สร้าง `BotControlSnapshot` ตรงใน Recover ออก เพื่อให้ Recover ใช้ validation boundary เดียวกัน
- เปลี่ยน `Stop Session` ให้เปิด non-blocking `QMessageBox` จริงใน production โดย `Cancel` เป็น default/escape, `Stop Session` เป็น destructive action และมี pending/repeated guard
- เพิ่ม injectable `StopConfirmation` seam ที่ระดับ `BotControlWidget` สำหรับ deterministic unit tests; `TradingWorkspace` และ `MainWindow` production composition ไม่ inject seam จึงใช้ dialog จริงเสมอ
- Cancel ไม่ emit และคืน focus ไป `Stop Session`; Confirm emit ครั้งเดียว แล้วคืน focus ไป `Bot State` เพราะ lifecycle publish `Stopping` และซ่อน/disable ปุ่ม Stop ทันที
- เปลี่ยน `_decimal_text()` เป็น fixed-point formatting ที่ไม่พึ่ง Decimal context, ตัด trailing zeros/dot โดยไม่เสีย digits และ canonicalize `0`/`-0` เป็น `0`
- เพิ่ม `Data Freshness` ใน Bot Control พร้อม mapping `Not Started`, `Fresh`, `Stale`, `Unavailable`

## RED

### Session ownership และ Workspace continuity

คำสั่ง:

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src ../../.venv/bin/python -m pytest tests/unit/application/test_bot_control.py tests/unit/ui/test_bot_lifecycle_workflow.py -q
```

ผลก่อนแก้ production:

```text
14 failed, 33 passed in 25.49s
```

Failures ยืนยันว่า header ของ Spot Session รับ wrong symbol/Futures/Live/preset/timeframe ได้, transition รับ result ที่เปลี่ยน `orders`, `basket`, `data_as_of_utc`, `read_state` และ workflow ไม่ fail closed เมื่อ result ข้าม Market หรือทำ Basket หล่น

### Stop confirmation, Decimal และ Data Freshness

คำสั่ง:

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src ../../.venv/bin/python -m pytest tests/unit/ui/test_bot_control.py -q
```

ผลก่อนแก้ production:

```text
5 failed, 4 passed in 0.15s
```

Failures ยืนยันว่าไม่มี confirmation seam, ไม่มี Data Freshness field และ `Decimal.normalize()` ปัดค่า high precision ตาม current context

เพิ่ม focus contract ของ Confirm ก่อนแก้แล้วได้:

```text
1 failed in 5.13s
```

Failure ยืนยันว่า focus ยังไม่กลับไปยัง stable Bot Control status หลัง Confirm

## GREEN

```text
Application/workflow focused: 47 passed in 0.39s
Final focused lifecycle/UI/MainWindow/acceptance: 128 passed in 4.38s
Full pytest: 855 passed in 8.00s
```

MainWindow และ acceptance tests กด `Stop Session` แล้วเลือก Confirm จาก production `QMessageBox` อย่างชัดเจน; unit tests ครอบ Cancel, Confirm, repeated guard, destructive/default-safe roles และ focus return

## Quality checks

```text
Ruff check src tests: All checks passed
Ruff format --check src tests: 154 files already formatted
Mypy: Success: no issues found in 154 source files
docs-site test: 50 passed
docs-site check:content: passed
git diff --check: passed
```

## Commit

```text
ec45c97 fix: enforce bot control lifecycle safety
```

## ข้อกังวลที่เหลือ

- DEV-134 ยังใช้ injectable fake lifecycle actions ตามขอบเขตเดิม; Runtime Start/Stop/Recovery จริงยังเป็น DEV-136
- ไม่มี Live order, Binance Private API, network หรือ trade-storage side effect เพิ่มในงานแก้ไขนี้
- ไม่มี blocker คงค้างสำหรับ final review findings ชุดนี้

## การทบทวน final findings

- Exact identity/error coverage: ครบทั้ง 5 execution guards และมี test ของ padded `SymbolRules.symbol`
- ภาษาในแผน: แปล prose/instructions/expected results โดยไม่เปลี่ยน commands หรือความหมาย

## ข้อกังวล

ไม่มีข้อกังวลที่เหลือ; ไม่มีการเปลี่ยน production behavior, network call หรือ Live execution.

## การแก้ไข minor final review เพิ่มเติม

- คืน header ของ writing-plans template ที่บังคับให้เป็นภาษาอังกฤษแบบตรงตัว รวม title, directive, `Goal`, `Architecture`, `Tech Stack`, `Global Constraints` และ labels ของโครงสร้าง
- ปรับ snippets และ node IDs ในแผนให้ตรงกับ tests ปัจจุบัน รวม exact `ValueError` assertions และ `SymbolRules` padded-symbol test
- ปรับคำสั่งเลือก mismatch tests ให้เลือก Spot 2 รายการด้วย `-k "near_match"` และ Futures guards 3 รายการด้วยชื่อ tests ปัจจุบันทั้งหมด

## การตรวจสอบ minor final review เพิ่มเติม

- Spot selection command — `2 passed, 5 deselected`
- Futures selection command — `3 passed, 18 deselected`
- stale-name scan สำหรับ node IDs และ `-k "another_symbol"` เดิม — ไม่พบผลลัพธ์
- `npm --prefix ../../docs-site test` — `50` tests ผ่าน
- `npm --prefix ../../docs-site run check:content` — ผ่าน
- `git diff --check` — ผ่าน
