-- บทบาทฐานข้อมูลของ F-03 (plan.md ข้อ 1)
--
-- แยกจาก migration เพราะ CREATE ROLE เป็นคำสั่งระดับ cluster และต้องใช้สิทธิ์สูงกว่า
-- ที่บทบาทซึ่งรัน migration ควรมี (RQ-5.1) ไฟล์นี้จึงรันด้วย superuser ของ container
-- ครั้งเดียวตอนตั้งเครื่อง
--
-- **รหัสผ่านในไฟล์นี้ใช้ได้เฉพาะเครื่องนักพัฒนาและ CI**
-- บนเครื่องจริงต้องตั้งค่าคนละชุดและเก็บที่อื่น — เป็นงาน F-31 (ดู requirements.md
-- หัวข้อ "ยังไม่ชัด") ห้ามนำไฟล์นี้ไปใช้บนเครื่องจริง

\set ON_ERROR_STOP on

-- ── เจ้าของโครงสร้าง ใช้เฉพาะตอนรัน migration ─────────────────────────────
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'tiewtrade_migrator') THEN
        CREATE ROLE tiewtrade_migrator LOGIN PASSWORD 'dev_migrator';
    END IF;
END
$$;

-- ── บทบาทที่ใช้ตอนทำงานปกติ ทุกตัวอยู่ใต้ RLS ────────────────────────────
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'tiewtrade_api') THEN
        CREATE ROLE tiewtrade_api LOGIN PASSWORD 'dev_api';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'tiewtrade_engine') THEN
        CREATE ROLE tiewtrade_engine LOGIN PASSWORD 'dev_engine';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'tiewtrade_market_data') THEN
        CREATE ROLE tiewtrade_market_data LOGIN PASSWORD 'dev_market_data';
    END IF;
    -- บทบาทของเส้นทางยืนยันตัวตน (F-05) — อยู่ใต้ RLS เหมือนบทบาททำงานอื่น
    -- แยกจาก api เพราะเป็นบทบาทเดียวที่แตะข้อมูลเข้าสู่ระบบและออก session ได้
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'tiewtrade_auth') THEN
        CREATE ROLE tiewtrade_auth LOGIN PASSWORD 'dev_auth';
    END IF;
END
$$;

-- ── บทบาทเดียวที่ข้าม RLS — งานกวาดรายการข้ามผู้ใช้เท่านั้น (Q-3) ─────────
-- อ่านอย่างเดียว ไม่มีสิทธิ์เขียนข้อมูลผู้ใช้ และไม่ได้สิทธิ์อ่านคอลัมน์ secret
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'tiewtrade_engine_scan') THEN
        CREATE ROLE tiewtrade_engine_scan LOGIN BYPASSRLS PASSWORD 'dev_engine_scan';
    END IF;
END
$$;

-- ── นโยบาย log ของฐานข้อมูล — ค่าที่ส่งไปต้องไม่ลง log ของ server (RQ-15) ──
--
-- `hide_parameters` ของ SQLAlchemy กันได้แค่ฝั่งแอป ส่วน PostgreSQL มี log ของตัวเอง
-- ที่เขียนคำสั่งและค่าที่ bind ลงไปได้ตามการตั้งค่า ถ้าไม่ปิด ค่าที่เป็นความลับจะไปอยู่ใน
-- log ของฐานข้อมูลโดยที่ฝั่งแอปดู "สะอาด" — เป็นการรั่วที่ไม่มีอะไรเตือนเลย
--
-- ตั้งที่ระดับฐานข้อมูลเพราะใช้ได้ทั้งใน Compose และใน CI ด้วยกลไกเดียวกัน
-- (service container ของ CI ส่ง command ให้ PostgreSQL ไม่ได้)
--
-- `log_error_verbosity = terse` ตัดบรรทัด DETAIL ซึ่งเป็นที่ที่รายการค่าที่ bind โผล่
--
-- **ข้อจำกัดที่ยังเหลือ:** ข้อความข้อผิดพลาดของ PostgreSQL เองอ้างค่าที่ผิดได้
-- (เช่น ค่าที่แปลงเป็น uuid ไม่ได้) ฉะนั้นค่าที่ผิดต้องถูกปฏิเสธ **ก่อน** ส่งไปฐานข้อมูล
-- ซึ่งเป็นกฎเดียวกับ RQ-9.1 ไม่ใช่พึ่งการตั้งค่า log อย่างเดียว
ALTER DATABASE :"DBNAME" SET log_statement = 'none';
ALTER DATABASE :"DBNAME" SET log_min_duration_statement = -1;
ALTER DATABASE :"DBNAME" SET log_parameter_max_length = 0;
ALTER DATABASE :"DBNAME" SET log_parameter_max_length_on_error = 0;
ALTER DATABASE :"DBNAME" SET log_error_verbosity = 'terse';

-- ── ค่าเริ่มต้นคือปฏิเสธ แล้วค่อยเปิดเท่าที่จำเป็น (RQ-5) ─────────────────
REVOKE ALL ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON DATABASE :"DBNAME" FROM PUBLIC;

GRANT CONNECT ON DATABASE :"DBNAME" TO
    tiewtrade_migrator, tiewtrade_api, tiewtrade_engine,
    tiewtrade_engine_scan, tiewtrade_market_data, tiewtrade_auth;

GRANT USAGE ON SCHEMA public TO
    tiewtrade_migrator, tiewtrade_api, tiewtrade_engine,
    tiewtrade_engine_scan, tiewtrade_market_data, tiewtrade_auth;

-- เจ้าของโครงสร้างเท่านั้นที่สร้างของใน schema ได้ (RQ-5.1)
GRANT CREATE ON SCHEMA public TO tiewtrade_migrator;
