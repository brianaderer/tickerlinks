"""insider_trade filing_url non-unique

Revision ID: m3h4i5j6k7l8
Revises: l2g3h4i5j6k7
Create Date: 2026-05-07
"""
from alembic import op

revision = "m3h4i5j6k7l8"
down_revision = "l2g3h4i5j6k7"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("insider_trades_filing_url_key", "insider_trades", type_="unique")
    op.create_index("ix_insider_filing_url", "insider_trades", ["filing_url"])


def downgrade():
    op.drop_index("ix_insider_filing_url", "insider_trades")
    op.create_unique_constraint("insider_trades_filing_url_key", "insider_trades", ["filing_url"])
