# F-10 — Public trade stream evidence

วันที่: 2026-10-07
ประเภท: หลักฐานประกอบแผน ไม่ใช่การอนุมัติข้อกำหนด

## เอกสารทางการ

[Binance TH WSS](https://www.binance.th/api-docs/en/#general-wss-information)
ระบุ combined endpoint `wss://nbstream.binance.th/w3w/wsa/stream`,
ชื่อ symbol ตัวเล็ก, อายุ connection 24 ชั่วโมง, server ping ทุก 3 นาที,
deadline pong 10 นาที และเพดาน 5 incoming control/frame messages ต่อวินาที
กับ 1,024 streams ต่อ connection

[Trade Streams](https://www.binance.th/api-docs/en/#trade-streams) ระบุ
`<symbol>@trade`, trade ID `t`, price `p`, trade time `T`, event time `E`.
[Recent Trades](https://www.binance.th/api-docs/en/#recent-trades-list)
คืน `id`, `price`, `time`; public GET มี weight 1 ตามเอกสาร

[websockets client](https://websockets.readthedocs.io/en/stable/reference/asyncio/client.html)
มี bounded receive queue, timeout และ ping/pong; production ต้องประกาศ dependency
โดยตรง ไม่พึ่ง package ที่ uvicorn ดึงมาทางอ้อม
[Redis Pub/Sub](https://redis.io/docs/latest/develop/pubsub/) ส่งแบบ at-most-once;
จึงใช้เป็น notification ไม่ใช้เป็นแหล่งข้อมูลที่ต้องไม่หาย

## หลักฐานที่เก็บ

ใช้เฉพาะ public data ไม่มี key/secret/ข้อมูลบัญชี ไม่ส่งออเดอร์
อ่าน REST 5 คำขอและเปิด stream 3 รอบแบบมี deadline/จำนวนตัวอย่างจำกัด
เวลา UTC อยู่ในแต่ละ fixture; เทียบเท่า 20:56–20:57 เวลาไทย

| ไฟล์ | ผลสังเกต |
|---|---|
| [01](2026-10-07-f10-public-contract/01-rest-and-query-stream.json) | REST `/trades?limit=1` ทั้ง 5 คู่ HTTP200 มี id/price/time; query-only stream ได้ control ack แต่ไม่มี trade ในช่วง 15 วินาที |
| [02](2026-10-07-f10-public-contract/02-explicit-subscription.json) | ส่ง LIST_SUBSCRIPTIONS/SUBSCRIBE; ได้ ack id2 และ trade ETHUSDT; หยุดเมื่อเก็บ 50 frames; pong probe ไม่ผ่าน deadline 5 วินาที |
| [03](2026-10-07-f10-public-contract/03-all-pairs.json) | explicit SUBSCRIBE ได้ trade ครบ BTC/ETH/SOL/XRP/DOGE, เก็บ 3 ตัวอย่างต่อคู่; pong probe สำเร็จ; มี ETH trade ID เดิมส่งซ้ำโดย E เปลี่ยน |

รูปแบบจริงมี combined envelope และ fields e/E/T/s/t/p/q/m/M;
ไม่พบ b/a ที่ตัวอย่างในเอกสารแสดง จึงไม่บังคับ fields ที่ไม่ใช้
หลาย trade มี T เท่ากัน: timestamp อย่างเดียวใช้เรียงไม่ได้
เทียบตัวตน trade ID กับเวลา/ราคา ไม่ใช้ event time หรือ received_at รีเซ็ตอายุ

## ข้อจำกัดของหลักฐาน

query-only ไม่ได้ข้อมูลในรอบแรกไม่ได้พิสูจน์ว่า endpoint ใช้ไม่ได้
แผนใช้ explicit SUBSCRIBE และรอ ack ตามวิธีที่สังเกตข้อมูลได้จริง
LIST_SUBSCRIPTIONS ไม่ได้ผลตอบกลับใน fixtures นี้ จึงไม่ใช้เป็น recovery gate
ไม่สรุป SLA/pong stability หรือ trade-ID monotonicity ทุกช่วงเวลาจากตัวอย่างสั้น
แผนฉบับแก้issue3ไม่ใช้ `(trade_time, trade_id)` เป็นtotal order
ใช้trade_timeเป็นpartialorder; เวลาเท่ากันแต่ราคาต่างกันถือว่าorderingยังไม่ยืนยัน
ไม่ใช้ตัวเลขID/arrivalorder/Eเป็นtie-breaker
ไม่ถือว่า ID ต้องต่อเนื่อง และไม่สร้าง trade ที่หาย
หาก ID/เวลา/ราคาขัดกันต้อง fail closed และกู้ข้อมูล ไม่เลือกทิ้ง conflict เงียบ ๆ
ยังต้องพิสูจน์ snapshot race และ reconnect ด้วย controlled fixtures ใน validation
ไม่เปลี่ยนไป Binance.com ตามข้อจำกัดตลาดของโครงการ

## Ordering contract — ตรวจเพิ่มสำหรับ review issue3

ตรวจเอกสารทางการวันที่2026-10-07:
- [General API Information](https://www.binance.th/api-docs/en/#general-api-information)
  ระบุRESTarrayเป็นoldest-first/newest-last จึงเลือกสมาชิกท้ายภายในresponseได้
- [Trade Streams](https://www.binance.th/api-docs/en/#trade-streams) ระบุTเป็นtrade time
  และtเป็นtrade ID ไม่พบข้อความรับรองว่าnumericIDใหญ่กว่าคือใหม่กว่า
  หรือรับรองRESTidกับWStเป็นsharedsequenceสำหรับmerge

สิ่งที่ใช้ได้: timestampต่างกันแยกเวลาเกิดtradeได้ภายในresolutionmilliseconds
สิ่งที่ใช้ไม่ได้: timestampเท่ากันไม่กำหนดลำดับสองราคาต่างกัน; IDที่ต่างกัน
หรือpacketที่มาทีหลังไม่ปิดช่องว่างนี้ และoldest-firstของRESTไม่ใช่
sequencebarrierระหว่างRESTsnapshotกับWSที่ยังส่งข้อมูลต่อเนื่อง

แผนจึงไม่ต้องรอให้ตัวอย่างสั้นพิสูจน์monotonicityที่เอกสารไม่รับรอง
แต่เก็บambiguitylatchและไม่READYเมื่อเปรียบเทียบไม่ได้
การresolveใช้RESTrequestที่เริ่มหลังพบambiguity มีTข้ามbucketที่กำกวม
และmergeกับSTREAMไม่มีsame-time/different-price; ทดสอบraceในV-8
การเลือกแบบนี้เป็นวิธีในแผนProposed ไม่ใช่หลักฐานว่าตลาดมีSLA/orderingอื่นเพิ่ม
fixturesเดิมคงไว้ตามที่เก็บจริง ไม่มีการเปลี่ยนตัวเลขเพื่อให้ตรงกับแผน
