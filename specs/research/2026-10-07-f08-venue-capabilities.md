# F-08 — Binance TH capability evidence

สถานะ: **Research only** — ไม่ใช่ requirements หรือ plan ที่อนุมัติ
วันที่ตรวจ: 2026-10-07

## ขอบเขตปัจจุบัน — หลังแก้ review issue 6 (2026-10-07)

เจ้าของยกเลิก sub-account/หลายกระเป๋าแล้ว F-08 ใช้หนึ่งบัญชีต่อผู้ใช้
และหนึ่ง API key รวมทุกสถานะตาม
[requirements บัญชีเดียว](../features/2026-10-07-single-trading-account/requirements.md)

- **NC-22 / UID-dedup / หลักฐาน key replacement ของ wallet: Superseded**
  ไม่ใช่ข้อบล็อก F-08 หรือเงื่อนไข trading/replacement ปัจจุบันจาก research นี้
  ไม่อ้างว่าพิสูจน์ UID สำเร็จ หรือ key ใหม่เป็นบัญชีเดิมโดยอัตโนมัติ
- **อำนาจถอน/โอน/จัดการบัญชีของ key ยังไม่ทราบ:** ติดตามผ่าน **NC-16**
  (รวม NC-21 เดิมแล้ว) ก่อน Live; ข้อห้าม endpoint ย้ายเงินยังคงอยู่
  การเลิกฟีเจอร์ sub-account ไม่ใช่หลักฐานว่า key ไม่มีอำนาจเหล่านี้
- **Balance/realtime latency:** หลักฐานด้านล่างเป็นประวัติ; F-08 ไม่แสดงยอด
  การทำ stream/latency ภายหลังต้องใช้ spec ของงานนั้นเอง
- **Trading/credential changes:** ใช้ requirements บัญชีเดียว RQ-6/RQ-15
  และ spec orders/positions/Live ภายหลัง ไม่ใช้เงื่อนไข wallet/UID เดิม

## ประวัติคำตัดสินก่อนยกเลิกหลายกระเป๋า — Superseded

เดิมเจ้าของเลื่อน balance display และยอมรับ wallet registration แบบ
account identity ยังไม่ยืนยัน โดยวาง identity proof เป็นด่านก่อน trading/replacement
แนวตีความนี้ถูกแทนด้วยขอบเขตบัญชีเดียวแล้ว เก็บไว้เป็นประวัติเท่านั้น
รหัส RQ-11/RQ-14/RQ-15/RQ-16 ในส่วนประวัติด้านล่างเป็นรหัสของ spec หลายกระเป๋าเดิม
ไม่ใช่รหัสชื่อเดียวกันใน requirements บัญชีเดียวฉบับปัจจุบัน

Public documentation only; no credentials, private API requests, or transactions.
No existing research directory was found; this note establishes `specs/research/`.

## Primary evidence — หลักฐานที่บันทึกเมื่อ 2026-10-07

