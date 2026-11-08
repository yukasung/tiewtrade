# Roadmap

สถานะ: **Proposed** — รอเจ้าของอนุมัติ
วันที่: 2026-09-24

---

## สถานะที่ใช้

| สถานะ | หมายถึง |
|---|---|
| **Planned** | ตกลงแล้วว่าจะทำ แต่ยังไม่มี spec |
| **Spec Ready** | มีโฟลเดอร์ใน `specs/features/` และ `requirements.md`, `plan.md`, `validation.md` ผ่านการอนุมัติครบทั้งสามฉบับ **และ** ไม่มี Needs Clarification ที่เกี่ยวกับงานนี้ค้างอยู่ — ครบทุกข้อจึงเริ่มเขียนโค้ดได้ (ตาม `AGENTS.md`) |
| **In Progress** | กำลังทำอยู่ |
| **Development Complete** | พัฒนาและรีวิวเสร็จ ด่านที่ไม่เลื่อนผ่านครบ รอตรวจรับรวมท้ายชุด/เกณฑ์ที่ยังค้างตาม testing หัวข้อ 7; ยังไม่รับรองพร้อมใช้งานจริง |
| **Completed** | โค้ดทำงานได้จริง **และ** มีเทสต์ **และ** `validation.md` ผ่านครบ |

**"มีไฟล์แล้ว" ไม่นับว่า Completed**

### รวมตรวจท้ายแต่ละชุด — Approved 2026-10-27

