# Backend Stream & Endpoint Requests for Frontend

## Current State of the Data

Checked all live endpoints — here's what the frontend is getting:

| Section | Endpoint | Status | Issue |
|---------|----------|--------|-------|
| Top Story / Predictions | `/api/predictions` | Has data | Working — but the "top story" selection is just confidence-sorted. Needs LLM curation. |
| Signal Wire | `/api/signals/matches` | Overpopulated | Returns every raw match (many duplicates per ticker per run). Needs aggregation into a digest per-ticker. |
| Sentiment Desk | `/api/sentiment` | **Empty** | Returns `[]`. The `/api/indices` endpoint also returns empty objects. Articles exist but are unprocessed (`summary: null`, `company: null`). The article processing pipeline hasn't run. |
| Headlines | `/api/articles` | Has data | Titles present but **all summaries are null** and most `company` fields are null. Articles were fetched but never processed through the LLM summarizer. |
| Market Brief | `/api/reports/latest` | Has data | Working. |
| Prediction Reasoning | `/api/predictions` | Has data | `reasoning` field is populated (LLM-generated). |

### Root Causes

1. **Articles not processed**: Articles have `processed: false` — the `process_single_article` pipeline (scrape → summarize → embed) hasn't run on them. Until it does, there are no summaries, no company associations for most articles, no ChromaDB embeddings, and therefore no sentiment scores.

2. **Signal Wire noise**: The matches endpoint returns every individual signal hit. When the engine runs, PLTR gets `Bearish Volume Divergence`, `Multi-Source Coverage`, `Near 52-Week High`, `Insider Cluster Buy`, etc. — all as separate rows. This should be an LLM-curated digest: "PLTR: 6 signals detected, net bullish at 65% — volume divergence countered by strong multi-source coverage and insider buying."

3. **Sentiment empty**: Depends on articles being processed and embedded into ChromaDB with sentiment metadata. Zero processed articles = zero sentiment.

---

## SSE Streams Needed

Based on `docs/sse-frontend.md`, here are the streams the frontend needs and the **logic behind each**:

### 1. `signals:ticker_digest` (NEW — needs backend implementation)

**What the frontend shows**: Signal Wire column — one card per ticker, with a synthesized summary.

**Current problem**: `signals:match_fired` gives raw individual matches. The frontend gets 10+ rows for PLTR alone.

**Requested logic**:
- After `signals:analysis_complete`, group all matches from that run by ticker
- For each ticker with 2+ matches, call the LLM to synthesize a **ticker digest**: a 1-2 sentence summary weighing the signals against each other, with a net direction and confidence
- Emit `signals:ticker_digest` with:
  ```json
  {
    "symbol": "PLTR",
    "direction": "bullish",
    "net_confidence": 0.65,
    "match_count": 6,
    "digest": "PLTR shows net bullish bias: insider cluster buying and 8-source coverage outweigh bearish volume divergence. Near 52-week high adds momentum.",
    "matches": ["Insider Cluster Buy", "Multi-Source Coverage", "Bearish Volume Divergence", "Near 52-Week High", "Multi-5-Source Coverage", "Sentiment Surge"]
  }
  ```
- The frontend will display these digests in the Signal Wire instead of raw matches
- This is an **AI-generated, SSE-streamed field** — the digest text should stream token-by-token like chat does

**Backend endpoint also needed**: `GET /api/signals/digests` — returns the latest ticker digests (persisted from the last engine run) so the frontend can hydrate on page load without waiting for a live SSE event.

### 2. `news:article_processed` (EXISTS — but never fires)

**What the frontend shows**: Headlines column — article title + AI summary + company tag.

**Current problem**: Articles are fetched but `process_single_article` never runs. Summaries are null, company associations are null.

**Requested fix**: Ensure the Celery pipeline processes articles after fetching them. The `news:article_processed` event already exists in the SSE spec. When it fires, the frontend will:
- Invalidate the `articles` TanStack Query cache to refetch with summaries
- Show a brief "new article" indicator

**No new stream needed** — just need the processing pipeline to actually run, and the SSE event to fire when it completes.

### 3. `signals:analysis_complete` (EXISTS — frontend needs to react)

**What the frontend shows**: Dashboard refreshes predictions, signal wire, market brief.

**Requested behavior**: When this fires, the frontend invalidates:
- `predictions` query
- `signalMatches` query (or `signalDigests` once that exists)
- `latestReport` query

**No backend change needed** — this is frontend-side wiring into the SSE listener.

### 4. `reports:generated` (EXISTS — frontend needs to react)

**What the frontend shows**: Market Brief section updates with new report.

**Requested behavior**: When this fires with `{report_id, summary}`, the frontend:
- Updates the Market Brief section immediately with the streamed summary
- Invalidates the `reports` query cache

**No backend change needed** — frontend wiring only.

### 5. Sentiment hydration

**What the frontend shows**: Sentiment Desk — per-ticker sentiment scores with bar visualization.

**Current problem**: `/api/sentiment` returns `[]` because no articles are processed/embedded.

**Requested fix**: This is downstream of fix #2. Once articles are processed and embedded into ChromaDB with company sentiments, the existing `get_sentiment_index()` function will return data. No new endpoint needed.

**Additionally**: When `news:article_processed` fires, the frontend should also invalidate the `sentiment` query to pick up new scores.

**Sentiment Desk display rules**:
- Scores are **cumulative over a 1-week rolling window** (not per-hour or per-run)
- Scores are **primacy weighted** — articles where the ticker is the primary subject carry more weight than articles where it's mentioned in passing. The `company_relevances` metadata in ChromaDB already tags each ticker as `primary` or `secondary`. The sentiment calculation should weight primary mentions higher (e.g. 1.0) vs secondary mentions (e.g. 0.3) when computing the aggregate score.
- The frontend displays the weighted score per ticker, sorted by total mention count descending

---

## Summary of Backend Work Needed

### Must build:
1. **Ticker digest LLM node** — post-analysis step that groups matches by ticker, calls LLM to synthesize a weighted summary, persists the result
2. **`signals:ticker_digest` SSE event** — emitted after each digest is generated, with token streaming for the digest text
3. **`GET /api/signals/digests` REST endpoint** — returns persisted digests for page-load hydration

### Must fix:
4. **Article processing pipeline** — articles are fetched but never processed. Need to ensure `process_single_article` runs (likely a Celery task chain issue — fetch → process should be wired up)
5. **Emit `news:article_processed` SSE event** — when article processing completes, fire the event so the frontend knows to refresh

### Already working (frontend just needs to wire up):
6. `signals:analysis_complete` → invalidate predictions + matches queries
7. `reports:generated` → update market brief
8. `prices:update` → invalidate price queries
