/**
 * Thin client for the local FastAPI chart service.
 *
 * Purpose: create/fetch charts used as conversation context.
 */

export type ChartApiResponse = {
  chart_key: string;
  cached: boolean;
  engine_version: string;
  meta: {
    name: string;
    datetime_iso: string;
    lat: number;
    lon: number;
    gender: string;
    lagna?: string | null;
    moon_nakshatra?: string | null;
  };
  structured_payload: Record<string, unknown>;
};

export type PlaceHit = { label: string; lat: number; lon: number };

export async function createChart(body: {
  name: string;
  datetime_iso: string;
  lat: number;
  lon: number;
  gender: string;
  force_recompute?: boolean;
}): Promise<ChartApiResponse> {
  const res = await fetch("/v1/charts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `chart failed (${res.status})`);
  }
  return res.json() as Promise<ChartApiResponse>;
}

export async function getChart(chartKey: string): Promise<ChartApiResponse> {
  const res = await fetch(`/v1/charts/${chartKey}`);
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `chart fetch failed (${res.status})`);
  }
  return res.json() as Promise<ChartApiResponse>;
}

export async function searchPlaces(q: string): Promise<PlaceHit[]> {
  if (q.trim().length < 3) return [];
  const res = await fetch(`/v1/places?q=${encodeURIComponent(q)}&limit=20`);
  if (!res.ok) return [];
  const data = (await res.json()) as { results: PlaceHit[] };
  return data.results ?? [];
}

export async function askChart(body: {
  chart_key: string;
  question: string;
  history?: { role: string; content: string }[];
  max_tokens?: number;
  model?: string;
  prompt_profile?: string;
}): Promise<{
  answer: string;
  model: string;
  chart_key: string;
  prompt_tokens: number;
  completion_tokens: number;
  estimated_cost_usd: number;
  trace_id?: string;
  tools_used?: { name: string; ms?: number; bytes?: number; ok?: boolean }[];
  mode?: string;
  prompt_profile?: string;
}> {
  const res = await fetch("/v1/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `ask failed (${res.status})`);
  }
  return res.json();
}
