/**
 * Place-of-birth typeahead (Streamlit KP v2 parity).
 *
 * Purpose: search local city DB via API and autofill lat/lon while typing.
 */

import { useEffect, useId, useRef, useState } from "react";
import { searchPlaces, type PlaceHit } from "./api";

type Props = {
  label?: string;
  value: string;
  onLabelChange: (label: string) => void;
  onSelect: (hit: PlaceHit) => void;
};

export function PlaceSearch({ label = "Place of birth", value, onLabelChange, onSelect }: Props) {
  const listId = useId();
  const [hits, setHits] = useState<PlaceHit[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (value.trim().length < 3) {
      setHits([]);
      return;
    }
    let cancelled = false;
    const t = window.setTimeout(() => {
      setLoading(true);
      searchPlaces(value)
        .then((r) => {
          if (!cancelled) {
            setHits(r);
            setOpen(true);
          }
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    }, 220);
    return () => {
      cancelled = true;
      window.clearTimeout(t);
    };
  }, [value]);

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (!boxRef.current?.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  return (
    <div className="place-search" ref={boxRef}>
      <label>
        {label}
        <input
          value={value}
          placeholder="Type at least 3 letters (city)…"
          autoComplete="off"
          aria-autocomplete="list"
          aria-controls={listId}
          onChange={(e) => {
            onLabelChange(e.target.value);
            setOpen(true);
          }}
          onFocus={() => hits.length && setOpen(true)}
        />
      </label>
      {loading && <span className="place-hint">Searching…</span>}
      {open && hits.length > 0 && (
        <ul id={listId} className="place-dropdown" role="listbox">
          {hits.map((h) => (
            <li key={`${h.label}-${h.lat}-${h.lon}`}>
              <button
                type="button"
                onClick={() => {
                  onSelect(h);
                  onLabelChange(h.label);
                  setOpen(false);
                }}
              >
                <span>{h.label}</span>
                <span className="place-coords">
                  {h.lat.toFixed(4)}, {h.lon.toFixed(4)}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
