"""add full_text and processed to news_articles

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-05-06 03:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("news_articles", sa.Column("full_text", sa.Text(), nullable=True))
    op.add_column("news_articles", sa.Column("processed", sa.Boolean(), server_default="false", nullable=False))


def downgrade():
    op.drop_column("news_articles", "processed")
    op.drop_column("news_articles", "full_text")
