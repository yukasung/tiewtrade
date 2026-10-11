# F-11 — Performance profile — 2026-10-10

สถานะ: **Measured** — หลักฐานวิเคราะห์ implementation ปัจจุบัน ไม่ใช่การอนุมัติแผนใหม่

## ผลที่วัด

ต้นทุนหลักคือการคำนวณ indicator และการ decode/ตรวจแท่ง ไม่ใช่ SHA-256
การ decode ทั้ง batch ทำให้ event loop ถูกถือไว้นานเกินเพดานด้วย
ยังไม่มีการแก้ production code, สูตร, snapshot, retention หรือเกณฑ์ V-15 ในงาน profile นี้

| รอบ API จริง | HTTP | เวลา | Event-loop lag สูงสุด |
|---|---|---:|---:|
| ไม่มี instrumentation | 504 INDICATOR_DEADLINE_EXCEEDED | 30.071612s | 150.893ms |
| จับเวลาแต่ละส่วน | 504 INDICATOR_DEADLINE_EXCEEDED | 30.040407s | 159.442ms |

รอบ instrumented feed core ได้97,008ช่อง (ประมาณ18.5% ของ525,600ช่อง)
และ decode98,000แท่ง/98batches ก่อนหมดเวลา จึงยังไม่ถึงหน้า output ล่าสุด
ไม่ได้รันเต็มจนสำเร็จหรือยืด deadline เพื่อให้สำเร็จ

| ส่วน | เวลารวมในรอบ instrumented | % ของเวลา HTTP | วิธีวัด |
|---|---:|---:|---|
| core | 14.208705s | 47.3% | ครอบ IndicatorStream.feed ทั้ง warm-up และ recursive updates |
| decode batch | 10.367999s | 34.5% | เวลา stored_rows ลบเวลา UserSession.execute ใน batch |
| DB | 2.155555s | 7.2% | await UserSession.execute รวม result buffering/driver conversion และ SET timeout |
| เตรียม/hash record | 1.968282s | 6.6% | timestamp, Money/Quantity.as_parts, canonical JSON และ digest.update |
| ส่วนที่เหลือ | ประมาณ1.340s | 4.5% | auth/admission, scheduling, loop/record construction, instrumentation และ error/cleanup |

decode `_stored` อย่างเดียวรวม10.120861s อยู่ภายใน decode batch ข้างต้น
ห้ามบวกซ้ำ DB เป็นเวลา client-side query ไม่ใช่ PostgreSQL execution time ล้วน
hash_timestamp0.447009s + hash_numbers1.097664s + hash_json0.390742s +
hash_update0.032869s; SHA-256 update เพียงประมาณ0.11% ของเวลา HTTP
ส่วนที่เหลือไม่ได้จับแยกแต่ละรายการ จึงไม่อ้างว่าได้วัด cleanup โดยตรง

## จุดที่ทำให้ช้า

1. `indicator_reader.py` feed core ทั้ง canonical dataset ในทุกหน้า แม้ส่งผล
   เพียง1,000ช่อง จึงทำ recursive arithmetic ซ้ำตามประวัติทั้งหมด
2. `storage.stored_rows()` สร้าง StoredCandle ทั้ง1,000แท่งแบบ synchronous
   ก่อนกลับไปถึง yield ของ reader; decode batch สูงสุด149.923ms หลังหัก DB
   จึงสามารถถือ event loop เกิน100ms ได้เอง แม้ reader yield ทุก16ช่อง
   lag ที่เห็นสอดคล้องกับช่วงนี้ แต่ไม่ได้เก็บ timeline เพื่อพิสูจน์ความสัมพันธ์ทุก sample
3. Money operations สร้าง value objects และตรวจ invariant/context หลายครั้ง:
   cProfile แยก core1,000แท่งพบ guarded wrapper45,080 calls,
   weighted_mean_money8,622 calls, Money.__post_init__18,557 calls,
   ensure_valid_amount19,543 calls และ _context45,080 calls
   นี่เป็นหลักฐานของ call volume ไม่ใช่เหตุให้ข้าม invariant หรือเปลี่ยน F-02
