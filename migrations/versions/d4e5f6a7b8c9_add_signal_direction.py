"""add direction and sample_size to signals

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-05-06 02:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("signals", sa.Column("direction", sa.String(10), nullable=True))
    op.add_column("signals", sa.Column("sample_size", sa.Integer(), default=0))

    # Populate direction from existing signal names
    op.execute("""
        UPDATE signals SET direction = CASE
            WHEN name ILIKE '%bullish%' THEN 'bullish'
            WHEN name ILIKE '%bearish%' THEN 'bearish'
            WHEN name ILIKE '%oversold%' THEN 'bullish'
            WHEN name ILIKE '%overbought%' THEN 'bearish'
            WHEN name ILIKE '%lower%' THEN 'bullish'
            WHEN name ILIKE '%upper%' THEN 'bearish'
            ELSE 'neutral'
        END
    """)

    op.alter_column("signals", "direction", nullable=False, server_default="neutral")

    # Drop old unique constraint on name alone, add new one on name+direction
    op.drop_constraint("signals_name_key", "signals", type_="unique")
    op.create_unique_constraint("uq_signal_name_direction", "signals", ["name", "direction"])


def downgrade():
    op.drop_constraint("uq_signal_name_direction", "signals", type_="unique")
    op.create_unique_constraint("signals_name_key", "signals", ["name"])
    op.drop_column("signals", "sample_size")
    op.drop_column("signals", "direction")
