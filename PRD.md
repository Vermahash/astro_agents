# Product Requirements Document: KP Astrology Platform

**Status:** Build-ready draft  
**Date:** 2026-08-21  
**Work directory:** `E:\astro_agents`  
**Frozen Streamlit (do not break):** `B:\n8n\astro\kp-calculator` (GitHub `Vermahash/kpastro` @ `v2`)  
**Implementation tracker (done + todo):** [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)

---

## 1. Problem statement

LLM astrology chats invent longitudes, cusps, and dashas. You already have a **verified KP chart engine** and a working **Streamlit KP Calculator** webpage.

This project keeps that Streamlit experience **exactly as it is**, and builds a **new platform** in `E:\astro_agents` that:

1. Reuses the same math (`calculate_vedic_charts`) via a vendor copy in `engine/`.
2. Ships a **new interactive web app** (modern UX) as the primary product surface.
3. Ships a **personal Telegram bot** for phone use when you are away from the desk.
4. Adds **RAG (HNSW)** over your books and a **critic/verify** pass.
5. Controls **API cost** with caching, compact prompts, and model routing.

---

## 2. Non?negotiable: Streamlit stays as-is

| Rule | Detail |
|------|--------|
| Live app location | `B:\n8n\astro\kp-calculator` |
| Deploy | Existing Streamlit / GitHub `v2` flow ? **unchanged** |
| Entry file | `astro_kp_v2.py` |
| Math | `astro_kp.py` in that repo remains the upstream source of truth |
| This repo | `E:\astro_agents\engine\` is a **copy** for development (`VENDOR_COPY.md`) |
| Forbidden | Pointing Streamlit Cloud at `E:\astro_agents`; ?fixing? Streamlit by rewriting it here |

**Sync policy:** When chart math is improved on `B:\`, robocopy into `E:\astro_agents\engine\` (see root README). Prefer fixing math upstream on `B:\` first so the webpage and the new apps stay aligned.

---

## 3. Product surfaces

| Surface | Audience | Role in v1 |
|---------|----------|------------|
| **Streamlit KP Calculator** | Existing validated UI | **Frozen** ? packet generation / manual Gemini copy workflow |
| **New interactive web app** (`web/`) | Primary desktop/laptop UX | Charts, Q&A, RAG, verify, profiles, usage |
| **Telegram bot** (`telegram/`) | You (whitelist) | Same backend API; phone-first commands + chat |

Both new surfaces call the same **`api/`** service. Neither replaces Streamlit.

```
                    ???????????????????????????
                    ? B:\...\kp-calculator    ?
                    ? Streamlit (FROZEN)      ?
                    ???????????????????????????

E:\astro_agents
????????????????   ????????????????   ????????????????
? web/ (new)   ????? api/         ????? telegram/    ?
????????????????   ?  + cache     ?   ????????????????
                   ?  + RAG       ?
                   ?  + critic    ?
                   ????????????????
                          ?
                   engine/ (vendor copy
                   of astro_kp*.py)