4. reader query295ครั้งในรอบที่จับเวลา; โดยทั่วไปหนึ่งbatchใช้2 SET timeout
   queries และ1 candle query แต่เวลา DB ยังน้อยกว่า core/decode มาก

cProfile core sample มี total self timeประมาณ0.352463s; weighted_mean_money
cumulative0.148656s, Money.__post_init__0.102509s และ _context0.053009s
cumulative times ซ้อนกัน ห้ามรวมเป็นผลประหยัดที่คาดว่าจะได้

## ขอบเขตและการทำซ้ำ

- Linux API container Python3.12.15, จำกัด2vCPU/1GiB; PostgreSQL16.15 และ Redis7
  บน Docker host เดียวกัน; Docker hostรายงาน20CPUs/33,571,786,752bytes memory
  ใช้ shared host ไม่ใช่เครื่อง benchmark ที่กันโหลดอื่นทั้งหมด
- base image `tiewtrade-api`, image ID
  `sha256:dd045295cb6c6293f8c602b97f961d2f1a8593474fd2cdd1070b543fbb22d7be`
  และ bind mount `backend/src` จาก working tree ปัจจุบันแบบ read-only
- ใช้ฐาน disposable `tiewtrade-f11-benchmark-postgres` เดิม port55434 และ Redis
  `tiewtrade-f11-test-redis` port56379 ไม่แตะฐานแอป
- Fixture เดิม525,600แถว 1m, BTC/USDT, close100/high101/low99,
  UNCONFIRMED พร้อม fetch_started_at หลังแท่งจบ; profile ไม่ลบหรือเขียน candles
  มีเพียงสมัครผู้ใช้ทดสอบใหม่เพื่อเรียก API ผ่าน auth/session/admission จริง
- HTTP ใช้ ASGITransport ใน processเดียวกับ API ไม่รวม browser/network/proxy
  ตรึง deadline30s/statement500ms/lock200ms ตาม implementation เดิม
- ตัวรัน `backend/tests/api/profile_indicators.py`: mount เป็น `/app/f11_profile.py`
  และ mountโฟลเดอร์นี้เป็น `/results`; ตั้ง API/AUTH/MARKET_DATA database URLs,
  Redis API URL, test keyringsแยกสามชุด และ signup/cookie settings แบบ benchmark
  แล้วรัน `python /app/f11_profile.py` ใน imageข้างต้นกับ `--cpus=2 --memory=1g`
- `profile.json` เก็บเวลาและ counters; `core.pstats` เปิดด้วย pstats/SnakeViz
  ได้จาก cProfile1,000แท่งแยกต่างหาก

Instrumentation เพิ่ม overhead; counters ของแต่ละ phaseครอบคนละส่วนที่ระบุ
จึงใช้จัดลำดับต้นทุน ไม่ใช้เป็นผล benchmark ผ่าน ไม่มีการคูณ sample แล้วอ้าง
เป็นเวลาจริงของ full dataset และ fixture ราคาคงที่ไม่ครอบต้นทุนทุกชุดราคา
รอบนี้ไม่วัด peak RSS/serialization สำเร็จ เพราะคำขอไม่ถึงผลครบหน้า

## สิ่งที่ข้อมูลนี้รองรับสำหรับขั้นถัดไป

การเสนอแผนแก้ performance ควรจัดการ core ที่คำนวณซ้ำทั้งประวัติและ decode
ที่ทำงานต่อเนื่องทั้งbatch ก่อนเน้น hash หรือเพิ่ม connection/concurrency
หากเสนอ checkpoint/state/revision ใหม่ ต้องระบุผลต่อ seed/digest, snapshot,
retention, grants/migration/rollback และพิสูจน์ค่ากับ pagination เดิม
ยังไม่มีการเลือกหรืออนุมัติแนวทางใหม่ และคงเกณฑ์30s/lag100msเดิม
