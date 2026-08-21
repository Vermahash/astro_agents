# API.md — Chart & Ask service

Status: scaffold (filled during Milestone 1).

Base URL (local): `http://127.0.0.1:8080`

## Endpoints (planned)

### `POST /v1/charts`

Compute or return cached KP chart via `engine.astro_kp.calculate_vedic_charts`.

**Request**

```json
{
  "name": "string",
  "datetime_iso": "1990-01-15T14:30:00+05:30",
  "lat": 28.61,
  "lon": 77.21,
  "gender": "Unknown",
  "force_recompute": false
}
```

**Response**

```json
{
  "chart_key": "sha256...",
  "cached": true,
  "structured_payload": {},
  "engine_version": "kpastro-v2"
}
```

### `GET /v1/charts/{chart_key}`

Fetch cached chart.

### `POST /v1/ask`

Interpretive or RAG-backed question with optional `chart_key`.

### `GET /v1/usage`

Token/cost estimate for the current budget period.

## Notes

- Web app and Telegram are clients of this API.
- Live Streamlit on `B:\` does not use these endpoints.
