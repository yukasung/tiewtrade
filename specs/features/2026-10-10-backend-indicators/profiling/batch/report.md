# F-11 — ผล bounded batch รอบแรก — 2026-10-10

สถานะ: **Measured / V-15 Failed** — ยังไม่พร้อม merge/Completed

## การเปลี่ยนที่ทำตาม NC-34

- financial transitionร่วมอยู่ใน `core.money.indicator_batch`; single-stepเรียก
  batchขนาด1 ไม่มีสูตร productionสองชุด เก็บscratch coefficientsเฉพาะภายใน
  operation; state/resultsที่คืนเป็นMoney/Scalarตามเดิม ปัดและตรวจoverflowทุกstep
- `CandleSeries` ใช้ตรวจidentityร่วมกับCandleconstructorเดิม; `validate_ohlcv`
  ตรวจMoney/Quantityที่สร้างผ่านinvariantแล้วในcontextเดียว ไม่สร้างzeroซ้ำทุกราคา
  Money/Quantity public constructorsและoperationsเดิมไม่ได้เปลี่ยน
- F-11reader fetchเฉพาะcolumnsที่ใช้แล้วdecode/hash/coreทีละ<=16ช่อง
  ภายใต้transactionเดิม; driverbuffer<=1,000แถว ไม่ใช้F-09stored_rowsที่decodeรวดเดียว
- materializeผลเฉพาะoutputpage; canonicalrecord/digestยังสแกนทั้งชุดทุกหน้า
  seed/retention/cursor/role/query budgetsเหมือนเดิม ไม่มีmigration/cache/worker
- หลังวัดเพิ่มการตรวจpublic batch stateที่มีEMA/previous<=0 หรือgain/loss/ATR<0
  และeventราคาผิดOHLC; valid fixtureยังใช้สูตรเดิม ผลด้านล่างวัดก่อนเพิ่มchecksนี้

## ผล API cold ตาม V-15

Linux APIใหม่2vCPU/1GiB ใช้fixture525,600แถวที่เตรียมในprocessแยกก่อนstartup
image/DB/Redisตาม[baseline profile](../report.md); คงHTTPdeadline30s
วัดidle RSSของAPI processก่อนrequest ไม่ใช้high-water markหลังINSERTfixture

| ตัวชี้วัด | ผล | เกณฑ์/ข้อจำกัด |
|---|---:|---|
| HTTP | 504 INDICATOR_DEADLINE_EXCEEDED | ต้อง200พร้อมผลที่ตรวจแล้ว จึงไม่ผ่าน |
| เวลารวม | 30.071056s | ไม่ได้อ่านครบภายใน30s |
| Event-loop lag สูงสุด | 27.593ms | ต่ำกว่า100msในคำขอที่ล้มนี้ |
| Idle RSS | 89,820KiB | baselineก่อนrequest |
| Peak RSSเพิ่ม | 64,076KiB (~62.6MiB) | ต่ำกว่า128MiBในคำขอที่ล้มนี้ |
| Body | 40bytes | เป็นerror ไม่ใช่ผล1,000ช่อง; ไม่ใช้รับรองsuccessful response size |

หยุดก่อนwarm5ตามด่านหยุดที่อนุมัติ ตัวเลขlag/RSSด้านบนไม่ถือว่าV-15ผ่าน
เพราะยังไม่มีผลสำเร็จครบทั้งชุด

## Profile เพื่อระบุต้นทุนที่เหลือ

รอบinstrumented30.090534s feed307,240ช่องก่อน504 เทียบbaselineinstrumented
97,008ช่อง; counters/overheadเปลี่ยนจากจับcoreทีละแท่งเป็นทีละbatch จึงไม่อ้าง
ว่าเป็นspeedupแบบควบคุมทุกปัจจัย หรือว่าfull-sizeจะจบในเวลาที่คูณจากsample

| ส่วน | เวลาที่วัด |
|---|---:|
| Decode | 8.754888s / 307,240แถว |
| Core batch | 6.807518s / 19,356calls |
| DB | 5.205480s / 925queries |
| เตรียม/hash record | 5.583017s |
| Fetch/result bufferingนอกexecute | 0.567018s / 308calls |

hash breakdown: timestamp1.288038s, canonical money strings3.241084s,
JSON0.975826s, SHA-256 update0.078070s เห็นว่าdecode/core/DB/serialization
ยังมีต้นทุนสะสมทั่วdataset แม้ไม่สร้างผลทุกจุด

cProfile core1,000ช่อง (batch16, ไม่มีoutputนอกหน้าที่ขอ): guarded wrapper
1,994calls เทียบ45,080เดิม และ advance_indicator_batch63calls
diagnosticpipeline10,000ช่อง/output1,000ใช้0.948276s แต่ขนาดsampleเล็ก
ไม่ผ่านเกณฑ์full-sizeแทน525,600ช่อง ไม่เพิ่มdeadlineหรือtruncateประวัติในAPI

## การตรวจและหลักฐาน

- ชุดMoneyเดิม/core/arithmetic/market_data/purity/reader/snapshot/API:
  **217ผ่าน/0ล้ม/0error/0skip** ตาม `tests.xml`; Windowsรันด้วย `uv run --with tzdata`
  เพื่อให้timezone fixtureเดิมมีข้อมูล ไม่เปลี่ยนdependency lockหรือexpected tests
- independent Fraction oracleตรวจEMA/RSI/MACD/ATRทุกstepของราคาที่มีเศษละเอียด
  และเปลี่ยนทิศ ที่batch1/2/16; ตรวจseed/warm-up, gaps/refresh, outputselection,
  unit/type/invalidstateและroundingเดิม
- PostgreSQLจริง: fetch16/64/1,000ตรงcanonicaldigestfixtureและผลหน้าเดิม;
  writercommitระหว่างreaderยังได้snapshotเดิม หน้าใหม่ได้409 และread-onlyไม่รั่ว
- Ruff check/format, mypy และ import contracts7ข้อผ่าน
- ยังไม่รันwarm5, writer/rejected-load, PV-8ทุกcase, retention clock matrixครบ,
  refreshintegrationและfullregressionจบ; ไม่อ้างว่าPV-1..10/V-1..18ผ่านครบ
- `benchmark.json`, `profile.json`, `core.pstats`, `tests.xml` เป็นraw artifacts
  ใช้runner `test_indicator_budgets.py --prepare` ในprocessแยก จากนั้นรันrunnerปกติ
  mountโฟลเดอร์นี้เป็น `/results`; ตัวเตรียมfixtureลบcandlesเฉพาะdisposable DB
- profileใช้ `profile_indicators.py --instrumented-only` พร้อมmount/resultsเดียวกัน
  ไม่มีorder/exchange calls และไม่มีการเขียนcandlesจากprofile

## จุดหยุด

F-11ยัง In Progress และV-15ยังFailed เกณฑ์30s/100ms/128MiBไม่เปลี่ยน
การเปลี่ยนไปใช้checkpoint/persistent cache/workerหรือผ่อนเกณฑ์อยู่นอกNC-34
ต้องเสนอแผนพร้อมผลต่อcold miss, readiness, seed/revision/retention,
permissions/migration/rollback และได้รับอนุมัติก่อนลงมือ
