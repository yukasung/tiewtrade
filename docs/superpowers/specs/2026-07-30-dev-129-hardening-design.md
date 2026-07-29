# DEV-129 Runtime Boundary Hardening Design

**Date:** 2026-07-30
**Status:** Approved
**Scope:** Desktop shutdown, public market-data input validation, SQLite schema compatibility, parser diagnostics, and candle-pipeline invariant documentation

## 1. Purpose

DEV-129 ปิดช่องว่างด้านความทนทานที่พบหลังส่งมอบ Paper runtime โดยไม่เปลี่ยน
business rules, execution behavior หรือ public error contract ที่ผู้ใช้พึ่งพา งานนี้ทำให้
Desktop ปิดตัวอย่างปลอดภัยขึ้น, ปฏิเสธ Binance request ที่เกิน contract ก่อนส่ง network,
แสดงข้อผิดพลาดฐานข้อมูลที่เข้าใจได้ และทำให้สาเหตุของ malformed payload ตรวจสอบได้ง่ายขึ้น

## 2. Desktop Shutdown

`MainWindow` ต้องเก็บ `QThreadPool` ที่ถูกส่งเข้ามาเป็น dependency เดียวกับที่ workflows
ใช้งาน เมื่อได้รับ `closeEvent` ให้ปิด workflows ก่อนเพื่อยกเลิก callback generation แล้วรอ
worker pool สูงสุด 5,000 milliseconds ก่อนยอมให้ window ปิด

ลำดับนี้ช่วยไม่ให้ callback จาก worker ที่ยังทำงานอยู่ย้อนกลับมาหา UI ที่ถูกทำลายแล้ว โดยมี
deadline เพื่อไม่ให้ผู้ใช้ติดอยู่ในขั้นตอนปิดโปรแกรมแบบไม่มีกำหนด หาก worker ยังไม่เสร็จหลัง
deadline Qt สามารถดำเนินการปิดต่อได้ตาม lifecycle ปัจจุบัน

## 3. Public Market Data Request Limit

`BinancePublicMarketData.load_recent()` ต้องรับ `count` ตั้งแต่ 1 ถึง Binance page limit
1,000 เท่านั้น ค่า `count > 1000` ต้องถูกปฏิเสธด้วย `ValueError` ก่อนสร้าง HTTP request
และต้องไม่ clamp ค่าเงียบ ๆ เพราะผู้เรียกอาจเข้าใจผิดว่าได้รับ candle ครบตามจำนวนที่ขอ

การดึง historical data มากกว่า 1,000 แท่งยังคงเป็นหน้าที่ของ paginated backfill flow ที่มีอยู่
ไม่ใช่ `load_recent()`

## 4. Newer SQLite Schema Compatibility

SQLite integration ต้องแทน raw `ValueError` ด้วย exception เฉพาะ
`UnsupportedDatabaseSchemaError` ซึ่งเก็บ `database_version` และ `supported_version`
เพื่อให้ composition layer ระบุสาเหตุได้อย่างชัดเจน

Desktop composition จะแปลง exception นี้เป็น application-level
`PaperSessionDatabaseVersionError` ก่อนส่งผ่าน workflow โดย UI แสดงข้อความ
`Database was created by a newer version of TiewTrade` เท่านั้น UI จะไม่ import
SQLite integration และจะไม่เปิดเผย filesystem path, SQL หรือรายละเอียดภายใน

exception อื่นจาก storage ยังคงใช้ unavailable behavior เดิม จึงไม่มีการเปลี่ยน semantics
ของ storage failures ทั่วไป

## 5. Binance Payload Diagnostics

public exception `BinanceMarketDataPayloadError` และข้อความที่ผู้เรียกเห็นต้องคงเดิม
แต่จุดที่ตรวจ type/value ของ payload จะเพิ่ม field-specific `ValueError` เป็น cause เช่น
ชื่อ field และชนิดหรือค่าที่ไม่ถูกต้อง แล้วใช้ exception chaining ส่งออกผ่าน public exception

แนวทางนี้ทำให้ log และ debugger บอกได้ว่า field ใดเสีย โดยไม่ทำให้ UI หรือ consumer
ต้องผูกกับรายละเอียด payload ของ Binance

## 6. Candle Backfill Invariant

`CompletedCandlePipeline.process_backfill()` ตรวจ candle sequence ทั้งชุดกับ deep copy
ก่อนนำ candle ชุดเดิมเข้า state จริง ดังนั้น return value จาก `accept()` ในรอบ commit
ถูกละทิ้งโดยตั้งใจ เพราะ validation pass รับประกันว่าทุก candle จะถูกยอมรับใน state เดิม

งานนี้เพิ่ม code comment ตรงจุดดังกล่าวเท่านั้น ไม่เปลี่ยน algorithm หรือสร้าง assertion
ซ้ำใน production path

## 7. Verification Strategy

ใช้ TDD แยกตาม boundary:

1. MainWindow test พิสูจน์ว่า workflows ถูกปิดก่อนและ pool รอด้วย deadline 5 วินาที
2. Public market-data test พิสูจน์ว่า `count > 1000` ถูกปฏิเสธและไม่มี HTTP request
3. SQLite/application/UI tests พิสูจน์ typed exception, translation และ sanitized message
4. Parser tests พิสูจน์ field-specific cause โดยคง public error text เดิม
5. Candle-pipeline tests เดิมต้องผ่านหลังเพิ่ม invariant comment

จากนั้นรัน full Python suite, Ruff, formatter, mypy, documentation tests และ
`git diff --check`

## 8. Non-Goals

- ไม่เพิ่ม Live order, Private API หรือ credential access
- ไม่เพิ่มการ retry, cancel หรือบังคับ terminate worker หลัง 5 วินาที
- ไม่เปลี่ยน Binance backfill pagination contract
- ไม่เปลี่ยนข้อความ public error ของ malformed market-data payload
- ไม่เปลี่ยน completed-candle acceptance semantics
- ไม่สร้าง generic exception hierarchy, interface, registry หรือ factory ใหม่
