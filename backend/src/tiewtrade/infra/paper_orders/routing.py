"""R8 owner fairness with optional, guarded same-pair admission hints (R9)."""


def _eligible(alias: str) -> str:
    # All aliases are static source literals; values remain bound parameters.
    return f"""{alias}.state<>'TERMINAL' AND {alias}.next_attempt_at<=clock_timestamp()
      AND ({alias}.lease_until IS NULL OR {alias}.lease_until<=clock_timestamp())"""


_BUSY_OWNERS_CTE = """busy AS MATERIALIZED (
  SELECT DISTINCT user_id FROM paper_order_dispatch
  WHERE state='CLAIMED' AND lease_until>clock_timestamp())"""

LEGACY_DUE_SQL = f"""WITH {_BUSY_OWNERS_CTE}, due AS (
  SELECT d.command_id,d.user_id,d.next_attempt_at,
    row_number() OVER(PARTITION BY d.user_id ORDER BY d.next_attempt_at,d.command_id) rank
  FROM paper_order_dispatch d WHERE {_eligible("d")}
    AND NOT EXISTS(SELECT 1 FROM busy WHERE busy.user_id=d.user_id))
  SELECT command_id,user_id,next_attempt_at FROM due WHERE rank=1
  ORDER BY next_attempt_at,command_id LIMIT :limit"""

# These statuses only qualify a scheduling preference, never a financial action.
_READY_RISK_HINT = """EXISTS(SELECT 1 FROM risk_limit_settings s
  JOIN risk_limit_evaluations e USING(user_id,mode)
  JOIN risk_owner_state o USING(user_id,mode)
  WHERE s.user_id=h.user_id AND s.mode='PAPER' AND NOT s.latched
    AND e.setting_revision=s.revision AND e.reason='READY'
    AND NOT e.replay_pending AND NOT o.replay_pending AND o.episode_id=h.episode_id)
  AND EXISTS(SELECT 1 FROM risk_protocol_control
    WHERE publication_enabled AND financial_enabled AND admission_enabled)"""

_NO_CANCEL_OR_UNKNOWN_HINTS = f"""NOT EXISTS(SELECT 1 FROM paper_order_dispatch other
  WHERE other.user_id=h.user_id AND {_eligible("other")}
    AND (other.routing_action='CANCEL' OR other.routing_action IS NULL
      OR other.routing_stage IS NULL))"""

_RANKED_HEADS_CTE = f"""WITH {_BUSY_OWNERS_CTE}, ranked AS (
  SELECT d.command_id,d.user_id,d.episode_id,d.next_attempt_at,d.state,
    d.routing_action,d.routing_base,d.routing_quote,d.routing_stage,d.preferred_for_due,
    row_number() OVER(PARTITION BY d.user_id ORDER BY d.next_attempt_at,d.command_id) rank
  FROM paper_order_dispatch d WHERE {_eligible("d")}
    AND NOT EXISTS(SELECT 1 FROM busy WHERE busy.user_id=d.user_id))"""


def _same_pair_candidates(*, source_resumption: bool = False) -> str:
    probe_column = ",h.probe_revision" if source_resumption else ""
    ordinary_head = "h.probe_revision IS NULL AND " if source_resumption else ""
    return f"""  SELECT coalesce(p.command_id,h.command_id) command_id,h.user_id,
    coalesce(p.next_attempt_at,h.next_attempt_at) next_attempt_at,
    CASE WHEN p.command_id IS NOT NULL THEN h.command_id END anchor_command_id,
    CASE WHEN p.command_id IS NOT NULL THEN h.next_attempt_at END anchor_due_at{probe_column}
  FROM heads h LEFT JOIN LATERAL (
    SELECT n.command_id,n.next_attempt_at FROM (
      SELECT d.command_id,d.next_attempt_at,d.episode_id,
        d.routing_action,d.routing_base,d.routing_quote
      FROM paper_order_dispatch d WHERE d.user_id=h.user_id AND {_eligible("d")}
        AND d.routing_stage='PENDING'
      ORDER BY d.next_attempt_at,d.command_id LIMIT 1) n
    WHERE {ordinary_head}h.state='PENDING' AND h.routing_action='NEW' AND h.routing_stage='ACTIVE'
      AND h.preferred_for_due IS DISTINCT FROM h.next_attempt_at
      AND n.routing_action='NEW' AND n.episode_id=h.episode_id
      AND n.routing_base=h.routing_base AND n.routing_quote=h.routing_quote
      AND {_READY_RISK_HINT} AND {_NO_CANCEL_OR_UNKNOWN_HINTS}
  ) p ON true"""


