# DEV-98: Paper Spot Snapshot Basket ID Readability

## เป้าหมาย

ปรับการคำนวณ `basket_id` ใน `PaperSpotSession._snapshot()` ให้อ่านลำดับ
ความสำคัญได้ตรงไปตรงมา โดยไม่เปลี่ยน business behavior, public API หรือ state
transition

## ปัญหาปัจจุบัน

โค้ดปัจจุบันใช้ conditional expression ซ้อนกัน:

```python
basket_id = (
    self._basket.basket_id
    if self._basket is not None
    else None
    if closed_basket is None
    else closed_basket.basket_id
)
```

แม้ผลลัพธ์ถูกต้อง แต่ผู้อ่านต้องรู้ associativity ของ conditional expression จึงจะ
เข้าใจลำดับความสำคัญของ active Basket กับ closed Basket ได้

## แนวทางที่เลือก

ใช้ `if/elif/else` ภายใน `_snapshot()`:

```python
if self._basket is not None:
    basket_id = self._basket.basket_id
elif closed_basket is not None:
    basket_id = closed_basket.basket_id
else:
    basket_id = None
```

ไม่แยก private method ใหม่ เพราะ logic นี้มี consumer เพียงจุดเดียวและมีหน้าที่สั้น
ชัดเจน การแยก method จะเพิ่มการกระโดดอ่านโดยไม่มี abstraction ที่นำกลับมาใช้ซ้ำ

## Behavior ที่ต้องคงเดิม

ลำดับการเลือก `basket_id` ต้องเป็น:

1. เมื่อมี active Basket ให้ใช้ `self._basket.basket_id`
2. เมื่อไม่มี active Basket แต่เพิ่งปิด Basket ให้ใช้ `closed_basket.basket_id`
3. เมื่อไม่มีทั้งสองค่าให้ใช้ `None`

กรณีที่ส่ง `closed_basket` พร้อมกับมี active Basket ให้ active Basket มีความสำคัญ
สูงกว่าเหมือนโค้ดเดิม แม้ flow ปัจจุบันไม่สร้างสถานะนี้ตามปกติ

## Testing

ใช้ tests ของ `PaperSpotSession` ยืนยัน behavior ก่อนและหลัง refactor โดยเพิ่ม
assertion ที่ขาดให้ครอบคลุม:

- snapshot หลัง Entry Fill ใช้ active Basket ID
- snapshot หลัง Take Profit Fill ยังส่ง closed Basket ID
- snapshot ที่ยังไม่มี Basket ส่ง `None`

tests เหล่านี้เป็น characterization tests ของ behavior เดิม จึงต้องผ่านทั้งก่อนและ
หลัง refactor ไม่เพิ่ม structural test ที่ผูกกับรูปแบบ source code

## ขอบเขตที่ไม่ทำ

- ไม่เปลี่ยน `PaperSpotSessionSnapshot`
- ไม่เปลี่ยน Basket lifecycle หรือ Take Profit
- ไม่สร้าง helper, interface หรือ Module ใหม่
- ไม่แก้ persistence, execution, strategy หรือ UI
- ไม่เปลี่ยนเอกสาร Source of Truth เพราะไม่มี business rule หรือ ownership change

## Acceptance

- ไม่มี nested conditional expression ในการกำหนด `basket_id`
- behavior ทั้งสามสถานะตรงกับของเดิม
- unit tests และ full test suite ผ่าน
- Ruff check/format, mypy strict และ `git diff --check` ผ่าน
