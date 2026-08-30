# IMPLEMENTATION_PLAN.md — Full build plan

**Canonical workdir:** `E:\astro_agents`  
**Frozen Streamlit:** `B:\n8n\astro\kp-calculator` (do not change for product features)  
**Related docs:** [PRD.md](PRD.md) (product intent) · [API.md](API.md) (HTTP contract) · [README.md](README.md) (how to run)

This is the **one document** for what to implement, what is done, and what remains. Prefer this over chat history when continuing work.

---

## 1. North star (target ecosystem)

**Today (M2.5–M2.6):** one LLM + chart tools + selective SQLite slices + optional packet planner fallback.

**Target (M4 harness — your vision):**

```
User question
    → Router (domain: finance / marriage / career / …)
    → Inventory builder (PRE-AUDIT checkpoint list for that domain)
    → Harness (Python only): fetch ONLY matching payload slices from SQLite
    → Optional RAG (books / doctrine — no numbers invented)
    → Specialist passes (optional, budget-gated): BPHS | Varga/SAV | Dasha/Nadi | KP | BNN
    → Brain synthesizer: 3-step PRE-AUDIT → inventory box → evidence audit → verdict
    → Critic: reject degrees/houses not in packet
    → User-facing formatted answer (finance-style tables)
```

**Hard rules**

| Rule | Detail |
|------|--------|
| Math | Only `engine.astro_kp.calculate_vedic_charts` — packet is authoritative |
| Harness | Agents receive **slices only**, not full dump (unless domain requires it) |
| PRE-AUDIT | Every answer: inventory → evidence audit → verdict ([PRE_AUDIT_DIRECTIVE.md](docs/prompts/PRE_AUDIT_DIRECTIVE.md)) |
| Streamlit | Frozen on `B:\` |
| Cost | `$5/mo` kill-switch; parallel specialists only when domain needs it |
| RAG | Doctrine/citations only — never replace packet numbers |

**Good news:** the engine **already computes** BPHS, bhava, shodashavarga, SAV/BAV, yogas, dasha, BNN, KP — in `structured_payload` (`natal_core`, `unified_kundali`, `ashtakavarga_sav`, `bnn_module`, `special_yogas`, `kp_*`, …). The gap is **routing + harness + multi-step Brain**, not missing math.

---

## 2. Target architecture

### Current (shipped — M2.5)

Single LLM + chart tools → SQLite slices → synthesize (KP-heavy today).

### Target harness (M4 — your finance-style ecosystem)

```mermaid
flowchart TB
  Q[User question]
  R[Domain router]
  I[Checkpoint inventory]
  H[Python harness slices only]
  RAG[RAG books optional]
  S1[BPHS specialist]
  S2[Varga SAV specialist]
  S3[Dasha Nadi specialist]
  S4[KP specialist]
  S5[BNN specialist]
  B[Brain PRE-AUDIT synthesizer]
  C[Critic verify]
  Out[Formatted answer]

  Q --> R --> I --> H
  H --> S1 & S2 & S3 & S4 & S5
  RAG -.-> B
  S1 & S2 & S3 & S4 & S5 --> B
  H --> B
  B --> C --> Out
