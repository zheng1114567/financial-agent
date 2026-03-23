export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
};

export type SessionMeta = {
  session_id: string;
  title: string;
  updated_at: string;
  preview: string;
};

const SESSIONS_KEY = "minibot_sessions_v1";

function msgKey(sessionId: string) {
  return `minibot_messages_${sessionId}`;
}

export function loadSessionList(): SessionMeta[] {
  try {
    const raw = localStorage.getItem(SESSIONS_KEY);
    if (!raw) return [];
    const arr = JSON.parse(raw) as SessionMeta[];
    return Array.isArray(arr) ? arr : [];
  } catch {
    return [];
  }
}

export function saveSessionList(list: SessionMeta[]) {
  localStorage.setItem(SESSIONS_KEY, JSON.stringify(list));
}

export function upsertSessionMeta(meta: SessionMeta) {
  const list = loadSessionList().filter((s) => s.session_id !== meta.session_id);
  list.push(meta);
  list.sort((a, b) => (a.updated_at < b.updated_at ? 1 : -1));
  saveSessionList(list);
}

export function loadMessages(sessionId: string): ChatMessage[] {
  try {
    const raw = localStorage.getItem(msgKey(sessionId));
    if (!raw) return [];
    const arr = JSON.parse(raw) as ChatMessage[];
    return Array.isArray(arr) ? arr : [];
  } catch {
    return [];
  }
}

export function saveMessages(sessionId: string, messages: ChatMessage[]) {
  localStorage.setItem(msgKey(sessionId), JSON.stringify(messages));
}

export function deleteSession(sessionId: string) {
  saveSessionList(loadSessionList().filter((s) => s.session_id !== sessionId));
  localStorage.removeItem(msgKey(sessionId));
}

export function newMessageId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `m_${Date.now()}_${Math.random().toString(16).slice(2)}`;
}
