"""add trend_snapshots table

Revision ID: k1f2g3h4i5j6
Revises: j0e1f2g3h4i5
Create Date: 2026-05-07 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON


revision = "k1f2g3h4i5j6"
down_revision = "j0e1f2g3h4i5"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "trend_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("trends", JSON, nullable=False, server_default="[]"),
    )


def downgrade():
    op.drop_table("trend_snapshots")