_SAME_PAIR_CANDIDATES = _same_pair_candidates()

SAME_PAIR_DUE_SQL = f"""{_RANKED_HEADS_CTE},
  heads AS MATERIALIZED(SELECT * FROM ranked WHERE rank=1
    ORDER BY next_attempt_at,command_id LIMIT :limit)
{_SAME_PAIR_CANDIDATES} ORDER BY h.next_attempt_at,h.command_id"""

# R10 alone changes global head priority; the R9 proof and owner FIFO stay intact.
ADMISSION_FIRST_DUE_SQL = f"""{_RANKED_HEADS_CTE},
  heads AS MATERIALIZED(SELECT * FROM ranked WHERE rank=1)
{_SAME_PAIR_CANDIDATES}
  ORDER BY (p.command_id IS NULL),h.next_attempt_at,h.command_id LIMIT :limit"""


# The scanner's classification is not trusted here. Recheck canonical commands,
# outcomes, header/status, active episode, FIFO and cancellation under owner lock.
PREFERENCE_PROOF_SQL = f"""SELECT 1 FROM paper_order_dispatch h
  JOIN paper_order_commands hc ON hc.id=h.command_id
  JOIN paper_order_command_results hr ON hr.command_id=hc.id AND hr.state='SUCCEEDED'
  JOIN paper_orders ho ON ho.command_id=hc.id
  JOIN paper_order_projections hp ON hp.order_id=ho.id
  JOIN paper_wallet_state w ON w.user_id=h.user_id AND w.active_episode_id=h.episode_id
  JOIN paper_order_dispatch d ON d.user_id=h.user_id AND d.episode_id=h.episode_id
  JOIN paper_order_commands c ON c.id=d.command_id
  WHERE h.user_id=:user AND h.command_id=:anchor AND h.next_attempt_at=:anchor_due
    AND h.state='PENDING' AND h.next_attempt_at<=clock_timestamp()
    AND h.preferred_for_due IS DISTINCT FROM h.next_attempt_at
    AND hc.action='NEW' AND ho.kind IN ('MARKET','LIMIT')
    AND hp.status IN ('ACCEPTED','PARTIALLY_FILLED')
    AND NOT EXISTS(SELECT 1 FROM paper_wallet_episode_closures x WHERE x.episode_id=h.episode_id)
    AND d.command_id=:id AND d.next_attempt_at=:expected_due AND {_eligible("d")}
    AND c.action='NEW' AND c.payload#>>'{{intent,base}}'=ho.base::text
    AND c.payload#>>'{{intent,quote}}'=ho.quote::text
    AND NOT EXISTS(SELECT 1 FROM paper_order_command_results r WHERE r.command_id=c.id)
    AND NOT EXISTS(SELECT 1 FROM paper_orders o WHERE o.command_id=c.id)
    AND NOT EXISTS(SELECT 1 FROM paper_order_dispatch other
      WHERE other.user_id=h.user_id AND {_eligible("other")}
        AND (other.next_attempt_at,other.command_id)<(h.next_attempt_at,h.command_id))
    AND NOT EXISTS(SELECT 1 FROM paper_order_dispatch other
      JOIN paper_order_commands oc ON oc.id=other.command_id
      WHERE other.user_id=h.user_id AND {_eligible("other")} AND oc.action='CANCEL')
    AND NOT EXISTS(SELECT 1 FROM paper_order_dispatch other
      WHERE other.user_id=h.user_id AND {_eligible("other")}
        AND (other.next_attempt_at,other.command_id)<(d.next_attempt_at,d.command_id)
        AND NOT EXISTS(SELECT 1 FROM paper_order_command_results r
          WHERE r.command_id=other.command_id))
    AND {_READY_RISK_HINT} AND {_NO_CANCEL_OR_UNKNOWN_HINTS}
  FOR UPDATE OF h,d"""


