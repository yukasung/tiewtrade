"""Paper order/evidence schema and additive quote-cash ledger integration."""

# ruff: noqa: E501 -- keep financial DDL constraints reviewable as complete clauses

from alembic import op

revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None

_IMMUTABLE = (
    "paper_execution_profiles",
    "paper_order_commands",
    "paper_order_command_results",
    "paper_orders",
    "paper_execution_inputs",
    "paper_execution_input_keys",
    "paper_order_events",
    "paper_execution_links",
)
_MUTABLE = (
    "paper_order_activity",
    "paper_order_dispatch",
    "paper_order_projections",
    "paper_reservations",
)


def _owner(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(f"""CREATE POLICY {table}_self ON {table} FOR ALL
      USING(user_id=tiewtrade_current_user_id()) WITH CHECK(user_id=tiewtrade_current_user_id())""")
    op.execute(f"GRANT SELECT,INSERT ON {table} TO tiewtrade_engine")


def upgrade() -> None:
    op.execute("""CREATE TABLE paper_execution_profiles (
      episode_id uuid PRIMARY KEY, wallet_id uuid NOT NULL, user_id uuid NOT NULL,
      mode text NOT NULL DEFAULT 'PAPER' CHECK(mode='PAPER'),
      fee_version text NOT NULL CHECK(fee_version='PAPER_STANDARD_V1'),
      model_version text NOT NULL CHECK(model_version='PAPER_DEPTH_SHADOW_V1'),
      created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(episode_id,wallet_id,user_id),
      FOREIGN KEY(episode_id,wallet_id,user_id) REFERENCES paper_wallet_episodes(id,wallet_id,user_id))""")
    op.execute("""CREATE TABLE paper_order_activity (
      episode_id uuid PRIMARY KEY, wallet_id uuid NOT NULL, user_id uuid NOT NULL,
      mode text NOT NULL DEFAULT 'PAPER' CHECK(mode='PAPER'),
      availability text NOT NULL DEFAULT 'UNKNOWN' CHECK(availability IN ('UNKNOWN','READY','CONFLICTED')),
      source_sequence bigint NOT NULL DEFAULT 0 CHECK(source_sequence>=0),
      revision bigint NOT NULL DEFAULT 0 CHECK(revision>=0), initialization_id uuid,
      source_proof text CHECK(source_proof ~ '^[0-9a-f]{64}$'), observed_at timestamptz, failure_code text,
      FOREIGN KEY(episode_id,wallet_id,user_id) REFERENCES paper_wallet_episodes(id,wallet_id,user_id),
      CHECK((availability='UNKNOWN' AND source_proof IS NULL AND observed_at IS NULL AND failure_code IS NULL)
         OR (availability='READY' AND source_proof IS NOT NULL AND initialization_id IS NOT NULL
             AND observed_at IS NOT NULL AND failure_code IS NULL)
         OR (availability='CONFLICTED' AND observed_at IS NOT NULL AND failure_code IS NOT NULL)))""")
    op.execute("ALTER TABLE paper_wallet_episodes NO FORCE ROW LEVEL SECURITY")
    op.execute("""INSERT INTO paper_order_activity(episode_id,wallet_id,user_id)
      SELECT id,wallet_id,user_id FROM paper_wallet_episodes""")
    op.execute("ALTER TABLE paper_wallet_episodes FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE TABLE paper_order_commands (
      id uuid PRIMARY KEY, user_id uuid NOT NULL, wallet_id uuid NOT NULL, episode_id uuid NOT NULL,
      mode text NOT NULL DEFAULT 'PAPER' CHECK(mode='PAPER'),
      action text NOT NULL CHECK(action IN ('NEW','CANCEL')), idempotency_key uuid NOT NULL,
      order_id uuid NOT NULL, request_fingerprint text NOT NULL CHECK(request_fingerprint ~ '^[0-9a-f]{64}$'),
      payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object'), requested_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE(user_id,action,idempotency_key), UNIQUE(id,user_id,episode_id),
      UNIQUE(id,user_id,episode_id,order_id,action),
      FOREIGN KEY(episode_id,wallet_id,user_id) REFERENCES paper_wallet_episodes(id,wallet_id,user_id))""")
    op.execute("""CREATE TABLE paper_order_command_results (
      command_id uuid PRIMARY KEY, user_id uuid NOT NULL, episode_id uuid NOT NULL,
      state text NOT NULL CHECK(state IN ('SUCCEEDED','REJECTED')), failure_code text,
      snapshot jsonb NOT NULL CHECK(jsonb_typeof(snapshot)='object'), completed_at timestamptz NOT NULL DEFAULT now(),
      FOREIGN KEY(command_id,user_id,episode_id) REFERENCES paper_order_commands(id,user_id,episode_id),
      CHECK((state='SUCCEEDED' AND failure_code IS NULL) OR (state='REJECTED' AND failure_code IS NOT NULL)))""")
    op.execute("""CREATE TABLE paper_order_dispatch (
      command_id uuid PRIMARY KEY, user_id uuid NOT NULL, episode_id uuid NOT NULL,
      state text NOT NULL DEFAULT 'PENDING' CHECK(state IN ('PENDING','CLAIMED','TERMINAL')),
      worker text, claim_id uuid, claim_revision bigint NOT NULL DEFAULT 0 CHECK(claim_revision>=0),
      lease_until timestamptz, attempts integer NOT NULL DEFAULT 0 CHECK(attempts>=0),
      next_attempt_at timestamptz NOT NULL DEFAULT now(),
      FOREIGN KEY(command_id,user_id,episode_id) REFERENCES paper_order_commands(id,user_id,episode_id),
      CHECK((state='CLAIMED' AND worker IS NOT NULL AND claim_id IS NOT NULL AND lease_until IS NOT NULL)
         OR (state<>'CLAIMED' AND worker IS NULL AND claim_id IS NULL AND lease_until IS NULL)))""")
    op.execute(
        "CREATE INDEX paper_order_dispatch_due ON paper_order_dispatch(next_attempt_at,user_id) WHERE state<>'TERMINAL'"
    )
    op.execute("""CREATE TABLE paper_orders (
      id uuid PRIMARY KEY, user_id uuid NOT NULL, wallet_id uuid NOT NULL, episode_id uuid NOT NULL,
      mode text NOT NULL DEFAULT 'PAPER' CHECK(mode='PAPER'),
      command_id uuid NOT NULL UNIQUE, source_action text NOT NULL DEFAULT 'NEW' CHECK(source_action='NEW'),
      sequence bigint NOT NULL CHECK(sequence>0),
      base tiewtrade_unit_code NOT NULL, quote tiewtrade_unit_code NOT NULL CHECK(quote='USDT'),
      origin text NOT NULL CHECK(origin IN ('MANUAL','BOT')), side text NOT NULL CHECK(side IN ('BUY','SELL')),
      kind text NOT NULL CHECK(kind IN ('MARKET','LIMIT')), time_in_force text,
      quantity tiewtrade_money_amount CHECK(quantity>0), budget tiewtrade_money_amount CHECK(budget>0),
      limit_price tiewtrade_money_amount CHECK(limit_price>0), accepted_at timestamptz NOT NULL,
      constraints jsonb NOT NULL CHECK(jsonb_typeof(constraints)='object'),
      UNIQUE(id,user_id,episode_id,base,quote), UNIQUE(user_id,episode_id,sequence),
      FOREIGN KEY(command_id,user_id,episode_id,id,source_action) REFERENCES paper_order_commands(id,user_id,episode_id,order_id,action),
      FOREIGN KEY(episode_id,wallet_id,user_id) REFERENCES paper_execution_profiles(episode_id,wallet_id,user_id),
      CHECK(base<>quote),
      CHECK((kind='MARKET' AND side='BUY' AND budget IS NOT NULL AND quantity IS NULL AND limit_price IS NULL AND time_in_force IS NULL)
         OR (kind='MARKET' AND side='SELL' AND quantity IS NOT NULL AND budget IS NULL AND limit_price IS NULL AND time_in_force IS NULL)
         OR (kind='LIMIT' AND quantity IS NOT NULL AND budget IS NULL AND limit_price IS NOT NULL AND time_in_force IS NOT NULL AND time_in_force='GTC')))""")
    op.execute("""CREATE TABLE paper_execution_inputs (
      recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(), id uuid NOT NULL,
      user_id uuid NOT NULL, wallet_id uuid NOT NULL, episode_id uuid NOT NULL,
      mode text NOT NULL DEFAULT 'PAPER' CHECK(mode='PAPER'),
      base tiewtrade_unit_code NOT NULL, quote tiewtrade_unit_code NOT NULL CHECK(quote='USDT'),
      input_id bigint NOT NULL CHECK(input_id>0), generation bigint NOT NULL CHECK(generation>0),
      decision_kind text NOT NULL CHECK(decision_kind IN ('INPUT','REBASE')),
      payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object'),
      digest text NOT NULL CHECK(digest ~ '^[0-9a-f]{64}$'),
      source_digest text NOT NULL CHECK(source_digest ~ '^[0-9a-f]{64}$'),
      PRIMARY KEY(recorded_at,id), UNIQUE(recorded_at,id,user_id,episode_id,base,quote),
      FOREIGN KEY(episode_id,wallet_id,user_id) REFERENCES paper_execution_profiles(episode_id,wallet_id,user_id),
      CHECK(base<>quote)) PARTITION BY RANGE(recorded_at)""")
    op.execute("""CREATE TABLE paper_execution_input_keys (
      user_id uuid NOT NULL, wallet_id uuid NOT NULL, episode_id uuid NOT NULL,
      base tiewtrade_unit_code NOT NULL, quote tiewtrade_unit_code NOT NULL,
      generation bigint NOT NULL CHECK(generation>0), input_id bigint NOT NULL CHECK(input_id>0),
      decision_kind text NOT NULL CHECK(decision_kind IN ('INPUT','REBASE')),
      recorded_at timestamptz NOT NULL, evidence_id uuid NOT NULL,
      PRIMARY KEY(episode_id,base,quote,generation,input_id,decision_kind),
      FOREIGN KEY(episode_id,wallet_id,user_id) REFERENCES paper_execution_profiles(episode_id,wallet_id,user_id),
      FOREIGN KEY(recorded_at,evidence_id,user_id,episode_id,base,quote)
        REFERENCES paper_execution_inputs(recorded_at,id,user_id,episode_id,base,quote))""")
    op.execute("""CREATE TABLE paper_order_events (
      id uuid PRIMARY KEY, order_id uuid NOT NULL, user_id uuid NOT NULL, episode_id uuid NOT NULL,
      base tiewtrade_unit_code NOT NULL, quote tiewtrade_unit_code NOT NULL,
      sequence bigint NOT NULL CHECK(sequence>0),
      event_kind text NOT NULL CHECK(event_kind IN ('ACCEPTED','REJECTED','FILL','CANCELED','EXPIRED','QUEUE_REBASED','CORRECTED')),
      execution_id uuid, input_recorded_at timestamptz, input_evidence_id uuid,
      payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object'), occurred_at timestamptz NOT NULL,
      UNIQUE(order_id,sequence), UNIQUE(id,user_id,episode_id,base,quote),
      UNIQUE(id,order_id,user_id,episode_id,base,quote),
      UNIQUE(id,order_id,user_id,episode_id,base,quote,execution_id),
      FOREIGN KEY(order_id,user_id,episode_id,base,quote) REFERENCES paper_orders(id,user_id,episode_id,base,quote),
      FOREIGN KEY(input_recorded_at,input_evidence_id,user_id,episode_id,base,quote)
        REFERENCES paper_execution_inputs(recorded_at,id,user_id,episode_id,base,quote),
      CHECK((input_recorded_at IS NULL)=(input_evidence_id IS NULL)),
      CHECK((event_kind='FILL' AND execution_id IS NOT NULL AND input_evidence_id IS NOT NULL)
         OR (event_kind<>'FILL' AND execution_id IS NULL)))""")
    op.execute(
        "CREATE UNIQUE INDEX paper_order_fill_execution ON paper_order_events(user_id,episode_id,execution_id) WHERE event_kind='FILL'"
    )
    op.execute("""CREATE TABLE paper_order_projections (
      order_id uuid PRIMARY KEY, user_id uuid NOT NULL, episode_id uuid NOT NULL,
      base tiewtrade_unit_code NOT NULL, quote tiewtrade_unit_code NOT NULL,
      status text NOT NULL CHECK(status IN ('ACCEPTED','PARTIALLY_FILLED','FILLED','CANCELED','EXPIRED','REJECTED')),
      filled_quantity tiewtrade_money_amount NOT NULL CHECK(filled_quantity>=0),
      spent tiewtrade_money_amount NOT NULL CHECK(spent>=0), resting boolean NOT NULL,
      queue_ahead tiewtrade_money_amount CHECK(queue_ahead>=0), revision bigint NOT NULL CHECK(revision>0),
      last_event_id uuid NOT NULL,
      FOREIGN KEY(order_id,user_id,episode_id,base,quote) REFERENCES paper_orders(id,user_id,episode_id,base,quote),
      FOREIGN KEY(last_event_id,order_id,user_id,episode_id,base,quote) REFERENCES paper_order_events(id,order_id,user_id,episode_id,base,quote),
      CHECK(NOT resting OR queue_ahead IS NOT NULL))""")
    op.execute("""CREATE TABLE paper_reservations (
      order_id uuid PRIMARY KEY, user_id uuid NOT NULL, episode_id uuid NOT NULL,
      base tiewtrade_unit_code NOT NULL, quote tiewtrade_unit_code NOT NULL,
      quote_reserved tiewtrade_money_amount NOT NULL CHECK(quote_reserved>=0),
      base_reserved tiewtrade_money_amount NOT NULL CHECK(base_reserved>=0),
      revision bigint NOT NULL CHECK(revision>0), CHECK(quote_reserved=0 OR base_reserved=0),
      FOREIGN KEY(order_id,user_id,episode_id,base,quote) REFERENCES paper_orders(id,user_id,episode_id,base,quote))""")
    op.execute("""ALTER TABLE paper_position_events ADD CONSTRAINT paper_position_event_kind_identity
      UNIQUE(id,user_id,episode_id,base,quote,event_kind,execution_id)""")
    op.execute("""CREATE TABLE paper_execution_links (
      position_event_id uuid PRIMARY KEY, user_id uuid NOT NULL, episode_id uuid NOT NULL,
      base tiewtrade_unit_code NOT NULL, quote tiewtrade_unit_code NOT NULL,
      order_id uuid NOT NULL, order_event_id uuid NOT NULL, execution_id uuid NOT NULL,
      position_event_kind text NOT NULL CHECK(position_event_kind IN ('RECORD','REPLACE','VOID')),
      cash_kind text NOT NULL CHECK(cash_kind IN ('TRADE_CASH','CORRECTION_CASH')),
      UNIQUE(position_event_id,user_id,episode_id,cash_kind),
      FOREIGN KEY(position_event_id,user_id,episode_id,base,quote,position_event_kind,execution_id)
        REFERENCES paper_position_events(id,user_id,episode_id,base,quote,event_kind,execution_id),
      FOREIGN KEY(order_id,user_id,episode_id,base,quote) REFERENCES paper_orders(id,user_id,episode_id,base,quote),
      FOREIGN KEY(order_event_id,order_id,user_id,episode_id,base,quote,execution_id)
        REFERENCES paper_order_events(id,order_id,user_id,episode_id,base,quote,execution_id),
      CHECK((position_event_kind='RECORD' AND cash_kind='TRADE_CASH')
         OR (position_event_kind IN ('REPLACE','VOID') AND cash_kind='CORRECTION_CASH')))""")

    for table in (*_IMMUTABLE, *_MUTABLE):
        _owner(table)
    for table in _IMMUTABLE:
        op.execute(f"SELECT tiewtrade_make_append_only('{table}'::regclass)")
    op.execute("""GRANT UPDATE(availability,source_sequence,revision,initialization_id,source_proof,observed_at,failure_code)
      ON paper_order_activity TO tiewtrade_engine""")
    op.execute("""GRANT UPDATE(state,worker,claim_id,claim_revision,lease_until,attempts,next_attempt_at)
      ON paper_order_dispatch TO tiewtrade_engine""")
    op.execute("""GRANT UPDATE(status,filled_quantity,spent,resting,queue_ahead,revision,last_event_id)
      ON paper_order_projections TO tiewtrade_engine""")
    op.execute(
        "GRANT UPDATE(quote_reserved,base_reserved,revision) ON paper_reservations TO tiewtrade_engine"
    )
    op.execute("""GRANT SELECT(command_id,user_id,episode_id,state,lease_until,next_attempt_at)
      ON paper_order_dispatch TO tiewtrade_engine_scan""")
    op.execute("""CREATE FUNCTION create_paper_execution_input_partition(day date) RETURNS void
      LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
      DECLARE part text:= 'paper_execution_inputs_' || to_char(day,'YYYYMMDD');
      BEGIN
        IF day IS NULL THEN RAISE EXCEPTION 'partition date required'; END IF;
        EXECUTE format('CREATE TABLE IF NOT EXISTS public.%I PARTITION OF public.paper_execution_inputs
          FOR VALUES FROM (%L) TO (%L)',part,
          day::timestamp AT TIME ZONE 'UTC',(day+1)::timestamp AT TIME ZONE 'UTC');
        PERFORM public.tiewtrade_protect_partition(('public.'||part)::regclass);
        PERFORM public.tiewtrade_clone_parent_policies(('public.'||part)::regclass);
        EXECUTE format('GRANT SELECT,INSERT ON public.%I TO tiewtrade_engine',part);
      END $$""")
    op.execute("REVOKE ALL ON FUNCTION create_paper_execution_input_partition(date) FROM PUBLIC")
    op.execute(
        "GRANT EXECUTE ON FUNCTION create_paper_execution_input_partition(date) TO tiewtrade_migrator"
    )
    op.execute("""SELECT create_paper_execution_input_partition((clock_timestamp() AT TIME ZONE 'UTC')::date+offset_day)
      FROM generate_series(-1,1) offset_day""")

    op.execute("ALTER TABLE paper_wallet_ledger DROP CONSTRAINT paper_wallet_ledger_kind_check")
    op.execute("ALTER TABLE paper_wallet_ledger DROP CONSTRAINT paper_wallet_ledger_amount_check")
    op.execute("ALTER TABLE paper_wallet_ledger DROP CONSTRAINT paper_wallet_ledger_episode_id_key")
    op.execute("ALTER TABLE paper_wallet_ledger ALTER COLUMN source_command_id DROP NOT NULL")
    op.execute("ALTER TABLE paper_wallet_ledger ADD COLUMN source_position_event_id uuid UNIQUE")
    op.execute("""ALTER TABLE paper_wallet_ledger ADD CONSTRAINT paper_wallet_cash_source
      FOREIGN KEY(source_position_event_id,user_id,episode_id,kind)
      REFERENCES paper_execution_links(position_event_id,user_id,episode_id,cash_kind)""")
    op.execute("""ALTER TABLE paper_wallet_ledger ADD CONSTRAINT paper_wallet_cash_shape CHECK(
      (kind='EXTERNAL_CAPITAL' AND amount>1000 AND source_command_id IS NOT NULL AND source_position_event_id IS NULL)
      OR (kind IN ('TRADE_CASH','CORRECTION_CASH') AND amount<>0 AND source_command_id IS NULL AND source_position_event_id IS NOT NULL))""")
    op.execute("""CREATE UNIQUE INDEX paper_wallet_one_external_capital ON paper_wallet_ledger(episode_id)
      WHERE kind='EXTERNAL_CAPITAL'""")


def downgrade() -> None:
    # Transactional DDL locks out writers while the owner checks all owners' facts.
    for table in (*_IMMUTABLE, *_MUTABLE, "paper_wallet_ledger"):
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
    for table in _IMMUTABLE:
        op.execute(f"""DO $$ BEGIN IF EXISTS(SELECT 1 FROM {table}) THEN
          RAISE EXCEPTION 'Paper financial history prevents downgrade'; END IF; END $$""")
    op.execute("""DO $$ BEGIN IF EXISTS(SELECT 1 FROM paper_wallet_ledger WHERE kind<>'EXTERNAL_CAPITAL')
      THEN RAISE EXCEPTION 'Paper cash effects prevent downgrade'; END IF; END $$""")
    op.execute("DROP INDEX paper_wallet_one_external_capital")
    op.execute("ALTER TABLE paper_wallet_ledger DROP CONSTRAINT paper_wallet_cash_shape")
    op.execute("ALTER TABLE paper_wallet_ledger DROP CONSTRAINT paper_wallet_cash_source")
    op.execute("ALTER TABLE paper_wallet_ledger DROP COLUMN source_position_event_id")
    op.execute("ALTER TABLE paper_wallet_ledger ALTER COLUMN source_command_id SET NOT NULL")
    op.execute(
        "ALTER TABLE paper_wallet_ledger ADD CONSTRAINT paper_wallet_ledger_kind_check CHECK(kind='EXTERNAL_CAPITAL')"
    )
    op.execute(
        "ALTER TABLE paper_wallet_ledger ADD CONSTRAINT paper_wallet_ledger_amount_check CHECK(amount>1000)"
    )
    op.execute(
        "ALTER TABLE paper_wallet_ledger ADD CONSTRAINT paper_wallet_ledger_episode_id_key UNIQUE(episode_id)"
    )
    op.execute("ALTER TABLE paper_wallet_ledger FORCE ROW LEVEL SECURITY")
    op.execute("DROP FUNCTION create_paper_execution_input_partition(date)")
    for table in (
        "paper_execution_links",
        "paper_reservations",
        "paper_order_projections",
        "paper_order_events",
        "paper_execution_input_keys",
        "paper_execution_inputs",
        "paper_orders",
        "paper_order_dispatch",
        "paper_order_command_results",
        "paper_order_commands",
        "paper_order_activity",
        "paper_execution_profiles",
    ):
        op.execute(f"DROP TABLE {table}")
    op.execute(
        "ALTER TABLE paper_position_events DROP CONSTRAINT paper_position_event_kind_identity"
    )
