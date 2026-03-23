import { postChat, type ChatMessage } from "./api";
import { createSSEParser, parseSSEDataJson } from "./sseParse";

export type UiMsg = { id: string; role: "user" | "assistant"; content: string };

/** 將目前 UI 訊息轉成 API 格式（不含空白 assistant 佔位） */
export function toApiMessages(msgs: UiMsg[]): ChatMessage[] {
  return msgs
    .filter((m) => (m.role === "user" || m.role === "assistant") && (m.role === "user" || m.content.length > 0))
    .map((m) => ({ role: m.role, content: m.content }));
}

export async function streamAssistantReply(
  apiMessages: ChatMessage[],
  options: {
    sessionId?: string | null;
    model?: string;
    onDelta: (delta: string) => void;
    onError: (message: string) => void;
  },
): Promise<{ sessionId: string | null; fatalError: string | null }> {
  const res = await postChat(apiMessages, {
    model: options.model ?? "qwen-plus",
    session_id: options.sessionId ?? undefined,
  });

  const sid = res.headers.get("X-Session-ID");

  if (!res.ok) {
    const t = await res.text();
    const msg = t || `HTTP ${res.status}`;
    options.onError(msg);
    return { sessionId: sid, fatalError: msg };
  }

  const reader = res.body?.getReader();
  if (!reader) {
    options.onError("無法讀取回應流");
    return { sessionId: sid, fatalError: "無法讀取回應流" };
  }

  let streamError: string | null = null;
  const feed = createSSEParser((ev) => {
    if (ev.event === "message") {
      const payload = parseSSEDataJson(ev.data) as {
        delta?: { content?: string };
      } | null;
      const piece = payload?.delta?.content;
      if (piece) options.onDelta(piece);
    }
    if (ev.event === "error") {
      const payload = parseSSEDataJson(ev.data) as { message?: string } | null;
      streamError = String(payload?.message ?? ev.data ?? "串流錯誤");
      options.onError(streamError);
    }
  });

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      feed(new TextDecoder().decode(value, { stream: true }));
    }
  } catch (e) {
    const msg = e instanceof Error ? e.message : "讀取中斷";
    options.onError(msg);
    return { sessionId: sid, fatalError: msg };
  }

  return { sessionId: sid, fatalError: streamError };
}
