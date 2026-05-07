"""add signal_digests table

Revision ID: h8c9d0e1f2g3
Revises: g7b8c9d0e1f2
Create Date: 2026-05-07 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON


revision = "h8c9d0e1f2g3"
down_revision = "g7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "signal_digests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("net_confidence", sa.Float(), nullable=False),
        sa.Column("match_count", sa.Integer(), nullable=False),
        sa.Column("digest", sa.Text(), nullable=False),
        sa.Column("matches", JSON(), default=[]),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False, index=True),
    )


def downgrade():
    op.drop_table("signal_digests")
