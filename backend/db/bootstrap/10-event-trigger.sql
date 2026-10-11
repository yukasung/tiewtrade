-- ดักการสร้างและการผูกพาร์ทิชัน แล้วปิดพาร์ทิชันใหม่ให้เอง (F-04, plan.md ข้อ 1.1)
--
-- `CREATE EVENT TRIGGER` ต้องใช้ superuser ซึ่งเป็นสิ่งที่บทบาทที่รัน migration
-- ต้องไม่มี (F-03 RQ-5.1) จึงอยู่ที่นี่ ไม่ใช่ใน migration
--
-- **ไฟล์นี้รันซ้ำได้** และใช้ติดตั้งกับฐานข้อมูลที่ bootstrap ไปแล้วได้ด้วย:
--   psql "$SUPERUSER_URL" -v ON_ERROR_STOP=1 -f backend/db/bootstrap/10-event-trigger.sql
-- หลังติดตั้งแล้ว ให้ปิดพาร์ทิชันที่ค้างอยู่ด้วยการรัน migration หรือสั่ง
--   SELECT tiewtrade_protect_all_partitions();
-- ด้วยบทบาทที่เป็นเจ้าของตาราง
--
-- **ขอบเขต: กันความผิดพลาดของคนทำงานปกติ ไม่ใช่รับประกันป้องกัน superuser**
-- (เจ้าของกำหนด 2026-09-27) คนที่เป็น superuser ปิด event trigger นี้ได้
-- เหมือนที่ปิด trigger อื่นได้ — ดู F-04 RQ-20
--
-- ฟังก์ชันที่ event trigger เรียกอยู่ใน migration 0006 และตัวมันตรวจเองว่ากลไก
-- ถูกติดตั้งแล้วหรือยัง ฉะนั้นติดตั้ง event trigger ก่อนรัน migration ได้ ไม่พัง

\set ON_ERROR_STOP on

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_event_trigger WHERE evtname = 'tiewtrade_protect_partitions'
    ) THEN
        -- ฟังก์ชันอาจยังไม่มีตอนรันไฟล์นี้ (ฐานข้อมูลใหม่ที่ยังไม่รัน migration)
        -- จึงสร้างตัวชั่วคราวที่ไม่ทำอะไรไว้ก่อน แล้ว migration 0006 จะเขียนทับด้วยตัวจริง
        IF to_regprocedure('tiewtrade_protect_partitions_on_ddl()') IS NULL THEN
            CREATE FUNCTION tiewtrade_protect_partitions_on_ddl() RETURNS event_trigger
                LANGUAGE plpgsql
            AS $body$
            BEGIN
                IF to_regprocedure('tiewtrade_protect_all_partitions()') IS NULL THEN
                    RETURN;
                END IF;
                PERFORM tiewtrade_protect_all_partitions();
            END
            $body$;
            ALTER FUNCTION tiewtrade_protect_partitions_on_ddl() OWNER TO tiewtrade_migrator;
        END IF;

        CREATE EVENT TRIGGER tiewtrade_protect_partitions
            ON ddl_command_end
            WHEN TAG IN ('CREATE TABLE', 'ALTER TABLE')
            EXECUTE FUNCTION tiewtrade_protect_partitions_on_ddl();
    END IF;
END
$$;

-- Source DROP protection is installed separately from ordinary partition hooks.
DO $$ BEGIN
    IF to_regprocedure('public.tiewtrade_indicator_source_on_drop()') IS NULL THEN
        CREATE FUNCTION public.tiewtrade_indicator_source_on_drop() RETURNS event_trigger
            LANGUAGE plpgsql AS $body$ BEGIN RETURN; END $body$;
        ALTER FUNCTION public.tiewtrade_indicator_source_on_drop() OWNER TO tiewtrade_migrator;
    END IF;
    IF NOT EXISTS(SELECT 1 FROM pg_event_trigger WHERE evtname='tiewtrade_indicator_source_drop') THEN
        CREATE EVENT TRIGGER tiewtrade_indicator_source_drop ON sql_drop
            EXECUTE FUNCTION public.tiewtrade_indicator_source_on_drop();
    END IF;
END $$;
REVOKE ALL ON FUNCTION public.tiewtrade_indicator_source_on_drop() FROM PUBLIC;

-- CREATE OR REPLACE TRIGGER can change a journal without dropping its name.
DO $$ BEGIN
    IF to_regprocedure('public.tiewtrade_indicator_source_on_trigger_ddl()') IS NULL THEN
        CREATE FUNCTION public.tiewtrade_indicator_source_on_trigger_ddl() RETURNS event_trigger
            LANGUAGE plpgsql AS $body$ BEGIN RETURN; END $body$;
        ALTER FUNCTION public.tiewtrade_indicator_source_on_trigger_ddl() OWNER TO tiewtrade_migrator;
    END IF;
    IF NOT EXISTS(SELECT 1 FROM pg_event_trigger WHERE evtname='tiewtrade_indicator_trigger_ddl') THEN
        CREATE EVENT TRIGGER tiewtrade_indicator_trigger_ddl ON ddl_command_end
            WHEN TAG IN ('CREATE TRIGGER')
            EXECUTE FUNCTION public.tiewtrade_indicator_source_on_trigger_ddl();
    END IF;
END $$;
REVOKE ALL ON FUNCTION public.tiewtrade_indicator_source_on_trigger_ddl() FROM PUBLIC;