ใช้ [testing หัวข้อ 7](standards/testing.md#7-เลือกการตรวจตามผลกระทบและลดงานซ้ำ)
เป็นกฎหลัก: แต่ละ feature ตรวจ targeted correctness/safety/regression, review,
static checks และ required CI ตามผลกระทบ; รวมชุดยาวเมื่อพัฒนาและรีวิวครบทั้งชุด
พร้อมด่านที่ไม่เลื่อนผ่านแล้ว บน candidate รวมที่นิ่ง ไม่รอทุก feature เป็น Completed
การอนุมัตินี้แทนระยะรันเดิมในแผน/validation/คำสั่งที่ให้ตรวจยาวราย feature
หรือให้ทุกชุดรอชุดที่ 9 โดยไม่เปลี่ยนเกณฑ์หรือผลเดิม

**เป้าหมายเวลา — Approved 2026-10-27:** รอบตรวจชุดยาวปกติประมาณ 1–2 ชั่วโมง
เป็นงบวางแผน ไม่ใช่เพดานตัดการตรวจ; หากคาดว่าเกิน 2 ชั่วโมง ให้ตรวจงานซ้ำและ
แจ้งเหตุผล/ขอบเขต/เวลาคาดหมายก่อนเริ่มตาม testing หัวข้อ 7 ไม่เพิ่มจุดขออนุมัติใหม่
แยกรอบระยะยาวตามเกณฑ์หรือความเสี่ยงที่จำเป็น โดยไม่ลดเกณฑ์หรือระยะต่อเนื่อง
งานที่ยังตรวจไม่ครบคง Pending Full Validation และเก็บผล Failed/Partial เดิม

| จุดตรวจร่วม | ขอบเขต / งานค้าง |
|---|---|
| ท้ายชุดที่ 4 — Paper Trading | หลัง F-13–F-17 พัฒนาและรีวิวครบ: full regression, Paper integration/end-to-end และเกณฑ์ชุดยาวที่เกี่ยวข้อง เช่น F-14 V-17, F-15 V-19/W1–W4, F-16 V-20; ใช้เกณฑ์/profile ที่อนุมัติแล้ว ไม่สร้าง profile ใหม่เอง |
| ท้ายชุดที่ 5 — ความเสี่ยงและความปลอดภัย | หลัง F-18–F-19 พัฒนาและรีวิวครบ: รวมเกณฑ์ชุดยาวของ risk/stop/recovery และ Paper integration ที่พร้อม เช่น F-18 V-21 และ F-16 V-18 ที่พึ่ง F-18; ไม่เลื่อน safety ที่จำเป็นต่อพฤติกรรมที่เปิดใช้งาน |
| ท้ายชุดถัดไป | รวมตรวจ feature ในชุดนั้นตามเกณฑ์เดิม; รายการที่รอ dependency ให้ระบุ feature ที่รอและ checkpoint ถัดไปใน validation/ทะเบียนเดิม |
| ชุดที่ 9 | ตรวจรับระบบรวมก่อนใช้งานจริง พร้อมเกณฑ์ค้างและ F-11 capacity/ระยะยาวเดิม; ใช้หลักฐานท้ายชุดที่ยัง valid ไม่รันทุกชุดยาวซ้ำอัตโนมัติ |

เกณฑ์ที่ยังรอ dependency/profile ที่อนุมัติให้คง Pending Full Validation/Pending Dependency
ไม่ถือว่าทั้ง feature/ชุดผ่านครบ คงผล Failed/Partial และสถานะปัจจุบันจนมีหลักฐานจริง
ทะเบียนเดิมด้านล่างใช้ติดตามต่อ โดยอ่านกำหนดเวลาร่วมกับตารางนี้;
ข้อความอ้างชุดที่ 9 ในบันทึกเดิมเป็นประวัติก่อน amendment นี้ ไม่ใช่คำสั่งให้รอทุกงาน

### การตรวจรับระบบหลังชุดที่ 8 (เจ้าของอนุมัติ 2026-10-11)

**ปรับการเลือก full regression — Approved 2026-10-26:** ใช้กับงานปัจจุบันและงานถัดไป
ตาม [testing หัวข้อ 7](standards/testing.md#7-เลือกการตรวจตามผลกระทบและลดงานซ้ำ):
ไม่บังคับชุดเต็มก่อน merge ทุก feature ใช้ targeted regression และ static checks
ตามผลกระทบ; บังคับ full regression เมื่อเปลี่ยนส่วนกลาง กระทบหลายระบบ ระบุขอบเขต
ผลกระทบไม่ได้ หรือ targeted Tests ไม่เพียงพอ และที่ release checkpoint.
คง safety/integration/concurrency tests ที่เกี่ยวข้องและ required CI; ไม่เปลี่ยนผล
validation เดิมหรือสถานะ feature จากการปรับ workflow นี้

**ใช้กับงานถัดไปทั้งหมด — Approved 2026-10-24:** กฎ testing หัวข้อ 7 เรื่องไม่รัน
workload/endurance/timed smoke อัตโนมัติท้ายงาน ใช้กับทุก feature รวม F-37,
F-16–F-32 และ F-36 ที่ยัง Planned ตลอดจนงานที่กลับมาพัฒนาต่อ.
spec ใหม่ต้องแบ่ง development/candidate/release checkpoints ตาม
[แม่แบบ feature](features/README.md); ไม่ใช่การอนุมัติ spec ล่วงหน้าหรือข้าม safety gates.
ตรวจเอกสารงานค้างแล้ว: F-13 ไม่มี full workload เพิ่มที่ต้องสร้าง,
F-14 V-17 และ F-15 V-19/W1–W4 รวม F-38 V-12/V-13/V-15 คงชุดที่ 9
ตามทะเบียนเดิม. ปรับ F-15 timed smoke และ F-38 checkpoint ให้ชัด;
ไม่รันผลที่ผ่านแล้วซ้ำโดยไม่มีผลกระทบใหม่ และไม่เปลี่ยน Pending/Failed เป็น Passed.

- เลื่อนการทดสอบโหลดและความเสถียรระยะยาวของ F-11 ไปตรวจรับรวมในชุดที่ 9 หลังพัฒนาชุดที่ 8 เสร็จ ไม่รันทดสอบยาวระหว่างพัฒนาโดยอัตโนมัติ
- ระหว่างพัฒนายังต้องทดสอบความถูกต้อง ความปลอดภัย การคำนวณเงิน และ regression ที่เกี่ยวข้อง; การเลื่อนนี้ไม่ยกเว้นด่านเหล่านั้น
- ใช้สถานะ **Development Complete — พัฒนาเสร็จ รอตรวจรับระบบ** ได้เมื่อ implementation/review และด่านที่ไม่เลื่อนผ่านครบแล้ว; ยังไม่ใช่ Completed และไม่รับรองพร้อมใช้งานจริง สถานะปัจจุบันของแต่ละ feature ดูตารางงานด้านล่าง
- ชุดที่ 9 ต้องตรวจ capacity/ระยะยาวและระบบรวมตาม [validation ของ F-11](features/2026-10-10-backend-indicators/validation.md) และ [แผน performance](features/2026-10-10-backend-indicators/performance-plan-v2.md) โดยคงเกณฑ์เดิม; C2 rerun และ R2-7 exact 525,600-slot ผ่านแล้ว ส่วน C3/C5, C4 fairness และ C6 ยังต้องติดตาม ไม่เปลี่ยน Failed/Partial ที่เหลือเป็น Passed
- ต้องผ่านการตรวจรับก่อนใช้เงินจริงใน F-25 หรือเปิดให้คนนอก; ระหว่างนี้พัฒนาและทดลองภายในด้วย Paper เท่านั้น การเปิด prepared mode ใช้งานจริงและ Completed ยังคงต้องผ่านด่านเดิม; merge เพื่อพัฒนาต่อทำได้เมื่อ implementation/review และด่านที่ไม่เลื่อนผ่านครบตาม testing standard (เจ้าของอนุมัติ 2026-10-11)
- ก่อนเริ่มรอบยาวให้ตกลงเวลากับเจ้าของอีกครั้ง เก็บ [หลักฐานเดิม](features/2026-10-10-backend-indicators/profiling/capacity-report.md) ไว้เพื่อเปรียบเทียบ

**เพิ่มเติมตามคำสั่งปรับ workflow 2026-10-12:** performance/workload/stress/endurance/
resource ชุดเต็มของ feature ต่าง ๆ รวม F-12 V-17 รันที่ release checkpoint/ชุดที่ 9
ตาม [testing standard หัวข้อ 7](standards/testing.md#7-เลือกการตรวจตามผลกระทบและลดงานซ้ำ).
ระบุ `Pending Full Validation` ในเกณฑ์ที่ยังไม่รัน ไม่เปลี่ยนผล Failed/Partial ที่มีอยู่
และไม่เลื่อนเทสต์ correctness/trading safety ตามการจัดระยะรัน benchmark.
ต้องรันส่วนที่จำเป็นเร็วขึ้นเมื่อมีความเสี่ยงจริงที่ smoke พิสูจน์ไม่ได้.

**F-01 ถึง F-04 เสร็จแล้ว** (2026-09-27) · **F-33** (2026-09-28) · **F-35** (2026-10-01)
· **F-05** (2026-10-03) · **F-06** (2026-10-04) · **F-07 เสร็จแล้ว** (2026-10-07) · **F-08 เสร็จแล้ว** (2026-10-07) — บัญชีเดียวและ TailAdmin ทุกหน้าปัจจุบัน; frontend113/E2E8/reviewsผ่าน; เจ้าของทดสอบ UI และสั่ง commit/push/PR/CI/merge ผ่าน [PR #6](https://github.com/yukasung/tiewtrade/pull/6)

สิ่งที่ F-01 ทิ้งไว้ให้งานถัดไปใช้: โครงชั้นโค้ดพร้อมกฎการพึ่งพาที่บังคับด้วย CI,
ตัวตรวจความบริสุทธิ์ของ `core`, ด่านตรวจ 9 ด่านที่พิสูจน์แล้วว่าจับความผิดได้จริง,
ขั้นตอนสร้างชนิดข้อมูลจากสัญญา API และ Docker Compose แบบบาง

สิ่งที่ F-33 ทิ้งไว้ให้งานถัดไปใช้: `tiewtrade.venues` — สามสัญญา (`PriceSource`,
`WalletSource`, `SymbolConstraintSource`), ชนิดข้อมูลกลาง (`Symbol` ที่เก็บสองส่วนแยกกัน,
`Price` ที่พาสองเวลา, `SymbolConstraints`, `WalletHoldings`), ข้อผิดพลาดกลาง 6 ชนิด (F-35 เพิ่ม `VenueProtocolError`)
ที่มีรหัสคงที่เอาไปใส่ `failure_code` ของ audit log ได้, `CallCost` กับ `RateLimitGuard`
และ `FakeVenue` ที่ทำตามสัญญาครบ **รวมกรณีผิดพลาดทุกชนิด** — งานหลังทดสอบได้
โดยไม่ยิงตลาดจริง ส่วนการตรวจข้อจำกัดของเหรียญอยู่ใน `tiewtrade.core.trading_limits`
เพราะเป็นการคำนวณ (`standards/backend.md` หัวข้อ 3)

**ห้ามให้คำศัพท์ของตลาดออกนอก `venues`** มีด่านอ่าน AST บังคับอยู่ ครอบข้อความ
ชื่อฟังก์ชัน ชื่อคลาส ชื่อตัวแปร และชื่อ module ที่ import — และ **ส่วนกลางของ `venues`
ห้าม import ไลบรารีเครือข่าย** ตัวเชื่อมจริงต่อเครือข่ายได้ แต่ต้องอยู่ใน package ย่อย

**สองเรื่องที่ฝากไว้กับ F-35 — ปิดแล้วทั้งคู่ (2026-10-01)**
รายชื่อโมดูลส่วนกลางยังอยู่สามที่เหมือนเดิม แต่มีเทสต์เทียบกับโครงสร้างจริงแล้ว
ลืมเติมชื่อจึงแดงทันที (`backend/tests/test_venue_isolation.py`) · และคำศัพท์ของตลาด
มาจาก `VENUE_VOCABULARY` ที่ **แต่ละ package ตัวเชื่อมประกาศเอง** ตัวเชื่อมที่ไม่ประกาศ
ทำให้ด่านแดง การเพิ่มตลาดใหม่จึงขยายด่านให้เองโดยไม่ต้องมีใครจำ

สิ่งที่ F-35 ทิ้งไว้ให้งานถัดไปใช้: `tiewtrade.venues.binance_th` — `BinanceThTransport`
(ทางเดียวที่ออกไปหาตลาด ทำ **จองโควตา → เรียก → แปลผล** ตามลำดับ), `IpWeightLimiter`,
ตารางแปลข้อผิดพลาดของตลาดเป็นหกชนิดกลาง, `BinanceThPrices`, `BinanceThConstraints`
พร้อมที่พักข้อมูลที่ผู้เรียกกำหนดอายุ · ข้อมูลตอบกลับจริงที่บันทึกไว้อยู่ใน
`backend/tests/venues/binance_th/recorded/` และเก็บใหม่ได้ด้วย
`backend/scripts/record_binance_th.py`

**สามข้อที่งานถัดไปต้องรู้:**
1. **ตัวกั้นอัตรานับได้แค่ในกระบวนการเดียว** หลายกระบวนการบนเครื่องเดียวกันยังชนเพดาน
   ต่อ IP ร่วมกันได้ — **ตัวกั้นที่มีสภาพร่วมกันต้องมาก่อนปล่อยผู้ใช้จริง**
   และเพดานจำนวนออเดอร์นับ **ต่อบัญชี** ซึ่งต้องมีตัวนับอีกตัวที่รู้จักบัญชี
   (ตัวที่มีอยู่ปฏิเสธต้นทุนที่มีออเดอร์ติดมา ไม่นับผ่านเงียบ ๆ)
2. **ยังไม่มีการแปลรหัส "เงินไม่พอ"** เพราะงานนี้ไม่ส่งออเดอร์จึงไม่มีคำตอบจริงให้ดู
   รหัส `-2010` ของตลาดเป็น "ออเดอร์ถูกปฏิเสธ" แบบรวม การแปลเป็น `INSUFFICIENT_FUNDS`
   จะเป็นการเดา — งานที่ส่งออเดอร์เป็นผู้เพิ่มจากคำตอบจริง
3. **คู่เทรดที่ตลาดรายงานตัวเลขผิดกฎมีจริง** (`stepSize` เป็นศูนย์) ข้อจำกัดจึงแปลง
   ทีละคู่ตอนมีคนถาม และคู่ที่อ่านไม่ได้ดังเป็น `VenueProtocolError` — ดู NC-13

สิ่งที่ F-06 ทิ้งไว้ให้งานถัดไปใช้: **ปัจจัยที่สองที่ใช้งานได้จริง** —
`tiewtrade.core.totp` (การคำนวณล้วน พิสูจน์ด้วยชุดตัวเลขทดสอบของ RFC 6238),
`tiewtrade.infra.crypto` (สัญญา `KeySource` + การปิดผนึกด้วย AES-GCM),
`infra/auth/{totp,recovery_codes,challenges,recovery_grants,cleanup}.py`
และเจ็ด endpoint ใต้ `/auth/totp/`

**เพิ่ม endpoint ใหม่แล้วต้องจัดประเภทมัน** — `routing_policy.py` เปลี่ยนจากสองรายการ
เป็น **ตารางเดียวที่ทุกเส้นทางต้องมีแถวของตัวเอง** (`public`, `renews`, `reverify`,
`risk_reducing`, `accepts_recovery_grant`) เส้นทางที่ไม่มีแถวทำให้เทสต์แดง **และ**
ถูก middleware ปฏิเสธตอนรัน · **`RouteRule` ปฏิเสธการตั้ง `risk_reducing` กับ
`reverify` พร้อมกันตั้งแต่ตอนประกาศ** ฉะนั้นกฎ "คำสั่งลดความเสี่ยงต้องทำได้เสมอ"
ถูกบังคับไว้ก่อนที่เส้นทางเหล่านั้นจะมีอยู่จริง

**`risk_reducing` ไม่ใช่ "ไม่ต้องยืนยันซ้ำ"** — รีเซ็ตเพดานขาดทุนและเปิดบอทกลับเป็น
**ข้อยกเว้นที่เจ้าของอนุมัติไว้** ซึ่งคนละเรื่องกัน ห้ามรวมเป็นธงเดียวเพราะงานหลัง
จะหยิบไปใช้เป็นเกณฑ์ตัดสินประเภทออเดอร์ผิด

**งานที่ต้องการปัจจัยที่สองใช้ `reverify=True` ในตาราง** ไม่ใช่ตรวจเองใน endpoint
— การตัดสินอยู่ที่ middleware ที่เดียว และรหัสมาทาง header `X-TiewTrade-TOTP`
· **F-07 เป็นผู้ใช้รายแรกของกลไกนี้** (เพิ่ม/เปลี่ยน API key) และ **F-24 ต้องแทนที่
`live_trading_enabled()` ใน `totp_routes.py` ด้วยของจริง** มิฉะนั้นกฎ "ปิด TOTP
ขณะที่ Live เปิดอยู่ไม่ได้" จะเป็นจริงแค่ในเทสต์

**F-07 ใช้โครงสร้างของ `infra/crypto` ซ้ำได้ แต่ต้องมีกุญแจของตัวเอง** — `KeyPurpose`
บังคับข้อนี้ที่ระดับชนิดข้อมูล และค่าที่ปิดผนึกผูกกับชื่องาน ฉะนั้นกุญแจที่ถูกตั้งสลับกัน
ตอนนำขึ้นเครื่องจะดังทันที ไม่ใช่เปิดผนึกออกเงียบ ๆ

**สามข้อที่งานถัดไปต้องรู้:**
1. **T-03 ยังไม่ปิด** งานนี้ตัดสินเฉพาะที่มาของกุญแจบนเครื่องพัฒนาและ CI
   ส่วนเครื่องจริงเป็นงาน **F-31** · **กุญแจหายทั้งระบบยังไม่มีทางกู้** และรหัสสำรอง
   ไม่ใช่คำตอบของเรื่องนั้น (มันแก้กรณีผู้ใช้เสียเครื่อง ไม่ใช่กรณีกุญแจหาย)
2. **NC-14 ยังเปิดอยู่และ F-06 ไม่ได้ปิดมัน** — รหัสสำรองยังต้องผ่านขั้นรหัสผ่าน
   ที่ถูกหน่วง และเพดานการเดาของปัจจัยที่สองก็กันเจ้าของออกเป็นช่วง ๆ ได้
   **ต้องปิดก่อน F-24**
3. **ยังไม่มีตัวตั้งเวลาเรียกงานเก็บกวาด** — `scripts/sweep_auth_tables.py` มีแล้ว
   และครอบทั้ง `auth_throttle` กับ `login_challenges` แต่คนต้องสั่งเอง
   การตั้งเวลาเป็นงาน **F-31** และต้องมีก่อนปล่อยผู้ใช้จริง

สิ่งที่ F-05 ทิ้งไว้ให้งานถัดไปใช้: **ผู้ใช้จริงที่ระบบรู้จัก** — `tiewtrade.infra.auth`
(ข้อมูลเข้าสู่ระบบ, session, ตัวนับอัตราการเรียก, argon2, รายการรหัสผ่านที่ห้าม),
`presented_session()` ใน `infra/db/session.py` สำหรับช่วงก่อนรู้ว่าเป็นผู้ใช้คนไหน,
และ middleware ตัวเดียวใน `services/api` ที่ตอบว่าคำขอเป็นของใคร

**เพิ่ม endpoint ใหม่แล้วมันถูกคุ้มครองโดยปริยาย** — เส้นทางที่ไม่อยู่ใน `PUBLIC_ROUTES`
ต้องมี session และมีเทสต์เดินทุกเส้นทางใน `app.routes` เพื่อให้ลืมคิดเรื่องสิทธิ์ไม่ได้
· **เส้นทางที่ต่ออายุ session ต้องประกาศตัวเองใน `RENEWING_ROUTES`** ค่าเริ่มต้นคือ
ไม่ต่ออายุ ฉะนั้น endpoint ที่หน้าเว็บเรียกเป็นรอบ ๆ (F-10) จะไม่ทำให้ session
ไม่หมดอายุโดยไม่ตั้งใจ

**งานที่ต้องการตัวตนของผู้ใช้ใช้ `Authenticated` จาก middleware** ไม่ใช่อ่านค่าจาก
คำขอเอง และ **ชนิดนั้นเพิ่มช่องได้** ซึ่งเป็นรอยต่อที่ F-06 จะใช้เสียบ TOTP

**สามข้อที่งานถัดไปต้องรู้:**
1. **NC-14 ยังเปิดอยู่** — การหน่วงกันเดารหัสผ่านปฏิเสธก่อนตรวจรหัสผ่าน ฉะนั้น
   เจ้าของที่กรอกถูกก็ถูกปฏิเสธ · **ต้องปิดก่อน F-24**
2. **ไม่มีทางกู้รหัสผ่าน** และไม่มีสคริปต์รีเซ็ต — ติด T-05 (ส่งอีเมล) และ NC-02
   (ใครมีอำนาจรีเซ็ต)
3. **ตาราง `auth_throttle` ยังไม่มีงานเก็บกวาด** แถวของ IP ที่ไม่กลับมาอีกค้างอยู่

สิ่งที่ F-04 ทิ้งไว้ให้งานถัดไปใช้: ตาราง `audit_events` ที่เพิ่มได้อย่างเดียว,
ทางเขียนเดียวคือ `record_event()` ที่อยู่ใน transaction เดียวกับการกระทำ,
ชนิดเหตุการณ์ที่จำกัดด้วย `CHECK` และตัวดักการสร้างพาร์ทิชันที่ปิดกลไกให้เอง

**งานที่แตะเงินทุกงานต้องเพิ่มชนิดเหตุการณ์ของตัวเอง** ในงานเดียวกัน ครบสามที่:
`AuditAction` ในโค้ด, ตัวตรวจ invariant รายเหตุการณ์ และ `CHECK` ใน migration
(ทั้งรูปร่างของ `details` และคอลัมน์แกน) — ชนิดที่ไม่ได้ประกาศเขียนลงฐานข้อมูลไม่ได้เลย
**ช่องข้อความอิสระห้ามโดยปริยาย** ถ้าจำเป็นต้องมี ต้องขออนุมัติเป็นรายช่อง

**ปิดคำตัดสินก่อน F-16 แล้ว (NC-F16-01, 2026-10-25):** เจ้าของอนุมัติปฏิเสธคำสั่ง
ที่บันทึกไม่ได้ รวมลดความเสี่ยง; Live ให้ผู้ใช้จัดการตรงที่ตลาด ตาม trading-safety §9.

สิ่งที่ F-03 ทิ้งไว้ให้งานถัดไปใช้: PostgreSQL ใน Compose และ CI, Alembic ที่เขียน SQL
ด้วยมือ, บทบาทฐานข้อมูล 5 ตัว (`engine` สองบทบาทตาม Q-3), กลไก RLS ที่ไม่ระบุผู้ใช้แล้ว
อ่านและเขียนไม่ได้, กลไก append-only ที่เปิดทีละตารางและครอบ `TRUNCATE` ด้วย,
domain ของเงินที่ปฏิเสธค่าที่เก็บไม่ได้แทนการปัดเงียบ ๆ, ตาราง `users` ชุดเล็กสุด
และนโยบาย log ที่ค่าที่ bind ไม่ลง log ของ PostgreSQL

**ทุกตารางใหม่ต้องมีคอลัมน์เจ้าของ เปิด RLS และให้สิทธิ์ทีละคอลัมน์** ตารางที่ห้ามแก้
ย้อนหลังให้เรียก `tiewtrade_make_append_only()` — F-04 (audit log) เป็นผู้ใช้จริงรายแรก

สิ่งที่ F-02 ทิ้งไว้ให้งานถัดไปใช้: `tiewtrade.core.money` — ชนิด `Money` กับ
`Quantity` ที่ผูกหน่วยติดมาด้วย, ขอบเขต context ของ `Decimal` ที่ครอบทุกทางเข้า
สาธารณะ, ทิศทางการปัด 4 แบบที่ชื่อไม่กำกวมกับค่าติดลบ, ข้อผิดพลาดชนิดเดียว
`MoneyError` ที่ผู้เรียกดักได้ และค่าคงที่ช่วงค่าที่ตรงกับ NUMERIC(38,18)

**ห้ามคำนวณเงินหรือปริมาณด้วย `Decimal` เปล่าหรือ `float` ที่อื่นอีก** ใช้ชนิด
ในโมดูลนี้เท่านั้น

---

## ชุดที่ 1 — ฐานราก

งานแก้ความถูกต้อง: [API deadline clock](features/2026-11-07-api-deadline-clock/requirements.md)
**In Progress (2026-11-07)** — requirements/plan/validation Approved; code review APPROVED / authorized refactor validated.
แก้ clock-domain mismatch ใน chart live/shared indicator HTTP deadline โดยคง budgets,
auth และ cancellation semantics เดิม; branch `fix/api-deadline-clock`.
Runtime แก้สอง HTTP boundaries; boundary/cleanup 41 และ API/DB/cleanup 69 ผ่าน (มี tests ซ้ำระหว่างชุด),
recovery default uvloop 10.4s และ standard asyncio 8.8s ผ่าน; static checks ผ่าน.
[Checkpoint](features/2026-11-07-api-deadline-clock/evidence/implementation-checkpoint.md).
[Refactor checkpoint](features/2026-11-07-api-deadline-clock/evidence/refactor-checkpoint.md): boundary rerun 24 ผ่าน; runtime unchanged.
เจ้าของอนุญาต commit/push/PR แล้ว; required CI Pending. ยังไม่ Completed และ merge ต้องรอคำสั่ง. งานลบ `/prices` ยังมี V-03 blocker จนตรวจ candidate รวม.

งานปรับ UI: [ลบหน้า “ราคาสด” `/prices`](features/2026-11-07-remove-prices-page/requirements.md)
**In Progress (2026-11-07)** — requirements/plan/validation Approved; NC-PRICES-01 Closed.
Implementation/review findings แก้ครบ บน branch `feature/remove-prices-page`.
**2026-11-08:** รวม main 1237bf6 (deadline fix); default-loop chart E2E 4 flows ผ่าน 22.6s,
ปิด Medium V-03 recovery blocker; Low stale route list ปิดแล้ว.
Frontend targeted 65, backend price API 9 และ static/build/price-service evidence เดิมยัง valid.
[Combined checkpoint](features/2026-11-07-remove-prices-page/evidence/combined-checkpoint-20261108.md).
2026-11-08 refactor test helper ผ่าน price-service E2E 19.3s, ESLint/TypeScript; review/local gates ผ่าน.
[Refactor checkpoint](features/2026-11-07-remove-prices-page/evidence/refactor-checkpoint-20261108.md).
รอคำสั่ง Git และ required CI; ยังไม่ Completed/พร้อม merge; ยังไม่ commit/push งานนี้.


Prices removal publication update (2026-11-08): owner authorized commit/push/PR; required CI Pending. Merge requires a separate command.
Main chart 3m base refresh: [affected validation passed](features/2026-11-07-remove-prices-page/evidence/base-refresh-checkpoint-20261108.md), 29 unit tests / five chart browser flows; required CI pending refreshed SHA.

F-01 follow-up: [Security dependency remediation](features/2026-11-05-security-dependency-remediation/requirements.md)
**Code review APPROVED — local checks passed; final CI pending (2026-11-05)** — certifi 2026.7.22 → 2026.10.18 และ
Vite 6.4.3 → 6.4.4; branch `feature/security-dependency-remediation`.
requirements/plan/validation Approved; เปลี่ยนเฉพาะสอง lock entries แล้ว.
156 backend + 10 frontend tests, TLS/dev/preview/build และ OSV ผ่าน local;
OSV ไม่มี High/Critical/Unknown และมี Medium 4 records. DV-10 Pending Full Validation.
เจ้าของอนุญาต commit/push/PR แล้ว; ขั้นถัดไปติดตาม required CI บน final candidate.
ยังไม่ merge/Completed และ DV-10 ยังคง Pending Full Validation.

F-01 follow-up: [Self-hosted CI / ลดรอบซ้ำ](features/2026-10-23-self-hosted-ci/requirements.md)
**Retired / ไม่เปิดใช้ self-hosted CI (2026-10-24)** — เจ้าของเปลี่ยน repository เป็น Public
และให้ปิดงานทดลอง; ใช้ GitHub-hosted workflow เดิมต่อโดยไม่เปลี่ยน triggers/storage.
Post-merge CI [39972554569 attempt 3](https://github.com/yukasung/tiewtrade/actions/runs/39972554569/attempts/3)
บน `51f0e2700e5c478e5b13b52f2cedcff2f6961d8d` ผ่านครบ 6/6;
`main` บังคับ checks ทั้ง 6 (strict/up-to-date, enforce admins), ห้าม force push/delete.
ผล Failed/Partial ของ isolation proof ยังอยู่ตามเดิม ไม่ถือว่า self-hosted validation ผ่าน;
NC-52 ถูกพักตามการเลิกใช้แนวทางนี้ ไม่ใช่ข้อพิสูจน์สำเร็จ. ไม่เคยลงทะเบียน runner.
VM/cache/runtime ถูกลบและถอน Lima แล้ว แต่ disabled account/home ยังเหลือจากข้อจำกัด macOS.
Helper/test ทดลองเก็บนอก repo ไม่รวมใน PR; ดู [checkpoint](features/2026-10-23-self-hosted-ci/evidence/closure-checkpoint.md).
ไม่เปลี่ยนสถานะ F-01/F-12 หรือรับรอง release/Live gates เพิ่มจากผล CI นี้.

| รหัส | งาน | สถานะ | หมายเหตุ |
|---|---|---|---|
| F-01 | วางโครง repo, เครื่องมือ, CI | **Completed** | เสร็จ 2026-09-27 — PR #1 merge เข้า main, CI เขียวครบ 5 job, เกณฑ์ใน `validation.md` ครบ 16 ข้อ |
| F-02 | ชนิดข้อมูลเงินและการคำนวณพื้นฐาน | **Completed** | เสร็จ 2026-09-27 — PR #3 merge เข้า main, CI เขียวครบ 5 job, เทสต์ 197 ข้อ, เกณฑ์ใน `validation.md` ครบ V-1..V-33 |
| F-03 | โครงฐานข้อมูล + migration + แยกข้อมูลผู้ใช้ | **Completed** | เสร็จ 2026-09-27 — merge เข้า main, CI เขียวครบ 6 job, เทสต์ 271 ข้อ, เกณฑ์ใน `validation.md` ครบ V-1..V-42 |
| F-04 | Audit log | **Completed** | เสร็จ 2026-09-27 — merge เข้า main, CI เขียวครบ 6 job, เทสต์ 364 ข้อ, เกณฑ์ใน `validation.md` ครบ V-1..V-40 |
| F-33 | **ชั้นแยก venue (แบบบาง)** | **Completed** | เสร็จ 2026-09-28 — merge เข้า main, CI เขียวครบ 6 job, เทสต์ 440 ข้อ · ส่งมอบ **สามสัญญา** (ราคา, กระเป๋า, ข้อจำกัดของเหรียญ) **สัญญาส่งออเดอร์ยังไม่ทำ เพราะติด NC-08** ต้องขออนุมัติแยกเมื่อ NC-08 ปิด |
| F-35 | **ตัวเชื่อม Binance TH** | **Completed** | เสร็จ 2026-10-01 — merge เข้า main, CI เขียวครบ 6 job, เทสต์ 620 ข้อ · ทำ **สองสัญญา: ราคา และข้อจำกัดของเหรียญ** จาก endpoint สาธารณะเท่านั้น **ไม่มีกุญแจ ไม่มีกระเป๋า ไม่มีการส่งคำสั่งซื้อขาย** (กระเป๋าต้องใช้กุญแจของผู้ใช้ จึงเป็นงานของ F-14 · การส่งออเดอร์ติด **NC-08**) · Spot เท่านั้น, `/api/v1`, ยังไม่มี Futures (**NC-12**) · มีงาน CI แยก `venue-contract` รันรายวันเทียบสัญญากับตลาดจริง **ไม่อยู่ในเงื่อนไข merge** |

## ชุดที่ 2 — ผู้ใช้และบัญชี

| รหัส | งาน | สถานะ | หมายเหตุ |
|---|---|---|---|
| F-05 | สมัคร, เข้าสู่ระบบ, session | **Completed** | **พบข้อบกพร่องตอนวางแผน F-06 และแก้ใน F-06:** ตัวนับอัตราการเรียกถูกย้อนทิ้งทุกครั้งที่คำขอถูกปฏิเสธ ฉะนั้น **การคุมอัตราหน้า login ไม่ทำงานเลย** — ไม่มีเทสต์ใดครอบเพราะเทสต์เดิมเรียกตัวนับตรง ๆ ไม่ผ่านเส้นทางที่ถูกปฏิเสธ (ดู `specs/features/2026-10-03-totp-2fa/plan.md` หัวข้อ 2) · เสร็จ 2026-10-03 — merge เข้า main, CI เขียวครบ 6 job, เทสต์ 707 ข้อ (หลังบ้าน) + 9 (หน้าบ้าน) + 3 (e2e) · session เก็บฝั่งเซิร์ฟเวอร์ เพิกถอนได้ทันที · บทบาทฐานข้อมูลที่หก `tiewtrade_auth` เป็นที่เดียวที่แตะข้อมูลเข้าสู่ระบบและออก session ได้ · **ค้าง NC-14 ต้องปิดก่อน F-24** และ **ต้องมีงานเก็บกวาดแถวตัวนับอัตราการเรียกก่อนปล่อยผู้ใช้จริง** |
| F-06 | TOTP (2FA) | **Completed** | เสร็จ 2026-10-04 — merge เข้า main (PR #4), CI เขียวครบ 6 job (run 37188326075), เทสต์ 927 ข้อ (หลังบ้าน) + 14 (หน้าบ้าน) + 5 (e2e) · **ตรวจด้วยมือครบ** — Google Authenticator และ Bitwarden ทั้งสแกน QR และกรอก secret ด้วยมือ · **พบและแก้ข้อบกพร่องของ F-05 ระหว่างทาง** (ตัวนับอัตราการเรียกถูกย้อนทิ้ง ทำให้การคุมอัตราหน้า login ไม่ทำงานเลย) · **รีวิวจับได้สามช่องและการตรวจคำรับรองจับได้อีกสอง** ทั้งหมดแก้แล้วพร้อมเทสต์ที่แดงก่อนแก้ — ดู `specs/reviews/2026-10-04-totp-validation-audit.md` · **ค้าง NC-14 ต้องปิดก่อน F-24** · T-03 ฝั่งเครื่องจริงและตัวตั้งเวลาของงานเก็บกวาดเป็นงาน F-31 · **F-24 ต้องแทนที่ `live_trading_enabled()` ด้วยของจริง** |
| F-07 | จัดการ API key ของผู้ใช้ | **Completed** | หลังบ้าน/หน้าจัดการ/validation ผ่านครบ (2026-10-07) · ทดสอบ key จริงผ่าน UI, เจ้าของยืนยันผลและถอน key ทดสอบแล้ว · ทุกด่านผ่านและ cleanup เสร็จ · NC-18/NC-19 ปิดแล้ว · push และ merge เข้า main แล้ว (PR #5, merge 2de95a2); CI รอบ push/PR ผ่านครบ 6 job · เข้ารหัส, ตรวจการใช้งาน key, แสดง 4 หลักท้าย · **T-03 คลายลงแล้วแต่ยังไม่ปิด** — F-06 วาง `infra/crypto` (สัญญา `KeySource`, การปิดผนึก, `key_version`) ไว้ให้ใช้ซ้ำ **แต่ต้องมีกุญแจของตัวเองและถอดได้เฉพาะใน `engine`** (RQ-14 ของ F-06) ส่วนที่มาของกุญแจบนเครื่องจริงยังเป็นงาน F-31 · ใช้ `reverify=True` ของ F-06 ตอนเพิ่มหรือเปลี่ยน key |
| F-08 | บัญชีเทรดเดียวต่อผู้ใช้; เทรดมือหรือบอททีละแบบ | **Completed** | ส่วนเพิ่ม TailAdmin ทุกหน้า Approved/implemented: frontend113/13suites, E2E8(26.3s), lint/types/build/reviewsผ่าน; ภาพ23ไฟล์และpreview5182อัปเดตแล้ว; ผลส่วนบัญชีเดิมเป็น baseline: 2026-10-07: cap1/RLS/server preference/freshTOTP/atomic audit และ TailAdmin/sharedcache; ถอดหลายกระเป๋าแล้ว · backend1480 (ไม่เปลี่ยนหลังfullrun)/frontend107/E2E8/static/DockerLinux/proxy/generated checks และ independent reviewsผ่าน · original issues1–6 และ re-review V13/logout/V14/key noticesปิดครบ · ยังไม่ส่งออเดอร์/รันบอท/แสดงยอด/เปิดLive · เจ้าของทดสอบ UI แล้วและสั่งรวมงานผ่าน [PR #6](https://github.com/yukasung/tiewtrade/pull/6); สถานะ CI/merge อ้างอิง PR · ผลตรวจ `specs/reviews/2026-10-07-f08-single-account-validation-audit.md` |

**ก่อนใช้บัญชีเทรดจริง:** งาน orders/bots/Live ต้องพิสูจน์ single writer,
กฎเปลี่ยนวิธีเทรด/credential, balance/position/order synchronization และความเสี่ยง
ของ key ตาม NC-16; ไม่เปิด Live จากการเลือกประเภทหรือจาก key ที่ตรวจผ่านเพียงอย่างเดียว
การพิสูจน์ UID เพื่อแยกหลายกระเป๋ายกเลิกจากขอบเขตแล้ว

## ชุดที่ 3 — ข้อมูลตลาด

**F-11 เลื่อน full validation — Approved 2026-10-24:** เจ้าของอนุมัติให้พัฒนาต่อ
และเลื่อน C5, C4/C6 ส่วนที่พึ่ง full workload รวมการตรวจครบ 8 timeframe ไปชุดที่ 9
หลังพัฒนาชุดที่ 8 เสร็จ ไม่ลดเหลือ timeframe เดียว. คง BTC-only checkpoint scope
และ ETH Pending ตาม amendment. ต่อมาเพิ่มโหมด smoke BTC8timeframe ตามอนุมัติ;
เจ้าของสั่งหยุด steady (exit130, progress ล่าสุด180s; ไม่ใช่ Passed), dirty ยังไม่รัน.
อนุมัติเลื่อน timed smoke ไปตรวจรับรวม ไม่รันซ้ำท้ายทุกงาน ตาม testing หัวข้อ7;
หลักฐานและข้อจำกัดอยู่ใน F-11 validation/README checkpoint เดิม.
ผล Failed/Partial และ Pending Full Validation คงอยู่; ต้องผ่าน review/candidate gates
ที่ไม่เลื่อนก่อน merge และตรวจรับครบก่อนใช้เงินจริงหรือเปิดให้คนนอก.
F-11 ยังคง Development Complete; ไม่ใช่ Completed หรืออนุมัติ production PREPARED.

**F-11 BTC-only checkpoint amendment — Approved 2026-10-24:** เจ้าของยืนยันให้
checkpoint ปัจจุบันตรวจ workload/readiness เฉพาะ BTCUSDT 8 timeframe ตาม
[validation amendment](features/2026-10-10-backend-indicators/validation.md).
ETH คง Pending Full Validation; ไม่เปลี่ยน production/F-38 ไม่ลดเวลา/threshold
และไม่ปิด Completed หรือ production PREPARED. เพิ่ม BTC-only scope เฉพาะโหมด smoke แล้ว;
default full harness ยังใช้ runtime catalog เดิม การปรับ full scope ยัง Pending;
C5 ยังไม่ได้เริ่ม ผล C1/C2/C3 เดิมคงไว้ตาม scope ที่วัดจริง.

**F-11 checkpoint ล่าสุด 2026-10-24:** C1 resumed audit และ R2-7 exact cold/warm ผ่าน;
แก้ publication timeout ด้วย migration0039 ตาม amendment ที่อนุมัติแล้ว.
Regression149testsและ exact workerผ่าน; C2 บน0039 **Passed** ครบ3,600.000502s,
readiness16/16ตลอด360samples, API correctness480/480, worker127attemptsทั้งหมดREADY.
ผล Failedก่อนแก้ที่1,270.13sยังเก็บไว้ ไม่ทับประวัติ.
C3 บน0039 **Passed** ครบ3,600.002226s: readinessฟื้น16/16ใน70.07s,
correct200ครบทุกseriesภายใน120.31sและไม่เกิดgapหลังrecovery;
availabilityขั้นต่ำhead98.06%/API96.67%, worker128attemptsทั้งหมดREADY.
ยังเหลือ C5/C4/C6 ส่วน full workload ซึ่งเลื่อนไปชุดที่ 9 ตามอนุมัติข้างต้น;
candidate gates ที่ไม่เลื่อนและ required CI ยังต้องผ่านก่อน merge;
ยังไม่ Completed และยังไม่รับรอง production PREPARED.
ดู [หลักฐานและงานค้าง](features/2026-10-10-backend-indicators/profiling/release-20261024/README.md).

| รหัส | งาน | สถานะ | หมายเหตุ |
|---|---|---|---|
| F-09 | ดึงและเก็บแท่งเทียนผ่านชั้น venue | **Completed** | issue1–5แก้แล้ว; backend1,652/frontend113/E2E9/lint/type/architecture/build/generatedcontract และDocker/CLI--once1,000rowsผ่านหลังแก้; final deep reviewAPPROVED; [audit](reviews/2026-10-07-f09-market-data-validation-audit.md); RESTยังUNCONFIRMED; เจ้าของอนุมัติส่งงานผ่าน [PR #7](https://github.com/yukasung/tiewtrade/pull/7) โดยตรวจ CI ก่อน merge |
| F-10 | รับราคาเรียลไทม์ + ต่อกลับเมื่อหลุด | **Completed** | 2026-10-08 · review fixesครบ; deepreview APPROVED; NC-24..29ปิด · latest local backend1870ผ่าน/2live deselected, frontend158, Playwright10; PG/Redis integration805ผ่าน · Ruff/format/mypy/7imports/lock/OpenAPI/buildผ่าน · remoteCIครบ6jobsผ่าน ([run37743108753](https://github.com/yukasung/tiewtrade/actions/runs/37743108753)); เจ้าของอนุมัติปิดงานและmergeแล้ว · ผลใน `features/2026-10-07-realtime-prices/validation.md` และ `reviews/2026-10-07-f10-realtime-prices/final-validation.md` |
| F-11 | คำนวณ indicator ที่ backend | **Development Complete** | 2026-10-12 — implementation/A–D/NC-38 และ refactor ผ่านรีวิว; ด่านที่ไม่เลื่อนผ่านครบตาม [validation](features/2026-10-10-backend-indicators/validation.md). [PR #9](https://github.com/yukasung/tiewtrade/pull/9) merge เข้า main (`279c03f`), [CI ก่อน merge](https://github.com/yukasung/tiewtrade/actions/runs/38210601366) ผ่านครบ 6 jobs ที่ `e84b0e8`; refactor regression149ผ่าน. รอตรวจรับชุด9: C2 rerun ผ่านเต็ม 60 นาทีและ R2-7 exact 525,600-slot ผ่านแล้ว; C3/C5, C4 ส่วนรอบเต็ม, C6 และ release checks ที่เหลือยังไม่ผ่าน — [หลักฐานล่าสุด](features/2026-10-10-backend-indicators/validation.md). ยังไม่ใช่ Completed และไม่รับรอง production PREPARED |
| F-12 | กราฟแท่งเทียนบนหน้าเว็บ | **Completed** | [PR #11](https://github.com/yukasung/tiewtrade/pull/11) merge เข้า `main` (`880e9d2`) แล้ว; required CI [run 38563250593](https://github.com/yukasung/tiewtrade/actions/runs/38563250593) ผ่านครบ. [ตรวจรับ 2026-10-14](features/2026-10-12-candlestick-chart/evidence/2026-10-14-acceptance-progress.md): browser 8 TF ผ่าน; deep history 40/40 contiguous และ API traversal ถึงขอบผ่านหลัง backfill อีก 15 series; C2 rerun ผ่าน. [ติดตาม live preview/browser 2026-10-22](features/2026-10-12-candlestick-chart/evidence/2026-10-22-live-preview-recovery.md): แก้ development Compose config drift ด้วย override เดิมแล้ว 16/16 series สด; warning price/candle หนึ่งครั้งตรงกับ macOS Deep Idle และกู้ connected/bootstrapped/lease สดเองโดยไม่เกิดซ้ำหลัง recovery; browser session จริงผ่าน pan→หน้าเก่า, Retry-After/manual retry และ resetแบบไม่ยิง API จึงปิด V-H8/history-window V-H1..8; owner manual ผ่าน 2026-10-22. [V-17 deterministic full rerun 2026-10-23](features/2026-10-12-candlestick-chart/evidence/2026-10-23-v17-full-rerun.md) ผ่าน LEGACY/PREPARED 600s ตาม threshold เดิม; [PR #24](https://github.com/yukasung/tiewtrade/pull/24) merge เข้า main เป็น `27a7718` แล้ว โดย CI ของ candidate ผ่าน 6/6; [post-merge CI 39934274551](https://github.com/yukasung/tiewtrade/actions/runs/39934274551) ผ่านครบ 6/6 แล้ว และ acceptance audit ปิด mapping/coverage gaps ครบ 15/15 เกณฑ์แล้ว รวม V-02 parser matrix, V-04 chart verify 21 fault cases และ V-09 direct candle-feed reconnect/backoff; backend targeted 220 tests, frontend 63 tests และ lint/types ผ่าน. Tests และ navigation remediation merge ใน PR #25 (`51f0e27`) แล้ว; final head `b79736c` ผ่าน push/PR CI และ post-merge run 39972554569 attempt 3 ผ่าน 6/6. ปิด U-02/I-02/S-03/C-02/C-03 ด้วยหลักฐานเดิมแล้ว; TF-18 ผ่านตามคำอนุมัติ NC-F12-TF18 วันที่ 2026-10-24 ให้ใช้ real backfill ร่วมกับ V-17 โดยไม่เพิ่ม SLA; ดู PR #25 checkpoint ในหลักฐานข้างต้น. รวมแท่งสดตาม NC-39; เลื่อนจุดเข้า/ออกจริงตาม NC-40 จนมีข้อมูลออเดอร์และ spec การเชื่อมกราฟ (R-14). Completed เฉพาะขอบเขต F-12; ไม่รับรอง F-11 release gates/production PREPARED/Live |
| F-37 | **รายการเหรียญที่รองรับและการจัดการ** | **Development Complete — Catalog/Order Safety Ready** | 2026-10-25: เจ้าของสั่ง merge [PR #29](https://github.com/yukasung/tiewtrade/pull/29) เข้า main เป็น `033671f`; corrections 2 High/2 Medium ปิดแล้วและ candidate `cf2efd9` ผ่าน [PR CI](https://github.com/yukasung/tiewtrade/actions/runs/40159910410) / [push CI](https://github.com/yukasung/tiewtrade/actions/runs/40159907464) ครบ 12/12 checks: backend 3258, frontend 265, Chromium 18+2 tests; post-merge CI [40160909137](https://github.com/yukasung/tiewtrade/actions/runs/40160909137). Milestone ปลด dependency ด้าน catalog/order safety ของ F-16 ตาม amendment 2026-10-25; V-10 เฉพาะ Paper/catalog ผ่าน ส่วน Live รอ F-22/F-23, V-18 รอ F-20/F-26 และ V-19 รอ approved release profile/full validation; ยังไม่ Completed. หลักฐาน [M1](features/2026-10-24-supported-symbol-management/evidence/m1-schema-role-core.md), [M5](features/2026-10-24-supported-symbol-management/evidence/m5-local-candidate.md), [review](reviews/2026-10-24-f37-supported-symbol-management/final-review.md). Runtime ปัจจุบัน 2 คู่ตาม F-38; ถอนไม่แตะ position เดิมและไม่เปิด Live |
| F-38 | ลดคู่เทรดช่วงพัฒนาเหลือ BTC/USDT และ ETH/USDT | **Completed** | 2026-10-27: final candidate `aabdfb9` ผ่าน current-image/schema 0042 capacity C1–C6 และ S1–S5, local review/crosswalk และ required [PR CI 40431978440](https://github.com/yukasung/tiewtrade/actions/runs/40431978440)/[push CI 40431967222](https://github.com/yukasung/tiewtrade/actions/runs/40431967222) ครบ 12/12 jobs (backend 3,462 passed); [PR #38](https://github.com/yukasung/tiewtrade/pull/38) merge เป็น `bf7b847` แล้ว. Reuse approved pre-0030 restore RPO=0/RTO 2.247043s ตาม [current crosswalk](features/2026-10-15-supported-pairs-reduction/evidence/release-20261026-merge/README.md); เก็บผลเดิมของ `bfb6ab0` เป็นประวัติ. Completed เฉพาะ F-38; ไม่เปิด production PREPARED/Live หรือเปลี่ยน F-11/F-15/ETH workload |

## ชุดที่ 4 — Paper Trading

**แนวทางร่วม Approved 2026-10-15:** งาน Paper/Live ที่เกี่ยวข้องต้องยึด
[ADR-004 — ใช้โค้ดการเทรดร่วมกัน](decisions/004-shared-paper-live-trading.md)
และนำเกณฑ์ parity/isolation ไปใส่ใน spec ของแต่ละ feature ก่อนขออนุมัติ implementation
ไม่เปลี่ยนสถานะการอนุมัติเอกสารหรือเงื่อนไข reset ของ F-13

| รหัส | งาน | สถานะ | หมายเหตุ |
|---|---|---|---|
| F-13 | กระเป๋า Paper และเงินตั้งต้น | **Development Complete** | requirements/plan/validation อนุมัติ 2026-10-15; create/read และ reset fail-closed merge ใน [PR #14](https://github.com/yukasung/tiewtrade/pull/14) (`2243675`) พร้อม required CI. F-15 ปิด authoritative reset success, controlled reset/admission/fill/GET races, source conflict/error, cancellation/timeout, lost acknowledgement, TCP disconnect และ process-kill ก่อน/หลัง RESET commit; [validation F-13](features/2026-10-15-paper-wallet/validation.md) V-1–V-15 ผ่านครบจาก final F-15 candidate, CI run #124 attempt 2 และ post-merge run #125. รอตรวจรับระบบตามสถานะ Development Complete จึงยังไม่ใช่ Completed |
| F-14 | การคิด position, margin, PnL | **Development Complete** | Requirements/plan/validation approved 2026-10-16; M1-M3 and F-15 position/order/reset integration validated. Closed-episode writer replay merged in [PR #32](https://github.com/yukasung/tiewtrade/pull/32) (`eb8c7d8`); financial caller replay merged in [PR #34](https://github.com/yukasung/tiewtrade/pull/34) (`80d5d04`). Final push/PR CI and [post-merge CI](https://github.com/yukasung/tiewtrade/actions/runs/40176371957) passed 6/6 jobs; backend 3270 passed with no retry. Local Failed/Partial evidence remains in [validation](features/2026-10-16-position-margin-pnl/validation.md#post-merge-closeout---2026-10-25). V-17 release workload remains **Pending Full Validation**; not Completed. |
| F-15 | จำลองการจับคู่ออเดอร์ Paper | **Development Complete** | requirements/NC-F15-01..10 และ plan/validation อนุมัติแล้ว; [M1](features/2026-10-18-paper-order-matching/evidence/m1-core.md)–[M5](features/2026-10-18-paper-order-matching/evidence/m5-candidate.md) ปิด implementation และ Critical/High findings. Candidate ล่าสุดเพิ่ม migration 0038, batch persistence, publisher supervision และ atomic per-owner claim; affected safety 125 tests, follow-up 12 tests, nominal smoke 500 commands/100 owners และ recovery smoke ผ่านโดยไม่มี duplicate fill หรือ balance/position inconsistency. V-1..V-18 และ required CI run #124 attempt 2 ผ่าน; post-merge CI run #125 ผ่านครบ 6 jobs. W1–W3 และ W4 บน final schema คง `Pending Full Validation` ตามคำสั่งเลื่อนไป release checkpoint จึงยังไม่ใช่ Completed. Production order admission/public order route ยังไม่เปิด และ actual unsupported filters ยังคง reject; 2026-10-25 deep-review remediation ใน branch `fix/f15-review-findings` แก้ rebase cursor, execution constraints และ expiry history โดย local full backend candidate ผ่าน 3267 tests และ runtime candidate CI ผ่านครบ 6 jobs ทั้ง push/PR (PR backend 3270 tests); sync main และติดตาม latest-head CI ใน [PR #33](https://github.com/yukasung/tiewtrade/pull/33) ตาม [M5 checkpoint](features/2026-10-18-paper-order-matching/evidence/m5-candidate.md#deep-review-remediation--2026-10-25) ; 2026-11-06 Set4 candidate98ff2f8: existing-profileW1Failed60scycle at pool checkout after100x20baseline; W4Passed0064; W2/W3NotRun pending diagnosis; V19Failed/Partial/PendingFullValidation ; Set4 follow-up: diag3 captured failed cycle; NC-SET4-02 Approved A, standalone R8 opt-in implemented/tested with defaults preserved; targeted safety/config/static passed; one full W1 baseline2000/2021cycles thenFailed publisher WriterLeaseLost (1378.654s total), observed p95 0.571253s >0.250s; W2/W3NotRun/W4Passed0064; NC-SET4-03 heartbeat/metadata safety89+8/static passed; first diagnostic Incomplete preserved; NC-SET4-04 latest A replacement completed3000commands/600cycles/all100financial oracles, Failed p95 469.526ms >250ms and input_lag22 >20; no observer/lease errors, cleanup complete; NC-SET4-05 checkpoint SQL batch/final-tail proposal prepared, awaiting A/B approval before implementation; no production change/full W1 retry |
| F-16 | สั่งออเดอร์เองผ่านหน้าจอ | **Development Complete — Pending Integration/Full Validation** | requirements/plan/validation Approved 2026-10-25; M1–M4 implementation/review และ local safety/validation ผ่านตาม [M4 evidence](features/2026-10-25-manual-order-entry/evidence/m4-candidate-review.md). เจ้าของสั่ง merge [PR #36](https://github.com/yukasung/tiewtrade/pull/36) เข้า main เป็น `1f16ddb`; final candidate `ab248fe` ผ่าน push/PR CI12/12 และ [post-merge CI](https://github.com/yukasung/tiewtrade/actions/runs/40208544618) ผ่าน6/6. V-19 ผ่าน; V-18 รอ F-18 risk integration และ V-20 Pending Full Validation ที่ release checkpoint/ชุดที่9 จึงยังไม่ Completed. Production NEW admission ยัง fail-closed และ Live execution ไม่เปิด; เก็บ failed attempts และความเสี่ยงย้อนหลังใน M4 |
| F-17 | TP/SL แบบผูกกับออเดอร์เข้า และแบบตั้งทีหลัง | **Review Findings Refactored — Final CI & Release Pending** | (R-09) [requirements](features/2026-11-02-tp-sl/requirements.md) และ NC-F17-01..05 Approved 2026-11-04; [plan](features/2026-11-02-tp-sl/plan.md)/[validation](features/2026-11-02-tp-sl/validation.md) Approved 2026-11-04; NC-F17-06 Approved 2026-11-04; NC-F17-07 Approved แบบ A; domain/DB/API/worker/UI ผ่าน deep review และแก้ runtime findings R1–R4 พร้อม regression tests; migration0064 เพิ่ม durable replacement retry; local backend90 และ targeted financial/race/correction/UI ผ่านตาม [evidence](features/2026-11-02-tp-sl/evidence/feature-candidate.md); R5 Feature validation เพิ่มหลักฐานครบ V-01–16 local targeted; final candidate/review gate/required CI ค้าง; เจ้าของอนุมัติ refactor แล้ว: backend74/frontend27/browser2 ผ่านหลัง refactor; Feature validation ต่อแล้ว: V-05/08/09/11/16 ผ่าน local targeted พร้อมหลักฐานเงินจริง/serve SLA/upgrade; เจ้าของเลือก A 2026-11-05: แก้ late-fill fixture ตาม due/single-owner claim; V-06/10 ผ่าน local targeted พร้อม protection regression39 tests; wrong-scope DB/HTTP passed; migration rollback amendment Approved 2026-11-05: empty roundtrip และ refusal16กรณี passed พร้อม financial/history/RLS preservation; full backend mypy642 files passed; UI/API/lifecycle matrices local passed: core59/API8/DB3/component27/browser6; Thai/English keyboard แบบ A approved และ passed; V-01–16 local passed, final review High CI composition finding fixed: default excludes F-17, dedicated npm/CI step6 tests passed58.2s; PR#46 first candidate6998c22: backend CI24failed/4263passed; test integration repairs targeted74+7passed แต่385bce8 CIยัง20failed/4267passed; แก้ seed helperให้owner-local พร้อม expanded111/SLA2/rollback16passed; 888cdff CIยัง20failed/4268passed; เจ้าของเลือก A หลัง3รอบให้เพิ่ม read-only CI diagnostic (fresh31passed); diagnostic2407df2 CI20failed/4270passedทั้งpush/PR พบforeign-owner candidate20/20ในทุกsnapshot; เจ้าของเลือก A ให้แยก F-17 integration ใช้ฐานว่างในCI คงtests/assertions/runtimeเดิม; collection4290ครบและisolated48passed; V-17 required CI บนcandidateใหม่pending; Batch/Release ยัง Not Run — Pending Full Validation ; 2026-11-06 checkpoint: merged98ff2f8/post-mergeCI42063166018 all6jobs passed, V17Passed; Set4F15W1Failed/W4Passed0064/W2-W3NotRun; integrated-profile NC-SET4-01 pending; see F17 Batch evidence ; Set4 latest: standalone R8 opt-in Approved/tested, one W1 reached2021cycles thenFailed publisher WriterLeaseLost; observed p95 571ms >250ms; W2/W3NotRun/W4Passed0064; V18Partial/Failed; NC-SET4-01 integrated profile open, NC-SET4-02 closed; no production change or rerun ; NC12 internal20 local W1/W2/overflow/shortW3/integratedW4 now Passed under amendments through§23; [aggregate receipt](features/2026-11-02-tp-sl/evidence/recovery-20261106/internal-pilot-local-checkpoint-20261107.md); latest recovery candidate review/requiredCI and opening/Release gates remain pending. |

## ชุดที่ 5 — ความเสี่ยงและความปลอดภัย

| รหัส | งาน | สถานะ | หมายเหตุ |
|---|---|---|---|
| F-18 | เพดานความเสี่ยงต่อกระเป๋า | **Development Complete — Paper Validation, Required CI & Manual Check Passed / Pending Dependencies** | Requirements/NC-F18-01..08 Approved 2026-10-25; เจ้าของอนุมัติ [plan](features/2026-10-25-wallet-risk-limits/plan.md)/[validation](features/2026-10-25-wallet-risk-limits/validation.md) ฉบับแก้ F18-R1..R4 วันที่ 2026-10-26 และสั่งทำครบ full regression/final review/workload ทีละชุด; M1 ผ่าน targeted 76 tests; M2 persistence/API checkpoint ผ่าน DB11/API9/worker5/audit74 tests ตาม [evidence](features/2026-10-25-wallet-risk-limits/evidence/m2-persistence-api.md), M3/M4 implementation และ targeted/browser composition มีหลักฐานแล้ว; [M5 checkpoint](features/2026-10-25-wallet-risk-limits/evidence/m5-final-candidate.md) กลับมาทำต่อหลัง F-38 Completed 2026-10-27: full backend regression3607tests passed; post-R5 projection244tests/monitor36tests/risk95tests และ harness19tests ผ่าน; W4 r7ผ่านหลังR5บนschema0055; W1 r9ผ่าน2,000baseline/partial-fill oracle แต่ Failed/Partial ที่measured reseed cycle60s; R6อนุมัติและsafety13tests/affected regression262testsผ่าน reseed20ผ่าน58.18sหลังbulk evidence W1 r10หยุดระหว่างsetupเพื่อแก้ส่งpayloadซ้ำ; affected rechecks100tests/W4r8ผ่าน; source-continuous full cycleยังfailed60s; R7อนุมัติ/round1 composition24testsผ่าน; full cycleจบก่อน60sและpostconditionrecheckผ่าน; W1 r11 Failed/Partial ที่baseline10/20; ลดSQLซ้ำในmonitorโดยคงprotocol/budgetsเดิม safety116+1และW4r9ผ่าน baseline100-owner batchและper-request postconditionsผ่าน (เก็บhelper failureเดิม); W1 r12ผ่านbaseline2,000/partial-fill แต่Failed60sที่reseed (445completed/70cycles); probe10sพบPaper578/956skipped; [R8](features/2026-10-25-wallet-risk-limits/claim-budget-amendment.md)อนุมัติและimplemented; selector26/safety221testsผ่าน; probePaper427/427roundsมีงานprocessed; W1r13Failed60sที่reseed (466completed/77cycles) บนfresh0055/currentR8; deep-reviewแก้ API provenance/active-order stop lookup/measured latency window ผ่านaffected199tests/mypy560; W1r14Failed60sที่reseed (467completed/78cycles); คืนresultpoll250ms/งดสร้างIDsในno-fillโดยคงfullfallbackและUUIDเดิม matching104tests/mypy561ผ่าน; frozen cycle53.863sผ่านแต่ไม่ใช่acceptance; finalW1r15Failed60sที่reseed (491completed/84cycles); Highยังเปิด และ R9 same-pair selector อนุมัติ2026-10-28และimplemented/schema0056; affected225/enabled49tests/mypy563/import7ผ่าน; frozen progress52.300sผ่านแต่W1r17Failed60sที่reseed(495completed/87cycles); ปิดoptionกลับR8ตามอนุมัติ/disabled29testsและW4final0056ผ่าน; finalbackendcoverage3675testsผ่านแบบresume(1192+2502−19)/mypy563/staticผ่าน; HighยังเปิดและoptionR9ปิด; R10อนุมัติ/implemented safety253/enabled26/mypy564/staticผ่าน frozen43.46sผ่านdiagnosticเท่านั้น W1r18Failed/Partial172.5sแต่ครบ3risk scenarios/1626completed312cycles; ค้างlatercycle60sหลังLIMITSELLรอ~39.86s/claimrev5สาเหตุเฉพาะใบยังไม่ยืนยัน; sourcefreshness diagnosticfailedbaseline; ปิดR10กลับR8/disabled26/mypy564/import7/staticผ่าน โดยเก็บทุก attempt; เจ้าของอนุมัติ runtime profileV2 10/5/30นาที วันที่2026-10-27 โดยคงโหลด/เกณฑ์ safety/SLA; V2 W1/W2/W3/final acceptance ยังค้าง. R11 อนุมัติ/implemented0057; affected116testsผ่านและ controlled SELL ลดจาก36.55sเป็น7.28s (รอหลังsourceฟื้น0.13s; ไม่ใช่SLAacceptance). W1r19 Failedช่วงseedbaselineด้วยWriterLeaseLostหลังPaperworkersเริ่มแล้ว/ก่อนวัดผล; R11/R10ปิดกลับR8, final0057backendcoverage3729ผ่านแบบresume/restoreและstaticผ่าน; รายละเอียดและผลล้มทั้งหมดใน[M5](features/2026-10-25-wallet-risk-limits/evidence/m5-final-candidate.md). Production NEW admission ยังปิดจนผ่าน activation gates; bot/Live/notification dependencies ยังไม่ถือว่าผ่าน; R25 อนุมัติ2026-10-29: Paper99.9%<=3sต่อowner/ทุกinput<=5s และconnectionbudget/cleanup; harness41testsผ่าน แต่nativeW1Failed60sที่reseed/APIpoolหลังbaseline2000(370completed/46cycles); รายละเอียดM5, ยังPending Full Validation และไม่เริ่มW2/W3; R26 approved/implemented: normal60s+one recovery120s/outer180s, targeted56ผ่าน; W1Failed60.053sที่RESETท้ายcycleปกติ(295completed), recoveryพิเศษถูกcancelที่45.830s; ยังPending Full ValidationตามM5; R34 final candidate ผ่าน W1–W4, local regression/static/final review และ Paper validation ตาม [M5](features/2026-10-25-wallet-risk-limits/evidence/m5-final-candidate.md); required remote CI run `41173114518` ผ่าน6/6; owner create-wallet/save-limit และ browser manual order-submit observations ผ่าน; V-22/V-23 ยัง Pending จึงยังไม่ Completed |
| F-19 | ปุ่มหยุดบอท (Kill Switch) | **Development Complete — Pending System Ready & Dependencies** | Implementation, owner-approved review fixes และ refactor บน `feature/f-19-kill-switch` เสร็จแล้ว; V-01..18 ผ่าน local ตาม [evidence](features/2026-10-31-kill-switch/evidence/implementation-checkpoint.md) รวม browser/manual QA, concurrency และ fault/recovery matrices. แยกปุ่ม Paper/Live ไม่มีปุ่มหยุดทั้งหมดของผู้ใช้. NC-F19-13 ทำ scheduled partial0.5/stop/cancel/release/restore/resume ถูกต้อง แต่ W1 Failed ที่ +159.73s เพราะ global partial window ทำ core MARKET BUY partial0.833/EXPIRED; ไม่มี duplicate execution/negative reservationและหยุดก่อน W2/W3. ตามคำสั่งเจ้าของ 2026-11-01 เลื่อน NC-F19-14 และ timed W1–W3 ไปรันครั้งเดียวที่ Full Validation ท้ายชุดที่ 5 โดยคงเกณฑ์/load/SLAเดิมและผล Failed ตามจริง. review findings 2 High/1 Medium แก้แล้วและ refactor ผ่าน; V-19 ผ่านบน final candidate `de25852` พร้อม required [push CI](https://github.com/yukasung/tiewtrade/actions/runs/41305111782)/[PR CI](https://github.com/yukasung/tiewtrade/actions/runs/41305117314) ครบ 6/6 jobs ต่อ run. [PR #41](https://github.com/yukasung/tiewtrade/pull/41) merge เข้า main เป็น `ccc3ce1` เมื่อ 2026-11-01 และ [post-merge CI](https://github.com/yukasung/tiewtrade/actions/runs/41306706760) ผ่าน 6/6 รวม backend4056/browser33. ยังไม่ Completed: V-20 คง Pending Full Validation ส่วน real TP/SL, bot, Live, notification V-21..24 คง Pending Dependency; ไม่ได้เปิด production/Live activation  Set-5 NC14/NC15 อนุมัติและ implement แล้ว; targeted harness64/CLI6/fresh-global25/Linux2ผ่าน. W1รอบ Set5แรกบนschema0062 Failedที่+121.09s (core cycle60sหมดระหว่างAPI pool checkout; observed risk/processing latencyสูง) ก่อนone-shot injection; W2/W3/W4ยังNot Run. NC-F19-16อนุมัติแล้ว: targeted76/Linux17/Ruff/mypyผ่าน; diagnosticหนึ่งรอบ Failedที่+172.298sระหว่างรอ scheduled partial fill60s. one-shot1568 commitแล้วแต่ owner REBASE1566→1575ข้าม tradeเก่าก่อนประมวลผล; transaction pool wait0.000659s. ไม่ปิดสาเหตุAPI-poolของรอบก่อนย้อนหลัง. เก็บfailed DB/trace. NC-F19-17อนุมัติและimplementแล้ว: targeted100/real-worker3/Linux16/Ruff/mypyผ่าน. W1ใหม่รันครบ600s, commands6000/cycles1200, one-shot/stop/resume/financial/source/resourceผ่าน แต่ Failed risk SLA (1302/918703เกิน3s, quotaไม่ผ่าน56/100owners,3samplesเกิน5s,max5.034698s). ไม่rerun/W2/W3/W4; วิเคราะห์หลักฐานเดิม 2026-11-02แล้ว: independent SLAตรงทุกlate identity, evidence21filesไม่เปลี่ยน; serverlogsยืนยัน137owner-lock timeoutsแต่ยังไม่ผูกowner/roundเพื่อเลือกproduction fix. NC-F19-18อนุมัติ/implementแล้ว: targeted116/Linux38/staticผ่าน, one300sdiagnostic OBSERVATION_COMPLETE/non-acceptance. ยืนยัน100-ownerpage/4-slotqueueทำให้actualserver3sdelay (semaphore3.161s),ไม่มีhard5sซ้ำและไม่ปิดoldfailure. NC-F19-19 approved/implemented: targeted35, fresh-DB safety26, Linux43 plus explicit fresh-global4, final targeted9/static passed; regression95 passed/1 fixture backlog failure retained and diagnosed. W1 Failed/environment invalid before load: baseline100x20/dedicated LOSS_LIMIT-RESET passed, later BOT resting NEW rejected SOURCE_UNAVAILABLE; all nine role URLs still pointed to preflight DB. No SLA conclusion. Parsed URL/actual DB/fresh-schema guard tested. Owner authorized replacement W1: nc19-w1-r3 verified all nine roles/fresh DB, baseline100x20/dedicated LOSS_LIMIT-RESET/manual-BOT setup passed, then Failed at recorded+37.594s from BOOK child SourceUnavailableError. Wall-time reversal16.857ms observed near failure; exact guard cause unproved. Raw72files/dump/partial safety retained, no W2/W3/W4. NC-F19-20 approved/implemented:94Linux tests/static passed; one verified-fresh60s diagnostic OBSERVATION_COMPLETE/non-acceptance,1203guard calls/0failures, Not Reproduced. No observed receipt clock reversal does not prove a fix; original r3 cause still unproved. Stopped without another workload. Owner-requested read-only clock review completed: host NTP activity confirmed, no matching host adjustment/sleep/wake/VM-restart record at failure; guest setter and exact cause unproved. No settings changed. [Clock review](features/2026-10-31-kill-switch/evidence/clock-environment-review-2026-11-02.md); NC-F19-21 approved/completed:22tests/static passed, one20min/12000exchanges complete/no gaps. Guest offset moves every~30s (24 decreases,max2.994309ms), host no offset decreases;70Unknown retained. Guest-relative timing movement localized, exact setter/original r3 cause unproved. No criteria/settings changes or W1 rerun; NC22 external-machine proposal superseded by owner-approved same-machine measurement audit, now complete:261rawhashes/9sourcefiles matched (3originalsource gaps retained),18offline tests/5controlled cases;NC17counts unchanged. Mediumstream-orderguarddefect reproduced but44realackfilesordered,notcauseofoldfailures. Owner-approved stream-order guard fixed:27non-DBtests/Ruff/format/mypy passed;boundedmetadata/fail-closed,allrowsretained. Reviewed without findings;owner-authorized narrow refactor complete,27tests/staticpassed,behaviorunchanged. NoSLArelaxation/environmentchange/newrun;oldlatency/clocklimitationsremain. [Measurement audit](features/2026-10-31-kill-switch/evidence/measurement-audit-2026-11-02.md). [NC21 evidence](features/2026-10-31-kill-switch/evidence/clock-comparison-2026-11-02.md). [NC20 evidence](features/2026-10-31-kill-switch/evidence/book-clock-diagnostic-2026-11-02.md); [fresh rerun evidence](features/2026-10-31-kill-switch/evidence/w1-fresh-rerun-2026-11-02.md). See [NC19 evidence](features/2026-10-31-kill-switch/evidence/rolling-monitor-2026-11-02.md) |

**F-19 NC-F19-23 update — 2026-11-02:** read-only tracefs capability preflight on
the unchanged Docker VM stopped **Incomplete** after0.565s because the bind lacked
`trace_clock`. No tracing instance, full instrumentation,90s trace, trading/DB/W1 or
setting change occurred. NC19 production/test hashes still match its measured candidate;
the clock setter remains Unknown. V-20 remains Failed/Pending Full Validation and a new
owner-approved amendment is required. See [NC23 evidence](features/2026-10-31-kill-switch/evidence/clock-setter-preflight-2026-11-02.md).

NC-F19-24 now proposes a same-machine, container-namespace-only tracefs mount with
CAP_SYS_ADMIN only, default confinement, bounded conditional90s trace and verified
rollback. Owner approved it on2026-11-02 for implementation, controlled tests and one
conditional execution only; the F-19 status above remains unchanged.

NC24 final checkpoint is **Incomplete**:45 controlled tests/static checks pass, but the
single execution lost its tmpfs result; its cleanup-only helper verified bounded security
then failed before mount on unavailable LSM evidence. No repeat/second helper/settings/
trading/DB/W1 occurred; cleanup and setter remain unverified/Unknown. Further action needs
a new approved amendment. See [NC24 evidence](features/2026-10-31-kill-switch/evidence/clock-setter-nc24-2026-11-02.md).

NC-F19-25 is now proposed as the terminal same-machine ftrace decision: Option A combines
exact residue cleanup and one conditional trace with durable Docker-log evidence; Option B
stops tracing. Owner selected Option B; NC25 stopped before implementation/execution.

Owner approved revised F-19 SLA, plan and validation on2026-11-02: per-owner/run99.5%≤3s,
99.9%≤5s and all inputs≤6s, with safety/correctness unchanged and Paper/Live production
activation together only after complete release gates. Explicit F19 evaluator/regression
implemented locally:40 non-DB tests and Ruff/format/mypy pass; F18 unchanged. Immutable
NC17 offline derivation passes revised Feature criteria (918703 complete samples, zero
clock/order errors, max5.034698s) while original Failed remains untouched. NC23/24 setter
observer source/tests excluded; NC25/further tracing stopped. No workload rerun now; final
integrated candidate gets one validation run when dependencies are complete. See
[revised SLA evidence](features/2026-10-31-kill-switch/evidence/revised-sla-evaluation-2026-11-02.md).

**F-19 Development Complete under the revised Feature gates.** Batch/System Ready remains
Pending Full Validation and dependencies; this status does not authorize Paper or Live
production activation.

## ชุดที่ 6 — บอท

| รหัส | งาน | สถานะ | หมายเหตุ |
|---|---|---|---|
| F-20 | ส่วนต่อประสานกลยุทธ์ + วงจรชีวิตบอท | Planned | |
| F-21 | กลยุทธ์สำเร็จรูปตัวแรก + ระบบปรับพารามิเตอร์ | Planned | (R-06) ยังไม่ได้ระบุว่ากลยุทธ์อะไร |

## ชุดที่ 7 — Live Trading

**NC-07 ปิดแล้ว 2026-09-26** เงื่อนไขที่เหลือของชุดนี้คือ F-18 และ F-19 ต้องเสร็จก่อน

| รหัส | งาน | สถานะ | หมายเหตุ |
|---|---|---|---|
| F-22 | ส่งออเดอร์จริงผ่านชั้น venue + กันสั่งซ้ำ | Planned | ผ่าน F-33 ต้องใช้ได้กับทั้งสองตลาด |
| F-23 | กระทบยอดกับ Binance | Planned | รวมถึงตรวจจับออเดอร์ที่เกิดนอกระบบ |
| F-24 | ขั้นตอนเปิด Live (ยืนยันตัวตน + คำเตือน) | Planned | Live ต้องไม่เปิดเอง · **ต้องปิด NC-14 ก่อนเริ่มงานนี้** (เจ้าของตัดสิน 2026-10-03) — เจ้าของบัญชีต้องกลับเข้ามาลดความเสี่ยงได้แม้ session หมดอายุและบัญชีถูกโจมตีต่อเนื่อง (`trading-safety.md` หัวข้อ 8) |
| F-25 | เริ่มใช้เงินจริงจำนวนน้อย | Planned | **ต้องผ่านชุดที่ 9 ก่อนเริ่มใช้เงินจริง** (เจ้าของอนุมัติ 2026-10-11) · **ไม่ทดสอบบน Testnet** (เจ้าของตัดสิน 2026-09-26) ข้ามจาก Paper ไปเงินจริงโดยตรง ต้องเริ่มด้วยจำนวนน้อยและมีคนเฝ้า — **ต้องมี F-26 (แจ้งเตือนในแอพ) เสร็จก่อน** เพราะกฎความปลอดภัยสั่งให้แจ้งเตือนจริงเมื่อตั้ง TP/SL ไม่สำเร็จ, ยกเลิกออเดอร์ไม่สำเร็จ, บอทหยุดผิดปกติ, มีไม้โผล่หลังกดหยุด และชนเพดานขาดทุน |

## ชุดที่ 8 — รอบระบบ

| รหัส | งาน | สถานะ | หมายเหตุ |
|---|---|---|---|
| F-26 | แจ้งเตือนในแอพ | Planned | **ต้องเสร็จก่อน F-25** (เจ้าของตัดสิน 2026-09-26) ไม่ติด T-05 ทำได้เลย |
| F-36 | แจ้งเตือน Email | Planned | (R-15) ติด **T-05**; พัฒนาในชุดที่ 8 ก่อนตรวจรับชุดที่ 9 และ F-25 (ปรับลำดับ 2026-10-11) |
| F-27 | แจ้งเตือน Telegram + LINE | Planned | ติด **T-05**; พัฒนาในชุดที่ 8 ก่อนตรวจรับชุดที่ 9 และ F-25 (ปรับลำดับ 2026-10-11) |
| F-28 | สรุปผลงานและประวัติการเทรด | Planned | |
| F-29 | ระบบผู้ดูแลแพลตฟอร์ม | Planned | ติด **NC-02** |
| F-30 | สลับภาษาไทย/อังกฤษ | Planned | (R-20) ต้องวางตั้งแต่ F-12 |
| F-31 | นำขึ้น VPS จริง | Planned | **ต้องมีตัวสร้างพาร์ทิชันของ audit log เป็นระยะก่อนขึ้นเครื่องจริง** — F-04 สร้างไว้ล่วงหน้า 12 เดือน เดือนที่เลยไปจะตกพาร์ทิชันปลายทางและสร้างพาร์ทิชันย้อนหลังไม่ได้อีก (F-04 plan ข้อ 3) · (R-16) **ต้องทำก่อน deploy:** `frontend/Dockerfile` ของ F-01 รัน `npm run dev` และ CI ยังไม่เคยรัน `npm run build` เลย จึงยังไม่มีใครรู้ว่า production bundle สร้างและเสิร์ฟได้ — ต้องเพิ่มขั้น build ใน CI แยก Compose ชุดพัฒนากับชุด deploy (รีวิว 2026-09-27 ข้อ 2) |
| F-32 | เอกสารทางกฎหมาย | Planned | ติด **NC-11** |

---

## ชุดที่ 9 — ตรวจรับระบบก่อนใช้งานจริง

**ลำดับและขอบเขต Approved — เจ้าของยืนยัน 2026-10-11** · สถานะ: **Planned**
เริ่มหลังพัฒนาชุดที่ 8 เสร็จ รวมการทดสอบละเอียดที่เลื่อนจาก F-11;
ไม่แทนการทดสอบความถูกต้อง ความปลอดภัย และ regression ระหว่างพัฒนาแต่ละ feature

| งานตรวจรับ | สถานะ | ขอบเขต |
|---|---|---|
| การทำงานร่วมกันและ flow ผู้ใช้ | Planned | ตรวจระบบทั้งชุดตั้งแต่หน้าจอ API ฐานข้อมูล และงานเบื้องหลังตาม spec ของแต่ละ feature |
| ความถูกต้องทางการเงินและออเดอร์ | Planned | เงิน ปริมาณ ออเดอร์ซ้ำ balance, position, PnL, leverage/margin และ liquidation ตามข้อกำหนดที่อนุมัติ |
| โหลดและความเสถียรระยะยาว | Planned | รวม capacity ของ F-11 ที่ค้าง: R2-C2/C3/C5 รอบเต็ม, C4/C6 และ R2-7 พร้อมติดตาม API lag และผล Failed/Partial เดิมตาม validation |
| ความล้มเหลวและการกู้คืน | Planned | exchange API failures, retry/idempotency, WebSocket หลุด, order synchronization และการกู้คืนตามแผนที่อนุมัติ |
| สำรองและกู้คืนฐานข้อมูล | Planned | ทดลอง backup และ restore จริงในสภาพแวดล้อมแยก ตรวจ schema/migrations, ความครบถ้วนและความสัมพันธ์ของข้อมูล, balance/position/order/audit ตาม spec; บันทึกเวลาและข้อมูลที่กู้คืนได้ โดยกำหนดเกณฑ์ RPO/RTO ในแผนตรวจรับเพื่อขออนุมัติก่อนรัน ไม่แตะฐานจริงหรือส่งออเดอร์ |
| ความปลอดภัยและความพร้อมใช้งานจริง | Planned | ตรวจสิทธิ์ การแยกผู้ใช้ secrets และ deployment/rollback ตามข้อกำหนด พร้อมรวบรวมหลักฐานและรีวิวปิดงาน |

ก่อนเริ่มให้จัดทำแผนและ validation ของรอบตรวจรับรวมเพื่อขออนุมัติ โดยอ้างอิงเกณฑ์
ของแต่ละ feature ไม่ลดเกณฑ์เดิมโดยอัตโนมัติ และตกลงเวลารันทดสอบยาวกับเจ้าของ
การตรวจรับก่อน F-25 ใช้ Paper/สภาพแวดล้อมทดสอบที่ได้รับอนุมัติ ไม่ส่งออเดอร์เงินจริง
และไม่เพิ่ม Testnet เป็นข้อกำหนด; การตรวจที่ต้องใช้เงินจริงอยู่ใน F-25 หลังผ่านชุดนี้

**ต้องผ่านชุดที่ 9 ก่อนเริ่ม F-25 ใช้เงินจริงหรือเปิดให้คนนอก** และต้องผ่านเงื่อนไขอื่น
ของจุดปล่อยด้วย ผลการตรวจรับเป็นหลักฐานสำหรับปิด validation ที่ค้างและเปลี่ยน
Development Complete เป็น Completed เมื่อเกณฑ์ของ feature นั้นครบ

---
### ทะเบียนงานค้างสำหรับชุดที่ 9

ทะเบียนนี้ติดตามด่านตรวจรับที่เลื่อน ไม่เปลี่ยนผลหลักฐานเดิมหรือสถานะ feature
เมื่อมีรายการใหม่ให้ระบุ feature/เกณฑ์/หลักฐานและการอนุมัติเลื่อนก่อนนำออกจากด่าน merge
เกณฑ์ตัวเลขและรายละเอียดใช้ validation ของ feature เป็นแหล่งอ้างอิง

| Feature / งาน | เกณฑ์ที่ต้องตรวจรับ | หลักฐาน / ข้อจำกัดปัจจุบัน |
|---|---|---|
| F-15 workload/endurance/restore | V-19 / W1..W4 | **Pending Full Validation — เกณฑ์อนุมัติ 2026-10-18**; W4 restore ผ่าน 2026-10-20; W1–W3 ยังไม่ผ่านครบ เก็บ failed attempts และ recovery smoke แยกตาม M5 checkpoint. [Validation](features/2026-10-18-paper-order-matching/validation.md) แยก BTC-only capacity ตาม F-38 ออกจาก ETH runtime correctness/readiness; smoke ไม่แทนชุดเต็ม |
| F-12 history window | RQ-37..42 / V-H1..8 | **Passed 2026-10-22** — [acceptance progress](features/2026-10-12-candlestick-chart/evidence/2026-10-14-acceptance-progress.md): backfill ครบและ stored history 40/40 contiguous/unique; API traversal ทุกคู่ × 8 TF ถึง `display_start`, page overlap ตรงกัน. [หลักฐาน 2026-10-22](features/2026-10-12-candlestick-chart/evidence/2026-10-22-live-preview-recovery.md): 16/16 live series สดและกู้ lease หลัง host sleep สำเร็จ; browser session จริงผ่าน pan→pagination 1,000 rows, controlled Retry-After→manual retry ไป API จริง และ reset กลับล่าสุดโดยไม่ยิง request เพิ่ม |
| F-12 workload/resource | V-17 ชุดเต็มทั้ง LEGACY/PREPARED และส่วนสรุป V-18 ที่พึ่ง V-17 | **Passed 2026-10-23** — [deterministic full rerun](features/2026-10-12-candlestick-chart/evidence/2026-10-23-v17-full-rerun.md) ผ่าน LEGACY/PREPARED 600s หลัง warmup 60s, 20 clients, 100 lifecycle cycles, fault/recovery 5/5 series และทุก threshold เดิม; [รอบแรกที่ Failed / Partial](features/2026-10-12-candlestick-chart/evidence/2026-10-23-v17-full-workload.md) ยังคงเก็บไว้. ส่วน V-18 ที่พึ่ง V-17 ปิดแล้ว; [PR #24](https://github.com/yukasung/tiewtrade/pull/24) merge เข้า main เป็น `27a7718` แล้ว โดย CI ของ candidate ผ่าน 6/6; [post-merge CI 39934274551](https://github.com/yukasung/tiewtrade/actions/runs/39934274551) ผ่านครบ 6/6 แล้ว และไม่ปิด C3/C5, C4/C6 หรือ release gates อื่น |
| F-16 manual order entry | V-18 / V-20 | **Development Complete — Pending Integration/Full Validation**; merge PR#36 เป็น1f16ddb และ post-merge CI40208544618ผ่าน6/6. V-19ผ่าน; V-18รอ F-18 ก่อน production activation และ V-20 **Pending Full Validation** ที่release checkpoint/ชุดที่9 โดยคงเกณฑ์ F-15 W1–W4 และมี integrated profile Approved A 2026-11-06 แล้ว; execution ยังไม่ถึง sustained HTTP phase — [validation](features/2026-10-25-manual-order-entry/validation.md) |
| F-18 wallet risk limits | V-21 / V-22 / V-23 | V-21 **Paper Validation Passed (R34/current candidate)**: W1–W4, 100 owners ×20 orders, fault/endurance, restore, financial/idempotency oracles, affected regression/static checks and final review passed; current-head required CI run `41173114518` passed all 6 jobs. Historical Failed/Partial evidence is preserved in [M5](features/2026-10-25-wallet-risk-limits/evidence/m5-final-candidate.md). Owner create-wallet/save-limit and browser manual order-submit observations passed. V-22/V-23 **Pending Dependency**: bot/Live authority and notification features. Production/Live activation remains closed; F-18 is not Completed until those gates are satisfied. |
| F-38 runtime/workload/restore | V-12/V-13/V-15 | **Passed — F-38 Completed 2026-10-27** — current C1 readiness 16, BTC workload 8, combined steady/dirty phase ละ 3,600s, S1–S5/C4/C6 ผ่าน; reuse approved pre-0030 restore ตาม provenance. Final candidate `aabdfb9` ผ่าน required push/PR CI 12/12 jobs และ PR #38 merge เป็น `bf7b847`; [current crosswalk](features/2026-10-15-supported-pairs-reduction/evidence/release-20261026-merge/README.md) |
| F-13 reset/recovery closure | V-6..V-10/V-13 | **Passed 2026-10-21** — reconcile กับ F-15 V-14/V-15 และ final candidate แล้ว: real-source reset, controlled races, source conflict/error, cancellation/timeout, lost acknowledgement, TCP disconnect และ process-kill ก่อน/หลัง RESET commit ผ่านโดยไม่มีข้อมูลหรือทุนซ้ำ; required CI run #124 attempt 2 และ post-merge run #125 ผ่านครบ ตาม [validation](features/2026-10-15-paper-wallet/validation.md) |
| F-11 โหลดและระยะยาว | R2-C2/C3/C5 รอบเต็ม; C4 ส่วน trace/fairness ที่ต้องใช้รอบเต็ม; C6 และ R2-G7/D7 เฉพาะส่วนที่พึ่ง capacity | C2 rerun ผ่าน 3,600.016s ใน [release checkpoint เดิม](features/2026-10-10-backend-indicators/profiling/release-20261014/README.md); R2-C1 และ R2-7 ผ่านซ้ำ 2026-10-23 ตาม [validation](features/2026-10-10-backend-indicators/validation.md). C3/C5 ยังไม่รัน, C4 ยังไม่ครบ และ C6 ยัง Failed; ต้องพิสูจน์ด่านที่เหลือตามเกณฑ์เดิม |
| F-11 หลักฐานประกอบการตรวจรับ | R2-7 ต้องมีกรณี 525,600 slots; รวมผล worker/resource/parity ที่ใช้ปิด capacity gate | **Passed 2026-10-23** — controlled exact fixture 525,600 rows/slots, 527 checkpoints, cold1/warm5 correctness 6/6, 7 candle queries/request, max lag 36.344ms และ max RSS delta 6,615,040 bytes; [Validation และ artifact paths](features/2026-10-10-backend-indicators/validation.md). ไม่เปลี่ยน production logic/threshold และไม่ปิด C3/C5/C4/C6 |
| ระบบรวม | Flow ผู้ใช้, เงิน/ออเดอร์, ความล้มเหลว/กู้คืน และความปลอดภัยตามตารางชุดที่ 9 | รอแผนตรวจรับรวมและ validation ที่อนุมัติ; ไม่แทนเทสต์ของแต่ละ feature |
| F-11/F-12 PREPARED diagnostic | Milestone A/B อนุมัติ 2026-10-13 | [Follow-up](features/2026-10-10-backend-indicators/profiling/prepared-chart-smoke-fixed-r2/README.md) ผ่าน smoke 30/30 และ API 60/60; รอบเต็ม [2026-10-14/15](features/2026-10-10-backend-indicators/profiling/release-20261014/README.md) ผ่าน C2, R2-7 ผ่าน 2026-10-23 ตาม [validation](features/2026-10-10-backend-indicators/validation.md) และ F-12 V-17 ผ่าน [deterministic full rerun](features/2026-10-12-candlestick-chart/evidence/2026-10-23-v17-full-rerun.md). C3/C5 และ C4/C6 ยังไม่ครบ จึงยังไม่เปิด PREPARED จริง |
| ฐานข้อมูล / F-31 | Backup/restore จริงและตรวจข้อมูลหลังคืนระบบ | ยังไม่มีหลักฐานตรวจรับในทะเบียนนี้; ต้องระบุวิธีและเกณฑ์ในแผนตรวจรับก่อนรัน |

**ด่านที่ไม่ได้เลื่อนของ F-11 (ตรวจผ่านก่อน merge PR #9 แล้ว):** full regression (ล่าสุด backend ผ่านแล้ว รวม Redis admission; หลักฐานอยู่ใน validation),
ความถูกต้อง/ความปลอดภัย/transaction/concurrency/parity และ mixed-version/GC cases
ที่ไม่ใช่รอบโหลดหรือระยะยาวซึ่งอนุมัติเลื่อน ต้องผ่านตาม validation เดิม
D1 first-release amendment Passedหลังแก้numeric parity/evidence trace ตาม d1-harness-review.md; D2..D6 ไม่ถูกยกเว้นเพราะ D7 รอ capacity;
การทดสอบสั้นของ fairness และ GC ผ่านแล้วตาม validation; ส่วนรอบโหลดและระยะยาวยังรอตรวจรับชุดที่ 9
หลักฐาน review/CI/merge ล่าสุดอยู่ใน [validation](features/2026-10-10-backend-indicators/validation.md); รายการตรวจรับชุดที่ 9 ข้างต้นยังค้าง และยังไม่รับรอง Completed หรือ production PREPARED
## ลำดับที่เสนอ

**Proposed — เจ้าของยังไม่อนุมัติ**

1. F-01 → F-04 (ฐานราก) — ทำก่อนเสมอ
2. **F-33 (ชั้นแยก venue) → F-35 (Binance TH)** — ต้องมาก่อนงานที่แตะตลาด
3. F-05 → F-08 (ผู้ใช้และบัญชี)
4. F-09 → F-12, **F-37 (รายการเหรียญ)** — เห็นผลบนหน้าจอเร็ว
5. F-13 → F-17 (Paper Trading) — **จุดปล่อยที่ 1: ทดสอบภายใน** (ดูเงื่อนไขด้านล่าง)
6. F-18, F-19 (เพดานความเสี่ยงและปุ่มหยุดบอท) — NC-07 ปิดแล้ว
7. F-20, F-21 (บอท)
8. **F-26 (แจ้งเตือนในแอพ)** — ต้องเสร็จก่อนแตะเงินจริงใน F-25
9. F-22 → F-24 (พัฒนา Live Trading; ยังไม่ใช้เงินจริง)
10. F-27, F-36, F-28 → F-32 (รอบระบบ ทำคู่ขนานได้)
11. **ชุดที่ 9 — ตรวจรับระบบก่อนใช้งานจริง** หลังพัฒนาชุดที่ 8 — รวม load/ระยะยาวของ F-11 และระบบรวม; ผ่านแล้วจึง F-25 และเปิดให้คนนอกเมื่อเงื่อนไขอื่นครบ

### จุดปล่อยมี 2 จุด ไม่ใช่จุดเดียว (เจ้าของตัดสิน 2026-09-26)

**จุดปล่อยที่ 1 — ทดสอบภายใน** หลัง F-17

- ให้เจ้าของและคนที่เรารู้จักลองใช้ โดยบอกชัดว่าระบบยังไม่เสร็จ
- **ห้ามเปิดให้คนทั่วไปสมัครเข้ามา**
- Paper เท่านั้น

**จุดปล่อยที่ 2 — เปิดให้คนนอก** ต้องครบทุกข้อนี้ก่อน

| ต้องมี | เพราะ |
|---|---|
| **ชุดที่ 9 ตรวจรับระบบ** | ต้องผ่านการตรวจรับระบบรวมก่อนเปิดให้คนนอก (เจ้าของอนุมัติ 2026-10-11) |
| F-18 เพดานความเสี่ยง | `trading-safety.md` หัวข้อ 13 บังคับว่า Paper ใช้กฎเดียวกับ Live ทุกข้อ |
| F-19 ปุ่มหยุดบอท | กฎเดียวกัน และผู้ใช้ต้องหยุดบอทได้ |
| F-32 เอกสารทางกฎหมาย | **NC-11** บล็อกการเปิดให้คนนอกใช้ตาม `mission.md` หัวข้อ 9 |
| **นโยบายเก็บข้อมูลของ audit log** | F-04 เก็บทุกอย่างไว้โดยไม่ลบ ซึ่งเป็น **ข้อยกเว้นชั่วคราวจาก `database.md` หัวข้อ 7** สำหรับช่วงพัฒนา ต้องเคาะว่าเก็บนานแค่ไหนก่อนมีข้อมูลของลูกค้าจริง (เจ้าของตัดสิน 2026-09-27 — F-04 RQ-21) |


**ข้อสังเกตที่ต้องให้เจ้าของตัดสิน:** เจ้าของเลือกว่าต้องมี Live ตั้งแต่แรก (R-04)
แต่ตามลำดับนี้ Live อยู่ท้าย เพราะต้องมีกฎความเสี่ยง หยุดฉุกเฉิน กันสั่งซ้ำ และกระทบยอด
ครบก่อน — ทางเลือกคือ **ปล่อย Paper ให้คนใช้ก่อน แล้วเปิด Live ตามทีหลัง**
ซึ่งได้ผู้ใช้จริงมาช่วยทดสอบก่อนที่จะมีเงินจริงเข้ามาเกี่ยวข้อง

F-18 follow-up (2026-10-28): source-lease SQL roundtrip reduction passed206affected
regressions plus21focused checks and relevant static checks. A bounded comparison
showed partial progress improvement but persistent financial-fence timeouts;
W1/W2/W3 remain Pending Full Validation, not Completed. Details in
[the F-18 checkpoint](features/2026-10-25-wallet-risk-limits/evidence/m5-final-candidate.md).
F-18 W1r20:2000baseline completed; measured60s cycle deadline failed with342
commands/42cycles completed. API pool checkout was the terminal wait; root cause
not yet isolated. V21 remains Failed/Pending Full Validation; W2/W3 not run.
F-18 W1r21: approved R10/source-clock experiment still failed60s cycle after
425commands/66cycles. Unresolved command retried3times; typed defer reason needs
evidence. Defaults remain off; W2/W3 not run; Failed/Pending Full Validation.


Set-4 NC-SET4-05 owner-approved A implemented0065/PG_BATCH_V1 and default-off
standalone final-tail gate. Real-DB equivalence (6snapshots,11→6client calls),
migration/authority/rollback/recovery, TP/SL/risk and targeted static checks passed;
initial test-fixture/hook failures retained with passing affected followups.
Exactly one fresh100-owner/6-cycle diagnostic is running (non-acceptance).
W1Failed/Partial and W2/W3NotRun remain; W4Passed0064 applies only to the old writer,
new0065 writer W4 is Pending Revalidation. V18/V19PendingFullValidation and missing
integrated NC-SET4-01 profile remain. Stop/report after this run, no Git publication.
Evidence: [Set-4 Batch ledger](features/2026-11-02-tp-sl/evidence/batch-20261106/README.md).


Set-4 follow-up NC-SET4-06: offline analysis/next plan completed at owner's request;
no runtime edits or new tests/workload. Proposed small paired writer campaign is
Awaiting Approval/Not Run; it will not establish100-owner or W1 acceptance.
See [isolation plan](features/2026-10-18-paper-order-matching/checkpoint-latency-isolation-plan.md).
Current failure and pending validation statuses remain unchanged.


Set-4 NC-SET4-07: Approved A; harness/targeted validation in progress, campaign
Not Run.8measured arms plus one reference,576checkpoint operations,
fixed0065batch with1/4writers ×0/100readers; production remains unchanged.
[Plan](features/2026-10-18-paper-order-matching/checkpoint-concurrency-polling-plan.md).
All previous failures/inconclusive results and acceptance gaps are retained.


Set-4 NC-SET4-08: next [plan](features/2026-10-18-paper-order-matching/checkpoint-runtime-drift-plan.md)
approved A; harness/targeted validation in progress, campaign Not Run. One-writer adjacent
polling pairs and bounded runtime observations,288 proposed checkpoints. Only
documentation/read-only prior-evidence analysis changed; no new workload or code.
NC07 remains Inconclusive; W1 and integrated acceptance gaps unchanged.


Set-4 NC-SET4-09: [approved plan](features/2026-10-18-paper-order-matching/parent-poll-budget-plan.md)
implemented in harness;115 targeted tests and static checks passed. Single diagnostic
**Incomplete / cycle bound Failed**:813.431s total,2000 baseline orders complete,
289/600 cycles and1632/3000 commands complete before60s cycle timeout. Poll gate
peak4/active0; resource cleanup verified. Full financial/final-tail/input-lag checks
Not Reached; partial worker p95=1003.8ms. Waiting moved to gate; no demonstrated
end-to-end fix. Original acceptance gaps unchanged, **Pending Full Validation**.
Stop/report reached. Recommended existing worker/queue trace inspection and next
planning await owner direction; no additional run, production change or Git action.

NC09 follow-up inspection completed on owner direction: four command-result stages
sum32.554s before handling,2.585s handling and3.367s subsequent observation delay.
Measured claim calls86.68% skipped. Last status read ended59.186s; next read waited
for a permit until60.002s. Retained final order is FILLED; last owner processing
transaction ended59.723s, suggesting a boundary observation miss (exact projection
commit time unavailable). Keep the Incomplete/Failed result and criteria unchanged.
Next recommended bounded worker claim-efficiency plan awaits owner direction;
no rerun or source change. See Batch ledger's NC09 follow-up for limitations.

Set-4 NC-SET4-10: [worker claim coordination plan](features/2026-10-18-paper-order-matching/worker-claim-coordination-plan.md)
approved A and implemented — **Targeted Safety Passed / Performance Not Run**.
Default-off PG coordinator for selection/claim only; processing remains parallel.
94 targeted cases passed (85 combined +9 setup-blocked regressions rerun), static
checks passed and7 import contracts kept. Cleanup verified. Owner fences/criteria
unchanged. No production activation, timed campaign or W1. Next NC10-scoped code
review awaits owner command; overall **Pending Full Validation** remains.

Set-4 consolidated closure checkpoint: NC10 review completed; one Medium test
coverage gap fixed (lost coordinator COMMIT reply after committed owner claim),
both commit-loss cases passed with scoped Ruff/format/mypy. F-17 integration48/48
passed on fresh0065. F-15 W4 now **Passed on0065** after actual backup/restore,
financial/history replay, RLS/grants and lease recovery checks; its fixture does
not cover F-17 history. No production changes in this follow-up. Current changes
still lack final published-candidate CI. F-17 stays **Development Complete —
Merged / Pending Batch & Release Validation**: W1 Failed/Partial, W2/W3 Not Run,
NC-SET4-01 still open, V19/V20 require planned bot/notification/Live dependencies.
Next: owner decision on the concrete [integrated Paper proposal](features/2026-11-02-tp-sl/integrated-paper-acceptance-plan.md)
before its new profile/harness is implemented. Raw results in the F-17 Batch ledger.


Set-4 latest integrated Paper checkpoint: owner approved the
[consolidated profile](features/2026-11-02-tp-sl/integrated-paper-acceptance-plan.md);
NC-SET4-01 is Closed / Approved A, superseding the earlier missing-profile blocker.
Harness tests133 and affected observation tests45 passed with scoped static checks.
Two coordinated diagnostics are retained as Failed/Incomplete: first failed setup;
second completed2000 baseline orders but only188/600 cycles,1091/3000 commands,
then60.001s timeout. Partial processing p95=441.6ms and18/20 worker exits; full
financial/final-tail acceptance was not reached. All pools/processes/connections
cleaned up. W1 Failed/Partial, W2/W3 Not Run, standalone W4 Passed0065; sustained
HTTP/F-14 workload/integrated restore phases have not run. F-17 V18 Partial/Failed,
V19/V20 Pending Dependency, final published-candidate CI Pending. No Completed claim.
Next: owner decision on the concrete [NC-SET4-11 protocol amendment](features/2026-10-18-paper-order-matching/worker-claim-contention-amendment.md)
needed to change blocking acquisition; no third run or source change made.


Set-4 NC-SET4-11 latest: owner Approved A, V2 nonblocking/250ms implementation and
135 targeted safety tests passed; scoped Ruff/format/mypy and7 import contracts
passed. One diagnostic **Incomplete / setup Failed** after165.058s at book
`WriterLeaseLost`:394/2000 baseline orders,0 measured commands/cycles. One worker
claim SQL deadline and one shutdown SIGTERM; cleanup verified. No gate-acquisition
timeout stack observed, but no workload/performance success established. Source837
hashes stable and all previous failures retained. **Stop/report checkpoint reached**;
no repeat, W1 or Git publication. F-17 remains Development Complete — Merged /
Pending Batch & Release Validation. V18 Partial/Failed, V19/V20 Pending Dependency;
V2 affected final-candidate checks/CI remain. Next recommended step: scoped baseline
publisher/DB timing plan before another owner-approved campaign; exact slow stage
is not recoverable from current setup-only aggregate evidence.

### Recovered candidate and publisher diagnostic checkpoint — 2026-11-06

Temporary Set-4 worktree/raw artifacts were lost. Source was reconstructed into the
permanent sibling `TiewTrade-paper-set4-recovery`; old narrative is historical, not
replacement raw evidence. Fresh recovery303+2 tests passed, all28 recovered Python
files type-checked; follow-up78 affected cases and scoped static checks passed,
7 import contracts kept. The retained original0065 DB function matches recovery.

The owner-approved publisher timing follow-up and exactly one diagnostic are complete:
566.039s, baseline2000/2000, measured917/3000 commands and145/600 cycles before
60.002s cycle timeout. Partial measured worker p95=470.510ms>250ms. Publisher lease
loss did not reproduce; no worker exited abnormally. Full financial/final-tail/resource
acceptance Not Reached. All pools/streams/processes and DB connections/locks closed;
839 candidate hashes stable. No repeat/W1/publication. See [new raw evidence](features/2026-11-02-tp-sl/evidence/recovery-20261106/README.md).

V18 remains Partial/Failed; V19/V20 Pending Dependency; final candidate CI Pending.
Integrated profile NC-SET4-01 remains Approved A. Next recommended step: a concrete
runtime-fix plan for queue/processing/polling progress using these traces, before any
new timed run. Preserve60s and250ms criteria; this checkpoint does not close F-17.

### Latency measurement correction — Approved A,2026-11-06

Owner selected a measurement-only correction after criteria review. Shared start-time
selection now excludes setup/fault-start/drain cohorts while retaining complete slow
durations.66 targeted cases and scoped Ruff/format passed; F15/new-test mypy passed.
Risk-harness mypy has2 pre-existing callback type errors reproduced on the pre-edit
snapshot; this checkpoint does not claim all harness types pass. Reanalysis of old
raw data retainsp95=470.510ms>250ms. No production change, new workload or Git action.
See [evidence and next step](features/2026-10-18-paper-order-matching/evidence/latency-population-20261106/README.md).
F-17 status and Failed/Partial/Release dependencies above remain unchanged. Next:
bounded performance-fix planning and the existing callback typing before relevant
candidate checks; new runtime work/timed testing awaits an agreed scope.

### Internal Paper pilot - NC-SET4-12 Approved A,2026-11-06

Owner approved the [internal-pilot requirements/plan/validation amendment](features/2026-11-02-tp-sl/internal-paper-acceptance-amendment.md):
10 invited testers,20 active-account acceptance, unchanged per-account workload,
latency, financial and duration criteria. Scoped harness/checks and conditional
campaign are authorized. Current results and the next gate are recorded below.
Existing100-account Failed/Partial/Not Run results and F17 V-18/V-19/V-20 remain;
F17 is not Completed. Next: implement/verify the approved harness, then proceed
only through passing campaign gates. Git/deploy gates remain.

NC12 checkpoint: UUID fix/affected tests and restore safety passed. The approved
controlled20 replacement passed132.922s:20/20 owners≤1s (max444.013ms),400baseline
orders and exact financial/retry checks passed. D20 completed600commands and passed
financial/p95/p99 gates, but **Failed** because final connections68 exceeded57+2.
The last sample coincides with the existing20-reader final-tail stage; earlier
samples57–59 and post-stop cleanup0 do not establish definitive pool attribution.
W1/W2/W3/W4 were Not Run at that checkpoint. The subsequently approved
[amendment§11](features/2026-11-02-tp-sl/internal-paper-acceptance-amendment.md)
added the harness-only final-tail poll limit; its result and next decision follow. Previous Failed/
Incomplete results remain; the pilot is Pending Validation and F17 is not Completed.

Section11 final-tail gate was Approved A;126 affected tests and scoped static checks
passed. Its one D20 replacement stopped **Incomplete** (395/600 commands) on publisher
book readiness before final-tail, leaving the resource fix unproven in that run.
Exact failed guard timestamps were not captured; no freshness/clock fix is justified
yet. Cleanup0 connections/locks. The owner subsequently approved section12.

Section12 checks passed154 targeted cases plus12 observer rechecks and scoped
static checks. Its single D20 run **Passed**:600/600commands,20/20 financial oracles,
p95=192.754ms/p99=325.518ms, connections57→58 (peak59), final-tail0.947s,
cleanup0/0, candidate unchanged. Readiness failure did not recur; prior cause
remains unproven. W1 subsequently **Incomplete** at1227.598s measured:
2384/3600completed; owner cycle exceeded60s waiting for final sell FILLED.
Partial p95/p99=487.319/1184.654ms and connections57→63 (peak64) remain concerns.
Full financial/global oracle, final-tail and snapshot/rebuild were not reached.
Read-only evidence identifies a costly terminal-history lookup; amendment§13
proposes reusing its existing index with bounded lookup, subject to owner approval.
Production unchanged; cleanup0/0. Section13 subsequently Approved A; query fix and50 targeted tests/static checks passed.
Next: the authorized fresh D20, then W1 only on passing gates.
W2/overflow/W3/fullW4 remain Not Run; no automatic retry.
The internal pilot remains Pending Validation; F17 remains not Completed.


NC12§13 query fix passed50 real-DB safety cases and scoped static checks. Its resumed
D20 **Failed** despite600/600commands and20/20 financial/resource oracles passing:
p95=531.809ms and2976/3000measured book inputs. No W1 replacement started.
The preflight recorded host load24.84 on8logicalCPUs with another project's
Node/Next workload; environment interference is a confounder, not a proven sole
cause. Existing pass/fail evidence remains tied to each candidate. Next: owner
decision on [amendment§14](features/2026-11-02-tp-sl/internal-paper-acceptance-amendment.md),
a fixed environment-readiness window before one D20. F17 is not Completed.


NC12§14 revised plan was approved and implemented with211 unique passing targeted
cases and scoped static checks. Its single preflight stopped **Incomplete** before
workload:load1=19.29>8logicalCPUs; disk/services passed. No fixture, workers or measured
commands started; cleanup0/0 and candidate unchanged. D20 on§14 and W1 replacement
onward remain Not Run. Implementation checkpoint complete; internal pilot/F17 remain
open. Next: owner-triggered preflight when host activity subsides, preserving all
criteria; no new code/threshold amendment or automatic retry is proposed.


NC12§14 readiness revision2, requested2026-11-07, replaces the load ceiling with
7-sample mean CPU idle≥20% and non-Critical memory pressure; Warning is retained
in evidence and load remains informational.108 targeted checks and scoped static
checks passed; native sensor read worked. New preflight/D20 remain Not Run.
Next: owner-triggered preflight/D20 using revision2. Original safety/performance
criteria and all recorded Failed/Incomplete results remain; F17 is not Completed.


NC12§14 revision2 D20 **Passed** on2026-11-07:7-sample preflight mean idle49.481%,
600/600commands,20/20financial oracles/global/resource checks; p95=116.400ms,
p99=164.199ms, book3000/3000, connections57→58 (peak59),cleanup0/0, candidate
unchanged. Evidence: `nc12-section14-v2-d20/`. Next: approved fresh-DB W1 with
preflight and30min authenticated HTTP workload, then conditional remaining phases.
F17/internal-pilot acceptance remain open until all required gates pass.


NC12§14 revision2 W1 **Failed solely the connection-growth predicate**:3600/3600
commands, all20 financial/global checks, engine p95/p99=133.580/191.986ms,
book18017/18000,20 snapshots p95/p99=32.977/33.661ms and20rebuilds max7.052s
passed. Connections57→60 against59allowed (peak61); increase occurs at first use,
but per-pool API ownership/return evidence is missing. Cleanup0/0; candidate
unchanged. Preserve Failed. Evidence: `nc12-section14-v2-w1/`.
Next: owner decision on amendment§15's direct pool-resource contract and one W1;
no W2/overflow/W3/fullW4 or automatic retry started. F17 remains not Completed.


NC12 §15 implementation checkpoint — 2026-11-07: owner approved A. Added NC12-only
owned-pool inventory/periodic samples/pre-disposal return checks, reusing PoolEvidence.
Production and other profile predicates unchanged. Affected regression:214 passed,
4 initial failures corrected; scoped rechecks35/35 passed. Ruff/format and scoped
mypy passed. Existing production50 safety checks remain applicable. One approved
fresh-DB W1 is next; no new timed result yet. Historical §14-v2 W1 remains Failed.


NC12 §15 W1 — Incomplete (2026-11-07),274.262s total. Preflight passed(meanCPUidle66.817%).
Stopped early because new pool instrumentation omitted the existing read-only admin
engine used by require_empty_database; DatabaseRole conversion recorded ValueError.
No30min/performance acceptance. All20 workers stopped cleanly; registered loans
returned, final DB cleanup0connections/0advisory locks; candidate/runner unchanged.
Evidence:`nc12-section15-w1/analysis.md`. Historical Failed results retained.
W2/overflow/W3/W4 not started. Next: owner approval of amendment§16 before correction
and one replacement W1; no automatic retry.


NC12 §16 criteria revision — Proposed,2026-11-07, at owner's request after repeated
unsuccessful attempts. Proposal separates environment/harness Incomplete from proven
system Failed; uses complete owned pool capacity/return evidence including the existing
admin observer. It preserves financial/safety/latency/workload thresholds, prior
Failed/Incomplete results and conditional phase gates. Actual startup/shutdown coverage
must pass targeted real-DB tests before another long campaign. Specific revised criteria
and one replacement W1 await approval in internal-paper-acceptance-amendment.md§16.
Documentation only this turn; no source change or new campaign.


NC12 §16 revised pilot latency proposal (owner requested less strict criteria):
engine p95≤500ms/p99≤2s for invited20-account Paper pilot only; retain250ms/1s as
reported target with explicit warning when missed. Keep financial/order/position
correctness, TP/SL start≤1s, snapshot/recovery/feed/workload/durations and full Release
requirements unchanged. Specific thresholds await approval; no runtime change or
new campaign. Admin-observer instrumentation defect still requires correction.


NC12 §16 implementation/checks complete,2026-11-07. Owner approved500ms/2s
engine processing for20-account Paper pilot only; original250ms/1s target remains
reported with performance_warning. Default profiles, protection start, snapshots,
workload duration and production unchanged. Complete parent inventory13(including
read-only ADMIN_OBSERVER5+10), workers2 each. Unknown identity/read-write admin
options/missing evidence fail closed; real resource failures remain distinct from
Incomplete observer evidence, including simultaneous failures.

Targeted182 passed8.46s; classification8 passed1.00s(5 overlapping,3 additional).
Ruff/format passed5repo files; mypy passed5files. Private campaign runner scoped Ruff
passed ignoring only its pre-existing BLE001 catch used to retain cleanup evidence;
format passed. Production source hashes unchanged from§15 candidate. No new financial
code or persistent/session state. Existing50 production safety cases remain applicable.

Next: one approved fresh-DB W1, same3600commands/30min withpreflight (~35–40min total).
Passing continues W2/overflow/W3/W4; failure/incomplete stops without retry. Earlier
results retained. This checkpoint is not F17 Completed.


NC12 §16 W1 — Passed,2026-11-07. Total2080.281s; measured1800.965s.
3600/3600commands,720cycles,1440fills,720cancels,720replays,0rejects; all20financial
oracles/global invariants passed. Engine p95=144.262ms/p99=211.241ms: both original
250ms/1s targets and approved pilot500ms/2s ceilings passed; no performance warning.
Measured inputs18010/18000. Snapshots20/20 passed p95=36.377ms/
p99=36.468ms; all20rebuilds passed,max6.359s.
Owned inventory complete(parent13,workers20×2); all21process reports passed, no
pool violations/incomplete evidence, all loans returned before disposal. Raw aggregate
connections57→61,peak61 retained; no initial+2 proxy used. Final cleanup0connections/
0advisory locks. Candidate/runner unchanged. Evidence:nc12-section16-w1/.

Next: approved fresh-DB W2, then overflow/W3/W4 conditional on passing. Historical
Failed/Incomplete runs retained. This is W1 internal-pilot acceptance only; F17 stays open.


NC12 §16 W2 — Failed throughput duration,2026-11-07. Total1136.363s;
measurement963.571s exceeds600s target+60s allowance=660s. This is the sole failed
acceptance predicate. Completed12000/12000commands,2400cycles,4800fills,2400cancels,
2400replays,0rejects; all20financial/global/snapshot/rebuild checks passed.
Engine p95=363.782ms/p99=492.133ms passes approved pilot500ms/2s; original250ms
p95 target missed and performance_warning=true retained. This does not waive the
separate throughput/duration criterion. Measured inputs9635/6000, workers no failures,
resource/pool checks all passed; all registered loans returned before disposal.
Parent13pools/workers20×2 inventory complete, observer errors none. Snapshots20/20
p95=18.214ms/p99=18.502ms; rebuild max1.068s. Input lag4 remained within the existing
bound. Final cleanup0connections/0advisory locks; candidate/runner unchanged.

The cohort's effective completed throughput is12.454commands/s over963.571s. This
closed-loop observation does not establish an absolute capacity or prove which
query/queue/worker stage is the bottleneck. No causal root-cause claim is made.
Evidence:campaign-result.json, run/result.json, gate-assessment.json, raw samples/logs.

Stop checkpoint: W1 Passed is retained; W2 Failed retained. No W2_OVERFLOW/W3/fullW4
started, no automatic rerun, source fix or further threshold relaxation. F17 remains
Pending Full Validation. Next requires owner decision on the next scope: retain the
20commands/s burst requirement and investigate/fix throughput, or explicitly approve
a distinct lower-load internal profile while retaining the20commands/s requirement
for the original release gate. Any concrete profile requires declared rate/counts/
duration before execution; do not choose numbers from this failed run to relabel it.




NC12 W2 existing-evidence analysis complete,2026-11-07. Owner-approved read-only
scope only: W2 owner cycle interval7.971s versus5s planned; dominant observed gaps
follow HTTP intake, while poll-permit p95≤2.5ms and bridge attempts=1 for all9600
unique requests. Worker scan/coordination/claim/process division remains unmeasured;
no causal SQL/backoff conclusion. W2 remains Failed; no new campaign/source fix.
Evidence:nc12-section16-w2/throughput-analysis.md and offline timing/timestamp JSON.
Next: approve proposed§17 bounded worker-phase diagnostic, or choose another scope.




NC12 §18 lower-burst proposal,2026-11-07: owner requested criteria revision instead
of another diagnostic. Defer unapproved§17. Propose explicit internal V2 W2 target
10commands/s, retaining20owners/400baseline/120cycles-per-owner/12000commands, hence
1200s target/1260s completion bound and≥12000book inputs. Financial/safety and all
other gates unchanged; reuse valid W1 evidence. Specific profile values/campaign
still await approval. No source change or new run. W2 V1 remains Failed; full F17
remains open separately from internal pilot acceptance.


NC12 §18 Approved/implemented,2026-11-07. Explicit PAPER_INTERNAL20_V2 changes
W2 only to10commands/s/1200s with120cycles-per-owner/12000commands unchanged.
Completion allowance1260s; required book inputs12000 at10Hz. V1/defaults, money,
worker/pool/coordinator/retry and other phase definitions unchanged. Actual V2 name
is forwarded to worker subprocesses and recorded in manifests/timing revision.
Tests233 passed8.77s;5 profile rechecks passed0.31s after test typing correction.
Scoped Ruff/format passed5repo files and private runner; mypy passed5files. Private
runner retains its pre-existing broad cleanup exception with BLE001 excluded only
for that file. Production source hashes unchanged; prior safety evidence remains
valid. W1§16 passing evidence reused only for unchanged assertions. All earlier
Failed/Incomplete runs retained. No§17 diagnostic added or executed.

Next: one approved fresh-DB V2 W2 withpreflight (~25–30min including20min measured),
then overflow/W3/W4 conditional on passing each gate. No repeated W1/D20. A failed/
incomplete gate stops without retry. Internal pilot and F17 remain open pending gates.


NC12 §18 V2 W2 — Failed resource contract,2026-11-07. Total1445.897s;
measured1241.602s passes1200s+60s allowance=1260s. All12000commands completed,
2400cycles,4800fills,2400cancels,2400replays,0rejections. All20financial/global/
position checks passed; snapshot p95=16.945ms/p99=17.360ms,20rebuilds,max3.415s.
Engine p95=363.444ms/p99=541.362ms passes500ms/2s pilot ceilings; performance_warning
retained because original250ms target missed. Inputs12395/12000,input lag9 within
existing bound, no worker failures. The relaxed throughput/duration gate passed.

The only failed gate is the owned-pool contract: parent recorded4 active-work
ConnectionResourceError entries, all original_exception=CancelledError,sqlstate empty,
quiescing=false. Inventory complete(parent13,workers20×2); all borrowed connections
returned before final disposal; all20worker reports passed. Final cleanup0connections/
0advisory locks and candidate/runner unchanged. No proven connection leak is reported.

The evidence does NOT identify which pool/task/query was cancelled or at what time.
Do not silently treat these as normal shutdown cancellations or assume a trading
transaction failed. Parent completed normally; this alone does not establish the
origin/safety of those4cancellations. Existing API price-read code has bounded read
deadlines, so deliberate read cancellation is one candidate, not a proven cause.

Stop checkpoint: preserve Failed and all prior results. No overflow/W3/fullW4,
replacement W2, further threshold change, production edit or Git/deploy action.
Existing§16 W1 remains Passed. Internal pilot and F17 remain open.

Recommended next scope: add test-only cancellation provenance(timestamp,pool role/
identity,task or named operation,quiescence/deadline context; never SQL,binds,secrets),
and targeted real-DB regressions distinguishing a known read-only deadline from
worker/financial cancellation, disconnect and leaked borrow. Reuse OwnedPools and
existing API lifecycle/readers. Establish a specific rule only after the origin is
known; no new timed campaign is proposed or authorized at this checkpoint. Current
source/harness is unchanged after the failed gate. A next implementation/campaign
requires a concrete approved scope under§18's stop rule.


NC12 §19 completed,2026-11-07. Test-only OwnedPools resource-error provenance
now includes UTC/monotonic timestamps, pid, engine/current-pool identity/generation,
role/capacity/configured-readonly, task id/cancellation count and bounded project
coroutine file/function/line locations. It never captures task names, SQL/binds,
URLs, payloads, locals or exception text. Unknown task/deadline stays unknown. Pool
identity is labelled current-engine-pool or original-registration fallback; after
churn this is not proof of the invalidated connection's original pool. Details are
bounded to16 with omitted count; all errors remain counted. No extra SQL queries.

Real-DB short regressions distinguish an explicit read-only query deadline from an
explicitly cancelled ENGINE query, preserve TimeoutError/CancelledError, show loans
returned and hooks restored, and prove neither secret binds nor task names appear.
Existing disconnect simulation, leaked-borrow, lifecycle/generation/classification
cases still pass. No financial state/session storage or production change.
Final affected suite82passed14.38s; scoped Ruff/format/mypy passed2files. Existing
production safety evidence remains valid; production hashes unchanged from§18.
Evidence: nc12-section19-final-targeted.xml/.log and nc12-section19-final-mypy.log.

Limitation: these controlled regressions do not identify the4historical W2 query
cancellations; the old artifact lacks source identity/time. Active cancellations
still fail under current acceptance; no warning waiver or retrospective Passed.
No workload/campaign was run. §18 V2 W2 remains Failed, W1 remains Passed; overflow/
W3/fullW4 and F17 acceptance remain pending. §19 stop/report checkpoint reached.


NC12 §20 approved2026-11-07. Reuse§19 final82targeted tests and scoped checks;
no further harness/production change. One fresh-DB PAPER_INTERNAL20_V2 W2 withbounded
cancellation provenance is starting; preflight and all existing gates remain binding.
Pin source/config/runner/schema; no retrospective status changes. Passing permits
existing overflow→W3→W4; failure/incomplete stops/report without retry. W1 reused.


NC12 §20 V2 W2 — Passed,2026-11-07. Total1398.032s; measured1205.681s≤1260s.
Completed12000/12000commands,2400cycles,4800fills,2400cancels,2400replays,0rejects;
all20financial/global/position checks passed. Engine p95=364.028ms/p99=516.442ms
passes pilot500ms/2s; performance_warning remains for original250ms p95 target.
Inputs12056/12000. Snapshots20/20 p95=50.690ms/p99=50.920ms; rebuildmax1.974s.
Owned inventory complete(parent13,workers20×2); all21process reports passed, no
resource errors/cancellations, all loans returned before disposal. Final cleanup
0connections/0advisory locks, candidate/runner unchanged. Evidence:nc12-section20-w2/.
No historical Failed/Incomplete status changed; the4old cancellations remain
unattributed because none recurred here. One passing run is not a causal fix claim.

Next: approved fresh-DB overflow case, then W3/W4 conditional on each gate passing.
W1§16 evidence reused. F17/internal pilot remain open until remaining gates pass.


NC12 §20 V2 overflow — Passed,2026-11-07. Total175.184s includingpreflight;
4097inputs overflow case recovered in20.155s≤60s, before/after economic snapshots
identical for all20owners (no fill/ledger/position change); baseline financial/global
checks passed. Parent plus initial/recovery workers' owned pool reports complete,
all loans returned, no resource errors; final cleanup0connections/0advisory locks,
candidate/runner unchanged. Evidence:nc12-section20-overflow/.
Next: approved W3 with unchanged4h/282cycles-per-owner/7fault schedule and periodic
position checks, then W4 only on passing. W1/W2 accepted in their existing scope;
F17/internal acceptance not yet closed. No further criteria or source change.


NC12 §20 W3 — Incomplete/owner time objection,2026-11-07. Owner said4hours was
too long and interrupted the turn. Stopped only the owned W3 campaign via SIGINT
at53.842s during preflight(3samples), before run/fixture/workers/measurement existed.
No W3 financial/performance/endurance acceptance claimed. Cleanup0connections/
0advisory locks; candidate/runner unchanged. Preserve raw Incomplete/CancelledError.
W1§16,W2§20 and overflow§20 passing evidence retained. No W3 retry/W4 started.
Next: specific shorter internal checkpoint proposal§21 requires approval before code
or execution; original4h Release requirement remains Pending Full Validation.


NC12 §21 Approved/implemented,2026-11-07. Explicit PAPER_INTERNAL20_V3 changes
W3 only to1800s/30cycles-per-owner/3000commands;7pinned fault kinds/durations retained
at180..1260s offsets. Selected duration drives hold/minimum, RSS window and30periodic
snapshot rounds(620total includingfinal20), with15000inputs and1830s completion
ceiling. V1/V2/default4h/282cycles/original schedule and240periodic rounds unchanged.
Short stability is labelled separately;4h Release remains Pending Full Validation.

Targeted220passed10.73s;6affected final rechecks passed1.50s; scoped Ruff/format and
mypy passed5repo files(private runner scoped Ruff excludes pre-existing BLE001 only).
Actual parent/reporting regression verifies1800s hold/minimum,30snapshot rounds,
short RSS and unchanged financial/counter/latency/resource predicates. Production
source hashes unchanged. Applicable W1/W2/overflow/production safety evidence reused;
no ceremonial reruns. See nc12-section21-*.xml/logs for evidence.

Next: approved one fresh-DB V3 short W3 with existing preflight, estimated35–45min
including30min measured/final replay/cleanup; passing permits W4. A failed/incomplete
gate stops without retry. Prior owner-stopped W3 remains Incomplete; no4h acceptance.


NC12 §21 V3 short W3 — Incomplete after observer resource alarms,2026-11-07.
Stopped the owned campaign after connection churn exposed invalid retired-pool
observations, saving the remaining planned runtime. Total596.076s includes preflight/
fixture/cleanup;30min measurement was not completed.755HTTP records and160snapshot
records retained; no full financial/oracle/fault/endurance acceptance is claimed.
Only initial restart and connection-churn faults had begun; remaining faults/W4 not run.

Parent observer recorded9PoolCapacityViolation and4PoolDisappearedBeforeReturn.
Raw snapshots show disposed ENGINE pool native checkedout=-1/-4 while independent
checkout/checkin event counts changed3→1→0. Installed SQLAlchemy QueuePool.dispose
sets _overflow=-size, and checkedout computes size-checkedin+overflow; late returns
can therefore make the retired pool's native counter negative. This is not an
actual negative/over-capacity connection count. Retired MARKET_DATA pool weakref
was collected while event count1 was still pending; its event count later reached0
before final shutdown. All registered loans returned in final parent proof; cleanup
0connections/0advisory locks and candidate/runner unchanged. Retain raw Incomplete/
CancelledError and original resource flags, not retrospective Passed.

The existing real-DB generation test disposed only after its borrow was returned;
it missed held loans across churn. This evidence identifies an observer accounting
defect, not a justification to waive lost-borrow/capacity safety or claim30min passed.
Evidence:retired-pool-observations.json, parent pool streams/summary, campaign log.

Next: proposed§22 fixes only retired-generation measurement semantics, adds real-DB
held-loan/GC regressions, then one replacement V3 W3 if approved and checks pass.
No source fix/new run after the failed gate. W1§16/W2§20/overflow§20 remain Passed;
4h Release remains Pending Full Validation and F17 remains open.


NC12 §22 implemented/checked,2026-11-07. Retired generations retain raw native
counters as informational after declared intermediate dispose; live pools still
require native bounds/configuration and every generation's event-tracked active/
peak borrow bounds remain binding. Retired weakref loss with pending returns is
recorded as pending, never waived at quiescence. Final zero-return/inventory/error
criteria unchanged; unexpected live pool loss and capacity mutation still fail.

Real-DB regression holds2loans across dispose, observes nativecheckedout=-1 while
one event-tracked loan remains, then returns both and proves oldpool GC without
observer retention. Simulated missing-native-view cases keep real DB loans and
checkin callbacks; returned passes, deliberately unreturned fails. Live pool loss/
retired configuration mutation and prior API/worker/disconnect/cancellation tests
pass. Initial2failures were reused nonempty DB and double-cleanup of a closed loan;
fixed test cleanup and used a fresh isolated test DB, preserving initial logs.
Final88targeted cases passed14.17s; scoped Ruff/format/mypy passed2files. Production
source unchanged and prior applicable financial/safety proofs retained.

Next: one approved fresh-DB PAPER_INTERNAL20_V3 short W3, same30min/3000commands/
7faults and§19provenance (~35–45min total), then W4 only on passing. Reuse W1/W2/
overflow. Earlier incomplete W3 and all Failed results retained;4h Release remains
Pending Full Validation. No criteria/production/Git/deploy change or automatic retry.


NC12 §22 V3 short W3 — Passed,2026-11-07. Total2089.437s; measured1800.001s.
3000/3000commands,600cycles,1200fills,600cancels,600replays,0rejects; all20financial/
global checks passed. Engine p95=132.721ms/p99=201.237ms passed original targets too.
All7faults RECOVERED:3worker restarts,2connection churns,2Redis outages. Snapshots
620/620 p95=48.893ms/p99=109.821ms;20rebuilds,max7.145s. Inputs18000/15000.
RSS window1800s growth−5.019% passed; this is short-window evidence, not4h endurance.
All81process pool reports complete, retired/live generations returned, no observer
resource errors; cleanup0connections/0advisory locks, candidate/runner unchanged.
Evidence:nc12-section22-w3/. Earlier Failed/Incomplete runs preserved.

Next: approved integrated W4 backup/restore/recovery on fresh source/target DBs.
W1§16,W2§20 and overflow§20 evidence retained; no repeat. Four-hour Release remains
Pending Full Validation and full F17 dependencies/review/CI gates remain open.


NC12 §22 W4 — Incomplete overall / integrated recovery Failed,2026-11-07.
Total206.839s; preflight passed. Real pg_dump/restore canonical data/RLS/grants checks
passed; domain replay21episodes,59evidence records,20checkpoints,18positions; one
expired legacy claim recovered without economic effects. Backup1816699bytes.
F16/F17 integrated recovery then timed out at60s, leaving its result Failed. Outer
campaign records Incomplete/TimeoutError; preserve both scopes and all raw evidence.
Source and target cleanup0connections/0advisory locks; candidate/runner unchanged.

Root cause identified from code and read-only DB evidence: recover() passes target
engines to publisher/parent readers, but f15.run_worker_process() constructs its own
ENGINE/ENGINE_SCAN using ambient source-role URLs. Thus parent waited for target
while worker serviced source. On source, the staged pending receipt and retry became
REJECTED/ORDER_SAFETY_UNAVAILABLE and retry attempt advanced to4; on target both
results remained absent and retry attempt2. These are isolated synthetic fixture
DBs, not user/live data. Never treat target non-progress as a need for larger timeout.
Evidence:source-versus-restored-worker-effects.json/restored-state-snapshot.json,
traceback atprofile_internal_restore.py recover andprofile_workload.py worker setup.

No final integrated pending/exit/retry/idempotency acceptance claimed. No source fix
or new run after this failed gate. W1§16/W2§20/overflow§20/shortW3§22 remain Passed;
4h Release and fullF17 dependencies/required CI remain pending. Next proposed§23
routes only W4 worker engines explicitly to target with unchanged factory defaults,
checks source unchanged, targeted real-DB/default-path regressions and one W4 rerun.
No repeated long workload is proposed.


NC12 §23 implemented/checked,2026-11-07. Optional synchronous test-worker engine
factory defaults to the original role factory lookup. Restored recovery constructs
independent worker-owned target ENGINE/ENGINE_SCAN using scoped role URLs during
synchronous construction only; source env restored before any await. Pool/credential/
scheduling/financial defaults unchanged. Verify compares full source canonical data
(including extensions) before/after target recovery and requires source_unchanged.

Targeted125unique cases covered:124passed in shared suite; the empty-source test
was run after a seeding test and failed its isolation prerequisite, then passed on
a separate fresh DB. Six routing/digest cases rechecked after test import correction
passed1.66s; empty prerequisite passed1.65s. Real two-DB SELECT current_database
proof for both roles plus normal stop/error/cancel cleanup and constructor/config
restoration passed. Scoped Ruff/format/mypy passed3files. Preserve initial logs.
No production change; prior long workload/safety evidence remains applicable to
unchanged default worker path. Required CI/full-regression not replaced by these
partitioned local checks; database-empty cases require isolated fixture execution.

Next: one approved fresh-source/fresh-target W4 with same preflight/fixtures/
backup/restore/60s recovery criterion and strengthened source-unchanged proof,
estimated5–10min. Do not repeat W1/W2/overflow/shortW3. Failed/incomplete stops;
pass closes this local integrated validation checkpoint only, with existing
review/CI/4h Release/bot/notification/Live obligations still separately pending.


NC12 §23 W4 — Passed,2026-11-07. Total148.403s including120s preflight.
Real backup/restore canonical data and RLS/grants match. Domain replay21episodes,
61evidence records,20checkpoints,18positions; one expired legacy claim recovered
with no economic effects. Backup1817181bytes. F16/F17 integrated recovery Passed:
restored-owner RLS,pending receipt identity,exact retry and0duplicate exit/fill.
Source canonical data unchanged=True. Source/target cleanup0connections/0advisory
locks, candidate/runner unchanged. Evidence:nc12-section23-w4/.

W1§16,W2§20,overflow§20,shortW3§22 and W4§23 local campaign gates now all Passed in
their declared internal profiles. This is not the100-account/4h Release profile or
F17 Completed. Current recovery candidate still requires final review/required CI
and production-admission/opening-gate audit/authorization; original bot/notification/
Live dependencies remain. No Git/deploy/activation performed. See aggregate receipt.

Aggregate:[internal local campaign receipt](features/2026-11-02-tp-sl/evidence/recovery-20261106/internal-pilot-local-checkpoint-20261107.md).

Recovery review test-isolation finding locally resolved2026-11-07; final remote CI
and other gates above remain pending. No F17 status change.
[Fix/check evidence](features/2026-11-02-tp-sl/evidence/recovery-20261106/review-fixture-fix.md).

Owner-authorized fixture refactor and affected validation done:207/207mixed tests
passed together, scoped static checks passed,0 fixture DBs left. Pending final
candidate CI/admission/opening and Release/dependency gates unchanged; no F17
completion or Git/deploy action. Details in the same evidence receipt.

Owner subsequently authorized recovery commit/push and required CI. Main integrated;
local Python static checks56files passed. Security remains blocked on evidence
UUID/checksum findings pending approved handling; final CI/admission/opening and
Release/dependency gates remain. No merge/deploy/Completed claim.
[Publication checkpoint](features/2026-11-02-tp-sl/evidence/recovery-20261106/publication-checkpoint.md).

Published0961f78 /PR59: required CI Failed (4756passed/5failed; remaining isolated
backend steps Not Run); complete browser E2E and other5CIjobs passed. Security
secrets job timed out at15min, workflow Cancelled/aggregate gate Failed. Local
test-config fixes105passed; security handling proposal needs owner approval before
the next combined candidate. No merge/opening/F17 completion.
[Result and proposal](features/2026-11-02-tp-sl/evidence/recovery-20261106/publication-final-ci.md).

Owner approved evidence-policy Option A. Scoped implementation/negative/parity
checks passed; full current-candidate scan and required CI remain pending. No
15-minute/security/trading-criteria relaxation. Prior Failed/Cancelled results and
F17/opening/Release/dependency status unchanged.
[Option A receipt](features/2026-11-02-tp-sl/evidence/recovery-20261106/evidence-policy-implementation.md).

Option A local full scan/mapping completed169.73s; strict registry validation Failed
because tree adds100column-distinct identities in8fixed blobs. No active exception
expansion, push or new remote-CI run. Owner decision required on the
[exact100-identity extension](features/2026-11-02-tp-sl/tree-occurrence-extension-proposal.md).
Historical results and F17 pending acceptance/dependency gates remain unchanged.

Owner approved the exact100tree extension. Local full history/tree and registry
validation Passed on6d021c4 in146.640s with0blocked/triage; exact48218artifact
identities resolved. Publishing combined candidate for final required CI; local
proof is not remote CI. No merge/deploy/internal opening or F17 completion.
[Current checkpoint](features/2026-11-02-tp-sl/evidence/recovery-20261106/tree-extension-local-checkpoint.md).

12e6204 remote Security Passed7/7. Application CI Failed2cases (4759passed,
31deselected; later isolated steps Not Run), other5jobs/E2E passed on push and PR.
No fourth full CI/fix cycle before owner decision under the3-round rule. Exact
security dataset/matcher remain approved; remaining proposal is two fixture/config
changes, not reduced acceptance. No merge/opening/F17 completion.
[Result/next checkpoint](features/2026-11-02-tp-sl/evidence/recovery-20261106/extension-remote-ci-checkpoint.md).

Owner approved remaining fixture/config Option A. Two specified lines fixed;
51targeted financial/claim/role cases and workflow/static checks passed locally.
Full secret scan and one combined publication/required-CI round pending; old
failures and F17 opening/Release/dependency gates remain unchanged.
[Local checkpoint](features/2026-11-02-tp-sl/evidence/recovery-20261106/remaining-ci-fixtures-local.md).

Remaining fixture/config pre-publication full secret scan Passed on4d997e9 in
132.892s,0blocked/triage, no new security exception/configuration change. Sending
the one authorized combined CI round; remote acceptance remains pending until its
actual final-head result. No opening/merge/F17 completion claim.

### F-12 extension — timeframe 3m — 2026-11-07

สถานะงาน: **Planning — requirements Approved; plan/validation Proposed**.
เจ้าของสั่งเพิ่ม3mและอนุมัติ [requirements](features/2026-11-07-chart-3m/requirements.md)
วันที่2026-11-07. [Plan](features/2026-11-07-chart-3m/plan.md) และ
[validation](features/2026-11-07-chart-3m/validation.md) จัดทำแล้ว รออนุมัติก่อนเขียนโค้ด.
ขอบเขตเพิ่มnative3mให้BTC/ETHตามcatalogเดิม ทั้งhistory/live และshared timeframe
contracts/SQL/readiness/scheduler. ยังไม่มีsource/migration/runtime changeหรือผลtests.
ไม่เปลี่ยนสถานะF17หรือรับรองว่าF12Completed; workloadรวมที่กระทบคงPending Full Validation.

Review follow-up: Medium workloadtraceabilityแก้ในproposalแล้ว โดยแยกRelease
V3-10A(F12 chart) / V3-10B(F11 preparedตามF38 combinedphases) และระบุruntime18
แยกจากBTCworkload9series. ยังไม่มีsource/migration/tests/campaign; High missing
implementationคงOpenจนplan/validationได้รับอนุมัติและimplementจริง ไม่ถือว่าปิดfinding
จากการแก้เอกสาร. ขั้นถัดไปรออนุมัติplan/validationฉบับแก้ไขก่อนเขียนโค้ด


3m implementation checkpoint2026-11-07: requirements/plan/validation Approved;
core/nativeadapter/UI/contracts and draft0066 implemented, targeted proof Partial.
Source proof/READY-state preservation conflicts with mandatory maintenance;
[NC-3M-01 Approved A — replacement safety checks pending](features/2026-11-07-chart-3m/source-maintenance-amendment.md)
authorizes existing maintenance/rebuild; replacement safety checks pending. Independent checks and retained
failures are in [candidate evidence](features/2026-11-07-chart-3m/evidence/candidate.md).
Owner runtime stays0065/no3m. No review-ready/completion/commit/push/merge claim;
next complete approved A implementation and targeted validation before Ready for Code Review.


3m checkpoint2026-11-07 after NC-3M-01 A: **Ready for Code Review**.
Migration maintenance/rebuild contract implemented; isolated DB14, fresh regressions310,
native/preview/candleAPI113, chartAPI39 and browser1+3 passed; frontend50/scoped static
checks passed. Retained failures and scope in [candidate receipt](features/2026-11-07-chart-3m/evidence/candidate.md).
Owner runtime0065 unchanged. Review/refactor/required CI and local activation pending;
Release V3-10A/B Pending Full Validation. No F17 completion or merge claim.
Next await owner `review code`; do not start review automatically.


3m review correction2026-11-07: owner review completed; M1 browser series identity
and M2 populated-cursor migration/fairness gaps addressed. Targeted cursor2 + browser1/3
passed; affected static checks passed. Existing production checks remain valid.
Next await owner `refactor the code` per AGENTS; required CI, Release workloads and local
activation remain pending. No commit/push/merge or F17 completion change.


3m refactor checkpoint2026-11-07: authorized scoped refactor completed without runtime
behavior changes. Cursor2 and browser1+3 affected checks plus scoped static checks passed.
See current [candidate receipt](features/2026-11-07-chart-3m/evidence/candidate.md).
Review findings addressed; required CI/full regression remains before merge, Release
V3-10A/B Pending Full Validation. Owner local0065 unchanged. Next requires owner Git
instruction to commit/push/open PR and then track CI; no completion/merge claim.


3m PR60 first CI15de827: backend Failed1/4790passed due to harness schema0065 pin;
other CI jobs and Security passed. Updated only checkpoint-harness candidate pin to0066,
kept exact original function verification;24targeted tests/static checks passed.
Replacement CI required before local activation; owner runtime still0065. No merge.


3m PR60 f4464c0 browser CI Failed1/18passed from async response-body predicate race.
Test-only serialized response reading correction passed full chart browser8/8 plus
ESLint/TypeScript. Other completed gates passed; latest-candidate CI still required.
Owner local remains0065; no migration/merge occurred.


3m PR60 a9faaf7: browser CI Failed1/18passed again (CDP response body retrieval),
local8/8passed. Third CI candidate remains not accepted. Stop before another trial per
AGENTS; [observer proposal](features/2026-11-07-chart-3m/browser-response-observer-amendment.md)
awaits owner decision. Follow already-running backend to completion; local remains0065.


3m PR60 a9faaf7 CI completion: backend4794main tests + all isolation/migration gates,
frontend/API contract/container and Security Passed. Browser remains Failed1/18passed
at live-body/CDP retrieval. All started jobs finished; no fourth trial. Await owner
A/B decision on browser observer proposal per AGENTS. Local remains0065; no merge.
Stop-checkpoint documents remain uncommitted to avoid a documentation-only CI loop.


3m observer A explicitly approved: test-only native fetch observer implemented without
production or threshold changes. Full chart browser8/8passed46.7s and scoped static
checks passed. One approved replacement required CI next; pass then local activation,
otherwise stop/report. Prior CI failures preserved; owner local still0065 at this point.


3m observer89259c1: browser E2E now Passed. Security Failed at candidate identity before
scans after main advanced viaPR61; base/merge-parent mismatch. Backend still running;
follow started jobs to completion. One approved CI round consumed, local unchanged.
[Base-refresh replacement proposal](features/2026-11-07-chart-3m/ci-base-refresh-amendment.md)
requires owner decision; no security policy changes or automatic retries.


3m observer checkpoint2026-11-08: CI42392101171 on89259c1/test-mergec5b9039 Passed
(backend4814 + all isolation/migration gates; all browser suites includingnative3m;
frontend/contracts/container). Security42392101117 Failed before scans at base identity
mismatch after main advanced to1237bf6. All jobs finished. Base-refresh proposal awaits
owner; no extra trial/local migration/PR merge. Local stays0065. Stop receipt uncommitted.


### F-17 current blocker checkpoint — 2026-11-08

**Current: Manual Paper acceptance Failed / remediation pending implementation.**
This supersedes the older next-step instruction to prepare invited access; it does
not alter passing CI/workload results on their original candidates and profiles.
Two manual BUYs partially filled and ended EXPIRED; both protections FAILED with
PROTECTION_SETUP_REJECTED. Stored net0.00131868BTC/step0.00001BTC reproduces
QUANTITY_NOT_ON_STEP. Local stop authority was not configured; no durable stop
request was found. Further source review reproduced browser storage errors that
prevent STOP dispatch and hide the failure. No duplicate economic effect is claimed.

[NC-F17-MANUAL-01 requirements](features/2026-11-02-tp-sl/manual-acceptance-fix-proposal.md)
MR-01–11 Approved A. The revised
[plan](features/2026-11-02-tp-sl/manual-acceptance-fix-plan.md) and
[validation](features/2026-11-02-tp-sl/manual-acceptance-fix-validation.md) remain
Proposed, including storage-failure recovery and actual stop readiness before
admission. Quantity/stop source fixes have not been implemented or tested.
Owner positions and financial history remain intact; publication/financial/
admission/protection gates are off after manual acceptance. No automatic sale,
wallet reset, re-arm of FAILED groups or Live order occurred.

Next: owner approval of the revised plan/validation, then implementation/targeted
safety checks and the existing review/refactor/CI gates. Do not reopen manual Paper
or schedule invited access from the old checkpoint. Full F17 is not Completed;
100-account/4h, bot/notification/Live obligations remain Pending Full Validation /
Dependency. No long workload rerun is required merely to update this status.


### F-17 remediation implementation checkpoint — 2026-11-08

Owner approved revised plan/validation. Net-fee aligned sizing, exact residual
reporting, durable exit sizing, browser-storage-safe STOP and scoped local launcher
preparation are implemented in an isolated worktree based on current main e6b32bb.
[Evidence](features/2026-11-02-tp-sl/evidence/manual-acceptance-fix/implementation-checkpoint.md).
Local scoped tests/static checks pass as recorded; original manual failure remains
Failed and original owner positions/history are intact. The prepared launcher has
not been started; owner Paper admission/financial/publication/protection remain off.
Next: owner review of this fix, then findings/refactor/affected validation according
to AGENTS.md. Required CI awaits owner-authorized publication; manual replacement
awaits the approved post-review checkpoint. No commit/push/deployment/Live order.
F17 is not Completed; original Release/dependency obligations remain pending.

### F-17 STOP review fix — 2026-11-08

Owner reviewed the remediation and authorized fixing the High stale STOP-key
finding. Fixed locally: fresh identity after resume despite failed journal cleanup,
server receipt/status recovery after remount, and no old-owner continuation into a
STOP after account switch.16targeted STOP tests and affected frontend lint/types
passed; [evidence](features/2026-11-02-tp-sl/evidence/manual-acceptance-fix/stop-review-fix.md).
Next gate is owner authorization for refactor, followed by affected validation.
No commit/push/deployment or manual replacement; Paper activation remains closed
and full F17 Release/dependency obligations remain pending.

### F-17 refactor / manual-profile checkpoint — 2026-11-08

Owner-authorized refactor complete;16STOP tests and affected frontend lint/types
passed. Candidate now serves owner local with compatible workers; source recovered
and risk reached READY, preserving selected financial/protection facts. Before
owner manual actions, found MF-13 expects resume on an actual MANUAL account, but
F19 source/spec allow only BOT resume. All four Paper gates are off again; no
agent orders, owner-account type change or reset. Original manual Failed remains.
[Evidence](features/2026-11-02-tp-sl/evidence/manual-acceptance-fix/refactor-checkpoint.md).
Next is the owner decision on [MF-13 A/B mapping](features/2026-11-02-tp-sl/manual-profile-clarification.md),
not a new refactor approval. MF-13 replacement remains Not Run / Pending Clarification;
Git publication/required CI and full Release dependencies remain pending.


### F-17 MF-13 decision — 2026-11-08

Owner approved [MANUAL-compatible option A](features/2026-11-02-tp-sl/manual-profile-clarification.md).
Clarification resolved; owner STOP/completion and expected unavailable resume are
pending in one replacement round. Retained isolated BOT proof is scoped separately.
Original manual Failed, required CI and Release dependencies remain unchanged.
All four Paper gates off; no agent trading action. Next: owner Paper STOP in local UI.


### F-17 owner manual observations / cleanup — 2026-11-08

Approved-A MANUAL STOP/completion, expected disabled resume, owner REPLACE→ARMED
with0.00131BTC coverage/0.00000868BTC residual, and CANCEL→CANCELED observed.
No exit/new order during the round; guarded cleanup completed, all four gates off.
MF-13 remains Partial for observed warning contrast. Required CI/publication and
Release dependencies pending; F17 is not Completed.
[Evidence](features/2026-11-02-tp-sl/evidence/manual-acceptance-fix/owner-stop-observation.md).
Next: address warning contrast and affected validation; Git publication still
requires owner instruction.


### F-17 warning readability correction — 2026-11-08

Restored shared template Alert variant/dark colors by excluding it from the legacy
role-alert error skin.33affected component tests, types/lint and isolated browser
light/dark styles passed; no owner-state/business change or repeated manual round.
[Evidence](features/2026-11-02-tp-sl/evidence/manual-acceptance-fix/alert-readability-checkpoint.md).
Next: owner-requested final-candidate review, then authorized Git/required CI;
Release dependencies remain pending. No Completed or merge-ready claim.


### F-17 compact protection table — 2026-11-08

Owner-approved Binance-style presentation implemented with current/issues and
history tabs, compact rows and read-only details; no venue-native OCO claim.
43component tests, scoped lint/types and10isolated browser scenario groups passed.
[Checkpoint](features/2026-11-02-tp-sl/evidence/manual-acceptance-fix/table-ui/checkpoint.md).
Local app stopped/Docker unavailable; no runtime gate opening or account action.
Next: owner-commanded UI review, local startup, authorized Git/required CI; existing
Release dependencies remain pending. F17 is not Completed.


### F-17 unified trading activity — 2026-11-08

Approved single OPEN/HISTORY navigation with Normal/TP-SL subtabs implemented.
Separate card removed; warnings and unknown-request recovery remain visible,
with original identity preserved across navigation.52distinct scoped tests and
8isolated browser scenarios passed; final lint/types passed. Local serves new UI,
all four trading gates off. [Evidence](features/2026-11-02-tp-sl/evidence/manual-acceptance-fix/unified-ui/checkpoint.md).
Next: owner-commanded final UI review; required CI/publication and Release pending.
No commit/push/merge or F17 Completed claim.


### F-17 single-row activity correction — 2026-11-08

Owner-approved one toolbar/one mixed table replaces category subtabs. Real orders
and app-monitored conditions remain distinct; cross-symbol protection actions use
their original row.56distinct targeted tests and8isolated browser scenarios passed;
final lint/types passed. [Evidence](features/2026-11-02-tp-sl/evidence/manual-acceptance-fix/single-row-ui/checkpoint.md).
Local source served, all four gates off, no agent economic mutation. Next owner-
commanded UI review; required CI/publication and F17 Release dependencies pending.
No Completed or merge-ready claim.


### F-17 review corrections — 2026-11-08

Owner-requested High stale STOP receipt and Medium queued-exit display findings
fixed locally.64affected tests, lint/types and6isolated browser cases passed.
[Evidence](features/2026-11-02-tp-sl/evidence/manual-acceptance-fix/review-corrections/checkpoint.md).
No agent financial mutation/gate opening or Git publication. Next owner instruction
for refactor under AGENTS.md; required CI and Release dependencies remain pending.
F17 is not Completed.


### F-17 review-correction refactor — 2026-11-08

Owner-authorized refactor and affected validation complete:64tests,6isolated
browser cases and scoped lint/types passed. Reused STOP recovery error policy
and fixture; exit display formatting unchanged.
[Evidence](features/2026-11-02-tp-sl/evidence/manual-acceptance-fix/review-corrections/refactor-checkpoint.md).
All gates off; no owner mutations or Git publication. Next owner Git instruction
for final candidate/required CI; merge and Release dependencies remain gated.
F17 is not Completed.
