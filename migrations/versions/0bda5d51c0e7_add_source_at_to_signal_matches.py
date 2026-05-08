"""add source_at to signal_matches

Revision ID: 0bda5d51c0e7
Revises: n4i5j6k7l8m9
Create Date: 2026-05-08 14:50:24.656875

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0bda5d51c0e7'
down_revision = 'n4i5j6k7l8m9'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('signal_matches', schema=None) as batch_op:
        batch_op.add_column(sa.Column('source_at', sa.DateTime(timezone=True), nullable=True))


def downgrade():
    with op.batch_alter_table('signal_matches', schema=None) as batch_op:
        batch_op.drop_column('source_at')
