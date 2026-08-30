/**
 * Sidebar chat history list.
 *
 * Purpose: show all saved chats and let the user reopen one to restore context.
 */

import type { ChatThread } from "./types";

type Props = {
  chats: ChatThread[];
  activeChatId: string | null;
  onNew: () => void;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
};

function formatWhen(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export function Sidebar({ chats, activeChatId, onNew, onSelect, onDelete }: Props) {
  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <h1 className="brand">Brahma Daivagya</h1>
        <p className="brand-sub">KP charts · grounded chat</p>
        <button type="button" className="btn btn-primary" onClick={onNew}>
          New chat
        </button>
      </div>
      <ul className="chat-list">
        {chats.length === 0 && (
          <li className="chat-meta" style={{ padding: "0.75rem" }}>
            No history yet. Start a chart to create one.
          </li>
        )}
        {chats.map((chat) => (
          <li key={chat.id}>
            <div className={`chat-item-row`}>
              <button
                type="button"
                className={`chat-item ${chat.id === activeChatId ? "active" : ""}`}
                onClick={() => onSelect(chat.id)}
              >
                <span className="chat-title">{chat.title}</span>
                <span className="chat-meta">
                  {chat.chart ? chat.chart.name : "No chart yet"} · {formatWhen(chat.updatedAt)}
                </span>
              </button>
              <button
                type="button"
                className="btn-ghost"
                title="Delete chat"
                onClick={() => onDelete(chat.id)}
              >
                Delete
              </button>
            </div>
          </li>
        ))}
      </ul>
    </aside>
  );
}
