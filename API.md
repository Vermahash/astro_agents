# API.md � Chart & Ask service

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

Tools: `list_chart_fields`, `get_chart_meta`, `get_chart_slice`, `get_cusp`, `get_planet`, `search_places`.

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
- **prompt_profile**: `default` (Gem + KP strict) or `planet_taste` (`docs/prompts/PLANET_TASTE.md`)

**Request**

```json
{
  "chart_key": "sha256...",
  "question": "What taste does Moon give from its star/sub?",
  "history": [],
  "max_tokens": 4096,
  "model": "deepseek-ai/deepseek-v4-flash-0731",
  "prompt_profile": "planet_taste"
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
  "mode": "tools",
  "tools_used": [{ "name": "get_chart_slice", "ms": 2.1, "bytes": 1200, "ok": true }],
  "pipeline_trace": { "trace_id": "abcdef...", "kind": "ask", "total_ms": 3200.5, "steps": [] },
  "packet_plan": null
}
```

`mode` is `tools` or `fallback_planner`. Requires `NVIDIA_API_KEY`. Enforces `ASTRO_MONTHLY_BUDGET_USD` (default 5).

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
