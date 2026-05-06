"""rename tickers to companies, add description

Revision ID: a1b2c3d4e5f6
Revises: 715d9926ec42
Create Date: 2026-05-05 23:40:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "a1b2c3d4e5f6"
down_revision = "715d9926ec42"
branch_labels = None
depends_on = None


def upgrade():
    op.rename_table("tickers", "companies")

    op.add_column("companies", sa.Column("description", sa.Text(), nullable=True))

    # Rename indexes on companies
    op.execute("ALTER INDEX ix_tickers_symbol RENAME TO ix_companies_symbol")

    # price_history: rename column + constraints + indexes
    op.alter_column("price_history", "ticker_id", new_column_name="company_id")
    op.drop_constraint("uq_ticker_timestamp", "price_history", type_="unique")
    op.create_unique_constraint("uq_company_timestamp", "price_history", ["company_id", "timestamp"])
    op.execute("ALTER INDEX ix_price_history_ticker_id RENAME TO ix_price_history_company_id")
    op.execute("ALTER INDEX ix_price_ticker_ts RENAME TO ix_price_company_ts")

    # news_articles: rename column + constraints + indexes
    op.alter_column("news_articles", "ticker_id", new_column_name="company_id")
    op.execute("ALTER INDEX ix_news_articles_ticker_id RENAME TO ix_news_articles_company_id")
    op.execute("ALTER INDEX ix_article_ticker_pub RENAME TO ix_article_company_pub")


def downgrade():
    # news_articles: revert
    op.execute("ALTER INDEX ix_article_company_pub RENAME TO ix_article_ticker_pub")
    op.execute("ALTER INDEX ix_news_articles_company_id RENAME TO ix_news_articles_ticker_id")
    op.alter_column("news_articles", "company_id", new_column_name="ticker_id")

    # price_history: revert
    op.execute("ALTER INDEX ix_price_company_ts RENAME TO ix_price_ticker_ts")
    op.execute("ALTER INDEX ix_price_history_company_id RENAME TO ix_price_history_ticker_id")
    op.drop_constraint("uq_company_timestamp", "price_history", type_="unique")
    op.create_unique_constraint("uq_ticker_timestamp", "price_history", ["ticker_id", "timestamp"])
    op.alter_column("price_history", "company_id", new_column_name="ticker_id")

    op.execute("ALTER INDEX ix_companies_symbol RENAME TO ix_tickers_symbol")
    op.drop_column("companies", "description")
    op.rename_table("companies", "tickers")
