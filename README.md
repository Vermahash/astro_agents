# astro_agents

Work directory for the **new** KP astrology system: interactive web app + personal Telegram bot.

**Full build plan (done + remaining):** [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)  
**Product intent:** [PRD.md](PRD.md) · **HTTP API:** [API.md](API.md)

## Streamlit stays untouched

| Location | Role |
|----------|------|
| `B:\n8n\astro\kp-calculator` | **LIVE** Streamlit KP Calculator (GitHub `Vermahash/kpastro` @ `v2`) � do not break |
| `E:\astro_agents\engine\` | **Vendor copy** of that code for this project to import |

Do **not** point Streamlit Cloud at `E:\astro_agents`.

When you fix math in the live Streamlit repo, re-sync:

```powershell
robocopy "B:\n8n\astro\kp-calculator" "E:\astro_agents\engine" /E /XD .git __pycache__ data\runtime /NFL /NDL /NJH /NJS
```

## Layout

```
E:\astro_agents\
??? PRD.md                 # Product requirements (decisions locked)
??? API.md                 # Service API
??? engine/                # Vendor copy of KP math
??? api/                   # FastAPI chart + usage (M1)
??? web/                   # React+Vite app (M2)
??? telegram/              # Personal bot (M3) � allowlist extensible
??? shared/                # Cache, config, chart service, tools, ask agent
??? mcp_server/            # MCP stdio server (same chart tools)
??? tests/
??? data/                  # chart cache, sqlite, rag
```

## Locked product choices

| Topic | Choice |
|-------|--------|
| Web | React + Vite ? FastAPI (scalable split) |
| LLM | Muse Glimmer default, Gemini Flash fallback |
| Budget | **$5/mo** hard cap |
| Users | You now; allowlist can grow |
| Host | Laptop now; env-based VPS migrate later |

## Run chart API (M1)

```bash
cd E:\astro_agents
pip install -r requirements.txt
uvicorn api.app:app --reload --port 8080
```

Keep this terminal open � chart and ask print a live pipeline (node, ms, tokens, tools, errors).
The same lines are also written to `data/logs/pipeline.log`. Live-tail:

```powershell
Get-Content E:\astro_agents\data\logs\pipeline.log -Wait -Tail 40
```

Ask uses a **tool agent**: Muse Glimmer (or MiniMax M3) calls chart tools against SQLite. If tools fail, it falls back to the keyword packet planner.

**A/B testing (web composer):** pick **Model** (`DeepSeek V4 Flash` / `Muse Glimmer` / MiniMax) and **Prompt** (`Planet taste` vs default). MiniMax often 429s on NIM trial — prefer DeepSeek for comparison.

## MCP server (same tools)

```powershell
cd E:\astro_agents
python -m mcp_server.chart_mcp
```

Point Cursor MCP config at that stdio command to inspect chart fields from the IDE.

## Run web app (M2 shell)

```bash
cd E:\astro_agents\web
npm install
npm run dev
```

Open http://localhost:5173 � sidebar chat history; reopening a chat restores messages + chart context.
API must be on :8080 (Vite proxies `/v1`). Both processes must be running or the UI looks blank / fails to load.

## Run Streamlit (unchanged, from B:)

```bash
cd /d B:\n8n\astro\kp-calculator
streamlit run astro_kp_v2.py
```

## Canonical math

`engine/astro_kp.py` ? `calculate_vedic_charts` (Krishnamurti / KP). Never reimplement in the LLM.
