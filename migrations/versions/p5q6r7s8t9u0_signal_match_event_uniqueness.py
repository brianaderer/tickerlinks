"""enforce signal match event uniqueness

Revision ID: p5q6r7s8t9u0
Revises: 0bda5d51c0e7
Create Date: 2026-05-13
"""
from alembic import op
import sqlalchemy as sa


revision = "p5q6r7s8t9u0"
down_revision = "0bda5d51c0e7"
branch_labels = None
depends_on = None


DEDUPE_CTE = """
WITH ranked AS (
    SELECT
        id,
        FIRST_VALUE(id) OVER (
            PARTITION BY company_id, signal_id, direction, source_at
            ORDER BY detected_at DESC, id DESC
        ) AS keep_id,
        ROW_NUMBER() OVER (
            PARTITION BY company_id, signal_id, direction, source_at
            ORDER BY detected_at DESC, id DESC
        ) AS rn
    FROM signal_matches
),
dupes AS (
    SELECT id, keep_id
    FROM ranked
    WHERE rn > 1
)
"""


def upgrade():
    op.execute("UPDATE signal_matches SET source_at = detected_at WHERE source_at IS NULL")

    op.execute(
        DEDUPE_CTE
        + """
INSERT INTO prediction_match (prediction_id, signal_match_id)
SELECT pm.prediction_id, d.keep_id
FROM prediction_match pm
JOIN dupes d ON d.id = pm.signal_match_id
ON CONFLICT DO NOTHING
"""
    )

    op.execute(
        DEDUPE_CTE
        + """
DELETE FROM prediction_match pm
USING dupes d
WHERE pm.signal_match_id = d.id
"""
    )

    op.execute(
        DEDUPE_CTE
        + """
DELETE FROM signal_matches sm
USING dupes d
WHERE sm.id = d.id
"""
    )

    with op.batch_alter_table("signal_matches", schema=None) as batch_op:
        batch_op.alter_column(
            "source_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
        )

    op.create_index(
        "ux_signal_match_event",
        "signal_matches",
        ["company_id", "signal_id", "direction", "source_at"],
        unique=True,
    )


def downgrade():
    op.drop_index("ux_signal_match_event", table_name="signal_matches")

    with op.batch_alter_table("signal_matches", schema=None) as batch_op:
        batch_op.alter_column(
            "source_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=True,
        )
