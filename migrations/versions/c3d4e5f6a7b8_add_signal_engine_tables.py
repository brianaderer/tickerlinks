"""add signal engine tables

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-05-06 01:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade():
    # Signals
    op.create_table(
        "signals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), unique=True, nullable=False),
        sa.Column("signal_type", sa.String(50), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("parameters", sa.JSON(), default={}),
        sa.Column("historical_accuracy", sa.Float(), default=0.0),
        sa.Column("active", sa.Boolean(), nullable=False, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_signals_type", "signals", ["signal_type"])

    # Signal matches
    op.create_table(
        "signal_matches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("signal_id", sa.Integer(), sa.ForeignKey("signals.id"), nullable=False),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("context", sa.JSON(), default={}),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_signal_matches_signal_id", "signal_matches", ["signal_id"])
    op.create_index("ix_signal_matches_company_id", "signal_matches", ["company_id"])
    op.create_index("ix_match_company_detected", "signal_matches", ["company_id", "detected_at"])

    # Predictions
    op.create_table(
        "predictions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("reasoning", sa.Text()),
        sa.Column("target_date", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_predictions_company_id", "predictions", ["company_id"])

    # Prediction <-> SignalMatch join
    op.create_table(
        "prediction_match",
        sa.Column("prediction_id", sa.Integer(), sa.ForeignKey("predictions.id"), nullable=False),
        sa.Column("signal_match_id", sa.Integer(), sa.ForeignKey("signal_matches.id"), nullable=False),
        sa.PrimaryKeyConstraint("prediction_id", "signal_match_id"),
    )

    # Backtests
    op.create_table(
        "backtests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("prediction_id", sa.Integer(), sa.ForeignKey("predictions.id"), unique=True, nullable=False),
        sa.Column("actual_direction", sa.String(10)),
        sa.Column("actual_magnitude", sa.Float()),
        sa.Column("accuracy_score", sa.Float()),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Insider trades
    op.create_table(
        "insider_trades",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("filer_name", sa.String(255), nullable=False),
        sa.Column("filer_title", sa.String(255)),
        sa.Column("transaction_type", sa.String(50), nullable=False),
        sa.Column("shares", sa.Float(), nullable=False),
        sa.Column("price_per_share", sa.Float()),
        sa.Column("total_value", sa.Float()),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("filing_url", sa.Text(), unique=True, nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_insider_trades_company_id", "insider_trades", ["company_id"])
    op.create_index("ix_insider_company_date", "insider_trades", ["company_id", "transaction_date"])

    # Fundamentals
    op.create_table(
        "fundamentals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("pe_trailing", sa.Float()),
        sa.Column("pe_forward", sa.Float()),
        sa.Column("eps_trailing", sa.Float()),
        sa.Column("eps_forward", sa.Float()),
        sa.Column("dividend_yield", sa.Float()),
        sa.Column("beta", sa.Float()),
        sa.Column("fifty_two_week_high", sa.Float()),
        sa.Column("fifty_two_week_low", sa.Float()),
        sa.Column("market_cap", sa.BigInteger()),
        sa.Column("current_price", sa.Float()),
        sa.Column("snapshot_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fundamentals_company_id", "fundamentals", ["company_id"])
    op.create_index("ix_fundamentals_company_snap", "fundamentals", ["company_id", "snapshot_at"])


def downgrade():
    op.drop_table("fundamentals")
    op.drop_table("insider_trades")
    op.drop_table("backtests")
    op.drop_table("prediction_match")
    op.drop_table("predictions")
    op.drop_table("signal_matches")
    op.drop_table("signals")
