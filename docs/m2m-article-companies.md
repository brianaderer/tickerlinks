# Many-to-Many Article-Company Associations

## What Changed

### Problem
Articles could only be tagged with a single company via a `company_id` FK on `news_articles`. The LLM-based ticker matcher (`match_tickers`) identifies multiple companies per article with sentiment and relevance, but those results were only written to Typesense -- never back to SQL. The frontend showed a single company tag (usually null) per article.

### Schema Change
- **Dropped**: `company_id` column, `ix_article_company_pub` index, and FK constraint from `news_articles`
- **Added**: `article_companies` join table with columns:
  - `article_id` (PK, FK -> news_articles.id)
  - `company_id` (PK, FK -> companies.id)
  - `sentiment` (string: bullish/bearish/neutral)
  - `relevance` (string: primary/secondary)
- **Migration**: `migrations/versions/i9d0e1f2g3h4_article_companies_m2m.py`

### Files Modified
| File | Change |
|------|--------|
| `app/models/article.py` | Added `article_companies` table definition and M2M relationship on `NewsArticle` |
| `app/models/company.py` | Removed old `articles` FK-based relationship (replaced by M2M backref) |
| `app/models/__init__.py` | Exports `article_companies` and `SignalDigest` |
| `app/articles/processor.py` | `_process_article()` now writes matched companies to `article_companies` table |
| `app/sources/news.py` | Removed `_match_company` method and fetch-time company assignment |
| `app/api/routes.py` | `/articles` and `/articles/<id>` return `companies[]` array; company filter uses join table |
| `app/signals/nodes/gather.py` | Article query uses join through `article_companies` instead of `company_id` |
| `frontend/src/types.ts` | `NewsArticle.company` replaced with `companies: ArticleCompany[]` |
| `frontend/src/pages/Articles.tsx` | Renders sentiment-colored company badges |
| `frontend/src/pages/ArticleReader.tsx` | Renders sentiment-colored company badges |
| `frontend/src/pages/Dashboard.tsx` | Renders company badges from `companies[]` |

### API Shape Change
Before:
```json
{ "company": "NVDA" }
```
After:
```json
{
  "companies": [
    { "symbol": "NVDA", "sentiment": "bullish", "relevance": "primary" },
    { "symbol": "MRVL", "sentiment": "neutral", "relevance": "secondary" }
  ]
}
```

## Deployment Steps

### 1. Run the migration
```bash
docker compose exec web flask db upgrade
```
This creates the `article_companies` table and drops the `company_id` column from `news_articles`.

### 2. Reprocess all articles
All existing articles need to be reprocessed so `match_tickers` runs and populates the new join table. There is a CLI command for this:
```bash
docker compose exec web flask process-articles
```
This queues every article with `processed=False` into Celery. However, **articles that were already marked `processed=True` won't be re-queued**. To force reprocessing of all articles (so the join table gets populated for previously processed ones too), reset the flag first:
```bash
docker compose exec web flask shell
```
```python
from app.extensions import db
from app.models import NewsArticle
NewsArticle.query.update({NewsArticle.processed: False})
db.session.commit()
```
Then run:
```bash
docker compose exec web flask process-articles
```

### 3. Verify
```bash
# Check that the join table has rows
docker compose exec web flask shell -c "
from app.models.article import article_companies
from app.extensions import db
count = db.session.execute(article_companies.select()).fetchall()
print(f'{len(count)} article-company associations')
"

# Check a specific article via API
curl -s http://localhost:5001/api/articles/230 | python3 -m json.tool
```
The `companies` array should now contain matched tickers with sentiment and relevance.
