/**
 * Chart workspace: kundali + key calculation tables from structured_payload.
 *
 * Purpose: bring Streamlit-level clarity into the portal (visual chart + data).
 */

import { useEffect, useState } from "react";
import { getChart, type ChartApiResponse } from "./api";
import { KundaliChart } from "./KundaliChart";
import type { ChartContext } from "./types";

type Props = {
  chart: ChartContext;
};

type PlanetRow = {
  planet: string;
  sign: string;
  house: string;
  degree: string;
  nak: string;
  star?: string;
  sub?: string;
};

function extractPlanetRows(payload: Record<string, unknown>): PlanetRow[] {
  const natal = payload.natal_core as
    | {
        longitudes?: Record<string, number>;
        sign_index?: Record<string, number>;
        house_from_lagna?: Record<string, number>;
        pada?: Record<string, number>;
        nakshatra_index?: Record<string, number>;
      }
    | undefined;
  const starSub = payload.planet_star_sub_lords as
    | Record<string, { star_lord?: string; sub_lord?: string; sub_sub_lord?: string }>
    | undefined;
  const signs = [
    "Aries",
    "Taurus",
    "Gemini",
    "Cancer",
    "Leo",
    "Virgo",
    "Libra",
    "Scorpio",
    "Sagittarius",
    "Capricorn",
    "Aquarius",
    "Pisces",
  ];
  const naks = [
    "Ashwini",
    "Bharani",
    "Krittika",
    "Rohini",
    "Mrigashira",
    "Ardra",
    "Punarvasu",
    "Pushya",
    "Ashlesha",
    "Magha",
    "P. Phalguni",
    "U. Phalguni",
    "Hasta",
    "Chitra",
    "Swati",
    "Vishakha",
    "Anuradha",
    "Jyeshtha",
    "Mula",
    "P. Ashadha",
    "U. Ashadha",
    "Shravana",
    "Dhanishta",
    "Shatabhisha",
    "P. Bhadrapada",
    "U. Bhadrapada",
    "Revati",
  ];

  if (!natal?.longitudes) return [];
  const rows: PlanetRow[] = [];
  for (const [planet, lon] of Object.entries(natal.longitudes)) {
    const si = natal.sign_index?.[planet] ?? Math.floor(lon / 30);
    const hi = natal.house_from_lagna?.[planet];
    const ni = natal.nakshatra_index?.[planet];
    const ss = starSub?.[planet];
    rows.push({
      planet,
      sign: signs[si % 12] ?? String(si),
      house: hi != null ? String(hi) : "—",
      degree: `${(lon % 30).toFixed(2)}°`,
      nak: ni != null ? `${naks[(ni - 1 + 27) % 27]} (${natal.pada?.[planet] ?? "—"})` : "—",
      star: ss?.star_lord,
      sub: ss?.sub_lord,
    });
  }
  return rows;
}

function cuspRows(payload: Record<string, unknown>): { house: string; sign: string; lord: string; star: string; sub: string }[] {
  const cusps = payload.cusps as
    | Record<string, { sign_index?: number; sign_lord?: string; star_lord?: string; sub_lord?: string }>
    | undefined;
  if (!cusps) return [];
  const signs = [
    "Aries",
    "Taurus",
    "Gemini",
    "Cancer",
    "Leo",
    "Virgo",
    "Libra",
    "Scorpio",
    "Sagittarius",
    "Capricorn",
    "Aquarius",
    "Pisces",
  ];
  return Array.from({ length: 12 }, (_, i) => {
    const h = String(i + 1);
    const c = cusps[h] ?? {};
    return {
      house: h,
      sign: signs[(c.sign_index ?? 0) % 12],
      lord: c.sign_lord ?? "—",
      star: c.star_lord ?? "—",
      sub: c.sub_lord ?? "—",
    };
  });
}

export function ChartWorkspace({ chart }: Props) {
  const [data, setData] = useState<ChartApiResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setErr(null);
    getChart(chart.chartKey)
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch((e) => {
        if (!cancelled) setErr(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [chart.chartKey]);

  const payload = (data?.structured_payload ?? {}) as Record<string, unknown>;
  const unified = payload.unified_kundali as { houses?: Record<string, unknown[]> } | undefined;
  const houses = (unified?.houses ?? {}) as Record<string, import("./KundaliChart").HousePlanet[]>;
  const planets = extractPlanetRows(payload);
  const cusps = cuspRows(payload);
  const dasha = (payload.kp_master_packet as { dasha?: Record<string, unknown> } | undefined)?.dasha;

  return (
    <section className="chart-workspace">
      <div className="chart-workspace-head">
        <h3>
          {chart.name}
          {chart.placeLabel ? ` · ${chart.placeLabel}` : ""}
        </h3>
        <p className="chat-meta">
          {chart.datetimeIso} · {chart.lat.toFixed(4)}, {chart.lon.toFixed(4)}
          {chart.lagna ? ` · Lagna ${chart.lagna}` : ""}
          {chart.moonNakshatra ? ` · Moon ${chart.moonNakshatra}` : ""}
        </p>
      </div>

      {loading && <p className="chat-meta">Loading chart packet…</p>}
      {err && <p className="error">{err}</p>}

      {!loading && !err && (
        <div className="chart-grid">
          <KundaliChart houses={houses} />

          <div className="data-panel">
            <h4>Planets (D1 whole-sign)</h4>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Planet</th>
                    <th>Sign</th>
                    <th>H</th>
                    <th>Deg</th>
                    <th>Nakshatra</th>
                    <th>Star</th>
                    <th>Sub</th>
                  </tr>
                </thead>
                <tbody>
                  {planets.map((r) => (
                    <tr key={r.planet}>
                      <td>{r.planet}</td>
                      <td>{r.sign}</td>
                      <td>{r.house}</td>
                      <td>{r.degree}</td>
                      <td>{r.nak}</td>
                      <td>{r.star ?? "—"}</td>
                      <td>{r.sub ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="data-panel">
            <h4>KP cusps (Placidus)</h4>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Cusp</th>
                    <th>Sign</th>
                    <th>Sign lord</th>
                    <th>Star</th>
                    <th>Sub</th>
                  </tr>
                </thead>
                <tbody>
                  {cusps.map((r) => (
                    <tr key={r.house}>
                      <td>{r.house}</td>
                      <td>{r.sign}</td>
                      <td>{r.lord}</td>
                      <td>{r.star}</td>
                      <td>{r.sub}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {dasha && (
            <div className="data-panel">
              <h4>Dasha snapshot</h4>
              <pre className="dasha-pre">{JSON.stringify(dasha, null, 2).slice(0, 2500)}</pre>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
