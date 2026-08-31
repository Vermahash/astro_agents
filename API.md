# API.md — Chart & Ask service

Pipeline flow charts (chart compute, ask routing, PRE-AUDIT, RAG, MCP): [README.md](README.md).

Base URL (laptop): `http://127.0.0.1:8080`

Watch the **uvicorn terminal** for pipeline traces (`[trace:�] [chart|ask]`) on every chart/ask call.
Same lines append to `data/logs/pipeline.log`.

Ask pipeline (M2.5 tool agent):

1. `tool_agent` � Muse Glimmer calls chart tools (`list_chart_fields`, `get_chart_slice`, �)
2. Tools read SQLite `data/sqlite/charts.db` (precomputed fields only)
3. Fallback: keyword `plan_packet` + single synthesize if tools unsupported / unused

## Run

```bash
cd E:\astro_agents
pip install -r requirements.txt
uvicorn api.app:app --reload --port 8080
```

Ensure `engine/global_cities_full.csv` exists if you use city search (chart compute with lat/lon does not need it).

## MCP chart tools (same registry)

```bash
python -m mcp_server.chart_mcp
```

Tools: `list_chart_fields`, `get_chart_meta`, `get_chart_slice`, `get_cusp`, `get_planet`, `search_places`, `get_harness_plan`, `search_books`, `search_classical_law`, `run_chart_query`.

## Endpoints

### `GET /health`

```json
{ "status": "ok" }
```

### `POST /v1/charts`

Compute or return cached KP chart via `engine.astro_kp.calculate_vedic_charts`.
Also upserts field rows into SQLite for tool lookups.

**Request**

```json
{
  "name": "Test",
  "datetime_iso": "1990-01-15T14:30:00+05:30",
  "lat": 28.6139,
  "lon": 77.2090,
  "gender": "Male",
  "force_recompute": false
}
```

**Response**

```json
{
  "chart_key": "sha256...",
  "cached": false,
  "engine_version": "kpastro-v2",
  "meta": {
    "name": "Test",
    "datetime_iso": "1990-01-15T14:30:00+05:30",
    "lat": 28.6139,
    "lon": 77.2090,
    "gender": "Male",
    "lagna": "...",
    "moon_nakshatra": "..."
  },
  "structured_payload": {}
}
```

Second identical request returns `"cached": true`.

### `GET /v1/charts/{chart_key}`

Fetch a previously computed chart from disk cache. `404` if missing.

### `POST /v1/ask`

Interpretive Q&A with NVIDIA NIM:

- **model** (optional): `meta/muse-glimmer-30b` | `deepseek-ai/deepseek-v4-flash-0731` | `minimaxai/minimax-m3`  
  Aliases: `muse` / `deepseek` / `minimax`  
  **Note:** MiniMax on NIM trial often returns **HTTP 429** after multi-round tool calls. DeepSeek/MiniMax run **single-shot** synthesize (tools off) to reduce rate limits.
- **prompt_profile**: `pre_audit` (default in web — PRE-AUDIT Brain), `default` (Gem + KP strict), or `planet_taste`

**Request**

```json
{
  "chart_key": "sha256...",
  "question": "What taste does Moon give from its star/sub?",
  "history": [],
  "max_tokens": 4096,
  "model": "deepseek-ai/deepseek-v4-flash-0731",
  "prompt_profile": "pre_audit",
  "use_web_law": false
}
```

### `GET /v1/models`

```json
{
  "default": "meta/muse-glimmer-30b",
  "models": [
    { "id": "meta/muse-glimmer-30b", "alias": "muse", "supports_tools": true },
    { "id": "deepseek-ai/deepseek-v4-flash-0731", "alias": "deepseek", "supports_tools": false },
    { "id": "minimaxai/minimax-m3", "alias": "minimax", "supports_tools": false, "notes": "often 429" }
  ]
}
```

**Response**

```json
{
  "answer": "...",
  "model": "meta/muse-glimmer-30b",
  "chart_key": "sha256...",
  "prompt_tokens": 1200,
  "completion_tokens": 400,
  "estimated_cost_usd": 0.002,
  "trace_id": "abcdef...",
  "mode": "harness",
  "tools_used": [],
  "pipeline_trace": { "trace_id": "abcdef...", "kind": "ask", "total_ms": 3200.5, "steps": [] },
  "packet_plan": { "keys": ["natal_core", "ashtakavarga_sav"], "rationale": "harness domains=['finance']" },
  "harness_plan": { "domain": "finance", "keys": [], "specialists": ["bphs", "varga_sav"] },
  "specialist_audit": [{ "id": "sav_h11", "status": "SUPPORTS", "cite": "H11 SAV=40" }],
  "rag_hits": [],
  "critic": { "ok": true, "issues": [] }
}
```

`mode` is `harness` (PRE-AUDIT Brain), `harness_fallback` (Python synthesizer if NIM times out), `tools`, or `fallback_planner`.

### `GET /v1/harness/aspects`

BPHS 12-bhava names plus every PRE-AUDIT life aspect (houses, Nadi sets, KP cusps, book query). No LLM.

### `GET /v1/harness/plan?q=`

Preview domain routing (no LLM). Joins multiple life aspects, e.g. `q=Tell me about health and finances` or `q=Will I buy a house?` (home/Sukha). Unmatched questions use `general` (life survey).

### `POST /v1/rag/index`

Rebuild HNSW index from `ASTRO_N8N_ROOT/knowledge`, `kp-calculator/docs`, extracted KP book JSON, and repo `docs/prompts`.

### `GET /v1/rag/search?q=&k=5`

Doctrine search over the local RAG index. Does not return chart numbers.

### `POST /v1/harness/audit`

Python-only PRE-AUDIT (no LLM): domain plan, SAV, specialist checkpoint table.

```json
{ "chart_key": "sha256...", "question": "Tell me about his finances", "use_rag": false }
```

### `GET /v1/places?q=&limit=20`

Typeahead place search (same `search_city` / city CSV as Streamlit KP v2).  
Requires `q` length ? 3.

```json
{
  "results": [
    { "label": "Delhi, India", "lat": 28.7041, "lon": 77.1025 }
  ]
}
```

### `GET /v1/usage`

```json
{
  "monthly_budget_usd": 5.0,
  "spent_usd": 0.0,
  "remaining_usd": 5.0,
  "default_llm": "nvidia/muse-glimmer",
  "fallback_llm": "gemini-flash",
  "allowlist_count": 0
}
```

Set allowlist via `ASTRO_ALLOWLIST_IDS=123,456`. Budget via `ASTRO_MONTHLY_BUDGET_USD=5`.

## Notes

- Web (Vite/React) and Telegram are clients of this API.
- Live Streamlit on `B:\n8n\astro\kp-calculator` does not use these endpoints.
- `datetime_iso` **must** include a timezone offset.
- LLM never invents chart math; tools only return engine-computed fields.
