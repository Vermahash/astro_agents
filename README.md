# astro_agents

Work directory for the **new** KP astrology system: interactive web app + personal Telegram bot.

## Streamlit stays untouched

| Location | Role |
|----------|------|
| `B:\n8n\astro\kp-calculator` | **LIVE** Streamlit KP Calculator (GitHub `Vermahash/kpastro` @ `v2`) — do not break |
| `E:\astro_agents\engine\` | **Vendor copy** of that code for this project to import |

Do **not** point Streamlit Cloud at `E:\astro_agents`.

When you fix math in the live Streamlit repo, re-sync:

```powershell
robocopy "B:\n8n\astro\kp-calculator" "E:\astro_agents\engine" /E /XD .git __pycache__ data\runtime /NFL /NDL /NJH /NJS
```

## Layout

```
E:\astro_agents\
??? PRD.md                 # Product requirements
??? API.md                 # Service API (filled in M1)
??? engine/                # Copied KP math + Streamlit UI sources (reference)
??? api/                   # Chart/ask HTTP service (new)
??? web/                   # New interactive web app (new)
??? telegram/              # Personal Telegram bot (new)
??? shared/                # Cache, usage governor, prompt helpers
??? data/                  # sqlite, chart cache, rag index
??? docs/                  # Project docs / prompt copies
```

## Run Streamlit (unchanged, from B:)

```bash
cd /d B:\n8n\astro\kp-calculator
streamlit run astro_kp_v2.py
```

## Canonical math

`engine/astro_kp.py` ? `calculate_vedic_charts` (Krishnamurti / KP). Never reimplement in the LLM.
