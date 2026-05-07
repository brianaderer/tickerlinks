"""add accuracy_snapshots to signals, remove dead signals

Revision ID: g7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-05-07 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON


revision = "g7b8c9d0e1f2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("signals", sa.Column("accuracy_snapshots", JSON(), server_default="[]"))

    op.execute("""
        DELETE FROM signal_matches WHERE signal_id IN (
            SELECT id FROM signals WHERE name IN (
                'Earnings Sentiment Bearish',
                'Mention Spike (24h)',
                'Analyst Consensus Bullish'
            )
        )
    """)
    op.execute("""
        DELETE FROM signals WHERE name IN (
            'Earnings Sentiment Bearish',
            'Mention Spike (24h)',
            'Analyst Consensus Bullish'
        )
    """)


def downgrade():
    op.drop_column("signals", "accuracy_snapshots")
