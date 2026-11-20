"""Add owner-scoped bot lifecycle and decision storage without activating bots."""

from alembic import op

revision = "0067"
down_revision = "0066"
branch_labels = None
depends_on = None

_TABLES = (
    "bot_runs",
    "bot_control_requests",
    "bot_control_results",
    "bot_control_dispatch",
    "bot_decisions",
    "bot_order_links",
    "bot_run_events",
)


def upgrade() -> None:
    # F-08 has one trading account per owner. Paper episodes can change, so the
    # slot is independent of the episode while each Paper run pins its episode.
    op.execute("""CREATE TABLE bot_runs (
      id uuid PRIMARY KEY, user_id uuid NOT NULL REFERENCES users(id),
      mode text NOT NULL CHECK(mode IN ('PAPER','LIVE')),
      wallet_id uuid, episode_id uuid,
      strategy_name text NOT NULL CHECK(length(btrim(strategy_name)) > 0),
      strategy_version integer NOT NULL CHECK(strategy_version > 0),
      configuration_version integer NOT NULL CHECK(configuration_version > 0),
      state_version integer NOT NULL CHECK(state_version > 0),
      configuration jsonb NOT NULL CHECK(jsonb_typeof(configuration)='object'),
      strategy_state jsonb NOT NULL CHECK(jsonb_typeof(strategy_state)='object'),
      status text NOT NULL CHECK(status IN
        ('STARTING','RUNNING','PAUSED','RECOVERING','STOPPED','RETIRED')),
      revision bigint NOT NULL DEFAULT 1 CHECK(revision > 0),
      source_progress jsonb NOT NULL DEFAULT '{}' CHECK(jsonb_typeof(source_progress)='object'),
      created_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE(id,user_id,mode), UNIQUE(id,user_id,mode,episode_id),
      FOREIGN KEY(episode_id,wallet_id,user_id)
        REFERENCES paper_wallet_episodes(id,wallet_id,user_id),
      CHECK((mode='PAPER' AND wallet_id IS NOT NULL AND episode_id IS NOT NULL)
         OR (mode='LIVE' AND wallet_id IS NULL AND episode_id IS NULL)))""")
    op.execute("""CREATE UNIQUE INDEX bot_runs_current_slot ON bot_runs(user_id,mode)
      WHERE status <> 'RETIRED'""")
    op.execute("""CREATE TABLE bot_control_requests (
      id uuid PRIMARY KEY, user_id uuid NOT NULL REFERENCES users(id),
      mode text NOT NULL CHECK(mode IN ('PAPER','LIVE')),
      idempotency_key uuid NOT NULL,
      fingerprint text NOT NULL CHECK(fingerprint ~ '^[0-9a-f]{64}$'),
      payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object'),
      requested_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE(user_id,mode,idempotency_key), UNIQUE(id,user_id,mode))""")
    op.execute("""CREATE TABLE bot_control_results (
      request_id uuid PRIMARY KEY, user_id uuid NOT NULL, mode text NOT NULL,
      run_id uuid, failure_code text, completed_at timestamptz NOT NULL DEFAULT now(),
      CHECK((run_id IS NULL) <> (failure_code IS NULL)),
      FOREIGN KEY(request_id,user_id,mode) REFERENCES bot_control_requests(id,user_id,mode),
      FOREIGN KEY(run_id,user_id,mode) REFERENCES bot_runs(id,user_id,mode))""")
    op.execute("""CREATE TABLE bot_control_dispatch (
      request_id uuid PRIMARY KEY, user_id uuid NOT NULL, mode text NOT NULL,
      claim_id uuid NOT NULL, claim_revision bigint NOT NULL CHECK(claim_revision > 0),
      lease_until timestamptz NOT NULL,
      FOREIGN KEY(request_id,user_id,mode) REFERENCES bot_control_requests(id,user_id,mode))""")
    op.execute("""CREATE TABLE bot_decisions (
      id uuid PRIMARY KEY, run_id uuid NOT NULL, user_id uuid NOT NULL, mode text NOT NULL,
      input_identity text NOT NULL CHECK(length(input_identity)>0),
      run_revision bigint NOT NULL CHECK(run_revision > 0),
      strategy_version integer NOT NULL CHECK(strategy_version > 0),
      configuration_version integer NOT NULL CHECK(configuration_version > 0),
      state_before jsonb NOT NULL CHECK(jsonb_typeof(state_before)='object'),
      state_after jsonb NOT NULL CHECK(jsonb_typeof(state_after)='object'),
      recorded_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE(run_id,input_identity), UNIQUE(id,run_id,user_id,mode),
      FOREIGN KEY(run_id,user_id,mode) REFERENCES bot_runs(id,user_id,mode))""")
    op.execute("""CREATE TABLE bot_order_links (
      decision_id uuid NOT NULL, run_id uuid NOT NULL, user_id uuid NOT NULL,
      mode text NOT NULL CHECK(mode='PAPER'), episode_id uuid NOT NULL,
      ordinal integer NOT NULL CHECK(ordinal >= 0), command_id uuid NOT NULL UNIQUE,
      order_id uuid NOT NULL, action text NOT NULL DEFAULT 'NEW' CHECK(action='NEW'),
      PRIMARY KEY(decision_id,ordinal),
      FOREIGN KEY(decision_id,run_id,user_id,mode) REFERENCES bot_decisions(id,run_id,user_id,mode),
      FOREIGN KEY(run_id,user_id,mode,episode_id) REFERENCES bot_runs(id,user_id,mode,episode_id),
      FOREIGN KEY(command_id,user_id,episode_id,order_id,action)
        REFERENCES paper_order_commands(id,user_id,episode_id,order_id,action))""")
    op.execute("""CREATE TABLE bot_run_events (
      id uuid NOT NULL, run_id uuid NOT NULL, user_id uuid NOT NULL, mode text NOT NULL,
      revision bigint NOT NULL CHECK(revision > 0),
      event text NOT NULL CHECK(length(event)>0),
      details jsonb NOT NULL CHECK(jsonb_typeof(details)='object'),
      recorded_at timestamptz NOT NULL DEFAULT now(),
      PRIMARY KEY(id,recorded_at),
      FOREIGN KEY(run_id,user_id,mode) REFERENCES bot_runs(id,user_id,mode)
    ) PARTITION BY RANGE(recorded_at)""")
    op.execute("CREATE TABLE bot_run_events_default PARTITION OF bot_run_events DEFAULT")
    op.execute("CREATE INDEX bot_run_events_read ON bot_run_events(run_id,revision)")
    for table in (*_TABLES, "bot_run_events_default"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""CREATE POLICY {table}_owner ON {table} FOR ALL
          USING(user_id=tiewtrade_current_user_id())
          WITH CHECK(user_id=tiewtrade_current_user_id())""")

    for table in (
        "bot_control_requests",
        "bot_control_results",
        "bot_decisions",
        "bot_order_links",
        "bot_run_events",
    ):
        op.execute(f"SELECT tiewtrade_make_append_only('{table}'::regclass)")

    op.execute("""GRANT SELECT(id,user_id,mode,status,revision,strategy_name,
      strategy_version,configuration_version) ON bot_runs TO tiewtrade_api""")
    op.execute("GRANT SELECT ON bot_control_requests,bot_control_results TO tiewtrade_api")
    op.execute("""GRANT SELECT(run_id,user_id,mode,revision,event,details) ON bot_run_events
      TO tiewtrade_api""")
    op.execute("""GRANT INSERT(id,user_id,mode,idempotency_key,fingerprint,payload)
      ON bot_control_requests TO tiewtrade_api""")
    op.execute("GRANT SELECT ON bot_control_requests TO tiewtrade_engine")
    op.execute("GRANT SELECT,INSERT,UPDATE ON bot_control_dispatch TO tiewtrade_engine")
    op.execute("GRANT SELECT,INSERT ON bot_runs TO tiewtrade_engine")
    op.execute("""GRANT UPDATE(status,revision,strategy_state,source_progress)
      ON bot_runs TO tiewtrade_engine""")
    op.execute("""GRANT SELECT,INSERT ON bot_control_results,bot_decisions,bot_order_links,
      bot_run_events TO tiewtrade_engine""")
    op.execute("""GRANT SELECT(id,user_id,mode,requested_at) ON bot_control_requests
      TO tiewtrade_engine_scan""")
    op.execute("GRANT SELECT(request_id) ON bot_control_results TO tiewtrade_engine_scan")
    op.execute(
        "GRANT SELECT(request_id,lease_until) ON bot_control_dispatch TO tiewtrade_engine_scan"
    )


def downgrade() -> None:
    op.execute("LOCK TABLE " + ",".join(_TABLES) + " IN ACCESS EXCLUSIVE MODE")
    # Migration owner reads across scopes only during this locked transaction.
    # PostgreSQL rolls the changes back if a populated schema refuses downgrade.
    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"""DO $$ BEGIN
          IF EXISTS(SELECT 1 FROM {table}) THEN
            RAISE EXCEPTION 'bot lifecycle history prevents downgrade';
          END IF;
        END $$""")
    for table in reversed(_TABLES):
        op.execute(f"DROP TABLE {table}")
