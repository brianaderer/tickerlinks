# Research Agent, Prediction Overhaul, Signal Wire Digests

## What Changed

### 1. Research Agent (`app/signals/research/`)
New LangGraph agent that searches the Typesense article database via tool calls. It plans queries, executes vector+filtered searches, evaluates coverage gaps, and refines up to 3 times. Returns up to 10 full-text articles with dates and metadata.

- `agent.py`: StateGraph (plan_query -> search -> evaluate -> refine loop), `@tool research_company`, `run_research()`
- `prompts.py`: Temporally-aware system prompts for query planning and gap evaluation

### 2. Prediction Overhaul

**predict_node rewrite** (`app/signals/nodes/predict.py`):
- Now runs a tool-calling agent loop instead of a single LLM call
- LLM receives full context: signals + price action + fundamentals
- LLM calls `research_company` tool to search articles (up to 3 tool calls per prediction)
- Returns structured JSON: direction, confidence, magnitude, reasoning
- `<think>` tags properly stripped with `[\s\S]*?` pattern

**Magnitude** (`app/models/prediction.py`):
- New `magnitude` float column (0.0-1.0) representing "how much you should care"
- LLM judges magnitude based on signal purity, alignment, count, diversity, and conviction
- Conflicting signals may produce high magnitude (volatile) or low magnitude (noise) — the model decides

**Upsert per company** (`app/signals/nodes/output.py`):
- One live prediction per company — existing predictions are updated in place instead of inserting duplicates
- Signal matches are re-linked on each update

**Beat schedule** (`app/extensions.py`):
- Signal analysis now runs every 15 minutes (was 60 minutes)

**API** (`app/api/routes.py`):
- `/predictions` returns only the latest prediction per company (deduplicated via `max(created_at)` subquery)
- Response includes `magnitude` field

**Frontend**:
- `PredictionCard` shows magnitude as a labeled badge (High/Medium/Low with percentage)
- `Prediction` type includes `magnitude: number | null`

### 3. Signal Wire -> Digests

The Dashboard Signal Wire was showing raw individual `SignalMatch` rows (duplicated across runs). Now it shows **Signal Digests** — aggregated, LLM-synthesized summaries per company.

- Added `SignalDigest` type and `useSignalDigests()` hook (`frontend/src/api/signals.ts`)
- Dashboard swapped from `useSignalMatches()` to `useSignalDigests()`
- Each digest shows: company, direction badge, AI-generated assessment, signal count, timestamp

## Schema Changes

### New column: `predictions.magnitude`
```sql
ALTER TABLE predictions ADD COLUMN magnitude FLOAT;
```
Migration: `migrations/versions/j0e1f2g3h4i5_add_prediction_magnitude.py`

### Prerequisite: `article_companies` table
Migration: `migrations/versions/i9d0e1f2g3h4_article_companies_m2m.py`

### Prerequisite: `signal_digests` table
Migration: `migrations/versions/h8c9d0e1f2g3_add_signal_digests.py`

## Deployment Steps

### 1. Run all pending migrations
```bash
docker compose exec web flask db upgrade
```
This creates `article_companies`, `signal_digests`, and adds `predictions.magnitude`.

### 2. Reprocess articles (for M2M company tags)
```bash
docker compose exec web flask shell
```
```python
from app.extensions import db
from app.models import NewsArticle
NewsArticle.query.update({NewsArticle.processed: False})
db.session.commit()
```
```bash
docker compose exec web flask process-articles
```

### 3. Trigger a signal analysis cycle
Either wait 15 minutes for the beat schedule, or manually:
```bash
docker compose exec web flask shell
```
```python
from app.tasks.analyze import run_signal_analysis
run_signal_analysis.delay()
```
This will:
- Run all signal detectors
- Aggregate signals into predictions (with research agent + magnitude)
- Generate signal digests
- The Dashboard Signal Wire and Predictions will populate

### 4. Verify
```bash
# Check predictions have magnitude
curl -s http://localhost:5001/api/predictions | python3 -m json.tool | head -20

# Check digests exist
curl -s http://localhost:5001/api/signals/digests | python3 -m json.tool

# Check no duplicate predictions per company
curl -s http://localhost:5001/api/predictions | python3 -c "
import sys, json
preds = json.load(sys.stdin)
companies = [p['company'] for p in preds]
dupes = [c for c in companies if companies.count(c) > 1]
print(f'{len(preds)} predictions, {len(set(dupes))} duplicated companies')
"
```

## Files Created
| File | Purpose |
|------|---------|
| `app/signals/research/__init__.py` | Package init |
| `app/signals/research/agent.py` | Research agent StateGraph + tool |
| `app/signals/research/prompts.py` | LLM prompts for query planning and evaluation |
| `migrations/versions/j0e1f2g3h4i5_add_prediction_magnitude.py` | Add magnitude column |

## Files Modified
| File | Change |
|------|--------|
| `app/signals/nodes/predict.py` | Full rewrite: tool-calling agent loop with research + full context |
| `app/signals/nodes/output.py` | Upsert per company instead of blind INSERT |
| `app/models/prediction.py` | Added `magnitude` column |
| `app/extensions.py` | Beat schedule 3600 -> 900 |
| `app/api/routes.py` | Latest-per-company query + magnitude in response |
| `frontend/src/types.ts` | Added `SignalDigest` interface, `magnitude` on `Prediction` |
| `frontend/src/api/signals.ts` | Added `useSignalDigests()` hook |
| `frontend/src/pages/Dashboard.tsx` | Signal Wire uses digests instead of raw matches |
| `frontend/src/components/PredictionCard.tsx` | Magnitude badge display |
