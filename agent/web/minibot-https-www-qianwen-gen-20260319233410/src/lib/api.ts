const CLIENT_ID_KEY = "minibot_x_client_id";

/** 后端要求 X-Client-ID；浏览器内持久化一个 UUID */
export function getOrCreateClientId(): string {
  if (typeof window === "undefined") return "ssr-placeholder";
  try {
    let id = window.localStorage.getItem(CLIENT_ID_KEY);
    if (!id) {
      id =
        typeof crypto !== "undefined" && "randomUUID" in crypto
          ? crypto.randomUUID()
          : `client-${Date.now()}`;
      window.localStorage.setItem(CLIENT_ID_KEY, id);
    }
    return id;
  } catch {
    return `client-${Date.now()}`;
  }
}

/**
 * 浏览器走 Vite 代理 /api -> http://127.0.0.1:8000（见 vite.config.ts）。
 */
export const API_BASE = "/api";

export type ChatMessage = { role: "user" | "assistant"; content: string };

export function apiJsonHeaders(): HeadersInit {
  return {
    "Content-Type": "application/json",
    "X-Client-ID": getOrCreateClientId(),
  };
}

export function apiClientHeaders(): HeadersInit {
  return { "X-Client-ID": getOrCreateClientId() };
}

/** POST /v2/chat，返回 Response（可讀取 X-Session-ID 與 body stream） */
export async function postChat(
  messages: ChatMessage[],
  options?: { model?: string; session_id?: string | null },
): Promise<Response> {
  const body: Record<string, unknown> = {
    messages,
    model: options?.model ?? "qwen-plus",
  };
  if (options?.session_id) body.session_id = options.session_id;
  return fetch(`${API_BASE}/v2/chat`, {
    method: "POST",
    headers: apiJsonHeaders(),
    body: JSON.stringify(body),
  });
}

export type SessionSummary = {
  session_id: string;
  title: string;
  updated_at: string;
  last_preview: string;
};

export async function fetchSessions(): Promise<{ sessions: SessionSummary[] }> {
  const r = await fetch(`${API_BASE}/v2/sessions`, { headers: apiClientHeaders() });
  if (!r.ok) {
    const t = await r.text();
    throw new Error(`載入歷史失敗 ${r.status}: ${t || r.statusText}`);
  }
  return r.json();
}

export async function fetchSession(sessionId: string): Promise<{
  session_id: string;
  title: string;
  messages: ChatMessage[];
  updated_at: string;
}> {
  const r = await fetch(`${API_BASE}/v2/sessions/${encodeURIComponent(sessionId)}`, {
    headers: apiClientHeaders(),
  });
  if (!r.ok) {
    const t = await r.text();
    throw new Error(`載入對話失敗 ${r.status}: ${t || r.statusText}`);
  }
  return r.json();
}

export async function patchSessionTitle(
  sessionId: string,
  title: string,
): Promise<{ id: string; title: string; updated_at: string }> {
  const r = await fetch(`${API_BASE}/v2/chat/${encodeURIComponent(sessionId)}/title`, {
    method: "PATCH",
    headers: apiJsonHeaders(),
    body: JSON.stringify({ title }),
  });
  if (!r.ok) {
    const t = await r.text();
    throw new Error(`更新標題失敗 ${r.status}: ${t || r.statusText}`);
  }
  return r.json();
}

/** 舊版簡化呼叫（單句 user） */
export const chatStream = async (input: string, model: string = "qwen-plus") => {
  const response = await postChat([{ role: "user", content: input }], { model });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }
  if (response.headers.get("content-type") !== "text/event-stream") {
    throw new Error("Expected text/event-stream response");
  }
  return response.body?.getReader();
};