```

---

## 4. Goals & non-goals

### Goals (v1)

- Interactive web app that feels like a product (not a thin Streamlit clone).
- Telegram personal access with allowlist.
- 100% chart numbers from `engine.astro_kp.calculate_vedic_charts` (KP / Krishnamurti).
- Book RAG (HNSW) + critic pass.
- Aggressive cost control (see ?9).

### Non-goals (v1)

- Redesigning or replacing the existing Streamlit webpage.
- Parallel multi-model inference on 8GB VRAM.
- Public multi-tenant SaaS.
- Inventing Lahiri-primary charts in the new apps (engine is KP).

---

## 5. Success criteria

1. Streamlit on `B:\` still runs and deploys as today.  
2. Web app can create a chart and answer a KP question grounded in JSON.  
3. Telegram (allowlisted) can do the same via API.  
4. Same birth data ? same numbers as Streamlit (golden tests).  
5. Cached chart + compact prompts keep personal API spend near a small monthly budget.

---

## 6. Work directory layout

```
E:\astro_agents\
??? PRD.md / API.md / README.md
??? engine/          # Vendor copy of KP calculator code + docs/books/prompts
??? api/             # FastAPI (or equivalent) chart + ask service
??? web/             # New interactive web frontend
??? telegram/        # Personal bot
??? shared/          # Cache, usage governor, prompt loaders
??? data/            # sqlite, chart cache, rag index
```

---

## 7. Functional requirements

### 7.1 Chart engine (P0)

- Wrap `calculate_vedic_charts`.
- Return `structured_payload` (+ condensed view for LLMs).
- Chart cache keyed by birth inputs + `engine_version`.

### 7.2 New web app (P0)

Interactive product UI (not Streamlit):

- Birth form (city search / lat-lon / timezone).
- Chart dashboard: cusps, planets, dasha, drishti highlights from JSON.
- Chat / ask panel grounded on active chart.
- Optional ?sources? from RAG.
- Usage / budget indicator.
- Profiles (stretch if timeboxed).

UX note: one clear composition per view; chart facts are first-class, not buried in a paste box only.

### 7.3 Telegram (P0 for personal)

- Whitelist telegram user ids.
- `/chart`, free-text Q&A, `/usage`, `/clear`.
- Same API as web.

### 7.4 RAG (P1)

- Corpus from `engine/docs/books/` (+ selected PMP rules).
- Local embeddings + persistent HNSW.
- top-k chunks only.

### 7.5 Critic (P0 for interpretive answers)

- Block replies that invent numbers not in JSON.
- Chart wins over books on numerics.

---

## 8. Tech choices (defaults)

| Concern | Choice |
|---------|--------|
| Math | `engine/astro_kp.py` |
| API | FastAPI |
| Web | Modern React/Vite or Next ? decide at M2 start (interactive SPA) |
| Bot | `python-telegram-bot` or aiogram |
| DB | SQLite |
| Vectors | Chroma or FAISS/Qdrant (HNSW) |
| LLM | Gemini Flash default; NVIDIA Muse Glimmer while trial helps |
| Embeddings | Local small model |

---

## 9. Cost control & caching (mandatory)

1. **Never pay LLM for math** ? Python only.  
2. **Chart cache** ? hash(birth + engine_version).  
3. **Session active chart** ? follow-ups send small JSON slices.  
4. **Deterministic fact answers** ? no LLM when the answer is a field lookup.  
5. **Stable system prompt prefix** ? provider prompt caching.  
6. **Local embeddings** ? $0 RAG retrieve after index build.  
7. **Model ladder** ? no LLM ? Flash ? Glimmer ? `/deep` only.  
8. **Token caps** ? short completions; low reasoning by default.  
9. **Answer cache** ? repeat Q on same chart.  
10. **Budget kill-switch** ? default **$5/mo**; facts still work when LLM disabled.

Anti-patterns: multi-agent fan-out every question; pasting full payload + full books every turn; flagship models as default.

---

## 10. Milestones

| ID | Deliverable |
|----|-------------|
| **M0** | This PRD + `E:\astro_agents` scaffold + engine copy (done when accepted) |
| **M1** | `api/` chart compute + cache + golden parity vs Streamlit samples |
| **M2** | `web/` interactive MVP (chart + ask) |
| **M2.5** | Tool agent + SQLite field store + MCP chart tools (selective slices; planner fallback) |
| **M3** | `telegram/` personal bot on same API |
| **M4** | RAG HNSW + critic + usage governor |
| **M5** | Deploy story for api/web (Streamlit remains on B:\) |

Each new module ships with docstrings, README usage, API.md updates, validation, logging, and tests (per project rules).

---

## 11. Locked decisions

| Topic | Decision |
|-------|----------|
| Web stack | **React + Vite** SPA talking to FastAPI ? efficient interactive UI; scales by separating API/web; migrate host later without rewrite |
| Default LLM | **NVIDIA Muse Glimmer** first; **Gemini Flash** as cheaper/fallback |
| Monthly budget | **$5 max** hard kill-switch on paid LLM spend |
| Users | **You only** now; allowlist supports adding more Telegram/web users later |
| Host | **Laptop-only** for v1; design API/config so **VPS migration** is config/env, not a rewrite |

*(Previously open; locked 2026-08-22.)*

---

## 12. Build rule

**Streamlit on `B:\` is sacred. New work lives in `E:\astro_agents`. If a feature invents chart numbers in an LLM, it is a bug.**
