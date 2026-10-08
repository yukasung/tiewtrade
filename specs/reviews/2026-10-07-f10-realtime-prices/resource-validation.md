# F-10 — Actual resource / concurrency evidence

วันที่: 2026-10-07
ขอบเขต: V-29..32; ผลวัดของเครื่องพัฒนา ไม่กำหนด performance SLA ใหม่

## วิธีตรวจและ isolation

ใช้ PostgreSQL จริง port 55432, Redis จริง port 56379, migrations จริง และ
runtime API/auth roles เดิม สร้างฐานข้อมูลใหม่ `tiewtrade_f10_resource_probe_1791388095`
สำหรับ probe เท่านั้น ไม่แตะฐานข้อมูล application หรือฐานข้อมูล fixture ของงานอื่น
Redis database 7 ใช้เฉพาะ probe; guard regression ใช้ disposable Redis database 8

[resource_probe.py](resource_probe.py) เปิด Uvicorn สอง **process** บน ports 58511/58512
(PIDs 62470/62471) แต่ละ process เปิด lifespan จริง มี pool/broadcaster/guard ของจริง
เพิ่มเฉพาะ observation hooks ใน probe เพื่อวัด SQLAlchemy transactions/SQL calls,
checked-out connections, asyncio tasks, physical/pending counts และ public-read timestamps
ไม่มี production API changes ในงาน validation นี้

สร้าง users/session ด้วย `create_user_in` และ `issue` ภายใต้ auth role; session tokens
ไม่อยู่ใน artifact/log ใช้สาม session ของ user เดียวเป็นตัวแทนสาม devices/browser sessions
Sockets เป็น TCP จริง ใช้ source addresses สามตัวที่ **มีอยู่แล้ว** บนเครื่อง
(ไม่ได้ตั้ง loopback alias, ปลอม X-Forwarded-For หรือเปลี่ยน Redis limits)
ช่วง setup ข้าม Redis fixed window จริงเพื่อเปิดครบ100 โดยยังคง IP30/global200
client รับทุก frame ต่อเนื่อง; ไม่เรียกตลาดจริง ไม่ใช้ API keys หรือเงิน

ผลดิบ: [resource-measurements.json](resource-measurements.json)

## ผลที่ตรวจได้

| เกณฑ์ | หลักฐาน | ผล |
|---|---|---|
| user3 ข้าม session/process | 3 session บนสอง API processes เปิดได้3; คำขอ4ถูก HTTP upgrade ปฏิเสธ; ปิดหนึ่งแล้วเปิด replacement ผ่านอีก process ได้ | ผ่าน |
| physical100/101 | process A มี100 TCP socketsพร้อมกัน; process Bมี2; process Aปฏิเสธ101 แม้ผู้ใช้ใหม่ยังมี user slots | ผ่าน |
| ก่อน DB lookup | actual ASGI guard regression ตั้ง physical100 หรือ pending16 แล้ว spy ยืนยันไม่เรียก admission/DB; Redisจริง attempt31/IP และ201/global ยืนยันไม่มี session lookup | ผ่าน |
| pending16/17 | เปิด16 actual ASGI guard calls ค้างใน admission;17ปิดทันทีโดยไม่เข้า admissionเพิ่ม ไม่มี semaphore waiting task; releaseแล้ว countersเป็น0 | ผ่าน |
| CAS / RLS / concurrentclaims | actual PG tests:9 parallelclaims ได้3, expired slot replacement, old release/renewไม่แตะreplacement, cross-userอ่าน/renewไม่ได้, schema/grantsตรงruntime | ผ่าน |
| separate bounded pool | realtime pool_size3/overflow0; maximumchecked-out3 ขณะ100sockets/notificationburst/PGlock; HTTPอยู่บน poolเดิม | ผ่าน |
| burstไม่ทำunboundedsharedreads | Redisจริงส่ง6900 invalidations; sharedsnapshotreadsสูงสุด10ในทุก rolling1s windowของทั้งสองprocess | ผ่าน |
| DB pressure failclosed | ถือ ACCESS EXCLUSIVE lockบนconnectiontableจริง; sockets102ทั้งหมดปิด; health/auth/meยังได้200ทุกคำขอ | ผ่าน |
| Redis slowdown failclosed | TCP proxyเฉพาะprobeหน่วง responseจากRedisจริง1s; newWSปฏิเสธใน504.704ms; interactiveHTTPยัง200 | ผ่าน |
| tasks/countersคืนหลังpressure | process A tasksสูงสุด507ที่100sockets และเหลือ5หลังcleanup; physical/pending0 ทั้งสองprocess | ผ่าน |

