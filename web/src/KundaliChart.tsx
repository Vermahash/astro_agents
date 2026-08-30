/**
 * South-Indian rasi kundali from unified_kundali (whole-sign houses).
 *
 * Purpose: fixed-sign grid with house numbers counted from Lagna — same
 * geometry most KP/Parashari tools use for clarity.
 *
 * Sign boxes (clockwise from top-left Pisces):
 *   Pi Ar Ta Ge
 *   Aq       Cn
 *   Cp       Le
 *   Sg Sc Li Vi
 */

export type HousePlanet = {
  planet?: string | null;
  sign?: string;
  sign_index?: number;
  degree_dms?: string;
  retro_marker?: string;
  bhava_shift?: boolean;
  bhava_house?: number;
};

const ABBR: Record<string, string> = {
  Lagna: "Asc",
  Sun: "Su",
  Moon: "Mo",
  Mars: "Ma",
  Mercury: "Me",
  Jupiter: "Ju",
  Venus: "Ve",
  Saturn: "Sa",
  Rahu: "Ra",
  Ketu: "Ke",
};

const SIGN_SHORT = ["Ar", "Ta", "Ge", "Cn", "Le", "Vi", "Li", "Sc", "Sg", "Cp", "Aq", "Pi"];

/** Cell order in 4×4 SI chart (null = center gap). */
const GRID: (number | null)[][] = [
  [11, 0, 1, 2],
  [10, null, null, 3],
  [9, null, null, 4],
  [8, 7, 6, 5],
];

type Props = {
  houses: Record<string, HousePlanet[]>;
  title?: string;
};

function bySignIndex(houses: Record<string, HousePlanet[]>): Map<number, HousePlanet[]> {
  const map = new Map<number, HousePlanet[]>();
  for (let h = 1; h <= 12; h++) {
    const entries = houses[`H${h}`] ?? [];
    const signIdx = entries.find((e) => e.sign_index != null)?.sign_index;
    if (signIdx == null) continue;
    map.set(signIdx, entries);
  }
  return map;
}

function ascSignIndex(houses: Record<string, HousePlanet[]>): number {
  const h1 = houses.H1 ?? [];
  const lagna = h1.find((e) => e.planet === "Lagna") ?? h1[0];
  return lagna?.sign_index ?? 0;
}

function houseNumber(signIdx: number, ascIdx: number): number {
  return ((signIdx - ascIdx + 12) % 12) + 1;
}

export function KundaliChart({ houses, title = "D1 Rasi · South Indian (houses from Lagna)" }: Props) {
  const bySign = bySignIndex(houses);
  const ascIdx = ascSignIndex(houses);

  return (
    <div className="kundali-wrap">
      <div className="kundali-title">{title}</div>
      <div className="si-grid" role="img" aria-label="South Indian kundali">
        {GRID.flatMap((row, ri) =>
          row.map((signIdx, ci) => {
            if (signIdx == null) {
              return <div key={`g-${ri}-${ci}`} className="si-cell si-empty" />;
            }
            const entries = bySign.get(signIdx) ?? [];
            const hNum = houseNumber(signIdx, ascIdx);
            const planets = entries
              .filter((e) => e.planet)
              .map((e) => {
                const ab = ABBR[e.planet!] ?? e.planet!.slice(0, 2);
                const r = e.retro_marker?.includes("R") ? "(R)" : "";
                return `${ab}${r}`;
              });
            const isLagna = hNum === 1;
            return (
              <div key={signIdx} className={`si-cell ${isLagna ? "si-lagna" : ""}`}>
                <div className="si-top">
                  <span className="si-house">{hNum}</span>
                  <span className="si-sign">{SIGN_SHORT[signIdx]}</span>
                </div>
                <div className="si-planets">{planets.length ? planets.join(" ") : "—"}</div>
              </div>
            );
          }),
        )}
      </div>
      <p className="kundali-legend">
        Numbers = whole-sign houses from Lagna (1 highlighted). Signs are fixed (South Indian).
        Asc Su Mo Ma Me Ju Ve Sa Ra Ke · (R) retrograde.
      </p>
    </div>
  );
}
