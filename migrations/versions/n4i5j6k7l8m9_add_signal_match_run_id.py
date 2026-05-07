"""add signal_match run_id column

Revision ID: n4i5j6k7l8m9
Revises: m3h4i5j6k7l8
Create Date: 2026-05-07
"""
from alembic import op
import sqlalchemy as sa

revision = "n4i5j6k7l8m9"
down_revision = "m3h4i5j6k7l8"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("signal_matches", sa.Column("run_id", sa.String(32), nullable=True))
    op.create_index("ix_signal_match_run_id", "signal_matches", ["run_id"])


def downgrade():
    op.drop_index("ix_signal_match_run_id", "signal_matches")
    op.drop_column("signal_matches", "run_id")
