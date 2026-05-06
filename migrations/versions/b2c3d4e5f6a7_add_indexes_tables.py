"""add indexes and company_index tables

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-06 00:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "indexes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_indexes_symbol", "indexes", ["symbol"], unique=True)

    op.create_table(
        "company_index",
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("index_id", sa.Integer(), sa.ForeignKey("indexes.id"), nullable=False),
        sa.PrimaryKeyConstraint("company_id", "index_id"),
    )


def downgrade():
    op.drop_table("company_index")
    op.drop_index("ix_indexes_symbol", table_name="indexes")
    op.drop_table("indexes")
