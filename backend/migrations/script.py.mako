"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
"""

from __future__ import annotations

from alembic import op

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = None
depends_on = None


def upgrade() -> None:
    raise NotImplementedError


def downgrade() -> None:
    raise NotImplementedError
