"""add magnitude to predictions

Revision ID: j0e1f2g3h4i5
Revises: i9d0e1f2g3h4
Create Date: 2026-05-07 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "j0e1f2g3h4i5"
down_revision = "i9d0e1f2g3h4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("predictions", sa.Column("magnitude", sa.Float(), nullable=True))


def downgrade():
    op.drop_column("predictions", "magnitude")
