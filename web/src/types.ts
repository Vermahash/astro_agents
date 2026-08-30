/**
 * Chat domain types for the web app.
 *
 * Purpose: model conversations, messages, and attached chart context
 * so reopening a chat restores attention to that thread.
 */

export type Role = "user" | "assistant" | "system";

export type ChatMessage = {
  id: string;
  role: Role;
  content: string;
  createdAt: string;
};

/** Chart context restored when a chat is reopened. */
export type ChartContext = {
  chartKey: string;
  name: string;
  datetimeIso: string;
  lat: number;
  lon: number;
  gender: string;
  placeLabel?: string;
  lagna?: string;
  moonNakshatra?: string;
};

export type ChatThread = {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  messages: ChatMessage[];
  chart: ChartContext | null;
};

export type ChatState = {
  chats: ChatThread[];
  activeChatId: string | null;
};
