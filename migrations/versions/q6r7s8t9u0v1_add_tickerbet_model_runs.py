"""add tickerbet model runs table

Revision ID: q6r7s8t9u0v1
Revises: p5q6r7s8t9u0
Create Date: 2026-05-14
"""
from alembic import op
import sqlalchemy as sa


revision = "q6r7s8t9u0v1"
down_revision = "p5q6r7s8t9u0"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "tickerbet_model_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("model_family", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("training_window_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("training_window_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("company_count", sa.Integer(), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("train_count", sa.Integer(), nullable=False),
        sa.Column("test_count", sa.Integer(), nullable=False),
        sa.Column("feature_columns", sa.JSON(), nullable=True),
        sa.Column("metrics", sa.JSON(), nullable=True),
        sa.Column("artifact_prefix", sa.String(length=512), nullable=True),
        sa.Column("dataset_key", sa.String(length=512), nullable=True),
        sa.Column("model_keys", sa.JSON(), nullable=True),
        sa.Column("metadata_key", sa.String(length=512), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id"),
    )
    op.create_index("ix_tickerbet_run_started", "tickerbet_model_runs", ["started_at"], unique=False)
    op.create_index("ix_tickerbet_run_status", "tickerbet_model_runs", ["status"], unique=False)


def downgrade():
    op.drop_index("ix_tickerbet_run_status", table_name="tickerbet_model_runs")
    op.drop_index("ix_tickerbet_run_started", table_name="tickerbet_model_runs")
    op.drop_table("tickerbet_model_runs")
