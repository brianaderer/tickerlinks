"""article_companies many-to-many join table

Revision ID: i9d0e1f2g3h4
Revises: h8c9d0e1f2g3
Create Date: 2026-05-07 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "i9d0e1f2g3h4"
down_revision = "h8c9d0e1f2g3"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "article_companies",
        sa.Column("article_id", sa.Integer(), sa.ForeignKey("news_articles.id"), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), primary_key=True),
        sa.Column("sentiment", sa.String(10), nullable=True),
        sa.Column("relevance", sa.String(10), nullable=True),
    )

    op.drop_index("ix_article_company_pub", table_name="news_articles")
    op.drop_constraint("news_articles_company_id_fkey", "news_articles", type_="foreignkey")
    op.drop_index("ix_news_articles_company_id", table_name="news_articles")
    op.drop_column("news_articles", "company_id")


def downgrade():
    op.add_column("news_articles", sa.Column("company_id", sa.Integer(), nullable=True))
    op.create_index("ix_news_articles_company_id", "news_articles", ["company_id"])
    op.create_foreign_key("news_articles_company_id_fkey", "news_articles", "companies", ["company_id"], ["id"])
    op.create_index("ix_article_company_pub", "news_articles", ["company_id", "published_at"])

    op.drop_table("article_companies")
