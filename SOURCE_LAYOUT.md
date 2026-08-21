# Astro workspace (`B:\n8n\astro`)

Clean layout after consolidating the old mixed folders (`books kp`, `backup`, `ocr`, `Parsers`, `Prompts`).

## Layout

```
astro/
├── kp-calculator/     # LIVE app + git repo (Vermahash/kpastro @ v2)
├── knowledge/         # Shared prompt scraps not tied to one deploy
├── tools/             # OCR toolkit, parsers/verifiers
└── archive/           # Old Streamlit apps, old KP snapshots, book-pipeline notes
```

## Product plan

- **[PRD.md](PRD.md)** — Personal Telegram KP agent, RAG, critic, and **API cost/caching** rules.  
- Supersedes the older MapReduce/Lahiri draft in `E:\astro_agents`.

## Use this for charts

| Path | Role |
|------|------|
| `kp-calculator/astro_kp.py` | **Canonical math** — `calculate_vedic_charts` |
| `kp-calculator/astro_kp_v2.py` | Streamlit UI (KP MASTER DATA PACKET) |
| `kp-calculator/docs/prompts/` | Gemini / PMP instruction packs |
| `kp-calculator/docs/books/` | Source PDFs for RAG / reference |
| `archive/legacy-streamlit/` | Old `astro_app_v2_1.py` etc. — **do not use for new work** |

## Run locally

```bash
cd kp-calculator
pip install -r requirements.txt
streamlit run astro_kp_v2.py
```

Streamlit Cloud / Codespaces still expects `astro_kp_v2.py` at the **repo root** (this folder).