Guards รหัส5 cases และ PG connection tests6 cases รวม **11 passed**; Ruff และ
mypy ของ guard regression ผ่าน API agent ตรวจ strict watchdog / blocked send /
revocation / coordinator timing แยกใน test suite ของเส้นทางจริง

## จำนวนและ latency ที่วัด

ทุก request ด้านล่างได้200; หน่วย milliseconds เป็น client-observed latency

| Phase | health requests / median / max | auth/me requests / median / max |
|---|---|---|
| 100sockets + Redis invalidation burst | 60 / 3.287 / 23.818 | 60 / 4.236 / 15.545 |
| PG connection-table lock | 20 / 10.250 / 71.023 | 20 / 6.620 / 72.143 |
| หลัง failclosedcleanup | 10 / 9.766 / 12.826 | 10 / 9.555 / 12.608 |
| Redisresponse delay1s | 10 / 8.713 / 10.672 | 10 / 8.898 / 9.785 |

Process A observation54.048s:8253 realtime transactions,72287 SQL calls;
process B54.046s:294 transactions,2246 SQL calls
ช่วง sampleที่physical100ยาว4.495s วัดรวม168.183transactions/s และ1470.262SQLcalls/s
ตัวเลขรวม setup/renew/publicread/cleanup ที่อยู่ในช่วง observation ไม่ได้อ้างว่า
จำนวนSQLcallsเท่ากับจำนวนcoordinator transactions หรือเป็นmaximum sustainedthroughput

## ข้อจำกัดและการรันซ้ำ

เป็น bounded local stress run ไม่ใช่ production SLA / capacity certification
100socketsไม่จำเป็นต้องคงสุขภาพดีเมื่อDBช้า: เกณฑ์คือปิดfailclosed, boundedresources
และinteractiveHTTPยังใช้ได้ การถือล็อกจริงทำให้ทุกsocketปิดตามที่คาด
pending16 regressionใช้ ASGI admission barrier เพื่อให้ boundary deterministic;
physical100และcrossprocessใช้จริงผ่านTCP/PG/Redis

การพยายามครั้งแรกไม่อ่าน frames ต่อเนื่องระหว่างรอ admissionwindow ทำให้ clientreceive
queueเต็มและconnectionsทยอยปิด จึงไม่ผ่าน100socketassertion ปรับ harnessให้drainทุกframe
แล้วรันใหม่; ไม่แก้productionlimitsเพื่อให้ผ่าน
แก้ shutdown orderingของprobeให้ปิด APIprocesses ก่อนรอRedisproxyconnectionsจบ
การรันสุดท้าย exit0 และปิดtemporaryprocessesแล้ว

รันจาก repo root หลังตั้ง isolated fixture URLs ตาม development environment:

```sh
source /private/tmp/f10-test-env.sh
backend/.venv/bin/python specs/reviews/2026-10-07-f10-realtime-prices/resource_probe.py --driver
TIEWTRADE_TEST_REDIS_URL=redis://127.0.0.1:56379/8 \
  backend/.venv/bin/python -m pytest backend/tests/api/test_price_guard_budget.py \
  backend/tests/infra/realtime/test_connections.py -q
```

Probeต้องมีสาม assignedIPv4addresses, localPostgreSQLadminสำหรับสร้าง disposableDB,
และports58511/58512/56380ว่าง; ไม่ใช้เพื่อทดสอบapplicationDB
ฐานข้อมูล probeที่สร้างไว้ใช้เพื่อvalidationเท่านั้น และลบหลังจบการตรวจ