```

| Stage | Module | Status |
|-------|--------|--------|
| Domain router | `shared/domain_harness.py` | Starter done |
| PRE-AUDIT | `docs/prompts/PRE_AUDIT_DIRECTIVE.md` | Done |
| Slice fetch | `chart_tools` / SQLite | Partial |
| Specialists + Brain | LangGraph or sequential nodes | Todo |
| RAG | `search_books` tool | Todo |
| Critic | packet number verifier | Todo |
| Output formatter | inventory box + audit tables | Todo |

Finance domain example: `classify_domain("finances")` → fetch `ashtakavarga_sav`, `bnn_module`, `unified_kundali`, yogas, KP cusps 2 & 11, Nadi `[2,6,10,11]` vs `[6,8,12]`.

### Runtime (laptop)

| Process | Command | Port |
|---------|---------|------|
| API | `uvicorn api.app:app --reload --port 8080` | 8080 |
| Web | `cd web && npm run dev` | 5173 |
| MCP (optional) | `python -m mcp_server.chart_mcp` | stdio |
| Trace tail | `Get-Content data\logs\pipeline.log -Wait -Tail 40` | — |

Env: copy `.env.example` → `.env` (`NVIDIA_API_KEY`, optional `NVIDIA_MODEL`).

---

## 3. Locked product choices

| Topic | Choice |
|-------|--------|
| Web | React + Vite → FastAPI |
| Default LLM | Muse Glimmer (`meta/muse-glimmer-30b`) |
| A/B LLMs | DeepSeek Flash (`deepseek-ai/deepseek-v4-flash-0731`); MiniMax often **429** on NIM |
| Prompts | `default` = ACTIVE_GEM + KP strict contract; `planet_taste` = placement/taste A/B |
| Budget | $5/mo hard cap |
| Users | You only; allowlist extensible |
| Host | Laptop now; env-based VPS later |

---

## 4. Milestone status

| ID | Deliverable | Status |
|----|-------------|--------|
| **M0** | Scaffold + engine vendor copy + PRD | **Done** |
| **M1** | Chart API + disk cache + places + usage | **Done** |
| **M2** | Web: chat history, place search, kundali, ask | **Done** |
| **M2.5** | SQLite field store + chart tools + MCP + tool agent + planner fallback + pipeline traces | **Done** |
| **M2.6** | Model A/B UI + planet_taste prompt + rate-limit handling | **Done** |
| **M3** | Telegram personal bot on same API | **Todo** |
| **M4** | **Harness ecosystem:** domain router, PRE-AUDIT Brain, specialists, RAG, critic, formatted output | **In progress** (router + directive started) |
| **M5** | Deploy packaging (api/web); Streamlit stays on B: | **Todo** |

---

## 5. What is already built (do not re-invent)

### API — `api/`

- `GET /health`, `GET /` → docs  
- `POST /v1/charts`, `GET /v1/charts/{key}`  
- `GET /v1/places`, `GET /v1/usage`, `GET /v1/models`  
- `POST /v1/ask` — `model`, `prompt_profile`, returns `tools_used`, `pipeline_trace`, `mode`

### Shared — `shared/`

| Module | Role |
|--------|------|
| `chart_service.py` | Compute/cache charts |
| `chart_store.py` | SQLite field rows (`data/sqlite/charts.db`) |
| `chart_tools.py` | Tool registry: list/meta/slice/cusp/planet/places |
| `ask_agent.py` | Tool-calling loop (Muse) |
| `ask_service.py` | Orchestrates tools → fallback planner |
| `packet_planner.py` | Keyword slice selection for fallback |
| `llm_nvidia.py` | NIM client + tools + rate-limit errors |
| `models_catalog.py` | Allowlisted models + `supports_tools` |
| `prompts.py` / `answer_contract.py` | Prompt profiles + KP strict overlay |
| `pipeline_trace.py` | Terminal + `data/logs/pipeline.log` |
| `usage.py` / `config.py` / `places.py` | Budget, env, city search |

### MCP — `mcp_server/chart_mcp.py`

Same tools as the agent registry (stdio for Cursor).

### Web — `web/`

Sidebar chats, place typeahead, kundali/panels, ask composer with **Model** + **Prompt** dropdowns.

### Prompts — `docs/prompts/`

- `ACTIVE_GEM.md` — pasted Gem  
- `PLANET_TASTE.md` — placement/taste A/B  
- `Gemini_instructionsKP.md` + `pmp/` — KP protocol pack  

### Tests — `tests/`

Chart cache, packet planner, tools/store/agent mock, models/prompts.

---

## 6. Remaining work — implement next

### M3 — Telegram bot

**Goal:** Phone access with same chart + ask backend.

**Build**

1. `telegram/bot.py` — aiogram or `python-telegram-bot`  
2. Allowlist from `ASTRO_ALLOWLIST_IDS`  
3. Commands: `/start`, `/chart` (birth fields), `/ask`, `/usage`  
4. Call `http://127.0.0.1:8080/v1/*` (or in-process shared services)  
5. Logging + unit tests for allowlist and message parsing  
6. Update README / API.md / this plan status  

**Out of scope for M3:** public bot, payments, multi-tenant.

---

### M4 — Harness ecosystem (Brain + specialists + RAG + critic)

**Goal:** Answers like your finance example — inventory box, parameter blocks, evidence audit table, verdict — with **only** Python packet slices (+ optional book RAG).

**Build order**

