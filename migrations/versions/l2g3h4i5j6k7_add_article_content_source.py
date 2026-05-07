"""add article content_source column

Revision ID: l2g3h4i5j6k7
Revises: k1f2g3h4i5j6
Create Date: 2026-05-07
"""
from alembic import op
import sqlalchemy as sa

revision = "l2g3h4i5j6k7"
down_revision = "k1f2g3h4i5j6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("news_articles", sa.Column("content_source", sa.String(20), nullable=True))


def downgrade():
    op.drop_column("news_articles", "content_source")