- `GET /api/v1/accountV2` documents balances, commissions, account flags and updateTime; no account identifier is shown. Broker info/sub sections lack response schemas. This does not prove other identifiers impossible. [Account Information / Broker sections](https://www.binance.th/api-docs/en/)
- User Data Streams provide `outboundAccountPosition`: asset/free/locked, `E` event time, `u` last account update. `balanceUpdate` provides delta and `T` clear time. Times are milliseconds. No one-second delivery guarantee was found. [User Data Streams](https://www.binance.th/api-docs/en/)
- Streams use listenKeys, 60-minute expiry/keepalive and 24-hour websocket connections. Both `/api/v1/listenKey` and `/api/v1/wsaListenKey` creation are documented; the stated websocket is `wss://nbstream.binance.th/w3w/wsa/stream?streams=<listenKey>`. Exact pairing needs confirmation. [Stream lifecycle](https://www.binance.th/api-docs/en/)
- Broker transfer, sub-account creation and API-key management explicitly require a main-account key. `/api/v1/subaccount/transfer` also exists. These declarations do not establish ordinary retail-key entitlements. [Transfer / Broker SubAccount Endpoints](https://www.binance.th/api-docs/en/)
- `GET /api/v1/openOrders` supports omitted symbol for all-symbol queries. [Current Open Orders](https://www.binance.th/api-docs/en/)
- Website sub-account management permits transfers and API-key administration through the logged-in master account. Website powers do not prove API-key powers. [Official sub-account guide](https://www.binance.th/en/faq/account-function/b37a51689f4d421e86530279971b31ca)

## Repository evidence และการตีความขอบเขตเดิม

`backend/src/tiewtrade/venues/binance_th/mapping.py` allows nine account top-level
fields (`_ACCOUNT_FIELDS`) and rejects extras. No UID field exists in that set.
F-07 requirements NC-16 records the same nine fields from the owner's earlier
account/accountV2 responses; this research did not repeat that request.
Adding an identifier field would need an approved change to the F-07 NC-19 guard
contract, not an unreviewed bypass in F-08.

- **Superseded — old multi-wallet RQ-15/RQ-16, not current trading/replacement gates:** the historical research did not verify a method proving submitted keys
  belong to the same stable real account. A user-entered UID, key fingerprint,
  matching balances or temporary listenKey was not accepted as proof for that design.
  First-party identity confirmation was proposed for that old wallet design;
  it is not a current requirement.
- **RQ-11 withdrawn from F-08 (historical finding):** realtime has documentary support, but the one-second
  market-to-screen requirement has not been established. Proposed measurement
  needs a confirmed source timestamp, synchronized clocks/error bounds, and
  frontend render instrumentation. `u` is a candidate requiring semantic
  confirmation; measuring only after backend receipt does not meet RQ-11.
  No latency test was performed. The owner subsequently removed balance display
  from F-08, so this evidence gap no longer blocks the current scope.
- **Key powers unresolved — tracked under NC-16 (NC-21 merged):** broker main-key requirements are stronger
  evidence than SIGNED authentication alone. Actual owner retail master-key
  permissions remain unknown. Obtain a venue statement covering transfer and
  management authorization/scopes; do not test by moving money. Existing
  forbidden-endpoint policy remains in force, including when considering reads
  under broker/sub-account namespaces.
- **Historical multi-wallet RQ-14 observation; future account activity proof needs its own spec:** an exchange open-orders read does not
  establish system bot/position state or prevent races. No implementation rule
  is chosen here for future features.

Primary evidence is retained without claiming new verification. Superseded interpretations
do not establish current blockers. Unresolved key-power risks remain under NC-16;
research never authorizes changing approved specifications or trading rules.

## ร่างคำถาม Binance TH Support เดิม — Superseded

สถานะร่าง: **Superseded — ประวัติขอบเขตหลายกระเป๋า; ยังไม่ได้ส่ง**

ร่างนี้มีคำถาม UID/dedup/replacement ของ wallet ที่ยกเลิกแล้ว ไม่ใช่งานต้องส่งปัจจุบัน
หากต้องสอบถามอำนาจ key ตาม NC-16 ให้จัดทำร่างใหม่ตาม scope นั้นโดยไม่ใช้ข้อ UID เดิม
หลักฐานและข้อความด้านล่างเก็บไว้เพื่ออธิบายสิ่งที่เคยเสนอเท่านั้น

ช่องทางแชตทางการ: https://www.binance.th/th/chat
อ้างอิง [FAQs by BINANCE TH](https://www.binance.th/en/announcement/binance-th-activities/5422dacb5b6e46e09a75d3b9711f7817)
ซึ่งระบุช่องทางนี้สำหรับติดต่อ customer support

> สวัสดีครับ/ค่ะ ขอสอบถามทีมเทคนิค API ของ Binance TH สำหรับบัญชีผู้ใช้ทั่วไป
> ทั้งบัญชีหลักและบัญชีย่อย โดยผู้ใช้สร้างบัญชีและ API key เองผ่านเว็บไซต์
> เราต้องการเชื่อมแต่ละบัญชีเป็นกระเป๋าในแอป โดยไม่สร้างบัญชีย่อยหรือโอนเงินผ่านแอป
>
> 1. มี endpoint แบบอ่านอย่างเดียวที่ใช้ API key ของบัญชีนั้นแล้วคืนรหัสบัญชีคงที่ไหม?
>    ต้องการให้ key คนละอันของบัญชีเดียวกันคืนรหัสเดียวกัน แม้ลบแล้วสร้าง key ใหม่
>    และให้บัญชีหลักกับบัญชีย่อยแต่ละบัญชีคืนรหัสต่างกัน เพื่อกันเชื่อมบัญชีซ้ำ
>    และตรวจว่า key ใหม่ยังเป็นบัญชีเดิม กรุณาระบุ endpoint, field และตัวอย่าง response
>    ที่ใช้ค่าทดแทน พร้อมสิทธิ์ที่ต้องเปิด หากไม่มี API นี้มีวิธีตรวจสอบที่รองรับอย่างไร?
> 2. API key ของบัญชีหลักของผู้ใช้ทั่วไป ซึ่งเปิด Read หรือ Read + Spot Trading
>    สามารถโอนสินทรัพย์ระหว่างบัญชีหรือจัดการบัญชีย่อย/API key ของบัญชีย่อยได้หรือไม่?
>    ขอแยกคำตอบตามสิทธิ์สองชุดนี้ และระบุว่าต้องเปิดใช้บริการอื่นเพิ่มเติมหรือไม่
> 3. ถ้ามีอำนาจดังกล่าว ผู้ใช้สามารถปิดแยกจากสิทธิ์อ่าน/เทรดได้ไหม และมี API
>    แบบอ่านอย่างเดียวที่รายงานสิทธิ์จริงของ key หรือไม่? เราไม่ใช้สถานะบัญชี
>    canTrade/canWithdraw/canDeposit แทนสิทธิ์ของ key
> 4. เอกสาร Broker SubAccount Endpoints ใช้กับบัญชีหลัก/บัญชีย่อยของผู้ใช้ทั่วไปได้ไหม
>    หรือเฉพาะบัญชีที่ได้รับสิทธิ์ Broker? ขอเอกสารอ้างอิงที่ตรงกับบัญชีผู้ใช้ทั่วไป
>
> ขอคำยืนยันเป็นลายลักษณ์อักษรหรือส่งลิงก์เอกสารทางการ เราไม่ต้องการทดสอบ
> ด้วยการโอนเงินจริง และไม่แนบ API key หรือ secret ในคำถามนี้ ขอบคุณครับ/ค่ะ

คำแนะนำในอดีตให้เก็บเลขอ้างอิงและหลักฐานที่ไม่มีข้อมูลบัญชีจริงยังเป็นหลักการเก็บหลักฐานได้
แต่การประเมิน NC-21 และ wallet RQ-15/RQ-16 ในร่างเดิมถูก Superseded แล้ว
คำตอบกว้าง ๆ ว่า “API รองรับ” ไม่ใช่หลักฐานสิทธิ์ key สำหรับ NC-16; ไม่มีคำตอบใหม่จากตลาดในงานแก้เอกสารนี้
