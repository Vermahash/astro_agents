/**
 * localStorage-backed chat history.
 *
 * Purpose: persist threads so sidebar history survives refresh and
 * selecting an old chat restores messages + chart context.
 *
 * Later: swap implementation for API/SQLite without changing UI callers.
 */

import type { ChatMessage, ChatState, ChatThread, ChartContext } from "./types";

const STORAGE_KEY = "astro_agents_chats_v1";

function uid(): string {
  return crypto.randomUUID();
}

function nowIso(): string {
  return new Date().toISOString();
}

export function loadState(): ChatState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { chats: [], activeChatId: null };
    const parsed = JSON.parse(raw) as ChatState;
    if (!Array.isArray(parsed.chats)) return { chats: [], activeChatId: null };
    return parsed;
  } catch {
    return { chats: [], activeChatId: null };
  }
}

export function saveState(state: ChatState): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

export function createChat(title = "New chart"): ChatThread {
  const ts = nowIso();
  return {
    id: uid(),
    title,
    createdAt: ts,
    updatedAt: ts,
    messages: [],
    chart: null,
  };
}

export function sortChats(chats: ChatThread[]): ChatThread[] {
  return [...chats].sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
}

export function upsertChat(state: ChatState, chat: ChatThread): ChatState {
  const others = state.chats.filter((c) => c.id !== chat.id);
  return {
    chats: sortChats([...others, { ...chat, updatedAt: nowIso() }]),
    activeChatId: chat.id,
  };
}

export function deleteChat(state: ChatState, chatId: string): ChatState {
  const chats = state.chats.filter((c) => c.id !== chatId);
  const activeChatId =
    state.activeChatId === chatId ? (chats[0]?.id ?? null) : state.activeChatId;
  return { chats, activeChatId };
}

export function appendMessage(
  chat: ChatThread,
  role: ChatMessage["role"],
  content: string,
): ChatThread {
  const msg: ChatMessage = {
    id: uid(),
    role,
    content,
    createdAt: nowIso(),
  };
  return {
    ...chat,
    updatedAt: nowIso(),
    messages: [...chat.messages, msg],
  };
}

export function attachChart(chat: ChatThread, chart: ChartContext): ChatThread {
  const title =
    chat.messages.length === 0 && chat.title === "New chart"
      ? `${chart.name} · chart`
      : chat.title;
  return {
    ...chat,
    title,
    chart,
    updatedAt: nowIso(),
  };
}

export function getActiveChat(state: ChatState): ChatThread | null {
  if (!state.activeChatId) return null;
  return state.chats.find((c) => c.id === state.activeChatId) ?? null;
}
