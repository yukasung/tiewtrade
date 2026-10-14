"""Move prepared indicator contracts to the MACD-free v2 generation.

An existing rollout must be PAUSED and drained by the operator before this
migration. A fresh LEGACY installation with no jobs may migrate directly.
Historical v1 generations remain tagged and are never reinterpreted.
"""

from alembic import op
from sqlalchemy import text

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None

_FUNCTIONS = (
    (
        "seed_indicator_build_jobs()",
        (
            ("'indicators-v1'", "'indicators-v2'", 1),
            ("c.codec_version<>1", "c.codec_version<>2", 1),
        ),
    ),
    (
        "claim_indicator_build_job(uuid)",
        (
            ("c.codec_version<>1", "c.codec_version<>2", 1),
            (
                "eligible.status='QUEUED'",
                "eligible.formula_version='indicators-v2' AND eligible.status='QUEUED'",
                3,
            ),
        ),
    ),
    (
        "require_indicator_build_claim(uuid,bigint,uuid,uuid,uuid,uuid)",
        (("c.codec_version=1", "c.codec_version=2", 1),),
    ),
    (
        "initialize_indicator_staging(uuid,bigint,uuid,uuid,uuid,uuid,timestamptz,uuid,bigint)",
        (
            ("'indicators-v1'", "'indicators-v2'", 1),
            ("p_source_fence,1,j.build_rollout_epoch", "p_source_fence,2,j.build_rollout_epoch", 1),
        ),
    ),
    (
        "append_indicator_checkpoint(uuid,bigint,uuid,uuid,uuid,uuid,timestamptz,jsonb)",
        (
            (
                "p_payload->>'version' IS DISTINCT FROM '1'",
                "p_payload->>'version' IS DISTINCT FROM '2'",
                1,
            ),
        ),
    ),
    (
        "publish_indicator_generation(uuid,bigint,uuid,uuid,uuid,uuid,boolean)",
        (
            ("'indicators-v1'", "'indicators-v2'", 1),
            ("g.codec_version<>1", "g.codec_version<>2", 1),
        ),
    ),
    (
        "coalesce_indicator_build_jobs()",
        (
            ("'indicators-v1'", "'indicators-v2'", 1),
            ("c.codec_version<>1", "c.codec_version<>2", 1),
        ),
    ),
    (
        "transition_indicator_rollout(indicator_rollout_mode,uuid,indicator_rollout_mode)",
        (
            ("'indicators-v1'", "'indicators-v2'", 1),
            ("c.codec_version<>1", "c.codec_version<>2", 1),
            ("g.codec_version=1", "g.codec_version=2", 1),
        ),
    ),
)


def _replace_functions(reverse: bool = False) -> None:
    connection = op.get_bind()
    for signature, substitutions in _FUNCTIONS:
        definition: str | None = connection.execute(
            text("SELECT pg_get_functiondef(to_regprocedure(:signature))"),
            {"signature": f"public.{signature}"},
        ).scalar_one()
        if definition is None:
            raise RuntimeError(f"missing indicator function: {signature}")
        for before, after, expected in substitutions:
            old, new = (after, before) if reverse else (before, after)
            if definition.count(old) != expected:
                raise RuntimeError(f"unexpected indicator function definition: {signature}")
            definition = definition.replace(old, new)
        op.execute(definition)


def upgrade() -> None:
    connection = op.get_bind()
    safe: bool | None = connection.execute(
        text("""SELECT s.state='IDLE'
      AND (c.mode='PAUSED' OR (c.mode='LEGACY' AND NOT EXISTS(
        SELECT 1 FROM indicator_build_jobs)))
      AND c.codec_version=1 AND c.protocol_version=1
      FROM indicator_rollout_control c CROSS JOIN indicator_build_slot s
      WHERE c.id=1 AND s.id=1 FOR UPDATE OF c,s""")
    ).scalar_one()
    if not safe:
        raise RuntimeError("INDICATOR_MACD_REMOVAL_REQUIRES_PAUSED_DRAINED_ROLLOUT")
    _replace_functions()
    op.execute("""UPDATE indicator_rollout_control SET codec_version=2,
      rollout_epoch=gen_random_uuid(),transition_from_mode=NULL,
      transition_from_epoch=NULL,transition_target=NULL WHERE id=1""")


def downgrade() -> None:
    connection = op.get_bind()
    safe: bool | None = connection.execute(
        text("""SELECT c.mode IN ('PAUSED','LEGACY')
      AND s.state='IDLE'
      AND c.codec_version=2 AND NOT EXISTS(
        SELECT 1 FROM indicator_generations WHERE formula_version='indicators-v2')
      FROM indicator_rollout_control c CROSS JOIN indicator_build_slot s
      WHERE c.id=1 AND s.id=1 FOR UPDATE OF c,s""")
    ).scalar_one()
    if not safe:
        raise RuntimeError("INDICATOR_V2_DOWNGRADE_REQUIRES_PAUSED_EMPTY_ROLLOUT")
    _replace_functions(reverse=True)
    op.execute("""DELETE FROM indicator_build_jobs WHERE formula_version='indicators-v2'""")
    op.execute("""UPDATE indicator_rollout_control SET codec_version=1,
      rollout_epoch=gen_random_uuid(),transition_from_mode=NULL,
      transition_from_epoch=NULL,transition_target=NULL WHERE id=1""")
