"""Default-off, durable native closure evidence and guarded canonical finality."""

from alembic import op

revision = "0076"
down_revision = "0075"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "GRANT "
        "SELECT(source,owner,epoch,connected,bootstrapped,failure_code,lease_until) "
        "ON market_candle_feed_state TO tiewtrade_engine"
    )
    op.execute("GRANT SELECT(epoch,revision) ON indicator_source_guard TO tiewtrade_market_data")
    op.execute("""CREATE TABLE market_candle_closure_control (
      id integer PRIMARY KEY CHECK(id=1), enabled boolean NOT NULL DEFAULT false,
      policy_version integer NOT NULL DEFAULT 1 CHECK(policy_version=1),
      activation_epoch uuid NOT NULL, recovery_at timestamptz NOT NULL DEFAULT
      clock_timestamp(), inventory jsonb, changed_at timestamptz NOT NULL DEFAULT now())""")
    op.execute("""INSERT INTO market_candle_closure_control(id,activation_epoch)
        VALUES(1,'00000000-0000-4000-8000-000000000076');""")
    op.execute("""CREATE TABLE market_candle_closure_observations (
      id uuid PRIMARY KEY, source text NOT NULL CHECK(source='primary_spot'),
      venue text NOT NULL DEFAULT 'BINANCE_TH' CHECK(venue='BINANCE_TH'),
      market text NOT NULL DEFAULT 'SPOT' CHECK(market='SPOT'),
      symbol_revision bigint NOT NULL REFERENCES supported_symbol_events(revision),
      catalog_revision bigint NOT NULL REFERENCES supported_symbol_events(revision),
      base tiewtrade_unit_code NOT NULL, quote tiewtrade_unit_code NOT NULL CHECK(quote='USDT'),
      timeframe text NOT NULL CHECK(timeframe IN ('1m','3m','5m','15m','1h','4h','1d','1w','1M')),
      open_at timestamptz NOT NULL, end_at timestamptz NOT NULL CHECK(end_at>open_at),
      open tiewtrade_money_amount NOT NULL CHECK(open>0),
      high tiewtrade_money_amount NOT NULL CHECK(high>0),
      low tiewtrade_money_amount NOT NULL CHECK(low>0),
      close tiewtrade_money_amount NOT NULL CHECK(close>0),
      volume tiewtrade_money_amount NOT NULL CHECK(volume>=0),
      trade_count bigint NOT NULL CHECK(trade_count>=0),
      first_trade_id bigint NOT NULL CHECK(first_trade_id>=-1),
      last_trade_id bigint NOT NULL CHECK(last_trade_id>=first_trade_id),
      closed_hint boolean NOT NULL CHECK(closed_hint),
      event_at timestamptz NOT NULL, received_at timestamptz NOT NULL CHECK(received_at>=end_at),
      writer_id uuid NOT NULL, writer_epoch bigint NOT NULL CHECK(writer_epoch>0),
      activation_epoch uuid NOT NULL,
      fingerprint text NOT NULL CHECK(fingerprint ~ '^[0-9a-f]{64}$'),
      created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      CHECK(high>=open AND high>=close AND low<=open AND low<=close AND high>=low),
      UNIQUE(source,base,quote,timeframe,open_at,writer_id,writer_epoch,activation_epoch,fingerprint),
      UNIQUE(id,source,base,quote,timeframe,open_at));""")
    op.execute("""CREATE TABLE market_candle_closure_results (
      id uuid PRIMARY KEY, observation_id uuid NOT NULL REFERENCES
      market_candle_closure_observations(id),
      outcome text NOT NULL CHECK(outcome IN ('MATCHED','CONFLICT','INVALIDATED')),
      fingerprint text NOT NULL CHECK(fingerprint ~ '^[0-9a-f]{64}$'),
      previous_result_id uuid REFERENCES market_candle_closure_results(id),
      canonical jsonb NOT NULL CHECK(jsonb_typeof(canonical)='object'),
      fetch_started_at timestamptz NOT NULL, observed_at timestamptz NOT NULL,
      policy_version integer NOT NULL CHECK(policy_version=1),
      activation_epoch uuid NOT NULL,
      source_epoch uuid NOT NULL, source_fence bigint NOT NULL CHECK(source_fence>=0),
      recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      UNIQUE(id,observation_id));""")
    op.execute("""CREATE TABLE market_candle_closure_state (
      source text NOT NULL CHECK(source='primary_spot'), base tiewtrade_unit_code NOT NULL,
      quote tiewtrade_unit_code NOT NULL, timeframe text NOT NULL, open_at timestamptz NOT NULL,
      observation_id uuid NOT NULL REFERENCES market_candle_closure_observations(id),
      result_id uuid REFERENCES market_candle_closure_results(id),
      recovery_at timestamptz,
      status text NOT NULL CHECK(status IN ('WAITING_REST','MATCHED','CONFLICT','INVALIDATED')),
      PRIMARY KEY(source,base,quote,timeframe,open_at),
      FOREIGN KEY(observation_id,source,base,quote,timeframe,open_at) REFERENCES
        market_candle_closure_observations(id,source,base,quote,timeframe,open_at),
      FOREIGN KEY(result_id,observation_id) REFERENCES
      market_candle_closure_results(id,observation_id));""")
    op.execute(
        "ALTER TABLE market_candles ADD COLUMN closure_proof_id uuid REFERENCES "
        "market_candle_closure_results(id)"
    )
    for table in ("market_candle_closure_observations", "market_candle_closure_results"):
        op.execute(f"SELECT tiewtrade_make_append_only('{table}'::regclass)")
        op.execute(f"GRANT SELECT,INSERT ON {table} TO tiewtrade_market_data")
        op.execute(
            f"GRANT SELECT ON {table} TO tiewtrade_engine,tiewtrade_api,tiewtrade_indicator_builder"
        )
    op.execute(
        "GRANT SELECT,INSERT,UPDATE,DELETE ON market_candle_closure_state TO tiewtrade_market_data"
    )
    op.execute(
        "GRANT SELECT ON market_candle_closure_state,market_candle_closure_control TO "
        "tiewtrade_market_data,tiewtrade_engine,tiewtrade_api,tiewtrade_indicator_builder"
    )
    op.execute(
        "GRANT UPDATE(recovery_at) ON market_candle_closure_control TO tiewtrade_market_data"
    )
    op.execute("""CREATE FUNCTION candle_closure_triggers_valid() RETURNS boolean
      LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$
      WITH RECURSIVE partitions(relid) AS (
        SELECT 'public.market_candles'::regclass::oid UNION
        SELECT i.inhrelid FROM pg_inherits i JOIN partitions p ON i.inhparent=p.relid
      ) SELECT NOT EXISTS(SELECT 1 FROM partitions p WHERE NOT EXISTS(
        SELECT 1 FROM pg_trigger t WHERE t.tgrelid=p.relid
        AND t.tgname='candle_closure_write_guard' AND t.tgtype=23
        AND t.tgfoid=to_regprocedure('public.guard_candle_closure_write()')
        AND t.tgenabled='O' AND NOT t.tgisinternal AND t.tgnargs=0
        AND t.tgqual IS NULL AND t.tgattr=''::int2vector)) $$""")
    op.execute("REVOKE ALL ON FUNCTION candle_closure_triggers_valid() FROM PUBLIC")
    op.execute(
        "GRANT EXECUTE ON FUNCTION candle_closure_triggers_valid() "
        "TO tiewtrade_market_data,tiewtrade_engine,tiewtrade_api,tiewtrade_indicator_builder"
    )
    op.execute("""CREATE FUNCTION activate_candle_closure(p_enabled boolean,p_inventory jsonb)
      RETURNS void LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$ BEGIN
      PERFORM public.begin_indicator_source_write();
      IF p_enabled AND (p_inventory->'legacy_writers_drained' IS DISTINCT FROM 'true'::jsonb
        OR p_inventory->'legacy_restart_disabled' IS DISTINCT FROM 'true'::jsonb
        OR p_inventory->'readers_compatible' IS DISTINCT FROM 'true'::jsonb
        OR NOT coalesce(p_inventory->>'candidate_sha' ~ '^[0-9a-f]{40,64}$',false)
        OR p_inventory->'paper_only' IS DISTINCT FROM 'true'::jsonb
        OR NOT EXISTS(SELECT 1 FROM indicator_rollout_control WHERE source_proof_state='READY')
        OR NOT public.indicator_source_triggers_valid()
        OR NOT public.candle_closure_triggers_valid())
      THEN RAISE EXCEPTION 'closure activation evidence incomplete'; END IF;
      IF NOT p_enabled AND (p_inventory->'admission_paused' IS DISTINCT FROM 'true'::jsonb)
      THEN RAISE EXCEPTION 'pause admission before deactivation'; END IF;
      IF EXISTS(SELECT 1 FROM market_candle_closure_control
        WHERE enabled=p_enabled AND inventory=p_inventory) THEN RETURN; END IF;
      UPDATE market_candle_closure_control SET enabled=p_enabled,inventory=p_inventory,
      changed_at=clock_timestamp(),recovery_at=clock_timestamp(),activation_epoch=gen_random_uuid()
      WHERE id=1;
      END $$""")
    op.execute("REVOKE ALL ON FUNCTION activate_candle_closure(boolean,jsonb) FROM PUBLIC")
    op.execute("""CREATE FUNCTION guard_candle_closure_write() RETURNS trigger LANGUAGE plpgsql
      SECURITY DEFINER SET search_path=pg_catalog,public AS $$
      DECLARE enabled_now boolean; activation uuid; proof record; evidence record; BEGIN
      SELECT enabled,activation_epoch INTO enabled_now,activation
      FROM market_candle_closure_control WHERE id=1;
      IF NOT enabled_now THEN
        IF NEW.closure_proof_id IS NOT NULL AND (TG_OP='INSERT' OR
          NEW.closure_proof_id IS DISTINCT FROM OLD.closure_proof_id)
        THEN RAISE EXCEPTION 'closure protocol disabled' USING ERRCODE='42501'; END IF;
        RETURN NEW;
      END IF;
      IF current_setting('tiewtrade.candle_closure_writer',true) IS DISTINCT FROM '1'
      THEN RAISE EXCEPTION 'incompatible closure writer' USING ERRCODE='42501'; END IF;
      IF NEW.finality='CLOSED' THEN
        SELECT * INTO proof FROM market_candle_closure_results WHERE id=NEW.closure_proof_id;
      SELECT * INTO evidence FROM market_candle_closure_observations WHERE
      id=proof.observation_id;
        IF proof.outcome IS DISTINCT FROM 'MATCHED'
          OR proof.activation_epoch IS DISTINCT FROM activation
          OR proof.policy_version IS DISTINCT FROM 1
          OR proof.observed_at<proof.fetch_started_at
          OR proof.observed_at>clock_timestamp()
      OR
      (evidence.source,evidence.base,evidence.quote,evidence.timeframe,evidence.open_at,evidence.end_at,
              evidence.open,evidence.high,evidence.low,evidence.close,evidence.volume)
             IS DISTINCT FROM
             (NEW.source,NEW.base,NEW.quote,NEW.timeframe,NEW.open_at,NEW.end_at,
              NEW.open,NEW.high,NEW.low,NEW.close,NEW.volume)
          OR proof.fetch_started_at<NEW.end_at
          OR NOT EXISTS(SELECT 1 FROM market_candle_closure_state s
            WHERE (s.source,s.base,s.quote,s.timeframe,s.open_at)=
              (NEW.source,NEW.base,NEW.quote,NEW.timeframe,NEW.open_at)
            AND s.result_id=proof.id AND s.status='MATCHED')
        THEN RAISE EXCEPTION 'matching closure proof required' USING ERRCODE='42501'; END IF;
      ELSIF TG_OP='UPDATE' AND OLD.finality='CLOSED' THEN
        IF NOT EXISTS(SELECT 1 FROM market_candle_closure_state s
          WHERE (s.source,s.base,s.quote,s.timeframe,s.open_at)=
            (NEW.source,NEW.base,NEW.quote,NEW.timeframe,NEW.open_at)
          AND s.status IN ('CONFLICT','INVALIDATED'))
        THEN RAISE EXCEPTION 'closure invalidation required' USING ERRCODE='42501'; END IF;
      END IF;
      IF TG_OP='UPDATE' AND NEW.closure_proof_id IS DISTINCT FROM OLD.closure_proof_id THEN
        INSERT INTO public.indicator_source_changes
        SELECT g.epoch,g.revision,NEW.source,NEW.base,NEW.quote,NEW.timeframe,NEW.open_at,'WRITE'
        FROM public.indicator_source_guard g WHERE id=1 ON CONFLICT DO NOTHING;
      END IF;
      RETURN NEW; END $$""")
    op.execute("REVOKE ALL ON FUNCTION guard_candle_closure_write() FROM PUBLIC")
    op.execute("""CREATE TRIGGER candle_closure_write_guard
        BEFORE INSERT OR UPDATE ON market_candles
        FOR EACH ROW EXECUTE FUNCTION guard_candle_closure_write();""")


def downgrade() -> None:
    op.execute("""DO $$ BEGIN
      IF EXISTS(SELECT 1 FROM market_candle_closure_control WHERE enabled)
        OR EXISTS(SELECT 1 FROM market_candle_closure_observations)
      THEN RAISE EXCEPTION 'closure history or activation prevents downgrade'; END IF; END $$""")
    op.execute(
        "REVOKE "
        "SELECT(source,owner,epoch,connected,bootstrapped,failure_code,lease_until) "
        "ON market_candle_feed_state FROM tiewtrade_engine"
    )
    op.execute("REVOKE SELECT(epoch,revision) ON indicator_source_guard FROM tiewtrade_market_data")
    op.execute("DROP TRIGGER candle_closure_write_guard ON market_candles")
    op.execute("ALTER TABLE market_candles DROP COLUMN closure_proof_id")
    op.execute("DROP FUNCTION candle_closure_triggers_valid()")
    op.execute("DROP FUNCTION guard_candle_closure_write()")
    op.execute("DROP FUNCTION activate_candle_closure(boolean,jsonb)")
    op.execute(
        "DROP TABLE "
        "market_candle_closure_state,market_candle_closure_results,market_candle_closure_observations,market_candle_closure_control"
    )