def _source_resume_hint(alias: str) -> str:
    """Publication progress is a scheduling hint; native freshness gates still run."""
    return f"""{alias}.state='PENDING' AND {alias}.attempts>0
      AND {alias}.routing_action='NEW' AND {alias}.routing_stage IN ('PENDING','ACTIVE')
      AND {alias}.source_wait_revision={alias}.claim_revision
      AND NOT {alias}.source_resume_used AND NOT {alias}.source_resume_claim
      AND {alias}.next_attempt_at>clock_timestamp()
      AND {alias}.source_wait_since<=clock_timestamp()
      AND ({alias}.lease_until IS NULL OR {alias}.lease_until<=clock_timestamp())
      AND EXISTS(SELECT 1 FROM market_execution_state b
        JOIN market_latest_prices p USING(source,base,quote)
        JOIN market_price_feed f USING(source)
        WHERE b.source='primary_spot' AND b.base::text={alias}.routing_base
          AND b.quote::text={alias}.routing_quote
          AND b.ready AND b.generation>0 AND b.lease_until>clock_timestamp()
          AND b.verified_at>{alias}.source_wait_since AND b.verified_at<=clock_timestamp()
          AND f.connected AND f.lease_until>clock_timestamp()
          AND p.reconciled_generation=f.generation AND p.effective_readiness='READY'
          AND p.received_at>{alias}.source_wait_since AND p.received_at<=clock_timestamp()
          AND p.trade_at<=clock_timestamp())
      AND NOT EXISTS(SELECT 1 FROM paper_order_dispatch other
        WHERE other.user_id={alias}.user_id AND {_eligible("other")}
          AND (other.routing_action='CANCEL' OR other.routing_action IS NULL
            OR other.routing_stage IS NULL))"""


_SOURCE_RESUME_HEADS_CTE = f"""WITH {_BUSY_OWNERS_CTE}, available AS MATERIALIZED (
  SELECT d.command_id,d.user_id,d.episode_id,d.next_attempt_at,d.state,
    d.routing_action,d.routing_base,d.routing_quote,d.routing_stage,d.preferred_for_due,
    CASE WHEN {_source_resume_hint("d")} THEN d.source_wait_revision END probe_revision,
    d.source_wait_since
  FROM paper_order_dispatch d WHERE d.state<>'TERMINAL'
    AND (d.lease_until IS NULL OR d.lease_until<=clock_timestamp())
    AND NOT EXISTS(SELECT 1 FROM busy WHERE busy.user_id=d.user_id)),
  eligible AS (
    SELECT *,CASE WHEN probe_revision IS NOT NULL THEN source_wait_since
      ELSE next_attempt_at END sort_at
    FROM available WHERE next_attempt_at<=clock_timestamp() OR probe_revision IS NOT NULL),
  ranked AS (
    SELECT *,row_number() OVER(PARTITION BY user_id ORDER BY sort_at,command_id) rank
    FROM eligible)"""


def source_resume_due_sql(*, prefer_same_pair: bool, admission_first: bool) -> str:
    """Compose the existing owner preference with early heads claimed directly."""
    if not prefer_same_pair:
        return f"""{_SOURCE_RESUME_HEADS_CTE}
          SELECT command_id,user_id,next_attempt_at,probe_revision FROM ranked WHERE rank=1
          ORDER BY sort_at,command_id LIMIT :limit"""
    # The common candidate builder keeps ordinary R9/R10 eligibility/proof intact.
    candidates = _same_pair_candidates(source_resumption=True)
    heads = "SELECT * FROM ranked WHERE rank=1"
    if not admission_first:
        heads += " ORDER BY sort_at,command_id LIMIT :limit"
    order = (
        "(p.command_id IS NULL),h.sort_at,h.command_id LIMIT :limit"
        if admission_first
        else "h.sort_at,h.command_id"
    )
    return f"""{_SOURCE_RESUME_HEADS_CTE}, heads AS MATERIALIZED({heads})
      {candidates} ORDER BY {order}"""


# Owner RLS restricts the ranked set; the owner advisory lock serializes claims,
# admissions and reset. Canonical commands must agree with scanner routing hints.
SOURCE_RESUME_PROOF_SQL = f"""{_SOURCE_RESUME_HEADS_CTE}
  SELECT 1 FROM ranked r
  JOIN paper_order_dispatch d ON d.command_id=r.command_id
  JOIN paper_order_commands c ON c.id=d.command_id AND c.user_id=d.user_id
    AND c.episode_id=d.episode_id
  JOIN paper_wallet_state w ON w.user_id=d.user_id AND w.active_episode_id=d.episode_id
  WHERE r.rank=1 AND r.probe_revision=:wait_revision
    AND d.command_id=:id AND d.user_id=:user AND d.next_attempt_at=:expected_due
    AND c.action='NEW' AND c.payload#>>'{{intent,base}}'=d.routing_base
    AND c.payload#>>'{{intent,quote}}'=d.routing_quote
    AND NOT EXISTS(SELECT 1 FROM paper_wallet_episode_closures x WHERE x.episode_id=d.episode_id)
    AND NOT EXISTS(SELECT 1 FROM paper_order_dispatch other
      JOIN paper_order_commands oc ON oc.id=other.command_id
      WHERE other.user_id=d.user_id AND {_eligible("other")} AND oc.action='CANCEL')
  FOR UPDATE OF d"""
