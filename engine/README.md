# KP Calculator — Brahma-Daivagya

GitHub: [Vermahash/kpastro](https://github.com/Vermahash/kpastro) (branch `v2`)

Validated KP chart engine + slim Streamlit UI. **All numerics live in `astro_kp.py`.** The UI never reimplements math.

## Quick start

```bash
pip install -r requirements.txt
streamlit run astro_kp_v2.py
```

## Layout

```
kp-calculator/
├── astro_kp.py              # Core Swiss Ephemeris / KP engine
├── astro_kp_v2.py           # Streamlit frontend (deploy entrypoint)
├── yoga_engine.py
├── kp_logic.py / kp_master_rules.py / kp_book_rules.py / kp_cusp_legacy.py
├── kp_book_ingest.py
├── global_cities_full.csv   # City DB (must stay next to engine)
├── docs/
│   ├── prompts/             # Gemini_instructionsKP*.md + pmp/
│   ├── books/               # Reference PDFs
│   └── formulas/            # KP formula docs
├── tests/
├── data/runtime/            # Local session/runtime artifacts
└── .extracted/              # Book ingest outputs
```

## Packet → Gemini

Copy the UI `structured_payload` / master packet and pair with:

- `docs/prompts/Gemini_instructionsKP.md`
- `docs/prompts/Gemini_instructionsKP_karma_alignment.md`

## Do not use

Older Parashari Streamlit apps live under `../archive/legacy-streamlit/` (`astro_app_v2_1.py`, etc.).
