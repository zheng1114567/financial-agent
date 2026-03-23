/**
 * 累積 SSE 文本塊並解析為完整事件（event + data），處理跨 chunk 截斷。
 */
export type SSEvent = { event: string; data: unknown };

export function consumeSSEBuffer(
  buffer: string,
  chunk: string,
): { events: SSEvent[]; rest: string } {
  const text = buffer + chunk;
  const parts = text.split("\n\n");
  const completeBlocks = parts.slice(0, -1);
  const rest = parts[parts.length - 1] ?? "";

  const events: SSEvent[] = [];
  for (const block of completeBlocks) {
    const trimmed = block.trim();
    if (!trimmed) continue;

    let eventName = "message";
    const dataLines: string[] = [];
    for (const line of trimmed.split("\n")) {
      const l = line.trim();
      if (!l) continue;
      if (l.startsWith("event:")) eventName = l.slice(6).trim();
      else if (l.startsWith("data:")) dataLines.push(l.slice(5).trim());
    }
    const dataStr = dataLines.join("\n");
    let data: unknown = dataStr;
    try {
      data = dataStr ? JSON.parse(dataStr) : {};
    } catch {
      /* 保留字串 */
    }
    events.push({ event: eventName, data });
  }
  return { events, rest };
}
