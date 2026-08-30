/**
 * Main web app shell: sidebar history + conversation + chart workspace.
 *
 * Purpose:
 *   Portal UX with place typeahead (Streamlit KP v2 parity), kundali display,
 *   and calculation tables — reopening a chat restores full context.
 */

import { useEffect, useMemo, useState, type FormEvent } from "react";
import { askChart, createChart } from "./api";
import { ChartWorkspace } from "./ChartWorkspace";
import {
  appendMessage,
  attachChart,
  createChat,
  deleteChat,
  getActiveChat,
  loadState,
  saveState,
  upsertChat,
} from "./chatStore";
import { PlaceSearch } from "./PlaceSearch";
import { Sidebar } from "./Sidebar";
import type { ChatState } from "./types";

function defaultDatetimeLocal(): string {
  const d = new Date();
  d.setSeconds(0, 0);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export default function App() {
  const [state, setState] = useState<ChatState>(() => loadState());
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [ask, setAsk] = useState("");
  const [showChart, setShowChart] = useState(true);
  const [llmModel, setLlmModel] = useState("deepseek-ai/deepseek-v4-flash-0731");
  const [promptProfile, setPromptProfile] = useState<"default" | "planet_taste">("planet_taste");

  const [name, setName] = useState("");
  const [dobLocal, setDobLocal] = useState(defaultDatetimeLocal);
  const [tzOffset, setTzOffset] = useState("+05:30");
  const [placeLabel, setPlaceLabel] = useState("");
  const [lat, setLat] = useState("");
  const [lon, setLon] = useState("");
  const [gender, setGender] = useState("Unknown");

  const active = useMemo(() => getActiveChat(state), [state]);

  useEffect(() => {
    saveState(state);
  }, [state]);

  useEffect(() => {
    if (!active?.chart) return;
    setName(active.chart.name);
    const iso = active.chart.datetimeIso;
    setDobLocal(iso.slice(0, 16));
    const m = iso.match(/([+-]\d{2}:\d{2}|Z)$/);
    if (m) setTzOffset(m[1] === "Z" ? "+00:00" : m[1]);
    setLat(String(active.chart.lat));
    setLon(String(active.chart.lon));
    setGender(active.chart.gender);
    setPlaceLabel(active.chart.placeLabel ?? "");
    setShowChart(true);
  }, [active?.id]);

  function commit(next: ChatState) {
    setState(next);
    saveState(next);
  }

  function onNew() {
    setError(null);
    setAsk("");
    const chat = createChat();
    commit(upsertChat(state, chat));
    setName("");
    setPlaceLabel("");
    setLat("");
    setLon("");
    setDobLocal(defaultDatetimeLocal());
  }

  function onSelect(id: string) {
    setError(null);
    setAsk("");
    commit({ ...state, activeChatId: id });
  }

  function onDelete(id: string) {
    commit(deleteChat(state, id));
  }

  async function onComputeChart(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!lat || !lon) {
      setError("Select a place of birth (or enter lat/lon) before computing.");
      return;
    }
    setBusy(true);
    try {
      const datetime_iso = `${dobLocal}${tzOffset}`;
      const data = await createChart({
        name: name.trim() || "Unnamed",
        datetime_iso,
        lat: Number(lat),
        lon: Number(lon),
        gender,
      });

      setState((prev) => {
        let chat = getActiveChat(prev) ?? createChat();
        chat = attachChart(chat, {
          chartKey: data.chart_key,
          name: data.meta.name,
          datetimeIso: data.meta.datetime_iso,
          lat: data.meta.lat,
          lon: data.meta.lon,
          gender: data.meta.gender,
          placeLabel: placeLabel || undefined,
          lagna: data.meta.lagna ?? undefined,
          moonNakshatra: data.meta.moon_nakshatra ?? undefined,
        });
        const summary = [
          `Chart ready${data.cached ? " (cache hit)" : ""}.`,
          placeLabel ? `Place: ${placeLabel}` : null,
          data.meta.lagna ? `Lagna: ${data.meta.lagna}` : null,
          data.meta.moon_nakshatra ? `Moon nakshatra: ${data.meta.moon_nakshatra}` : null,
          "Kundali and tables are below. This chart stays attached when you reopen the chat.",
        ]
          .filter(Boolean)
          .join("\n");
        chat = appendMessage(chat, "assistant", summary);
        const next = upsertChat(prev, chat);
        saveState(next);
        return next;
      });
      setShowChart(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function onSendAsk(e: FormEvent) {
    e.preventDefault();
    const text = ask.trim();
    if (!text) return;
    setError(null);

    const chatNow = getActiveChat(state);
    if (!chatNow?.chart) {
      setState((prev) => {
        let chat = getActiveChat(prev) ?? createChat();
        chat = appendMessage(chat, "user", text);
        chat = appendMessage(
          chat,
          "assistant",
          "No chart on this chat yet. Search a place, compute the chart, then ask.",
        );
        const next = upsertChat(prev, chat);
        saveState(next);
        return next;
      });
      setAsk("");
      return;
    }

    const history = chatNow.messages.slice(-6).map((m) => ({
      role: m.role,
      content: m.content,
    }));

    setState((prev) => {
      let chat = getActiveChat(prev)!;
      chat = appendMessage(chat, "user", text);
      const next = upsertChat(prev, chat);
      saveState(next);
      return next;
    });
    setAsk("");
    setBusy(true);

    try {
      const res = await askChart({
        chart_key: chatNow.chart.chartKey,
        question: text,
        history,
        model: llmModel,
        prompt_profile: promptProfile,
      });
      setState((prev) => {
        let chat = getActiveChat(prev)!;
        const answer = (res.answer || "").trim();
        if (!answer) {
          chat = appendMessage(
            chat,
            "assistant",
            `Ask returned empty text from ${res.model} (tokens ${res.prompt_tokens}+${res.completion_tokens}). Check pipeline.log — Muse Glimmer may have spent the budget on hidden reasoning.`,
          );
        } else {
          const toolBits =
            res.tools_used && res.tools_used.length
              ? ` · tools: ${res.tools_used.map((t) => t.name).join(", ")}`
              : res.mode
                ? ` · mode=${res.mode}`
                : "";
          const profileBit = res.prompt_profile ? ` · prompt=${res.prompt_profile}` : "";
          const footer = `\n\n— ${res.model} · ~$${res.estimated_cost_usd.toFixed(4)} · tokens ${res.prompt_tokens}+${res.completion_tokens}${toolBits}${profileBit}`;
          chat = appendMessage(chat, "assistant", answer + footer);
        }
        const next = upsertChat(prev, chat);
        saveState(next);
        return next;
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
      setState((prev) => {
        let chat = getActiveChat(prev)!;
        chat = appendMessage(chat, "assistant", `Ask failed: ${msg}`);
        const next = upsertChat(prev, chat);
        saveState(next);
        return next;
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="app-shell">
      <Sidebar
        chats={state.chats}
        activeChatId={state.activeChatId}
        onNew={onNew}
        onSelect={onSelect}
        onDelete={onDelete}
      />

      <main className="main">
        <header className="main-header">
          <h2>{active?.title ?? "Welcome"}</h2>
          <div className="header-actions">
            {active?.chart && (
              <>
                <span className="context-pill">
                  Context: {active.chart.name}
                  {active.chart.lagna ? ` · ${active.chart.lagna}` : ""}
                </span>
                <button type="button" className="btn" onClick={() => setShowChart((v) => !v)}>
                  {showChart ? "Hide chart" : "Show chart"}
                </button>
              </>
            )}
          </div>
        </header>

        <div className="messages">
          {!active && (
            <div className="welcome">
              <h1>Brahma Daivagya</h1>
              <p>
                Search place of birth (same city DB as KP Streamlit), compute the chart, see the
                kundali and tables — every chat stays in the sidebar with full context.
              </p>
              <button type="button" className="btn btn-primary" onClick={onNew}>
                New chat
              </button>
            </div>
          )}

          {active?.messages.map((m) => (
            <div key={m.id} className={`bubble ${m.role}`}>
              {m.content}
            </div>
          ))}

          {active?.chart && showChart && <ChartWorkspace chart={active.chart} />}
        </div>

        {active && (
          <div className="composer">
            <form className="chart-form" onSubmit={onComputeChart}>
              <label className="wide">
                Name
                <input value={name} onChange={(e) => setName(e.target.value)} required />
              </label>
              <label className="wide">
                Birth (local)
                <input
                  type="datetime-local"
                  value={dobLocal}
                  onChange={(e) => setDobLocal(e.target.value)}
                  required
                />
              </label>
              <label>
                TZ offset
                <input value={tzOffset} onChange={(e) => setTzOffset(e.target.value)} required />
              </label>
              <label>
                Gender
                <select value={gender} onChange={(e) => setGender(e.target.value)}>
                  <option>Unknown</option>
                  <option>Male</option>
                  <option>Female</option>
                  <option>Other</option>
                </select>
              </label>

              <div className="place-span">
                <PlaceSearch
                  value={placeLabel}
                  onLabelChange={setPlaceLabel}
                  onSelect={(hit) => {
                    setPlaceLabel(hit.label);
                    setLat(String(hit.lat));
                    setLon(String(hit.lon));
                  }}
                />
              </div>

              <label>
                Lat
                <input value={lat} onChange={(e) => setLat(e.target.value)} required placeholder="auto" />
              </label>
              <label>
                Lon
                <input value={lon} onChange={(e) => setLon(e.target.value)} required placeholder="auto" />
              </label>
              <label style={{ alignSelf: "end" }}>
                <span style={{ visibility: "hidden" }}>go</span>
                <button className="btn btn-primary" type="submit" disabled={busy}>
                  {busy ? "Computing…" : active.chart ? "Recompute chart" : "Compute chart"}
                </button>
              </label>
            </form>

            <div className="ask-controls">
              <label>
                Model
                <select value={llmModel} onChange={(e) => setLlmModel(e.target.value)}>
                  <option value="deepseek-ai/deepseek-v4-flash-0731">DeepSeek V4 Flash</option>
                  <option value="meta/muse-glimmer-30b">Muse Glimmer 30B</option>
                  <option value="minimaxai/minimax-m3">MiniMax M3 (often 429)</option>
                </select>
              </label>
              <label>
                Prompt
                <select
                  value={promptProfile}
                  onChange={(e) => setPromptProfile(e.target.value as "default" | "planet_taste")}
                >
                  <option value="planet_taste">Planet taste (placement A/B)</option>
                  <option value="default">Default Gem + KP strict</option>
                </select>
              </label>
            </div>

            <form className="ask-row" onSubmit={onSendAsk}>
              <textarea
                value={ask}
                onChange={(e) => setAsk(e.target.value)}
                placeholder={
                  active.chart
                    ? `Ask about ${active.chart.name}'s chart…`
                    : "Ask anything (attach a chart first for KP grounding)…"
                }
              />
              <button className="btn" type="submit">
                Send
              </button>
            </form>

            {error && <div className="error">{error}</div>}
          </div>
        )}
      </main>
    </div>
  );
}
