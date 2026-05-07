# Signal Wire: Empty State Fix

## Problem
The Dashboard Signal Wire shows "No signal digests yet" because:
1. The `signal_digests` table doesn't exist — migration `h8c9d0e1f2g3` hasn't been run
2. No signal analysis cycle has completed since the Dashboard was switched from raw `SignalMatch` rows to aggregated `SignalDigest` entries

## What Changed
The Dashboard Signal Wire was rendering every individual signal firing (e.g. "PLTR - Bearish Volume Divergence" duplicated across runs). It now uses the `/signals/digests` endpoint which returns one LLM-synthesized summary per company per analysis cycle.

The digest generation already exists in the backend (`app/signals/nodes/digest.py`) — it runs as the final node in the signal engine LangGraph pipeline. It just needs the table created and a cycle to run.

## Deployment Steps

### 1. Run migrations
```bash
docker compose exec web flask db upgrade
```
Key migration: `h8c9d0e1f2g3_add_signal_digests.py` creates the `signal_digests` table.

### 2. Trigger a signal analysis cycle
Either wait for the next Celery beat, or manually:
```bash
docker compose exec web flask shell
```
```python
from app.tasks.analyze import run_signal_analysis
run_signal_analysis.delay()
```
The `digest_node` at the end of the pipeline will generate digests and populate the Signal Wire.

### 3. Verify
```bash
curl -s http://localhost:5001/api/signals/digests | python3 -m json.tool
```
Should return one entry per company with `symbol`, `direction`, `net_confidence`, `match_count`, `digest` text, and `generated_at`.
