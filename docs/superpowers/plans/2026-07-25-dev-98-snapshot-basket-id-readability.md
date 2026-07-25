# แผนการดำเนินงาน DEV-98: ทำให้การเลือก Basket ID ใน Snapshot อ่านง่ายขึ้น

> **สำหรับผู้ปฏิบัติงานแบบ agent:** ต้องใช้ทักษะย่อย `superpowers:subagent-driven-development` (แนะนำ) หรือ `superpowers:executing-plans` เพื่อดำเนินแผนนี้ทีละงาน ขั้นตอนใช้รูปแบบช่องทำเครื่องหมาย (`- [ ]`) เพื่อติดตามสถานะ

**เป้าหมาย:** เปลี่ยน nested conditional expression ที่เลือก `basket_id` ใน `PaperSpotSession._snapshot()` เป็น `if/elif/else` โดยคง behavior เดิมทุกกรณี

**สถาปัตยกรรม:** แก้เฉพาะ implementation ภายใน `_snapshot()` และไม่เพิ่ม abstraction ใหม่ ใช้ characterization tests ยืนยันลำดับ active Basket, closed Basket และไม่มี Basket ทั้งก่อนและหลัง refactor

**ชุดเทคโนโลยี:** Python 3.12+, dataclasses, pytest, Ruff, mypy strict

## ข้อจำกัดโดยรวม

- ห้ามเปลี่ยน `PaperSpotSessionSnapshot` หรือ public API
- ห้ามเปลี่ยน Basket lifecycle, Take Profit, persistence, execution หรือ strategy
- active Basket ต้องมีความสำคัญสูงกว่า `closed_basket`
- ไม่สร้าง helper, interface, class หรือ Module ใหม่
- ใช้ภาษาอังกฤษสำหรับ identifiers และ code comments

---

## โครงสร้างไฟล์

| ไฟล์ | หน้าที่ |
| --- | --- |
| `src/tiewtrade/application/paper_spot_session.py` | เปลี่ยนรูปแบบการเลือก `basket_id` ภายใน `_snapshot()` |
| `tests/unit/application/test_paper_spot_session.py` | ยืนยัน behavior ของ `basket_id` ทั้ง active, closed และ empty state |

### งานที่ 1: ทำให้ลำดับการเลือก Basket ID อ่านตรงไปตรงมา

**ไฟล์:**

- แก้ไข: `src/tiewtrade/application/paper_spot_session.py:158-168`
- แก้ไข: `tests/unit/application/test_paper_spot_session.py`

**อินเทอร์เฟซ:**

- รับเข้า: `PaperSpotSession.process_completed_candle(candle, *, received_at) -> PaperSpotSessionSnapshot`
- ส่งออก: behavior เดิมของ `PaperSpotSessionSnapshot.basket_id: UUID | None`

- [ ] **ขั้นที่ 1: เพิ่ม characterization assertions ที่ขาด**

ใน
`test_take_profit_skips_entry_fill_candle_and_closes_on_following_candle()`
เพิ่ม assertion หลังตรวจ `target_snapshot.closed_basket`:

```python
assert target_snapshot.basket_id == target_snapshot.closed_basket.basket_id
```

เพิ่ม test สำหรับ Session ที่ยังไม่มี Basket:

```python
def test_snapshot_has_no_basket_id_before_first_entry() -> None:
    application = paper_session()
    first_candle = candle(0, open_price="100", close_price="101")

    snapshot = application.process_completed_candle(
        first_candle,
        received_at=first_candle.close_time,
    )

    assert snapshot.accepted is True
    assert snapshot.basket_id is None
```

กรณี active Basket มี assertion อยู่แล้วใน
`test_pending_intent_fills_at_the_next_completed_candle_open()`:

```python
assert snapshot.basket_id == uuid5(session.session_id, "basket:1")
```

- [ ] **ขั้นที่ 2: รัน characterization tests ก่อน refactor**

รัน:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/application/test_paper_spot_session.py -q
```

ผลที่คาดหวัง: PASS เพราะ tests บันทึก behavior เดิม ไม่ได้เพิ่ม behavior ใหม่

- [ ] **ขั้นที่ 3: เปลี่ยน nested conditional เป็น explicit branches**

แทนที่การกำหนด `basket_id` เดิมใน `_snapshot()` ด้วย:

```python
if self._basket is not None:
    basket_id = self._basket.basket_id
elif closed_basket is not None:
    basket_id = closed_basket.basket_id
else:
    basket_id = None
```

ห้ามแยก helper method และห้ามแก้ field อื่นของ snapshot

- [ ] **ขั้นที่ 4: รัน unit test หลัง refactor**

รัน:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/application/test_paper_spot_session.py -q
```

ผลที่คาดหวัง: PASS และจำนวน test ในไฟล์เพิ่มขึ้นหนึ่งรายการ

- [ ] **ขั้นที่ 5: รัน quality gates ทั้งหมด**

รัน:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest -q
PYTHONPATH=src ../../.venv/bin/python -m ruff check src tests
PYTHONPATH=src ../../.venv/bin/python -m ruff format --check src tests
PYTHONPATH=src ../../.venv/bin/python -m mypy src
npm --prefix docs-site test
npm --prefix docs-site run check:content
git diff --check
```

ผลที่คาดหวัง:

- Python tests ผ่านทั้งหมด
- docs tests ผ่าน 50 รายการ
- Ruff, format, mypy, content check และ `git diff --check` ผ่าน

- [ ] **ขั้นที่ 6: ตรวจและ commit**

ตรวจ `git diff main...HEAD` เทียบ:

- `AGENTS.md`, `PRODUCT.md`, `CONTEXT.md`, `ARCHITECTURE.md`,
  `PROJECT_PLAN.md`
- `docs/superpowers/specs/2026-07-25-dev-98-snapshot-basket-id-readability-design.md`

จากนั้น commit:

```bash
git add src/tiewtrade/application/paper_spot_session.py \
  tests/unit/application/test_paper_spot_session.py
git commit -m "refactor: clarify Paper Spot snapshot basket ID"
```

ยังไม่ push หรือ merge จนกว่าจะได้รับคำยืนยันแยกจากผู้ใช้
