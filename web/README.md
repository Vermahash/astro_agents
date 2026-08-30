# Web app (React + Vite)

Interactive UI for Brahma Daivagya: **sidebar chat history** + main conversation.
Reopening a chat restores messages and attached KP chart context.

## Run (API must be up)

```bash
# terminal 1
cd E:\astro_agents
uvicorn api.app:app --reload --port 8080

# terminal 2
cd E:\astro_agents\web
npm install
npm run dev
```

Open http://localhost:5173

Vite proxies `/v1` → `http://127.0.0.1:8080`.

## Behavior

- **Place of birth** typeahead uses the same city CSV / `search_city` logic as Streamlit KP v2 (`GET /v1/places`) and autofills lat/lon.
- **New chat** creates a thread in the sidebar.
- **Compute chart** calls `POST /v1/charts`, attaches context, and shows **South-Indian kundali** + planet/cusp tables.
- **History** in `localStorage`; reopening restores messages + chart + place fields.
- Interpretive LLM `/ask` still stubbed until the next milestone.