1. **Wire domain harness into ask** — `classify_domain()` → fetch only `DOMAIN_PAYLOAD_KEYS[domain]` (replace keyword-only `packet_planner` over time)  
2. **Brain prompt** — load `PRE_AUDIT_DIRECTIVE.md` + domain inventory title + slice JSON  
3. **Specialist nodes** (sequential first, parallel later if budget allows):  
   - BPHS: `natal_core`, `unified_kundali`, `special_yogas`  
   - Varga/SAV: `unified_kundali`, `ashtakavarga_sav`, `ashtakavarga_bav`  
   - Dasha/Nadi: dasha fields in `unified_kundali` / timeline + `kp_astrology_matrix` nadi tables  
   - KP: `cusps`, `planet_star_sub_lords`, `kp_prediction`  
   - BNN: `bnn_module`  
   Each specialist returns structured `{checkpoints: [{name, status, cite}]}` — no prose yet.  
4. **Brain synthesizer** — merges specialist JSON + runs Step 3 verdict; formats sections 1–10 from directive  
5. **RAG** — local HNSW over `engine/docs/books` + prompts; tool `search_books`; never inject numbers  
6. **Critic** — regex/JSON check: every degree/house cited must exist in packet; fail → INSUFFICIENT DATA  
7. **LangGraph** (optional orchestration) — same nodes, visible in `pipeline.log`  
8. Tests: finance question → plan keys include `ashtakavarga_sav`; critic rejects invented longitude  

**Anti-patterns:** full packet every turn; LLM recalculating SAV; multi-agent fan-out on trivial questions.

---

### M5 — Deploy

**Goal:** Run api+web off-laptop without rewriting.

**Build**

1. `Dockerfile` / compose for `api` + static `web` build  
2. Env-based CORS, host, budget  
3. Document VPS checklist  
4. Keep Streamlit deploy on B:/GitHub untouched  

---

### Quality / ops backlog (anytime)

| Item | Why |
|------|-----|
| Golden parity tests vs Streamlit samples | Success criterion #4 |
| Gemini Flash fallback wiring | PRD model ladder |
| Answer cache | Cost |
| Deterministic “field lookup” answers without LLM | Cost |
| MiniMax: keep optional; expect 429 on NIM trial | Known |
| DeepSeek: tools off by design (single-shot) | Rate-limit hygiene |
| Improve tool reliability on Muse | Empty content / reasoning budget |

---

## 7. Ask path (current behavior)

1. Load chart JSON + ensure SQLite rows  
2. Budget gate  
3. Load prompt (`default` or `planet_taste`)  
4. If `model_supports_tools` (Muse): tool agent loop  
5. Else (DeepSeek / MiniMax): packet planner + one synthesize  
6. Record usage; emit pipeline log  

**Tools:** `list_chart_fields`, `get_chart_meta`, `get_chart_slice`, `get_cusp`, `get_planet`, `search_places`

---

## 8. Feature completeness checklist (per new module)

When adding a module, ship all of:

- [ ] API endpoint (if user-facing)  
- [ ] Service logic  
- [ ] DB / cache interaction  
- [ ] Validation  
- [ ] Logging / pipeline marks  
- [ ] Unit tests  
- [ ] Docstrings on new modules  
- [ ] README + API.md + **this plan** status update  

---

## 9. Directory map

```
E:\astro_agents\
  IMPLEMENTATION_PLAN.md   ← you are here
  PRD.md, API.md, README.md
  .env.example
  api/                     FastAPI
  shared/                  services, tools, LLM, prompts
  mcp_server/              MCP stdio
  web/                     React + Vite
  engine/                  vendor KP math (no .git)
  docs/prompts/            Gem + KP + planet_taste + PRE_AUDIT_DIRECTIVE
  shared/domain_harness.py domain → payload key map (finance, marriage, …)
  telegram/                empty stub → M3
  tests/
  data/cache/charts/       JSON charts
  data/sqlite/             charts.db + usage
  data/logs/pipeline.log   live traces
```

---

## 10. Definition of “v1 complete”

- [x] Chart compute/cache parity path exists  
- [x] Web ask grounded in packet/tools  
- [x] Selective tools + MCP + traces  
- [x] Model/prompt A/B for quality testing  
- [ ] Telegram allowlisted bot  
- [ ] RAG + critic  
- [ ] Deploy story  
- [ ] Golden number tests vs Streamlit samples  

---

## 11. Immediate next action

**Implement M3 (Telegram)** unless quality work is higher priority (golden tests / critic lite).

When starting a milestone, update the status table in **§4** of this file when that milestone ships.
