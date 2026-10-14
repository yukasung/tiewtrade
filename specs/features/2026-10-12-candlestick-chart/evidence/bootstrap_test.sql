\set ON_ERROR_STOP on
DO $$ BEGIN
  IF current_database() NOT IN ('tiewtrade_f12_test','tiewtrade_e2e_f12') THEN
    RAISE EXCEPTION 'F12_TEST_DATABASE_REJECTED';
  END IF;
  EXECUTE format('ALTER DATABASE %I SET log_parameter_max_length=0',current_database());
  EXECUTE format('ALTER DATABASE %I SET log_parameter_max_length_on_error=0',current_database());
  EXECUTE format('ALTER DATABASE %I SET log_error_verbosity=terse',current_database());
  EXECUTE format('ALTER DATABASE %I SET log_statement=none',current_database());
  EXECUTE format('ALTER DATABASE %I SET log_min_duration_statement=-1',current_database());
  EXECUTE format('REVOKE ALL ON DATABASE %I FROM PUBLIC',current_database());
  EXECUTE format('GRANT CONNECT ON DATABASE %I TO tiewtrade_migrator,tiewtrade_api,tiewtrade_auth,
    tiewtrade_engine,tiewtrade_engine_scan,tiewtrade_market_data,tiewtrade_indicator_builder',current_database());
END $$;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO tiewtrade_migrator,tiewtrade_api,tiewtrade_auth,
  tiewtrade_engine,tiewtrade_engine_scan,tiewtrade_market_data,tiewtrade_indicator_builder;
